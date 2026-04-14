"""Coverage tests for ao_kernel.workspace facade.

Targets PR-C4: bring ``workspace.py`` branch coverage from ~66% to
85% so the ratchet gate can rise to 85. The facade is thin — tests
exercise the ``load_config`` auto-resolve path, ``doctor``, and
``migrate`` entry points, each monkey-patched so CLI subprocesses
do not actually run.
"""

from __future__ import annotations

import json
from pathlib import Path

from ao_kernel import workspace as ws_mod


class TestLoadConfig:
    def test_returns_empty_when_no_workspace(self, monkeypatch, tmp_path: Path):
        monkeypatch.chdir(tmp_path)
        from ao_kernel import config as cfg_mod
        monkeypatch.setattr(cfg_mod, "workspace_root", lambda override=None: None)
        assert ws_mod.load_config() == {}

    def test_loads_workspace_json_when_present(self, monkeypatch, tmp_path: Path):
        ao_dir = tmp_path / ".ao"
        ao_dir.mkdir()
        (ao_dir / "workspace.json").write_text(
            json.dumps({"version": "v1", "kind": "repo", "root": str(tmp_path)}),
            encoding="utf-8",
        )
        from ao_kernel import config as cfg_mod
        monkeypatch.setattr(cfg_mod, "workspace_root", lambda override=None: ao_dir)
        assert ws_mod.load_config()["kind"] == "repo"


class TestDoctorEntry:
    def test_delegates_to_doctor_cmd(self, monkeypatch):
        called: dict[str, object] = {}

        def _fake_run(*, workspace_root_override=None):
            called["ws"] = workspace_root_override
            return 0

        from ao_kernel import doctor_cmd as doctor_mod
        monkeypatch.setattr(doctor_mod, "run", _fake_run)
        assert ws_mod.doctor(workspace_root_override="/tmp/ws") == 0
        assert called["ws"] == "/tmp/ws"


class TestMigrateEntry:
    def test_delegates_to_migrate_cmd(self, monkeypatch):
        captured: dict[str, object] = {}

        def _fake_run(*, workspace_root_override=None, dry_run=False, backup=False):
            captured["ws"] = workspace_root_override
            captured["dry"] = dry_run
            captured["backup"] = backup
            return 0

        from ao_kernel import migrate_cmd as migrate_mod
        monkeypatch.setattr(migrate_mod, "run", _fake_run)
        assert (
            ws_mod.migrate(
                workspace_root_override="/tmp/ws", dry_run=True, backup=True,
            )
            == 0
        )
        assert captured["ws"] == "/tmp/ws"
        assert captured["dry"] is True
        assert captured["backup"] is True
