"""ao_kernel.session — Public session management facade.

Clean import path for session context operations.

Usage:
    from ao_kernel.session import new_context, save_context, load_context
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def new_context(
    session_id: str,
    workspace_root: str | Path,
    ttl_seconds: int = 3600,
) -> dict[str, Any]:
    """Create a new session context."""
    from ao_kernel._internal.session.context_store import new_context as _new
    return _new(
        session_id=session_id,
        workspace_root=str(workspace_root),
        ttl_seconds=ttl_seconds,
    )


def save_context(
    context: dict[str, Any],
    workspace_root: str | Path,
    session_id: str | None = None,
) -> None:
    """Save session context atomically."""
    from ao_kernel._internal.session.context_store import save_context_atomic, SessionPaths
    sid = session_id or context.get("session_id", "default")
    paths = SessionPaths(workspace_root=Path(workspace_root), session_id=sid)
    save_context_atomic(paths.context_path, context)


def load_context(
    workspace_root: str | Path,
    session_id: str = "default",
) -> dict[str, Any]:
    """Load session context from workspace.

    Raises FileNotFoundError if no session file exists (normal flow).
    Raises SessionContextError for corruption (fail-closed path).
    """
    from ao_kernel._internal.session.context_store import load_context as _load, SessionPaths
    paths = SessionPaths(workspace_root=Path(workspace_root), session_id=session_id)
    if not paths.context_path.exists():
        raise FileNotFoundError(f"No session file: {paths.context_path}")
    return _load(paths.context_path)


def distill_memory(
    workspace_root: str | Path,
    distilled: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Consolidate session facts."""
    from ao_kernel._internal.session.memory_distiller import consolidate_facts
    return consolidate_facts(
        workspace_root=Path(workspace_root),
        distilled=distilled or [],
    )


__all__ = ["new_context", "save_context", "load_context", "distill_memory"]
