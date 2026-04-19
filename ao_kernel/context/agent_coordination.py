"""Multi-agent coordination — shared canonical decision access with revision tracking.

Enables multiple agents (Claude, Codex, etc.) to read/write the same canonical
decision store with consistency guarantees.

Revision-based: every write updates the canonical store, which changes its
content hash. Agents that cached a previous revision call ``has_changed()`` /
``check_stale()`` to detect modifications before acting.

SDK hooks:
    record_decision(key, value, source)  — write ephemeral (session), or
                                            promote to canonical when
                                            auto_promote=True AND confidence
                                            meets threshold.
    query_memory(key_pattern)             — read canonical decisions + facts
    compile_context_sdk(...)              — derive preamble for LLM injection
                                            WITHOUT firing a request (useful
                                            for handoff, debug, pre-flight
                                            audit, cache warming)
    finalize_session_sdk(context, ...)    — delegate to session_lifecycle.end_session
                                            (single finalize primitive — no
                                            double promotion).
    get_revision / has_changed / read_with_revision — advisory concurrency
                                            helpers (see disclaimer below).

Concurrency disclaimer (CNS-20260414-009 warning):
    ``check_stale`` / ``has_changed`` are ADVISORY ONLY. They do not take a
    filesystem lock; between calling them and writing, another writer can
    update the canonical store and cause a lost-update race. OS-level
    locking / CAS is planned as a separate CNS. Until then, callers that
    truly need serialisation must provide their own coordination (file
    lock, single-writer process, etc.).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ao_kernel.context.canonical_store import load_store


def get_revision(workspace_root: Path) -> str:
    """Return an opaque revision token for the canonical store.

    The token is the full SHA-256 hex digest of a sorted-keys JSON dump
    (64 hex characters). Callers should treat the value as opaque and
    compare for equality rather than relying on its length or format —
    the representation may change in future versions (CNS-009 warning-5).
    """
    store = load_store(workspace_root)
    content = json.dumps(store, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(content.encode()).hexdigest()


def read_with_revision(
    workspace_root: Path,
    *,
    key_pattern: str = "*",
    category: str | None = None,
) -> dict[str, Any]:
    """Read canonical decisions together with the current revision token.

    The returned dict has ``revision`` (opaque string), ``items``
    (list of matching decisions), and ``count`` (convenience). Agents
    retain ``revision`` so later calls can ask ``has_changed()`` before
    trusting their cached view.
    """
    from ao_kernel.context.canonical_store import query

    revision = get_revision(workspace_root)
    items = query(workspace_root, key_pattern=key_pattern, category=category)

    return {
        "revision": revision,
        "items": items,
        "count": len(items),
    }


def has_changed(workspace_root: Path, *, last_revision: str) -> bool:
    """Return True when the canonical store has moved past ``last_revision``.

    ADVISORY ONLY. See module docstring for concurrency disclaimer.
    """
    current = get_revision(workspace_root)
    return current != last_revision


def check_stale(workspace_root: Path, *, last_revision: str) -> bool:
    """Backward-compatible alias of :func:`has_changed`.

    New code should prefer ``has_changed`` — the name makes the semantics
    ("the store has moved") clearer than "stale".
    """
    return has_changed(workspace_root, last_revision=last_revision)


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
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record a decision.

    Promotion rules (CNS-20260414-009 blocking fix):
      - ``auto_promote=True`` AND ``confidence >= promote_threshold``
        → write to canonical store (durable, full TTL).
      - Otherwise → write to ``context['ephemeral_decisions']`` (session-
        scoped, NOT canonical). If no ``context`` is supplied, the call
        still returns ``recorded=True, promoted=False`` but nothing is
        persisted — caller is responsible for supplying a session context
        when they want to accumulate ephemeral decisions.

    Previous behaviour silently wrote low-confidence decisions to canonical
    with ``fresh_days=7``; that contradicted the documented flag name and
    has been removed.

    Returns a summary dict:
        ``{recorded: bool, promoted: bool, key, value, confidence, destination}``
    where ``destination`` is one of ``"canonical"``, ``"session"``,
    or ``"dropped"`` (no context provided, nothing persisted).
    """
    promoted = False
    destination: str
    recorded = True

    if auto_promote and confidence >= promote_threshold:
        from ao_kernel.context.canonical_store import promote_decision

        promote_decision(
            workspace_root,
            key=key,
            value=value,
            source=source,
            confidence=confidence,
            session_id=session_id,
        )
        promoted = True
        destination = "canonical"
    elif context is not None:
        from ao_kernel._internal.session.context_store import upsert_decision

        upsert_decision(
            context,
            key=key,
            value=value,
            source=source,
        )
        destination = "session"
    else:
        # No canonical promotion AND no session context to hold the ephemeral
        # record — nothing is persisted. Caller sees destination="dropped"
        # and can either supply a context or raise the confidence.
        recorded = False
        destination = "dropped"

    return {
        "recorded": recorded,
        "promoted": promoted,
        "destination": destination,
        "key": key,
        "value": value,
        "confidence": confidence,
    }


def compile_context_sdk(
    workspace_root: Path,
    *,
    session_context: dict[str, Any] | None = None,
    profile: str | None = None,
    messages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compile a preamble for LLM injection WITHOUT issuing a request.

    Distinct from ``AoKernelClient.llm_call``: this returns the assembled
    preamble so callers can inspect it, cache it, audit prompts before
    firing, or hand context to another tool. Equivalent preamble is what
    ``llm_call`` would embed internally.

    Args:
        workspace_root: Workspace root (canonical + facts sources).
        session_context: Ephemeral session context (optional).
        profile: Context profile id (``startup`` / ``task_execution`` / etc.).
            When None, ``context_compiler`` auto-detects from messages.
        messages: Conversation messages for profile auto-detection.

    Returns:
        ``{preamble, total_tokens, profile_id, items_included, items_excluded}``
    """
    from ao_kernel.consultation.promotion import (
        PromotedConsultation,
        query_promoted_consultations,
    )
    from ao_kernel.context.canonical_store import query
    from ao_kernel.context.context_compiler import compile_context
    from ao_kernel.context.profile_router import detect_profile, get_profile

    canonical_items = query(workspace_root, category=None)
    # v3.6 E2 iter-2 Codex BLOCK #1 absorb — exclude consultation-
    # category rows from the canonical lane so they render exactly
    # once under the dedicated `## Consultations` section instead of
    # appearing as both a generic canonical blob AND a consultation
    # line. The consultation surface is the typed one.
    canonical_dict = {item["key"]: item for item in canonical_items if item.get("category") != "consultation"}

    facts_path = workspace_root / ".cache" / "index" / "workspace_facts.v1.json"
    workspace_facts = None
    if facts_path.exists():
        try:
            workspace_facts = json.loads(facts_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    # v3.6 E2 — load consultations at the caller layer (compiler stays
    # pure, plan §3.E2 + Codex iter-1 revision #1). Resolve profile up
    # front so we only query the store when the profile wants
    # consultations (`max_consultations > 0`), then slice + prefer-AGREE
    # sort before handing the tuple to the compiler.
    resolved_profile_id = profile
    if resolved_profile_id is None and messages:
        resolved_profile_id = detect_profile(messages)
    profile_config = get_profile(resolved_profile_id)
    consultation_cap = max(0, profile_config.max_consultations)
    consultation_records: tuple[PromotedConsultation, ...] = ()
    if consultation_cap:
        try:
            all_consultations = query_promoted_consultations(workspace_root)
        except Exception:  # noqa: BLE001 — consumer-side query must not raise
            all_consultations = ()
        # Prefer AGREE first, PARTIAL second; each already sorted by
        # promoted_at desc inside the facade.
        agree = tuple(r for r in all_consultations if r.final_verdict == "AGREE")
        partial = tuple(r for r in all_consultations if r.final_verdict == "PARTIAL")
        consultation_records = (agree + partial)[:consultation_cap]

    result = compile_context(
        session_context or {"ephemeral_decisions": []},
        canonical_decisions=canonical_dict,
        workspace_facts=workspace_facts,
        consultations=consultation_records,
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
    """Finalize a session — single primitive (CNS-009 blocking fix).

    Previous implementation called ``end_session`` (which already promotes
    at a fixed 0.7 threshold) AND then ran ``promote_from_ephemeral``
    again with the caller-supplied threshold. That produced double-
    promotion and silently ignored ``auto_promote=False``. This version
    delegates the promotion decision to ``end_session`` directly.

    Returns a summary dict with the session id and the actual promotion
    count (taken from the canonical store delta).
    """
    from ao_kernel.context.canonical_store import query as query_canonical
    from ao_kernel.context.session_lifecycle import end_session

    before = {item["key"] for item in query_canonical(workspace_root)}
    end_session(
        context,
        workspace_root,
        auto_promote=auto_promote,
        promote_threshold=promote_threshold,
    )
    after = {item["key"] for item in query_canonical(workspace_root)}
    promoted_count = len(after - before)

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
    """Query canonical decisions + facts.

    Thin wrapper over :func:`canonical_store.query`. Exposed as an SDK
    surface so callers do not have to reach into ``_internal``-adjacent
    modules.
    """
    from ao_kernel.context.canonical_store import query

    return query(workspace_root, key_pattern=key_pattern, category=category)


__all__ = [
    "get_revision",
    "read_with_revision",
    "has_changed",
    "check_stale",
    "record_decision",
    "compile_context_sdk",
    "finalize_session_sdk",
    "query_memory",
]
