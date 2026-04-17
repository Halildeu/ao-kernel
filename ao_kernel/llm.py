"""ao_kernel.llm — Public LLM facade for ao-kernel.

Clean import path for governed LLM operations.

Usage:
    from ao_kernel.llm import resolve_route, build_request, normalize_response
    from ao_kernel.llm import count_tokens, check_capabilities
    from ao_kernel.llm import get_circuit_breaker, get_rate_limiter
    from ao_kernel.llm import stream_request, StreamResult, StreamEvent

All implementations live in ao_kernel._internal.prj_kernel_api.
This module provides the stable public API surface.
"""

from __future__ import annotations

from decimal import Decimal
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
    from ao_kernel._internal.prj_kernel_api.llm_router import resolve

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

    Provider guardrails are checked if policy is available (fail-closed on violation).
    Raises ValueError if stream=True and tools are provided (fail-closed).
    """
    # Provider guardrails: enforced when workspace has explicit override policy
    # Bundled defaults are reference-only (many providers disabled by default)
    try:
        from ao_kernel.config import workspace_root as _ws_root
        from pathlib import Path as _Path
        ws = _ws_root()
        if ws:
            guardrails_path = _Path(ws) / "policies" / "policy_llm_providers_guardrails.v1.json"
            if guardrails_path.exists():
                from ao_kernel.governance import check_policy
                guardrails = check_policy(
                    "policy_llm_providers_guardrails.v1.json",
                    {"provider_id": provider_id, "model": model},
                    workspace=_Path(ws),
                )
                if not guardrails.get("allowed", True):
                    raise ValueError(
                        f"Provider guardrails denied: {guardrails.get('reason_codes', [])}"
                    )
    except (FileNotFoundError, ImportError):
        pass

    from ao_kernel._internal.prj_kernel_api.llm_request_builder import build_live_request

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
    from ao_kernel._internal.prj_kernel_api.llm_request_builder import check_capabilities_before_request

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
    from ao_kernel._internal.prj_kernel_api.llm_response_normalizer import (
        normalize_response as _normalize,
    )

    return _normalize(resp_bytes, provider_id=provider_id)


def extract_text(resp_bytes: bytes) -> str:
    """Extract text content from provider response bytes."""
    from ao_kernel._internal.prj_kernel_api.llm_response_normalizer import extract_llm_output_text

    return extract_llm_output_text(resp_bytes)


def extract_usage(resp_bytes: bytes) -> dict[str, Any] | None:
    """Extract token usage from provider response."""
    from ao_kernel._internal.prj_kernel_api.llm_response_normalizer import (
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
    from ao_kernel._internal.prj_kernel_api.llm_transport import execute_http_request_with_resilience

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
from ao_kernel._internal.prj_kernel_api.llm_stream import StreamEvent  # noqa: E402
from ao_kernel._internal.prj_kernel_api.llm_stream_transport import StreamResult  # noqa: E402
from ao_kernel._internal.prj_kernel_api.llm_stream_transport import execute_stream_request as stream_request  # noqa: E402


# ── Resilience ───────────────────────────────────────────────────────


def get_circuit_breaker(provider_id: str) -> Any:
    """Get or create per-provider circuit breaker.

    Returns the breaker instance from the internal module (typed as Any because
    the internal type is not part of the public API).
    """
    from ao_kernel._internal.prj_kernel_api.circuit_breaker import get_circuit_breaker as _get

    return _get(provider_id)


def get_rate_limiter(provider_id: str) -> Any:
    """Get or create per-provider rate limiter.

    Returns the limiter instance from the internal module (typed as Any because
    the internal type is not part of the public API).
    """
    from ao_kernel._internal.prj_kernel_api.rate_limiter import get_rate_limiter as _get

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
    from ao_kernel._internal.providers.token_counter import count_tokens as _count

    return _count(messages, provider_id=provider_id, model=model)


def count_tokens_heuristic(messages: list[dict[str, Any]]) -> int:
    """Fast heuristic token count for a message list."""
    from ao_kernel._internal.providers.token_counter import count_tokens_heuristic as _count

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
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | None = None,
    response_format: dict[str, Any] | None = None,
    embedding_config: Any | None = None,
    vector_store: Any | None = None,
) -> dict[str, Any]:
    """Build LLM request with context injection.

    If session_context is provided, compiles context and injects into messages.
    Falls back to plain build_request if no context available.
    Propagates tools, tool_choice, and response_format to the underlying request.

    ``embedding_config`` (EmbeddingConfig) and ``vector_store`` (VectorStoreBackend)
    are threaded through to compile_context for semantic reranking. Both are
    optional — when omitted, the compiler falls back to the deterministic
    scoring contract (no regression).
    """
    if session_context:
        from pathlib import Path
        from ao_kernel.context.context_compiler import compile_context

        # Load canonical decisions + workspace facts if workspace available
        canonical_dict = None
        workspace_facts = None
        if workspace_root:
            try:
                from ao_kernel.context.canonical_store import query as query_canonical
                import json
                canonical_items = query_canonical(Path(workspace_root))
                canonical_dict = {item["key"]: item for item in canonical_items} if canonical_items else None
            except Exception:
                pass
            try:
                facts_path = Path(workspace_root) / ".cache" / "index" / "workspace_facts.v1.json"
                if facts_path.exists():
                    workspace_facts = json.loads(facts_path.read_text(encoding="utf-8"))
                    # Normalize facts format for compiler
                    if isinstance(workspace_facts, list):
                        workspace_facts = {"facts": {f.get("key", str(i)): f for i, f in enumerate(workspace_facts)}}
            except Exception:
                pass

        compiled = compile_context(
            session_context,
            canonical_decisions=canonical_dict,
            workspace_facts=workspace_facts,
            profile=profile,
            messages=messages,
            embedding_config=embedding_config,
            vector_store=vector_store,
        )
        if compiled.preamble:
            # Use compiled preamble directly — it includes all 3 lanes
            # (session + canonical + facts), not just session_context
            new_messages = list(messages)
            if new_messages and new_messages[0].get("role") == "system":
                original = new_messages[0].get("content", "")
                new_messages[0] = {
                    **new_messages[0],
                    "content": compiled.preamble + "\n\n" + original,
                }
            else:
                new_messages.insert(0, {"role": "system", "content": compiled.preamble})
            messages = new_messages

    req = build_request(
        provider_id=provider_id,
        model=model,
        messages=messages,
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        request_id=request_id,
        stream=stream,
        tools=tools,
        tool_choice=tool_choice,
        response_format=response_format,
    )
    # PR-B2 v5 iter-4 B4 absorb: additive return field carrying the
    # context-injected effective messages. Used by cost middleware to
    # compute pre-dispatch token estimate over the real prompt rather
    # than the caller-supplied raw messages. Pre-B2 callers ignore this
    # field — backward compat.
    req["injected_messages"] = messages
    return req


def governed_call(
    messages: list[dict[str, Any]],
    *,
    # Core routing (required):
    provider_id: str,
    model: str,
    api_key: str,
    base_url: str,
    request_id: str,
    # Call shape (optional):
    temperature: float | None = None,
    max_tokens: int | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | None = None,
    response_format: dict[str, Any] | None = None,
    # Context-aware build (PR-B2 v4 iter-3 B1 absorb):
    session_context: dict[str, Any] | None = None,
    workspace_root_str: str | None = None,
    profile: str | None = None,
    embedding_config: Any | None = None,
    vector_store: Any | None = None,
    # Cost-tracking identity (PR-B2 v3 iter-2 B2 — all 4 required for
    # cost-active path; None → transparent bypass):
    workspace_root: Any | None = None,
    run_id: str | None = None,
    step_id: str | None = None,
    attempt: int | None = None,
) -> dict[str, Any]:
    """Composed LLM call with optional cost governance.

    **STREAMING BOUNDARY (v5 iter-4 B2 absorb)**: NON-STREAMING ONLY.
    Callers with ``stream=True`` intent MUST NOT call ``governed_call``;
    they stay on the existing build + ``_execute_stream`` path in
    client.py. Streaming cost tracking is FAZ-C scope (chunk-level
    tokenization + partial ledger deferred).

    **Activation gate**: all of (``workspace_root``, ``run_id``,
    ``step_id``, ``attempt``) must be non-None AND
    ``policy.enabled=true``; any missing kwarg → transparent bypass.
    Bypass path behaves exactly like pre-B2 flow (build + execute +
    normalize) with zero cost hooks.

    **Return shape (v5 iter-4 B1 absorb — rich internal dict)**:

    - On ``CAPABILITY_GAP``: ``{"status": "CAPABILITY_GAP", "missing":
      [...], "provider_id", "model", "request_id", "text": ""}`` —
      caller envelope-ready (mirrors client.py:531-547 pre-B2 shape).
    - On ``TRANSPORT_ERROR``: ``{"status": "TRANSPORT_ERROR",
      "error_code", "http_status", "provider_id", "model", "request_id",
      "text": "", "elapsed_ms"}`` — caller envelope-ready (mirrors
      client.py:608-618).
    - On normal success: ``{"status": "OK", "normalized": <dict>,
      "resp_bytes": bytes, "transport_result": <dict>, "elapsed_ms": int,
      "request_id": str}``. Caller (client.py / mcp_server.py) unwraps:
      ``normalized`` for response text/usage/tool_calls, ``resp_bytes``
      + ``transport_result`` for evidence/telemetry, ``elapsed_ms``
      for final envelope. **Mevcut post-call pipeline (decision
      extraction, scorecard, telemetry) caller'da kalır; governed_call
      içinde duplicate EDİLMEZ.**

    **Cost-layer errors RAISE** (not envelope):
    :class:`BudgetExhaustedError`, :class:`CostTrackingConfigError`,
    :class:`PriceCatalogNotFoundError`, :class:`LLMUsageMissingError`.
    Caller decides propagate or try/except wrap.

    See plan v7 §2.6 for the full flow spec.
    """
    # 0. Fail-fast validation of optional cost-identity kwargs
    # (CNS-032 iter-1 absorb): if caller provides `attempt`, it must
    # satisfy the ledger schema's `minimum: 1` constraint. We catch
    # invalid values here — before any capability / transport /
    # ledger work — so the error surface is transparent and the run
    # state never diverges from the ledger schema.
    if attempt is not None and attempt < 1:
        raise ValueError(
            f"attempt must be >= 1 (got {attempt!r}); "
            f"ledger idempotency schema constraint"
        )

    # 1. Capability check (BEFORE cost, BEFORE transport).
    cap_ok, _, missing = check_capabilities(
        provider_id=provider_id,
        model=model,
        has_tools=bool(tools),
        has_response_format=bool(response_format),
    )
    if not cap_ok and missing:
        return {
            "status": "CAPABILITY_GAP",
            "text": "",
            "missing": missing,
            "provider_id": provider_id,
            "model": model,
            "request_id": request_id,
        }

    # 2. Cost gate — all 4 identity + ws + policy.enabled.
    cost_active = all(
        [workspace_root, run_id, step_id, attempt is not None]
    )
    cost_policy = None
    if cost_active:
        from pathlib import Path
        from ao_kernel.cost.policy import load_cost_policy

        ws_path = (
            workspace_root
            if isinstance(workspace_root, Path)
            else Path(str(workspace_root))
        )
        cost_policy = load_cost_policy(ws_path)
        cost_active = cost_policy.enabled

    # 3. Build request (context-aware branch).
    if session_context is not None:
        req = build_request_with_context(
            messages=messages,
            provider_id=provider_id,
            model=model,
            base_url=base_url,
            api_key=api_key,
            session_context=session_context,
            workspace_root=workspace_root_str,
            profile=profile,
            embedding_config=embedding_config,
            vector_store=vector_store,
            temperature=temperature,
            max_tokens=max_tokens,
            request_id=request_id,
            tools=tools,
            tool_choice=tool_choice,
            response_format=response_format,
        )
        # injected_messages field added in v5 iter-4 B4 absorb.
        effective_messages = req.get("injected_messages", messages)
    else:
        req = build_request(
            messages=messages,
            provider_id=provider_id,
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            request_id=request_id,
            tools=tools,
            tool_choice=tool_choice,
            response_format=response_format,
        )
        effective_messages = messages

    # 4. Cost reserve (if active).
    est_cost = None
    catalog_entry = None
    if cost_active and cost_policy is not None:
        from pathlib import Path
        from ao_kernel.cost.middleware import pre_dispatch_reserve

        ws_path = (
            workspace_root
            if isinstance(workspace_root, Path)
            else Path(str(workspace_root))
        )
        est_cost, catalog_entry = pre_dispatch_reserve(
            workspace_root=ws_path,
            run_id=str(run_id),
            step_id=str(step_id),
            attempt=int(attempt) if attempt is not None else 1,
            provider_id=provider_id,
            model=model,
            prompt_messages=list(effective_messages),
            max_tokens=max_tokens,
            policy=cost_policy,
        )
        # Raises: BudgetExhaustedError, CostTrackingConfigError,
        # PriceCatalogNotFoundError — caller decides.

    # 5. Transport (existing execute_request).
    transport_result = execute_request(
        url=req["url"],
        headers=req["headers"],
        body_bytes=req["body_bytes"],
        timeout_seconds=30.0,
        provider_id=provider_id,
        request_id=request_id,
    )

    # 6. Transport envelope preserve.
    if transport_result.get("status") != "OK":
        # Reservation HOLDS per Q5 iter-1 (no refund on error).
        return {
            "status": "TRANSPORT_ERROR",
            "text": "",
            "error_code": transport_result.get("error_code", "UNKNOWN"),
            "http_status": transport_result.get("http_status"),
            "provider_id": provider_id,
            "model": model,
            "request_id": request_id,
            "elapsed_ms": transport_result.get("elapsed_ms", 0),
        }

    # 7. Normalize.
    normalized = normalize_response(
        transport_result["resp_bytes"],
        provider_id=provider_id,
    )

    # 8. Cost reconcile + record (if active).
    if cost_active and cost_policy is not None and catalog_entry is not None:
        from pathlib import Path
        from ao_kernel.cost.middleware import post_response_reconcile

        ws_path = (
            workspace_root
            if isinstance(workspace_root, Path)
            else Path(str(workspace_root))
        )
        post_response_reconcile(
            workspace_root=ws_path,
            run_id=str(run_id),
            step_id=str(step_id),
            attempt=int(attempt) if attempt is not None else 1,
            provider_id=provider_id,
            model=model,
            catalog_entry=catalog_entry,
            est_cost=est_cost if est_cost is not None else Decimal("0"),
            raw_response_bytes=transport_result["resp_bytes"],
            policy=cost_policy,
        )
        # Raises LLMUsageMissingError when policy.fail_closed_on_missing_usage
        # AND usage absent. Ledger audit entry always recorded first.

    # 9. Rich internal success dict (v5 iter-4 B1).
    return {
        "status": "OK",
        "normalized": normalized,
        "resp_bytes": transport_result["resp_bytes"],
        "transport_result": transport_result,
        "elapsed_ms": transport_result.get("elapsed_ms", 0),
        "request_id": request_id,
    }


def process_response_with_context(
    output_text: str,
    session_context: dict[str, Any],
    *,
    provider_id: str = "",
    request_id: str = "",
    workspace_root: str | None = None,
    tool_results: list[dict[str, Any]] | None = None,
    vector_store: Any | None = None,
    embedding_config: Any | None = None,
) -> dict[str, Any]:
    """Process LLM response through context pipeline.

    Extracts decisions, processes tool results, runs memory pipeline.
    When ``vector_store`` is provided, extracted decisions are also indexed
    for semantic retrieval (write-path failures are non-blocking — see
    semantic_indexer contract).

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
        vector_store=vector_store,
        embedding_config=embedding_config,
    )

    # Process tool results (extract_from_tool_result — was disconnected, now wired)
    if tool_results:
        from ao_kernel.context.decision_extractor import extract_from_tool_result
        from ao_kernel._internal.session.context_store import upsert_decision

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
