#!/usr/bin/env python3
"""Read-only readiness gate for repo-intelligence tier promotion.

This script records whether the explicit repo-intelligence scan/index/query
surface is ready for a later operator promotion decision. It never widens
support by itself.
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

_SCHEMA = "repo-intelligence-tier-promotion-readiness.schema.v1.json"
_READY_DECISION = "ready_for_operator_promotion_decision"
_BLOCKED_DECISION = "blocked_operator_bound_evidence_required"

_MANIFEST_GATES: tuple[tuple[str, str, str], ...] = (
    (
        "explicit_operator_authorization",
        "Operator authorization record for a repo-intelligence tier-promotion supersession is attached.",
        "operator_authorization_record_missing",
    ),
    (
        "general_purpose_platform_claim_authorization",
        "Operator authorization explicitly targets a general-purpose production platform claim, not only repo-intelligence tier hardening.",
        "general_purpose_platform_claim_authorization_missing",
    ),
    (
        "guardrail_hardening_matrix",
        "Promotion-grade guardrail matrix covers AST/chunk edge cases, namespace isolation, stale vector cleanup, no-root-write, no-auto-feed, and no-MCP exposure.",
        "guardrail_hardening_matrix_missing",
    ),
    (
        "vector_backend_e2e_evidence",
        "Configured vector backend evidence proves explicit write, stale cleanup, namespace isolation, and read-only query hash/line validation.",
        "vector_backend_e2e_evidence_missing",
    ),
    (
        "scan_index_query_packaging_smoke",
        "Wheel-installed scan/index/query smoke passes outside the source checkout with fail-closed missing-backend paths.",
        "scan_index_query_packaging_smoke_missing",
    ),
    (
        "operator_verified_runtime_semantics",
        "Operator-verified semantics confirm how repo-intelligence participates in the platform claim without hidden context injection.",
        "operator_verified_runtime_semantics_missing",
    ),
    (
        "cross_lane_production_matrix_evidence",
        "Full production matrix evidence covers the non-repo-intelligence lanes needed for a general-purpose production platform claim.",
        "cross_lane_production_matrix_evidence_missing",
    ),
    (
        "gp59_reclassification_plan",
        "GP-5.9 BC-1..BC-10 reclassification plan identifies every blocker removed, retained, or replaced by the platform-claim supersession.",
        "gp59_reclassification_plan_missing",
    ),
    (
        "support_boundary_transition_plan",
        "PUBLIC-BETA, SUPPORT-BOUNDARY, KNOWN-BUGS, and GP-5.9 transition text is prepared for a later platform-claim decision PR without changing the current boundary here.",
        "support_boundary_transition_plan_missing",
    ),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the repo-intelligence tier promotion readiness report"
    )
    parser.add_argument(
        "--output",
        choices=("json", "text"),
        default="text",
        help="Output format",
    )
    parser.add_argument(
        "--evidence-manifest",
        type=Path,
        help=(
            "Optional JSON manifest with boolean gate keys. This script still "
            "does not grant support widening; it can only mark the package "
            "ready for a later operator decision."
        ),
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        help="Optional path to persist the JSON report",
    )
    args = parser.parse_args(argv)

    report = build_readiness(
        repo_root=_REPO_ROOT,
        evidence_manifest_path=args.evidence_manifest,
    )
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
        print(f"live_adapter_execution: {str(report['live_adapter_execution']).lower()}")
        if report["promotion_blockers"]:
            print("promotion_blockers:")
            for blocker in report["promotion_blockers"]:
                print(f"- {blocker}")
    return 0 if report["overall_status"] == "ready_for_operator_decision" else 1


def build_readiness(
    *,
    repo_root: Path,
    evidence_manifest_path: Path | None = None,
) -> JsonDict:
    evidence_manifest = _load_evidence_manifest(evidence_manifest_path)
    status_payload = _load_json(repo_root / ".claude" / "plans" / "gpp_status.v1.json")

    gates = [
        _gpp_boundary_gate(status_payload),
        _token_gate(
            repo_root=repo_root,
            gate_id="public_beta_current_boundary",
            source_path="docs/PUBLIC-BETA.md",
            summary="Current public matrix still pins repo scan/index/query as Beta/experimental and does not promote the tier.",
            tokens=(
                "`repo scan` read-only repo intelligence",
                "Beta / experimental",
                "`repo index --write-vectors` explicit vector write",
                "`repo query` read-only repo vector retrieval",
                "support_widening=false",
            ),
        ),
        _token_gate(
            repo_root=repo_root,
            gate_id="support_boundary_current_boundary",
            source_path="docs/SUPPORT-BOUNDARY.md",
            summary="Current support boundary still treats repo-intelligence as beta/operator-managed or experimental.",
            tokens=(
                "The `repo scan` surface is Beta / experimental and read-only.",
                "The `repo index --write-vectors` surface is Beta / experimental explicit-write",
                "The `repo query` surface is Beta / experimental read-only retrieval.",
                "`support_widening=false`",
            ),
        ),
    ]
    gates.extend(_manifest_gate(evidence_manifest, *spec) for spec in _MANIFEST_GATES)

    promotion_blockers = sorted(
        dict.fromkeys(
            finding
            for gate in gates
            if gate["blocking"]
            for finding in gate["findings"]
        )
    )
    ready = not promotion_blockers

    return {
        "schema_version": "1",
        "artifact_kind": "repo_intelligence_tier_promotion_readiness",
        "program_id": "repo-intelligence-tier-promotion-supersession",
        "overall_status": "ready_for_operator_decision" if ready else "blocked",
        "decision": _READY_DECISION if ready else _BLOCKED_DECISION,
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
        "requested_promotion": {
            "surface": "repo_intelligence_scan_index_query",
            "current_tier": "Beta / experimental",
            "target_tier": "general-purpose production platform claim contributor",
            "target_claim": "general_purpose_production_platform_claim",
            "scope": [
                "repo scan local artifact generation",
                "repo index dry-run write planning",
                "repo index explicit vector writes with confirmation and stale cleanup",
                "repo query read-only vector retrieval",
                "GP-5.9 production platform claim reclassification",
                "cross-lane production matrix evidence",
                "no MCP exposure",
                "no hidden context compiler auto-feed",
                "no root authority file writes",
            ],
        },
        "current_authority": _current_authority(status_payload),
        "gates": gates,
        "promotion_blockers": promotion_blockers,
        "next_actions": _next_actions(ready),
    }


def validate_report(report: JsonDict) -> None:
    schema = load_default("schemas", _SCHEMA)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(report),
        key=lambda error: (list(error.path), error.message),
    )
    if errors:
        messages = "; ".join(error.message for error in errors)
        raise ValueError(f"invalid repo-intelligence tier promotion readiness report: {messages}")


def _current_authority(status_payload: JsonDict) -> JsonDict:
    current_wp = status_payload.get("current_wp") if isinstance(status_payload.get("current_wp"), dict) else {}
    closure = status_payload.get("program_closure") if isinstance(status_payload.get("program_closure"), dict) else {}
    return {
        "program_id": str(status_payload.get("program_id", "missing")),
        "current_wp": str(current_wp.get("id", "missing")),
        "current_status": str(current_wp.get("status", "missing")),
        "exit_decision": str(current_wp.get("exit_decision", "missing")),
        "support_widening_allowed": bool(status_payload.get("support_widening_allowed")),
        "production_platform_claim_allowed": bool(status_payload.get("production_platform_claim_allowed")),
        "live_adapter_execution_allowed": bool(status_payload.get("live_adapter_execution_allowed")),
        "program_closure_decision": closure.get("decision") if isinstance(closure.get("decision"), str) else None,
    }


def _gpp_boundary_gate(status_payload: JsonDict) -> JsonDict:
    authority = _current_authority(status_payload)
    findings: list[str] = []
    if authority["current_wp"] != "GPP-9":
        findings.append("current_wp_not_gpp9")
    if authority["current_status"] != "closed":
        findings.append("gpp9_not_closed")
    if authority["support_widening_allowed"] is not False:
        findings.append("support_widening_allowed_unexpectedly_true")
    if authority["production_platform_claim_allowed"] is not False:
        findings.append("production_platform_claim_allowed_unexpectedly_true")
    if authority["live_adapter_execution_allowed"] is not False:
        findings.append("live_adapter_execution_allowed_unexpectedly_true")
    if authority["program_closure_decision"] != (
        "gpp9_keep_narrow_stable_runtime_authoritative_program_closed_no_live_adapter_execution_no_support_widening_no_production_claim"
    ):
        findings.append("gpp9_program_closure_decision_missing")
    return {
        "id": "current_gpp9_boundary",
        "status": "pass" if not findings else "blocked",
        "blocking": bool(findings),
        "summary": "GPP-9 is closed with no support widening; any promotion must be a separate operator-bound supersession.",
        "evidence": [".claude/plans/gpp_status.v1.json"],
        "findings": findings,
    }


def _token_gate(
    *,
    repo_root: Path,
    gate_id: str,
    source_path: str,
    summary: str,
    tokens: tuple[str, ...],
) -> JsonDict:
    text = _read_text(repo_root / source_path)
    findings = [f"missing_token:{source_path}:{token}" for token in tokens if token not in text]
    return {
        "id": gate_id,
        "status": "pass" if not findings else "blocked",
        "blocking": bool(findings),
        "summary": summary,
        "evidence": [source_path],
        "findings": findings,
    }


def _manifest_gate(
    evidence_manifest: JsonDict,
    gate_id: str,
    summary: str,
    missing_finding: str,
) -> JsonDict:
    passed = evidence_manifest.get(gate_id) is True
    return {
        "id": gate_id,
        "status": "pass" if passed else "blocked",
        "blocking": not passed,
        "summary": summary,
        "evidence": [f"evidence_manifest:{gate_id}=true"] if passed else [],
        "findings": [] if passed else [missing_finding],
    }


def _next_actions(ready: bool) -> list[str]:
    if ready:
        return [
        "Open a separate operator promotion decision PR that consumes this readiness report.",
        "Keep support_widening=false and production_platform_claim=false in this readiness artifact; the later decision artifact owns any boundary change.",
        "Update PUBLIC-BETA, SUPPORT-BOUNDARY, KNOWN-BUGS, and GP-5.9 platform-claim logic only in the promotion decision PR after operator review.",
        ]
    return [
        "Attach explicit operator authorization for the repo-intelligence tier-promotion supersession.",
        "Attach explicit operator authorization for the general-purpose production platform claim target.",
        "Collect the promotion-grade guardrail matrix: AST/chunk edge cases, namespace isolation, stale vector cleanup, no-root-write, no-auto-feed, and no-MCP exposure.",
        "Collect vector backend E2E evidence for explicit writes, stale cleanup, namespace isolation, read-only query validation, and fail-closed missing-backend paths.",
        "Run wheel-installed scan/index/query packaging smoke outside the source checkout.",
        "Collect cross-lane production matrix evidence for real adapter, read-only E2E, controlled write-side, remote PR write, rollback, cost, and release-governance lanes.",
        "Prepare the GP-5.9 BC-1..BC-10 reclassification plan and support boundary transition text, but do not change the live support tier until the decision PR consumes passing evidence.",
    ]


def _load_evidence_manifest(path: Path | None) -> JsonDict:
    if path is None:
        return {}
    loaded = _load_json(path)
    return loaded if isinstance(loaded, dict) else {}


def _load_json(path: Path) -> JsonDict:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


if __name__ == "__main__":
    raise SystemExit(main())
