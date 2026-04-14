"""ao_kernel.context — Governed context management for AI runtime.

Write→Read loop:
    LLM Response → Decision Extractor → session context → Context Compiler → LLM Request

Modules:
    decision_extractor: Extract decisions from LLM output
    context_injector: Basic context injection (Faz 1)
    context_compiler: 3-lane relevance-scored compilation (Faz 2)
    profile_router: Task-type detection + config
    memory_pipeline: Automatic per-turn processing
    session_lifecycle: start/end session management
"""

from ao_kernel.context.agent_coordination import (
    check_stale,
    compile_context_sdk,
    finalize_session_sdk,
    get_revision,
    has_changed,
    query_memory,
    read_with_revision,
    record_decision,
)
from ao_kernel.context.canonical_store import CanonicalDecision, promote_decision, query as query_canonical
from ao_kernel.context.context_compiler import CompiledContext, compile_context
from ao_kernel.context.context_injector import build_context_preamble, inject_context_into_messages
from ao_kernel.context.decision_extractor import Decision, extract_decisions, extract_from_tool_result
from ao_kernel.context.memory_pipeline import process_turn
from ao_kernel.context.profile_router import ProfileConfig, detect_profile, get_profile
from ao_kernel.context.session_lifecycle import end_session, start_session

__all__ = [
    "Decision",
    "extract_decisions",
    "extract_from_tool_result",
    "build_context_preamble",
    "inject_context_into_messages",
    "compile_context",
    "CompiledContext",
    "detect_profile",
    "get_profile",
    "ProfileConfig",
    "process_turn",
    "start_session",
    "end_session",
    "CanonicalDecision",
    "promote_decision",
    "query_canonical",
    # Agent-coordination SDK (CNS-20260414-009 facade expose)
    "record_decision",
    "query_memory",
    "get_revision",
    "has_changed",
    "check_stale",
    "read_with_revision",
    "compile_context_sdk",
    "finalize_session_sdk",
]
