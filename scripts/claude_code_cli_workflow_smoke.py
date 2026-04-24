#!/usr/bin/env python3
"""Operator smoke for the governed Claude Code CLI workflow."""

from __future__ import annotations

import argparse
import json
import sys

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ao_kernel.real_adapter_workflow_smoke import (  # noqa: E402
    render_workflow_text_report,
    run_claude_code_cli_workflow_smoke,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="claude_code_cli_workflow_smoke.py",
        description=(
            "Run the governed_review_claude_code_cli workflow smoke against "
            "a controlled disposable workspace."
        ),
    )
    parser.add_argument(
        "--output",
        choices=("text", "json"),
        default="text",
        help="Render mode for the smoke report.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=60.0,
        help="Adapter command timeout and run time budget in seconds.",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove the temporary workspace after verification.",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip the helper-level claude-code-cli smoke before the workflow.",
    )
    args = parser.parse_args()

    report = run_claude_code_cli_workflow_smoke(
        timeout_seconds=args.timeout_seconds,
        cleanup=args.cleanup,
        skip_preflight=args.skip_preflight,
    )
    if args.output == "json":
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    else:
        print(render_workflow_text_report(report))
    return 0 if report.overall_status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
