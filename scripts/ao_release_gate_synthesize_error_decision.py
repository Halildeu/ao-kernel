#!/usr/bin/env python3
"""Emit a synthetic ``error_fail_closed`` ao-release-gate decision.

The ao-release-gate shadow workflow (GPP-2D-2c) runs every pre-decision
step under ``continue-on-error: true`` so a transient API fetch / builder
failure does not break the advisory job. When the decision step did not
produce ``decision.json``, the workflow's always-run synthesis step
invokes this script to write a synthetic decision artifact, so every
shadow run still emits an auditable record and the job exits 0.

The artifact carries the canonical ``error_fail_closed`` finding shape:

- ``decision = "error_fail_closed"`` (the fail-closed decision used by the
  ao-release-gate core for malformed / unevaluable payloads);
- ``allow = false``;
- ``conclusion_mode = "shadow"``;
- ``github_check_run.conclusion = "neutral"`` (shadow advisory);
- the gate-authored finding code
  ``ao_release_gate_shadow_pre_decision_step_failed``, which is
  workflow-only (the decision core never produces it).

No secret material is read or written. The script is side-effect free
beyond writing the output file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _utc_timestamp() -> str:
    """Return an ISO-8601 UTC timestamp.

    Prefers the canonical ``ao_kernel.live_adapter_gate.utc_timestamp`` so
    the synthetic artifact matches the format the core would emit. Falls
    back to the stdlib when the package is not importable (e.g. when the
    base-ref install failed mid-shadow).
    """

    try:
        from ao_kernel.live_adapter_gate import utc_timestamp

        return utc_timestamp()
    except Exception:  # noqa: BLE001 - intentionally broad: any import or runtime failure
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_error_decision() -> dict[str, Any]:
    """Build the synthetic ``error_fail_closed`` decision dictionary."""

    finding_code = "ao_release_gate_shadow_pre_decision_step_failed"
    reason = (
        "ao-release-gate shadow workflow could not produce a decision; "
        "a pre-decision step failed under continue-on-error."
    )
    return {
        "schema_version": "1",
        "artifact_kind": "ao_release_gate_decision",
        "program_id": "GPP-2v",
        "generated_at": _utc_timestamp(),
        "app_slug": "ao-release-gate",
        "dry_run": True,
        "merge_authority_enabled": False,
        "conclusion_mode": "shadow",
        "decision": "error_fail_closed",
        "allow": False,
        "finding_code": "error_fail_closed",
        "reason": reason,
        "context": {},
        "checks": [],
        "findings": [finding_code],
        "github_check_run": {
            "name": "ao-release-gate",
            "status": "completed",
            "conclusion": "neutral",
            "title": "ao-release-gate: error_fail_closed",
            "summary": reason,
            "text": f"Findings: {finding_code}",
        },
    }


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output",
        type=Path,
        help="Path for the synthetic decision JSON artifact.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""

    parser = build_parser()
    args = parser.parse_args(argv)
    decision = build_error_decision()
    args.output.write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
