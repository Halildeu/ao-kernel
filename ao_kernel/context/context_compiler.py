"""Context compiler — merge 3 lanes into relevance-scored, budget-aware context.

Lane 1: Active session decisions (most recent, ephemeral)
Lane 2: Canonical decisions (promoted, permanent) — Faz 3 placeholder
Lane 3: Workspace facts (distilled cross-session) — from memory_distiller

Each item gets a relevance score based on:
    - Profile match (priority_prefixes)
    - Recency (newer = higher)
    - Confidence (from extraction)

Budget enforcement: total tokens never exceed profile.max_tokens.
Every included item carries selection_reason metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ao_kernel.context.profile_router import ProfileConfig, get_profile


@dataclass
class ContextItem:
    """A single item considered for context injection."""

    key: str
    value: Any
    source_lane: str       # "session" | "canonical" | "fact"
    relevance_score: float # 0.0-1.0
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
    profile: str | None = None,
    messages: list[dict[str, Any]] | None = None,
) -> CompiledContext:
    """Compile context from 3 lanes with relevance scoring and budget enforcement.

    Args:
        session_context: Current session context dict
        canonical_decisions: Promoted permanent decisions (Faz 3 — optional now)
        workspace_facts: Distilled workspace facts (from memory_distiller)
        profile: Explicit profile ID or None (auto-detect from messages)
        messages: Conversation messages (for profile auto-detection)

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

        selection_log.append({
            "key": item.key,
            "lane": item.source_lane,
            "score": round(item.relevance_score, 3),
            "included": item.included,
            "reason": item.selection_reason,
        })

    # Build preamble from included items
    preamble = _build_preamble(
        [i for i in items if i.included],
        profile_config,
    )

    return CompiledContext(
        preamble=preamble,
        total_tokens=used_chars // 4,
        items_included=included_count,
        items_excluded=len(items) - included_count,
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


def _build_preamble(items: list[ContextItem], profile: ProfileConfig) -> str:
    """Build formatted preamble from included items."""
    if not items:
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

    return "\n".join(parts)
