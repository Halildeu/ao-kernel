"""Promote a benchmark scorecard into a candidate baseline.v1.json (V5 Epic 7).

Joins benchmark scorecard rows against the scenario catalog by
``source_scorecard_scenario`` and emits a schema-conforming baseline manifest.

Codex 019e8410 cross-AI plan-time AGREE (4 iters: REVISE/REVISE/REVISE/AGREE).

Discipline:
- Mode + enforcement filter: only catalog scenarios with
  ``mode == --benchmark-mode`` AND ``enforcement == 'policy_threshold'``
  are included. advisory_only entries and mode-mismatched entries are
  skipped silently from the baseline; the script logs the selection
  summary.
- Empty selection: by default the script exits 2 ("nothing to promote
  for this mode"). ``--allow-empty`` opts into writing an empty baseline
  for operator-managed advanced workflows. The E-7a committed fast
  baseline always has >=1 entry per the catalog.
- Deterministic output: requires ``--generated-at`` (no wall-clock
  default) so byte-equal drift tests are stable across machines.
- No network: reads local scorecard + catalog files only. GitHub
  artifact download is intentionally out of scope.

Usage:
    python scripts/promote_baseline.py \
        --scorecard benchmark_scorecard.v1.json \
        --scenario-catalog docs/performance/performance-scenario-catalog.v1.json \
        --out docs/performance/baseline.v1.json \
        --source-git-sha <hex> \
        --source-git-ref refs/heads/main \
        --benchmark-mode fast \
        --python-version 3.13 \
        --runner-os ubuntu-latest \
        --generated-at 2026-06-01T20:00:00Z
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

EXIT_EMPTY_SELECTION = 2


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def select_scenarios_for_baseline(
    catalog: dict[str, Any],
    benchmark_mode: str,
) -> list[dict[str, Any]]:
    """Filter catalog entries for inclusion in the baseline.

    Codex E7-BASELINE-CATALOG-MODE-FILTER absorb:
    - include: ``mode == --benchmark-mode`` AND ``enforcement == 'policy_threshold'``
    - skip: ``enforcement == 'advisory_only'`` OR ``mode != --benchmark-mode``
    """
    selected: list[dict[str, Any]] = []
    for scenario in catalog["scenarios"]:
        if scenario["mode"] != benchmark_mode:
            continue
        if scenario["enforcement"] != "policy_threshold":
            continue
        selected.append(scenario)
    return selected


def _find_scorecard_row(
    scorecard: dict[str, Any],
    source_name: str,
) -> dict[str, Any] | None:
    for row in scorecard.get("benchmarks", []) or []:
        if row.get("scenario") == source_name:
            return row
    return None


def build_baseline_scenario(
    catalog_scenario: dict[str, Any],
    scorecard_row: dict[str, Any],
    benchmark_mode: str,
) -> dict[str, Any]:
    cost_source = scorecard_row.get("cost_source")
    return {
        "id": catalog_scenario["id"],
        "source_scorecard_scenario": catalog_scenario["source_scorecard_scenario"],
        "workflow_id": catalog_scenario["workflow_id"],
        "benchmark_mode": benchmark_mode,
        "metric": {
            "name": "duration_ms",
            "unit": "ms",
            "value": float(scorecard_row["duration_ms"]),
            "statistic": "single_run",
        },
        "status": scorecard_row.get("status", "pass"),
        "workflow_completed": bool(scorecard_row.get("workflow_completed", True)),
        "cost_source": cost_source,
        "review_score_expected": scorecard_row.get("review_score"),
        "candidate_baseline": True,
        "sample_count": 1,
        "variance_profile": "single_ci_run",
    }


def build_baseline(
    catalog: dict[str, Any],
    scorecard: dict[str, Any],
    *,
    benchmark_mode: str,
    source_git_sha: str,
    source_git_ref: str,
    python_version: str,
    runner_os: str,
    generated_at: str,
) -> dict[str, Any]:
    catalog_entries = select_scenarios_for_baseline(catalog, benchmark_mode)
    scenarios: list[dict[str, Any]] = []
    skipped: list[str] = []
    for catalog_scenario in catalog_entries:
        row = _find_scorecard_row(scorecard, catalog_scenario["source_scorecard_scenario"])
        if row is None:
            skipped.append(catalog_scenario["id"])
            continue
        scenarios.append(build_baseline_scenario(catalog_scenario, row, benchmark_mode))

    # Deterministic order — sort by id
    scenarios.sort(key=lambda s: s["id"])

    if skipped:
        print(
            f"warning: catalog scenarios missing in scorecard, skipped: {skipped}",
            file=sys.stderr,
        )

    return {
        "schema_version": "performance-baseline.v1",
        "service": "ao-kernel",
        "guard_flags": {
            "support_widening_allowed": False,
            "production_platform_claim_allowed": False,
            "live_adapter_execution_allowed": False,
        },
        "generated_from": {
            "scorecard_schema_version": scorecard.get("schema_version", "v1"),
            "source_git_sha": source_git_sha,
            "source_git_ref": source_git_ref,
            "benchmark_mode": benchmark_mode,
            "python_version": python_version,
            "runner_os": runner_os,
            "generated_at": generated_at,
        },
        "candidate_baseline": True,
        "sample_count": 1,
        "variance_profile": "single_ci_run",
        "scenarios": scenarios,
    }


def _canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Promote scorecard to baseline")
    parser.add_argument("--scorecard", type=Path, required=True)
    parser.add_argument("--scenario-catalog", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-git-sha", type=str, required=True)
    parser.add_argument("--source-git-ref", type=str, required=True)
    parser.add_argument(
        "--benchmark-mode",
        type=str,
        required=True,
        choices=("fast", "full"),
    )
    parser.add_argument("--python-version", type=str, required=True)
    parser.add_argument("--runner-os", type=str, required=True)
    parser.add_argument(
        "--generated-at",
        type=str,
        required=True,
        help="ISO 8601 timestamp (UTC, Z-suffix); must be supplied explicitly so the output is deterministic.",
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Permit writing an empty baseline when no catalog entries match the mode/enforcement filter.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render baseline JSON to stdout without writing the output file.",
    )
    args = parser.parse_args(argv)

    catalog = _load_json(args.scenario_catalog)
    scorecard = _load_json(args.scorecard)

    baseline = build_baseline(
        catalog,
        scorecard,
        benchmark_mode=args.benchmark_mode,
        source_git_sha=args.source_git_sha,
        source_git_ref=args.source_git_ref,
        python_version=args.python_version,
        runner_os=args.runner_os,
        generated_at=args.generated_at,
    )

    if not baseline["scenarios"] and not args.allow_empty:
        print(
            f"error: 0 policy_threshold scenarios selected for mode={args.benchmark_mode}; "
            "advisory_only/mismatched-mode entries skipped. "
            "Pass --allow-empty to write an empty baseline explicitly.",
            file=sys.stderr,
        )
        return EXIT_EMPTY_SELECTION

    text = _canonical_json(baseline)
    if args.dry_run:
        sys.stdout.write(text)
        return 0
    args.out.write_text(text)
    print(
        f"wrote {args.out} with {len(baseline['scenarios'])} scenarios "
        f"(mode={args.benchmark_mode})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
