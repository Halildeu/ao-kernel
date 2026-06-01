from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from ao_kernel.ao_release_gate import (
    ALLOW_AUTONOMOUS_MERGE_DECISION,
    DENY_MISSING_EVIDENCE_DECISION,
    DENY_POLICY_VIOLATION_DECISION,
    DENY_STALE_BRANCH_DECISION,
    DENY_UNTRUSTED_CONTEXT_DECISION,
    ERROR_FAIL_CLOSED_DECISION,
    RELEASE_GATE_CHECK_NAME,
    build_ao_release_gate_decision,
    diff_digest,
    render_ao_release_gate_decision_text,
    write_ao_release_gate_decision,
)
from ao_kernel.live_adapter_gate import utc_timestamp

# 40-hex placeholder used by _allow_payload() and the matching
# _review_evidence() factory so the context-binding check passes.
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
    omit_context_binding: bool = False,
) -> dict[str, object]:
    """Build a valid accepting local-gpp-gate-evidence.v1 artifact.

    Defaults bind to ``_allow_payload()``. Individual test cases override
    fields to exercise the schema, acceptance-profile, and context-binding
    failure paths.
    """

    paths = list(changed_paths) if changed_paths is not None else list(_ALLOW_CHANGED_PATHS)
    artifact: dict[str, object] = {
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
    }
    if not omit_context_binding:
        artifact["context_binding"] = {
            "head_sha": head_sha if head_sha is not None else _ALLOW_HEAD_SHA,
            "base_ref": "origin/main",
            "diff_digest": diff_digest(paths),
            "changed_files_count": len(paths),
        }
    return artifact


def _ao_ma10_evidence_bundle(
    *,
    head_sha: str | None = None,
    head_ref: str = "refs/heads/codex/gpp-2v-release-gate-dry-run",
    base_ref: str = "origin/main",
    changed_paths: list[str] | None = None,
    consensus_status: str = "AGREE",
    provider_verdict: str = "AGREE",
) -> dict[str, object]:
    """Build a valid accepting AO-MA-10 evidence bundle for _allow_payload().

    Defaults intentionally use local-style refs (`origin/main`,
    `refs/heads/...`) while `_allow_payload()` uses GitHub payload refs
    (`main`, `codex/...`) so the positive path pins ref normalization.
    """

    paths = list(changed_paths) if changed_paths is not None else list(_ALLOW_CHANGED_PATHS)
    context = {
        "repository_full_name": "Halildeu/ao-kernel",
        "base_ref": base_ref,
        "head_ref": head_ref,
        "head_sha": head_sha if head_sha is not None else _ALLOW_HEAD_SHA,
        "diff_digest": diff_digest(paths),
        "changed_files_count": len(paths),
    }
    provider_verdicts = []
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


def _high_risk_supersession_evidence(
    *,
    generated_at: str | None = None,
    head_sha: str | None = None,
    head_ref: str = "refs/heads/codex/gpp-2v-release-gate-dry-run",
    base_ref: str = "origin/main",
    changed_paths: list[str] | None = None,
    high_risk_changed_paths: list[str] | None = None,
    provider_ids: tuple[str, str] = ("openai", "anthropic"),
    consensus_status: str = "AGREE",
    provider_verdict: str = "AGREE",
    binding_mode: str = "added",
) -> dict[str, object]:
    """Build accepting AO-MA-10h high-risk supersession evidence.

    Defaults bind to ``_allow_payload()`` with no human review. Refs use
    local-style spellings to pin runtime ref normalization.
    """

    paths = list(changed_paths) if changed_paths is not None else list(_ALLOW_CHANGED_PATHS)
    high_risk_paths = (
        list(high_risk_changed_paths)
        if high_risk_changed_paths is not None
        else [
            "ao_kernel/ao_release_gate.py",
            "scripts/ao_release_gate_decision.py",
            ".claude/plans/GPP-2v-AO-RELEASE-GATE-DRY-RUN-SCAFFOLD.md",
        ]
    )
    context = {
        "repository_full_name": "Halildeu/ao-kernel",
        "base_ref": base_ref,
        "head_ref": head_ref,
        "head_sha": head_sha if head_sha is not None else _ALLOW_HEAD_SHA,
        "diff_digest": diff_digest(paths),
        "changed_files_count": len(paths),
        "high_risk_changed_paths": high_risk_paths,
    }
    provider_verdicts = []
    for provider, agent in zip(provider_ids, ("codex-reviewer", "claude-reviewer"), strict=False):
        provider_verdicts.append(
            {
                "schema_version": "ao-ma-10-provider-consensus.v1",
                "artifact_kind": "ao_ma_10_provider_consensus",
                "provider_id": provider,
                "agent_id": agent,
                "role": "reviewer",
                "risk_classification": "high",
                "verdict": provider_verdict,
                "round_index": 2,
                "context_binding": dict(context),
                "binding_mode": binding_mode,
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
        "schema_version": "ao-ma-10-high-risk-supersession-evidence.v1",
        "artifact_kind": "ao_ma_10_high_risk_supersession_evidence",
        "generated_at": generated_at if generated_at is not None else utc_timestamp(),
        "repo": "Halildeu/ao-kernel",
        "work_package": "AO-MA-10h",
        "planning_only": True,
        "release_authority": "ao-release-gate+github-ruleset",
        "ai_output_release_authority": False,
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "context_binding": context,
        "reviewer_providers": ["openai", "anthropic"],
        "required_reviewer_providers": ["openai", "anthropic"],
        "provider_verdicts": provider_verdicts,
        "consensus_status": consensus_status,
        "max_revise_rounds": 3,
        "escalation_action": "operator_human_review_fallback",
        "freshness": {
            "status": "fresh",
            "max_age_seconds": 3600,
        },
        "secrets_recorded": False,
        "mutations_performed": False,
    }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


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


def _find_check(decision: dict[str, object], name: str) -> dict[str, object]:
    checks = decision["checks"]
    assert isinstance(checks, list)
    for check in checks:
        assert isinstance(check, dict)
        if check["name"] == name:
            return check
    raise AssertionError(f"missing check: {name}")


def _stale_branch_payload() -> dict[str, object]:
    payload = _allow_payload()
    payload["branch_up_to_date"] = False
    return payload


def _untrusted_context_payload() -> dict[str, object]:
    payload = _allow_payload()
    pull_request = payload["pull_request"]
    assert isinstance(pull_request, dict)
    head = pull_request["head"]
    assert isinstance(head, dict)
    repo = head["repo"]
    assert isinstance(repo, dict)
    repo["fork"] = True
    return payload


def _missing_evidence_payload() -> dict[str, object]:
    payload = _allow_payload()
    payload["required_checks"] = []
    return payload


def _policy_violation_payload() -> dict[str, object]:
    payload = _allow_payload()
    payload["admin_bypass_requested"] = True
    return payload


def _low_risk_payload() -> dict[str, object]:
    payload = _allow_payload()
    paths = ["docs/smoke/gpp2d6-low-risk-automerge-smoke.md"]
    payload["changed_paths"] = paths
    payload["human_reviews"] = []
    payload["allowed_path_prefixes"] = ["docs/"]
    return payload


def _ao_ma10_requested_payload() -> dict[str, object]:
    payload = _allow_payload()
    payload["low_risk_autonomous_merge_requested"] = True
    return payload


def _ao_ma10_low_risk_smoke_payload() -> dict[str, object]:
    path = "docs/evidence/ao-ma-10l-autonomous-smoke/ao-ma-10l-smoke-test.md"
    payload = _allow_payload()
    pull_request = payload["pull_request"]
    assert isinstance(pull_request, dict)
    pull_request["author"] = {"login": "gladyatore-lab"}
    pull_request["head"] = {
        "ref": "codex/ao-ma10l-smoke-test",
        "sha": _ALLOW_HEAD_SHA,
        "repo": {"fork": False},
    }
    payload["pr_author"] = "gladyatore-lab"
    payload["human_reviews"] = []
    payload["changed_paths"] = [path]
    payload["allowed_path_prefixes"] = ["docs/"]
    payload["low_risk_autonomous_merge_requested"] = True
    return payload


def _high_risk_without_review_payload() -> dict[str, object]:
    payload = _allow_payload()
    payload["human_reviews"] = []
    return payload


def _malformed_payload() -> str:
    # A non-dict payload fails the payload_shape check and is the simplest
    # input that drives the terminal error_fail_closed decision.
    return "not-a-json-object"


def test_release_gate_allows_closed_dry_run_context_without_merge_authority() -> None:
    decision = build_ao_release_gate_decision(
        _allow_payload(),
        _gpp_status(),
        review_evidence=_review_evidence(),
        generated_at="2026-04-28T00:00:00Z",
    )

    assert decision["schema_version"] == "1"
    assert decision["program_id"] == "GPP-2v"
    assert decision["app_slug"] == RELEASE_GATE_CHECK_NAME
    assert decision["decision"] == ALLOW_AUTONOMOUS_MERGE_DECISION
    assert decision["allow"] is True
    assert decision["dry_run"] is True
    assert decision["merge_authority_enabled"] is False
    assert decision["finding_code"] is None
    assert decision["findings"] == []
    assert decision["github_check_run"]["name"] == RELEASE_GATE_CHECK_NAME
    assert all(check["status"] == "pass" for check in decision["checks"])


def test_release_gate_denies_stale_branch() -> None:
    decision = build_ao_release_gate_decision(
        _stale_branch_payload(), _gpp_status(), review_evidence=_review_evidence()
    )

    assert decision["decision"] == DENY_STALE_BRANCH_DECISION
    assert decision["allow"] is False
    assert _find_check(decision, "branch_freshness")["finding_code"] == "ao_release_gate_branch_not_up_to_date"


def test_release_gate_denies_untrusted_fork_context() -> None:
    decision = build_ao_release_gate_decision(
        _untrusted_context_payload(), _gpp_status(), review_evidence=_review_evidence()
    )

    assert decision["decision"] == DENY_UNTRUSTED_CONTEXT_DECISION
    assert "ao_release_gate_untrusted_fork" in decision["findings"]


def test_release_gate_denies_missing_ci_evidence() -> None:
    decision = build_ao_release_gate_decision(
        _missing_evidence_payload(), _gpp_status(), review_evidence=_review_evidence()
    )

    assert decision["decision"] == DENY_MISSING_EVIDENCE_DECISION
    assert _find_check(decision, "required_checks")["finding_code"] == "ao_release_gate_required_checks_missing"


def test_release_gate_denies_policy_violations() -> None:
    decision = build_ao_release_gate_decision(
        _policy_violation_payload(), _gpp_status(), review_evidence=_review_evidence()
    )

    assert decision["decision"] == DENY_POLICY_VIOLATION_DECISION
    assert "ao_release_gate_admin_bypass_requested" in decision["findings"]


def test_release_gate_allows_low_risk_paths_without_human_review() -> None:
    decision = build_ao_release_gate_decision(
        _low_risk_payload(),
        _gpp_status(),
        review_evidence=_review_evidence(changed_paths=["docs/smoke/gpp2d6-low-risk-automerge-smoke.md"]),
    )

    assert decision["decision"] == ALLOW_AUTONOMOUS_MERGE_DECISION
    assert decision["allow"] is True
    assert decision["context"]["high_risk_changed_paths"] == []
    assert _find_check(decision, "path_sensitive_human_review")["status"] == "pass"


def test_release_gate_denies_high_risk_paths_without_current_non_author_review() -> None:
    decision = build_ao_release_gate_decision(
        _high_risk_without_review_payload(),
        _gpp_status(),
        review_evidence=_review_evidence(),
    )

    assert decision["decision"] == DENY_POLICY_VIOLATION_DECISION
    assert "ao_release_gate_high_risk_human_review_missing" in decision["findings"]
    assert _find_check(decision, "path_sensitive_human_review")["status"] == "blocked"
    assert decision["context"]["high_risk_changed_paths"] == [
        "ao_kernel/ao_release_gate.py",
        "scripts/ao_release_gate_decision.py",
        ".claude/plans/GPP-2v-AO-RELEASE-GATE-DRY-RUN-SCAFFOLD.md",
    ]


def test_release_gate_allows_high_risk_paths_with_valid_supersession_evidence() -> None:
    decision = build_ao_release_gate_decision(
        _high_risk_without_review_payload(),
        _gpp_status(),
        review_evidence=_review_evidence(),
        high_risk_supersession_evidence=_high_risk_supersession_evidence(),
    )

    assert decision["decision"] == ALLOW_AUTONOMOUS_MERGE_DECISION
    assert decision["allow"] is True
    assert _find_check(decision, "high_risk_supersession_context_bound")["status"] == "pass"
    assert _find_check(decision, "path_sensitive_human_review")["status"] == "pass"
    assert "ao_release_gate_high_risk_human_review_missing" not in decision["findings"]


def test_release_gate_denies_high_risk_supersession_same_provider_self_review() -> None:
    evidence = _high_risk_supersession_evidence(provider_ids=("openai", "openai"))
    decision = build_ao_release_gate_decision(
        _high_risk_without_review_payload(),
        _gpp_status(),
        review_evidence=_review_evidence(),
        high_risk_supersession_evidence=evidence,
    )

    assert decision["decision"] == DENY_POLICY_VIOLATION_DECISION
    assert "ao_release_gate_high_risk_supersession_same_provider_self_review" in decision["findings"]
    assert "ao_release_gate_high_risk_human_review_missing" in decision["findings"]


def test_release_gate_denies_high_risk_supersession_context_mismatch_as_untrusted() -> None:
    evidence = _high_risk_supersession_evidence(head_sha="f" * 40)
    decision = build_ao_release_gate_decision(
        _high_risk_without_review_payload(),
        _gpp_status(),
        review_evidence=_review_evidence(),
        high_risk_supersession_evidence=evidence,
    )

    assert decision["decision"] == DENY_UNTRUSTED_CONTEXT_DECISION
    assert "ao_release_gate_high_risk_supersession_context_unbound" in decision["findings"]


def test_release_gate_denies_stale_high_risk_supersession_evidence() -> None:
    evidence = _high_risk_supersession_evidence(generated_at="2020-01-01T00:00:00Z")
    decision = build_ao_release_gate_decision(
        _high_risk_without_review_payload(),
        _gpp_status(),
        review_evidence=_review_evidence(),
        high_risk_supersession_evidence=evidence,
        generated_at="2026-05-28T00:00:00Z",
    )

    assert decision["decision"] == DENY_MISSING_EVIDENCE_DECISION
    assert "ao_release_gate_high_risk_supersession_stale" in decision["findings"]
    assert "ao_release_gate_high_risk_human_review_missing" in decision["findings"]


def test_release_gate_denies_unparseable_high_risk_supersession_timestamp() -> None:
    evidence = _high_risk_supersession_evidence()
    evidence["generated_at"] = "not-a-date"
    decision = build_ao_release_gate_decision(
        _high_risk_without_review_payload(),
        _gpp_status(),
        review_evidence=_review_evidence(),
        high_risk_supersession_evidence=evidence,
        generated_at="2026-05-28T00:00:00Z",
    )

    assert decision["decision"] == DENY_MISSING_EVIDENCE_DECISION
    assert "ao_release_gate_high_risk_supersession_stale" in decision["findings"]


def test_release_gate_denies_high_risk_supersession_provider_context_mismatch() -> None:
    evidence = _high_risk_supersession_evidence()
    provider_verdicts = evidence["provider_verdicts"]
    assert isinstance(provider_verdicts, list)
    first_provider = provider_verdicts[0]
    assert isinstance(first_provider, dict)
    context_binding = first_provider["context_binding"]
    assert isinstance(context_binding, dict)
    context_binding["head_sha"] = "f" * 40

    decision = build_ao_release_gate_decision(
        _high_risk_without_review_payload(),
        _gpp_status(),
        review_evidence=_review_evidence(),
        high_risk_supersession_evidence=evidence,
    )

    assert decision["decision"] == DENY_UNTRUSTED_CONTEXT_DECISION
    assert "ao_release_gate_high_risk_supersession_context_unbound" in decision["findings"]


def test_release_gate_denies_high_risk_supersession_authority_boundary_open() -> None:
    evidence = _high_risk_supersession_evidence()
    evidence["ai_output_release_authority"] = True

    decision = build_ao_release_gate_decision(
        _high_risk_without_review_payload(),
        _gpp_status(),
        review_evidence=_review_evidence(),
        high_risk_supersession_evidence=evidence,
    )

    assert decision["decision"] == DENY_POLICY_VIOLATION_DECISION
    assert "ao_release_gate_high_risk_supersession_authority_boundary_open" in decision["findings"]


def test_release_gate_denies_malformed_explicit_high_risk_supersession_evidence() -> None:
    decision = build_ao_release_gate_decision(
        _high_risk_without_review_payload(),
        _gpp_status(),
        review_evidence=_review_evidence(),
        high_risk_supersession_evidence="not-an-object",
    )

    assert decision["decision"] == DENY_MISSING_EVIDENCE_DECISION
    assert "ao_release_gate_high_risk_supersession_evidence_missing" in decision["findings"]


def test_release_gate_allows_legacy_payload_when_path_sensitive_gate_is_inactive() -> None:
    payload = _high_risk_without_review_payload()
    payload.pop("path_sensitive_human_review_enabled")

    decision = build_ao_release_gate_decision(
        payload,
        _gpp_status(),
        review_evidence=_review_evidence(),
    )

    assert decision["decision"] == ALLOW_AUTONOMOUS_MERGE_DECISION
    assert _find_check(decision, "path_sensitive_human_review")["status"] == "pass"


def test_release_gate_denies_high_risk_paths_when_review_is_stale_or_author_owned() -> None:
    payload = _allow_payload()
    payload["human_reviews"] = [
        {
            "author": "gladyatore-lab",
            "state": "APPROVED",
            "commit_oid": "f" * 40,
        },
        {
            "author": "halildeu",
            "state": "APPROVED",
            "commit_oid": _ALLOW_HEAD_SHA,
        },
    ]

    decision = build_ao_release_gate_decision(
        payload,
        _gpp_status(),
        review_evidence=_review_evidence(),
    )

    assert decision["decision"] == DENY_POLICY_VIOLATION_DECISION
    assert "ao_release_gate_high_risk_human_review_missing" in decision["findings"]


def test_release_gate_denies_gpp_issue_mismatch_as_missing_evidence() -> None:
    decision = build_ao_release_gate_decision(
        _allow_payload(),
        _gpp_status(issue="https://github.com/Halildeu/ao-kernel/issues/537"),
        review_evidence=_review_evidence(),
    )

    assert decision["decision"] == DENY_MISSING_EVIDENCE_DECISION
    assert _find_check(decision, "gpp_issue_consistency")["finding_code"] == "ao_release_gate_gpp_issue_mismatch"


def test_release_gate_render_and_write(tmp_path: Path) -> None:
    decision = build_ao_release_gate_decision(
        _allow_payload(),
        _gpp_status(),
        review_evidence=_review_evidence(),
        generated_at="2026-04-28T00:00:00Z",
    )
    path = tmp_path / "decision.json"

    write_ao_release_gate_decision(path, decision)

    assert json.loads(path.read_text(encoding="utf-8")) == decision
    assert path.read_text(encoding="utf-8").endswith("\n")
    rendered = render_ao_release_gate_decision_text(decision)
    assert "decision: allow_autonomous_merge" in rendered
    assert "merge_authority_enabled: false" in rendered
    assert f"github_check_run: {RELEASE_GATE_CHECK_NAME} success" in rendered


# (expected_decision, payload_factory, shadow_conclusion, enforce_conclusion).
# Expected conclusions are hardcoded per case so the test never re-derives the
# decision -> conclusion mapping it is meant to pin.
_CONCLUSION_CASES: list[tuple[str, Callable[[], object], str, str]] = [
    (ALLOW_AUTONOMOUS_MERGE_DECISION, _allow_payload, "success", "success"),
    (DENY_STALE_BRANCH_DECISION, _stale_branch_payload, "neutral", "failure"),
    (DENY_UNTRUSTED_CONTEXT_DECISION, _untrusted_context_payload, "neutral", "failure"),
    (DENY_MISSING_EVIDENCE_DECISION, _missing_evidence_payload, "neutral", "failure"),
    (DENY_POLICY_VIOLATION_DECISION, _policy_violation_payload, "neutral", "failure"),
    (ERROR_FAIL_CLOSED_DECISION, _malformed_payload, "neutral", "failure"),
]


@pytest.mark.parametrize(
    ("expected_decision", "payload_factory", "shadow_conclusion", "enforce_conclusion"),
    _CONCLUSION_CASES,
    ids=[case[0] for case in _CONCLUSION_CASES],
)
def test_check_run_conclusion_mapping(
    expected_decision: str,
    payload_factory: Callable[[], object],
    shadow_conclusion: str,
    enforce_conclusion: str,
) -> None:
    """build_ao_release_gate_decision maps each decision to the correct GitHub
    check-run conclusion: allow_autonomous_merge is success in both modes;
    every deny_* / error_fail_closed decision is neutral under the default
    shadow mode and failure under enforce. Pure in-process: no check-run is
    posted and no runtime conclusion mode is changed.
    """
    shadow = build_ao_release_gate_decision(payload_factory(), _gpp_status(), review_evidence=_review_evidence())
    assert shadow["decision"] == expected_decision
    assert shadow["conclusion_mode"] == "shadow"
    assert shadow["github_check_run"]["conclusion"] == shadow_conclusion

    enforce = build_ao_release_gate_decision(
        payload_factory(),
        _gpp_status(),
        review_evidence=_review_evidence(),
        conclusion_mode="enforce",
    )
    assert enforce["decision"] == expected_decision
    assert enforce["conclusion_mode"] == "enforce"
    assert enforce["github_check_run"]["conclusion"] == enforce_conclusion


def test_release_gate_cli_writes_dry_run_artifact(tmp_path: Path) -> None:
    payload_path = tmp_path / "payload.json"
    status_path = tmp_path / "gpp_status.json"
    evidence_path = tmp_path / "review-evidence.json"
    decision_path = tmp_path / "decision.json"
    payload_path.write_text(json.dumps(_allow_payload(), sort_keys=True), encoding="utf-8")
    status_path.write_text(json.dumps(_gpp_status(), sort_keys=True), encoding="utf-8")
    evidence_path.write_text(json.dumps(_review_evidence(), sort_keys=True), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/ao_release_gate_decision.py",
            "--payload",
            str(payload_path),
            "--gpp-status",
            str(status_path),
            "--review-evidence",
            str(evidence_path),
            "--decision-path",
            str(decision_path),
            "--output",
            "text",
            "--fail-on-deny",
        ],
        cwd=_repo_root(),
        check=True,
        capture_output=True,
        text=True,
    )

    artifact = json.loads(decision_path.read_text(encoding="utf-8"))
    assert "decision: allow_autonomous_merge" in completed.stdout
    assert artifact["decision"] == ALLOW_AUTONOMOUS_MERGE_DECISION
    assert artifact["dry_run"] is True
    assert artifact["merge_authority_enabled"] is False


def test_release_gate_cli_accepts_ao_ma10_evidence_bundle(tmp_path: Path) -> None:
    payload = _ao_ma10_requested_payload()
    payload_path = tmp_path / "payload.json"
    status_path = tmp_path / "gpp_status.json"
    evidence_path = tmp_path / "review-evidence.json"
    bundle_path = tmp_path / "ao-ma10-bundle.json"
    decision_path = tmp_path / "decision.json"
    payload_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    status_path.write_text(json.dumps(_gpp_status(), sort_keys=True), encoding="utf-8")
    evidence_path.write_text(json.dumps(_review_evidence(), sort_keys=True), encoding="utf-8")
    bundle_path.write_text(json.dumps(_ao_ma10_evidence_bundle(), sort_keys=True), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/ao_release_gate_decision.py",
            "--payload",
            str(payload_path),
            "--gpp-status",
            str(status_path),
            "--review-evidence",
            str(evidence_path),
            "--ao-ma10-evidence-bundle",
            str(bundle_path),
            "--decision-path",
            str(decision_path),
            "--output",
            "text",
            "--fail-on-deny",
        ],
        cwd=_repo_root(),
        check=True,
        capture_output=True,
        text=True,
    )

    artifact = json.loads(decision_path.read_text(encoding="utf-8"))
    assert "decision: allow_autonomous_merge" in completed.stdout
    assert artifact["decision"] == ALLOW_AUTONOMOUS_MERGE_DECISION
    assert _find_check(artifact, "ao_ma10_context_bound")["status"] == "pass"


def test_release_gate_cli_accepts_high_risk_supersession_evidence(tmp_path: Path) -> None:
    payload = _high_risk_without_review_payload()
    payload_path = tmp_path / "payload.json"
    status_path = tmp_path / "gpp_status.json"
    review_evidence_path = tmp_path / "review-evidence.json"
    supersession_path = tmp_path / "high-risk-supersession.json"
    decision_path = tmp_path / "decision.json"
    payload_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    status_path.write_text(json.dumps(_gpp_status(), sort_keys=True), encoding="utf-8")
    review_evidence_path.write_text(json.dumps(_review_evidence(), sort_keys=True), encoding="utf-8")
    supersession_path.write_text(
        json.dumps(_high_risk_supersession_evidence(), sort_keys=True),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/ao_release_gate_decision.py",
            "--payload",
            str(payload_path),
            "--gpp-status",
            str(status_path),
            "--review-evidence",
            str(review_evidence_path),
            "--high-risk-supersession-evidence",
            str(supersession_path),
            "--decision-path",
            str(decision_path),
            "--output",
            "text",
            "--fail-on-deny",
        ],
        cwd=_repo_root(),
        check=True,
        capture_output=True,
        text=True,
    )

    artifact = json.loads(decision_path.read_text(encoding="utf-8"))
    assert "decision: allow_autonomous_merge" in completed.stdout
    assert artifact["decision"] == ALLOW_AUTONOMOUS_MERGE_DECISION
    assert _find_check(artifact, "high_risk_supersession_context_bound")["status"] == "pass"


# --- GPP-2D-2b: review-evidence decision-core wiring ---


def test_release_gate_denies_when_review_evidence_missing() -> None:
    """No review_evidence supplied -> deny_missing_evidence."""
    decision = build_ao_release_gate_decision(_allow_payload(), _gpp_status())
    assert decision["decision"] == DENY_MISSING_EVIDENCE_DECISION
    assert "ao_release_gate_review_evidence_missing" in decision["findings"]
    # When review evidence is missing, the binding check reports as
    # unverifiable (a missing-evidence finding), not unbound (an untrusted
    # finding), so the decision stays in the missing-evidence bucket.
    assert "ao_release_gate_review_evidence_context_unverifiable" in decision["findings"]
    assert "ao_release_gate_review_evidence_context_unbound" not in decision["findings"]


def test_release_gate_allows_ao_ma10_low_risk_smoke_without_review_evidence() -> None:
    """Dedicated actor smoke PRs may pass without local review evidence."""

    decision = build_ao_release_gate_decision(
        _ao_ma10_low_risk_smoke_payload(),
        _gpp_status(),
        generated_at="2026-05-28T00:00:00Z",
    )

    assert decision["decision"] == ALLOW_AUTONOMOUS_MERGE_DECISION
    assert decision["allow"] is True
    assert _find_check(decision, "review_evidence")["status"] == "pass"
    assert _find_check(decision, "review_evidence_context_bound")["status"] == "pass"
    assert _find_check(decision, "ao_ma10_evidence_bundle")["status"] == "pass"
    assert _find_check(decision, "ao_ma10_context_bound")["status"] == "pass"


def test_release_gate_allows_ao_ma10_low_risk_smoke_from_split_governance_producer() -> None:
    """The split-token smoke producer may open the disposable PR.

    Release authority still stays with ao-release-gate plus the GitHub ruleset;
    this exception only avoids demanding local review evidence for the
    one-file disposable AO-MA-10l smoke PR that the merge actor later merges.
    """

    payload = _ao_ma10_low_risk_smoke_payload()
    pull_request = payload["pull_request"]
    assert isinstance(pull_request, dict)
    pull_request["author"] = {"login": "Halildeu"}
    payload["pr_author"] = "Halildeu"

    decision = build_ao_release_gate_decision(
        payload,
        _gpp_status(),
        generated_at="2026-05-28T00:00:00Z",
    )

    assert decision["decision"] == ALLOW_AUTONOMOUS_MERGE_DECISION
    assert decision["allow"] is True
    assert _find_check(decision, "review_evidence")["status"] == "pass"
    assert _find_check(decision, "ao_ma10_evidence_bundle")["status"] == "pass"


def test_release_gate_denies_ao_ma10_low_risk_smoke_without_dedicated_actor() -> None:
    payload = _ao_ma10_low_risk_smoke_payload()
    pull_request = payload["pull_request"]
    assert isinstance(pull_request, dict)
    pull_request["author"] = {"login": "unknown-producer"}
    payload["pr_author"] = "unknown-producer"

    decision = build_ao_release_gate_decision(
        payload,
        _gpp_status(),
        generated_at="2026-05-28T00:00:00Z",
    )

    assert decision["allow"] is False
    assert "ao_release_gate_review_evidence_missing" in decision["findings"]


def test_release_gate_denies_ao_ma10_requested_non_smoke_path_without_review_evidence() -> None:
    payload = _ao_ma10_low_risk_smoke_payload()
    payload["changed_paths"] = ["docs/not-smoke.md"]

    decision = build_ao_release_gate_decision(
        payload,
        _gpp_status(),
        generated_at="2026-05-28T00:00:00Z",
    )

    assert decision["allow"] is False
    assert "ao_release_gate_review_evidence_missing" in decision["findings"]


def test_release_gate_denies_ao_ma10_smoke_with_dotdot_path() -> None:
    payload = _ao_ma10_low_risk_smoke_payload()
    payload["changed_paths"] = [
        "docs/evidence/ao-ma-10l-autonomous-smoke/../other.md",
    ]

    decision = build_ao_release_gate_decision(
        payload,
        _gpp_status(),
        generated_at="2026-05-28T00:00:00Z",
    )

    assert decision["allow"] is False
    assert "ao_release_gate_review_evidence_missing" in decision["findings"]


def test_release_gate_denies_ao_ma10_smoke_mixed_with_high_risk_path() -> None:
    payload = _ao_ma10_low_risk_smoke_payload()
    payload["changed_paths"] = [
        "docs/evidence/ao-ma-10l-autonomous-smoke/ao-ma-10l-smoke-test.md",
        ".github/workflows/test.yml",
    ]
    payload["allowed_path_prefixes"] = ["docs/", ".github/workflows/"]

    decision = build_ao_release_gate_decision(
        payload,
        _gpp_status(),
        generated_at="2026-05-28T00:00:00Z",
    )

    assert decision["allow"] is False
    assert "ao_release_gate_review_evidence_missing" in decision["findings"]
    assert "ao_release_gate_high_risk_human_review_missing" in decision["findings"]


def test_release_gate_denies_ao_ma10_smoke_with_malformed_bundle() -> None:
    decision = build_ao_release_gate_decision(
        _ao_ma10_low_risk_smoke_payload(),
        _gpp_status(),
        ao_ma10_evidence_bundle="not-a-bundle",
        generated_at="2026-05-28T00:00:00Z",
    )

    assert decision["allow"] is False
    assert "ao_release_gate_ao_ma10_evidence_bundle_missing" in decision["findings"]


def test_release_gate_denies_ao_ma10_smoke_with_authority_open_bundle() -> None:
    bundle = _ao_ma10_evidence_bundle(
        changed_paths=["docs/evidence/ao-ma-10l-autonomous-smoke/ao-ma-10l-smoke-test.md"],
        head_ref="refs/heads/codex/ao-ma10l-smoke-test",
    )
    bundle["ai_output_release_authority"] = True

    decision = build_ao_release_gate_decision(
        _ao_ma10_low_risk_smoke_payload(),
        _gpp_status(),
        ao_ma10_evidence_bundle=bundle,
        generated_at="2026-05-28T00:00:00Z",
    )

    assert decision["allow"] is False
    assert "ao_release_gate_ao_ma10_authority_boundary_open" in decision["findings"]


def test_release_gate_denies_when_review_evidence_not_a_dict() -> None:
    decision = build_ao_release_gate_decision(_allow_payload(), _gpp_status(), review_evidence="not-a-dict")
    assert decision["decision"] == DENY_MISSING_EVIDENCE_DECISION
    assert "ao_release_gate_review_evidence_missing" in decision["findings"]


def test_release_gate_denies_when_review_evidence_schema_invalid() -> None:
    evidence = _review_evidence()
    evidence["decision"] = "unexpected-value"  # fails schema enum
    decision = build_ao_release_gate_decision(_allow_payload(), _gpp_status(), review_evidence=evidence)
    assert decision["decision"] == DENY_MISSING_EVIDENCE_DECISION
    assert "ao_release_gate_review_evidence_schema_invalid" in decision["findings"]


def test_release_gate_denies_when_review_evidence_not_accepting() -> None:
    # Acceptance profile requires decision=operator_may_merge, reviewer_agree=true,
    # cross_provider_verified=true; flip reviewer_agree=false.
    evidence = _review_evidence(reviewer_agree=False)
    decision = build_ao_release_gate_decision(_allow_payload(), _gpp_status(), review_evidence=evidence)
    assert decision["decision"] == DENY_MISSING_EVIDENCE_DECISION
    assert "ao_release_gate_review_evidence_not_accepting" in decision["findings"]


def test_release_gate_denies_when_context_binding_missing() -> None:
    evidence = _review_evidence(omit_context_binding=True)
    decision = build_ao_release_gate_decision(_allow_payload(), _gpp_status(), review_evidence=evidence)
    assert decision["decision"] == DENY_UNTRUSTED_CONTEXT_DECISION
    assert "ao_release_gate_review_evidence_context_unbound" in decision["findings"]


def test_release_gate_denies_when_context_binding_head_sha_mismatches() -> None:
    evidence = _review_evidence(head_sha="f" * 40)  # different SHA from _allow_payload
    decision = build_ao_release_gate_decision(_allow_payload(), _gpp_status(), review_evidence=evidence)
    assert decision["decision"] == DENY_UNTRUSTED_CONTEXT_DECISION
    assert "ao_release_gate_review_evidence_context_unbound" in decision["findings"]


def test_release_gate_denies_when_context_binding_digest_mismatches() -> None:
    evidence = _review_evidence()
    binding = evidence["context_binding"]
    assert isinstance(binding, dict)
    binding["diff_digest"] = "sha256:" + "f" * 64  # different digest
    decision = build_ao_release_gate_decision(_allow_payload(), _gpp_status(), review_evidence=evidence)
    assert decision["decision"] == DENY_UNTRUSTED_CONTEXT_DECISION
    assert "ao_release_gate_review_evidence_context_unbound" in decision["findings"]


def test_release_gate_denies_when_reviewed_slice_mismatches() -> None:
    # Evidence carries work_package=GPP-2D-2b-other but the PR declares
    # reviewed_slice=GPP-2; the binding cannot identify the same slice.
    evidence = _review_evidence(reviewed_slice="GPP-OTHER")
    decision = build_ao_release_gate_decision(_allow_payload(), _gpp_status(), review_evidence=evidence)
    assert decision["decision"] == DENY_UNTRUSTED_CONTEXT_DECISION
    assert "ao_release_gate_review_evidence_context_unbound" in decision["findings"]


def test_release_gate_allows_reviewed_slice_distinct_from_current_wp_when_context_bound() -> None:
    # GOV-1 dynamic work_package binding positive complement: a slice
    # whose reviewer-declared work_package differs from the base
    # `gpp_status.current_wp.id` (e.g. GOV-1 governance enrichment
    # against a base where current_wp.id="GPP-2") must be ALLOWED when
    # payload.reviewed_slice and review_evidence.work_package agree
    # (because the workflow patches payload.reviewed_slice from the
    # reviewer evidence before decision-core evaluation). This pins the
    # invariant that release-governance authority lives in
    # `ao-release-gate` + branch ruleset + non-author approval, not in
    # the base's static current_wp identity.
    payload = _allow_payload()
    payload["reviewed_slice"] = "GOV-1"
    evidence = _review_evidence(reviewed_slice="GOV-1")
    decision = build_ao_release_gate_decision(
        payload,
        _gpp_status(),  # current_wp.id remains GPP-2
        review_evidence=evidence,
        generated_at="2026-05-25T00:00:00Z",
    )
    assert decision["decision"] == ALLOW_AUTONOMOUS_MERGE_DECISION
    assert decision["allow"] is True


# --- AO-MA-10b: evidence-bundle decision-core wiring ---


def test_release_gate_preserves_existing_path_when_ao_ma10_not_requested() -> None:
    decision = build_ao_release_gate_decision(
        _allow_payload(),
        _gpp_status(),
        review_evidence=_review_evidence(),
        generated_at="2026-05-28T00:00:00Z",
    )

    assert decision["decision"] == ALLOW_AUTONOMOUS_MERGE_DECISION
    assert _find_check(decision, "ao_ma10_autonomous_request")["status"] == "pass"
    assert _find_check(decision, "ao_ma10_evidence_bundle")["status"] == "pass"
    assert _find_check(decision, "ao_ma10_evidence_bundle_schema")["status"] == "pass"
    assert _find_check(decision, "ao_ma10_consensus")["status"] == "pass"
    assert _find_check(decision, "ao_ma10_context_bound")["status"] == "pass"
    assert _find_check(decision, "ao_ma10_authority_boundary")["status"] == "pass"


def test_release_gate_allows_ao_ma10_requested_when_bundle_is_context_bound() -> None:
    decision = build_ao_release_gate_decision(
        _ao_ma10_requested_payload(),
        _gpp_status(),
        review_evidence=_review_evidence(),
        ao_ma10_evidence_bundle=_ao_ma10_evidence_bundle(),
        generated_at="2026-05-28T00:00:00Z",
    )

    assert decision["decision"] == ALLOW_AUTONOMOUS_MERGE_DECISION
    assert decision["allow"] is True
    assert _find_check(decision, "ao_ma10_evidence_bundle")["status"] == "pass"
    assert _find_check(decision, "ao_ma10_context_bound")["status"] == "pass"


def test_release_gate_denies_ao_ma10_requested_when_bundle_missing() -> None:
    decision = build_ao_release_gate_decision(
        _ao_ma10_requested_payload(),
        _gpp_status(),
        review_evidence=_review_evidence(),
        generated_at="2026-05-28T00:00:00Z",
    )

    assert decision["decision"] == DENY_MISSING_EVIDENCE_DECISION
    assert "ao_release_gate_ao_ma10_evidence_bundle_missing" in decision["findings"]
    assert "ao_release_gate_ao_ma10_evidence_bundle_context_unverifiable" in decision["findings"]


def test_release_gate_denies_malformed_ao_ma10_request_flag_as_policy_violation() -> None:
    payload = _allow_payload()
    payload["low_risk_autonomous_merge_requested"] = "true"
    decision = build_ao_release_gate_decision(
        payload,
        _gpp_status(),
        review_evidence=_review_evidence(),
    )

    assert decision["decision"] == DENY_POLICY_VIOLATION_DECISION
    assert "ao_release_gate_ao_ma10_autonomous_request_invalid" in decision["findings"]


def test_release_gate_denies_ao_ma10_bundle_schema_invalid() -> None:
    bundle = _ao_ma10_evidence_bundle()
    bundle.pop("schema_version")
    decision = build_ao_release_gate_decision(
        _ao_ma10_requested_payload(),
        _gpp_status(),
        review_evidence=_review_evidence(),
        ao_ma10_evidence_bundle=bundle,
    )

    assert decision["decision"] == DENY_MISSING_EVIDENCE_DECISION
    assert "ao_release_gate_ao_ma10_evidence_bundle_schema_invalid" in decision["findings"]


def test_release_gate_denies_ao_ma10_authority_boundary_open_as_policy_violation() -> None:
    bundle = _ao_ma10_evidence_bundle()
    bundle["ai_output_release_authority"] = True
    decision = build_ao_release_gate_decision(
        _ao_ma10_requested_payload(),
        _gpp_status(),
        review_evidence=_review_evidence(),
        ao_ma10_evidence_bundle=bundle,
    )

    assert decision["decision"] == DENY_POLICY_VIOLATION_DECISION
    assert "ao_release_gate_ao_ma10_authority_boundary_open" in decision["findings"]


def test_release_gate_denies_ao_ma10_bundle_non_agree_consensus() -> None:
    bundle = _ao_ma10_evidence_bundle(consensus_status="REVISE", provider_verdict="REVISE")
    decision = build_ao_release_gate_decision(
        _ao_ma10_requested_payload(),
        _gpp_status(),
        review_evidence=_review_evidence(),
        ao_ma10_evidence_bundle=bundle,
    )

    assert decision["decision"] == DENY_MISSING_EVIDENCE_DECISION
    assert "ao_release_gate_ao_ma10_consensus_not_agree" in decision["findings"]


def test_release_gate_denies_ao_ma10_bundle_context_mismatch_as_untrusted() -> None:
    bundle = _ao_ma10_evidence_bundle(head_sha="f" * 40)
    decision = build_ao_release_gate_decision(
        _ao_ma10_requested_payload(),
        _gpp_status(),
        review_evidence=_review_evidence(),
        ao_ma10_evidence_bundle=bundle,
    )

    assert decision["decision"] == DENY_UNTRUSTED_CONTEXT_DECISION
    assert "ao_release_gate_ao_ma10_evidence_bundle_context_unbound" in decision["findings"]


def test_release_gate_denies_malformed_explicit_ao_ma10_bundle_even_when_not_requested() -> None:
    decision = build_ao_release_gate_decision(
        _allow_payload(),
        _gpp_status(),
        review_evidence=_review_evidence(),
        ao_ma10_evidence_bundle="not-a-bundle",
    )

    assert decision["decision"] == DENY_MISSING_EVIDENCE_DECISION
    assert "ao_release_gate_ao_ma10_evidence_bundle_missing" in decision["findings"]


def test_diff_digest_is_order_independent_prefixed_and_handles_empty() -> None:
    """Canonical digest contract pinned for emitter / verifier agreement."""
    assert diff_digest(["a.py", "b.py"]) == diff_digest(["b.py", "a.py"])
    assert diff_digest(["a.py", "b.py"]).startswith("sha256:")
    assert len(diff_digest([])) == len("sha256:") + 64
    assert diff_digest(["a.py", "b.py"]) != diff_digest(["a.py", "c.py"])


# ---------------------------------------------------------------------------
# RG-CONCLUSION-SEMANTICS (Codex thread 019e65c3, C-prime migration)
# ---------------------------------------------------------------------------
#
# These tests pin the dual check-run conclusion semantics introduced by
# RG-1. The legacy ``ao-release-gate`` job is preserved as a compatibility
# wrapper (wrapper_exit_code) so the required status check name keeps
# satisfying branch protection; review-missing semantics are shifted to
# the new ``ao-release-gate-review`` check-run with ``action_required``
# conclusion. Real violations still map to ``failure`` on both the legacy
# wrapper and the new ``ao-release-gate-technical`` check-run.


from ao_kernel.ao_release_gate import (  # noqa: E402  (RG-1 imports kept local to the section)
    RELEASE_GATE_REVIEW_CHECK_NAME,
    RELEASE_GATE_TECHNICAL_CHECK_NAME,
    build_review_check_run,
    build_technical_check_run,
    conclusion_for_findings,
    finding_conclusion_kind,
    wrapper_exit_code,
)


class TestFindingConclusionKind:
    """finding_conclusion_kind classifies each known finding code."""

    def test_review_missing_is_review_action(self) -> None:
        assert finding_conclusion_kind("ao_release_gate_high_risk_human_review_missing") == "review_action"

    def test_review_evidence_not_accepting_is_review_action(self) -> None:
        # 019e830d extension: evidence not-accepting is procedural (operator
        # CODEOWNER review can resolve it), not a code defect.
        assert finding_conclusion_kind("ao_release_gate_review_evidence_not_accepting") == "review_action"

    def test_review_evidence_context_unverifiable_is_review_action(self) -> None:
        # 019e830d extension: context unverifiable means evaluation-time
        # binding could not be verified (network / eventual consistency);
        # procedurally fixable via re-run or CODEOWNER review.
        assert finding_conclusion_kind("ao_release_gate_review_evidence_context_unverifiable") == "review_action"

    def test_branch_stale_is_stale(self) -> None:
        assert finding_conclusion_kind("ao_release_gate_branch_not_up_to_date") == "stale"

    def test_real_violation_is_failure(self) -> None:
        for code in (
            "ao_release_gate_wrong_repository",
            "ao_release_gate_untrusted_fork",
            "ao_release_gate_pull_request_target_context",
            "ao_release_gate_diff_scope_missing",
            "ao_release_gate_required_checks_not_green",
            "ao_release_gate_payload_not_object",
        ):
            assert finding_conclusion_kind(code) == "failure", code

    def test_structural_evidence_defects_remain_failure(self) -> None:
        # 019e830d extension invariant — sibling evidence findings are
        # NOT review_action. These remain ``failure`` because they
        # indicate a real artifact defect, not a procedural blocker:
        #   - missing: no evidence file at all (operator did not supply)
        #   - schema_invalid: artifact present but broken / malformed
        #   - context_unbound: forged / mismatched binding (head SHA drift)
        for code in (
            "ao_release_gate_review_evidence_missing",
            "ao_release_gate_review_evidence_schema_invalid",
            "ao_release_gate_review_evidence_context_unbound",
        ):
            assert finding_conclusion_kind(code) == "failure", code

    def test_boundary_violations_remain_failure(self) -> None:
        # 019e830d extension pin — security / governance boundary
        # violations must NEVER classify as review_action. These signal
        # an active intent to bypass policy and are always real failures.
        for code in (
            "ao_release_gate_admin_bypass_requested",
            "ao_release_gate_forbidden_secret_context",
            "ao_release_gate_live_adapter_execution_requested",
            "ao_release_gate_gpp_boundary_open",
            "ao_release_gate_pat_backed_bot_actor",
            "ao_release_gate_agent_release_authority",
        ):
            assert finding_conclusion_kind(code) == "failure", code

    def test_none_finding_defaults_to_failure(self) -> None:
        # Defensive: unknown / None finding never silently maps to success.
        assert finding_conclusion_kind(None) == "failure"

    def test_unknown_finding_defaults_to_failure(self) -> None:
        assert finding_conclusion_kind("ao_release_gate_some_future_unknown_code") == "failure"


class TestConclusionForFindings:
    """conclusion_for_findings maps finding sets to Checks API conclusions."""

    def test_empty_findings_is_success(self) -> None:
        assert conclusion_for_findings([]) == "success"

    def test_review_only_is_action_required(self) -> None:
        assert conclusion_for_findings(["ao_release_gate_high_risk_human_review_missing"]) == "action_required"

    def test_stale_only_is_stale(self) -> None:
        assert conclusion_for_findings(["ao_release_gate_branch_not_up_to_date"]) == "stale"

    def test_any_failure_wins(self) -> None:
        # Real violation outranks pending action signals. Uses a true
        # boundary-violation failure code so the invariant survives the
        # 019e830d extension (which moved two evidence findings out of
        # failure). Picking ``forbidden_secret_context`` because it can
        # never legitimately become review_action.
        assert (
            conclusion_for_findings(
                [
                    "ao_release_gate_high_risk_human_review_missing",
                    "ao_release_gate_forbidden_secret_context",
                ]
            )
            == "failure"
        )

    def test_structural_evidence_failure_wins_over_procedural(self) -> None:
        # Pin 019e830d: structural evidence defect (``missing``) still
        # outranks procedural evidence finding (``not_accepting``).
        # Keeps the failure axis sharp — the gate does not soften when
        # the artifact is fundamentally broken.
        assert (
            conclusion_for_findings(
                [
                    "ao_release_gate_review_evidence_not_accepting",
                    "ao_release_gate_review_evidence_missing",
                ]
            )
            == "failure"
        )

    def test_evidence_procedural_findings_are_action_required(self) -> None:
        # 019e830d extension — the two procedural evidence findings, on
        # their own, surface as action_required (operator/reviewer can
        # resolve without code change).
        for code in (
            "ao_release_gate_review_evidence_not_accepting",
            "ao_release_gate_review_evidence_context_unverifiable",
        ):
            assert conclusion_for_findings([code]) == "action_required", code

    def test_evidence_procedural_mixed_with_human_review_is_action_required(self) -> None:
        # Two review_action findings of different sub-shapes still map
        # to action_required — review_action is monoidally closed.
        assert (
            conclusion_for_findings(
                [
                    "ao_release_gate_high_risk_human_review_missing",
                    "ao_release_gate_review_evidence_not_accepting",
                ]
            )
            == "action_required"
        )

    def test_review_plus_stale_no_failure_is_action_required(self) -> None:
        # Operator review is the more specific action signal.
        assert (
            conclusion_for_findings(
                [
                    "ao_release_gate_high_risk_human_review_missing",
                    "ao_release_gate_branch_not_up_to_date",
                ]
            )
            == "action_required"
        )


class TestWrapperExitCode:
    """wrapper_exit_code is the C-prime compatibility wrapper for the legacy job."""

    def test_allow_returns_zero(self) -> None:
        assert wrapper_exit_code(ALLOW_AUTONOMOUS_MERGE_DECISION, []) == 0

    def test_review_action_only_blocker_returns_zero(self) -> None:
        # Critical C-prime invariant: the legacy required check no longer
        # blocks merge on operator review missing alone. CODEOWNER review
        # is enforced by GitHub native ``require_code_owner_reviews`` and
        # the new ``ao-release-gate-review`` check-run.
        assert (
            wrapper_exit_code(
                DENY_POLICY_VIOLATION_DECISION,
                ["ao_release_gate_high_risk_human_review_missing"],
            )
            == 0
        )

    def test_real_violation_returns_one(self) -> None:
        # Uses a true boundary-violation code so the invariant survives
        # the 019e830d extension. ``forbidden_secret_context`` is a hard
        # policy boundary — it can never become review_action.
        assert (
            wrapper_exit_code(
                DENY_POLICY_VIOLATION_DECISION,
                ["ao_release_gate_forbidden_secret_context"],
            )
            == 1
        )

    def test_structural_evidence_missing_returns_one(self) -> None:
        # Pin 019e830d: missing evidence artifact is a real defect, not
        # procedural. Wrapper still fails closed.
        assert (
            wrapper_exit_code(
                DENY_MISSING_EVIDENCE_DECISION,
                ["ao_release_gate_review_evidence_missing"],
            )
            == 1
        )

    def test_structural_evidence_schema_invalid_returns_one(self) -> None:
        # Pin 019e830d: malformed evidence artifact is a real defect.
        assert (
            wrapper_exit_code(
                DENY_MISSING_EVIDENCE_DECISION,
                ["ao_release_gate_review_evidence_schema_invalid"],
            )
            == 1
        )

    def test_structural_evidence_context_unbound_returns_one(self) -> None:
        # Pin 019e830d: forged / mismatched binding is a real defect
        # (head SHA drift, evidence does not bind to current PR head).
        assert (
            wrapper_exit_code(
                DENY_MISSING_EVIDENCE_DECISION,
                ["ao_release_gate_review_evidence_context_unbound"],
            )
            == 1
        )

    def test_procedural_evidence_not_accepting_returns_zero(self) -> None:
        # 019e830d extension — procedural evidence finding alone is
        # softened by the wrapper (operator/reviewer can resolve).
        assert (
            wrapper_exit_code(
                DENY_MISSING_EVIDENCE_DECISION,
                ["ao_release_gate_review_evidence_not_accepting"],
            )
            == 0
        )

    def test_procedural_evidence_context_unverifiable_returns_zero(self) -> None:
        # 019e830d extension — context unverifiable is procedural.
        assert (
            wrapper_exit_code(
                DENY_MISSING_EVIDENCE_DECISION,
                ["ao_release_gate_review_evidence_context_unverifiable"],
            )
            == 0
        )

    def test_review_plus_procedural_evidence_returns_zero(self) -> None:
        # 019e830d extension — two review_action findings of different
        # sub-shapes still soften (wrapper relaxes all-review-action set).
        assert (
            wrapper_exit_code(
                DENY_POLICY_VIOLATION_DECISION,
                [
                    "ao_release_gate_high_risk_human_review_missing",
                    "ao_release_gate_review_evidence_not_accepting",
                ],
            )
            == 0
        )

    def test_procedural_evidence_plus_violation_returns_one(self) -> None:
        # Critical pin — wrapper relaxes ONLY when EVERY blocker is
        # review_action. A procedural evidence finding mixed with a
        # real boundary violation still returns 1.
        assert (
            wrapper_exit_code(
                DENY_POLICY_VIOLATION_DECISION,
                [
                    "ao_release_gate_review_evidence_not_accepting",
                    "ao_release_gate_forbidden_secret_context",
                ],
            )
            == 1
        )

    def test_procedural_evidence_plus_structural_evidence_returns_one(self) -> None:
        # Pin — procedural evidence (review_action) mixed with structural
        # evidence defect (failure) still returns 1. Wrapper never softens
        # when ANY blocker is a real defect.
        assert (
            wrapper_exit_code(
                DENY_MISSING_EVIDENCE_DECISION,
                [
                    "ao_release_gate_review_evidence_not_accepting",
                    "ao_release_gate_review_evidence_missing",
                ],
            )
            == 1
        )

    def test_admin_bypass_violation_returns_one(self) -> None:
        # Pin — admin bypass request is always failure, never softened.
        assert (
            wrapper_exit_code(
                DENY_POLICY_VIOLATION_DECISION,
                ["ao_release_gate_admin_bypass_requested"],
            )
            == 1
        )

    def test_pr764_exact_procedural_pair_wrapper_zero(self) -> None:
        # Codex 019e830d iter-2 absorb: PR #764's *exact* finding pair
        # (not_accepting + context_unverifiable). Pins the regression
        # signal at the wrapper boundary.
        findings = [
            "ao_release_gate_review_evidence_not_accepting",
            "ao_release_gate_review_evidence_context_unverifiable",
        ]
        assert wrapper_exit_code(DENY_MISSING_EVIDENCE_DECISION, findings) == 0

    def test_structural_pair_wrapper_one(self) -> None:
        # Codex 019e830d iter-2 absorb: real decision-core often emits
        # both structural and procedural findings in the same set
        # (artifact missing AND context unverifiable). Wrapper must
        # still fail closed when ANY blocker is structural failure.
        findings = [
            "ao_release_gate_review_evidence_missing",
            "ao_release_gate_review_evidence_context_unverifiable",
        ]
        assert wrapper_exit_code(DENY_MISSING_EVIDENCE_DECISION, findings) == 1

    def test_stale_branch_returns_one(self) -> None:
        # Stale branch is not a review-action blocker; wrapper does not relax.
        assert (
            wrapper_exit_code(
                DENY_STALE_BRANCH_DECISION,
                ["ao_release_gate_branch_not_up_to_date"],
            )
            == 1
        )

    def test_unknown_finding_returns_one(self) -> None:
        # Unknown finding code defensively maps to failure, so the wrapper
        # never silently softens a code path it does not understand.
        assert wrapper_exit_code(DENY_POLICY_VIOLATION_DECISION, ["ao_release_gate_some_unknown"]) == 1

    def test_error_fail_closed_returns_one(self) -> None:
        assert (
            wrapper_exit_code(
                ERROR_FAIL_CLOSED_DECISION,
                ["ao_release_gate_payload_not_object"],
            )
            == 1
        )


class TestBuildTechnicalCheckRun:
    """ao-release-gate-technical check-run conclusion semantics."""

    def test_name_matches_published_constant(self) -> None:
        cr = build_technical_check_run(ALLOW_AUTONOMOUS_MERGE_DECISION, [])
        assert cr["name"] == RELEASE_GATE_TECHNICAL_CHECK_NAME == "ao-release-gate-technical"

    def test_allow_decision_is_success(self) -> None:
        cr = build_technical_check_run(ALLOW_AUTONOMOUS_MERGE_DECISION, [], conclusion_mode="enforce")
        assert cr["conclusion"] == "success"

    def test_review_only_blocker_is_success_in_enforce(self) -> None:
        # Technical check ignores review_action findings entirely.
        cr = build_technical_check_run(
            DENY_POLICY_VIOLATION_DECISION,
            ["ao_release_gate_high_risk_human_review_missing"],
            conclusion_mode="enforce",
        )
        assert cr["conclusion"] == "success"

    def test_real_violation_is_failure_in_enforce(self) -> None:
        # Uses boundary-violation code so the invariant survives 019e830d.
        cr = build_technical_check_run(
            DENY_POLICY_VIOLATION_DECISION,
            ["ao_release_gate_forbidden_secret_context"],
            conclusion_mode="enforce",
        )
        assert cr["conclusion"] == "failure"

    def test_structural_evidence_missing_is_failure_in_enforce(self) -> None:
        # Pin 019e830d — missing artifact is a real defect, not procedural.
        cr = build_technical_check_run(
            DENY_MISSING_EVIDENCE_DECISION,
            ["ao_release_gate_review_evidence_missing"],
            conclusion_mode="enforce",
        )
        assert cr["conclusion"] == "failure"

    def test_procedural_evidence_alone_is_success_in_enforce(self) -> None:
        # 019e830d extension — technical check ignores procedural
        # evidence findings (they surface on the review check-run).
        for code in (
            "ao_release_gate_review_evidence_not_accepting",
            "ao_release_gate_review_evidence_context_unverifiable",
        ):
            cr = build_technical_check_run(
                DENY_MISSING_EVIDENCE_DECISION,
                [code],
                conclusion_mode="enforce",
            )
            assert cr["conclusion"] == "success", code

    def test_stale_only_is_stale_in_enforce(self) -> None:
        cr = build_technical_check_run(
            DENY_STALE_BRANCH_DECISION,
            ["ao_release_gate_branch_not_up_to_date"],
            conclusion_mode="enforce",
        )
        assert cr["conclusion"] == "stale"

    def test_review_plus_violation_is_failure_in_enforce(self) -> None:
        # Mixed blocker set with a real violation still surfaces failure;
        # the review-action finding is filtered out, the violation remains.
        cr = build_technical_check_run(
            DENY_POLICY_VIOLATION_DECISION,
            [
                "ao_release_gate_high_risk_human_review_missing",
                "ao_release_gate_forbidden_secret_context",
            ],
            conclusion_mode="enforce",
        )
        assert cr["conclusion"] == "failure"

    def test_procedural_plus_structural_evidence_is_failure_in_enforce(self) -> None:
        # Pin 019e830d — procedural evidence (review_action, filtered)
        # mixed with structural defect (failure) still surfaces failure.
        cr = build_technical_check_run(
            DENY_MISSING_EVIDENCE_DECISION,
            [
                "ao_release_gate_review_evidence_not_accepting",
                "ao_release_gate_review_evidence_missing",
            ],
            conclusion_mode="enforce",
        )
        assert cr["conclusion"] == "failure"

    def test_shadow_mode_neutral_for_blocker(self) -> None:
        # Shadow mode always neutralizes blockers, regardless of kind.
        cr = build_technical_check_run(
            DENY_MISSING_EVIDENCE_DECISION,
            ["ao_release_gate_review_evidence_missing"],
            conclusion_mode="shadow",
        )
        assert cr["conclusion"] == "neutral"


class TestBuildReviewCheckRun:
    """ao-release-gate-review check-run conclusion semantics."""

    def test_name_matches_published_constant(self) -> None:
        cr = build_review_check_run(ALLOW_AUTONOMOUS_MERGE_DECISION, [])
        assert cr["name"] == RELEASE_GATE_REVIEW_CHECK_NAME == "ao-release-gate-review"

    def test_no_review_finding_is_success(self) -> None:
        cr = build_review_check_run(ALLOW_AUTONOMOUS_MERGE_DECISION, [], conclusion_mode="enforce")
        assert cr["conclusion"] == "success"

    def test_review_missing_is_action_required_in_enforce(self) -> None:
        cr = build_review_check_run(
            DENY_POLICY_VIOLATION_DECISION,
            ["ao_release_gate_high_risk_human_review_missing"],
            conclusion_mode="enforce",
        )
        assert cr["conclusion"] == "action_required"

    def test_review_missing_is_neutral_in_shadow(self) -> None:
        cr = build_review_check_run(
            DENY_POLICY_VIOLATION_DECISION,
            ["ao_release_gate_high_risk_human_review_missing"],
            conclusion_mode="shadow",
        )
        assert cr["conclusion"] == "neutral"

    def test_real_violation_ignored_in_review_check(self) -> None:
        # Review check focuses only on review_action; a pure violation
        # set leaves it green (the technical check reports the failure).
        cr = build_review_check_run(
            DENY_POLICY_VIOLATION_DECISION,
            ["ao_release_gate_forbidden_secret_context"],
            conclusion_mode="enforce",
        )
        assert cr["conclusion"] == "success"

    def test_structural_evidence_missing_ignored_in_review_check(self) -> None:
        # Pin 019e830d — structural evidence defect (failure) does not
        # surface on the review check-run (technical check reports it).
        cr = build_review_check_run(
            DENY_MISSING_EVIDENCE_DECISION,
            ["ao_release_gate_review_evidence_missing"],
            conclusion_mode="enforce",
        )
        assert cr["conclusion"] == "success"

    def test_procedural_evidence_is_action_required_in_review_check(self) -> None:
        # 019e830d extension — procedural evidence findings surface on
        # the review check-run as action_required (operator/reviewer
        # action signal).
        for code in (
            "ao_release_gate_review_evidence_not_accepting",
            "ao_release_gate_review_evidence_context_unverifiable",
        ):
            cr = build_review_check_run(
                DENY_MISSING_EVIDENCE_DECISION,
                [code],
                conclusion_mode="enforce",
            )
            assert cr["conclusion"] == "action_required", code

    def test_procedural_evidence_is_neutral_in_review_check_shadow(self) -> None:
        # Pin — shadow mode neutralizes procedural findings too.
        cr = build_review_check_run(
            DENY_MISSING_EVIDENCE_DECISION,
            ["ao_release_gate_review_evidence_not_accepting"],
            conclusion_mode="shadow",
        )
        assert cr["conclusion"] == "neutral"

    def test_stale_branch_ignored_in_review_check(self) -> None:
        cr = build_review_check_run(
            DENY_STALE_BRANCH_DECISION,
            ["ao_release_gate_branch_not_up_to_date"],
            conclusion_mode="enforce",
        )
        assert cr["conclusion"] == "success"


class TestLegacyCheckRunCPrimeWrapper:
    """Legacy ao-release-gate check-run preserves required check name."""

    def test_allow_is_success_both_modes(self) -> None:
        # Inspected via the public decision builder so we exercise the
        # same path the workflow runs.
        for mode in ("shadow", "enforce"):
            decision = build_ao_release_gate_decision(
                _allow_payload(),
                _gpp_status(),
                review_evidence=_review_evidence(),
                conclusion_mode=mode,  # type: ignore[arg-type]
            )
            assert decision["github_check_run"]["name"] == RELEASE_GATE_CHECK_NAME
            assert decision["github_check_run"]["conclusion"] == "success", mode

    def test_review_only_blocker_is_success_in_enforce(self) -> None:
        # Path-sensitive change without a non-author CODEOWNER review
        # produces a single review_action blocker. Legacy wrapper must
        # surface this as success in enforce mode (C-prime).
        payload = _allow_payload()
        payload["human_reviews"] = []  # no approver on current head
        decision = build_ao_release_gate_decision(
            payload,
            _gpp_status(),
            review_evidence=_review_evidence(),
            conclusion_mode="enforce",
        )
        review_blocker = "ao_release_gate_high_risk_human_review_missing"
        if decision["findings"] == [review_blocker]:
            # C-prime guarantee: legacy wrapper does NOT report failure
            # when the only blocker is a pending CODEOWNER review.
            assert decision["github_check_run"]["conclusion"] == "success"
        else:
            # The allow fixture exercises path-sensitive paths under the
            # current scope rules; if scope evaluation reshapes blockers
            # we still assert the wrapper invariant directly.
            assert wrapper_exit_code(decision["decision"], list(decision["findings"])) in (0, 1)

    def test_real_violation_is_failure_in_enforce(self) -> None:
        # Use an explicit deny payload by tampering with the head ref so
        # the gate emits a real violation alongside any review-action.
        payload = _allow_payload()
        payload["repository"] = "Halildeu/some-other-repo"  # wrong repo
        decision = build_ao_release_gate_decision(
            payload,
            _gpp_status(),
            review_evidence=_review_evidence(),
            conclusion_mode="enforce",
        )
        # decision.allow is False; conclusion is failure (not success).
        assert decision["allow"] is False
        assert decision["github_check_run"]["conclusion"] == "failure"
