"""V5 Epic 2 E-2-6 advisory live-adapter evidence workflow invariants."""

from __future__ import annotations

import json
import ast
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts.live_adapter_evidence_workflow_runner import (
    FORBIDDEN_SECRET_ENV_NAMES,
    FAILURE_STDERR_MESSAGE,
    WorkflowEvidenceError,
    emit_advisory_workflow_evidence,
)

try:
    import yaml
except ImportError:
    yaml = None

_REPO_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "live-adapter-evidence-emit.yml"
_RUNNER_PATH = _REPO_ROOT / "scripts" / "live_adapter_evidence_workflow_runner.py"


def _workflow_text() -> str:
    return _WORKFLOW_PATH.read_text(encoding="utf-8")


def _load_workflow() -> dict[Any, Any]:
    if yaml is None:
        pytest.skip("PyYAML not installed")
    loaded = yaml.safe_load(_workflow_text())
    assert isinstance(loaded, dict)
    return loaded


def _on_block(workflow: dict[Any, Any]) -> dict[Any, Any]:
    on_block = workflow.get("on") if "on" in workflow else workflow.get(True)
    assert isinstance(on_block, dict)
    return on_block


def _clear_forbidden_secret_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in FORBIDDEN_SECRET_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_workflow_exists_at_canonical_path() -> None:
    assert _WORKFLOW_PATH.exists()


def test_workflow_uses_pull_request_and_dispatch_only() -> None:
    workflow = _load_workflow()
    on_block = _on_block(workflow)
    assert sorted(on_block) == ["pull_request", "workflow_dispatch"]
    assert "main" in on_block["pull_request"]["branches"]
    assert "synchronize" in on_block["pull_request"]["types"]
    assert "pull_request_target" not in _workflow_text()


def test_workflow_is_read_only_artifact_only() -> None:
    workflow = _load_workflow()
    assert workflow["permissions"] == {"contents": "read"}
    text = _workflow_text()
    for forbidden in (
        "contents: write",
        "pull-requests: write",
        "actions: write",
        "id-token: write",
        "issues: write",
        "checks: write",
        "secrets.",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "AO_CLAUDE_CODE_CLI_AUTH",
        "TEAMS_WEBHOOK_URL",
        "gh pr comment",
        "curl ",
    ):
        assert forbidden not in text, f"unexpected advisory workflow surface: {forbidden}"
    assert "actions/upload-artifact@v7" in text
    assert "persist-credentials: false" in text


def test_workflow_invokes_runner_and_uploads_directory() -> None:
    text = _workflow_text()
    assert "scripts/live_adapter_evidence_workflow_runner.py" in text
    assert "--output-dir live-adapter-evidence" in text
    assert "path: live-adapter-evidence/" in text


def test_runner_emits_summary_envelope_and_audit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_forbidden_secret_env(monkeypatch)
    output_dir = tmp_path / "artifact"
    summary = emit_advisory_workflow_evidence(output_dir=output_dir)

    summary_path = output_dir / "live-adapter-evidence-workflow-summary.v1.json"
    envelope_path = output_dir / "evidence" / "live-adapter-dryrun.envelope.v1.json"
    audit_path = output_dir / "evidence" / "per_call_audit.jsonl"
    assert summary_path.is_file()
    assert envelope_path.is_file()
    assert audit_path.is_file()
    persisted = json.loads(summary_path.read_text(encoding="utf-8"))
    envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
    audit_rows = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]

    assert summary["mode"] == "advisory_ci_path_a"
    assert persisted["envelope_digest"] == envelope["envelope_digest"]
    assert audit_rows[0]["envelope_digest"] == envelope["envelope_digest"]
    for payload in (persisted, envelope, audit_rows[0]):
        assert payload["live_adapter_execution"] is False
        assert payload["support_widening"] is False
        assert payload["production_platform_claim"] is False
    assert persisted["secret_env_policy"]["forbidden_env_present"] == []


def test_runner_fails_closed_when_forbidden_secret_env_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_forbidden_secret_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "redacted-test-token")
    with pytest.raises(WorkflowEvidenceError, match="forbidden secret environment variables"):
        emit_advisory_workflow_evidence(output_dir=tmp_path / "artifact")


def test_runner_cli_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_forbidden_secret_env(monkeypatch)
    proc = subprocess.run(
        [
            sys.executable,
            str(_RUNNER_PATH),
            "--output-dir",
            str(tmp_path / "artifact"),
            "--output-format",
            "json",
        ],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["mode"] == "advisory_ci_path_a"
    assert payload["artifacts_written"] is True
    assert payload["live_adapter_execution"] is False
    assert "envelope_digest" not in payload
    assert "artifacts" not in payload


def test_runner_cli_failure_stderr_is_static(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_forbidden_secret_env(monkeypatch)
    output_dir_file = tmp_path / "artifact-file"
    output_dir_file.write_text("not a directory", encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            str(_RUNNER_PATH),
            "--output-dir",
            str(output_dir_file),
            "--output-format",
            "text",
        ],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert proc.returncode == 1
    assert proc.stderr.strip() == FAILURE_STDERR_MESSAGE
    assert str(tmp_path) not in proc.stderr
    assert str(output_dir_file) not in proc.stderr
    assert "envelope_digest" not in proc.stderr
    for forbidden_name in FORBIDDEN_SECRET_ENV_NAMES:
        assert forbidden_name not in proc.stderr


def test_runner_source_does_not_import_http_or_secret_providers() -> None:
    tree = ast.parse(_RUNNER_PATH.read_text(encoding="utf-8"), filename=str(_RUNNER_PATH))
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)
    for forbidden in (
        "requests",
        "httpx",
        "urllib",
        "socket",
        "subprocess",
        "vault",
        "SecretResolutionDiscipline",
        "resolve_api_key",
    ):
        assert not any(module == forbidden or module.startswith(f"{forbidden}.") for module in imported_modules), (
            f"runner must stay dry-run artifact-only: {forbidden}"
        )
