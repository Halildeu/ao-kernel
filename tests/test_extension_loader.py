"""Tests for extension loader and registry (B3, CNS-008)."""

from __future__ import annotations

import json
from pathlib import Path

from ao_kernel.extensions.loader import ExtensionRegistry, LoadReport


def _valid_manifest(ext_id: str, *, enabled: bool = True, **overrides: object) -> dict:
    """Helper — schema-conformant manifest skeleton."""
    base = {
        "version": "v1",
        "extension_id": ext_id,
        "semver": "1.0.0",
        "origin": "CUSTOMER",
        "owner": "CUSTOMER",
        "enabled": enabled,
        "layer_contract": {"write_roots_allowlist": []},
        "entrypoints": {"ops": [], "kernel_api_actions": [], "cockpit_sections": []},
        "policies": [],
        "ui_surfaces": [],
        "compat": {"core_min": "0.0.0", "core_max": "", "notes": []},
    }
    base.update(overrides)
    return base


class TestBundledDefaults:
    def test_load_from_defaults_returns_report(self):
        reg = ExtensionRegistry()
        report = reg.load_from_defaults()
        assert isinstance(report, LoadReport)
        assert report.loaded >= 15  # 18 bundled, a few may be skipped

    def test_get_known_extension(self):
        reg = ExtensionRegistry()
        reg.load_from_defaults()
        ext = reg.get("PRJ-KERNEL-API")
        assert ext is not None
        assert ext.extension_id == "PRJ-KERNEL-API"
        assert ext.version == "v1"
        # B3a: lossless parse — owner/ui_surfaces/compat must be populated.
        assert ext.owner in ("CORE", "CUSTOMER")
        assert isinstance(ext.ui_surfaces, list)
        assert "core_min" in ext.compat

    def test_manifest_carries_provenance(self):
        reg = ExtensionRegistry()
        reg.load_from_defaults()
        ext = reg.get("PRJ-KERNEL-API")
        assert ext is not None
        assert ext.source == "bundled"
        assert ext.manifest_path.endswith("extension.manifest.v1.json")
        # SHA256 hex == 64 chars.
        assert len(ext.content_hash) == 64

    def test_list_enabled_filters_disabled_and_blocked(self):
        reg = ExtensionRegistry()
        reg.load_from_defaults()
        for ext in reg.list_enabled():
            assert ext.enabled is True
            assert not ext.activation_blockers

    def test_find_by_entrypoint_airunner(self):
        reg = ExtensionRegistry()
        reg.load_from_defaults()
        results = reg.find_by_entrypoint("airunner-run")
        assert "PRJ-AIRUNNER" in [r.extension_id for r in results]

    def test_duplicate_entrypoints_recorded(self):
        """Bundled set has known duplicates: intake_* shared by PRJ-KERNEL-API / PRJ-WORK-INTAKE."""
        reg = ExtensionRegistry()
        reg.load_from_defaults()
        conflicts = reg.find_conflicts()
        entrypoints = {c.entrypoint for c in conflicts}
        assert "intake_create_plan" in entrypoints

    def test_first_wins_is_deterministic(self):
        """Sorted iteration guarantees the same winner across runs."""
        r1 = ExtensionRegistry()
        r1.load_from_defaults()
        r2 = ExtensionRegistry()
        r2.load_from_defaults()
        w1 = {c.entrypoint: c.winner for c in r1.find_conflicts()}
        w2 = {c.entrypoint: c.winner for c in r2.find_conflicts()}
        assert w1 == w2


class TestWorkspaceOverride:
    def test_load_from_workspace_reads_ao_extensions(self, tmp_path: Path):
        """B3e: workspace loader expects <project_root>/.ao/extensions/."""
        project_root = tmp_path
        ext_dir = project_root / ".ao" / "extensions" / "MY-EXT"
        ext_dir.mkdir(parents=True)
        (ext_dir / "extension.manifest.v1.json").write_text(
            json.dumps(_valid_manifest("MY-EXT")), encoding="utf-8",
        )
        reg = ExtensionRegistry()
        report = reg.load_from_workspace(project_root)
        assert report.loaded == 1
        ext = reg.get("MY-EXT")
        assert ext is not None
        assert ext.source == "workspace"

    def test_workspace_overrides_bundled(self, tmp_path: Path):
        """Same extension_id in workspace replaces bundled entry."""
        reg = ExtensionRegistry()
        reg.load_from_defaults()
        project_root = tmp_path
        ext_dir = project_root / ".ao" / "extensions" / "PRJ-AIRUNNER"
        ext_dir.mkdir(parents=True)
        overridden = _valid_manifest("PRJ-AIRUNNER", semver="9.9.9")
        (ext_dir / "extension.manifest.v1.json").write_text(
            json.dumps(overridden), encoding="utf-8",
        )
        reg.load_from_workspace(project_root)
        ext = reg.get("PRJ-AIRUNNER")
        assert ext is not None
        assert ext.semver == "9.9.9"
        assert ext.source == "workspace"

    def test_missing_workspace_dir_returns_zero(self, tmp_path: Path):
        reg = ExtensionRegistry()
        report = reg.load_from_workspace(tmp_path)  # no .ao/extensions present
        assert report.loaded == 0


class TestSchemaValidation:
    def test_invalid_manifest_is_skipped_with_report(self, tmp_path: Path):
        project_root = tmp_path
        ext_dir = project_root / ".ao" / "extensions" / "BROKEN"
        ext_dir.mkdir(parents=True)
        # Missing required fields.
        (ext_dir / "extension.manifest.v1.json").write_text(
            json.dumps({"extension_id": "BROKEN"}), encoding="utf-8",
        )
        reg = ExtensionRegistry()
        report = reg.load_from_workspace(project_root)
        assert report.loaded == 0
        assert len(report.skipped) == 1
        assert "schema_invalid" in report.skipped[0]["reason"]

    def test_json_parse_error_is_skipped_with_report(self, tmp_path: Path):
        project_root = tmp_path
        ext_dir = project_root / ".ao" / "extensions" / "GARBAGE"
        ext_dir.mkdir(parents=True)
        (ext_dir / "extension.manifest.v1.json").write_text("{not json")
        reg = ExtensionRegistry()
        report = reg.load_from_workspace(project_root)
        assert report.loaded == 0
        assert "json_error" in report.skipped[0]["reason"]


class TestCompatGating:
    def test_core_min_too_high_blocks_activation(self, tmp_path: Path):
        project_root = tmp_path
        ext_dir = project_root / ".ao" / "extensions" / "FUTURE-EXT"
        ext_dir.mkdir(parents=True)
        manifest = _valid_manifest(
            "FUTURE-EXT",
            compat={"core_min": "99.0.0", "core_max": "", "notes": []},
        )
        (ext_dir / "extension.manifest.v1.json").write_text(
            json.dumps(manifest), encoding="utf-8",
        )
        reg = ExtensionRegistry()
        reg.load_from_workspace(project_root)
        ext = reg.get("FUTURE-EXT")
        assert ext is not None
        # Present in list_all, absent from list_enabled.
        assert ext.extension_id in [e.extension_id for e in reg.list_all()]
        assert ext.extension_id not in [e.extension_id for e in reg.list_enabled()]
        assert any("core_min" in b for b in ext.activation_blockers)

    def test_compat_healthy_is_enabled(self, tmp_path: Path):
        project_root = tmp_path
        ext_dir = project_root / ".ao" / "extensions" / "OK-EXT"
        ext_dir.mkdir(parents=True)
        manifest = _valid_manifest(
            "OK-EXT",
            compat={"core_min": "0.0.0", "core_max": "999.0.0", "notes": []},
        )
        (ext_dir / "extension.manifest.v1.json").write_text(
            json.dumps(manifest), encoding="utf-8",
        )
        reg = ExtensionRegistry()
        reg.load_from_workspace(project_root)
        ext = reg.get("OK-EXT")
        assert ext is not None
        assert not ext.activation_blockers


class TestStaleRefs:
    def test_missing_ai_context_refs_flagged(self, tmp_path: Path):
        project_root = tmp_path
        ext_dir = project_root / ".ao" / "extensions" / "STALE-EXT"
        ext_dir.mkdir(parents=True)
        manifest = _valid_manifest(
            "STALE-EXT",
            ai_context_refs=["nonexistent/file.md", "also-missing.txt"],
        )
        (ext_dir / "extension.manifest.v1.json").write_text(
            json.dumps(manifest), encoding="utf-8",
        )
        reg = ExtensionRegistry()
        reg.load_from_workspace(project_root, refs_base=project_root)
        ext = reg.get("STALE-EXT")
        assert ext is not None
        assert "nonexistent/file.md" in ext.stale_refs
        assert "also-missing.txt" in ext.stale_refs

    def test_existing_refs_not_flagged(self, tmp_path: Path):
        project_root = tmp_path
        (project_root / "real.md").write_text("present")
        ext_dir = project_root / ".ao" / "extensions" / "FRESH-EXT"
        ext_dir.mkdir(parents=True)
        manifest = _valid_manifest(
            "FRESH-EXT",
            ai_context_refs=["real.md"],
        )
        (ext_dir / "extension.manifest.v1.json").write_text(
            json.dumps(manifest), encoding="utf-8",
        )
        reg = ExtensionRegistry()
        reg.load_from_workspace(project_root, refs_base=project_root)
        ext = reg.get("FRESH-EXT")
        assert ext is not None
        assert ext.stale_refs == ()


class TestQueries:
    def test_get_unknown_returns_none(self):
        reg = ExtensionRegistry()
        assert reg.get("NONEXISTENT") is None

    def test_list_all_is_sorted(self):
        reg = ExtensionRegistry()
        reg.load_from_defaults()
        ids = [m.extension_id for m in reg.list_all()]
        assert ids == sorted(ids)
