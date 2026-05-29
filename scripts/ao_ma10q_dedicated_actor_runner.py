#!/usr/bin/env python3
"""AO-MA-10q no-secret dedicated actor runner for AO-MA-10l.

This helper removes the last ad-hoc shell-wrapper step from the low-risk
autonomous merge smoke. It never accepts a token value on the command line.
Instead, it creates a temporary ``gh`` wrapper that reads one named environment
variable and passes that token to the GitHub CLI as ``GH_TOKEN``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol


SCHEMA_VERSION = "ao-ma-10q-dedicated-actor-runner-result.v1"
ARTIFACT_KIND = "ao_ma_10q_dedicated_actor_runner_result"
RELEASE_AUTHORITY = "ao-release-gate+github-ruleset"
DEFAULT_REPO = "Halildeu/ao-kernel"
DEFAULT_BASE_REF = "main"
DEFAULT_EXPECTED_ACTOR = "gladyatore-lab"
DEFAULT_TOKEN_ENV = "GLADYATORE_LAB_GH_TOKEN"
DEFAULT_GOVERNANCE_TOKEN_ENV = "AO_GOVERNANCE_GH_TOKEN"
EXECUTE_CONFIRMATION = "AO-MA-10L-EXECUTE"
TOKEN_ENV_RE = re.compile(r"[A-Z_][A-Z0-9_]*")
MIN_SMOKE_SUBPROCESS_GRACE_SECONDS = 60
SMOKE_SUBPROCESS_GRACE_POLLS = 4


class Runner(Protocol):
    def __call__(self, command: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]: ...


def _smoke_process_timeout(*, timeout_seconds: int, poll_seconds: int) -> int:
    """Return the subprocess budget for the delegated AO-MA-10l smoke."""

    if timeout_seconds <= 0:
        return 180
    grace_seconds = max(MIN_SMOKE_SUBPROCESS_GRACE_SECONDS, poll_seconds * SMOKE_SUBPROCESS_GRACE_POLLS)
    return timeout_seconds + grace_seconds


def _run(command: list[str], *, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout)


def _run_smoke_command(
    runner: Runner,
    command: list[str],
    *,
    timeout_seconds: int,
    poll_seconds: int,
) -> subprocess.CompletedProcess[str]:
    return runner(
        command,
        timeout=_smoke_process_timeout(timeout_seconds=timeout_seconds, poll_seconds=poll_seconds),
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _base_result(*, repo: str, base_ref: str, expected_actor: str, token_env: str, execute: bool) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "repository": repo,
        "base_ref": base_ref,
        "expected_actor": expected_actor,
        "token_env": token_env,
        "producer_token_env": token_env,
        "token_value_recorded": False,
        "execute_requested": execute,
        "mutations_performed": False,
        "release_authority": RELEASE_AUTHORITY,
        "ai_output_release_authority": False,
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "wrapper": {
            "created": False,
            "mode": None,
            "path_recorded": False,
        },
        "producer_wrapper": {
            "created": False,
            "mode": None,
            "path_recorded": False,
            "same_as_merge_actor_wrapper": True,
        },
        "smoke_result": None,
        "smoke_command": [],
        "decision": {
            "result": "blocked",
            "blockers": [],
            "warnings": [],
            "next_required_slice": "provide dedicated non-admin actor token env and rerun AO-MA-10q",
        },
    }


def _set_decision(result: dict[str, Any], *, decision: str, blockers: list[str], warnings: list[str] | None = None) -> None:
    if decision == "merged":
        next_required = "record AO-MA-10l merged artifact and keep low-risk autonomous lane active"
    elif "dedicated_actor_token_env_missing" in blockers:
        next_required = "set the dedicated non-admin actor token env and rerun AO-MA-10q"
    else:
        next_required = "resolve AO-MA-10q/AO-MA-10l blockers"
    result["decision"] = {
        "result": decision,
        "blockers": sorted(blockers),
        "warnings": sorted(warnings or []),
        "next_required_slice": next_required,
    }


def _validate_token_env_name(token_env: str) -> None:
    if not TOKEN_ENV_RE.fullmatch(token_env):
        raise ValueError("token env name must match [A-Z_][A-Z0-9_]*")


def _write_gh_wrapper(*, path: Path, token_env: str, base_gh_bin: str) -> None:
    _validate_token_env_name(token_env)
    github_token_var = "GH_" + "TOKEN"
    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env sh",
                "set -eu",
                f'if [ -z "${{{token_env}:-}}" ]; then',
                '  echo "dedicated GitHub token env is missing" >&2',
                "  exit 2",
                "fi",
                f'{github_token_var}="${{{token_env}}}" exec {shlex.quote(base_gh_bin)} "$@"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)


def _load_smoke_result(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("AO-MA-10l output must be a JSON object")
    return data


def _sanitize_smoke_command(command: list[str], *, wrappers: list[Path], smoke_output: Path) -> list[str]:
    wrapper_paths = {str(wrapper) for wrapper in wrappers}
    sanitized: list[str] = []
    for item in command:
        if item in wrapper_paths:
            sanitized.append("<temporary-gh-wrapper>")
        elif item == str(smoke_output):
            sanitized.append("<temporary-smoke-output>")
        else:
            sanitized.append(item)
    return sanitized


def run(
    *,
    repo: str,
    base_ref: str,
    expected_actor: str,
    token_env: str,
    governance_token_env: str,
    base_gh_bin: str,
    output: Path,
    execute: bool,
    confirmation: str | None,
    timeout_seconds: int,
    poll_seconds: int,
    runner: Runner = _run,
) -> dict[str, Any]:
    _validate_token_env_name(token_env)
    _validate_token_env_name(governance_token_env)
    result = _base_result(
        repo=repo,
        base_ref=base_ref,
        expected_actor=expected_actor,
        token_env=token_env,
        execute=execute,
    )

    if not os.environ.get(token_env):
        _set_decision(result, decision="blocked", blockers=["dedicated_actor_token_env_missing"])
        _write_json(output, result)
        return result

    with tempfile.TemporaryDirectory(prefix="ao-ma10q-") as temp:
        temp_dir = Path(temp)
        wrapper = temp_dir / "gh-dedicated"
        governance_wrapper = temp_dir / "gh-governance"
        smoke_output = temp_dir / "ao-ma10l-result.json"
        _write_gh_wrapper(path=wrapper, token_env=token_env, base_gh_bin=base_gh_bin)
        governance_wrapper_created = False
        if os.environ.get(governance_token_env):
            _write_gh_wrapper(path=governance_wrapper, token_env=governance_token_env, base_gh_bin=base_gh_bin)
            governance_wrapper_created = True
        result["wrapper"] = {
            "created": True,
            "mode": "0700",
            "path_recorded": False,
        }
        result["producer_token_env"] = governance_token_env if governance_wrapper_created else token_env
        result["producer_wrapper"] = {
            "created": governance_wrapper_created,
            "mode": "0700" if governance_wrapper_created else None,
            "path_recorded": False,
            "same_as_merge_actor_wrapper": not governance_wrapper_created,
        }

        command = [
            sys.executable,
            "scripts/ao_ma10l_autonomous_smoke.py",
            "--repo",
            repo,
            "--base-ref",
            base_ref,
            "--expected-actor",
            expected_actor,
            "--gh-bin",
            str(wrapper),
            "--output",
            str(smoke_output),
            "--timeout-seconds",
            str(timeout_seconds),
            "--poll-seconds",
            str(poll_seconds),
            "--format",
            "json",
        ]
        if governance_wrapper_created:
            command.extend(["--governance-gh-bin", str(governance_wrapper)])
            command.extend(["--producer-gh-bin", str(governance_wrapper)])
        if execute:
            command.append("--execute")
            if confirmation is not None:
                command.extend(["--confirmation", confirmation])
        wrappers = [wrapper]
        if governance_wrapper_created:
            wrappers.append(governance_wrapper)
        result["smoke_command"] = _sanitize_smoke_command(command, wrappers=wrappers, smoke_output=smoke_output)

        blockers: list[str] = []
        warnings: list[str] = []
        smoke_result: dict[str, Any] | None = None
        try:
            proc = _run_smoke_command(
                runner,
                command,
                timeout_seconds=timeout_seconds,
                poll_seconds=poll_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            blockers.append(f"smoke_command_timeout: {int(exc.timeout)}s")
            _set_decision(result, decision="blocked", blockers=blockers, warnings=warnings)
            _write_json(output, result)
            return result
        if smoke_output.exists():
            try:
                smoke_result = _load_smoke_result(smoke_output)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                blockers.append(f"smoke_result_invalid: {exc}")
        else:
            blockers.append("smoke_result_missing")

        if proc.returncode not in (0, 1):
            blockers.append("smoke_command_failed")
        if smoke_result:
            raw_pr_producer = smoke_result.get("pr_producer")
            pr_producer: dict[str, Any] = raw_pr_producer if isinstance(raw_pr_producer, dict) else {}
            producer_role = pr_producer.get("role")
            producer_same_as_merge_actor = pr_producer.get("same_as_merge_actor")
            producer_release_authority = pr_producer.get("release_authority")
            producer_allowed_operations = pr_producer.get("allowed_operations")
            expected_producer_role = "governance_producer" if governance_wrapper_created else "merge_actor"
            expected_same_as_merge_actor = not governance_wrapper_created
            if producer_role not in {"merge_actor", "governance_producer"}:
                blockers.append(f"producer_role_invalid: {producer_role}")
            if producer_role != expected_producer_role:
                blockers.append("producer_role_execution_context_mismatch")
            if producer_same_as_merge_actor is not expected_same_as_merge_actor:
                blockers.append("producer_same_actor_execution_context_mismatch")
            if producer_role == "merge_actor" and producer_same_as_merge_actor is not True:
                blockers.append("producer_merge_actor_role_mismatch")
            if producer_role == "governance_producer" and producer_same_as_merge_actor is not False:
                blockers.append("producer_governance_role_mismatch")
            if producer_release_authority is not False:
                blockers.append("producer_release_authority_observed")
            if producer_allowed_operations != ["base_ref_read", "branch_create", "file_create", "pr_create"]:
                blockers.append("producer_allowed_operations_mismatch")
            raw_smoke_decision = smoke_result.get("decision")
            smoke_decision: dict[str, Any] = raw_smoke_decision if isinstance(raw_smoke_decision, dict) else {}
            blockers.extend(item for item in smoke_decision.get("blockers", []) if isinstance(item, str))
            warnings.extend(item for item in smoke_decision.get("warnings", []) if isinstance(item, str))
            result["smoke_result"] = smoke_result
            result["mutations_performed"] = bool(smoke_result.get("mutations_performed"))
            raw_decision = smoke_decision.get("result")
            decision = raw_decision if isinstance(raw_decision, str) else "blocked"
        else:
            decision = "blocked"
        if blockers:
            decision = "blocked"
        _set_decision(result, decision=decision, blockers=blockers, warnings=warnings)
        _write_json(output, result)
        return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--base-ref", default=DEFAULT_BASE_REF)
    parser.add_argument("--expected-actor", default=DEFAULT_EXPECTED_ACTOR)
    parser.add_argument("--token-env", default=DEFAULT_TOKEN_ENV)
    parser.add_argument("--governance-token-env", default=DEFAULT_GOVERNANCE_TOKEN_ENV)
    parser.add_argument("--base-gh-bin", default="gh")
    parser.add_argument("--output", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirmation")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--poll-seconds", type=int, default=15)
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args(argv)

    result = run(
        repo=args.repo,
        base_ref=args.base_ref,
        expected_actor=args.expected_actor,
        token_env=args.token_env,
        governance_token_env=args.governance_token_env,
        base_gh_bin=args.base_gh_bin,
        output=Path(args.output),
        execute=args.execute,
        confirmation=args.confirmation,
        timeout_seconds=args.timeout_seconds,
        poll_seconds=args.poll_seconds,
    )
    if args.format == "text":
        print(result["decision"]["result"])
        for blocker in result["decision"]["blockers"]:
            print(f"blocker: {blocker}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["decision"]["result"] in {"ready_for_smoke_dry_run", "merged"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
