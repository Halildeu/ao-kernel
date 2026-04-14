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
    except Exception as exc:
        # Fail-closed: corrupted/invalid session must NOT silently reset.
        # Let the caller decide: catch SessionCorruptedError to create a
        # fresh session, or let it propagate (fail-closed default).
        from ao_kernel.errors import SessionCorruptedError
        raise SessionCorruptedError(
            f"Session '{session_id}' corrupted or invalid. "
            f"Original error: {exc}"
        ) from exc


def end_session(
    context: dict[str, Any],
    workspace_root: str | Path,
    *,
    auto_promote: bool = True,
    promote_threshold: float = 0.7,
) -> dict[str, Any]:
    """End a session — final compact + distillation trigger + optional promote.

    Per CNS-20260414-009 consensus: this is the single finalize primitive.
    ``agent_coordination.finalize_session_sdk`` now delegates here with its
    params instead of running a second promotion pass (which caused double-
    promotion and silently ignored the caller's ``auto_promote=False``).

    Args:
        context: Session context dict (mutated in place + saved).
        workspace_root: Workspace root path.
        auto_promote: When True (default), ephemeral decisions meeting the
            confidence threshold are promoted to the canonical store.
            Pass False for agent-coordination flows that want to persist
            only ephemeral state without touching canonical.
        promote_threshold: Minimum confidence for auto-promotion (0.0–1.0).
            Only consulted when ``auto_promote`` is True.

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
    except Exception as exc:
        import logging
        logging.getLogger("ao_kernel").warning("session distillation failed: %s", exc)

    # Auto-promote high-confidence decisions to canonical store (opt-out via flag).
    if auto_promote:
        try:
            from ao_kernel.context.canonical_store import promote_from_ephemeral
            decisions = context.get("ephemeral_decisions", [])  # session-scoped, NOT canonical_store decisions
            promote_from_ephemeral(
                ws,
                decisions,
                min_confidence=promote_threshold,
                session_id=session_id,
            )
        except Exception as exc:
            import logging
            logging.getLogger("ao_kernel").warning("session promotion failed: %s", exc)

    # Final save
    from ao_kernel.session import save_context
    save_context(context, workspace_root=ws, session_id=session_id)

    return context
