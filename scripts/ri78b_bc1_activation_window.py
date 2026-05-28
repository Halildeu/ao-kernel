#!/usr/bin/env python3
"""RI-7.8b-bc1 protected execution window runtime guard (fail-closed).

Validates the bounded operator-bound activation window for the BC-1 protected
live-adapter attestation workflow. Runs INSIDE the workflow job (after
checkout, before the live attestation step). Any guard failure exits non-zero
to abort the run before any provider call.

Guard chain (each failure → exit 1):
1. ``--workflow-path`` exists and matches the expected canonical path
2. ``workflow_content_sha256`` (raw bytes) matches the active supersession entry
   ``future_workflow_contract.workflow_content_sha256`` binding
3. gpp_status.v1.json contains exactly one supersession entry with
   ``id == RI-7.8b-bc1-6b`` and ``scope ==
   bc1_protected_live_adapter_attestation_only``
4. Entry status in ``{awaiting_operator_dispatch, active}``
5. Top-level guard flags (``support_widening_allowed``,
   ``production_platform_claim_allowed``, ``live_adapter_execution_allowed``)
   all remain ``false`` (baseline closure preserved)
6. Entry ``guard_flag_policy_resolution``:
   - ``support_widening_allowed == false``
   - ``production_platform_claim_allowed == false``
   - ``live_adapter_execution_allowed == true`` (the scoped effective grant)
7. ``now_utc < entry.valid_until`` (activation has not expired)
8. ``entry.allowed_refs`` contains ``refs/heads/main``
9. Scenario input is one of the allowed scenarios
10. GitHub Actions API: total distinct ``workflow_dispatch`` runs for this
    workflow on ``main`` (workflow lifetime cap) <= MAX_DISTINCT_RUNS.
    Window-relative filtering (since ``entry.actual_start_at``) is owned by
    RI-7.8b-bc1-6c which records the per-run evidence + closure proof; 6b
    enforces the lifetime cap because ``actual_start_at`` is null prior to
    the first dispatch.

The script does NOT mutate gpp_status.v1.json. State transitions
(``awaiting_operator_dispatch`` → ``active``, ``active`` → ``closed``) are
recorded post-run by the RI-7.8b-bc1-6c slice as new evidence + new
gpp_status PR.

Secret boundary: this script never reads, prints, or transmits provider
credentials. It operates on path digests and JSON state only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CANONICAL_WORKFLOW_PATH = ".github/workflows/bc1-protected-live-adapter-attestation.yml"
ACTIVATION_ID = "RI-7.8b-bc1-6b"
SCOPE = "bc1_protected_live_adapter_attestation_only"
MAX_DISTINCT_RUNS = 5
ALLOWED_SCENARIOS = {"clean_attestation", "fail_closed_attestation"}


def _fail(msg: str) -> None:
    """Print to stderr and exit non-zero (fail-closed)."""
    print(f"fail-closed: {msg}", file=sys.stderr)
    sys.exit(1)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_iso_z(s: str) -> datetime:
    if s.endswith("Z"):
        return datetime.fromisoformat(s[:-1] + "+00:00")
    return datetime.fromisoformat(s)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _load_status(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        _fail(f"cannot load gpp_status.v1.json at {path}: {exc}")
        return {}  # unreachable; keeps type-checker happy


def _find_active_entry(status: dict, workflow_sha: str) -> dict:
    entries = status.get("operator_bound_supersessions") or []
    if not isinstance(entries, list):
        _fail("gpp_status.operator_bound_supersessions must be a list")

    matches = [
        e
        for e in entries
        if isinstance(e, dict) and e.get("id") == ACTIVATION_ID and e.get("scope") == SCOPE
    ]
    if len(matches) == 0:
        _fail(f"no supersession entry id={ACTIVATION_ID} scope={SCOPE} found")
    if len(matches) > 1:
        _fail(
            f"multiple supersession entries id={ACTIVATION_ID} scope={SCOPE} found"
            f" (got {len(matches)})"
        )

    entry = matches[0]
    # Authority mode — accept either the legacy operator-bound (6b) state OR
    # the autonomous pre-prod (6c-fast-follow) trigger-commit state.
    authority_mode = entry.get("authority_mode") or "manual_protected_environment"
    status_str = entry.get("status")
    accepted_statuses_by_mode = {
        "manual_protected_environment": {"awaiting_operator_dispatch", "active"},
        "operator_delegated_autonomous_preprod": {
            "awaiting_auto_dispatch_trigger_commit",
            "active",
        },
    }
    accepted = accepted_statuses_by_mode.get(authority_mode)
    if accepted is None:
        _fail(f"unknown authority_mode={authority_mode!r}")
    if status_str not in accepted:
        _fail(
            f"supersession entry status={status_str!r} not in [awaiting_operator_dispatch, active]"
        )

    binding = entry.get("future_workflow_contract") or {}
    expected_sha = binding.get("workflow_content_sha256")
    if expected_sha != workflow_sha:
        _fail(
            "workflow_content_sha256 mismatch: "
            f"file={workflow_sha} entry={expected_sha}"
        )

    return entry


def _check_baseline_flags(status: dict) -> None:
    for key in (
        "support_widening_allowed",
        "production_platform_claim_allowed",
        "live_adapter_execution_allowed",
    ):
        if status.get(key) is not False:
            _fail(f"top-level {key}={status.get(key)!r} must remain false")


def _check_entry_guard_policy(entry: dict) -> None:
    policy = entry.get("guard_flag_policy_resolution") or {}
    if policy.get("support_widening_allowed") is not False:
        _fail("entry.guard_flag_policy_resolution.support_widening_allowed must be false")
    if policy.get("production_platform_claim_allowed") is not False:
        _fail(
            "entry.guard_flag_policy_resolution.production_platform_claim_allowed must be false"
        )
    if policy.get("live_adapter_execution_allowed") is not True:
        _fail(
            "entry.guard_flag_policy_resolution.live_adapter_execution_allowed must be true"
            " (scoped effective grant)"
        )


def _check_window_not_expired(entry: dict) -> None:
    valid_until = entry.get("valid_until")
    if not valid_until:
        _fail("entry.valid_until missing")
    try:
        until = _parse_iso_z(valid_until)
    except ValueError as exc:
        _fail(f"entry.valid_until parse error: {exc}")
    if _now_utc() >= until:
        _fail(f"activation window expired: now >= valid_until={valid_until}")


def _check_allowed_refs(entry: dict) -> None:
    allowed = (entry.get("protected_environment_binding") or {}).get("allowed_refs") or []
    ref = os.environ.get("GITHUB_REF", "")
    if ref not in allowed:
        _fail(f"github.ref={ref!r} not in entry.allowed_refs={allowed}")


def _check_scenario(scenario: str) -> None:
    if scenario not in ALLOWED_SCENARIOS:
        _fail(f"scenario={scenario!r} not in {sorted(ALLOWED_SCENARIOS)}")


def _accepted_events_for_authority_mode(authority_mode: str) -> tuple[str, ...]:
    """Per Codex thread 019e702f iter-2 absorb: event-aware run cap.

    ``manual_protected_environment`` legacy 6b path counts only
    ``workflow_dispatch`` runs. ``operator_delegated_autonomous_preprod``
    6c-fast-follow/6c-trigger path counts BOTH ``push`` (auto-dispatch
    via trigger commit) AND ``workflow_dispatch`` (manual fallback) so
    that the bounded-window cap is honest about the activation surface
    actually in use.
    """
    if authority_mode == "manual_protected_environment":
        return ("workflow_dispatch",)
    if authority_mode == "operator_delegated_autonomous_preprod":
        return ("push", "workflow_dispatch")
    return ("workflow_dispatch",)


def _check_distinct_run_count(entry: dict) -> None:
    """Use GitHub Actions API to count total distinct workflow runs for
    this workflow on main (workflow lifetime cap). Must be <=
    MAX_DISTINCT_RUNS including the current run. Window-relative
    filtering (since ``entry.actual_start_at``) is owned by
    RI-7.8b-bc1-6c-closure; while ``actual_start_at`` is null
    (status=awaiting_auto_dispatch_trigger_commit OR
    awaiting_operator_dispatch) we enforce the lifetime cap to keep
    contract == implementation.

    Event-aware: ``manual_protected_environment`` mode counts
    ``workflow_dispatch`` runs only. ``operator_delegated_autonomous_preprod``
    counts both ``push`` (auto-dispatch via trigger commit) and
    ``workflow_dispatch`` (manual fallback). Matrix scenarios share
    one ``workflow_run_id`` so distinct run ids — not matrix jobs — are
    counted. Window-relative time filter (``created_at >=
    actual_start_at``) is applied when the entry has transitioned to
    ``active``; otherwise lifetime cap applies.
    """
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        _fail("GITHUB_REPOSITORY not set")

    authority_mode = entry.get("authority_mode") or "manual_protected_environment"
    accepted_events = _accepted_events_for_authority_mode(authority_mode)
    actual_start_at_raw = entry.get("actual_start_at")
    actual_start_dt: datetime | None = None
    if isinstance(actual_start_at_raw, str) and actual_start_at_raw:
        try:
            actual_start_dt = _parse_iso_z(actual_start_at_raw)
        except ValueError:
            actual_start_dt = None

    distinct_run_ids: set[str] = set()
    for event in accepted_events:
        try:
            result = subprocess.run(
                [
                    "gh",
                    "api",
                    f"repos/{repo}/actions/workflows/bc1-protected-live-adapter-attestation.yml/runs",
                    "-q",
                    ".workflow_runs[] | (.id | tostring) + \"\\t\" + .created_at",
                    "-X",
                    "GET",
                    "-f",
                    "branch=main",
                    "-f",
                    f"event={event}",
                    "-f",
                    "per_page=100",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            _fail(f"gh api call failed: {exc}")

        if result.returncode != 0:
            _fail(f"gh api non-zero exit: {result.stderr.strip()}")

        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t", 1)
            run_id = parts[0].strip()
            created_at = parts[1].strip() if len(parts) > 1 else ""
            if not run_id:
                continue
            if actual_start_dt is not None and created_at:
                try:
                    created_dt = _parse_iso_z(created_at)
                except ValueError:
                    distinct_run_ids.add(run_id)
                    continue
                if created_dt >= actual_start_dt:
                    distinct_run_ids.add(run_id)
            else:
                # Lifetime cap (status=awaiting_*; actual_start_at null)
                distinct_run_ids.add(run_id)

    current_run = os.environ.get("GITHUB_RUN_ID")
    if current_run:
        distinct_run_ids.add(current_run)

    if len(distinct_run_ids) > MAX_DISTINCT_RUNS:
        _fail(
            f"distinct workflow run count {len(distinct_run_ids)} exceeds max"
            f" {MAX_DISTINCT_RUNS} (authority_mode={authority_mode} "
            f"accepted_events={list(accepted_events)} "
            f"run_ids={sorted(distinct_run_ids)})"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="RI-7.8b-bc1 protected execution window guard"
    )
    parser.add_argument("--workflow-path", required=True)
    parser.add_argument("--gpp-status", required=True)
    parser.add_argument("--scenario", required=True)
    args = parser.parse_args()

    workflow_path = Path(args.workflow_path)
    if not workflow_path.exists():
        _fail(f"workflow file missing: {workflow_path}")
    if (
        str(workflow_path) != CANONICAL_WORKFLOW_PATH
        and workflow_path.name != Path(CANONICAL_WORKFLOW_PATH).name
    ):
        _fail(f"workflow path {workflow_path} not canonical {CANONICAL_WORKFLOW_PATH}")

    workflow_sha = _sha256(workflow_path)

    status_path = Path(args.gpp_status)
    if not status_path.exists():
        _fail(f"gpp_status.v1.json missing: {status_path}")
    status = _load_status(status_path)

    _check_baseline_flags(status)
    entry = _find_active_entry(status, workflow_sha)
    _check_entry_guard_policy(entry)
    _check_window_not_expired(entry)
    _check_allowed_refs(entry)
    _check_scenario(args.scenario)
    _check_distinct_run_count(entry)

    print(
        "ri78b_bc1_activation_window guard PASS: "
        f"workflow_sha={workflow_sha[:16]}... entry_status={entry.get('status')} "
        f"scenario={args.scenario}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
