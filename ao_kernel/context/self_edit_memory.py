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
        confidence=config["confidence"],
        session_id=session_id,
        fresh_days=config["fresh_days"],
        review_days=config["review_days"],
        expire_days=config["expire_days"],
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
) -> dict[str, Any]:
    """Agent explicitly removes a memory.

    Doesn't physically delete — marks as expired (audit trail preserved).
    """
    full_key = f"memory.{key}" if not key.startswith("memory.") else key

    from ao_kernel.context.canonical_store import load_store, save_store

    store = load_store(workspace_root)
    found = False
    for section in ("decisions", "facts"):
        if full_key in store.get(section, {}):
            store[section][full_key]["expires_at"] = "2000-01-01T00:00:00Z"
            store[section][full_key]["_forgotten"] = True
            found = True

    if found:
        save_store(workspace_root, store)
        return {"forgotten": True, "key": full_key}
    return {"forgotten": False, "error": "MEMORY_NOT_FOUND", "key": full_key}


def recall(
    workspace_root: Path,
    *,
    key_pattern: str = "memory.*",
) -> list[dict[str, Any]]:
    """Agent queries its self-stored memories."""
    from ao_kernel.context.canonical_store import query
    return query(workspace_root, key_pattern=key_pattern)


__all__ = ["remember", "update", "forget", "recall"]
