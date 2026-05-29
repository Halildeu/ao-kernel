#!/usr/bin/env python3
"""Fail-closed autonomous PR merge executor.

This executor is deliberately narrow: it is not release authority. It only
executes the normal GitHub pull merge endpoint after GitHub reports that the
repo-owned required checks have passed and the source-pinned ao-release-gate
checks were produced by GitHub Actions.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


SCHEMA_VERSION = "ao-autonomous-pr-merge-executor-result.v1"
ARTIFACT_KIND = "ao_autonomous_pr_merge_executor_result"
RELEASE_AUTHORITY = "ao-release-gate+github-ruleset"
DEFAULT_REPO = "Halildeu/ao-kernel"
DEFAULT_BASE_REF = "main"
DEFAULT_EXPECTED_ACTOR = "github-actions[bot]"
EXECUTE_CONFIRMATION = "AO-AUTONOMOUS-MERGE-EXECUTE"
GITHUB_ACTIONS_APP_ID = 15368
SOURCE_PINNED_REQUIRED_CHECKS = ("ao-release-gate-technical", "ao-release-gate-review")
READY_MERGE_STATES = {"CLEAN", "HAS_HOOKS"}
INTEGRATION_TOKEN_WARNING = "github_user_endpoint_unavailable_for_integration_token"
FORBIDDEN_ADMIN_FLAG = "--" "admin"

Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=60)


def _json_command(command: list[str], runner: Runner) -> tuple[dict[str, Any] | list[Any], str | None]:
    proc = runner(command)
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}"
        return {}, detail
    if not proc.stdout.strip():
        return {}, "empty response"
    try:
        parsed = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {}, "invalid json response"
    if not isinstance(parsed, (dict, list)):
        return {}, "json response must be object or array"
    return parsed, None


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _string_list(value: Any) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _is_actions_integration_error(expected_actor: str, error: str | None) -> bool:
    return (
        expected_actor == DEFAULT_EXPECTED_ACTOR
        and error is not None
        and "resource not accessible by integration" in error.lower()
    )


def _permission_from_repo_payload(payload: dict[str, Any]) -> dict[str, Any]:
    permissions = payload.get("permissions")
    if not isinstance(permissions, dict):
        return {}
    if permissions.get("admin") is True:
        return {"permission": "admin", "role_name": "admin"}
    if permissions.get("maintain") is True:
        return {"permission": "maintain", "role_name": "maintain"}
    if permissions.get("push") is True:
        return {"permission": "write", "role_name": "write"}
    if permissions.get("triage") is True:
        return {"permission": "triage", "role_name": "triage"}
    if permissions.get("pull") is True:
        return {"permission": "read", "role_name": "read"}
    return {}


def _safe_head_ref_for_delete(head_ref: Any, base_ref: str, *, is_cross_repository: bool) -> str | None:
    if is_cross_repository:
        return None
    if not isinstance(head_ref, str) or not head_ref:
        return None
    if head_ref == base_ref or head_ref.startswith("refs/"):
        return None
    return head_ref


def merge_command(repo: str, pr_number: int, *, head_sha: str, gh_bin: str = "gh") -> list[str]:
    return [
        gh_bin,
        "api",
        f"repos/{repo}/pulls/{pr_number}/merge",
        "--method",
        "PUT",
        "-f",
        "merge_method=squash",
        "-f",
        f"sha={head_sha}",
    ]


def branch_delete_command(repo: str, head_ref: str, gh_bin: str = "gh") -> list[str]:
    return [gh_bin, "api", f"repos/{repo}/git/refs/heads/{head_ref}", "--method", "DELETE"]


def collect_live_state(
    *,
    repo: str,
    pr_number: int,
    gh_bin: str,
    expected_actor: str,
    runner: Runner = _run,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    viewer, error = _json_command([gh_bin, "api", "user"], runner)
    if error is not None or not isinstance(viewer, dict):
        if _is_actions_integration_error(expected_actor, error):
            viewer = {"login": expected_actor}
            warnings.append(INTEGRATION_TOKEN_WARNING)
        else:
            errors.append(f"viewer: {error or 'invalid shape'}")
            viewer = {}

    login = _string(_object(viewer).get("login"))
    permission: dict[str, Any] = {}
    if login and login != expected_actor:
        permission_payload, error = _json_command(
            [gh_bin, "api", f"repos/{repo}/collaborators/{login}/permission"],
            runner,
        )
        if error is None and isinstance(permission_payload, dict):
            permission = permission_payload
        else:
            errors.append(f"permission: {error or 'invalid shape'}")
    else:
        repo_payload, error = _json_command([gh_bin, "api", f"repos/{repo}"], runner)
        if error is None and isinstance(repo_payload, dict):
            permission = _permission_from_repo_payload(repo_payload)
        else:
            errors.append(f"repo_permission: {error or 'invalid shape'}")

    pr_view, error = _json_command(
        [
            gh_bin,
            "pr",
            "view",
            str(pr_number),
            "--repo",
            repo,
            "--json",
            "state,isDraft,baseRefName,headRefName,headRefOid,isCrossRepository,mergeStateStatus,mergedAt,url",
        ],
        runner,
    )
    if error is not None or not isinstance(pr_view, dict):
        errors.append(f"pr_view: {error or 'invalid shape'}")
        pr_view = {}

    required_checks, error = _json_command(
        [
            gh_bin,
            "pr",
            "checks",
            str(pr_number),
            "--repo",
            repo,
            "--required",
            "--json",
            "name,bucket,state,link",
        ],
        runner,
    )
    if error is not None or not isinstance(required_checks, list):
        errors.append(f"pr_checks: {error or 'invalid shape'}")
        required_checks = []

    head_sha = _string(_object(pr_view).get("headRefOid"))
    check_runs: dict[str, Any] | list[Any] = {}
    if head_sha:
        check_runs, error = _json_command(
            [gh_bin, "api", f"repos/{repo}/commits/{head_sha}/check-runs?per_page=100"],
            runner,
        )
        if error is not None or not isinstance(check_runs, dict):
            errors.append(f"check_runs: {error or 'invalid shape'}")
            check_runs = {}

    return {
        "viewer": viewer,
        "permission": permission,
        "pr_view": pr_view,
        "required_checks": required_checks,
        "check_runs": check_runs,
        "collection_errors": errors,
        "collection_warnings": warnings,
    }


def _required_checks_pass(required_checks: list[Any]) -> tuple[bool, list[dict[str, Any]]]:
    failing: list[dict[str, Any]] = []
    for raw in required_checks:
        item = raw if isinstance(raw, dict) else {}
        if item.get("bucket") != "pass":
            failing.append(
                {
                    "name": item.get("name"),
                    "bucket": item.get("bucket"),
                    "state": item.get("state"),
                    "link": item.get("link"),
                }
            )
    return not failing, failing


def _source_pinned_release_gate_checks(check_runs_payload: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    check_runs = check_runs_payload.get("check_runs")
    runs = check_runs if isinstance(check_runs, list) else []
    observed: list[dict[str, Any]] = []
    for required_name in SOURCE_PINNED_REQUIRED_CHECKS:
        matches: list[dict[str, Any]] = []
        for raw in runs:
            run = raw if isinstance(raw, dict) else {}
            if run.get("name") != required_name:
                continue
            app = _object(run.get("app"))
            matches.append(
                {
                    "name": run.get("name"),
                    "status": run.get("status"),
                    "conclusion": run.get("conclusion"),
                    "app_id": app.get("id"),
                    "app_slug": app.get("slug"),
                    "details_url": run.get("details_url"),
                }
            )
        selected = next(
            (
                item
                for item in matches
                if item["app_id"] == GITHUB_ACTIONS_APP_ID
                and item["status"] == "completed"
                and item["conclusion"] == "success"
            ),
            None,
        )
        observed.append(selected or {"name": required_name, "matches": matches})
    return all("app_id" in item for item in observed), observed


def build_result(
    *,
    repo: str,
    pr_number: int,
    live_state: dict[str, Any],
    expected_actor: str,
    base_ref: str,
    event_head_sha: str | None,
    execute: bool,
    confirmation: str | None,
    merge_exit_code: int | None = None,
    merge_error: str = "",
    branch_delete_exit_code: int | None = None,
    branch_delete_error: str = "",
    branch_delete_command_argv: list[str] | None = None,
    gh_bin: str = "gh",
) -> dict[str, Any]:
    blockers: set[str] = set()
    warnings: set[str] = set(_string_list(live_state.get("collection_warnings")))
    blockers.update(_string_list(live_state.get("collection_errors")))

    viewer = _object(live_state.get("viewer"))
    permission = _object(live_state.get("permission"))
    pr_view = _object(live_state.get("pr_view"))
    required_checks = live_state.get("required_checks")
    required_checks_list = required_checks if isinstance(required_checks, list) else []
    check_runs = _object(live_state.get("check_runs"))
    collection_error_items = _string_list(live_state.get("collection_errors"))

    actual_actor = _string(viewer.get("login"))
    permission_name = _string(permission.get("permission")) or _string(permission.get("role_name"))

    if actual_actor != expected_actor:
        blockers.add("unexpected_merge_actor")
    if permission_name == "admin" or permission.get("role_name") == "admin":
        blockers.add("merge_actor_admin_permission_observed")
    if permission_name != "write":
        blockers.add("merge_actor_not_write")

    pr_state = pr_view.get("state")
    merged_at = _string(pr_view.get("mergedAt"))
    if pr_state != "OPEN":
        if pr_state == "MERGED" or merged_at:
            warnings.add("pr_already_merged_noop")
        else:
            blockers.add("pr_not_open")
    if pr_view.get("isDraft") is True:
        blockers.add("pr_is_draft")
    if pr_view.get("baseRefName") != base_ref:
        blockers.add("pr_base_not_expected")
    if pr_view.get("isCrossRepository") is True:
        blockers.add("cross_repository_pr_not_supported")
    if pr_view.get("mergeStateStatus") not in READY_MERGE_STATES and pr_state == "OPEN":
        blockers.add("pr_merge_state_not_clean")

    head_sha = _string(pr_view.get("headRefOid"))
    if not head_sha:
        blockers.add("pr_head_sha_missing")
    if event_head_sha and head_sha and event_head_sha != head_sha:
        blockers.add("event_head_sha_stale")

    checks_ok, failing_checks = _required_checks_pass(required_checks_list)
    if not checks_ok:
        blockers.add("required_checks_not_passed")

    source_pinned_ok, source_pinned_observed = _source_pinned_release_gate_checks(check_runs)
    if not source_pinned_ok:
        blockers.add("source_pinned_ao_release_gate_checks_not_success")

    merge_argv = merge_command(repo, pr_number, head_sha=head_sha or "<missing-head-sha>", gh_bin=gh_bin)
    if any(item == FORBIDDEN_ADMIN_FLAG for item in merge_argv):
        blockers.add("admin_merge_command_constructed")
    if execute and confirmation != EXECUTE_CONFIRMATION:
        blockers.add("execute_confirmation_missing")

    safe_head_ref = _safe_head_ref_for_delete(
        pr_view.get("headRefName"),
        base_ref,
        is_cross_repository=pr_view.get("isCrossRepository") is True,
    )
    delete_argv = branch_delete_command_argv
    if delete_argv is None:
        delete_argv = branch_delete_command(repo, safe_head_ref, gh_bin=gh_bin) if safe_head_ref else []

    merge_attempted = bool(execute and not blockers and pr_state == "OPEN")
    if merge_exit_code not in (None, 0):
        blockers.add("merge_command_failed")
    if merge_exit_code == 0 and branch_delete_exit_code not in (None, 0):
        warnings.add("branch_delete_failed")

    if pr_state == "MERGED" or (merged_at and "pr_not_open" not in blockers):
        result = "noop_already_merged"
        for item in collection_error_items:
            warnings.add(f"noop_collection_error:{item}")
        blockers.clear()
    elif blockers:
        result = "blocked"
    elif execute and merge_exit_code == 0:
        result = "merged"
    elif execute and merge_exit_code is None:
        result = "ready_to_merge"
    else:
        result = "ready_for_merge_dry_run"

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "generated_at": _utc_now(),
        "repository": repo,
        "pr_number": pr_number,
        "base_ref": base_ref,
        "expected_actor": expected_actor,
        "actual_actor": actual_actor,
        "actor_permission": permission_name,
        "event_head_sha": event_head_sha,
        "dry_run": not execute,
        "execute_requested": execute,
        "merge_command_attempted": merge_attempted,
        "branch_delete_attempted": branch_delete_exit_code is not None,
        "mutations_performed": result == "merged",
        "release_authority": RELEASE_AUTHORITY,
        "ai_output_release_authority": False,
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "pr_state": {
            "state": pr_view.get("state"),
            "is_draft": pr_view.get("isDraft"),
            "base_ref": pr_view.get("baseRefName"),
            "head_ref": pr_view.get("headRefName"),
            "head_sha": head_sha,
            "is_cross_repository": pr_view.get("isCrossRepository"),
            "merge_state_status": pr_view.get("mergeStateStatus"),
            "merged_at": merged_at,
        },
        "required_checks": {
            "total": len(required_checks_list),
            "all_passed": checks_ok,
            "failing": failing_checks,
        },
        "source_pinned_release_gate_checks": {
            "required_app_id": GITHUB_ACTIONS_APP_ID,
            "all_passed": source_pinned_ok,
            "observed": source_pinned_observed,
        },
        "merge_command_argv": merge_argv,
        "merge_error": merge_error if merge_exit_code not in (None, 0) else "",
        "branch_delete_command_argv": delete_argv,
        "branch_delete_error": branch_delete_error if branch_delete_exit_code not in (None, 0) else "",
        "collection_errors": _string_list(live_state.get("collection_errors")),
        "decision": {
            "result": result,
            "blockers": sorted(blockers),
            "warnings": sorted(warnings),
            "next_required_slice": (
                "autonomous merge completed"
                if result in {"merged", "noop_already_merged"}
                else "wait for required checks and rerun autonomous merge executor"
                if result == "blocked"
                else "execute autonomous merge executor"
            ),
        },
    }


def execute_merge(
    *,
    repo: str,
    pr_number: int,
    pr_view: dict[str, Any],
    base_ref: str,
    gh_bin: str,
    runner: Runner = _run,
) -> tuple[int, str, int | None, str, list[str], list[str]]:
    head_sha = _string(pr_view.get("headRefOid"))
    if not head_sha:
        return 1, "missing head sha", None, "", [], []
    merge_argv = merge_command(repo, pr_number, head_sha=head_sha, gh_bin=gh_bin)
    merge_proc = runner(merge_argv)
    merge_error = merge_proc.stderr.strip() or merge_proc.stdout.strip()
    delete_argv: list[str] = []
    delete_exit_code: int | None = None
    delete_error = ""
    safe_head_ref = _safe_head_ref_for_delete(
        pr_view.get("headRefName"),
        base_ref,
        is_cross_repository=pr_view.get("isCrossRepository") is True,
    )
    if merge_proc.returncode == 0 and safe_head_ref:
        delete_argv = branch_delete_command(repo, safe_head_ref, gh_bin=gh_bin)
        delete_proc = runner(delete_argv)
        delete_exit_code = delete_proc.returncode
        delete_error = delete_proc.stderr.strip() or delete_proc.stdout.strip()
    return merge_proc.returncode, merge_error, delete_exit_code, delete_error, merge_argv, delete_argv


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--base-ref", default=DEFAULT_BASE_REF)
    parser.add_argument("--expected-actor", default=DEFAULT_EXPECTED_ACTOR)
    parser.add_argument("--event-head-sha")
    parser.add_argument("--gh-bin", default="gh")
    parser.add_argument("--output", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirmation")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args(argv)

    live_state = collect_live_state(
        repo=args.repo,
        pr_number=args.pr,
        gh_bin=args.gh_bin,
        expected_actor=args.expected_actor,
    )
    preliminary = build_result(
        repo=args.repo,
        pr_number=args.pr,
        live_state=live_state,
        expected_actor=args.expected_actor,
        base_ref=args.base_ref,
        event_head_sha=args.event_head_sha,
        execute=args.execute,
        confirmation=args.confirmation,
        gh_bin=args.gh_bin,
    )

    merge_exit_code: int | None = None
    merge_error = ""
    branch_delete_exit_code: int | None = None
    branch_delete_error = ""
    branch_delete_argv: list[str] = []
    if preliminary["decision"]["result"] == "ready_to_merge":
        (
            merge_exit_code,
            merge_error,
            branch_delete_exit_code,
            branch_delete_error,
            _merge_argv,
            branch_delete_argv,
        ) = execute_merge(
            repo=args.repo,
            pr_number=args.pr,
            pr_view=_object(live_state.get("pr_view")),
            base_ref=args.base_ref,
            gh_bin=args.gh_bin,
        )

    result = build_result(
        repo=args.repo,
        pr_number=args.pr,
        live_state=live_state,
        expected_actor=args.expected_actor,
        base_ref=args.base_ref,
        event_head_sha=args.event_head_sha,
        execute=args.execute,
        confirmation=args.confirmation,
        merge_exit_code=merge_exit_code,
        merge_error=merge_error,
        branch_delete_exit_code=branch_delete_exit_code,
        branch_delete_error=branch_delete_error,
        branch_delete_command_argv=branch_delete_argv,
        gh_bin=args.gh_bin,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.format == "text":
        print(result["decision"]["result"])
        for blocker in result["decision"]["blockers"]:
            print(f"blocker: {blocker}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["decision"]["result"] in {"ready_for_merge_dry_run", "merged", "noop_already_merged"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
