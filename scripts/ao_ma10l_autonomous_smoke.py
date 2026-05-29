#!/usr/bin/env python3
"""AO-MA-10l positive low-risk autonomous merge smoke orchestrator.

This orchestrator is deliberately fail-closed. It is not release authority and
does not decide that a PR may merge by itself. It sequences the existing
repo-owned evidence gates:

1. AO-MA-10a0 live GitHub readiness snapshot.
2. AO-MA-10a1 low-risk autonomous merge eligibility.
3. A disposable low-risk PR created by the selected PR producer runtime.
4. Live required-check pass observation.
5. AO-MA-10c merge-agent execution.

By default it performs no GitHub writes. Execute mode requires the explicit
AO-MA-10L-EXECUTE confirmation, and still stops before any write if A0/A1 is
blocked.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


SCHEMA_VERSION = "ao-ma-10l-autonomous-smoke-result.v1"
ARTIFACT_KIND = "ao_ma_10l_autonomous_smoke_result"
RELEASE_AUTHORITY = "ao-release-gate+github-ruleset"
DEFAULT_REPO = "Halildeu/ao-kernel"
DEFAULT_BASE_REF = "main"
DEFAULT_EXPECTED_ACTOR = "gladyatore-lab"
DEFAULT_SMOKE_ROOT = "docs/evidence/ao-ma-10l-autonomous-smoke"
EXECUTE_CONFIRMATION = "AO-MA-10L-EXECUTE"
MERGE_AGENT_CONFIRMATION = "AO-MA-10C-EXECUTE"
TECHNICAL_CHECK = "ao-release-gate-technical"
REVIEW_CHECK = "ao-release-gate-review"

Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=120)


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _run_checked(command: list[str], runner: Runner) -> tuple[str, str | None]:
    proc = runner(command)
    if proc.returncode != 0:
        return "", proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}"
    return proc.stdout.strip(), None


def _run_json(command: list[str], runner: Runner) -> tuple[dict[str, Any] | list[Any], str | None]:
    stdout, error = _run_checked(command, runner)
    if error is not None:
        return {}, error
    if not stdout:
        return {}, "empty response"
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        return {}, "invalid json response"
    if not isinstance(parsed, (dict, list)):
        return {}, "json response must be object or array"
    return parsed, None


def _result_template(
    *,
    repo: str,
    base_ref: str,
    expected_actor: str,
    run_id: str,
    branch: str,
    smoke_path: str,
    execute: bool,
    generated_at: str,
    producer_same_as_merge_actor: bool,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "generated_at": generated_at,
        "repository": repo,
        "base_ref": base_ref,
        "expected_actor": expected_actor,
        "run_id": run_id,
        "branch": branch,
        "smoke_path": smoke_path,
        "pr_producer": {
            "role": "merge_actor" if producer_same_as_merge_actor else "governance_producer",
            "same_as_merge_actor": producer_same_as_merge_actor,
            "release_authority": False,
            "allowed_operations": ["base_ref_read", "branch_create", "file_create", "pr_create"],
        },
        "execute_requested": execute,
        "mutations_performed": False,
        "release_authority": RELEASE_AUTHORITY,
        "ai_output_release_authority": False,
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "readiness_decision": None,
        "eligibility_decision": None,
        "created_pr": None,
        "required_checks": {"observed": False, "all_passed": False, "failing": []},
        "merge_agent_result": None,
        "commands": [],
        "decision": {
            "result": "blocked",
            "blockers": [],
            "warnings": [],
            "next_required_slice": "resolve AO-MA-10l blockers",
        },
    }


def _add_command(result: dict[str, Any], command: list[str]) -> None:
    result["commands"].append(command)


def _set_decision(result: dict[str, Any], blockers: set[str], warnings: set[str], ready_result: str) -> None:
    if blockers:
        decision = "blocked"
        next_required = (
            "authenticate gh as the dedicated non-admin merge actor and rerun AO-MA-10l"
            if {"unexpected_merge_actor", "merge_actor_admin_permission_observed", "dedicated_merge_actor_not_confirmed"}
            & blockers
            else "resolve AO-MA-10l blockers"
        )
    else:
        decision = ready_result
        next_required = "record AO-MA-10l evidence and keep autonomous low-risk lane active"
    result["decision"] = {
        "result": decision,
        "blockers": sorted(blockers),
        "warnings": sorted(warnings),
        "next_required_slice": next_required,
    }


def _collect_readiness(
    *,
    repo: str,
    expected_actor: str,
    gh_bin: str,
    actor_gh_bin: str | None,
    output: Path,
    runner: Runner,
) -> tuple[dict[str, Any], list[str]]:
    command = [
        sys.executable,
        "scripts/ao_ma10_github_readiness_snapshot.py",
        "--repository",
        repo,
        "--dedicated-merge-actor",
        expected_actor,
        "--gh-bin",
        gh_bin,
        "--output",
        str(output),
    ]
    if actor_gh_bin is not None and actor_gh_bin != gh_bin:
        command.extend(["--actor-gh-bin", actor_gh_bin])
    _, error = _run_checked(command, runner)
    if error is not None:
        return {}, [f"readiness_snapshot_failed: {error}"]
    try:
        return _json(output), []
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {}, [f"readiness_snapshot_invalid: {exc}"]


def _collect_eligibility(
    *,
    snapshot: Path,
    changed_file: str,
    output: Path,
    runner: Runner,
) -> tuple[dict[str, Any], list[str]]:
    command = [
        sys.executable,
        "scripts/ao_ma10_autonomous_merge_eligibility.py",
        "--snapshot",
        str(snapshot),
        "--changed-file",
        changed_file,
        "--output",
        str(output),
        "--format",
        "json",
    ]
    proc = runner(command)
    if proc.returncode not in (0, 1):
        return {}, [f"eligibility_failed: {proc.stderr.strip() or proc.stdout.strip() or proc.returncode}"]
    try:
        return _json(output), []
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {}, [f"eligibility_invalid: {exc}"]


def _readiness_blockers(snapshot: dict[str, Any]) -> list[str]:
    return _string_list(_object(snapshot.get("readiness")).get("blockers"))


def _readiness_warnings(snapshot: dict[str, Any]) -> list[str]:
    return _string_list(_object(snapshot.get("readiness")).get("warnings"))


def _eligibility_blockers(eligibility: dict[str, Any]) -> list[str]:
    return _string_list(_object(eligibility.get("decision")).get("blockers"))


def _eligibility_warnings(eligibility: dict[str, Any]) -> list[str]:
    return _string_list(_object(eligibility.get("decision")).get("warnings"))


def _validate_initial_gates(
    *,
    snapshot: dict[str, Any],
    eligibility: dict[str, Any],
    blockers: set[str],
    warnings: set[str],
) -> None:
    blockers.update(_readiness_blockers(snapshot))
    warnings.update(_readiness_warnings(snapshot))
    blockers.update(_eligibility_blockers(eligibility))
    warnings.update(_eligibility_warnings(eligibility))
    if _object(snapshot.get("readiness")).get("decision") != "ready_for_dry_run":
        blockers.add("readiness_snapshot_not_ready")
    if _object(eligibility.get("decision")).get("result") != "ready_for_low_risk_dry_run":
        blockers.add("eligibility_not_ready")
    if snapshot.get("release_authority") != RELEASE_AUTHORITY or eligibility.get("release_authority") != RELEASE_AUTHORITY:
        blockers.add("release_authority_mismatch")
    if snapshot.get("ai_output_release_authority") is not False or eligibility.get("ai_output_release_authority") is not False:
        blockers.add("ai_output_release_authority_observed")


def _smoke_content(*, repo: str, run_id: str, generated_at: str) -> str:
    return "\n".join(
        [
            "# AO-MA-10l autonomous merge smoke",
            "",
            f"- repository: `{repo}`",
            f"- run_id: `{run_id}`",
            f"- generated_at: `{generated_at}`",
            "- purpose: disposable low-risk PR for autonomous merge evidence",
            "- support_widening: false",
            "- production_platform_claim: false",
            "- live_adapter_execution: false",
            "",
        ]
    )


def _parse_pr_number(value: str) -> int | None:
    match = re.search(r"/pull/([0-9]+)(?:\b|$)", value.strip())
    return int(match.group(1)) if match else None


def _create_disposable_pr(
    *,
    repo: str,
    producer_gh_bin: str,
    base_ref: str,
    branch: str,
    smoke_path: str,
    smoke_content: str,
    runner: Runner,
    temp_dir: Path,
    result: dict[str, Any],
) -> tuple[int | None, set[str]]:
    blockers: set[str] = set()

    get_ref = [producer_gh_bin, "api", f"repos/{repo}/git/ref/heads/{base_ref}"]
    _add_command(result, get_ref)
    ref_payload, error = _run_json(get_ref, runner)
    if error is not None or not isinstance(ref_payload, dict):
        return None, {f"github_base_ref_read_failed: {error or 'invalid shape'}"}
    base_sha = _object(ref_payload.get("object")).get("sha")
    if not isinstance(base_sha, str) or not base_sha:
        return None, {"github_base_ref_sha_missing"}

    create_ref = [
        producer_gh_bin,
        "api",
        f"repos/{repo}/git/refs",
        "--method",
        "POST",
        "-f",
        f"ref=refs/heads/{branch}",
        "-f",
        f"sha={base_sha}",
    ]
    _add_command(result, create_ref)
    _, error = _run_json(create_ref, runner)
    if error is not None:
        return None, {f"github_branch_create_failed: {error}"}
    result["mutations_performed"] = True

    encoded = base64.b64encode(smoke_content.encode("utf-8")).decode("ascii")
    payload_path = temp_dir / "contents-payload.json"
    payload_path.write_text(
        json.dumps(
            {
                "message": f"chore(ao-ma-10l): autonomous smoke {branch}",
                "content": encoded,
                "branch": branch,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    put_file = [
        producer_gh_bin,
        "api",
        f"repos/{repo}/contents/{smoke_path}",
        "--method",
        "PUT",
        "--input",
        str(payload_path),
    ]
    _add_command(result, put_file)
    _, error = _run_json(put_file, runner)
    if error is not None:
        return None, {f"github_file_create_failed: {error}"}

    title = "chore(ao-ma-10l): disposable autonomous merge smoke"
    body = (
        "AO-MA-10l disposable low-risk autonomous merge smoke.\n\n"
        "This PR must be merged only by the AO-MA-10c merge-agent after A0/A1 "
        "readiness and required checks pass."
    )
    create_pr = [
        producer_gh_bin,
        "pr",
        "create",
        "--repo",
        repo,
        "--base",
        base_ref,
        "--head",
        branch,
        "--title",
        title,
        "--body",
        body,
    ]
    _add_command(result, create_pr)
    stdout, error = _run_checked(create_pr, runner)
    if error is not None:
        blockers.add(f"github_pr_create_failed: {error}")
        return None, blockers
    pr_number = _parse_pr_number(stdout)
    if pr_number is None:
        blockers.add("github_pr_number_parse_failed")
        return None, blockers
    result["created_pr"] = {"number": pr_number, "url": stdout.strip(), "branch": branch}
    return pr_number, blockers


def _required_checks_passed(raw_checks: list[Any]) -> tuple[bool, list[dict[str, Any]]]:
    failing: list[dict[str, Any]] = []
    names = {item.get("name") for item in raw_checks if isinstance(item, dict)}
    if TECHNICAL_CHECK not in names:
        failing.append({"name": TECHNICAL_CHECK, "bucket": "missing", "state": None})
    if REVIEW_CHECK not in names:
        failing.append({"name": REVIEW_CHECK, "bucket": "missing", "state": None})
    for item in raw_checks:
        if not isinstance(item, dict):
            failing.append({"name": None, "bucket": None, "state": None})
            continue
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


def _wait_for_required_checks(
    *,
    repo: str,
    gh_bin: str,
    pr_number: int,
    runner: Runner,
    result: dict[str, Any],
    timeout_seconds: int,
    poll_seconds: int,
) -> set[str]:
    deadline = time.monotonic() + timeout_seconds
    last_failing: list[dict[str, Any]] = []
    while True:
        command = [
            gh_bin,
            "pr",
            "checks",
            str(pr_number),
            "--repo",
            repo,
            "--required",
            "--json",
            "name,bucket,state,link",
        ]
        _add_command(result, command)
        checks_payload, error = _run_json(command, runner)
        if error is not None or not isinstance(checks_payload, list):
            result["required_checks"] = {"observed": True, "all_passed": False, "failing": []}
            return {f"github_required_checks_read_failed: {error or 'invalid shape'}"}
        passed, failing = _required_checks_passed(checks_payload)
        result["required_checks"] = {"observed": True, "all_passed": passed, "failing": failing}
        if passed:
            return set()
        last_failing = failing
        if timeout_seconds <= 0 or time.monotonic() >= deadline:
            break
        time.sleep(max(1, poll_seconds))
    result["required_checks"] = {"observed": True, "all_passed": False, "failing": last_failing}
    return {"required_checks_not_passed"}


def _run_merge_agent(
    *,
    repo: str,
    gh_bin: str,
    pr_number: int,
    snapshot: Path,
    eligibility: Path,
    output: Path,
    runner: Runner,
    result: dict[str, Any],
) -> tuple[dict[str, Any], set[str]]:
    command = [
        sys.executable,
        "scripts/ao_ma10c_merge_agent.py",
        "--repo",
        repo,
        "--gh-bin",
        gh_bin,
        "--pr",
        str(pr_number),
        "--snapshot",
        str(snapshot),
        "--eligibility",
        str(eligibility),
        "--output",
        str(output),
        "--execute",
        "--confirmation",
        MERGE_AGENT_CONFIRMATION,
        "--format",
        "json",
    ]
    _add_command(result, command)
    proc = runner(command)
    if proc.returncode not in (0, 1):
        return {}, {f"merge_agent_failed: {proc.stderr.strip() or proc.stdout.strip() or proc.returncode}"}
    try:
        merge_result = _json(output)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {}, {f"merge_agent_result_invalid: {exc}"}
    if _object(merge_result.get("decision")).get("result") != "merged":
        blockers = {"merge_agent_not_merged"}
        blockers.update(f"merge_agent:{item}" for item in _string_list(_object(merge_result.get("decision")).get("blockers")))
        return merge_result, blockers
    return merge_result, set()


def run_smoke(
    *,
    repo: str,
    base_ref: str,
    expected_actor: str,
    gh_bin: str,
    governance_gh_bin: str | None,
    producer_gh_bin: str | None,
    smoke_root: str,
    output: Path,
    execute: bool,
    confirmation: str | None,
    timeout_seconds: int,
    poll_seconds: int,
    runner: Runner = _run,
    now: datetime | None = None,
) -> dict[str, Any]:
    generated_at = (now or _utc_now()).astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    run_id = generated_at.replace("-", "").replace(":", "").replace("Z", "Z").replace("T", "-")
    branch = f"codex/ao-ma10l-smoke-{run_id.lower()}"
    smoke_path = f"{smoke_root.rstrip('/')}/ao-ma-10l-smoke-{run_id.lower()}.md"
    effective_producer_gh_bin = producer_gh_bin or gh_bin
    producer_same_as_merge_actor = effective_producer_gh_bin == gh_bin
    result = _result_template(
        repo=repo,
        base_ref=base_ref,
        expected_actor=expected_actor,
        run_id=run_id,
        branch=branch,
        smoke_path=smoke_path,
        execute=execute,
        generated_at=generated_at,
        producer_same_as_merge_actor=producer_same_as_merge_actor,
    )
    blockers: set[str] = set()
    warnings: set[str] = set()

    if execute and confirmation != EXECUTE_CONFIRMATION:
        blockers.add("execute_confirmation_missing")

    with tempfile.TemporaryDirectory(prefix="ao-ma10l-") as temp:
        temp_dir = Path(temp)
        readiness_gh_bin = governance_gh_bin or gh_bin
        initial_snapshot_path = temp_dir / "a0-initial.json"
        initial_eligibility_path = temp_dir / "a1-initial.json"
        snapshot, errors = _collect_readiness(
            repo=repo,
            expected_actor=expected_actor,
            gh_bin=readiness_gh_bin,
            actor_gh_bin=gh_bin,
            output=initial_snapshot_path,
            runner=runner,
        )
        blockers.update(errors)
        eligibility: dict[str, Any] = {}
        if not errors:
            eligibility, errors = _collect_eligibility(
                snapshot=initial_snapshot_path,
                changed_file=smoke_path,
                output=initial_eligibility_path,
                runner=runner,
            )
            blockers.update(errors)
        result["readiness_decision"] = _object(snapshot.get("readiness")).get("decision")
        result["eligibility_decision"] = _object(eligibility.get("decision")).get("result")
        if snapshot and eligibility:
            _validate_initial_gates(snapshot=snapshot, eligibility=eligibility, blockers=blockers, warnings=warnings)

        if blockers:
            _set_decision(result, blockers, warnings, "ready_for_smoke_dry_run")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return result

        if not execute:
            _set_decision(result, blockers, warnings, "ready_for_smoke_dry_run")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return result

        pr_number, create_blockers = _create_disposable_pr(
            repo=repo,
            producer_gh_bin=effective_producer_gh_bin,
            base_ref=base_ref,
            branch=branch,
            smoke_path=smoke_path,
            smoke_content=_smoke_content(repo=repo, run_id=run_id, generated_at=generated_at),
            runner=runner,
            temp_dir=temp_dir,
            result=result,
        )
        blockers.update(create_blockers)
        if pr_number is not None and not blockers:
            blockers.update(
                _wait_for_required_checks(
                    repo=repo,
                    gh_bin=gh_bin,
                    pr_number=pr_number,
                    runner=runner,
                    result=result,
                    timeout_seconds=timeout_seconds,
                    poll_seconds=poll_seconds,
                )
            )

        if pr_number is not None and not blockers:
            final_snapshot_path = temp_dir / "a0-final.json"
            final_eligibility_path = temp_dir / "a1-final.json"
            final_snapshot, errors = _collect_readiness(
                repo=repo,
                expected_actor=expected_actor,
                gh_bin=readiness_gh_bin,
                actor_gh_bin=gh_bin,
                output=final_snapshot_path,
                runner=runner,
            )
            blockers.update(errors)
            final_eligibility: dict[str, Any] = {}
            if not errors:
                final_eligibility, errors = _collect_eligibility(
                    snapshot=final_snapshot_path,
                    changed_file=smoke_path,
                    output=final_eligibility_path,
                    runner=runner,
                )
                blockers.update(errors)
            result["readiness_decision"] = _object(final_snapshot.get("readiness")).get("decision")
            result["eligibility_decision"] = _object(final_eligibility.get("decision")).get("result")
            if final_snapshot and final_eligibility:
                _validate_initial_gates(
                    snapshot=final_snapshot,
                    eligibility=final_eligibility,
                    blockers=blockers,
                    warnings=warnings,
                )

            if not blockers:
                merge_output = temp_dir / "merge-agent-result.json"
                merge_result, merge_blockers = _run_merge_agent(
                    repo=repo,
                    gh_bin=gh_bin,
                    pr_number=pr_number,
                    snapshot=final_snapshot_path,
                    eligibility=final_eligibility_path,
                    output=merge_output,
                    runner=runner,
                    result=result,
                )
                result["merge_agent_result"] = merge_result or None
                blockers.update(merge_blockers)

        ready = "merged" if not blockers else "blocked"
        _set_decision(result, blockers, warnings, ready)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--base-ref", default=DEFAULT_BASE_REF)
    parser.add_argument("--expected-actor", default=DEFAULT_EXPECTED_ACTOR)
    parser.add_argument(
        "--gh-bin",
        default="gh",
        help="GitHub CLI binary or wrapper to use for actor-owned live GitHub writes and merge checks.",
    )
    parser.add_argument(
        "--governance-gh-bin",
        help="Optional GitHub CLI binary or wrapper for read-only governance API checks.",
    )
    parser.add_argument(
        "--producer-gh-bin",
        help=(
            "Optional GitHub CLI binary or wrapper for disposable branch/file/PR creation. "
            "Defaults to --gh-bin so existing dedicated-actor-only runs remain unchanged."
        ),
    )
    parser.add_argument("--smoke-root", default=DEFAULT_SMOKE_ROOT)
    parser.add_argument("--output", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirmation")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--poll-seconds", type=int, default=15)
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args(argv)

    result = run_smoke(
        repo=args.repo,
        base_ref=args.base_ref,
        expected_actor=args.expected_actor,
        gh_bin=args.gh_bin,
        governance_gh_bin=args.governance_gh_bin,
        producer_gh_bin=args.producer_gh_bin,
        smoke_root=args.smoke_root,
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
