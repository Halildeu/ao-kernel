"""Tests for ao_kernel.workspace.project_root (C0, CNS-010).

Codex consensus required a single-source-of-truth helper for the project
root semantic, distinct from the historical config.workspace_root() that
returns the .ao directory itself.
"""

from __future__ import annotations

import pytest

from ao_kernel.workspace import find_root, project_root


@pytest.fixture
def project_with_ao(tmp_path):
    """tmp_path/ contains .ao/ — represents a real workspace root."""
    (tmp_path / ".ao").mkdir()
    (tmp_path / ".ao" / "workspace.json").write_text(
        '{"version": "v2", "kind": "ao-kernel"}'
    )
    return tmp_path


class TestProjectRootAutoDiscovery:
    def test_project_root_strips_ao_tail(self, project_with_ao, monkeypatch):
        monkeypatch.chdir(project_with_ao)
        result = project_root()
        assert result == project_with_ao
        # Sanity: find_root still returns the .ao directory itself for
        # backward compatibility with pre-CNS-010 callers.
        assert find_root() == project_with_ao / ".ao"

    def test_project_root_returns_none_outside_workspace(self, tmp_path, monkeypatch):
        isolated = tmp_path / "no-workspace"
        isolated.mkdir()
        monkeypatch.chdir(isolated)
        assert project_root() is None
        assert find_root() is None

    def test_project_root_walks_up_from_subdir(self, project_with_ao, monkeypatch):
        deep = project_with_ao / "src" / "pkg" / "module"
        deep.mkdir(parents=True)
        monkeypatch.chdir(deep)
        # Both helpers honor the upward search; project_root just normalizes.
        assert project_root() == project_with_ao
        assert find_root() == project_with_ao / ".ao"


class TestProjectRootOverride:
    def test_override_is_returned_verbatim(self, tmp_path):
        (tmp_path / ".ao").mkdir()
        # Override is the project root itself; no tail to strip.
        result = project_root(override=tmp_path)
        assert result == tmp_path

    def test_override_without_ao_passes_through(self, tmp_path):
        # Library-mode-style override: no .ao/ inside, but caller asserted
        # this path. Honor it for smoke runs.
        result = project_root(override=tmp_path)
        assert result == tmp_path


class TestProjectRootContractAlignment:
    """Verify the helper aligns three previously-divergent surfaces:
    AoKernelClient, MCP server, extension loader.
    """

    def test_client_uses_project_root_semantics(self, project_with_ao, monkeypatch):
        from ao_kernel.client import AoKernelClient
        monkeypatch.chdir(project_with_ao)
        client = AoKernelClient()
        assert client.workspace_root == project_with_ao

    def test_mcp_helper_uses_project_root_semantics(self, project_with_ao, monkeypatch):
        from ao_kernel.mcp_server import _find_workspace_root
        monkeypatch.chdir(project_with_ao)
        assert _find_workspace_root() == project_with_ao

    def test_extension_loader_documents_project_root_input(self, project_with_ao):
        # Behavioral check: loader expects project root, not .ao directly.
        from ao_kernel.extensions.loader import ExtensionRegistry
        ext_dir = project_with_ao / ".ao" / "extensions" / "DEMO"
        ext_dir.mkdir(parents=True)
        (ext_dir / "extension.manifest.v1.json").write_text(
            '{"version":"v1","extension_id":"DEMO","semver":"1.0.0",'
            '"origin":"CUSTOMER","owner":"CUSTOMER","layer_contract":'
            '{"write_roots_allowlist":[]},"entrypoints":'
            '{"ops":[],"kernel_api_actions":[],"cockpit_sections":[]},'
            '"policies":[],"ui_surfaces":[],"compat":'
            '{"core_min":"0.0.0","core_max":"","notes":[]}}'
        )
        reg = ExtensionRegistry()
        report = reg.load_from_workspace(project_with_ao)
        assert report.loaded == 1
