#!/usr/bin/env python3
"""Run the GP-5.5b controlled local patch/test rehearsal.

This helper deliberately does not widen the shipped write support boundary. It
creates a disposable detached git worktree, previews a deterministic patch,
requires an explicit apply flag, acquires path-scoped write ownership, applies
the patch, runs a targeted verification command, rolls the patch back, verifies
rollback idempotency, and cleans the worktree up.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ao_kernel.config import load_default  # noqa: E402
from ao_kernel.coordination import (  # noqa: E402
    ClaimRegistry,
    PathWriteLeaseSet,
    acquire_path_write_claims,
    load_coordination_policy,
    release_path_write_claims,
)
from ao_kernel.executor.policy_enforcer import (  # noqa: E402
    RedactionConfig,
    SandboxedEnvironment,
)
from ao_kernel.patch import apply_patch, preview_diff, rollback_patch  # noqa: E402

JsonDict = dict[str, Any]

_PATCH_ID = "gp5-5b-rehearsal"
_OWNER_AGENT_ID = "gp5-5b-controlled-patch-test-rehearsal"
_TARGET_FILE = "gp5_controlled_patch_rehearsal_target.txt"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the GP-5.5b controlled local patch/test rehearsal"
    )
    parser.add_argument(
        "--approve-apply",
        action="store_true",
        help="Explicitly approve the deterministic rehearsal patch apply step",
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
        "--artifact-dir",
        type=Path,
        help="Optional directory for persistent preview/decision/reverse-diff artifacts",
    )
    parser.add_argument(
        "--keep-worktree",
        action="store_true",
        help="Retain the disposable worktree for investigation instead of cleaning it up",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=60.0,
        help="Timeout for git and targeted verification commands",
    )
    args = parser.parse_args(argv)

    artifact_dir = args.artifact_dir
    if artifact_dir is None and args.report_path is not None:
        artifact_dir = args.report_path.with_name(f"{args.report_path.stem}.artifacts")

    report = run_rehearsal(
        repo_root=_REPO_ROOT,
        approve_apply=args.approve_apply,
        keep_worktree=args.keep_worktree,
        timeout_seconds=args.timeout_seconds,
        artifact_dir=artifact_dir,
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
        print(f"target_worktree: {report['target_worktree']['path']}")
        print(f"changed_paths: {', '.join(report['patch']['changed_paths'])}")
        print(f"targeted_test_status: {report['test_plan']['targeted_test_status']}")
        print(f"rollback_status: {report['rollback_plan']['rollback_status']}")
        if report["overall_status"] == "blocked":
            print(f"blocked_reason: {report['blocked_reason']}")
    return 0 if report["overall_status"] == "pass" else 1


def run_rehearsal(
    *,
    repo_root: Path,
    approve_apply: bool,
    keep_worktree: bool,
    timeout_seconds: float,
    artifact_dir: Path | None,
) -> JsonDict:
    repo_root = repo_root.resolve()
    temp_root = Path(tempfile.mkdtemp(prefix="ao-kernel-gp5-5b-")).resolve()
    target_worktree = temp_root / "target-worktree"
    run_dir = temp_root / "run-evidence"
    patch_content = _rehearsal_patch()
    sandbox: SandboxedEnvironment | None = None
    cleanup_attempted = False
    worktree_removed = False
    temp_root_removed = False

    source_head = _run_git(repo_root, ["rev-parse", "HEAD"], timeout_seconds).stdout.strip()
    source_dirty = _git_status(repo_root, timeout_seconds)

    report: JsonDict | None = None
    try:
        _run_git(
            repo_root,
            ["worktree", "add", "--detach", str(target_worktree), "HEAD"],
            timeout_seconds,
        )
        if target_worktree.resolve() == repo_root:
            raise RuntimeError("target worktree resolved to operator main worktree")

        _write_worktree_excludes(target_worktree, timeout_seconds)
        _write_enabled_coordination_policy(target_worktree)
        sandbox = _sandbox_for_git(target_worktree)
        run_dir.mkdir(parents=True, exist_ok=True)

        dirty_preflight = _git_status(target_worktree, timeout_seconds)
        preview = preview_diff(
            target_worktree,
            patch_content,
            sandbox,
            patch_id=_PATCH_ID,
            timeout=timeout_seconds,
        )
        preview_artifact = _write_json(
            run_dir / "gp5-5b-diff-preview.json",
            {
                "patch_id": preview.patch_id,
                "files_changed": list(preview.files_changed),
                "lines_added": preview.lines_added,
                "lines_removed": preview.lines_removed,
                "binary_paths": list(preview.binary_paths),
                "conflicts_detected": preview.conflicts_detected,
            },
        )
        persistent_preview = _persist_artifact(preview_artifact, artifact_dir)

        apply_decision = {
            "approved": approve_apply,
            "decision": "approve_apply" if approve_apply else "blocked_missing_approval",
            "reason": (
                "Operator supplied --approve-apply for the deterministic GP-5.5b rehearsal."
                if approve_apply
                else "GP-5.5b requires explicit apply approval before any write."
            ),
            "write_without_preview_allowed": False,
        }
        apply_decision_artifact = _write_json(
            run_dir / "gp5-5b-apply-decision.json",
            apply_decision,
        )
        persistent_decision = _persist_artifact(apply_decision_artifact, artifact_dir)

        if not approve_apply:
            dirty_after_block = _git_status(target_worktree, timeout_seconds)
            report = _build_blocked_report(
                repo_root=repo_root,
                source_head=source_head,
                source_dirty=source_dirty,
                target_worktree=target_worktree,
                dirty_preflight=dirty_preflight,
                dirty_after_rollback=dirty_after_block,
                preview=preview,
                preview_artifact=persistent_preview,
                apply_decision_artifact=persistent_decision,
                blocked_reason="explicit apply approval was not supplied",
            )
            return report

        registry = ClaimRegistry(target_worktree)
        policy = load_coordination_policy(target_worktree)

        apply_lease = acquire_path_write_claims(
            registry,
            target_worktree,
            owner_agent_id=_OWNER_AGENT_ID,
            paths=preview.files_changed,
            policy=policy,
        )
        apply_claims = _lease_payload(apply_lease)
        try:
            apply_result = apply_patch(
                target_worktree,
                patch_content,
                sandbox,
                run_dir,
                patch_id=_PATCH_ID,
                timeout=timeout_seconds,
            )
        finally:
            release_path_write_claims(registry, apply_lease)

        persistent_reverse_diff = _persist_artifact(apply_result.reverse_diff_path, artifact_dir)
        targeted_command = _targeted_test_command(expected="patched")
        targeted_result = _run_command(targeted_command, cwd=target_worktree, timeout=timeout_seconds)
        if targeted_result["returncode"] != 0:
            raise RuntimeError(f"targeted verification failed: {targeted_result['stderr']}")

        rollback_lease = acquire_path_write_claims(
            registry,
            target_worktree,
            owner_agent_id=_OWNER_AGENT_ID,
            paths=apply_result.files_changed,
            policy=policy,
        )
        rollback_claims = _lease_payload(rollback_lease)
        try:
            rollback_result = rollback_patch(
                target_worktree,
                apply_result.reverse_diff_id,
                sandbox,
                run_dir,
                timeout=timeout_seconds,
            )
        finally:
            release_path_write_claims(registry, rollback_lease)

        rollback_verify_command = _targeted_absence_command()
        rollback_verify = _run_command(
            rollback_verify_command,
            cwd=target_worktree,
            timeout=timeout_seconds,
        )
        if rollback_verify["returncode"] != 0:
            raise RuntimeError(f"rollback verification failed: {rollback_verify['stderr']}")

        idempotency_lease = acquire_path_write_claims(
            registry,
            target_worktree,
            owner_agent_id=_OWNER_AGENT_ID,
            paths=apply_result.files_changed,
            policy=policy,
        )
        try:
            idempotency_result = rollback_patch(
                target_worktree,
                apply_result.reverse_diff_id,
                sandbox,
                run_dir,
                timeout=timeout_seconds,
            )
        finally:
            release_path_write_claims(registry, idempotency_lease)
        if not idempotency_result.idempotent_skip:
            raise RuntimeError("rollback idempotency check did not report idempotent_skip")

        dirty_after_rollback = _git_status(target_worktree, timeout_seconds)
        live_claims_after = [
            claim.resource_id for claim in registry.list_agent_claims(_OWNER_AGENT_ID)
        ]
        if dirty_after_rollback:
            raise RuntimeError(f"target worktree not clean after rollback: {dirty_after_rollback!r}")
        if live_claims_after:
            raise RuntimeError(f"path write claims leaked after rehearsal: {live_claims_after!r}")

        report = _build_pass_report(
            repo_root=repo_root,
            source_head=source_head,
            source_dirty=source_dirty,
            target_worktree=target_worktree,
            dirty_preflight=dirty_preflight,
            dirty_after_rollback=dirty_after_rollback,
            preview=preview,
            apply_claims=apply_claims,
            rollback_claims=rollback_claims,
            live_claims_after=live_claims_after,
            apply_result=apply_result,
            rollback_result=rollback_result,
            preview_artifact=persistent_preview,
            apply_decision_artifact=persistent_decision,
            reverse_diff_artifact=persistent_reverse_diff,
            targeted_command=targeted_command,
            rollback_verify_command=rollback_verify_command,
        )
        return report
    finally:
        if target_worktree.exists() and not keep_worktree:
            cleanup_attempted = True
            try:
                _run_git(repo_root, ["worktree", "remove", "--force", str(target_worktree)], timeout_seconds)
                worktree_removed = not target_worktree.exists()
            except Exception:
                worktree_removed = False
        elif target_worktree.exists() and keep_worktree:
            cleanup_attempted = False
            worktree_removed = False
        else:
            worktree_removed = True

        if report is not None:
            report["cleanup"]["worktree_remove_attempted"] = cleanup_attempted
            report["cleanup"]["worktree_removed"] = worktree_removed
            report["cleanup"]["temp_root_removed"] = False
            if keep_worktree:
                report["cleanup"]["retained_reason"] = "--keep-worktree supplied"

        if not keep_worktree:
            try:
                shutil.rmtree(temp_root)
                temp_root_removed = not temp_root.exists()
            except OSError:
                temp_root_removed = False
            if report is not None:
                report["cleanup"]["temp_root_removed"] = temp_root_removed


def validate_report(report: JsonDict) -> None:
    schema = load_default(
        "schemas",
        "gp5-controlled-patch-test-rehearsal-report.schema.v1.json",
    )
    errors = sorted(Draft202012Validator(schema).iter_errors(report), key=str)
    if errors:
        messages = "; ".join(error.message for error in errors[:3])
        raise ValueError(f"invalid GP-5.5b rehearsal report: {messages}")


def _build_pass_report(
    *,
    repo_root: Path,
    source_head: str,
    source_dirty: list[str],
    target_worktree: Path,
    dirty_preflight: list[str],
    dirty_after_rollback: list[str],
    preview: Any,
    apply_claims: list[JsonDict],
    rollback_claims: list[JsonDict],
    live_claims_after: list[str],
    apply_result: Any,
    rollback_result: Any,
    preview_artifact: JsonDict,
    apply_decision_artifact: JsonDict,
    reverse_diff_artifact: JsonDict,
    targeted_command: list[str],
    rollback_verify_command: list[str],
) -> JsonDict:
    del rollback_result  # status is carried in the rollback fields below.
    return {
        "schema_version": "1",
        "artifact_kind": "gp5_controlled_patch_test_rehearsal_report",
        "program_id": "GP-5.5b",
        "overall_status": "pass",
        "decision": "pass_controlled_local_patch_test_rehearsal_no_support_widening",
        "support_widening": False,
        "runtime_patch_support_widening": False,
        "remote_side_effects_allowed": False,
        "active_main_worktree_touched": False,
        "source_repo": _source_repo(repo_root, source_head, source_dirty),
        "target_worktree": _target_worktree(
            target_worktree,
            dirty_preflight,
            dirty_after_rollback,
        ),
        "patch": {
            "patch_id": apply_result.patch_id,
            "changed_paths": list(apply_result.files_changed),
            "lines_added": apply_result.lines_added,
            "lines_removed": apply_result.lines_removed,
            "diff_preview_status": "pass",
            "apply_status": "pass",
            "reverse_diff_id": apply_result.reverse_diff_id,
            "reverse_diff_sha256": _sha256_path(apply_result.reverse_diff_path),
        },
        "write_ownership": {
            "path_scoped_claims_required": True,
            "owner_agent_id": _OWNER_AGENT_ID,
            "apply_claims": apply_claims,
            "rollback_claims": rollback_claims,
            "claims_released": True,
            "live_claims_after": live_claims_after,
        },
        "apply_boundary": {
            "diff_preview_artifact_required": True,
            "explicit_operator_approval_required": True,
            "explicit_operator_approval_observed": True,
            "write_without_preview_allowed": False,
        },
        "test_plan": {
            "targeted_tests_required": True,
            "explainable_selection_required": True,
            "selection_reason": (
                "The deterministic patch touches one rehearsal target file; "
                "the targeted command verifies exactly that changed path."
            ),
            "targeted_test_commands": [targeted_command, rollback_verify_command],
            "targeted_test_status": "pass",
            "full_gate_fallback_required": True,
            "full_gate_fallback_command": [sys.executable, "-m", "pytest", "-q"],
            "full_gate_fallback_status": "available_not_run",
        },
        "rollback_plan": {
            "reverse_diff_required": True,
            "rollback_status": "pass",
            "rollback_verification_status": "pass",
            "idempotency_check_status": "pass",
        },
        "cleanup": {
            "worktree_remove_attempted": False,
            "worktree_removed": False,
            "temp_root_removed": False,
        },
        "evidence_artifacts": {
            "diff_preview_artifact": preview_artifact,
            "apply_decision_artifact": apply_decision_artifact,
            "reverse_diff_artifact": reverse_diff_artifact,
        },
        "promotion_decision": _promotion_decision(),
    }


def _build_blocked_report(
    *,
    repo_root: Path,
    source_head: str,
    source_dirty: list[str],
    target_worktree: Path,
    dirty_preflight: list[str],
    dirty_after_rollback: list[str],
    preview: Any,
    preview_artifact: JsonDict,
    apply_decision_artifact: JsonDict,
    blocked_reason: str,
) -> JsonDict:
    return {
        "schema_version": "1",
        "artifact_kind": "gp5_controlled_patch_test_rehearsal_report",
        "program_id": "GP-5.5b",
        "overall_status": "blocked",
        "decision": "blocked_controlled_local_patch_test_rehearsal_no_support_widening",
        "support_widening": False,
        "runtime_patch_support_widening": False,
        "remote_side_effects_allowed": False,
        "active_main_worktree_touched": False,
        "blocked_reason": blocked_reason,
        "source_repo": _source_repo(repo_root, source_head, source_dirty),
        "target_worktree": _target_worktree(
            target_worktree,
            dirty_preflight,
            dirty_after_rollback,
        ),
        "patch": {
            "patch_id": preview.patch_id,
            "changed_paths": list(preview.files_changed),
            "lines_added": preview.lines_added,
            "lines_removed": preview.lines_removed,
            "diff_preview_status": "pass",
            "apply_status": "blocked_not_approved",
        },
        "write_ownership": {
            "path_scoped_claims_required": True,
            "owner_agent_id": _OWNER_AGENT_ID,
            "apply_claims": [],
            "rollback_claims": [],
            "claims_released": True,
            "live_claims_after": [],
        },
        "apply_boundary": {
            "diff_preview_artifact_required": True,
            "explicit_operator_approval_required": True,
            "explicit_operator_approval_observed": False,
            "write_without_preview_allowed": False,
        },
        "test_plan": {
            "targeted_tests_required": True,
            "explainable_selection_required": True,
            "selection_reason": "Targeted tests are not run without explicit apply approval.",
            "targeted_test_commands": [],
            "targeted_test_status": "not_run",
            "full_gate_fallback_required": True,
            "full_gate_fallback_command": [sys.executable, "-m", "pytest", "-q"],
            "full_gate_fallback_status": "not_run",
        },
        "rollback_plan": {
            "reverse_diff_required": True,
            "rollback_status": "not_run",
            "rollback_verification_status": "not_run",
            "idempotency_check_status": "not_run",
        },
        "cleanup": {
            "worktree_remove_attempted": False,
            "worktree_removed": False,
            "temp_root_removed": False,
        },
        "evidence_artifacts": {
            "diff_preview_artifact": preview_artifact,
            "apply_decision_artifact": apply_decision_artifact,
            "reverse_diff_artifact": {"status": "not_created"},
        },
        "promotion_decision": _promotion_decision(),
    }


def _source_repo(repo_root: Path, source_head: str, source_dirty: list[str]) -> JsonDict:
    return {
        "path": str(repo_root),
        "head_sha": source_head,
        "dirty_state": source_dirty,
    }


def _target_worktree(
    target_worktree: Path,
    dirty_preflight: list[str],
    dirty_after_rollback: list[str],
) -> JsonDict:
    return {
        "kind": "disposable_worktree",
        "path": str(target_worktree),
        "separate_from_operator_main": True,
        "dirty_state_preflight": dirty_preflight,
        "dirty_state_after_rollback": dirty_after_rollback,
        "cleanup_required": True,
    }


def _promotion_decision() -> JsonDict:
    return {
        "support_widening_allowed": False,
        "next_gate": "GP-5.6a",
        "reason": (
            "GP-5.5b proves local disposable patch/test rollback mechanics only; "
            "remote PR rehearsal and production write support remain separate gates."
        ),
    }


def _rehearsal_patch() -> str:
    return (
        f"diff --git a/{_TARGET_FILE} b/{_TARGET_FILE}\n"
        "new file mode 100644\n"
        "index 0000000..b87f674\n"
        "--- /dev/null\n"
        f"+++ b/{_TARGET_FILE}\n"
        "@@ -0,0 +1 @@\n"
        "+status=patched\n"
    )


def _targeted_test_command(*, expected: str) -> list[str]:
    script = (
        "from pathlib import Path; "
        f"path = Path({_TARGET_FILE!r}); "
        "assert path.read_text(encoding='utf-8').strip() == "
        f"{f'status={expected}'!r}"
    )
    return [sys.executable, "-c", script]


def _targeted_absence_command() -> list[str]:
    script = (
        "from pathlib import Path; "
        f"path = Path({_TARGET_FILE!r}); "
        "assert not path.exists()"
    )
    return [sys.executable, "-c", script]


def _write_enabled_coordination_policy(worktree: Path) -> None:
    policy_dir = worktree / ".ao" / "policies"
    policy_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "v1",
        "enabled": True,
        "heartbeat_interval_seconds": 30,
        "expiry_seconds": 90,
        "takeover_grace_period_seconds": 15,
        "max_claims_per_agent": 5,
        "claim_resource_patterns": ["*"],
        "evidence_redaction": {"patterns": []},
    }
    (policy_dir / "policy_coordination_claims.v1.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_worktree_excludes(worktree: Path, timeout_seconds: float) -> None:
    """Keep rehearsal-only coordination files out of git dirty checks.

    Linked worktrees have their own git-dir, so this does not mutate the
    operator's active main worktree exclude file.
    """
    proc = _run_git(worktree, ["rev-parse", "--git-path", "info/exclude"], timeout_seconds)
    exclude_path = Path(proc.stdout.strip())
    if not exclude_path.is_absolute():
        exclude_path = worktree / exclude_path
    exclude_path.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude_path.read_text(encoding="utf-8") if exclude_path.exists() else ""
    additions = [
        "# ao-kernel GP-5.5b disposable worktree coordination state",
        ".ao/policies/",
        ".ao/claims/",
    ]
    lines = existing.splitlines()
    changed = False
    for line in additions:
        if line not in lines:
            lines.append(line)
            changed = True
    if changed:
        exclude_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _sandbox_for_git(worktree: Path) -> SandboxedEnvironment:
    git_path = shutil.which("git")
    if git_path is None:
        raise RuntimeError("git is not available on PATH")
    real_git = Path(os.path.realpath(git_path))
    prefix_candidates = {
        str(real_git.parent),
        "/usr/bin",
        "/usr/local/bin",
        "/opt/homebrew/bin",
        "/opt/local/bin",
    }
    prefixes = tuple(
        str(Path(prefix).resolve())
        for prefix in sorted(prefix_candidates)
        if Path(prefix).exists()
    )
    env_vars = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "LANG": os.environ.get("LANG", "C"),
    }
    if "TMPDIR" in os.environ:
        env_vars["TMPDIR"] = os.environ["TMPDIR"]
    return SandboxedEnvironment(
        env_vars=env_vars,
        cwd=worktree,
        allowed_commands_exact=frozenset({"git"}),
        allowed_command_prefixes=prefixes,
        policy_derived_path_entries=tuple(Path(prefix) for prefix in prefixes),
        exposure_modes=frozenset(),
        evidence_redaction=RedactionConfig(
            env_keys_matching=(),
            stdout_patterns=(),
            file_content_patterns=(),
        ),
        inherit_from_parent=True,
    )


def _lease_payload(lease_set: PathWriteLeaseSet) -> list[JsonDict]:
    return [
        {
            "area": lease.scope.area,
            "resource_id": lease.scope.resource_id,
            "claim_id": lease.claim.claim_id,
            "fencing_token": lease.claim.fencing_token,
        }
        for lease in lease_set.leases
    ]


def _git_status(path: Path, timeout_seconds: float) -> list[str]:
    proc = _run_git(path, ["status", "--porcelain"], timeout_seconds)
    return [line for line in proc.stdout.splitlines() if line]


def _run_git(path: Path, args: list[str], timeout_seconds: float) -> subprocess.CompletedProcess[str]:
    return _run_checked_command(["git", "-C", str(path), *args], cwd=path, timeout=timeout_seconds)


def _run_command(
    command: list[str],
    *,
    cwd: Path,
    timeout: float,
) -> JsonDict:
    start = time.monotonic()
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    elapsed = time.monotonic() - start
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "duration_seconds": elapsed,
    }


def _run_checked_command(
    command: list[str],
    *,
    cwd: Path,
    timeout: float,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        rendered = " ".join(command)
        detail = proc.stderr.strip() or proc.stdout.strip() or "no output"
        raise RuntimeError(f"command failed: {rendered}: {detail}")
    return proc


def _write_json(path: Path, payload: JsonDict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _persist_artifact(path: Path, artifact_dir: Path | None) -> JsonDict:
    if not path.exists():
        return {"status": "not_created"}
    sha = _sha256_path(path)
    if artifact_dir is None:
        return {
            "status": "present",
            "path": str(path),
            "sha256": sha,
        }
    artifact_dir.mkdir(parents=True, exist_ok=True)
    dest = artifact_dir / path.name
    shutil.copyfile(path, dest)
    return {
        "status": "present",
        "path": str(dest),
        "sha256": sha,
    }


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
