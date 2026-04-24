#!/usr/bin/env python3
"""Generate the GP-5.9 production platform claim decision report.

The gate closes the GP-5 program against the evidence currently present on
`origin/main`. It is intentionally allowed to close as a non-promotion decision:
missing protected live-adapter evidence must remain a visible blocker, not a
fake green production claim.
"""

from __future__ import annotations

import argparse
import importlib.util
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

_SCHEMA = "gp5-production-platform-claim-decision.schema.v1.json"
_KEEP_NARROW = "keep_narrow_stable_runtime"
_DEFER = "defer_support_widening"

_EVIDENCE_REQUIREMENTS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "gp5_program_plan",
        ".claude/plans/GP-5-GENERAL-PURPOSE-PRODUCTION-PLATFORM-INTEGRATION.md",
        ("GP-5.9", "Production platform claim decision", "BC-1", "BC-10"),
    ),
    (
        "gp5_status",
        ".claude/plans/POST-BETA-CORRECTNESS-EXPANSION-STATUS.md",
        ("GP-5.9", "production platform claim decision", "GP-5.8"),
    ),
    (
        "gp58_plan",
        ".claude/plans/GP-5.8-OPERATIONS-SUPPORT-PACKAGE.md",
        ("operations_package_ready_no_support_widening", "production_platform_claim=false"),
    ),
    (
        "gp59_plan",
        ".claude/plans/GP-5.9-PRODUCTION-PLATFORM-CLAIM-DECISION.md",
        ("keep_narrow_stable_runtime", "support_widening=false", "production_platform_claim=false"),
    ),
    (
        "public_beta",
        "docs/PUBLIC-BETA.md",
        ("GP-5 production platform claim decision", "keep_narrow_stable_runtime"),
    ),
    (
        "support_boundary",
        "docs/SUPPORT-BOUNDARY.md",
        ("GP-5.9", "keep_narrow_stable_runtime", "production_platform_claim=false"),
    ),
    (
        "known_bugs",
        "docs/KNOWN-BUGS.md",
        ("GP-5.9 closeout interpretation", "KB-001", "KB-002"),
    ),
    (
        "operations_runbook",
        "docs/OPERATIONS-RUNBOOK.md",
        ("GP-5.9 production claim decision incidents", "keep_narrow_stable_runtime"),
    ),
    (
        "gp58_script",
        "scripts/gp5_operations_support_package.py",
        ("operations_package_ready_no_support_widening", "GP-5.9"),
    ),
    (
        "packaging_smoke",
        "scripts/packaging_smoke.py",
        ("examples/demo_review.py", '"ao_kernel", "version"'),
    ),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the GP-5.9 production platform claim decision report"
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

    report = build_platform_claim_decision(repo_root=_REPO_ROOT)
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
    return 0 if report["overall_status"] == "closed" else 1


def build_platform_claim_decision(*, repo_root: Path) -> JsonDict:
    evidence_surfaces = [
        _coverage_item(repo_root, surface, source_path, tokens)
        for surface, source_path, tokens in _EVIDENCE_REQUIREMENTS
    ]
    gp58 = _gp58_operations_package(repo_root)
    success_criteria = _success_criteria(gp58)
    promotion_blockers = _promotion_blockers(success_criteria)
    support_boundary = _support_boundary_summary(repo_root)

    blockers = _report_blockers(
        evidence_surfaces=evidence_surfaces,
        gp58=gp58,
        support_boundary=support_boundary,
    )
    closed = not blockers

    report: JsonDict = {
        "schema_version": "1",
        "artifact_kind": "gp5_production_platform_claim_decision",
        "program_id": "GP-5.9",
        "issue": {
            "number": 455,
            "url": "https://github.com/Halildeu/ao-kernel/issues/455",
        },
        "tracker": {
            "number": 424,
            "url": "https://github.com/Halildeu/ao-kernel/issues/424",
        },
        "overall_status": "closed" if closed else "blocked",
        "decision": _KEEP_NARROW if closed else _DEFER,
        "support_widening": False,
        "production_platform_claim": False,
        "stable_runtime_boundary": "narrow_production_runtime",
        "promoted_tiers": [],
        "success_criteria": success_criteria,
        "promotion_blockers": promotion_blockers,
        "evidence_surfaces": evidence_surfaces,
        "gp58_operations_package": gp58,
        "support_boundary": support_boundary,
        "next_actions": [
            "Keep GP-5.1b blocked until protected live-adapter environment and credential handle attestation exists.",
            "Continue RI-5a export-plan work independently; do not auto-feed repo intelligence into workflows from GP-5.9.",
            "Open a new widening program only when protected real-adapter evidence and support-boundary changes are ready together.",
        ],
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
        raise ValueError(f"invalid GP-5.9 production claim decision report: {messages}")


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


def _gp58_operations_package(repo_root: Path) -> JsonDict:
    module_path = repo_root / "scripts" / "gp5_operations_support_package.py"
    if not module_path.exists():
        return {
            "status": "missing",
            "decision": "missing",
            "findings": ["gp58_script_missing"],
        }

    spec = importlib.util.spec_from_file_location("gp5_operations_support_package", module_path)
    if spec is None or spec.loader is None:
        return {
            "status": "missing",
            "decision": "missing",
            "findings": ["gp58_script_unloadable"],
        }
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.build_operations_support_package(repo_root=repo_root)
    module.validate_report(report)
    findings: list[str] = []
    if report.get("overall_status") != "ready":
        findings.append("gp58_not_ready")
    if report.get("decision") != "operations_package_ready_no_support_widening":
        findings.append("gp58_decision_not_ready")
    if report.get("support_widening") is not False:
        findings.append("gp58_support_widening")
    if report.get("production_platform_claim") is not False:
        findings.append("gp58_platform_claim")
    return {
        "status": "ready" if not findings else "blocked",
        "decision": str(report.get("decision", "missing")),
        "findings": findings,
    }


def _success_criteria(gp58: JsonDict) -> list[JsonDict]:
    gp58_ready = gp58["status"] == "ready"
    return [
        _criterion(
            "BC-1",
            "blocked",
            "No real adapter is production-certified by protected gate evidence.",
            ["GP-5.1a protected prerequisite audit remains blocked/unattested."],
            ["protected_live_adapter_gate_unattested"],
        ),
        _criterion(
            "BC-2",
            "pass",
            "Repo-intelligence retrieval remains explicit opt-in with hash/stale evidence.",
            ["GP-5.3a..GP-5.3e beta explicit-handoff contracts are on main."],
            [],
        ),
        _criterion(
            "BC-3",
            "pass",
            "Read-only workflow rehearsal produces attributable deterministic artifacts.",
            ["GP-5.4a read-only rehearsal passed with visible intent handoff."],
            [],
        ),
        _criterion(
            "BC-4",
            "pass",
            "Write-side patch/test is bounded by disposable worktree rehearsal evidence.",
            ["GP-5.5a contract and GP-5.5b controlled local rehearsal passed."],
            [],
        ),
        _criterion(
            "BC-5",
            "pass",
            "Remote PR write remains sandbox/disposable with rollback evidence.",
            ["GP-5.6a disposable PR rehearsal passed without production support widening."],
            [],
        ),
        _criterion(
            "BC-6",
            "pass" if gp58_ready else "blocked",
            "Docs, tests, runbooks, known-bugs, and support boundary are aligned.",
            ["GP-5.8 operations package is ready."],
            [] if gp58_ready else ["gp58_operations_package_not_ready"],
        ),
        _criterion(
            "BC-7",
            "pass",
            "Missing auth and denied live-write states remain explicit non-pass states.",
            ["GP-5.1a and GP-5.6a use blocked/fail-closed evidence paths."],
            [],
        ),
        _criterion(
            "BC-8",
            "pass",
            "Packaging freshness is represented by wheel-installed smoke.",
            ["packaging_smoke remains the release/readiness gate for installed behavior."],
            [],
        ),
        _criterion(
            "BC-9",
            "pass",
            "Existing narrow shipped baseline remains the supported production runtime.",
            ["No GP-5 slice widened support or removed the shipped baseline."],
            [],
        ),
        _criterion(
            "BC-10",
            "blocked",
            "Real-adapter cost/token evidence is unavailable because protected evidence is absent.",
            ["No protected real-adapter production evidence artifact exists."],
            ["real_adapter_usage_and_cost_evidence_missing"],
        ),
    ]


def _criterion(
    criterion_id: str,
    status: str,
    summary: str,
    evidence: list[str],
    blockers: list[str],
) -> JsonDict:
    return {
        "id": criterion_id,
        "status": status,
        "summary": summary,
        "evidence": evidence,
        "blockers": blockers,
    }


def _promotion_blockers(criteria: list[JsonDict]) -> list[str]:
    blockers: list[str] = []
    for criterion in criteria:
        blockers.extend(criterion["blockers"])
    blockers.extend(
        [
            "claude_code_cli_auth_operator_managed",
            "gh_cli_pr_live_write_not_production_promoted",
            "repo_intelligence_context_handoff_not_runtime_auto_fed",
            "kb001_claude_code_cli_operator_managed_auth",
            "kb002_gh_cli_pr_sandbox_only_live_write",
        ]
    )
    return sorted(dict.fromkeys(blockers))


def _support_boundary_summary(repo_root: Path) -> JsonDict:
    path = repo_root / "docs" / "SUPPORT-BOUNDARY.md"
    text = _read_text(path)
    findings: list[str] = []
    for token in ("GP-5.9", "keep_narrow_stable_runtime", "production_platform_claim=false"):
        if token not in text:
            findings.append(f"support_boundary_missing:{token}")
    return {
        "stable_boundary_unchanged": True,
        "general_purpose_claim_granted": False,
        "findings": findings,
    }


def _report_blockers(
    *,
    evidence_surfaces: list[JsonDict],
    gp58: JsonDict,
    support_boundary: JsonDict,
) -> list[str]:
    blockers = [
        f"evidence_surface_blocked:{item['surface']}"
        for item in evidence_surfaces
        if item["status"] != "ready"
    ]
    if gp58["status"] != "ready":
        blockers.append("gp58_operations_package_not_ready")
    if support_boundary["findings"]:
        blockers.append("support_boundary_incomplete")
    return blockers


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


if __name__ == "__main__":
    raise SystemExit(main())
