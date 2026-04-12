"""Tests for SSE parser and provider delta extractors."""

from __future__ import annotations

import io
import json

import pytest

from src.prj_kernel_api.llm_stream import (
    StreamEvent,
    _parse_sse_lines,
    extract_delta_text,
    extract_stream_usage,
    iter_stream_events,
)


def _make_response(lines: list[str]) -> io.BytesIO:
    """Create a file-like response from SSE lines."""
    raw = "\n".join(lines) + "\n"
    return io.BytesIO(raw.encode("utf-8"))


class TestSSEParser:
    def test_simple_data_line(self):
        resp = _make_response(["data: {\"text\":\"hello\"}", ""])
        events = list(_parse_sse_lines(resp))
        assert len(events) == 1
        assert events[0]["data"] == '{"text":"hello"}'

    def test_multiline_data(self):
        resp = _make_response(["data: line1", "data: line2", ""])
        events = list(_parse_sse_lines(resp))
        assert len(events) == 1
        assert events[0]["data"] == "line1\nline2"

    def test_done_termination(self):
        resp = _make_response([
            "data: {\"text\":\"hi\"}",
            "",
            "data: [DONE]",
            "",
        ])
        events = list(_parse_sse_lines(resp))
        assert len(events) == 2
        assert events[1]["data"] == "[DONE]"

    def test_comment_ignored(self):
        resp = _make_response([": this is a comment", "data: {\"ok\":true}", ""])
        events = list(_parse_sse_lines(resp))
        assert len(events) == 1
        assert "comment" not in events[0]["data"]

    def test_event_field(self):
        resp = _make_response(["event: message", "data: {}", ""])
        events = list(_parse_sse_lines(resp))
        assert events[0]["event"] == "message"

    def test_empty_lines_boundary(self):
        resp = _make_response([
            "data: {\"n\":1}", "",
            "data: {\"n\":2}", "",
        ])
        events = list(_parse_sse_lines(resp))
        assert len(events) == 2

    def test_no_trailing_empty_line(self):
        """Server doesn't send trailing empty line — still yields."""
        resp = _make_response(["data: {\"final\":true}"])
        events = list(_parse_sse_lines(resp))
        assert len(events) == 1

    def test_malformed_data_preserved(self):
        resp = _make_response(["data: not json at all", ""])
        events = list(_parse_sse_lines(resp))
        assert events[0]["data"] == "not json at all"


class TestAnthropicDelta:
    def test_content_block_delta(self):
        event = {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "Hello"},
        }
        assert extract_delta_text(event, "claude") == "Hello"

    def test_message_start_no_text(self):
        event = {"type": "message_start", "message": {"id": "msg_123"}}
        assert extract_delta_text(event, "claude") == ""

    def test_usage_in_message_delta(self):
        event = {
            "type": "message_delta",
            "usage": {"input_tokens": 10, "output_tokens": 25},
        }
        usage = extract_stream_usage(event, "claude")
        assert usage == {"input_tokens": 10, "output_tokens": 25}

    def test_usage_in_message_start(self):
        event = {
            "type": "message_start",
            "message": {"usage": {"input_tokens": 50, "output_tokens": 0}},
        }
        usage = extract_stream_usage(event, "claude")
        assert usage is not None
        assert usage["input_tokens"] == 50


class TestOpenAIDelta:
    def test_choices_delta_content(self):
        event = {
            "choices": [{"index": 0, "delta": {"content": "world"}}],
        }
        assert extract_delta_text(event, "openai") == "world"

    def test_empty_delta(self):
        event = {
            "choices": [{"index": 0, "delta": {"role": "assistant"}}],
        }
        assert extract_delta_text(event, "openai") == ""

    def test_usage_in_final_chunk(self):
        event = {
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        usage = extract_stream_usage(event, "openai")
        assert usage == {"input_tokens": 10, "output_tokens": 20}

    def test_deepseek_compat(self):
        """deepseek uses same wire format as openai."""
        event = {"choices": [{"index": 0, "delta": {"content": "test"}}]}
        assert extract_delta_text(event, "deepseek") == "test"

    def test_qwen_compat(self):
        event = {"choices": [{"index": 0, "delta": {"content": "qwen"}}]}
        assert extract_delta_text(event, "qwen") == "qwen"


class TestGoogleDelta:
    def test_candidates_text(self):
        event = {
            "candidates": [{
                "content": {"parts": [{"text": "gemini says"}]},
            }],
        }
        assert extract_delta_text(event, "google") == "gemini says"

    def test_usage_metadata(self):
        event = {
            "candidates": [{"content": {"parts": [{"text": ""}]}}],
            "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 15},
        }
        usage = extract_stream_usage(event, "google")
        assert usage == {"input_tokens": 5, "output_tokens": 15}


class TestIterStreamEvents:
    def test_full_anthropic_stream(self):
        lines = [
            'data: {"type":"message_start","message":{"id":"msg_1","usage":{"input_tokens":10,"output_tokens":0}}}',
            "",
            'data: {"type":"content_block_start","index":0,"content_block":{"type":"text"}}',
            "",
            'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hi"}}',
            "",
            'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":" there"}}',
            "",
            'data: {"type":"message_delta","usage":{"input_tokens":10,"output_tokens":5}}',
            "",
            'data: {"type":"message_stop"}',
            "",
            "data: [DONE]",
            "",
        ]
        resp = _make_response(lines)
        events = list(iter_stream_events(resp, "claude"))

        text_events = [e for e in events if e.text]
        assert len(text_events) == 2
        assert text_events[0].text == "Hi"
        assert text_events[1].text == " there"

        done_events = [e for e in events if e.event_type == "done"]
        assert len(done_events) >= 1

    def test_full_openai_stream(self):
        lines = [
            'data: {"choices":[{"index":0,"delta":{"role":"assistant","content":""}}]}',
            "",
            'data: {"choices":[{"index":0,"delta":{"content":"Hello"}}]}',
            "",
            'data: {"choices":[{"index":0,"delta":{"content":" world"}}]}',
            "",
            'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":5,"completion_tokens":2}}',
            "",
            "data: [DONE]",
            "",
        ]
        resp = _make_response(lines)
        events = list(iter_stream_events(resp, "openai"))

        text_events = [e for e in events if e.text]
        assert "".join(e.text for e in text_events) == "Hello world"

    def test_malformed_json_yields_error(self):
        lines = ["data: {invalid json}", ""]
        resp = _make_response(lines)
        events = list(iter_stream_events(resp, "openai"))
        assert any(e.event_type == "error" for e in events)

    def test_provider_error_event(self):
        lines = ['data: {"error":{"message":"rate limited","type":"rate_limit"}}', ""]
        resp = _make_response(lines)
        events = list(iter_stream_events(resp, "openai"))
        assert any(e.event_type == "error" for e in events)
