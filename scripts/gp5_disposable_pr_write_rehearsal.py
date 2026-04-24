#!/usr/bin/env python3
"""Run the GP-5.6a disposable PR write rehearsal gate.

The gate deliberately does not promote production remote PR support. It requires
a passing GP-5.5b controlled local patch/test rehearsal report, then optionally
exercises a bounded sandbox PR create -> verify -> close -> branch-delete chain.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Sequence

from jsonschema import Draft202012Validator

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ao_kernel.config import load_default  # noqa: E402
from ao_kernel.real_adapter_smoke import (  # noqa: E402
    CommandResult,
    GhCliPrSmokeReport,
    run_gh_cli_pr_smoke,
)

JsonDict = dict[str, Any]
Runner = Callable[[Sequence[str], Path | None, float | None], CommandResult]
SmokeRunner = Callable[..., GhCliPrSmokeReport]

_GP55B_SCHEMA = "gp5-controlled-patch-test-rehearsal-report.schema.v1.json"
_GP56A_SCHEMA = "gp5-disposable-pr-write-rehearsal-report.schema.v1.json"
_PASS_DECISION = "pass_disposable_pr_write_rehearsal_no_support_widening"
_BLOCKED_DECISION = "blocked_disposable_pr_write_rehearsal_no_support_widening"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the GP-5.6a disposable PR write rehearsal"
    )
    parser.add_argument(
        "--local-patch-report",
        type=Path,
        required=True,
        help="Path to a passing GP-5.5b controlled patch/test rehearsal report",
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="Disposable owner/name sandbox repo for the remote PR rehearsal",
    )
    parser.add_argument(
        "--base",
        default="main",
        help="Base branch in the disposable sandbox repo",
    )
    parser.add_argument(
        "--head",
        help="Ephemeral head branch. Defaults to smoke/gp56a-<timestamp>.",
    )
    parser.add_argument(
        "--allow-live-write",
        action="store_true",
        help="Required guard flag before any remote branch or PR write",
    )
    parser.add_argument(
        "--require-disposable-keyword",
        default="sandbox",
        help="Required keyword in the target repo name (default: sandbox)",
    )
    parser.add_argument(
        "--output",
        choices=("json", "text"),
        default="text",
        help="Output format",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        help="Optional path to persist the JSON report",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=30.0,
        help="Per-command timeout for gh CLI/API calls",
    )
    args = parser.parse_args(argv)

    report = run_disposable_pr_write_rehearsal(
        repo_root=_REPO_ROOT,
        local_patch_report=args.local_patch_report,
        repo=args.repo,
        base_ref=args.base,
        head_ref=args.head or _default_head_ref(),
        allow_live_write=args.allow_live_write,
        require_disposable_keyword=args.require_disposable_keyword,
        timeout_seconds=args.timeout_seconds,
    )
    validate_report(report)

    if args.report_path is not None:
        args.report_path.parent.mkdir(parents=True, exist_ok=True)
        args.report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    if args.output == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"overall_status: {report['overall_status']}")
        print(f"decision: {report['decision']}")
        print(f"repo: {report['target_repo']['repo']}")
        print(f"head_ref: {report['target_repo']['head_ref']}")
        print(f"remote_pr: {report['remote_pr'].get('url', '<not-run>')}")
        print(f"cleanup_complete: {report['cleanup']['cleanup_complete']}")
        if report["overall_status"] == "blocked":
            print(f"blocked_reason: {report['blocked_reason']}")
    return 0 if report["overall_status"] == "pass" else 1


def run_disposable_pr_write_rehearsal(
    *,
    repo_root: Path,
    local_patch_report: Path,
    repo: str,
    base_ref: str,
    head_ref: str,
    allow_live_write: bool,
    require_disposable_keyword: str,
    timeout_seconds: float,
    runner: Runner | None = None,
    smoke_runner: SmokeRunner = run_gh_cli_pr_smoke,
    gh_binary: str | None = None,
) -> JsonDict:
    runner = runner or _default_runner
    gh_binary = gh_binary or shutil.which("gh") or "gh"
    repo_root = repo_root.resolve()
    local_precondition = _validate_local_patch_precondition(local_patch_report)
    disposable_guard_ok = _repo_matches_disposable_keyword(
        repo,
        require_disposable_keyword,
    )

    report = _base_report(
        local_patch_precondition=local_precondition,
        repo=repo,
        base_ref=base_ref,
        head_ref=head_ref,
        require_disposable_keyword=require_disposable_keyword,
        allow_live_write=allow_live_write,
        disposable_guard_ok=disposable_guard_ok,
    )

    blocked_reason = _preflight_blocked_reason(
        local_precondition=local_precondition,
        allow_live_write=allow_live_write,
        disposable_guard_ok=disposable_guard_ok,
        head_ref=head_ref,
        base_ref=base_ref,
    )
    if blocked_reason is not None:
        return _blocked(report, blocked_reason)

    branch_created = False
    try:
        branch_result = _create_remote_branch_with_seed_commit(
            gh_binary=gh_binary,
            repo=repo,
            base_ref=base_ref,
            head_ref=head_ref,
            runner=runner,
            timeout_seconds=timeout_seconds,
        )
        report["remote_branch"].update(branch_result)
        branch_created = branch_result["create_status"] == "pass"

        if (
            branch_result["create_status"] == "pass"
            and branch_result["seed_commit_status"] == "pass"
        ):
            smoke_report = smoke_runner(
                timeout_seconds=timeout_seconds,
                cwd=repo_root,
                repo=repo,
                base_ref=base_ref,
                head_ref=head_ref,
                mode="live_write",
                allow_live_write=True,
                keep_live_write_pr_open=False,
                require_disposable_repo_keyword=require_disposable_keyword or None,
                probe_title="ao-kernel GP-5.6a disposable PR write rehearsal",
                probe_body=(
                    "GP-5.6a disposable PR write rehearsal. "
                    "This PR must be closed during the same run."
                ),
            )
            report["gh_cli_pr_smoke"] = _smoke_payload(smoke_report)
            _apply_smoke_to_remote_pr(report, smoke_report)

            pr_url = report["remote_pr"].get("url")
            if smoke_report.overall_status == "pass" and isinstance(pr_url, str):
                closed_payload = _verify_pr_closed(
                    gh_binary=gh_binary,
                    repo=repo,
                    pr_url=pr_url,
                    runner=runner,
                    timeout_seconds=timeout_seconds,
                )
                report["remote_pr"].update(closed_payload)
    finally:
        if branch_created:
            delete_payload = _delete_remote_branch(
                gh_binary=gh_binary,
                repo=repo,
                head_ref=head_ref,
                runner=runner,
                timeout_seconds=timeout_seconds,
            )
            report["remote_branch"].update(delete_payload)
            report["cleanup"]["remote_branch_deleted"] = bool(
                delete_payload.get("delete_verified")
            )

    return _finalize_report(report)


def validate_report(report: JsonDict) -> None:
    schema = load_default("schemas", _GP56A_SCHEMA)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(report),
        key=lambda error: list(error.path),
    )
    if errors:
        joined = "; ".join(error.message for error in errors)
        raise ValueError(f"GP-5.6a report schema validation failed: {joined}")


def _base_report(
    *,
    local_patch_precondition: JsonDict,
    repo: str,
    base_ref: str,
    head_ref: str,
    require_disposable_keyword: str,
    allow_live_write: bool,
    disposable_guard_ok: bool,
) -> JsonDict:
    return {
        "schema_version": "1",
        "artifact_kind": "gp5_disposable_pr_write_rehearsal_report",
        "program_id": "GP-5.6a",
        "overall_status": "blocked",
        "decision": _BLOCKED_DECISION,
        "support_widening": False,
        "production_remote_pr_support": False,
        "arbitrary_repo_support": False,
        "local_patch_precondition": local_patch_precondition,
        "target_repo": {
            "repo": repo,
            "base_ref": base_ref,
            "head_ref": head_ref,
            "disposable_keyword": require_disposable_keyword,
            "disposable_guard_status": "pass" if disposable_guard_ok else "fail",
            "live_write_opt_in": allow_live_write,
            "production_repo_allowed": False,
        },
        "remote_branch": {
            "create_status": "not_run",
            "seed_commit_status": "not_run",
            "delete_attempted": False,
            "delete_status": "not_run",
            "delete_verified": False,
            "evidence_file_path": "",
        },
        "remote_pr": {
            "create_status": "not_run",
            "verify_open_status": "not_run",
            "rollback_close_status": "not_run",
            "verify_closed_status": "not_run",
            "final_state": "not_run",
        },
        "gh_cli_pr_smoke": {
            "overall_status": "not_run",
            "findings": [],
            "checks": [],
        },
        "cleanup": {
            "remote_pr_closed": False,
            "remote_branch_deleted": False,
            "cleanup_complete": False,
            "side_effects_remaining": [],
        },
        "promotion_decision": {
            "support_widening_allowed": False,
            "decision": "no_support_widening",
            "next_gate": "GP-5.7 or a dedicated support-promotion decision",
            "reason": (
                "GP-5.6a proves only a disposable sandbox rehearsal. It does "
                "not certify production remote PR support."
            ),
        },
    }


def _blocked(report: JsonDict, reason: str) -> JsonDict:
    report["overall_status"] = "blocked"
    report["decision"] = _BLOCKED_DECISION
    report["blocked_reason"] = reason
    _refresh_cleanup(report)
    return report


def _finalize_report(report: JsonDict) -> JsonDict:
    _refresh_cleanup(report)
    if (
        report["local_patch_precondition"]["status"] == "pass"
        and report["target_repo"]["disposable_guard_status"] == "pass"
        and report["remote_branch"]["create_status"] == "pass"
        and report["remote_branch"]["seed_commit_status"] == "pass"
        and report["remote_branch"]["delete_verified"] is True
        and report["remote_pr"]["create_status"] == "pass"
        and report["remote_pr"]["verify_open_status"] == "pass"
        and report["remote_pr"]["rollback_close_status"] == "pass"
        and report["remote_pr"]["verify_closed_status"] == "pass"
        and report["remote_pr"]["final_state"] == "CLOSED"
        and report["gh_cli_pr_smoke"]["overall_status"] == "pass"
        and report["cleanup"]["cleanup_complete"] is True
    ):
        report["overall_status"] = "pass"
        report["decision"] = _PASS_DECISION
        report.pop("blocked_reason", None)
        return report

    report["overall_status"] = "blocked"
    report["decision"] = _BLOCKED_DECISION
    report["blocked_reason"] = _first_blocked_reason(report)
    return report


def _refresh_cleanup(report: JsonDict) -> None:
    pr_closed = report["remote_pr"]["final_state"] == "CLOSED"
    branch_deleted = report["remote_branch"]["delete_verified"] is True
    remaining: list[str] = []
    if report["remote_pr"]["create_status"] == "pass" and not pr_closed:
        remaining.append("remote_pr_open_or_unverified")
    if report["remote_branch"]["create_status"] == "pass" and not branch_deleted:
        remaining.append("remote_branch_exists_or_unverified")
    report["cleanup"] = {
        "remote_pr_closed": pr_closed,
        "remote_branch_deleted": branch_deleted,
        "cleanup_complete": not remaining,
        "side_effects_remaining": remaining,
    }


def _first_blocked_reason(report: JsonDict) -> str:
    if report["local_patch_precondition"]["status"] != "pass":
        return "local GP-5.5b precondition did not pass"
    if report["target_repo"]["disposable_guard_status"] != "pass":
        return "target repo did not satisfy disposable guard"
    if report["remote_branch"]["create_status"] != "pass":
        return "remote branch creation failed"
    if report["remote_branch"]["seed_commit_status"] != "pass":
        return "remote branch seed commit failed"
    if report["gh_cli_pr_smoke"]["overall_status"] != "pass":
        return "gh-cli-pr live-write smoke did not pass"
    if report["remote_pr"]["verify_closed_status"] != "pass":
        return "remote PR closed-state verification failed"
    if report["remote_branch"]["delete_verified"] is not True:
        return "remote branch delete verification failed"
    return "GP-5.6a rehearsal did not meet every pass criterion"


def _preflight_blocked_reason(
    *,
    local_precondition: JsonDict,
    allow_live_write: bool,
    disposable_guard_ok: bool,
    head_ref: str,
    base_ref: str,
) -> str | None:
    if local_precondition["status"] != "pass":
        return "passing GP-5.5b controlled local patch/test report is required"
    if not allow_live_write:
        return "explicit --allow-live-write is required before remote writes"
    if not disposable_guard_ok:
        return "target repo must satisfy disposable sandbox keyword guard"
    if not head_ref.startswith("smoke/gp56a-"):
        return "head ref must use the smoke/gp56a- prefix"
    if head_ref == base_ref:
        return "head ref and base ref must differ"
    return None


def _validate_local_patch_precondition(report_path: Path) -> JsonDict:
    resolved = report_path.expanduser().resolve()
    findings: list[str] = []
    report: JsonDict = {}
    sha256 = "0" * 64
    if not resolved.is_file():
        findings.append("local_patch_report_missing")
    else:
        raw = resolved.read_bytes()
        sha256 = hashlib.sha256(raw).hexdigest()
        try:
            report = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            findings.append("local_patch_report_not_json")

    if report:
        schema_errors = _schema_errors(_GP55B_SCHEMA, report)
        if schema_errors:
            findings.append("local_patch_report_schema_invalid")
        if report.get("overall_status") != "pass":
            findings.append("local_patch_report_not_pass")
        if report.get("decision") != (
            "pass_controlled_local_patch_test_rehearsal_no_support_widening"
        ):
            findings.append("local_patch_report_decision_not_accepted")
        if report.get("support_widening") is not False:
            findings.append("local_patch_report_support_widening")
        if report.get("remote_side_effects_allowed") is not False:
            findings.append("local_patch_report_remote_side_effects")
        if report.get("rollback_plan", {}).get("rollback_status") != "pass":
            findings.append("local_patch_report_rollback_not_pass")
        cleanup = report.get("cleanup", {})
        if not (
            cleanup.get("worktree_removed") is True
            and cleanup.get("temp_root_removed") is True
        ):
            findings.append("local_patch_report_cleanup_not_pass")

    return {
        "report_path": str(resolved),
        "report_sha256": sha256,
        "status": "pass" if not findings else "fail",
        "overall_status": str(report.get("overall_status", "")),
        "decision": str(report.get("decision", "")),
        "support_widening": bool(report.get("support_widening", False)),
        "remote_side_effects_allowed": bool(
            report.get("remote_side_effects_allowed", True)
        ),
        "rollback_status": str(report.get("rollback_plan", {}).get("rollback_status", "")),
        "cleanup_status": _cleanup_status(report),
        "findings": findings,
    }


def _schema_errors(schema_name: str, payload: JsonDict) -> list[str]:
    schema = load_default("schemas", schema_name)
    return sorted(
        error.message for error in Draft202012Validator(schema).iter_errors(payload)
    )


def _cleanup_status(report: JsonDict) -> str:
    cleanup = report.get("cleanup", {})
    if cleanup.get("worktree_removed") is True and cleanup.get("temp_root_removed") is True:
        return "pass"
    if cleanup:
        return "fail"
    return ""


def _repo_matches_disposable_keyword(repo: str, keyword: str) -> bool:
    required = keyword.strip().lower()
    return not required or required in repo.lower()


def _create_remote_branch_with_seed_commit(
    *,
    gh_binary: str,
    repo: str,
    base_ref: str,
    head_ref: str,
    runner: Runner,
    timeout_seconds: float,
) -> JsonDict:
    evidence_file = f"gp5-rehearsals/{head_ref.replace('/', '-')}.txt"
    base_result = _run_gh(
        runner,
        (gh_binary, "api", f"repos/{repo}/git/ref/heads/{base_ref}"),
        timeout_seconds,
    )
    if base_result.returncode != 0:
        return {
            "create_status": "fail",
            "seed_commit_status": "not_run",
            "delete_attempted": False,
            "delete_status": "not_run",
            "delete_verified": False,
            "evidence_file_path": evidence_file,
            "finding_code": "gp56a_base_ref_unavailable",
        }

    try:
        base_sha = json.loads(base_result.stdout)["object"]["sha"]
    except (KeyError, TypeError, json.JSONDecodeError):
        return {
            "create_status": "fail",
            "seed_commit_status": "not_run",
            "delete_attempted": False,
            "delete_status": "not_run",
            "delete_verified": False,
            "evidence_file_path": evidence_file,
            "finding_code": "gp56a_base_ref_json_invalid",
        }

    create_result = _run_gh(
        runner,
        (
            gh_binary,
            "api",
            "-X",
            "POST",
            f"repos/{repo}/git/refs",
            "-f",
            f"ref=refs/heads/{head_ref}",
            "-f",
            f"sha={base_sha}",
        ),
        timeout_seconds,
    )
    if create_result.returncode != 0:
        return {
            "create_status": "fail",
            "seed_commit_status": "not_run",
            "delete_attempted": False,
            "delete_status": "not_run",
            "delete_verified": False,
            "evidence_file_path": evidence_file,
            "finding_code": "gp56a_remote_branch_create_failed",
        }

    content = (
        "ao-kernel GP-5.6a disposable PR write rehearsal\n"
        f"repo={repo}\nbase={base_ref}\nhead={head_ref}\n"
    )
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    seed_result = _run_gh(
        runner,
        (
            gh_binary,
            "api",
            "-X",
            "PUT",
            f"repos/{repo}/contents/{evidence_file}",
            "-f",
            "message=GP-5.6a disposable PR write rehearsal",
            "-f",
            f"content={encoded}",
            "-f",
            f"branch={head_ref}",
        ),
        timeout_seconds,
    )
    payload = {
        "create_status": "pass",
        "seed_commit_status": "pass" if seed_result.returncode == 0 else "fail",
        "delete_attempted": False,
        "delete_status": "not_run",
        "delete_verified": False,
        "evidence_file_path": evidence_file,
    }
    if seed_result.returncode != 0:
        payload["finding_code"] = "gp56a_seed_commit_failed"
        return payload
    try:
        payload["created_commit_sha"] = json.loads(seed_result.stdout)["commit"]["sha"]
    except (KeyError, TypeError, json.JSONDecodeError):
        payload["created_commit_sha"] = ""
    return payload


def _apply_smoke_to_remote_pr(report: JsonDict, smoke_report: GhCliPrSmokeReport) -> None:
    checks_by_name = {check.name: check for check in smoke_report.checks}
    live = checks_by_name.get("pr_live_write")
    verify = checks_by_name.get("pr_live_write_verify")
    rollback = checks_by_name.get("pr_live_write_rollback")
    if live is not None:
        report["remote_pr"]["create_status"] = live.status
        pr_url = live.observed.get("pr_url") if isinstance(live.observed, dict) else None
        if isinstance(pr_url, str):
            report["remote_pr"]["url"] = pr_url
        if live.finding_code:
            report["remote_pr"]["finding_code"] = live.finding_code
    if verify is not None:
        report["remote_pr"]["verify_open_status"] = verify.status
        if verify.finding_code:
            report["remote_pr"]["finding_code"] = verify.finding_code
    if rollback is not None:
        report["remote_pr"]["rollback_close_status"] = rollback.status
        if rollback.finding_code:
            report["remote_pr"]["finding_code"] = rollback.finding_code


def _smoke_payload(smoke_report: GhCliPrSmokeReport) -> JsonDict:
    return {
        "overall_status": smoke_report.overall_status,
        "findings": list(smoke_report.findings),
        "checks": [
            {
                "name": check.name,
                "status": check.status,
                "finding_code": check.finding_code,
                "detail": check.detail,
                "observed": dict(check.observed),
            }
            for check in smoke_report.checks
        ],
    }


def _verify_pr_closed(
    *,
    gh_binary: str,
    repo: str,
    pr_url: str,
    runner: Runner,
    timeout_seconds: float,
) -> JsonDict:
    result = _run_gh(
        runner,
        (
            gh_binary,
            "pr",
            "view",
            pr_url,
            "--repo",
            repo,
            "--json",
            "state,url,headRefName,baseRefName,isDraft",
        ),
        timeout_seconds,
    )
    if result.returncode != 0:
        return {
            "verify_closed_status": "fail",
            "final_state": "UNKNOWN",
            "finding_code": "gp56a_pr_closed_verify_failed",
        }
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "verify_closed_status": "fail",
            "final_state": "UNKNOWN",
            "finding_code": "gp56a_pr_closed_verify_not_json",
        }
    state = str(payload.get("state", "UNKNOWN")).upper()
    return {
        "verify_closed_status": "pass" if state == "CLOSED" else "fail",
        "final_state": state if state in {"CLOSED", "OPEN"} else "UNKNOWN",
    }


def _delete_remote_branch(
    *,
    gh_binary: str,
    repo: str,
    head_ref: str,
    runner: Runner,
    timeout_seconds: float,
) -> JsonDict:
    delete_result = _run_gh(
        runner,
        (
            gh_binary,
            "api",
            "-X",
            "DELETE",
            f"repos/{repo}/git/refs/heads/{head_ref}",
        ),
        timeout_seconds,
    )
    verify_result = _run_gh(
        runner,
        (gh_binary, "api", f"repos/{repo}/git/ref/heads/{head_ref}"),
        timeout_seconds,
    )
    deleted = delete_result.returncode == 0 and verify_result.returncode != 0
    payload: JsonDict = {
        "delete_attempted": True,
        "delete_status": "pass" if delete_result.returncode == 0 else "fail",
        "delete_verified": deleted,
    }
    if not deleted:
        payload["finding_code"] = "gp56a_remote_branch_delete_unverified"
    return payload


def _run_gh(
    runner: Runner,
    argv: Sequence[str],
    timeout_seconds: float | None,
) -> CommandResult:
    try:
        return runner(tuple(str(part) for part in argv), None, timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            argv=tuple(str(part) for part in argv),
            returncode=124,
            stdout=_decode_timeout_stream(exc.stdout),
            stderr=_decode_timeout_stream(exc.stderr),
            timed_out=True,
        )


def _default_runner(
    argv: Sequence[str],
    cwd: Path | None,
    timeout_seconds: float | None,
) -> CommandResult:
    proc = subprocess.run(
        [str(part) for part in argv],
        cwd=None if cwd is None else str(cwd),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_seconds,
    )
    return CommandResult(
        argv=tuple(str(part) for part in argv),
        returncode=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
    )


def _decode_timeout_stream(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _default_head_ref() -> str:
    return f"smoke/gp56a-{int(time.time())}"


if __name__ == "__main__":
    raise SystemExit(main())
