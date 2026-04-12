"""Tests for ao_kernel.config — workspace resolver + defaults loader."""

from __future__ import annotations

import json
import warnings
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

    def test_legacy_fallback_with_warning(self, legacy_workspace: Path):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = workspace_root()
            assert result is not None
            assert "ws_customer_default" in str(result)
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1
            assert "legacy" in str(deprecation_warnings[0].message).lower()

    def test_ao_takes_precedence_over_legacy(self, tmp_path: Path):
        """If both .ao/ and .cache/ws_customer_default exist, .ao/ wins."""
        import os

        (tmp_path / ".ao").mkdir()
        (tmp_path / ".ao" / "workspace.json").write_text('{"version":"0.1.0","kind":"ao-workspace"}')
        (tmp_path / ".cache" / "ws_customer_default").mkdir(parents=True)
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = workspace_root()
            assert result is not None
            assert result.name == ".ao"
        finally:
            os.chdir(old_cwd)


class TestLoadWorkspaceJson:
    def test_valid_workspace(self, tmp_workspace: Path):
        data = load_workspace_json(tmp_workspace)
        assert data["version"] == "0.1.0"
        assert data["kind"] == "ao-workspace"

    def test_missing_workspace_json(self, tmp_path: Path):
        with pytest.raises(WorkspaceCorruptedError, match="workspace.json not found"):
            load_workspace_json(tmp_path)

    def test_invalid_json(self, tmp_path: Path):
        (tmp_path / "workspace.json").write_text("not json{{{")
        with pytest.raises(WorkspaceCorruptedError, match="not valid JSON"):
            load_workspace_json(tmp_path)

    def test_missing_required_field(self, tmp_path: Path):
        (tmp_path / "workspace.json").write_text('{"version": "0.1.0"}')
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
