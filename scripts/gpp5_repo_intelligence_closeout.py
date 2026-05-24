#!/usr/bin/env python3
"""Generate the GPP-5 repo-intelligence closeout preflight report.

This closeout is deliberately read-only. It verifies that the GPP-5
repo-intelligence building blocks are present and that the runtime still has no
hidden prompt injection, context-compiler auto-feed, MCP exposure, root export,
artifact/vector writes, live adapter execution, support widening, or production
platform claim. It does not run GPP-6.
"""

from __future__ import annotations

import argparse
import inspect
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ao_kernel.config import load_default  # noqa: E402
from ao_kernel.context.agent_coordination import compile_context_sdk  # noqa: E402
from ao_kernel.context.context_compiler import compile_context  # noqa: E402
from ao_kernel.mcp_server import TOOL_DEFINITIONS, TOOL_DISPATCH, create_tool_gateway  # noqa: E402
from ao_kernel import repo_intelligence  # noqa: E402

JsonDict = dict[str, Any]

_SCHEMA = "gpp5-repo-intelligence-closeout.schema.v1.json"
_PASS_DECISION = "repo_intelligence_read_only_workflow_surface_closed_no_support_widening"
_BLOCKED_DECISION = "blocked_repo_intelligence_closeout_no_support_widening"

_REQUIRED_WPS = (
    (
        "GPP-5a",
        "repo_intelligence_product_onboarding_contract_ready_no_support_widening",
        "https://github.com/Halildeu/ao-kernel/issues/553",
        ".claude/plans/GPP-5a-REPO-INTELLIGENCE-PRODUCT-ONBOARDING.md",
    ),
    (
        "GPP-5b",
        "repo_intelligence_explicit_workflow_context_ready_no_support_widening",
        "https://github.com/Halildeu/ao-kernel/issues/555",
        ".claude/plans/GPP-5b-REPO-INTELLIGENCE-WORKFLOW-CONTEXT.md",
    ),
    (
        "GPP-5c",
        "repo_intelligence_read_only_workflow_surface_ready_no_support_widening",
        "https://github.com/Halildeu/ao-kernel/issues/557",
        ".claude/plans/GPP-5c-REPO-INTELLIGENCE-WORKFLOW-SURFACE.md",
    ),
)

_CONTRACT_SURFACES = (
    (
        "product_onboarding",
        "repo-intelligence-product-onboarding.schema.v1.json",
        "validate_repo_intelligence_product_onboarding",
    ),
    (
        "explicit_workflow_context",
        "repo-intelligence-explicit-workflow-context.schema.v1.json",
        "resolve_repo_intelligence_workflow_context",
    ),
    (
        "read_only_workflow_surface",
        "repo-intelligence-read-only-workflow-surface.schema.v1.json",
        "build_repo_intelligence_read_only_workflow_surface",
    ),
)

_FORBIDDEN_CONTEXT_PARAMETERS = {
    "repo_intelligence_context",
    "repo_intelligence_workflow_context",
    "repo_intelligence_workflow_surface",
    "repo_query_context",
    "context_compiler_feed",
}
_FORBIDDEN_WORKFLOW_TOKENS = {
    "repo_intelligence_context",
    "repo_intelligence_workflow_context",
    "repo_intelligence_workflow_surface",
    "repo_query_context",
    "context_compiler_feed",
}
_DISALLOWED_REPO_MCP_TOOL_NAMES = {
    "ao_repo_scan",
    "ao_repo_index",
    "ao_repo_query",
    "ao_repo_export",
    "ao_repo_export_plan",
    "ao_repo_intelligence",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the GPP-5 repo-intelligence closeout preflight report"
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

    report = build_gpp5_repo_intelligence_closeout(repo_root=_REPO_ROOT)
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
        print(f"gpp6_readiness: {report['gpp6_readiness']['status']}")
        if report["overall_status"] == "blocked":
            print(f"blocked_reason: {report['blocked_reason']}")
    return 0 if report["overall_status"] == "closed" else 1


def build_gpp5_repo_intelligence_closeout(*, repo_root: Path) -> JsonDict:
    status_payload = _load_json(repo_root / ".claude" / "plans" / "gpp_status.v1.json")
    work_packages = [
        _completed_wp_summary(
            status_payload=status_payload,
            repo_root=repo_root,
            wp_id=wp_id,
            expected_decision=decision,
            expected_issue=issue,
            record_path=record,
        )
        for wp_id, decision, issue, record in _REQUIRED_WPS
    ]
    contract_surfaces = [
        _contract_surface_summary(surface_id=surface_id, schema_name=schema_name, api_name=api_name)
        for surface_id, schema_name, api_name in _CONTRACT_SURFACES
    ]
    negative_guards = [
        _context_compiler_guard(),
        _workflow_definition_guard(repo_root),
        _mcp_surface_guard(),
    ]
    program_flags = _program_flag_summary(status_payload)
    findings = _collect_findings(
        work_packages=work_packages,
        contract_surfaces=contract_surfaces,
        negative_guards=negative_guards,
        program_flags=program_flags,
    )
    closed = not findings

    report: JsonDict = {
        "schema_version": "1",
        "artifact_kind": "gpp5_repo_intelligence_closeout_preflight",
        "program_id": "GPP-5d",
        "issue": {
            "number": 559,
            "url": "https://github.com/Halildeu/ao-kernel/issues/559",
        },
        "overall_status": "closed" if closed else "blocked",
        "decision": _PASS_DECISION if closed else _BLOCKED_DECISION,
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution_allowed": False,
        "work_packages": work_packages,
        "contract_surfaces": contract_surfaces,
        "negative_runtime_guards": negative_guards,
        "program_flags": program_flags,
        "gpp6_readiness": _gpp6_readiness(status_payload),
        "next_actions": [
            "Use this closeout as repo-intelligence evidence for GPP-6 preparation only.",
            "Keep GPP-6 execution blocked until GPP-2 protected gate and GPP-4 real-adapter read-only decision are explicitly ready.",
            "Do not wire context compiler auto-feed, MCP exposure, root export, or live adapter execution without a later design gate.",
        ],
    }
    if findings:
        report["blocked_reason"] = "; ".join(findings)
    return report


def validate_report(report: JsonDict) -> None:
    schema = load_default("schemas", _SCHEMA)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(report),
        key=lambda error: (list(error.path), error.message),
    )
    if errors:
        messages = "; ".join(error.message for error in errors)
        raise ValueError(f"invalid GPP-5 repo-intelligence closeout report: {messages}")


def _completed_wp_summary(
    *,
    status_payload: JsonDict,
    repo_root: Path,
    wp_id: str,
    expected_decision: str,
    expected_issue: str,
    record_path: str,
) -> JsonDict:
    completed = {
        _string(item.get("id")): item
        for item in _list(status_payload.get("completed_wps"))
        if isinstance(item, dict)
    }
    item = completed.get(wp_id, {})
    findings: list[str] = []
    if not item:
        findings.append("completed_wp_missing")
    if _string(item.get("decision")) != expected_decision:
        findings.append("decision_mismatch")
    if _string(item.get("issue")) != expected_issue:
        findings.append("issue_mismatch")
    if _string(item.get("record")) != record_path:
        findings.append("record_path_mismatch")
    if not (repo_root / record_path).is_file():
        findings.append("record_file_missing")
    return {
        "id": wp_id,
        "status": "ready" if not findings else "blocked",
        "decision": _string(item.get("decision")) or expected_decision,
        "issue": _string(item.get("issue")) or expected_issue,
        "record": _string(item.get("record")) or record_path,
        "findings": findings,
    }


def _contract_surface_summary(*, surface_id: str, schema_name: str, api_name: str) -> JsonDict:
    findings: list[str] = []
    try:
        schema = load_default("schemas", schema_name)
        Draft202012Validator.check_schema(schema)
    except Exception as exc:  # pragma: no cover - defensive report detail
        findings.append(f"schema_invalid:{type(exc).__name__}")
    if not hasattr(repo_intelligence, api_name):
        findings.append("public_api_missing")
    return {
        "surface": surface_id,
        "status": "ready" if not findings else "blocked",
        "schema_ref": schema_name,
        "public_api": f"ao_kernel.repo_intelligence.{api_name}",
        "findings": findings,
    }


def _context_compiler_guard() -> JsonDict:
    findings: list[str] = []
    compile_parameters = set(inspect.signature(compile_context).parameters)
    sdk_parameters = set(inspect.signature(compile_context_sdk).parameters)
    forbidden_compile = sorted(compile_parameters & _FORBIDDEN_CONTEXT_PARAMETERS)
    forbidden_sdk = sorted(sdk_parameters & _FORBIDDEN_CONTEXT_PARAMETERS)
    if forbidden_compile:
        findings.append("compile_context_forbidden_parameters:" + ",".join(forbidden_compile))
    if forbidden_sdk:
        findings.append("compile_context_sdk_forbidden_parameters:" + ",".join(forbidden_sdk))

    compiled = compile_context(
        {
            "session_id": "gpp5-closeout",
            "repo_intelligence_workflow_surface": {
                "content": "hidden repo-intelligence payload must not render"
            },
            "repo_query_context": "# Repo Query Context Pack\n\nhidden payload\n",
            "context_compiler_feed": {
                "enabled": True,
            },
            "ephemeral_decisions": [],
        },
        profile="TASK_EXECUTION",
    )
    if compiled.preamble != "" or compiled.items_included != 0:
        findings.append("repo_intelligence_hidden_payload_rendered")
    return {
        "guard": "context_compiler_auto_feed_disabled",
        "status": "pass" if not findings else "fail",
        "findings": findings,
    }


def _workflow_definition_guard(repo_root: Path) -> JsonDict:
    workflow_dir = repo_root / "ao_kernel" / "defaults" / "workflows"
    findings: list[str] = []
    scanned_files = 0
    for path in sorted(workflow_dir.glob("*.json")):
        scanned_files += 1
        payload = _load_json(path)
        tokens = _payload_tokens(payload)
        matches = sorted(tokens & _FORBIDDEN_WORKFLOW_TOKENS)
        if matches:
            findings.append(f"{path.name}:{','.join(matches)}")
    return {
        "guard": "workflow_definitions_no_repo_intelligence_auto_feed",
        "status": "pass" if not findings else "fail",
        "scanned_files": scanned_files,
        "findings": findings,
    }


def _mcp_surface_guard() -> JsonDict:
    findings: list[str] = []
    tool_names = {str(tool["name"]) for tool in TOOL_DEFINITIONS}
    gateway_tool_names = {str(tool["name"]) for tool in create_tool_gateway().list_tools()}
    if tool_names != set(TOOL_DISPATCH):
        findings.append("tool_definitions_dispatch_mismatch")
    if gateway_tool_names != set(TOOL_DISPATCH):
        findings.append("tool_gateway_dispatch_mismatch")
    disallowed = sorted(tool_names & _DISALLOWED_REPO_MCP_TOOL_NAMES)
    gateway_disallowed = sorted(gateway_tool_names & _DISALLOWED_REPO_MCP_TOOL_NAMES)
    if disallowed:
        findings.append("mcp_disallowed_repo_tools:" + ",".join(disallowed))
    if gateway_disallowed:
        findings.append("gateway_disallowed_repo_tools:" + ",".join(gateway_disallowed))
    if any(name.startswith("ao_repo_") or "repo_intelligence" in name for name in tool_names):
        findings.append("mcp_repo_intelligence_tool_present")
    return {
        "guard": "mcp_repo_intelligence_surface_absent",
        "status": "pass" if not findings else "fail",
        "findings": findings,
    }


def _program_flag_summary(status_payload: JsonDict) -> JsonDict:
    findings: list[str] = []
    if status_payload.get("support_widening_allowed") is not False:
        findings.append("support_widening_allowed_not_false")
    if status_payload.get("production_platform_claim_allowed") is not False:
        findings.append("production_platform_claim_allowed_not_false")
    if status_payload.get("live_adapter_execution_allowed") is not False:
        findings.append("live_adapter_execution_allowed_not_false")
    return {
        "status": "pass" if not findings else "fail",
        "support_widening_allowed": status_payload.get("support_widening_allowed"),
        "production_platform_claim_allowed": status_payload.get("production_platform_claim_allowed"),
        "live_adapter_execution_allowed": status_payload.get("live_adapter_execution_allowed"),
        "findings": findings,
    }


def _gpp6_readiness(status_payload: JsonDict) -> JsonDict:
    completed_ids = {
        _string(item.get("id"))
        for item in _list(status_payload.get("completed_wps"))
        if isinstance(item, dict)
    }
    current_wp = status_payload.get("current_wp", {})
    blockers: list[str] = []
    # GPP-2 is considered closeout-complete when it is either:
    #   a) currently in current_wp with status="closed", OR
    #   b) preserved in completed_wps (post-GPP-3a migration).
    gpp2_closeout_ready = (
        isinstance(current_wp, dict)
        and current_wp.get("id") == "GPP-2"
        and current_wp.get("status") == "closed"
    ) or any(
        isinstance(item, dict)
        and item.get("id") == "GPP-2"
        and ("closed_at" in item or item.get("status") == "closed")
        for item in _list(status_payload.get("completed_wps"))
    )
    if not gpp2_closeout_ready:
        blockers.append("gpp2_protected_gate_blocked")
    if "GPP-4" not in completed_ids:
        blockers.append("gpp4_real_adapter_read_only_decision_missing")
    return {
        "status": "ready" if not blockers else "blocked_by_upstream_gates",
        "entry_criteria": [
            "GPP-4 production-certified read-only adapter decision or explicit protected beta permission",
            "GPP-5 repo-intelligence workflow context ingestion closeout",
        ],
        "blockers": blockers,
        "support_widening_allowed": False,
        "production_platform_claim_allowed": False,
        "live_adapter_execution_allowed": False,
    }


def _collect_findings(
    *,
    work_packages: list[JsonDict],
    contract_surfaces: list[JsonDict],
    negative_guards: list[JsonDict],
    program_flags: JsonDict,
) -> list[str]:
    findings: list[str] = []
    for item in work_packages:
        if item["status"] != "ready":
            findings.append(f"{item['id']}:{','.join(item['findings'])}")
    for item in contract_surfaces:
        if item["status"] != "ready":
            findings.append(f"{item['surface']}:{','.join(item['findings'])}")
    for item in negative_guards:
        if item["status"] != "pass":
            findings.append(f"{item['guard']}:{','.join(item['findings'])}")
    if program_flags["status"] != "pass":
        findings.append("program_flags:" + ",".join(program_flags["findings"]))
    return findings


def _payload_tokens(payload: Any) -> set[str]:
    tokens: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            tokens.add(str(key))
            tokens.update(_payload_tokens(value))
    elif isinstance(payload, list):
        for value in payload:
            tokens.update(_payload_tokens(value))
    elif isinstance(payload, str):
        tokens.add(payload)
    return tokens


def _load_json(path: Path) -> JsonDict:
    return json.loads(path.read_text(encoding="utf-8"))


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return value if isinstance(value, str) else ""


if __name__ == "__main__":
    raise SystemExit(main())
