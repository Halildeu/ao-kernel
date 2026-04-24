from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _schema() -> dict[str, Any]:
    return load_default("schemas", "gp5-full-production-rehearsal-contract.schema.v1.json")


def _errors(payload: dict[str, Any]) -> list[str]:
    return sorted(error.message for error in Draft202012Validator(_schema()).iter_errors(payload))


def _clean_run(run_id: str, *, target_kind: str = "sandbox_repo") -> dict[str, Any]:
    return {
        "run_id": run_id,
        "target": {
            "kind": target_kind,
            "non_disposable_pr_target": False,
            "arbitrary_user_repo": False,
        },
        "repo_intelligence_context": {
            "mode": "explicit_stdout_markdown",
            "hidden_injection": False,
            "root_export_required": False,
        },
        "adapter": {
            "mode": "codex_stub_rehearsal",
            "production_certified": False,
            "usage_or_unavailable_reason_required": True,
        },
        "patch_test": {
            "controlled_worktree_required": True,
            "rollback_required": True,
        },
        "pr_rehearsal": {
            "disposable_pr_required": True,
            "remote_rollback_required": True,
            "arbitrary_repo_support": False,
        },
        "expected_outcome": "pass_or_blocked_with_evidence",
    }


def _valid_contract() -> dict[str, Any]:
    return {
        "schema_version": "1",
        "artifact_kind": "gp5_full_production_rehearsal_contract",
        "program_id": "GP-5.7a",
        "issue": {
            "number": 449,
            "url": "https://github.com/Halildeu/ao-kernel/issues/449",
        },
        "overall_status": "contract_ready",
        "decision": "contract_ready_no_support_widening",
        "support_widening": False,
        "production_platform_claim": False,
        "protected_real_adapter_gate": {
            "required_for_promotion": True,
            "attestation_status": "blocked_unattested",
            "live_adapter_execution_allowed_in_this_slice": False,
            "blocked_gate": "GP-5.1b",
        },
        "precondition_reports": [
            {
                "gate": "GP-5.3e",
                "status": "completed",
                "artifact": ".claude/plans/GP-5.3e-REPO-INTELLIGENCE-WORKFLOW-BUILDING-BLOCK-DECISION.md",
                "support_widening": False,
            },
            {
                "gate": "GP-5.4a",
                "status": "pass",
                "artifact": ".claude/plans/GP-5.4a-GOVERNED-READ-ONLY-WORKFLOW-REHEARSAL.md",
                "support_widening": False,
            },
            {
                "gate": "GP-5.5b",
                "status": "pass",
                "artifact": ".claude/plans/GP-5.5b-CONTROLLED-LOCAL-PATCH-TEST-REHEARSAL.md",
                "support_widening": False,
            },
            {
                "gate": "GP-5.6a",
                "status": "pass",
                "artifact": ".claude/plans/GP-5.6a-DISPOSABLE-PR-WRITE-REHEARSAL.md",
                "support_widening": False,
            },
        ],
        "target_chain": [
            "issue_or_task",
            "repo_scan_index_query",
            "explicit_context_handoff",
            "adapter_reasoning",
            "patch_plan",
            "controlled_patch",
            "tests",
            "disposable_pr_rehearsal",
            "rollback_closeout",
        ],
        "clean_rehearsal_matrix": {
            "required_clean_runs": 3,
            "runs": [_clean_run("clean-1"), _clean_run("clean-2"), _clean_run("clean-3")],
        },
        "failure_rehearsal_matrix": {
            "required_failure_runs": 1,
            "scenarios": [
                {
                    "scenario_id": "fail-closed-non-disposable-pr-repo",
                    "trigger": "non_disposable_pr_repo",
                    "expected_status": "blocked",
                    "support_widening": False,
                }
            ],
        },
        "evidence_requirements": [
            {
                "requirement_id": "issue_or_task_reference",
                "status_before_gp57b": "required",
            },
            {
                "requirement_id": "repo_intelligence_artifacts",
                "status_before_gp57b": "required",
            },
            {
                "requirement_id": "context_handoff_pack",
                "status_before_gp57b": "required",
            },
            {
                "requirement_id": "adapter_identity_and_usage",
                "status_before_gp57b": "required",
            },
            {
                "requirement_id": "patch_plan_artifact",
                "status_before_gp57b": "required",
            },
            {
                "requirement_id": "controlled_patch_test_report",
                "status_before_gp57b": "required",
            },
            {
                "requirement_id": "disposable_pr_write_report",
                "status_before_gp57b": "required",
            },
            {
                "requirement_id": "rollback_closeout_report",
                "status_before_gp57b": "required",
            },
        ],
        "promotion_decision": {
            "support_widening_allowed": False,
            "next_gate": "GP-5.7b",
            "release_impact": "contract_only_no_runtime_change",
            "reason": "GP-5.7a defines the future rehearsal matrix only.",
        },
    }


def test_gp57a_contract_schema_is_valid_and_accepts_contract() -> None:
    schema = _schema()

    Draft202012Validator.check_schema(schema)
    assert _errors(_valid_contract()) == []


def test_gp57a_contract_rejects_support_widening_and_platform_claim() -> None:
    contract = _valid_contract()
    contract["support_widening"] = True
    contract["production_platform_claim"] = True
    contract["promotion_decision"]["support_widening_allowed"] = True

    assert _errors(contract).count("False was expected") == 3


def test_gp57a_contract_requires_three_clean_rehearsals() -> None:
    contract = _valid_contract()
    contract["clean_rehearsal_matrix"]["runs"] = contract["clean_rehearsal_matrix"]["runs"][:2]

    assert any(error.endswith("is too short") for error in _errors(contract))


def test_gp57a_contract_requires_at_least_one_fail_closed_rehearsal() -> None:
    contract = _valid_contract()
    contract["failure_rehearsal_matrix"]["scenarios"] = []

    assert "[] should be non-empty" in _errors(contract)


def test_gp57a_contract_rejects_non_disposable_remote_pr_target() -> None:
    contract = _valid_contract()
    run = contract["clean_rehearsal_matrix"]["runs"][0]
    run["target"]["non_disposable_pr_target"] = True
    run["target"]["arbitrary_user_repo"] = True
    run["pr_rehearsal"]["arbitrary_repo_support"] = True

    assert _errors(contract).count("False was expected") == 3


def test_gp57a_contract_rejects_live_adapter_execution_in_contract_slice() -> None:
    contract = _valid_contract()
    contract["protected_real_adapter_gate"]["live_adapter_execution_allowed_in_this_slice"] = True

    assert "False was expected" in _errors(contract)


def test_gp57a_contract_docs_keep_no_support_widening_boundary() -> None:
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

    assert "GP-5.7a" in program
    assert "GP-5.7a full production rehearsal contract" in status
    assert "gp5-full-production-rehearsal-contract.schema.v1.json" in runbook
    assert "GP-5 full production rehearsal contract" in public_beta
    assert "production_platform_claim=false" in support_boundary


def test_gp57a_valid_contract_fixture_is_not_mutated_between_tests() -> None:
    contract = _valid_contract()
    mutated = copy.deepcopy(contract)
    mutated["target_chain"].append("unsupported_extra_step")

    assert _errors(contract) == []
    assert "Expected at most 9 items but found 1 extra: 'unsupported_extra_step'" in _errors(mutated)
