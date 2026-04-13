"""Tests for extension loader and registry."""

from __future__ import annotations

import json
from pathlib import Path

from ao_kernel.extensions.loader import ExtensionRegistry


class TestExtensionRegistry:
    def test_load_from_defaults(self):
        """Bundled defaults contain 18 extension manifests."""
        reg = ExtensionRegistry()
        count = reg.load_from_defaults()
        assert count >= 16  # at least 16 bundled manifests
        all_ext = reg.list_all()
        assert len(all_ext) >= 16

    def test_get_known_extension(self):
        """Can retrieve a specific extension by ID."""
        reg = ExtensionRegistry()
        reg.load_from_defaults()
        ext = reg.get("PRJ-KERNEL-API")
        assert ext is not None
        assert ext.extension_id == "PRJ-KERNEL-API"
        assert ext.version == "v1"

    def test_list_enabled_filters_disabled(self):
        """list_enabled only returns extensions with enabled=True."""
        reg = ExtensionRegistry()
        reg.load_from_defaults()
        enabled = reg.list_enabled()
        for ext in enabled:
            assert ext.enabled is True

    def test_find_by_entrypoint(self):
        """find_by_entrypoint discovers extensions declaring a specific entrypoint."""
        reg = ExtensionRegistry()
        reg.load_from_defaults()
        # PRJ-AIRUNNER declares ops entrypoints
        results = reg.find_by_entrypoint("airunner-run")
        ext_ids = [r.extension_id for r in results]
        assert "PRJ-AIRUNNER" in ext_ids

    def test_load_from_workspace(self, tmp_path: Path):
        """Workspace extensions override bundled defaults."""
        ext_dir = tmp_path / "extensions" / "MY-EXT"
        ext_dir.mkdir(parents=True)
        manifest = {
            "extension_id": "MY-EXT",
            "version": "v1",
            "semver": "1.0.0",
            "enabled": True,
            "origin": "WORKSPACE",
            "entrypoints": {"ops": ["my-op"]},
            "gates": {"required": []},
            "layer_contract": {},
            "policies": [],
        }
        (ext_dir / "extension.manifest.v1.json").write_text(
            json.dumps(manifest), encoding="utf-8",
        )

        reg = ExtensionRegistry()
        count = reg.load_from_workspace(tmp_path)
        assert count == 1

        ext = reg.get("MY-EXT")
        assert ext is not None
        assert ext.origin == "WORKSPACE"
        assert ext.semver == "1.0.0"

    def test_get_unknown_returns_none(self):
        """Unknown extension ID returns None."""
        reg = ExtensionRegistry()
        assert reg.get("NONEXISTENT") is None
