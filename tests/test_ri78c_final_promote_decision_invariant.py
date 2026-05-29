"""Invariant tests for RI-7.8c final promote decision (non-promotion under cli-only mode).

This PR records the operator's authoritative non-promotion decision for the
RI-7 readiness chain under current CLI-only subscription mode. Submanifest
final_operator_promotion_decision_recorded flips false -> true. Top-level
guard flags const FALSE PRESERVED. NO bc10 chain asset modification.

Tests enforce (per Codex iter-11 absorb item #4 + #5):
- Schema Draft 2020-12 valid, additionalProperties=false recursive
- Evidence validates against schema
- Decision string includes no_live_adapter_execution (GPP-9 alignment)
- Top-level guard flags const FALSE PRESERVED
- Submanifest final flip false -> true
- bc10 aggregate stays false (no enum migration; bc10 defer ref preserved)
- bc1 + bc10 scope-out under cli-only mode (NOT 'passed')
- bc10 chain assets all unchanged
- gpp_status untouched (RI-7.8b-bc10-6b stays in deferred_cli_only_mode terminal state from PR #731)
- Predecessor refs PR #673 (ri78a) + #691 (bc1) + #731 (bc10 defer) digests match
- No fake work attestation
- Cross-AI peer review provider split
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

SCHEMA_PATH = REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ri7-8c-final-promote-decision-evidence.schema.v1.json"
EVIDENCE_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8c-FINAL-PROMOTE-DECISION.v1.json"
SUBMANIFEST_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8-EVIDENCE-MANIFEST.v1.json"
READINESS_MANIFEST_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7-EVIDENCE-MANIFEST.v1.json"
GPP_STATUS_PATH = REPO_ROOT / ".claude" / "plans" / "gpp_status.v1.json"
DEFER_EVIDENCE_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8b-bc10-6c-DEFER-DECISION.v1.json"
RI78A_EVIDENCE_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8a-LIVE-EVIDENCE-PRE-AUTHORIZATION.v1.json"
RI78B_BC1_6C_CLOSURE_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8b-bc1-6c-CLOSURE.v1.json"
LOCAL_AI_REVIEW_PATH = REPO_ROOT / "local-ai-review-evidence.v1.json"

ASSET_PRESERVED_PATHS = [
    ".github/workflows/bc10-real-adapter-usage-cost.yml",
    "scripts/ri78b_bc10_activation_window.py",
    "scripts/bc10_run_scenarios.py",
    "ao_kernel/defaults/pricing/openai_gpt_4o_mini.v1.json",
    "ao_kernel/defaults/schemas/ri7-8b-bc10-6c-per-call-evidence.schema.v1.json",
    "ao_kernel/defaults/schemas/ri7-8b-bc10-6c-aggregate-evidence.schema.v1.json",
    "ao_kernel/defaults/schemas/ri7-8b-bc10-6c-closure-evidence.schema.v1.json",
    "ao_kernel/defaults/schemas/ri7-8b-bc10-6c-defer-decision-evidence.schema.v1.json",
    "ao_kernel/defaults/schemas/ri7-8b-bc10-6b-protected-execution-window-evidence.schema.v1.json",
    "ao_kernel/defaults/schemas/ri7-8b-bc10-6a-execution-window-authorization-evidence.schema.v1.json",
    "ao_kernel/defaults/schemas/ri7-8b-bc10-per-call-runtime-call-marker.schema.v1.json",
    ".claude/plans/RI-7.8a-LIVE-EVIDENCE-PRE-AUTHORIZATION.v1.json",
    ".claude/plans/RI-7.8b-bc1-6c-CLOSURE.v1.json",
    ".claude/plans/RI-7.8b-bc10-6a-EXECUTION-WINDOW-AUTHORIZATION.v1.json",
    ".claude/plans/RI-7.8b-bc10-6b-PROTECTED-EXECUTION-WINDOW.v1.json",
    ".claude/plans/RI-7.8b-bc10-6c-DEFER-DECISION.v1.json",
]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_diff_base() -> str | None:
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
    for ref in ["origin/main", "main"]:
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


def _is_ri78c_introducer_pr() -> bool:
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
        return str(EVIDENCE_PATH.relative_to(REPO_ROOT)) in added
    except (subprocess.SubprocessError, OSError):
        return False


# ---------------------------------------------------------------------------
# Schema / evidence validity
# ---------------------------------------------------------------------------


def test_ri78c_schema_exists():
    assert SCHEMA_PATH.exists()


def test_ri78c_evidence_exists():
    assert EVIDENCE_PATH.exists()


def test_ri78c_schema_is_draft_2020_12():
    schema = _load_json(SCHEMA_PATH)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    jsonschema.Draft202012Validator.check_schema(schema)


def test_ri78c_schema_additional_properties_false_recursive():
    schema = _load_json(SCHEMA_PATH)

    def check(node, ctx=""):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node.get("additionalProperties") is False, (
                    f"{ctx}: object type missing additionalProperties:false"
                )
            for k, v in node.items():
                check(v, f"{ctx}.{k}")
        elif isinstance(node, list):
            for i, item in enumerate(node):
                check(item, f"{ctx}[{i}]")

    check(schema)


def test_ri78c_evidence_validates_against_schema():
    schema = _load_json(SCHEMA_PATH)
    evidence = _load_json(EVIDENCE_PATH)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(evidence), key=lambda e: list(e.absolute_path))
    assert not errors, "Evidence does not validate: " + "; ".join(
        f"{list(e.absolute_path)}: {e.message}" for e in errors[:5]
    )


# ---------------------------------------------------------------------------
# Decision string (Codex iter-11 absorb #4)
# ---------------------------------------------------------------------------


def test_ri78c_decision_string_includes_required_clauses():
    """Decision string must include no_live_adapter_execution per GPP-9 alignment."""
    evidence = _load_json(EVIDENCE_PATH)
    decision = evidence["decision"]
    assert decision == (
        "ri78c_final_operator_non_promotion_keep_narrow_stable_runtime_authoritative_"
        "cli_only_no_programmatic_api_no_live_adapter_execution_no_support_widening_"
        "no_production_claim"
    )
    # Per Codex iter-11 absorb item #4 — explicit required clauses
    assert "no_live_adapter_execution" in decision
    assert "no_support_widening" in decision
    assert "no_production_claim" in decision
    assert "no_programmatic_api" in decision
    assert "cli_only" in decision
    assert "keep_narrow_stable_runtime" in decision


def test_ri78c_decision_aligned_with_gpp9_closure():
    evidence = _load_json(EVIDENCE_PATH)
    cons = evidence["gpp9_closure_consistency"]
    assert cons["existing_gpp9_decision_string"] == (
        "gpp9_keep_narrow_stable_runtime_authoritative_program_closed_"
        "no_live_adapter_execution_no_support_widening_no_production_claim"
    )
    assert cons["ri78c_decision_aligned_with_gpp9_closure"] is True
    assert cons["top_level_guard_flags_remain_const_false"] is True
    assert cons["keep_narrow_stable_runtime_remains_authoritative"] is True
    assert cons["no_program_reopening"] is True


# ---------------------------------------------------------------------------
# Top-level guard flags const FALSE PRESERVED
# ---------------------------------------------------------------------------


def test_ri78c_top_level_guard_flags_const_false_in_evidence():
    evidence = _load_json(EVIDENCE_PATH)
    assert evidence["support_widening"] is False
    assert evidence["production_platform_claim"] is False
    assert evidence["live_adapter_execution"] is False


def test_ri78c_gpp_status_top_level_guard_flags_preserved():
    """gpp_status top-level guard flags MUST remain const false."""
    gpp = _load_json(GPP_STATUS_PATH)
    assert gpp.get("support_widening_allowed") is False
    assert gpp.get("production_platform_claim_allowed") is False
    assert gpp.get("live_adapter_execution_allowed") is False


def test_ri78c_evidence_current_gpp_guard_snapshot_const_false():
    evidence = _load_json(EVIDENCE_PATH)
    snap = evidence["current_gpp_guard_snapshot"]
    assert snap["support_widening_allowed"] is False
    assert snap["production_platform_claim_allowed"] is False
    assert snap["live_adapter_execution_allowed"] is False


# ---------------------------------------------------------------------------
# Submanifest final flip false -> true; bc10 aggregate stays false
# ---------------------------------------------------------------------------


def test_ri78c_submanifest_final_flip_true():
    sub = _load_json(SUBMANIFEST_PATH)
    assert sub["final_operator_promotion_decision_recorded"] is True


def test_ri78c_submanifest_bc10_aggregate_stays_false():
    """bc10 aggregate stays false (no enum migration; defer-decision pattern preserved)."""
    sub = _load_json(SUBMANIFEST_PATH)
    assert sub["bc10_real_adapter_usage_cost_aggregate_recorded"] is False


def test_ri78c_submanifest_bc10_defer_decision_recorded_preserved():
    """bc10 defer decision key from PR #731 MUST remain true."""
    sub = _load_json(SUBMANIFEST_PATH)
    assert sub["bc10_defer_decision_recorded"] is True


def test_ri78c_submanifest_other_keys_preserved():
    sub = _load_json(SUBMANIFEST_PATH)
    assert sub["live_evidence_pre_authorization_recorded"] is True
    assert sub["bc1_protected_live_adapter_attestation_recorded"] is True


def test_ri78c_evidence_submanifest_snapshot_after_decision():
    evidence = _load_json(EVIDENCE_PATH)
    snap = evidence["ri78_submanifest_snapshot_after_decision"]
    assert snap["live_evidence_pre_authorization_recorded"] is True
    assert snap["bc1_protected_live_adapter_attestation_recorded"] is True
    assert snap["bc10_real_adapter_usage_cost_aggregate_recorded"] is False
    assert snap["bc10_defer_decision_recorded"] is True
    assert snap["final_operator_promotion_decision_recorded"] is True


# ---------------------------------------------------------------------------
# BC baseline scope-out (NOT 'passed')
# ---------------------------------------------------------------------------


def test_ri78c_bc_baseline_scope_out_not_passed():
    evidence = _load_json(EVIDENCE_PATH)
    rec = evidence["bc_baseline_scope_out_record"]
    assert (
        rec["bc1_status_under_cli_only_mode"]
        == "scope_out_under_cli_only_mode_not_passed_marker_only_evidence_in_pr_691"
    )
    assert (
        rec["bc10_status_under_cli_only_mode"]
        == "scope_out_under_cli_only_mode_not_passed_deferred_per_pr_731_assets_dormant"
    )
    assert rec["bc1_reclassification_to_passed_explicitly_forbidden"] is True
    assert rec["bc10_reclassification_to_passed_explicitly_forbidden"] is True
    assert rec["bc1_through_bc9_baseline_preserved"] is True
    assert rec["no_enum_migration"] is True


# ---------------------------------------------------------------------------
# Predecessor refs (PR #673, #691, #731)
# ---------------------------------------------------------------------------


def test_ri78c_predecessor_pr_numbers():
    evidence = _load_json(EVIDENCE_PATH)
    assert evidence["ri78a_predecessor_ref"]["pr_number"] == 673
    assert evidence["ri78b_bc1_6c_predecessor_ref"]["pr_number"] == 691
    assert evidence["ri78b_bc10_6c_defer_decision_predecessor_ref"]["pr_number"] == 731


def test_ri78c_predecessor_digest_match_ri78a():
    if not _is_ri78c_introducer_pr():
        pytest.skip("ri78c state-at-landing pin: only enforced on introducer PR")
    evidence = _load_json(EVIDENCE_PATH)
    pred = evidence["ri78a_predecessor_ref"]
    expected = _sha256_file(RI78A_EVIDENCE_PATH)
    assert pred["evidence_sha256"] == expected


def test_ri78c_predecessor_digest_match_bc1_closure():
    if not _is_ri78c_introducer_pr():
        pytest.skip("ri78c state-at-landing pin: only enforced on introducer PR")
    evidence = _load_json(EVIDENCE_PATH)
    pred = evidence["ri78b_bc1_6c_predecessor_ref"]
    expected = _sha256_file(RI78B_BC1_6C_CLOSURE_PATH)
    assert pred["closure_evidence_sha256"] == expected


def test_ri78c_predecessor_digest_match_bc10_defer():
    if not _is_ri78c_introducer_pr():
        pytest.skip("ri78c state-at-landing pin: only enforced on introducer PR")
    evidence = _load_json(EVIDENCE_PATH)
    pred = evidence["ri78b_bc10_6c_defer_decision_predecessor_ref"]
    expected = _sha256_file(DEFER_EVIDENCE_PATH)
    assert pred["defer_evidence_sha256"] == expected


# ---------------------------------------------------------------------------
# Asset preservation (NO bc10 chain modification + gpp_status untouched)
# ---------------------------------------------------------------------------


def test_ri78c_no_asset_modification():
    for asset_path in ASSET_PRESERVED_PATHS:
        full = REPO_ROOT / asset_path
        assert full.exists(), f"Asset deleted in ri78c PR (forbidden): {asset_path}"


def test_ri78c_forbidden_change_audit_machine_enforced():
    if not _is_ri78c_introducer_pr():
        pytest.skip("ri78c state-at-landing pin: only enforced on introducer PR")
    base_sha = _resolve_diff_base()
    if base_sha is None:
        pytest.skip("No git base resolved")
    changed = _git_changed_paths_against(base_sha)
    forbidden = [
        ".claude/plans/gpp_status.v1.json",
    ] + ASSET_PRESERVED_PATHS
    for f in forbidden:
        assert f not in changed, f"Forbidden surface modified in ri78c PR: {f}"


def test_ri78c_gpp_status_bc10_entry_terminal_preserved():
    """RI-7.8b-bc10-6b supersession entry stays in deferred_cli_only_mode terminal state from PR #731."""
    gpp = _load_json(GPP_STATUS_PATH)
    entries = gpp.get("operator_bound_supersessions", [])
    bc10_entries = [e for e in entries if e.get("id") == "RI-7.8b-bc10-6b"]
    assert len(bc10_entries) == 1
    entry = bc10_entries[0]
    assert entry["status"] == "deferred_cli_only_mode"
    assert entry["authority_consumed"] is False
    assert entry["dispatch_allowed_after_decision"] is False


# ---------------------------------------------------------------------------
# Mutations performed object
# ---------------------------------------------------------------------------


def test_ri78c_mutations_performed_object():
    evidence = _load_json(EVIDENCE_PATH)
    mut = evidence["mutations_performed"]
    assert mut["schema_created"] is True
    assert mut["evidence_created"] is True
    assert mut["submanifest_final_decision_key_flipped"] is True
    assert mut["gpp_status_mutated"] is False
    assert mut["workflow_modified"] is False
    assert mut["activation_script_modified"] is False
    assert mut["runner_script_modified"] is False
    assert mut["pricing_source_modified"] is False
    assert mut["bc10_chain_schemas_modified"] is False
    assert mut["bc10_chain_evidence_modified"] is False
    assert mut["bc10_workflow_dispatched"] is False
    assert mut["provider_call_performed"] is False
    assert mut["secret_referenced"] is False
    assert mut["guard_flag_flipped"] is False
    assert mut["asset_retired_or_deleted"] is False
    assert mut["gpp9_closure_record_modified"] is False


# ---------------------------------------------------------------------------
# No Fake Work attestation
# ---------------------------------------------------------------------------


def test_ri78c_no_fake_work_attestation():
    evidence = _load_json(EVIDENCE_PATH)
    nfw = evidence["no_fake_work_attestation"]
    assert nfw["non_promotion_under_cli_only_is_real_acceptance"] is True
    assert nfw["promoting_to_general_purpose_production_under_cli_only_would_be_fake_work"] is True
    assert nfw["no_billable_call_recorded"] is True
    assert nfw["no_real_aggregate_recorded"] is True
    assert nfw["no_artificial_promotion_evidence_generated"] is True


# ---------------------------------------------------------------------------
# Future promotion authority chain (HARD pin: no flip from this PR)
# ---------------------------------------------------------------------------


def test_ri78c_future_promotion_authority_chain():
    evidence = _load_json(EVIDENCE_PATH)
    fpac = evidence["future_promotion_authority_chain"]
    assert fpac["future_general_purpose_production_promotion_requires_new_operator_bound_supersession_pr"] is True
    assert fpac["future_general_purpose_beta_promotion_requires_new_operator_bound_supersession_pr"] is True
    assert fpac["future_promotion_requires_explicit_production_platform_claim_allowed_flip"] is True
    assert fpac["future_promotion_requires_full_production_matrix_evidence"] is True
    assert fpac["future_promotion_requires_operator_verified_semantics"] is True
    assert fpac["bc10_chain_assets_remain_dormant_for_future_api_mode_reactivation"] is True
    assert fpac["current_ri78c_decision_does_not_authorize_any_future_flip"] is True


# ---------------------------------------------------------------------------
# Cross-AI peer review
# ---------------------------------------------------------------------------


def test_ri78c_cross_ai_review_provider_split():
    evidence = _load_json(EVIDENCE_PATH)
    cr = evidence["cross_ai_review_ref"]
    assert cr["implementer_provider"] == "anthropic"
    assert cr["reviewer_provider"] == "openai"
    assert cr["final_verdict"] in {"REVISE", "AGREE"}
    assert cr["thread_id"], "thread_id must be non-empty"


# ---------------------------------------------------------------------------
# Negative schema tests
# ---------------------------------------------------------------------------


def _mutate(evidence: dict, *path_value_pairs) -> dict:
    out = copy.deepcopy(evidence)
    for path, value in path_value_pairs:
        cursor = out
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = value
    return out


def _assert_rejected(evidence: dict, reason: str):
    schema = _load_json(SCHEMA_PATH)
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(evidence))
    assert errors, f"Mutation should be rejected: {reason}"


def test_ri78c_negative_decision_drift_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("decision",), "ri78c_promote_general_purpose_production"))
    _assert_rejected(bad, "decision must be const non-promotion")


def test_ri78c_negative_top_level_guard_flag_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("live_adapter_execution",), True))
    _assert_rejected(bad, "live_adapter_execution must be false const")


def test_ri78c_negative_support_widening_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("support_widening",), True))
    _assert_rejected(bad, "support_widening must be false const")


def test_ri78c_negative_production_platform_claim_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("production_platform_claim",), True))
    _assert_rejected(bad, "production_platform_claim must be false const")


def test_ri78c_negative_submanifest_after_final_false_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (("submanifest_transition", "after", "final_operator_promotion_decision_recorded"), False),
    )
    _assert_rejected(bad, "submanifest after.final must be true")


def test_ri78c_negative_provider_call_performed_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("mutations_performed", "provider_call_performed"), True))
    _assert_rejected(bad, "provider_call_performed must be false const")


def test_ri78c_negative_guard_flag_flipped_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("mutations_performed", "guard_flag_flipped"), True))
    _assert_rejected(bad, "guard_flag_flipped must be false const")


def test_ri78c_negative_asset_retired_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("mutations_performed", "asset_retired_or_deleted"), True))
    _assert_rejected(bad, "asset_retired_or_deleted must be false const")


def test_ri78c_negative_bc10_aggregate_flip_to_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (
            ("ri78_submanifest_snapshot_after_decision", "bc10_real_adapter_usage_cost_aggregate_recorded"),
            True,
        ),
    )
    _assert_rejected(bad, "bc10 aggregate must stay false in ri78c snapshot")


def test_ri78c_negative_bc1_reclassification_false_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (("bc_baseline_scope_out_record", "bc1_reclassification_to_passed_explicitly_forbidden"), False),
    )
    _assert_rejected(bad, "bc1 reclassification forbidden must be true const")


def test_ri78c_negative_no_fake_work_false_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (("no_fake_work_attestation", "non_promotion_under_cli_only_is_real_acceptance"), False),
    )
    _assert_rejected(bad, "no fake work attestation must hold")


def test_ri78c_negative_does_not_authorize_missing_action_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = copy.deepcopy(evidence)
    bad["does_not_authorize"] = [
        "support_widening",
        "production_platform_claim",
        "live_adapter_execution",
        "top_level_guard_flag_flip",
        "bc10_chain_dormant_asset_retire_or_delete",
        "bc1_or_bc10_baseline_reclassification_to_passed",
        "billable_provider_call",
        "openai_api_key_reference",
        "general_purpose_production_platform_promotion_under_cli_only_mode",
        # missing promote_general_purpose_beta_under_cli_only_mode
    ]
    _assert_rejected(bad, "does_not_authorize must have all 10 actions")
