"""ao_kernel.workspace — Public workspace management facade.

Clean import path for workspace operations.

Usage:
    from ao_kernel.workspace import init, doctor, migrate, find_root, load_config
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def find_root(override: str | Path | None = None) -> Path | None:
    """Find workspace root. Returns None in library mode."""
    from ao_kernel.config import workspace_root
    return workspace_root(override=override)


def load_config(workspace: Path | None = None) -> dict[str, Any]:
    """Load workspace.json from workspace root."""
    from ao_kernel.config import load_workspace_json, workspace_root
    ws = workspace or workspace_root()
    if ws is None:
        return {}
    return load_workspace_json(ws)


def init(workspace_root_override: str | None = None) -> int:
    """Create .ao/ workspace. Returns exit code."""
    from ao_kernel.init_cmd import run
    return run(workspace_root_override=workspace_root_override)


def doctor(workspace_root_override: str | None = None) -> int:
    """Run workspace health check. Returns exit code."""
    from ao_kernel.doctor_cmd import run
    return run(workspace_root_override=workspace_root_override)


def migrate(
    workspace_root_override: str | None = None,
    *,
    dry_run: bool = False,
    backup: bool = False,
) -> int:
    """Run workspace migration. Returns exit code."""
    from ao_kernel.migrate_cmd import run
    return run(
        workspace_root_override=workspace_root_override,
        dry_run=dry_run,
        backup=backup,
    )


__all__ = ["find_root", "load_config", "init", "doctor", "migrate"]
