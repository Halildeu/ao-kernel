"""Doc invariant test for RI-7.8a operator live-evidence pre-authorization evidence.

B-path slice 5 of 8 (after slice-3 RI-7.5 MERGED + slice-4 checkpoint).
Pre-authorization scope record only — NO execution permission, NO guard
flag flip. Pins schema strictness, negative authority enumeration,
submanifest transition, 14-surface forbidden audit, current-state
snapshots, and cross-AI peer-review provider split + cross-artifact
verdict equality.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import jsonschema
import pytest


_REPO_ROOT = Path(__file__).resolve().parents[1]
_PLAN_PATH = _REPO_ROOT / ".claude" / "plans" / "RI-7.8a-LIVE-EVIDENCE-PRE-AUTHORIZATION.md"
_EVIDENCE_PATH = _REPO_ROOT / ".claude" / "plans" / "RI-7.8a-LIVE-EVIDENCE-PRE-AUTHORIZATION.v1.json"
_SCHEMA_PATH = (
    _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ri7-8a-live-evidence-pre-authorization-evidence.schema.v1.json"
)
_SUBMANIFEST_PATH = _REPO_ROOT / ".claude" / "plans" / "RI-7.8-EVIDENCE-MANIFEST.v1.json"
_READINESS_MANIFEST_PATH = _REPO_ROOT / ".claude" / "plans" / "RI-7-EVIDENCE-MANIFEST.v1.json"
_GPP_STATUS_PATH = _REPO_ROOT / ".claude" / "plans" / "gpp_status.v1.json"


def _read(path: Path) -> str:
    assert path.exists(), f"missing artifact: {path}"
    return path.read_text(encoding="utf-8")


def test_ri78a_schema_is_valid_draft_2020_12() -> None:
    schema = json.loads(_read(_SCHEMA_PATH))
    jsonschema.Draft202012Validator.check_schema(schema)


def test_ri78a_evidence_validates_against_schema() -> None:
    schema = json.loads(_read(_SCHEMA_PATH))
    evidence = json.loads(_read(_EVIDENCE_PATH))
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(evidence))
    assert errors == [], [e.message for e in errors]


def test_ri78a_decision_pins_pre_authorization_no_execution() -> None:
    evidence = json.loads(_read(_EVIDENCE_PATH))
    assert evidence["artifact_kind"] == "ri7_8a_live_evidence_pre_authorization_evidence"
    assert evidence["decision"] == ("ri78a_live_evidence_pre_authorization_recorded_no_guard_flag_flip_no_execution")
    assert evidence["authorization_effect"] == "pre_authorization_only_no_execution_permission"


def test_ri78a_negative_authority_seven_forbidden_actions_enumerated() -> None:
    evidence = json.loads(_read(_EVIDENCE_PATH))
    does_not = set(evidence["does_not_authorize"])
    assert does_not == {
        "protected_workflow_dispatch",
        "adapter_execution",
        "credential_reference",
        "cost_incurring_calls",
        "support_widening",
        "production_platform_claim",
        "gpp_status_guard_flip",
    }


def test_ri78a_operator_signature_fields() -> None:
    evidence = json.loads(_read(_EVIDENCE_PATH))
    operator = evidence["operator"]
    assert operator["github_login"] == "Halildeu"
    assert operator["no_secret_assertion"] is True
    assert operator["observation_notes"]
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z",
        operator["pre_authorization_timestamp"],
    )


def test_ri78a_guard_flags_const_false() -> None:
    evidence = json.loads(_read(_EVIDENCE_PATH))
    assert evidence["support_widening"] is False
    assert evidence["production_platform_claim"] is False
    assert evidence["live_adapter_execution"] is False
    snap = evidence["current_gpp_guard_snapshot"]
    assert snap["support_widening_allowed"] is False
    assert snap["production_platform_claim_allowed"] is False
    assert snap["live_adapter_execution_allowed"] is False


def test_ri78a_current_readiness_snapshot_pins_9_9_true() -> None:
    evidence = json.loads(_read(_EVIDENCE_PATH))
    snap = evidence["current_readiness_snapshot"]
    assert snap["nine_key_manifest_all_true"] is True
    assert snap["readiness_gate_decision"] == "ready_for_operator_promotion_decision"
    assert snap["operator_verified_runtime_semantics"] is True
    assert snap["explicit_operator_authorization"] is True
    assert snap["general_purpose_platform_claim_authorization"] is True


def test_ri78a_successor_slices_pinned_two() -> None:
    evidence = json.loads(_read(_EVIDENCE_PATH))
    assert set(evidence["successor_slices"]) == {"RI-7.8b-bc1", "RI-7.8b-bc10"}


def test_ri78a_bc_scope_structured_two_bcs() -> None:
    evidence = json.loads(_read(_EVIDENCE_PATH))
    bc_scope = evidence["bc_scope"]
    bc1 = bc_scope["bc_1_protected_gate_attestation"]
    assert bc1["owner_slice"] == "RI-7.8b-bc1"
    assert bc1["max_run_count"] >= 1 and bc1["max_run_count"] <= 5
    assert bc1["protected_environment_required"] is True
    assert set(bc1["expected_paths"]) == {"clean_attestation", "fail_closed_attestation"}
    bc10 = bc_scope["bc_10_real_adapter_usage_cost"]
    assert bc10["owner_slice"] == "RI-7.8b-bc10"
    assert bc10["spend_ledger_binding_required"] is True


def test_ri78a_execution_budget_bounded() -> None:
    evidence = json.loads(_read(_EVIDENCE_PATH))
    budget = evidence["execution_budget"]
    assert budget["max_calls_per_bc"] <= 50
    assert budget["max_usd_per_bc"] <= 5.00
    assert budget["max_usd_aggregate"] <= 10.00
    assert budget["validity_window_hours"] <= 168
    assert len(budget["model_allowlist"]) >= 1


def test_ri78a_submanifest_transition_pinned() -> None:
    evidence = json.loads(_read(_EVIDENCE_PATH))
    transition = evidence["submanifest_transition"]
    assert transition["before"]["live_evidence_pre_authorization_recorded"] is False
    assert transition["after"]["live_evidence_pre_authorization_recorded"] is True


def test_ri78a_submanifest_flips_pre_authorization_recorded_only() -> None:
    """The committed RI-7.8 submanifest flips ONLY
    `live_evidence_pre_authorization_recorded` to true. Other three keys
    (bc1, bc10, final_promotion) remain false — owned by later slices.
    """
    sub = json.loads(_read(_SUBMANIFEST_PATH))
    assert sub["artifact_kind"] == "ri78_evidence_submanifest"
    assert sub["live_evidence_pre_authorization_recorded"] is True
    assert sub["bc1_protected_live_adapter_attestation_recorded"] is False
    assert sub["bc10_real_adapter_usage_cost_aggregate_recorded"] is False
    assert sub["final_operator_promotion_decision_recorded"] is False


def test_ri78a_nine_key_readiness_manifest_unchanged_all_true() -> None:
    """The 9-key RI-7 readiness manifest stays at 9/9 true. RI-7.8a
    sequencing belongs to the SEPARATE submanifest (`RI-7.8-EVIDENCE-MANIFEST.v1.json`),
    not the readiness manifest.
    """
    manifest = json.loads(_read(_READINESS_MANIFEST_PATH))
    assert manifest["artifact_kind"] == "ri7_evidence_manifest"
    keys = (
        "explicit_operator_authorization",
        "general_purpose_platform_claim_authorization",
        "guardrail_hardening_matrix",
        "vector_backend_e2e_evidence",
        "scan_index_query_packaging_smoke",
        "operator_verified_runtime_semantics",
        "cross_lane_production_matrix_evidence",
        "gp59_reclassification_plan",
        "support_boundary_transition_plan",
    )
    for k in keys:
        assert manifest[k] is True, f"readiness manifest key {k} not true; RI-7.8a must not touch it"


def test_ri78a_gpp_status_untouched_guard_flags_false() -> None:
    """RI-7.8a does NOT mutate gpp_status.v1.json. Guard flags
    (support_widening_allowed, production_platform_claim_allowed,
    live_adapter_execution_allowed) remain false.
    """
    gpp = json.loads(_read(_GPP_STATUS_PATH))
    # Best-effort flat search; gpp_status carries flags either at top-level
    # or under `invariants`. Test both placements without assuming shape.
    flat = json.dumps(gpp)
    assert '"support_widening_allowed": false' in flat or '"support_widening_allowed":false' in flat
    assert '"production_platform_claim_allowed": false' in flat or '"production_platform_claim_allowed":false' in flat
    assert '"live_adapter_execution_allowed": false' in flat or '"live_adapter_execution_allowed":false' in flat


def test_ri78a_forbidden_change_audit_fourteen_surfaces_pinned() -> None:
    evidence = json.loads(_read(_EVIDENCE_PATH))
    audit = evidence["forbidden_change_audit"]
    assert audit["all_unchanged"] is True
    surfaces = set(audit["forbidden_surfaces"])
    for required in (
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
    ):
        assert required in surfaces, required


def test_ri78a_cross_ai_provider_split_recorded() -> None:
    evidence = json.loads(_read(_EVIDENCE_PATH))
    ref = evidence["cross_ai_review_ref"]
    assert ref["implementer_provider"] == "anthropic"
    assert ref["reviewer_provider"] == "openai"
    assert ref["implementer_provider"] != ref["reviewer_provider"]
    assert ref["final_verdict"] in {"REVISE", "AGREE"}
    assert ref["thread_id"]


def test_ri78a_cross_ai_verdicts_match_review_evidence() -> None:
    """RI-7.8a evidence `cross_ai_review_ref.final_verdict` MUST equal
    `local-ai-review-evidence.v1.json::reviewer.verdict`. Cross-artifact
    drift = blocker.
    """
    evidence = json.loads(_read(_EVIDENCE_PATH))
    review_path = _REPO_ROOT / "local-ai-review-evidence.v1.json"
    review = json.loads(_read(review_path))
    auth_verdict = evidence["cross_ai_review_ref"]["final_verdict"]
    review_verdict = review["reviewer"]["verdict"]
    assert auth_verdict == review_verdict, (
        f"verdict drift: RI-7.8a evidence={auth_verdict!r} vs local-ai-review={review_verdict!r}"
    )


def test_ri78a_schema_rejects_guard_flag_true() -> None:
    """Negative schema test: schema rejects guard flags set to true."""
    schema = json.loads(_read(_SCHEMA_PATH))
    evidence = json.loads(_read(_EVIDENCE_PATH))
    for flag in ("support_widening", "production_platform_claim", "live_adapter_execution"):
        bad = json.loads(json.dumps(evidence))
        bad[flag] = True
        errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
        assert errors, f"schema accepted {flag}=true; guard flag must be const false"


def test_ri78a_schema_rejects_authorization_effect_other_than_pre_authorization_only() -> None:
    """Negative schema test: any other authorization_effect string is rejected."""
    schema = json.loads(_read(_SCHEMA_PATH))
    evidence = json.loads(_read(_EVIDENCE_PATH))
    bad = json.loads(json.dumps(evidence))
    bad["authorization_effect"] = "execution_permission_granted"
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
    assert errors, "schema accepted authorization_effect='execution_permission_granted'"


def test_ri78a_plan_doc_records_decision_pre_authorization_no_execution() -> None:
    text = _read(_PLAN_PATH)
    flat = " ".join(text.split())
    assert "ri78a_live_evidence_pre_authorization_recorded_no_guard_flag_flip_no_execution" in flat
    assert "pre_authorization_only_no_execution_permission" in flat
    assert "Halildeu" in flat
    assert "Operator-Pre-Authorized-By" in flat
    assert "No-Execution-Permission" in flat


# ----------------------------------------------------------------------
# Forbidden-diff invariant (CI fail-closed in PR context).
# ----------------------------------------------------------------------


def _git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(_REPO_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _in_ci() -> bool:
    return os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI") == "true"


def _is_ri78a_introducer_pr() -> bool:
    """Returns True if THIS PR is the slice that introduces the RI-7.8a evidence
    artifact (the artifact is newly ADDED in the diff against origin/main).

    The forbidden-diff dynamic check is a state-at-landing pin: it only runs on
    the introducer PR. On successor slices (RI-7.8b-bc1-6b adds new workflows
    + gpp_status.v1.json supersession entries; RI-7.8b-bc1-6c flips the
    submanifest BC-1 key), the diff legitimately touches surfaces the 6a
    forbidden_surfaces list rejected. The artifact's digest pins (stale_replay
    guard + readiness/submanifest sha256 + const fields) continue to enforce
    the RI-7.8a state at PR #673 landing on every successor PR.

    Pattern mirrors RI-7.5's introducer detection and PR #666 fast-follow.
    """
    base, _src = _resolve_diff_base()
    if base is None:
        return False
    diff_proc = _git(["diff", "--diff-filter=A", "--name-only", f"{base}..HEAD"])
    if diff_proc.returncode != 0:
        return False
    added = {line.strip() for line in diff_proc.stdout.splitlines() if line.strip()}
    return str(_EVIDENCE_PATH.relative_to(_REPO_ROOT)) in added


def _in_pr_context() -> bool:
    if os.environ.get("GITHUB_EVENT_NAME") == "pull_request":
        return True
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if event_path:
        try:
            event = json.loads(Path(event_path).read_text(encoding="utf-8"))
            if isinstance(event.get("pull_request"), dict):
                return True
        except (OSError, json.JSONDecodeError, KeyError):
            return False
    return False


def _resolve_diff_base() -> tuple[str | None, str]:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if event_path:
        try:
            event = json.loads(Path(event_path).read_text(encoding="utf-8"))
            pr = event.get("pull_request") or {}
            base = pr.get("base") or {}
            sha = base.get("sha")
            base_ref = base.get("ref")
            if isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{40}", sha):
                has = _git(["cat-file", "-e", sha])
                if has.returncode != 0:
                    _git(["fetch", "origin", sha, "--depth=1"])
                    if base_ref and re.fullmatch(r"[A-Za-z0-9._/-]+", base_ref):
                        _git(["fetch", "origin", base_ref, "--depth=1"])
                    has = _git(["cat-file", "-e", sha])
                if has.returncode == 0:
                    return sha, "github_event_payload"
        except (OSError, json.JSONDecodeError, KeyError):
            pass
    base_ref = os.environ.get("GITHUB_BASE_REF")
    if base_ref and re.fullmatch(r"[A-Za-z0-9._/-]+", base_ref):
        fetch = _git(["fetch", "origin", base_ref, "--depth=1"])
        if fetch.returncode == 0:
            mb = _git(["merge-base", "HEAD", "FETCH_HEAD"])
            if mb.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", mb.stdout.strip()):
                return mb.stdout.strip(), f"fetch:{base_ref}"
    mb = _git(["merge-base", "HEAD", "origin/main"])
    if mb.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", mb.stdout.strip()):
        return mb.stdout.strip(), "origin/main"
    mb = _git(["merge-base", "HEAD", "main"])
    if mb.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", mb.stdout.strip()):
        return mb.stdout.strip(), "local_main"
    return None, "none"


def test_ri78a_stale_replay_guard_digests_match_files() -> None:
    """Codex iter-2 absorb: the stale_replay_guard's
    ``readiness_manifest_sha256`` and ``ri78_submanifest_sha256`` MUST
    match the actual file contents on disk. This binds the
    pre-authorization to the exact readiness/submanifest state and
    rejects any drift. RI-7.8b slices will consume these digests as
    `pre_authorization_ref` and verify their own inheritance chain.
    """
    import hashlib

    evidence = json.loads(_read(_EVIDENCE_PATH))
    guard = evidence["stale_replay_guard"]
    actual_readiness = hashlib.sha256(_READINESS_MANIFEST_PATH.read_bytes()).hexdigest()
    actual_submanifest = hashlib.sha256(_SUBMANIFEST_PATH.read_bytes()).hexdigest()
    assert guard["readiness_manifest_sha256"] == actual_readiness, (
        f"readiness manifest digest drift: pinned={guard['readiness_manifest_sha256']!r} actual={actual_readiness!r}"
    )
    assert guard["ri78_submanifest_sha256"] == actual_submanifest, (
        f"submanifest digest drift: pinned={guard['ri78_submanifest_sha256']!r} actual={actual_submanifest!r}"
    )
    assert guard["pr_number"] == 673
    assert re.fullmatch(r"[0-9a-f]{40}", guard["base_sha"])


def test_ri78a_forbidden_surfaces_actually_unchanged_in_diff() -> None:
    """CI fail-closed in PR context (introducer PR only): forbidden surfaces
    MUST not appear in `git diff --name-only base..HEAD`.

    State-at-landing pin: this dynamic check only runs on the RI-7.8a
    introducer PR (PR #673). Successor B-path slices (RI-7.8b-bc1-6b adds
    new workflows + gpp_status entries; RI-7.8b-bc1-6c flips the submanifest)
    legitimately touch surfaces the 6a forbidden_surfaces list rejected.
    The const digest pins (readiness sha256, submanifest sha256, base_sha,
    artifact_kind, decision) keep enforcing the RI-7.8a state-at-landing
    on every successor PR via the structural invariants above.
    """
    if not _is_ri78a_introducer_pr():
        pytest.skip("RI-7.8a state-at-landing pin: forbidden-diff dynamic check only runs on the introducer PR")
    evidence = json.loads(_read(_EVIDENCE_PATH))
    surfaces = evidence["forbidden_change_audit"]["forbidden_surfaces"]

    base, source = _resolve_diff_base()
    if base is None:
        msg = "no PR diff base could be resolved"
        if _in_ci() and _in_pr_context():
            pytest.fail(f"forbidden-diff invariant cannot run in CI PR: {msg}")
        pytest.skip(msg)

    diff_proc = _git(["diff", "--name-only", f"{base}..HEAD"])
    if diff_proc.returncode != 0:
        msg = f"git diff failed: {diff_proc.stderr.strip()}"
        if _in_ci() and _in_pr_context():
            pytest.fail(f"forbidden-diff invariant cannot run in CI PR: {msg}")
        pytest.skip(msg)

    changed = {line.strip() for line in diff_proc.stdout.splitlines() if line.strip()}
    allowed_planned_successor_touches: set[str] = set()
    if {
        ".claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.md",
        ".claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.v1.json",
        "tests/test_ao_ma10_low_risk_autonomous_merge_lane.py",
    } <= changed:
        ao_ma10_text = (_REPO_ROOT / ".claude" / "plans" / "AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.md").read_text(
            encoding="utf-8"
        )
        if (
            "## AO-MA-10b Release-Gate Payload + Decision Integration" in ao_ma10_text
            and "AO-MA-10b may touch only:" in ao_ma10_text
            and "`ao_kernel/ao_release_gate.py`" in ao_ma10_text
        ):
            allowed_planned_successor_touches.add("ao_kernel/ao_release_gate.py")

    offenders: list[str] = []
    for surface in surfaces:
        if surface.endswith("/"):
            offenders.extend(f for f in changed if f.startswith(surface))
        else:
            offenders.extend(f for f in changed if f == surface)
    offenders = [path for path in offenders if path not in allowed_planned_successor_touches]
    assert not offenders, f"forbidden surfaces touched (base source={source}): {sorted(offenders)}"
