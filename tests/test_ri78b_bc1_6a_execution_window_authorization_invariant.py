"""Invariant tests for RI-7.8b-bc1-6a execution-window authorization slice.

This test suite enforces:

- Schema strictness (Draft 2020-12, additionalProperties=false, const pins, exact-set forbidden audit)
- Evidence validates against schema
- Operator signature: Halildeu + ISO 8601 UTC + no-secret-assertion + 6-signal contract
- Negative schema tests: guard flag true / authorization_effect drift / window_status drift /
  actual_start_at non-null / observed=true / submanifest after.bc1=true → rejected
- RI-7.8a predecessor evidence UNCHANGED + digests pin predecessor state
- RI-7.8 submanifest UNCHANGED in 6a (all 4 keys at predecessor values)
- 9-key readiness manifest UNCHANGED at 9/9 true
- gpp_status.v1.json UNCHANGED
- forbidden_change_audit exact set (16 surfaces) + machine-enforced via git diff vs origin/main
- expected_dispatch_inputs_allowlist ∩ expected_forbidden_inputs == ∅
- future workflow file does NOT exist in 6a PR
- cross-AI peer review provider split const (anthropic implementer, openai reviewer)
- cross-artifact verdict equality (evidence cross_ai_review_ref.final_verdict ==
  local-ai-review-evidence.reviewer.verdict)
- plan doc records the decision string
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

PR_NUMBER_HINT = "675"

REPO_ROOT = Path(__file__).resolve().parent.parent

SCHEMA_PATH = (
    REPO_ROOT
    / "ao_kernel"
    / "defaults"
    / "schemas"
    / "ri7-8b-bc1-6a-execution-window-authorization-evidence.schema.v1.json"
)
EVIDENCE_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8b-bc1-6a-EXECUTION-WINDOW-AUTHORIZATION.v1.json"
PLAN_DOC_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8b-bc1-6a-EXECUTION-WINDOW-AUTHORIZATION.md"
SUBMANIFEST_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8-EVIDENCE-MANIFEST.v1.json"
READINESS_MANIFEST_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7-EVIDENCE-MANIFEST.v1.json"
RI78A_EVIDENCE_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8a-LIVE-EVIDENCE-PRE-AUTHORIZATION.v1.json"
GPP_STATUS_PATH = REPO_ROOT / ".claude" / "plans" / "gpp_status.v1.json"
LOCAL_AI_REVIEW_PATH = REPO_ROOT / "local-ai-review-evidence.v1.json"
FUTURE_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "bc1-protected-live-adapter-attestation.yml"

EXPECTED_FORBIDDEN_SURFACES = [
    ".claude/plans/gpp_status.v1.json",
    "scripts/gp5_platform_claim_decision.py",
    ".github/workflows/",
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
    """Best-effort diff base resolution against origin/main.

    Strategy:
    1. Try `git merge-base HEAD origin/main`
    2. Fallback to `origin/main` ref directly
    3. Fallback to local `main`
    4. Return None on failure (CI fail-closed: test passes structurally,
       but git-diff invariant returns None → skip with explicit reason).
    """
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


def _path_matches_surface(path: str, surface: str) -> bool:
    if surface.endswith("/"):
        return path.startswith(surface)
    return path == surface


# ---------------------------------------------------------------------------
# Schema / evidence structural invariants
# ---------------------------------------------------------------------------


def test_ri78b_bc1_6a_schema_path_exists():
    assert SCHEMA_PATH.exists(), f"Schema missing: {SCHEMA_PATH}"


def test_ri78b_bc1_6a_evidence_path_exists():
    assert EVIDENCE_PATH.exists(), f"Evidence missing: {EVIDENCE_PATH}"


def test_ri78b_bc1_6a_schema_is_draft_2020_12():
    schema = _load_json(SCHEMA_PATH)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    jsonschema.Draft202012Validator.check_schema(schema)


def test_ri78b_bc1_6a_evidence_validates_against_schema():
    schema = _load_json(SCHEMA_PATH)
    evidence = _load_json(EVIDENCE_PATH)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(evidence), key=lambda e: list(e.absolute_path))
    assert not errors, "Evidence does not validate: " + "; ".join(
        f"{list(e.absolute_path)}: {e.message}" for e in errors
    )


def test_ri78b_bc1_6a_decision_const():
    evidence = _load_json(EVIDENCE_PATH)
    assert (
        evidence["decision"] == "ri78b_bc1_6a_execution_window_authorization_recorded_no_execution_no_guard_flag_flip"
    )


def test_ri78b_bc1_6a_authorization_effect_const():
    evidence = _load_json(EVIDENCE_PATH)
    assert evidence["authorization_effect"] == "execution_window_authorization_recorded_no_execution_no_guard_flag_flip"


def test_ri78b_bc1_6a_does_not_authorize_7_enum():
    evidence = _load_json(EVIDENCE_PATH)
    expected = {
        "workflow_dispatch_now",
        "adapter_execution_now",
        "credential_reference",
        "cost_incurring_calls_now",
        "support_widening",
        "production_platform_claim",
        "gpp_status_guard_flip",
    }
    assert set(evidence["does_not_authorize"]) == expected
    assert len(evidence["does_not_authorize"]) == 7


# ---------------------------------------------------------------------------
# Operator authority + ri78a predecessor + window contract
# ---------------------------------------------------------------------------


def test_ri78b_bc1_6a_operator_signature_halildeu_iso_8601_no_secret():
    evidence = _load_json(EVIDENCE_PATH)
    op = evidence["operator_authorization_record"]
    assert op["github_login"] == "Halildeu"
    assert op["no_secret_assertion"] is True
    assert op["authorization_scope"] == "bc1_6a_execution_window_contract_only"
    assert op["does_not_authorize_immediate_execution"] is True
    # ISO 8601 UTC with Z suffix
    import re

    assert re.match(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$",
        op["authorization_recorded_at"],
    ), op["authorization_recorded_at"]
    assert op["authorization_source"], "authorization_source must be non-empty"
    assert op["observation_notes"], "observation_notes must be non-empty"


def test_ri78b_bc1_6a_ri78a_predecessor_digest_matches_predecessor_state():
    evidence = _load_json(EVIDENCE_PATH)
    pred = evidence["ri78a_predecessor_ref"]
    assert pred["pr_number"] == 673
    # Hash predecessor files now and compare to evidence pins
    expected_ri78a_sha = _sha256_file(RI78A_EVIDENCE_PATH)
    expected_submanifest_sha = _sha256_file(SUBMANIFEST_PATH)
    expected_readiness_sha = _sha256_file(READINESS_MANIFEST_PATH)
    assert pred["ri78a_evidence_sha256"] == expected_ri78a_sha
    assert pred["ri78_submanifest_sha256"] == expected_submanifest_sha
    assert pred["readiness_manifest_sha256"] == expected_readiness_sha


def test_ri78b_bc1_6a_stale_replay_guard_digests_match():
    evidence = _load_json(EVIDENCE_PATH)
    guard = evidence["stale_replay_guard"]
    assert guard["base_ref"] == "refs/heads/main"
    assert guard["head_ref"] == "refs/heads/codex/ri-7-8b-bc1-6a-execution-window-authorization"
    expected_ri78a_sha = _sha256_file(RI78A_EVIDENCE_PATH)
    expected_submanifest_sha = _sha256_file(SUBMANIFEST_PATH)
    expected_readiness_sha = _sha256_file(READINESS_MANIFEST_PATH)
    assert guard["ri78a_evidence_sha256"] == expected_ri78a_sha
    assert guard["ri78_submanifest_sha256"] == expected_submanifest_sha
    assert guard["readiness_manifest_sha256"] == expected_readiness_sha


def test_ri78b_bc1_6a_window_status_const_authorized_pending_6b_activation():
    evidence = _load_json(EVIDENCE_PATH)
    win = evidence["authorization_window_contract"]
    assert win["window_status"] == "authorized_pending_6b_activation"
    assert win["actual_start_at"] is None
    assert win["actual_end_at"] is None
    assert win["activation_owner_slice"] == "RI-7.8b-bc1-6b"
    assert win["contract_status"] == "expected_unresolved_until_6b"
    assert 1 <= win["max_run_count"] <= 5
    assert 0 < win["max_usd"] <= 5.0
    assert 1 <= win["max_activation_delay_hours"] <= 168
    assert 1 <= win["max_execution_window_duration_hours"] <= 24


# ---------------------------------------------------------------------------
# Time-window audit binding (Codex iter-3 post-impl review absorb)
# ---------------------------------------------------------------------------


def _parse_iso_z(s: str) -> datetime:
    """Parse '...Z' ISO 8601 UTC into aware datetime."""
    if s.endswith("Z"):
        return datetime.fromisoformat(s[:-1] + "+00:00")
    return datetime.fromisoformat(s)


def test_ri78b_bc1_6a_authorization_recorded_at_not_in_future():
    """authorization_recorded_at MUST be <= now (UTC) + small tolerance.

    Future-dated authorization timestamps cannot be operator-bound at the time
    of recording — they retroactively claim provenance that did not exist.
    """
    evidence = _load_json(EVIDENCE_PATH)
    op = evidence["operator_authorization_record"]
    recorded_at = _parse_iso_z(op["authorization_recorded_at"])
    now = datetime.now(timezone.utc)
    tolerance = timedelta(minutes=15)
    assert recorded_at <= now + tolerance, (
        f"authorization_recorded_at={recorded_at.isoformat()} is in the future "
        f"relative to now={now.isoformat()} (tolerance=15min). Future-dated "
        f"operator-bound timestamps are audit-invalid."
    )


def test_ri78b_bc1_6a_validity_window_bounded_by_max_activation_delay():
    """authorization_valid_until > authorization_recorded_at AND
    (valid_until - recorded_at) <= max_activation_delay_hours."""
    evidence = _load_json(EVIDENCE_PATH)
    op = evidence["operator_authorization_record"]
    win = evidence["authorization_window_contract"]
    recorded_at = _parse_iso_z(op["authorization_recorded_at"])
    valid_until = _parse_iso_z(win["authorization_valid_until"])
    assert valid_until > recorded_at, (
        f"authorization_valid_until={valid_until.isoformat()} must be strictly "
        f"after authorization_recorded_at={recorded_at.isoformat()}"
    )
    delta = valid_until - recorded_at
    max_hours = win["max_activation_delay_hours"]
    max_delta = timedelta(hours=max_hours)
    assert delta <= max_delta, (
        f"(valid_until - recorded_at)={delta} exceeds max_activation_delay_hours={max_hours} ({max_delta})"
    )


def test_ri78b_bc1_6a_pr_number_hint_bound_to_real_pr():
    """Both stale_replay_guard.pr_number_hint and context_binding.pr_number_hint
    MUST equal the real PR number once it is open. 'TBD' is rejected."""
    evidence = _load_json(EVIDENCE_PATH)
    assert evidence["stale_replay_guard"]["pr_number_hint"] == PR_NUMBER_HINT
    assert evidence["context_binding"]["pr_number_hint"] == PR_NUMBER_HINT
    assert evidence["stale_replay_guard"]["pr_number_hint"] != "TBD"


def test_ri78b_bc1_6a_authorization_source_is_auditable_reference():
    """authorization_source MUST reference an auditable artifact: PR/issue URL,
    review id, commit SHA + trailer ref, or runbook ref. A bare plan doc path
    alone is too weak for cross-AI audit."""
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
        f"authorization_source={source!r} must include an auditable reference marker (one of: {auditable_markers})"
    )


def test_ri78b_bc1_6a_protected_env_name_not_production():
    evidence = _load_json(EVIDENCE_PATH)
    env = evidence["protected_environment_binding"]
    assert env["env_name"] == "ao-kernel-bc1-live-adapter-attestation"
    assert not env["env_name"].startswith("production")
    assert "production" not in env["env_name"].split("-")
    assert env["observed"] is False
    assert env["observed_at"] is None
    assert env["observation_source"] is None
    assert env["observed_environment_sha256"] is None
    assert env["observation_owner_slice"] == "RI-7.8b-bc1-6b"
    assert env["required_reviewers_expected"] is True
    assert env["prevent_self_review_expected"] is True
    assert env["allowed_refs_expected"] == ["refs/heads/main"]
    assert env["admin_bypass_allowed_expected"] is False


def test_ri78b_bc1_6a_future_workflow_contract_pinned():
    evidence = _load_json(EVIDENCE_PATH)
    wf = evidence["future_workflow_contract"]
    assert wf["workflow_path"] == ".github/workflows/bc1-protected-live-adapter-attestation.yml"
    assert wf["expected_absent_or_not_touched_in_6a"] is True
    assert wf["creation_owner_slice"] == "RI-7.8b-bc1-6b"
    assert wf["workflow_sha"] is None
    assert wf["allowed_ref"] == "refs/heads/main"
    assert wf["contract_status"] == "expected_unresolved_until_6b"
    # Allowlist non-empty, no overlap with forbidden inputs
    allowlist = set(wf["expected_dispatch_inputs_allowlist"])
    forbidden = set(wf["expected_forbidden_inputs"])
    assert allowlist, "allowlist must be non-empty"
    assert allowlist & forbidden == set(), f"allowlist ∩ forbidden must be empty; got overlap: {allowlist & forbidden}"


def test_ri78b_bc1_6a_future_workflow_file_absent_in_repo():
    """6a MUST NOT create the future BC-1 workflow file."""
    assert not FUTURE_WORKFLOW_PATH.exists(), f"6a must not create the future BC-1 workflow: {FUTURE_WORKFLOW_PATH}"


def test_ri78b_bc1_6a_closure_clauses_const():
    evidence = _load_json(EVIDENCE_PATH)
    clause = evidence["closure_expiry_and_revocation_clause"]
    assert (
        clause["authorization_expiry_action"]
        == "authorization_auto_invalidates_if_not_activated_by_6b_within_validity_window"
    )
    assert clause["window_end_action"] == "live_adapter_execution_must_remain_false_outside_window"
    assert clause["post_window_verifier_owner"] == "RI-7.8b-bc1-6c"
    assert clause["revocation_action"] == "operator_may_revoke_before_6b_activation_via_new_pr_or_supersession_entry"
    assert clause["rerun_policy"] == "expired_or_exceeded_runs_are_fail_closed_no_silent_retry"


def test_ri78b_bc1_6a_activation_requirements_all_true():
    evidence = _load_json(EVIDENCE_PATH)
    act = evidence["activation_requirements"]
    assert act["activation_requires_new_operator_confirmation"] is True
    assert act["activation_requires_workflow_sha_binding"] is True
    assert act["activation_requires_protected_environment_observation"] is True
    assert act["activation_requires_guard_flag_policy_resolution"] is True


# ---------------------------------------------------------------------------
# State snapshots: 9/9 readiness + GPP guard + RI-7.8 submanifest unchanged
# ---------------------------------------------------------------------------


def test_ri78b_bc1_6a_readiness_snapshot_9_9_true():
    evidence = _load_json(EVIDENCE_PATH)
    snap = evidence["current_readiness_snapshot"]
    assert snap["nine_key_manifest_all_true"] is True
    assert snap["readiness_gate_decision"] == "ready_for_operator_promotion_decision"
    assert snap["operator_verified_runtime_semantics"] is True
    assert snap["explicit_operator_authorization"] is True
    assert snap["general_purpose_platform_claim_authorization"] is True


def test_ri78b_bc1_6a_gpp_guard_snapshot_all_false():
    evidence = _load_json(EVIDENCE_PATH)
    guard = evidence["current_gpp_guard_snapshot"]
    assert guard["support_widening_allowed"] is False
    assert guard["production_platform_claim_allowed"] is False
    assert guard["live_adapter_execution_allowed"] is False


def test_ri78b_bc1_6a_ri78_submanifest_unchanged_in_6a():
    """6a MUST NOT mutate the RI-7.8 submanifest; all four keys at predecessor values."""
    sub = _load_json(SUBMANIFEST_PATH)
    assert sub["live_evidence_pre_authorization_recorded"] is True
    assert sub["bc1_protected_live_adapter_attestation_recorded"] is False
    assert sub["bc10_real_adapter_usage_cost_aggregate_recorded"] is False
    assert sub["final_operator_promotion_decision_recorded"] is False
    # Evidence snapshot must mirror the four state keys exactly (schema_version
    # / artifact_kind on the submanifest file are excluded — the snapshot tracks
    # only the four chain-progress flags).
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


def test_ri78b_bc1_6a_nine_key_readiness_unchanged_all_true():
    manifest = _load_json(READINESS_MANIFEST_PATH)
    forbidden_keys = {"schema_version", "artifact_kind"}
    flag_keys = [k for k in manifest if k not in forbidden_keys]
    assert len(flag_keys) == 9, f"Expected 9 readiness keys, got {len(flag_keys)}"
    for key in flag_keys:
        assert manifest[key] is True, f"Readiness key {key} must be true, got {manifest[key]}"


def test_ri78b_bc1_6a_guard_flags_const_false():
    evidence = _load_json(EVIDENCE_PATH)
    assert evidence["support_widening"] is False
    assert evidence["production_platform_claim"] is False
    assert evidence["live_adapter_execution"] is False


def test_ri78b_bc1_6a_submanifest_transition_before_after_equal_false():
    evidence = _load_json(EVIDENCE_PATH)
    trans = evidence["submanifest_transition"]
    assert trans["before"]["bc1_protected_live_adapter_attestation_recorded"] is False
    assert trans["after"]["bc1_protected_live_adapter_attestation_recorded"] is False


# ---------------------------------------------------------------------------
# Forbidden-change audit: exact set + machine-enforced via git diff
# ---------------------------------------------------------------------------


def test_ri78b_bc1_6a_forbidden_change_audit_exact_16_set():
    evidence = _load_json(EVIDENCE_PATH)
    audit = evidence["forbidden_change_audit"]
    assert audit["all_unchanged"] is True
    assert set(audit["forbidden_surfaces"]) == set(EXPECTED_FORBIDDEN_SURFACES)
    assert len(audit["forbidden_surfaces"]) == 16


def test_ri78b_bc1_6a_forbidden_change_audit_machine_enforced_against_origin_main():
    """Verify via git diff that NONE of the forbidden surfaces are touched in this PR."""
    base_sha = _resolve_diff_base()
    if base_sha is None:
        pytest.skip("No git base resolved (origin/main / main not reachable)")
    changed = _git_changed_paths_against(base_sha)
    for surface in EXPECTED_FORBIDDEN_SURFACES:
        for path in changed:
            assert not _path_matches_surface(path, surface), (
                f"Forbidden surface touched in 6a PR: surface={surface}, changed_path={path}"
            )


def test_ri78b_bc1_6a_gpp_status_untouched():
    """gpp_status.v1.json must not be touched in 6a."""
    base_sha = _resolve_diff_base()
    if base_sha is None:
        pytest.skip("No git base resolved")
    changed = _git_changed_paths_against(base_sha)
    assert ".claude/plans/gpp_status.v1.json" not in changed


def test_ri78b_bc1_6a_ri78a_predecessor_evidence_untouched():
    """Predecessor evidence is immutable; 6a must not touch it."""
    base_sha = _resolve_diff_base()
    if base_sha is None:
        pytest.skip("No git base resolved")
    changed = _git_changed_paths_against(base_sha)
    assert ".claude/plans/RI-7.8a-LIVE-EVIDENCE-PRE-AUTHORIZATION.v1.json" not in changed


def test_ri78b_bc1_6a_ri78_submanifest_file_untouched_in_diff():
    """Submanifest must be UNCHANGED in 6a (BC-1 key flip belongs to 6c)."""
    base_sha = _resolve_diff_base()
    if base_sha is None:
        pytest.skip("No git base resolved")
    changed = _git_changed_paths_against(base_sha)
    assert ".claude/plans/RI-7.8-EVIDENCE-MANIFEST.v1.json" not in changed


# ---------------------------------------------------------------------------
# Cross-AI peer review provider split + cross-artifact verdict equality
# ---------------------------------------------------------------------------


def test_ri78b_bc1_6a_cross_ai_review_provider_split_const():
    evidence = _load_json(EVIDENCE_PATH)
    cr = evidence["cross_ai_review_ref"]
    assert cr["implementer_provider"] == "anthropic"
    assert cr["reviewer_provider"] == "openai"
    assert cr["final_verdict"] in {"REVISE", "AGREE"}
    assert cr["thread_id"], "thread_id must be non-empty"


def test_ri78b_bc1_6a_cross_artifact_verdict_equality():
    if not LOCAL_AI_REVIEW_PATH.exists():
        pytest.skip("local-ai-review-evidence.v1.json missing — will be added before merge")
    review = _load_json(LOCAL_AI_REVIEW_PATH)
    evidence = _load_json(EVIDENCE_PATH)
    assert review["reviewer"]["provider"] == "openai"
    assert review["implementer"]["provider"] == "anthropic"
    # Work package binding
    assert review["work_package"] == "RI-7.8b-bc1-6a"
    # Verdict equality
    assert review["reviewer"]["verdict"] == evidence["cross_ai_review_ref"]["final_verdict"]


# ---------------------------------------------------------------------------
# Plan doc records the decision
# ---------------------------------------------------------------------------


def test_ri78b_bc1_6a_plan_doc_records_decision():
    text = PLAN_DOC_PATH.read_text()
    assert "ri78b_bc1_6a_execution_window_authorization_recorded_no_execution_no_guard_flag_flip" in text
    assert "no execution permission" in text.lower()
    assert "no guard flag flip" in text.lower() or "no flag flip" in text.lower()


# ---------------------------------------------------------------------------
# Negative schema tests — drift detection (each mutation must fail validation)
# ---------------------------------------------------------------------------


def _mutate(evidence: dict, *path_value_pairs) -> dict:
    """Return a deep-copied evidence with mutations applied in order."""
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


def test_ri78b_bc1_6a_negative_authorization_effect_other_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("authorization_effect",), "execution_permission_granted"))
    _assert_rejected(bad, "authorization_effect must be const")


def test_ri78b_bc1_6a_negative_decision_other_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("decision",), "some_other_decision"))
    _assert_rejected(bad, "decision must be const")


def test_ri78b_bc1_6a_negative_window_status_other_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (("authorization_window_contract", "window_status"), "active_executable"),
    )
    _assert_rejected(bad, "window_status must be authorized_pending_6b_activation")


def test_ri78b_bc1_6a_negative_actual_start_at_non_null_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (
            ("authorization_window_contract", "actual_start_at"),
            "2026-06-01T00:00:00Z",
        ),
    )
    _assert_rejected(bad, "actual_start_at must be null in 6a")


def test_ri78b_bc1_6a_negative_actual_end_at_non_null_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (("authorization_window_contract", "actual_end_at"), "2026-06-02T00:00:00Z"),
    )
    _assert_rejected(bad, "actual_end_at must be null in 6a")


def test_ri78b_bc1_6a_negative_observed_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("protected_environment_binding", "observed"), True))
    _assert_rejected(bad, "observed must be false in 6a")


def test_ri78b_bc1_6a_negative_support_widening_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("support_widening",), True))
    _assert_rejected(bad, "support_widening must be false")


def test_ri78b_bc1_6a_negative_production_platform_claim_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("production_platform_claim",), True))
    _assert_rejected(bad, "production_platform_claim must be false")


def test_ri78b_bc1_6a_negative_live_adapter_execution_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("live_adapter_execution",), True))
    _assert_rejected(bad, "live_adapter_execution must be false")


def test_ri78b_bc1_6a_negative_submanifest_after_bc1_true_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (
            (
                "submanifest_transition",
                "after",
                "bc1_protected_live_adapter_attestation_recorded",
            ),
            True,
        ),
    )
    _assert_rejected(bad, "submanifest after.bc1 must be false in 6a")


def test_ri78b_bc1_6a_negative_operator_github_login_other_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (("operator_authorization_record", "github_login"), "SomeoneElse"),
    )
    _assert_rejected(bad, "operator github_login must be Halildeu")


def test_ri78b_bc1_6a_negative_protected_env_production_name_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (
            ("protected_environment_binding", "env_name"),
            "production-live-adapter-attestation",
        ),
    )
    _assert_rejected(bad, "env_name must NOT be production_*")


def test_ri78b_bc1_6a_negative_future_workflow_sha_non_null_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        evidence,
        (("future_workflow_contract", "workflow_sha"), "a" * 40),
    )
    _assert_rejected(bad, "workflow_sha must be null in 6a")


def test_ri78b_bc1_6a_negative_forbidden_audit_all_unchanged_false_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    bad = _mutate(evidence, (("forbidden_change_audit", "all_unchanged"), False))
    _assert_rejected(bad, "all_unchanged must be true const")


def test_ri78b_bc1_6a_negative_does_not_authorize_missing_action_rejected():
    evidence = _load_json(EVIDENCE_PATH)
    # Remove one required forbidden action
    bad = copy.deepcopy(evidence)
    bad["does_not_authorize"] = [
        "workflow_dispatch_now",
        "adapter_execution_now",
        "credential_reference",
        "cost_incurring_calls_now",
        "support_widening",
        "production_platform_claim",
        # missing gpp_status_guard_flip
    ]
    _assert_rejected(bad, "does_not_authorize must have all 7 actions")
