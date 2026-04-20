"""v3.13.1 P1 — ``resolve_workspace_dir`` tolerant normalization.

Pins the new helper exposed from :mod:`ao_kernel.config` that gives
``load_workspace_json`` (and by extension doctor / migrate /
workspace_status MCP tool) a single normalization contract:

- Accept **project root** where workspace.json lives under ``.ao/``.
- Accept **workspace directory** directly (legacy / explicit
  ``--workspace-root .ao`` usage).
- Return the argument unchanged when neither shape matches so the
  downstream caller can fail-closed with the user-supplied path in
  the message.

This closes the `doctor --workspace-root .` fail path without
changing the ``workspace_root(override=...)`` or ``init_cmd.run``
contracts (those stay non-breaking; operators that explicitly point
at ``.ao`` keep working).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


_WS_PAYLOAD = {"version": "3.13.0", "kind": "ao-workspace"}


def _write_ws_json(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "workspace.json"
    path.write_text(json.dumps(_WS_PAYLOAD), encoding="utf-8")
    return path


class TestResolveWorkspaceDirShape:
    def test_project_root_with_ao_subdir_resolves_to_ao(self, tmp_path: Path) -> None:
        from ao_kernel.config import resolve_workspace_dir

        ao_dir = tmp_path / ".ao"
        _write_ws_json(ao_dir)
        resolved = resolve_workspace_dir(tmp_path)
        assert resolved == ao_dir

    def test_workspace_dir_directly_returned_unchanged(self, tmp_path: Path) -> None:
        from ao_kernel.config import resolve_workspace_dir

        ao_dir = tmp_path / ".ao"
        _write_ws_json(ao_dir)
        # Caller passes the .ao dir explicitly → return as-is.
        resolved = resolve_workspace_dir(ao_dir)
        assert resolved == ao_dir

    def test_neither_shape_returns_input_unchanged(self, tmp_path: Path) -> None:
        from ao_kernel.config import resolve_workspace_dir

        # No workspace.json anywhere → return input path resolved so
        # downstream error message carries the user-supplied path.
        resolved = resolve_workspace_dir(tmp_path)
        assert resolved == tmp_path

    def test_accepts_string_input(self, tmp_path: Path) -> None:
        from ao_kernel.config import resolve_workspace_dir

        ao_dir = tmp_path / ".ao"
        _write_ws_json(ao_dir)
        resolved = resolve_workspace_dir(str(tmp_path))
        assert resolved == ao_dir

    def test_project_root_direct_workspace_json_takes_precedence(self, tmp_path: Path) -> None:
        """Edge case: if project root contains both ``workspace.json``
        AND ``.ao/workspace.json`` (legacy installs may have this),
        the direct workspace.json wins — the assumption is the caller
        already normalized explicitly."""
        from ao_kernel.config import resolve_workspace_dir

        _write_ws_json(tmp_path)
        _write_ws_json(tmp_path / ".ao")
        assert resolve_workspace_dir(tmp_path) == tmp_path


class TestLoadWorkspaceJsonIntegration:
    def test_project_root_override_now_loads_ao_workspace(self, tmp_path: Path) -> None:
        """Core fix: ``load_workspace_json(project_root)`` used to
        raise ``WorkspaceCorruptedError`` because it looked at
        ``<project_root>/workspace.json``. After P1 it descends into
        ``<project_root>/.ao/workspace.json`` transparently.
        """
        from ao_kernel.config import load_workspace_json

        _write_ws_json(tmp_path / ".ao")
        data = load_workspace_json(tmp_path)
        assert data["version"] == "3.13.0"
        assert data["kind"] == "ao-workspace"

    def test_workspace_dir_override_still_works(self, tmp_path: Path) -> None:
        """Back-compat: operators who pass the ``.ao`` dir explicitly
        keep working — the helper returns them unchanged."""
        from ao_kernel.config import load_workspace_json

        ao_dir = tmp_path / ".ao"
        _write_ws_json(ao_dir)
        data = load_workspace_json(ao_dir)
        assert data["version"] == "3.13.0"

    def test_missing_workspace_fails_closed_with_user_path(self, tmp_path: Path) -> None:
        """If neither shape matches, the error message must reference
        the user-supplied path (not the normalized one) so operators
        can reason about what they typed."""
        from ao_kernel.config import WorkspaceCorruptedError, load_workspace_json

        with pytest.raises(WorkspaceCorruptedError, match="workspace.json not found"):
            load_workspace_json(tmp_path)

    def test_malformed_workspace_json_still_fails(self, tmp_path: Path) -> None:
        from ao_kernel.config import WorkspaceCorruptedError, load_workspace_json

        ao_dir = tmp_path / ".ao"
        ao_dir.mkdir(parents=True)
        (ao_dir / "workspace.json").write_text("{not valid", encoding="utf-8")
        with pytest.raises(WorkspaceCorruptedError, match="not valid JSON"):
            load_workspace_json(tmp_path)


class TestDoctorIntegration:
    """Pin the end-to-end `doctor --workspace-root .` flow that
    motivated P1. Previously this sequence would report a FAIL on
    "workspace.json valid"; after the normalizer, it passes."""

    def test_doctor_check_workspace_json_accepts_project_root(self, tmp_path: Path) -> None:
        from ao_kernel.doctor_cmd import _check_workspace_json

        _write_ws_json(tmp_path / ".ao")
        # Real doctor call path (Codex iter-1 feedback: pin the actual
        # doctor_cmd helper, not a proxy through load_workspace_json).
        # _check_workspace_json invokes workspace_root(override) →
        # load_workspace_json(ws). With the P1 normalizer, project-root
        # override resolves into .ao/ transparently and the check
        # returns True.
        assert _check_workspace_json(str(tmp_path)) is True


class TestMigrateIntegration:
    """Codex iter-1 BLOCKER absorb: after P1 ``load_workspace_json``
    is path-tolerant, but migrate's mutation/backup/report paths must
    ALSO operate on the resolved workspace directory. Otherwise
    ``migrate --workspace-root <project_root>`` reads ``.ao/workspace.json``
    correctly but writes a fresh ``workspace.json`` next to the project
    root + a backup sibling in the wrong place."""

    def test_dry_run_mutation_file_targets_resolved_ao_dir(self, tmp_path: Path) -> None:
        """Dry-run report must carry the resolved ``.ao/workspace.json``
        mutation file path, not ``<project_root>/workspace.json``."""
        import ao_kernel
        from ao_kernel.migrate_cmd import run as migrate_run

        ao_dir = tmp_path / ".ao"
        ao_dir.mkdir(parents=True)
        # Force a version mismatch so a mutation is planned.
        stale_payload = {"version": "3.0.0", "kind": "ao-workspace"}
        (ao_dir / "workspace.json").write_text(json.dumps(stale_payload), encoding="utf-8")

        # Capture stdout report JSON.
        import io
        import sys as _sys

        buf = io.StringIO()
        saved = _sys.stdout
        _sys.stdout = buf
        try:
            rc = migrate_run(str(tmp_path), dry_run=True)
        finally:
            _sys.stdout = saved
        assert rc == 0
        report = json.loads(buf.getvalue())

        assert report["status"] == "MIGRATION_NEEDED"
        assert report["workspace_path"].endswith("/.ao")
        assert report["mutations"], "expected a version_update mutation"
        mutation_file = Path(report["mutations"][0]["file"])
        assert mutation_file == (ao_dir / "workspace.json").resolve()
        assert mutation_file.parent == ao_dir.resolve()
        assert report["mutations"][0]["to"] == ao_kernel.__version__

    def test_non_dry_run_writes_to_ao_workspace_json_and_backup_under_ao(self, tmp_path: Path) -> None:
        """Non-dry-run must mutate the resolved ``.ao/workspace.json``
        and stash the backup directory under ``.ao/.backup/``, not the
        project root."""
        import ao_kernel
        from ao_kernel.migrate_cmd import run as migrate_run

        ao_dir = tmp_path / ".ao"
        ao_dir.mkdir(parents=True)
        stale_payload = {"version": "3.0.0", "kind": "ao-workspace"}
        (ao_dir / "workspace.json").write_text(json.dumps(stale_payload), encoding="utf-8")

        import io
        import sys as _sys

        buf = io.StringIO()
        saved = _sys.stdout
        _sys.stdout = buf
        try:
            rc = migrate_run(str(tmp_path), dry_run=False, backup=True)
        finally:
            _sys.stdout = saved
        assert rc == 0
        report = json.loads(buf.getvalue())
        assert report["status"] == "MIGRATED"

        # Mutation happened in the resolved .ao dir.
        updated = json.loads((ao_dir / "workspace.json").read_text(encoding="utf-8"))
        assert updated["version"] == ao_kernel.__version__
        assert "migrated_at" in updated

        # Project root must NOT contain a stray workspace.json.
        assert not (tmp_path / "workspace.json").is_file()

        # Backup directory must live under resolved .ao/.backup/.
        assert "backup_path" in report
        backup_path = Path(report["backup_path"]).resolve()
        assert ao_dir.resolve() in backup_path.parents
        assert not (tmp_path / ".backup").is_dir()
