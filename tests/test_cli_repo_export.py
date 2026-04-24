from __future__ import annotations

import json
from pathlib import Path

import pytest

from ao_kernel._internal.repo_intelligence.artifacts import validate_repo_root_export_result
from ao_kernel._internal.repo_intelligence.export_plan import CONFIRM_RI5B_ROOT_EXPORT
from ao_kernel.cli import main


def _make_cli_project(tmp_path: Path) -> Path:
    project = tmp_path / "cli-root-export-project"
    (project / ".ao").mkdir(parents=True)
    (project / "pkg").mkdir()
    (project / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (project / "pkg" / "cli.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (project / "pyproject.toml").write_text(
        "[project]\nname = \"cli-root-export-project\"\n",
        encoding="utf-8",
    )
    return project


def _write_enabled_coordination_policy(project: Path) -> None:
    policy_dir = project / ".ao" / "policies"
    policy_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "v1",
        "enabled": True,
        "heartbeat_interval_seconds": 30,
        "expiry_seconds": 90,
        "takeover_grace_period_seconds": 15,
        "max_claims_per_agent": 10,
        "claim_resource_patterns": ["*"],
        "evidence_redaction": {"patterns": []},
    }
    (policy_dir / "policy_coordination_claims.v1.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_repo_export_help_is_confirmed_write_surface(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["repo", "export", "--help"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    assert captured.err == ""
    assert "--confirm-root-export" in captured.out
    assert "CONFIRM_RI5B_ROOT_EXPORT_V1" in captured.out
    assert "--targets" in captured.out


def test_repo_export_missing_confirmation_fails_without_root_write(tmp_path: Path, capsys) -> None:
    project = _make_cli_project(tmp_path)

    assert main(["repo", "scan", "--project-root", str(project), "--output", "json"]) == 0
    capsys.readouterr()
    assert (
        main(
            [
                "repo",
                "export-plan",
                "--project-root",
                str(project),
                "--workspace-root",
                ".ao",
                "--targets",
                "codex",
                "--output",
                "json",
            ]
        )
        == 0
    )
    capsys.readouterr()

    rc = main(
        [
            "repo",
            "export",
            "--project-root",
            str(project),
            "--workspace-root",
            ".ao",
            "--targets",
            "codex",
            "--output",
            "json",
        ]
    )
    captured = capsys.readouterr()

    assert rc == 1
    assert captured.out == ""
    assert "exact confirmation token required" in captured.err
    assert not (project / "CODEX_CONTEXT.md").exists()


def test_repo_export_writes_selected_absent_root_and_json_result(tmp_path: Path, capsys) -> None:
    project = _make_cli_project(tmp_path)
    _write_enabled_coordination_policy(project)

    assert main(["repo", "scan", "--project-root", str(project), "--output", "json"]) == 0
    capsys.readouterr()
    assert (
        main(
            [
                "repo",
                "export-plan",
                "--project-root",
                str(project),
                "--workspace-root",
                ".ao",
                "--targets",
                "codex,agents",
                "--output",
                "json",
            ]
        )
        == 0
    )
    capsys.readouterr()

    rc = main(
        [
            "repo",
            "export",
            "--project-root",
            str(project),
            "--workspace-root",
            ".ao",
            "--targets",
            "codex",
            "--confirm-root-export",
            CONFIRM_RI5B_ROOT_EXPORT,
            "--output",
            "json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert captured.err == ""
    validate_repo_root_export_result(payload)
    assert (project / "CODEX_CONTEXT.md").is_file()
    assert not (project / "AGENTS.md").exists()
    assert payload["summary"]["written_count"] == 1
    assert payload["targets"][0]["target"] == "codex"


def test_repo_export_existing_conflict_fails_without_overwrite(tmp_path: Path, capsys) -> None:
    project = _make_cli_project(tmp_path)
    _write_enabled_coordination_policy(project)
    (project / "CODEX_CONTEXT.md").write_text("human maintained\n", encoding="utf-8")
    before = (project / "CODEX_CONTEXT.md").read_bytes()

    assert main(["repo", "scan", "--project-root", str(project), "--output", "json"]) == 0
    capsys.readouterr()
    assert (
        main(
            [
                "repo",
                "export-plan",
                "--project-root",
                str(project),
                "--workspace-root",
                ".ao",
                "--targets",
                "codex",
                "--output",
                "json",
            ]
        )
        == 0
    )
    capsys.readouterr()

    rc = main(
        [
            "repo",
            "export",
            "--project-root",
            str(project),
            "--workspace-root",
            ".ao",
            "--targets",
            "codex",
            "--confirm-root-export",
            CONFIRM_RI5B_ROOT_EXPORT,
            "--output",
            "json",
        ]
    )
    captured = capsys.readouterr()

    assert rc == 1
    assert captured.out == ""
    assert "is blocked" in captured.err
    assert (project / "CODEX_CONTEXT.md").read_bytes() == before
