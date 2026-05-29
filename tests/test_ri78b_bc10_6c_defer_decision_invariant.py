"""Invariant tests for RI-7.8b-bc10-6c-defer-decision.

This PR is a docs/decision-only artifact recording the operator's decision
to defer the bc10 chain (real billable provider call evidence) because
actual ao-kernel usage is cli_subscription_only mode. NO provider call,
NO secret reference, NO workflow/script/pricing source mutation, NO
top-level guard flag flip, NO asset retirement.

Tests enforce (per Codex iter-11 AGREE):
- Schema Draft 2020-12 valid, additionalProperties=false recursive
- Evidence validates against schema
- Top-level guard flags const FALSE PRESERVED (gpp_status snapshot)
- bc10 aggregate STAYS FALSE in submanifest (no flip, no enum migration)
- bc10_defer_decision_recorded=true is additive key (NEW)
- gpp_status RI-7.8b-bc10-6b supersession entry is terminal/non-dispatchable:
  status=deferred_cli_only_mode, authority_consumed=false,
  effective_execution_state=deferred_non_dispatchable,
  dispatch_allowed_after_decision=false
- Historical guard_flag_policy_resolution.live_adapter_execution_allowed=true
  PRESERVED in entry but non-effective (authority_consumed=false)
- Asset preservation: PR #695/#697/#700 schemas + workflow + scripts UNCHANGED
- NO provider call, NO secret reference, NO guard flag flip
- Predecessor refs (PR #673/#691/#695/#697/#700) pinned
- Cross-AI peer review provider split (anthropic/openai)
- No Fake Work attestation
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

SCHEMA_PATH = REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ri7-8b-bc10-6c-defer-decision-evidence.schema.v1.json"
EVIDENCE_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8b-bc10-6c-DEFER-DECISION.v1.json"
SUBMANIFEST_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8-EVIDENCE-MANIFEST.v1.json"
GPP_STATUS_PATH = REPO_ROOT / ".claude" / "plans" / "gpp_status.v1.json"
LOCAL_AI_REVIEW_PATH = REPO_ROOT / "local-ai-review-evidence.v1.json"

# bc10 chain assets MUST remain unchanged (dormant preservation)
ASSET_PRESERVED_PATHS = [
    ".github/workflows/bc10-real-adapter-usage-cost.yml",
    "scripts/ri78b_bc10_activation_window.py",
    "scripts/bc10_run_scenarios.py",
    "ao_kernel/defaults/pricing/openai_gpt_4o_mini.v1.json",
    "ao_kernel/defaults/schemas/ri7-8b-bc10-6c-per-call-evidence.schema.v1.json",
    "ao_kernel/defaults/schemas/ri7-8b-bc10-6c-aggregate-evidence.schema.v1.json",
    "ao_kernel/defaults/schemas/ri7-8b-bc10-6c-closure-evidence.schema.v1.json",
    "ao_kernel/defaults/schemas/ri7-8b-bc10-6b-protected-execution-window-evidence.schema.v1.json",
    "ao_kernel/defaults/schemas/ri7-8b-bc10-6a-execution-window-authorization-evidence.schema.v1.json",
    "ao_kernel/defaults/schemas/ri7-8b-bc10-per-call-runtime-call-marker.schema.v1.json",
    ".claude/plans/RI-7.8a-LIVE-EVIDENCE-PRE-AUTHORIZATION.v1.json",
    ".claude/plans/RI-7.8b-bc1-6c-CLOSURE.v1.json",
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


def _is_ri78b_bc10_6c_defer_introducer_pr() -> bool:
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
# Schema validity
# ---------------------------------------------------------------------------


def test_defer_schema_exists():
    assert SCHEMA_PATH.exists()


def test_defer_evidence_exists():
    assert EVIDENCE_PATH.exists()


def test_defer_schema_is_draft_2020_12():
    schema = _load_json(SCHEMA_PATH)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    jsonschema.Draft202012Validator.check_schema(schema)


def test_defer_schema_uses_additional_properties_false_recursively():
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


def test_defer_evidence_validates_against_schema():
    schema = _load_json(SCHEMA_PATH)
    evidence = _load_json(EVIDENCE_PATH)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(evidence), key=lambda e: list(e.absolute_path))
    assert not errors, "Evidence does not validate: " + "; ".join(
        f"{list(e.absolute_path)}: {e.message}" for e in errors[:5]
    )


def test_defer_decision_const():
    evidence = _load_json(EVIDENCE_PATH)
    assert (
        evidence["decision"]
        == "ri78b_bc10_6c_defer_cli_only_mode_no_billable_api_call_required_assets_preserved_dormant"
    )


def test_defer_does_not_authorize_9_actions():
    evidence = _load_json(EVIDENCE_PATH)
    expected = {
        "billable_provider_call_now",
        "billable_provider_call_ever_under_this_decision",
        "openai_api_key_reference_anywhere",
        "support_widening",
        "production_platform_claim",
        "live_adapter_execution",
        "top_level_guard_flag_flip",
        "asset_retire_or_delete",
        "bc10_real_adapter_usage_cost_aggregate_flip_to_true",
    }
    assert set(evidence["does_not_authorize"]) == expected
    assert len(evidence["does_not_authorize"]) == 9


# ---------------------------------------------------------------------------
# Top-level guard flags const FALSE PRESERVED
# ---------------------------------------------------------------------------


def test_defer_top_level_guard_flags_preserved_in_gpp_status():
    gpp = _load_json(GPP_STATUS_PATH)
    assert gpp.get("support_widening_allowed") is False
    assert gpp.get("production_platform_claim_allowed") is False
    assert gpp.get("live_adapter_execution_allowed") is False


def test_defer_top_level_guard_flags_preserved_in_evidence():
    evidence = _load_json(EVIDENCE_PATH)
    assert evidence["support_widening"] is False
    assert evidence["production_platform_claim"] is False
    assert evidence["live_adapter_execution"] is False


def test_defer_current_gpp_guard_snapshot_const_false():
    evidence = _load_json(EVIDENCE_PATH)
    snap = evidence["current_gpp_guard_snapshot"]
    assert snap["support_widening_allowed"] is False
    assert snap["production_platform_claim_allowed"] is False
    assert snap["live_adapter_execution_allowed"] is False


# ---------------------------------------------------------------------------
# Submanifest semantic (bc10 aggregate stays false + defer key additive)
# ---------------------------------------------------------------------------


def test_defer_submanifest_bc10_aggregate_stays_false():
    """No real aggregate exists; no enum migration; bc10 stays false."""
    sub = _load_json(SUBMANIFEST_PATH)
    assert sub["bc10_real_adapter_usage_cost_aggregate_recorded"] is False


def test_defer_submanifest_bc10_defer_decision_recorded_true():
    sub = _load_json(SUBMANIFEST_PATH)
    assert sub["bc10_defer_decision_recorded"] is True
    assert sub["bc10_defer_decision_ref"] == ".claude/plans/RI-7.8b-bc10-6c-DEFER-DECISION.v1.json"


def test_defer_submanifest_other_keys_preserved():
    sub = _load_json(SUBMANIFEST_PATH)
    assert sub["live_evidence_pre_authorization_recorded"] is True
    assert sub["bc1_protected_live_adapter_attestation_recorded"] is True
    assert sub["final_operator_promotion_decision_recorded"] is False


# ---------------------------------------------------------------------------
# Supersession entry terminal/non-dispatchable transition
# ---------------------------------------------------------------------------


def test_defer_supersession_entry_terminal_non_dispatchable():
    gpp = _load_json(GPP_STATUS_PATH)
    entries = gpp.get("operator_bound_supersessions", [])
    bc10_entries = [e for e in entries if e.get("id") == "RI-7.8b-bc10-6b"]
    assert len(bc10_entries) == 1
    entry = bc10_entries[0]
    assert entry["status"] == "deferred_cli_only_mode"
    assert entry["authority_consumed"] is False
    assert entry["effective_execution_state"] == "deferred_non_dispatchable"
    assert entry["dispatch_allowed_after_decision"] is False
    assert entry["defer_reason"] == "operator_cli_only_no_programmatic_api_no_openai_api_key"
    assert entry["billable_provider_call_count"] == 0
    assert entry["live_adapter_execution_consumed"] is False
    assert entry["historical_authority_preserved_but_non_effective"] is True
    assert entry["defer_decision_ref"] == ".claude/plans/RI-7.8b-bc10-6c-DEFER-DECISION.v1.json"
    assert entry["actual_start_at"] is None
    assert entry["actual_end_at"] is None


def test_defer_supersession_historical_authority_preserved_but_non_effective():
    """guard_flag_policy_resolution.live_adapter_execution_allowed=true is
    PRESERVED in the entry as historical record but authority_consumed=false
    + effective_execution_state=deferred_non_dispatchable makes it
    NON-EFFECTIVE per Codex iter-11 absorb item #1."""
    gpp = _load_json(GPP_STATUS_PATH)
    entry = next(e for e in gpp["operator_bound_supersessions"] if e["id"] == "RI-7.8b-bc10-6b")
    # Historical record preserved (was set to true in bc10-6b PR #697 when entry was active)
    gfp = entry["guard_flag_policy_resolution"]
    assert gfp["live_adapter_execution_allowed"] is True  # historical
    # But effective state makes it non-dispatchable
    assert entry["authority_consumed"] is False
    assert entry["effective_execution_state"] == "deferred_non_dispatchable"


def test_defer_supersession_entry_scope_preserved():
    """Original scope + authority_mode preserved (historical record integrity)."""
    gpp = _load_json(GPP_STATUS_PATH)
    entry = next(e for e in gpp["operator_bound_supersessions"] if e["id"] == "RI-7.8b-bc10-6b")
    assert entry["scope"] == "bc10_real_adapter_usage_cost_only"
    assert entry["authority_mode"] == "manual_protected_environment"
    assert entry["max_billable_calls_count"] == 4
    assert entry["max_usd"] == 5.00


# ---------------------------------------------------------------------------
# Asset preservation (dormant)
# ---------------------------------------------------------------------------


def test_defer_evidence_asset_preservation_block():
    evidence = _load_json(EVIDENCE_PATH)
    asset = evidence["asset_preservation_block"]
    assert asset["current_mode"] == "cli_subscription_only"
    assert asset["current_dispatch_allowed"] is False
    assert asset["future_reactivation_requires"] == "new_operator_bound_supersession_pr"
    assert asset["asset_preserved_for_future_api_mode"] is True
    assert asset["retire_status"] == "not_retired_dormant_assets_for_audit_continuity_and_future_api_mode"
    pr_set = {a["pr"] for a in asset["assets_preserved"]}
    assert pr_set == {695, 697, 700}


def test_defer_no_asset_retire_or_delete():
    """All bc10 chain assets MUST still exist (dormant preservation)."""
    for asset_path in ASSET_PRESERVED_PATHS:
        full = REPO_ROOT / asset_path
        assert full.exists(), f"Asset deleted in defer PR (forbidden): {asset_path}"


def test_defer_forbidden_change_audit_machine_enforced():
    """Asset preservation: bc10 workflow + scripts + pricing source + schemas
    MUST NOT be modified by this defer PR."""
    if not _is_ri78b_bc10_6c_defer_introducer_pr():
        pytest.skip("defer state-at-landing pin: only enforced on introducer PR")
    base_sha = _resolve_diff_base()
    if base_sha is None:
        pytest.skip("No git base resolved")
    changed = _git_changed_paths_against(base_sha)
    for asset_path in ASSET_PRESERVED_PATHS:
        assert asset_path not in changed, f"Asset MODIFIED in defer PR (forbidden): {asset_path}"


# ---------------------------------------------------------------------------
# Mutations performed object
# ---------------------------------------------------------------------------


def test_defer_mutations_performed_object():
    evidence = _load_json(EVIDENCE_PATH)
    mut = evidence["mutations_performed"]
    # Created surfaces
    assert mut["schema_created"] is True
    assert mut["evidence_created"] is True
    assert mut["supersession_entry_transitioned_to_terminal"] is True
    assert mut["submanifest_additive_key_added"] is True
    # NOT modified surfaces
    assert mut["workflow_modified"] is False
    assert mut["activation_script_modified"] is False
    assert mut["runner_script_modified"] is False
    assert mut["pricing_source_modified"] is False
    assert mut["per_call_schema_modified"] is False
    assert mut["aggregate_schema_modified"] is False
    assert mut["closure_schema_modified"] is False
    # NO bc10 execution
    assert mut["bc10_workflow_dispatched"] is False
    assert mut["provider_call_performed"] is False
    assert mut["secret_referenced"] is False
    assert mut["guard_flag_flipped"] is False
    assert mut["asset_retired_or_deleted"] is False


# ---------------------------------------------------------------------------
# No Fake Work attestation
# ---------------------------------------------------------------------------


def test_defer_no_fake_work_attestation():
    evidence = _load_json(EVIDENCE_PATH)
    nfw = evidence["no_fake_work_attestation"]
    assert nfw["real_billable_call_under_cli_only_would_be_fake_work"] is True
    assert nfw["evidence_for_cli_only_mode_is_real_acceptance"] is True
    assert nfw["no_provider_response_recorded"] is True
    assert nfw["no_token_usage_recorded"] is True
    assert nfw["no_cost_aggregate_computed"] is True


# ---------------------------------------------------------------------------
# Current usage pattern (cli-only mode)
# ---------------------------------------------------------------------------


def test_defer_current_usage_pattern_cli_only():
    evidence = _load_json(EVIDENCE_PATH)
    p = evidence["current_usage_pattern"]
    assert p["claude_code_cli_monthly_subscription"] is True
    assert p["codex_cli_monthly_subscription"] is True
    assert p["no_programmatic_api_usage"] is True
    assert p["no_openai_api_key_available_or_planned"] is True
    assert p["no_AoKernelClient_llm_call_invocations"] is True
    assert p["cli_subscription_operator_managed_mode"] is True


# ---------------------------------------------------------------------------
# Predecessor refs
# ---------------------------------------------------------------------------


def test_defer_predecessor_pr_numbers():
    evidence = _load_json(EVIDENCE_PATH)
    assert evidence["ri78a_predecessor_ref"]["pr_number"] == 673
    assert evidence["ri78b_bc1_6c_predecessor_ref"]["pr_number"] == 691
    assert evidence["ri78b_bc10_6a_predecessor_ref"]["pr_number"] == 695
    assert evidence["ri78b_bc10_6b_predecessor_ref"]["pr_number"] == 697
    assert evidence["ri78b_bc10_6c_schemas_predecessor_ref"]["pr_number"] == 700


# ---------------------------------------------------------------------------
# Operator decision record
# ---------------------------------------------------------------------------


def test_defer_operator_signature_halildeu_iso_8601_no_secret():
    import re

    evidence = _load_json(EVIDENCE_PATH)
    op = evidence["operator_decision_record"]
    assert op["github_login"] == "Halildeu"
    assert op["no_secret_assertion"] is True
    assert op["decision_scope"] == "bc10_real_adapter_usage_cost_chain_defer_under_cli_only_mode"
    assert re.match(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$",
        op["decision_recorded_at"],
    )
    assert op["decision_source"], "decision_source must be non-empty"
    assert op["observation_notes"], "observation_notes must be non-empty"


# ---------------------------------------------------------------------------
# Cross-AI peer review
# ---------------------------------------------------------------------------


def test_defer_cross_ai_review_provider_split():
    evidence = _load_json(EVIDENCE_PATH)
    cr = evidence["cross_ai_review_ref"]
    assert cr["implementer_provider"] == "anthropic"
    assert cr["reviewer_provider"] == "openai"
    assert cr["final_verdict"] in {"REVISE", "AGREE"}
    assert cr["thread_id"], "thread_id must be non-empty"


def test_defer_cross_artifact_verdict_equality():
    if not LOCAL_AI_REVIEW_PATH.exists():
        pytest.skip("local-ai-review-evidence missing")
    review = _load_json(LOCAL_AI_REVIEW_PATH)
    if review.get("work_package") != "RI-7.8b-bc10-6c-defer-decision":
        pytest.skip("local-ai-review-evidence is for another active PR")
    evidence = _load_json(EVIDENCE_PATH)
    assert review["reviewer"]["provider"] == "openai"
    assert review["implementer"]["provider"] == "anthropic"
    assert review["reviewer"]["verdict"] == evidence["cross_ai_review_ref"]["final_verdict"]


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


def test_defer_negative_decision_drift_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("decision",), "some_other_decision"))
    _assert_rejected(bad, "decision drift")


def test_defer_negative_dispatch_allowed_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (("supersession_entry_transition", "dispatch_allowed_after_decision"), True),
    )
    _assert_rejected(bad, "dispatch_allowed_after_decision must be false const")


def test_defer_negative_authority_consumed_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("supersession_entry_transition", "authority_consumed"), True))
    _assert_rejected(bad, "authority_consumed must be false const")


def test_defer_negative_provider_call_performed_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("mutations_performed", "provider_call_performed"), True))
    _assert_rejected(bad, "provider_call_performed must be false const")


def test_defer_negative_asset_retired_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("mutations_performed", "asset_retired_or_deleted"), True))
    _assert_rejected(bad, "asset_retired_or_deleted must be false const")


def test_defer_negative_workflow_modified_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("mutations_performed", "workflow_modified"), True))
    _assert_rejected(bad, "workflow_modified must be false const")


def test_defer_negative_top_level_guard_flag_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("live_adapter_execution",), True))
    _assert_rejected(bad, "live_adapter_execution must be false const")


def test_defer_negative_submanifest_after_bc10_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (
            ("submanifest_transition", "after", "bc10_real_adapter_usage_cost_aggregate_recorded"),
            True,
        ),
    )
    _assert_rejected(bad, "bc10 aggregate must stay false in defer PR")


def test_defer_negative_submanifest_after_defer_false_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (("submanifest_transition", "after", "bc10_defer_decision_recorded"), False),
    )
    _assert_rejected(bad, "bc10_defer_decision_recorded must be true in 'after'")


def test_defer_negative_status_drift_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (("supersession_entry_transition", "after_status"), "active"),
    )
    _assert_rejected(bad, "after_status must be deferred_cli_only_mode")


def test_defer_negative_current_mode_drift_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (("asset_preservation_block", "current_mode"), "api_mode"),
    )
    _assert_rejected(bad, "current_mode must be cli_subscription_only")


def test_defer_negative_no_fake_work_false_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (("no_fake_work_attestation", "real_billable_call_under_cli_only_would_be_fake_work"), False),
    )
    _assert_rejected(bad, "no fake work attestation must hold")


def test_defer_negative_does_not_authorize_missing_action_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = copy.deepcopy(evidence)
    bad["does_not_authorize"] = [
        "billable_provider_call_now",
        "billable_provider_call_ever_under_this_decision",
        "openai_api_key_reference_anywhere",
        "support_widening",
        "production_platform_claim",
        "live_adapter_execution",
        "top_level_guard_flag_flip",
        "asset_retire_or_delete",
        # missing bc10_real_adapter_usage_cost_aggregate_flip_to_true
    ]
    _assert_rejected(bad, "does_not_authorize must have all 9 actions")
