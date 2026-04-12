"""Behavioral tests for ao_kernel.llm facade — real input→output validation."""

from __future__ import annotations

import json

import pytest


class TestBuildRequest:
    def test_openai_request_has_required_fields(self):
        from ao_kernel.llm import build_request
        req = build_request(
            provider_id="openai", model="gpt-4",
            messages=[{"role": "user", "content": "hello"}],
            base_url="https://api.openai.com/v1/chat/completions",
            api_key="sk-test",
        )
        assert req["url"] == "https://api.openai.com/v1/chat/completions"
        assert req["body_json"]["model"] == "gpt-4"
        assert req["body_json"]["messages"][0]["content"] == "hello"
        assert "Authorization" in req["headers"]
        assert req["headers"]["Authorization"] == "Bearer sk-test"
        assert isinstance(req["body_bytes"], bytes)

    def test_anthropic_request_has_required_fields(self):
        from ao_kernel.llm import build_request
        req = build_request(
            provider_id="claude", model="claude-3-opus",
            messages=[{"role": "user", "content": "hi"}],
            base_url="https://api.anthropic.com/v1/messages",
            api_key="sk-ant-test",
        )
        assert req["headers"]["x-api-key"] == "sk-ant-test"
        assert req["headers"]["anthropic-version"] == "2023-06-01"
        assert req["body_json"]["model"] == "claude-3-opus"
        # Anthropic converts messages to own format
        assert isinstance(req["body_json"]["messages"], list)

    def test_stream_flag_added_to_body(self):
        from ao_kernel.llm import build_request
        req = build_request(
            provider_id="openai", model="gpt-4",
            messages=[{"role": "user", "content": "hi"}],
            base_url="https://api.openai.com/v1/chat/completions",
            api_key="sk-test", stream=True,
        )
        assert req["body_json"]["stream"] is True

    def test_no_stream_flag_by_default(self):
        from ao_kernel.llm import build_request
        req = build_request(
            provider_id="openai", model="gpt-4",
            messages=[{"role": "user", "content": "hi"}],
            base_url="https://api.openai.com/v1/chat/completions",
            api_key="sk-test",
        )
        assert "stream" not in req["body_json"]

    def test_stream_with_tools_raises_valueerror(self):
        from ao_kernel.llm import build_request
        with pytest.raises(ValueError, match="stream=True with tools"):
            build_request(
                provider_id="openai", model="gpt-4",
                messages=[{"role": "user", "content": "hi"}],
                base_url="https://api.openai.com/v1/chat/completions",
                api_key="sk-test", stream=True,
                tools=[{"type": "function", "function": {"name": "test"}}],
            )

    def test_google_stream_changes_endpoint(self):
        from ao_kernel.llm import build_request
        req = build_request(
            provider_id="google", model="gemini-pro",
            messages=[{"role": "user", "content": "hi"}],
            base_url="https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent",
            api_key="key-test", stream=True,
        )
        assert "streamGenerateContent" in req["url"]
        assert "alt=sse" in req["url"]

    def test_temperature_and_max_tokens(self):
        from ao_kernel.llm import build_request
        req = build_request(
            provider_id="openai", model="gpt-4",
            messages=[{"role": "user", "content": "hi"}],
            base_url="https://api.openai.com/v1/chat/completions",
            api_key="sk-test", temperature=0.7, max_tokens=100,
        )
        assert req["body_json"]["temperature"] == 0.7
        assert req["body_json"]["max_tokens"] == 100


class TestNormalizeResponse:
    def test_openai_text_extraction(self):
        from ao_kernel.llm import normalize_response
        resp = json.dumps({
            "choices": [{"message": {"content": "Hello world"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2},
        }).encode()
        result = normalize_response(resp, provider_id="openai")
        assert result["text"] == "Hello world"
        assert result["usage"]["input_tokens"] == 5
        assert result["usage"]["output_tokens"] == 2
        assert result["provider_id"] == "openai"

    def test_anthropic_text_extraction(self):
        from ao_kernel.llm import normalize_response
        resp = json.dumps({
            "content": [{"type": "text", "text": "Merhaba"}],
            "usage": {"input_tokens": 10, "output_tokens": 3},
        }).encode()
        result = normalize_response(resp, provider_id="claude")
        assert result["text"] == "Merhaba"
        assert result["usage"]["input_tokens"] == 10

    def test_empty_response_handling(self):
        from ao_kernel.llm import normalize_response
        result = normalize_response(b"", provider_id="openai")
        assert isinstance(result["text"], str)

    def test_malformed_json_response(self):
        from ao_kernel.llm import normalize_response
        result = normalize_response(b"not json at all", provider_id="openai")
        assert isinstance(result["text"], str)


class TestExtractText:
    def test_extracts_from_anthropic_format(self):
        from ao_kernel.llm import extract_text
        resp = json.dumps({"content": [{"type": "text", "text": "Test output"}]}).encode()
        assert extract_text(resp) == "Test output"

    def test_extracts_from_openai_format(self):
        from ao_kernel.llm import extract_text
        resp = json.dumps({"choices": [{"message": {"content": "OpenAI says"}}]}).encode()
        assert extract_text(resp) == "OpenAI says"

    def test_handles_empty_bytes(self):
        from ao_kernel.llm import extract_text
        result = extract_text(b"")
        assert isinstance(result, str)


class TestExtractUsage:
    def test_openai_usage(self):
        from ao_kernel.llm import extract_usage
        resp = json.dumps({"usage": {"prompt_tokens": 10, "completion_tokens": 20}}).encode()
        usage = extract_usage(resp)
        assert usage is not None
        assert usage["input_tokens"] == 10
        assert usage["output_tokens"] == 20

    def test_no_usage_returns_none(self):
        from ao_kernel.llm import extract_usage
        usage = extract_usage(b'{"choices": []}')
        assert usage is None


class TestTokenCounting:
    def test_heuristic_returns_positive_int(self):
        from ao_kernel.llm import count_tokens_heuristic
        messages = [{"role": "user", "content": "Hello world, this is a test sentence."}]
        result = count_tokens_heuristic(messages)
        assert isinstance(result, int)
        assert result > 0

    def test_heuristic_longer_text_more_tokens(self):
        from ao_kernel.llm import count_tokens_heuristic
        short = [{"role": "user", "content": "Hi"}]
        long = [{"role": "user", "content": "This is a much longer message with many words."}]
        assert count_tokens_heuristic(long) > count_tokens_heuristic(short)


class TestCircuitBreaker:
    def test_new_breaker_allows_requests(self):
        from ao_kernel.llm import get_circuit_breaker
        cb = get_circuit_breaker("facade_test_provider")
        allowed, reason = cb.allow_request()
        assert allowed is True

    def test_breaker_has_status(self):
        from ao_kernel.llm import get_circuit_breaker
        cb = get_circuit_breaker("facade_test_status")
        status = cb.status_dict()
        assert isinstance(status, dict)
        assert "state" in status


class TestRateLimiter:
    def test_limiter_exists_and_acquires(self):
        from ao_kernel.llm import get_rate_limiter
        rl = get_rate_limiter("facade_test_rl")
        assert rl is not None
        assert hasattr(rl, "acquire")


class TestStreamTypes:
    def test_stream_event_dataclass(self):
        from ao_kernel.llm import StreamEvent
        evt = StreamEvent(event_type="text_delta", text="hello", index=0)
        assert evt.event_type == "text_delta"
        assert evt.text == "hello"
        assert evt.index == 0
        assert evt.raw is None

    def test_stream_result_dataclass(self):
        from ao_kernel.llm import StreamResult
        result = StreamResult(status="OK", complete=True, text="done", finish_reason="stop")
        assert result.status == "OK"
        assert result.complete is True
        assert result.text == "done"

    def test_all_exports_count(self):
        from ao_kernel.llm import __all__
        assert len(__all__) == 14
