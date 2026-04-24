from __future__ import annotations

import json
from pathlib import Path

from ao_kernel.cli import main


def _make_cli_project(tmp_path: Path) -> Path:
    project = tmp_path / "cli-project"
    (project / ".ao").mkdir(parents=True)
    (project / "pkg").mkdir()
    (project / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (project / "pkg" / "cli.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (project / "pyproject.toml").write_text(
        "[project]\nname = \"cli-project\"\n[project.scripts]\ncli-project = \"pkg.cli:main\"\n",
        encoding="utf-8",
    )
    return project


def test_repo_scan_json_output_writes_only_context_artifacts(tmp_path: Path, capsys) -> None:
    project = _make_cli_project(tmp_path)

    rc = main(["repo", "scan", "--project-root", str(project), "--output", "json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert captured.err == ""
    assert payload["status"] == "ok"
    assert payload["summary"]["included_files"] == 3
    assert [item["path"] for item in payload["artifacts"]] == [
        ".ao/context/repo_map.json",
        ".ao/context/repo_index_manifest.json",
    ]
    assert (project / ".ao" / "context" / "repo_map.json").is_file()
    assert (project / ".ao" / "context" / "repo_index_manifest.json").is_file()
    assert not (project / "CLAUDE.md").exists()
    assert not (project / "AGENTS.md").exists()
    assert not (project / "CODEX_CONTEXT.md").exists()


def test_repo_scan_default_output_is_text(tmp_path: Path, capsys) -> None:
    project = _make_cli_project(tmp_path)

    rc = main(["repo", "scan", "--project-root", str(project)])
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.err == ""
    assert "repo scan complete" in captured.out
    assert ".ao/context/repo_map.json" in captured.out


def test_repo_scan_missing_ao_fails_with_init_hint(tmp_path: Path, capsys) -> None:
    project = tmp_path / "no-workspace"
    project.mkdir()
    (project / "main.py").write_text("print('hello')\n", encoding="utf-8")

    rc = main(["repo", "scan", "--project-root", str(project), "--output", "json"])
    captured = capsys.readouterr()

    assert rc == 1
    assert captured.out == ""
    assert "ao-kernel init" in captured.err
    assert not (project / ".ao").exists()
