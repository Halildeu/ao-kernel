"""Deterministic gh-cli-pr stub adapter for demos + CI (PR-A6).

Emits a canonical ``output_envelope`` JSON on stdout with a stub
PR URL + number. No real ``gh`` invocation; exercises the adapter
CLI transport without VCS side effects.

Invocation (matching gh-cli-pr.manifest.v1.json fixture):

    python3 -m ao_kernel.fixtures.gh_pr_stub --run-id <uuid>

Output (stdout; single line JSON):

    {"status":"ok","diff":null,"pr_url":"demo://stub/1",
     "pr_number":1,"commands_executed":["gh pr create (stub)"],
     "evidence_events":[],
     "finish_reason":"normal",
     "cost_actual":{"tokens_input":0,"tokens_output":0,"time_seconds":0.0}}
"""

from __future__ import annotations

import argparse
import json
import sys


_CANNED_OUTPUT = {
    "status": "ok",
    "diff": None,
    "pr_url": "demo://stub/1",
    "pr_number": 1,
    "commands_executed": ["gh pr create (stub)"],
    "evidence_events": [],
    "finish_reason": "normal",
    "cost_actual": {
        "tokens_input": 0,
        "tokens_output": 0,
        "time_seconds": 0.0,
    },
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gh_pr_stub")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--prompt-file", required=False)
    parser.add_argument(
        "--stdin-mode",
        choices=["none", "prompt_only", "multipart"],
        default="none",
    )
    args = parser.parse_args(argv)

    # Consume stdin if requested (deterministic stub ignores content)
    if args.stdin_mode != "none":
        sys.stdin.read()

    print(json.dumps(_CANNED_OUTPUT, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
