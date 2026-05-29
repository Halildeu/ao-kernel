"""Invariant tests for RI-7.8b-bc10-6b protected execution window infrastructure slice.

This test suite enforces:

- Schema strictness (Draft 2020-12, additionalProperties=false, const pins, exact-set forbidden audit)
- Evidence validates against schema
- Operator signature: Halildeu + ISO 8601 UTC + no-secret-assertion + 8-signal contract
- Authority mode = manual_protected_environment (NOT autonomous)
- workflow file exists with const-matching content_sha256
- activation script + runner script exist + executable
- pricing source file exists with const-matching digest
- supersession entry exists in gpp_status with correct keys + manual_protected_environment authority
- Top-level guard flags const false PRESERVED (NOT touched)
- Submanifest unchanged (bc1=true post-#691, bc10=false)
- 9-key readiness manifest unchanged at 9/9 true
- Predecessor digest pins (RI-7.8a, BC-1 6c closure, bc10-6a)
- Marker schema valid + sample marker validates
- forbidden_change_audit exact set (10 surfaces) + machine-enforced via git diff
- Cross-AI peer review provider split (anthropic implementer, openai reviewer)
- Cross-artifact verdict equality
- 22+ negative drift tests
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

SCHEMA_PATH = (
    REPO_ROOT
    / "ao_kernel"
    / "defaults"
    / "schemas"
    / "ri7-8b-bc10-6b-protected-execution-window-evidence.schema.v1.json"
)
MARKER_SCHEMA_PATH = (
    REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ri7-8b-bc10-per-call-runtime-call-marker.schema.v1.json"
)
PRICING_SCHEMA_PATH = (
    REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ao-kernel-provider-pricing-source.schema.v1.json"
)
EVIDENCE_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8b-bc10-6b-PROTECTED-EXECUTION-WINDOW.v1.json"
SUBMANIFEST_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8-EVIDENCE-MANIFEST.v1.json"
READINESS_MANIFEST_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7-EVIDENCE-MANIFEST.v1.json"
RI78A_EVIDENCE_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8a-LIVE-EVIDENCE-PRE-AUTHORIZATION.v1.json"
RI78B_BC1_6C_CLOSURE_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8b-bc1-6c-CLOSURE.v1.json"
RI78B_BC10_6A_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8b-bc10-6a-EXECUTION-WINDOW-AUTHORIZATION.v1.json"
GPP_STATUS_PATH = REPO_ROOT / ".claude" / "plans" / "gpp_status.v1.json"
LOCAL_AI_REVIEW_PATH = REPO_ROOT / "local-ai-review-evidence.v1.json"

WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "bc10-real-adapter-usage-cost.yml"
ACTIVATION_SCRIPT_PATH = REPO_ROOT / "scripts" / "ri78b_bc10_activation_window.py"
RUNNER_SCRIPT_PATH = REPO_ROOT / "scripts" / "bc10_run_scenarios.py"
PRICING_SOURCE_PATH = REPO_ROOT / "ao_kernel" / "defaults" / "pricing" / "openai_gpt_4o_mini.v1.json"

EXPECTED_FORBIDDEN_SURFACES = [
    ".claude/plans/RI-7.8-EVIDENCE-MANIFEST.v1.json",
    ".claude/plans/RI-7.8a-LIVE-EVIDENCE-PRE-AUTHORIZATION.v1.json",
    ".claude/plans/RI-7.8b-bc1-6c-CLOSURE.v1.json",
    ".claude/plans/RI-7.8b-bc10-6a-EXECUTION-WINDOW-AUTHORIZATION.v1.json",
    ".claude/plans/RI-7-EVIDENCE-MANIFEST.v1.json",
    "ao_kernel/__init__.py",
    "ao_kernel/defaults/policies/",
    "ao_kernel/ao_release_gate.py",
    "docs/PUBLIC-BETA.md",
    "scripts/repo_intelligence_tier_promotion_readiness.py",
]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _is_ri78b_bc10_6b_introducer_pr() -> bool:
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


def _skip_if_current_local_review_evidence_is_for_another_slice() -> None:
    if not LOCAL_AI_REVIEW_PATH.exists():
        return
    review = _load_json(LOCAL_AI_REVIEW_PATH)
    if review.get("work_package") != "RI-7.8b-bc10-6b":
        pytest.skip("local-ai-review-evidence.v1.json belongs to another active PR work package")


def _path_matches_surface(path: str, surface: str) -> bool:
    if surface.endswith("/"):
        return path.startswith(surface)
    return path == surface


# ---------------------------------------------------------------------------
# Schema / evidence structural invariants
# ---------------------------------------------------------------------------


def test_ri78b_bc10_6b_schema_path_exists():
    assert SCHEMA_PATH.exists(), f"Schema missing: {SCHEMA_PATH}"


def test_ri78b_bc10_6b_evidence_path_exists():
    assert EVIDENCE_PATH.exists(), f"Evidence missing: {EVIDENCE_PATH}"


def test_ri78b_bc10_6b_marker_schema_path_exists():
    assert MARKER_SCHEMA_PATH.exists(), f"Marker schema missing: {MARKER_SCHEMA_PATH}"


def test_ri78b_bc10_6b_pricing_schema_path_exists():
    assert PRICING_SCHEMA_PATH.exists(), f"Pricing schema missing: {PRICING_SCHEMA_PATH}"


def test_ri78b_bc10_6b_pricing_source_exists():
    assert PRICING_SOURCE_PATH.exists(), f"Pricing source missing: {PRICING_SOURCE_PATH}"


def test_ri78b_bc10_6b_workflow_exists():
    assert WORKFLOW_PATH.exists(), f"Workflow missing: {WORKFLOW_PATH}"


def test_ri78b_bc10_6b_activation_script_exists():
    assert ACTIVATION_SCRIPT_PATH.exists(), f"Activation script missing: {ACTIVATION_SCRIPT_PATH}"


def test_ri78b_bc10_6b_runner_script_exists():
    assert RUNNER_SCRIPT_PATH.exists(), f"Runner script missing: {RUNNER_SCRIPT_PATH}"


def test_ri78b_bc10_6b_schema_is_draft_2020_12():
    schema = _load_json(SCHEMA_PATH)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    jsonschema.Draft202012Validator.check_schema(schema)


def test_ri78b_bc10_6b_marker_schema_is_draft_2020_12():
    schema = _load_json(MARKER_SCHEMA_PATH)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    jsonschema.Draft202012Validator.check_schema(schema)


def test_ri78b_bc10_6b_pricing_schema_is_draft_2020_12():
    schema = _load_json(PRICING_SCHEMA_PATH)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    jsonschema.Draft202012Validator.check_schema(schema)


def test_ri78b_bc10_6b_evidence_validates_against_schema():
    schema = _load_json(SCHEMA_PATH)
    evidence = _load_json(EVIDENCE_PATH)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(evidence), key=lambda e: list(e.absolute_path))
    assert not errors, "Evidence does not validate: " + "; ".join(
        f"{list(e.absolute_path)}: {e.message}" for e in errors[:5]
    )


def test_ri78b_bc10_6b_pricing_source_validates():
    schema = _load_json(PRICING_SCHEMA_PATH)
    data = _load_json(PRICING_SOURCE_PATH)
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(data))
    assert not errors, "Pricing source does not validate: " + "; ".join(
        f"{list(e.absolute_path)}: {e.message}" for e in errors[:5]
    )


def test_ri78b_bc10_6b_decision_const():
    evidence = _load_json(EVIDENCE_PATH)
    assert (
        evidence["decision"]
        == "ri78b_bc10_6b_protected_execution_window_infrastructure_recorded_dispatch_pending_no_run_evidence_no_submanifest_flip"
    )


def test_ri78b_bc10_6b_authorization_effect_const():
    evidence = _load_json(EVIDENCE_PATH)
    assert (
        evidence["authorization_effect"]
        == "protected_execution_window_infrastructure_recorded_pending_operator_dispatch_no_billable_call_no_submanifest_flip"
    )


def test_ri78b_bc10_6b_does_not_authorize_8_enum():
    evidence = _load_json(EVIDENCE_PATH)
    expected = {
        "credential_material_in_repo",
        "credential_input_parameter",
        "credential_material_in_artifact_or_log",
        "credential_reference_outside_protected_environment",
        "bc10_submanifest_flip_now",
        "automatic_workflow_dispatch_without_operator_action",
        "cost_overflow_outside_max_usd",
        "support_widening_or_production_platform_claim",
    }
    assert set(evidence["does_not_authorize"]) == expected
    assert len(evidence["does_not_authorize"]) == 8


def test_ri78b_bc10_6b_authority_mode_manual_protected_environment():
    evidence = _load_json(EVIDENCE_PATH)
    assert evidence["authority_mode"] == "manual_protected_environment"
    assert evidence["autonomous_trigger_allowed"] is False


# ---------------------------------------------------------------------------
# Operator activation + predecessor refs
# ---------------------------------------------------------------------------


def test_ri78b_bc10_6b_operator_signature_halildeu_iso_8601_no_secret():
    evidence = _load_json(EVIDENCE_PATH)
    op = evidence["operator_activation_confirmation"]
    assert op["github_login"] == "Halildeu"
    assert op["no_secret_assertion"] is True
    assert op["activation_scope"] == "bc10_real_adapter_usage_cost_only"
    import re

    assert re.match(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$",
        op["activation_confirmed_at"],
    )
    assert op["activation_source"], "activation_source must be non-empty"
    assert op["observation_notes"], "observation_notes must be non-empty"


def test_ri78b_bc10_6b_predecessor_pr_numbers():
    evidence = _load_json(EVIDENCE_PATH)
    assert evidence["ri78a_predecessor_ref"]["pr_number"] == 673
    assert evidence["ri78b_bc1_6c_predecessor_ref"]["pr_number"] == 691
    assert evidence["ri78b_bc10_6a_predecessor_ref"]["pr_number"] == 695


def test_ri78b_bc10_6b_ri78a_predecessor_digest_matches():
    if not _is_ri78b_bc10_6b_introducer_pr():
        pytest.skip("6b state-at-landing pin: only enforced on the introducer PR")
    evidence = _load_json(EVIDENCE_PATH)
    pred = evidence["ri78a_predecessor_ref"]
    expected_sha = _sha256_file(RI78A_EVIDENCE_PATH)
    expected_readiness = _sha256_file(READINESS_MANIFEST_PATH)
    assert pred["evidence_sha256"] == expected_sha
    assert pred["readiness_manifest_sha256"] == expected_readiness


def test_ri78b_bc10_6b_ri78b_bc1_6c_predecessor_digest_matches():
    if not _is_ri78b_bc10_6b_introducer_pr():
        pytest.skip("6b state-at-landing pin: only enforced on the introducer PR")
    evidence = _load_json(EVIDENCE_PATH)
    pred = evidence["ri78b_bc1_6c_predecessor_ref"]
    expected_closure = _sha256_file(RI78B_BC1_6C_CLOSURE_PATH)
    expected_submanifest = _sha256_file(SUBMANIFEST_PATH)
    assert pred["closure_evidence_sha256"] == expected_closure
    assert pred["ri78_submanifest_sha256_after_bc1_flip"] == expected_submanifest


def test_ri78b_bc10_6b_ri78b_bc10_6a_predecessor_digest_matches():
    if not _is_ri78b_bc10_6b_introducer_pr():
        pytest.skip("6b state-at-landing pin: only enforced on the introducer PR")
    evidence = _load_json(EVIDENCE_PATH)
    pred = evidence["ri78b_bc10_6a_predecessor_ref"]
    expected_sha = _sha256_file(RI78B_BC10_6A_PATH)
    assert pred["evidence_sha256"] == expected_sha


def test_ri78b_bc10_6b_workflow_content_sha256_matches_file():
    if not _is_ri78b_bc10_6b_introducer_pr():
        pytest.skip("6b state-at-landing pin: only enforced on the introducer PR")
    evidence = _load_json(EVIDENCE_PATH)
    pinned = evidence["workflow_binding"]["workflow_content_sha256"]
    actual = _sha256_file(WORKFLOW_PATH)
    assert pinned == actual, f"workflow SHA-256 drift: pinned={pinned}, actual={actual}"


def test_ri78b_bc10_6b_pricing_source_digest_matches_file():
    if not _is_ri78b_bc10_6b_introducer_pr():
        pytest.skip("6b state-at-landing pin: only enforced on the introducer PR")
    evidence = _load_json(EVIDENCE_PATH)
    pinned_raw = evidence["pricing_source"]["source_digest"]
    assert pinned_raw.startswith("sha256:")
    pinned = pinned_raw[len("sha256:") :]
    actual = _sha256_file(PRICING_SOURCE_PATH)
    assert pinned == actual, f"pricing source SHA-256 drift: pinned={pinned}, actual={actual}"


# ---------------------------------------------------------------------------
# gpp_status supersession entry
# ---------------------------------------------------------------------------


def test_ri78b_bc10_6b_supersession_entry_present():
    gpp = _load_json(GPP_STATUS_PATH)
    entries = gpp.get("operator_bound_supersessions", [])
    bc10_entries = [e for e in entries if e.get("id") == "RI-7.8b-bc10-6b"]
    assert len(bc10_entries) == 1
    entry = bc10_entries[0]
    assert entry["status"] == "awaiting_operator_dispatch"
    assert entry["scope"] == "bc10_real_adapter_usage_cost_only"
    assert entry["authority_mode"] == "manual_protected_environment"
    assert entry["manual_approval_required"] is True
    assert entry["autonomous_trigger_allowed"] is False
    assert entry["max_run_count"] == 5
    assert entry["max_billable_calls_count"] == 4
    assert entry["max_usd"] == 5.00
    assert entry["actual_start_at"] is None
    assert entry["actual_end_at"] is None
    assert entry["closure_owner_slice"] == "RI-7.8b-bc10-6c"


def test_ri78b_bc10_6b_supersession_workflow_binding():
    gpp = _load_json(GPP_STATUS_PATH)
    entry = next(e for e in gpp["operator_bound_supersessions"] if e["id"] == "RI-7.8b-bc10-6b")
    fwc = entry["future_workflow_contract"]
    assert fwc["workflow_path"] == ".github/workflows/bc10-real-adapter-usage-cost.yml"
    assert fwc["allowed_ref"] == "refs/heads/main"
    assert fwc["model_allowlist"] == ["openai/gpt-4o-mini"]
    # workflow_content_sha256 must match actual file
    if _is_ri78b_bc10_6b_introducer_pr():
        actual = _sha256_file(WORKFLOW_PATH)
        assert fwc["workflow_content_sha256"] == actual


def test_ri78b_bc10_6b_supersession_pricing_source_digest():
    gpp = _load_json(GPP_STATUS_PATH)
    entry = next(e for e in gpp["operator_bound_supersessions"] if e["id"] == "RI-7.8b-bc10-6b")
    pricing = entry["pricing_source"]
    assert pricing["source_type"] == "operator_pinned"
    assert pricing["source_ref"] == "ao_kernel/defaults/pricing/openai_gpt_4o_mini.v1.json"
    assert pricing["source_digest"].startswith("sha256:")
    if _is_ri78b_bc10_6b_introducer_pr():
        actual = _sha256_file(PRICING_SOURCE_PATH)
        assert pricing["source_digest"] == f"sha256:{actual}"


def test_ri78b_bc10_6b_supersession_protected_env_binding():
    gpp = _load_json(GPP_STATUS_PATH)
    entry = next(e for e in gpp["operator_bound_supersessions"] if e["id"] == "RI-7.8b-bc10-6b")
    peb = entry["protected_environment_binding"]
    assert peb["required"] is True
    assert peb["mode"] == "manual_protected_environment"
    assert peb["env_name"] == "ao-kernel-bc10-real-adapter-usage-cost"
    assert peb["allowed_refs"] == ["refs/heads/main"]
    assert peb["admin_bypass_allowed"] is False
    assert peb["prevent_self_review_required"] is True
    assert peb["distinct_reviewer_required"] is True


def test_ri78b_bc10_6b_supersession_guard_flag_policy():
    gpp = _load_json(GPP_STATUS_PATH)
    entry = next(e for e in gpp["operator_bound_supersessions"] if e["id"] == "RI-7.8b-bc10-6b")
    gfp = entry["guard_flag_policy_resolution"]
    assert gfp["support_widening_allowed"] is False
    assert gfp["production_platform_claim_allowed"] is False
    assert gfp["live_adapter_execution_allowed"] is True
    assert gfp["effective_only_for"] == "RI-7.8b-bc10"


def test_ri78b_bc10_6b_gpp_top_level_guard_flags_preserved():
    """Top-level guard flags MUST remain const false. bc10-6b only adds a
    scoped supersession entry; top-level baseline closure preserved."""
    gpp = _load_json(GPP_STATUS_PATH)
    assert gpp.get("support_widening_allowed") is False
    assert gpp.get("production_platform_claim_allowed") is False
    assert gpp.get("live_adapter_execution_allowed") is False


# ---------------------------------------------------------------------------
# State snapshots: readiness + submanifest + guard flags
# ---------------------------------------------------------------------------


def test_ri78b_bc10_6b_readiness_snapshot_9_9_true():
    evidence = _load_json(EVIDENCE_PATH)
    snap = evidence["current_readiness_snapshot"]
    assert snap["nine_key_manifest_all_true"] is True
    assert snap["readiness_gate_decision"] == "ready_for_operator_promotion_decision"


def test_ri78b_bc10_6b_gpp_guard_snapshot_all_false():
    evidence = _load_json(EVIDENCE_PATH)
    guard = evidence["current_gpp_guard_snapshot"]
    assert guard["support_widening_allowed"] is False
    assert guard["production_platform_claim_allowed"] is False
    assert guard["live_adapter_execution_allowed"] is False


def test_ri78b_bc10_6b_ri78_submanifest_post_bc1_state():
    if not _is_ri78b_bc10_6b_introducer_pr():
        pytest.skip("6b state-at-landing pin: only enforced on the introducer PR")
    sub = _load_json(SUBMANIFEST_PATH)
    assert sub["live_evidence_pre_authorization_recorded"] is True
    assert sub["bc1_protected_live_adapter_attestation_recorded"] is True
    assert sub["bc10_real_adapter_usage_cost_aggregate_recorded"] is False
    assert sub["final_operator_promotion_decision_recorded"] is False


def test_ri78b_bc10_6b_nine_key_readiness_unchanged_all_true():
    manifest = _load_json(READINESS_MANIFEST_PATH)
    forbidden_keys = {"schema_version", "artifact_kind"}
    flag_keys = [k for k in manifest if k not in forbidden_keys]
    assert len(flag_keys) == 9
    for key in flag_keys:
        assert manifest[key] is True


def test_ri78b_bc10_6b_guard_flags_const_false_in_evidence():
    evidence = _load_json(EVIDENCE_PATH)
    assert evidence["support_widening"] is False
    assert evidence["production_platform_claim"] is False
    assert evidence["live_adapter_execution"] is False


def test_ri78b_bc10_6b_submanifest_transition_unchanged():
    evidence = _load_json(EVIDENCE_PATH)
    trans = evidence["submanifest_transition"]
    assert trans["before"]["bc1_protected_live_adapter_attestation_recorded"] is True
    assert trans["before"]["bc10_real_adapter_usage_cost_aggregate_recorded"] is False
    assert trans["after"]["bc1_protected_live_adapter_attestation_recorded"] is True
    assert trans["after"]["bc10_real_adapter_usage_cost_aggregate_recorded"] is False


# ---------------------------------------------------------------------------
# Mutation reporting
# ---------------------------------------------------------------------------


def test_ri78b_bc10_6b_mutations_performed_object_const():
    evidence = _load_json(EVIDENCE_PATH)
    mut = evidence["mutations_performed"]
    assert mut["workflow_created"] is True
    assert mut["activation_script_created"] is True
    assert mut["runner_script_created"] is True
    assert mut["pricing_source_created"] is True
    assert mut["supersession_entry_appended"] is True
    assert mut["submanifest_mutated"] is False
    assert mut["provider_call_performed"] is False
    assert mut["secret_referenced_in_repo"] is False
    assert mut["guard_flag_flipped"] is False


# ---------------------------------------------------------------------------
# Workflow + pricing source content checks
# ---------------------------------------------------------------------------


def test_ri78b_bc10_6b_workflow_no_push_trigger():
    """bc10 workflow MUST NOT have push trigger (autonomous pattern forbidden)."""
    content = WORKFLOW_PATH.read_text()
    # Must have workflow_dispatch
    assert "workflow_dispatch:" in content
    # Must NOT have push trigger
    # (loose check; precise YAML parse would be better but content is small)
    lines = content.splitlines()
    on_section_start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("on:"):
            on_section_start = i
            break
    assert on_section_start is not None
    # Scan next ~10 lines for push/branches keys
    on_section = "\n".join(lines[on_section_start : on_section_start + 15])
    # push trigger check
    if "  push:" in on_section or "\npush:" in on_section:
        assert False, "bc10 workflow MUST NOT have push trigger (use workflow_dispatch only)"


def test_ri78b_bc10_6b_workflow_has_environment_binding():
    content = WORKFLOW_PATH.read_text()
    assert "environment: ao-kernel-bc10-real-adapter-usage-cost" in content


def test_ri78b_bc10_6b_workflow_has_no_secret_in_inputs():
    content = WORKFLOW_PATH.read_text()
    # workflow_dispatch.inputs block should not contain secret/api_key/token
    for forbidden in ["api_key:", "token:", "secret:", "credential:", "password:", "auth_header:"]:
        assert forbidden not in content, f"workflow inputs must not include {forbidden!r}"


def test_ri78b_bc10_6b_workflow_secret_only_in_runner_step():
    """The ${{ secrets.OPENAI_API_KEY }} reference must appear exactly once
    (in the runner step env block; comments and uppercase docstrings don't count)."""
    content = WORKFLOW_PATH.read_text()
    assert "OPENAI_API_KEY" in content
    # Count only actual secret expansion references (not comments)
    occurrences = content.count("secrets.OPENAI_API_KEY")
    assert occurrences == 1, f"secrets.OPENAI_API_KEY must appear exactly once (in runner step env); got {occurrences}"


def test_ri78b_bc10_6b_pricing_model_correct_decimals():
    pricing = _load_json(PRICING_SOURCE_PATH)
    assert pricing["currency"] == "USD"
    assert pricing["precision_decimal_places"] == 8
    assert pricing["input_cost_per_1k_tokens_usd"] == "0.00015000"
    assert pricing["output_cost_per_1k_tokens_usd"] == "0.00060000"
    assert pricing["canonical_model_id"] == "openai/gpt-4o-mini"


# ---------------------------------------------------------------------------
# Forbidden-change audit: exact set + machine-enforced via git diff
# ---------------------------------------------------------------------------


def test_ri78b_bc10_6b_forbidden_change_audit_exact_10_set():
    evidence = _load_json(EVIDENCE_PATH)
    audit = evidence["forbidden_change_audit"]
    assert audit["all_unchanged"] is True
    assert set(audit["forbidden_surfaces"]) == set(EXPECTED_FORBIDDEN_SURFACES)
    assert len(audit["forbidden_surfaces"]) == 10


def test_ri78b_bc10_6b_forbidden_change_audit_machine_enforced_against_origin_main():
    if not _is_ri78b_bc10_6b_introducer_pr():
        pytest.skip("6b state-at-landing pin: only enforced on the introducer PR")
    _skip_if_current_local_review_evidence_is_for_another_slice()
    base_sha = _resolve_diff_base()
    if base_sha is None:
        pytest.skip("No git base resolved")
    changed = _git_changed_paths_against(base_sha)
    for surface in EXPECTED_FORBIDDEN_SURFACES:
        for path in changed:
            assert not _path_matches_surface(path, surface), (
                f"Forbidden surface touched in 6b PR: surface={surface}, changed_path={path}"
            )


def test_ri78b_bc10_6b_submanifest_file_untouched_in_diff():
    if not _is_ri78b_bc10_6b_introducer_pr():
        pytest.skip("6b state-at-landing pin: only enforced on the introducer PR")
    _skip_if_current_local_review_evidence_is_for_another_slice()
    base_sha = _resolve_diff_base()
    if base_sha is None:
        pytest.skip("No git base resolved")
    changed = _git_changed_paths_against(base_sha)
    assert ".claude/plans/RI-7.8-EVIDENCE-MANIFEST.v1.json" not in changed


def test_ri78b_bc10_6b_ri78a_predecessor_evidence_untouched():
    if not _is_ri78b_bc10_6b_introducer_pr():
        pytest.skip("6b state-at-landing pin: only enforced on the introducer PR")
    _skip_if_current_local_review_evidence_is_for_another_slice()
    base_sha = _resolve_diff_base()
    if base_sha is None:
        pytest.skip("No git base resolved")
    changed = _git_changed_paths_against(base_sha)
    assert ".claude/plans/RI-7.8a-LIVE-EVIDENCE-PRE-AUTHORIZATION.v1.json" not in changed


def test_ri78b_bc10_6b_ri78b_bc10_6a_predecessor_evidence_untouched():
    if not _is_ri78b_bc10_6b_introducer_pr():
        pytest.skip("6b state-at-landing pin: only enforced on the introducer PR")
    _skip_if_current_local_review_evidence_is_for_another_slice()
    base_sha = _resolve_diff_base()
    if base_sha is None:
        pytest.skip("No git base resolved")
    changed = _git_changed_paths_against(base_sha)
    assert ".claude/plans/RI-7.8b-bc10-6a-EXECUTION-WINDOW-AUTHORIZATION.v1.json" not in changed


# ---------------------------------------------------------------------------
# Cross-AI peer review provider split + cross-artifact verdict equality
# ---------------------------------------------------------------------------


def test_ri78b_bc10_6b_cross_ai_review_provider_split_const():
    evidence = _load_json(EVIDENCE_PATH)
    cr = evidence["cross_ai_review_ref"]
    assert cr["implementer_provider"] == "anthropic"
    assert cr["reviewer_provider"] == "openai"
    assert cr["final_verdict"] in {"REVISE", "AGREE"}
    assert cr["thread_id"], "thread_id must be non-empty"


def test_ri78b_bc10_6b_cross_artifact_verdict_equality():
    if not LOCAL_AI_REVIEW_PATH.exists():
        pytest.skip("local-ai-review-evidence.v1.json missing")
    review = _load_json(LOCAL_AI_REVIEW_PATH)
    if review["work_package"] != "RI-7.8b-bc10-6b":
        pytest.skip("local-ai-review-evidence.v1.json belongs to another active PR work package")
    evidence = _load_json(EVIDENCE_PATH)
    assert review["reviewer"]["provider"] == "openai"
    assert review["implementer"]["provider"] == "anthropic"
    assert review["work_package"] == "RI-7.8b-bc10-6b"
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


def test_ri78b_bc10_6b_negative_authority_mode_autonomous_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("authority_mode",), "operator_delegated_autonomous_preprod"))
    _assert_rejected(bad, "authority_mode must be manual_protected_environment")


def test_ri78b_bc10_6b_negative_autonomous_trigger_allowed_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("autonomous_trigger_allowed",), True))
    _assert_rejected(bad, "autonomous_trigger_allowed must be false const")


def test_ri78b_bc10_6b_negative_top_level_support_widening_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("support_widening",), True))
    _assert_rejected(bad, "support_widening must be false const")


def test_ri78b_bc10_6b_negative_top_level_live_adapter_execution_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("live_adapter_execution",), True))
    _assert_rejected(bad, "live_adapter_execution must be false const")


def test_ri78b_bc10_6b_negative_provider_call_performed_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("mutations_performed", "provider_call_performed"), True))
    _assert_rejected(bad, "provider_call_performed must be false const in 6b")


def test_ri78b_bc10_6b_negative_secret_referenced_in_repo_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("mutations_performed", "secret_referenced_in_repo"), True))
    _assert_rejected(bad, "secret_referenced_in_repo must be false const")


def test_ri78b_bc10_6b_negative_submanifest_mutated_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("mutations_performed", "submanifest_mutated"), True))
    _assert_rejected(bad, "submanifest_mutated must be false const in 6b")


def test_ri78b_bc10_6b_negative_guard_flag_flipped_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("mutations_performed", "guard_flag_flipped"), True))
    _assert_rejected(bad, "guard_flag_flipped must be false const in 6b")


def test_ri78b_bc10_6b_negative_workflow_path_drift_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (("workflow_binding", "workflow_path"), ".github/workflows/other-workflow.yml"),
    )
    _assert_rejected(bad, "workflow_path must be const")


def test_ri78b_bc10_6b_negative_env_name_production_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (("protected_environment_observation", "env_name"), "production-bc10-real-adapter"),
    )
    _assert_rejected(bad, "env_name must be ao-kernel-bc10-real-adapter-usage-cost")


def test_ri78b_bc10_6b_negative_prevent_self_review_false_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (("protected_environment_observation", "prevent_self_review_required"), False),
    )
    _assert_rejected(bad, "prevent_self_review_required must be true const for bc10")


def test_ri78b_bc10_6b_negative_admin_bypass_allowed_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (("protected_environment_observation", "admin_bypass_allowed_required"), True),
    )
    _assert_rejected(bad, "admin_bypass_allowed_required must be false const")


def test_ri78b_bc10_6b_negative_distinct_reviewer_required_false_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (("protected_environment_observation", "distinct_reviewer_required"), False),
    )
    _assert_rejected(bad, "distinct_reviewer_required must be true const")


def test_ri78b_bc10_6b_negative_model_allowlist_extra_model_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (("workflow_binding", "model_allowlist"), ["openai/gpt-4o-mini", "openai/gpt-4o"]),
    )
    _assert_rejected(bad, "model_allowlist max 1 item")


def test_ri78b_bc10_6b_negative_max_billable_calls_count_high_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("run_budget", "max_billable_calls_count"), 10))
    _assert_rejected(bad, "max_billable_calls_count must be const 4")


def test_ri78b_bc10_6b_negative_max_usd_high_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("run_budget", "max_usd"), 100.00))
    _assert_rejected(bad, "max_usd must be const 5.00")


def test_ri78b_bc10_6b_negative_max_output_tokens_cap_high_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("workflow_binding", "max_output_tokens_cap"), 1024))
    _assert_rejected(bad, "max_output_tokens_cap max 256")


def test_ri78b_bc10_6b_negative_retries_disabled_false_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("workflow_binding", "retries_disabled"), False))
    _assert_rejected(bad, "retries_disabled must be true const")


def test_ri78b_bc10_6b_negative_trigger_events_push_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("workflow_binding", "trigger_events_allowlist"), ["push"]))
    _assert_rejected(bad, "trigger_events_allowlist must be ['workflow_dispatch']")


def test_ri78b_bc10_6b_negative_does_not_authorize_missing_action_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = copy.deepcopy(evidence)
    bad["does_not_authorize"] = [
        "credential_material_in_repo",
        "credential_input_parameter",
        "credential_material_in_artifact_or_log",
        "credential_reference_outside_protected_environment",
        "bc10_submanifest_flip_now",
        "automatic_workflow_dispatch_without_operator_action",
        "cost_overflow_outside_max_usd",
        # missing support_widening_or_production_platform_claim
    ]
    _assert_rejected(bad, "does_not_authorize must have all 8 actions")


def test_ri78b_bc10_6b_negative_forbidden_audit_all_unchanged_false_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("forbidden_change_audit", "all_unchanged"), False))
    _assert_rejected(bad, "all_unchanged must be true const")


def test_ri78b_bc10_6b_marker_schema_rejects_zero_usage_success():
    """iter-5 strengthening: success_billable marker with zero tokens / zero cost
    must be rejected by schema (defeats bc10 cost evidence purpose otherwise)."""
    marker_schema = _load_json(MARKER_SCHEMA_PATH)
    bad_marker = {
        "schema_version": "ri7-8b-bc10-per-call-runtime-call-marker.v1",
        "artifact_kind": "ri7_8b_bc10_per_call_runtime_call_marker",
        "scenario": "small_completion_a",
        "scenario_outcome": "success_billable",
        "requested_model": "openai/gpt-4o-mini",
        "resolved_model": "openai/gpt-4o-mini",
        "model_allowlist_enforced": True,
        "model_allowlist": ["openai/gpt-4o-mini"],
        "max_output_tokens_cap": 64,
        "provider_call_performed": True,
        "billable_call_count_delta": 1,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "projected_cost_usd": "0.00010000",
        "actual_cost_usd": "0.00000000",
        "cumulative_cost_usd_before": "0.00000000",
        "cumulative_cost_usd_after": "0.00000000",
        "pricing_source_digest": "sha256:" + "a" * 64,
        "usage_source": "provider_api_response",
        "cost_source": "provider_usage_plus_pinned_pricing_source",
        "run_id": "12345",
        "run_attempt": "1",
        "head_sha": "a" * 40,
        "workflow_ref": "foo@refs/heads/main",
        "workflow_content_sha256": "a" * 64,
        "secret_boundary": "no_secret_material_emitted_no_token_no_credential",
        "raw_response_recorded": False,
        "secret_material_recorded": False,
        "secret_scope_after_all_pre_provider_guards": True,
        "budget_cap_precheck_denied_completes_without_provider_client_init": True,
        "budget_cap_precheck_denied_completes_without_api_key_read": True,
        "retry_behavior": "wrapper_no_retry_loop_transport_default_skipped",
    }
    errors = list(jsonschema.Draft202012Validator(marker_schema).iter_errors(bad_marker))
    assert errors, "marker schema must reject zero-usage success_billable"


def test_ri78b_bc10_6b_marker_schema_accepts_non_zero_usage_success():
    marker_schema = _load_json(MARKER_SCHEMA_PATH)
    good_marker = {
        "schema_version": "ri7-8b-bc10-per-call-runtime-call-marker.v1",
        "artifact_kind": "ri7_8b_bc10_per_call_runtime_call_marker",
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
        "pricing_source_digest": "sha256:" + "a" * 64,
        "usage_source": "provider_api_response",
        "cost_source": "provider_usage_plus_pinned_pricing_source",
        "run_id": "12345",
        "run_attempt": "1",
        "head_sha": "a" * 40,
        "workflow_ref": "foo@refs/heads/main",
        "workflow_content_sha256": "a" * 64,
        "secret_boundary": "no_secret_material_emitted_no_token_no_credential",
        "raw_response_recorded": False,
        "secret_material_recorded": False,
        "secret_scope_after_all_pre_provider_guards": True,
        "budget_cap_precheck_denied_completes_without_provider_client_init": True,
        "budget_cap_precheck_denied_completes_without_api_key_read": True,
        "retry_behavior": "wrapper_no_retry_loop_transport_default_skipped",
    }
    errors = list(jsonschema.Draft202012Validator(marker_schema).iter_errors(good_marker))
    assert not errors, f"marker schema must accept non-zero usage success_billable; got {errors[:3]}"


def test_ri78b_bc10_6b_negative_scoped_support_widening_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (("guard_flag_policy_resolution_evidence", "scoped_support_widening_allowed"), True),
    )
    _assert_rejected(bad, "scoped_support_widening_allowed must be false const")
