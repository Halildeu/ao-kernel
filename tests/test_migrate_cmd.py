"""Tests for ao_kernel.migrate_cmd — workspace migration."""

from __future__ import annotations

import json
from pathlib import Path

from ao_kernel.migrate_cmd import run


class TestMigrateCmd:
    def test_up_to_date(self, tmp_workspace: Path, capsys):
        rc = run()
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "UP_TO_DATE"
        assert out["mutations"] == []
        assert out["backup_skipped"] == "no_mutations"

    def test_dry_run(self, tmp_workspace: Path, capsys):
        rc = run(dry_run=True)
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["dry_run"] is True

    def test_no_workspace(self, empty_dir: Path, capsys):
        rc = run()
        assert rc == 1
        assert "bulunamadi" in capsys.readouterr().out.lower()

    def test_version_mismatch_triggers_migration(self, tmp_workspace: Path, capsys):
        ws_json = tmp_workspace / "workspace.json"
        data = json.loads(ws_json.read_text())
        data["version"] = "0.0.1"
        ws_json.write_text(json.dumps(data))

        rc = run(dry_run=True)
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "MIGRATION_NEEDED"
        assert len(out["mutations"]) > 0
        assert out["mutations"][0]["type"] == "version_update"

    def test_backup_on_migration(self, tmp_workspace: Path, capsys):
        ws_json = tmp_workspace / "workspace.json"
        data = json.loads(ws_json.read_text())
        data["version"] = "0.0.1"
        ws_json.write_text(json.dumps(data))

        rc = run(backup=True)
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "MIGRATED"
        assert "backup_path" in out

        updated = json.loads(ws_json.read_text())
        assert updated["version"] == "0.1.0"
        assert "migrated_at" in updated

    def test_legacy_workspace_detected(self, legacy_workspace: Path, capsys):
        rc = run(dry_run=True)
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["legacy_workspace_detected"] is True
