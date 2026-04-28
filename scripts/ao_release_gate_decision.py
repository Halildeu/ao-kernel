#!/usr/bin/env python3
"""Evaluate an ao-release-gate dry-run payload."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ao_kernel.ao_release_gate import (  # noqa: E402
    RELEASE_GATE_ARTIFACT,
    build_ao_release_gate_decision,
    render_ao_release_gate_decision_text,
    write_ao_release_gate_decision,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--payload",
        type=Path,
        required=True,
        help="Path to a PR-shaped release-gate payload JSON.",
    )
    parser.add_argument(
        "--gpp-status",
        type=Path,
        default=Path(".claude/plans/gpp_status.v1.json"),
        help="Path to the machine-readable GPP status JSON.",
    )
    parser.add_argument(
        "--decision-path",
        type=Path,
        default=Path(RELEASE_GATE_ARTIFACT),
        help="Path for the dry-run release-gate decision artifact.",
    )
    parser.add_argument("--output", choices=("json", "text"), default="json", help="Stdout render mode.")
    parser.add_argument(
        "--fail-on-deny",
        action="store_true",
        help="Return exit code 1 when the release-gate decision is not allow_autonomous_merge.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""

    parser = build_parser()
    args = parser.parse_args(argv)
    payload: object = json.loads(args.payload.read_text(encoding="utf-8"))
    gpp_status: object = json.loads(args.gpp_status.read_text(encoding="utf-8"))
    decision = build_ao_release_gate_decision(payload, gpp_status)
    write_ao_release_gate_decision(args.decision_path, decision)

    if args.output == "json":
        print(json.dumps(decision, indent=2, sort_keys=True))
    else:
        print(render_ao_release_gate_decision_text(decision))

    if args.fail_on_deny and not decision["allow"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
