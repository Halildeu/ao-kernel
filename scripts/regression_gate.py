"""Thin CLI for the policy-aware regression gate (V5 Epic 7x).

Wraps ``ao_kernel/_internal/scorecard/regression`` with argparse + exit
code emission. Codex 019e84b7 cross-AI plan-time AGREE.

Operator usage:

    python scripts/regression_gate.py \
        --head benchmark_scorecard.v1.json \
        --baseline docs/performance/baseline.v1.json \
        --threshold docs/performance/performance-regression-threshold.v1.json \
        --catalog docs/performance/performance-scenario-catalog.v1.json \
        --benchmark-mode fast \
        --out regression-comparison-result.v1.json \
        --generated-at "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

Operator override (mutually exclusive):

    --advisory-mode  → exit 0 even on hard_fail (operator override; logged)
    --strict-mode    → exit 1 on warn or hard_fail (operator-local only; CLI
                       banner warns this is NOT CI required-check evidence)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from ao_kernel._internal.scorecard.regression import (  # noqa: E402
    ComparisonInputs,
    build_comparison_result,
    canonical_json,
    determine_exit_code,
)


def _strict_mode_banner() -> str:
    return (
        "WARNING: --strict-mode is operator-local only. This run does NOT "
        "represent CI required-check promotion evidence. Workflow YAML "
        "continue-on-error flip is governance-gated (future E-7x-3 PR)."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Regression gate (policy-driven)")
    parser.add_argument("--head", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--threshold", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--benchmark-mode", type=str, required=True, choices=("fast", "full"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--generated-at", type=str, required=True)

    override = parser.add_mutually_exclusive_group()
    override.add_argument("--advisory-mode", action="store_true", help="Override: warn+hard_fail → exit 0")
    override.add_argument("--strict-mode", action="store_true", help="Override: warn+hard_fail → exit 1 (operator-local)")

    args = parser.parse_args(argv)

    cli_override: str | None
    if args.advisory_mode:
        cli_override = "advisory"
    elif args.strict_mode:
        cli_override = "strict"
        print(_strict_mode_banner(), file=sys.stderr)
    else:
        cli_override = None

    inputs = ComparisonInputs(
        head_scorecard_path=args.head,
        baseline_path=args.baseline,
        threshold_path=args.threshold,
        catalog_path=args.catalog,
        benchmark_mode=args.benchmark_mode,
        cli_override=cli_override,
        generated_at=args.generated_at,
    )
    threshold = json.loads(args.threshold.read_text())
    result = build_comparison_result(inputs, threshold)
    args.out.write_text(canonical_json(result))
    enforcement = result["compared_from"]["enforcement_mode_resolved"]
    return determine_exit_code(result, enforcement, cli_override)


if __name__ == "__main__":
    sys.exit(main())
