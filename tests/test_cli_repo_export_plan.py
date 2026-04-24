from __future__ import annotations

import json
from pathlib import Path

import pytest

from ao_kernel.cli import main
from ao_kernel._internal.repo_intelligence.artifacts import validate_repo_export_plan

ROOT_AUTHORITY_EXPORT_FILES = (
    "CLAUDE.md",
    "AGENTS.md",
    "ARCHITECTURE.md",
    "CODEX_CONTEXT.md",
)


def _make_cli_project(tmp_path: Path) -> Path:
    project = tmp_path / "cli-export-plan-project"
    (project / ".ao").mkdir(parents=True)
    (project / "pkg").mkdir()
    (project / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (project / "pkg" / "cli.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (project / "pyproject.toml").write_text(
        "[project]\nname = \"cli-export-plan-project\"\n[project.scripts]\ncli-export-plan-project = \"pkg.cli:main\"\n",
        encoding="utf-8",
    )
    return project


def _root_snapshot(project: Path) -> dict[str, bytes | None]:
    return {
        relative_path: ((project / relative_path).read_bytes() if (project / relative_path).is_file() else None)
        for relative_path in ROOT_AUTHORITY_EXPORT_FILES
    }


def _context_files(project: Path) -> set[str]:
    context_dir = project / ".ao" / "context"
    return {
        item.relative_to(context_dir).as_posix()
        for item in sorted(context_dir.rglob("*"))
        if item.is_file()
    }


def test_repo_export_plan_help_is_available(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["repo", "export-plan", "--help"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    assert captured.err == ""
    assert "--targets" in captured.out
    assert "--confirm-root-export" not in captured.out
    assert "--write-root" not in captured.out


def test_repo_export_plan_writes_only_context_plan_and_stdout_json(tmp_path: Path, capsys) -> None:
    project = _make_cli_project(tmp_path)
    for relative_path in ROOT_AUTHORITY_EXPORT_FILES:
        (project / relative_path).write_text(f"existing {relative_path}\n", encoding="utf-8")

    assert main(["repo", "scan", "--project-root", str(project), "--output", "json"]) == 0
    capsys.readouterr()
    root_before = _root_snapshot(project)
    context_before = _context_files(project)

    rc = main(
        [
            "repo",
            "export-plan",
            "--project-root",
            str(project),
            "--workspace-root",
            ".ao",
            "--targets",
            "agents,codex",
            "--output",
            "json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    artifact_path = project / ".ao" / "context" / "repo_export_plan.json"
    written = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert rc == 0
    assert captured.err == ""
    validate_repo_export_plan(payload)
    validate_repo_export_plan(written)
    assert payload == written
    assert payload["artifact_kind"] == "repo_export_plan"
    assert [item["target"] for item in payload["targets"]] == ["codex", "agents"]
    assert {item["action"] for item in payload["targets"]} == {"blocked"}
    assert _root_snapshot(project) == root_before
    assert _context_files(project) == {*context_before, "repo_export_plan.json"}


def test_repo_export_plan_missing_workspace_fails_closed_without_context_write(tmp_path: Path, capsys) -> None:
    project = tmp_path / "missing-workspace"
    project.mkdir()

    rc = main(["repo", "export-plan", "--project-root", str(project), "--output", "json"])
    captured = capsys.readouterr()

    assert rc == 1
    assert captured.out == ""
    assert ".ao workspace not found" in captured.err
    assert not (project / ".ao").exists()


def test_repo_export_plan_rejects_workspace_outside_project(tmp_path: Path, capsys) -> None:
    project = _make_cli_project(tmp_path)
    outside_workspace = tmp_path / "external-ao"
    outside_workspace.mkdir()

    rc = main(
        [
            "repo",
            "export-plan",
            "--project-root",
            str(project),
            "--workspace-root",
            str(outside_workspace),
            "--output",
            "json",
        ]
    )
    captured = capsys.readouterr()

    assert rc == 1
    assert captured.out == ""
    assert "workspace root must be inside project root" in captured.err
    assert not (outside_workspace / "context").exists()


def test_repo_export_plan_rejects_unsupported_targets(tmp_path: Path, capsys) -> None:
    project = _make_cli_project(tmp_path)

    rc = main(
        [
            "repo",
            "export-plan",
            "--project-root",
            str(project),
            "--targets",
            "claude",
            "--output",
            "json",
        ]
    )
    captured = capsys.readouterr()

    assert rc == 1
    assert captured.out == ""
    assert "unsupported export-plan target" in captured.err
    assert not (project / ".ao" / "context" / "repo_export_plan.json").exists()
