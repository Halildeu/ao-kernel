from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from ao_kernel.kernel_api_write_smoke import (
    KernelApiWriteSmokeReport,
    render_text_report,
    run_kernel_api_write_smoke,
)


def _check(report: KernelApiWriteSmokeReport, name: str) -> tuple[str, str]:
    for check in report.checks:
        if check.name == name:
            return check.status, check.detail
    raise AssertionError(f"check not found: {name}")


def test_kernel_api_write_smoke_passes_on_temp_workspace(tmp_path: Path) -> None:
    report = run_kernel_api_write_smoke(workspace_root=tmp_path)

    assert report.overall_status == "pass"
    assert report.extension_id == "PRJ-KERNEL-API"
    assert Path(report.workspace_root) == tmp_path.resolve()
    assert report.findings == ()

    for name in (
        "project_status_dry_run_default",
        "project_status_write_requires_confirm",
        "project_status_write_apply",
        "project_status_write_idempotent",
        "roadmap_follow_conflict_takeover",
        "roadmap_finish_idempotent",
        "write_audit_artifacts",
    ):
        status, detail = _check(report, name)
        assert status == "pass", f"{name} failed: {detail}"

    artifact_paths = [Path(path) for path in report.artifacts]
    assert artifact_paths, "expected at least one artifact path"
    assert all(path.exists() for path in artifact_paths)
    assert any(path.name == "kernel_api_write_audit.v1.jsonl" for path in artifact_paths)


def test_render_text_report_contains_contract_sections(tmp_path: Path) -> None:
    report = run_kernel_api_write_smoke(workspace_root=tmp_path)
    rendered = render_text_report(report)

    assert "overall_status: pass" in rendered
    assert "project_status_write_idempotent" in rendered
    assert "roadmap_follow_conflict_takeover" in rendered
    assert "write_audit_artifacts" in rendered


def test_script_wrapper_emits_json_report() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "scripts/kernel_api_write_smoke.py", "--output", "json"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["overall_status"] == "pass"
    assert payload["extension_id"] == "PRJ-KERNEL-API"
    assert isinstance(payload["checks"], list)
    assert isinstance(payload["artifacts"], list)

