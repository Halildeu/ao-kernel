"""Tests for tool streaming — stream+tools support (v0.3.0)."""

from __future__ import annotations

import json



class TestStreamToolsAllowed:
    def test_stream_with_tools_no_longer_raises(self):
        from src.prj_kernel_api.llm_request_builder import build_live_request
        req = build_live_request(
            provider_id="openai",
            model="gpt-4",
            messages=[{"role": "user", "content": "hi"}],
            base_url="https://api.openai.com/v1/chat/completions",
            api_key="sk-test",
            stream=True,
            tools=[{"type": "function", "function": {"name": "get_weather"}}],
        )
        assert req["body_json"]["stream"] is True
        assert len(req["body_json"]["tools"]) == 1

    def test_facade_stream_tools_works(self):
        from ao_kernel.llm import build_request
        req = build_request(
            provider_id="openai",
            model="gpt-4",
            messages=[{"role": "user", "content": "hi"}],
            base_url="https://api.openai.com/v1/chat/completions",
            api_key="sk-test",
            stream=True,
            tools=[{"type": "function", "function": {"name": "calc"}}],
        )
        assert req["body_json"]["stream"] is True


class TestToolCallReconstruction:
    def test_openai_tool_deltas(self):
        from src.prj_kernel_api.llm_stream_normalizer import reconstruct_tool_calls

        events = [
            {"choices": [{"delta": {"tool_calls": [
                {"index": 0, "id": "call_1", "function": {"name": "get_weather", "arguments": ""}},
            ]}}]},
            {"choices": [{"delta": {"tool_calls": [
                {"index": 0, "function": {"arguments": '{"city":'}},
            ]}}]},
            {"choices": [{"delta": {"tool_calls": [
                {"index": 0, "function": {"arguments": '"London"}'}},
            ]}}]},
        ]

        tools = reconstruct_tool_calls(events, "openai")
        assert len(tools) == 1
        assert tools[0]["function"]["name"] == "get_weather"
        args = json.loads(tools[0]["function"]["arguments"])
        assert args["city"] == "London"

    def test_openai_multiple_tools(self):
        from src.prj_kernel_api.llm_stream_normalizer import reconstruct_tool_calls

        events = [
            {"choices": [{"delta": {"tool_calls": [
                {"index": 0, "id": "call_1", "function": {"name": "tool_a", "arguments": '{"x":1}'}},
            ]}}]},
            {"choices": [{"delta": {"tool_calls": [
                {"index": 1, "id": "call_2", "function": {"name": "tool_b", "arguments": '{"y":2}'}},
            ]}}]},
        ]

        tools = reconstruct_tool_calls(events, "openai")
        assert len(tools) == 2
        names = {t["function"]["name"] for t in tools}
        assert "tool_a" in names
        assert "tool_b" in names

    def test_anthropic_tool_blocks(self):
        from src.prj_kernel_api.llm_stream_normalizer import reconstruct_tool_calls

        events = [
            {"type": "content_block_start", "index": 1, "content_block": {
                "type": "tool_use", "id": "toolu_1", "name": "search",
            }},
            {"type": "content_block_delta", "index": 1, "delta": {
                "type": "input_json_delta", "partial_json": '{"query":',
            }},
            {"type": "content_block_delta", "index": 1, "delta": {
                "type": "input_json_delta", "partial_json": '"test"}',
            }},
        ]

        tools = reconstruct_tool_calls(events, "claude")
        assert len(tools) == 1
        assert tools[0]["function"]["name"] == "search"
        args = json.loads(tools[0]["function"]["arguments"])
        assert args["query"] == "test"

    def test_empty_events_no_tools(self):
        from src.prj_kernel_api.llm_stream_normalizer import reconstruct_tool_calls
        assert reconstruct_tool_calls([], "openai") == []
        assert reconstruct_tool_calls([], "claude") == []

    def test_text_only_events_no_tools(self):
        from src.prj_kernel_api.llm_stream_normalizer import reconstruct_tool_calls
        events = [
            {"choices": [{"delta": {"content": "Hello"}}]},
            {"choices": [{"delta": {"content": " world"}}]},
        ]
        assert reconstruct_tool_calls(events, "openai") == []
