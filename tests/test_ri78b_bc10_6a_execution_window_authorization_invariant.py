"""Invariant tests for RI-7.8b-bc10-6a execution-window authorization slice.

This test suite enforces:

- Schema strictness (Draft 2020-12, additionalProperties=false, const pins, exact-set forbidden audit)
- Evidence validates against schema
- Operator signature: Halildeu + ISO 8601 UTC + no-secret-assertion + 9-signal contract
- Negative schema tests: guard flag true / authorization_effect drift / window_status drift /
  actual_start_at non-null / observed=true / submanifest after.bc10=true → rejected
- RI-7.8a predecessor evidence digests pin predecessor state
- RI-7.8b-bc1-6c predecessor closure digests pin BC-1 landing state
- RI-7.8 submanifest at predecessor state (bc1=true post-#691, bc10=false, final=false)
- 9-key readiness manifest UNCHANGED at 9/9 true
- gpp_status.v1.json UNCHANGED in 6a (supersession entry append belongs to 6b)
- forbidden_change_audit exact set (17 surfaces) + machine-enforced via git diff vs origin/main
- expected_dispatch_inputs_allowlist ∩ expected_forbidden_inputs == ∅
- future workflow file does NOT exist in 6a PR
- model_allowlist pinned to ["openai/gpt-4o-mini"] (matches RI-7.8a envelope)
- planned_6b_authority_mode pinned to manual_protected_environment (not autonomous)
- mutations_performed all-false invariant
- cross-AI peer review provider split const (anthropic implementer, openai reviewer)
- cross-artifact verdict equality (evidence cross_ai_review_ref.final_verdict ==
  local-ai-review-evidence.reviewer.verdict)
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

SCHEMA_PATH = (
    REPO_ROOT
    / "ao_kernel"
    / "defaults"
    / "schemas"
    / "ri7-8b-bc10-6a-execution-window-authorization-evidence.schema.v1.json"
)
EVIDENCE_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8b-bc10-6a-EXECUTION-WINDOW-AUTHORIZATION.v1.json"
SUBMANIFEST_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8-EVIDENCE-MANIFEST.v1.json"
READINESS_MANIFEST_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7-EVIDENCE-MANIFEST.v1.json"
RI78A_EVIDENCE_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8a-LIVE-EVIDENCE-PRE-AUTHORIZATION.v1.json"
RI78B_BC1_6C_CLOSURE_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8b-bc1-6c-CLOSURE.v1.json"
GPP_STATUS_PATH = REPO_ROOT / ".claude" / "plans" / "gpp_status.v1.json"
LOCAL_AI_REVIEW_PATH = REPO_ROOT / "local-ai-review-evidence.v1.json"
FUTURE_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "bc10-real-adapter-usage-cost.yml"

EXPECTED_FORBIDDEN_SURFACES = [
    ".claude/plans/gpp_status.v1.json",
    "scripts/gp5_platform_claim_decision.py",
    ".github/workflows/",
    ".github/workflows/bc10-real-adapter-usage-cost.yml",
    "ao_kernel/mcp_server.py",
    "ao_kernel/__init__.py",
    "ao_kernel/defaults/policies/",
    "docs/PUBLIC-BETA.md",
    "docs/SUPPORT-BOUNDARY.md",
    "docs/KNOWN-BUGS.md",
    "ao_kernel/defaults/schemas/local-gpp-gate-evidence.schema.v1.json",
    "ao_kernel/ao_release_gate.py",
    "scripts/local_gpp_gate.py",
    "scripts/repo_intelligence_tier_promotion_readiness.py",
    ".claude/plans/RI-7-EVIDENCE-MANIFEST.v1.json",
    ".claude/plans/RI-7.8a-LIVE-EVIDENCE-PRE-AUTHORIZATION.v1.json",
    ".claude/plans/RI-7.8-EVIDENCE-MANIFEST.v1.json",
]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_diff_base() -> str | None:
    """Best-effort diff base resolution against origin/main."""
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


def _is_ri78b_bc10_6a_introducer_pr() -> bool:
    """Returns True if THIS PR is the slice that introduces the bc10-6a evidence
    artifact (i.e. the artifact is newly ADDED in the diff against origin/main).

    Git-diff-dependent invariants (forbidden_change_audit machine enforcement,
    future-workflow-absent, predecessor evidence untouched, submanifest
    untouched in diff) must only run on the introducer PR. On successor PRs
    (RI-7.8b-bc10-6b, RI-7.8b-bc10-6c, etc.) the diff scope intentionally
    includes new workflows + gpp_status mutations + submanifest flips, which
    would fail the 6a-state-at-landing pin if it were re-evaluated against
    the new diff.
    """
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
    if review.get("work_package") != "RI-7.8b-bc10-6a":
        pytest.skip("local-ai-review-evidence.v1.json belongs to another active PR work package")


def _path_matches_surface(path: str, surface: str) -> bool:
    if surface.endswith("/"):
        return path.startswith(surface)
    return path == surface


# ---------------------------------------------------------------------------
# Schema / evidence structural invariants
# ---------------------------------------------------------------------------


def test_ri78b_bc10_6a_schema_path_exists():
    assert SCHEMA_PATH.exists(), f"Schema missing: {SCHEMA_PATH}"


def test_ri78b_bc10_6a_evidence_path_exists():
    assert EVIDENCE_PATH.exists(), f"Evidence missing: {EVIDENCE_PATH}"


def test_ri78b_bc10_6a_schema_is_draft_2020_12():
    schema = _load_json(SCHEMA_PATH)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    jsonschema.Draft202012Validator.check_schema(schema)


def test_ri78b_bc10_6a_evidence_validates_against_schema():
    schema = _load_json(SCHEMA_PATH)
    evidence = _load_json(EVIDENCE_PATH)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(evidence), key=lambda e: list(e.absolute_path))
    assert not errors, "Evidence does not validate: " + "; ".join(
        f"{list(e.absolute_path)}: {e.message}" for e in errors
    )


def test_ri78b_bc10_6a_decision_const():
    evidence = _load_json(EVIDENCE_PATH)
    assert evidence["decision"] == "ri78b_bc10_6a_execution_window_authorization_contract_no_execution_no_flip"


def test_ri78b_bc10_6a_authorization_effect_const():
    evidence = _load_json(EVIDENCE_PATH)
    assert (
        evidence["authorization_effect"]
        == "execution_window_authorization_recorded_no_execution_no_guard_flag_flip_no_billable_call_no_secret_reference"
    )


def test_ri78b_bc10_6a_does_not_authorize_9_enum():
    evidence = _load_json(EVIDENCE_PATH)
    expected = {
        "workflow_dispatch_now",
        "adapter_execution_now",
        "credential_reference",
        "billable_provider_call_now",
        "cost_incurring_calls_now",
        "support_widening",
        "production_platform_claim",
        "gpp_status_guard_flip",
        "submanifest_bc10_flip",
    }
    assert set(evidence["does_not_authorize"]) == expected
    assert len(evidence["does_not_authorize"]) == 9


# ---------------------------------------------------------------------------
# Operator authority + predecessor refs + window contract
# ---------------------------------------------------------------------------


def test_ri78b_bc10_6a_operator_signature_halildeu_iso_8601_no_secret():
    evidence = _load_json(EVIDENCE_PATH)
    op = evidence["operator_authorization_record"]
    assert op["github_login"] == "Halildeu"
    assert op["no_secret_assertion"] is True
    assert op["authorization_scope"] == "bc10_6a_execution_window_contract_only"
    assert op["does_not_authorize_immediate_execution"] is True
    import re

    assert re.match(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$",
        op["authorization_recorded_at"],
    ), op["authorization_recorded_at"]
    assert op["authorization_source"], "authorization_source must be non-empty"
    assert op["observation_notes"], "observation_notes must be non-empty"


def test_ri78b_bc10_6a_ri78a_predecessor_digest_matches_predecessor_state():
    if not _is_ri78b_bc10_6a_introducer_pr():
        pytest.skip("6a state-at-landing pin: only enforced on the introducer PR")
    evidence = _load_json(EVIDENCE_PATH)
    pred = evidence["ri78a_predecessor_ref"]
    assert pred["pr_number"] == 673
    expected_ri78a_sha = _sha256_file(RI78A_EVIDENCE_PATH)
    expected_readiness_sha = _sha256_file(READINESS_MANIFEST_PATH)
    assert pred["ri78a_evidence_sha256"] == expected_ri78a_sha
    assert pred["readiness_manifest_sha256"] == expected_readiness_sha


def test_ri78b_bc10_6a_ri78b_bc1_6c_predecessor_digest_matches_predecessor_state():
    if not _is_ri78b_bc10_6a_introducer_pr():
        pytest.skip("6a state-at-landing pin: only enforced on the introducer PR")
    evidence = _load_json(EVIDENCE_PATH)
    pred = evidence["ri78b_bc1_6c_predecessor_ref"]
    assert pred["pr_number"] == 691
    expected_closure_sha = _sha256_file(RI78B_BC1_6C_CLOSURE_PATH)
    expected_submanifest_sha = _sha256_file(SUBMANIFEST_PATH)
    assert pred["closure_evidence_sha256"] == expected_closure_sha
    assert pred["ri78_submanifest_sha256_after_bc1_flip"] == expected_submanifest_sha


def test_ri78b_bc10_6a_stale_replay_guard_digests_match():
    if not _is_ri78b_bc10_6a_introducer_pr():
        pytest.skip("6a state-at-landing pin: only enforced on the introducer PR")
    evidence = _load_json(EVIDENCE_PATH)
    guard = evidence["stale_replay_guard"]
    assert guard["base_ref"] == "refs/heads/main"
    assert guard["head_ref"] == "refs/heads/codex/ri-7-8b-bc10-6a-execution-window-authorization"
    expected_ri78a_sha = _sha256_file(RI78A_EVIDENCE_PATH)
    expected_closure_sha = _sha256_file(RI78B_BC1_6C_CLOSURE_PATH)
    expected_submanifest_sha = _sha256_file(SUBMANIFEST_PATH)
    expected_readiness_sha = _sha256_file(READINESS_MANIFEST_PATH)
    assert guard["ri78a_evidence_sha256"] == expected_ri78a_sha
    assert guard["ri78b_bc1_6c_closure_evidence_sha256"] == expected_closure_sha
    assert guard["ri78_submanifest_sha256_after_bc1_flip"] == expected_submanifest_sha
    assert guard["readiness_manifest_sha256"] == expected_readiness_sha


def test_ri78b_bc10_6a_window_status_const_authorized_pending_6b_activation():
    evidence = _load_json(EVIDENCE_PATH)
    win = evidence["authorization_window_contract"]
    assert win["window_status"] == "authorized_pending_6b_activation"
    assert win["actual_start_at"] is None
    assert win["actual_end_at"] is None
    assert win["activation_owner_slice"] == "RI-7.8b-bc10-6b"
    assert win["contract_status"] == "expected_unresolved_until_6b"
    assert 1 <= win["max_run_count"] <= 5
    assert 1 <= win["max_billable_calls_count"] <= 4
    assert 0 < win["max_usd"] <= 5.0
    assert 1 <= win["max_activation_delay_hours"] <= 168
    assert 1 <= win["max_execution_window_duration_hours"] <= 24


# ---------------------------------------------------------------------------
# bc10-specific: planned_6b_authority_mode + mutations_performed
# ---------------------------------------------------------------------------


def test_ri78b_bc10_6a_planned_6b_authority_mode_manual_protected_environment():
    """bc10 6b MUST use manual_protected_environment (not autonomous).

    BC-1 6c used autonomous pre-prod pattern (operator-delegated). bc10
    involves REAL billable provider calls, so manual operator confirmation
    via GitHub Environment required reviewers is required at activation time.
    """
    evidence = _load_json(EVIDENCE_PATH)
    auth = evidence["planned_6b_authority_mode"]
    assert auth["authority_mode"] == "manual_protected_environment"
    assert auth["manual_approval_required"] is True
    assert auth["autonomous_trigger_allowed"] is False
    assert auth["rationale"], "rationale must be non-empty"


def test_ri78b_bc10_6a_mutations_performed_all_false():
    """bc10-6a MUST NOT perform any mutation. 7-key all-false invariant."""
    evidence = _load_json(EVIDENCE_PATH)
    mut = evidence["mutations_performed"]
    assert mut["runtime_modified"] is False
    assert mut["workflow_created"] is False
    assert mut["submanifest_mutated"] is False
    assert mut["gpp_status_mutated"] is False
    assert mut["provider_call_performed"] is False
    assert mut["secret_referenced"] is False
    assert mut["guard_flag_flipped"] is False


# ---------------------------------------------------------------------------
# Time-window audit binding
# ---------------------------------------------------------------------------


def _parse_iso_z(s: str) -> datetime:
    if s.endswith("Z"):
        return datetime.fromisoformat(s[:-1] + "+00:00")
    return datetime.fromisoformat(s)


def test_ri78b_bc10_6a_authorization_recorded_at_not_in_future():
    evidence = _load_json(EVIDENCE_PATH)
    op = evidence["operator_authorization_record"]
    recorded_at = _parse_iso_z(op["authorization_recorded_at"])
    now = datetime.now(timezone.utc)
    tolerance = timedelta(minutes=15)
    assert recorded_at <= now + tolerance, (
        f"authorization_recorded_at={recorded_at.isoformat()} is in the future "
        f"relative to now={now.isoformat()} (tolerance=15min)."
    )


def test_ri78b_bc10_6a_validity_window_bounded_by_max_activation_delay():
    evidence = _load_json(EVIDENCE_PATH)
    op = evidence["operator_authorization_record"]
    win = evidence["authorization_window_contract"]
    recorded_at = _parse_iso_z(op["authorization_recorded_at"])
    valid_until = _parse_iso_z(win["authorization_valid_until"])
    assert valid_until > recorded_at
    delta = valid_until - recorded_at
    max_hours = win["max_activation_delay_hours"]
    max_delta = timedelta(hours=max_hours)
    assert delta <= max_delta, (
        f"(valid_until - recorded_at)={delta} exceeds max_activation_delay_hours={max_hours} ({max_delta})"
    )


def test_ri78b_bc10_6a_authorization_source_is_auditable_reference():
    evidence = _load_json(EVIDENCE_PATH)
    source = evidence["operator_authorization_record"]["authorization_source"]
    auditable_markers = (
        "pull/",
        "pulls/",
        "issues/",
        "issue/",
        "commit/",
        "pr/",
        "/pull/",
        "github.com",
        "PR #",
    )
    assert any(marker.lower() in source.lower() for marker in auditable_markers), (
        f"authorization_source={source!r} must include an auditable reference marker"
    )


def test_ri78b_bc10_6a_protected_env_name_bc10_specific_not_production():
    evidence = _load_json(EVIDENCE_PATH)
    env = evidence["protected_environment_binding"]
    assert env["env_name"] == "ao-kernel-bc10-real-adapter-usage-cost"
    assert not env["env_name"].startswith("production")
    assert "production" not in env["env_name"].split("-")
    assert "bc10" in env["env_name"]
    assert env["observed"] is False
    assert env["observed_at"] is None
    assert env["observation_source"] is None
    assert env["observed_environment_sha256"] is None
    assert env["observation_owner_slice"] == "RI-7.8b-bc10-6b"
    assert env["required_reviewers_expected"] is True
    assert env["prevent_self_review_expected"] is True
    assert env["allowed_refs_expected"] == ["refs/heads/main"]
    assert env["admin_bypass_allowed_expected"] is False


def test_ri78b_bc10_6a_future_workflow_contract_pinned_bc10_specific():
    evidence = _load_json(EVIDENCE_PATH)
    wf = evidence["future_workflow_contract"]
    assert wf["workflow_path"] == ".github/workflows/bc10-real-adapter-usage-cost.yml"
    assert wf["expected_absent_or_not_touched_in_6a"] is True
    assert wf["creation_owner_slice"] == "RI-7.8b-bc10-6b"
    assert wf["workflow_sha"] is None
    assert wf["workflow_content_sha256"] is None
    assert wf["allowed_ref"] == "refs/heads/main"
    assert wf["contract_status"] == "expected_unresolved_until_6b"
    assert wf["expected_retries_disabled"] is True
    assert wf["expected_pre_call_cost_check"] is True
    assert wf["expected_post_call_cost_check"] is True
    assert 1 <= wf["expected_max_output_tokens_cap"] <= 256
    allowlist = set(wf["expected_dispatch_inputs_allowlist"])
    forbidden = set(wf["expected_forbidden_inputs"])
    assert allowlist, "allowlist must be non-empty"
    assert allowlist & forbidden == set(), "allowlist ∩ forbidden must be empty"


def test_ri78b_bc10_6a_model_allowlist_pinned_to_low_cost_only():
    evidence = _load_json(EVIDENCE_PATH)
    models = evidence["future_workflow_contract"]["model_allowlist"]
    assert models == ["openai/gpt-4o-mini"]
    assert len(models) == 1


def test_ri78b_bc10_6a_future_workflow_file_absent_in_repo():
    if not _is_ri78b_bc10_6a_introducer_pr():
        pytest.skip("6a state-at-landing pin: only enforced on the introducer PR")
    assert not FUTURE_WORKFLOW_PATH.exists(), f"6a must not create the future bc10 workflow: {FUTURE_WORKFLOW_PATH}"


def test_ri78b_bc10_6a_closure_clauses_const():
    evidence = _load_json(EVIDENCE_PATH)
    clause = evidence["closure_expiry_and_revocation_clause"]
    assert (
        clause["authorization_expiry_action"]
        == "authorization_auto_invalidates_if_not_activated_by_6b_within_validity_window"
    )
    assert (
        clause["window_end_action"]
        == "live_adapter_execution_must_remain_false_outside_window_and_bc10_submanifest_must_remain_false_until_6c_flip"
    )
    assert clause["post_window_verifier_owner"] == "RI-7.8b-bc10-6c"
    assert clause["revocation_action"] == "operator_may_revoke_before_6b_activation_via_new_pr_or_supersession_entry"
    assert clause["rerun_policy"] == "expired_or_exceeded_runs_are_fail_closed_no_silent_retry"
    assert clause["cost_cap_breach_action"] == "fail_closed_window_terminates_no_silent_continuation"


def test_ri78b_bc10_6a_activation_requirements_all_true():
    evidence = _load_json(EVIDENCE_PATH)
    act = evidence["activation_requirements"]
    assert act["activation_requires_new_operator_confirmation"] is True
    assert act["activation_requires_workflow_sha_binding"] is True
    assert act["activation_requires_workflow_content_sha256_binding"] is True
    assert act["activation_requires_protected_environment_observation"] is True
    assert act["activation_requires_guard_flag_policy_resolution"] is True
    assert act["activation_requires_manual_approval_review"] is True
    assert act["activation_requires_model_allowlist_enforcement"] is True


# ---------------------------------------------------------------------------
# State snapshots: 9/9 readiness + GPP guard + RI-7.8 submanifest post-BC-1
# ---------------------------------------------------------------------------


def test_ri78b_bc10_6a_readiness_snapshot_9_9_true():
    evidence = _load_json(EVIDENCE_PATH)
    snap = evidence["current_readiness_snapshot"]
    assert snap["nine_key_manifest_all_true"] is True
    assert snap["readiness_gate_decision"] == "ready_for_operator_promotion_decision"
    assert snap["operator_verified_runtime_semantics"] is True
    assert snap["explicit_operator_authorization"] is True
    assert snap["general_purpose_platform_claim_authorization"] is True


def test_ri78b_bc10_6a_gpp_guard_snapshot_all_false():
    evidence = _load_json(EVIDENCE_PATH)
    guard = evidence["current_gpp_guard_snapshot"]
    assert guard["support_widening_allowed"] is False
    assert guard["production_platform_claim_allowed"] is False
    assert guard["live_adapter_execution_allowed"] is False


def test_ri78b_bc10_6a_ri78_submanifest_post_bc1_state():
    """bc10-6a snapshot MUST reflect post-#691 state: bc1=true, bc10=false."""
    if not _is_ri78b_bc10_6a_introducer_pr():
        pytest.skip("6a state-at-landing pin: only enforced on the introducer PR")
    sub = _load_json(SUBMANIFEST_PATH)
    assert sub["live_evidence_pre_authorization_recorded"] is True
    assert sub["bc1_protected_live_adapter_attestation_recorded"] is True
    assert sub["bc10_real_adapter_usage_cost_aggregate_recorded"] is False
    assert sub["final_operator_promotion_decision_recorded"] is False
    evidence = _load_json(EVIDENCE_PATH)
    snap = evidence["ri78_submanifest_snapshot"]
    state_keys = (
        "live_evidence_pre_authorization_recorded",
        "bc1_protected_live_adapter_attestation_recorded",
        "bc10_real_adapter_usage_cost_aggregate_recorded",
        "final_operator_promotion_decision_recorded",
    )
    for key in state_keys:
        assert snap[key] == sub[key], f"submanifest snapshot drift for {key}: evidence={snap[key]} file={sub[key]}"


def test_ri78b_bc10_6a_nine_key_readiness_unchanged_all_true():
    manifest = _load_json(READINESS_MANIFEST_PATH)
    forbidden_keys = {"schema_version", "artifact_kind"}
    flag_keys = [k for k in manifest if k not in forbidden_keys]
    assert len(flag_keys) == 9, f"Expected 9 readiness keys, got {len(flag_keys)}"
    for key in flag_keys:
        assert manifest[key] is True, f"Readiness key {key} must be true, got {manifest[key]}"


def test_ri78b_bc10_6a_guard_flags_const_false():
    evidence = _load_json(EVIDENCE_PATH)
    assert evidence["support_widening"] is False
    assert evidence["production_platform_claim"] is False
    assert evidence["live_adapter_execution"] is False


def test_ri78b_bc10_6a_submanifest_transition_before_after_equal_post_bc1():
    """bc1=true preserved in both before & after (6a doesn't flip BC-1).
    bc10=false preserved in both before & after (6a doesn't flip BC-10)."""
    evidence = _load_json(EVIDENCE_PATH)
    trans = evidence["submanifest_transition"]
    assert trans["before"]["bc1_protected_live_adapter_attestation_recorded"] is True
    assert trans["before"]["bc10_real_adapter_usage_cost_aggregate_recorded"] is False
    assert trans["after"]["bc1_protected_live_adapter_attestation_recorded"] is True
    assert trans["after"]["bc10_real_adapter_usage_cost_aggregate_recorded"] is False


# ---------------------------------------------------------------------------
# Forbidden-change audit: exact set + machine-enforced via git diff
# ---------------------------------------------------------------------------


def test_ri78b_bc10_6a_forbidden_change_audit_exact_17_set():
    evidence = _load_json(EVIDENCE_PATH)
    audit = evidence["forbidden_change_audit"]
    assert audit["all_unchanged"] is True
    assert set(audit["forbidden_surfaces"]) == set(EXPECTED_FORBIDDEN_SURFACES)
    assert len(audit["forbidden_surfaces"]) == 17


def test_ri78b_bc10_6a_forbidden_change_audit_machine_enforced_against_origin_main():
    if not _is_ri78b_bc10_6a_introducer_pr():
        pytest.skip("6a state-at-landing pin: only enforced on the introducer PR")
    _skip_if_current_local_review_evidence_is_for_another_slice()
    base_sha = _resolve_diff_base()
    if base_sha is None:
        pytest.skip("No git base resolved (origin/main / main not reachable)")
    changed = _git_changed_paths_against(base_sha)
    for surface in EXPECTED_FORBIDDEN_SURFACES:
        for path in changed:
            assert not _path_matches_surface(path, surface), (
                f"Forbidden surface touched in 6a PR: surface={surface}, changed_path={path}"
            )


def test_ri78b_bc10_6a_gpp_status_untouched():
    if not _is_ri78b_bc10_6a_introducer_pr():
        pytest.skip("6a state-at-landing pin: only enforced on the introducer PR")
    _skip_if_current_local_review_evidence_is_for_another_slice()
    base_sha = _resolve_diff_base()
    if base_sha is None:
        pytest.skip("No git base resolved")
    changed = _git_changed_paths_against(base_sha)
    assert ".claude/plans/gpp_status.v1.json" not in changed


def test_ri78b_bc10_6a_ri78a_predecessor_evidence_untouched():
    if not _is_ri78b_bc10_6a_introducer_pr():
        pytest.skip("6a state-at-landing pin: only enforced on the introducer PR")
    _skip_if_current_local_review_evidence_is_for_another_slice()
    base_sha = _resolve_diff_base()
    if base_sha is None:
        pytest.skip("No git base resolved")
    changed = _git_changed_paths_against(base_sha)
    assert ".claude/plans/RI-7.8a-LIVE-EVIDENCE-PRE-AUTHORIZATION.v1.json" not in changed


def test_ri78b_bc10_6a_ri78_submanifest_file_untouched_in_diff():
    if not _is_ri78b_bc10_6a_introducer_pr():
        pytest.skip("6a state-at-landing pin: only enforced on the introducer PR")
    _skip_if_current_local_review_evidence_is_for_another_slice()
    base_sha = _resolve_diff_base()
    if base_sha is None:
        pytest.skip("No git base resolved")
    changed = _git_changed_paths_against(base_sha)
    assert ".claude/plans/RI-7.8-EVIDENCE-MANIFEST.v1.json" not in changed


def test_ri78b_bc10_6a_ri78b_bc1_6c_closure_predecessor_untouched():
    """BC-1 closure evidence is immutable; bc10-6a must not touch it."""
    if not _is_ri78b_bc10_6a_introducer_pr():
        pytest.skip("6a state-at-landing pin: only enforced on the introducer PR")
    _skip_if_current_local_review_evidence_is_for_another_slice()
    base_sha = _resolve_diff_base()
    if base_sha is None:
        pytest.skip("No git base resolved")
    changed = _git_changed_paths_against(base_sha)
    assert ".claude/plans/RI-7.8b-bc1-6c-CLOSURE.v1.json" not in changed


# ---------------------------------------------------------------------------
# Cross-AI peer review provider split + cross-artifact verdict equality
# ---------------------------------------------------------------------------


def test_ri78b_bc10_6a_cross_ai_review_provider_split_const():
    evidence = _load_json(EVIDENCE_PATH)
    cr = evidence["cross_ai_review_ref"]
    assert cr["implementer_provider"] == "anthropic"
    assert cr["reviewer_provider"] == "openai"
    assert cr["final_verdict"] in {"REVISE", "AGREE"}
    assert cr["thread_id"], "thread_id must be non-empty"


def test_ri78b_bc10_6a_cross_artifact_verdict_equality():
    if not LOCAL_AI_REVIEW_PATH.exists():
        pytest.skip("local-ai-review-evidence.v1.json missing — will be added before merge")
    review = _load_json(LOCAL_AI_REVIEW_PATH)
    if review["work_package"] != "RI-7.8b-bc10-6a":
        pytest.skip("local-ai-review-evidence.v1.json belongs to another active PR work package")
    evidence = _load_json(EVIDENCE_PATH)
    assert review["reviewer"]["provider"] == "openai"
    assert review["implementer"]["provider"] == "anthropic"
    assert review["work_package"] == "RI-7.8b-bc10-6a"
    assert review["reviewer"]["verdict"] == evidence["cross_ai_review_ref"]["final_verdict"]


# ---------------------------------------------------------------------------
# Negative schema tests — drift detection (each mutation must fail validation)
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


def test_ri78b_bc10_6a_negative_authorization_effect_other_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("authorization_effect",), "execution_permission_granted"))
    _assert_rejected(bad, "authorization_effect must be const")


def test_ri78b_bc10_6a_negative_decision_other_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("decision",), "some_other_decision"))
    _assert_rejected(bad, "decision must be const")


def test_ri78b_bc10_6a_negative_window_status_other_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (("authorization_window_contract", "window_status"), "active_executable"),
    )
    _assert_rejected(bad, "window_status must be authorized_pending_6b_activation")


def test_ri78b_bc10_6a_negative_actual_start_at_non_null_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (
            ("authorization_window_contract", "actual_start_at"),
            "2026-06-01T00:00:00Z",
        ),
    )
    _assert_rejected(bad, "actual_start_at must be null in 6a")


def test_ri78b_bc10_6a_negative_observed_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("protected_environment_binding", "observed"), True))
    _assert_rejected(bad, "observed must be false in 6a")


def test_ri78b_bc10_6a_negative_authority_mode_autonomous_rejected():
    """bc10-6a MUST pin manual_protected_environment; autonomous is forbidden."""
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (("planned_6b_authority_mode", "authority_mode"), "operator_delegated_autonomous_preprod"),
    )
    _assert_rejected(bad, "authority_mode must be manual_protected_environment")


def test_ri78b_bc10_6a_negative_autonomous_trigger_allowed_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (("planned_6b_authority_mode", "autonomous_trigger_allowed"), True),
    )
    _assert_rejected(bad, "autonomous_trigger_allowed must be false const")


def test_ri78b_bc10_6a_negative_provider_call_performed_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("mutations_performed", "provider_call_performed"), True))
    _assert_rejected(bad, "provider_call_performed must be false const")


def test_ri78b_bc10_6a_negative_secret_referenced_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("mutations_performed", "secret_referenced"), True))
    _assert_rejected(bad, "secret_referenced must be false const")


def test_ri78b_bc10_6a_negative_support_widening_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("support_widening",), True))
    _assert_rejected(bad, "support_widening must be false")


def test_ri78b_bc10_6a_negative_live_adapter_execution_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("live_adapter_execution",), True))
    _assert_rejected(bad, "live_adapter_execution must be false")


def test_ri78b_bc10_6a_negative_submanifest_after_bc10_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (
            (
                "submanifest_transition",
                "after",
                "bc10_real_adapter_usage_cost_aggregate_recorded",
            ),
            True,
        ),
    )
    _assert_rejected(bad, "submanifest after.bc10 must be false in 6a")


def test_ri78b_bc10_6a_negative_operator_github_login_other_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (("operator_authorization_record", "github_login"), "SomeoneElse"),
    )
    _assert_rejected(bad, "operator github_login must be Halildeu")


def test_ri78b_bc10_6a_negative_protected_env_production_name_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (
            ("protected_environment_binding", "env_name"),
            "production-real-adapter-usage-cost",
        ),
    )
    _assert_rejected(bad, "env_name must NOT be production_*")


def test_ri78b_bc10_6a_negative_workflow_content_sha256_non_null_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (("future_workflow_contract", "workflow_content_sha256"), "a" * 64),
    )
    _assert_rejected(bad, "workflow_content_sha256 must be null in 6a")


def test_ri78b_bc10_6a_negative_model_allowlist_extra_model_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (("future_workflow_contract", "model_allowlist"), ["openai/gpt-4o-mini", "openai/gpt-4o"]),
    )
    _assert_rejected(bad, "model_allowlist must be maxItems=1 enum=openai/gpt-4o-mini")


def test_ri78b_bc10_6a_negative_forbidden_audit_all_unchanged_false_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("forbidden_change_audit", "all_unchanged"), False))
    _assert_rejected(bad, "all_unchanged must be true const")


def test_ri78b_bc10_6a_negative_does_not_authorize_missing_action_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = copy.deepcopy(evidence)
    bad["does_not_authorize"] = [
        "workflow_dispatch_now",
        "adapter_execution_now",
        "credential_reference",
        "billable_provider_call_now",
        "cost_incurring_calls_now",
        "support_widening",
        "production_platform_claim",
        "gpp_status_guard_flip",
        # missing submanifest_bc10_flip
    ]
    _assert_rejected(bad, "does_not_authorize must have all 9 actions")
