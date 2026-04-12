"""Tests for ao_kernel.cli — CLI entrypoint with behavioral verification."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from ao_kernel.cli import main


class TestVersion:
    def test_version_format(self, capsys):
        rc = main(["version"])
        assert rc == 0
        out = capsys.readouterr().out.strip()
        assert re.match(r"^ao-kernel \d+\.\d+\.\d+$", out)

    def test_version_matches_package(self, capsys):
        import ao_kernel
        main(["version"])
        out = capsys.readouterr().out.strip()
        assert ao_kernel.__version__ in out


class TestHelp:
    def test_no_command_shows_subcommands(self, capsys):
        rc = main([])
        assert rc == 0
        out = capsys.readouterr().out
        for cmd in ("init", "migrate", "doctor", "version", "mcp"):
            assert cmd in out


class TestInit:
    def test_creates_workspace_directory(self, empty_dir):
        rc = main(["init"])
        assert rc == 0
        ws = empty_dir / ".ao"
        assert ws.is_dir()
        assert (ws / "workspace.json").is_file()
        assert (ws / "policies").is_dir()
        assert (ws / "schemas").is_dir()
        assert (ws / "registry").is_dir()
        assert (ws / "extensions").is_dir()

    def test_workspace_json_has_required_fields(self, empty_dir):
        main(["init"])
        data = json.loads((empty_dir / ".ao" / "workspace.json").read_text())
        assert data["version"] == "0.1.0"
        assert data["kind"] == "ao-workspace"
        assert "created_at" in data

    def test_idempotent_no_error(self, tmp_workspace, capsys):
        rc = main(["init"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "mevcut" in out.lower()


class TestDoctor:
    def test_all_checks_pass_with_workspace(self, tmp_workspace, capsys):
        rc = main(["doctor"])
        assert rc == 0
        out = capsys.readouterr().out
        lines = [l for l in out.splitlines() if l.strip().startswith("[")]
        fail_lines = [l for l in lines if "[!]" in l]
        assert len(fail_lines) == 0
        assert len(lines) >= 7  # At least 7 check lines


class TestMigrate:
    def test_dry_run_returns_valid_json(self, tmp_workspace, capsys):
        rc = main(["migrate", "--dry-run"])
        assert rc == 0
        report = json.loads(capsys.readouterr().out)
        assert report["status"] == "UP_TO_DATE"
        assert report["dry_run"] is True
        assert isinstance(report["mutations"], list)
        assert "workspace_version" in report
        assert "package_version" in report

    def test_no_workspace_returns_error(self, empty_dir, capsys):
        rc = main(["migrate"])
        assert rc == 1
        out = capsys.readouterr().out.lower()
        assert "bulunamadi" in out or "not found" in out

    def test_workspace_root_override(self, tmp_workspace, capsys):
        rc = main(["--workspace-root", str(tmp_workspace), "doctor"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "ao-kernel doctor" in out


class TestMcpSubcommand:
    def test_mcp_no_subcommand_shows_usage(self, capsys):
        rc = main(["mcp"])
        assert rc == 1
        out = capsys.readouterr().out
        assert "mcp" in out.lower()
