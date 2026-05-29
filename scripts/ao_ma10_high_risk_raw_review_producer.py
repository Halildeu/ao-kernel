#!/usr/bin/env python3
"""Produce AO-MA-10 raw high-risk reviewer evidence from provider commands.

This script is deliberately *not* release authority. It only turns two
independent provider review command outputs into raw
``local-ai-review-evidence.v1`` files. The existing repo-owned
``ao-release-gate`` required check remains the authority that validates,
binds, and consumes those files.

Each provider command receives a JSON review request on stdin and returns JSON
on stdout with at least ``agent``, ``verdict``, ``findings``, and
``checks_considered``. The command may also return a complete
``local-ai-review-evidence.v1`` object; the script still rebinds repository,
scope, provider, and guard fields from trusted local inputs before writing.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

# Prefer this checkout's source tree over any editable install that may point
# at another local checkout. This keeps the script usable from temporary
# worktrees when the primary checkout is unavailable.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ao_kernel.ao_release_gate import _high_risk_paths  # noqa: E402
from ao_kernel.config import load_default  # noqa: E402

RAW_REVIEW_SCHEMA = "local-ai-review-evidence.schema.v1.json"
REQUIRED_PROVIDERS = ("openai", "anthropic")
DEFAULT_OUTPUT_DIR = Path("ao-ma-10-high-risk-reviews")
PROVIDER_COMMAND_ENVS = {
    "openai": "AO_MA10_OPENAI_REVIEW_CMD",
    "anthropic": "AO_MA10_ANTHROPIC_REVIEW_CMD",
}
SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{16,}"),
)


@dataclass(frozen=True)
class ProviderCommand:
    provider: str
    command: tuple[str, ...]


def _run_git(repo_root: Path, args: list[str]) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _changed_files(repo_root: Path, base_ref: str, head_ref: str) -> list[str]:
    output = _run_git(repo_root, ["diff", "--name-only", f"{base_ref}...{head_ref}"])
    return sorted(line.strip() for line in output.splitlines() if line.strip())


def _diff_text(repo_root: Path, base_ref: str, head_ref: str, max_bytes: int) -> str:
    output = _run_git(
        repo_root,
        ["diff", "--no-ext-diff", "--unified=80", f"{base_ref}...{head_ref}"],
    )
    encoded = output.encode("utf-8")
    if len(encoded) > max_bytes:
        raise ValueError(f"diff is {len(encoded)} bytes, exceeds --max-diff-bytes={max_bytes}")
    return output


def _assert_no_secret_like_text(value: str, *, label: str) -> None:
    for pattern in SECRET_PATTERNS:
        if pattern.search(value):
            raise ValueError(f"{label} contains secret-like material")


def _load_json_output(stdout: str, provider: str) -> dict[str, Any]:
    _assert_no_secret_like_text(stdout, label=f"{provider} reviewer stdout")
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{provider} reviewer output is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{provider} reviewer output must be a JSON object")
    return payload


def _validate_raw_review(payload: dict[str, Any]) -> None:
    Draft202012Validator(load_default("schemas", RAW_REVIEW_SCHEMA)).validate(payload)


def _required_check_present(checks: Any, name: str) -> bool:
    if not isinstance(checks, list):
        return False
    matches = [
        item
        for item in checks
        if isinstance(item, dict) and item.get("name") == name
    ]
    return bool(matches) and all(item.get("status") == "pass" for item in matches)


def _normalize_reviewer_payload(
    *,
    provider: str,
    provider_output: dict[str, Any],
    repository: str,
    work_package: str,
    implementer: dict[str, str],
    base_ref: str,
    head_ref: str,
    changed_files: list[str],
) -> dict[str, Any]:
    reviewer_block = provider_output.get("reviewer")
    if isinstance(reviewer_block, dict):
        agent = reviewer_block.get("agent", f"{provider}-reviewer")
        verdict = reviewer_block.get("verdict", provider_output.get("verdict"))
    else:
        agent = provider_output.get("agent", f"{provider}-reviewer")
        verdict = provider_output.get("verdict")

    checks = provider_output.get("checks_considered")
    findings = provider_output.get("findings")
    if verdict != "AGREE":
        raise ValueError(f"{provider} reviewer verdict is not AGREE")
    if not isinstance(findings, list) or not all(isinstance(item, str) and item for item in findings):
        raise ValueError(f"{provider} reviewer findings must be a non-empty string list")
    if any(item.startswith("FORBIDDEN:") for item in findings):
        raise ValueError(f"{provider} reviewer returned a forbidden finding")
    if not _required_check_present(checks, "tests"):
        raise ValueError(f"{provider} reviewer did not record passing tests")
    if not _required_check_present(checks, "secret_scan"):
        raise ValueError(f"{provider} reviewer did not record passing secret_scan")

    raw = {
        "schema_version": "local-ai-review-evidence.v1",
        "repo": repository,
        "work_package": work_package,
        "implementer": dict(implementer),
        "reviewer": {
            "agent": str(agent),
            "provider": provider,
            "verdict": "AGREE",
        },
        "scope_reviewed": {
            "base_ref": base_ref,
            "head_ref": head_ref,
            "changed_files": list(changed_files),
        },
        "checks_considered": checks,
        "findings": findings,
        "secrets_recorded": False,
        "live_adapter_execution": False,
        "support_widening": False,
        "production_platform_claim": False,
    }
    serialized = json.dumps(raw, sort_keys=True)
    _assert_no_secret_like_text(serialized, label=f"{provider} raw review evidence")
    _validate_raw_review(raw)
    return raw


def _parse_provider_specs(values: list[str]) -> dict[str, ProviderCommand]:
    commands: dict[str, ProviderCommand] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--provider must have form provider=command")
        provider, raw_command = value.split("=", 1)
        provider = provider.strip()
        if provider not in REQUIRED_PROVIDERS:
            raise ValueError(f"unsupported provider {provider!r}")
        command = tuple(shlex.split(raw_command))
        if not command:
            raise ValueError(f"empty command for provider {provider}")
        commands[provider] = ProviderCommand(provider=provider, command=command)

    for provider, env_name in PROVIDER_COMMAND_ENVS.items():
        if provider in commands:
            continue
        raw_command = os.environ.get(env_name, "")
        if raw_command.strip():
            commands[provider] = ProviderCommand(
                provider=provider,
                command=tuple(shlex.split(raw_command)),
            )

    missing = sorted(set(REQUIRED_PROVIDERS) - set(commands))
    if missing:
        raise ValueError(f"missing required provider command(s): {', '.join(missing)}")
    return commands


def _review_request(
    *,
    repository: str,
    work_package: str,
    base_ref: str,
    head_ref: str,
    changed_files: list[str],
    high_risk_paths: list[str],
    diff_text: str,
) -> str:
    request = {
        "task": "review_high_risk_pr_change",
        "instructions": [
            "Return JSON only.",
            "Use verdict AGREE only if the change matches the work package and no drift, bug, secret, or forbidden action is present.",
            "Use REVISE or BLOCK when any issue remains.",
            "Do not include secret values in findings.",
            "AI output is evidence only; release authority remains ao-release-gate plus GitHub ruleset.",
        ],
        "required_output_shape": {
            "agent": "short reviewer label",
            "verdict": "AGREE|REVISE|BLOCK",
            "checks_considered": [
                {"name": "tests", "status": "pass|fail"},
                {"name": "secret_scan", "status": "pass|fail"},
            ],
            "findings": ["short finding strings"],
        },
        "context": {
            "repository": repository,
            "work_package": work_package,
            "base_ref": base_ref,
            "head_ref": head_ref,
            "changed_files": changed_files,
            "high_risk_changed_paths": high_risk_paths,
        },
        "diff": diff_text,
    }
    payload = json.dumps(request, indent=2, sort_keys=True)
    _assert_no_secret_like_text(payload, label="review request")
    return payload


def _run_provider_command(command: ProviderCommand, review_request: str, timeout_seconds: int) -> dict[str, Any]:
    proc = subprocess.run(
        list(command.command),
        input=review_request,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    if proc.stderr.strip():
        _assert_no_secret_like_text(proc.stderr, label=f"{command.provider} reviewer stderr")
    if proc.returncode != 0:
        raise RuntimeError(f"{command.provider} reviewer command failed with exit {proc.returncode}")
    return _load_json_output(proc.stdout, command.provider)


def produce_raw_reviews(
    *,
    repository: str,
    work_package: str,
    implementer: dict[str, str],
    base_ref: str,
    head_ref: str,
    repo_root: Path,
    output_dir: Path,
    provider_commands: dict[str, ProviderCommand],
    max_diff_bytes: int,
    timeout_seconds: int,
) -> dict[str, Path]:
    changed_files = _changed_files(repo_root, base_ref, head_ref)
    if not changed_files:
        raise ValueError("changed-files set is empty; raw review evidence cannot be produced")
    high_risk_paths = _high_risk_paths(changed_files)
    if not high_risk_paths:
        raise ValueError("no high-risk changed paths found; raw review producer is not needed")
    diff = _diff_text(repo_root, base_ref, head_ref, max_diff_bytes)
    _assert_no_secret_like_text(diff, label="git diff")
    request = _review_request(
        repository=repository,
        work_package=work_package,
        base_ref=base_ref,
        head_ref=head_ref,
        changed_files=changed_files,
        high_risk_paths=high_risk_paths,
        diff_text=diff,
    )

    rendered: dict[str, dict[str, Any]] = {}
    for provider in REQUIRED_PROVIDERS:
        output = _run_provider_command(provider_commands[provider], request, timeout_seconds)
        rendered[provider] = _normalize_reviewer_payload(
            provider=provider,
            provider_output=output,
            repository=repository,
            work_package=work_package,
            implementer=implementer,
            base_ref=base_ref,
            head_ref=head_ref,
            changed_files=changed_files,
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for provider, evidence in rendered.items():
        path = output_dir / f"{provider}.local-ai-review-evidence.v1.json"
        path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        paths[provider] = path
    return paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default="Halildeu/ao-kernel")
    parser.add_argument("--work-package", required=True)
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--provider", action="append", default=[], help="provider=command; required for openai and anthropic unless env commands are set")
    parser.add_argument("--implementer-agent", default="autonomous-implementer")
    parser.add_argument("--implementer-provider", choices=["anthropic", "openai", "google", "xai"], default="openai")
    parser.add_argument("--max-diff-bytes", type=int, default=200_000)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    provider_commands = _parse_provider_specs(args.provider)
    paths = produce_raw_reviews(
        repository=args.repository,
        work_package=args.work_package,
        implementer={"agent": args.implementer_agent, "provider": args.implementer_provider},
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        repo_root=args.repo_root,
        output_dir=args.output_dir,
        provider_commands=provider_commands,
        max_diff_bytes=args.max_diff_bytes,
        timeout_seconds=args.timeout_seconds,
    )
    for provider in REQUIRED_PROVIDERS:
        print(f"{provider}: {paths[provider]}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI safety net
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
