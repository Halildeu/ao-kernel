from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Sequence

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default
from ao_kernel.real_adapter_smoke import CommandResult, GhCliPrSmokeReport, SmokeCheck


def _module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "scripts" / "gp5_disposable_pr_write_rehearsal.py"
    spec = importlib.util.spec_from_file_location("gp5_disposable_pr_write_rehearsal", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _schema_errors(payload: dict[str, Any]) -> list[str]:
    schema = load_default(
        "schemas",
        "gp5-disposable-pr-write-rehearsal-report.schema.v1.json",
    )
    return sorted(error.message for error in Draft202012Validator(schema).iter_errors(payload))


def _write_gp55b_report(path: Path, *, support_widening: bool = False) -> None:
    payload = {
        "schema_version": "1",
        "artifact_kind": "gp5_controlled_patch_test_rehearsal_report",
        "program_id": "GP-5.5b",
        "overall_status": "pass",
        "decision": "pass_controlled_local_patch_test_rehearsal_no_support_widening",
        "support_widening": support_widening,
        "runtime_patch_support_widening": False,
        "remote_side_effects_allowed": False,
        "active_main_worktree_touched": False,
        "source_repo": {
            "path": "/tmp/source",
            "head_sha": "abcdef1234567890",
            "dirty_state": [],
        },
        "target_worktree": {
            "kind": "disposable_worktree",
            "path": "/tmp/target",
            "separate_from_operator_main": True,
            "dirty_state_preflight": [],
            "dirty_state_after_rollback": [],
            "cleanup_required": True,
        },
        "patch": {
            "patch_id": "gp5-5b-rehearsal",
            "changed_paths": ["gp5_controlled_patch_rehearsal_target.txt"],
            "lines_added": 1,
            "lines_removed": 0,
            "diff_preview_status": "pass",
            "apply_status": "pass",
            "reverse_diff_id": "reverse-1",
            "reverse_diff_sha256": "a" * 64,
        },
        "write_ownership": {
            "path_scoped_claims_required": True,
            "owner_agent_id": "gp5-5b-controlled-patch-test-rehearsal",
            "apply_claims": [
                {
                    "area": "path",
                    "resource_id": "gp5_controlled_patch_rehearsal_target.txt",
                    "claim_id": "claim-1",
                    "fencing_token": 1,
                }
            ],
            "rollback_claims": [
                {
                    "area": "path",
                    "resource_id": "gp5_controlled_patch_rehearsal_target.txt",
                    "claim_id": "claim-2",
                    "fencing_token": 2,
                }
            ],
            "claims_released": True,
            "live_claims_after": [],
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
            "targeted_test_commands": [["python3", "-c", "pass"]],
            "targeted_test_status": "pass",
            "full_gate_fallback_required": True,
            "full_gate_fallback_command": ["pytest"],
            "full_gate_fallback_status": "available_not_run",
        },
        "rollback_plan": {
            "reverse_diff_required": True,
            "rollback_status": "pass",
            "rollback_verification_status": "pass",
            "idempotency_check_status": "pass",
        },
        "cleanup": {
            "worktree_remove_attempted": True,
            "worktree_removed": True,
            "temp_root_removed": True,
        },
        "evidence_artifacts": {
            "diff_preview_artifact": {"status": "not_created"},
            "apply_decision_artifact": {"status": "not_created"},
            "reverse_diff_artifact": {"status": "not_created"},
        },
        "promotion_decision": {
            "support_widening_allowed": False,
            "next_gate": "GP-5.6a",
            "reason": "local rehearsal only",
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _result(
    argv: Sequence[str],
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> CommandResult:
    return CommandResult(
        argv=tuple(argv),
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _passing_smoke(**kwargs: Any) -> GhCliPrSmokeReport:
    repo = kwargs["repo"]
    head_ref = kwargs["head_ref"]
    base_ref = kwargs["base_ref"]
    pr_url = f"https://github.com/{repo}/pull/56"
    return GhCliPrSmokeReport(
        overall_status="pass",
        adapter_id="gh-cli-pr",
        binary_path="/fake/gh",
        repo_name=repo,
        default_branch=base_ref,
        repo_url=f"https://github.com/{repo}",
        checks=(
            SmokeCheck(
                name="pr_live_write",
                status="pass",
                detail="created",
                observed={"pr_url": pr_url},
            ),
            SmokeCheck(
                name="pr_live_write_verify",
                status="pass",
                detail="verified open",
                observed={
                    "pr_url": pr_url,
                    "head_ref": head_ref,
                    "base_ref": base_ref,
                },
            ),
            SmokeCheck(
                name="pr_live_write_rollback",
                status="pass",
                detail="closed",
                observed={"pr_url": pr_url},
            ),
        ),
        findings=(),
    )


def test_gp56a_passes_with_gp55b_precondition_and_sandbox_cleanup(tmp_path: Path) -> None:
    mod = _module()
    local_report = tmp_path / "gp55b.json"
    _write_gp55b_report(local_report)
    calls: list[tuple[str, ...]] = []

    def runner(
        argv: Sequence[str],
        cwd: Path | None,
        timeout: float | None,
    ) -> CommandResult:
        cmd = tuple(argv)
        calls.append(cmd)
        if cmd == ("/fake/gh", "api", "repos/Halildeu/ao-kernel-sandbox/git/ref/heads/main"):
            return _result(cmd, stdout='{"object":{"sha":"base-sha"}}')
        if cmd == (
            "/fake/gh",
            "api",
            "repos/Halildeu/ao-kernel-sandbox/git/ref/heads/smoke/gp56a-test",
        ):
            if any(
                prior[:5]
                == (
                    "/fake/gh",
                    "api",
                    "-X",
                    "DELETE",
                    "repos/Halildeu/ao-kernel-sandbox/git/refs/heads/smoke/gp56a-test",
                )
                for prior in calls[:-1]
            ):
                return _result(cmd, returncode=1, stderr="not found")
            return _result(cmd, stdout='{"object":{"sha":"commit-sha"}}')
        if cmd[:5] == (
            "/fake/gh",
            "api",
            "-X",
            "POST",
            "repos/Halildeu/ao-kernel-sandbox/git/refs",
        ):
            return _result(cmd, stdout='{"ref":"refs/heads/smoke/gp56a-test"}')
        if cmd[:5] == (
            "/fake/gh",
            "api",
            "-X",
            "PUT",
            "repos/Halildeu/ao-kernel-sandbox/contents/gp5-rehearsals/smoke-gp56a-test.txt",
        ):
            return _result(cmd, stdout='{"commit":{"sha":"commit-sha"}}')
        if cmd[:4] == (
            "/fake/gh",
            "pr",
            "view",
            "https://github.com/Halildeu/ao-kernel-sandbox/pull/56",
        ):
            return _result(
                cmd,
                stdout=(
                    '{"state":"CLOSED","url":"https://github.com/Halildeu/ao-kernel-sandbox/pull/56",'
                    '"headRefName":"smoke/gp56a-test","baseRefName":"main","isDraft":true}'
                ),
            )
        if cmd[:5] == (
            "/fake/gh",
            "api",
            "-X",
            "DELETE",
            "repos/Halildeu/ao-kernel-sandbox/git/refs/heads/smoke/gp56a-test",
        ):
            return _result(cmd)
        raise AssertionError(f"unexpected command: {cmd!r}")

    report = mod.run_disposable_pr_write_rehearsal(
        repo_root=Path(__file__).resolve().parents[1],
        local_patch_report=local_report,
        repo="Halildeu/ao-kernel-sandbox",
        base_ref="main",
        head_ref="smoke/gp56a-test",
        allow_live_write=True,
        require_disposable_keyword="sandbox",
        timeout_seconds=1,
        runner=runner,
        smoke_runner=_passing_smoke,
        gh_binary="/fake/gh",
    )

    assert _schema_errors(report) == []
    assert report["overall_status"] == "pass"
    assert report["decision"] == "pass_disposable_pr_write_rehearsal_no_support_widening"
    assert report["support_widening"] is False
    assert report["production_remote_pr_support"] is False
    assert report["arbitrary_repo_support"] is False
    assert report["remote_pr"]["final_state"] == "CLOSED"
    assert report["cleanup"]["cleanup_complete"] is True
    assert report["remote_branch"]["delete_verified"] is True


def test_gp56a_blocks_without_explicit_live_write_and_does_not_call_gh(tmp_path: Path) -> None:
    mod = _module()
    local_report = tmp_path / "gp55b.json"
    _write_gp55b_report(local_report)

    def runner(
        argv: Sequence[str],
        cwd: Path | None,
        timeout: float | None,
    ) -> CommandResult:
        raise AssertionError(f"remote command should not run: {tuple(argv)!r}")

    report = mod.run_disposable_pr_write_rehearsal(
        repo_root=Path(__file__).resolve().parents[1],
        local_patch_report=local_report,
        repo="Halildeu/ao-kernel-sandbox",
        base_ref="main",
        head_ref="smoke/gp56a-test",
        allow_live_write=False,
        require_disposable_keyword="sandbox",
        timeout_seconds=1,
        runner=runner,
        smoke_runner=_passing_smoke,
        gh_binary="/fake/gh",
    )

    assert _schema_errors(report) == []
    assert report["overall_status"] == "blocked"
    assert report["blocked_reason"] == "explicit --allow-live-write is required before remote writes"
    assert report["remote_branch"]["create_status"] == "not_run"
    assert report["gh_cli_pr_smoke"]["overall_status"] == "not_run"


def test_gp56a_rejects_non_passing_or_widening_local_report(tmp_path: Path) -> None:
    mod = _module()
    local_report = tmp_path / "gp55b-widening.json"
    _write_gp55b_report(local_report, support_widening=True)

    report = mod.run_disposable_pr_write_rehearsal(
        repo_root=Path(__file__).resolve().parents[1],
        local_patch_report=local_report,
        repo="Halildeu/ao-kernel-sandbox",
        base_ref="main",
        head_ref="smoke/gp56a-test",
        allow_live_write=True,
        require_disposable_keyword="sandbox",
        timeout_seconds=1,
        runner=lambda argv, cwd, timeout: _result(argv),
        smoke_runner=_passing_smoke,
        gh_binary="/fake/gh",
    )

    assert _schema_errors(report) == []
    assert report["overall_status"] == "blocked"
    assert "local_patch_report_schema_invalid" in report["local_patch_precondition"]["findings"]
    assert "local_patch_report_support_widening" in report["local_patch_precondition"]["findings"]
    assert report["remote_branch"]["create_status"] == "not_run"


def test_gp56a_disposable_guard_blocks_production_repo(tmp_path: Path) -> None:
    mod = _module()
    local_report = tmp_path / "gp55b.json"
    _write_gp55b_report(local_report)

    report = mod.run_disposable_pr_write_rehearsal(
        repo_root=Path(__file__).resolve().parents[1],
        local_patch_report=local_report,
        repo="Halildeu/ao-kernel",
        base_ref="main",
        head_ref="smoke/gp56a-test",
        allow_live_write=True,
        require_disposable_keyword="sandbox",
        timeout_seconds=1,
        runner=lambda argv, cwd, timeout: _result(argv),
        smoke_runner=_passing_smoke,
        gh_binary="/fake/gh",
    )

    assert _schema_errors(report) == []
    assert report["overall_status"] == "blocked"
    assert report["target_repo"]["disposable_guard_status"] == "fail"
    assert report["blocked_reason"] == "target repo must satisfy disposable sandbox keyword guard"


def test_gp56a_schema_rejects_support_widening(tmp_path: Path) -> None:
    mod = _module()
    local_report = tmp_path / "gp55b.json"
    _write_gp55b_report(local_report)
    report = mod.run_disposable_pr_write_rehearsal(
        repo_root=Path(__file__).resolve().parents[1],
        local_patch_report=local_report,
        repo="Halildeu/ao-kernel-sandbox",
        base_ref="main",
        head_ref="smoke/gp56a-test",
        allow_live_write=False,
        require_disposable_keyword="sandbox",
        timeout_seconds=1,
        runner=lambda argv, cwd, timeout: _result(argv),
        smoke_runner=_passing_smoke,
        gh_binary="/fake/gh",
    )
    report["support_widening"] = True
    report["production_remote_pr_support"] = True
    report["arbitrary_repo_support"] = True
    report["promotion_decision"]["support_widening_allowed"] = True

    assert "False was expected" in _schema_errors(report)


def test_gp56a_docs_keep_disposable_boundary_explicit() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    public_beta = (repo_root / "docs" / "PUBLIC-BETA.md").read_text(encoding="utf-8")
    support_boundary = (repo_root / "docs" / "SUPPORT-BOUNDARY.md").read_text(
        encoding="utf-8"
    )
    runbook = (repo_root / "docs" / "OPERATIONS-RUNBOOK.md").read_text(encoding="utf-8")
    adapters = (repo_root / "docs" / "ADAPTERS.md").read_text(encoding="utf-8")

    assert "GP-5.6a disposable PR write rehearsal" in public_beta
    assert "gp5-disposable-pr-write-rehearsal-report.schema.v1.json" in public_beta
    assert "production_remote_pr_support=false" in support_boundary
    assert "scripts/gp5_disposable_pr_write_rehearsal.py" in runbook
    assert "sandbox branch delete verify" in adapters
    assert "support widening değildir" in adapters
