"""Invariant tests for RI-7.8b-bc1-6c-fast-follow autonomous pre-prod activation.

Enforces:
- Schema strictness (Draft 2020-12, additionalProperties=false, const pins)
- Evidence validates against schema
- workflow_content_sha256 + trigger_schema_sha256 match actual files
- gpp_status entry transition: authority_mode + manual_approval_required + status
- Trigger file ABSENT in this PR (delayed-effect deferred to 6c-closure)
- Trigger schema present + valid Draft 2020-12
- Activation guard script mode-aware (manual_protected_environment +
  operator_delegated_autonomous_preprod)
- 9-key readiness UNCHANGED + RI-7.8 submanifest UNCHANGED
- forbidden_change_audit exact 13 surfaces
- Predecessor digests (RI-7.8a + RI-7.8b-bc1-6a + RI-7.8b-bc1-6b)
- Cross-AI peer review provider split const
- Bounded-window limits preserved (max 5 runs / max $5 / max 24h / run_attempt==1)
- Workflow YAML structural: env removed, push trigger added, matrix added,
  workflow_dispatch fallback retained
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
    / "ri7-8b-bc1-6c-fast-follow-autonomous-preprod-evidence.schema.v1.json"
)
EVIDENCE_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8b-bc1-6c-fast-follow-AUTONOMOUS-PREPROD.v1.json"
PLAN_DOC_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8b-bc1-6c-fast-follow-AUTONOMOUS-PREPROD.md"
TRIGGER_SCHEMA_PATH = REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ri7-8b-bc1-6c-dispatch-trigger.schema.v1.json"
TRIGGER_FILE_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8b-bc1-6c-DISPATCH-TRIGGER.v1.json"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "bc1-protected-live-adapter-attestation.yml"
ACTIVATION_GUARD_PATH = REPO_ROOT / "scripts" / "ri78b_bc1_activation_window.py"
SUBMANIFEST_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8-EVIDENCE-MANIFEST.v1.json"
READINESS_MANIFEST_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7-EVIDENCE-MANIFEST.v1.json"
RI78A_EVIDENCE_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8a-LIVE-EVIDENCE-PRE-AUTHORIZATION.v1.json"
RI78B_6A_EVIDENCE_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8b-bc1-6a-EXECUTION-WINDOW-AUTHORIZATION.v1.json"
RI78B_6B_EVIDENCE_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8b-bc1-6b-PROTECTED-EXECUTION-WINDOW.v1.json"
GPP_STATUS_PATH = REPO_ROOT / ".claude" / "plans" / "gpp_status.v1.json"
LOCAL_AI_REVIEW_PATH = REPO_ROOT / "local-ai-review-evidence.v1.json"

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


def _is_ri78b_6c_fast_follow_introducer_pr() -> bool:
    """Return True only for the PR that first adds the 6c-fast-follow
    evidence artifact (the introducer PR).

    Diff-dependent checks below (workflow SHA, trigger schema SHA,
    trigger-file-absent) pin the 6c-fast-follow state at landing.
    Successor PRs may legitimately edit the workflow and create the
    trigger file (6c-trigger PR) while the 6c-fast-follow evidence and
    digest pins remain unchanged at state-at-landing. Pattern parity
    with RI-7.1, RI-7.2, RI-7.5, RI-7.8a, RI-7.8b-bc1-6a/6b and
    AO-MA-10 runtime introducer-PR detection.
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


def _path_matches_surface(path: str, surface: str) -> bool:
    if surface.endswith("/"):
        return path.startswith(surface)
    return path == surface


# ---------------------------------------------------------------------------
# Schema + evidence validation
# ---------------------------------------------------------------------------


def test_6c_fast_follow_schema_path_exists():
    assert SCHEMA_PATH.exists()


def test_6c_fast_follow_evidence_path_exists():
    assert EVIDENCE_PATH.exists()


def test_6c_fast_follow_trigger_schema_exists():
    assert TRIGGER_SCHEMA_PATH.exists()


def test_6c_fast_follow_trigger_file_absent_in_this_pr():
    """Trigger file (delayed-effect execution surface) MUST be absent in this
    PR. Its creation belongs to RI-7.8b-bc1-6c-trigger (PR-A of the two-PR
    split, per Codex thread 019e702f iter-2) alongside the workflow
    hardening; per-run evidence + closure proof + BC-1 flip belong to
    RI-7.8b-bc1-6c-closure (PR-B). Introducer-only skip: this scope
    invariant applies to the 6c-fast-follow introducer PR; the 6c-trigger
    successor PR legitimately creates the file."""
    if not _is_ri78b_6c_fast_follow_introducer_pr():
        pytest.skip(
            "6c-fast-follow evidence MODIFIED (not ADDED) in this diff; "
            "state-at-landing pin applies; introducer-only scope check skipped"
        )
    assert not TRIGGER_FILE_PATH.exists(), (
        f"Trigger file must NOT exist in 6c-fast-follow PR (deferred to 6c-trigger): {TRIGGER_FILE_PATH}"
    )


def test_6c_fast_follow_schema_is_draft_2020_12():
    schema = _load_json(SCHEMA_PATH)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    jsonschema.Draft202012Validator.check_schema(schema)


def test_6c_fast_follow_trigger_schema_is_draft_2020_12():
    schema = _load_json(TRIGGER_SCHEMA_PATH)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    jsonschema.Draft202012Validator.check_schema(schema)


def test_6c_fast_follow_evidence_validates_against_schema():
    schema = _load_json(SCHEMA_PATH)
    evidence = _load_json(EVIDENCE_PATH)
    v = jsonschema.Draft202012Validator(schema)
    errors = sorted(v.iter_errors(evidence), key=lambda e: list(e.absolute_path))
    assert not errors, "Evidence does not validate: " + "; ".join(
        f"{list(e.absolute_path)}: {e.message}" for e in errors
    )


ALLOWED_NEW_SURFACES_PR = [
    # Core 6c-fast-follow scope (9)
    ".claude/plans/RI-7.8b-bc1-6c-fast-follow-AUTONOMOUS-PREPROD.md",
    ".claude/plans/RI-7.8b-bc1-6c-fast-follow-AUTONOMOUS-PREPROD.v1.json",
    ".claude/plans/gpp_status.v1.json",
    ".github/workflows/bc1-protected-live-adapter-attestation.yml",
    "ao_kernel/defaults/schemas/ri7-8b-bc1-6c-dispatch-trigger.schema.v1.json",
    "ao_kernel/defaults/schemas/ri7-8b-bc1-6c-fast-follow-autonomous-preprod-evidence.schema.v1.json",
    "local-ai-review-evidence.v1.json",
    "scripts/ri78b_bc1_activation_window.py",
    "tests/test_ri78b_bc1_6c_fast_follow_invariant.py",
    # Systemic 6b state-at-landing introducer-only pin fix
    "tests/test_ri78b_bc1_6b_protected_execution_window_invariant.py",
]


def test_6c_fast_follow_decision_const():
    e = _load_json(EVIDENCE_PATH)
    assert (
        e["decision"] == "ri78b_bc1_6c_fast_follow_autonomous_preprod_contract_revised_no_trigger_file_no_run_evidence"
    )


def test_6c_fast_follow_authority_mode_revision():
    e = _load_json(EVIDENCE_PATH)
    rev = e["authority_mode_revision"]
    assert rev["from_mode"] == "manual_protected_environment"
    assert rev["to_mode"] == "operator_delegated_autonomous_preprod"
    assert rev["manual_approval_required"] is False
    assert rev["code_level_guard_only"] is True


# ---------------------------------------------------------------------------
# Workflow file structural checks
# ---------------------------------------------------------------------------


def test_6c_fast_follow_workflow_content_sha256_matches_file():
    """Dynamic SHA compare runs only on the 6c-fast-follow introducer PR.
    Successor PRs (e.g., 6c-trigger) legitimately update the workflow
    while the 6c-fast-follow evidence file's stored SHA pins the
    state-at-landing fact. Pattern parity with introducer-PR detection
    landed in PR #687 (AO-MA-10 runtime)."""
    if not _is_ri78b_6c_fast_follow_introducer_pr():
        pytest.skip(
            "6c-fast-follow evidence MODIFIED (not ADDED) in this diff; "
            "state-at-landing pin applies; dynamic workflow SHA compare skipped"
        )
    e = _load_json(EVIDENCE_PATH)
    actual = _sha256_file(WORKFLOW_PATH)
    assert e["workflow_changes"]["workflow_content_sha256"] == actual
    assert e["stale_replay_guard"]["workflow_content_sha256"] == actual


def test_6c_fast_follow_workflow_yaml_environment_removed():
    text = WORKFLOW_PATH.read_text()
    # The active `environment: ` job binding MUST be absent. (Comments/docstrings
    # may reference "environment" as a word.)
    assert "    environment: ao-kernel-bc1-live-adapter-attestation" not in text, (
        "workflow file MUST NOT contain the 6b protected environment binding"
    )


def test_6c_fast_follow_workflow_yaml_push_trigger_added():
    text = WORKFLOW_PATH.read_text()
    assert "  push:" in text
    assert "branches: [main]" in text
    assert "RI-7.8b-bc1-6c-DISPATCH-TRIGGER.v1.json" in text


def test_6c_fast_follow_workflow_yaml_matrix_added():
    text = WORKFLOW_PATH.read_text()
    assert "strategy:" in text
    assert "matrix:" in text
    assert "scenario:" in text
    assert "clean_attestation" in text
    assert "fail_closed_attestation" in text


def test_6c_fast_follow_workflow_yaml_workflow_dispatch_retained():
    text = WORKFLOW_PATH.read_text()
    assert "workflow_dispatch:" in text


def test_6c_fast_follow_trigger_schema_sha256_matches_file():
    e = _load_json(EVIDENCE_PATH)
    actual = _sha256_file(TRIGGER_SCHEMA_PATH)
    assert e["trigger_schema_pinned"]["schema_content_sha256"] == actual
    assert e["stale_replay_guard"]["trigger_schema_sha256"] == actual


# ---------------------------------------------------------------------------
# gpp_status entry: authority_mode + status + autonomous_trigger_contract
# ---------------------------------------------------------------------------


def test_6c_fast_follow_gpp_status_top_level_guard_const_false():
    s = _load_json(GPP_STATUS_PATH)
    assert s["support_widening_allowed"] is False
    assert s["production_platform_claim_allowed"] is False
    assert s["live_adapter_execution_allowed"] is False


def test_6c_fast_follow_gpp_status_supersession_entry_authority_mode():
    s = _load_json(GPP_STATUS_PATH)
    entries = s.get("operator_bound_supersessions", [])
    entry = next(e for e in entries if e.get("id") == "RI-7.8b-bc1-6b")
    assert entry["authority_mode"] == "operator_delegated_autonomous_preprod"
    assert entry["manual_approval_required"] is False
    assert entry["status"] == "awaiting_auto_dispatch_trigger_commit"
    assert entry["protected_environment_binding"]["mode"] == "code_level_only_preprod"
    assert entry["protected_environment_binding"]["env_name"] is None
    assert entry["protected_environment_binding"]["required"] is False
    assert (
        entry["autonomous_trigger_contract"]["trigger_file_path"]
        == ".claude/plans/RI-7.8b-bc1-6c-DISPATCH-TRIGGER.v1.json"
    )
    assert entry["autonomous_trigger_contract"]["operator_github_login"] == "Halildeu"


# ---------------------------------------------------------------------------
# Activation guard mode-aware
# ---------------------------------------------------------------------------


def test_6c_fast_follow_activation_guard_mode_aware():
    text = ACTIVATION_GUARD_PATH.read_text()
    assert "authority_mode" in text
    assert "manual_protected_environment" in text
    assert "operator_delegated_autonomous_preprod" in text
    assert "awaiting_auto_dispatch_trigger_commit" in text


# ---------------------------------------------------------------------------
# Predecessor digests
# ---------------------------------------------------------------------------


def test_6c_fast_follow_predecessor_digests_match_files():
    e = _load_json(EVIDENCE_PATH)
    assert e["ri78a_predecessor_ref"]["evidence_sha256"] == _sha256_file(RI78A_EVIDENCE_PATH)
    assert e["ri78b_6a_predecessor_ref"]["evidence_sha256"] == _sha256_file(RI78B_6A_EVIDENCE_PATH)
    assert e["ri78b_6b_predecessor_ref"]["evidence_sha256"] == _sha256_file(RI78B_6B_EVIDENCE_PATH)


# ---------------------------------------------------------------------------
# State snapshots
# ---------------------------------------------------------------------------


def test_6c_fast_follow_submanifest_unchanged():
    sub = _load_json(SUBMANIFEST_PATH)
    assert sub["live_evidence_pre_authorization_recorded"] is True
    assert sub["bc1_protected_live_adapter_attestation_recorded"] is False
    assert sub["bc10_real_adapter_usage_cost_aggregate_recorded"] is False
    assert sub["final_operator_promotion_decision_recorded"] is False


def test_6c_fast_follow_readiness_unchanged():
    m = _load_json(READINESS_MANIFEST_PATH)
    flag_keys = [k for k in m if k not in {"schema_version", "artifact_kind"}]
    assert len(flag_keys) == 9
    for k in flag_keys:
        assert m[k] is True


def test_6c_fast_follow_guard_flags_const_false():
    e = _load_json(EVIDENCE_PATH)
    assert e["support_widening"] is False
    assert e["production_platform_claim"] is False
    assert e["live_adapter_execution"] is False


def test_6c_fast_follow_bounded_window_limits_preserved():
    e = _load_json(EVIDENCE_PATH)
    b = e["bounded_window_limits_preserved"]
    assert b["max_distinct_runs"] == 5
    assert b["max_run_attempt"] == 1
    assert b["max_usd"] == 5.00
    assert b["max_duration_hours"] == 24


def test_6c_fast_follow_submanifest_transition_before_after_equal_false():
    e = _load_json(EVIDENCE_PATH)
    t = e["submanifest_transition"]
    assert t["before"]["bc1_protected_live_adapter_attestation_recorded"] is False
    assert t["after"]["bc1_protected_live_adapter_attestation_recorded"] is False


# ---------------------------------------------------------------------------
# Forbidden audit
# ---------------------------------------------------------------------------


def test_6c_fast_follow_forbidden_change_audit_exact_13_set():
    e = _load_json(EVIDENCE_PATH)
    a = e["forbidden_change_audit"]
    assert a["all_unchanged"] is True
    assert set(a["forbidden_surfaces"]) == set(EXPECTED_FORBIDDEN_SURFACES)


def test_6c_fast_follow_forbidden_change_audit_machine_enforced():
    base_sha = _resolve_diff_base()
    if base_sha is None:
        pytest.skip("No git base resolved")
    changed = _git_changed_paths_against(base_sha)
    for surface in EXPECTED_FORBIDDEN_SURFACES:
        for path in changed:
            assert not _path_matches_surface(path, surface), (
                f"Forbidden surface touched in 6c-fast-follow: surface={surface}, path={path}"
            )


# ---------------------------------------------------------------------------
# Cross-AI peer review
# ---------------------------------------------------------------------------


def test_6c_fast_follow_cross_ai_review_provider_split_const():
    e = _load_json(EVIDENCE_PATH)
    cr = e["cross_ai_review_ref"]
    assert cr["implementer_provider"] == "anthropic"
    assert cr["reviewer_provider"] == "openai"
    assert cr["final_verdict"] in {"REVISE", "AGREE"}


def test_6c_fast_follow_cross_artifact_verdict_equality():
    if not LOCAL_AI_REVIEW_PATH.exists():
        pytest.skip("local-ai-review-evidence missing")
    review = _load_json(LOCAL_AI_REVIEW_PATH)
    if review.get("work_package") != "RI-7.8b-bc1-6c-fast-follow":
        pytest.skip("local-ai-review-evidence belongs to another work package")
    e = _load_json(EVIDENCE_PATH)
    assert review["implementer"]["provider"] == "anthropic"
    assert review["reviewer"]["provider"] == "openai"
    assert review["work_package"] == "RI-7.8b-bc1-6c-fast-follow"
    assert review["reviewer"]["verdict"] == e["cross_ai_review_ref"]["final_verdict"]


# ---------------------------------------------------------------------------
# Plan doc
# ---------------------------------------------------------------------------


def test_6c_fast_follow_plan_doc_records_decision():
    text = PLAN_DOC_PATH.read_text()
    assert "ri78b_bc1_6c_fast_follow_autonomous_preprod_contract_revised_no_trigger_file_no_run_evidence" in text
    assert "operator_delegated_autonomous_preprod" in text


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
    v = jsonschema.Draft202012Validator(schema)
    errors = list(v.iter_errors(evidence))
    assert errors, f"Mutation should be rejected: {reason}"


def test_6c_fast_follow_negative_to_mode_drift_rejected():
    e = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        e,
        (
            ("authority_mode_revision", "to_mode"),
            "manual_protected_environment",
        ),
    )
    _assert_rejected(bad, "to_mode must be operator_delegated_autonomous_preprod")


def test_6c_fast_follow_negative_manual_approval_true_rejected():
    e = _load_json(EVIDENCE_PATH)
    bad = _mutate(e, (("authority_mode_revision", "manual_approval_required"), True))
    _assert_rejected(bad, "manual_approval_required must be false")


def test_6c_fast_follow_negative_bounded_limit_relaxation_rejected():
    e = _load_json(EVIDENCE_PATH)
    bad = _mutate(e, (("bounded_window_limits_preserved", "max_distinct_runs"), 10))
    _assert_rejected(bad, "max_distinct_runs must be const 5")


def test_6c_fast_follow_negative_submanifest_after_bc1_true_rejected():
    e = _load_json(EVIDENCE_PATH)
    bad = _mutate(
        e,
        (
            (
                "submanifest_transition",
                "after",
                "bc1_protected_live_adapter_attestation_recorded",
            ),
            True,
        ),
    )
    _assert_rejected(bad, "submanifest after.bc1 must be false in 6c-fast-follow")


def test_6c_fast_follow_negative_top_level_live_adapter_execution_true_rejected():
    e = _load_json(EVIDENCE_PATH)
    bad = _mutate(e, (("live_adapter_execution",), True))
    _assert_rejected(bad, "live_adapter_execution must be false")
