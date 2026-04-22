from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import ao_kernel.real_adapter_smoke as smoke
from ao_kernel.adapters import AdapterRegistry
from ao_kernel.real_adapter_smoke import CommandResult, run_gh_cli_pr_smoke


def _result(
    argv: tuple[str, ...] | list[str],
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


def _bundled_manifest():
    reg = AdapterRegistry()
    reg.load_bundled()
    return reg.get("gh-cli-pr")


def test_binary_missing_blocks_and_skips_remaining_checks() -> None:
    report = run_gh_cli_pr_smoke(
        which=lambda command: None,
        runner=lambda argv, cwd, timeout: _result(argv),
        cwd=Path("/tmp"),
    )

    assert report.overall_status == "blocked"
    assert report.findings == ("gh_binary_missing",)
    assert [check.status for check in report.checks] == [
        "fail",
        "skip",
        "skip",
        "skip",
        "skip",
        "skip",
    ]


def test_auth_status_requires_active_github_login() -> None:
    def runner(
        argv: tuple[str, ...] | list[str],
        cwd: Path | None,
        timeout: float | None,
    ) -> CommandResult:
        cmd = tuple(argv)
        if cmd == ("/fake/gh", "--version"):
            return _result(cmd, stdout="gh version 2.83.2 (2025-12-10)\n")
        if cmd == ("/fake/gh", "auth", "status", "--json", "hosts"):
            return _result(cmd, stdout='{"hosts":{"github.com":[]}}')
        if cmd == (
            "/fake/gh",
            "repo",
            "view",
            "--json",
            "nameWithOwner,defaultBranchRef,isPrivate,url",
        ):
            return _result(
                cmd,
                stdout=(
                    '{"nameWithOwner":"Halildeu/ao-kernel",'
                    '"defaultBranchRef":{"name":"main"},'
                    '"isPrivate":false,'
                    '"url":"https://github.com/Halildeu/ao-kernel"}'
                ),
            )
        if cmd[:4] == ("/fake/gh", "pr", "create", "--repo"):
            return _result(
                cmd,
                stdout="Would have created a Pull Request with:\n",
            )
        raise AssertionError(f"unexpected argv: {cmd!r}")

    report = run_gh_cli_pr_smoke(
        which=lambda command: "/fake/gh",
        runner=runner,
        cwd=Path("/tmp"),
    )

    assert report.overall_status == "blocked"
    assert "gh_not_authenticated" in report.findings
    auth_check = next(check for check in report.checks if check.name == "auth_status")
    assert auth_check.finding_code == "gh_not_authenticated"
    assert auth_check.detail == "github.com icin aktif gh auth kaydi bulunamadi"


def test_repo_view_failure_skips_dry_run() -> None:
    def runner(
        argv: tuple[str, ...] | list[str],
        cwd: Path | None,
        timeout: float | None,
    ) -> CommandResult:
        cmd = tuple(argv)
        if cmd == ("/fake/gh", "--version"):
            return _result(cmd, stdout="gh version 2.83.2 (2025-12-10)\n")
        if cmd == ("/fake/gh", "auth", "status", "--json", "hosts"):
            return _result(
                cmd,
                stdout=(
                    '{"hosts":{"github.com":[{"state":"success","active":true,'
                    '"host":"github.com","login":"Halildeu",'
                    '"tokenSource":"keyring","scopes":"repo",'
                    '"gitProtocol":"https"}]}}'
                ),
            )
        if cmd == (
            "/fake/gh",
            "repo",
            "view",
            "--json",
            "nameWithOwner,defaultBranchRef,isPrivate,url",
        ):
            return _result(cmd, returncode=1, stderr="failed to resolve repo")
        raise AssertionError(f"unexpected argv: {cmd!r}")

    report = run_gh_cli_pr_smoke(
        which=lambda command: "/fake/gh",
        runner=runner,
        cwd=Path("/tmp"),
    )

    assert report.overall_status == "blocked"
    assert "gh_repo_view_failed" in report.findings
    repo_check = next(check for check in report.checks if check.name == "repo_view")
    dry_run_check = next(check for check in report.checks if check.name == "pr_dry_run")
    assert repo_check.finding_code == "gh_repo_view_failed"
    assert dry_run_check.status == "skip"


def test_dry_run_failure_is_reported_explicitly() -> None:
    def runner(
        argv: tuple[str, ...] | list[str],
        cwd: Path | None,
        timeout: float | None,
    ) -> CommandResult:
        cmd = tuple(argv)
        if cmd == ("/fake/gh", "--version"):
            return _result(cmd, stdout="gh version 2.83.2 (2025-12-10)\n")
        if cmd == ("/fake/gh", "auth", "status", "--json", "hosts"):
            return _result(
                cmd,
                stdout=(
                    '{"hosts":{"github.com":[{"state":"success","active":true,'
                    '"host":"github.com","login":"Halildeu",'
                    '"tokenSource":"keyring","scopes":"repo",'
                    '"gitProtocol":"https"}]}}'
                ),
            )
        if cmd == (
            "/fake/gh",
            "repo",
            "view",
            "--json",
            "nameWithOwner,defaultBranchRef,isPrivate,url",
        ):
            return _result(
                cmd,
                stdout=(
                    '{"nameWithOwner":"Halildeu/ao-kernel",'
                    '"defaultBranchRef":{"name":"main"},'
                    '"isPrivate":false,'
                    '"url":"https://github.com/Halildeu/ao-kernel"}'
                ),
            )
        if cmd[:4] == ("/fake/gh", "pr", "create", "--repo"):
            return _result(cmd, returncode=1, stderr="dry-run failed")
        raise AssertionError(f"unexpected argv: {cmd!r}")

    report = run_gh_cli_pr_smoke(
        which=lambda command: "/fake/gh",
        runner=runner,
        cwd=Path("/tmp"),
    )

    assert report.overall_status == "blocked"
    assert "gh_pr_dry_run_failed" in report.findings
    dry_run_check = next(check for check in report.checks if check.name == "pr_dry_run")
    assert dry_run_check.finding_code == "gh_pr_dry_run_failed"


def test_manifest_contract_mismatch_is_reported() -> None:
    manifest = replace(
        _bundled_manifest(),
        invocation={
            **_bundled_manifest().invocation,
            "args": ["pr", "create", "--title", "{task_prompt}"],
        },
    )

    def runner(
        argv: tuple[str, ...] | list[str],
        cwd: Path | None,
        timeout: float | None,
    ) -> CommandResult:
        cmd = tuple(argv)
        if cmd == ("/fake/gh", "--version"):
            return _result(cmd, stdout="gh version 2.83.2 (2025-12-10)\n")
        if cmd == ("/fake/gh", "auth", "status", "--json", "hosts"):
            return _result(
                cmd,
                stdout=(
                    '{"hosts":{"github.com":[{"state":"success","active":true,'
                    '"host":"github.com","login":"Halildeu",'
                    '"tokenSource":"keyring","scopes":"repo",'
                    '"gitProtocol":"https"}]}}'
                ),
            )
        if cmd == (
            "/fake/gh",
            "repo",
            "view",
            "--json",
            "nameWithOwner,defaultBranchRef,isPrivate,url",
        ):
            return _result(
                cmd,
                stdout=(
                    '{"nameWithOwner":"Halildeu/ao-kernel",'
                    '"defaultBranchRef":{"name":"main"},'
                    '"isPrivate":false,'
                    '"url":"https://github.com/Halildeu/ao-kernel"}'
                ),
            )
        if cmd[:4] == ("/fake/gh", "pr", "create", "--repo"):
            return _result(
                cmd,
                stdout="Would have created a Pull Request with:\n",
            )
        raise AssertionError(f"unexpected argv: {cmd!r}")

    original = smoke._load_gh_pr_manifest
    smoke._load_gh_pr_manifest = lambda: manifest
    try:
        report = run_gh_cli_pr_smoke(
            which=lambda command: "/fake/gh",
            runner=runner,
            cwd=Path("/tmp"),
        )
    finally:
        smoke._load_gh_pr_manifest = original

    assert report.overall_status == "blocked"
    assert "gh_pr_manifest_contract_mismatch" in report.findings
    manifest_check = next(
        check for check in report.checks if check.name == "manifest_contract"
    )
    assert manifest_check.finding_code == "gh_pr_manifest_contract_mismatch"


def test_clean_pass_reports_repo_and_dry_run_success() -> None:
    def runner(
        argv: tuple[str, ...] | list[str],
        cwd: Path | None,
        timeout: float | None,
    ) -> CommandResult:
        cmd = tuple(argv)
        if cmd == ("/fake/gh", "--version"):
            return _result(cmd, stdout="gh version 2.83.2 (2025-12-10)\n")
        if cmd == ("/fake/gh", "auth", "status", "--json", "hosts"):
            return _result(
                cmd,
                stdout=(
                    '{"hosts":{"github.com":[{"state":"success","active":true,'
                    '"host":"github.com","login":"Halildeu",'
                    '"tokenSource":"keyring","scopes":"repo",'
                    '"gitProtocol":"https"}]}}'
                ),
            )
        if cmd == (
            "/fake/gh",
            "repo",
            "view",
            "--json",
            "nameWithOwner,defaultBranchRef,isPrivate,url",
        ):
            return _result(
                cmd,
                stdout=(
                    '{"nameWithOwner":"Halildeu/ao-kernel",'
                    '"defaultBranchRef":{"name":"main"},'
                    '"isPrivate":false,'
                    '"url":"https://github.com/Halildeu/ao-kernel"}'
                ),
            )
        if cmd[:4] == ("/fake/gh", "pr", "create", "--repo"):
            return _result(
                cmd,
                stdout=(
                    "Would have created a Pull Request with:\n"
                    "Title: ao-kernel gh-cli-pr smoke probe\n"
                ),
            )
        raise AssertionError(f"unexpected argv: {cmd!r}")

    report = run_gh_cli_pr_smoke(
        which=lambda command: "/fake/gh",
        runner=runner,
        cwd=Path("/tmp"),
    )

    assert report.overall_status == "pass"
    assert report.findings == ()
    assert report.repo_name == "Halildeu/ao-kernel"
    assert report.default_branch == "main"
    dry_run_check = next(check for check in report.checks if check.name == "pr_dry_run")
    assert dry_run_check.status == "pass"
