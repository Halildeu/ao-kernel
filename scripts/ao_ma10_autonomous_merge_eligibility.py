#!/usr/bin/env python3
"""Build AO-MA-10a1 autonomous merge eligibility evidence.

This script is intentionally read-only. It consumes an AO-MA-10a0 GitHub
readiness snapshot plus a candidate changed-file set, then decides whether a
future low-risk autonomous merge dry-run may proceed. It does not call GitHub
write APIs, mutate branch protection, change CODEOWNERS, or merge PRs.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ao_kernel.ao_release_gate import (  # noqa: E402
    HIGH_RISK_PATH_PATTERNS,
    RELEASE_GATE_REVIEW_CHECK_NAME,
    RELEASE_GATE_TECHNICAL_CHECK_NAME,
)


SCHEMA_VERSION = "ao-ma-10-autonomous-merge-eligibility.v1"
ARTIFACT_KIND = "ao_ma_10_autonomous_merge_eligibility"
RELEASE_AUTHORITY = "ao-release-gate+github-ruleset"
GITHUB_ACTIONS_APP_ID = 15368
TECHNICAL_CHECK = RELEASE_GATE_TECHNICAL_CHECK_NAME
REVIEW_CHECK = RELEASE_GATE_REVIEW_CHECK_NAME
DEFAULT_PLAN_PATH = ".claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.v1.json"
DEFAULT_SNAPSHOT_PATH = ".claude/plans/AO-MA-10A0-GITHUB-READINESS-SNAPSHOT.v1.json"


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _git_changed_files(repo_root: Path, base_ref: str, head_ref: str) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "diff", "--name-only", f"{base_ref}..{head_ref}"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git diff failed: {proc.stderr.strip()}")
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _changed_files_from_args(args: argparse.Namespace) -> list[str]:
    changed: list[str] = []
    changed.extend(args.changed_file or [])
    for file_list_path in args.changed_files_path or []:
        changed.extend(
            line.strip()
            for line in Path(file_list_path).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    if args.git_base:
        changed.extend(_git_changed_files(Path(args.repo_root), args.git_base, args.git_head))
    return sorted(set(changed))


def _invalid_path(path: str) -> bool:
    return (
        not path
        or path.startswith("/")
        or "\\" in path
        or path == "."
        or path.startswith("../")
        or "/../" in path
        or path.endswith("/..")
    )


def _allowed_by_prefix(path: str, allowed_prefixes: list[str]) -> bool:
    for prefix in allowed_prefixes:
        if prefix == "local-ai-review-evidence.v1.json":
            if path == prefix:
                return True
            continue
        if path == prefix:
            return True
        if path.startswith(prefix):
            return True
    return False


def _matching_prohibited_patterns(path: str, patterns: list[str]) -> list[str]:
    return [pattern for pattern in patterns if re.search(pattern, path)]


def _matching_high_risk_patterns(path: str) -> list[str]:
    return [pattern for pattern in HIGH_RISK_PATH_PATTERNS if fnmatch(path, pattern)]


def _ruleset_check_status(snapshot: dict[str, Any], check_name: str) -> tuple[bool, bool]:
    checks_raw = _object(snapshot.get("rulesets")).get("effective_required_checks")
    checks = checks_raw if isinstance(checks_raw, list) else []
    matching = [check for check in checks if isinstance(check, dict) and check.get("context") == check_name]
    present = bool(matching)
    source_pinned = any(check.get("integration_id") == GITHUB_ACTIONS_APP_ID for check in matching)
    return present, source_pinned


def _snapshot_collection_blockers(snapshot: dict[str, Any]) -> list[str]:
    return _string_list(_object(snapshot.get("readiness")).get("blockers"))


def _snapshot_warnings(snapshot: dict[str, Any]) -> list[str]:
    return _string_list(_object(snapshot.get("readiness")).get("warnings"))


def _low_risk_evaluation(
    *,
    changed_files: list[str],
    allowed_prefixes: list[str],
    prohibited_patterns: list[str],
) -> dict[str, Any]:
    invalid_paths = sorted(path for path in changed_files if _invalid_path(path))
    prohibited_matches: list[dict[str, Any]] = []
    high_risk_matches: list[dict[str, Any]] = []
    not_allowed: list[str] = []
    for path in changed_files:
        matches = _matching_prohibited_patterns(path, prohibited_patterns)
        if matches:
            prohibited_matches.append({"path": path, "patterns": matches})
        high_risk = _matching_high_risk_patterns(path)
        if high_risk:
            high_risk_matches.append({"path": path, "patterns": high_risk})
        if not _allowed_by_prefix(path, allowed_prefixes):
            not_allowed.append(path)

    low_risk = bool(changed_files) and not invalid_paths and not prohibited_matches and not high_risk_matches and not not_allowed
    return {
        "files": changed_files,
        "files_count": len(changed_files),
        "low_risk": low_risk,
        "invalid_paths": invalid_paths,
        "not_allowed": sorted(not_allowed),
        "prohibited_matches": prohibited_matches,
        "release_gate_high_risk_matches": high_risk_matches,
    }


def build_eligibility(
    *,
    snapshot: dict[str, Any],
    plan: dict[str, Any],
    changed_files: list[str],
    generated_at: str,
) -> dict[str, Any]:
    criteria = _object(plan.get("low_risk_criteria"))
    allowed_prefixes = _string_list(criteria.get("allowed_path_prefixes"))
    prohibited_patterns = _string_list(criteria.get("prohibited_path_patterns"))

    technical_present, technical_pinned = _ruleset_check_status(snapshot, TECHNICAL_CHECK)
    review_present, review_pinned = _ruleset_check_status(snapshot, REVIEW_CHECK)

    branch_protection = _object(snapshot.get("branch_protection"))
    rulesets = _object(snapshot.get("rulesets"))
    merge_actor = _object(snapshot.get("merge_actor"))
    codeowners = _object(snapshot.get("codeowners"))
    guard_flags = _object(snapshot.get("guard_flags"))

    candidate = _low_risk_evaluation(
        changed_files=changed_files,
        allowed_prefixes=allowed_prefixes,
        prohibited_patterns=prohibited_patterns,
    )

    blockers = set(_snapshot_collection_blockers(snapshot))
    warnings = set(_snapshot_warnings(snapshot))

    if snapshot.get("read_only") is not True:
        blockers.add("snapshot_not_read_only")
    if snapshot.get("mutations_performed") is not False:
        blockers.add("snapshot_mutated")
    if snapshot.get("release_authority") != RELEASE_AUTHORITY:
        blockers.add("release_authority_mismatch")
    if snapshot.get("ai_output_release_authority") is not False:
        blockers.add("ai_output_release_authority_observed")
    readiness = _object(snapshot.get("readiness"))
    if readiness.get("decision") != "ready_for_dry_run":
        blockers.add("readiness_snapshot_not_ready")
    if guard_flags != {
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
    }:
        blockers.add("guard_flags_not_false")

    if not candidate["files"]:
        blockers.add("changed_files_missing")
    if candidate["invalid_paths"]:
        blockers.add("changed_file_path_invalid")
    if candidate["not_allowed"] or candidate["prohibited_matches"] or candidate["release_gate_high_risk_matches"]:
        blockers.add("changed_files_not_low_risk")
    if candidate["release_gate_high_risk_matches"]:
        blockers.add("changed_files_match_release_gate_high_risk")

    if not technical_present:
        blockers.add("ao_release_gate_technical_required_check_missing")
    elif not technical_pinned:
        blockers.add("ao_release_gate_technical_required_check_not_source_pinned")
    if not review_present:
        blockers.add("ao_release_gate_review_required_check_missing")
    elif not review_pinned:
        blockers.add("ao_release_gate_review_required_check_not_source_pinned")

    if rulesets.get("bypass_actors_empty") is not True:
        blockers.add("ruleset_bypass_actors_present")
    if branch_protection.get("required_approving_review_count", 0) != 0:
        blockers.add("legacy_required_review_blocks_low_risk_autonomy")
    if branch_protection.get("require_code_owner_reviews") is not False:
        blockers.add("legacy_code_owner_review_blocks_low_risk_autonomy")
    if merge_actor.get("viewer_can_administer") is True or merge_actor.get("permission") == "admin":
        blockers.add("merge_actor_admin_permission_observed")
    if merge_actor.get("administration_write_absent_for_dedicated_actor") is not True:
        blockers.add("dedicated_merge_actor_not_confirmed")
    if codeowners.get("broad_default_owner_absent") is not True:
        blockers.add("codeowners_broad_default_owner_present")
    if codeowners.get("governance_paths_owned") is not True:
        blockers.add("codeowners_governance_paths_not_fully_owned")

    decision = "ready_for_low_risk_dry_run" if not blockers else "blocked"
    next_required_slice = (
        "AO-MA-10a2 context-bound evidence bundle + registered-provider consensus schemas"
        if decision == "ready_for_low_risk_dry_run"
        else "resolve_live_github_enforcement_blockers_before_AO-MA-10a2"
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "generated_at": generated_at,
        "read_only": True,
        "mutations_performed": False,
        "release_authority": RELEASE_AUTHORITY,
        "ai_output_release_authority": False,
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "readiness_source": {
            "schema_version": snapshot.get("schema_version"),
            "artifact_kind": snapshot.get("artifact_kind"),
            "repository": snapshot.get("repository"),
            "branch": snapshot.get("branch"),
            "generated_at": snapshot.get("generated_at"),
            "decision": readiness.get("decision"),
            "blockers": sorted(set(_snapshot_collection_blockers(snapshot))),
        },
        "candidate_changed_files": candidate,
        "github_gate_requirements": {
            "ao_release_gate_technical_required_check_present": technical_present,
            "ao_release_gate_technical_source_pinned_to_actions": technical_pinned,
            "ao_release_gate_review_required_check_present": review_present,
            "ao_release_gate_review_source_pinned_to_actions": review_pinned,
            "ruleset_bypass_actors_empty": rulesets.get("bypass_actors_empty") is True,
            "legacy_required_review_disabled_for_low_risk": branch_protection.get(
                "required_approving_review_count",
                0,
            )
            == 0,
            "legacy_code_owner_review_disabled_for_low_risk": branch_protection.get("require_code_owner_reviews")
            is False,
            "dedicated_merge_actor_non_admin": not (
                merge_actor.get("viewer_can_administer") is True or merge_actor.get("permission") == "admin"
            ),
            "dedicated_merge_actor_without_admin_write": merge_actor.get(
                "administration_write_absent_for_dedicated_actor"
            )
            is True,
        },
        "decision": {
            "result": decision,
            "blockers": sorted(blockers),
            "warnings": sorted(warnings),
            "next_required_slice": next_required_slice,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", default=DEFAULT_SNAPSHOT_PATH)
    parser.add_argument("--plan", default=DEFAULT_PLAN_PATH)
    parser.add_argument("--changed-file", action="append")
    parser.add_argument("--changed-files-path", action="append")
    parser.add_argument("--git-base")
    parser.add_argument("--git-head", default="HEAD")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args(argv)

    snapshot = _load_json(Path(args.snapshot))
    plan = _load_json(Path(args.plan))
    changed_files = _changed_files_from_args(args)
    evidence = build_eligibility(
        snapshot=snapshot,
        plan=plan,
        changed_files=changed_files,
        generated_at=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.format == "text":
        print(evidence["decision"]["result"])
        for blocker in evidence["decision"]["blockers"]:
            print(f"blocker: {blocker}")
    else:
        print(json.dumps(evidence, indent=2, sort_keys=True))

    return 0 if evidence["decision"]["result"] == "ready_for_low_risk_dry_run" else 1


if __name__ == "__main__":
    raise SystemExit(main())
