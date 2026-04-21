"""Tests for ao_kernel.init_cmd — workspace initialization."""

from __future__ import annotations

import json
from pathlib import Path

from ao_kernel.init_cmd import run


class TestInitCmd:
    def test_creates_workspace(self, empty_dir: Path):
        rc = run()
        assert rc == 0
        ws = empty_dir / ".ao"
        assert ws.is_dir()
        assert (ws / "workspace.json").is_file()
        assert (ws / "policies").is_dir()
        assert (ws / "schemas").is_dir()
        assert (ws / "registry").is_dir()
        assert (ws / "extensions").is_dir()

    def test_workspace_json_content(self, empty_dir: Path):
        run()
        data = json.loads((empty_dir / ".ao" / "workspace.json").read_text())
        
        import ao_kernel
        assert data["version"] == ao_kernel.__version__
        assert data["kind"] == "ao-workspace"
        assert "created_at" in data

    def test_idempotent(self, tmp_workspace: Path):
        rc = run()
        assert rc == 0

    def test_project_root_override_creates_nested_ao_workspace(self, tmp_path: Path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        rc = run(workspace_root_override=str(project_root))
        assert rc == 0
        assert (project_root / ".ao" / "workspace.json").is_file()
        assert not (project_root / "workspace.json").exists()

    def test_explicit_ao_override_still_writes_directly(self, tmp_path: Path):
        ao_dir = tmp_path / "project" / ".ao"
        rc = run(workspace_root_override=str(ao_dir))
        assert rc == 0
        assert (ao_dir / "workspace.json").is_file()

    def test_existing_workspace_dir_override_is_idempotent(self, tmp_path: Path, capsys):
        ao_dir = tmp_path / "project" / ".ao"
        rc1 = run(workspace_root_override=str(ao_dir))
        assert rc1 == 0
        capsys.readouterr()

        rc2 = run(workspace_root_override=str(tmp_path / "project"))
        assert rc2 == 0
        out = capsys.readouterr().out
        assert "already exists" in out.lower()
