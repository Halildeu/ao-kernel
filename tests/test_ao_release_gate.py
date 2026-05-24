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


def test_diff_digest_is_order_independent_prefixed_and_handles_empty() -> None:
    """Canonical digest contract pinned for emitter / verifier agreement."""
    assert diff_digest(["a.py", "b.py"]) == diff_digest(["b.py", "a.py"])
    assert diff_digest(["a.py", "b.py"]).startswith("sha256:")
    assert len(diff_digest([])) == len("sha256:") + 64
    assert diff_digest(["a.py", "b.py"]) != diff_digest(["a.py", "c.py"])
