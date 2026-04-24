#!/usr/bin/env python3
"""Generate the GP-5.8 operations/support package gate report.

The gate is intentionally documentation- and evidence-oriented. It verifies
that operator runbooks, known-bug interpretation, support-boundary wording, and
release-governance notes are present before any later GP-5 production claim
decision is attempted.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ao_kernel.config import load_default  # noqa: E402

JsonDict = dict[str, Any]

_SCHEMA = "gp5-operations-support-package.schema.v1.json"
_PASS_DECISION = "operations_package_ready_no_support_widening"
_BLOCKED_DECISION = "operations_package_blocked_no_support_widening"

_COVERAGE_REQUIREMENTS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "adapter",
        "docs/OPERATIONS-RUNBOOK.md",
        (
            "`claude-code-cli` smoke fails",
            "GP-5.8 adapter incidents",
            "protected live-adapter gate",
        ),
    ),
    (
        "repo_intelligence",
        "docs/OPERATIONS-RUNBOOK.md",
        (
            "GP-5.8 repo-intelligence incidents",
            "`repo scan`",
            "`repo query`",
        ),
    ),
    (
        "vector_backend",
        "docs/OPERATIONS-RUNBOOK.md",
        (
            "GP-5.8 vector backend incidents",
            "`repo index --write-vectors`",
            "embedding API key",
        ),
    ),
    (
        "write_side",
        "docs/OPERATIONS-RUNBOOK.md",
        (
            "GP-5.8 write-side incidents",
            "path-scoped claims",
            "reverse diff",
        ),
    ),
    (
        "pr_rollback",
        "docs/OPERATIONS-RUNBOOK.md",
        (
            "GP-5.8 PR rollback incidents",
            "gh pr close",
            "git/refs/heads",
        ),
    ),
    (
        "packaging_release",
        "docs/OPERATIONS-RUNBOOK.md",
        (
            "Publish or package verification fails",
            "python3 scripts/packaging_smoke.py",
            "post-publish fresh-venv install",
        ),
    ),
    (
        "gp57b_aggregation",
        "docs/OPERATIONS-RUNBOOK.md",
        (
            "GP-5.7b full production rehearsal execution gate fails",
            "blocked_reason",
            "rerunning any live sandbox write",
        ),
    ),
    (
        "known_bugs",
        "docs/KNOWN-BUGS.md",
        (
            "Stable shipped baseline blocker status: **none currently known**",
            "GP-5.8 promotion interpretation",
            "KB-001",
            "KB-002",
        ),
    ),
    (
        "support_boundary",
        "docs/SUPPORT-BOUNDARY.md",
        (
            "GP-5.8",
            "support_widening=false",
            "production_platform_claim=false",
        ),
    ),
    (
        "branch_protection",
        ".claude/plans/GP-5.8-OPERATIONS-SUPPORT-PACKAGE.md",
        (
            "required checks",
            "branch protection",
            "release_gate_impact=none",
        ),
    ),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the GP-5.8 operations/support package report"
    )
    parser.add_argument(
        "--output",
        choices=("json", "text"),
        default="text",
        help="Output format",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        help="Optional path to persist the JSON report",
    )
    args = parser.parse_args(argv)

    report = build_operations_support_package(repo_root=_REPO_ROOT)
    validate_report(report)

    if args.report_path is not None:
        args.report_path.parent.mkdir(parents=True, exist_ok=True)
        args.report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    if args.output == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"overall_status: {report['overall_status']}")
        print(f"decision: {report['decision']}")
        print(f"support_widening: {str(report['support_widening']).lower()}")
        print(f"production_platform_claim: {str(report['production_platform_claim']).lower()}")
        if report["overall_status"] == "blocked":
            print(f"blocked_reason: {report['blocked_reason']}")
    return 0 if report["overall_status"] == "ready" else 1


def build_operations_support_package(*, repo_root: Path) -> JsonDict:
    coverage = [_coverage_item(repo_root, surface, source_path, tokens) for surface, source_path, tokens in _COVERAGE_REQUIREMENTS]
    known_bugs = _known_bugs_summary(repo_root)
    support_boundary = _support_boundary_summary(repo_root)
    branch_protection = _branch_protection_summary(repo_root)

    blockers = _blockers(
        coverage=coverage,
        known_bugs=known_bugs,
        support_boundary=support_boundary,
        branch_protection=branch_protection,
    )
    ready = not blockers

    report: JsonDict = {
        "schema_version": "1",
        "artifact_kind": "gp5_operations_support_package",
        "program_id": "GP-5.8",
        "issue": {
            "number": 453,
            "url": "https://github.com/Halildeu/ao-kernel/issues/453",
        },
        "overall_status": "ready" if ready else "blocked",
        "decision": _PASS_DECISION if ready else _BLOCKED_DECISION,
        "support_widening": False,
        "production_platform_claim": False,
        "runbook_coverage": coverage,
        "known_bugs": known_bugs,
        "support_boundary": support_boundary,
        "branch_protection": branch_protection,
        "promotion_decision": {
            "support_widening_allowed": False,
            "production_claim_allowed": False,
            "next_gate": "GP-5.9",
            "reason": (
                "GP-5.8 makes the platform operable enough for a later claim "
                "decision, but it does not itself widen support."
            ),
        },
    }
    if blockers:
        report["blocked_reason"] = "; ".join(blockers)
    return report


def validate_report(report: JsonDict) -> None:
    schema = load_default("schemas", _SCHEMA)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(report),
        key=lambda error: (list(error.path), error.message),
    )
    if errors:
        messages = "; ".join(error.message for error in errors)
        raise ValueError(f"invalid GP-5.8 operations/support package report: {messages}")


def _coverage_item(repo_root: Path, surface: str, source_path: str, tokens: tuple[str, ...]) -> JsonDict:
    text = _read_text(repo_root / source_path)
    findings = [f"missing_token:{token}" for token in tokens if token not in text]
    return {
        "surface": surface,
        "status": "ready" if not findings else "blocked",
        "source_path": source_path,
        "required_tokens": list(tokens),
        "findings": findings,
    }


def _known_bugs_summary(repo_root: Path) -> JsonDict:
    path = "docs/KNOWN-BUGS.md"
    text = _read_text(repo_root / path)
    findings: list[str] = []
    if "Stable shipped baseline blocker status: **none currently known**" not in text:
        findings.append("stable_blocker_status_missing")
    for bug_id in ("KB-001", "KB-002"):
        if bug_id not in text:
            findings.append(f"known_bug_missing:{bug_id}")
    if "GP-5.8 promotion interpretation" not in text:
        findings.append("gp58_promotion_interpretation_missing")
    return {
        "registry_path": path,
        "stable_shipped_baseline_blockers": 0,
        "open_beta_lane_bugs": ["KB-001", "KB-002"],
        "promotion_blockers": [
            "protected_live_adapter_gate_unattested",
            "claude_code_cli_operator_managed_auth",
            "gh_cli_pr_live_write_not_production_promoted",
        ],
        "findings": findings,
    }


def _support_boundary_summary(repo_root: Path) -> JsonDict:
    path = "docs/SUPPORT-BOUNDARY.md"
    text = _read_text(repo_root / path)
    findings: list[str] = []
    for token in ("GP-5.8", "support_widening=false", "production_platform_claim=false"):
        if token not in text:
            findings.append(f"support_boundary_missing:{token}")
    return {
        "stable_boundary_unchanged": True,
        "promoted_tiers": [],
        "next_possible_claim_gate": "GP-5.9",
        "findings": findings,
    }


def _branch_protection_summary(repo_root: Path) -> JsonDict:
    path = ".claude/plans/GP-5.8-OPERATIONS-SUPPORT-PACKAGE.md"
    text = _read_text(repo_root / path)
    findings: list[str] = []
    for token in ("required checks", "branch protection", "release_gate_impact=none"):
        if token not in text:
            findings.append(f"branch_protection_note_missing:{token}")
    return {
        "required_checks_reviewed": not findings,
        "release_gate_impact": "none",
        "findings": findings,
    }


def _blockers(
    *,
    coverage: list[JsonDict],
    known_bugs: JsonDict,
    support_boundary: JsonDict,
    branch_protection: JsonDict,
) -> list[str]:
    blockers = [
        f"coverage_blocked:{item['surface']}"
        for item in coverage
        if item["status"] != "ready"
    ]
    if known_bugs["findings"]:
        blockers.append("known_bugs_registry_incomplete")
    if support_boundary["findings"]:
        blockers.append("support_boundary_incomplete")
    if branch_protection["findings"]:
        blockers.append("branch_protection_note_incomplete")
    return blockers


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


if __name__ == "__main__":
    raise SystemExit(main())
