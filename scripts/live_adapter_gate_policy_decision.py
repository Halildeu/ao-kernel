#!/usr/bin/env python3
"""Evaluate a protected live-adapter deployment-protection policy payload."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ao_kernel.live_adapter_gate_policy import (  # noqa: E402
    POLICY_DECISION_ARTIFACT,
    build_live_adapter_gate_policy_decision,
    render_live_adapter_gate_policy_decision_text,
    write_live_adapter_gate_policy_decision,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--payload",
        type=Path,
        required=True,
        help="Path to a deployment_protection_rule webhook or enriched policy payload JSON.",
    )
    parser.add_argument(
        "--decision-path",
        type=Path,
        default=Path(POLICY_DECISION_ARTIFACT),
        help="Path for the policy decision artifact.",
    )
    parser.add_argument("--output", choices=("json", "text"), default="json", help="Stdout render mode.")
    parser.add_argument(
        "--fail-on-reject",
        action="store_true",
        help="Return exit code 1 when the policy decision is reject.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""

    parser = build_parser()
    args = parser.parse_args(argv)
    payload: object = json.loads(args.payload.read_text(encoding="utf-8"))
    decision = build_live_adapter_gate_policy_decision(payload)
    write_live_adapter_gate_policy_decision(args.decision_path, decision)

    if args.output == "json":
        print(json.dumps(decision, indent=2, sort_keys=True))
    else:
        print(render_live_adapter_gate_policy_decision_text(decision))

    if args.fail_on_reject and decision["decision"] == "reject":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
