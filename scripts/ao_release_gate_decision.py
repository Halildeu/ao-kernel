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
    build_review_check_run,
    build_technical_check_run,
    render_ao_release_gate_decision_text,
    wrapper_exit_code,
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
        "--review-evidence",
        type=Path,
        default=None,
        help=(
            "Optional path to a local-gpp-gate-evidence.v1 attestation. When given, the file is "
            "loaded and passed to the decision core as untrusted review evidence; when omitted, "
            "the decision core treats review evidence as missing and the decision is "
            "deny_missing_evidence."
        ),
    )
    parser.add_argument(
        "--conclusion-mode",
        choices=("shadow", "enforce"),
        default="shadow",
        help=(
            "Decision-core conclusion mode. 'shadow' (default) maps every deny/error decision to "
            "github_check_run.conclusion=neutral so an advisory check does not produce red CI. "
            "'enforce' maps deny/error to conclusion=failure (the historical mapping required "
            "once the check is wired as a required status check on branch protection)."
        ),
    )
    parser.add_argument(
        "--fail-on-deny",
        action="store_true",
        help="Return exit code 1 when the release-gate decision is not allow_autonomous_merge.",
    )
    parser.add_argument(
        "--wrapper-exit-code",
        action="store_true",
        help=(
            "RG-CONCLUSION-SEMANTICS C-prime wrapper exit logic. Returns 0 when the gate "
            "would allow merge OR when the only blocker is a pending CODEOWNER review on "
            "the current PR head; returns 1 for any real violation, stale branch, or mixed "
            "blocker set. Preserves the legacy ao-release-gate required check name while "
            "shifting CODEOWNER-review-missing semantics off the failure axis. Mutually "
            "exclusive with --fail-on-deny in practice; if both are passed, "
            "--wrapper-exit-code is the effective signal (review-action-only blocker no "
            "longer maps to non-zero exit)."
        ),
    )
    parser.add_argument(
        "--emit-multi-check-runs",
        type=Path,
        default=None,
        metavar="DIR",
        help=(
            "RG-CONCLUSION-SEMANTICS C-prime dual-publish. When given, write two additional "
            "no-secret check-run artifacts under DIR: 'ao-release-gate-technical.check-run.json' "
            "and 'ao-release-gate-review.check-run.json'. These are consumed by the workflow's "
            "Checks API publish step so the new dual check-runs surface on every PR alongside "
            "the legacy compatibility wrapper."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""

    parser = build_parser()
    args = parser.parse_args(argv)
    payload: object = json.loads(args.payload.read_text(encoding="utf-8"))
    gpp_status: object = json.loads(args.gpp_status.read_text(encoding="utf-8"))
    review_evidence: object | None = None
    if args.review_evidence is not None:
        review_evidence = json.loads(args.review_evidence.read_text(encoding="utf-8"))
    decision = build_ao_release_gate_decision(
        payload,
        gpp_status,
        review_evidence=review_evidence,
        conclusion_mode=args.conclusion_mode,
    )
    write_ao_release_gate_decision(args.decision_path, decision)

    if args.output == "json":
        print(json.dumps(decision, indent=2, sort_keys=True))
    else:
        print(render_ao_release_gate_decision_text(decision))

    if args.emit_multi_check_runs is not None:
        args.emit_multi_check_runs.mkdir(parents=True, exist_ok=True)
        technical = build_technical_check_run(
            decision["decision"],
            list(decision["findings"]),
            conclusion_mode=args.conclusion_mode,
        )
        review = build_review_check_run(
            decision["decision"],
            list(decision["findings"]),
            conclusion_mode=args.conclusion_mode,
        )
        (args.emit_multi_check_runs / "ao-release-gate-technical.check-run.json").write_text(
            json.dumps(technical, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (args.emit_multi_check_runs / "ao-release-gate-review.check-run.json").write_text(
            json.dumps(review, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    if args.wrapper_exit_code:
        return wrapper_exit_code(decision["decision"], list(decision["findings"]))
    if args.fail_on_deny and not decision["allow"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
