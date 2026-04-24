#!/usr/bin/env python3
"""Emit the fail-closed GP-4 live adapter gate reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ao_kernel.live_adapter_gate import (  # noqa: E402
    EVIDENCE_ARTIFACT,
    ENVIRONMENT_CONTRACT_ARTIFACT,
    build_live_adapter_gate_environment_contract,
    build_live_adapter_gate_report,
    build_live_adapter_gate_evidence_artifact,
    render_live_adapter_gate_text,
    write_live_adapter_gate_environment_contract,
    write_live_adapter_gate_evidence_artifact,
    write_live_adapter_gate_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="live_adapter_gate_contract.py",
        description=(
            "Emit the design-only GP-4.1 live-adapter gate contract report. "
            "This command also writes the GP-4.2 evidence artifact plus the "
            "GP-4.3 protected environment contract and never executes a live "
            "external adapter."
        ),
    )
    parser.add_argument(
        "--output",
        choices=("text", "json"),
        default="json",
        help="Render mode for stdout.",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=Path("live-adapter-gate-contract.v1.json"),
        help="Path for the canonical JSON report artifact.",
    )
    parser.add_argument(
        "--evidence-path",
        type=Path,
        default=Path(EVIDENCE_ARTIFACT),
        help="Path for the canonical GP-4.2 evidence artifact.",
    )
    parser.add_argument(
        "--environment-contract-path",
        type=Path,
        default=Path(ENVIRONMENT_CONTRACT_ARTIFACT),
        help="Path for the canonical GP-4.3 protected environment contract.",
    )
    parser.add_argument("--target-ref", default="main", help="Protected target ref being evaluated.")
    parser.add_argument("--reason", default="", help="Manual dispatch reason.")
    parser.add_argument("--requested-by", default="", help="Actor that requested the gate.")
    parser.add_argument("--event-name", default="workflow_dispatch", help="GitHub event name.")
    parser.add_argument("--head-sha", default="", help="Commit SHA evaluated by the gate.")
    args = parser.parse_args()

    report = build_live_adapter_gate_report(
        target_ref=args.target_ref,
        reason=args.reason,
        requested_by=args.requested_by,
        event_name=args.event_name,
        head_sha=args.head_sha,
    )
    write_live_adapter_gate_report(args.report_path, report)
    evidence_artifact = build_live_adapter_gate_evidence_artifact(
        report,
        contract_report_path=args.report_path.name,
    )
    write_live_adapter_gate_evidence_artifact(args.evidence_path, evidence_artifact)
    environment_contract = build_live_adapter_gate_environment_contract(
        generated_at=report["generated_at"],
    )
    write_live_adapter_gate_environment_contract(
        args.environment_contract_path,
        environment_contract,
    )

    if args.output == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_live_adapter_gate_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
