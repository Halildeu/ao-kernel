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

    def test_custom_root(self, tmp_path: Path):
        custom = tmp_path / "custom_ws"
        custom.mkdir()
        rc = run(workspace_root_override=str(custom))
        assert rc == 0
        assert (custom / "workspace.json").is_file()
