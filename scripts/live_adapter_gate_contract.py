#!/usr/bin/env python3
"""Emit the GP-4.1 CI-managed live adapter gate skeleton report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ao_kernel.live_adapter_gate import (  # noqa: E402
    build_live_adapter_gate_report,
    render_live_adapter_gate_text,
    write_live_adapter_gate_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="live_adapter_gate_contract.py",
        description=(
            "Emit the design-only GP-4.1 live-adapter gate contract report. "
            "This command never executes a live external adapter."
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

    if args.output == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_live_adapter_gate_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
