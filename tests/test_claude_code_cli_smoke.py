from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ao_kernel.real_adapter_smoke import CommandResult, run_claude_code_cli_smoke


_SUCCESSFUL_CHECK_NAMES = [
    "version",
    "auth_status",
    "prompt_access",
    "manifest_invocation",
]
_REPORT_KEYS = {
    "overall_status",
    "adapter_id",
    "binary_path",
    "api_key_env_present",
    "checks",
    "findings",
}
_CHECK_KEYS = {
    "name",
    "status",
    "detail",
    "finding_code",
    "argv",
    "returncode",
    "observed",
}


def _result(
    argv: Sequence[str],
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> CommandResult:
    return CommandResult(
        argv=tuple(argv),
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _successful_runner(
    argv: Sequence[str],
    cwd: Path | None,
    timeout: float | None,
) -> CommandResult:
    cmd = tuple(argv)
    if cmd == ("/fake/claude", "--version"):
        return _result(cmd, stdout="2.1.87 (Claude Code)\n")
    if cmd == ("/fake/claude", "auth", "status"):
        return _result(
            cmd,
            stdout=json.dumps(
                {
                    "loggedIn": True,
                    "authMethod": "claude.ai",
                    "orgName": "Test Org",
                }
            ),
        )
    if cmd == ("/fake/claude", "-p", "reply with the single token ok"):
        return _result(cmd, stdout="ok\n")
    if cmd[:1] == ("/fake/claude",):
        return _result(
            cmd,
            stdout=json.dumps(
                {
                    "status": "ok",
                    "review_findings": {
                        "schema_version": "1",
                        "findings": [],
                        "summary": "smoke ok",
                    },
                }
            ),
        )
    raise AssertionError(f"unexpected argv: {cmd!r}")


def _prompt_access_denied_runner(
    argv: Sequence[str],
    cwd: Path | None,
    timeout: float | None,
) -> CommandResult:
    cmd = tuple(argv)
    if cmd == ("/fake/claude", "--version"):
        return _result(cmd, stdout="2.1.87 (Claude Code)\n")
    if cmd == ("/fake/claude", "auth", "status"):
        return _result(
            cmd,
            stdout=json.dumps(
                {
                    "loggedIn": True,
                    "authMethod": "claude.ai",
                    "orgName": "Test Org",
                }
            ),
        )
    if cmd[:1] == ("/fake/claude",):
        return _result(
            cmd,
            returncode=1,
            stderr=(
                "Your organization does not have access to Claude. "
                "Please login again or contact your administrator."
            ),
        )
    raise AssertionError(f"unexpected argv: {cmd!r}")


def _auth_not_logged_in_runner(
    argv: Sequence[str],
    cwd: Path | None,
    timeout: float | None,
) -> CommandResult:
    cmd = tuple(argv)
    if cmd == ("/fake/claude", "--version"):
        return _result(cmd, stdout="2.1.87 (Claude Code)\n")
    if cmd == ("/fake/claude", "auth", "status"):
        return _result(
            cmd,
            stdout=json.dumps(
                {
                    "loggedIn": False,
                    "authMethod": None,
                    "orgName": None,
                }
            ),
        )
    if cmd == ("/fake/claude", "-p", "reply with the single token ok"):
        return _result(cmd, stdout="ok\n")
    if cmd[:1] == ("/fake/claude",):
        return _result(
            cmd,
            stdout=json.dumps(
                {
                    "status": "ok",
                    "review_findings": {
                        "schema_version": "1",
                        "findings": [],
                        "summary": "smoke ok",
                    },
                }
            ),
        )
    raise AssertionError(f"unexpected argv: {cmd!r}")


def _json_payload(report: Any) -> dict[str, object]:
    # Exercise the same JSON-safe shape emitted by scripts/claude_code_cli_smoke.py.
    return json.loads(json.dumps(report.as_dict()))


def test_binary_missing_blocks_and_skips_remaining_checks() -> None:
    report = run_claude_code_cli_smoke(
        which=lambda command: None,
        runner=lambda argv, cwd, timeout: _result(argv),
        env={},
    )

    assert report.overall_status == "blocked"
    assert report.findings == ("claude_binary_missing",)
    assert [check.status for check in report.checks] == [
        "fail",
        "skip",
        "skip",
        "skip",
        "skip",
    ]


def test_success_json_output_matches_preflight_evidence_contract() -> None:
    report = run_claude_code_cli_smoke(
        which=lambda command: "/fake/claude",
        runner=_successful_runner,
        env={},
    )

    payload = _json_payload(report)

    assert set(payload) == _REPORT_KEYS
    assert payload["overall_status"] == "pass"
    assert payload["adapter_id"] == "claude-code-cli"
    assert payload["binary_path"] == "/fake/claude"
    assert payload["api_key_env_present"] is False
    assert payload["findings"] == []

    checks = payload["checks"]
    assert isinstance(checks, list)
    assert [check["name"] for check in checks] == _SUCCESSFUL_CHECK_NAMES
    assert all(set(check) == _CHECK_KEYS for check in checks)
    assert all(check["status"] == "pass" for check in checks)
    assert all(check["finding_code"] is None for check in checks)
    assert all(check["returncode"] == 0 for check in checks)
    assert all(check["argv"][0] == "/fake/claude" for check in checks)

    auth_check = next(check for check in checks if check["name"] == "auth_status")
    assert auth_check["observed"] == {
        "loggedIn": True,
        "authMethod": "claude.ai",
        "orgName": "Test Org",
        "fallback_api_key_env_present": False,
    }


def test_auth_status_pass_prompt_access_fail_blocks_preflight_contract() -> None:
    report = run_claude_code_cli_smoke(
        which=lambda command: "/fake/claude",
        runner=_prompt_access_denied_runner,
        env={},
    )

    payload = _json_payload(report)

    assert payload["overall_status"] == "blocked"
    assert "prompt_access_denied" in payload["findings"]
    checks = payload["checks"]
    assert isinstance(checks, list)

    auth_check = next(check for check in checks if check["name"] == "auth_status")
    assert auth_check["status"] == "pass"
    assert auth_check["finding_code"] is None

    prompt_check = next(check for check in checks if check["name"] == "prompt_access")
    assert prompt_check["status"] == "fail"
    assert prompt_check["finding_code"] == "prompt_access_denied"
    assert prompt_check["observed"]["failure_kind"] == "org_oauth_not_allowed"


def test_api_key_env_presence_is_observed_not_primary_success_signal() -> None:
    report = run_claude_code_cli_smoke(
        which=lambda command: "/fake/claude",
        runner=_prompt_access_denied_runner,
        env={"ANTHROPIC_API_KEY": "fake"},
    )

    payload = _json_payload(report)

    assert payload["api_key_env_present"] is True
    assert payload["overall_status"] == "blocked"
    assert "prompt_access_denied" in payload["findings"]

    auth_check = next(
        check for check in payload["checks"] if check["name"] == "auth_status"
    )
    assert auth_check["observed"]["fallback_api_key_env_present"] is True


def test_auth_status_not_logged_in_blocks_preflight_contract() -> None:
    report = run_claude_code_cli_smoke(
        which=lambda command: "/fake/claude",
        runner=_auth_not_logged_in_runner,
        env={},
    )

    payload = _json_payload(report)

    assert payload["overall_status"] == "blocked"
    assert "claude_not_logged_in" in payload["findings"]
    auth_check = next(
        check for check in payload["checks"] if check["name"] == "auth_status"
    )
    assert auth_check["status"] == "fail"
    assert auth_check["finding_code"] == "claude_not_logged_in"
    assert auth_check["observed"]["loggedIn"] is False


def test_prompt_access_denied_is_classified_explicitly() -> None:
    def runner(
        argv: Sequence[str],
        cwd: Path | None,
        timeout: float | None,
    ) -> CommandResult:
        cmd = tuple(argv)
        if cmd == ("/fake/claude", "--version"):
            return _result(cmd, stdout="2.1.87 (Claude Code)\n")
        if cmd == ("/fake/claude", "auth", "status"):
            return _result(
                cmd,
                stdout=json.dumps(
                    {
                        "loggedIn": True,
                        "authMethod": "claude.ai",
                        "orgName": "Test Org",
                    }
                ),
            )
        if cmd == ("/fake/claude", "-p", "reply with the single token ok"):
            return _result(
                cmd,
                returncode=1,
                stderr=(
                    "Your organization does not have access to Claude. "
                    "Please login again or contact your administrator."
                ),
            )
        if cmd[:1] == ("/fake/claude",):
            return _result(
                cmd,
                returncode=1,
                stderr=(
                    "Your organization does not have access to Claude. "
                    "Please login again or contact your administrator."
                ),
            )
        raise AssertionError(f"unexpected argv: {cmd!r}")

    report = run_claude_code_cli_smoke(
        which=lambda command: "/fake/claude",
        runner=runner,
        env={},
    )

    assert report.overall_status == "blocked"
    assert "prompt_access_denied" in report.findings
    prompt_check = next(check for check in report.checks if check.name == "prompt_access")
    assert prompt_check.finding_code == "prompt_access_denied"
    assert prompt_check.detail == (
        "canli prompt smoke org-duzeyi OAuth/prompt access blokajina dustu"
    )
    assert prompt_check.observed["failure_kind"] == "org_oauth_not_allowed"


def test_invalid_bearer_token_is_classified_explicitly() -> None:
    def runner(
        argv: Sequence[str],
        cwd: Path | None,
        timeout: float | None,
    ) -> CommandResult:
        cmd = tuple(argv)
        if cmd == ("/fake/claude", "--version"):
            return _result(cmd, stdout="2.1.87 (Claude Code)\n")
        if cmd == ("/fake/claude", "auth", "status"):
            return _result(
                cmd,
                stdout=json.dumps(
                    {
                        "loggedIn": True,
                        "authMethod": "claude.ai",
                        "orgName": "Test Org",
                    }
                ),
            )
        if cmd[:1] == ("/fake/claude",):
            return _result(
                cmd,
                returncode=1,
                stderr=(
                    "Failed to authenticate. API Error: 401 "
                    '{"type":"error","error":{"type":"authentication_error",'
                    '"message":"Invalid bearer token"}}'
                ),
            )
        raise AssertionError(f"unexpected argv: {cmd!r}")

    report = run_claude_code_cli_smoke(
        which=lambda command: "/fake/claude",
        runner=runner,
        env={},
    )

    assert report.overall_status == "blocked"
    assert "prompt_access_denied" in report.findings
    prompt_check = next(check for check in report.checks if check.name == "prompt_access")
    assert prompt_check.finding_code == "prompt_access_denied"
    assert prompt_check.detail == (
        "canli prompt smoke bearer token gecersizligi nedeniyle bloklandi"
    )
    assert prompt_check.observed["failure_kind"] == "invalid_bearer_token"


def test_prompt_timeout_is_reported_without_crashing() -> None:
    def runner(
        argv: Sequence[str],
        cwd: Path | None,
        timeout: float | None,
    ) -> CommandResult:
        cmd = tuple(argv)
        if cmd == ("/fake/claude", "--version"):
            return _result(cmd, stdout="2.1.87 (Claude Code)\n")
        if cmd == ("/fake/claude", "auth", "status"):
            return _result(
                cmd,
                stdout=json.dumps(
                    {
                        "loggedIn": True,
                        "authMethod": "claude.ai",
                        "orgName": "Test Org",
                    }
                ),
            )
        if cmd == ("/fake/claude", "-p", "reply with the single token ok"):
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout or 20.0)
        if cmd[:1] == ("/fake/claude",):
            return _result(
                cmd,
                stdout=json.dumps(
                    {
                        "status": "ok",
                        "review_findings": {
                            "schema_version": "1",
                            "findings": [],
                            "summary": "smoke ok",
                        },
                    }
                ),
            )
        raise AssertionError(f"unexpected argv: {cmd!r}")

    report = run_claude_code_cli_smoke(
        which=lambda command: "/fake/claude",
        runner=runner,
        env={},
    )

    assert report.overall_status == "blocked"
    assert "prompt_smoke_timeout" in report.findings
    prompt_check = next(check for check in report.checks if check.name == "prompt_access")
    assert prompt_check.finding_code == "prompt_smoke_timeout"
    assert prompt_check.detail == "canli prompt smoke timeout'a dustu"
    assert prompt_check.observed["timed_out"] == "true"


def test_manifest_contract_mismatch_is_reported() -> None:
    def runner(
        argv: Sequence[str],
        cwd: Path | None,
        timeout: float | None,
    ) -> CommandResult:
        cmd = tuple(argv)
        if cmd == ("/fake/claude", "--version"):
            return _result(cmd, stdout="2.1.87 (Claude Code)\n")
        if cmd == ("/fake/claude", "auth", "status"):
            return _result(
                cmd,
                stdout=json.dumps(
                    {
                        "loggedIn": True,
                        "authMethod": "claude.ai",
                        "orgName": "Test Org",
                    }
                ),
            )
        if cmd == ("/fake/claude", "-p", "reply with the single token ok"):
            return _result(cmd, stdout="ok\n")
        if cmd[:4] == ("/fake/claude", "-p", "Your entire response MUST be a single JSON object with exactly this shape: {\"status\":\"ok\",\"review_findings\":{\"schema_version\":\"1\",\"findings\":[],\"summary\":\"smoke ok\"}}", "--append-system-prompt-file"):
            return _result(
                cmd,
                returncode=1,
                stderr="error: unknown option '--append-system-prompt-file'",
            )
        raise AssertionError(f"unexpected argv: {cmd!r}")

    report = run_claude_code_cli_smoke(
        which=lambda command: "/fake/claude",
        runner=runner,
        env={},
    )

    assert report.overall_status == "blocked"
    assert "manifest_cli_contract_mismatch" in report.findings
    manifest_check = next(
        check for check in report.checks if check.name == "manifest_invocation"
    )
    assert manifest_check.finding_code == "manifest_cli_contract_mismatch"


def test_manifest_timeout_is_reported_without_success_promotion() -> None:
    def runner(
        argv: Sequence[str],
        cwd: Path | None,
        timeout: float | None,
    ) -> CommandResult:
        cmd = tuple(argv)
        if cmd == ("/fake/claude", "--version"):
            return _result(cmd, stdout="2.1.87 (Claude Code)\n")
        if cmd == ("/fake/claude", "auth", "status"):
            return _result(
                cmd,
                stdout=json.dumps(
                    {
                        "loggedIn": True,
                        "authMethod": "claude.ai",
                        "orgName": "Test Org",
                    }
                ),
            )
        if cmd == ("/fake/claude", "-p", "reply with the single token ok"):
            return _result(cmd, stdout="ok\n")
        if cmd[:1] == ("/fake/claude",):
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout or 20.0)
        raise AssertionError(f"unexpected argv: {cmd!r}")

    report = run_claude_code_cli_smoke(
        which=lambda command: "/fake/claude",
        runner=runner,
        env={},
    )

    assert report.overall_status == "blocked"
    assert "manifest_smoke_timeout" in report.findings
    manifest_check = next(
        check for check in report.checks if check.name == "manifest_invocation"
    )
    assert manifest_check.finding_code == "manifest_smoke_timeout"
    assert manifest_check.observed["timed_out"] == "true"


def test_manifest_non_json_output_is_contract_failure() -> None:
    def runner(
        argv: Sequence[str],
        cwd: Path | None,
        timeout: float | None,
    ) -> CommandResult:
        cmd = tuple(argv)
        if cmd == ("/fake/claude", "--version"):
            return _result(cmd, stdout="2.1.87 (Claude Code)\n")
        if cmd == ("/fake/claude", "auth", "status"):
            return _result(
                cmd,
                stdout=json.dumps(
                    {
                        "loggedIn": True,
                        "authMethod": "claude.ai",
                        "orgName": "Test Org",
                    }
                ),
            )
        if cmd == ("/fake/claude", "-p", "reply with the single token ok"):
            return _result(cmd, stdout="ok\n")
        if cmd[:1] == ("/fake/claude",):
            return _result(cmd, stdout="not json\n")
        raise AssertionError(f"unexpected argv: {cmd!r}")

    report = run_claude_code_cli_smoke(
        which=lambda command: "/fake/claude",
        runner=runner,
        env={},
    )

    assert report.overall_status == "blocked"
    assert "manifest_output_not_json" in report.findings
    manifest_check = next(
        check for check in report.checks if check.name == "manifest_invocation"
    )
    assert manifest_check.finding_code == "manifest_output_not_json"


def test_success_path_returns_pass_report() -> None:
    report = run_claude_code_cli_smoke(
        which=lambda command: "/fake/claude",
        runner=_successful_runner,
        env={},
    )

    assert report.overall_status == "pass"
    assert report.findings == ()
    assert all(check.status == "pass" for check in report.checks)
