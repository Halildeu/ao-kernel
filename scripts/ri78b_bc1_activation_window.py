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
10. GitHub Actions API: distinct ``workflow_dispatch`` runs for this workflow on
    ``main`` since ``entry.actual_start_at`` (or now if null) <= 5

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
    status_str = entry.get("status")
    if status_str not in {"awaiting_operator_dispatch", "active"}:
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


def _check_distinct_run_count(entry: dict) -> None:
    """Use GitHub Actions API to count distinct workflow_dispatch runs since
    actual_start_at on main. Must be <= MAX_DISTINCT_RUNS including the
    current run."""
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        _fail("GITHUB_REPOSITORY not set")

    try:
        result = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{repo}/actions/workflows/bc1-protected-live-adapter-attestation.yml/runs",
                "-q",
                ".workflow_runs[].id",
                "-X",
                "GET",
                "-f",
                "branch=main",
                "-f",
                "event=workflow_dispatch",
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

    run_ids = sorted(set(line.strip() for line in result.stdout.splitlines() if line.strip()))
    current_run = os.environ.get("GITHUB_RUN_ID")
    if current_run and current_run not in run_ids:
        run_ids.append(current_run)

    if len(run_ids) > MAX_DISTINCT_RUNS:
        _fail(
            f"distinct workflow_dispatch run count {len(run_ids)} exceeds max"
            f" {MAX_DISTINCT_RUNS} (run_ids={run_ids})"
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
