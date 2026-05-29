"""Invariant tests for RI-7.8b-bc10-6c schemas (per-call evidence + aggregate + closure).

This PR is schema-only: defines the 3 contracts for the future bc10-6c-closure PR.
NO actual per-call evidence, aggregate, or closure files exist in this PR.
NO gpp_status mutation, NO submanifest flip, NO workflow/script change.

Tests enforce:
- All 3 schemas are Draft 2020-12 valid
- additionalProperties=false on all object types
- Const pins, enum constraints, allOf coherence rules accept positive samples
  and reject negative samples
- Forbidden scope: workflow + scripts + gpp_status + submanifest UNCHANGED
- Top-level guard flags const false PRESERVED (snapshot)
- Cross-AI peer review reference structure
"""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

PER_CALL_SCHEMA = REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ri7-8b-bc10-6c-per-call-evidence.schema.v1.json"
AGGREGATE_SCHEMA = REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ri7-8b-bc10-6c-aggregate-evidence.schema.v1.json"
CLOSURE_SCHEMA = REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ri7-8b-bc10-6c-closure-evidence.schema.v1.json"

GPP_STATUS_PATH = REPO_ROOT / ".claude" / "plans" / "gpp_status.v1.json"
SUBMANIFEST_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8-EVIDENCE-MANIFEST.v1.json"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "bc10-real-adapter-usage-cost.yml"
ACTIVATION_SCRIPT_PATH = REPO_ROOT / "scripts" / "ri78b_bc10_activation_window.py"
RUNNER_SCRIPT_PATH = REPO_ROOT / "scripts" / "bc10_run_scenarios.py"
LOCAL_AI_REVIEW_PATH = REPO_ROOT / "local-ai-review-evidence.v1.json"

# bc10-6c-schemas MUST NOT add these files (they belong to bc10-6c-closure)
FORBIDDEN_RUN_EVIDENCE_PATHS = [
    ".claude/plans/RI-7.8b-bc10-6c-RUN-EVIDENCE-small_completion_a.v1.json",
    ".claude/plans/RI-7.8b-bc10-6c-RUN-EVIDENCE-small_completion_b.v1.json",
    ".claude/plans/RI-7.8b-bc10-6c-RUN-EVIDENCE-small_completion_c.v1.json",
    ".claude/plans/RI-7.8b-bc10-6c-RUN-EVIDENCE-budget_cap_precheck_denied.v1.json",
    ".claude/plans/RI-7.8b-bc10-6c-AGGREGATE.v1.json",
    ".claude/plans/RI-7.8b-bc10-6c-CLOSURE.v1.json",
]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _resolve_diff_base() -> str | None:
    candidates = ["origin/main", "main"]
    try:
        result = subprocess.run(
            ["git", "merge-base", "HEAD", "origin/main"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        pass
    for ref in candidates:
        try:
            result = subprocess.run(
                ["git", "rev-parse", ref],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (subprocess.SubprocessError, OSError):
            continue
    return None


def _git_changed_paths_against(base_sha: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_sha}...HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git diff failed: {result.stderr}")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _is_ri78b_bc10_6c_schemas_introducer_pr() -> bool:
    base_sha = _resolve_diff_base()
    if base_sha is None:
        return False
    try:
        result = subprocess.run(
            ["git", "diff", "--diff-filter=A", "--name-only", f"{base_sha}...HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return False
        added = {line.strip() for line in result.stdout.splitlines() if line.strip()}
        return str(PER_CALL_SCHEMA.relative_to(REPO_ROOT)) in added
    except (subprocess.SubprocessError, OSError):
        return False


# ---------------------------------------------------------------------------
# Schema validity (Draft 2020-12)
# ---------------------------------------------------------------------------


def test_per_call_schema_exists_and_valid():
    assert PER_CALL_SCHEMA.exists()
    schema = _load_json(PER_CALL_SCHEMA)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    jsonschema.Draft202012Validator.check_schema(schema)


def test_aggregate_schema_exists_and_valid():
    assert AGGREGATE_SCHEMA.exists()
    schema = _load_json(AGGREGATE_SCHEMA)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    jsonschema.Draft202012Validator.check_schema(schema)


def test_closure_schema_exists_and_valid():
    assert CLOSURE_SCHEMA.exists()
    schema = _load_json(CLOSURE_SCHEMA)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    jsonschema.Draft202012Validator.check_schema(schema)


def test_all_schemas_use_additional_properties_false():
    """All object types in all 3 schemas MUST have additionalProperties: false."""
    for path in [PER_CALL_SCHEMA, AGGREGATE_SCHEMA, CLOSURE_SCHEMA]:
        schema = _load_json(path)

        def check_recursive(node, ctx=""):
            if isinstance(node, dict):
                if node.get("type") == "object":
                    # Check this is closed
                    assert node.get("additionalProperties") is False, (
                        f"{path.name}{ctx}: object type missing additionalProperties:false"
                    )
                for k, v in node.items():
                    check_recursive(v, f"{ctx}.{k}")
            elif isinstance(node, list):
                for i, item in enumerate(node):
                    check_recursive(item, f"{ctx}[{i}]")

        check_recursive(schema)


# ---------------------------------------------------------------------------
# Per-call schema: positive + negative samples
# ---------------------------------------------------------------------------


def _valid_per_call_success() -> dict:
    return {
        "schema_version": "ri7-8b-bc10-6c-per-call-evidence.v1",
        "artifact_kind": "ri7_8b_bc10_6c_per_call_evidence",
        "marker_schema_version": "ri7-8b-bc10-per-call-runtime-call-marker.v1",
        "marker_sha256": "a" * 64,
        "marker_source_url": "https://github.com/Halildeu/ao-kernel/actions/runs/12345/artifacts/67890",
        "workflow_run_id": "12345",
        "run_attempt": "1",
        "head_sha": "b" * 40,
        "workflow_ref": "Halildeu/ao-kernel/.github/workflows/bc10-real-adapter-usage-cost.yml@refs/heads/main",
        "workflow_content_sha256": "c" * 64,
        "pricing_source_digest": "sha256:" + "d" * 64,
        "scenario": "small_completion_a",
        "scenario_outcome": "success_billable",
        "requested_model": "openai/gpt-4o-mini",
        "resolved_model": "openai/gpt-4o-mini",
        "model_allowlist_enforced": True,
        "model_allowlist": ["openai/gpt-4o-mini"],
        "max_output_tokens_cap": 64,
        "provider_call_performed": True,
        "billable_call_count_delta": 1,
        "input_tokens": 10,
        "output_tokens": 25,
        "total_tokens": 35,
        "projected_cost_usd": "0.00010000",
        "actual_cost_usd": "0.00001650",
        "cumulative_cost_usd_before": "0.00000000",
        "cumulative_cost_usd_after": "0.00001650",
        "usage_source": "provider_api_response",
        "cost_source": "provider_usage_plus_pinned_pricing_source",
        "secret_boundary": "no_secret_material_emitted_no_token_no_credential",
        "raw_response_recorded": False,
        "secret_material_recorded": False,
        "secret_scope_after_all_pre_provider_guards": True,
        "budget_cap_precheck_denied_completes_without_provider_client_init": True,
        "budget_cap_precheck_denied_completes_without_api_key_read": True,
        "retry_behavior": "wrapper_no_retry_loop_transport_default_skipped",
    }


def _valid_per_call_budget_denied() -> dict:
    return {
        **_valid_per_call_success(),
        "scenario": "budget_cap_precheck_denied",
        "scenario_outcome": "budget_cap_precheck_denied",
        "provider_call_performed": False,
        "billable_call_count_delta": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "projected_cost_usd": "6.00000000",
        "actual_cost_usd": "0.00000000",
        "cumulative_cost_usd_before": "0.00001650",
        "cumulative_cost_usd_after": "0.00001650",
        "usage_source": "no_call_no_usage",
        "cost_source": "no_billable_provider_call",
    }


def test_per_call_success_sample_validates():
    schema = _load_json(PER_CALL_SCHEMA)
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(_valid_per_call_success()))
    assert not errors, f"valid success sample rejected: {errors[:3]}"


def test_per_call_budget_denied_sample_validates():
    schema = _load_json(PER_CALL_SCHEMA)
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(_valid_per_call_budget_denied()))
    assert not errors, f"valid budget_denied sample rejected: {errors[:3]}"


def test_per_call_negative_zero_usage_success_rejected():
    schema = _load_json(PER_CALL_SCHEMA)
    bad = _valid_per_call_success()
    bad["input_tokens"] = 0
    bad["output_tokens"] = 0
    bad["total_tokens"] = 0
    bad["actual_cost_usd"] = "0.00000000"
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
    assert errors, "zero-usage success_billable must be rejected"


def test_per_call_negative_budget_denied_with_provider_call_rejected():
    schema = _load_json(PER_CALL_SCHEMA)
    bad = _valid_per_call_budget_denied()
    bad["provider_call_performed"] = True
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
    assert errors, "budget_denied with provider_call_performed=true must be rejected"


def test_per_call_negative_wrong_model_rejected():
    schema = _load_json(PER_CALL_SCHEMA)
    bad = _valid_per_call_success()
    bad["resolved_model"] = "openai/gpt-4o"
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
    assert errors, "non-allowlist model must be rejected"


def test_per_call_negative_secret_referenced_rejected():
    schema = _load_json(PER_CALL_SCHEMA)
    bad = _valid_per_call_success()
    bad["secret_material_recorded"] = True
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
    assert errors


def test_per_call_negative_raw_response_recorded_rejected():
    schema = _load_json(PER_CALL_SCHEMA)
    bad = _valid_per_call_success()
    bad["raw_response_recorded"] = True
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
    assert errors


def test_per_call_negative_max_tokens_too_high_rejected():
    schema = _load_json(PER_CALL_SCHEMA)
    bad = _valid_per_call_success()
    bad["max_output_tokens_cap"] = 1024
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
    assert errors


# ---------------------------------------------------------------------------
# Aggregate schema
# ---------------------------------------------------------------------------


def _valid_aggregate() -> dict:
    return {
        "schema_version": "ri7-8b-bc10-6c-aggregate-evidence.v1",
        "artifact_kind": "ri7_8b_bc10_6c_aggregate_evidence",
        "aggregate_kind": "ri7_8b_bc10_aggregate_evidence",
        "workflow_run_id": "12345",
        "run_attempt": "1",
        "head_sha": "b" * 40,
        "workflow_content_sha256": "c" * 64,
        "pricing_source_digest": "sha256:" + "d" * 64,
        "cumulative_usd": "0.00004950",
        "billable_calls_count": 3,
        "denied_calls_count": 1,
        "total_markers_count": 4,
        "line_items": [
            {
                "scenario": "small_completion_a",
                "scenario_outcome": "success_billable",
                "billable": True,
                "actual_cost_usd": "0.00001650",
                "projected_cost_usd": "0.00010000",
                "marker_sha256": "1" * 64,
                "per_call_evidence_path": ".claude/plans/RI-7.8b-bc10-6c-RUN-EVIDENCE-small_completion_a.v1.json",
                "per_call_evidence_sha256": "e" * 64,
                "usage_source": "provider_api_response",
                "cost_source": "provider_usage_plus_pinned_pricing_source",
            },
            {
                "scenario": "small_completion_b",
                "scenario_outcome": "success_billable",
                "billable": True,
                "actual_cost_usd": "0.00001650",
                "projected_cost_usd": "0.00010000",
                "marker_sha256": "2" * 64,
                "per_call_evidence_path": ".claude/plans/RI-7.8b-bc10-6c-RUN-EVIDENCE-small_completion_b.v1.json",
                "per_call_evidence_sha256": "f" * 64,
                "usage_source": "provider_api_response",
                "cost_source": "provider_usage_plus_pinned_pricing_source",
            },
            {
                "scenario": "small_completion_c",
                "scenario_outcome": "success_billable",
                "billable": True,
                "actual_cost_usd": "0.00001650",
                "projected_cost_usd": "0.00010000",
                "marker_sha256": "3" * 64,
                "per_call_evidence_path": ".claude/plans/RI-7.8b-bc10-6c-RUN-EVIDENCE-small_completion_c.v1.json",
                "per_call_evidence_sha256": "9" * 64,
                "usage_source": "provider_api_response",
                "cost_source": "provider_usage_plus_pinned_pricing_source",
            },
            {
                "scenario": "budget_cap_precheck_denied",
                "scenario_outcome": "budget_cap_precheck_denied",
                "billable": False,
                "actual_cost_usd": "0.00000000",
                "projected_cost_usd": "6.00000000",
                "marker_sha256": "4" * 64,
                "per_call_evidence_path": ".claude/plans/RI-7.8b-bc10-6c-RUN-EVIDENCE-budget_cap_precheck_denied.v1.json",
                "per_call_evidence_sha256": "5" * 64,
                "usage_source": "no_call_no_usage",
                "cost_source": "no_billable_provider_call",
            },
        ],
        "usage_source": "provider_api_response_plus_no_call_no_usage",
        "cost_source": "provider_usage_plus_pinned_pricing_source",
        "billing_digest": "0" * 64,
        "worst_case_invariant_holds": True,
        "max_usd": 5.00,
        "max_billable_calls_count": 4,
        "max_projected_call_cost_usd": "0.10000000",
        "raw_response_recorded": False,
        "secret_material_recorded": False,
    }


def test_aggregate_sample_validates():
    schema = _load_json(AGGREGATE_SCHEMA)
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(_valid_aggregate()))
    assert not errors, f"valid aggregate rejected: {errors[:3]}"


def test_aggregate_negative_3_line_items_rejected():
    schema = _load_json(AGGREGATE_SCHEMA)
    bad = _valid_aggregate()
    bad["line_items"] = bad["line_items"][:3]
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
    assert errors, "3 line items must be rejected (need exactly 4)"


def test_aggregate_negative_5_line_items_rejected():
    schema = _load_json(AGGREGATE_SCHEMA)
    bad = _valid_aggregate()
    extra = copy.deepcopy(bad["line_items"][0])
    extra["scenario"] = "small_completion_a"  # duplicate scenario
    bad["line_items"].append(extra)
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
    assert errors, "5 line items must be rejected"


def test_aggregate_negative_duplicate_scenario_rejected():
    schema = _load_json(AGGREGATE_SCHEMA)
    bad = _valid_aggregate()
    bad["line_items"][1]["scenario"] = "small_completion_a"  # duplicate
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
    assert errors, "duplicate scenario in line_items must be rejected"


def test_aggregate_negative_missing_budget_denied_rejected():
    schema = _load_json(AGGREGATE_SCHEMA)
    bad = _valid_aggregate()
    bad["line_items"][3]["scenario"] = "small_completion_a"  # missing budget_denied
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
    assert errors, "missing budget_cap_precheck_denied scenario must be rejected"


def test_aggregate_negative_billable_count_wrong_rejected():
    schema = _load_json(AGGREGATE_SCHEMA)
    bad = _valid_aggregate()
    bad["billable_calls_count"] = 4
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
    assert errors


def test_aggregate_negative_max_usd_too_high_rejected():
    schema = _load_json(AGGREGATE_SCHEMA)
    bad = _valid_aggregate()
    bad["max_usd"] = 100.00
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
    assert errors


# ---------------------------------------------------------------------------
# Closure schema
# ---------------------------------------------------------------------------


def _valid_closure() -> dict:
    return {
        "schema_version": "ri7-8b-bc10-6c-closure-evidence.v1",
        "artifact_kind": "ri7_8b_bc10_6c_closure_evidence",
        "decision": "ri78b_bc10_6c_closure_recorded_with_aggregate_and_submanifest_flip_operator_bound",
        "closure_proof": {
            "scenario_outcomes": [
                "success_billable",
                "success_billable",
                "success_billable",
                "budget_cap_precheck_denied",
            ],
            "no_unexpected_failure": True,
            "run_count": 1,
            "run_attempt": "1",
        },
        "spend_ledger": {
            "max_usd": 5.00,
            "cumulative_usd": "0.00004950",
            "billable_calls_count": 3,
            "cost_source": "provider_usage_plus_pinned_pricing_source",
            "line_items": [
                {"scenario": "small_completion_a", "billable": True, "actual_cost_usd": "0.00001650"},
                {"scenario": "small_completion_b", "billable": True, "actual_cost_usd": "0.00001650"},
                {"scenario": "small_completion_c", "billable": True, "actual_cost_usd": "0.00001650"},
                {"scenario": "budget_cap_precheck_denied", "billable": False, "actual_cost_usd": "0.00000000"},
            ],
        },
        "bounded_window_envelope": {
            "max_distinct_runs": 5,
            "actual_runs": 1,
            "max_usd": 5.00,
            "cumulative_usd": "0.00004950",
            "max_duration_hours": 24,
            "actual_duration_hours": 0.5,
            "max_run_attempt": 1,
        },
        "operator_activation_identity": {
            "operator_github_login": "Halildeu",
            "merged_by_login": "Halildeu",
            "identity_match": True,
        },
        "commit_verification": {"verified": True, "reason": "valid"},
        "required_checks_passed": True,
        "ao_ma_10_high_risk_prerequisite": {
            "pr_number": 687,
            "commit_sha": "0" * 40,
        },
        "bc10_flip_attestation": {
            "before": False,
            "after": True,
            "flip_owner_slice": "RI-7.8b-bc10-6c",
            "top_level_flags_unchanged": {
                "support_widening_allowed": False,
                "production_platform_claim_allowed": False,
                "live_adapter_execution_allowed": False,
            },
        },
        "status_transition_history": [
            {
                "from_status": "awaiting_operator_dispatch",
                "to_status": "active",
                "at": "2026-05-29T10:00:00Z",
            },
            {
                "from_status": "active",
                "to_status": "closed",
                "at": "2026-05-29T10:30:00Z",
            },
            {
                "from_status": "closed",
                "to_status": "closed",
                "at": "2026-05-29T10:35:00Z",
            },
        ],
        "protected_environment_observation_result": {
            "env_name": "ao-kernel-bc10-real-adapter-usage-cost",
            "observation_source": "github_environment_api",
            "observed_before_provider_call": True,
            "required_reviewers_count": 1,
            "distinct_reviewer_present": True,
            "prevent_self_review": True,
            "can_admins_bypass": False,
            "custom_branch_policies": True,
            "deployment_branch_policies": [{"type": "branch", "name": "main"}],
            "main_only_policy_verified": True,
            "observation_result": "passed",
        },
        "environment_approval_identity": {
            "workflow_dispatch_actor": "Halildeu",
            "environment_reviewer_login": "gladyatore-lab",
            "reviewer_distinct_from_dispatch_actor": True,
            "approval_record_source": "github_deployment_review_api",
            "approved_at": "2026-05-29T10:05:00Z",
        },
        "per_call_evidence_refs": [
            {
                "scenario": "small_completion_a",
                "path": ".claude/plans/RI-7.8b-bc10-6c-RUN-EVIDENCE-small_completion_a.v1.json",
                "sha256": "e" * 64,
            },
            {
                "scenario": "small_completion_b",
                "path": ".claude/plans/RI-7.8b-bc10-6c-RUN-EVIDENCE-small_completion_b.v1.json",
                "sha256": "f" * 64,
            },
            {
                "scenario": "small_completion_c",
                "path": ".claude/plans/RI-7.8b-bc10-6c-RUN-EVIDENCE-small_completion_c.v1.json",
                "sha256": "9" * 64,
            },
            {
                "scenario": "budget_cap_precheck_denied",
                "path": ".claude/plans/RI-7.8b-bc10-6c-RUN-EVIDENCE-budget_cap_precheck_denied.v1.json",
                "sha256": "5" * 64,
            },
        ],
        "aggregate_evidence_ref": {
            "path": ".claude/plans/RI-7.8b-bc10-6c-AGGREGATE.v1.json",
            "sha256": "a" * 64,
        },
        "cross_artifact_binding": {
            "all_per_call_refs_present_in_aggregate": True,
            "aggregate_billing_digest_verified": True,
            "workflow_run_id_consistent": True,
            "run_attempt_consistent": True,
            "pricing_source_digest_consistent": True,
            "workflow_content_sha256_consistent": True,
        },
        "guard_flags": {
            "support_widening_allowed": False,
            "production_platform_claim_allowed": False,
            "live_adapter_execution_allowed": False,
        },
        "secret_boundary": "no_secret_material_no_credential_names_no_token_in_repo",
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
    }


def test_closure_sample_validates():
    schema = _load_json(CLOSURE_SCHEMA)
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(_valid_closure()))
    assert not errors, f"valid closure rejected: {[(list(e.absolute_path), e.message[:100]) for e in errors[:3]]}"


def test_closure_negative_admin_bypass_true_rejected():
    schema = _load_json(CLOSURE_SCHEMA)
    bad = _valid_closure()
    bad["protected_environment_observation_result"]["can_admins_bypass"] = True
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
    assert errors


def test_closure_negative_protected_branches_fallback_rejected():
    """Schema does NOT accept protected_branches=true fallback."""
    schema = _load_json(CLOSURE_SCHEMA)
    bad = _valid_closure()
    bad["protected_environment_observation_result"]["custom_branch_policies"] = False
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
    assert errors


def test_closure_negative_prevent_self_review_false_rejected():
    schema = _load_json(CLOSURE_SCHEMA)
    bad = _valid_closure()
    bad["protected_environment_observation_result"]["prevent_self_review"] = False
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
    assert errors


def test_closure_negative_reviewer_not_distinct_rejected():
    schema = _load_json(CLOSURE_SCHEMA)
    bad = _valid_closure()
    bad["environment_approval_identity"]["reviewer_distinct_from_dispatch_actor"] = False
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
    assert errors


def test_closure_negative_bc10_flip_after_false_rejected():
    schema = _load_json(CLOSURE_SCHEMA)
    bad = _valid_closure()
    bad["bc10_flip_attestation"]["after"] = False
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
    assert errors


def test_closure_negative_top_level_guard_flag_true_rejected():
    schema = _load_json(CLOSURE_SCHEMA)
    bad = _valid_closure()
    bad["bc10_flip_attestation"]["top_level_flags_unchanged"]["live_adapter_execution_allowed"] = True
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
    assert errors


def test_closure_negative_extra_branch_policy_rejected():
    schema = _load_json(CLOSURE_SCHEMA)
    bad = _valid_closure()
    bad["protected_environment_observation_result"]["deployment_branch_policies"].append(
        {"type": "branch", "name": "develop"}
    )
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
    assert errors


def test_closure_negative_tag_policy_rejected():
    schema = _load_json(CLOSURE_SCHEMA)
    bad = _valid_closure()
    bad["protected_environment_observation_result"]["deployment_branch_policies"] = [{"type": "tag", "name": "main"}]
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
    assert errors


def test_closure_negative_non_main_policy_rejected():
    schema = _load_json(CLOSURE_SCHEMA)
    bad = _valid_closure()
    bad["protected_environment_observation_result"]["deployment_branch_policies"] = [
        {"type": "branch", "name": "develop"}
    ]
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
    assert errors


def test_closure_negative_missing_cross_artifact_binding_rejected():
    schema = _load_json(CLOSURE_SCHEMA)
    bad = _valid_closure()
    del bad["cross_artifact_binding"]
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
    assert errors


def test_closure_negative_cross_binding_inconsistent_rejected():
    schema = _load_json(CLOSURE_SCHEMA)
    bad = _valid_closure()
    bad["cross_artifact_binding"]["workflow_run_id_consistent"] = False
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
    assert errors


# ---------------------------------------------------------------------------
# Forbidden scope: 6c-schemas MUST NOT touch these surfaces
# ---------------------------------------------------------------------------


def test_6c_schemas_workflow_unchanged():
    if not _is_ri78b_bc10_6c_schemas_introducer_pr():
        pytest.skip("6c-schemas state-at-landing pin: only enforced on introducer PR")
    base_sha = _resolve_diff_base()
    if base_sha is None:
        pytest.skip("No git base resolved")
    changed = _git_changed_paths_against(base_sha)
    assert ".github/workflows/bc10-real-adapter-usage-cost.yml" not in changed


def test_6c_schemas_activation_script_unchanged():
    if not _is_ri78b_bc10_6c_schemas_introducer_pr():
        pytest.skip("6c-schemas state-at-landing pin: only enforced on introducer PR")
    base_sha = _resolve_diff_base()
    if base_sha is None:
        pytest.skip("No git base resolved")
    changed = _git_changed_paths_against(base_sha)
    assert "scripts/ri78b_bc10_activation_window.py" not in changed


def test_6c_schemas_runner_script_unchanged():
    if not _is_ri78b_bc10_6c_schemas_introducer_pr():
        pytest.skip("6c-schemas state-at-landing pin: only enforced on introducer PR")
    base_sha = _resolve_diff_base()
    if base_sha is None:
        pytest.skip("No git base resolved")
    changed = _git_changed_paths_against(base_sha)
    assert "scripts/bc10_run_scenarios.py" not in changed


def test_6c_schemas_gpp_status_unchanged():
    if not _is_ri78b_bc10_6c_schemas_introducer_pr():
        pytest.skip("6c-schemas state-at-landing pin: only enforced on introducer PR")
    base_sha = _resolve_diff_base()
    if base_sha is None:
        pytest.skip("No git base resolved")
    changed = _git_changed_paths_against(base_sha)
    assert ".claude/plans/gpp_status.v1.json" not in changed


def test_6c_schemas_submanifest_unchanged():
    if not _is_ri78b_bc10_6c_schemas_introducer_pr():
        pytest.skip("6c-schemas state-at-landing pin: only enforced on introducer PR")
    base_sha = _resolve_diff_base()
    if base_sha is None:
        pytest.skip("No git base resolved")
    changed = _git_changed_paths_against(base_sha)
    assert ".claude/plans/RI-7.8-EVIDENCE-MANIFEST.v1.json" not in changed


def test_6c_schemas_no_run_evidence_files_added():
    """6c-schemas MUST NOT add any per-call/aggregate/closure evidence files."""
    for forbidden in FORBIDDEN_RUN_EVIDENCE_PATHS:
        forbidden_path = REPO_ROOT / forbidden
        assert not forbidden_path.exists(), f"6c-schemas must not add {forbidden}; that belongs to bc10-6c-closure"


def test_6c_schemas_top_level_guard_flags_preserved():
    """gpp_status.v1.json top-level guard flags MUST remain const false."""
    if not GPP_STATUS_PATH.exists():
        pytest.skip("gpp_status.v1.json not found")
    data = _load_json(GPP_STATUS_PATH)
    assert data.get("support_widening_allowed") is False
    assert data.get("production_platform_claim_allowed") is False
    assert data.get("live_adapter_execution_allowed") is False


def test_6c_schemas_submanifest_bc10_still_false():
    """Submanifest BC-10 key must still be false (flip belongs to bc10-6c-closure)."""
    if not SUBMANIFEST_PATH.exists():
        pytest.skip("submanifest not found")
    data = _load_json(SUBMANIFEST_PATH)
    assert data.get("bc10_real_adapter_usage_cost_aggregate_recorded") is False
    assert data.get("bc1_protected_live_adapter_attestation_recorded") is True


# ---------------------------------------------------------------------------
# local-ai-review-evidence cross-artifact bind
# ---------------------------------------------------------------------------


def test_local_ai_review_work_package_matches():
    if not LOCAL_AI_REVIEW_PATH.exists():
        pytest.skip("local-ai-review-evidence missing")
    data = _load_json(LOCAL_AI_REVIEW_PATH)
    if data.get("work_package") != "RI-7.8b-bc10-6c-schemas":
        pytest.skip("local-ai-review-evidence is for another active PR")
    assert data["implementer"]["provider"] == "anthropic"
    assert data["reviewer"]["provider"] == "openai"
    assert data["reviewer"]["verdict"] in {"REVISE", "AGREE"}
