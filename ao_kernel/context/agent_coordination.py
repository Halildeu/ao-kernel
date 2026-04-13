"""Multi-agent coordination — shared canonical decision access with revision tracking.

Enables multiple agents (Claude, Codex, etc.) to read/write the same canonical
decision store with consistency guarantees.

Revision-based: every write increments a revision counter. Agents can detect
stale reads by comparing their last-seen revision.

SDK hooks:
    record_decision(key, value, source) — write to session + auto-promote if confident
    compile_context(profile, max_tokens) — compile context for LLM injection
    finalize_session() — end session with compaction + distillation
    query_memory(key_pattern) — query canonical decisions + facts
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ao_kernel.context.canonical_store import load_store


def get_revision(workspace_root: Path) -> str:
    """Get current canonical store revision hash.

    Agents compare this to detect if store has changed since their last read.
    """
    store = load_store(workspace_root)
    content = json.dumps(store, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def read_with_revision(
    workspace_root: Path,
    *,
    key_pattern: str = "*",
    category: str | None = None,
) -> dict[str, Any]:
    """Read canonical decisions with revision metadata.

    Returns {revision, items, count} — agent stores revision for stale detection.
    """
    from ao_kernel.context.canonical_store import query

    revision = get_revision(workspace_root)
    items = query(workspace_root, key_pattern=key_pattern, category=category)

    return {
        "revision": revision,
        "items": items,
        "count": len(items),
    }


def check_stale(workspace_root: Path, *, last_revision: str) -> bool:
    """Check if the canonical store has changed since last_revision.

    Returns True if store is stale (has been modified by another agent).
    """
    current = get_revision(workspace_root)
    return current != last_revision


# ── SDK Hooks ───────────────────────────────────────────────────────


def record_decision(
    workspace_root: Path,
    *,
    key: str,
    value: Any,
    source: str = "agent",
    confidence: float = 0.8,
    session_id: str = "",
    auto_promote: bool = True,
    promote_threshold: float = 0.7,
) -> dict[str, Any]:
    """SDK hook: Record a decision. Auto-promotes to canonical if confident enough.

    Returns {recorded: True, promoted: bool, key, value}.
    """
    from ao_kernel.context.canonical_store import promote_decision

    # Always persist to canonical store (record = persist)
    promoted = False
    if auto_promote and confidence >= promote_threshold:
        promote_decision(
            workspace_root,
            key=key,
            value=value,
            source=source,
            confidence=confidence,
            session_id=session_id,
        )
        promoted = True
    else:
        # Even without auto-promote, persist as low-confidence canonical
        promote_decision(
            workspace_root,
            key=key,
            value=value,
            source=source,
            confidence=confidence,
            session_id=session_id,
            fresh_days=7,  # Short-lived for low-confidence
        )

    return {
        "recorded": True,
        "promoted": promoted,
        "key": key,
        "value": value,
        "confidence": confidence,
    }


def compile_context_sdk(
    workspace_root: Path,
    *,
    session_context: dict[str, Any] | None = None,
    profile: str | None = None,
    max_tokens: int = 4000,
    messages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """SDK hook: Compile context for LLM injection.

    Loads canonical decisions + workspace facts and compiles with session context.
    Returns {preamble, total_tokens, profile_id, items_included}.
    """
    from ao_kernel.context.canonical_store import query
    from ao_kernel.context.context_compiler import compile_context

    # Load canonical decisions as dict
    canonical_items = query(workspace_root, category=None)
    canonical_dict = {item["key"]: item for item in canonical_items}

    # Load workspace facts
    facts_path = workspace_root / ".cache" / "index" / "workspace_facts.v1.json"
    workspace_facts = None
    if facts_path.exists():
        try:
            workspace_facts = json.loads(facts_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    result = compile_context(
        session_context or {"ephemeral_decisions": []},
        canonical_decisions=canonical_dict,
        workspace_facts=workspace_facts,
        profile=profile,
        messages=messages,
    )

    return {
        "preamble": result.preamble,
        "total_tokens": result.total_tokens,
        "profile_id": result.profile_id,
        "items_included": result.items_included,
        "items_excluded": result.items_excluded,
    }


def finalize_session_sdk(
    workspace_root: Path,
    context: dict[str, Any],
    *,
    auto_promote: bool = True,
    promote_threshold: float = 0.7,
) -> dict[str, Any]:
    """SDK hook: Finalize a session — compact, distill, promote high-confidence decisions.

    Returns {compacted, distilled, promoted_count}.
    """
    from ao_kernel.context.canonical_store import promote_from_ephemeral
    from ao_kernel.context.session_lifecycle import end_session

    # End session (compact + distill)
    end_session(context, workspace_root)

    # Auto-promote high-confidence decisions
    promoted_count = 0
    if auto_promote:
        decisions = context.get("ephemeral_decisions", [])
        promoted = promote_from_ephemeral(
            workspace_root,
            decisions,
            min_confidence=promote_threshold,
            session_id=context.get("session_id", ""),
        )
        promoted_count = len(promoted)

    return {
        "finalized": True,
        "session_id": context.get("session_id", ""),
        "promoted_count": promoted_count,
    }


def query_memory(
    workspace_root: Path,
    *,
    key_pattern: str = "*",
    category: str | None = None,
) -> list[dict[str, Any]]:
    """SDK hook: Query canonical decisions + facts.

    Simple wrapper for canonical_store.query.
    """
    from ao_kernel.context.canonical_store import query
    return query(workspace_root, key_pattern=key_pattern, category=category)


__all__ = [
    "get_revision",
    "read_with_revision",
    "check_stale",
    "record_decision",
    "compile_context_sdk",
    "finalize_session_sdk",
    "query_memory",
]
