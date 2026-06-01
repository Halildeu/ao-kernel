"""AO-MA-11A-2 CLI 7-stage tests (gate engine + API fixtures + bypass split)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


from scripts.ao_ma11a2_plan_approval_gate import (
    GateReport,
    fetch_approvals,
    parse_approval_from_history,
    run_gate,
    validate_plan_binding,
)


_BASE_SHA = "a" * 40
_GH_REPO = "Halildeu/ao-kernel"
_GH_RUN_ID = "123456"


# ---- Fixture builders ----


def _write_plan(tmp_path: Path, plan_text: str) -> tuple[Path, str]:
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(plan_text, encoding="utf-8")
    digest = "sha256:" + hashlib.sha256(plan_path.read_bytes()).hexdigest()
    return plan_path, digest


def _write_bundle(tmp_path: Path, *, plan_digest: str, base_sha: str = _BASE_SHA):
    bundle = {
        "schema_version": "ao-ma-11a-plan-consensus-bundle.v1",
        "artifact_kind": "ao_ma_11a_plan_consensus_bundle",
        "consensus_id": "ao-ma-plan-20260601-test01",
        "operator_goal": "test plan",
        "plan_digest": plan_digest,
        "plan_binding": {
            "repository_full_name": _GH_REPO,
            "base_ref": "refs/heads/main",
            "base_sha": base_sha,
        },
        "acceptance_criteria": ["a"],
        "required_providers": ["anthropic", "openai", "minimax"],
        "provider_verdicts": [
            {
                "provider_id": "anthropic",
                "round_index": 1,
                "verdict": "AGREE",
                "agent_id": "test-agent",
                "rationale": "test rationale",
                "objections": [],
            },
            {
                "provider_id": "openai",
                "round_index": 1,
                "verdict": "AGREE",
                "agent_id": "test-agent",
                "rationale": "test rationale",
                "objections": [],
            },
            {
                "provider_id": "minimax",
                "round_index": 1,
                "verdict": "AGREE",
                "agent_id": "test-agent",
                "rationale": "test rationale",
                "objections": [],
            },
        ],
        "round_budget": 3,
        "rounds_used": 1,
        "unanimous_status": "AGREE",
        "spm_anchor": {
            "spm_profile_ref": "test",
            "roadmap_item_id": "AO-MA-TEST",
            "quality_targets": {
                "coverage_branch_min": 0.7,
                "required_test_classes": ["unit"],
                "required_evidence_classes": ["test_report"],
            },
            "tracking_refs": [],
        },
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "release_authority": "ao-release-gate+github-ruleset",
        "ai_output_release_authority": False,
        "secrets_recorded": False,
        "created_at": "2026-06-01T00:00:00Z",
    }
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    sha = "sha256:" + hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    return bundle, bundle_path, sha


def _write_request(tmp_path: Path, *, consensus_id: str, plan_digest: str):
    request = {
        "schema_version": "ao-ma-11a-plan-approval-request.v1",
        "consensus_id": consensus_id,
        "plan_digest": plan_digest,
        "requested_at": "2026-06-01T00:00:00Z",
    }
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request, indent=2), encoding="utf-8")
    sha = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    return path, sha


def _make_caller_happy(approving_login: str = "Halildeu", triggering_actor: str = "ao-bot"):
    """Codex iter-2 Blocker 4 absorb: real GH API response shape fixture."""

    def caller(method: str, path: str) -> Any:
        if "environments/ao-ma-plan-approval" in path:
            return {
                "name": "ao-ma-plan-approval",
                "protection_rules": [
                    {
                        "type": "required_reviewers",
                        "reviewers": [{"id": 1, "login": approving_login}],
                    }
                ],
            }
        if "/approvals" in path:
            return [
                {
                    "state": "approved",
                    "user": {"login": approving_login, "id": 1},
                    "created_at": "2026-06-01T10:00:00Z",
                    "environments": [{"name": "ao-ma-plan-approval"}],
                    "comment": "ok",
                }
            ]
        if "actions/runs/" in path:
            return {
                "id": int(_GH_RUN_ID),
                "triggering_actor": {"login": triggering_actor},
            }
        raise KeyError(path)

    return caller


# ---- Stage 1: path containment via run_gate ----


def test_stage1_absolute_path_rejected(tmp_path):
    plan_path, plan_digest = _write_plan(tmp_path, "x")
    bundle, bundle_path, bundle_sha = _write_bundle(tmp_path, plan_digest=plan_digest)
    request_path, request_sha = _write_request(tmp_path, consensus_id=bundle["consensus_id"], plan_digest=plan_digest)
    report = run_gate(
        plan_path="/etc/passwd",  # absolute → reject
        consensus_bundle_path=bundle_path.name,
        approval_request_path=request_path.name,
        plan_digest=plan_digest,
        consensus_bundle_sha256=bundle_sha,
        approval_request_sha256=request_sha,
        github_run_id=_GH_RUN_ID,
        github_repository=_GH_REPO,
        github_sha=_BASE_SHA,
        gh_api_caller=_make_caller_happy(),
        repo_root=tmp_path,
    )
    assert report.final_decision == "rejected_path"
    assert not report.path_containment_pass


# ---- Stage 2: SHA recompute ----


def test_stage2_sha_mismatch_rejected(tmp_path):
    plan_path, plan_digest = _write_plan(tmp_path, "x")
    bundle, bundle_path, bundle_sha = _write_bundle(tmp_path, plan_digest=plan_digest)
    request_path, request_sha = _write_request(tmp_path, consensus_id=bundle["consensus_id"], plan_digest=plan_digest)
    report = run_gate(
        plan_path=plan_path.name,
        consensus_bundle_path=bundle_path.name,
        approval_request_path=request_path.name,
        plan_digest="sha256:" + "0" * 64,  # wrong
        consensus_bundle_sha256=bundle_sha,
        approval_request_sha256=request_sha,
        github_run_id=_GH_RUN_ID,
        github_repository=_GH_REPO,
        github_sha=_BASE_SHA,
        gh_api_caller=_make_caller_happy(),
        repo_root=tmp_path,
    )
    assert report.final_decision == "rejected_sha"


# ---- Stage 3: plan binding stale-main guard ----


def test_stage3_stale_base_sha_rejected(tmp_path):
    plan_path, plan_digest = _write_plan(tmp_path, "x")
    bundle, bundle_path, bundle_sha = _write_bundle(
        tmp_path,
        plan_digest=plan_digest,
        base_sha="b" * 40,  # stale
    )
    request_path, request_sha = _write_request(tmp_path, consensus_id=bundle["consensus_id"], plan_digest=plan_digest)
    report = run_gate(
        plan_path=plan_path.name,
        consensus_bundle_path=bundle_path.name,
        approval_request_path=request_path.name,
        plan_digest=plan_digest,
        consensus_bundle_sha256=bundle_sha,
        approval_request_sha256=request_sha,
        github_run_id=_GH_RUN_ID,
        github_repository=_GH_REPO,
        github_sha=_BASE_SHA,  # different from bundle's b*40
        gh_api_caller=_make_caller_happy(),
        repo_root=tmp_path,
    )
    assert report.final_decision == "rejected_binding"
    assert "stale" in (report.stage_fail_reason or "").lower()


def test_validate_plan_binding_repo_mismatch(tmp_path):
    plan_path, plan_digest = _write_plan(tmp_path, "x")
    bundle, _, _ = _write_bundle(tmp_path, plan_digest=plan_digest)
    ok, err = validate_plan_binding(
        bundle,
        plan_digest=plan_digest,
        github_repository="wrong/repo",
        github_sha=_BASE_SHA,
    )
    assert not ok
    assert "repository" in err.lower()


def test_validate_plan_binding_base_ref_check(tmp_path):
    plan_path, plan_digest = _write_plan(tmp_path, "x")
    bundle, _, _ = _write_bundle(tmp_path, plan_digest=plan_digest)
    bundle["plan_binding"]["base_ref"] = "refs/heads/dev"
    ok, err = validate_plan_binding(
        bundle,
        plan_digest=plan_digest,
        github_repository=_GH_REPO,
        github_sha=_BASE_SHA,
    )
    assert not ok
    assert "refs/heads/main" in err


# ---- Stage 5: API state fixtures ----


def test_stage5_empty_approvals_returns_empty():
    """Empty after retries → empty state."""

    def caller(method, path):
        return []

    approvals, err = fetch_approvals(
        gh_api_caller=caller,
        repo_full_name=_GH_REPO,
        run_id=_GH_RUN_ID,
        retries=2,
        backoff_seconds=0.01,
    )
    assert err == ""
    assert approvals == []


def test_stage5_api_error_propagates():
    def caller(method, path):
        raise RuntimeError("API down")

    approvals, err = fetch_approvals(
        gh_api_caller=caller,
        repo_full_name=_GH_REPO,
        run_id=_GH_RUN_ID,
        retries=1,
        backoff_seconds=0.01,
    )
    assert approvals is None
    assert "api_error" in err


def test_parse_approval_happy():
    approvals = [
        {
            "state": "approved",
            "user": {"login": "Halildeu"},
            "created_at": "2026-06-01T10:00:00Z",
            "environments": [{"name": "ao-ma-plan-approval"}],
        }
    ]
    parsed, state = parse_approval_from_history(approvals, target_environment="ao-ma-plan-approval")
    assert state == "approved"
    assert parsed["approving_login"] == "Halildeu"
    assert parsed["approving_at"] == "2026-06-01T10:00:00Z"


def test_parse_approval_rejected():
    approvals = [
        {
            "state": "rejected",
            "user": {"login": "Halildeu"},
            "created_at": "2026-06-01T10:00:00Z",
            "environments": [{"name": "ao-ma-plan-approval"}],
        }
    ]
    parsed, state = parse_approval_from_history(approvals, target_environment="ao-ma-plan-approval")
    assert state == "rejected"


def test_parse_approval_wrong_environment():
    approvals = [
        {
            "state": "approved",
            "user": {"login": "Halildeu"},
            "created_at": "2026-06-01T10:00:00Z",
            "environments": [{"name": "different-env"}],
        }
    ]
    parsed, state = parse_approval_from_history(approvals, target_environment="ao-ma-plan-approval")
    assert state == "wrong_environment"


def test_parse_approval_empty_list():
    parsed, state = parse_approval_from_history([], target_environment="ao-ma-plan-approval")
    assert state == "empty"
    assert parsed is None


# ---- Stage 4-7 full happy path ----


def test_full_happy_path_approved(tmp_path):
    plan_path, plan_digest = _write_plan(tmp_path, "test plan content")
    bundle, bundle_path, bundle_sha = _write_bundle(tmp_path, plan_digest=plan_digest)
    request_path, request_sha = _write_request(tmp_path, consensus_id=bundle["consensus_id"], plan_digest=plan_digest)
    report = run_gate(
        plan_path=plan_path.name,
        consensus_bundle_path=bundle_path.name,
        approval_request_path=request_path.name,
        plan_digest=plan_digest,
        consensus_bundle_sha256=bundle_sha,
        approval_request_sha256=request_sha,
        github_run_id=_GH_RUN_ID,
        github_repository=_GH_REPO,
        github_sha=_BASE_SHA,
        gh_api_caller=_make_caller_happy(),
        repo_root=tmp_path,
    )
    assert report.final_decision == "approved", f"reason: {report.stage_fail_reason}"
    assert report.path_containment_pass
    assert report.sha_recompute_pass
    assert report.plan_binding_pass
    assert report.consensus_validator_pass
    assert report.approval_validator_pass
    assert not report.bypass_detected
    assert report.approval_api_state == "approved"
    assert report.approving_login == "Halildeu"


# ---- Self-review (bypass detection) ----


def test_self_review_detected_marks_bypass(tmp_path):
    """When approving_login == triggering_actor, self_review_rejected=False → bypass_detected=True."""
    plan_path, plan_digest = _write_plan(tmp_path, "x")
    bundle, bundle_path, bundle_sha = _write_bundle(tmp_path, plan_digest=plan_digest)
    request_path, request_sha = _write_request(tmp_path, consensus_id=bundle["consensus_id"], plan_digest=plan_digest)
    report = run_gate(
        plan_path=plan_path.name,
        consensus_bundle_path=bundle_path.name,
        approval_request_path=request_path.name,
        plan_digest=plan_digest,
        consensus_bundle_sha256=bundle_sha,
        approval_request_sha256=request_sha,
        github_run_id=_GH_RUN_ID,
        github_repository=_GH_REPO,
        github_sha=_BASE_SHA,
        gh_api_caller=_make_caller_happy(approving_login="Halildeu", triggering_actor="Halildeu"),
        repo_root=tmp_path,
    )
    assert report.bypass_detected, "self-review MUST trigger bypass_detected=true"
    assert report.final_decision == "rejected_identity"


# ---- GateReport compute_bypass ----


def test_gate_report_compute_bypass_all_3_false():
    r = GateReport()
    r.compute_bypass()
    assert r.bypass_detected  # default: all 3 false → bypass


def test_validate_only_mode_emits_pre_flight_passed(tmp_path):
    """Codex iter-2 post-impl absorb: validate_only emits pre_flight_passed
    final_decision (NOT approved); API stages skipped (approving_login/at None,
    approval_validator_pass False, approval_api_state empty).
    """
    plan_path, plan_digest = _write_plan(tmp_path, "x")
    bundle, bundle_path, bundle_sha = _write_bundle(tmp_path, plan_digest=plan_digest)
    request_path, request_sha = _write_request(tmp_path, consensus_id=bundle["consensus_id"], plan_digest=plan_digest)

    def env_only_caller(method, path):
        if "environments/ao-ma-plan-approval" in path:
            return {
                "name": "ao-ma-plan-approval",
                "protection_rules": [{"type": "required_reviewers", "reviewers": [{"id": 1}]}],
            }
        # validate_only MUST NOT call API beyond env preflight
        raise AssertionError(f"validate_only should not fetch: {path}")

    report = run_gate(
        plan_path=plan_path.name,
        consensus_bundle_path=bundle_path.name,
        approval_request_path=request_path.name,
        plan_digest=plan_digest,
        consensus_bundle_sha256=bundle_sha,
        approval_request_sha256=request_sha,
        github_run_id=_GH_RUN_ID,
        github_repository=_GH_REPO,
        github_sha=_BASE_SHA,
        gh_api_caller=env_only_caller,
        repo_root=tmp_path,
        validate_only=True,
    )
    assert report.final_decision == "pre_flight_passed"
    assert report.path_containment_pass
    assert report.sha_recompute_pass
    assert report.plan_binding_pass
    assert report.consensus_validator_pass
    assert not report.approval_validator_pass
    assert report.approval_api_state == "empty"
    assert report.approving_login is None
    assert report.approving_at is None
    assert report.stage_fail_reason is None
    assert report.to_exit_code() == 0


def test_gate_report_compute_bypass_all_3_true_no_bypass():
    r = GateReport(
        no_bypass_state_observed=True,
        self_review_rejected=True,
        required_reviewer_configured=True,
    )
    r.compute_bypass()
    assert not r.bypass_detected
