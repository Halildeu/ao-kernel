from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from ao_kernel.ao_release_gate import (
    ALLOW_AUTONOMOUS_MERGE_DECISION,
    DENY_MISSING_EVIDENCE_DECISION,
    DENY_POLICY_VIOLATION_DECISION,
    DENY_STALE_BRANCH_DECISION,
    DENY_UNTRUSTED_CONTEXT_DECISION,
    RELEASE_GATE_CHECK_NAME,
    build_ao_release_gate_decision,
    render_ao_release_gate_decision_text,
    write_ao_release_gate_decision,
)


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
            "head": {"ref": "codex/gpp-2v-release-gate-dry-run", "sha": "abc123", "repo": {"fork": False}},
        },
        "issue_url": "https://github.com/Halildeu/ao-kernel/issues/539",
        "branch_up_to_date": True,
        "event_name": "pull_request",
        "changed_paths": [
            "ao_kernel/ao_release_gate.py",
            "scripts/ao_release_gate_decision.py",
            "tests/test_ao_release_gate.py",
            ".claude/plans/GPP-2v-AO-RELEASE-GATE-DRY-RUN-SCAFFOLD.md",
        ],
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


def test_release_gate_allows_closed_dry_run_context_without_merge_authority() -> None:
    decision = build_ao_release_gate_decision(
        _allow_payload(),
        _gpp_status(),
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
    assert decision["github_check_run"]["conclusion"] == "success"
    assert all(check["status"] == "pass" for check in decision["checks"])


def test_release_gate_denies_stale_branch() -> None:
    payload = _allow_payload()
    payload["branch_up_to_date"] = False

    decision = build_ao_release_gate_decision(payload, _gpp_status())

    assert decision["decision"] == DENY_STALE_BRANCH_DECISION
    assert decision["allow"] is False
    # Shadow mode (the default) maps deny/error decisions to ``neutral`` so
    # advisory deliveries do not surface as red CI before AO-GATE-8.
    assert decision["conclusion_mode"] == "shadow"
    assert decision["github_check_run"]["conclusion"] == "neutral"
    assert _find_check(decision, "branch_freshness")["finding_code"] == "ao_release_gate_branch_not_up_to_date"


def test_release_gate_denies_untrusted_fork_context() -> None:
    payload = _allow_payload()
    pull_request = payload["pull_request"]
    assert isinstance(pull_request, dict)
    head = pull_request["head"]
    assert isinstance(head, dict)
    repo = head["repo"]
    assert isinstance(repo, dict)
    repo["fork"] = True

    decision = build_ao_release_gate_decision(payload, _gpp_status())

    assert decision["decision"] == DENY_UNTRUSTED_CONTEXT_DECISION
    assert "ao_release_gate_untrusted_fork" in decision["findings"]


def test_release_gate_denies_missing_ci_evidence() -> None:
    payload = _allow_payload()
    payload["required_checks"] = []

    decision = build_ao_release_gate_decision(payload, _gpp_status())

    assert decision["decision"] == DENY_MISSING_EVIDENCE_DECISION
    assert _find_check(decision, "required_checks")["finding_code"] == "ao_release_gate_required_checks_missing"


def test_release_gate_denies_policy_violations() -> None:
    payload = _allow_payload()
    payload["admin_bypass_requested"] = True

    decision = build_ao_release_gate_decision(payload, _gpp_status())

    assert decision["decision"] == DENY_POLICY_VIOLATION_DECISION
    assert "ao_release_gate_admin_bypass_requested" in decision["findings"]


def test_release_gate_denies_gpp_issue_mismatch_as_missing_evidence() -> None:
    decision = build_ao_release_gate_decision(
        _allow_payload(),
        _gpp_status(issue="https://github.com/Halildeu/ao-kernel/issues/537"),
    )

    assert decision["decision"] == DENY_MISSING_EVIDENCE_DECISION
    assert _find_check(decision, "gpp_issue_consistency")["finding_code"] == "ao_release_gate_gpp_issue_mismatch"


def test_release_gate_render_and_write(tmp_path: Path) -> None:
    decision = build_ao_release_gate_decision(
        _allow_payload(),
        _gpp_status(),
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


def test_check_run_conclusion_shadow_neutral_for_deny_missing_evidence() -> None:
    payload = _allow_payload()
    payload["required_checks"] = []

    decision = build_ao_release_gate_decision(payload, _gpp_status())

    assert decision["decision"] == DENY_MISSING_EVIDENCE_DECISION
    assert decision["conclusion_mode"] == "shadow"
    assert decision["github_check_run"]["conclusion"] == "neutral"


def test_check_run_conclusion_enforce_failure_for_deny_missing_evidence() -> None:
    payload = _allow_payload()
    payload["required_checks"] = []

    decision = build_ao_release_gate_decision(payload, _gpp_status(), conclusion_mode="enforce")

    assert decision["decision"] == DENY_MISSING_EVIDENCE_DECISION
    assert decision["conclusion_mode"] == "enforce"
    assert decision["github_check_run"]["conclusion"] == "failure"


def test_check_run_conclusion_shadow_neutral_for_deny_policy_violation() -> None:
    payload = _allow_payload()
    payload["admin_bypass_requested"] = True

    decision = build_ao_release_gate_decision(payload, _gpp_status())

    assert decision["decision"] == DENY_POLICY_VIOLATION_DECISION
    assert decision["conclusion_mode"] == "shadow"
    assert decision["github_check_run"]["conclusion"] == "neutral"


def test_check_run_conclusion_enforce_failure_for_deny_policy_violation() -> None:
    payload = _allow_payload()
    payload["admin_bypass_requested"] = True

    decision = build_ao_release_gate_decision(payload, _gpp_status(), conclusion_mode="enforce")

    assert decision["decision"] == DENY_POLICY_VIOLATION_DECISION
    assert decision["conclusion_mode"] == "enforce"
    assert decision["github_check_run"]["conclusion"] == "failure"


def test_check_run_conclusion_success_for_allow_in_both_modes() -> None:
    payload = _allow_payload()

    shadow_decision = build_ao_release_gate_decision(payload, _gpp_status())
    enforce_decision = build_ao_release_gate_decision(payload, _gpp_status(), conclusion_mode="enforce")

    assert shadow_decision["decision"] == ALLOW_AUTONOMOUS_MERGE_DECISION
    assert enforce_decision["decision"] == ALLOW_AUTONOMOUS_MERGE_DECISION
    # The allow path is ``success`` regardless of mode — only deny/error
    # decisions diverge between ``shadow`` (``neutral``) and ``enforce``
    # (``failure``).
    assert shadow_decision["github_check_run"]["conclusion"] == "success"
    assert enforce_decision["github_check_run"]["conclusion"] == "success"
    assert shadow_decision["conclusion_mode"] == "shadow"
    assert enforce_decision["conclusion_mode"] == "enforce"


def test_release_gate_cli_writes_dry_run_artifact(tmp_path: Path) -> None:
    payload_path = tmp_path / "payload.json"
    status_path = tmp_path / "gpp_status.json"
    decision_path = tmp_path / "decision.json"
    payload_path.write_text(json.dumps(_allow_payload(), sort_keys=True), encoding="utf-8")
    status_path.write_text(json.dumps(_gpp_status(), sort_keys=True), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/ao_release_gate_decision.py",
            "--payload",
            str(payload_path),
            "--gpp-status",
            str(status_path),
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
