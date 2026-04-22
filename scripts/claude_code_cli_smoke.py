#!/usr/bin/env python3
"""Operator smoke for the bundled ``claude-code-cli`` adapter."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ao_kernel.real_adapter_smoke import (
    render_text_report,
    run_claude_code_cli_smoke,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="claude_code_cli_smoke.py",
        description=(
            "Run operator-facing smoke checks for the bundled "
            "claude-code-cli adapter."
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
        default=20.0,
        help="Per-command timeout for live Claude CLI probes.",
    )
    args = parser.parse_args()

    report = run_claude_code_cli_smoke(
        timeout_seconds=args.timeout_seconds,
    )
    if args.output == "json":
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    else:
        print(render_text_report(report))
    return 0 if report.overall_status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
