from __future__ import annotations

import json
from pathlib import Path

from ao_kernel.cli import main


def _make_cli_project(tmp_path: Path) -> Path:
    project = tmp_path / "cli-index-project"
    (project / ".ao").mkdir(parents=True)
    (project / "pkg").mkdir()
    (project / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (project / "pkg" / "cli.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (project / "pyproject.toml").write_text(
        "[project]\nname = \"cli-index-project\"\n[project.scripts]\ncli-index-project = \"pkg.cli:main\"\n",
        encoding="utf-8",
    )
    return project


def test_repo_index_dry_run_writes_vector_write_plan_only_after_scan(tmp_path: Path, capsys) -> None:
    project = _make_cli_project(tmp_path)

    scan_rc = main(["repo", "scan", "--project-root", str(project), "--output", "json"])
    capsys.readouterr()
    index_rc = main(
        [
            "repo",
            "index",
            "--project-root",
            str(project),
            "--workspace-root",
            ".ao",
            "--dry-run",
            "--output",
            "json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert scan_rc == 0
    assert index_rc == 0
    assert captured.err == ""
    assert payload["status"] == "ok"
    assert payload["command"] == "repo index"
    assert payload["dry_run"] is True
    assert payload["summary"]["embedding_calls"] == 0
    assert payload["summary"]["vector_writes"] == 0
    assert payload["artifacts"] and payload["artifacts"][0]["path"] == ".ao/context/repo_vector_write_plan.json"
    assert (project / ".ao" / "context" / "repo_vector_write_plan.json").is_file()
    assert not (project / "CLAUDE.md").exists()
    assert not (project / "AGENTS.md").exists()
    assert not (project / "ARCHITECTURE.md").exists()
    assert not (project / "CODEX_CONTEXT.md").exists()


def test_repo_index_dry_run_default_output_is_text(tmp_path: Path, capsys) -> None:
    project = _make_cli_project(tmp_path)

    assert main(["repo", "scan", "--project-root", str(project), "--output", "json"]) == 0
    capsys.readouterr()
    rc = main(["repo", "index", "--project-root", str(project), "--dry-run"])
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.err == ""
    assert "repo index dry-run complete" in captured.out
    assert ".ao/context/repo_vector_write_plan.json" in captured.out


def test_repo_index_missing_chunk_manifest_fails_closed(tmp_path: Path, capsys) -> None:
    project = _make_cli_project(tmp_path)

    rc = main(
        [
            "repo",
            "index",
            "--project-root",
            str(project),
            "--workspace-root",
            ".ao",
            "--dry-run",
            "--output",
            "json",
        ]
    )
    captured = capsys.readouterr()

    assert rc == 1
    assert captured.out == ""
    assert "repo chunk manifest not found" in captured.err
    assert not (project / ".ao" / "context" / "repo_vector_write_plan.json").exists()


def test_repo_index_invalid_chunk_manifest_fails_closed(tmp_path: Path, capsys) -> None:
    project = _make_cli_project(tmp_path)
    context_dir = project / ".ao" / "context"
    context_dir.mkdir(parents=True)
    (context_dir / "repo_chunks.json").write_text('{"artifact_kind": "not_repo_chunks"}', encoding="utf-8")

    rc = main(["repo", "index", "--project-root", str(project), "--dry-run", "--output", "json"])
    captured = capsys.readouterr()

    assert rc == 1
    assert captured.out == ""
    assert "invalid repo chunk manifest" in captured.err
    assert not (context_dir / "repo_vector_write_plan.json").exists()


def test_repo_index_requires_dry_run_until_vector_writes_are_implemented(tmp_path: Path, capsys) -> None:
    project = _make_cli_project(tmp_path)

    rc = main(["repo", "index", "--project-root", str(project), "--output", "json"])
    captured = capsys.readouterr()

    assert rc == 1
    assert captured.out == ""
    assert "requires --dry-run" in captured.err


def test_repo_index_write_vectors_is_reserved_until_explicit_write_slice(tmp_path: Path, capsys) -> None:
    project = _make_cli_project(tmp_path)

    rc = main(["repo", "index", "--project-root", str(project), "--write-vectors"])
    captured = capsys.readouterr()

    assert rc == 1
    assert captured.out == ""
    assert "not implemented in this tranche" in captured.err
