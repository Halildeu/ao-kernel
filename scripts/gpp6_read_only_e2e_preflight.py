#!/usr/bin/env python3
"""Generate the GPP-6 read-only E2E preparation preflight report.

This script does not run GPP-6. It verifies that the repo-intelligence
closeout evidence is present, records that upstream protected-runtime gates are
still blocking execution, and keeps all runtime side effects disabled.
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

_SCHEMA = "gpp6-read-only-e2e-preflight.schema.v1.json"
_PASS_BLOCKED_DECISION = "read_only_e2e_preflight_ready_execution_blocked_no_support_widening"
_PASS_READY_DECISION = "read_only_e2e_preflight_ready_no_support_widening"
_BLOCKED_DECISION = "blocked_read_only_e2e_preflight_no_support_widening"

_GPP5D = {
    "id": "GPP-5d",
    "decision": "repo_intelligence_read_only_workflow_surface_closed_no_support_widening",
    "issue": "https://github.com/Halildeu/ao-kernel/issues/559",
    "record": ".claude/plans/GPP-5d-REPO-INTELLIGENCE-CLOSEOUT.md",
}

_CHAIN_STEPS = (
    "repo_scan_index_query",
    "explicit_context_handoff",
    "protected_real_adapter",
    "governed_workflow",
    "review_findings_or_patch_plan_artifact",
    "evidence_timeline",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the GPP-6 read-only E2E preflight report")
    parser.add_argument("--output", choices=("json", "text"), default="text", help="Output format")
    parser.add_argument("--report-path", type=Path, help="Optional path to persist the JSON report")
    parser.add_argument(
        "--fail-on-execution-blocked",
        action="store_true",
        help="Return exit code 1 when upstream gates still block GPP-6 execution.",
    )
    args = parser.parse_args(argv)

    report = build_gpp6_read_only_e2e_preflight(repo_root=_REPO_ROOT)
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
        print(f"execution_status: {report['execution_status']}")
        if report["upstream_blockers"]:
            print(f"upstream_blockers: {', '.join(report['upstream_blockers'])}")
        if report["overall_status"] == "blocked":
            print(f"blocked_reason: {report['blocked_reason']}")

    if args.fail_on_execution_blocked and report["execution_status"] != "ready_for_protected_rehearsal":
        return 1
    return 0 if report["overall_status"] == "ready" else 1


def build_gpp6_read_only_e2e_preflight(*, repo_root: Path) -> JsonDict:
    status_payload = _load_json(repo_root / ".claude" / "plans" / "gpp_status.v1.json")
    gpp5d = _completed_wp_summary(status_payload=status_payload, repo_root=repo_root, expected=_GPP5D)
    entry_criteria = [
        _gpp5d_entry(gpp5d),
        _gpp2_entry(status_payload),
        _gpp4_entry(status_payload),
    ]
    upstream_blockers = _upstream_blockers(entry_criteria)
    program_flags = _program_flag_summary(status_payload)
    safety = _safety_summary()
    findings = _collect_findings(gpp5d=gpp5d, program_flags=program_flags, safety=safety)
    ready = not findings
    execution_status = "ready_for_protected_rehearsal" if ready and not upstream_blockers else "blocked_by_upstream_gates"

    if not ready:
        decision = _BLOCKED_DECISION
    elif execution_status == "ready_for_protected_rehearsal":
        decision = _PASS_READY_DECISION
    else:
        decision = _PASS_BLOCKED_DECISION

    report: JsonDict = {
        "schema_version": "1",
        "artifact_kind": "gpp6_read_only_e2e_preflight",
        "program_id": "GPP-6a",
        "issue": {
            "number": 561,
            "url": "https://github.com/Halildeu/ao-kernel/issues/561",
        },
        "overall_status": "ready" if ready else "blocked",
        "decision": decision,
        "execution_status": execution_status,
        "upstream_blockers": upstream_blockers,
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution_allowed": False,
        "protected_workflow_dispatch_allowed": False,
        "remote_write_allowed": False,
        "gpp5d_closeout": gpp5d,
        "entry_criteria": entry_criteria,
        "execution_plan": _execution_plan(),
        "program_flags": program_flags,
        "safety": safety,
        "next_actions": [
            "Use this preflight as GPP-6 preparation evidence only.",
            "Keep GPP-6 execution blocked until GPP-2 protected gate evidence and GPP-4 read-only adapter decision are ready.",
            "Do not dispatch protected workflows, invoke live adapters, write artifacts, write vectors, or perform remote writes from this slice.",
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
        raise ValueError(f"invalid GPP-6 read-only E2E preflight report: {messages}")


def _completed_wp_summary(*, status_payload: JsonDict, repo_root: Path, expected: JsonDict) -> JsonDict:
    completed = {
        _string(item.get("id")): item
        for item in _list(status_payload.get("completed_wps"))
        if isinstance(item, dict)
    }
    item = completed.get(expected["id"], {})
    findings: list[str] = []
    if not item:
        findings.append("completed_wp_missing")
    if _string(item.get("decision")) != expected["decision"]:
        findings.append("decision_mismatch")
    if _string(item.get("issue")) != expected["issue"]:
        findings.append("issue_mismatch")
    if _string(item.get("record")) != expected["record"]:
        findings.append("record_path_mismatch")
    if not (repo_root / expected["record"]).is_file():
        findings.append("record_file_missing")
    return {
        "id": expected["id"],
        "status": "ready" if not findings else "blocked",
        "decision": _string(item.get("decision")) or expected["decision"],
        "issue": _string(item.get("issue")) or expected["issue"],
        "record": _string(item.get("record")) or expected["record"],
        "findings": findings,
    }


def _gpp5d_entry(gpp5d: JsonDict) -> JsonDict:
    return {
        "id": "gpp5d_repo_intelligence_closeout",
        "status": "ready" if gpp5d["status"] == "ready" else "blocked",
        "required_for_execution": True,
        "evidence": gpp5d["record"],
        "findings": list(gpp5d["findings"]),
    }


def _gpp2_entry(status_payload: JsonDict) -> JsonDict:
    current_wp = status_payload.get("current_wp", {})
    ready = isinstance(current_wp, dict) and current_wp.get("id") == "GPP-2" and current_wp.get("status") != "blocked"
    return {
        "id": "gpp2_protected_gate",
        "status": "ready" if ready else "blocked",
        "required_for_execution": True,
        "evidence": _string(current_wp.get("issue")) if isinstance(current_wp, dict) else "",
        "findings": [] if ready else ["gpp2_protected_gate_blocked"],
    }


def _gpp4_entry(status_payload: JsonDict) -> JsonDict:
    completed_ids = {
        _string(item.get("id"))
        for item in _list(status_payload.get("completed_wps"))
        if isinstance(item, dict)
    }
    ready = "GPP-4" in completed_ids
    return {
        "id": "gpp4_read_only_adapter_decision",
        "status": "ready" if ready else "missing",
        "required_for_execution": True,
        "evidence": "completed_wps:GPP-4" if ready else "",
        "findings": [] if ready else ["gpp4_real_adapter_read_only_decision_missing"],
    }


def _upstream_blockers(entry_criteria: list[JsonDict]) -> list[str]:
    blockers: list[str] = []
    for item in entry_criteria:
        if item["id"] == "gpp5d_repo_intelligence_closeout":
            continue
        blockers.extend(_string(finding) for finding in item["findings"])
    return [blocker for blocker in blockers if blocker]


def _execution_plan() -> list[JsonDict]:
    return [
        {
            "step": step,
            "status": "not_executed",
            "protected_workflow_dispatch": False,
            "live_adapter_execution": False,
            "remote_side_effects": False,
        }
        for step in _CHAIN_STEPS
    ]


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


def _safety_summary() -> JsonDict:
    return {
        "status": "pass",
        "protected_workflow_dispatch": False,
        "live_adapter_execution": False,
        "remote_write": False,
        "context_compiler_auto_feed": False,
        "mcp_repo_intelligence": False,
        "root_export": False,
        "artifact_writes": False,
        "vector_writes": False,
        "secret_value_readback": False,
        "support_widening": False,
        "production_platform_claim": False,
        "findings": [],
    }


def _collect_findings(*, gpp5d: JsonDict, program_flags: JsonDict, safety: JsonDict) -> list[str]:
    findings: list[str] = []
    if gpp5d["status"] != "ready":
        findings.append("gpp5d_closeout:" + ",".join(gpp5d["findings"]))
    if program_flags["status"] != "pass":
        findings.append("program_flags:" + ",".join(program_flags["findings"]))
    if safety["status"] != "pass":
        findings.append("safety:" + ",".join(safety["findings"]))
    return findings


def _load_json(path: Path) -> JsonDict:
    return json.loads(path.read_text(encoding="utf-8"))


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return value if isinstance(value, str) else ""


if __name__ == "__main__":
    raise SystemExit(main())
