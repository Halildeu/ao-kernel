"""ao_kernel.llm — Public LLM facade for ao-kernel.

Clean import path for LLM operations. Replaces direct src.* shim imports.

Usage:
    from ao_kernel.llm import resolve_route, build_request, normalize_response
    from ao_kernel.llm import count_tokens, check_capabilities
    from ao_kernel.llm import get_circuit_breaker, get_rate_limiter
    from ao_kernel.llm import stream_request, StreamResult, StreamEvent

This module re-exports from src/ shim with stable names. When src/ shim
is removed in v2.0.0, implementations will move here.
"""

from __future__ import annotations

from typing import Any

# ── Routing ──────────────────────────────────────────────────────────


def resolve_route(
    *,
    intent: str,
    perspective: str | None = None,
    provider_priority: list[str] | None = None,
    workspace_root: str | None = None,
) -> dict[str, Any]:
    """Resolve the best provider/model for an LLM intent.

    Deterministic routing: intent → class → provider → model.
    Verified-only, TTL-gated. Fail-closed.

    Returns dict with 'status' ('OK' or 'FAIL'), 'provider_id', 'model', etc.
    """
    from src.prj_kernel_api.llm_router import resolve

    return resolve(
        request={
            "intent": intent,
            "perspective": perspective,
            "provider_priority": provider_priority or [],
        },
        workspace_root=workspace_root,
    )


# ── Request Building ─────────────────────────────────────────────────


def build_request(
    *,
    provider_id: str,
    model: str,
    messages: list[dict[str, Any]],
    base_url: str,
    api_key: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
    request_id: str | None = None,
    response_format: dict[str, Any] | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | None = None,
    stream: bool = False,
) -> dict[str, Any]:
    """Build provider-native HTTP request for an LLM call.

    Returns dict with keys: url, headers, body_bytes, body_json.
    Supports all 6 providers: claude, openai, google, deepseek, qwen, xai.

    Raises ValueError if stream=True and tools are provided (fail-closed).
    """
    from src.prj_kernel_api.llm_request_builder import build_live_request

    return build_live_request(
        provider_id=provider_id,
        model=model,
        messages=messages,
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        request_id=request_id,
        response_format=response_format,
        tools=tools,
        tool_choice=tool_choice,
        stream=stream,
    )


def check_capabilities(
    *,
    provider_id: str,
    model: str,
    has_tools: bool = False,
    has_response_format: bool = False,
) -> tuple[bool, str, list[str]]:
    """Pre-flight capability check before building request.

    Returns (ok, provider_id, missing_capability_names).
    """
    from src.prj_kernel_api.llm_request_builder import check_capabilities_before_request

    return check_capabilities_before_request(
        provider_id=provider_id,
        model=model,
        has_tools=has_tools,
        has_response_format=has_response_format,
    )


# ── Response Normalization ───────────────────────────────────────────


def normalize_response(resp_bytes: bytes, *, provider_id: str) -> dict[str, Any]:
    """Normalize a provider response into standard format.

    Returns: {text, usage, tool_calls, raw_json, provider_id}
    Handles Anthropic, OpenAI, Google, and compatible formats.
    """
    from src.prj_kernel_api.llm_response_normalizer import (
        normalize_response as _normalize,
    )

    return _normalize(resp_bytes, provider_id=provider_id)


def extract_text(resp_bytes: bytes) -> str:
    """Extract text content from provider response bytes."""
    from src.prj_kernel_api.llm_response_normalizer import extract_llm_output_text

    return extract_llm_output_text(resp_bytes)


def extract_usage(resp_bytes: bytes) -> dict[str, Any] | None:
    """Extract token usage from provider response."""
    from src.prj_kernel_api.llm_response_normalizer import (
        extract_usage as _extract,
    )

    return _extract(resp_bytes)


# ── Transport ────────────────────────────────────────────────────────


def execute_request(
    *,
    url: str,
    headers: dict[str, str],
    body_bytes: bytes,
    timeout_seconds: float,
    max_response_bytes: int = 131072,
    provider_id: str,
    request_id: str,
    max_retries: int = 0,
) -> dict[str, Any]:
    """Execute HTTP request with retry + circuit breaker.

    Returns dict with: status, http_status, resp_bytes, elapsed_ms, error_code, etc.
    """
    from src.prj_kernel_api.llm_transport import execute_http_request_with_resilience

    return execute_http_request_with_resilience(
        url=url,
        headers=headers,
        body_bytes=body_bytes,
        timeout_seconds=timeout_seconds,
        max_response_bytes=max_response_bytes,
        provider_id=provider_id,
        request_id=request_id,
        max_retries=max_retries,
    )


# ── Streaming ────────────────────────────────────────────────────────

# Re-export streaming types for convenience
from src.prj_kernel_api.llm_stream import StreamEvent  # noqa: E402
from src.prj_kernel_api.llm_stream_transport import StreamResult  # noqa: E402
from src.prj_kernel_api.llm_stream_transport import execute_stream_request as stream_request  # noqa: E402


# ── Resilience ───────────────────────────────────────────────────────


def get_circuit_breaker(provider_id: str):
    """Get or create per-provider circuit breaker."""
    from src.prj_kernel_api.circuit_breaker import get_circuit_breaker as _get

    return _get(provider_id)


def get_rate_limiter(provider_id: str):
    """Get or create per-provider rate limiter."""
    from src.prj_kernel_api.rate_limiter import get_rate_limiter as _get

    return _get(provider_id)


# ── Token Counting ───────────────────────────────────────────────────


def count_tokens(
    messages: list[dict[str, Any]],
    *,
    provider_id: str = "openai",
    model: str = "gpt-4",
) -> dict[str, Any]:
    """Count tokens for a message list using provider-specific counting.

    Returns dict with token count details.
    """
    from src.providers.token_counter import count_tokens as _count

    return _count(messages, provider_id=provider_id, model=model)


def count_tokens_heuristic(messages: list[dict[str, Any]]) -> int:
    """Fast heuristic token count for a message list."""
    from src.providers.token_counter import count_tokens_heuristic as _count

    return _count(messages)


# ── Context-Aware LLM Operations ────────────────────────────────────


def build_request_with_context(
    *,
    provider_id: str,
    model: str,
    messages: list[dict[str, Any]],
    base_url: str,
    api_key: str,
    session_context: dict[str, Any] | None = None,
    workspace_root: str | None = None,
    profile: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    request_id: str | None = None,
    stream: bool = False,
) -> dict[str, Any]:
    """Build LLM request with context injection.

    If session_context is provided, compiles context and injects into messages.
    Falls back to plain build_request if no context available.
    """
    if session_context:
        from ao_kernel.context.context_compiler import compile_context
        from ao_kernel.context.context_injector import inject_context_into_messages

        compiled = compile_context(
            session_context,
            profile=profile,
            messages=messages,
        )
        if compiled.preamble:
            messages = inject_context_into_messages(
                messages, session_context, max_tokens=compiled.total_tokens or 2000,
            )

    return build_request(
        provider_id=provider_id,
        model=model,
        messages=messages,
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        request_id=request_id,
        stream=stream,
    )


def process_response_with_context(
    output_text: str,
    session_context: dict[str, Any],
    *,
    provider_id: str = "",
    request_id: str = "",
    workspace_root: str | None = None,
    tool_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Process LLM response through context pipeline.

    Extracts decisions, processes tool results, runs memory pipeline.
    Returns updated session context.
    """
    from pathlib import Path
    from ao_kernel.context.memory_pipeline import process_turn

    ws = Path(workspace_root) if workspace_root else None

    # Process LLM text output
    session_context = process_turn(
        output_text,
        session_context,
        provider_id=provider_id,
        request_id=request_id,
        workspace_root=ws,
    )

    # Process tool results (extract_from_tool_result — was disconnected, now wired)
    if tool_results:
        from ao_kernel.context.decision_extractor import extract_from_tool_result
        from src.session.context_store import upsert_decision

        for tr in tool_results:
            tool_name = tr.get("tool_name", tr.get("name", ""))
            tool_output = tr.get("output", tr)
            if isinstance(tool_output, dict):
                decisions = extract_from_tool_result(
                    tool_name, tool_output, request_id=request_id,
                )
                for d in decisions:
                    upsert_decision(
                        session_context,
                        key=d.key,
                        value=d.value,
                        source=d.source,
                    )

    return session_context


# ── Public API ───────────────────────────────────────────────────────

__all__ = [
    "resolve_route",
    "build_request",
    "build_request_with_context",
    "process_response_with_context",
    "check_capabilities",
    "normalize_response",
    "extract_text",
    "extract_usage",
    "execute_request",
    "stream_request",
    "StreamEvent",
    "StreamResult",
    "get_circuit_breaker",
    "get_rate_limiter",
    "count_tokens",
    "count_tokens_heuristic",
]
