"""Operator smoke helpers for bundled real-adapter certification lanes.

This module intentionally targets operator-managed surfaces rather than
the deterministic shipped demo baseline. Today it covers two adapters:

1. ``claude-code-cli``:
   version/auth/prompt/manifest smoke for the bundled Claude CLI path.
2. ``gh-cli-pr``:
   binary/auth/repo/dry-run preflight for the typed GitHub PR connector.

The smoke outputs are machine-readable so docs and runbooks can point at
one command instead of a prose-only checklist.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Sequence

from ao_kernel.adapters import AdapterManifest, AdapterRegistry
from ao_kernel.executor.adapter_invoker import _resolve_cli_invocation

_AUTH_ENV_KEYS = ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY")
_PROMPT_ACCESS_PROBE = "reply with the single token ok"
_MANIFEST_SMOKE_PROMPT = (
    'Your entire response MUST be a single JSON object with exactly this shape: '
    '{"status":"ok","review_findings":{"schema_version":"1","findings":[],"summary":"smoke ok"}}'
)
_GH_PR_DRY_RUN_TITLE = "ao-kernel gh-cli-pr smoke probe"
_GH_PR_DRY_RUN_BODY = "Safe dry-run preflight for gh-cli-pr certification."
_GH_DRY_RUN_MARKER = "would have created a pull request"


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


@dataclass(frozen=True)
class SmokeCheck:
    name: str
    status: Literal["pass", "fail", "skip"]
    detail: str
    finding_code: str | None = None
    argv: tuple[str, ...] = ()
    returncode: int | None = None
    observed: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ClaudeCodeSmokeReport:
    overall_status: Literal["pass", "blocked"]
    adapter_id: str
    binary_path: str | None
    api_key_env_present: bool
    checks: tuple[SmokeCheck, ...]
    findings: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GhCliPrSmokeReport:
    overall_status: Literal["pass", "blocked"]
    adapter_id: str
    binary_path: str | None
    repo_name: str | None
    default_branch: str | None
    repo_url: str | None
    checks: tuple[SmokeCheck, ...]
    findings: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


Runner = Callable[[Sequence[str], Path | None, float | None], CommandResult]
WhichFn = Callable[[str], str | None]


def run_claude_code_cli_smoke(
    *,
    timeout_seconds: float = 20.0,
    runner: Runner | None = None,
    which: WhichFn = shutil.which,
    env: Mapping[str, str] | None = None,
) -> ClaudeCodeSmokeReport:
    """Run operator-facing smoke checks for the bundled Claude adapter."""

    runner = runner or _default_runner
    env_map = dict(os.environ if env is None else env)

    manifest = _load_claude_manifest()
    command = str(manifest.invocation["command"])
    binary_path = which(command)
    api_key_env_present = any(bool(env_map.get(key)) for key in _AUTH_ENV_KEYS)

    checks: list[SmokeCheck] = []

    if binary_path is None:
        checks.append(
            SmokeCheck(
                name="binary",
                status="fail",
                detail=(
                    f"bundled manifest command {command!r} PATH uzerinde bulunamadi"
                ),
                finding_code="claude_binary_missing",
                observed={"command": command},
            )
        )
        checks.extend(
            (
                SmokeCheck(
                    name="version",
                    status="skip",
                    detail="binary bulunamadigi icin version smoke atlandi",
                ),
                SmokeCheck(
                    name="auth_status",
                    status="skip",
                    detail="binary bulunamadigi icin auth status smoke atlandi",
                ),
                SmokeCheck(
                    name="prompt_access",
                    status="skip",
                    detail="binary bulunamadigi icin prompt access smoke atlandi",
                ),
                SmokeCheck(
                    name="manifest_invocation",
                    status="skip",
                    detail="binary bulunamadigi icin manifest smoke atlandi",
                ),
            )
        )
        return _finalize_report(
            adapter_id=manifest.adapter_id,
            binary_path=None,
            api_key_env_present=api_key_env_present,
            checks=checks,
        )

    version_result = _run_check(
        runner,
        (binary_path, "--version"),
        None,
        timeout_seconds,
    )
    checks.append(_classify_version_check(version_result))

    auth_result = _run_check(
        runner,
        (binary_path, "auth", "status"),
        None,
        timeout_seconds,
    )
    checks.append(_classify_auth_status_check(auth_result, api_key_env_present))

    prompt_result = _run_check(
        runner,
        (binary_path, "-p", _PROMPT_ACCESS_PROBE),
        None,
        timeout_seconds,
    )
    checks.append(_classify_prompt_access_check(prompt_result))

    with tempfile.TemporaryDirectory(prefix="ao-kernel-claude-code-smoke-") as tmp:
        temp_root = Path(tmp)
        prompt_file = temp_root / "prompt.txt"
        prompt_file.write_text(_MANIFEST_SMOKE_PROMPT, encoding="utf-8")

        envelope = dict(manifest.input_envelope_shape)
        envelope.update(
            {
                "task_prompt": _MANIFEST_SMOKE_PROMPT,
                "context_pack_ref": str(prompt_file),
                "run_id": "wp82-smoke",
            }
        )
        resolved = _resolve_cli_invocation(
            invocation=manifest.invocation,
            input_envelope=envelope,
        )
        manifest_result = _run_check(
            runner,
            (binary_path, *resolved.args),
            temp_root,
            timeout_seconds,
        )
        checks.append(_classify_manifest_invocation_check(manifest_result))

    return _finalize_report(
        adapter_id=manifest.adapter_id,
        binary_path=binary_path,
        api_key_env_present=api_key_env_present,
        checks=checks,
    )


def run_gh_cli_pr_smoke(
    *,
    timeout_seconds: float = 20.0,
    runner: Runner | None = None,
    which: WhichFn = shutil.which,
    cwd: Path | None = None,
    repo: str | None = None,
    base_ref: str | None = None,
    head_ref: str | None = None,
    probe_title: str = _GH_PR_DRY_RUN_TITLE,
    probe_body: str = _GH_PR_DRY_RUN_BODY,
) -> GhCliPrSmokeReport:
    """Run side-effect-safe smoke checks for the bundled gh PR adapter."""

    runner = runner or _default_runner
    manifest = _load_gh_pr_manifest()
    command = str(manifest.invocation["command"])
    binary_path = which(command)
    working_dir = cwd or Path.cwd()

    checks: list[SmokeCheck] = []

    if binary_path is None:
        checks.append(
            SmokeCheck(
                name="binary",
                status="fail",
                detail=(
                    f"bundled manifest command {command!r} PATH uzerinde bulunamadi"
                ),
                finding_code="gh_binary_missing",
                observed={"command": command},
            )
        )
        checks.extend(
            (
                SmokeCheck(
                    name="version",
                    status="skip",
                    detail="binary bulunamadigi icin version smoke atlandi",
                ),
                SmokeCheck(
                    name="auth_status",
                    status="skip",
                    detail="binary bulunamadigi icin auth status smoke atlandi",
                ),
                SmokeCheck(
                    name="manifest_contract",
                    status="skip",
                    detail="binary bulunamadigi icin manifest contract smoke atlandi",
                ),
                SmokeCheck(
                    name="repo_view",
                    status="skip",
                    detail="binary bulunamadigi icin repo view smoke atlandi",
                ),
                SmokeCheck(
                    name="pr_dry_run",
                    status="skip",
                    detail="binary bulunamadigi icin PR dry-run smoke atlandi",
                ),
            )
        )
        return _finalize_gh_report(
            adapter_id=manifest.adapter_id,
            binary_path=None,
            repo_name=None,
            default_branch=None,
            repo_url=None,
            checks=checks,
        )

    version_result = _run_check(
        runner,
        (binary_path, "--version"),
        None,
        timeout_seconds,
    )
    checks.append(_classify_gh_version_check(version_result))

    auth_result = _run_check(
        runner,
        (binary_path, "auth", "status", "--json", "hosts"),
        None,
        timeout_seconds,
    )
    checks.append(_classify_gh_auth_status_check(auth_result))
    checks.append(_classify_gh_manifest_contract_check(manifest))

    repo_view_argv = [binary_path, "repo", "view"]
    if repo:
        repo_view_argv.extend(("--repo", repo))
    repo_view_argv.extend(
        ("--json", "nameWithOwner,defaultBranchRef,isPrivate,url")
    )
    repo_result = _run_check(
        runner,
        tuple(repo_view_argv),
        working_dir,
        timeout_seconds,
    )
    repo_check, resolved_repo, detected_default_branch, repo_url = (
        _classify_gh_repo_view_check(repo_result)
    )
    checks.append(repo_check)

    resolved_base = base_ref or detected_default_branch
    resolved_head = head_ref or detected_default_branch
    if resolved_repo and resolved_base and resolved_head:
        with tempfile.TemporaryDirectory(prefix="ao-kernel-gh-cli-pr-smoke-") as tmp:
            temp_root = Path(tmp)
            body_file = temp_root / "pr-body.md"
            body_file.write_text(probe_body, encoding="utf-8")

            dry_run_result = _run_check(
                runner,
                (
                    binary_path,
                    "pr",
                    "create",
                    "--repo",
                    resolved_repo,
                    "--head",
                    resolved_head,
                    "--base",
                    resolved_base,
                    "--title",
                    probe_title,
                    "--body-file",
                    str(body_file),
                    "--dry-run",
                ),
                working_dir,
                timeout_seconds,
            )
        checks.append(
            _classify_gh_pr_dry_run_check(
                dry_run_result,
                repo_name=resolved_repo,
                head_ref=resolved_head,
                base_ref=resolved_base,
            )
        )
    else:
        checks.append(
            SmokeCheck(
                name="pr_dry_run",
                status="skip",
                detail="repo/default-branch cozulmedigi icin PR dry-run smoke atlandi",
            )
        )

    return _finalize_gh_report(
        adapter_id=manifest.adapter_id,
        binary_path=binary_path,
        repo_name=resolved_repo,
        default_branch=detected_default_branch,
        repo_url=repo_url,
        checks=checks,
    )


def render_text_report(
    report: ClaudeCodeSmokeReport | GhCliPrSmokeReport,
) -> str:
    """Render a concise operator-facing report."""

    lines = [
        f"overall_status: {report.overall_status}",
        f"adapter_id: {report.adapter_id}",
        f"binary_path: {report.binary_path or '<missing>'}",
    ]
    if isinstance(report, ClaudeCodeSmokeReport):
        lines.append(f"api_key_env_present: {str(report.api_key_env_present).lower()}")
    if isinstance(report, GhCliPrSmokeReport):
        lines.append(f"repo_name: {report.repo_name or '<unresolved>'}")
        lines.append(f"default_branch: {report.default_branch or '<unresolved>'}")
        lines.append(f"repo_url: {report.repo_url or '<unresolved>'}")
    lines.append("checks:")
    for check in report.checks:
        lines.append(f"- {check.name}: {check.status} - {check.detail}")
        if check.finding_code:
            lines.append(f"  finding_code: {check.finding_code}")
        if check.argv:
            lines.append(f"  argv: {' '.join(check.argv)}")
        if check.returncode is not None:
            lines.append(f"  returncode: {check.returncode}")
    if report.findings:
        lines.append(f"findings: {', '.join(report.findings)}")
    else:
        lines.append("findings: <none>")
    return "\n".join(lines)


def _load_claude_manifest() -> AdapterManifest:
    reg = AdapterRegistry()
    reg.load_bundled()
    return reg.get("claude-code-cli")


def _load_gh_pr_manifest() -> AdapterManifest:
    reg = AdapterRegistry()
    reg.load_bundled()
    return reg.get("gh-cli-pr")


def _default_runner(
    argv: Sequence[str],
    cwd: Path | None,
    timeout_seconds: float | None,
) -> CommandResult:
    proc = subprocess.run(
        [str(part) for part in argv],
        cwd=None if cwd is None else str(cwd),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_seconds,
    )
    return CommandResult(
        argv=tuple(str(part) for part in argv),
        returncode=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
    )


def _run_check(
    runner: Runner,
    argv: Sequence[str],
    cwd: Path | None,
    timeout_seconds: float | None,
) -> CommandResult:
    try:
        return runner(argv, cwd, timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            argv=tuple(str(part) for part in argv),
            returncode=124,
            stdout=_decode_timeout_stream(exc.stdout),
            stderr=_decode_timeout_stream(exc.stderr),
            timed_out=True,
        )


def _classify_version_check(result: CommandResult) -> SmokeCheck:
    if result.timed_out:
        return SmokeCheck(
            name="version",
            status="fail",
            detail="claude --version cagrisi timeout'a dustu",
            finding_code="claude_version_timeout",
            argv=result.argv,
            returncode=result.returncode,
            observed=_trim_output(result),
        )
    if result.returncode == 0 and result.stdout.strip():
        return SmokeCheck(
            name="version",
            status="pass",
            detail=f"claude version: {result.stdout.strip()}",
            argv=result.argv,
            returncode=result.returncode,
        )
    return SmokeCheck(
        name="version",
        status="fail",
        detail="claude --version cagrisi basarisiz",
        finding_code="claude_version_unavailable",
        argv=result.argv,
        returncode=result.returncode,
        observed=_trim_output(result),
    )


def _classify_gh_version_check(result: CommandResult) -> SmokeCheck:
    if result.timed_out:
        return SmokeCheck(
            name="version",
            status="fail",
            detail="gh --version cagrisi timeout'a dustu",
            finding_code="gh_version_timeout",
            argv=result.argv,
            returncode=result.returncode,
            observed=_trim_output(result),
        )
    if result.returncode == 0 and result.stdout.strip():
        first_line = result.stdout.strip().splitlines()[0]
        return SmokeCheck(
            name="version",
            status="pass",
            detail=f"gh version: {first_line}",
            argv=result.argv,
            returncode=result.returncode,
        )
    return SmokeCheck(
        name="version",
        status="fail",
        detail="gh --version cagrisi basarisiz",
        finding_code="gh_version_unavailable",
        argv=result.argv,
        returncode=result.returncode,
        observed=_trim_output(result),
    )


def _classify_auth_status_check(
    result: CommandResult,
    api_key_env_present: bool,
) -> SmokeCheck:
    if result.timed_out:
        return SmokeCheck(
            name="auth_status",
            status="fail",
            detail="claude auth status cagrisi timeout'a dustu",
            finding_code="claude_auth_status_timeout",
            argv=result.argv,
            returncode=result.returncode,
            observed=_trim_output(result),
        )
    if result.returncode != 0:
        return SmokeCheck(
            name="auth_status",
            status="fail",
            detail="claude auth status cagrisi basarisiz",
            finding_code="claude_auth_status_failed",
            argv=result.argv,
            returncode=result.returncode,
            observed=_trim_output(result),
        )

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return SmokeCheck(
            name="auth_status",
            status="fail",
            detail="claude auth status JSON donmedi",
            finding_code="claude_auth_status_not_json",
            argv=result.argv,
            returncode=result.returncode,
            observed=_trim_output(result),
        )

    logged_in = bool(payload.get("loggedIn"))
    detail = (
        f"loggedIn={logged_in} authMethod={payload.get('authMethod')!r} "
        f"orgName={payload.get('orgName')!r}"
    )
    if logged_in:
        return SmokeCheck(
            name="auth_status",
            status="pass",
            detail=detail,
            argv=result.argv,
            returncode=result.returncode,
            observed={
                "loggedIn": logged_in,
                "authMethod": payload.get("authMethod"),
                "orgName": payload.get("orgName"),
                "fallback_api_key_env_present": api_key_env_present,
            },
        )
    return SmokeCheck(
        name="auth_status",
        status="fail",
        detail=detail,
        finding_code="claude_not_logged_in",
        argv=result.argv,
        returncode=result.returncode,
        observed={
            "loggedIn": logged_in,
            "authMethod": payload.get("authMethod"),
            "orgName": payload.get("orgName"),
            "fallback_api_key_env_present": api_key_env_present,
        },
    )


def _classify_gh_auth_status_check(result: CommandResult) -> SmokeCheck:
    if result.timed_out:
        return SmokeCheck(
            name="auth_status",
            status="fail",
            detail="gh auth status cagrisi timeout'a dustu",
            finding_code="gh_auth_status_timeout",
            argv=result.argv,
            returncode=result.returncode,
            observed=_trim_output(result),
        )
    if result.returncode != 0:
        return SmokeCheck(
            name="auth_status",
            status="fail",
            detail="gh auth status cagrisi basarisiz",
            finding_code="gh_auth_status_failed",
            argv=result.argv,
            returncode=result.returncode,
            observed=_trim_output(result),
        )

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return SmokeCheck(
            name="auth_status",
            status="fail",
            detail="gh auth status JSON donmedi",
            finding_code="gh_auth_status_not_json",
            argv=result.argv,
            returncode=result.returncode,
            observed=_trim_output(result),
        )

    hosts = payload.get("hosts")
    github_hosts = hosts.get("github.com") if isinstance(hosts, dict) else None
    active_entry = None
    if isinstance(github_hosts, list):
        for entry in github_hosts:
            if (
                isinstance(entry, dict)
                and entry.get("active") is True
                and entry.get("state") == "success"
            ):
                active_entry = entry
                break

    if active_entry is None:
        return SmokeCheck(
            name="auth_status",
            status="fail",
            detail="github.com icin aktif gh auth kaydi bulunamadi",
            finding_code="gh_not_authenticated",
            argv=result.argv,
            returncode=result.returncode,
            observed={
                "github_hosts_present": "true" if github_hosts is not None else "false",
            },
        )

    return SmokeCheck(
        name="auth_status",
        status="pass",
        detail=(
            f"host='github.com' login={active_entry.get('login')!r} "
            f"tokenSource={active_entry.get('tokenSource')!r}"
        ),
        argv=result.argv,
        returncode=result.returncode,
        observed={
            "host": active_entry.get("host"),
            "login": active_entry.get("login"),
            "tokenSource": active_entry.get("tokenSource"),
            "scopes": active_entry.get("scopes"),
            "gitProtocol": active_entry.get("gitProtocol"),
        },
    )


def _classify_gh_manifest_contract_check(manifest: AdapterManifest) -> SmokeCheck:
    expected_args = (
        "pr",
        "create",
        "--title",
        "{task_prompt}",
        "--body-file",
        "{context_pack_ref}",
    )
    actual_args = tuple(str(part) for part in manifest.invocation.get("args", ()))
    if (
        manifest.invocation.get("command") == "gh"
        and actual_args == expected_args
        and manifest.invocation.get("stdin_mode") == "none"
    ):
        return SmokeCheck(
            name="manifest_contract",
            status="pass",
            detail="bundled gh-cli-pr manifest contract smoke gecti",
            observed={"args": list(actual_args)},
        )
    return SmokeCheck(
        name="manifest_contract",
        status="fail",
        detail="bundled gh-cli-pr manifest argv mevcut contract ile uyusmuyor",
        finding_code="gh_pr_manifest_contract_mismatch",
        observed={
            "command": str(manifest.invocation.get("command")),
            "args": list(actual_args),
            "stdin_mode": str(manifest.invocation.get("stdin_mode")),
        },
    )


def _classify_gh_repo_view_check(
    result: CommandResult,
) -> tuple[SmokeCheck, str | None, str | None, str | None]:
    if result.timed_out:
        return (
            SmokeCheck(
                name="repo_view",
                status="fail",
                detail="gh repo view cagrisi timeout'a dustu",
                finding_code="gh_repo_view_timeout",
                argv=result.argv,
                returncode=result.returncode,
                observed=_trim_output(result),
            ),
            None,
            None,
            None,
        )
    if result.returncode != 0:
        return (
            SmokeCheck(
                name="repo_view",
                status="fail",
                detail="gh repo view cagrisi basarisiz",
                finding_code="gh_repo_view_failed",
                argv=result.argv,
                returncode=result.returncode,
                observed=_trim_output(result),
            ),
            None,
            None,
            None,
        )

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return (
            SmokeCheck(
                name="repo_view",
                status="fail",
                detail="gh repo view JSON donmedi",
                finding_code="gh_repo_view_not_json",
                argv=result.argv,
                returncode=result.returncode,
                observed=_trim_output(result),
            ),
            None,
            None,
            None,
        )

    repo_name = payload.get("nameWithOwner")
    repo_url = payload.get("url")
    default_branch_ref = payload.get("defaultBranchRef")
    default_branch = None
    if isinstance(default_branch_ref, dict):
        default_branch = default_branch_ref.get("name")

    if not repo_name or not default_branch or not repo_url:
        return (
            SmokeCheck(
                name="repo_view",
                status="fail",
                detail="gh repo view gerekli alanlari donmedi",
                finding_code="gh_repo_view_incomplete",
                argv=result.argv,
                returncode=result.returncode,
                observed={
                    "nameWithOwner": str(repo_name),
                    "defaultBranch": str(default_branch),
                    "url": str(repo_url),
                },
            ),
            None,
            None,
            None,
        )

    return (
        SmokeCheck(
            name="repo_view",
            status="pass",
            detail=(
                f"repo={repo_name!r} default_branch={default_branch!r} "
                f"isPrivate={payload.get('isPrivate')!r}"
            ),
            argv=result.argv,
            returncode=result.returncode,
            observed={
                "nameWithOwner": repo_name,
                "defaultBranch": default_branch,
                "url": repo_url,
                "isPrivate": payload.get("isPrivate"),
            },
        ),
        str(repo_name),
        str(default_branch),
        str(repo_url),
    )


def _classify_gh_pr_dry_run_check(
    result: CommandResult,
    *,
    repo_name: str,
    head_ref: str,
    base_ref: str,
) -> SmokeCheck:
    if result.timed_out:
        return SmokeCheck(
            name="pr_dry_run",
            status="fail",
            detail="gh pr create --dry-run timeout'a dustu",
            finding_code="gh_pr_dry_run_timeout",
            argv=result.argv,
            returncode=result.returncode,
            observed=_trim_output(result),
        )

    combined = f"{result.stdout}\n{result.stderr}".lower()
    if result.returncode == 0 and _GH_DRY_RUN_MARKER in combined:
        return SmokeCheck(
            name="pr_dry_run",
            status="pass",
            detail=(
                f"gh pr create --dry-run gecti "
                f"(repo={repo_name!r}, head={head_ref!r}, base={base_ref!r})"
            ),
            argv=result.argv,
            returncode=result.returncode,
        )

    return SmokeCheck(
        name="pr_dry_run",
        status="fail",
        detail="gh pr create --dry-run basarisiz",
        finding_code="gh_pr_dry_run_failed",
        argv=result.argv,
        returncode=result.returncode,
        observed=_trim_output(result),
    )


def _classify_prompt_access_check(result: CommandResult) -> SmokeCheck:
    if result.timed_out:
        return SmokeCheck(
            name="prompt_access",
            status="fail",
            detail="canli prompt smoke timeout'a dustu",
            finding_code="prompt_smoke_timeout",
            argv=result.argv,
            returncode=result.returncode,
            observed=_trim_output(result),
        )
    if result.returncode == 0 and result.stdout.strip() == "ok":
        return SmokeCheck(
            name="prompt_access",
            status="pass",
            detail="canli prompt smoke gecti",
            argv=result.argv,
            returncode=result.returncode,
        )

    finding, detail, failure_kind = _classify_auth_failure(
        result,
        context_label="canli prompt smoke",
        default_finding="prompt_smoke_failed",
        default_detail="canli prompt smoke basarisiz",
    )
    observed = _trim_output(result)
    if failure_kind is not None:
        observed["failure_kind"] = failure_kind
    return SmokeCheck(
        name="prompt_access",
        status="fail",
        detail=detail,
        finding_code=finding,
        argv=result.argv,
        returncode=result.returncode,
        observed=observed,
    )


def _classify_manifest_invocation_check(result: CommandResult) -> SmokeCheck:
    if result.timed_out:
        return SmokeCheck(
            name="manifest_invocation",
            status="fail",
            detail="bundled manifest smoke timeout'a dustu",
            finding_code="manifest_smoke_timeout",
            argv=result.argv,
            returncode=result.returncode,
            observed=_trim_output(result),
        )
    if result.returncode == 0:
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return SmokeCheck(
                name="manifest_invocation",
                status="fail",
                detail="bundled manifest smoke stdout JSON degil",
                finding_code="manifest_output_not_json",
                argv=result.argv,
                returncode=result.returncode,
                observed=_trim_output(result),
            )
        if not isinstance(payload, dict) or "status" not in payload:
            return SmokeCheck(
                name="manifest_invocation",
                status="fail",
                detail="bundled manifest smoke status alani tasimiyor",
                finding_code="manifest_output_missing_status",
                argv=result.argv,
                returncode=result.returncode,
                observed={"stdout_keys": sorted(payload.keys()) if isinstance(payload, dict) else None},
            )
        return SmokeCheck(
            name="manifest_invocation",
            status="pass",
            detail="bundled manifest smoke gecti",
            argv=result.argv,
            returncode=result.returncode,
        )

    if _looks_like_manifest_contract_mismatch(result):
        finding = "manifest_cli_contract_mismatch"
        detail = "bundled manifest argv mevcut Claude CLI sozlesmesiyle uyusmuyor"
    else:
        finding, detail, failure_kind = _classify_auth_failure(
            result,
            context_label="bundled manifest smoke",
            default_finding="manifest_smoke_failed",
            default_detail="bundled manifest smoke basarisiz",
        )
        observed = _trim_output(result)
        if failure_kind is not None:
            observed["failure_kind"] = failure_kind
        return SmokeCheck(
            name="manifest_invocation",
            status="fail",
            detail=detail,
            finding_code=finding,
            argv=result.argv,
            returncode=result.returncode,
            observed=observed,
        )

    return SmokeCheck(
        name="manifest_invocation",
        status="fail",
        detail=detail,
        finding_code=finding,
        argv=result.argv,
        returncode=result.returncode,
        observed=_trim_output(result),
    )


def _classify_auth_failure(
    result: CommandResult,
    *,
    context_label: str,
    default_finding: str,
    default_detail: str,
) -> tuple[str, str, str | None]:
    combined = f"{result.stdout}\n{result.stderr}".lower()
    if (
        "organization does not have access to claude" in combined
        or "oauth authentication is currently not allowed for this organization"
        in combined
    ):
        return (
            "prompt_access_denied",
            f"{context_label} org-duzeyi OAuth/prompt access blokajina dustu",
            "org_oauth_not_allowed",
        )
    if "account does not have access to claude" in combined:
        return (
            "prompt_access_denied",
            f"{context_label} hesap-duzeyi prompt access blokajina dustu",
            "account_access_denied",
        )
    if "invalid bearer token" in combined:
        return (
            "prompt_access_denied",
            f"{context_label} bearer token gecersizligi nedeniyle bloklandi",
            "invalid_bearer_token",
        )
    if "not logged in" in combined:
        return (
            "prompt_access_denied",
            f"{context_label} login/auth eksikligi nedeniyle bloklandi",
            "not_logged_in",
        )
    if _looks_like_prompt_access_denied(result):
        return (
            "prompt_access_denied",
            f"{context_label} auth/prompt access asamasinda bloklandi",
            "generic_auth_failure",
        )
    return default_finding, default_detail, None


def _looks_like_manifest_contract_mismatch(result: CommandResult) -> bool:
    combined = f"{result.stdout}\n{result.stderr}".lower()
    needles = (
        "unknown option",
        "unknown command",
        "did you mean",
        "error: unknown option",
        "--prompt-file",
        "--append-system-prompt-file",
    )
    return any(needle in combined for needle in needles)


def _looks_like_prompt_access_denied(result: CommandResult) -> bool:
    combined = f"{result.stdout}\n{result.stderr}".lower()
    needles = (
        "does not have access to claude",
        "oauth authentication is currently not allowed for this organization",
        "invalid bearer token",
        "please login again",
        "contact your administrator",
        "not logged in",
        "failed to authenticate",
        "authentication failed",
    )
    return any(needle in combined for needle in needles)


def _trim_output(result: CommandResult) -> dict[str, str]:
    trimmed: dict[str, str] = {}
    if result.stdout.strip():
        trimmed["stdout"] = result.stdout.strip()[:400]
    if result.stderr.strip():
        trimmed["stderr"] = result.stderr.strip()[:400]
    if result.timed_out:
        trimmed["timed_out"] = "true"
    return trimmed


def _decode_timeout_stream(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _finalize_report(
    *,
    adapter_id: str,
    binary_path: str | None,
    api_key_env_present: bool,
    checks: Sequence[SmokeCheck],
) -> ClaudeCodeSmokeReport:
    findings = tuple(
        dict.fromkeys(
            check.finding_code
            for check in checks
            if check.finding_code is not None
        )
    )
    overall_status: Literal["pass", "blocked"] = (
        "pass" if not findings else "blocked"
    )
    return ClaudeCodeSmokeReport(
        overall_status=overall_status,
        adapter_id=adapter_id,
        binary_path=binary_path,
        api_key_env_present=api_key_env_present,
        checks=tuple(checks),
        findings=findings,
    )


def _finalize_gh_report(
    *,
    adapter_id: str,
    binary_path: str | None,
    repo_name: str | None,
    default_branch: str | None,
    repo_url: str | None,
    checks: Sequence[SmokeCheck],
) -> GhCliPrSmokeReport:
    findings = tuple(
        dict.fromkeys(
            check.finding_code
            for check in checks
            if check.finding_code is not None
        )
    )
    overall_status: Literal["pass", "blocked"] = (
        "pass" if not findings else "blocked"
    )
    return GhCliPrSmokeReport(
        overall_status=overall_status,
        adapter_id=adapter_id,
        binary_path=binary_path,
        repo_name=repo_name,
        default_branch=default_branch,
        repo_url=repo_url,
        checks=tuple(checks),
        findings=findings,
    )
