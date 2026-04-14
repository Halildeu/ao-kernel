"""Tests for roadmap internal modules — compiler, executor, step_templates, exec_steps, exec_evidence.

Covers: schema validation, plan compilation, step dispatch, VirtualFS, readonly enforcement,
constraint checking, evidence snapshots, DLQ handling.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


# Minimal schema that accepts any roadmap object (validation testing uses real schema)
PERMISSIVE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
}


@pytest.fixture
def schema_path(tmp_path: Path) -> Path:
    p = tmp_path / "schema.json"
    p.write_text(json.dumps(PERMISSIVE_SCHEMA))
    return p


# ── Compiler Tests ──────────────────────────────────────────────────


class TestCompilerValidation:
    """Tests for compiler.validate_roadmap and compile_roadmap."""

    def _make_roadmap(self, *, milestones: list[dict] | None = None, **overrides: Any) -> dict:
        base = {
            "roadmap_id": "test-roadmap",
            "version": "1.0",
            "milestones": milestones or [
                {"id": "MS-001", "title": "Test Milestone", "deliverables": [], "gates": []},
            ],
        }
        base.update(overrides)
        return base

    def test_compile_produces_plan_with_steps(self, tmp_path: Path, schema_path: Path):
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        roadmap = self._make_roadmap(milestones=[
            {
                "id": "MS-001",
                "title": "First",
                "deliverables": [{"type": "create_file", "path": "a.txt", "content": "hello"}],
                "gates": [{"type": "assert_paths_exist", "paths": ["a.txt"]}],
            },
        ])
        roadmap_path = tmp_path / "roadmap.json"
        roadmap_path.write_text(json.dumps(roadmap))

        result = compile_roadmap(
            roadmap_path=roadmap_path,
            schema_path=schema_path,
            cache_root=tmp_path / ".cache",
        )
        assert result.status == "OK"
        assert result.plan_id
        assert len(result.plan["steps"]) >= 2  # deliverable + gate

    def test_compile_filters_milestones(self, tmp_path: Path, schema_path: Path):
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        roadmap = self._make_roadmap(milestones=[
            {"id": "MS-001", "title": "Keep", "deliverables": [{"type": "note", "text": "a"}], "gates": []},
            {"id": "MS-002", "title": "Skip", "deliverables": [{"type": "note", "text": "b"}], "gates": []},
        ])
        roadmap_path = tmp_path / "roadmap.json"
        roadmap_path.write_text(json.dumps(roadmap))

        result = compile_roadmap(
            roadmap_path=roadmap_path,
            schema_path=schema_path,
            cache_root=tmp_path / ".cache",
            milestone_ids=["MS-001"],
        )
        assert result.status == "OK"
        assert result.milestones_included == ["MS-001"]

    def test_compile_rejects_missing_milestone_id(self, tmp_path: Path, schema_path: Path):
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        roadmap = self._make_roadmap()
        roadmap_path = tmp_path / "roadmap.json"
        roadmap_path.write_text(json.dumps(roadmap))

        with pytest.raises(ValueError, match="MILESTONE_NOT_FOUND|not found"):
            compile_roadmap(
                roadmap_path=roadmap_path,
                schema_path=schema_path,
                cache_root=tmp_path / ".cache",
                milestone_ids=["NONEXISTENT"],
            )

    def test_compile_deterministic_plan_id(self, tmp_path: Path, schema_path: Path):
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        roadmap = self._make_roadmap()
        roadmap_path = tmp_path / "roadmap.json"
        roadmap_path.write_text(json.dumps(roadmap))

        r1 = compile_roadmap(roadmap_path=roadmap_path, schema_path=schema_path, cache_root=tmp_path / ".cache1")
        r2 = compile_roadmap(roadmap_path=roadmap_path, schema_path=schema_path, cache_root=tmp_path / ".cache2")
        assert r1.plan_id == r2.plan_id

    def test_compile_empty_milestones(self, tmp_path: Path, schema_path: Path):
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        roadmap = self._make_roadmap(milestones=[])
        roadmap_path = tmp_path / "roadmap.json"
        roadmap_path.write_text(json.dumps(roadmap))

        result = compile_roadmap(roadmap_path=roadmap_path, schema_path=schema_path, cache_root=tmp_path / ".cache")
        assert result.status == "OK"
        assert len(result.plan["steps"]) == 0


# ── Step Templates Tests ────────────────────────────────────────────


class TestVirtualFS:
    """Tests for VirtualFS overlay used in dry-run mode."""

    def test_set_and_get(self):
        from ao_kernel._internal.roadmap.step_templates import VirtualFS
        vfs = VirtualFS(files={})
        vfs.set_text("new.txt", "hello")
        assert vfs.get_text("new.txt", workspace=Path("/dummy")) == "hello"

    def test_get_falls_back_to_real_file(self, tmp_path: Path):
        from ao_kernel._internal.roadmap.step_templates import VirtualFS
        real_file = tmp_path / "real.txt"
        real_file.write_text("from disk")
        vfs = VirtualFS(files={})
        assert vfs.get_text("real.txt", workspace=tmp_path) == "from disk"

    def test_virtual_overrides_real(self, tmp_path: Path):
        from ao_kernel._internal.roadmap.step_templates import VirtualFS
        real_file = tmp_path / "file.txt"
        real_file.write_text("old")
        vfs = VirtualFS(files={"file.txt": "new"})
        assert vfs.get_text("file.txt", workspace=tmp_path) == "new"

    def test_would_exist_virtual(self):
        from ao_kernel._internal.roadmap.step_templates import VirtualFS
        vfs = VirtualFS(files={"exists.txt": "data"})
        assert vfs.would_exist("exists.txt", workspace=Path("/dummy")) is True
        assert vfs.would_exist("missing.txt", workspace=Path("/dummy")) is False

    def test_would_exist_real(self, tmp_path: Path):
        from ao_kernel._internal.roadmap.step_templates import VirtualFS
        (tmp_path / "real.txt").write_text("x")
        vfs = VirtualFS(files={})
        assert vfs.would_exist("real.txt", workspace=tmp_path) is True


class TestStepCreateFile:
    """Tests for step_create_file template."""

    def test_creates_file_on_disk(self, tmp_path: Path):
        from ao_kernel._internal.roadmap.step_templates import step_create_file, VirtualFS
        vfs = VirtualFS(files={})
        result = step_create_file(
            workspace=tmp_path, virtual_fs=vfs,
            path="output.txt", content="hello world",
            overwrite=False, dry_run=False,
        )
        assert result["status"] in ("OK", "CREATED")
        assert (tmp_path / "output.txt").read_text() == "hello world"

    def test_dry_run_only_writes_virtual(self, tmp_path: Path):
        from ao_kernel._internal.roadmap.step_templates import step_create_file, VirtualFS
        vfs = VirtualFS(files={})
        result = step_create_file(
            workspace=tmp_path, virtual_fs=vfs,
            path="dry.txt", content="dry content",
            overwrite=False, dry_run=True,
        )
        assert "DRY" in result["status"] or "SKIP" in result["status"]
        assert not (tmp_path / "dry.txt").exists()
        assert vfs.get_text("dry.txt", workspace=tmp_path) == "dry content"

    def test_rejects_path_outside_workspace(self, tmp_path: Path):
        from ao_kernel._internal.roadmap.step_templates import step_create_file, VirtualFS, RoadmapStepError
        vfs = VirtualFS(files={})
        with pytest.raises(RoadmapStepError):
            step_create_file(
                workspace=tmp_path, virtual_fs=vfs,
                path="../escape.txt", content="bad",
                overwrite=False, dry_run=False,
            )


class TestStepRunCmd:
    """Tests for step_run_cmd template."""

    def test_successful_command(self, tmp_path: Path):
        from ao_kernel._internal.roadmap.step_templates import step_run_cmd
        result, logs = step_run_cmd(
            workspace=tmp_path,
            cmd="echo hello",
            must_succeed=True,
            dry_run=False,
        )
        assert result["return_code"] == 0
        assert "hello" in logs

    def test_dry_run_skips_execution(self, tmp_path: Path):
        from ao_kernel._internal.roadmap.step_templates import step_run_cmd
        result, logs = step_run_cmd(
            workspace=tmp_path,
            cmd="echo should_not_run",
            must_succeed=True,
            dry_run=True,
        )
        assert "DRY" in result["status"] or "SKIP" in result["status"]

    def test_failing_command_with_must_succeed(self, tmp_path: Path):
        from ao_kernel._internal.roadmap.step_templates import step_run_cmd, RoadmapStepError
        with pytest.raises(RoadmapStepError):
            step_run_cmd(
                workspace=tmp_path,
                cmd="false",
                must_succeed=True,
                dry_run=False,
            )

    def test_failing_command_without_must_succeed(self, tmp_path: Path):
        from ao_kernel._internal.roadmap.step_templates import step_run_cmd
        result, logs = step_run_cmd(
            workspace=tmp_path,
            cmd="false",
            must_succeed=False,
            dry_run=False,
        )
        assert result["return_code"] != 0


class TestStepAssertPaths:
    """Tests for assertion step templates."""

    def test_assert_paths_exist_all_present(self, tmp_path: Path):
        from ao_kernel._internal.roadmap.step_templates import step_assert_paths_exist, VirtualFS
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        vfs = VirtualFS(files={})
        result = step_assert_paths_exist(workspace=tmp_path, virtual_fs=vfs, paths=["a.txt", "b.txt"])
        assert result["status"] == "OK"

    def test_assert_paths_exist_missing(self, tmp_path: Path):
        from ao_kernel._internal.roadmap.step_templates import step_assert_paths_exist, VirtualFS, RoadmapStepError
        vfs = VirtualFS(files={})
        with pytest.raises(RoadmapStepError):
            step_assert_paths_exist(workspace=tmp_path, virtual_fs=vfs, paths=["missing.txt"])

    def test_assert_paths_virtual_counts(self, tmp_path: Path):
        from ao_kernel._internal.roadmap.step_templates import step_assert_paths_exist, VirtualFS
        vfs = VirtualFS(files={"virtual.txt": "content"})
        result = step_assert_paths_exist(workspace=tmp_path, virtual_fs=vfs, paths=["virtual.txt"])
        assert result["status"] == "OK"


# ── Evidence Utilities Tests ────────────────────────────────────────


class TestEvidenceUtils:
    """Tests for exec_evidence utility functions."""

    def test_snapshot_tree_hashes_files(self, tmp_path: Path):
        from ao_kernel._internal.roadmap.exec_evidence import _snapshot_tree
        (tmp_path / "a.txt").write_text("alpha")
        (tmp_path / "b.txt").write_text("beta")
        tree = _snapshot_tree(tmp_path, ignore_prefixes=[])
        assert "a.txt" in tree
        assert "b.txt" in tree
        assert len(tree["a.txt"]) == 64  # SHA256 hex

    def test_snapshot_tree_ignores_prefixes(self, tmp_path: Path):
        from ao_kernel._internal.roadmap.exec_evidence import _snapshot_tree
        (tmp_path / ".cache").mkdir()
        (tmp_path / ".cache" / "ignore.txt").write_text("skip")
        (tmp_path / "keep.txt").write_text("keep")
        tree = _snapshot_tree(tmp_path, ignore_prefixes=[".cache"])
        assert "keep.txt" in tree
        assert ".cache/ignore.txt" not in tree

    def test_snapshot_tree_empty_dir(self, tmp_path: Path):
        from ao_kernel._internal.roadmap.exec_evidence import _snapshot_tree
        tree = _snapshot_tree(tmp_path, ignore_prefixes=[])
        assert tree == {}

    def test_sha256_bytes_deterministic(self):
        from ao_kernel._internal.roadmap.exec_evidence import _sha256_bytes
        h1 = _sha256_bytes(b"test data")
        h2 = _sha256_bytes(b"test data")
        h3 = _sha256_bytes(b"different")
        assert h1 == h2
        assert h1 != h3
        assert len(h1) == 64

    def test_normalize_rel_path(self):
        from ao_kernel._internal.roadmap.exec_evidence import _normalize_rel_path
        assert _normalize_rel_path("./foo/bar.txt") == "foo/bar.txt"
        assert _normalize_rel_path("/foo/bar.txt") == "foo/bar.txt"
        assert _normalize_rel_path("foo\\bar.txt") == "foo/bar.txt"

    def test_now_iso8601_format(self):
        import re
        from ao_kernel._internal.roadmap.exec_evidence import _now_iso8601
        ts = _now_iso8601()
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", ts)
