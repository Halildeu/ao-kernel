"""Tests for OTEL telemetry adapter — no-op fallback and span API."""

from __future__ import annotations

import pytest

from ao_kernel.telemetry import (
    _NoOpSpan,
    is_otel_available,
    record_llm_call_duration,
    record_mcp_tool_call,
    record_policy_check,
    record_stream_first_token,
    record_token_usage,
    span,
)


class TestNoOpFallback:
    """When OTEL is not installed, all operations should be no-ops."""

    def test_span_yields_object(self):
        with span("test.span", {"key": "value"}) as s:
            s.set_attribute("test", True)
            s.add_event("test_event")
            # Should not raise

    def test_noop_span_methods(self):
        s = _NoOpSpan()
        s.set_attribute("key", "value")
        s.add_event("event")
        s.set_status(None)
        s.record_exception(ValueError("test"))
        s.end()
        # None should raise

    def test_record_metrics_no_error(self):
        """All metric recording functions should work without OTEL."""
        record_llm_call_duration(100.0, provider="openai", model="gpt-4", status="OK")
        record_token_usage(provider="claude", input_tokens=50, output_tokens=25)
        record_policy_check(policy="policy_test.v1.json", decision="allow")
        record_mcp_tool_call(50.0, tool="ao_policy_check", decision="allow")
        record_stream_first_token(30.0, provider="openai")
        # None should raise

    def test_is_otel_available_returns_bool(self):
        result = is_otel_available()
        assert isinstance(result, bool)


class TestSpanContext:
    def test_span_returns_on_success(self):
        with span("test.success") as s:
            pass  # Should complete normally

    def test_span_propagates_exception(self):
        with pytest.raises(ValueError, match="test error"):
            with span("test.error") as s:
                raise ValueError("test error")

    def test_nested_spans(self):
        with span("parent") as p:
            p.set_attribute("level", "parent")
            with span("child") as c:
                c.set_attribute("level", "child")
        # Should complete without error

    def test_span_with_attributes(self):
        with span("test.attrs", {
            "gen_ai.system": "openai",
            "gen_ai.request.model": "gpt-4",
            "ao.request_id": "req-123",
        }) as s:
            s.set_attribute("ao.status", "OK")
            s.set_attribute("ao.elapsed_ms", 150)
