"""Resource loader bridge: resolves policies/schemas/registry from ao_kernel defaults or repo root.

Shim dosyaları repo-kökü path'e bakıyordu. Bu modül ao_kernel.config.load_default()
ile bundled defaults'a yönlendirir. Repo-kökü varsa (editable install) onu tercih eder,
yoksa (wheel install) bundled defaults'tan yükler.

Usage:
    from ao_kernel._internal.shared.resource_loader import load_resource, load_resource_path
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _find_repo_root() -> Path | None:
    """Find repo root by searching for pyproject.toml upward from this file."""
    start = Path(__file__).resolve()
    for p in [start, *start.parents]:
        if (p / "pyproject.toml").exists():
            return p
    return None


def load_resource(resource_type: str, filename: str) -> Any:
    """Load a JSON resource, preferring repo-root over bundled defaults.

    For editable installs, repo-root files are used (so local edits work).
    For wheel installs, ao_kernel/defaults/ bundled files are used.

    Args:
        resource_type: e.g. "policies", "schemas", "registry", "operations"
        filename: e.g. "policy_autonomy.v1.json"
    """
    repo_root = _find_repo_root()
    if repo_root is not None:
        # Map resource_type to repo-root path
        type_to_dir = {
            "policies": "policies",
            "schemas": "schemas",
            "registry": "registry",
            "operations": "docs/OPERATIONS",
        }
        repo_dir = type_to_dir.get(resource_type, resource_type)
        repo_path = repo_root / repo_dir / filename
        if repo_path.is_file():
            return json.loads(repo_path.read_text(encoding="utf-8"))

    # Fallback to bundled defaults
    from ao_kernel.config import load_default
    return load_default(resource_type, filename)


def load_resource_path(resource_type: str, filename: str) -> Path | None:
    """Return filesystem Path to a resource, or None if only available via importlib.

    Useful when a Path object is needed (e.g., for jsonschema file-based validation).
    Returns None for wheel installs where resources are inside the wheel.
    """
    repo_root = _find_repo_root()
    if repo_root is not None:
        type_to_dir = {
            "policies": "policies",
            "schemas": "schemas",
            "registry": "registry",
            "operations": "docs/OPERATIONS",
        }
        repo_dir = type_to_dir.get(resource_type, resource_type)
        repo_path = repo_root / repo_dir / filename
        if repo_path.is_file():
            return repo_path
    return None
