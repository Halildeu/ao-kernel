#!/usr/bin/env python3
"""Aggregate GP-5.7b full production rehearsal evidence.

This gate intentionally does not run live remote writes by itself. It validates
pre-existing GP-5.7a, GP-5.4a, GP-5.5b, and GP-5.6a JSON evidence reports,
requires three clean pass chains plus one fail-closed chain, and emits a
schema-backed GP-5.7b decision report.
"""

from __future__ import annotations

import argparse
import hashlib
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

_REQUIRED_CLEAN_RUNS = 3
_REQUIRED_FAILURE_RUNS = 1
_ZERO_SHA = "0" * 64

_CONTRACT_SCHEMA = "gp5-full-production-rehearsal-contract.schema.v1.json"
_REPORT_SCHEMA = "gp5-full-production-rehearsal-report.schema.v1.json"
_READ_ONLY_SCHEMA = "gp5-read-only-rehearsal-report.schema.v1.json"
_CONTROLLED_PATCH_SCHEMA = "gp5-controlled-patch-test-rehearsal-report.schema.v1.json"
_DISPOSABLE_PR_SCHEMA = "gp5-disposable-pr-write-rehearsal-report.schema.v1.json"

_PASS_DECISION = "pass_full_production_rehearsal_no_support_widening"
_BLOCKED_DECISION = "blocked_full_production_rehearsal_no_support_widening"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate GP-5.7b full production rehearsal reports"
    )
    parser.add_argument(
        "--matrix-file",
        type=Path,
        required=True,
        help="JSON matrix describing contract, clean runs, and failure runs",
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
        help="Optional path to persist the GP-5.7b JSON report",
    )
    args = parser.parse_args(argv)

    matrix_file = args.matrix_file.resolve()
    matrix = _load_matrix(matrix_file)
    report = build_full_rehearsal_report(matrix=matrix, matrix_base_dir=matrix_file.parent)
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
        print(f"clean_passes: {report['evidence_matrix']['observed_clean_passes']}")
        print(f"failure_blocks: {report['evidence_matrix']['observed_failure_blocks']}")
        if report["overall_status"] == "blocked":
            print(f"blocked_reason: {report['blocked_reason']}")
    return 0 if report["overall_status"] == "pass" else 1


def build_full_rehearsal_report(*, matrix: JsonDict, matrix_base_dir: Path) -> JsonDict:
    contract = _summarize_contract(_resolve_matrix_path(matrix_base_dir, matrix["contract_report"]))
    clean_runs = [
        _summarize_clean_run(run, matrix_base_dir)
        for run in matrix.get("clean_runs", [])
    ]
    failure_runs = [
        _summarize_failure_run(run, matrix_base_dir)
        for run in matrix.get("failure_runs", [])
    ]

    observed_clean_passes = sum(1 for run in clean_runs if run["status"] == "pass")
    observed_failure_blocks = sum(1 for run in failure_runs if run["status"] == "blocked")
    blockers = _top_level_blockers(
        contract=contract,
        clean_runs=clean_runs,
        failure_runs=failure_runs,
        observed_clean_passes=observed_clean_passes,
        observed_failure_blocks=observed_failure_blocks,
    )
    passed = not blockers

    report: JsonDict = {
        "schema_version": "1",
        "artifact_kind": "gp5_full_production_rehearsal_report",
        "program_id": "GP-5.7b",
        "issue": {
            "number": 451,
            "url": "https://github.com/Halildeu/ao-kernel/issues/451",
        },
        "overall_status": "pass" if passed else "blocked",
        "decision": _PASS_DECISION if passed else _BLOCKED_DECISION,
        "support_widening": False,
        "production_platform_claim": False,
        "contract": contract,
        "evidence_matrix": {
            "required_clean_runs": _REQUIRED_CLEAN_RUNS,
            "observed_clean_runs": len(clean_runs),
            "observed_clean_passes": observed_clean_passes,
            "required_failure_runs": _REQUIRED_FAILURE_RUNS,
            "observed_failure_runs": len(failure_runs),
            "observed_failure_blocks": observed_failure_blocks,
        },
        "clean_runs": clean_runs,
        "failure_runs": failure_runs,
        "promotion_decision": {
            "support_widening_allowed": False,
            "next_gate": "GP-5.8",
            "release_impact": "rehearsal_gate_only_no_support_widening",
            "reason": (
                "GP-5.7b aggregates evidence only. Support widening and the "
                "general-purpose production platform claim remain gated by GP-5.8+."
            ),
        },
    }
    if blockers:
        report["blocked_reason"] = "; ".join(blockers)
    return report


def validate_report(report: JsonDict) -> None:
    schema = load_default("schemas", _REPORT_SCHEMA)
    errors = _schema_errors(schema, report)
    if errors:
        raise ValueError(f"invalid GP-5.7b rehearsal report: {'; '.join(errors)}")


def _summarize_contract(path: Path) -> JsonDict:
    payload, sha256, findings = _read_report(path)
    if payload is not None:
        findings.extend(_schema_findings(_CONTRACT_SCHEMA, payload))
        if payload.get("overall_status") != "contract_ready":
            findings.append("contract_overall_status_not_ready")
        if payload.get("decision") != "contract_ready_no_support_widening":
            findings.append("contract_decision_not_ready")
        if payload.get("support_widening") is not False:
            findings.append("contract_support_widening_not_false")
        if payload.get("production_platform_claim") is not False:
            findings.append("contract_production_platform_claim_not_false")
    return {
        "path": str(path),
        "sha256": sha256,
        "status": "pass" if not findings else "fail",
        "program_id": str(payload.get("program_id", "")) if isinstance(payload, dict) else "",
        "decision": str(payload.get("decision", "")) if isinstance(payload, dict) else "",
        "support_widening": bool(payload.get("support_widening")) if isinstance(payload, dict) else False,
        "production_platform_claim": (
            bool(payload.get("production_platform_claim")) if isinstance(payload, dict) else False
        ),
        "findings": findings,
    }


def _summarize_clean_run(run: JsonDict, matrix_base_dir: Path) -> JsonDict:
    read_only = _summarize_read_only(
        _resolve_matrix_path(matrix_base_dir, run["read_only_report"])
    )
    controlled_patch = _summarize_controlled_patch(
        _resolve_matrix_path(matrix_base_dir, run["controlled_patch_report"])
    )
    disposable_pr = _summarize_disposable_pr(
        _resolve_matrix_path(matrix_base_dir, run["disposable_pr_report"])
    )
    findings: list[str] = []
    if read_only["status"] != "pass":
        findings.append("read_only_workflow_not_pass")
    if controlled_patch["status"] != "pass":
        findings.append("controlled_patch_test_not_pass")
    if disposable_pr["status"] != "pass":
        findings.append("disposable_pr_write_not_pass")
    target_kind = str(run.get("target_kind", "sandbox_repo"))
    return {
        "run_id": str(run.get("run_id", "")),
        "status": "pass" if not findings else "blocked",
        "target_kind": target_kind,
        "read_only_workflow": read_only,
        "controlled_patch_test": controlled_patch,
        "disposable_pr_write": disposable_pr,
        "findings": findings,
    }


def _summarize_read_only(path: Path) -> JsonDict:
    payload, sha256, findings = _read_report(path)
    workflow = payload.get("workflow_rehearsal", {}) if isinstance(payload, dict) else {}
    if payload is not None:
        findings.extend(_schema_findings(_READ_ONLY_SCHEMA, payload))
        if payload.get("overall_status") != "pass":
            findings.append("read_only_overall_status_not_pass")
        if payload.get("decision") != "pass_read_only_rehearsal_no_support_widening":
            findings.append("read_only_decision_not_pass")
        if payload.get("support_widening") is not False:
            findings.append("read_only_support_widening_not_false")
        if workflow.get("workflow_id") != "review_ai_flow":
            findings.append("read_only_workflow_id_not_review_ai_flow")
        if workflow.get("adapter_id") != "codex-stub":
            findings.append("read_only_adapter_not_codex_stub")
        if workflow.get("final_state") != "completed":
            findings.append("read_only_final_state_not_completed")
        if workflow.get("remote_side_effects") is not False:
            findings.append("read_only_remote_side_effects_not_false")
    return {
        "path": str(path),
        "sha256": sha256,
        "status": _summary_status(payload, findings),
        "decision": str(payload.get("decision", "")) if isinstance(payload, dict) else "",
        "support_widening": bool(payload.get("support_widening")) if isinstance(payload, dict) else False,
        "workflow_id": str(workflow.get("workflow_id", "")),
        "adapter_id": str(workflow.get("adapter_id", "")),
        "final_state": workflow.get("final_state"),
        "remote_side_effects": bool(workflow.get("remote_side_effects")) if workflow else False,
        "findings": findings,
    }


def _summarize_controlled_patch(path: Path) -> JsonDict:
    payload, sha256, findings = _read_report(path)
    rollback = payload.get("rollback_plan", {}) if isinstance(payload, dict) else {}
    cleanup = payload.get("cleanup", {}) if isinstance(payload, dict) else {}
    if payload is not None:
        findings.extend(_schema_findings(_CONTROLLED_PATCH_SCHEMA, payload))
        if payload.get("overall_status") != "pass":
            findings.append("controlled_patch_overall_status_not_pass")
        if payload.get("decision") != "pass_controlled_local_patch_test_rehearsal_no_support_widening":
            findings.append("controlled_patch_decision_not_pass")
        for key in (
            "support_widening",
            "runtime_patch_support_widening",
            "remote_side_effects_allowed",
            "active_main_worktree_touched",
        ):
            if payload.get(key) is not False:
                findings.append(f"controlled_patch_{key}_not_false")
        if rollback.get("rollback_status") != "pass":
            findings.append("controlled_patch_rollback_not_pass")
        if rollback.get("idempotency_check_status") != "pass":
            findings.append("controlled_patch_idempotency_not_pass")
        if cleanup.get("worktree_removed") is not True:
            findings.append("controlled_patch_worktree_not_removed")
        if cleanup.get("temp_root_removed") is not True:
            findings.append("controlled_patch_temp_root_not_removed")
    return {
        "path": str(path),
        "sha256": sha256,
        "status": _summary_status(payload, findings),
        "decision": str(payload.get("decision", "")) if isinstance(payload, dict) else "",
        "support_widening": bool(payload.get("support_widening")) if isinstance(payload, dict) else False,
        "runtime_patch_support_widening": (
            bool(payload.get("runtime_patch_support_widening")) if isinstance(payload, dict) else False
        ),
        "remote_side_effects_allowed": (
            bool(payload.get("remote_side_effects_allowed")) if isinstance(payload, dict) else False
        ),
        "active_main_worktree_touched": (
            bool(payload.get("active_main_worktree_touched")) if isinstance(payload, dict) else False
        ),
        "rollback_status": str(rollback.get("rollback_status", "")),
        "cleanup_status": _cleanup_status(cleanup, ("worktree_removed", "temp_root_removed")),
        "findings": findings,
    }


def _summarize_disposable_pr(path: Path) -> JsonDict:
    payload, sha256, findings = _read_report(path)
    target = payload.get("target_repo", {}) if isinstance(payload, dict) else {}
    remote_pr = payload.get("remote_pr", {}) if isinstance(payload, dict) else {}
    remote_branch = payload.get("remote_branch", {}) if isinstance(payload, dict) else {}
    cleanup = payload.get("cleanup", {}) if isinstance(payload, dict) else {}
    if payload is not None:
        findings.extend(_schema_findings(_DISPOSABLE_PR_SCHEMA, payload))
        if payload.get("overall_status") != "pass":
            findings.append("disposable_pr_overall_status_not_pass")
        if payload.get("decision") != "pass_disposable_pr_write_rehearsal_no_support_widening":
            findings.append("disposable_pr_decision_not_pass")
        for key in ("support_widening", "production_remote_pr_support", "arbitrary_repo_support"):
            if payload.get(key) is not False:
                findings.append(f"disposable_pr_{key}_not_false")
        if target.get("production_repo_allowed") is not False:
            findings.append("disposable_pr_production_repo_allowed_not_false")
        if target.get("disposable_guard_status") != "pass":
            findings.append("disposable_pr_guard_not_pass")
        if remote_pr.get("final_state") != "CLOSED":
            findings.append("disposable_pr_final_state_not_closed")
        if remote_branch.get("delete_verified") is not True:
            findings.append("disposable_pr_branch_delete_not_verified")
        if cleanup.get("cleanup_complete") is not True:
            findings.append("disposable_pr_cleanup_not_complete")
    return {
        "path": str(path),
        "sha256": sha256,
        "status": _summary_status(payload, findings),
        "decision": str(payload.get("decision", "")) if isinstance(payload, dict) else "",
        "support_widening": bool(payload.get("support_widening")) if isinstance(payload, dict) else False,
        "production_remote_pr_support": (
            bool(payload.get("production_remote_pr_support")) if isinstance(payload, dict) else False
        ),
        "arbitrary_repo_support": (
            bool(payload.get("arbitrary_repo_support")) if isinstance(payload, dict) else False
        ),
        "repo": str(target.get("repo", "")),
        "disposable_guard_status": str(target.get("disposable_guard_status", "")),
        "cleanup_status": _cleanup_status(cleanup, ("cleanup_complete",)),
        "final_pr_state": str(remote_pr.get("final_state", "")),
        "findings": findings,
    }


def _summarize_failure_run(run: JsonDict, matrix_base_dir: Path) -> JsonDict:
    report_kind = str(run.get("report_kind", ""))
    path = _resolve_matrix_path(matrix_base_dir, run["report_path"])
    payload, sha256, findings = _read_report(path)
    if payload is not None:
        schema_file = {
            "read_only_workflow": _READ_ONLY_SCHEMA,
            "controlled_patch_test": _CONTROLLED_PATCH_SCHEMA,
            "disposable_pr_write": _DISPOSABLE_PR_SCHEMA,
        }.get(report_kind)
        if schema_file is None:
            findings.append("unknown_failure_report_kind")
        else:
            findings.extend(_schema_findings(schema_file, payload))
        if payload.get("overall_status") != "blocked":
            findings.append("failure_scenario_report_not_blocked")
        if payload.get("support_widening") is not False:
            findings.append("failure_scenario_support_widening_not_false")
    status = "blocked" if payload is not None and not findings else "fail"
    return {
        "scenario_id": str(run.get("scenario_id", "")),
        "trigger": str(run.get("trigger", "")),
        "report_kind": report_kind,
        "path": str(path),
        "sha256": sha256,
        "status": status,
        "decision": str(payload.get("decision", "")) if isinstance(payload, dict) else "",
        "support_widening": bool(payload.get("support_widening")) if isinstance(payload, dict) else False,
        "findings": findings,
    }


def _top_level_blockers(
    *,
    contract: JsonDict,
    clean_runs: list[JsonDict],
    failure_runs: list[JsonDict],
    observed_clean_passes: int,
    observed_failure_blocks: int,
) -> list[str]:
    blockers: list[str] = []
    if contract["status"] != "pass":
        blockers.append("contract_report_not_pass")
    if observed_clean_passes < _REQUIRED_CLEAN_RUNS:
        blockers.append(
            f"observed_clean_passes={observed_clean_passes} below required={_REQUIRED_CLEAN_RUNS}"
        )
    if observed_failure_blocks < _REQUIRED_FAILURE_RUNS:
        blockers.append(
            f"observed_failure_blocks={observed_failure_blocks} below required={_REQUIRED_FAILURE_RUNS}"
        )
    for run in clean_runs:
        if run["status"] != "pass":
            blockers.append(f"clean_run_not_pass:{run['run_id']}")
    for run in failure_runs:
        if run["status"] != "blocked":
            blockers.append(f"failure_run_not_fail_closed:{run['scenario_id']}")
    return blockers


def _summary_status(payload: JsonDict | None, findings: list[str]) -> str:
    if not findings:
        return "pass"
    if isinstance(payload, dict) and payload.get("overall_status") == "blocked":
        return "blocked"
    return "fail"


def _cleanup_status(payload: JsonDict, required_true_keys: tuple[str, ...]) -> str:
    if payload and all(payload.get(key) is True for key in required_true_keys):
        return "pass"
    return "fail"


def _read_report(path: Path) -> tuple[JsonDict | None, str, list[str]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return None, _ZERO_SHA, [f"report_read_error:{exc}"]
    sha256 = hashlib.sha256(raw).hexdigest()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, sha256, [f"report_json_error:{exc}"]
    if not isinstance(payload, dict):
        return None, sha256, ["report_json_root_not_object"]
    return payload, sha256, []


def _schema_findings(schema_name: str, payload: JsonDict) -> list[str]:
    schema = load_default("schemas", schema_name)
    return [f"schema:{message}" for message in _schema_errors(schema, payload)]


def _schema_errors(schema: JsonDict, payload: JsonDict) -> list[str]:
    errors = sorted(
        Draft202012Validator(schema).iter_errors(payload),
        key=lambda error: (list(error.path), error.message),
    )
    return [error.message for error in errors]


def _resolve_matrix_path(base_dir: Path, raw_path: str | Path) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def _load_matrix(path: Path) -> JsonDict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("matrix root must be a JSON object")
    for key in ("contract_report", "clean_runs", "failure_runs"):
        if key not in payload:
            raise ValueError(f"matrix missing required key: {key}")
    if not isinstance(payload["clean_runs"], list):
        raise ValueError("matrix clean_runs must be an array")
    if not isinstance(payload["failure_runs"], list):
        raise ValueError("matrix failure_runs must be an array")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
