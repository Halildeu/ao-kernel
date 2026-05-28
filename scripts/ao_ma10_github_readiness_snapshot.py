#!/usr/bin/env python3
"""Collect the AO-MA-10a0 GitHub readiness snapshot.

This script is intentionally read-only. It records whether the live GitHub
repository state is compatible with the future low-risk autonomous merge lane.
It does not mutate rulesets, branch protection, CODEOWNERS, workflows, or PRs.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "ao-ma-10-github-readiness-snapshot.v1"
ARTIFACT_KIND = "ao_ma_10_github_readiness_snapshot"
RELEASE_AUTHORITY = "ao-release-gate+github-ruleset"
AO_RELEASE_GATE_REQUIRED_CHECKS = ("ao-release-gate-technical", "ao-release-gate-review")
GITHUB_ACTIONS_APP_ID = 15368


def _run_json_with_error(command: list[str], label: str) -> tuple[dict[str, Any] | list[Any], str | None]:
    proc = subprocess.run(command, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        return {}, f"{label}: command failed with exit {proc.returncode}"
    if not proc.stdout.strip():
        return {}, f"{label}: empty response"
    try:
        data: dict[str, Any] | list[Any] = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {}, f"{label}: invalid json response"
    return data, None


def _split_repo(repository: str) -> tuple[str, str]:
    match = re.fullmatch(r"([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", repository)
    if match is None:
        raise ValueError("repository must be OWNER/NAME")
    return match.group(1), match.group(2)


def _repo_info_with_error(gh_bin: str, repository: str) -> tuple[dict[str, Any], str | None]:
    owner, name = _split_repo(repository)
    query = """
      query($owner:String!, $name:String!) {
        repository(owner:$owner, name:$name) {
          nameWithOwner
          autoMergeAllowed
          mergeCommitAllowed
          squashMergeAllowed
          rebaseMergeAllowed
          deleteBranchOnMerge
          viewerPermission
          viewerCanAdminister
        }
      }
    """
    data, error = _run_json_with_error(
        [
            gh_bin,
            "api",
            "graphql",
            "-f",
            f"query={query}",
            "-F",
            f"owner={owner}",
            "-F",
            f"name={name}",
        ],
        "repository",
    )
    if error is not None:
        return {}, error
    if not isinstance(data, dict):
        return {}, "repository: invalid response shape"
    if isinstance(data.get("errors"), list):
        return {}, "repository: graphql errors present"
    repo = ((data.get("data") or {}).get("repository") or {}) if isinstance(data.get("data"), dict) else {}
    if not isinstance(repo, dict) or not repo:
        return {}, "repository: missing repository payload"
    return repo, None


def _viewer_login_with_error(gh_bin: str) -> tuple[str | None, str | None]:
    data, error = _run_json_with_error([gh_bin, "api", "user"], "viewer_login")
    if error is not None:
        return None, error
    if isinstance(data, dict) and isinstance(data.get("login"), str):
        return data["login"], None
    return None, "viewer_login: missing login"


def _viewer_repo_permission_with_error(gh_bin: str, repository: str, login: str | None) -> tuple[str | None, str | None]:
    if not login:
        return None, None
    data, error = _run_json_with_error(
        [gh_bin, "api", f"repos/{repository}/collaborators/{login}/permission"],
        "viewer_permission",
    )
    if error is not None:
        return None, error
    if isinstance(data, dict) and isinstance(data.get("permission"), str):
        return data["permission"], None
    return None, "viewer_permission: missing permission"


def _codeowners_text_with_error(gh_bin: str, repository: str, branch: str) -> tuple[str, str | None]:
    data, error = _run_json_with_error(
        [gh_bin, "api", f"repos/{repository}/contents/.github/CODEOWNERS?ref={branch}"],
        "codeowners",
    )
    if error is not None:
        return "", error
    if not isinstance(data, dict) or not isinstance(data.get("content"), str):
        return "", "codeowners: missing content field"
    encoded = data["content"]
    try:
        return base64.b64decode(encoded.encode("utf-8")).decode("utf-8"), None
    except Exception:
        return "", "codeowners: invalid base64 content"


def _ssot_required_check_claim_observed(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    # Ignore historical changelog/runbook prose. This predicate is only meant
    # to detect current-status claims that conflict with live GitHub API truth.
    current_text = text.split("## 2. Current Baseline", 1)[0]
    return (
        "ao-release-gate" in current_text
        and "required check" in current_text
        and "ruleset id `16803733`" in current_text
        and "integration_id 15368" in current_text
    )


def _normalize_branch_protection(protection: dict[str, Any]) -> dict[str, Any]:
    reviews = protection.get("required_pull_request_reviews")
    reviews = reviews if isinstance(reviews, dict) else {}
    status_checks = protection.get("required_status_checks")
    status_checks = status_checks if isinstance(status_checks, dict) else {}
    enforce_admins = protection.get("enforce_admins")
    enforce_admins = enforce_admins if isinstance(enforce_admins, dict) else {}
    checks = []
    for item in status_checks.get("checks", []):
        if not isinstance(item, dict):
            continue
        checks.append(
            {
                "context": item.get("context"),
                "app_id": item.get("app_id"),
            }
        )
    contexts = [item for item in status_checks.get("contexts", []) if isinstance(item, str)]
    return {
        "present": bool(protection),
        "enforce_admins": bool(enforce_admins.get("enabled")),
        "required_approving_review_count": reviews.get("required_approving_review_count", 0),
        "require_code_owner_reviews": bool(reviews.get("require_code_owner_reviews")),
        "dismiss_stale_reviews": bool(reviews.get("dismiss_stale_reviews")),
        "strict_status_checks": bool(status_checks.get("strict")),
        "required_checks": sorted({*contexts, *[str(check["context"]) for check in checks if check.get("context")]}),
        "required_check_source_pins": checks,
    }


def _ruleset_applies_to_default_branch(ruleset: dict[str, Any]) -> bool:
    if ruleset.get("target") != "branch" or ruleset.get("enforcement") != "active":
        return False
    conditions = ruleset.get("conditions")
    if not isinstance(conditions, dict):
        return True
    ref_name = conditions.get("ref_name")
    if not isinstance(ref_name, dict):
        return True
    include = ref_name.get("include")
    if not isinstance(include, list):
        return True
    exclude = ref_name.get("exclude")
    excluded_refs = exclude if isinstance(exclude, list) else []
    default_branch_tokens = {"~DEFAULT_BRANCH", "refs/heads/main", "main"}
    if any(token in excluded_refs for token in default_branch_tokens):
        return False
    return "~ALL" in include or any(token in include for token in default_branch_tokens)


def _normalize_rulesets(rulesets: list[Any], branch_rules: list[Any]) -> dict[str, Any]:
    default_rulesets: list[dict[str, Any]] = []
    bypass_actors: list[Any] = []
    for item in rulesets:
        if not isinstance(item, dict) or not _ruleset_applies_to_default_branch(item):
            continue
        default_rulesets.append(
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "target": item.get("target"),
                "source_type": item.get("source_type"),
                "enforcement": item.get("enforcement"),
                "bypass_actors_count": len(item.get("bypass_actors") or []),
                "rule_types": sorted(
                    rule.get("type")
                    for rule in item.get("rules", [])
                    if isinstance(rule, dict) and isinstance(rule.get("type"), str)
                ),
            }
        )
        bypass_actors.extend(item.get("bypass_actors") or [])

    required_checks: list[dict[str, Any]] = []
    for rule in branch_rules:
        if not isinstance(rule, dict) or rule.get("type") != "required_status_checks":
            continue
        params = rule.get("parameters") if isinstance(rule.get("parameters"), dict) else {}
        for check in params.get("required_status_checks", []) or []:
            if not isinstance(check, dict):
                continue
            context = check.get("context") or check.get("name")
            integration_id = check.get("integration_id") or check.get("app_id")
            required_checks.append({"context": context, "integration_id": integration_id})

    return {
        "default_branch_rulesets": default_rulesets,
        "bypass_actors_count": len(bypass_actors),
        "bypass_actors_empty": len(bypass_actors) == 0,
        "effective_required_checks": required_checks,
    }


def _required_checks_present(checks: list[dict[str, Any]], *, id_key: str) -> tuple[bool, bool]:
    matching_by_context = {
        str(check.get("context")): check
        for check in checks
        if check.get("context") in AO_RELEASE_GATE_REQUIRED_CHECKS
    }
    if set(matching_by_context) != set(AO_RELEASE_GATE_REQUIRED_CHECKS):
        return False, False
    source_pinned = all(
        matching_by_context[context].get(id_key) == GITHUB_ACTIONS_APP_ID
        for context in AO_RELEASE_GATE_REQUIRED_CHECKS
    )
    return True, source_pinned


def _codeowners_summary(text: str) -> dict[str, Any]:
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
    broad_default_owner_present = any(line.startswith("* ") or line.startswith("*\t") for line in lines)
    governance_patterns = [
        "/.github/",
        "/AGENTS.md",
        "/CLAUDE.md",
        "/.claude/",
        "/ao_kernel/ao_release_gate",
        "/scripts/ao_release_gate",
        "/scripts/local_gpp_gate",
        "/deploy/",
    ]
    governance_paths_owned = all(any(line.startswith(pattern) for line in lines) for pattern in governance_patterns)
    low_risk_prefixes_owned = [
        prefix
        for prefix in ("/.claude/", "/ao_kernel/defaults/schemas/*gate*.json")
        if any(line.startswith(prefix) for line in lines)
    ]
    return {
        "present": bool(lines),
        "broad_default_owner_present": broad_default_owner_present,
        "broad_default_owner_absent": not broad_default_owner_present,
        "governance_paths_owned": governance_paths_owned,
        "low_risk_prefixes_still_codeowned": low_risk_prefixes_owned,
    }


def build_snapshot(
    *,
    repository: str,
    branch: str,
    generated_at: str,
    repo_info: dict[str, Any],
    viewer_login: str | None,
    viewer_permission: str | None,
    branch_protection: dict[str, Any],
    rulesets: list[Any],
    branch_rules: list[Any],
    codeowners_text: str,
    collection_errors: list[str] | None = None,
    ssot_required_check_claim_observed: bool = False,
    ssot_claim_source: str | None = None,
) -> dict[str, Any]:
    normalized_bp = _normalize_branch_protection(branch_protection)
    normalized_rulesets = _normalize_rulesets(rulesets, branch_rules)
    codeowners = _codeowners_summary(codeowners_text)

    bp_gate_present, bp_gate_pinned = _required_checks_present(
        normalized_bp["required_check_source_pins"],
        id_key="app_id",
    )
    ruleset_gate_present, ruleset_gate_pinned = _required_checks_present(
        normalized_rulesets["effective_required_checks"],
        id_key="integration_id",
    )
    # AO-MA-10 uses the ruleset as the release-authority surface. Legacy
    # branch protection is still recorded, but it is not sufficient by itself.
    gate_present = ruleset_gate_present
    gate_pinned = ruleset_gate_pinned

    blockers: list[str] = []
    warnings: list[str] = []

    errors = collection_errors or []

    if errors:
        blockers.append("github_api_read_failed")

    if not gate_present:
        blockers.append("ao_release_gate_required_check_missing")
    elif not gate_pinned:
        blockers.append("ao_release_gate_required_check_not_source_pinned")

    if not normalized_rulesets["bypass_actors_empty"]:
        blockers.append("ruleset_bypass_actors_present")

    if normalized_bp["required_approving_review_count"]:
        blockers.append("legacy_required_review_blocks_low_risk_autonomy")

    viewer_can_administer = bool(repo_info.get("viewerCanAdminister"))
    if viewer_can_administer or viewer_permission == "admin":
        blockers.append("merge_actor_admin_permission_observed")

    if not bool(repo_info.get("autoMergeAllowed")):
        warnings.append("repository_auto_merge_disabled_merge_agent_direct_mode_required")

    if codeowners["low_risk_prefixes_still_codeowned"]:
        warnings.append("some_nominal_low_risk_prefixes_still_codeowned")

    if not codeowners["broad_default_owner_absent"]:
        blockers.append("codeowners_broad_default_owner_present")

    if not codeowners["governance_paths_owned"]:
        blockers.append("codeowners_governance_paths_not_fully_owned")

    ssot_conflict = ssot_required_check_claim_observed and not ruleset_gate_pinned
    if ssot_conflict:
        blockers.append("ssot_live_required_check_drift_detected")

    decision = "ready_for_dry_run" if not blockers else "blocked"

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "repository": repository,
        "branch": branch,
        "generated_at": generated_at,
        "snapshot_source": "github_api_read_only",
        "read_only": True,
        "mutations_performed": False,
        "release_authority": RELEASE_AUTHORITY,
        "ai_output_release_authority": False,
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "repository_settings": {
            "auto_merge_allowed": bool(repo_info.get("autoMergeAllowed")),
            "merge_commit_allowed": bool(repo_info.get("mergeCommitAllowed")),
            "squash_merge_allowed": bool(repo_info.get("squashMergeAllowed")),
            "rebase_merge_allowed": bool(repo_info.get("rebaseMergeAllowed")),
            "delete_branch_on_merge": bool(repo_info.get("deleteBranchOnMerge")),
        },
        "merge_actor": {
            "login": viewer_login,
            "permission": viewer_permission or repo_info.get("viewerPermission"),
            "viewer_can_administer": viewer_can_administer,
            "administration_write_absent_for_dedicated_actor": False,
        },
        "branch_protection": {
            **normalized_bp,
            "ao_release_gate_required_check_present": bp_gate_present,
            "ao_release_gate_source_pinned_to_actions": bp_gate_pinned,
        },
        "rulesets": {
            **normalized_rulesets,
            "ao_release_gate_required_check_present": ruleset_gate_present,
            "ao_release_gate_source_pinned_to_actions": ruleset_gate_pinned,
        },
        "codeowners": codeowners,
        "collection_errors": errors,
        "ssot_cross_check": {
            "prior_required_check_claim_observed": ssot_required_check_claim_observed,
            "live_snapshot_conflicts_with_prior_claim": ssot_conflict,
            "prior_claim_source": ssot_claim_source,
        },
        "readiness": {
            "decision": decision,
            "blockers": sorted(set(blockers)),
            "warnings": sorted(set(warnings)),
            "next_required_slice": "AO-MA-10a1 autonomous_merge_eligibility after blockers are resolved",
        },
    }


def collect_live_snapshot(repository: str, branch: str, gh_bin: str) -> dict[str, Any]:
    collection_errors: list[str] = []
    repo_info, error = _repo_info_with_error(gh_bin, repository)
    if error:
        collection_errors.append(error)
    login, error = _viewer_login_with_error(gh_bin)
    if error:
        collection_errors.append(error)
    permission, error = _viewer_repo_permission_with_error(gh_bin, repository, login)
    if error:
        collection_errors.append(error)
    protection, error = _run_json_with_error(
        [gh_bin, "api", f"repos/{repository}/branches/{branch}/protection"],
        "branch_protection",
    )
    if error:
        collection_errors.append(error)
    rulesets_raw, error = _run_json_with_error([gh_bin, "api", f"repos/{repository}/rulesets"], "rulesets")
    if error:
        collection_errors.append(error)
    detailed_rulesets: list[Any] = []
    if isinstance(rulesets_raw, list):
        for entry in rulesets_raw:
            if not isinstance(entry, dict) or entry.get("target") != "branch":
                continue
            ruleset_id = entry.get("id")
            if isinstance(ruleset_id, int):
                detailed, error = _run_json_with_error(
                    [gh_bin, "api", f"repos/{repository}/rulesets/{ruleset_id}"],
                    f"ruleset:{ruleset_id}",
                )
                if error:
                    collection_errors.append(error)
                detailed_rulesets.append(detailed if detailed else entry)
    branch_rules, error = _run_json_with_error(
        [gh_bin, "api", f"repos/{repository}/rules/branches/{branch}"],
        "branch_rules",
    )
    if error:
        collection_errors.append(error)
    codeowners, error = _codeowners_text_with_error(gh_bin, repository, branch)
    if error:
        collection_errors.append(error)

    return build_snapshot(
        repository=repository,
        branch=branch,
        generated_at=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        repo_info=repo_info,
        viewer_login=login,
        viewer_permission=permission,
        branch_protection=protection if isinstance(protection, dict) else {},
        rulesets=detailed_rulesets,
        branch_rules=branch_rules if isinstance(branch_rules, list) else [],
        codeowners_text=codeowners,
        collection_errors=collection_errors,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default="Halildeu/ao-kernel")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--gh-bin", default="gh")
    parser.add_argument(
        "--ssot-status-path",
        default=".claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md",
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    snapshot = collect_live_snapshot(args.repository, args.branch, args.gh_bin)
    ssot_path = Path(args.ssot_status_path)
    ssot_claim_observed = _ssot_required_check_claim_observed(ssot_path)
    ssot_conflict = ssot_claim_observed and not snapshot["rulesets"]["ao_release_gate_source_pinned_to_actions"]
    snapshot["ssot_cross_check"] = {
        "prior_required_check_claim_observed": ssot_claim_observed,
        "live_snapshot_conflicts_with_prior_claim": ssot_conflict,
        "prior_claim_source": str(ssot_path),
    }
    if ssot_conflict:
        blockers = set(snapshot["readiness"]["blockers"])
        blockers.add("ssot_live_required_check_drift_detected")
        snapshot["readiness"]["blockers"] = sorted(blockers)
        snapshot["readiness"]["decision"] = "blocked"
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
