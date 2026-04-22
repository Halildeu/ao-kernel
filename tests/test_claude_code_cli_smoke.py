from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from ao_kernel.real_adapter_smoke import CommandResult, run_claude_code_cli_smoke


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
        if cmd[:4] == ("/fake/claude", "code", "run", "--prompt-file"):
            return _result(
                cmd,
                returncode=1,
                stderr="error: unknown option '--prompt-file'",
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


def test_success_path_returns_pass_report() -> None:
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
        env={"ANTHROPIC_API_KEY": "sk-test"},
    )

    assert report.overall_status == "pass"
    assert report.findings == ()
    assert all(check.status == "pass" for check in report.checks)
