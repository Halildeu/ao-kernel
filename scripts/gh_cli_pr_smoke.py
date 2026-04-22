#!/usr/bin/env python3
"""Operator smoke for the bundled ``gh-cli-pr`` adapter."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ao_kernel.real_adapter_smoke import render_text_report, run_gh_cli_pr_smoke


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="gh_cli_pr_smoke.py",
        description=(
            "Run side-effect-safe smoke checks for the bundled gh-cli-pr adapter."
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
        help="Per-command timeout for live gh CLI probes.",
    )
    parser.add_argument(
        "--repo",
        help="Optional owner/name repo override for gh repo/pr commands.",
    )
    parser.add_argument(
        "--base",
        help="Optional base branch override for the dry-run PR probe.",
    )
    parser.add_argument(
        "--head",
        help="Optional head branch override for the dry-run PR probe.",
    )
    args = parser.parse_args()

    report = run_gh_cli_pr_smoke(
        timeout_seconds=args.timeout_seconds,
        cwd=_REPO_ROOT,
        repo=args.repo,
        base_ref=args.base,
        head_ref=args.head,
    )
    if args.output == "json":
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    else:
        print(render_text_report(report))
    return 0 if report.overall_status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
