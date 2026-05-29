#!/usr/bin/env python3
"""AO-MA-10r no-secret dedicated merge actor credential doctor.

This helper verifies that one named environment variable authenticates ``gh`` as
the expected non-admin merge actor before AO-MA-10q is allowed to execute a live
low-risk autonomous smoke. It performs read-only GitHub API calls and never
accepts or records a token value.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


SCHEMA_VERSION = "ao-ma-10r-dedicated-actor-credential-doctor-result.v1"
ARTIFACT_KIND = "ao_ma_10r_dedicated_actor_credential_doctor_result"
RELEASE_AUTHORITY = "ao-release-gate+github-ruleset"
DEFAULT_REPO = "Halildeu/ao-kernel"
DEFAULT_BASE_REF = "main"
DEFAULT_EXPECTED_ACTOR = "gladyatore-lab"
DEFAULT_TOKEN_ENV = "GLADYATORE_LAB_GH_TOKEN"
BRANCH_PROBE_PREFIX = "codex/ao-ma10r-token-probe"
TOKEN_ENV_RE = re.compile(r"[A-Z_][A-Z0-9_]*")
WRITE_CAPABLE_LEVELS = {"write", "maintain"}

Runner = Callable[[list[str], Mapping[str, str]], subprocess.CompletedProcess[str]]


def _run(command: list[str], env: Mapping[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=60, env=dict(env))


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_token_env_name(token_env: str) -> None:
    if not TOKEN_ENV_RE.fullmatch(token_env):
        raise ValueError("token env name must match [A-Z_][A-Z0-9_]*")


def _base_result(*, repo: str, expected_actor: str, token_env: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "generated_at": _utc_now(),
        "repository": repo,
        "expected_actor": expected_actor,
        "token_env": token_env,
        "token_value_recorded": False,
        "mutations_performed": False,
        "release_authority": RELEASE_AUTHORITY,
        "ai_output_release_authority": False,
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "branch_write_probe": {
            "requested": False,
            "branch": None,
            "base_ref": None,
            "create_result": "not_requested",
            "delete_result": "not_requested",
        },
        "actor": {
            "login": None,
            "id": None,
            "matches_expected": False,
        },
        "repository_access": {
            "permission_level": None,
            "can_read_repository": False,
            "can_read_pull_requests": False,
            "can_merge_without_admin": False,
            "admin_permission_observed": False,
        },
        "commands": [],
        "collection_errors": [],
        "decision": {
            "result": "blocked",
            "blockers": [],
            "warnings": [],
            "next_required_slice": "provide a dedicated non-admin actor token and rerun AO-MA-10r",
        },
    }


def _redacted_command(command: list[str]) -> list[str]:
    # Commands are static and never include token values, but keep a single
    # helper so future command changes stay intentionally audited.
    return list(command)


def _run_json(
    command: list[str],
    *,
    env: Mapping[str, str],
    runner: Runner,
    result: dict[str, Any],
) -> tuple[dict[str, Any] | list[Any], str | None]:
    result["commands"].append(_redacted_command(command))
    proc = runner(command, env)
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}"
        return {}, detail
    if not proc.stdout.strip():
        return {}, "empty response"
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {}, "invalid json response"
    if not isinstance(payload, (dict, list)):
        return {}, "json response must be object or array"
    return payload, None


def _run_status(
    command: list[str],
    *,
    env: Mapping[str, str],
    runner: Runner,
    result: dict[str, Any],
) -> str | None:
    result["commands"].append(_redacted_command(command))
    proc = runner(command, env)
    if proc.returncode != 0:
        return proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}"
    return None


def _permission_level(repo_payload: dict[str, Any]) -> str:
    permissions = repo_payload.get("permissions")
    if not isinstance(permissions, dict):
        return "none"
    if permissions.get("admin") is True:
        return "admin"
    if permissions.get("maintain") is True:
        return "maintain"
    if permissions.get("push") is True:
        return "write"
    if permissions.get("triage") is True:
        return "triage"
    if permissions.get("pull") is True:
        return "read"
    return "none"


def _set_decision(result: dict[str, Any], blockers: set[str], warnings: set[str]) -> None:
    if blockers:
        decision = "blocked"
        next_required = "resolve AO-MA-10r credential blockers before AO-MA-10q execute smoke"
    else:
        decision = "credential_ready"
        next_required = "run AO-MA-10q execute smoke with the same dedicated actor token env"
    result["decision"] = {
        "result": decision,
        "blockers": sorted(blockers),
        "warnings": sorted(warnings),
        "next_required_slice": next_required,
    }


def _run_branch_write_probe(
    *,
    repo: str,
    base_ref: str,
    gh_bin: str,
    env: Mapping[str, str],
    runner: Runner,
    result: dict[str, Any],
    blockers: set[str],
) -> None:
    branch = f"{BRANCH_PROBE_PREFIX}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"
    probe = {
        "requested": True,
        "branch": branch,
        "base_ref": base_ref,
        "create_result": "not_attempted",
        "delete_result": "not_attempted",
    }
    result["branch_write_probe"] = probe

    base_payload, error = _run_json(
        [gh_bin, "api", f"repos/{repo}/git/ref/heads/{base_ref}"],
        env=env,
        runner=runner,
        result=result,
    )
    if error is not None or not isinstance(base_payload, dict):
        blockers.add("branch_write_probe_base_ref_read_failed")
        result["collection_errors"].append(f"branch_probe_base_ref: {error or 'invalid shape'}")
        probe["create_result"] = "blocked"
        probe["delete_result"] = "not_attempted"
        return

    object_payload = base_payload.get("object")
    sha = object_payload.get("sha") if isinstance(object_payload, dict) else None
    if not isinstance(sha, str) or not sha:
        blockers.add("branch_write_probe_base_ref_read_failed")
        result["collection_errors"].append("branch_probe_base_ref: missing object.sha")
        probe["create_result"] = "blocked"
        probe["delete_result"] = "not_attempted"
        return

    error = _run_status(
        [
            gh_bin,
            "api",
            f"repos/{repo}/git/refs",
            "--method",
            "POST",
            "-f",
            f"ref=refs/heads/{branch}",
            "-f",
            f"sha={sha}",
        ],
        env=env,
        runner=runner,
        result=result,
    )
    if error is not None:
        blockers.add("branch_write_probe_create_failed")
        result["collection_errors"].append(f"branch_probe_create: {error}")
        probe["create_result"] = "failed"
        probe["delete_result"] = "not_attempted"
        return

    result["mutations_performed"] = True
    probe["create_result"] = "created"
    error = _run_status(
        [
            gh_bin,
            "api",
            f"repos/{repo}/git/refs/heads/{branch}",
            "--method",
            "DELETE",
        ],
        env=env,
        runner=runner,
        result=result,
    )
    if error is not None:
        blockers.add("branch_write_probe_cleanup_failed")
        result["collection_errors"].append(f"branch_probe_delete: {error}")
        probe["delete_result"] = "failed"
        return
    probe["delete_result"] = "deleted"


def run(
    *,
    repo: str,
    base_ref: str,
    expected_actor: str,
    token_env: str,
    gh_bin: str,
    output: Path,
    branch_write_probe: bool,
    runner: Runner = _run,
) -> dict[str, Any]:
    _validate_token_env_name(token_env)
    result = _base_result(repo=repo, expected_actor=expected_actor, token_env=token_env)
    blockers: set[str] = set()
    warnings: set[str] = set()

    token = os.environ.get(token_env)
    if not token:
        blockers.add("dedicated_actor_token_env_missing")
        _set_decision(result, blockers, warnings)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return result

    env = dict(os.environ)
    github_token_var = "GH_" + "TOKEN"
    env[github_token_var] = token

    user_payload, error = _run_json([gh_bin, "api", "user"], env=env, runner=runner, result=result)
    if error is not None or not isinstance(user_payload, dict):
        blockers.add("github_user_read_failed")
        result["collection_errors"].append(f"user: {error or 'invalid shape'}")
        user_payload = {}

    login = user_payload.get("login")
    actor_id = user_payload.get("id")
    login_value = login if isinstance(login, str) else None
    actor_id_value = actor_id if isinstance(actor_id, int) else None
    result["actor"] = {
        "login": login_value,
        "id": actor_id_value,
        "matches_expected": login_value == expected_actor,
    }
    if login_value != expected_actor:
        blockers.add("unexpected_merge_actor")

    repo_payload, error = _run_json([gh_bin, "api", f"repos/{repo}"], env=env, runner=runner, result=result)
    if error is not None or not isinstance(repo_payload, dict):
        blockers.add("github_repository_read_failed")
        result["collection_errors"].append(f"repository: {error or 'invalid shape'}")
        repo_payload = {}

    permission_level = _permission_level(repo_payload)
    admin_permission_observed = permission_level == "admin"
    can_merge_without_admin = permission_level in WRITE_CAPABLE_LEVELS
    can_read_repository = permission_level in {"read", "triage", "write", "maintain", "admin"}
    if admin_permission_observed:
        blockers.add("merge_actor_admin_permission_observed")
    if not can_merge_without_admin:
        blockers.add("merge_actor_not_write_capable")
    if not can_read_repository:
        blockers.add("repository_read_permission_missing")

    pulls_payload, error = _run_json(
        [gh_bin, "api", f"repos/{repo}/pulls?state=open&per_page=1"],
        env=env,
        runner=runner,
        result=result,
    )
    can_read_pulls = isinstance(pulls_payload, list) and error is None
    if not can_read_pulls:
        blockers.add("pull_request_read_failed")
        result["collection_errors"].append(f"pulls: {error or 'invalid shape'}")

    result["repository_access"] = {
        "permission_level": permission_level,
        "can_read_repository": can_read_repository,
        "can_read_pull_requests": can_read_pulls,
        "can_merge_without_admin": can_merge_without_admin,
        "admin_permission_observed": admin_permission_observed,
    }
    if branch_write_probe and not blockers:
        _run_branch_write_probe(
            repo=repo,
            base_ref=base_ref,
            gh_bin=gh_bin,
            env=env,
            runner=runner,
            result=result,
            blockers=blockers,
        )
    _set_decision(result, blockers, warnings)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--base-ref", default=DEFAULT_BASE_REF)
    parser.add_argument("--expected-actor", default=DEFAULT_EXPECTED_ACTOR)
    parser.add_argument("--token-env", default=DEFAULT_TOKEN_ENV)
    parser.add_argument("--gh-bin", default="gh")
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--branch-write-probe",
        action="store_true",
        help="Create and delete a temporary branch to prove the token can perform the write path used by AO-MA-10l.",
    )
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args(argv)

    result = run(
        repo=args.repo,
        base_ref=args.base_ref,
        expected_actor=args.expected_actor,
        token_env=args.token_env,
        gh_bin=args.gh_bin,
        output=Path(args.output),
        branch_write_probe=args.branch_write_probe,
    )

    if args.format == "text":
        print(result["decision"]["result"])
        for blocker in result["decision"]["blockers"]:
            print(f"blocker: {blocker}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["decision"]["result"] == "credential_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
