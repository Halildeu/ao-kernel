"""Scorecard collector — pytest plugin that harvests benchmark runs.

Registered on ``tests/benchmarks/conftest.py``. Canonical input rule:
exactly one test per scenario carries ``@pytest.mark.scorecard_primary``.
Duplicates and missing-primary both fail-close at session finish
(Codex iter-2 AGREE tighten #3).

Scenario ids the collector expects to see at least once are declared in
``EXPECTED_PRIMARY_SCENARIOS`` so the zero-primary path is explicit.

The collector is schema-aware but not strictly schema-validating at
write time — strict validation runs in the compare path (SSOT on the
artefact consumer, not producer).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


logger = logging.getLogger(__name__)


EXPECTED_PRIMARY_SCENARIOS: frozenset[str] = frozenset(
    {"governed_bugfix", "governed_review"},
)
"""Canonical scenarios the benchmark suite is expected to exercise.

When the collector runs and finds no ``scorecard_primary``-marked tests
AND this set is non-empty, the session is failed (zero-primary guard).
Relax this to ``frozenset()`` in downstream harnesses that intentionally
run a subset.
"""


DEFAULT_OUTPUT_FILENAME = "benchmark_scorecard.v1.json"


@dataclass(frozen=True)
class PrimarySidecar:
    """Record produced by a primary-marked test and consumed by the
    session-finish hook.

    - ``run_dir`` — the evidence directory (``events.jsonl`` is there).
    - ``run_state_path`` — canonical run-state JSON (typically
      ``.ao/runs/<run_id>/state.v1.json``). Kept separate from
      ``run_dir`` because the benchmark harness puts evidence under
      ``.ao/evidence/workflows/<run_id>/`` while ``run_store`` persists
      state under ``.ao/runs/<run_id>/``. The collector only reads
      ``budget.cost_usd`` from the state file.
    - ``review_findings_path`` — optional concrete path to the
      ``review-findings.v1.json`` capability artefact.
    """

    scenario_id: str
    run_dir: Path
    run_state_path: Path | None = None
    review_findings_path: Path | None = None


@dataclass(frozen=True)
class BenchmarkResult:
    scenario: str
    status: str  # "pass" | "fail"
    workflow_completed: bool
    duration_ms: int | None
    cost_consumed_usd: float | None
    cost_source: str | None
    review_score: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "status": self.status,
            "workflow_completed": self.workflow_completed,
            "duration_ms": self.duration_ms,
            "cost_consumed_usd": self.cost_consumed_usd,
            "cost_source": self.cost_source,
            "review_score": self.review_score,
        }


@dataclass
class ScorecardRegistry:
    """Session-scoped accumulator."""

    sidecars: list[PrimarySidecar] = field(default_factory=list)
    duplicate_scenarios: set[str] = field(default_factory=set)

    def record(self, sidecar: PrimarySidecar) -> None:
        if any(s.scenario_id == sidecar.scenario_id for s in self.sidecars):
            self.duplicate_scenarios.add(sidecar.scenario_id)
        self.sidecars.append(sidecar)

    def distinct_scenarios(self) -> list[str]:
        return sorted({s.scenario_id for s in self.sidecars})


class ScorecardCollectorError(RuntimeError):
    """Raised when the canonical-input invariants are violated.

    Duplicate primary markers on the same scenario, or zero primaries
    when at least one is expected.
    """


def resolve_output_path(cwd: Path | None = None) -> Path:
    """Output path comes from ``AO_SCORECARD_OUTPUT`` or default under CWD."""
    override = os.environ.get("AO_SCORECARD_OUTPUT")
    if override:
        return Path(override).expanduser().resolve()
    base = cwd if cwd is not None else Path.cwd()
    return base / DEFAULT_OUTPUT_FILENAME


def _iter_events(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "events.jsonl"
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _event_ts(event: Mapping[str, Any]) -> float | None:
    raw = event.get("ts") or event.get("timestamp")
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def _duration_ms(events: list[dict[str, Any]]) -> int | None:
    if not events:
        return None
    ts = [t for t in (_event_ts(ev) for ev in events) if t is not None]
    if len(ts) < 2:
        return None
    delta = max(ts) - min(ts)
    if delta < 0:
        return None
    return int(round(delta * 1000))


def _latest_run_state(
    run_state_path: Path | None,
) -> Mapping[str, Any] | None:
    """Load the run-state JSON (``budget`` axis lives here).

    Returns ``None`` when the path is unset or unreadable so the
    extractor can record ``cost_consumed_usd=None`` gracefully.
    """
    if run_state_path is None:
        return None
    if not run_state_path.is_file():
        return None
    try:
        loaded = json.loads(run_state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if isinstance(loaded, dict):
        return loaded
    return None


def _extract_cost(run_state: Mapping[str, Any] | None) -> float | None:
    if not run_state:
        return None
    budget = run_state.get("budget") or {}
    axis = budget.get("cost_usd") or {}
    limit = axis.get("limit")
    remaining = axis.get("remaining")
    if limit is None or remaining is None:
        return None
    try:
        return max(0.0, float(limit) - float(remaining))
    except (TypeError, ValueError):
        return None


def _extract_review_score(
    review_findings_path: Path | None,
) -> float | None:
    if review_findings_path is None or not review_findings_path.is_file():
        return None
    try:
        payload = json.loads(review_findings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    raw = payload.get("score")
    if isinstance(raw, (int, float)):
        score = float(raw)
        if 0.0 <= score <= 1.0:
            return score
    return None


def _detect_cost_source(
    events: list[dict[str, Any]],
    cost_consumed: float | None,
) -> str | None:
    """Determine the `cost_source` label for a benchmark run.

    v3.7 F2 absorb — decision tree (adapter-path reconcile benchmark
    uplift):

    1. Events stream carries `kind="llm_spend_recorded"` with
       `payload.source="adapter_path"` → ``"real_adapter"``. The
       canonical signal that the real adapter-path `post_adapter_reconcile`
       middleware fired.
    2. Else, legacy fast-mode run produced a budget drain via the
       (now-removed) ``_maybe_consume_budget`` shim — historical
       scorecard artefacts emitted ``"mock_shim"``. Post-F2 fast-mode
       runs no longer drain the budget, so this branch is only ever
       entered when reading older artefacts.
    3. Otherwise ``None`` — the common F2+ fast-mode path.
    """
    for event in events:
        if event.get("kind") != "llm_spend_recorded":
            continue
        payload = event.get("payload") or {}
        if isinstance(payload, Mapping) and payload.get("source") == "adapter_path":
            return "real_adapter"
    if cost_consumed is not None and cost_consumed > 0:
        # Legacy fast-mode shim drain; retained for backward
        # compatibility reading older run artefacts. Post-F2
        # fast-mode runs won't reach this branch because the shim
        # was removed.
        return "mock_shim"
    return None


def build_result(sidecar: PrimarySidecar) -> BenchmarkResult:
    """Derive a ``BenchmarkResult`` from a primary sidecar."""
    events = _iter_events(sidecar.run_dir)
    event_kinds = {event.get("kind") for event in events}
    workflow_completed = "workflow_completed" in event_kinds
    failed = "workflow_failed" in event_kinds
    status = "pass" if workflow_completed and not failed else "fail"
    run_state = _latest_run_state(sidecar.run_state_path)
    cost_consumed = _extract_cost(run_state)
    cost_source = _detect_cost_source(events, cost_consumed)
    review_score = _extract_review_score(sidecar.review_findings_path)
    return BenchmarkResult(
        scenario=sidecar.scenario_id,
        status=status,
        workflow_completed=workflow_completed,
        duration_ms=_duration_ms(events),
        cost_consumed_usd=cost_consumed,
        cost_source=cost_source,
        review_score=review_score,
    )


def _git_sha() -> str:
    env = os.environ.get("GITHUB_SHA")
    if env and len(env) >= 7:
        return env
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() or "0000000"
    except (subprocess.SubprocessError, FileNotFoundError):
        return "0000000"


def _git_ref() -> str | None:
    env = os.environ.get("GITHUB_REF")
    if env:
        return env
    try:
        out = subprocess.run(
            ["git", "symbolic-ref", "-q", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        ref = out.stdout.strip()
        return ref or None
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def _pr_number() -> int | None:
    env = os.environ.get("GITHUB_PR_NUMBER") or os.environ.get("PR_NUMBER")
    if env and env.isdigit():
        return int(env)
    ref = os.environ.get("GITHUB_REF", "")
    # "refs/pull/<N>/merge" on GHA PR events
    parts = ref.split("/")
    if len(parts) >= 3 and parts[1] == "pull" and parts[2].isdigit():
        return int(parts[2])
    return None


def build_scorecard(
    results: Iterable[BenchmarkResult],
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    sorted_results = sorted(results, key=lambda r: r.scenario)
    ts = generated_at or datetime.now(timezone.utc)
    scorecard: dict[str, Any] = {
        "schema_version": "v1",
        "generated_at": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_sha": _git_sha(),
        "benchmarks": [result.to_dict() for result in sorted_results],
    }
    ref = _git_ref()
    if ref:
        scorecard["git_ref"] = ref
    pr = _pr_number()
    scorecard["pr_number"] = pr
    return scorecard


def finalize_session(
    registry: ScorecardRegistry,
    output_path: Path | None = None,
    *,
    expected_scenarios: frozenset[str] = EXPECTED_PRIMARY_SCENARIOS,
) -> Path | None:
    """Validate canonical-input invariants + write the scorecard JSON.

    Raises ``ScorecardCollectorError`` on duplicate or missing-primary
    misconfiguration. Returns the path that was written (or ``None`` when
    there is nothing to write, e.g. a non-benchmark pytest session).
    """
    from ao_kernel._internal.shared.utils import write_json_atomic

    if not registry.sidecars and not expected_scenarios:
        return None

    if registry.duplicate_scenarios:
        dups = sorted(registry.duplicate_scenarios)
        raise ScorecardCollectorError(
            "Duplicate @pytest.mark.scorecard_primary on scenarios: "
            f"{dups!r}. Each canonical scenario must have exactly one "
            "primary-marked test."
        )

    observed = set(registry.distinct_scenarios())
    missing = expected_scenarios - observed
    if missing:
        raise ScorecardCollectorError(
            "Missing @pytest.mark.scorecard_primary tests for canonical "
            f"scenarios: {sorted(missing)!r}. Each expected scenario in "
            f"{sorted(expected_scenarios)!r} must have exactly one "
            "primary-marked test. Either mark a primary test for the "
            "missing scenarios or set EXPECTED_PRIMARY_SCENARIOS="
            "frozenset() in a downstream harness."
        )

    results = [build_result(sidecar) for sidecar in registry.sidecars]
    scorecard = build_scorecard(results)

    path = output_path or resolve_output_path()
    write_json_atomic(path, scorecard)
    logger.info("scorecard written: %s (scenarios=%s)", path, sorted(observed))
    return path


__all__ = [
    "DEFAULT_OUTPUT_FILENAME",
    "EXPECTED_PRIMARY_SCENARIOS",
    "BenchmarkResult",
    "PrimarySidecar",
    "ScorecardCollectorError",
    "ScorecardRegistry",
    "build_result",
    "build_scorecard",
    "finalize_session",
    "resolve_output_path",
]
