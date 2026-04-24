"""Self-editing memory — agent decides what to remember.

Inspired by Letta/MemGPT: instead of passive extraction, the agent
explicitly tells the system what to store, update, or forget.

Three operations (exposed as tool-callable functions):
    remember(key, value, importance)  — store a new memory
    update(key, new_value)            — update existing memory
    forget(key)                       — remove a memory

These integrate with the canonical store for persistence.
Governance: all memory operations are policy-checked.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def remember(
    workspace_root: Path,
    *,
    key: str,
    value: Any,
    importance: str = "normal",  # low | normal | high | critical
    source: str = "agent",
    session_id: str = "",
) -> dict[str, Any]:
    """Agent explicitly stores a memory.

    Importance levels affect retention:
        critical: never auto-expire, always in hot tier
        high: 90-day fresh, hot tier preferred
        normal: 30-day fresh, warm tier
        low: 7-day fresh, cold tier candidate
    """
    from ao_kernel.context.canonical_store import promote_decision

    importance_config = {
        "critical": {"fresh_days": 365, "review_days": 365, "expire_days": 3650, "confidence": 1.0},
        "high": {"fresh_days": 90, "review_days": 180, "expire_days": 365, "confidence": 0.9},
        "normal": {"fresh_days": 30, "review_days": 90, "expire_days": 365, "confidence": 0.8},
        "low": {"fresh_days": 7, "review_days": 30, "expire_days": 90, "confidence": 0.5},
    }
    config = importance_config.get(importance, importance_config["normal"])

    cd = promote_decision(
        workspace_root,
        key=f"memory.{key}",
        value=value,
        category="agent_memory",
        source=source,
        confidence=float(config["confidence"]),
        session_id=session_id,
        fresh_days=int(config["fresh_days"]),
        review_days=int(config["review_days"]),
        expire_days=int(config["expire_days"]),
        provenance={"method": "self_edit", "importance": importance},
    )

    return {
        "stored": True,
        "key": f"memory.{key}",
        "importance": importance,
        "fresh_until": cd.fresh_until,
        "expires_at": cd.expires_at,
    }


def update(
    workspace_root: Path,
    *,
    key: str,
    new_value: Any,
    source: str = "agent",
    session_id: str = "",
) -> dict[str, Any]:
    """Agent updates an existing memory."""
    full_key = f"memory.{key}" if not key.startswith("memory.") else key

    from ao_kernel.context.canonical_store import query, promote_decision

    existing = query(workspace_root, key_pattern=full_key)
    if not existing:
        return {"updated": False, "error": "MEMORY_NOT_FOUND", "key": full_key}

    old_value = existing[0].get("value")
    promote_decision(
        workspace_root,
        key=full_key,
        value=new_value,
        category="agent_memory",
        source=source,
        confidence=existing[0].get("confidence", 0.8),
        session_id=session_id,
        supersedes=full_key,
        provenance={"method": "self_edit_update", "old_value": old_value},
    )

    return {"updated": True, "key": full_key, "old_value": old_value, "new_value": new_value}


def forget(
    workspace_root: Path,
    *,
    key: str,
    expected_revision: str | None = None,
    allow_overwrite: bool = True,
) -> dict[str, Any]:
    """Agent explicitly removes a memory.

    Doesn't physically delete — marks as expired (audit trail preserved).

    Routes through the canonical CAS helper (CNS-20260414-010 Stage A),
    so the lock and revision guards are shared with ``promote_decision``.
    ``expected_revision`` / ``allow_overwrite`` match the pattern: default
    ``allow_overwrite=True`` preserves v2.x behavior until a future major
    release flips the default.
    """
    full_key = f"memory.{key}" if not key.startswith("memory.") else key

    # Lazy import avoids a module-level cycle with canonical_store.
    from ao_kernel.context.canonical_store import _mutate_with_cas

    found: list[bool] = [False]

    def _apply(store: dict[str, Any]) -> None:
        for section in ("decisions", "facts"):
            if full_key in store.get(section, {}):
                store[section][full_key]["expires_at"] = "2000-01-01T00:00:00Z"
                store[section][full_key]["_forgotten"] = True
                found[0] = True

    _mutate_with_cas(
        workspace_root,
        _apply,
        expected_revision=expected_revision,
        allow_overwrite=allow_overwrite,
    )

    if found[0]:
        return {"forgotten": True, "key": full_key}
    return {"forgotten": False, "error": "MEMORY_NOT_FOUND", "key": full_key}


def recall(
    workspace_root: Path,
    *,
    key_pattern: str = "*",
) -> list[dict[str, Any]]:
    """Agent queries its self-stored memories.

    The key_pattern is automatically prefixed with "memory." to match
    the prefix added by remember(). Glob patterns supported (fnmatch).

    Examples:
        recall(ws, key_pattern="*")          → all memories
        recall(ws, key_pattern="test.*")     → memory.test.*
        recall(ws, key_pattern="test.fact")  → memory.test.fact
    """
    from ao_kernel.context.canonical_store import query
    full_pattern = f"memory.{key_pattern}" if not key_pattern.startswith("memory.") else key_pattern
    return query(workspace_root, key_pattern=full_pattern)


__all__ = ["remember", "update", "forget", "recall"]
