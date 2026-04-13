"""Unit tests for tool_calling.py — build, extract, normalize across providers."""

from __future__ import annotations

import json

from ao_kernel._internal.prj_kernel_api.tool_calling import (
    build_tools_param,
    build_tools_param_claude,
    build_tools_param_openai,
    extract_tool_calls,
    extract_tool_calls_claude,
    extract_tool_calls_openai,
    build_tool_result,
)


SAMPLE_TOOLS = [
    {"name": "get_weather", "description": "Get weather", "parameters": {"type": "object", "properties": {"city": {"type": "string"}}}},
    {"name": "search", "description": "Search", "parameters": {"type": "object", "properties": {"q": {"type": "string"}}}},
]


class TestBuildToolsParam:
    def test_claude_format(self):
        result = build_tools_param_claude(SAMPLE_TOOLS)
        assert len(result) == 2
        assert result[0]["name"] == "get_weather"
        assert "input_schema" in result[0]
        assert result[0]["input_schema"]["properties"]["city"]["type"] == "string"

    def test_openai_format(self):
        result = build_tools_param_openai(SAMPLE_TOOLS)
        assert len(result) == 2
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "get_weather"
        assert "parameters" in result[0]["function"]

    def test_dispatch_claude(self):
        result = build_tools_param("claude", SAMPLE_TOOLS)
        assert "input_schema" in result[0]

    def test_dispatch_openai_compatible(self):
        for provider in ("openai", "deepseek", "qwen", "xai", "google"):
            result = build_tools_param(provider, SAMPLE_TOOLS)
            assert result[0]["type"] == "function", f"Failed for {provider}"


class TestExtractToolCallsClaude:
    def test_normal_tool_use(self):
        resp = json.dumps({
            "content": [
                {"type": "text", "text": "Let me check the weather."},
                {"type": "tool_use", "id": "call_1", "name": "get_weather", "input": {"city": "Istanbul"}},
            ]
        }).encode()
        calls = extract_tool_calls_claude(resp)
        assert len(calls) == 1
        assert calls[0]["id"] == "call_1"
        assert calls[0]["name"] == "get_weather"
        assert calls[0]["input"]["city"] == "Istanbul"

    def test_empty_content(self):
        resp = json.dumps({"content": []}).encode()
        assert extract_tool_calls_claude(resp) == []

    def test_malformed_json(self):
        assert extract_tool_calls_claude(b"not json") == []

    def test_no_tool_use_blocks(self):
        resp = json.dumps({"content": [{"type": "text", "text": "Hello"}]}).encode()
        assert extract_tool_calls_claude(resp) == []


class TestExtractToolCallsOpenAI:
    def test_chat_completions_format(self):
        resp = json.dumps({
            "choices": [{"message": {"tool_calls": [
                {"id": "tc_1", "type": "function", "function": {"name": "search", "arguments": '{"q": "ao-kernel"}'}},
            ]}}]
        }).encode()
        calls = extract_tool_calls_openai(resp)
        assert len(calls) == 1
        assert calls[0]["id"] == "tc_1"
        assert calls[0]["name"] == "search"
        assert calls[0]["arguments"]["q"] == "ao-kernel"

    def test_responses_api_format(self):
        resp = json.dumps({
            "output": [
                {"type": "function_call", "call_id": "fc_1", "name": "get_weather", "arguments": '{"city": "Ankara"}'},
            ]
        }).encode()
        calls = extract_tool_calls_openai(resp)
        assert len(calls) == 1
        assert calls[0]["id"] == "fc_1"
        assert calls[0]["name"] == "get_weather"
        assert calls[0]["arguments"]["city"] == "Ankara"

    def test_malformed_arguments_json(self):
        resp = json.dumps({
            "choices": [{"message": {"tool_calls": [
                {"id": "tc_2", "type": "function", "function": {"name": "test", "arguments": "not valid json{"}},
            ]}}]
        }).encode()
        calls = extract_tool_calls_openai(resp)
        assert len(calls) == 1
        assert calls[0]["arguments"] == {}

    def test_empty_response(self):
        assert extract_tool_calls_openai(b"{}") == []


class TestExtractToolCallsDispatch:
    def test_claude_dispatch(self):
        resp = json.dumps({
            "content": [{"type": "tool_use", "id": "c1", "name": "test", "input": {"a": 1}}]
        }).encode()
        calls = extract_tool_calls("claude", resp)
        assert len(calls) == 1
        assert calls[0]["input"]["a"] == 1

    def test_openai_dispatch_normalizes_arguments_to_input(self):
        resp = json.dumps({
            "choices": [{"message": {"tool_calls": [
                {"id": "t1", "type": "function", "function": {"name": "fn", "arguments": '{"x": 2}'}},
            ]}}]
        }).encode()
        calls = extract_tool_calls("openai", resp)
        assert len(calls) == 1
        assert "input" in calls[0]
        assert "arguments" not in calls[0]
        assert calls[0]["input"]["x"] == 2


class TestBuildToolResult:
    def test_claude_tool_result(self):
        result = build_tool_result("claude", "call_1", {"status": "ok", "data": 42})
        assert result["type"] == "tool_result"
        assert result["tool_use_id"] == "call_1"
        assert isinstance(result["content"], str)
        assert json.loads(result["content"])["data"] == 42

    def test_openai_tool_result(self):
        result = build_tool_result("openai", "tc_1", {"answer": "yes"})
        assert result["role"] == "tool"
        assert result["tool_call_id"] == "tc_1"
        assert json.loads(result["content"])["answer"] == "yes"
