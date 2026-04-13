"""Automatic memory pipeline — runs after every LLM turn.

No manual calls needed. The pipeline:
    1. Extract decisions from LLM output (JSON primary, heuristic fallback)
    2. Upsert each decision into session context
    3. Prune expired decisions
    4. Compact if threshold exceeded
    5. Save context atomically

This closes the write→read loop: LLM output → decisions → context → next LLM input.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ao_kernel.telemetry import record_policy_check, span


def process_turn(
    output_text: str,
    context: dict[str, Any],
    *,
    provider_id: str = "",
    request_id: str = "",
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    """Process a single LLM turn — extract, prune, compact, save.

    Args:
        output_text: Raw LLM response text
        context: Current session context dict
        provider_id: LLM provider identifier
        request_id: Request ID for evidence linkage
        workspace_root: Workspace root (needed for compaction archive)

    Returns:
        Updated context dict (mutated in place and saved)
    """
    with span("ao.memory_pipeline", {"ao.request_id": request_id}):
        # 1. Extract decisions
        from ao_kernel.context.decision_extractor import extract_decisions

        decisions = extract_decisions(
            output_text,
            provider_id=provider_id,
            request_id=request_id,
        )

        # 2. Upsert each decision
        from src.session.context_store import upsert_decision

        for decision in decisions:
            upsert_decision(
                context,
                key=decision.key,
                value=decision.value,
                source=decision.source,
            )

        # 3. Prune expired decisions
        from datetime import datetime, timezone
        from src.session.context_store import prune_expired_decisions

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        prune_expired_decisions(context, now)

        # 4. Compact if threshold exceeded
        if workspace_root:
            from src.session.compaction_engine import should_compact, compact_session_decisions

            if should_compact(context):
                compact_session_decisions(
                    context,
                    workspace_root=workspace_root,
                    session_id=context.get("session_id", "default"),
                )

        # 5. Save context
        if workspace_root:
            from ao_kernel.session import save_context

            save_context(
                context,
                workspace_root=workspace_root,
                session_id=context.get("session_id"),
            )

        # Telemetry
        record_policy_check(
            policy="memory_pipeline",
            decision=f"extracted:{len(decisions)}",
        )

    return context
