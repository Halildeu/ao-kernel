"""Session lifecycle management — start, process, end.

Provides the top-level API for governed session management.
All operations are automatic — no manual calls needed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def start_session(
    workspace_root: str | Path,
    session_id: str,
    ttl_seconds: int = 3600,
) -> dict[str, Any]:
    """Start a session — load existing or create new context.

    Returns session context dict.
    """
    ws = Path(workspace_root)
    try:
        from ao_kernel.session import load_context
        ctx = load_context(workspace_root=ws, session_id=session_id)
        # Fail-closed: if loaded context has hash mismatch, log warning but use it
        # (better than silent reset which loses data)
        return ctx
    except FileNotFoundError:
        # No existing session file — create new (normal flow)
        from ao_kernel.session import new_context
        return new_context(
            session_id=session_id,
            workspace_root=ws,
            ttl_seconds=ttl_seconds,
        )
    except Exception:
        # Corrupted/invalid session — log and create new
        # Note: this is a compromise. Fail-closed would refuse to start,
        # but for usability, we create a fresh session with warning.
        import warnings
        warnings.warn(
            f"Session '{session_id}' corrupted or invalid. Creating fresh session.",
            RuntimeWarning,
            stacklevel=2,
        )
        from ao_kernel.session import new_context
        return new_context(
            session_id=session_id,
            workspace_root=ws,
            ttl_seconds=ttl_seconds,
        )


def end_session(
    context: dict[str, Any],
    workspace_root: str | Path,
) -> dict[str, Any]:
    """End a session — final compact + distillation trigger.

    Returns finalized context.
    """
    ws = Path(workspace_root)
    session_id = context.get("session_id", "default")

    # Final compaction
    from ao_kernel._internal.session.compaction_engine import compact_session_decisions
    compact_session_decisions(
        context,
        workspace_root=ws,
        session_id=session_id,
    )

    # Trigger distillation (async-safe — writes to workspace_facts)
    try:
        from ao_kernel._internal.session.memory_distiller import run_distillation
        run_distillation(workspace_root=ws)
    except Exception:
        pass  # Distillation failure shouldn't block session close

    # Auto-promote high-confidence decisions to canonical store
    try:
        from ao_kernel.context.canonical_store import promote_from_ephemeral
        decisions = context.get("ephemeral_decisions", [])
        promote_from_ephemeral(
            ws,
            decisions,
            min_confidence=0.7,
            session_id=session_id,
        )
    except Exception:
        pass  # Promotion failure shouldn't block session close

    # Final save
    from ao_kernel.session import save_context
    save_context(context, workspace_root=ws, session_id=session_id)

    return context
