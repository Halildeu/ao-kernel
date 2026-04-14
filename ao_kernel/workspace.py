"""ao_kernel.workspace — Public workspace management facade.

Clean import path for workspace operations.

Usage:
    from ao_kernel.workspace import init, doctor, migrate, find_root, load_config
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def find_root(override: str | Path | None = None) -> Path | None:
    """Find workspace root. Returns None in library mode.

    Historical contract: returns the ``.ao`` directory itself when auto-
    discovered. Retained for backward compatibility. Callers that want the
    PROJECT ROOT (the directory that contains ``.ao/``) should use
    :func:`project_root` instead — it normalizes the ``.ao`` tail away.
    """
    from ao_kernel.config import workspace_root
    return workspace_root(override=override)


def project_root(override: str | Path | None = None) -> Path | None:
    """Return the PROJECT ROOT (the directory that CONTAINS ``.ao/``).

    Per CNS-20260414-010 consensus: ``ao_kernel.config.workspace_root()``
    returns the ``.ao`` directory itself by design (historic contract,
    documented in CLAUDE.md §3). MCP helpers, extension loader, evidence
    writers, and other public surfaces all want the enclosing project
    directory — the place where ``.ao/evidence/``, ``.ao/sessions/``, and
    ``.ao/extensions/`` live. This helper normalizes the difference so
    call-sites stop reinventing the ``.parent`` trick.

    Args:
        override: Explicit workspace root (project root). When the given
            path is a directory, it is returned verbatim whether or not
            it contains a ``.ao`` sub-directory — honors the caller's
            choice for library-mode smoke runs.

    Returns:
        A project-root ``Path`` or ``None`` when no ``.ao`` directory can
        be discovered and no override was supplied.
    """
    from ao_kernel.config import workspace_root

    ws = workspace_root(override=override)
    if ws is None:
        return None
    # Auto-discovery returns the ``.ao`` directory itself; override returns
    # whatever the caller gave us. Only normalize when we actually see the
    # ``.ao`` tail so caller-supplied project roots pass through untouched.
    return ws.parent if ws.name == ".ao" else ws


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


__all__ = ["find_root", "project_root", "load_config", "init", "doctor", "migrate"]
