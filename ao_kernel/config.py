"""Workspace resolver and bundled defaults loader.

Resolution order for workspace_root():
    1. ``override`` argument (from --workspace-root CLI flag)
    2. ``.ao/`` directory (searched from CWD upward)
    3. ``.cache/ws_customer_default`` (legacy — MUST remain in v1.x)
    4. None (library mode — no workspace required)
"""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

from ao_kernel.errors import DefaultsNotFoundError, WorkspaceCorruptedError

_VALID_RESOURCE_TYPES = frozenset({
    "policies",
    "schemas",
    "registry",
    "extensions",
    "operations",
    "catalogs",
})
# "catalogs" added in FAZ-B PR-B0 (CNS-028v2 iter-5 W2/W4 absorb):
# bundled ao_kernel/defaults/catalogs/*.v1.json carry reference data
# (e.g. price-catalog.v1.json) that has the same wheel-safe discovery
# need as policies/schemas but is content-versioned data rather than
# enforcement policy. Loader path follows the existing plural kind
# convention; callers use full filename per test_config.py:70 pattern.


def workspace_root(override: str | Path | None = None) -> Path | None:
    """Resolve the workspace root directory.

    Returns None in library mode (no workspace found).
    CLI commands should treat None as an error and exit with a message.
    """
    if override is not None:
        p = Path(override).resolve()
        if not p.is_dir():
            raise FileNotFoundError(f"Workspace override path does not exist: {p}")
        return p

    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / ".ao"
        if candidate.is_dir():
            return candidate

    # Legacy .cache/ws_customer_default removed in v2.0.0
    # Use .ao/ workspace instead: ao-kernel init

    return None


def load_workspace_json(workspace: Path) -> dict[str, Any]:
    """Load and validate workspace.json from the given workspace directory."""
    ws_file = workspace / "workspace.json"
    if not ws_file.is_file():
        raise WorkspaceCorruptedError(
            f"workspace.json not found in {workspace}. "
            "Run 'ao-kernel init' to create a workspace."
        )
    try:
        data = json.loads(ws_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise WorkspaceCorruptedError(
            f"workspace.json is not valid JSON: {e}"
        ) from e

    if not isinstance(data, dict):
        raise WorkspaceCorruptedError("workspace.json must be a JSON object")
    for key in ("version", "kind"):
        if key not in data:
            raise WorkspaceCorruptedError(
                f"workspace.json missing required field: {key!r}"
            )
    return cast(dict[str, Any], data)


def load_default(resource_type: str, filename: str) -> dict[str, Any]:
    """Load a bundled default JSON file from ao_kernel/defaults/.

    Args:
        resource_type: One of "policies", "schemas", "registry",
                       "extensions", "operations".
                       For nested paths use slash: "extensions/PRJ-AIRUNNER".
        filename: The JSON filename.

    Returns:
        Parsed JSON object. Raises if the top-level JSON value is not an object.
    """
    base_type = resource_type.split("/")[0]
    if base_type not in _VALID_RESOURCE_TYPES:
        raise ValueError(
            f"resource_type base must be one of {sorted(_VALID_RESOURCE_TYPES)}, "
            f"got {base_type!r}"
        )

    resource = files("ao_kernel.defaults").joinpath(resource_type).joinpath(filename)
    try:
        text = resource.read_text(encoding="utf-8")
    except (FileNotFoundError, TypeError) as e:
        raise DefaultsNotFoundError(
            f"Bundled default not found: {resource_type}/{filename}"
        ) from e
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise DefaultsNotFoundError(
            f"Bundled default must be a JSON object: {resource_type}/{filename}"
        )
    return cast(dict[str, Any], parsed)


def load_with_override(
    resource_type: str,
    filename: str,
    workspace: Path | None = None,
) -> dict[str, Any]:
    """Load a JSON resource, preferring workspace override over bundled default.

    If workspace contains resource_type/filename, loads from there.
    Otherwise falls back to the bundled default. Top-level JSON must be an object.
    """
    if workspace is not None:
        override_path = workspace / resource_type / filename
        if override_path.is_file():
            parsed = json.loads(override_path.read_text(encoding="utf-8"))
            if not isinstance(parsed, dict):
                raise DefaultsNotFoundError(
                    f"Override must be a JSON object: {override_path}"
                )
            return cast(dict[str, Any], parsed)
    return load_default(resource_type, filename)
