#!/usr/bin/env python3
"""Emit a synthetic ``error_fail_closed`` ao-release-gate decision.

GPP-2D-3 audit fallback. The enforce job in
``.github/workflows/test.yml`` runs the decision script with
``--fail-on-deny``, so a real deny / error decision exits 1 and the job
fails — and ``decision.json`` is already on disk because the script
wrote it before exiting. The script is only invoked AFTER several
pre-decision steps (API fetch, payload builder, freshness, etc.).

If one of those pre-decision steps crashes (transient API error,
runner network blip, etc.), the decision script never runs and
``decision.json`` never exists. This synthesizer fills that gap so the
audit artifact upload always carries a usable record. **It does NOT
mask job failure**: by design it is invoked under ``if: always()`` only
when ``decision.json`` is missing, and the preceding failed step has
already marked the job failed.

The previous GPP-2D-2c synthesizer was fail-OPEN (it produced an
artifact AND let the job exit 0 because shadow was advisory). GPP-2D-3
retires that contract: the enforce job's conclusion mirrors the
decision body. This synthesizer never sets ``conclusion=success`` and
never short-circuits the job exit code.

The script is side-effect free beyond writing the output file. No
secret material is read or written.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_REASON = (
    "ao-release-gate could not produce a decision; a pre-decision step "
    "failed before the decision core could run."
)
DEFAULT_FINDING = "ao_release_gate_pre_decision_step_failed"


def _utc_timestamp() -> str:
    """Return an ISO-8601 UTC timestamp.

    Prefers the canonical ``ao_kernel.live_adapter_gate.utc_timestamp`` so
    the synthetic artifact matches the format the core would emit. Falls
    back to the stdlib when the package is not importable (e.g. when the
    base-ref install failed mid-run).
    """

    try:
        from ao_kernel.live_adapter_gate import utc_timestamp

        return utc_timestamp()
    except Exception:  # noqa: BLE001 - intentionally broad: any import or runtime failure
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_error_decision(*, conclusion_mode: str, reason: str, finding_code: str) -> dict[str, Any]:
    """Build the synthetic ``error_fail_closed`` decision dictionary."""

    # Shadow advisory maps deny/error to neutral; enforce maps to failure.
    # The synthesizer mirrors the same mapping as the decision core's
    # _check_run helper.
    check_run_conclusion = "failure" if conclusion_mode == "enforce" else "neutral"
    return {
        "schema_version": "1",
        "artifact_kind": "ao_release_gate_decision",
        "program_id": "GPP-2v",
        "generated_at": _utc_timestamp(),
        "app_slug": "ao-release-gate",
        "dry_run": True,
        "merge_authority_enabled": False,
        "conclusion_mode": conclusion_mode,
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
            "conclusion": check_run_conclusion,
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
    parser.add_argument(
        "--conclusion-mode",
        choices=("shadow", "enforce"),
        default="shadow",
        help=(
            "Conclusion mode to record in the synthesized artifact. "
            "'shadow' (default) maps deny/error to github_check_run.conclusion=neutral so the "
            "GPP-2D-2c advisory shadow workflow's fallback artifact stays shadow / neutral when "
            "PR-A lands without PR-B's workflow swap. The GPP-2D-3b enforce job passes "
            "'--conclusion-mode enforce' explicitly so the enforce-job fallback artifact maps "
            "deny/error to conclusion=failure."
        ),
    )
    parser.add_argument(
        "--reason",
        default=DEFAULT_REASON,
        help="Free-text reason recorded in the artifact's reason / check-run summary.",
    )
    parser.add_argument(
        "--finding-code",
        default=DEFAULT_FINDING,
        help=(
            "Finding code recorded in findings[] and the check-run text. Defaults to "
            f"'{DEFAULT_FINDING}'; the workflow-only "
            "'ao_release_gate_upstream_required_check_failed' is used for the "
            "needs:-failure path."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint.

    The script always returns 0 after a successful write. It does **not**
    propagate a fail-closed exit code on its own — the calling workflow
    step has its own contract (either preceding steps already failed the
    job, or a wrapping step explicitly exits 1 after this synthesizer
    writes the audit record).
    """

    parser = build_parser()
    args = parser.parse_args(argv)
    decision = build_error_decision(
        conclusion_mode=args.conclusion_mode,
        reason=args.reason,
        finding_code=args.finding_code,
    )
    args.output.write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
