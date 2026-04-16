"""Tests for ao_kernel.config — workspace resolver + defaults loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ao_kernel.config import (
    load_default,
    load_with_override,
    load_workspace_json,
    workspace_root,
)
from ao_kernel.errors import (
    DefaultsNotFoundError,
    WorkspaceCorruptedError,
)


class TestWorkspaceRoot:
    def test_override_existing_dir(self, tmp_path: Path):
        result = workspace_root(override=str(tmp_path))
        assert result == tmp_path.resolve()

    def test_override_nonexistent_raises(self):
        with pytest.raises(FileNotFoundError):
            workspace_root(override="/nonexistent/path/abc123")

    def test_finds_ao_dir(self, tmp_workspace: Path):
        result = workspace_root()
        assert result is not None
        assert result.name == ".ao"

    def test_returns_none_library_mode(self, empty_dir: Path):
        result = workspace_root()
        assert result is None

    def test_legacy_workspace_no_longer_found(self, legacy_workspace: Path):
        """v2.0.0: Legacy .cache/ws_customer_default no longer supported."""
        result = workspace_root()
        assert result is None  # Legacy fallback removed in v2.0.0


class TestLoadWorkspaceJson:
    def test_valid_workspace(self, tmp_workspace: Path):
        data = load_workspace_json(tmp_workspace)
        import ao_kernel
        assert data["version"] == ao_kernel.__version__
        assert data["kind"] == "ao-workspace"

    def test_missing_workspace_json(self, tmp_path: Path):
        with pytest.raises(WorkspaceCorruptedError, match="workspace.json not found"):
            load_workspace_json(tmp_path)

    def test_invalid_json(self, tmp_path: Path):
        (tmp_path / "workspace.json").write_text("not json{{{")
        with pytest.raises(WorkspaceCorruptedError, match="not valid JSON"):
            load_workspace_json(tmp_path)

    def test_missing_required_field(self, tmp_path: Path):
        (tmp_path / "workspace.json").write_text('{"version": "2.0.0"}')
        with pytest.raises(WorkspaceCorruptedError, match="missing required field"):
            load_workspace_json(tmp_path)


class TestLoadDefault:
    def test_load_policy(self):
        data = load_default("policies", "policy_autonomy.v1.json")
        assert isinstance(data, dict)

    def test_load_schema(self):
        data = load_default("schemas", "active-context-profile.schema.v1.json")
        assert isinstance(data, dict)

    def test_load_registry(self):
        data = load_default("registry", "provider_capability_registry.v1.json")
        assert isinstance(data, dict)

    def test_load_extension_manifest(self):
        data = load_default("extensions/PRJ-DEPLOY", "extension.manifest.v1.json")
        assert isinstance(data, dict)
        assert "extension_id" in data

    def test_load_operations(self):
        data = load_default("operations", "llm_class_registry.v1.json")
        assert isinstance(data, dict)

    def test_load_catalog(self):
        """PR-B0: bundled price catalog under catalogs/ resource type."""
        data = load_default("catalogs", "price-catalog.v1.json")
        assert isinstance(data, dict)
        assert data["catalog_version"] == "1"
        assert data["source"] == "bundled"
        assert isinstance(data["entries"], list)
        assert len(data["entries"]) >= 4
        # Each entry carries provider/model/unit pricing
        for e in data["entries"]:
            assert "provider_id" in e and "model" in e
            assert e["currency"] == "USD"
            assert e["billing_unit"] == "per_1k_tokens"

    def test_load_catalog_checksum_valid(self):
        """Bundled catalog's checksum must match the canonical-JSON
        SHA-256 of its entries[] array (the verification the PR-B2
        runtime will perform at load)."""
        import hashlib
        import json as _json

        data = load_default("catalogs", "price-catalog.v1.json")
        canonical = _json.dumps(
            data["entries"],
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        expected = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        assert data["checksum"] == expected

    def test_load_default_deterministic_equality(self):
        """Two consecutive ``load_default`` calls return objects that
        compare equal by value (identity is NOT asserted — each call
        parses fresh JSON; W5''v5 absorb in CNS-028v2)."""
        a = load_default("catalogs", "price-catalog.v1.json")
        b = load_default("catalogs", "price-catalog.v1.json")
        assert a == b  # value equality
        assert a is not b  # but fresh dict each time (no shared-mutable cache)

    def test_invalid_resource_type(self):
        with pytest.raises(ValueError, match="resource_type"):
            load_default("invalid_type", "file.json")

    def test_nonexistent_file(self):
        with pytest.raises(DefaultsNotFoundError):
            load_default("policies", "nonexistent_file.json")


class TestLoadWithOverride:
    def test_workspace_override_takes_precedence(self, tmp_workspace: Path):
        override_data = {"custom": True, "version": "v1"}
        policy_dir = tmp_workspace / "policies"
        policy_dir.mkdir(exist_ok=True)
        (policy_dir / "policy_autonomy.v1.json").write_text(json.dumps(override_data))

        result = load_with_override("policies", "policy_autonomy.v1.json", workspace=tmp_workspace)
        assert result["custom"] is True

    def test_fallback_to_default(self, tmp_workspace: Path):
        result = load_with_override("policies", "policy_autonomy.v1.json", workspace=tmp_workspace)
        assert isinstance(result, dict)
        assert "custom" not in result

    def test_no_workspace(self):
        result = load_with_override("policies", "policy_autonomy.v1.json", workspace=None)
        assert isinstance(result, dict)
