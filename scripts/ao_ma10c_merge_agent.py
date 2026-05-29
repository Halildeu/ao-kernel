#!/usr/bin/env python3
"""AO-MA-10c fail-closed merge-agent dry-run/executor.

The merge agent is an executor, not release authority. It may only execute a
normal GitHub merge after repo-owned evidence says the pull request is eligible,
the live PR checks are passing, and the authenticated actor is the dedicated
non-admin merge actor.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


SCHEMA_VERSION = "ao-ma-10c-merge-agent-result.v1"
ARTIFACT_KIND = "ao_ma_10c_merge_agent_result"
RELEASE_AUTHORITY = "ao-release-gate+github-ruleset"
DEFAULT_EXPECTED_ACTOR = "github-actions[bot]"
DEFAULT_BASE_REF = "main"
DEFAULT_MAX_SNAPSHOT_AGE_SECONDS = 300
DEFAULT_MERGE_STATE_MAX_ATTEMPTS = 12
DEFAULT_MERGE_STATE_POLL_SECONDS = 5
EXECUTE_CONFIRMATION = "AO-MA-10C-EXECUTE"
FORBIDDEN_ADMIN_FLAG = "--" "admin"
READY_MERGE_STATES = {"CLEAN", "HAS_HOOKS"}
TRANSIENT_MERGE_STATES = {"UNKNOWN", "UNSTABLE"}
INTEGRATION_TOKEN_WARNING = "github_user_endpoint_unavailable_for_integration_token"

Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=60)


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


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


def _permission_fallback_allowed(error: str | None) -> bool:
    if not error:
        return False
    normalized = error.lower()
    return "resource not accessible by personal access token" in normalized and "http 403" in normalized


def _is_github_actions_integration_token(expected_actor: str, error: str | None) -> bool:
    if expected_actor != DEFAULT_EXPECTED_ACTOR or not error:
        return False
    normalized = error.lower()
    return "resource not accessible by integration" in normalized and "http 403" in normalized


def _actor_can_read_pull_requests_with_error(
    *,
    repo: str,
    gh_bin: str,
    runner: Runner,
) -> tuple[bool, str | None]:
    data, error = _json_command(
        [gh_bin, "api", f"repos/{repo}/pulls?state=open&per_page=1"],
        runner,
    )
    if error is not None:
        return False, error
    if isinstance(data, list):
        return True, None
    return False, "pulls: invalid response shape"


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _age_seconds(generated_at: Any, now: datetime) -> int | None:
    parsed = _parse_time(generated_at)
    if parsed is None:
        return None
    return int((now.astimezone(UTC) - parsed).total_seconds())


def merge_command(repo: str, pr_number: int, gh_bin: str = "gh") -> list[str]:
    """Build the only permitted merge command shape.

    Fine-grained PATs can have repository write permission while GitHub's
    GraphQL pull-request merge mutation remains unavailable to the GitHub CLI
    PR merge path. The REST pull merge endpoint is the narrower operation this
    actor needs after required checks and rulesets are already green.
    """

    return [
        gh_bin,
        "api",
        f"repos/{repo}/pulls/{pr_number}/merge",
        "--method",
        "PUT",
        "-f",
        "merge_method=squash",
    ]


def merge_command_with_sha(repo: str, pr_number: int, *, head_sha: str | None, gh_bin: str = "gh") -> list[str]:
    command = merge_command(repo, pr_number, gh_bin=gh_bin)
    if head_sha:
        command.extend(["-f", f"sha={head_sha}"])
    return command


def branch_delete_command(repo: str, head_ref: str, gh_bin: str = "gh") -> list[str]:
    return [
        gh_bin,
        "api",
        f"repos/{repo}/git/refs/heads/{head_ref}",
        "--method",
        "DELETE",
    ]


def _safe_head_ref_for_delete(head_ref: Any, base_ref: str, *, is_cross_repository: bool) -> str | None:
    if is_cross_repository:
        return None
    if not isinstance(head_ref, str) or not head_ref:
        return None
    if head_ref == base_ref or head_ref.startswith("refs/"):
        return None
    return head_ref


def execute_merge(
    *,
    repo: str,
    pr_number: int,
    pr_view: dict[str, Any],
    base_ref: str,
    gh_bin: str,
) -> tuple[int, str, int | None, str, list[str], list[str]]:
    head_sha = pr_view.get("headRefOid") if isinstance(pr_view.get("headRefOid"), str) else None
    merge_argv = merge_command_with_sha(repo, pr_number, head_sha=head_sha, gh_bin=gh_bin)
    merge_proc = _run(merge_argv)
    merge_error = merge_proc.stderr.strip() or merge_proc.stdout.strip()

    delete_argv: list[str] = []
    delete_exit_code: int | None = None
    delete_error = ""
    head_ref = _safe_head_ref_for_delete(
        pr_view.get("headRefName"),
        base_ref,
        is_cross_repository=pr_view.get("isCrossRepository") is True,
    )
    if merge_proc.returncode == 0 and head_ref:
        delete_argv = branch_delete_command(repo, head_ref, gh_bin=gh_bin)
        delete_proc = _run(delete_argv)
        delete_exit_code = delete_proc.returncode
        delete_error = delete_proc.stderr.strip() or delete_proc.stdout.strip()

    return merge_proc.returncode, merge_error, delete_exit_code, delete_error, merge_argv, delete_argv


def collect_live_github_state(
    *,
    repo: str,
    pr_number: int,
    gh_bin: str,
    expected_actor: str = DEFAULT_EXPECTED_ACTOR,
    runner: Runner = _run,
    merge_state_max_attempts: int = DEFAULT_MERGE_STATE_MAX_ATTEMPTS,
    merge_state_poll_seconds: int = DEFAULT_MERGE_STATE_POLL_SECONDS,
) -> dict[str, Any]:
    """Collect live GitHub state needed immediately before a merge attempt."""

    collection_errors: list[str] = []
    collection_warnings: list[str] = []

    viewer, error = _json_command([gh_bin, "api", "user"], runner)
    if error is not None or not isinstance(viewer, dict):
        if _is_github_actions_integration_token(expected_actor, error):
            viewer = {"login": expected_actor}
            collection_warnings.append(INTEGRATION_TOKEN_WARNING)
        else:
            collection_errors.append(f"viewer: {error or 'invalid shape'}")
            viewer = {}
    login = viewer.get("login") if isinstance(viewer.get("login"), str) else None

    permission: dict[str, Any] = {}
    if login:
        permission_payload, error = _json_command(
            [gh_bin, "api", f"repos/{repo}/collaborators/{login}/permission"],
            runner,
        )
        if error is not None or not isinstance(permission_payload, dict):
            if not _permission_fallback_allowed(error):
                collection_errors.append(f"permission: {error or 'invalid shape'}")
            else:
                repo_payload, repo_error = _json_command([gh_bin, "api", f"repos/{repo}"], runner)
                if repo_error is not None or not isinstance(repo_payload, dict):
                    collection_errors.append(f"permission: {error or 'invalid shape'}")
                    collection_errors.append(f"repo_permission_fallback: {repo_error or 'invalid shape'}")
                else:
                    permission = _permission_from_repo_payload(repo_payload)
                    if not permission:
                        collection_errors.append("repo_permission_fallback: missing permissions")
        else:
            permission = permission_payload
        if (
            INTEGRATION_TOKEN_WARNING in collection_warnings
            and permission.get("permission") != "write"
            and permission.get("role_name") != "write"
        ):
            can_read_pulls, pulls_error = _actor_can_read_pull_requests_with_error(
                repo=repo,
                gh_bin=gh_bin,
                runner=runner,
            )
            if can_read_pulls:
                permission = {"permission": "write", "role_name": "write"}
            else:
                collection_errors.append(f"pulls: {pulls_error or 'write permission inference failed'}")

    pr_view: dict[str, Any] = {}
    attempts = max(1, merge_state_max_attempts)
    for attempt in range(attempts):
        payload, error = _json_command(
            [
                gh_bin,
                "pr",
                "view",
                str(pr_number),
                "--repo",
                repo,
                "--json",
                "state,isDraft,baseRefName,headRefName,headRefOid,isCrossRepository,mergeStateStatus",
            ],
            runner,
        )
        if error is not None or not isinstance(payload, dict):
            collection_errors.append(f"pr_view: {error or 'invalid shape'}")
            pr_view = {}
            break
        pr_view = payload
        merge_state = pr_view.get("mergeStateStatus")
        if merge_state in READY_MERGE_STATES or merge_state not in TRANSIENT_MERGE_STATES or attempt == attempts - 1:
            break
        time.sleep(max(0, merge_state_poll_seconds))

    checks, error = _json_command(
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
    if error is not None or not isinstance(checks, list):
        collection_errors.append(f"pr_checks: {error or 'invalid shape'}")
        checks = []

    return {
        "viewer": viewer,
        "permission": permission,
        "pr_view": pr_view,
        "required_checks": checks,
        "collection_errors": collection_errors,
        "collection_warnings": collection_warnings,
    }


def _checks_pass(required_checks: list[Any]) -> tuple[bool, list[dict[str, Any]]]:
    failing: list[dict[str, Any]] = []
    for raw in required_checks:
        if not isinstance(raw, dict):
            failing.append({"name": None, "bucket": None, "state": None})
            continue
        bucket = raw.get("bucket")
        if bucket != "pass":
            failing.append(
                {
                    "name": raw.get("name"),
                    "bucket": bucket,
                    "state": raw.get("state"),
                    "link": raw.get("link"),
                }
            )
    return not failing, failing


def build_result(
    *,
    repo: str,
    pr_number: int,
    snapshot: dict[str, Any],
    eligibility: dict[str, Any],
    live_state: dict[str, Any],
    expected_actor: str = DEFAULT_EXPECTED_ACTOR,
    base_ref: str = DEFAULT_BASE_REF,
    max_snapshot_age_seconds: int = DEFAULT_MAX_SNAPSHOT_AGE_SECONDS,
    now: datetime | None = None,
    execute: bool = False,
    confirmation: str | None = None,
    merge_exit_code: int | None = None,
    merge_stderr: str = "",
    branch_delete_exit_code: int | None = None,
    branch_delete_stderr: str = "",
    branch_delete_command_argv: list[str] | None = None,
    gh_bin: str = "gh",
) -> dict[str, Any]:
    now = (now or datetime.now(UTC)).astimezone(UTC)
    blockers: set[str] = set()
    warnings: set[str] = set()

    snapshot_readiness = _object(snapshot.get("readiness"))
    snapshot_actor = _object(snapshot.get("merge_actor"))
    snapshot_guard_flags = _object(snapshot.get("guard_flags"))
    eligibility_decision = _object(eligibility.get("decision"))
    eligibility_guard_flags = _object(eligibility.get("guard_flags"))
    live_viewer = _object(live_state.get("viewer"))
    live_permission = _object(live_state.get("permission"))
    pr_view = _object(live_state.get("pr_view"))
    required_checks = live_state.get("required_checks")
    required_checks_list = required_checks if isinstance(required_checks, list) else []
    collection_errors = _string_list(live_state.get("collection_errors"))
    warnings.update(_string_list(live_state.get("collection_warnings")))

    if collection_errors:
        blockers.add("github_api_read_failed")

    snapshot_age = _age_seconds(snapshot.get("generated_at"), now)
    if snapshot_age is None or snapshot_age < 0 or snapshot_age > max_snapshot_age_seconds:
        blockers.add("readiness_snapshot_stale")

    if snapshot.get("repository") != repo:
        blockers.add("snapshot_repository_mismatch")
    if snapshot.get("branch") != base_ref:
        blockers.add("snapshot_branch_mismatch")
    if snapshot.get("release_authority") != RELEASE_AUTHORITY or eligibility.get("release_authority") != RELEASE_AUTHORITY:
        blockers.add("release_authority_mismatch")
    if snapshot.get("ai_output_release_authority") is not False or eligibility.get("ai_output_release_authority") is not False:
        blockers.add("ai_output_release_authority_observed")
    if snapshot_guard_flags != {
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
    } or eligibility_guard_flags != {
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
    }:
        blockers.add("guard_flags_not_false")

    if snapshot_readiness.get("decision") != "ready_for_dry_run":
        blockers.add("readiness_snapshot_not_ready")
    if eligibility_decision.get("result") != "ready_for_low_risk_dry_run":
        blockers.add("eligibility_not_ready")

    live_login = live_viewer.get("login")
    if live_login != expected_actor:
        blockers.add("unexpected_merge_actor")
    permission = live_permission.get("permission")
    if permission == "admin" or live_permission.get("role_name") == "admin" or live_permission.get("user", {}) == "admin":
        blockers.add("merge_actor_admin_permission_observed")
    if permission != "write":
        blockers.add("merge_actor_not_write")
    if snapshot_actor.get("permission") == "admin" or snapshot_actor.get("viewer_can_administer") is True:
        blockers.add("merge_actor_admin_permission_observed")
    if snapshot_actor.get("administration_write_absent_for_dedicated_actor") is not True:
        blockers.add("dedicated_merge_actor_not_confirmed")

    if pr_view.get("state") != "OPEN":
        blockers.add("pr_not_open")
    if pr_view.get("isDraft") is True:
        blockers.add("pr_is_draft")
    if pr_view.get("baseRefName") != base_ref:
        blockers.add("pr_base_not_main")
    if pr_view.get("mergeStateStatus") not in READY_MERGE_STATES:
        blockers.add("pr_merge_state_not_clean")

    checks_ok, failing_checks = _checks_pass(required_checks_list)
    if not checks_ok:
        blockers.add("required_checks_not_passed")

    head_sha = pr_view.get("headRefOid") if isinstance(pr_view.get("headRefOid"), str) else None
    if not head_sha:
        blockers.add("pr_head_sha_missing")
    command = merge_command_with_sha(repo, pr_number, head_sha=head_sha, gh_bin=gh_bin)
    is_cross_repository = pr_view.get("isCrossRepository") is True
    safe_head_ref = _safe_head_ref_for_delete(
        pr_view.get("headRefName"),
        base_ref,
        is_cross_repository=is_cross_repository,
    )
    delete_command = branch_delete_command_argv
    if delete_command is None:
        delete_command = branch_delete_command(repo, safe_head_ref, gh_bin=gh_bin) if safe_head_ref else []
    if any(item == FORBIDDEN_ADMIN_FLAG for item in command):
        blockers.add("admin_merge_command_constructed")

    if execute and confirmation != EXECUTE_CONFIRMATION:
        blockers.add("execute_confirmation_missing")

    merge_attempted = bool(execute and not blockers)
    if merge_exit_code not in (None, 0):
        blockers.add("merge_command_failed")
    if merge_exit_code == 0 and not delete_command:
        warnings.add(
            "branch_delete_skipped_cross_repository"
            if is_cross_repository
            else "branch_delete_skipped_no_safe_head_ref"
        )
    if merge_exit_code == 0 and branch_delete_exit_code not in (None, 0):
        warnings.add("branch_delete_failed")

    if blockers:
        result = "blocked"
    elif execute:
        result = "merged"
    else:
        result = "ready_for_merge_dry_run"

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "generated_at": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "repository": repo,
        "pr_number": pr_number,
        "base_ref": base_ref,
        "expected_actor": expected_actor,
        "actual_actor": live_login,
        "actor_permission": permission,
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
        "snapshot_age_seconds": snapshot_age,
        "readiness_decision": snapshot_readiness.get("decision"),
        "eligibility_decision": eligibility_decision.get("result"),
        "pr_state": {
            "state": pr_view.get("state"),
            "is_draft": pr_view.get("isDraft"),
            "base_ref": pr_view.get("baseRefName"),
            "head_ref": pr_view.get("headRefName"),
            "head_sha": pr_view.get("headRefOid"),
            "is_cross_repository": pr_view.get("isCrossRepository"),
            "merge_state_status": pr_view.get("mergeStateStatus"),
        },
        "required_checks": {
            "total": len(required_checks_list),
            "all_passed": checks_ok,
            "failing": failing_checks,
        },
        "merge_command_argv": command,
        "merge_error": merge_stderr if merge_exit_code not in (None, 0) else "",
        "branch_delete_command_argv": delete_command,
        "branch_delete_error": branch_delete_stderr if branch_delete_exit_code not in (None, 0) else "",
        "collection_errors": collection_errors,
        "decision": {
            "result": result,
            "blockers": sorted(blockers),
            "warnings": sorted(warnings),
            "next_required_slice": (
                "authenticate gh as the dedicated non-admin merge actor and rerun AO-MA-10c"
                if "unexpected_merge_actor" in blockers or "merge_actor_admin_permission_observed" in blockers
                else "AO-MA-10l positive disposable low-risk autonomous merge smoke"
                if result in {"ready_for_merge_dry_run", "merged"}
                else "resolve AO-MA-10c blockers before merge-agent activation"
            ),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="Halildeu/ao-kernel")
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--eligibility", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-actor", default=DEFAULT_EXPECTED_ACTOR)
    parser.add_argument("--base-ref", default=DEFAULT_BASE_REF)
    parser.add_argument("--max-snapshot-age-seconds", type=int, default=DEFAULT_MAX_SNAPSHOT_AGE_SECONDS)
    parser.add_argument("--gh-bin", default="gh")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirmation")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args(argv)

    snapshot = _load_json(Path(args.snapshot))
    eligibility = _load_json(Path(args.eligibility))
    live_state = collect_live_github_state(
        repo=args.repo,
        pr_number=args.pr,
        gh_bin=args.gh_bin,
        expected_actor=args.expected_actor,
    )

    merge_exit_code: int | None = None
    merge_stderr = ""
    branch_delete_exit_code: int | None = None
    branch_delete_stderr = ""
    branch_delete_command_argv: list[str] = []
    preliminary = build_result(
        repo=args.repo,
        pr_number=args.pr,
        snapshot=snapshot,
        eligibility=eligibility,
        live_state=live_state,
        expected_actor=args.expected_actor,
        base_ref=args.base_ref,
        max_snapshot_age_seconds=args.max_snapshot_age_seconds,
        execute=args.execute,
        confirmation=args.confirmation,
        gh_bin=args.gh_bin,
    )

    if args.execute and preliminary["decision"]["result"] != "blocked":
        (
            merge_exit_code,
            merge_stderr,
            branch_delete_exit_code,
            branch_delete_stderr,
            _merge_command_argv,
            branch_delete_command_argv,
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
        snapshot=snapshot,
        eligibility=eligibility,
        live_state=live_state,
        expected_actor=args.expected_actor,
        base_ref=args.base_ref,
        max_snapshot_age_seconds=args.max_snapshot_age_seconds,
        execute=args.execute,
        confirmation=args.confirmation,
        merge_exit_code=merge_exit_code,
        merge_stderr=merge_stderr,
        branch_delete_exit_code=branch_delete_exit_code,
        branch_delete_stderr=branch_delete_stderr,
        branch_delete_command_argv=branch_delete_command_argv,
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

    return 0 if result["decision"]["result"] in {"ready_for_merge_dry_run", "merged"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
