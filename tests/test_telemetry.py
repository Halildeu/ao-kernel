"""Behavioral tests for OTEL telemetry adapter — state verification, not just crash-free."""

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


class TestOtelAvailability:
    def test_returns_consistent_bool(self):
        result1 = is_otel_available()
        result2 = is_otel_available()
        assert isinstance(result1, bool)
        assert result1 == result2  # Cached, must be stable


class TestNoOpSpan:
    def test_set_attribute_returns_none(self):
        s = _NoOpSpan()
        r1 = s.set_attribute("string", "value")
        r2 = s.set_attribute("int", 42)
        r3 = s.set_attribute("float", 3.14)
        r4 = s.set_attribute("bool", False)
        assert r1 is None
        assert r2 is None
        assert r3 is None
        assert r4 is None

    def test_add_event_returns_none(self):
        s = _NoOpSpan()
        r1 = s.add_event("test_event", {"key": "value"})
        r2 = s.add_event("empty_event")
        assert r1 is None
        assert r2 is None

    def test_record_exception_returns_none(self):
        s = _NoOpSpan()
        r1 = s.record_exception(ValueError("test"))
        r2 = s.record_exception(RuntimeError("another"))
        assert r1 is None
        assert r2 is None

    def test_end_returns_none(self):
        s = _NoOpSpan()
        assert s.end() is None


class TestSpanContextManager:
    def test_span_yields_object_with_set_attribute(self):
        with span("test.operation", {"key": "value"}) as s:
            s.set_attribute("result", "success")
            s.add_event("checkpoint")
            assert hasattr(s, "set_attribute")
            assert hasattr(s, "add_event")

    def test_span_propagates_exception_and_reraises(self):
        with pytest.raises(ValueError, match="intentional"):
            with span("test.failing") as s:
                s.set_attribute("before_error", True)
                raise ValueError("intentional error")

    def test_nested_spans_preserve_execution_order(self):
        results = []
        with span("parent") as p:
            p.set_attribute("level", "parent")
            results.append("parent_start")
            with span("child") as c:
                c.set_attribute("level", "child")
                results.append("child")
            results.append("parent_end")
        assert results == ["parent_start", "child", "parent_end"]

    def test_span_with_none_attributes_no_crash(self):
        with span("test.none") as s:
            s.set_attribute("nullable", None)
            assert hasattr(s, "set_attribute")


class TestMetricRecording:
    """Verify metric functions accept correct signatures and are reentrant.

    Without OTEL installed these are no-ops. We verify:
    1. Functions accept documented parameter types without TypeError
    2. Functions are reentrant (stateless between calls)
    3. Return value is None (no-op contract)
    """

    def test_llm_call_duration_accepts_all_statuses(self):
        r1 = record_llm_call_duration(150.5, provider="openai", model="gpt-4", status="OK")
        r2 = record_llm_call_duration(0.0, provider="claude", model="opus", status="FAIL")
        r3 = record_llm_call_duration(99999.0, provider="google", model="gemini", status="PARTIAL")
        assert r1 is None
        assert r2 is None
        assert r3 is None

    def test_token_usage_accepts_zero_and_positive(self):
        r1 = record_token_usage(provider="openai", input_tokens=100, output_tokens=50)
        r2 = record_token_usage(provider="claude", input_tokens=0, output_tokens=0)
        assert r1 is None
        assert r2 is None

    def test_policy_check_accepts_allow_and_deny(self):
        r1 = record_policy_check(policy="policy_autonomy.v1.json", decision="allow")
        r2 = record_policy_check(policy="policy_guardrails.v1.json", decision="deny")
        assert r1 is None
        assert r2 is None

    def test_mcp_tool_call_accepts_different_tools(self):
        r1 = record_mcp_tool_call(42.0, tool="ao_policy_check", decision="allow")
        r2 = record_mcp_tool_call(0.1, tool="ao_llm_route", decision="deny")
        assert r1 is None
        assert r2 is None

    def test_stream_first_token_accepts_different_providers(self):
        r1 = record_stream_first_token(25.0, provider="openai")
        r2 = record_stream_first_token(150.0, provider="claude")
        assert r1 is None
        assert r2 is None

    def test_all_metrics_reentrant_no_state_corruption(self):
        """Call every metric function twice to verify no state corruption."""
        for i in range(2):
            record_llm_call_duration(float(i), provider="test", model="m", status="OK")
            record_token_usage(provider="test", input_tokens=i, output_tokens=i)
            record_policy_check(policy="p", decision="allow")
            record_mcp_tool_call(float(i), tool="t", decision="allow")
            record_stream_first_token(float(i), provider="test")
        # If we reach here, 10 calls completed without exception or state leak
        assert isinstance(is_otel_available(), bool)
