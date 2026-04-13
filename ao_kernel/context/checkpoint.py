"""Checkpoint/resume — durable session state for governed workflows.

Session context IS the checkpoint. No separate format needed.
Atomic save + SHA256 hash verification provides crash safety.

Usage:
    from ao_kernel.context.checkpoint import save_checkpoint, resume_checkpoint

    # Save checkpoint (already happens in memory pipeline, but can be explicit)
    save_checkpoint(context, workspace_root=ws, session_id="my-session")

    # Resume from checkpoint
    context = resume_checkpoint(workspace_root=ws, session_id="my-session")
    # Returns context if valid, raises CheckpointError if corrupted/expired

Boundary: this is SESSION/MEMORY checkpoint. For workflow-level progress
tracking (step completion, pending effects), use domain-specific state files.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CheckpointError(RuntimeError):
    """Checkpoint is invalid, expired, or corrupted."""

    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


def save_checkpoint(
    context: dict[str, Any],
    *,
    workspace_root: str | Path,
    session_id: str | None = None,
) -> str:
    """Save current session context as a durable checkpoint.

    Returns checkpoint path on success.
    This is already called by memory_pipeline.process_turn(), but
    can also be called explicitly for manual checkpoint creation.
    """
    from ao_kernel.session import save_context

    sid = session_id or context.get("session_id", "default")
    save_context(context, workspace_root=Path(workspace_root), session_id=sid)

    path = Path(workspace_root) / ".cache" / "sessions" / sid / "session_context.v1.json"
    return str(path)


def resume_checkpoint(
    *,
    workspace_root: str | Path,
    session_id: str,
    fail_on_expired: bool = True,
) -> dict[str, Any]:
    """Resume from a previously saved checkpoint.

    Fail-closed behavior:
    - Hash mismatch → CheckpointError (corrupted)
    - Expired TTL → CheckpointError if fail_on_expired=True
    - File not found → CheckpointError

    Returns valid session context dict ready for process_turn().
    """
    from ao_kernel.session import load_context

    ws = Path(workspace_root)
    try:
        context = load_context(workspace_root=ws, session_id=session_id)
    except FileNotFoundError:
        raise CheckpointError(
            "CHECKPOINT_NOT_FOUND",
            f"No checkpoint found for session '{session_id}'",
        )
    except Exception as exc:
        raise CheckpointError(
            "CHECKPOINT_CORRUPTED",
            f"Checkpoint corrupted or invalid: {exc}",
        ) from exc

    # Validate hash integrity (load_context already does this)
    hashes = context.get("hashes", {})
    if not isinstance(hashes, dict) or "session_context_sha256" not in hashes:
        raise CheckpointError(
            "CHECKPOINT_NO_HASH",
            "Checkpoint missing integrity hash",
        )

    # Check TTL expiration
    if fail_on_expired:
        expires_at = context.get("expires_at", "")
        if expires_at:
            try:
                exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) > exp_dt:
                    raise CheckpointError(
                        "CHECKPOINT_EXPIRED",
                        f"Checkpoint expired at {expires_at}",
                    )
            except (ValueError, TypeError):
                pass  # Unparseable expiry — allow resume

    # Validate provider cursor if exists
    provider_state = context.get("provider_state", {})
    if isinstance(provider_state, dict) and provider_state.get("conversation_id"):
        context.setdefault("_resume_metadata", {})["has_provider_cursor"] = True

    return context


def list_checkpoints(
    workspace_root: str | Path,
) -> list[dict[str, Any]]:
    """List all available checkpoints in workspace.

    Returns list of {session_id, created_at, expires_at, decision_count, path}.
    """
    import json

    ws = Path(workspace_root)
    sessions_dir = ws / ".cache" / "sessions"
    if not sessions_dir.is_dir():
        return []

    checkpoints = []
    for session_dir in sorted(sessions_dir.iterdir()):
        if not session_dir.is_dir():
            continue
        ctx_file = session_dir / "session_context.v1.json"
        if not ctx_file.is_file():
            continue
        try:
            ctx = json.loads(ctx_file.read_text(encoding="utf-8"))
            checkpoints.append({
                "session_id": ctx.get("session_id", session_dir.name),
                "created_at": ctx.get("created_at", ""),
                "expires_at": ctx.get("expires_at", ""),
                "decision_count": len(ctx.get("ephemeral_decisions", [])),
                "path": str(ctx_file),
            })
        except (json.JSONDecodeError, OSError):
            continue

    return checkpoints


__all__ = [
    "CheckpointError",
    "save_checkpoint",
    "resume_checkpoint",
    "list_checkpoints",
]
