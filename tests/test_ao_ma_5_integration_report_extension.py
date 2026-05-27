"""AO-MA-5 schema extension tests for ao-ma-integration-report.v1.

The integration_report.v1 schema gains three optional fields to support
the AO-MA-5 integrator slice:

- `pending_worker_results` (path_list) — workers awaiting review/verify evidence
- `worker_decisions[]` — per-worker accept/reject/not_integratable + reason_code
- `assembly_plan[]` — operator-runnable argv-form command plan (data, not shell strings)

All three are optional for backward compatibility. The existing AO-MA-2
fixture (without these fields) must still validate. New tests below pin
both directions: extension acceptance + backward compat preservation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "ao_kernel"
    / "defaults"
    / "schemas"
    / "ao-ma-integration-report.schema.v1.json"
)


def _load_schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _base_payload() -> dict:
    return {
        "schema_version": "ao-ma-integration-report.v1",
        "task_graph_id": "ao-ma-20260527-test111",
        "integrator": {
            "agent_id": "claude-integrator",
            "agent_type": "integrator",
            "provider": "anthropic",
            "session_id": "test-session-001",
        },
        "base_ref": "refs/heads/main",
        "base_sha": "a" * 40,
        "head_ref": "refs/heads/codex/test-integrator",
        "head_sha": "b" * 40,
        "accepted_worker_results": [],
        "rejected_worker_results": [],
        "final_changed_files": [],
        "conflicts": [],
        "review_verdict_refs": [],
        "verification_report_refs": [],
        "release_authority": "ao-release-gate+github-ruleset",
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
    }


def test_schema_is_a_valid_draft_2020_12_schema() -> None:
    schema = _load_schema()
    Draft202012Validator.check_schema(schema)


def test_backward_compat_existing_fixture_still_validates() -> None:
    """Codex iter-3 absorb: new fields are optional; the original AO-MA-2
    fixture (which has no pending_worker_results / worker_decisions /
    assembly_plan) must still validate against the extended schema.
    """

    schema = _load_schema()
    fixture = json.loads(
        (_SCHEMA_PATH.parents[3] / "tests/fixtures/ao_ma_2/integration_report.valid.json").read_text("utf-8")
    )
    Draft202012Validator(schema).validate(fixture)


def test_extension_pending_worker_results_accepted() -> None:
    schema = _load_schema()
    payload = _base_payload()
    payload["pending_worker_results"] = ["workers/task-001/worker_result.v1.json"]
    Draft202012Validator(schema).validate(payload)


def test_extension_worker_decisions_accept_full_payload() -> None:
    schema = _load_schema()
    payload = _base_payload()
    payload["worker_decisions"] = [
        {
            "task_id": "task-001",
            "worker_result_ref": "workers/task-001/worker_result.v1.json",
            "decision": "accept",
            "reason_code": "accepted_full_evidence",
            "evidence_refs": [
                "workers/task-001/worker_result.v1.json",
                "workers/task-001/review_verdict.v1.json",
                "workers/task-001/verification_report.v1.json",
            ],
        }
    ]
    Draft202012Validator(schema).validate(payload)


def test_extension_worker_decisions_null_worker_result_ref_when_missing() -> None:
    """Codex iter-3 absorb must_close #2: null sentinel distinguishes from
    a file literally named 'missing'. Schema oneOf path|null."""

    schema = _load_schema()
    payload = _base_payload()
    payload["worker_decisions"] = [
        {
            "task_id": "task-002",
            "worker_result_ref": None,
            "decision": "not_integratable",
            "reason_code": "missing_worker_result",
        }
    ]
    Draft202012Validator(schema).validate(payload)


def test_extension_worker_decisions_rejects_invalid_decision() -> None:
    schema = _load_schema()
    payload = _base_payload()
    payload["worker_decisions"] = [
        {
            "task_id": "task-001",
            "worker_result_ref": "workers/task-001/worker_result.v1.json",
            "decision": "totally-invalid",
            "reason_code": "accepted_full_evidence",
        }
    ]
    with pytest.raises(ValidationError, match="totally-invalid"):
        Draft202012Validator(schema).validate(payload)


def test_extension_worker_decisions_rejects_invalid_reason_code() -> None:
    schema = _load_schema()
    payload = _base_payload()
    payload["worker_decisions"] = [
        {
            "task_id": "task-001",
            "worker_result_ref": "workers/task-001/worker_result.v1.json",
            "decision": "reject",
            "reason_code": "i_made_this_up",
        }
    ]
    with pytest.raises(ValidationError, match="i_made_this_up"):
        Draft202012Validator(schema).validate(payload)


def test_extension_worker_decisions_all_10_reason_codes_accepted() -> None:
    """Pin the full reason_code enum to prevent silent shrinkage."""

    schema = _load_schema()
    expected_codes = {
        "accepted_full_evidence",
        "missing_worker_result",
        "missing_review_verdict",
        "missing_verification_report",
        "review_revise",
        "review_block",
        "verification_failed",
        "actual_write_set_overlap",
        "guard_flag_violation",
        "schema_invalid",
    }
    for code in expected_codes:
        payload = _base_payload()
        payload["worker_decisions"] = [
            {
                "task_id": "task-001",
                "worker_result_ref": None if "missing" in code else "workers/x/worker_result.v1.json",
                "decision": "accept" if code == "accepted_full_evidence" else "reject",
                "reason_code": code,
            }
        ]
        Draft202012Validator(schema).validate(payload)


def test_extension_assembly_plan_argv_form() -> None:
    schema = _load_schema()
    payload = _base_payload()
    payload["assembly_plan"] = [
        {
            "argv": ["git", "merge", "--no-ff", "codex/ao-ma-test/task-001"],
            "operator_only": True,
            "side_effect": "local_git_merge",
            "requires_clean_worktree": True,
            "note": "Merge task-001 branch into integrator branch",
        }
    ]
    Draft202012Validator(schema).validate(payload)


def test_extension_assembly_plan_rejects_operator_only_false() -> None:
    """Codex iter-2/3 absorb: operator_only is const True — integrator
    NEVER executes assembly_step. A schema-level false here would be a
    HARD RULE violation."""

    schema = _load_schema()
    payload = _base_payload()
    payload["assembly_plan"] = [
        {
            "argv": ["git", "push", "origin", "main"],
            "operator_only": False,  # SCHEMA VIOLATION
            "side_effect": "remote_pr_create",
        }
    ]
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(payload)


def test_extension_assembly_plan_rejects_invalid_side_effect() -> None:
    schema = _load_schema()
    payload = _base_payload()
    payload["assembly_plan"] = [
        {
            "argv": ["git", "checkout", "main"],
            "operator_only": True,
            "side_effect": "rm_rf_everything",
        }
    ]
    with pytest.raises(ValidationError, match="rm_rf_everything"):
        Draft202012Validator(schema).validate(payload)


def test_extension_assembly_plan_rejects_empty_argv() -> None:
    schema = _load_schema()
    payload = _base_payload()
    payload["assembly_plan"] = [
        {
            "argv": [],
            "operator_only": True,
            "side_effect": "local_git_merge",
        }
    ]
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(payload)


def test_extension_all_four_side_effects_accepted() -> None:
    """Pin the side_effect enum to prevent silent shrinkage."""

    schema = _load_schema()
    expected = {"local_git_merge", "remote_pr_create", "local_branch_create", "local_worktree_remove"}
    for side_effect in expected:
        payload = _base_payload()
        payload["assembly_plan"] = [
            {
                "argv": ["git", "noop"],
                "operator_only": True,
                "side_effect": side_effect,
            }
        ]
        Draft202012Validator(schema).validate(payload)
