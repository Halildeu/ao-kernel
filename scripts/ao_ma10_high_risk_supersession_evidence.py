#!/usr/bin/env python3
"""Build AO-MA-10 high-risk supersession evidence at CI runtime.

The committed PR-head inputs are raw ``local-ai-review-evidence.v1`` files.
They intentionally carry no ``head_sha`` so they do not create a commit
self-reference. This script runs from trusted base code, resolves the live PR
diff, validates independent provider review records, and emits the
head-bound ``ao-ma-10-high-risk-supersession-evidence.v1`` artifact consumed by
``ao-release-gate``.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ao_kernel.ao_release_gate import _high_risk_paths, diff_digest
from ao_kernel.config import load_default

RAW_REVIEW_SCHEMA = "local-ai-review-evidence.schema.v1.json"
HIGH_RISK_SUPERSESSION_SCHEMA = "ao-ma-10-high-risk-supersession-evidence.schema.v1.json"
RELEASE_AUTHORITY = "ao-release-gate+github-ruleset"
REQUIRED_PROVIDER_IDS = ("openai", "anthropic")


def _run_git(repo_root: Path, args: list[str]) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed")
    return proc.stdout.strip()


def _changed_files(repo_root: Path, base_ref: str, head_ref: str) -> list[str]:
    output = _run_git(repo_root, ["diff", "--name-only", f"{base_ref}...{head_ref}"])
    return sorted(line.strip() for line in output.splitlines() if line.strip())


def _head_sha(repo_root: Path, head_ref: str) -> str:
    candidate = _run_git(repo_root, ["rev-parse", head_ref])
    if len(candidate) != 40 or any(char not in "0123456789abcdef" for char in candidate):
        raise ValueError("diff head ref did not resolve to a canonical SHA")
    return candidate


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _validate(schema_name: str, payload: dict[str, Any]) -> None:
    Draft202012Validator(load_default("schemas", schema_name)).validate(payload)


def _checks_pass(raw_review: dict[str, Any], check_name: str) -> bool:
    checks = raw_review.get("checks_considered")
    if not isinstance(checks, list):
        return False
    matching = [
        check
        for check in checks
        if isinstance(check, dict) and check.get("name") == check_name
    ]
    return bool(matching) and all(check.get("status") == "pass" for check in matching)


def _provider_verdict_from_raw_review(
    raw_review: dict[str, Any],
    *,
    repository: str,
    review_work_package: str,
    review_base_ref: str,
    review_head_ref: str,
    changed_files: list[str],
    context_binding: dict[str, Any],
    round_index: int,
) -> dict[str, Any]:
    _validate(RAW_REVIEW_SCHEMA, raw_review)

    if raw_review.get("repo") != repository:
        raise ValueError("raw review repository mismatch")
    if raw_review.get("work_package") != review_work_package:
        raise ValueError("raw review work_package mismatch")
    scope = raw_review.get("scope_reviewed")
    if not isinstance(scope, dict):
        raise ValueError("raw review scope missing")
    if scope.get("base_ref") != review_base_ref or scope.get("head_ref") != review_head_ref:
        raise ValueError("raw review scope refs mismatch")
    declared_files = scope.get("changed_files")
    if not isinstance(declared_files, list) or sorted(declared_files) != changed_files:
        raise ValueError("raw review changed_files mismatch")

    reviewer = raw_review.get("reviewer")
    implementer = raw_review.get("implementer")
    if not isinstance(reviewer, dict) or not isinstance(implementer, dict):
        raise ValueError("raw review identity blocks missing")
    if reviewer.get("verdict") != "AGREE":
        raise ValueError("raw review verdict is not AGREE")
    if reviewer.get("agent") == implementer.get("agent"):
        raise ValueError("raw review agent must be independent from implementer")
    if raw_review.get("secrets_recorded") is not False:
        raise ValueError("raw review records secret material")
    for flag in ("support_widening", "production_platform_claim", "live_adapter_execution"):
        if raw_review.get(flag) is not False:
            raise ValueError(f"raw review opens forbidden guard flag {flag}")
    if not _checks_pass(raw_review, "tests") or not _checks_pass(raw_review, "secret_scan"):
        raise ValueError("raw review must record passing tests and secret_scan checks")
    findings = raw_review.get("findings")
    if not isinstance(findings, list):
        raise ValueError("raw review findings must be a list")
    if any(isinstance(item, str) and item.startswith("FORBIDDEN:") for item in findings):
        raise ValueError("raw review contains a forbidden finding")

    provider_id = reviewer.get("provider")
    if provider_id not in REQUIRED_PROVIDER_IDS:
        raise ValueError("raw review provider is not required for high-risk supersession")

    return {
        "schema_version": "ao-ma-10-provider-consensus.v1",
        "artifact_kind": "ao_ma_10_provider_consensus",
        "provider_id": provider_id,
        "agent_id": reviewer.get("agent"),
        "role": "reviewer",
        "risk_classification": "high",
        "verdict": "AGREE",
        "round_index": round_index,
        "context_binding": dict(context_binding),
        "findings_count": len(findings),
        "secrets_recorded": False,
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
        "release_authority": RELEASE_AUTHORITY,
        "ai_output_release_authority": False,
    }


def build_high_risk_supersession_evidence(
    *,
    repository: str,
    review_work_package: str,
    review_base_ref: str,
    review_head_ref: str,
    diff_base_ref: str,
    diff_head_ref: str,
    repo_root: Path,
    raw_review_paths: list[Path],
    max_age_seconds: int,
    round_index: int,
    generated_at: str,
) -> dict[str, Any]:
    changed_files = _changed_files(repo_root, diff_base_ref, diff_head_ref)
    if not changed_files:
        raise ValueError("changed-files set is empty; high-risk evidence cannot be built")
    high_risk_changed_paths = _high_risk_paths(changed_files)
    if not high_risk_changed_paths:
        raise ValueError("no high-risk changed paths found; supersession evidence is not needed")
    context_binding = {
        "repository_full_name": repository,
        "base_ref": review_base_ref,
        "head_ref": review_head_ref,
        "head_sha": _head_sha(repo_root, diff_head_ref),
        "diff_digest": diff_digest(changed_files),
        "changed_files_count": len(changed_files),
        "high_risk_changed_paths": high_risk_changed_paths,
    }

    raw_reviews = [_load_json(path) for path in raw_review_paths]
    if len(raw_reviews) < 2:
        raise ValueError("at least two raw high-risk review evidence files are required")
    provider_verdicts = [
        _provider_verdict_from_raw_review(
            raw_review,
            repository=repository,
            review_work_package=review_work_package,
            review_base_ref=review_base_ref,
            review_head_ref=review_head_ref,
            changed_files=changed_files,
            context_binding=context_binding,
            round_index=round_index,
        )
        for raw_review in raw_reviews
    ]
    provider_ids = [verdict["provider_id"] for verdict in provider_verdicts]
    if sorted(provider_ids) != sorted(REQUIRED_PROVIDER_IDS):
        raise ValueError("high-risk supersession requires exactly OpenAI and Anthropic reviewer providers")

    evidence = {
        "schema_version": "ao-ma-10-high-risk-supersession-evidence.v1",
        "artifact_kind": "ao_ma_10_high_risk_supersession_evidence",
        "generated_at": generated_at,
        "repo": repository,
        "work_package": "AO-MA-10h",
        "planning_only": True,
        "release_authority": RELEASE_AUTHORITY,
        "ai_output_release_authority": False,
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "context_binding": context_binding,
        "reviewer_providers": sorted(provider_ids),
        "required_reviewer_providers": list(REQUIRED_PROVIDER_IDS),
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default="Halildeu/ao-kernel")
    parser.add_argument("--review-work-package", required=True)
    parser.add_argument("--review-base-ref", required=True)
    parser.add_argument("--review-head-ref", required=True)
    parser.add_argument("--diff-base-ref", required=True)
    parser.add_argument("--diff-head-ref", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--review-evidence", action="append", type=Path, required=True)
    parser.add_argument("--max-age-seconds", type=int, default=3600)
    parser.add_argument("--round-index", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    evidence = build_high_risk_supersession_evidence(
        repository=args.repository,
        review_work_package=args.review_work_package,
        review_base_ref=args.review_base_ref,
        review_head_ref=args.review_head_ref,
        diff_base_ref=args.diff_base_ref,
        diff_head_ref=args.diff_head_ref,
        repo_root=args.repo_root,
        raw_review_paths=args.review_evidence,
        max_age_seconds=args.max_age_seconds,
        round_index=args.round_index,
        generated_at=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("high-risk supersession evidence: generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
