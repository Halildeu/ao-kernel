"""Context compiler — merge 4 lanes into relevance-scored, budget-aware context.

Lane 1: Active session decisions (most recent, ephemeral)
Lane 2: Canonical decisions (promoted, permanent) — from canonical_store
Lane 3: Workspace facts (distilled cross-session) — from memory_distiller
Lane 4: Promoted consultations (v3.6 E2) — typed agent-to-agent decisions
        from ``ao_kernel.consultation.promotion.query_promoted_consultations``.
        Caller supplies the already-loaded tuple; the compiler is pure and
        does NOT perform any I/O (see plan §3.E2 + Codex iter-1 revision #1).

Each item gets a relevance score based on:
    - Profile match (priority_prefixes)
    - Recency (newer = higher)
    - Confidence (from extraction)

Budget enforcement: total tokens never exceed profile.max_tokens.
Every included item carries selection_reason metadata.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from ao_kernel.context.profile_router import ProfileConfig, get_profile

if TYPE_CHECKING:
    # Runtime-skipped to avoid a circular import: promotion.py imports
    # canonical_store.query, which triggers ao_kernel.context.__init__,
    # which loads this module. Annotations use string forward refs via
    # `from __future__ import annotations` above.
    from ao_kernel.consultation.promotion import PromotedConsultation

logger = logging.getLogger(__name__)


@dataclass
class ContextItem:
    """A single item considered for context injection."""

    key: str
    value: Any
    source_lane: str  # "session" | "canonical" | "fact"
    relevance_score: float  # 0.0-1.0
    selection_reason: str  # why included/excluded
    included: bool = False
    token_estimate: int = 0


@dataclass
class CompiledContext:
    """Result of context compilation."""

    preamble: str
    total_tokens: int
    items_included: int
    items_excluded: int
    profile_id: str
    selection_log: list[dict[str, Any]] = field(default_factory=list)


def compile_context(
    session_context: dict[str, Any],
    *,
    canonical_decisions: dict[str, Any] | None = None,
    workspace_facts: dict[str, Any] | None = None,
    consultations: Sequence[PromotedConsultation] = (),
    profile: str | None = None,
    messages: list[dict[str, Any]] | None = None,
    enable_semantic_search: bool | None = None,
    embedding_config: Any | None = None,
    vector_store: Any | None = None,
) -> CompiledContext:
    """Compile context from 4 lanes with relevance scoring and budget enforcement.

    Args:
        session_context: Current session context dict
        canonical_decisions: Promoted permanent decisions (Faz 3 — optional now)
        workspace_facts: Distilled workspace facts (from memory_distiller)
        consultations: Promoted consultations to render in the
            ``## Consultations`` section (v3.6 E2). MUST be
            pre-loaded by the caller (``compile_context_sdk`` or
            equivalent); the compiler is pure and does NOT query the
            canonical store itself. Ordering is preserved — render
            respects caller-supplied sort.
        profile: Explicit profile ID or None (auto-detect from messages)
        messages: Conversation messages (for profile auto-detection)
        enable_semantic_search: Enable semantic reranking (None = use profile/env).
            Default OFF. Set AO_SEMANTIC_SEARCH=1 env var to enable globally.
        embedding_config: Optional EmbeddingConfig passed to semantic_search.
            Decoupled from chat route (chat provider may not support embeddings).
        vector_store: Optional VectorStoreBackend. When provided, semantic_search
            delegates to the backend for scale; otherwise in-memory path is used.

    Returns:
        CompiledContext with preamble, metrics, and selection log.
    """
    # Resolve profile
    if profile is None and messages:
        from ao_kernel.context.profile_router import detect_profile

        profile = detect_profile(messages)
    profile_config = get_profile(profile)

    # Collect items from all lanes
    items: list[ContextItem] = []

    # Lane 1: Active session decisions
    for d in session_context.get("ephemeral_decisions", []):
        items.append(_score_decision(d, "session", profile_config))

    # Lane 2: Canonical decisions (Faz 3 placeholder)
    if canonical_decisions:
        for key, cd in canonical_decisions.items():
            if isinstance(cd, dict):
                items.append(_score_canonical(key, cd, profile_config))

    # Lane 3: Workspace facts
    if workspace_facts:
        facts = workspace_facts.get("facts", workspace_facts)
        if isinstance(facts, dict):
            for key, fact in facts.items():
                if isinstance(fact, dict):
                    items.append(_score_fact(key, fact, profile_config))

    # Sort by relevance (highest first)
    items.sort(key=lambda x: x.relevance_score, reverse=True)

    # Semantic reranking (opt-in, default OFF)
    _apply_semantic_reranking(
        items,
        messages,
        profile_config,
        enable_semantic_search,
        embedding_config=embedding_config,
        vector_store=vector_store,
    )

    # Budget enforcement
    budget = profile_config.max_tokens * 4  # ~4 chars per token
    max_items = profile_config.max_decisions
    used_chars = 0
    included_count = 0
    selection_log: list[dict[str, Any]] = []

    for item in items:
        chars_needed = item.token_estimate * 4
        if included_count >= max_items:
            item.included = False
            item.selection_reason = f"excluded: max_decisions ({max_items}) reached"
        elif used_chars + chars_needed > budget:
            item.included = False
            item.selection_reason = f"excluded: token budget ({profile_config.max_tokens}) exceeded"
        else:
            item.included = True
            used_chars += chars_needed
            included_count += 1

        selection_log.append(
            {
                "key": item.key,
                "lane": item.source_lane,
                "score": round(item.relevance_score, 3),
                "included": item.included,
                "reason": item.selection_reason,
            }
        )

    # Apply profile consultation cap (last-added-first-dropped per
    # plan §3.E2) + enforce token budget (Codex iter-2 BLOCK #2 absorb
    # — consultation lines must count toward max_tokens; previously
    # they bypassed budget and also were not reflected in
    # total_tokens / telemetry).
    #
    # v3.8 H5: consultation lines now also contribute to the
    # `items_included` / `items_excluded` / `selection_log`
    # observability surface so downstream telemetry reflects the
    # full lane set (Codex v3.6 E2 residual follow-up).
    cap = max(0, profile_config.max_consultations)
    capped_consultations = tuple(consultations[:cap]) if cap else ()
    accepted_consultations: list[PromotedConsultation] = []
    consultation_excluded = 0

    # v3.8 H5 iter-2 (Codex post-impl BLOCK absorb): consultations
    # dropped by the profile `max_consultations` cap (beyond the
    # capped-tuple slice) must also show up in accounting and
    # selection_log — otherwise EMERGENCY (cap=0) or
    # TASK_EXECUTION (cap=3 with 5 inputs) would keep tail records
    # invisible to telemetry.
    cap_dropped = consultations[cap:] if cap < len(consultations) else ()
    for record in cap_dropped:
        consultation_excluded += 1
        selection_log.append(
            {
                "key": f"consultation.{record.cns_id}",
                "lane": "consultation",
                "score": None,
                "included": False,
                "reason": f"excluded: max_consultations ({profile_config.max_consultations}) cap",
            }
        )

    for record in capped_consultations:
        rendered_line = _render_consultation(record)
        line_chars = len(rendered_line) + 1  # trailing newline
        key = f"consultation.{record.cns_id}"
        if used_chars + line_chars > budget:
            consultation_excluded += 1
            selection_log.append(
                {
                    "key": key,
                    "lane": "consultation",
                    "score": None,
                    "included": False,
                    "reason": f"excluded: token budget ({profile_config.max_tokens}) exceeded",
                }
            )
            # Rest of capped tuple also can't fit (monotonic budget);
            # tail-drop + account each as excluded so counters stay
            # consistent with last-added-first-dropped contract.
            continue
        accepted_consultations.append(record)
        used_chars += line_chars
        included_count += 1
        selection_log.append(
            {
                "key": key,
                "lane": "consultation",
                "score": None,
                "included": True,
                "reason": "included",
            }
        )

    # Build preamble from included items + budget-fit consultations
    preamble = _build_preamble(
        [i for i in items if i.included],
        profile_config,
        consultations=tuple(accepted_consultations),
    )

    total_tokens = used_chars // 4
    total_excluded = (len(items) - sum(1 for i in items if i.included)) + consultation_excluded

    # Telemetry (optional subsystem per CLAUDE.md §7 — graceful fallback, debug log)
    try:
        from ao_kernel.telemetry import record_context_compile

        record_context_compile(
            included_count,
            total_excluded,
            profile=profile_config.profile_id,
            total_tokens=total_tokens,
        )
    except Exception as e:
        logger.debug("context telemetry record skipped: %s", e)

    return CompiledContext(
        preamble=preamble,
        total_tokens=total_tokens,
        items_included=included_count,
        items_excluded=total_excluded,
        profile_id=profile_config.profile_id,
        selection_log=selection_log,
    )


def _score_decision(d: dict[str, Any], lane: str, profile: ProfileConfig) -> ContextItem:
    """Score a session decision for relevance."""
    key = d.get("key", "")
    value = d.get("value", "")
    confidence = d.get("confidence", 0.5) if isinstance(d.get("confidence"), (int, float)) else 0.5

    # Profile match bonus
    profile_match = any(key.startswith(p) for p in profile.priority_prefixes)
    profile_score = 0.3 if profile_match else 0.0

    # Recency bonus (newer = higher)
    recency = _recency_score(d.get("created_at", ""))

    score = min(1.0, confidence * 0.4 + recency * 0.3 + profile_score)
    text = f"- {key}: {value}"

    return ContextItem(
        key=key,
        value=value,
        source_lane=lane,
        relevance_score=score,
        selection_reason=f"profile_match={profile_match}, recency={recency:.2f}, confidence={confidence}",
        token_estimate=max(1, len(text) // 4),
    )


def _score_canonical(key: str, cd: dict[str, Any], profile: ProfileConfig) -> ContextItem:
    """Score a canonical decision."""
    value = cd.get("value", "")
    confidence = cd.get("confidence", 0.8)

    profile_match = any(key.startswith(p) for p in profile.priority_prefixes)
    score = min(1.0, confidence * 0.5 + (0.3 if profile_match else 0.0) + 0.1)
    text = f"- [canonical] {key}: {value}"

    return ContextItem(
        key=key,
        value=value,
        source_lane="canonical",
        relevance_score=score,
        selection_reason=f"canonical, confidence={confidence}",
        token_estimate=max(1, len(text) // 4),
    )


def _score_fact(key: str, fact: dict[str, Any], profile: ProfileConfig) -> ContextItem:
    """Score a workspace fact."""
    value = fact.get("value", fact.get("latest_value", ""))
    confidence = fact.get("confidence", 0.7)

    profile_match = any(key.startswith(p) for p in profile.priority_prefixes)
    score = min(1.0, confidence * 0.4 + (0.2 if profile_match else 0.0) + 0.05)
    text = f"- [fact] {key}: {value}"

    return ContextItem(
        key=key,
        value=value,
        source_lane="fact",
        relevance_score=score,
        selection_reason=f"fact, confidence={confidence}",
        token_estimate=max(1, len(text) // 4),
    )


def _recency_score(created_at: str) -> float:
    """Score 0.0-1.0 based on how recent the timestamp is."""
    if not created_at:
        return 0.3
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        age_hours = (now - dt).total_seconds() / 3600
        if age_hours < 1:
            return 1.0
        if age_hours < 24:
            return 0.8
        if age_hours < 168:  # 1 week
            return 0.5
        return 0.2
    except (ValueError, TypeError):
        return 0.3


def _apply_semantic_reranking(
    items: list[ContextItem],
    messages: list[dict[str, Any]] | None,
    profile_config: ProfileConfig,
    enable_override: bool | None,
    *,
    embedding_config: Any | None = None,
    vector_store: Any | None = None,
) -> None:
    """Optionally rerank items by semantic similarity to user query.

    Gate logic (short-circuit):
        1. Explicit override wins (True/False)
        2. Env var AO_SEMANTIC_SEARCH=1 enables globally
        3. Profile config (default OFF for all profiles)

    Modifies items in-place (blends semantic score into relevance_score).
    Fails silently if embedding API unavailable — deterministic fallback preserved.

    ``embedding_config`` (EmbeddingConfig) supplies provider/model/api_key
    decoupled from the chat route. ``vector_store`` (VectorStoreBackend),
    when provided, is used by semantic_search to query the embedding index.
    """
    import os

    # Resolve enable flag
    if enable_override is not None:
        enabled = enable_override
    elif os.environ.get("AO_SEMANTIC_SEARCH", "").strip().lower() in ("1", "true", "yes"):
        enabled = True
    else:
        enabled = profile_config.enable_semantic_search

    if not enabled or not items or not messages:
        return

    # Extract query from first user message
    query = ""
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                query = content
            elif isinstance(content, list):
                query = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
            break

    if not query:
        return

    try:
        from ao_kernel.context.semantic_retrieval import semantic_search

        # Build decisions list from items for semantic_search
        decisions_for_search = [{"key": item.key, "value": item.value, "_embedding": None} for item in items]

        # semantic_search needs pre-embedded decisions or API key;
        # if neither available, it returns [] — deterministic fallback
        results = semantic_search(
            query,
            decisions_for_search,
            top_k=len(items),
            min_similarity=0.2,
            embedding_config=embedding_config,
            vector_store=vector_store,
        )

        if not results:
            return  # No embeddings available — keep deterministic order

        # Build similarity map
        sim_map: dict[str, float] = {}
        for r in results:
            sim_map[r.get("key", "")] = r.get("_similarity", 0.0)

        # Blend: new_score = 0.7 * deterministic + 0.3 * semantic
        for item in items:
            sim = sim_map.get(item.key, 0.0)
            if sim > 0:
                item.relevance_score = min(1.0, item.relevance_score * 0.7 + sim * 0.3)

        # Re-sort after blending
        items.sort(key=lambda x: x.relevance_score, reverse=True)

    except Exception:
        pass  # Fail-open: semantic search is non-critical


def _render_consultation(record: PromotedConsultation) -> str:
    """Compact one-line render for a promoted consultation entry.

    Format: ``- [CNS-ID] topic VERDICT (from_agent→to_agent, resolved_at)``
    with graceful fallback for any None edge field (strict core
    guaranteed by the reader facade, lenient edges handled here).
    """
    topic = record.topic or "(topic unknown)"
    from_agent = record.from_agent or "(from)"
    to_agent = record.to_agent or "(to)"
    resolved = record.resolved_at or "unresolved"
    return f"- [{record.cns_id}] {topic} {record.final_verdict} ({from_agent}\u2192{to_agent}, {resolved})"


def _build_preamble(
    items: list[ContextItem],
    profile: ProfileConfig,
    *,
    consultations: Sequence[PromotedConsultation] = (),
) -> str:
    """Build formatted preamble from included items + consultations."""
    if not items and not consultations:
        return ""

    sections: dict[str, list[str]] = {"session": [], "canonical": [], "fact": []}

    for item in items:
        lane = item.source_lane
        if lane in sections:
            sections[lane].append(f"- {item.key}: {item.value}")

    parts: list[str] = []
    parts.append(f"[Context Profile: {profile.profile_id}]")

    if sections["session"]:
        parts.append("## Session Decisions")
        parts.extend(sections["session"])

    if sections["canonical"]:
        parts.append("## Canonical Decisions")
        parts.extend(sections["canonical"])

    if sections["fact"]:
        parts.append("## Workspace Facts")
        parts.extend(sections["fact"])

    if consultations:
        parts.append("## Consultations")
        parts.extend(_render_consultation(rec) for rec in consultations)

    return "\n".join(parts)
