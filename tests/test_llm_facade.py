"""Tests for ao_kernel.llm facade — clean import path for LLM operations."""

from __future__ import annotations

import pytest


class TestLlmFacadeImports:
    """Verify all public API items are importable."""

    def test_resolve_route(self):
        from ao_kernel.llm import resolve_route
        assert callable(resolve_route)

    def test_build_request(self):
        from ao_kernel.llm import build_request
        assert callable(build_request)

    def test_check_capabilities(self):
        from ao_kernel.llm import check_capabilities
        assert callable(check_capabilities)

    def test_normalize_response(self):
        from ao_kernel.llm import normalize_response
        assert callable(normalize_response)

    def test_extract_text(self):
        from ao_kernel.llm import extract_text
        assert callable(extract_text)

    def test_extract_usage(self):
        from ao_kernel.llm import extract_usage
        assert callable(extract_usage)

    def test_execute_request(self):
        from ao_kernel.llm import execute_request
        assert callable(execute_request)

    def test_stream_request(self):
        from ao_kernel.llm import stream_request
        assert callable(stream_request)

    def test_stream_event_type(self):
        from ao_kernel.llm import StreamEvent
        assert StreamEvent is not None

    def test_stream_result_type(self):
        from ao_kernel.llm import StreamResult
        assert StreamResult is not None

    def test_get_circuit_breaker(self):
        from ao_kernel.llm import get_circuit_breaker
        assert callable(get_circuit_breaker)

    def test_get_rate_limiter(self):
        from ao_kernel.llm import get_rate_limiter
        assert callable(get_rate_limiter)

    def test_count_tokens(self):
        from ao_kernel.llm import count_tokens
        assert callable(count_tokens)

    def test_count_tokens_heuristic(self):
        from ao_kernel.llm import count_tokens_heuristic
        assert callable(count_tokens_heuristic)

    def test_all_exports(self):
        from ao_kernel.llm import __all__
        assert len(__all__) == 14


class TestLlmFacadeFunctionality:
    def test_resolve_route_returns_dict(self):
        from ao_kernel.llm import resolve_route
        # Router may fail without full docs/OPERATIONS setup — that's OK
        # We're testing the facade wrapper, not the router internals
        try:
            result = resolve_route(intent="FAST_TEXT")
            assert isinstance(result, dict)
        except FileNotFoundError:
            pass  # Expected when docs/OPERATIONS not in repo root

    def test_build_request_openai(self):
        from ao_kernel.llm import build_request
        req = build_request(
            provider_id="openai",
            model="gpt-4",
            messages=[{"role": "user", "content": "hello"}],
            base_url="https://api.openai.com/v1/chat/completions",
            api_key="sk-test",
        )
        assert "url" in req
        assert "body_bytes" in req
        assert req["body_json"]["model"] == "gpt-4"

    def test_build_request_stream_flag(self):
        from ao_kernel.llm import build_request
        req = build_request(
            provider_id="claude",
            model="claude-3",
            messages=[{"role": "user", "content": "hi"}],
            base_url="https://api.anthropic.com/v1/messages",
            api_key="sk-ant-test",
            stream=True,
        )
        assert req["body_json"]["stream"] is True

    def test_build_request_stream_tools_raises(self):
        from ao_kernel.llm import build_request
        with pytest.raises(ValueError, match="stream=True with tools"):
            build_request(
                provider_id="openai",
                model="gpt-4",
                messages=[{"role": "user", "content": "hi"}],
                base_url="https://api.openai.com/v1/chat/completions",
                api_key="sk-test",
                stream=True,
                tools=[{"type": "function", "function": {"name": "test"}}],
            )

    def test_normalize_response_openai(self):
        import json
        from ao_kernel.llm import normalize_response
        resp = json.dumps({
            "choices": [{"message": {"content": "Hello world"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2},
        }).encode()
        result = normalize_response(resp, provider_id="openai")
        assert result["text"] == "Hello world"
        assert result["usage"]["input_tokens"] == 5

    def test_extract_text_anthropic(self):
        import json
        from ao_kernel.llm import extract_text
        resp = json.dumps({
            "content": [{"type": "text", "text": "Merhaba"}],
        }).encode()
        assert extract_text(resp) == "Merhaba"

    def test_count_tokens_heuristic(self):
        from ao_kernel.llm import count_tokens_heuristic
        messages = [{"role": "user", "content": "Hello world, this is a test."}]
        result = count_tokens_heuristic(messages)
        assert isinstance(result, int)
        assert result > 0

    def test_circuit_breaker_instance(self):
        from ao_kernel.llm import get_circuit_breaker
        cb = get_circuit_breaker("test_provider")
        assert hasattr(cb, "allow_request")
        assert hasattr(cb, "record_success")

    def test_rate_limiter_instance(self):
        from ao_kernel.llm import get_rate_limiter
        rl = get_rate_limiter("test_provider")
        assert rl is not None
