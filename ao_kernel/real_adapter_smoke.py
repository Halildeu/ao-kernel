"""Operator smoke helpers for the bundled ``claude-code-cli`` adapter.

This module intentionally targets the operator-managed certification lane
rather than the deterministic shipped demo surface. The goal is to make
real-adapter readiness concrete and reproducible:

1. Verify the Claude CLI binary is present.
2. Verify the CLI can report a version and auth state.
3. Verify prompt access with a minimal live call.
4. Verify the bundled adapter manifest still matches the installed CLI
   contract closely enough to start a smoke invocation.

The smoke is machine-readable so docs/runbooks can point at a single
command instead of a prose-only checklist.
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


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


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

    version_result = runner((binary_path, "--version"), None, timeout_seconds)
    checks.append(_classify_version_check(version_result))

    auth_result = runner((binary_path, "auth", "status"), None, timeout_seconds)
    checks.append(_classify_auth_status_check(auth_result, api_key_env_present))

    prompt_result = runner(
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
        manifest_result = runner(
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


def render_text_report(report: ClaudeCodeSmokeReport) -> str:
    """Render a concise operator-facing report."""

    lines = [
        f"overall_status: {report.overall_status}",
        f"adapter_id: {report.adapter_id}",
        f"binary_path: {report.binary_path or '<missing>'}",
        "checks:",
    ]
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


def _classify_version_check(result: CommandResult) -> SmokeCheck:
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


def _classify_auth_status_check(
    result: CommandResult,
    api_key_env_present: bool,
) -> SmokeCheck:
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


def _classify_prompt_access_check(result: CommandResult) -> SmokeCheck:
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
    return trimmed


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
