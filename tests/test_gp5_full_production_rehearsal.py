from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _module():
    module_path = _repo_root() / "scripts" / "gp5_full_production_rehearsal.py"
    spec = importlib.util.spec_from_file_location("gp5_full_production_rehearsal", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _schema_errors(payload: dict[str, Any]) -> list[str]:
    schema = load_default(
        "schemas",
        "gp5-full-production-rehearsal-report.schema.v1.json",
    )
    errors = Draft202012Validator(schema).iter_errors(payload)
    return sorted(error.message for error in errors)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _contract() -> dict[str, Any]:
    helper_path = _repo_root() / "tests" / "test_gp5_full_production_rehearsal_contract.py"
    spec = importlib.util.spec_from_file_location("gp57a_contract_helpers", helper_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return copy.deepcopy(module._valid_contract())  # noqa: SLF001


def _read_only_report() -> dict[str, Any]:
    return {
        "schema_version": "1",
        "artifact_kind": "gp5_read_only_workflow_rehearsal_report",
        "overall_status": "pass",
        "decision": "pass_read_only_rehearsal_no_support_widening",
        "support_widening": False,
        "repo_intelligence_handoff": {
            "mode": "explicit_operator_markdown",
            "source": "deterministic_contract_fixture",
            "repo_query_command_contract": "python3 -m ao_kernel repo query --output markdown",
            "generation_steps": ["fixture"],
            "markdown_sha256": "a" * 64,
            "markdown_bytes": 1,
            "hidden_injection": False,
            "mcp_tool_used": False,
            "root_export_used": False,
            "context_compiler_auto_feed": False,
        },
        "workflow_rehearsal": {
            "workflow_id": "review_ai_flow",
            "adapter_id": "codex-stub",
            "execution_mode": "wheel_installed_temp_venv",
            "command": ["python3", "examples/demo_review.py", "--cleanup"],
            "returncode": 0,
            "final_state": "completed",
            "remote_side_effects": False,
            "stdout_sha256": "b" * 64,
            "stderr_sha256": "c" * 64,
        },
    }


def _controlled_patch_report(*, support_widening: bool = False) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "artifact_kind": "gp5_controlled_patch_test_rehearsal_report",
        "program_id": "GP-5.5b",
        "overall_status": "pass",
        "decision": "pass_controlled_local_patch_test_rehearsal_no_support_widening",
        "support_widening": support_widening,
        "runtime_patch_support_widening": False,
        "remote_side_effects_allowed": False,
        "active_main_worktree_touched": False,
        "source_repo": {
            "path": "/tmp/source",
            "head_sha": "abcdef1234567890",
            "dirty_state": [],
        },
        "target_worktree": {
            "kind": "disposable_worktree",
            "path": "/tmp/target",
            "separate_from_operator_main": True,
            "dirty_state_preflight": [],
            "dirty_state_after_rollback": [],
            "cleanup_required": True,
        },
        "patch": {
            "patch_id": "gp5-5b-rehearsal",
            "changed_paths": ["gp5_controlled_patch_rehearsal_target.txt"],
            "lines_added": 1,
            "lines_removed": 0,
            "diff_preview_status": "pass",
            "apply_status": "pass",
            "reverse_diff_id": "reverse-1",
            "reverse_diff_sha256": "d" * 64,
        },
        "write_ownership": {
            "path_scoped_claims_required": True,
            "owner_agent_id": "gp5-5b-controlled-patch-test-rehearsal",
            "apply_claims": [
                {
                    "area": "path",
                    "resource_id": "gp5_controlled_patch_rehearsal_target.txt",
                    "claim_id": "claim-1",
                    "fencing_token": 1,
                }
            ],
            "rollback_claims": [
                {
                    "area": "path",
                    "resource_id": "gp5_controlled_patch_rehearsal_target.txt",
                    "claim_id": "claim-2",
                    "fencing_token": 2,
                }
            ],
            "claims_released": True,
            "live_claims_after": [],
        },
        "apply_boundary": {
            "diff_preview_artifact_required": True,
            "explicit_operator_approval_required": True,
            "explicit_operator_approval_observed": True,
            "write_without_preview_allowed": False,
        },
        "test_plan": {
            "targeted_tests_required": True,
            "explainable_selection_required": True,
            "targeted_test_commands": [["python3", "-c", "pass"]],
            "targeted_test_status": "pass",
            "full_gate_fallback_required": True,
            "full_gate_fallback_command": ["pytest"],
            "full_gate_fallback_status": "available_not_run",
        },
        "rollback_plan": {
            "reverse_diff_required": True,
            "rollback_status": "pass",
            "rollback_verification_status": "pass",
            "idempotency_check_status": "pass",
        },
        "cleanup": {
            "worktree_remove_attempted": True,
            "worktree_removed": True,
            "temp_root_removed": True,
        },
        "evidence_artifacts": {
            "diff_preview_artifact": {"status": "not_created"},
            "apply_decision_artifact": {"status": "not_created"},
            "reverse_diff_artifact": {"status": "not_created"},
        },
        "promotion_decision": {
            "support_widening_allowed": False,
            "next_gate": "GP-5.6a",
            "reason": "local rehearsal only",
        },
    }


def _disposable_pr_report(*, status: str = "pass", production_support: bool = False) -> dict[str, Any]:
    passed = status == "pass"
    report = {
        "schema_version": "1",
        "artifact_kind": "gp5_disposable_pr_write_rehearsal_report",
        "program_id": "GP-5.6a",
        "overall_status": "pass" if passed else "blocked",
        "decision": (
            "pass_disposable_pr_write_rehearsal_no_support_widening"
            if passed
            else "blocked_disposable_pr_write_rehearsal_no_support_widening"
        ),
        "support_widening": False,
        "production_remote_pr_support": production_support,
        "arbitrary_repo_support": production_support,
        "local_patch_precondition": {
            "report_path": "gp55b.json",
            "report_sha256": "e" * 64,
            "status": "pass",
            "overall_status": "pass",
            "decision": "pass_controlled_local_patch_test_rehearsal_no_support_widening",
            "support_widening": False,
            "remote_side_effects_allowed": False,
            "rollback_status": "pass",
            "cleanup_status": "pass",
            "findings": [],
        },
        "target_repo": {
            "repo": "Halildeu/ao-kernel-sandbox" if passed else "Halildeu/ao-kernel",
            "base_ref": "main",
            "head_ref": "smoke/gp56a-test",
            "disposable_keyword": "sandbox",
            "disposable_guard_status": "pass" if passed else "fail",
            "live_write_opt_in": True,
            "production_repo_allowed": production_support,
        },
        "remote_branch": {
            "create_status": "pass" if passed else "not_run",
            "seed_commit_status": "pass" if passed else "not_run",
            "delete_attempted": passed,
            "delete_status": "pass" if passed else "not_run",
            "delete_verified": passed,
            "evidence_file_path": "gp5-rehearsals/gp56a.txt",
            "created_commit_sha": "commit-sha" if passed else "",
        },
        "remote_pr": {
            "url": "https://github.com/Halildeu/ao-kernel-sandbox/pull/56" if passed else "",
            "create_status": "pass" if passed else "not_run",
            "verify_open_status": "pass" if passed else "not_run",
            "rollback_close_status": "pass" if passed else "not_run",
            "verify_closed_status": "pass" if passed else "not_run",
            "final_state": "CLOSED" if passed else "not_run",
        },
        "gh_cli_pr_smoke": {
            "overall_status": "pass" if passed else "not_run",
            "findings": [],
            "checks": [{"name": "pr_live_write", "status": "pass" if passed else "not_run"}],
        },
        "cleanup": {
            "remote_pr_closed": passed,
            "remote_branch_deleted": passed,
            "cleanup_complete": passed,
            "side_effects_remaining": [],
        },
        "promotion_decision": {
            "support_widening_allowed": False,
            "decision": "no_support_widening",
            "next_gate": "GP-5.7",
            "reason": "sandbox only",
        },
    }
    if not passed:
        report["blocked_reason"] = "target repo must satisfy disposable sandbox keyword guard"
    return report


def _write_clean_run(
    base: Path,
    run_id: str,
    *,
    patch_support_widening: bool = False,
    pr_production_support: bool = False,
) -> dict[str, str]:
    read_only = base / f"{run_id}-read-only.json"
    patch = base / f"{run_id}-patch.json"
    pr = base / f"{run_id}-pr.json"
    _write_json(read_only, _read_only_report())
    _write_json(patch, _controlled_patch_report(support_widening=patch_support_widening))
    _write_json(pr, _disposable_pr_report(production_support=pr_production_support))
    return {
        "run_id": run_id,
        "target_kind": "sandbox_repo",
        "read_only_report": read_only.name,
        "controlled_patch_report": patch.name,
        "disposable_pr_report": pr.name,
    }


def _write_valid_matrix(tmp_path: Path) -> Path:
    _write_json(tmp_path / "contract.json", _contract())
    for index in range(1, 4):
        _write_clean_run(tmp_path, f"clean-{index}")
    _write_json(tmp_path / "fail-pr.json", _disposable_pr_report(status="blocked"))
    matrix = {
        "contract_report": "contract.json",
        "clean_runs": [
            {
                "run_id": f"clean-{index}",
                "target_kind": "sandbox_repo",
                "read_only_report": f"clean-{index}-read-only.json",
                "controlled_patch_report": f"clean-{index}-patch.json",
                "disposable_pr_report": f"clean-{index}-pr.json",
            }
            for index in range(1, 4)
        ],
        "failure_runs": [
            {
                "scenario_id": "fail-closed-non-disposable-pr-repo",
                "trigger": "non_disposable_pr_repo",
                "report_kind": "disposable_pr_write",
                "report_path": "fail-pr.json",
            }
        ],
    }
    matrix_path = tmp_path / "matrix.json"
    _write_json(matrix_path, matrix)
    return matrix_path


def test_gp57b_full_rehearsal_passes_with_three_clean_runs_and_one_fail_closed(
    tmp_path: Path,
) -> None:
    mod = _module()
    matrix_path = _write_valid_matrix(tmp_path)

    report = mod.build_full_rehearsal_report(
        matrix=json.loads(matrix_path.read_text(encoding="utf-8")),
        matrix_base_dir=tmp_path,
    )

    assert _schema_errors(report) == []
    assert report["overall_status"] == "pass"
    assert report["decision"] == "pass_full_production_rehearsal_no_support_widening"
    assert report["support_widening"] is False
    assert report["production_platform_claim"] is False
    assert report["evidence_matrix"]["observed_clean_passes"] == 3
    assert report["evidence_matrix"]["observed_failure_blocks"] == 1
    assert all(run["status"] == "pass" for run in report["clean_runs"])
    assert report["failure_runs"][0]["status"] == "blocked"


def test_gp57b_blocks_when_clean_pass_threshold_is_not_met(tmp_path: Path) -> None:
    mod = _module()
    matrix_path = _write_valid_matrix(tmp_path)
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    matrix["clean_runs"] = matrix["clean_runs"][:2]

    report = mod.build_full_rehearsal_report(matrix=matrix, matrix_base_dir=tmp_path)

    assert _schema_errors(report) == []
    assert report["overall_status"] == "blocked"
    assert "observed_clean_passes=2 below required=3" in report["blocked_reason"]


def test_gp57b_blocks_support_widening_in_clean_subreport(tmp_path: Path) -> None:
    mod = _module()
    _write_json(tmp_path / "contract.json", _contract())
    clean_runs = [
        _write_clean_run(tmp_path, "clean-1", patch_support_widening=True),
        _write_clean_run(tmp_path, "clean-2"),
        _write_clean_run(tmp_path, "clean-3"),
    ]
    _write_json(tmp_path / "fail-pr.json", _disposable_pr_report(status="blocked"))
    matrix = {
        "contract_report": "contract.json",
        "clean_runs": clean_runs,
        "failure_runs": [
            {
                "scenario_id": "fail-closed-non-disposable-pr-repo",
                "trigger": "non_disposable_pr_repo",
                "report_kind": "disposable_pr_write",
                "report_path": "fail-pr.json",
            }
        ],
    }

    report = mod.build_full_rehearsal_report(matrix=matrix, matrix_base_dir=tmp_path)

    assert _schema_errors(report) == []
    assert report["overall_status"] == "blocked"
    assert report["clean_runs"][0]["status"] == "blocked"
    assert "controlled_patch_support_widening_not_false" in report["clean_runs"][0][
        "controlled_patch_test"
    ]["findings"]


def test_gp57b_requires_failure_scenario_to_be_blocked(tmp_path: Path) -> None:
    mod = _module()
    matrix_path = _write_valid_matrix(tmp_path)
    _write_json(tmp_path / "fail-pr.json", _disposable_pr_report(status="pass"))

    report = mod.build_full_rehearsal_report(
        matrix=json.loads(matrix_path.read_text(encoding="utf-8")),
        matrix_base_dir=tmp_path,
    )

    assert _schema_errors(report) == []
    assert report["overall_status"] == "blocked"
    assert report["failure_runs"][0]["status"] == "fail"
    assert "failure_scenario_report_not_blocked" in report["failure_runs"][0]["findings"]


def test_gp57b_blocks_non_disposable_or_production_pr_claim_in_clean_run(
    tmp_path: Path,
) -> None:
    mod = _module()
    _write_json(tmp_path / "contract.json", _contract())
    clean_runs = [
        _write_clean_run(tmp_path, "clean-1", pr_production_support=True),
        _write_clean_run(tmp_path, "clean-2"),
        _write_clean_run(tmp_path, "clean-3"),
    ]
    _write_json(tmp_path / "fail-pr.json", _disposable_pr_report(status="blocked"))
    matrix = {
        "contract_report": "contract.json",
        "clean_runs": clean_runs,
        "failure_runs": [
            {
                "scenario_id": "fail-closed-non-disposable-pr-repo",
                "trigger": "non_disposable_pr_repo",
                "report_kind": "disposable_pr_write",
                "report_path": "fail-pr.json",
            }
        ],
    }

    report = mod.build_full_rehearsal_report(matrix=matrix, matrix_base_dir=tmp_path)

    assert _schema_errors(report) == []
    assert report["overall_status"] == "blocked"
    findings = report["clean_runs"][0]["disposable_pr_write"]["findings"]
    assert "disposable_pr_production_remote_pr_support_not_false" in findings
    assert "disposable_pr_arbitrary_repo_support_not_false" in findings


def test_gp57b_cli_writes_pass_report(tmp_path: Path) -> None:
    mod = _module()
    matrix_path = _write_valid_matrix(tmp_path)
    report_path = tmp_path / "gp57b-report.json"

    result = mod.main(
        [
            "--matrix-file",
            str(matrix_path),
            "--output",
            "json",
            "--report-path",
            str(report_path),
        ]
    )

    assert result == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert _schema_errors(report) == []
    assert report["overall_status"] == "pass"


def test_gp57b_docs_keep_execution_gate_boundary_explicit() -> None:
    repo_root = _repo_root()
    program = (
        repo_root / ".claude" / "plans" / "GP-5-GENERAL-PURPOSE-PRODUCTION-PLATFORM-INTEGRATION.md"
    ).read_text(encoding="utf-8")
    status = (
        repo_root / ".claude" / "plans" / "POST-BETA-CORRECTNESS-EXPANSION-STATUS.md"
    ).read_text(encoding="utf-8")
    runbook = (repo_root / "docs" / "OPERATIONS-RUNBOOK.md").read_text(encoding="utf-8")
    public_beta = (repo_root / "docs" / "PUBLIC-BETA.md").read_text(encoding="utf-8")
    support_boundary = (repo_root / "docs" / "SUPPORT-BOUNDARY.md").read_text(encoding="utf-8")

    assert "GP-5.7b" in program
    assert "GP-5.7b full production rehearsal execution gate" in status
    assert "gp5-full-production-rehearsal-report.schema.v1.json" in runbook
    assert "GP-5 full production rehearsal execution gate" in public_beta
    assert "GP-5.7b" in support_boundary
