#!/usr/bin/env python3
"""Build an AO-MA-10a2 context-bound evidence bundle.

The builder is intentionally read-only. It resolves a local git diff, loads
registered provider consensus artifacts, verifies that every provider artifact
is bound to the same repository/head/diff context, and emits a no-secret bundle
for later ao-release-gate integration. It does not call GitHub write APIs,
change workflows, mutate rulesets, alter CODEOWNERS, or merge pull requests.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from jsonschema import Draft202012Validator

from ao_kernel.ao_release_gate import diff_digest
from ao_kernel.config import load_default


SCHEMA_VERSION = "ao-ma-10-evidence-bundle.v1"
ARTIFACT_KIND = "ao_ma_10_evidence_bundle"
PROVIDER_CONSENSUS_SCHEMA = "ao-ma-10-provider-consensus.schema.v1.json"
EVIDENCE_BUNDLE_SCHEMA = "ao-ma-10-evidence-bundle.schema.v1.json"
RELEASE_AUTHORITY = "ao-release-gate+github-ruleset"
REQUIRED_REVIEWER_PROVIDERS = ("openai", "anthropic")

ConsensusStatus = Literal["AGREE", "REVISE", "PARTIAL", "RED"]


def _run_git(repo_root: Path, args: list[str]) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _changed_files(repo_root: Path, base_ref: str, head_ref: str) -> list[str]:
    output = _run_git(repo_root, ["diff", "--name-only", f"{base_ref}..{head_ref}"])
    return sorted(line.strip() for line in output.splitlines() if line.strip())


def _head_sha(repo_root: Path, head_ref: str) -> str:
    return _run_git(repo_root, ["rev-parse", head_ref])


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _validate(schema_name: str, payload: dict[str, Any]) -> None:
    schema = load_default("schemas", schema_name)
    Draft202012Validator(schema).validate(payload)


def _context_binding(
    *,
    repository: str,
    base_ref: str,
    head_ref: str,
    head_sha: str,
    changed_files: list[str],
) -> dict[str, Any]:
    return {
        "repository_full_name": repository,
        "base_ref": base_ref,
        "head_ref": head_ref,
        "head_sha": head_sha,
        "diff_digest": diff_digest(changed_files),
        "changed_files_count": len(changed_files),
    }


def _consensus_status(provider_verdicts: list[dict[str, Any]]) -> ConsensusStatus:
    verdicts = {item.get("verdict") for item in provider_verdicts}
    if verdicts == {"AGREE"}:
        return "AGREE"
    if "RED" in verdicts:
        return "RED"
    if "REVISE" in verdicts:
        return "REVISE"
    return "PARTIAL"


def _assert_provider_context(provider_verdicts: list[dict[str, Any]], context: dict[str, Any]) -> None:
    for verdict in provider_verdicts:
        if verdict.get("context_binding") != context:
            provider = verdict.get("provider_id", "<unknown>")
            raise ValueError(f"provider consensus context mismatch for provider {provider!r}")


def _assert_required_providers(provider_verdicts: list[dict[str, Any]]) -> tuple[str, ...]:
    providers = tuple(item.get("provider_id") for item in provider_verdicts)
    provider_set = set(providers)
    missing = [provider for provider in REQUIRED_REVIEWER_PROVIDERS if provider not in provider_set]
    if missing:
        raise ValueError(f"missing required reviewer providers: {', '.join(missing)}")
    if len(provider_set) != len(providers):
        raise ValueError("provider consensus includes duplicate provider_id values")
    return tuple(provider for provider in providers if isinstance(provider, str))


def build_bundle(
    *,
    repository: str,
    work_package: str,
    base_ref: str,
    head_ref: str,
    repo_root: Path,
    provider_consensus_paths: list[Path],
    max_age_seconds: int,
    generated_at: str,
) -> dict[str, Any]:
    changed = _changed_files(repo_root, base_ref, head_ref)
    if not changed:
        raise ValueError("changed-files set is empty; evidence cannot be context-bound")
    context = _context_binding(
        repository=repository,
        base_ref=base_ref,
        head_ref=head_ref,
        head_sha=_head_sha(repo_root, head_ref),
        changed_files=changed,
    )

    provider_verdicts = [_load_json(path) for path in provider_consensus_paths]
    if len(provider_verdicts) < 2:
        raise ValueError("at least two provider consensus artifacts are required")
    for verdict in provider_verdicts:
        _validate(PROVIDER_CONSENSUS_SCHEMA, verdict)
    _assert_provider_context(provider_verdicts, context)
    providers = _assert_required_providers(provider_verdicts)

    bundle = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "generated_at": generated_at,
        "repo": repository,
        "work_package": work_package,
        "read_only": True,
        "mutations_performed": False,
        "release_authority": RELEASE_AUTHORITY,
        "ai_output_release_authority": False,
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "context_binding": context,
        "reviewer_providers": sorted(providers),
        "required_reviewer_providers": list(REQUIRED_REVIEWER_PROVIDERS),
        "provider_verdicts": provider_verdicts,
        "consensus_status": _consensus_status(provider_verdicts),
        "freshness": {
            "status": "fresh",
            "max_age_seconds": max_age_seconds,
        },
        "secrets_recorded": False,
    }
    _validate(EVIDENCE_BUNDLE_SCHEMA, bundle)
    return bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default="Halildeu/ao-kernel")
    parser.add_argument("--work-package", default="AO-MA-10a2")
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--provider-consensus", action="append", required=True)
    parser.add_argument("--max-age-seconds", type=int, default=3600)
    parser.add_argument("--output")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args(argv)

    bundle = build_bundle(
        repository=args.repository,
        work_package=args.work_package,
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        repo_root=Path(args.repo_root),
        provider_consensus_paths=[Path(path) for path in args.provider_consensus],
        max_age_seconds=args.max_age_seconds,
        generated_at=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.format == "text":
        print(bundle["consensus_status"])
        print(f"providers: {', '.join(bundle['reviewer_providers'])}")
        print(f"diff_digest: {bundle['context_binding']['diff_digest']}")
    else:
        print(json.dumps(bundle, indent=2, sort_keys=True))
    return 0 if bundle["consensus_status"] == "AGREE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
