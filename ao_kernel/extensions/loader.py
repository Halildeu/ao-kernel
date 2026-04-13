"""Extension loader — discover and load extension manifests at runtime.

Supports two sources:
    1. Bundled defaults (ao_kernel/defaults/extensions/) — always available
    2. Workspace extensions (.ao/extensions/) — workspace-mode override

Manifests are JSON files: extension.manifest.v1.json
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ExtensionManifest:
    """Parsed extension manifest."""

    extension_id: str
    version: str
    semver: str
    enabled: bool
    origin: str
    entrypoints: dict[str, list[str]]
    gates: dict[str, list[str]]
    layer_contract: dict[str, Any]
    policies: list[str]


def _parse_manifest(data: dict[str, Any]) -> ExtensionManifest:
    """Parse raw JSON dict into ExtensionManifest."""
    return ExtensionManifest(
        extension_id=str(data.get("extension_id", "")),
        version=str(data.get("version", "v1")),
        semver=str(data.get("semver", "0.0.0")),
        enabled=bool(data.get("enabled", False)),
        origin=str(data.get("origin", "UNKNOWN")),
        entrypoints=data.get("entrypoints", {}),
        gates=data.get("gates", {}),
        layer_contract=data.get("layer_contract", {}),
        policies=data.get("policies", []),
    )


class ExtensionRegistry:
    """Runtime registry of loaded extensions."""

    def __init__(self) -> None:
        self._extensions: dict[str, ExtensionManifest] = {}

    def load_from_defaults(self) -> int:
        """Load bundled extension manifests from ao_kernel/defaults/extensions/.

        Returns number of manifests loaded.
        """
        try:
            import importlib.resources as resources
            extensions_pkg = resources.files("ao_kernel.defaults.extensions")
        except (ImportError, ModuleNotFoundError):
            return 0

        count = 0
        for item in extensions_pkg.iterdir():
            if not item.is_dir():
                continue
            manifest_file = item / "extension.manifest.v1.json"
            try:
                text = manifest_file.read_text(encoding="utf-8")
                data = json.loads(text)
                if isinstance(data, dict):
                    manifest = _parse_manifest(data)
                    self._extensions[manifest.extension_id] = manifest
                    count += 1
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                continue
        return count

    def load_from_workspace(self, workspace_root: Path) -> int:
        """Load workspace extension manifests (override bundled).

        Returns number of manifests loaded.
        """
        extensions_dir = workspace_root / "extensions"
        if not extensions_dir.is_dir():
            return 0

        count = 0
        for ext_dir in sorted(extensions_dir.iterdir()):
            if not ext_dir.is_dir():
                continue
            manifest_path = ext_dir / "extension.manifest.v1.json"
            if not manifest_path.exists():
                continue
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    manifest = _parse_manifest(data)
                    self._extensions[manifest.extension_id] = manifest
                    count += 1
            except (json.JSONDecodeError, OSError):
                continue
        return count

    def get(self, extension_id: str) -> ExtensionManifest | None:
        """Get extension by ID."""
        return self._extensions.get(extension_id)

    def list_all(self) -> list[ExtensionManifest]:
        """List all loaded extensions (enabled + disabled)."""
        return sorted(self._extensions.values(), key=lambda m: m.extension_id)

    def list_enabled(self) -> list[ExtensionManifest]:
        """List only enabled extensions."""
        return [m for m in self.list_all() if m.enabled]

    def find_by_entrypoint(self, entrypoint_name: str) -> list[ExtensionManifest]:
        """Find extensions that declare a specific entrypoint."""
        results = []
        for m in self._extensions.values():
            for ep_list in m.entrypoints.values():
                if isinstance(ep_list, list) and entrypoint_name in ep_list:
                    results.append(m)
                    break
        return results
