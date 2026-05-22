from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from ao_kernel.ao_release_gate import (
    ALLOW_AUTONOMOUS_MERGE_DECISION,
    DENY_POLICY_VIOLATION_DECISION,
    RELEASE_GATE_CHECK_NAME,
    diff_digest,
)
from ao_kernel.ao_release_gate_service import (
    build_ao_release_gate_service_result,
    render_ao_release_gate_service_text,
    write_ao_release_gate_service_result,
)
from ao_kernel.live_adapter_gate_policy_service import github_webhook_signature

# 40-hex placeholder used by _allow_payload() and the matching
# _review_evidence() factory so the context-binding check passes.
_ALLOW_HEAD_SHA = "abc1230000000000000000000000000000000000"
_ALLOW_REVIEWED_SLICE = "GPP-2"
_ALLOW_CHANGED_PATHS = [
    "ao_kernel/ao_release_gate_service.py",
    "ao_kernel/ao_release_gate_runtime.py",
    "tests/test_ao_release_gate_service.py",
    "tests/test_ao_release_gate_runtime.py",
    ".claude/plans/GPP-2w-AO-RELEASE-GATE-CHECK-RUN-SERVICE.md",
]


def _review_evidence() -> dict[str, object]:
    """Build a valid local-gpp-gate-evidence.v1 attestation bound to _allow_payload()."""
    return {
        "schema_version": "local-gpp-gate-evidence.v1",
        "decision": "operator_may_merge",
        "repo": "Halildeu/ao-kernel",
        "work_package": _ALLOW_REVIEWED_SLICE,
        "generated_at": "2026-04-28T00:00:00Z",
        "checks": {
            "startup_preflight_passed": True,
            "gpp_status_checked": True,
            "scope_allowed": True,
            "tests_passed": True,
            "secret_scan_passed": True,
            "reviewer_agree": True,
            "cross_provider_verified": True,
            "forbidden_actions_absent": True,
        },
        "findings": [],
        "reviewer_findings_count": 0,
        "gpp_2_status": "blocked",
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
        "context_binding": {
            "head_sha": _ALLOW_HEAD_SHA,
            "base_ref": "origin/main",
            "diff_digest": diff_digest(_ALLOW_CHANGED_PATHS),
            "changed_files_count": len(_ALLOW_CHANGED_PATHS),
        },
    }


def _gpp_status(*, issue: str = "https://github.com/Halildeu/ao-kernel/issues/541") -> dict[str, object]:
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
            "number": 541,
            "base": {"ref": "main"},
            "head": {
                "ref": "codex/gpp-2w-release-gate-service",
                "sha": _ALLOW_HEAD_SHA,
                "repo": {"fork": False},
            },
        },
        "issue_url": "https://github.com/Halildeu/ao-kernel/issues/541",
        "branch_up_to_date": True,
        "event_name": "pull_request",
        "reviewed_slice": _ALLOW_REVIEWED_SLICE,
        "changed_paths": list(_ALLOW_CHANGED_PATHS),
        "allowed_path_prefixes": [
            "ao_kernel/",
            "tests/",
            ".claude/plans/",
        ],
        "required_checks": [
            {"name": "lint", "status": "completed", "conclusion": "success"},
            {"name": "test (3.13)", "status": "completed", "conclusion": "success"},
        ],
        "forbidden_secret_context_detected": False,
        "admin_bypass_requested": False,
        "pat_backed_bot_actor": False,
        "codex_or_claude_release_authority": False,
        "live_adapter_execution_requested": False,
    }


def _body(payload: Mapping[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def _headers(body: bytes, *, secret: str = "secret", event: str = "pull_request") -> dict[str, str]:
    return {
        "X-GitHub-Event": event,
        "X-GitHub-Delivery": "delivery-1",
        "X-Hub-Signature-256": github_webhook_signature(secret, body),
    }


def test_service_blocks_missing_required_signature() -> None:
    body = _body(_allow_payload())

    result = build_ao_release_gate_service_result(
        body,
        {"X-GitHub-Event": "pull_request"},
        gpp_status=_gpp_status(),
        webhook_secret="secret",
    )

    assert result["status"] == "blocked"
    assert result["should_post_check_run"] is False
    assert result["decision"] is None
    assert "ao_release_gate_service_signature_invalid" in result["findings"]


def test_service_blocks_wrong_event_before_policy_evaluation() -> None:
    body = _body(_allow_payload())

    result = build_ao_release_gate_service_result(
        body,
        _headers(body, event="push"),
        gpp_status=_gpp_status(),
        webhook_secret="secret",
    )

    assert result["status"] == "blocked"
    assert result["should_post_check_run"] is False
    assert result["decision"] is None
    assert "ao_release_gate_service_wrong_event" in result["findings"]


def test_service_blocks_malformed_json_before_policy_evaluation() -> None:
    body = b"{not-json"

    result = build_ao_release_gate_service_result(
        body,
        _headers(body),
        gpp_status=_gpp_status(),
        webhook_secret="secret",
    )

    assert result["status"] == "blocked"
    assert result["should_post_check_run"] is False
    assert result["decision"] is None
    assert "ao_release_gate_service_invalid_json" in result["findings"]


def test_service_builds_success_check_run_for_allowed_dry_run() -> None:
    payload = _allow_payload()
    body = _body(payload)

    result = build_ao_release_gate_service_result(
        body,
        _headers(body),
        gpp_status=_gpp_status(),
        review_evidence=_review_evidence(),
        webhook_secret="secret",
        generated_at="2026-04-28T00:00:00Z",
    )

    assert result["status"] == "check_run_ready"
    assert result["should_post_check_run"] is True
    assert result["signature_verified"] is True
    assert result["decision"] is not None
    assert result["decision"]["decision"] == ALLOW_AUTONOMOUS_MERGE_DECISION
    assert result["decision"]["dry_run"] is True
    assert result["decision"]["merge_authority_enabled"] is False
    assert result["check_run_request"]["method"] == "POST"
    assert result["check_run_request"]["url"] == "https://api.github.com/repos/Halildeu/ao-kernel/check-runs"
    assert result["check_run_request"]["authorization_required"] is True
    assert result["check_run_request"]["json"] == {
        "name": RELEASE_GATE_CHECK_NAME,
        "head_sha": _ALLOW_HEAD_SHA,
        "status": "completed",
        "conclusion": "success",
        "output": {
            "title": f"{RELEASE_GATE_CHECK_NAME}: allow_autonomous_merge",
            "summary": "Dry-run release gate would allow autonomous merge; no merge or GitHub write was performed.",
            "text": "All release-gate checks passed.",
        },
    }


def test_service_builds_neutral_check_run_for_denied_policy_in_shadow_mode() -> None:
    payload = _allow_payload()
    payload["admin_bypass_requested"] = True
    body = _body(payload)

    result = build_ao_release_gate_service_result(
        body,
        _headers(body),
        gpp_status=_gpp_status(),
        review_evidence=_review_evidence(),
        webhook_secret="secret",
    )

    assert result["status"] == "check_run_ready"
    assert result["should_post_check_run"] is True
    assert result["conclusion_mode"] == "shadow"
    assert result["decision"] is not None
    assert result["decision"]["decision"] == DENY_POLICY_VIOLATION_DECISION
    assert "ao_release_gate_admin_bypass_requested" in result["decision"]["findings"]
    assert result["check_run_request"]["json"] is not None
    assert result["check_run_request"]["json"]["conclusion"] == "neutral"


def test_service_builds_failure_check_run_for_denied_policy_in_enforce_mode() -> None:
    payload = _allow_payload()
    payload["admin_bypass_requested"] = True
    body = _body(payload)

    result = build_ao_release_gate_service_result(
        body,
        _headers(body),
        gpp_status=_gpp_status(),
        review_evidence=_review_evidence(),
        webhook_secret="secret",
        conclusion_mode="enforce",
    )

    assert result["status"] == "check_run_ready"
    assert result["should_post_check_run"] is True
    assert result["conclusion_mode"] == "enforce"
    assert result["decision"] is not None
    assert result["decision"]["decision"] == DENY_POLICY_VIOLATION_DECISION
    assert result["check_run_request"]["json"] is not None
    assert result["check_run_request"]["json"]["conclusion"] == "failure"


def test_service_result_includes_conclusion_mode() -> None:
    payload = _allow_payload()
    body = _body(payload)

    shadow_result = build_ao_release_gate_service_result(
        body,
        _headers(body),
        gpp_status=_gpp_status(),
        review_evidence=_review_evidence(),
        webhook_secret="secret",
    )
    enforce_result = build_ao_release_gate_service_result(
        body,
        _headers(body),
        gpp_status=_gpp_status(),
        review_evidence=_review_evidence(),
        webhook_secret="secret",
        conclusion_mode="enforce",
    )

    assert shadow_result["conclusion_mode"] == "shadow"
    assert enforce_result["conclusion_mode"] == "enforce"
    # Allow path stays ``success`` in either mode.
    assert shadow_result["check_run_request"]["json"] is not None
    assert enforce_result["check_run_request"]["json"] is not None
    assert shadow_result["check_run_request"]["json"]["conclusion"] == "success"
    assert enforce_result["check_run_request"]["json"]["conclusion"] == "success"


def test_service_render_and_write(tmp_path: Path) -> None:
    body = _body(_allow_payload())
    result = build_ao_release_gate_service_result(
        body,
        _headers(body),
        gpp_status=_gpp_status(),
        review_evidence=_review_evidence(),
        webhook_secret="secret",
        generated_at="2026-04-28T00:00:00Z",
    )
    path = tmp_path / "service.json"

    write_ao_release_gate_service_result(path, result)

    assert json.loads(path.read_text(encoding="utf-8")) == result
    assert path.read_text(encoding="utf-8").endswith("\n")
    rendered = render_ao_release_gate_service_text(result)
    assert "status: check_run_ready" in rendered
    assert "should_post_check_run: true" in rendered
    assert "check_run_url: https://api.github.com/repos/Halildeu/ao-kernel/check-runs" in rendered
    assert "merge_authority_enabled: false" in rendered
