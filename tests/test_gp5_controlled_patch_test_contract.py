from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


def _schema() -> dict[str, Any]:
    return load_default("schemas", "gp5-controlled-patch-test-contract.schema.v1.json")


def _errors(payload: dict[str, Any]) -> list[str]:
    return sorted(error.message for error in Draft202012Validator(_schema()).iter_errors(payload))


def _valid_contract() -> dict[str, Any]:
    return {
        "schema_version": "1",
        "artifact_kind": "gp5_controlled_patch_test_contract",
        "program_id": "GP-5.5a",
        "decision": "design_contract_ready_no_runtime_write_support",
        "lane_status": "contract_design_only",
        "support_widening": False,
        "runtime_patch_application_enabled": False,
        "remote_side_effects_allowed": False,
        "active_main_worktree_allowed": False,
        "target_worktree": {
            "kind": "disposable_worktree",
            "separate_from_operator_main": True,
            "cleanup_required": True,
            "dirty_state_preflight_required": True,
        },
        "write_ownership": {
            "path_scoped_claims_required": True,
            "owner_record_required": True,
            "takeover_or_handoff_record_required": True,
        },
        "diff_preview": {
            "preview_required": True,
            "preview_artifact_required": True,
            "files_changed_required": True,
        },
        "apply_boundary": {
            "explicit_operator_approval_required": True,
            "write_without_preview_allowed": False,
            "future_runtime_rehearsal_required": True,
        },
        "test_plan": {
            "targeted_tests_required": True,
            "explainable_selection_required": True,
            "fallback_full_gate_required": True,
            "commands": [
                "pytest -q <targeted-tests>",
                "python3 -m ruff check <changed-paths>",
            ],
        },
        "rollback_plan": {
            "reverse_diff_required": True,
            "rollback_verification_required": True,
            "cleanup_evidence_required": True,
            "idempotency_check_required": True,
        },
        "evidence_requirements": {
            "changed_paths": True,
            "diff_preview_artifact": True,
            "apply_decision_record": True,
            "tests_run": True,
            "rollback_evidence": True,
            "cleanup_evidence": True,
            "incident_runbook_reference": True,
        },
        "excluded_surfaces": {
            "live_remote_pr": False,
            "real_adapter_live_write": False,
            "production_support_claim": False,
        },
        "promotion_decision": {
            "support_widening_allowed": False,
            "next_gate": "GP-5.5b",
            "reason": "GP-5.5a is design-only; runtime rehearsal is a separate gate.",
        },
    }


def test_controlled_patch_test_contract_accepts_complete_design_only_payload() -> None:
    Draft202012Validator.check_schema(_schema())
    assert _errors(_valid_contract()) == []


def test_controlled_patch_test_contract_rejects_support_widening() -> None:
    payload = _valid_contract()
    payload["support_widening"] = True
    payload["excluded_surfaces"]["production_support_claim"] = True

    errors = _errors(payload)

    assert "False was expected" in errors


def test_controlled_patch_test_contract_requires_disposable_or_dedicated_worktree() -> None:
    payload = _valid_contract()
    payload["active_main_worktree_allowed"] = True
    payload["target_worktree"]["kind"] = "operator_main"

    errors = _errors(payload)

    assert "False was expected" in errors
    assert "'operator_main' is not one of ['disposable_worktree', 'dedicated_worktree']" in errors


def test_controlled_patch_test_contract_requires_rollback_and_test_evidence() -> None:
    payload = _valid_contract()
    del payload["rollback_plan"]["rollback_verification_required"]
    del payload["test_plan"]["fallback_full_gate_required"]
    payload["evidence_requirements"]["rollback_evidence"] = False

    errors = _errors(payload)

    assert "'rollback_verification_required' is a required property" in errors
    assert "'fallback_full_gate_required' is a required property" in errors
    assert "True was expected" in errors


def test_controlled_patch_test_docs_keep_no_support_widening_boundary() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    public_beta = (repo_root / "docs" / "PUBLIC-BETA.md").read_text(encoding="utf-8")
    support_boundary = (repo_root / "docs" / "SUPPORT-BOUNDARY.md").read_text(encoding="utf-8")
    runbook = (repo_root / "docs" / "OPERATIONS-RUNBOOK.md").read_text(encoding="utf-8")

    assert "GP-5 controlled patch/test lane" in public_beta
    assert "Rehearsal / no support widening" in public_beta
    assert "gp5-controlled-patch-test-contract.schema.v1.json" in public_beta
    assert "support_widening=false" in support_boundary
    assert "GP-5 controlled patch/test rehearsal skeleton" in runbook
