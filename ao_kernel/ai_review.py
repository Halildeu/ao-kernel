"""Provider-backed review collection and consensus helpers.

This module productizes the previously operator-scripted cross-provider review
flow. It collects no-secret reviewer evidence from configured provider
commands, records command/prompt provenance, and emits fail-closed consensus
artifacts. It does not grant release authority; the repository-owned
``ao-release-gate`` required check plus GitHub ruleset remains authoritative.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from jsonschema import Draft202012Validator

from ao_kernel.ao_release_gate import (
    RELEASE_GATE_CHECK_NAME,
    _high_risk_paths,
    build_ao_release_gate_decision,
    diff_digest,
    expected_high_risk_supersession_reviewers,
)
from ao_kernel.config import load_default

PROVIDER_REVIEW_POOL = ("openai", "anthropic", "minimax")
PROVIDER_COMMAND_ENVS = {
    "openai": "AO_MA10_OPENAI_REVIEW_CMD",
    "anthropic": "AO_MA10_ANTHROPIC_REVIEW_CMD",
    "minimax": "AO_MA10_MINIMAX_REVIEW_CMD",
}
RELEASE_AUTHORITY = "ao-release-gate+github-ruleset"
COLLECTION_SCHEMA = "ai-review-collection-evidence.schema.v1.json"
CONSENSUS_SCHEMA = "ai-review-consensus-evidence.schema.v1.json"
DRY_RUN_SCHEMA = "ai-review-high-risk-dry-run-evidence.schema.v1.json"
RAW_REVIEW_SCHEMA = "local-ai-review-evidence.schema.v1.json"
HIGH_RISK_SUPERSESSION_SCHEMA = "ao-ma-10-high-risk-supersession-evidence.schema.v1.json"

SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{16,}"),
)

Verdict = Literal["AGREE", "REVISE", "BLOCK", "PARTIAL", "RED"]


@dataclass(frozen=True)
class ProviderCommand:
    """A configured provider command plus safe provenance metadata."""

    provider: str
    argv: tuple[str, ...]
    source: str


@dataclass(frozen=True)
class ProviderRoundResult:
    """One provider's bounded review output for one consensus round."""

    provider: str
    agent: str
    verdict: Verdict
    checks_considered: list[dict[str, str]]
    findings: list[str]
    prompt_sha256: str
    command: ProviderCommand


def utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def assert_no_secret_like_text(value: str, *, label: str) -> None:
    for pattern in SECRET_PATTERNS:
        if pattern.search(value):
            raise ValueError(f"{label} contains secret-like material")


def _validate(schema_name: str, payload: dict[str, Any]) -> None:
    Draft202012Validator(load_default("schemas", schema_name)).validate(payload)


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


def changed_files(repo_root: Path, base_ref: str, head_ref: str) -> list[str]:
    output = _run_git(repo_root, ["diff", "--name-only", f"{base_ref}...{head_ref}"])
    return sorted(line.strip() for line in output.splitlines() if line.strip())


def head_sha(repo_root: Path, head_ref: str) -> str:
    candidate = _run_git(repo_root, ["rev-parse", head_ref])
    if len(candidate) != 40 or any(char not in "0123456789abcdef" for char in candidate):
        raise ValueError("head ref did not resolve to a canonical 40-hex SHA")
    return candidate


def diff_text(repo_root: Path, base_ref: str, head_ref: str, max_bytes: int) -> str:
    output = _run_git(repo_root, ["diff", "--no-ext-diff", "--unified=80", f"{base_ref}...{head_ref}"])
    encoded = output.encode("utf-8")
    if len(encoded) > max_bytes:
        raise ValueError(f"diff is {len(encoded)} bytes, exceeds max_diff_bytes={max_bytes}")
    assert_no_secret_like_text(output, label="git diff")
    return output


def parse_provider_commands(
    values: list[str] | None,
    *,
    required_providers: tuple[str, ...],
) -> dict[str, ProviderCommand]:
    commands: dict[str, ProviderCommand] = {}
    for value in values or []:
        if "=" not in value:
            raise ValueError("--provider must have form provider=command")
        provider, raw_command = value.split("=", 1)
        provider = provider.strip()
        if provider not in PROVIDER_REVIEW_POOL:
            raise ValueError(f"unsupported provider {provider!r}")
        assert_no_secret_like_text(raw_command, label=f"{provider} provider command")
        argv = tuple(shlex.split(raw_command))
        if not argv:
            raise ValueError(f"empty command for provider {provider}")
        commands[provider] = ProviderCommand(provider=provider, argv=argv, source="cli")

    for provider, env_name in PROVIDER_COMMAND_ENVS.items():
        if provider in commands:
            continue
        raw_command = os.environ.get(env_name, "")
        if raw_command.strip():
            assert_no_secret_like_text(raw_command, label=f"{provider} provider command env")
            argv = tuple(shlex.split(raw_command))
            if not argv:
                raise ValueError(f"empty command for provider {provider}")
            commands[provider] = ProviderCommand(provider=provider, argv=argv, source=f"env:{env_name}")

    missing = sorted(set(required_providers) - set(commands))
    if missing:
        raise ValueError(f"missing required provider command(s): {', '.join(missing)}")
    return commands


def command_provenance(command: ProviderCommand, *, prompt_sha256: str, timeout_seconds: int) -> dict[str, Any]:
    redacted_argv = list(command.argv)
    rendered = shlex.join(redacted_argv)
    assert_no_secret_like_text(rendered, label=f"{command.provider} command argv")
    return {
        "provider_id": command.provider,
        "command_source": command.source,
        "command_executable": redacted_argv[0],
        "command_argv_redacted": redacted_argv,
        "command_argv_sha256": sha256_text(rendered),
        "prompt_sha256": prompt_sha256,
        "timeout_seconds": timeout_seconds,
    }


def required_reviewer_providers(implementer_provider: str) -> tuple[str, str]:
    reviewers = tuple(str(provider) for provider in expected_high_risk_supersession_reviewers(implementer_provider))
    if len(reviewers) != 2:
        raise ValueError(f"expected exactly two reviewer providers, got {len(reviewers)}")
    return reviewers


def build_context_binding(
    *,
    repository: str,
    repo_root: Path,
    base_ref: str,
    head_ref: str,
    changed: list[str],
) -> dict[str, Any]:
    return {
        "repository_full_name": repository,
        "base_ref": base_ref,
        "head_ref": head_ref,
        "head_sha": head_sha(repo_root, head_ref),
        "diff_digest": diff_digest(changed),
        "changed_files_count": len(changed),
    }


def build_review_request(
    *,
    repository: str,
    work_package: str,
    base_ref: str,
    head_ref: str,
    changed: list[str],
    high_risk_changed_paths: list[str],
    rendered_diff: str,
    round_index: int,
    previous_findings: list[dict[str, Any]],
) -> str:
    request = {
        "task": "review_high_risk_pr_change",
        "instructions": [
            "Return JSON only.",
            "Use AGREE only if the change matches the work package and no drift, bug, secret, or forbidden action remains.",
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
            "changed_files": changed,
            "high_risk_changed_paths": high_risk_changed_paths,
            "round_index": round_index,
            "previous_findings": previous_findings,
        },
        "diff": rendered_diff,
    }
    payload = json.dumps(request, indent=2, sort_keys=True)
    assert_no_secret_like_text(payload, label="review request")
    return payload


def _load_provider_output(stdout: str, provider: str) -> dict[str, Any]:
    assert_no_secret_like_text(stdout, label=f"{provider} reviewer stdout")
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{provider} reviewer output is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{provider} reviewer output must be a JSON object")
    return cast(dict[str, Any], payload)


def _checks_from_output(provider_output: dict[str, Any], provider: str) -> list[dict[str, str]]:
    checks = provider_output.get("checks_considered")
    if not isinstance(checks, list):
        raise ValueError(f"{provider} reviewer checks_considered must be a list")
    normalized: list[dict[str, str]] = []
    for check in checks:
        if not isinstance(check, dict):
            raise ValueError(f"{provider} reviewer check entry must be an object")
        name = check.get("name")
        status = check.get("status")
        if not isinstance(name, str) or not isinstance(status, str):
            raise ValueError(f"{provider} reviewer check entry must include string name/status")
        if status not in {"pass", "fail"}:
            raise ValueError(f"{provider} reviewer check status must be pass or fail")
        normalized.append({"name": name, "status": status})
    return normalized


def _findings_from_output(provider_output: dict[str, Any], provider: str) -> list[str]:
    findings = provider_output.get("findings")
    if not isinstance(findings, list) or not all(isinstance(item, str) and item for item in findings):
        raise ValueError(f"{provider} reviewer findings must be a non-empty string list")
    for finding in findings:
        assert_no_secret_like_text(finding, label=f"{provider} reviewer finding")
    return list(findings)


def _verdict_from_output(provider_output: dict[str, Any], provider: str) -> Verdict:
    reviewer = provider_output.get("reviewer")
    raw = reviewer.get("verdict") if isinstance(reviewer, dict) else provider_output.get("verdict")
    if raw not in {"AGREE", "REVISE", "BLOCK", "PARTIAL", "RED"}:
        raise ValueError(f"{provider} reviewer verdict must be AGREE, REVISE, BLOCK, PARTIAL, or RED")
    return cast(Verdict, raw)


def _agent_from_output(provider_output: dict[str, Any], provider: str) -> str:
    reviewer = provider_output.get("reviewer")
    raw = reviewer.get("agent") if isinstance(reviewer, dict) else provider_output.get("agent")
    if not isinstance(raw, str) or not raw:
        return f"{provider}-reviewer"
    assert_no_secret_like_text(raw, label=f"{provider} reviewer agent")
    return raw


def run_provider_command(
    command: ProviderCommand,
    *,
    review_request: str,
    timeout_seconds: int,
) -> ProviderRoundResult:
    prompt_digest = sha256_text(review_request)
    proc = subprocess.run(
        list(command.argv),
        input=review_request,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    if proc.stderr.strip():
        assert_no_secret_like_text(proc.stderr, label=f"{command.provider} reviewer stderr")
    if proc.returncode != 0:
        raise RuntimeError(f"{command.provider} reviewer command failed with exit {proc.returncode}")
    payload = _load_provider_output(proc.stdout, command.provider)
    return ProviderRoundResult(
        provider=command.provider,
        agent=_agent_from_output(payload, command.provider),
        verdict=_verdict_from_output(payload, command.provider),
        checks_considered=_checks_from_output(payload, command.provider),
        findings=_findings_from_output(payload, command.provider),
        prompt_sha256=prompt_digest,
        command=command,
    )


def _required_check_present(checks: list[dict[str, str]], name: str) -> bool:
    matching = [item for item in checks if item["name"] == name]
    return bool(matching) and all(item["status"] == "pass" for item in matching)


def raw_review_from_round(
    *,
    result: ProviderRoundResult,
    repository: str,
    work_package: str,
    implementer: dict[str, str],
    base_ref: str,
    head_ref: str,
    changed: list[str],
) -> dict[str, Any]:
    if result.verdict != "AGREE":
        raise ValueError(f"{result.provider} reviewer verdict is not AGREE")
    if any(item.startswith("FORBIDDEN:") for item in result.findings):
        raise ValueError(f"{result.provider} reviewer returned a forbidden finding")
    if not _required_check_present(result.checks_considered, "tests"):
        raise ValueError(f"{result.provider} reviewer did not record passing tests")
    if not _required_check_present(result.checks_considered, "secret_scan"):
        raise ValueError(f"{result.provider} reviewer did not record passing secret_scan")
    raw = {
        "schema_version": "local-ai-review-evidence.v1",
        "repo": repository,
        "work_package": work_package,
        "implementer": dict(implementer),
        "reviewer": {
            "agent": result.agent,
            "provider": result.provider,
            "verdict": "AGREE",
        },
        "scope_reviewed": {
            "base_ref": base_ref,
            "head_ref": head_ref,
            "changed_files": list(changed),
        },
        "checks_considered": result.checks_considered,
        "findings": result.findings,
        "secrets_recorded": False,
        "live_adapter_execution": False,
        "support_widening": False,
        "production_platform_claim": False,
    }
    serialized = json.dumps(raw, sort_keys=True)
    assert_no_secret_like_text(serialized, label=f"{result.provider} raw review evidence")
    _validate(RAW_REVIEW_SCHEMA, raw)
    return raw


def write_raw_reviews(
    *,
    output_dir: Path,
    round_results: list[ProviderRoundResult],
    repository: str,
    work_package: str,
    implementer: dict[str, str],
    base_ref: str,
    head_ref: str,
    changed: list[str],
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for result in round_results:
        raw = raw_review_from_round(
            result=result,
            repository=repository,
            work_package=work_package,
            implementer=implementer,
            base_ref=base_ref,
            head_ref=head_ref,
            changed=changed,
        )
        path = output_dir / f"{result.provider}.local-ai-review-evidence.v1.json"
        path.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        paths[result.provider] = path
    return paths


def build_collection_artifact(
    *,
    repository: str,
    work_package: str,
    implementer: dict[str, str],
    required_providers: tuple[str, ...],
    context_binding: dict[str, Any],
    high_risk_changed_paths: list[str],
    raw_review_paths: dict[str, Path],
    round_results: list[ProviderRoundResult],
    timeout_seconds: int,
) -> dict[str, Any]:
    raw_paths = {provider: str(path) for provider, path in sorted(raw_review_paths.items())}
    provenance = [
        command_provenance(result.command, prompt_sha256=result.prompt_sha256, timeout_seconds=timeout_seconds)
        for result in round_results
    ]
    artifact = {
        "schema_version": "ai-review-collection-evidence.v1",
        "artifact_kind": "ai_review_collection_evidence",
        "generated_at": utc_timestamp(),
        "repo": repository,
        "work_package": work_package,
        "release_authority": RELEASE_AUTHORITY,
        "ai_output_release_authority": False,
        "implementer": implementer,
        "required_reviewer_providers": list(required_providers),
        "reviewer_providers": sorted(raw_paths),
        "context_binding": {
            **context_binding,
            "high_risk_changed_paths": high_risk_changed_paths,
        },
        "raw_review_paths": raw_paths,
        "provider_provenance": provenance,
        "collection_status": "collected",
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "secrets_recorded": False,
        "mutations_performed": False,
    }
    _validate(COLLECTION_SCHEMA, artifact)
    return artifact


def run_collect(
    *,
    repository: str,
    work_package: str,
    implementer_agent: str,
    implementer_provider: str,
    base_ref: str,
    head_ref: str,
    repo_root: Path,
    output_dir: Path,
    provider_values: list[str] | None,
    max_diff_bytes: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    required_providers = required_reviewer_providers(implementer_provider)
    provider_commands = parse_provider_commands(provider_values, required_providers=required_providers)
    changed = changed_files(repo_root, base_ref, head_ref)
    if not changed:
        raise ValueError("changed-files set is empty; review evidence cannot be produced")
    high_risk_changed_paths = _high_risk_paths(changed)
    if not high_risk_changed_paths:
        raise ValueError("no high-risk changed paths found; ai-review collect is not needed")
    rendered_diff = diff_text(repo_root, base_ref, head_ref, max_diff_bytes)
    request = build_review_request(
        repository=repository,
        work_package=work_package,
        base_ref=base_ref,
        head_ref=head_ref,
        changed=changed,
        high_risk_changed_paths=high_risk_changed_paths,
        rendered_diff=rendered_diff,
        round_index=1,
        previous_findings=[],
    )
    results = [
        run_provider_command(provider_commands[provider], review_request=request, timeout_seconds=timeout_seconds)
        for provider in required_providers
    ]
    implementer = {"agent": implementer_agent, "provider": implementer_provider}
    raw_paths = write_raw_reviews(
        output_dir=output_dir,
        round_results=results,
        repository=repository,
        work_package=work_package,
        implementer=implementer,
        base_ref=base_ref,
        head_ref=head_ref,
        changed=changed,
    )
    context = build_context_binding(
        repository=repository,
        repo_root=repo_root,
        base_ref=base_ref,
        head_ref=head_ref,
        changed=changed,
    )
    artifact = build_collection_artifact(
        repository=repository,
        work_package=work_package,
        implementer=implementer,
        required_providers=required_providers,
        context_binding=context,
        high_risk_changed_paths=high_risk_changed_paths,
        raw_review_paths=raw_paths,
        round_results=results,
        timeout_seconds=timeout_seconds,
    )
    collection_path = output_dir / "ai_review_collection.v1.json"
    collection_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact


def build_consensus_artifact(
    *,
    repository: str,
    work_package: str,
    implementer: dict[str, str],
    context_binding: dict[str, Any],
    high_risk_changed_paths: list[str],
    required_providers: tuple[str, ...],
    rounds: list[dict[str, Any]],
    consensus_status: str,
    raw_review_paths: dict[str, Path],
    collection_path: Path | None,
    max_rounds: int,
) -> dict[str, Any]:
    artifact = {
        "schema_version": "ai-review-consensus-evidence.v1",
        "artifact_kind": "ai_review_consensus_evidence",
        "generated_at": utc_timestamp(),
        "repo": repository,
        "work_package": work_package,
        "release_authority": RELEASE_AUTHORITY,
        "ai_output_release_authority": False,
        "implementer": implementer,
        "required_reviewer_providers": list(required_providers),
        "context_binding": {
            **context_binding,
            "high_risk_changed_paths": high_risk_changed_paths,
        },
        "rounds": rounds,
        "consensus_status": consensus_status,
        "max_rounds": max_rounds,
        "raw_review_paths": {provider: str(path) for provider, path in sorted(raw_review_paths.items())},
        "collection_evidence_path": str(collection_path) if collection_path else None,
        "escalation_action": "operator_human_review_fallback",
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "secrets_recorded": False,
        "mutations_performed": False,
    }
    _validate(CONSENSUS_SCHEMA, artifact)
    return artifact


def run_consensus(
    *,
    repository: str,
    work_package: str,
    implementer_agent: str,
    implementer_provider: str,
    base_ref: str,
    head_ref: str,
    repo_root: Path,
    output_dir: Path,
    provider_values: list[str] | None,
    max_diff_bytes: int,
    timeout_seconds: int,
    max_rounds: int,
) -> dict[str, Any]:
    if max_rounds <= 0 or max_rounds > 3:
        raise ValueError("--max-rounds must be between 1 and 3")
    required_providers = required_reviewer_providers(implementer_provider)
    provider_commands = parse_provider_commands(provider_values, required_providers=required_providers)
    changed = changed_files(repo_root, base_ref, head_ref)
    if not changed:
        raise ValueError("changed-files set is empty; consensus evidence cannot be produced")
    high_risk_changed_paths = _high_risk_paths(changed)
    if not high_risk_changed_paths:
        raise ValueError("no high-risk changed paths found; ai-review consensus is not needed")
    rendered_diff = diff_text(repo_root, base_ref, head_ref, max_diff_bytes)
    context = build_context_binding(
        repository=repository,
        repo_root=repo_root,
        base_ref=base_ref,
        head_ref=head_ref,
        changed=changed,
    )
    previous_findings: list[dict[str, Any]] = []
    rounds: list[dict[str, Any]] = []
    agreeing_results: list[ProviderRoundResult] = []
    consensus_status = "not_agreed"
    output_dir.mkdir(parents=True, exist_ok=True)

    for round_index in range(1, max_rounds + 1):
        request = build_review_request(
            repository=repository,
            work_package=work_package,
            base_ref=base_ref,
            head_ref=head_ref,
            changed=changed,
            high_risk_changed_paths=high_risk_changed_paths,
            rendered_diff=rendered_diff,
            round_index=round_index,
            previous_findings=previous_findings,
        )
        results = [
            run_provider_command(provider_commands[provider], review_request=request, timeout_seconds=timeout_seconds)
            for provider in required_providers
        ]
        round_record = {
            "round_index": round_index,
            "provider_results": [
                {
                    "provider_id": result.provider,
                    "agent_id": result.agent,
                    "verdict": result.verdict,
                    "findings_count": len(result.findings),
                    "findings": result.findings,
                    "checks_considered": result.checks_considered,
                    "provider_provenance": command_provenance(
                        result.command,
                        prompt_sha256=result.prompt_sha256,
                        timeout_seconds=timeout_seconds,
                    ),
                }
                for result in results
            ],
        }
        rounds.append(round_record)
        if all(result.verdict == "AGREE" for result in results):
            agreeing_results = results
            consensus_status = "AGREE"
            break
        previous_findings = [
            {"provider_id": result.provider, "verdict": result.verdict, "findings": result.findings}
            for result in results
            if result.verdict != "AGREE"
        ]

    implementer = {"agent": implementer_agent, "provider": implementer_provider}
    raw_paths: dict[str, Path] = {}
    collection_path: Path | None = None
    if consensus_status == "AGREE":
        raw_paths = write_raw_reviews(
            output_dir=output_dir,
            round_results=agreeing_results,
            repository=repository,
            work_package=work_package,
            implementer=implementer,
            base_ref=base_ref,
            head_ref=head_ref,
            changed=changed,
        )
        collection = build_collection_artifact(
            repository=repository,
            work_package=work_package,
            implementer=implementer,
            required_providers=required_providers,
            context_binding=context,
            high_risk_changed_paths=high_risk_changed_paths,
            raw_review_paths=raw_paths,
            round_results=agreeing_results,
            timeout_seconds=timeout_seconds,
        )
        collection_path = output_dir / "ai_review_collection.v1.json"
        collection_path.write_text(json.dumps(collection, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    consensus = build_consensus_artifact(
        repository=repository,
        work_package=work_package,
        implementer=implementer,
        context_binding=context,
        high_risk_changed_paths=high_risk_changed_paths,
        required_providers=required_providers,
        rounds=rounds,
        consensus_status=consensus_status,
        raw_review_paths=raw_paths,
        collection_path=collection_path,
        max_rounds=max_rounds,
    )
    consensus_path = output_dir / "ai_review_consensus.v1.json"
    consensus_path.write_text(json.dumps(consensus, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return consensus


def provider_verdict_from_raw_review(
    *,
    raw_review: dict[str, Any],
    provider: str,
    context: dict[str, Any],
    round_index: int,
    binding_mode: str,
) -> dict[str, Any]:
    reviewer = raw_review.get("reviewer")
    findings = raw_review.get("findings")
    if not isinstance(reviewer, dict):
        raise ValueError("raw review reviewer block missing")
    if not isinstance(findings, list):
        raise ValueError("raw review findings missing")
    return {
        "schema_version": "ao-ma-10-provider-consensus.v1",
        "artifact_kind": "ao_ma_10_provider_consensus",
        "provider_id": provider,
        "agent_id": str(reviewer.get("agent") or f"{provider}-reviewer"),
        "role": "reviewer",
        "risk_classification": "high",
        "verdict": "AGREE",
        "round_index": round_index,
        "context_binding": dict(context),
        "binding_mode": binding_mode,
        "findings_count": len(findings),
        "secrets_recorded": False,
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
        "release_authority": RELEASE_AUTHORITY,
        "ai_output_release_authority": False,
    }


def build_high_risk_supersession_from_raw_reviews(
    *,
    repository: str,
    work_package: str,
    implementer_provider: str,
    context_binding: dict[str, Any],
    high_risk_changed_paths: list[str],
    raw_review_paths: dict[str, Path],
    max_age_seconds: int,
    round_index: int,
) -> dict[str, Any]:
    required = required_reviewer_providers(implementer_provider)
    provider_verdicts: list[dict[str, Any]] = []
    for provider in required:
        path = raw_review_paths.get(provider)
        if path is None:
            raise ValueError(f"missing raw review path for provider {provider}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"raw review for provider {provider} must be an object")
        _validate(RAW_REVIEW_SCHEMA, raw)
        reviewer = raw.get("reviewer")
        if not isinstance(reviewer, dict) or reviewer.get("provider") != provider:
            raise ValueError(f"raw review provider mismatch for {provider}")
        if reviewer.get("verdict") != "AGREE":
            raise ValueError(f"raw review verdict for {provider} is not AGREE")
        for flag in ("secrets_recorded", "support_widening", "production_platform_claim", "live_adapter_execution"):
            if raw.get(flag) is not False:
                raise ValueError(f"raw review {provider} has forbidden flag {flag}")
        provider_verdicts.append(
            provider_verdict_from_raw_review(
                raw_review=raw,
                provider=provider,
                context={**context_binding, "high_risk_changed_paths": high_risk_changed_paths},
                round_index=round_index,
                binding_mode="added",
            )
        )
    evidence = {
        "schema_version": "ao-ma-10-high-risk-supersession-evidence.v1",
        "artifact_kind": "ao_ma_10_high_risk_supersession_evidence",
        "generated_at": utc_timestamp(),
        "repo": repository,
        "work_package": work_package,
        "planning_only": True,
        "release_authority": RELEASE_AUTHORITY,
        "ai_output_release_authority": False,
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "context_binding": {**context_binding, "high_risk_changed_paths": high_risk_changed_paths},
        "implementer_provider": implementer_provider,
        "reviewer_providers": sorted(required),
        "required_reviewer_providers": list(required),
        "provider_verdicts": provider_verdicts,
        "consensus_status": "AGREE",
        "max_revise_rounds": 3,
        "escalation_action": "operator_human_review_fallback",
        "freshness": {"status": "fresh", "max_age_seconds": max_age_seconds},
        "secrets_recorded": False,
        "mutations_performed": False,
    }
    _validate(HIGH_RISK_SUPERSESSION_SCHEMA, evidence)
    return evidence


def build_dry_run_payload(
    *,
    repository: str,
    work_package: str,
    context_binding: dict[str, Any],
    changed: list[str],
) -> dict[str, Any]:
    repo_name = repository.split("/", 1)[1] if "/" in repository else repository
    return {
        "repository": {"full_name": repository},
        "pull_request": {
            "number": 0,
            "author": {"login": "ao-kernel-dry-run"},
            "base": {"ref": "main"},
            "head": {
                "ref": str(context_binding["head_ref"]).replace("refs/heads/", ""),
                "sha": context_binding["head_sha"],
                "repo": {"fork": False, "name": repo_name},
            },
        },
        "issue_url": "https://github.com/Halildeu/ao-kernel/issues/0",
        "branch_up_to_date": True,
        "event_name": "pull_request",
        "reviewed_slice": work_package,
        "changed_paths": list(changed),
        "pr_author": "ao-kernel-dry-run",
        "human_reviews": [],
        "path_sensitive_human_review_enabled": True,
        "allowed_path_prefixes": [
            ".github/",
            ".claude/",
            "AGENTS.md",
            "CLAUDE.md",
            "ao_kernel/",
            "scripts/",
            "tests/",
            "deploy/",
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


def build_local_gate_review_evidence(
    *,
    repository: str,
    work_package: str,
    context_binding: dict[str, Any],
) -> dict[str, Any]:
    """Build context-bound local-gpp review evidence for dry-run evaluation.

    This does not simulate a provider verdict. The provider verdicts are the
    raw review evidence files; this object only supplies the legacy
    review-evidence acceptance input that ``ao-release-gate`` validates
    alongside high-risk supersession evidence.
    """

    evidence = {
        "schema_version": "local-gpp-gate-evidence.v1",
        "decision": "operator_may_merge",
        "repo": repository,
        "work_package": work_package,
        "generated_at": utc_timestamp(),
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
        "gpp_2_status": "closed",
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
        "context_binding": {
            "head_sha": context_binding["head_sha"],
            "base_ref": context_binding["base_ref"],
            "diff_digest": context_binding["diff_digest"],
            "changed_files_count": context_binding["changed_files_count"],
        },
    }
    _validate("local-gpp-gate-evidence.schema.v1.json", evidence)
    return evidence


def run_high_risk_dry_run(
    *,
    repository: str,
    work_package: str,
    implementer_provider: str,
    base_ref: str,
    head_ref: str,
    repo_root: Path,
    output_dir: Path,
    raw_review_paths: list[Path],
    max_age_seconds: int,
) -> dict[str, Any]:
    changed = changed_files(repo_root, base_ref, head_ref)
    high_risk_changed_paths = _high_risk_paths(changed)
    if not high_risk_changed_paths:
        raise ValueError("no high-risk changed paths found; high-risk dry-run is not needed")
    context = build_context_binding(
        repository=repository,
        repo_root=repo_root,
        base_ref=base_ref,
        head_ref=head_ref,
        changed=changed,
    )
    raw_by_provider: dict[str, Path] = {}
    for path in raw_review_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("reviewer"), dict):
            raise ValueError(f"invalid raw review evidence: {path}")
        provider = payload["reviewer"].get("provider")
        if not isinstance(provider, str):
            raise ValueError(f"raw review evidence missing provider: {path}")
        raw_by_provider[provider] = path
    supersession = build_high_risk_supersession_from_raw_reviews(
        repository=repository,
        work_package=work_package,
        implementer_provider=implementer_provider,
        context_binding=context,
        high_risk_changed_paths=high_risk_changed_paths,
        raw_review_paths=raw_by_provider,
        max_age_seconds=max_age_seconds,
        round_index=1,
    )
    payload = build_dry_run_payload(
        repository=repository,
        work_package=work_package,
        context_binding=context,
        changed=changed,
    )
    local_gate_evidence = build_local_gate_review_evidence(
        repository=repository,
        work_package=work_package,
        context_binding=context,
    )
    gpp_status = {
        "current_wp": {"id": "GPP-9", "status": "closed", "issue": payload["issue_url"]},
        "support_widening_allowed": False,
        "production_platform_claim_allowed": False,
        "live_adapter_execution_allowed": False,
    }
    decision = build_ao_release_gate_decision(
        payload,
        gpp_status,
        review_evidence=local_gate_evidence,
        high_risk_supersession_evidence=supersession,
        conclusion_mode="enforce",
    )
    status = "pass" if bool(decision.get("allow")) else "blocked"
    output_dir.mkdir(parents=True, exist_ok=True)
    supersession_path = output_dir / "high_risk_supersession_evidence.v1.json"
    decision_path = output_dir / "ao_release_gate_decision.v1.json"
    local_gate_path = output_dir / "local_gpp_gate_review_evidence.v1.json"
    supersession_path.write_text(json.dumps(supersession, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    local_gate_path.write_text(json.dumps(local_gate_evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    decision_path.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    artifact = {
        "schema_version": "ai-review-high-risk-dry-run-evidence.v1",
        "artifact_kind": "ai_review_high_risk_dry_run_evidence",
        "generated_at": utc_timestamp(),
        "repo": repository,
        "work_package": work_package,
        "release_authority": RELEASE_AUTHORITY,
        "ai_output_release_authority": False,
        "context_binding": {**context, "high_risk_changed_paths": high_risk_changed_paths},
        "raw_review_paths": {provider: str(path) for provider, path in sorted(raw_by_provider.items())},
        "local_gate_evidence_path": str(local_gate_path),
        "high_risk_supersession_evidence_path": str(supersession_path),
        "ao_release_gate_decision_path": str(decision_path),
        "ao_release_gate_decision": str(decision.get("decision")),
        "ao_release_gate_allow": bool(decision.get("allow")),
        "dry_run_status": status,
        "merge_attempted": False,
        "github_mutation_performed": False,
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "secrets_recorded": False,
        "mutations_performed": False,
    }
    _validate(DRY_RUN_SCHEMA, artifact)
    dry_run_path = output_dir / "ai_review_high_risk_dry_run.v1.json"
    dry_run_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact


def _safe_console_payload(payload: dict[str, Any]) -> dict[str, Any]:
    raw_paths = payload.get("raw_review_paths")
    raw_review_providers: list[str] = []
    if isinstance(raw_paths, dict):
        raw_review_providers = [provider for provider in PROVIDER_REVIEW_POOL if provider in raw_paths]

    if "collection_status" in payload:
        return {
            "status": "collected",
            "artifact_kind": "ai_review_collection_evidence",
            "raw_review_providers": raw_review_providers,
            "evidence_written": True,
        }
    if "consensus_status" in payload:
        status = "AGREE" if payload.get("consensus_status") == "AGREE" else "not_agreed"
        return {
            "status": status,
            "artifact_kind": "ai_review_consensus_evidence",
            "raw_review_providers": raw_review_providers,
            "evidence_written": True,
        }
    dry_run_status = "pass" if payload.get("dry_run_status") == "pass" else "blocked"
    return {
        "status": dry_run_status,
        "artifact_kind": "ai_review_high_risk_dry_run_evidence",
        "raw_review_providers": raw_review_providers,
        "evidence_written": True,
        "github_mutation_performed": False,
        "merge_attempted": False,
    }


def _print_payload(payload: dict[str, Any], *, output: str) -> None:
    safe_payload = _safe_console_payload(payload)
    if output == "json":
        print(json.dumps(safe_payload, indent=2, sort_keys=True))
    else:
        print(f"status: {safe_payload['status']}")
        if safe_payload["raw_review_providers"]:
            print("raw_review_providers:")
            for provider in safe_payload["raw_review_providers"]:
                print(f"- {provider}")


def add_ai_review_subparser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = sub.add_parser("ai-review", help="Collect cross-provider AI review evidence")
    review_sub = parser.add_subparsers(dest="ai_review_command")

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--repository", default="Halildeu/ao-kernel")
        p.add_argument("--work-package", required=True)
        p.add_argument("--base-ref", required=True)
        p.add_argument("--head-ref", required=True)
        p.add_argument("--repo-root", type=Path, default=Path("."))
        p.add_argument("--output-dir", type=Path, default=Path("ai-review-artifacts"))
        p.add_argument("--implementer-agent", default="autonomous-implementer")
        p.add_argument(
            "--implementer-provider",
            choices=["anthropic", "openai", "google", "xai", "minimax"],
            default="openai",
        )
        p.add_argument(
            "--provider",
            action="append",
            default=[],
            help="provider=command; missing commands can be supplied via AO_MA10_*_REVIEW_CMD env vars",
        )
        p.add_argument("--max-diff-bytes", type=int, default=200_000)
        p.add_argument("--timeout-seconds", type=int, default=600)
        p.add_argument("--format", choices=["text", "json"], default="json")

    collect_p = review_sub.add_parser("collect", help="Collect raw local-ai-review evidence from providers")
    add_common(collect_p)

    consensus_p = review_sub.add_parser("consensus", help="Run bounded provider ping-pong until unanimous AGREE")
    add_common(consensus_p)
    consensus_p.add_argument("--max-rounds", type=int, default=3)

    dry_run_p = review_sub.add_parser(
        "high-risk-dry-run",
        help="Build high-risk supersession evidence and run local ao-release-gate decision dry-run",
    )
    dry_run_p.add_argument("--repository", default="Halildeu/ao-kernel")
    dry_run_p.add_argument("--work-package", required=True)
    dry_run_p.add_argument("--base-ref", required=True)
    dry_run_p.add_argument("--head-ref", required=True)
    dry_run_p.add_argument("--repo-root", type=Path, default=Path("."))
    dry_run_p.add_argument("--output-dir", type=Path, default=Path("ai-review-artifacts"))
    dry_run_p.add_argument(
        "--review-evidence",
        action="append",
        type=Path,
        required=True,
        help="Raw local-ai-review-evidence.v1 JSON path; repeat for each required provider",
    )
    dry_run_p.add_argument(
        "--implementer-provider",
        choices=["anthropic", "openai", "google", "xai", "minimax"],
        default="openai",
    )
    dry_run_p.add_argument("--max-age-seconds", type=int, default=3600)
    dry_run_p.add_argument("--format", choices=["text", "json"], default="json")


def dispatch_ai_review(args: argparse.Namespace) -> int:
    command = getattr(args, "ai_review_command", None)
    try:
        if command == "collect":
            payload = run_collect(
                repository=args.repository,
                work_package=args.work_package,
                implementer_agent=args.implementer_agent,
                implementer_provider=args.implementer_provider,
                base_ref=args.base_ref,
                head_ref=args.head_ref,
                repo_root=args.repo_root.resolve(),
                output_dir=args.output_dir.resolve(),
                provider_values=args.provider,
                max_diff_bytes=args.max_diff_bytes,
                timeout_seconds=args.timeout_seconds,
            )
            _print_payload(payload, output=args.format)
            return 0
        if command == "consensus":
            payload = run_consensus(
                repository=args.repository,
                work_package=args.work_package,
                implementer_agent=args.implementer_agent,
                implementer_provider=args.implementer_provider,
                base_ref=args.base_ref,
                head_ref=args.head_ref,
                repo_root=args.repo_root.resolve(),
                output_dir=args.output_dir.resolve(),
                provider_values=args.provider,
                max_diff_bytes=args.max_diff_bytes,
                timeout_seconds=args.timeout_seconds,
                max_rounds=args.max_rounds,
            )
            _print_payload(payload, output=args.format)
            return 0 if payload["consensus_status"] == "AGREE" else 1
        if command == "high-risk-dry-run":
            payload = run_high_risk_dry_run(
                repository=args.repository,
                work_package=args.work_package,
                implementer_provider=args.implementer_provider,
                base_ref=args.base_ref,
                head_ref=args.head_ref,
                repo_root=args.repo_root.resolve(),
                output_dir=args.output_dir.resolve(),
                raw_review_paths=args.review_evidence,
                max_age_seconds=args.max_age_seconds,
            )
            _print_payload(payload, output=args.format)
            return 0 if payload["dry_run_status"] == "pass" else 1
    except Exception as exc:  # noqa: BLE001 - CLI must fail closed with concise stderr
        print(f"ai-review {command or '<missing>'} failed: {exc}", file=sys.stderr)
        return 1
    print("Usage: ao-kernel ai-review {collect|consensus|high-risk-dry-run}", file=sys.stderr)
    return 1
