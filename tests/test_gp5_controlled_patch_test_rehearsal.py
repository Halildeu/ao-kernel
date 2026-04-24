from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _schema() -> dict[str, Any]:
    return load_default("schemas", "gp5-controlled-patch-test-rehearsal-report.schema.v1.json")


def _errors(payload: dict[str, Any]) -> list[str]:
    return sorted(error.message for error in Draft202012Validator(_schema()).iter_errors(payload))


def _run_rehearsal(*args: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    repo_root = _repo_root()
    return subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "gp5_controlled_patch_test_rehearsal.py"),
            *args,
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def test_gp55b_rehearsal_passes_with_explicit_apply_and_cleans_up(tmp_path: Path) -> None:
    report_path = tmp_path / "gp55b-report.json"

    proc = _run_rehearsal(
        "--approve-apply",
        "--output",
        "json",
        "--report-path",
        str(report_path),
        tmp_path=tmp_path,
    )

    assert proc.returncode == 0, proc.stderr
    stdout_report = json.loads(proc.stdout)
    persisted_report = json.loads(report_path.read_text(encoding="utf-8"))
    assert stdout_report == persisted_report
    assert _errors(persisted_report) == []

    assert persisted_report["overall_status"] == "pass"
    assert persisted_report["decision"] == (
        "pass_controlled_local_patch_test_rehearsal_no_support_widening"
    )
    assert persisted_report["support_widening"] is False
    assert persisted_report["runtime_patch_support_widening"] is False
    assert persisted_report["remote_side_effects_allowed"] is False
    assert persisted_report["active_main_worktree_touched"] is False
    assert persisted_report["target_worktree"]["separate_from_operator_main"] is True
    assert persisted_report["target_worktree"]["dirty_state_preflight"] == []
    assert persisted_report["target_worktree"]["dirty_state_after_rollback"] == []
    assert persisted_report["patch"]["changed_paths"] == [
        "gp5_controlled_patch_rehearsal_target.txt"
    ]
    assert persisted_report["patch"]["apply_status"] == "pass"
    assert persisted_report["write_ownership"]["apply_claims"]
    assert persisted_report["write_ownership"]["rollback_claims"]
    assert persisted_report["write_ownership"]["claims_released"] is True
    assert persisted_report["write_ownership"]["live_claims_after"] == []
    assert persisted_report["apply_boundary"]["explicit_operator_approval_observed"] is True
    assert persisted_report["test_plan"]["targeted_test_status"] == "pass"
    assert persisted_report["test_plan"]["full_gate_fallback_status"] == "available_not_run"
    assert persisted_report["rollback_plan"]["rollback_status"] == "pass"
    assert persisted_report["rollback_plan"]["rollback_verification_status"] == "pass"
    assert persisted_report["rollback_plan"]["idempotency_check_status"] == "pass"
    assert persisted_report["cleanup"]["worktree_remove_attempted"] is True
    assert persisted_report["cleanup"]["worktree_removed"] is True
    assert persisted_report["cleanup"]["temp_root_removed"] is True
    assert not Path(persisted_report["target_worktree"]["path"]).exists()

    artifact_dir = tmp_path / "gp55b-report.artifacts"
    assert artifact_dir.is_dir()
    for artifact in persisted_report["evidence_artifacts"].values():
        assert artifact["status"] == "present"
        assert Path(artifact["path"]).is_file()


def test_gp55b_rehearsal_blocks_without_explicit_apply(tmp_path: Path) -> None:
    report_path = tmp_path / "gp55b-blocked.json"

    proc = _run_rehearsal(
        "--output",
        "json",
        "--report-path",
        str(report_path),
        tmp_path=tmp_path,
    )

    assert proc.returncode == 1
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert _errors(report) == []
    assert report["overall_status"] == "blocked"
    assert report["patch"]["apply_status"] == "blocked_not_approved"
    assert report["apply_boundary"]["explicit_operator_approval_observed"] is False
    assert report["test_plan"]["targeted_test_status"] == "not_run"
    assert report["rollback_plan"]["rollback_status"] == "not_run"
    assert report["cleanup"]["worktree_removed"] is True
    assert report["cleanup"]["temp_root_removed"] is True
    assert not Path(report["target_worktree"]["path"]).exists()


def test_gp55b_rehearsal_schema_rejects_support_widening(tmp_path: Path) -> None:
    report_path = tmp_path / "gp55b-report.json"
    proc = _run_rehearsal(
        "--approve-apply",
        "--output",
        "json",
        "--report-path",
        str(report_path),
        tmp_path=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))

    report["support_widening"] = True
    report["runtime_patch_support_widening"] = True
    report["active_main_worktree_touched"] = True
    report["promotion_decision"]["support_widening_allowed"] = True

    errors = _errors(report)

    assert "False was expected" in errors


def test_gp55b_docs_keep_rehearsal_boundary_explicit() -> None:
    repo_root = _repo_root()
    public_beta = (repo_root / "docs" / "PUBLIC-BETA.md").read_text(encoding="utf-8")
    support_boundary = (repo_root / "docs" / "SUPPORT-BOUNDARY.md").read_text(encoding="utf-8")
    runbook = (repo_root / "docs" / "OPERATIONS-RUNBOOK.md").read_text(encoding="utf-8")

    assert "GP-5 controlled patch/test lane" in public_beta
    assert "Rehearsal / no support widening" in public_beta
    assert "gp5-controlled-patch-test-rehearsal-report.schema.v1.json" in public_beta
    assert "runtime_patch_support_widening=false" in support_boundary
    assert "GP-5.5b controlled local patch/test rehearsal" in runbook
