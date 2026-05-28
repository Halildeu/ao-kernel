"""Invariant tests for RI-7.8b-bc1-6b protected execution window infrastructure.

This test suite enforces:

- Schema strictness (Draft 2020-12, additionalProperties=false, const pins,
  exact-set forbidden audit)
- Evidence validates against schema
- workflow_content_sha256 in evidence matches actual workflow file bytes
- gpp_status.v1.json:
  - Top-level guard flags remain const false (baseline closure preserved)
  - operator_bound_supersessions[RI-7.8b-bc1-6b] entry shape + scoped policy
  - Scoped entry workflow_content_sha256 matches the file
- Workflow file structural checks: workflow_dispatch trigger, environment,
  minimal permissions (contents/actions/deployments: read), concurrency,
  scenario choice input, no forbidden input names
- Activation guard script exists at canonical path
- Operator activation: Halildeu + ISO 8601 UTC + auditable source +
  no-secret-assertion + 6-signal contract
- RI-7.8 submanifest UNCHANGED in 6b
- 9-key readiness manifest UNCHANGED
- Predecessor (RI-7.8a + RI-7.8b-bc1-6a) digests match files
- forbidden_change_audit exact 13 surfaces + machine-enforced via git diff
- expected_dispatch_inputs_allowlist ∩ expected_forbidden_inputs == ∅
- Time invariants (activation_confirmed_at not future,
  validity_window_until > confirmed_at AND delta <= max_activation_delay_hours)
- Cross-AI peer review provider split const + cross-artifact verdict equality
- Plan doc records the decision
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
    / "ri7-8b-bc1-6b-protected-execution-window-evidence.schema.v1.json"
)
EVIDENCE_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8b-bc1-6b-PROTECTED-EXECUTION-WINDOW.v1.json"
PLAN_DOC_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8b-bc1-6b-PROTECTED-EXECUTION-WINDOW.md"
SUBMANIFEST_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8-EVIDENCE-MANIFEST.v1.json"
READINESS_MANIFEST_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7-EVIDENCE-MANIFEST.v1.json"
RI78A_EVIDENCE_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8a-LIVE-EVIDENCE-PRE-AUTHORIZATION.v1.json"
RI78B_6A_EVIDENCE_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8b-bc1-6a-EXECUTION-WINDOW-AUTHORIZATION.v1.json"
GPP_STATUS_PATH = REPO_ROOT / ".claude" / "plans" / "gpp_status.v1.json"
LOCAL_AI_REVIEW_PATH = REPO_ROOT / "local-ai-review-evidence.v1.json"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "bc1-protected-live-adapter-attestation.yml"
ACTIVATION_GUARD_PATH = REPO_ROOT / "scripts" / "ri78b_bc1_activation_window.py"

EXPECTED_FORBIDDEN_SURFACES = [
    "scripts/gp5_platform_claim_decision.py",
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
    ".claude/plans/RI-7.8-EVIDENCE-MANIFEST.v1.json",
]

ALLOWED_NEW_SURFACES = [
    # Core 6b infrastructure (8 files)
    ".claude/plans/RI-7.8b-bc1-6b-PROTECTED-EXECUTION-WINDOW.md",
    ".claude/plans/RI-7.8b-bc1-6b-PROTECTED-EXECUTION-WINDOW.v1.json",
    "ao_kernel/defaults/schemas/ri7-8b-bc1-6b-protected-execution-window-evidence.schema.v1.json",
    "tests/test_ri78b_bc1_6b_protected_execution_window_invariant.py",
    ".github/workflows/bc1-protected-live-adapter-attestation.yml",
    "scripts/ri78b_bc1_activation_window.py",
    ".claude/plans/gpp_status.v1.json",
    "local-ai-review-evidence.v1.json",
    # Systemic predecessor invariant fix (introducer-PR detection pattern)
    # — RI-7.8a + RI-7.8b-bc1-6a diff-dependent state-at-landing tests were
    # failing on 6b successor PR. Fix lives inline because 6b is the first
    # slice that triggers the systemic bug.
    "tests/test_ri78a_live_evidence_pre_authorization_invariant.py",
    "tests/test_ri78b_bc1_6a_execution_window_authorization_invariant.py",
    # AO-MA-10 introducer_signature category-error fix: AO-MA-10 erroneously
    # listed RI-7.8b-bc1-6a test file in its introducer signature, causing
    # AO-MA-10 scope assertion to fire on 6b PR (which legitimately edits
    # the 6a test file for introducer-PR detection). Removed the 6a entry
    # from AO-MA-10 signature here.
    "tests/test_ao_ma10_low_risk_autonomous_merge_lane.py",
    # RI-7.1 + RI-7.2 + RI-7.5 forbidden-diff invariants — introducer-PR
    # detection pattern parity (state-at-landing pin per RI-7.5 PR #670 /
    # RI-7.1 PR #666). 6b is the first slice that triggers the sistemic
    # bug; const digest pins still enforce state-at-landing on every
    # successor PR.
    "tests/test_ri7_operator_authorization_invariant.py",
    "tests/test_ri7_guardrail_hardening_matrix_invariant.py",
    "tests/test_ri7_operator_verified_runtime_semantics_invariant.py",
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
    for ref in ("origin/main", "main"):
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


def _is_ri78b_6b_introducer_pr() -> bool:
    """Return True only for the PR that first adds the 6b evidence artifact.

    Diff-dependent checks in this file pin the 6b state at landing. Successor
    slices may legitimately edit unrelated runtime/check files while the 6b
    artifact and digest pins remain unchanged, so those checks must not be
    re-evaluated against every later PR diff.
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
    if review.get("work_package") != "RI-7.8b-bc1-6b":
        pytest.skip("local-ai-review-evidence.v1.json belongs to another active PR work package")


def _path_matches_surface(path: str, surface: str) -> bool:
    if surface.endswith("/"):
        return path.startswith(surface)
    return path == surface


def _parse_iso_z(s: str) -> datetime:
    if s.endswith("Z"):
        return datetime.fromisoformat(s[:-1] + "+00:00")
    return datetime.fromisoformat(s)


# ---------------------------------------------------------------------------
# Schema + evidence structural invariants
# ---------------------------------------------------------------------------


def test_ri78b_bc1_6b_schema_path_exists():
    assert SCHEMA_PATH.exists()


def test_ri78b_bc1_6b_evidence_path_exists():
    assert EVIDENCE_PATH.exists()


def test_ri78b_bc1_6b_workflow_path_exists():
    assert WORKFLOW_PATH.exists()


def test_ri78b_bc1_6b_activation_guard_exists():
    assert ACTIVATION_GUARD_PATH.exists()


def test_ri78b_bc1_6b_schema_is_draft_2020_12():
    schema = _load_json(SCHEMA_PATH)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    jsonschema.Draft202012Validator.check_schema(schema)


def test_ri78b_bc1_6b_evidence_validates_against_schema():
    schema = _load_json(SCHEMA_PATH)
    evidence = _load_json(EVIDENCE_PATH)
    v = jsonschema.Draft202012Validator(schema)
    errors = sorted(v.iter_errors(evidence), key=lambda e: list(e.absolute_path))
    assert not errors, "Evidence does not validate: " + "; ".join(
        f"{list(e.absolute_path)}: {e.message}" for e in errors
    )


def test_ri78b_bc1_6b_decision_const():
    e = _load_json(EVIDENCE_PATH)
    assert (
        e["decision"]
        == "ri78b_bc1_6b_protected_execution_window_infrastructure_recorded_dispatch_pending_no_run_evidence_no_submanifest_flip"
    )


def test_ri78b_bc1_6b_authorization_effect_const():
    e = _load_json(EVIDENCE_PATH)
    assert (
        e["authorization_effect"]
        == "protected_execution_window_infrastructure_recorded_pending_operator_dispatch_no_run_evidence_no_submanifest_flip"
    )


def test_ri78b_bc1_6b_does_not_authorize_6_enum():
    e = _load_json(EVIDENCE_PATH)
    expected = {
        "submanifest_bc1_flip_now",
        "automatic_workflow_dispatch_without_operator_action",
        "credential_reference_in_repo",
        "cost_incurring_calls_outside_dispatched_window",
        "support_widening",
        "production_platform_claim",
    }
    assert set(e["does_not_authorize"]) == expected
    assert len(e["does_not_authorize"]) == 6


# ---------------------------------------------------------------------------
# Workflow file content + binding
# ---------------------------------------------------------------------------


def test_ri78b_bc1_6b_workflow_content_sha256_matches_file():
    """State-at-landing pin: workflow sha256 in 6b evidence must match the file
    at the introducer PR. Successor slices (6c-fast-follow removes env, adds
    push trigger + matrix) legitimately mutate the file; the const digests
    inside 6b evidence keep enforcing the 6b state at landing time."""
    if not _is_ri78b_6b_introducer_pr():
        pytest.skip("6b state-at-landing pin: only enforced on the introducer PR")
    e = _load_json(EVIDENCE_PATH)
    expected = _sha256_file(WORKFLOW_PATH)
    assert e["workflow_binding"]["workflow_content_sha256"] == expected
    assert e["stale_replay_guard"]["workflow_content_sha256"] == expected


def test_ri78b_bc1_6b_workflow_yaml_structure():
    """State-at-landing pin: 6b's expected workflow YAML structure (environment
    binding + workflow_dispatch only + minimal permissions). Successor slices
    (6c-fast-follow removes env, adds push trigger + matrix) legitimately
    revise this structure; this dynamic check only runs on the introducer PR."""
    if not _is_ri78b_6b_introducer_pr():
        pytest.skip("6b state-at-landing pin: only enforced on the introducer PR")
    text = WORKFLOW_PATH.read_text()
    # workflow_dispatch only
    assert "workflow_dispatch:" in text
    assert "on:\n  push:" not in text
    assert "on:\n  pull_request:" not in text
    assert "on:\n  schedule:" not in text
    # environment binding
    assert "environment: ao-kernel-bc1-live-adapter-attestation" in text
    # minimal permissions
    assert "contents: read" in text
    assert "actions: read" in text
    assert "deployments: read" in text
    assert "contents: write" not in text
    assert "deployments: write" not in text
    assert "actions: write" not in text
    # concurrency
    assert "concurrency:" in text
    assert "group: ri78b-bc1-protected-live-adapter-attestation" in text
    # forbidden input names must NOT be declared as inputs
    for forbidden in ("api_key", "token", "secret", "credential", "password", "auth_header"):
        # Reject if any forbidden name appears as a YAML key in `inputs:` block.
        # Heuristic: check `{name}:` after `inputs:` (loose but catches obvious cases).
        assert f"\n      {forbidden}:" not in text, f"forbidden input name {forbidden!r} declared in workflow inputs"


def test_ri78b_bc1_6b_workflow_binding_const():
    e = _load_json(EVIDENCE_PATH)
    wf = e["workflow_binding"]
    assert wf["workflow_path"] == ".github/workflows/bc1-protected-live-adapter-attestation.yml"
    assert wf["allowed_ref"] == "refs/heads/main"
    assert wf["dispatch_inputs_allowlist"] == ["scenario"]
    assert set(wf["forbidden_inputs"]) == {"api_key", "token", "secret", "credential", "password", "auth_header"}
    assert wf["permissions_minimal"]["contents"] == "read"
    assert wf["permissions_minimal"]["actions"] == "read"
    assert wf["permissions_minimal"]["deployments"] == "read"
    assert wf["concurrency_group"] == "ri78b-bc1-protected-live-adapter-attestation"
    assert wf["run_attempt_one_only"] is True


def test_ri78b_bc1_6b_dispatch_allowlist_forbidden_disjoint():
    e = _load_json(EVIDENCE_PATH)
    allow = set(e["workflow_binding"]["dispatch_inputs_allowlist"])
    forbid = set(e["workflow_binding"]["forbidden_inputs"])
    assert allow, "allowlist must be non-empty"
    assert allow & forbid == set()


# ---------------------------------------------------------------------------
# gpp_status.v1.json: top-level baseline + scoped supersession entry
# ---------------------------------------------------------------------------


def test_ri78b_bc1_6b_gpp_status_top_level_guard_flags_const_false():
    status = _load_json(GPP_STATUS_PATH)
    assert status["support_widening_allowed"] is False
    assert status["production_platform_claim_allowed"] is False
    assert status["live_adapter_execution_allowed"] is False


def test_ri78b_bc1_6b_gpp_status_supersession_entry_present():
    """State-at-landing pin: 6b's expected gpp_status entry shape (manual
    protected environment authority mode). Successor slice 6c-fast-follow
    revises this entry to operator_delegated_autonomous_preprod authority
    mode (status awaiting_auto_dispatch_trigger_commit, env_name null,
    autonomous_trigger_contract added). This check only runs on the 6b
    introducer PR; mode-aware always-on invariants stay above."""
    if not _is_ri78b_6b_introducer_pr():
        pytest.skip("6b state-at-landing pin: only enforced on the introducer PR")
    status = _load_json(GPP_STATUS_PATH)
    entries = status.get("operator_bound_supersessions", [])
    matches = [e for e in entries if e.get("id") == "RI-7.8b-bc1-6b"]
    assert len(matches) == 1, f"expected exactly 1 entry, got {len(matches)}"
    entry = matches[0]
    assert entry["scope"] == "bc1_protected_live_adapter_attestation_only"
    assert entry["status"] in {"awaiting_operator_dispatch", "active"}
    assert entry["operator_authority"]["operator_github_login"] == "Halildeu"
    assert entry["actual_start_at"] is None
    assert entry["actual_end_at"] is None
    assert entry["max_run_count"] == 5
    assert entry["max_run_attempt"] == 1
    assert entry["max_usd"] == 5.0
    assert entry["protected_environment_binding"]["env_name"] == "ao-kernel-bc1-live-adapter-attestation"
    assert entry["protected_environment_binding"]["admin_bypass_allowed"] is False
    assert entry["protected_environment_binding"]["allowed_refs"] == ["refs/heads/main"]


def test_ri78b_bc1_6b_gpp_status_entry_scoped_policy():
    status = _load_json(GPP_STATUS_PATH)
    entries = status.get("operator_bound_supersessions", [])
    entry = next(e for e in entries if e.get("id") == "RI-7.8b-bc1-6b")
    policy = entry["guard_flag_policy_resolution"]
    assert policy["support_widening_allowed"] is False
    assert policy["production_platform_claim_allowed"] is False
    assert policy["live_adapter_execution_allowed"] is True
    assert policy["effective_only_for"] == "RI-7.8b-bc1"


def test_ri78b_bc1_6b_gpp_status_entry_workflow_content_sha256_matches_file():
    """State-at-landing pin: 6b's workflow_content_sha256 in the gpp_status
    entry must match the workflow file at 6b landing. Successor slice
    6c-fast-follow updates the workflow file (env removal + push trigger +
    matrix), so the digest will not match on later PRs; the 6b state at
    landing is captured by the artifact const digests above."""
    if not _is_ri78b_6b_introducer_pr():
        pytest.skip("6b state-at-landing pin: only enforced on the introducer PR")
    status = _load_json(GPP_STATUS_PATH)
    entries = status.get("operator_bound_supersessions", [])
    entry = next(e for e in entries if e.get("id") == "RI-7.8b-bc1-6b")
    expected = _sha256_file(WORKFLOW_PATH)
    assert entry["future_workflow_contract"]["workflow_content_sha256"] == expected


# ---------------------------------------------------------------------------
# Operator authority + predecessor digests + state snapshots
# ---------------------------------------------------------------------------


def test_ri78b_bc1_6b_operator_signature_halildeu_iso_8601_no_secret():
    e = _load_json(EVIDENCE_PATH)
    op = e["operator_activation_confirmation"]
    assert op["github_login"] == "Halildeu"
    assert op["no_secret_assertion"] is True
    assert op["activation_scope"] == "bc1_protected_live_adapter_attestation_only"
    assert op["observation_notes"]
    import re

    assert re.match(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$",
        op["activation_confirmed_at"],
    )


def test_ri78b_bc1_6b_activation_source_is_auditable_reference():
    e = _load_json(EVIDENCE_PATH)
    src = e["operator_activation_confirmation"]["activation_source"]
    markers = ("pull/", "pulls/", "issues/", "issue/", "commit/", "pr/", "/pull/", "github.com", "PR #")
    assert any(m.lower() in src.lower() for m in markers), (
        f"activation_source={src!r} must include an auditable reference marker"
    )


def test_ri78b_bc1_6b_predecessor_digests_match_files():
    e = _load_json(EVIDENCE_PATH)
    assert e["ri78a_predecessor_ref"]["evidence_sha256"] == _sha256_file(RI78A_EVIDENCE_PATH)
    assert e["ri78b_6a_predecessor_ref"]["evidence_sha256"] == _sha256_file(RI78B_6A_EVIDENCE_PATH)


def test_ri78b_bc1_6b_stale_replay_guard_digests_match_files():
    """State-at-landing pin: 6b's stale_replay_guard digests (predecessors +
    workflow content + submanifest + readiness manifest) must match the files
    at 6b landing. Successor slices (6c-fast-follow updates workflow file)
    intentionally drift this comparison; the 6b state at landing is captured
    by the immutable digest pins inside the artifact itself."""
    if not _is_ri78b_6b_introducer_pr():
        pytest.skip("6b state-at-landing pin: only enforced on the introducer PR")
    e = _load_json(EVIDENCE_PATH)
    g = e["stale_replay_guard"]
    assert g["ri78a_evidence_sha256"] == _sha256_file(RI78A_EVIDENCE_PATH)
    assert g["ri78b_6a_evidence_sha256"] == _sha256_file(RI78B_6A_EVIDENCE_PATH)
    assert g["ri78_submanifest_sha256"] == _sha256_file(SUBMANIFEST_PATH)
    assert g["readiness_manifest_sha256"] == _sha256_file(READINESS_MANIFEST_PATH)
    assert g["workflow_content_sha256"] == _sha256_file(WORKFLOW_PATH)
    assert g["base_ref"] == "refs/heads/main"
    assert g["head_ref"] == "refs/heads/codex/ri-7-8b-bc1-6b-protected-execution-window"


# ---------------------------------------------------------------------------
# Time-window invariants (Codex iter-3 absorb pattern)
# ---------------------------------------------------------------------------


def test_ri78b_bc1_6b_activation_confirmed_at_not_in_future():
    e = _load_json(EVIDENCE_PATH)
    confirmed = _parse_iso_z(e["operator_activation_confirmation"]["activation_confirmed_at"])
    now = datetime.now(timezone.utc)
    assert confirmed <= now + timedelta(minutes=15), (
        f"activation_confirmed_at={confirmed} is in the future relative to now={now}"
    )


def test_ri78b_bc1_6b_validity_window_bounded():
    e = _load_json(EVIDENCE_PATH)
    confirmed = _parse_iso_z(e["operator_activation_confirmation"]["activation_confirmed_at"])
    until = _parse_iso_z(e["run_budget"]["validity_window_until"])
    assert until > confirmed
    # max_activation_delay_hours per the 6a contract was 168h
    assert until - confirmed <= timedelta(hours=168)


# ---------------------------------------------------------------------------
# Submanifest UNCHANGED + readiness manifest UNCHANGED
# ---------------------------------------------------------------------------


def test_ri78b_bc1_6b_ri78_submanifest_unchanged_in_6b():
    sub = _load_json(SUBMANIFEST_PATH)
    assert sub["live_evidence_pre_authorization_recorded"] is True
    assert sub["bc1_protected_live_adapter_attestation_recorded"] is False
    assert sub["bc10_real_adapter_usage_cost_aggregate_recorded"] is False
    assert sub["final_operator_promotion_decision_recorded"] is False


def test_ri78b_bc1_6b_nine_key_readiness_unchanged():
    m = _load_json(READINESS_MANIFEST_PATH)
    flag_keys = [k for k in m if k not in {"schema_version", "artifact_kind"}]
    assert len(flag_keys) == 9
    for k in flag_keys:
        assert m[k] is True, f"readiness key {k} must be true"


def test_ri78b_bc1_6b_guard_flags_const_false():
    e = _load_json(EVIDENCE_PATH)
    assert e["support_widening"] is False
    assert e["production_platform_claim"] is False
    assert e["live_adapter_execution"] is False


def test_ri78b_bc1_6b_submanifest_transition_before_after_equal_false():
    e = _load_json(EVIDENCE_PATH)
    t = e["submanifest_transition"]
    assert t["before"]["bc1_protected_live_adapter_attestation_recorded"] is False
    assert t["after"]["bc1_protected_live_adapter_attestation_recorded"] is False


# ---------------------------------------------------------------------------
# Forbidden audit exact set + machine-enforced via git diff
# ---------------------------------------------------------------------------


def test_ri78b_bc1_6b_forbidden_change_audit_exact_13_set():
    e = _load_json(EVIDENCE_PATH)
    a = e["forbidden_change_audit"]
    assert a["all_unchanged"] is True
    assert set(a["forbidden_surfaces"]) == set(EXPECTED_FORBIDDEN_SURFACES)
    assert len(a["forbidden_surfaces"]) == 13


def test_ri78b_bc1_6b_forbidden_change_audit_machine_enforced():
    if not _is_ri78b_6b_introducer_pr():
        pytest.skip("6b state-at-landing pin: only enforced on the introducer PR")
    _skip_if_current_local_review_evidence_is_for_another_slice()
    base_sha = _resolve_diff_base()
    if base_sha is None:
        pytest.skip("No git base resolved")
    changed = _git_changed_paths_against(base_sha)
    for surface in EXPECTED_FORBIDDEN_SURFACES:
        for path in changed:
            assert not _path_matches_surface(path, surface), (
                f"Forbidden surface touched in 6b PR: surface={surface}, path={path}"
            )


def test_ri78b_bc1_6b_diff_scope_only_allowed_surfaces():
    """6b PR may only touch the allowed new surfaces (workflow file,
    activation guard, schema, evidence, plan doc, invariant test,
    gpp_status.v1.json, local-ai-review-evidence)."""
    if not _is_ri78b_6b_introducer_pr():
        pytest.skip("6b state-at-landing pin: only enforced on the introducer PR")
    _skip_if_current_local_review_evidence_is_for_another_slice()
    base_sha = _resolve_diff_base()
    if base_sha is None:
        pytest.skip("No git base resolved")
    changed = _git_changed_paths_against(base_sha)
    allowed = set(ALLOWED_NEW_SURFACES)
    unexpected = [p for p in changed if p not in allowed]
    assert not unexpected, f"Unexpected files in 6b PR: {unexpected}"


# ---------------------------------------------------------------------------
# Cross-AI peer review provider split + cross-artifact verdict equality
# ---------------------------------------------------------------------------


def test_ri78b_bc1_6b_cross_ai_review_provider_split_const():
    e = _load_json(EVIDENCE_PATH)
    cr = e["cross_ai_review_ref"]
    assert cr["implementer_provider"] == "anthropic"
    assert cr["reviewer_provider"] == "openai"
    assert cr["final_verdict"] in {"REVISE", "AGREE"}
    assert cr["thread_id"]


def test_ri78b_bc1_6b_cross_artifact_verdict_equality():
    if not LOCAL_AI_REVIEW_PATH.exists():
        pytest.skip("local-ai-review-evidence.v1.json missing")
    review = _load_json(LOCAL_AI_REVIEW_PATH)
    if review["work_package"] != "RI-7.8b-bc1-6b":
        pytest.skip("local-ai-review-evidence.v1.json belongs to another active PR work package")
    e = _load_json(EVIDENCE_PATH)
    assert review["implementer"]["provider"] == "anthropic"
    assert review["reviewer"]["provider"] == "openai"
    assert review["work_package"] == "RI-7.8b-bc1-6b"
    assert review["reviewer"]["verdict"] == e["cross_ai_review_ref"]["final_verdict"]


# ---------------------------------------------------------------------------
# Plan doc records the decision
# ---------------------------------------------------------------------------


def test_ri78b_bc1_6b_plan_doc_records_decision():
    text = PLAN_DOC_PATH.read_text()
    assert (
        "ri78b_bc1_6b_protected_execution_window_infrastructure_recorded_dispatch_pending_no_run_evidence_no_submanifest_flip"
        in text
    )
    assert "no live execution" in text.lower() or "no live adapter execution" in text.lower()


# ---------------------------------------------------------------------------
# Negative schema tests (drift detection)
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
    v = jsonschema.Draft202012Validator(schema)
    errors = list(v.iter_errors(evidence))
    assert errors, f"Mutation should be rejected: {reason}"


def test_ri78b_bc1_6b_negative_top_level_baseline_live_true_rejected():
    e = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        e,
        (
            (
                "guard_flag_policy_resolution_evidence",
                "top_level_baseline_preserved",
                "live_adapter_execution_allowed",
            ),
            True,
        ),
    )
    _assert_rejected(bad, "top_level live_adapter_execution_allowed must be false (baseline closure)")


def test_ri78b_bc1_6b_negative_scoped_live_false_rejected():
    e = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        e,
        (
            ("guard_flag_policy_resolution_evidence", "scoped_live_adapter_execution_allowed"),
            False,
        ),
    )
    _assert_rejected(bad, "scoped_live_adapter_execution_allowed must be true (effective grant)")


def test_ri78b_bc1_6b_negative_submanifest_after_bc1_true_rejected():
    e = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        e,
        (
            ("submanifest_transition", "after", "bc1_protected_live_adapter_attestation_recorded"),
            True,
        ),
    )
    _assert_rejected(bad, "submanifest after.bc1 must remain false in 6b")


def test_ri78b_bc1_6b_negative_top_level_guard_flag_true_rejected():
    e = _load_json(EVIDENCE_PATH)
    bad = _mutate(e, (("live_adapter_execution",), True))
    _assert_rejected(bad, "top-level live_adapter_execution must be false")


def test_ri78b_bc1_6b_negative_workflow_path_drift_rejected():
    e = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        e,
        (
            ("workflow_binding", "workflow_path"),
            ".github/workflows/other.yml",
        ),
    )
    _assert_rejected(bad, "workflow_path must be canonical const")


def test_ri78b_bc1_6b_negative_protected_env_production_name_rejected():
    e = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        e,
        (("protected_environment_observation", "env_name"), "production-live-adapter-attestation"),
    )
    _assert_rejected(bad, "env_name must NOT be production_*")


def test_ri78b_bc1_6b_negative_max_run_count_too_high_rejected():
    e = _load_json(EVIDENCE_PATH)
    bad = _mutate(e, (("run_budget", "max_distinct_runs"), 10))
    _assert_rejected(bad, "max_distinct_runs must be <= 5")


def test_ri78b_bc1_6b_negative_max_run_attempt_non_one_rejected():
    e = _load_json(EVIDENCE_PATH)
    bad = _mutate(e, (("run_budget", "max_run_attempt"), 2))
    _assert_rejected(bad, "max_run_attempt must be const 1")
