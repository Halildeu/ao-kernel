"""Behavioral tests for the structured doctor report surface."""

from __future__ import annotations

from pathlib import Path

from ao_kernel.doctor_cmd import build_report


class TestDoctorReport:
    def test_build_report_returns_truth_inventory(self, tmp_workspace: Path):
        report = build_report(workspace_root_override=str(tmp_workspace.parent))

        assert report["exit_code"] == 0
        assert report["version"]
        assert isinstance(report["checks"], list)
        assert len(report["checks"]) >= 8

        checks = {item["label"]: item["status"] for item in report["checks"]}
        assert checks["Workspace found"] == "OK"
        assert checks["workspace.json valid"] == "OK"
        assert checks["Bundled extension truth"] == "WARN"

        summary = report["summary"]
        assert summary["ok_count"] >= 1
        assert summary["warn_count"] >= 1
        assert summary["fail_count"] == 0

        extension_truth = report["extension_truth"]
        assert extension_truth["total_extensions"] >= 1
        assert extension_truth["runtime_backed"] >= 1
        assert extension_truth["quarantined"] >= 1
        assert "PRJ-HELLO" in extension_truth["runtime_backed_ids"]
