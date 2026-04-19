"""v3.12 H3 (coverage tranche 6) — `_internal/session/agent_context_version.py` pins.

Module was 75% covered transitively; this file pins the missing
error/edge branches so the module can move out of
`coverage.run.omit`:

- `_file_hash` exception branch (read fails mid-operation)
- `_file_modified_at` exception branch (stat fails)
- `compute_agent_context_version` extra_files extension + size/modified
  metadata population + agent_tag attach
- `verify_agent_context_version` non-dict file-entry skip + stale_files
  accumulation + first-run (`previous=None`) short-circuit
- `load_agent_context_version` missing file → None and malformed JSON → None

Mirrors v3.8 H1 / v3.9 M1 / v3.11 P3/P4 tranche patterns: small,
mechanical, no production code change. `cross_session_context.py` and
`provider_memory.py` (very low transitive coverage) stay omitted;
they're candidated for dedicated v3.13 tranches H3b/H3c.
"""

from __future__ import annotations

from pathlib import Path


def _write(path: Path, body: str = "content\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


class TestFileHashAndModifiedErrorBranches:
    def test_file_hash_on_read_error_returns_empty_triple(self, tmp_path: Path) -> None:
        # Make the path resolve to a directory — read_bytes() raises
        # IsADirectoryError, which the helper swallows and returns
        # the zero-triple.
        from ao_kernel._internal.session.agent_context_version import _file_hash

        dir_path = tmp_path / "notafile"
        dir_path.mkdir()
        result = _file_hash(dir_path)
        assert result == ("", False, 0)

    def test_file_modified_at_on_stat_error_returns_empty(self, tmp_path: Path) -> None:
        from ao_kernel._internal.session.agent_context_version import (
            _file_modified_at,
        )

        # Path that does not exist → stat raises → guarded branch returns "".
        result = _file_modified_at(tmp_path / "does-not-exist")
        assert result == ""


class TestComputeAgentContextVersion:
    def test_extra_files_extend_tracked_list(self, tmp_path: Path) -> None:
        from ao_kernel._internal.session.agent_context_version import (
            compute_agent_context_version,
        )

        extra = tmp_path / "custom/policy.json"
        _write(extra, '{"x": 1}\n')
        record = compute_agent_context_version(
            workspace_root=tmp_path,
            extra_files=["custom/policy.json"],
        )
        paths = [f["path"] for f in record["files"]]
        assert "custom/policy.json" in paths
        # The bundled bootstrap files are still tracked.
        assert any(p == "AGENTS.md" for p in paths)

    def test_existing_file_records_size_and_modified_at(self, tmp_path: Path) -> None:
        from ao_kernel._internal.session.agent_context_version import (
            compute_agent_context_version,
        )

        probe = tmp_path / "AGENTS.md"
        _write(probe, "hello agents\n")
        record = compute_agent_context_version(workspace_root=tmp_path)
        agents_entry = next(f for f in record["files"] if f["path"] == "AGENTS.md")
        assert agents_entry["exists"] is True
        assert agents_entry["size_bytes"] == len("hello agents\n")
        assert "modified_at" in agents_entry

    def test_agent_tag_attached_when_non_empty(self, tmp_path: Path) -> None:
        from ao_kernel._internal.session.agent_context_version import (
            compute_agent_context_version,
        )

        record = compute_agent_context_version(workspace_root=tmp_path, agent_tag="sdk-unit-test")
        assert record["agent_tag"] == "sdk-unit-test"


class TestVerifyAgentContextVersion:
    def test_previous_none_short_circuits_to_current(self, tmp_path: Path) -> None:
        from ao_kernel._internal.session.agent_context_version import (
            verify_agent_context_version,
        )

        # No persisted record and no explicit previous → function
        # returns the freshly computed record without a stale marker.
        record = verify_agent_context_version(workspace_root=tmp_path)
        assert record["status"] == "CURRENT"
        assert record["stale_files"] == []

    def test_changed_file_marks_stale(self, tmp_path: Path) -> None:
        from ao_kernel._internal.session.agent_context_version import (
            compute_agent_context_version,
            verify_agent_context_version,
        )

        probe = tmp_path / "AGENTS.md"
        _write(probe, "v1\n")
        snapshot = compute_agent_context_version(workspace_root=tmp_path)
        # Mutate the file.
        _write(probe, "v2\n")
        new_record = verify_agent_context_version(workspace_root=tmp_path, previous=snapshot)
        assert new_record["status"] == "STALE_CONTEXT"
        assert "AGENTS.md" in new_record["stale_files"]

    def test_non_dict_file_entry_is_skipped(self, tmp_path: Path) -> None:
        from ao_kernel._internal.session.agent_context_version import (
            verify_agent_context_version,
        )

        # Pre-PR records may carry a non-dict entry (e.g. a raw path
        # string) in ``files``; the verifier must not crash.
        previous = {
            "version": "v1",
            "files": ["AGENTS.md", {"path": "AGENTS.md", "sha256": ""}],
        }
        new_record = verify_agent_context_version(workspace_root=tmp_path, previous=previous)
        # Non-dict entry silently skipped; run still produces CURRENT
        # (no matching path → no stale marker).
        assert new_record["status"] == "CURRENT"


class TestLoadAgentContextVersion:
    def test_returns_none_when_file_absent(self, tmp_path: Path) -> None:
        from ao_kernel._internal.session.agent_context_version import (
            load_agent_context_version,
        )

        # Clean workspace, no persisted record.
        assert load_agent_context_version(workspace_root=tmp_path) is None

    def test_returns_none_on_malformed_json(self, tmp_path: Path) -> None:
        from ao_kernel._internal.session.agent_context_version import (
            load_agent_context_version,
        )

        # Write garbage JSON at the expected output path.
        target = tmp_path.resolve() / ".cache/index/agent_context_version.v1.json"
        _write(target, "{not valid json")
        assert load_agent_context_version(workspace_root=tmp_path) is None

    def test_roundtrip_write_then_load(self, tmp_path: Path) -> None:
        from ao_kernel._internal.session.agent_context_version import (
            compute_agent_context_version,
            load_agent_context_version,
            write_agent_context_version,
        )

        record = compute_agent_context_version(workspace_root=tmp_path, agent_tag="roundtrip")
        rel = write_agent_context_version(workspace_root=tmp_path, record=record)
        assert rel == ".cache/index/agent_context_version.v1.json"

        reloaded = load_agent_context_version(workspace_root=tmp_path)
        assert reloaded is not None
        assert reloaded["agent_tag"] == "roundtrip"
        assert reloaded["aggregate_sha256"] == record["aggregate_sha256"]
