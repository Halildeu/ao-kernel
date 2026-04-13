"""Context Injector — inject session context into LLM prompts.

Reads session context and formats relevant decisions as a system prompt
preamble. Token budget aware — never exceeds max_tokens.

Plugin-ready: workspace_facts can be added to the same assembly pipeline.
"""

from __future__ import annotations

from typing import Any


def build_context_preamble(
    context: dict[str, Any],
    *,
    max_tokens: int = 2000,
    relevance_filter: str | None = None,
    include_facts: dict[str, Any] | None = None,
) -> str:
    """Build a context preamble string for LLM system prompt injection.

    Args:
        context: Session context dict (from context_store.load_context)
        max_tokens: Approximate token budget (~4 chars per token)
        relevance_filter: Optional key prefix filter (e.g., "runtime." only injects runtime decisions)
        include_facts: Optional workspace_facts dict to include

    Returns:
        Formatted preamble string ready to prepend to system prompt.
        Empty string if no relevant context.
    """
    if not context:
        return ""

    sections: list[str] = []
    char_budget = max_tokens * 4  # ~4 chars per token

    # Section 1: Session decisions
    decisions = context.get("decisions", [])
    if decisions:
        decision_lines = _format_decisions(decisions, relevance_filter)
        if decision_lines:
            sections.append("## Prior Decisions\n" + "\n".join(decision_lines))

    # Section 2: Workspace facts (plugin)
    if include_facts:
        fact_lines = _format_facts(include_facts)
        if fact_lines:
            sections.append("## Workspace Facts\n" + "\n".join(fact_lines))

    # Section 3: Provider state (continuation hint)
    provider_state = context.get("provider_state", {})
    if provider_state:
        state_line = _format_provider_state(provider_state)
        if state_line:
            sections.append("## Session State\n" + state_line)

    if not sections:
        return ""

    preamble = "\n\n".join(sections)

    # Enforce token budget
    if len(preamble) > char_budget:
        preamble = preamble[:char_budget].rsplit("\n", 1)[0] + "\n[...context truncated]"

    return preamble


def inject_context_into_messages(
    messages: list[dict[str, Any]],
    context: dict[str, Any],
    *,
    max_tokens: int = 2000,
    relevance_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Inject context preamble into the first system/user message.

    If first message is system, prepends to its content.
    If no system message, inserts one at the beginning.

    Returns new message list (does not mutate input).
    """
    preamble = build_context_preamble(
        context, max_tokens=max_tokens, relevance_filter=relevance_filter,
    )
    if not preamble:
        return messages

    new_messages = list(messages)  # shallow copy

    # Find or create system message
    if new_messages and new_messages[0].get("role") == "system":
        original = new_messages[0].get("content", "")
        new_messages[0] = {
            **new_messages[0],
            "content": preamble + "\n\n" + original,
        }
    else:
        new_messages.insert(0, {
            "role": "system",
            "content": preamble,
        })

    return new_messages


def _format_decisions(
    decisions: list[dict[str, Any]],
    relevance_filter: str | None,
) -> list[str]:
    """Format decisions as readable lines, filtered and sorted."""
    lines = []
    # Sort by created_at descending (newest first)
    sorted_decisions = sorted(
        decisions,
        key=lambda d: d.get("created_at", ""),
        reverse=True,
    )

    for d in sorted_decisions:
        key = d.get("key", "")
        value = d.get("value", "")
        source = d.get("source", "")

        if relevance_filter and not key.startswith(relevance_filter):
            continue

        line = f"- {key}: {value}"
        if source:
            line += f" (source: {source})"
        lines.append(line)

    return lines


def _format_facts(facts: dict[str, Any]) -> list[str]:
    """Format workspace facts as readable lines."""
    lines = []
    items = facts.get("facts", facts)
    if isinstance(items, dict):
        for key, fact in items.items():
            if isinstance(fact, dict):
                value = fact.get("value", fact.get("latest_value", ""))
                confidence = fact.get("confidence", "")
                line = f"- {key}: {value}"
                if confidence:
                    line += f" (confidence: {confidence})"
                lines.append(line)
            else:
                lines.append(f"- {key}: {fact}")
    return lines


def _format_provider_state(provider_state: dict[str, Any]) -> str:
    """Format provider state as a single-line hint."""
    parts = []
    if provider_state.get("conversation_id"):
        parts.append(f"conversation: {provider_state['conversation_id']}")
    if provider_state.get("last_response_id"):
        parts.append(f"last_response: {provider_state['last_response_id']}")
    if provider_state.get("memory_strategy"):
        parts.append(f"memory: {provider_state['memory_strategy']}")
    return ", ".join(parts) if parts else ""
