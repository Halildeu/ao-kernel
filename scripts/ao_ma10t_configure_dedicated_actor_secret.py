#!/usr/bin/env python3
"""Configure the AO-MA-10 dedicated actor repository secret without recording it.

The full no-human merge smoke needs the ``GLADYATORE_LAB_GH_TOKEN`` repository
secret so the main-only AO-MA-10S workflow can authenticate as the dedicated
non-admin merge actor. This helper keeps the operator handoff bounded:

* the token is read from one named environment variable;
* the token is passed to ``gh secret set`` through stdin, never a CLI argument;
* the output artifact records only metadata and guard flags.
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


SCHEMA_VERSION = "ao-ma-10t-dedicated-actor-secret-bootstrap-result.v1"
ARTIFACT_KIND = "ao_ma_10t_dedicated_actor_secret_bootstrap_result"
RELEASE_AUTHORITY = "ao-release-gate+github-ruleset"
DEFAULT_REPO = "Halildeu/ao-kernel"
DEFAULT_SECRET_NAME = "GLADYATORE_LAB_GH_TOKEN"
DEFAULT_SOURCE_TOKEN_ENV = "GLADYATORE_LAB_GH_TOKEN"
EXECUTE_CONFIRMATION = "AO-MA-10T-CONFIGURE-SECRET"
ENV_RE = re.compile(r"[A-Z_][A-Z0-9_]*")

Runner = Callable[[list[str], Mapping[str, str], str | None], subprocess.CompletedProcess[str]]


def _run(command: list[str], env: Mapping[str, str], stdin: str | None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=120,
        env=dict(env),
        input=stdin,
    )


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_env_name(name: str) -> None:
    if not ENV_RE.fullmatch(name):
        raise ValueError("environment variable name must match [A-Z_][A-Z0-9_]*")


def _base_result(*, repo: str, secret_name: str, source_token_env: str, execute: bool) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "generated_at": _utc_now(),
        "repository": repo,
        "secret_name": secret_name,
        "source_token_env": source_token_env,
        "execute_requested": execute,
        "token_value_recorded": False,
        "secret_value_recorded": False,
        "mutations_performed": False,
        "release_authority": RELEASE_AUTHORITY,
        "ai_output_release_authority": False,
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "commands": [],
        "secret_metadata": None,
        "decision": {
            "result": "blocked",
            "blockers": [],
            "warnings": [],
            "next_required_slice": "provide the dedicated actor token env and rerun AO-MA-10T",
        },
    }


def _set_decision(result: dict[str, Any], *, decision: str, blockers: set[str], warnings: set[str]) -> None:
    if blockers:
        next_required = "resolve AO-MA-10T credential/bootstrap blockers"
    elif decision == "ready_to_configure":
        next_required = "rerun AO-MA-10T with --execute and the confirmation string"
    else:
        next_required = "dispatch AO-MA-10S execute smoke from main"
    result["decision"] = {
        "result": "blocked" if blockers else decision,
        "blockers": sorted(blockers),
        "warnings": sorted(warnings),
        "next_required_slice": next_required,
    }


def _write_json(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run_json(
    command: list[str],
    *,
    env: Mapping[str, str],
    runner: Runner,
    result: dict[str, Any],
    stdin: str | None = None,
) -> tuple[dict[str, Any], str | None]:
    result["commands"].append(list(command))
    proc = runner(command, env, stdin)
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}"
        return {}, detail
    if not proc.stdout.strip():
        return {}, None
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {}, "invalid json response"
    if not isinstance(payload, dict):
        return {}, "json response must be object"
    return payload, None


def run(
    *,
    repo: str,
    secret_name: str,
    source_token_env: str,
    gh_bin: str,
    output: Path,
    execute: bool,
    confirmation: str | None,
    runner: Runner = _run,
) -> dict[str, Any]:
    _validate_env_name(secret_name)
    _validate_env_name(source_token_env)
    result = _base_result(
        repo=repo,
        secret_name=secret_name,
        source_token_env=source_token_env,
        execute=execute,
    )
    blockers: set[str] = set()
    warnings: set[str] = set()

    token = os.environ.get(source_token_env)
    if not token:
        blockers.add("source_token_env_missing")
        _set_decision(result, decision="blocked", blockers=blockers, warnings=warnings)
        _write_json(output, result)
        return result

    if not execute:
        _set_decision(result, decision="ready_to_configure", blockers=blockers, warnings=warnings)
        _write_json(output, result)
        return result

    if confirmation != EXECUTE_CONFIRMATION:
        blockers.add("execute_confirmation_missing")
        _set_decision(result, decision="blocked", blockers=blockers, warnings=warnings)
        _write_json(output, result)
        return result

    env = dict(os.environ)
    set_command = [gh_bin, "secret", "set", secret_name, "--repo", repo]
    _, error = _run_json(set_command, env=env, runner=runner, result=result, stdin=token)
    if error is not None:
        blockers.add("gh_secret_set_failed")
        result.setdefault("collection_errors", []).append(f"secret_set: {error}")
    else:
        result["mutations_performed"] = True

    if not blockers:
        metadata_command = [gh_bin, "api", f"repos/{repo}/actions/secrets/{secret_name}"]
        metadata, error = _run_json(metadata_command, env=env, runner=runner, result=result)
        if error is not None:
            blockers.add("secret_metadata_read_failed")
            result.setdefault("collection_errors", []).append(f"secret_metadata: {error}")
        elif metadata.get("name") != secret_name:
            blockers.add("secret_metadata_name_mismatch")
            result["secret_metadata"] = {"name": metadata.get("name")}
        else:
            result["secret_metadata"] = {
                "name": metadata.get("name"),
                "created_at_present": isinstance(metadata.get("created_at"), str),
                "updated_at_present": isinstance(metadata.get("updated_at"), str),
            }

    _set_decision(result, decision="secret_configured", blockers=blockers, warnings=warnings)
    _write_json(output, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--secret-name", default=DEFAULT_SECRET_NAME)
    parser.add_argument("--source-token-env", default=DEFAULT_SOURCE_TOKEN_ENV)
    parser.add_argument("--gh-bin", default="gh")
    parser.add_argument("--output", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirmation")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args(argv)

    result = run(
        repo=args.repo,
        secret_name=args.secret_name,
        source_token_env=args.source_token_env,
        gh_bin=args.gh_bin,
        output=Path(args.output),
        execute=args.execute,
        confirmation=args.confirmation,
    )
    if args.format == "text":
        print(result["decision"]["result"])
        for blocker in result["decision"]["blockers"]:
            print(f"blocker: {blocker}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["decision"]["result"] in {"ready_to_configure", "secret_configured"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
