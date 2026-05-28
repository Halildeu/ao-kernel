"""AO-MA-10d negative fail-closed suite.

These tests pin the negative prerequisites that must stay blocked before any
merge-agent dry-run or real autonomous merge smoke is attempted.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any, cast

import pytest

from ao_kernel.ao_release_gate import (
    AoReleaseGateDecision,
    DENY_MISSING_EVIDENCE_DECISION,
    DENY_POLICY_VIOLATION_DECISION,
    DENY_UNTRUSTED_CONTEXT_DECISION,
    RELEASE_GATE_CHECK_NAME,
    build_ao_release_gate_decision,
    diff_digest,
)


_ALLOW_HEAD_SHA = "abc1230000000000000000000000000000000000"
_ALLOW_REVIEWED_SLICE = "GPP-2"
_ALLOW_CHANGED_PATHS = [
    "ao_kernel/ao_release_gate.py",
    "scripts/ao_release_gate_decision.py",
    "tests/test_ao_release_gate.py",
    ".claude/plans/GPP-2v-AO-RELEASE-GATE-DRY-RUN-SCAFFOLD.md",
]


def _review_evidence(
    *,
    head_sha: str | None = None,
    changed_paths: list[str] | None = None,
    reviewed_slice: str | None = None,
    repo: str = "Halildeu/ao-kernel",
    decision: str = "operator_may_merge",
    reviewer_agree: bool = True,
    cross_provider_verified: bool = True,
) -> dict[str, object]:
    paths = list(changed_paths) if changed_paths is not None else list(_ALLOW_CHANGED_PATHS)
    return {
        "schema_version": "local-gpp-gate-evidence.v1",
        "decision": decision,
        "repo": repo,
        "work_package": reviewed_slice if reviewed_slice is not None else _ALLOW_REVIEWED_SLICE,
        "generated_at": "2026-04-28T00:00:00Z",
        "checks": {
            "startup_preflight_passed": True,
            "gpp_status_checked": True,
            "scope_allowed": True,
            "tests_passed": True,
            "secret_scan_passed": True,
            "reviewer_agree": reviewer_agree,
            "cross_provider_verified": cross_provider_verified,
            "forbidden_actions_absent": True,
        },
        "findings": [],
        "reviewer_findings_count": 0,
        "gpp_2_status": "closed",
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
        "context_binding": {
            "head_sha": head_sha if head_sha is not None else _ALLOW_HEAD_SHA,
            "base_ref": "origin/main",
            "diff_digest": diff_digest(paths),
            "changed_files_count": len(paths),
        },
    }


def _ao_ma10_evidence_bundle(
    *,
    head_sha: str | None = None,
    head_ref: str = "refs/heads/codex/gpp-2v-release-gate-dry-run",
    base_ref: str = "origin/main",
    changed_paths: list[str] | None = None,
    consensus_status: str = "AGREE",
    provider_verdict: str = "AGREE",
) -> dict[str, object]:
    paths = list(changed_paths) if changed_paths is not None else list(_ALLOW_CHANGED_PATHS)
    context = {
        "repository_full_name": "Halildeu/ao-kernel",
        "base_ref": base_ref,
        "head_ref": head_ref,
        "head_sha": head_sha if head_sha is not None else _ALLOW_HEAD_SHA,
        "diff_digest": diff_digest(paths),
        "changed_files_count": len(paths),
    }
    provider_verdicts: list[dict[str, object]] = []
    for provider, agent in (("openai", "codex-reviewer"), ("anthropic", "claude-reviewer")):
        provider_verdicts.append(
            {
                "schema_version": "ao-ma-10-provider-consensus.v1",
                "artifact_kind": "ao_ma_10_provider_consensus",
                "provider_id": provider,
                "agent_id": agent,
                "role": "reviewer",
                "verdict": provider_verdict,
                "round_index": 1,
                "context_binding": dict(context),
                "findings_count": 0 if provider_verdict == "AGREE" else 1,
                "secrets_recorded": False,
                "support_widening": False,
                "production_platform_claim": False,
                "live_adapter_execution": False,
                "release_authority": "ao-release-gate+github-ruleset",
                "ai_output_release_authority": False,
            }
        )
    return {
        "schema_version": "ao-ma-10-evidence-bundle.v1",
        "artifact_kind": "ao_ma_10_evidence_bundle",
        "generated_at": "2026-05-28T00:00:00Z",
        "repo": "Halildeu/ao-kernel",
        "work_package": "AO-MA-10a2",
        "read_only": True,
        "mutations_performed": False,
        "release_authority": "ao-release-gate+github-ruleset",
        "ai_output_release_authority": False,
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "context_binding": context,
        "reviewer_providers": ["anthropic", "openai"],
        "required_reviewer_providers": ["openai", "anthropic"],
        "provider_verdicts": provider_verdicts,
        "consensus_status": consensus_status,
        "freshness": {
            "status": "fresh",
            "max_age_seconds": 3600,
        },
        "secrets_recorded": False,
    }


def _gpp_status(*, issue: str = "https://github.com/Halildeu/ao-kernel/issues/539") -> dict[str, object]:
    return {
        "current_wp": {
            "id": "GPP-2",
            "status": "blocked",
            "issue": issue,
        },
        "support_widening_allowed": False,
        "production_platform_claim_allowed": False,
        "live_adapter_execution_allowed": False,
    }


def _allow_payload() -> dict[str, object]:
    return {
        "repository": {"full_name": "Halildeu/ao-kernel"},
        "pull_request": {
            "number": 539,
            "author": {"login": "Halildeu"},
            "base": {"ref": "main"},
            "head": {
                "ref": "codex/gpp-2v-release-gate-dry-run",
                "sha": _ALLOW_HEAD_SHA,
                "repo": {"fork": False},
            },
        },
        "issue_url": "https://github.com/Halildeu/ao-kernel/issues/539",
        "branch_up_to_date": True,
        "event_name": "pull_request",
        "reviewed_slice": _ALLOW_REVIEWED_SLICE,
        "changed_paths": list(_ALLOW_CHANGED_PATHS),
        "pr_author": "Halildeu",
        "human_reviews": [
            {
                "author": "gladyatore-lab",
                "state": "APPROVED",
                "commit_oid": _ALLOW_HEAD_SHA,
            }
        ],
        "path_sensitive_human_review_enabled": True,
        "allowed_path_prefixes": [
            "ao_kernel/",
            "scripts/",
            "tests/",
            ".claude/plans/",
        ],
        "required_checks": [
            {"name": "lint", "status": "completed", "conclusion": "success"},
            {"name": "test (3.13)", "status": "completed", "conclusion": "success"},
            {"name": RELEASE_GATE_CHECK_NAME, "status": "completed", "conclusion": "success"},
        ],
        "forbidden_secret_context_detected": False,
        "admin_bypass_requested": False,
        "pat_backed_bot_actor": False,
        "codex_or_claude_release_authority": False,
        "live_adapter_execution_requested": False,
    }


def _ao_ma10_requested_payload() -> dict[str, object]:
    payload = _allow_payload()
    payload["low_risk_autonomous_merge_requested"] = True
    return payload


def _high_risk_without_review_payload() -> dict[str, object]:
    payload = _allow_payload()
    payload["human_reviews"] = []
    return payload


def _decide(
    *,
    payload: dict[str, object] | None = None,
    review_evidence: object = None,
    bundle: object = None,
) -> AoReleaseGateDecision:
    if payload is None:
        payload = _ao_ma10_requested_payload()
    if review_evidence is None:
        review_evidence = _review_evidence()
    if bundle is None:
        bundle = _ao_ma10_evidence_bundle()
    return build_ao_release_gate_decision(
        payload,
        _gpp_status(),
        review_evidence=review_evidence,
        ao_ma10_evidence_bundle=bundle,
        generated_at="2026-05-28T00:00:00Z",
    )


def _check(decision: AoReleaseGateDecision, name: str) -> dict[str, object]:
    raw_decision = cast(dict[str, object], decision)
    checks = raw_decision["checks"]
    assert isinstance(checks, list)
    for check in checks:
        assert isinstance(check, dict)
        if check["name"] == name:
            return cast(dict[str, object], check)
    raise AssertionError(f"missing check: {name}")


def _assert_denied(decision: AoReleaseGateDecision, expected_decision: str, expected_finding: str) -> None:
    assert decision["allow"] is False
    assert decision["decision"] == expected_decision
    assert expected_finding in decision["findings"]


def test_ao_ma10d_same_provider_review_blocked_smoke_duplicate_provider_ids() -> None:
    bundle = _ao_ma10_evidence_bundle()
    assert isinstance(bundle["provider_verdicts"], list)
    for verdict in bundle["provider_verdicts"]:
        assert isinstance(verdict, dict)
        verdict["provider_id"] = "openai"
        verdict["agent_id"] = "same-provider-reviewer"

    decision = _decide(bundle=bundle)

    _assert_denied(
        decision,
        DENY_POLICY_VIOLATION_DECISION,
        "ao_release_gate_ao_ma10_same_provider_self_review",
    )
    assert _check(decision, "ao_ma10_consensus")["status"] == "blocked"


def test_ao_ma10d_same_provider_review_blocked_smoke_missing_required_provider() -> None:
    bundle = _ao_ma10_evidence_bundle()
    verdicts = bundle["provider_verdicts"]
    assert isinstance(verdicts, list)
    assert isinstance(verdicts[1], dict)
    verdicts[1]["provider_id"] = "minimax"
    verdicts[1]["agent_id"] = "minimax-reviewer"

    decision = _decide(bundle=bundle)

    _assert_denied(
        decision,
        DENY_POLICY_VIOLATION_DECISION,
        "ao_release_gate_ao_ma10_same_provider_self_review",
    )


@pytest.mark.parametrize(
    ("mutate", "case_id"),
    [
        (lambda bundle: bundle["freshness"].__setitem__("status", "stale"), "stale-status"),
        (lambda bundle: bundle.pop("freshness"), "missing-freshness"),
    ],
    ids=lambda case: case if isinstance(case, str) else None,
)
def test_ao_ma10d_stale_evidence_blocked_smoke(mutate: Callable[[dict[str, Any]], object], case_id: str) -> None:
    del case_id
    bundle = deepcopy(_ao_ma10_evidence_bundle())
    mutate(bundle)

    decision = _decide(bundle=bundle)

    assert decision["allow"] is False
    _assert_denied(
        decision,
        DENY_MISSING_EVIDENCE_DECISION,
        "ao_release_gate_ao_ma10_evidence_bundle_schema_invalid",
    )


def test_ao_ma10d_negative_high_risk_blocked_smoke_without_review() -> None:
    payload = _high_risk_without_review_payload()
    payload["low_risk_autonomous_merge_requested"] = True

    decision = _decide(payload=payload)

    assert decision["allow"] is False
    _assert_denied(
        decision,
        DENY_POLICY_VIOLATION_DECISION,
        "ao_release_gate_high_risk_human_review_missing",
    )


def test_ao_ma10d_negative_high_risk_blocked_smoke_prohibited_path() -> None:
    path = ".github/workflows/ao-release-gate.yml"
    payload = _allow_payload()
    payload["low_risk_autonomous_merge_requested"] = True
    payload["changed_paths"] = [path]
    payload["human_reviews"] = []
    payload["allowed_path_prefixes"] = ["docs/"]

    decision = _decide(
        payload=payload,
        review_evidence=_review_evidence(changed_paths=[path]),
        bundle=_ao_ma10_evidence_bundle(changed_paths=[path]),
    )

    assert decision["allow"] is False
    _assert_denied(
        decision,
        DENY_POLICY_VIOLATION_DECISION,
        "ao_release_gate_high_risk_human_review_missing",
    )


def test_ao_ma10d_missing_verifier_blocked_smoke_without_review_evidence() -> None:
    decision = build_ao_release_gate_decision(
        _ao_ma10_requested_payload(),
        _gpp_status(),
        ao_ma10_evidence_bundle=_ao_ma10_evidence_bundle(),
        generated_at="2026-05-28T00:00:00Z",
    )

    assert decision["allow"] is False
    _assert_denied(
        decision,
        DENY_MISSING_EVIDENCE_DECISION,
        "ao_release_gate_review_evidence_missing",
    )


def test_ao_ma10d_missing_verifier_blocked_smoke_non_accepting_review_evidence() -> None:
    decision = _decide(review_evidence=_review_evidence(reviewer_agree=False))

    assert decision["allow"] is False
    _assert_denied(
        decision,
        DENY_MISSING_EVIDENCE_DECISION,
        "ao_release_gate_review_evidence_not_accepting",
    )


@pytest.mark.parametrize(
    ("mutate", "case_id"),
    [
        (lambda bundle: bundle.__setitem__("ai_output_release_authority", True), "ai-authority"),
        (lambda bundle: bundle.__setitem__("mutations_performed", True), "mutation"),
        (lambda bundle: bundle.__setitem__("secrets_recorded", True), "secret"),
        (lambda bundle: bundle.__setitem__("release_authority", "claude-agree"), "release-authority"),
        (lambda bundle: bundle["guard_flags"].__setitem__("support_widening", True), "support-widening"),
        (
            lambda bundle: bundle["guard_flags"].__setitem__("production_platform_claim", True),
            "production-claim",
        ),
        (lambda bundle: bundle["guard_flags"].__setitem__("live_adapter_execution", True), "live-adapter"),
    ],
    ids=lambda case: case if isinstance(case, str) else None,
)
def test_ao_ma10d_authority_boundary_negative(
    mutate: Callable[[dict[str, Any]], object], case_id: str
) -> None:
    del case_id
    bundle = deepcopy(_ao_ma10_evidence_bundle())
    mutate(bundle)

    decision = _decide(bundle=bundle)

    assert decision["allow"] is False
    _assert_denied(
        decision,
        DENY_POLICY_VIOLATION_DECISION,
        "ao_release_gate_ao_ma10_authority_boundary_open",
    )


@pytest.mark.parametrize(
    ("mutate", "case_id"),
    [
        (
            lambda binding: binding.__setitem__("repository_full_name", "Halildeu/another-repo"),
            "repository",
        ),
        (lambda binding: binding.__setitem__("base_ref", "feature/other-base"), "base-ref"),
        (lambda binding: binding.__setitem__("head_ref", "codex/other-head"), "head-ref"),
        (lambda binding: binding.__setitem__("head_sha", "f" * 40), "head-sha"),
        (lambda binding: binding.__setitem__("diff_digest", diff_digest(["different.txt"])), "diff-digest"),
        (lambda binding: binding.__setitem__("changed_files_count", 99), "changed-files-count"),
    ],
    ids=lambda case: case if isinstance(case, str) else None,
)
def test_ao_ma10d_context_binding_negative(mutate: Callable[[dict[str, Any]], object], case_id: str) -> None:
    del case_id
    bundle = deepcopy(_ao_ma10_evidence_bundle())
    binding = bundle["context_binding"]
    assert isinstance(binding, dict)
    mutate(binding)

    decision = _decide(bundle=bundle)

    assert decision["allow"] is False
    _assert_denied(
        decision,
        DENY_UNTRUSTED_CONTEXT_DECISION,
        "ao_release_gate_ao_ma10_evidence_bundle_context_unbound",
    )


@pytest.mark.parametrize(
    ("payload", "case_id"),
    [
        ({"low_risk_autonomous_merge_requested": "true"}, "string-true"),
        ({"low_risk_autonomous_merge_requested": 1}, "integer-one"),
        (
            {
                "low_risk_autonomous_merge_requested": True,
                "release_gate_context": {"ao_ma10_autonomous_merge_requested": False},
            },
            "conflicting-flags",
        ),
    ],
    ids=lambda case: case if isinstance(case, str) else None,
)
def test_ao_ma10d_malformed_request_flag_blocked_smoke(payload: dict[str, object], case_id: str) -> None:
    del case_id
    full_payload = _allow_payload()
    full_payload.update(payload)

    decision = _decide(payload=full_payload)

    assert decision["allow"] is False
    _assert_denied(
        decision,
        DENY_POLICY_VIOLATION_DECISION,
        "ao_release_gate_ao_ma10_autonomous_request_invalid",
    )


def test_ao_ma10d_positive_control_still_allows_context_bound_distinct_provider_bundle() -> None:
    decision = _decide()

    assert decision["allow"] is True
    assert decision["findings"] == []
    assert _check(decision, "ao_ma10_consensus")["status"] == "pass"
    assert _check(decision, "ao_ma10_context_bound")["status"] == "pass"
    assert _check(decision, "ao_ma10_authority_boundary")["status"] == "pass"
    assert decision["context"]["head_sha"] == _ALLOW_HEAD_SHA
    assert decision["context"]["changed_paths"] == _ALLOW_CHANGED_PATHS
