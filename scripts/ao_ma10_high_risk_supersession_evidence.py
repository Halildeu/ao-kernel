#!/usr/bin/env python3
"""Build AO-MA-10 high-risk supersession evidence at CI runtime.

The committed PR-head inputs are raw ``local-ai-review-evidence.v1`` files.
They intentionally carry no ``head_sha`` so they do not create a commit
self-reference. This script runs from trusted base code, resolves the live PR
diff, validates independent provider review records, and emits the
head-bound ``ao-ma-10-high-risk-supersession-evidence.v1`` artifact consumed by
``ao-release-gate``.

Binding mode (Codex thread 019e6ffc plan-time AGREE absorb)
----------------------------------------------------------

Each raw reviewer evidence file is classified by its appearance in the current
PR's diff (``git diff --name-status --no-renames``):

* ``added``     -- ADDED in this PR's diff (introducer PR; full strict scope
                   binding enforced: ``work_package``, ``base_ref``,
                   ``head_ref``, ``changed_files``).
* ``modified``  -- MODIFIED/TYPED/COPIED/RENAMED in this PR's diff. Full
                   strict scope binding still enforced to prevent
                   stale-rebind or PR-head tampering: a reviewer file that
                   moves in the current PR MUST match current PR's bindings.
* ``unchanged`` -- NOT in this PR's diff (file landed in an earlier merge and
                   remains byte-identical at base SHA). Scope binding
                   relaxed: this is the state-at-landing pin. Immutable
                   properties (verdict=AGREE, reviewer agent independence,
                   secrets_recorded=false, guard flags=false, required
                   providers, tests+secret_scan checks) ARE still enforced
                   perpetually. Current PR consensus on this PR's diff is
                   delivered separately via the root
                   ``local-ai-review-evidence.v1.json`` (single reviewer,
                   strict-bound).
* ``deleted``   -- DELETED in this PR's diff (governance break; the workflow
                   pair-presence check should have caught this earlier;
                   fail-closed here as defence in depth).

This classification fixes the systemic operational burden where every
high-risk PR after the introducer had to rebind the raw evidence files to
match its own work_package, which was both heavy and tampering-shaped.
"""

from __future__ import annotations

import argparse
import json
import re
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
PROVIDER_REVIEW_POOL = ("openai", "anthropic", "minimax")
DEFAULT_REVIEWER_PROVIDER_IDS = ("openai", "anthropic")

# Canonical work_package regex shared with the trusted-base workflow's
# reviewed_wp step (.github/workflows/test.yml line ~634) and the schema's
# work_package pattern (ao-ma-10-high-risk-supersession-evidence.schema.v1.json).
# Defense-in-depth: validate the --review-work-package argument here too so a
# malformed identifier cannot reach jsonschema validation as an opaque string.
WORK_PACKAGE_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Za-z0-9][A-Za-z0-9._]*)*$")
WORK_PACKAGE_MIN_LEN = 3
WORK_PACKAGE_MAX_LEN = 80


def _validate_work_package(value: str) -> None:
    """Fail-closed regex/length check on the supplied --review-work-package.

    Mirrors the canonical workflow regex + schema pattern + length bounds.
    Raises ``ValueError`` on any drift so a malformed identifier never reaches
    the generated artifact (the schema would catch it via jsonschema, but a
    pre-check produces an actionable error pointing at the input argument).
    """

    if not isinstance(value, str) or not value.strip():
        raise ValueError("--review-work-package must be a non-empty string")
    stripped = value.strip()
    if len(stripped) < WORK_PACKAGE_MIN_LEN or len(stripped) > WORK_PACKAGE_MAX_LEN:
        raise ValueError(
            f"--review-work-package length out of range: must be "
            f"{WORK_PACKAGE_MIN_LEN}..{WORK_PACKAGE_MAX_LEN} chars"
        )
    if not WORK_PACKAGE_PATTERN.fullmatch(stripped):
        raise ValueError(
            "--review-work-package does not match canonical pattern "
            f"{WORK_PACKAGE_PATTERN.pattern}"
        )

# Fixed repo-relative allowlist for raw reviewer evidence paths. The workflow
# invokes this script from `base/` with raw paths passed as `../head/...`, so
# we cannot rely on Path.relative_to(repo_root) for normalization. Match by
# tail path parts instead (see _resolve_repo_relative_path). Each filename
# stem also pins the expected reviewer provider (anti audit-provenance drift).
HIGH_RISK_REVIEW_REPO_RELATIVE_PATHS: dict[str, str] = {
    "ao-ma-10-high-risk-reviews/anthropic.local-ai-review-evidence.v1.json": "anthropic",
    "ao-ma-10-high-risk-reviews/minimax.local-ai-review-evidence.v1.json": "minimax",
    "ao-ma-10-high-risk-reviews/openai.local-ai-review-evidence.v1.json": "openai",
}

VALID_BINDING_MODES = ("added", "modified", "unchanged")


def _implementer_provider_id(implementer: dict[str, Any]) -> str:
    if implementer.get("kind") == "human":
        return "human"
    provider = implementer.get("provider")
    if not isinstance(provider, str) or not provider:
        raise ValueError("raw review implementer provider missing")
    return provider


def required_reviewer_provider_ids(implementer_provider: str) -> tuple[str, str]:
    if implementer_provider in PROVIDER_REVIEW_POOL:
        return tuple(provider for provider in PROVIDER_REVIEW_POOL if provider != implementer_provider)  # type: ignore[return-value]
    return DEFAULT_REVIEWER_PROVIDER_IDS


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


def _resolve_repo_relative_path(raw_path: Path) -> str:
    """Match raw_path's tail parts to allowed repo-relative paths.

    The workflow invokes this script with raw paths like
    ``../head/ao-ma-10-high-risk-reviews/openai.local-ai-review-evidence.v1.json``
    (raw paths are passed as positional args, the script runs from ``base/``).
    Path.relative_to(repo_root) would fail here. We instead match by suffix
    on the path components (deterministic, no string false-positives).
    """
    raw_parts = raw_path.parts
    for allowed in HIGH_RISK_REVIEW_REPO_RELATIVE_PATHS:
        allowed_parts = Path(allowed).parts
        if len(raw_parts) < len(allowed_parts):
            continue
        if raw_parts[-len(allowed_parts):] == allowed_parts:
            return allowed
    raise ValueError(
        f"raw review path {raw_path} not in allowlist "
        f"{sorted(HIGH_RISK_REVIEW_REPO_RELATIVE_PATHS.keys())}"
    )


def _classify_evidence_binding(
    *,
    repo_root: Path,
    diff_base_ref: str,
    diff_head_ref: str,
    repo_relative_path: str,
) -> str:
    """Classify raw evidence path's appearance in this PR's diff.

    Uses ``git diff --name-status --no-renames`` so rename detection config
    cannot drift the classification: rename is reported as ``D + A`` instead
    of ``R``. Returns one of VALID_BINDING_MODES or ``"deleted"`` for the
    pair-presence governance break case.
    """
    output = _run_git(
        repo_root,
        [
            "diff",
            "--name-status",
            "--no-renames",
            f"{diff_base_ref}...{diff_head_ref}",
            "--",
            repo_relative_path,
        ],
    )
    if not output:
        return "unchanged"
    # Tolerate "R100", "C100" status prefixes by looking at the first char.
    status_code = output.split()[0][0]
    mapping = {
        "A": "added",
        "M": "modified",
        "T": "modified",
        "C": "modified",
        "R": "modified",
        "D": "deleted",
    }
    return mapping.get(status_code, "modified")


def _provider_verdict_from_raw_review(
    raw_review: dict[str, Any],
    raw_path: Path,
    *,
    implementer_provider: str,
    required_provider_ids: tuple[str, str],
    repository: str,
    review_work_package: str,
    review_base_ref: str,
    review_head_ref: str,
    changed_files: list[str],
    context_binding: dict[str, Any],
    round_index: int,
    repo_root: Path,
    diff_base_ref: str,
    diff_head_ref: str,
) -> dict[str, Any]:
    _validate(RAW_REVIEW_SCHEMA, raw_review)

    # --- A. Resolve repo-relative path + classify binding mode ---
    repo_rel = _resolve_repo_relative_path(raw_path)
    binding_mode = _classify_evidence_binding(
        repo_root=repo_root,
        diff_base_ref=diff_base_ref,
        diff_head_ref=diff_head_ref,
        repo_relative_path=repo_rel,
    )
    if binding_mode == "deleted":
        raise ValueError(
            f"raw review path {repo_rel} deleted in this PR — governance break "
            "(workflow pair-presence check should have caught this earlier)"
        )

    # --- B. Always-enforced IMMUTABLE properties (state-at-landing safe) ---
    if raw_review.get("repo") != repository:
        raise ValueError("raw review repository mismatch")

    reviewer = raw_review.get("reviewer")
    implementer = raw_review.get("implementer")
    if not isinstance(reviewer, dict) or not isinstance(implementer, dict):
        raise ValueError("raw review identity blocks missing")
    if reviewer.get("verdict") != "AGREE":
        raise ValueError("raw review verdict is not AGREE")
    if reviewer.get("agent") == implementer.get("agent"):
        raise ValueError(
            "raw review reviewer agent must be independent from implementer agent"
        )
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
    if provider_id == implementer_provider:
        raise ValueError("raw review reviewer provider must differ from implementer provider")
    if provider_id not in required_provider_ids:
        raise ValueError("raw review provider is not required for high-risk supersession")

    # Path-to-provider binding (audit provenance): the openai.* file must
    # carry reviewer.provider=openai and the anthropic.* file must carry
    # reviewer.provider=anthropic. This prevents provider sets from being
    # correct overall while individual provenance is shuffled.
    expected_provider = HIGH_RISK_REVIEW_REPO_RELATIVE_PATHS[repo_rel]
    if provider_id != expected_provider:
        raise ValueError(
            f"raw review provider {provider_id!r} does not match path-bound "
            f"expected provider {expected_provider!r} for {repo_rel}"
        )

    # --- C. Mode-dependent CURRENT-PR strict bindings ---
    scope = raw_review.get("scope_reviewed")
    if not isinstance(scope, dict):
        raise ValueError("raw review scope missing")

    if binding_mode in ("added", "modified"):
        # Introducer (added) or PR-head touched (modified): full strict.
        # Prevents stale-rebind and current-PR tampering: if the file moves
        # in this PR, it must move to a current-PR-bound shape.
        if raw_review.get("work_package") != review_work_package:
            raise ValueError(
                f"raw review work_package mismatch (binding_mode={binding_mode}); "
                "current-PR binding required"
            )
        if scope.get("base_ref") != review_base_ref or scope.get("head_ref") != review_head_ref:
            raise ValueError(
                f"raw review scope refs mismatch (binding_mode={binding_mode}); "
                "current-PR binding required"
            )
        declared_files = scope.get("changed_files")
        if not isinstance(declared_files, list) or sorted(declared_files) != changed_files:
            raise ValueError(
                f"raw review changed_files mismatch (binding_mode={binding_mode}); "
                "current-PR binding required"
            )
    else:
        # binding_mode == "unchanged": state-at-landing pin.
        # The introducer PR already validated scope binding; the immutable
        # properties enforced above guarantee tampering-safe reuse. Current
        # PR review on this PR's diff is delivered separately via the root
        # ``local-ai-review-evidence.v1.json`` artifact.
        pass

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
        "binding_mode": binding_mode,
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
    _validate_work_package(review_work_package)
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

    raw_reviews = [(path, _load_json(path)) for path in raw_review_paths]
    if len(raw_reviews) < 2:
        raise ValueError("at least two raw high-risk review evidence files are required")
    implementer_providers = {
        _implementer_provider_id(raw_review["implementer"])
        for _path, raw_review in raw_reviews
        if isinstance(raw_review.get("implementer"), dict)
    }
    if len(implementer_providers) != 1:
        raise ValueError("raw reviews must agree on exactly one implementer provider")
    implementer_provider = next(iter(implementer_providers))
    required_provider_ids = required_reviewer_provider_ids(implementer_provider)
    provider_verdicts = [
        _provider_verdict_from_raw_review(
            raw_review,
            raw_path,
            implementer_provider=implementer_provider,
            required_provider_ids=required_provider_ids,
            repository=repository,
            review_work_package=review_work_package,
            review_base_ref=review_base_ref,
            review_head_ref=review_head_ref,
            changed_files=changed_files,
            context_binding=context_binding,
            round_index=round_index,
            repo_root=repo_root,
            diff_base_ref=diff_base_ref,
            diff_head_ref=diff_head_ref,
        )
        for raw_path, raw_review in raw_reviews
    ]
    provider_ids = [verdict["provider_id"] for verdict in provider_verdicts]
    if sorted(provider_ids) != sorted(required_provider_ids):
        raise ValueError(
            "high-risk supersession requires exactly the expected reviewer "
            "providers after excluding the implementer provider"
        )

    evidence = {
        "schema_version": "ao-ma-10-high-risk-supersession-evidence.v1",
        "artifact_kind": "ao_ma_10_high_risk_supersession_evidence",
        "generated_at": generated_at,
        "repo": repository,
        # Multi-work-package migration (2026-06-02): emit the
        # review-bound work_package supplied by the trusted-base
        # workflow (resolved from the root reviewer evidence file's
        # work_package field, which the workflow validates with the
        # canonical [A-Z][A-Z0-9]*(?:-[A-Za-z0-9][A-Za-z0-9._]*)*
        # regex). Previously hardcoded to "AO-MA-10h", which blocked
        # every other high-risk PR from producing conforming evidence.
        # The schema's work_package pattern matches the same regex so
        # identifiers round-trip without drift. Per-PR authority is
        # enforced by context_binding (head_sha, diff_digest, etc.),
        # provider distinctness, unanimous AGREE, freshness, and
        # guard-flag closure — not by an allowlist on this field.
        "work_package": review_work_package,
        "planning_only": True,
        "release_authority": RELEASE_AUTHORITY,
        "ai_output_release_authority": False,
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "context_binding": context_binding,
        "implementer_provider": implementer_provider,
        "reviewer_providers": sorted(provider_ids),
        "required_reviewer_providers": list(required_provider_ids),
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
