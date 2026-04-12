"""OpenTelemetry adapter — lazy import, no-op fallback when OTEL not installed.

Single module for all telemetry. Other modules import from here, never from
opentelemetry directly. When `ao-kernel[otel]` is not installed, all functions
return no-op objects — zero cost, zero exceptions.

Semantic conventions:
    - LLM fields: gen_ai.* (OTEL Gen AI semantic conventions)
    - Governance/runtime: ao.* (custom namespace)

Spans (v0.2.0 core):
    - ao.llm_call: root span for LLM requests
    - ao.policy_check: policy evaluation
    - ao.mcp_tool_call: MCP tool invocation
    - ao.quality_gate: output quality check (when expensive)
    - ao.stream_call: streaming LLM (child of llm_call context)

Metrics:
    - ao.llm.call.duration: histogram (provider, model, status)
    - ao.llm.tokens.usage: counter (provider, direction)
    - ao.policy.check.total: counter (policy, decision)
    - ao.mcp.tool.call.duration: histogram (tool, decision)
    - ao.stream.first_token_ms: histogram (provider)
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Iterator


# ── OTEL Availability Check ─────────────────────────────────────────

_OTEL_AVAILABLE: bool | None = None
_tracer = None
_meter = None


def _check_otel() -> bool:
    global _OTEL_AVAILABLE
    if _OTEL_AVAILABLE is not None:
        return _OTEL_AVAILABLE
    try:
        from opentelemetry import trace, metrics  # noqa: F401
        _OTEL_AVAILABLE = True
    except ImportError:
        _OTEL_AVAILABLE = False
    return _OTEL_AVAILABLE


def _get_tracer():
    global _tracer
    if _tracer is not None:
        return _tracer
    if not _check_otel():
        return None
    from opentelemetry import trace
    _tracer = trace.get_tracer("ao-kernel", "0.1.0")
    return _tracer


def _get_meter():
    global _meter
    if _meter is not None:
        return _meter
    if not _check_otel():
        return None
    from opentelemetry import metrics
    _meter = metrics.get_meter("ao-kernel", "0.1.0")
    return _meter


def is_otel_available() -> bool:
    """Check if OpenTelemetry is installed and available."""
    return _check_otel()


# ── No-Op Span Context ──────────────────────────────────────────────


class _NoOpSpan:
    """No-op span when OTEL is not available."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def add_event(self, name: str, attributes: dict | None = None) -> None:
        pass

    def set_status(self, status: Any, description: str | None = None) -> None:
        pass

    def record_exception(self, exception: Exception) -> None:
        pass

    def end(self) -> None:
        pass


_NOOP_SPAN = _NoOpSpan()


# ── Span API ────────────────────────────────────────────────────────


@contextmanager
def span(
    name: str,
    attributes: dict[str, Any] | None = None,
) -> Iterator[Any]:
    """Create a traced span. No-op if OTEL not installed.

    Usage:
        with telemetry.span("ao.llm_call", {"gen_ai.system": "openai"}) as s:
            s.set_attribute("gen_ai.response.model", model)
            # ... do work ...
    """
    tracer = _get_tracer()
    if tracer is None:
        yield _NOOP_SPAN
        return

    from opentelemetry import trace
    with tracer.start_as_current_span(name, attributes=attributes) as s:
        try:
            yield s
        except Exception as exc:
            s.set_status(trace.StatusCode.ERROR, str(exc)[:200])
            s.record_exception(exc)
            raise


# ── Metric Helpers ──────────────────────────────────────────────────

_histograms: dict[str, Any] = {}
_counters: dict[str, Any] = {}


def _get_histogram(name: str, unit: str = "ms", description: str = "") -> Any:
    if name in _histograms:
        return _histograms[name]
    meter = _get_meter()
    if meter is None:
        return None
    h = meter.create_histogram(name, unit=unit, description=description)
    _histograms[name] = h
    return h


def _get_counter(name: str, unit: str = "1", description: str = "") -> Any:
    if name in _counters:
        return _counters[name]
    meter = _get_meter()
    if meter is None:
        return None
    c = meter.create_counter(name, unit=unit, description=description)
    _counters[name] = c
    return c


def record_llm_call_duration(
    duration_ms: float,
    *,
    provider: str,
    model: str,
    status: str,
) -> None:
    """Record LLM call duration histogram."""
    h = _get_histogram(
        "ao.llm.call.duration",
        unit="ms",
        description="LLM call duration in milliseconds",
    )
    if h:
        h.record(duration_ms, {"gen_ai.system": provider, "gen_ai.request.model": model, "ao.status": status})


def record_token_usage(
    *,
    provider: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    """Record token usage counter."""
    c = _get_counter(
        "ao.llm.tokens.usage",
        unit="token",
        description="LLM token usage",
    )
    if c:
        if input_tokens > 0:
            c.add(input_tokens, {"gen_ai.system": provider, "ao.token.direction": "input"})
        if output_tokens > 0:
            c.add(output_tokens, {"gen_ai.system": provider, "ao.token.direction": "output"})


def record_policy_check(
    *,
    policy: str,
    decision: str,
) -> None:
    """Record policy check counter."""
    c = _get_counter(
        "ao.policy.check.total",
        description="Policy check decisions",
    )
    if c:
        c.add(1, {"ao.policy.name": policy, "ao.decision": decision})


def record_mcp_tool_call(
    duration_ms: float,
    *,
    tool: str,
    decision: str,
) -> None:
    """Record MCP tool call duration."""
    h = _get_histogram(
        "ao.mcp.tool.call.duration",
        unit="ms",
        description="MCP tool call duration",
    )
    if h:
        h.record(duration_ms, {"ao.mcp.tool": tool, "ao.decision": decision})


def record_stream_first_token(
    first_token_ms: float,
    *,
    provider: str,
) -> None:
    """Record streaming first token latency."""
    h = _get_histogram(
        "ao.stream.first_token_ms",
        unit="ms",
        description="Time to first streaming token",
    )
    if h:
        h.record(first_token_ms, {"gen_ai.system": provider})
