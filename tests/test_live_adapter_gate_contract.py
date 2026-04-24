from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from ao_kernel.live_adapter_gate import (
    BLOCKED_FINDING,
    build_live_adapter_gate_report,
    render_live_adapter_gate_text,
    write_live_adapter_gate_report,
)


def test_build_live_adapter_gate_report_is_explicitly_blocked() -> None:
    report = build_live_adapter_gate_report(
        target_ref="main",
        reason="release rehearsal",
        requested_by="maintainer",
        event_name="workflow_dispatch",
        head_sha="abc123",
        generated_at="2026-04-24T00:00:00Z",
    )

    assert report["schema_version"] == "1"
    assert report["program_id"] == "GP-4.1"
    assert report["adapter_id"] == "claude-code-cli"
    assert report["support_tier"] == "Beta (operator-managed)"
    assert report["overall_status"] == "blocked"
    assert report["finding_code"] == BLOCKED_FINDING
    assert report["live_execution_attempted"] is False
    assert report["support_widening"] is False
    assert report["trigger"] == {
        "event_name": "workflow_dispatch",
        "target_ref": "main",
        "head_sha": "abc123",
        "requested_by": "maintainer",
        "reason": "release rehearsal",
    }

    checks = {check["name"]: check for check in report["checks"]}
    assert checks["live_execution"]["status"] == "blocked"
    assert checks["live_execution"]["finding_code"] == BLOCKED_FINDING
    assert checks["secret_access"]["status"] == "skipped"
    assert checks["support_boundary"]["status"] == "pass"


def test_write_live_adapter_gate_report_round_trips_json(tmp_path: Path) -> None:
    report = build_live_adapter_gate_report(generated_at="2026-04-24T00:00:00Z")
    path = tmp_path / "live-adapter-gate-contract.v1.json"

    write_live_adapter_gate_report(path, report)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload == report
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_render_live_adapter_gate_text_marks_no_live_execution() -> None:
    report = build_live_adapter_gate_report(generated_at="2026-04-24T00:00:00Z")
    rendered = render_live_adapter_gate_text(report)

    assert "overall_status: blocked" in rendered
    assert "live_execution_attempted: false" in rendered
    assert "support_widening: false" in rendered
    assert f"live_execution: blocked ({BLOCKED_FINDING})" in rendered


def test_script_emits_json_and_report_file(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    report_path = tmp_path / "contract.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/live_adapter_gate_contract.py",
            "--output",
            "json",
            "--report-path",
            str(report_path),
            "--target-ref",
            "main",
            "--reason",
            "test",
            "--requested-by",
            "pytest",
            "--event-name",
            "workflow_dispatch",
            "--head-sha",
            "abc123",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    stdout_payload = json.loads(result.stdout)
    file_payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert stdout_payload == file_payload
    assert stdout_payload["overall_status"] == "blocked"
    assert stdout_payload["live_execution_attempted"] is False


def test_live_adapter_gate_workflow_is_manual_contract_only() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    workflow = (repo_root / ".github/workflows/live-adapter-gate.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "\n  push:" not in workflow
    assert "\n  pull_request:" not in workflow
    assert "live_adapter_gate_contract.py" in workflow
    assert "claude_code_cli_smoke.py" not in workflow
    assert "claude_code_cli_workflow_smoke.py" not in workflow
    assert "secrets." not in workflow
    assert "contents: read" in workflow
