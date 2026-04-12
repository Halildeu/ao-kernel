"""Tests for ao_kernel.cli — CLI entrypoint."""

from __future__ import annotations

from ao_kernel.cli import main


class TestCli:
    def test_version(self, capsys):
        rc = main(["version"])
        assert rc == 0
        assert "0.1.0" in capsys.readouterr().out

    def test_no_command_prints_help(self, capsys):
        rc = main([])
        assert rc == 0
        out = capsys.readouterr().out
        assert "ao-kernel" in out

    def test_init_creates_workspace(self, empty_dir, capsys):
        rc = main(["init"])
        assert rc == 0
        assert (empty_dir / ".ao" / "workspace.json").is_file()

    def test_init_idempotent(self, tmp_workspace, capsys):
        rc = main(["init"])
        assert rc == 0
        assert "zaten mevcut" in capsys.readouterr().out

    def test_doctor_with_workspace(self, tmp_workspace, capsys):
        rc = main(["doctor"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "OK" in out

    def test_migrate_dry_run(self, tmp_workspace, capsys):
        rc = main(["migrate", "--dry-run"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "UP_TO_DATE" in out

    def test_migrate_no_workspace(self, empty_dir, capsys):
        rc = main(["migrate"])
        assert rc == 1
        assert "bulunamadi" in capsys.readouterr().out.lower()

    def test_workspace_root_override(self, tmp_workspace, capsys):
        rc = main(["--workspace-root", str(tmp_workspace), "doctor"])
        assert rc == 0
