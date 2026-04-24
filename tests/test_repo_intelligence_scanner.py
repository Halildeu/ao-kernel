from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ao_kernel._internal.repo_intelligence.artifacts import validate_repo_map
from ao_kernel._internal.repo_intelligence.scanner import scan_repo


def _make_sample_repo(tmp_path: Path) -> Path:
    project = tmp_path / "sample"
    (project / ".ao").mkdir(parents=True)
    (project / ".git").mkdir()
    (project / "pkg").mkdir()
    (project / "scripts").mkdir()
    (project / "__pycache__").mkdir()
    (project / "build").mkdir()
    (project / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (project / "pkg" / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    (project / "pkg" / "cli.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (project / "scripts" / "tool.py").write_text("print('tool')\n", encoding="utf-8")
    (project / "README.md").write_text("# Sample\n", encoding="utf-8")
    (project / ".git" / "ignored.py").write_text("ignored = True\n", encoding="utf-8")
    (project / ".ao" / "workspace.json").write_text("{}\n", encoding="utf-8")
    (project / "__pycache__" / "cached.pyc").write_bytes(b"cache")
    (project / "build" / "ignored.py").write_text("ignored = True\n", encoding="utf-8")
    (project / "pyproject.toml").write_text(
        "[project]\nname = \"sample-project\"\n[project.scripts]\nsample = \"pkg.cli:main\"\n",
        encoding="utf-8",
    )
    if hasattr(os, "symlink"):
        (project / "linked.py").symlink_to(project / "pkg" / "module.py")
    return project


def _stable_repo_map(doc: dict[str, Any]) -> dict[str, Any]:
    stable = dict(doc)
    stable["generator"] = dict(doc["generator"])
    stable["generator"]["generated_at"] = "<timestamp>"
    return stable


def test_scan_repo_builds_schema_valid_deterministic_map(tmp_path: Path) -> None:
    project = _make_sample_repo(tmp_path)

    first = scan_repo(project)
    second = scan_repo(project)

    validate_repo_map(first)
    assert _stable_repo_map(first) == _stable_repo_map(second)
    assert first["project"]["name"] == "sample-project"
    assert first["summary"]["included_files"] >= 5
    assert first["languages"]["python"] == 4
    assert first["languages"]["markdown"] == 1


def test_scan_repo_uses_repo_relative_posix_paths_and_ignores_defaults(tmp_path: Path) -> None:
    project = _make_sample_repo(tmp_path)

    repo_map = scan_repo(project)
    paths = [item["path"] for item in repo_map["files"]]
    ignored_paths = [item["path"] for item in repo_map["ignored"]["paths"]]

    assert paths == sorted(paths)
    assert "pkg/module.py" in paths
    assert all(not path.startswith("/") for path in paths)
    assert all("\\" not in path for path in paths)
    assert ".git" in ignored_paths
    assert ".ao" in ignored_paths
    assert "__pycache__" in ignored_paths
    assert "build" in ignored_paths


def test_scan_repo_finds_python_candidates_and_entrypoints_without_ast(tmp_path: Path) -> None:
    project = _make_sample_repo(tmp_path)

    repo_map = scan_repo(project)
    candidates = {(item["kind"], item["module"]) for item in repo_map["python"]["candidates"]}
    entrypoints = {(item["kind"], item["name"], item["path"]) for item in repo_map["python"]["entrypoints"]}

    assert ("package", "pkg") in candidates
    assert ("module", "pkg.module") in candidates
    assert ("module", "pkg.cli") in candidates
    assert ("python_file", "cli", "pkg/cli.py") in entrypoints
    assert ("python_file", "tool", "scripts/tool.py") in entrypoints
    assert ("console_script", "sample", "pyproject.toml") in entrypoints


def test_scan_repo_does_not_follow_symlinks(tmp_path: Path) -> None:
    project = _make_sample_repo(tmp_path)

    repo_map = scan_repo(project)
    diagnostic_codes = {item["code"] for item in repo_map["diagnostics"]}
    file_paths = {item["path"] for item in repo_map["files"]}

    assert "linked.py" not in file_paths
    assert "symlink_skipped" in diagnostic_codes
