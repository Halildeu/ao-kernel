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
            "Run gh-cli-pr adapter smoke checks (preflight default; "
            "live-write explicit opt-in)."
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
        help=(
            "Base branch override. live-write mode'da explicit --base zorunludur; "
            "preflight modunda default branch fallback kullanilir."
        ),
    )
    parser.add_argument(
        "--head",
        help=(
            "Head branch override. live-write mode'da explicit --head zorunludur; "
            "preflight modunda default branch fallback kullanilir."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=("preflight", "live-write"),
        default="preflight",
        help=(
            "Probe mode. preflight runs side-effect-safe dry-run; "
            "live-write runs create+rollback chain with explicit opt-in."
        ),
    )
    parser.add_argument(
        "--allow-live-write",
        action="store_true",
        help="Required guard flag for --mode live-write.",
    )
    parser.add_argument(
        "--keep-live-write-pr-open",
        action="store_true",
        help=(
            "Create edilen PR'i acik birak. Bu secenek lane'i riskli sayar ve "
            "rapor blocked doner."
        ),
    )
    parser.add_argument(
        "--require-disposable-keyword",
        default="sandbox",
        help=(
            "Disposable repo guard keyword for live-write mode "
            "(default: sandbox, empty string disables the guard)."
        ),
    )
    args = parser.parse_args()

    report = run_gh_cli_pr_smoke(
        timeout_seconds=args.timeout_seconds,
        cwd=_REPO_ROOT,
        repo=args.repo,
        base_ref=args.base,
        head_ref=args.head,
        mode=args.mode.replace("-", "_"),
        allow_live_write=args.allow_live_write,
        keep_live_write_pr_open=args.keep_live_write_pr_open,
        require_disposable_repo_keyword=args.require_disposable_keyword or None,
    )
    if args.output == "json":
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    else:
        print(render_text_report(report))
    return 0 if report.overall_status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
