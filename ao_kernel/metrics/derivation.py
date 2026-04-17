"""Evidence events → Prometheus metric population (PR-B5 C3).

Evidence / run_store / coordination-SSOT read pipeline. Fail-closed
on malformed JSONL per :class:`EvidenceSourceCorruptedError` (mirrors
the ``timeline.py`` internal pattern). No filtering / windowing —
plan v4 §2.3 dropped ``run_id_filter`` / ``since_ts`` from the
default textfile mode because Prometheus counter semantics require
cumulative full scans.

.. note::
   The :func:`ao_kernel.coordination.registry.live_claims_count` hook
   acquires ``claims.lock`` to read the claim SSOT; on a workspace
   with coordination enabled, the lockfile is created on first
   metrics scrape. No claim files are mutated.

The one-way flow is:

    events.jsonl lines → event dicts → per-kind handler → metric family

Cancelled workflow runs take a separate branch: the coordination
runtime never emits a ``workflow_cancelled`` event (denial path emits
``approval_denied`` and transitions run state). So the workflow
duration histogram reads ``state.v1.json.completed_at`` for cancelled
runs via :func:`ao_kernel.workflow.run_store.list_terminal_runs`
(plan v4 Q3 A).

The claim active gauge is populated from
:func:`ao_kernel.coordination.registry.live_claims_count` rather than
an evidence-derived net count — expired/takeover races make the net
count negative (plan v4 Q1 A).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ao_kernel.coordination.registry import live_claims_count
from ao_kernel.metrics.errors import EvidenceSourceCorruptedError
from ao_kernel.metrics.policy import MetricsPolicy
from ao_kernel.metrics.registry import BuiltRegistry
from ao_kernel.workflow.run_store import list_terminal_runs


_WORKFLOW_STARTED = "workflow_started"
_WORKFLOW_COMPLETED = "workflow_completed"
_WORKFLOW_FAILED = "workflow_failed"
_LLM_SPEND = "llm_spend_recorded"
_LLM_USAGE_MISSING = "llm_usage_missing"
_POLICY_CHECKED = "policy_checked"
_CLAIM_TAKEOVER = "claim_takeover"

_TERMINAL_STATES = frozenset({"completed", "failed", "cancelled"})


@dataclass
class DerivationStats:
    """Summary of a derivation pass, exposed for CLI verbose output and
    regression tests.

    ``duration_ms_missing`` tracks the plan v4 R13 backward-compat
    branch: pre-B5 ``llm_spend_recorded`` events without the
    ``duration_ms`` field are counted here and skipped for histogram
    population (no synthetic default).
    """

    events_scanned: int = 0
    runs_scanned: int = 0
    llm_spend_counted: int = 0
    llm_usage_missing_counted: int = 0
    policy_checks_counted: int = 0
    claim_takeovers_counted: int = 0
    workflow_terminals_counted: int = 0
    cancelled_from_state: int = 0
    duration_ms_missing: int = 0
    corrupt_files: tuple[Path, ...] = field(default_factory=tuple)


def _parse_iso(ts: str) -> datetime:
    """Parse ISO-8601 timestamp into aware UTC datetime.

    Mirrors ``coordination.registry._parse_iso`` so derivation and
    coordination agree on the same ``Z`` shorthand handling.
    """
    normalised = ts.replace("Z", "+00:00") if ts.endswith("Z") else ts
    dt = datetime.fromisoformat(normalised)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _events_for_run(run_dir: Path) -> list[dict[str, Any]]:
    """Read + parse ``events.jsonl`` under ``run_dir``.

    Raises :class:`EvidenceSourceCorruptedError` on any malformed line
    (fail-closed per CLAUDE.md §2). Returns ``[]`` when the file is
    absent or empty — a run directory without evidence is not an
    error (e.g., a created-state run that never reached execution).
    """
    events_path = run_dir / "events.jsonl"
    if not events_path.is_file():
        return []
    events: list[dict[str, Any]] = []
    text = events_path.read_text(encoding="utf-8")
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            events.append(json.loads(stripped))
        except json.JSONDecodeError as exc:
            raise EvidenceSourceCorruptedError(
                f"malformed JSONL at {events_path}:{lineno}: {exc}"
            ) from exc
    return events


def _iter_run_directories(workspace_root: Path) -> list[Path]:
    """Return all run directories under ``.ao/evidence/workflows/``.

    Each child is a ``run_id`` directory containing ``events.jsonl``
    and optional adapter logs. Returns ``[]`` for an empty workspace
    (dormant parity — no raise).
    """
    root = workspace_root / ".ao" / "evidence" / "workflows"
    if not root.is_dir():
        return []
    return [d for d in sorted(root.iterdir()) if d.is_dir()]


def _apply_llm_spend(
    built: BuiltRegistry,
    payload: dict[str, Any],
    advanced_model: bool,
) -> tuple[bool, bool]:
    """Populate LLM counters + (maybe) duration histogram from a
    single ``llm_spend_recorded`` payload.

    Returns ``(spend_counted, duration_missing)``: the caller uses
    these for DerivationStats bookkeeping. ``duration_missing=True``
    signals the plan v4 R13 backward-compat branch (pre-B5 event
    without ``duration_ms``).
    """
    cost_family = built.llm_cost_usd
    tokens_family = built.llm_tokens_used
    if cost_family is None or tokens_family is None:
        # Cost-disjunction branch: registry was built without LLM
        # families (see :func:`build_registry(..., include_llm_metrics=False)`).
        return False, False

    provider = str(payload.get("provider_id") or "unknown")
    model = str(payload.get("model") or "unknown")
    base_labels = {"provider": provider}
    if advanced_model:
        base_labels["model"] = model

    # tokens counter (3 directions: input / output / cached)
    for direction, field_name in (
        ("input", "tokens_input"),
        ("output", "tokens_output"),
        ("cached", "cached_tokens"),
    ):
        raw = payload.get(field_name)
        if raw is None:
            continue
        try:
            count = int(raw)
        except (TypeError, ValueError):
            continue
        if count <= 0:
            continue
        labels = {**base_labels, "direction": direction}
        tokens_family.labels(**labels).inc(count)

    # cost counter (≥0)
    cost_raw = payload.get("cost_usd")
    if cost_raw is not None:
        try:
            cost = float(cost_raw)
        except (TypeError, ValueError):
            cost = 0.0
        if cost > 0:
            cost_family.labels(**base_labels).inc(cost)

    # duration histogram (plan v4 R13 backward-compat)
    duration_missing = False
    duration_raw = payload.get("duration_ms")
    if duration_raw is None:
        duration_missing = True
    else:
        try:
            duration_ms = float(duration_raw)
        except (TypeError, ValueError):
            duration_missing = True
        else:
            duration_family = built.llm_call_duration
            if duration_ms >= 0 and duration_family is not None:
                duration_family.labels(**base_labels).observe(
                    duration_ms / 1000.0,
                )

    return True, duration_missing


def _apply_usage_missing(
    built: BuiltRegistry,
    payload: dict[str, Any],
    advanced_model: bool,
) -> bool:
    family = built.llm_usage_missing
    if family is None:
        return False
    provider = str(payload.get("provider_id") or "unknown")
    labels = {"provider": provider}
    if advanced_model:
        labels["model"] = str(payload.get("model") or "unknown")
    family.labels(**labels).inc()
    return True


def _apply_policy_checked(
    built: BuiltRegistry, payload: dict[str, Any]
) -> bool:
    violations_raw = payload.get("violations_count")
    try:
        violations = int(violations_raw or 0)
    except (TypeError, ValueError):
        violations = 0
    outcome = "deny" if violations > 0 else "allow"
    built.policy_check.labels(outcome=outcome).inc()
    return True


def _apply_claim_takeover(built: BuiltRegistry) -> bool:
    built.claim_takeover.inc()
    return True


def _apply_workflow_duration(
    built: BuiltRegistry,
    started_ts: str,
    completed_ts: str,
    final_state: str,
) -> bool:
    try:
        delta = (
            _parse_iso(completed_ts) - _parse_iso(started_ts)
        ).total_seconds()
    except (TypeError, ValueError):
        return False
    if delta < 0:
        return False
    built.workflow_duration.labels(final_state=final_state).observe(delta)
    return True


def _apply_claim_active(
    built: BuiltRegistry,
    workspace_root: Path,
    advanced_agent_id: bool,
) -> None:
    try:
        counts = live_claims_count(workspace_root)
    except Exception:
        # Coordination subsystem errors (dormant policy, corrupted
        # claim file) are fail-open for the gauge: an observability
        # surface should not crash because a different subsystem is
        # unhealthy. The operator is expected to run
        # ``ao-kernel doctor`` if the gauge reports 0.
        counts = {}
    if advanced_agent_id:
        for agent_id, count in counts.items():
            built.claim_active.labels(agent_id=agent_id).set(count)
    else:
        total = sum(counts.values())
        built.claim_active.set(total)


def derive_metrics_from_evidence(
    workspace_root: Path,
    built: BuiltRegistry,
    policy: MetricsPolicy,
) -> DerivationStats:
    """Populate ``built`` with metrics derived from the workspace's
    evidence trail + coordination registry + run_store.

    Fail-closed behaviour:

    - Malformed JSONL → :class:`EvidenceSourceCorruptedError` (no
      partial metrics — a corrupt audit trail cannot be trusted).
    - Missing workspace (``.ao/evidence/workflows/`` absent) → stats
      reflect zero scans; the caller / CLI surfaces a dormant banner.
    """
    stats = DerivationStats()
    allowlist = policy.advanced_allowlist()
    advanced_model = "model" in allowlist
    advanced_agent_id = "agent_id" in allowlist

    # Track workflow_started payloads so we can compute duration on
    # the paired terminal event emitted later in the file.
    started_ts_by_run: dict[str, str] = {}

    run_dirs = _iter_run_directories(workspace_root)
    for run_dir in run_dirs:
        stats.runs_scanned += 1
        events = _events_for_run(run_dir)
        for event in events:
            stats.events_scanned += 1
            kind = event.get("kind")
            payload = event.get("payload") or {}
            if kind == _LLM_SPEND:
                spend_counted, duration_missing = _apply_llm_spend(
                    built, payload, advanced_model,
                )
                if spend_counted:
                    stats.llm_spend_counted += 1
                if duration_missing:
                    stats.duration_ms_missing += 1
            elif kind == _LLM_USAGE_MISSING:
                if _apply_usage_missing(built, payload, advanced_model):
                    stats.llm_usage_missing_counted += 1
            elif kind == _POLICY_CHECKED:
                if _apply_policy_checked(built, payload):
                    stats.policy_checks_counted += 1
            elif kind == _CLAIM_TAKEOVER:
                if _apply_claim_takeover(built):
                    stats.claim_takeovers_counted += 1
            elif kind == _WORKFLOW_STARTED:
                ts = event.get("ts") or payload.get("ts")
                run_id = payload.get("run_id") or run_dir.name
                if ts:
                    started_ts_by_run[run_id] = str(ts)
            elif kind in (_WORKFLOW_COMPLETED, _WORKFLOW_FAILED):
                ts = event.get("ts") or payload.get("ts")
                run_id = payload.get("run_id") or run_dir.name
                started = started_ts_by_run.pop(run_id, None)
                if started and ts:
                    final_state = (
                        "completed"
                        if kind == _WORKFLOW_COMPLETED
                        else "failed"
                    )
                    if _apply_workflow_duration(
                        built, started, str(ts), final_state,
                    ):
                        stats.workflow_terminals_counted += 1

    # Plan v4 Q3 A: cancelled runs have no terminal event — derive
    # duration from ``state.v1.json.{created_at, completed_at}``.
    for record in list_terminal_runs(workspace_root):
        if record.get("state") != "cancelled":
            continue
        started = record.get("created_at")
        completed = record.get("completed_at")
        if not (started and completed):
            continue
        if _apply_workflow_duration(
            built, str(started), str(completed), "cancelled",
        ):
            stats.cancelled_from_state += 1

    _apply_claim_active(built, workspace_root, advanced_agent_id)

    return stats


__all__ = [
    "DerivationStats",
    "derive_metrics_from_evidence",
]
