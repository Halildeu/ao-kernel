"""Contract tests for tool use pipeline — format conversion, extraction, registry graduation.

Verifies:
- build_tools_param idempotency (Claude + OpenAI formats)
- build_live_request integrates format conversion
- extract_tool_calls roundtrip (Claude + OpenAI)
- llm_call forwards tool_results to context pipeline
- capability registry graduation (experimental → supported)
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from ao_kernel._internal.prj_kernel_api.tool_calling import (
    build_tools_param_claude,
    build_tools_param_openai,
    extract_tool_calls,
)
from ao_kernel._internal.prj_kernel_api.llm_request_builder import build_live_request


# ── Canonical tool fixture ──

CANONICAL_TOOL = {
    "name": "get_weather",
    "description": "Get the current weather",
    "parameters": {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    },
}


# ── Format conversion contract ──


class TestBuildToolsParamContract:
    def test_claude_format_has_input_schema(self):
        """Claude format uses input_schema, not parameters."""
        result = build_tools_param_claude([CANONICAL_TOOL])
        tool = result[0]
        assert "input_schema" in tool
        assert "parameters" not in tool
        assert tool["name"] == "get_weather"
        assert tool["input_schema"]["properties"]["city"]["type"] == "string"

    def test_openai_format_has_function_wrapper(self):
        """OpenAI format wraps in {type: 'function', function: {...}}."""
        result = build_tools_param_openai([CANONICAL_TOOL])
        tool = result[0]
        assert tool["type"] == "function"
        assert "function" in tool
        assert tool["function"]["name"] == "get_weather"
        assert tool["function"]["parameters"]["properties"]["city"]["type"] == "string"

    def test_idempotent_claude_format(self):
        """Tools already in Claude format pass through unchanged."""
        claude_tool = {
            "name": "search",
            "description": "Search the web",
            "input_schema": {"type": "object", "properties": {"q": {"type": "string"}}},
        }
        result = build_tools_param_claude([claude_tool])
        assert result[0] is claude_tool  # same object, not rebuilt

    def test_idempotent_openai_format(self):
        """Tools already in OpenAI format pass through unchanged."""
        openai_tool = {
            "type": "function",
            "function": {
                "name": "search",
                "description": "Search the web",
                "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
            },
        }
        result = build_tools_param_openai([openai_tool])
        assert result[0] is openai_tool  # same object, not rebuilt

    def test_build_live_request_converts_tools_claude(self):
        """build_live_request applies format conversion for Claude."""
        req = build_live_request(
            provider_id="claude",
            model="claude-3-opus",
            messages=[{"role": "user", "content": "hi"}],
            base_url="https://api.anthropic.com/v1/messages",
            api_key="test",
            tools=[CANONICAL_TOOL],
        )
        body = json.loads(req["body_bytes"])
        tool = body["tools"][0]
        assert "input_schema" in tool
        assert "parameters" not in tool

    def test_build_live_request_converts_tools_openai(self):
        """build_live_request applies format conversion for OpenAI."""
        req = build_live_request(
            provider_id="openai",
            model="gpt-4",
            messages=[{"role": "user", "content": "hi"}],
            base_url="https://api.openai.com/v1/chat/completions",
            api_key="test",
            tools=[CANONICAL_TOOL],
        )
        body = json.loads(req["body_bytes"])
        tool = body["tools"][0]
        assert tool["type"] == "function"
        assert tool["function"]["name"] == "get_weather"


# ── Extraction roundtrip ──


class TestExtractToolCallsRoundtrip:
    def test_claude_roundtrip(self):
        """Claude: tool_use block → extract → normalized {id, name, input}."""
        resp = json.dumps({
            "content": [
                {"type": "text", "text": "Let me check the weather."},
                {
                    "type": "tool_use",
                    "id": "toolu_123",
                    "name": "get_weather",
                    "input": {"city": "Istanbul"},
                },
            ],
            "stop_reason": "tool_use",
        }).encode()
        calls = extract_tool_calls("claude", resp)
        assert len(calls) == 1
        assert calls[0]["id"] == "toolu_123"
        assert calls[0]["name"] == "get_weather"
        assert calls[0]["input"] == {"city": "Istanbul"}

    def test_openai_roundtrip(self):
        """OpenAI: tool_calls in choices → extract → normalized {id, name, input}."""
        resp = json.dumps({
            "choices": [{
                "message": {
                    "content": None,
                    "tool_calls": [{
                        "id": "call_abc",
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": '{"city": "Istanbul"}',
                        },
                    }],
                },
                "finish_reason": "tool_calls",
            }],
        }).encode()
        calls = extract_tool_calls("openai", resp)
        assert len(calls) == 1
        assert calls[0]["id"] == "call_abc"
        assert calls[0]["name"] == "get_weather"
        # Normalized: 'arguments' → 'input'
        assert calls[0]["input"] == {"city": "Istanbul"}


# ── Client tool_results forwarding ──


class TestLLMCallToolResults:
    def test_llm_call_forwards_tool_results(self, tmp_workspace: Path):
        """tool_results parameter reaches process_response_with_context."""
        from ao_kernel.client import AoKernelClient

        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        client.start_session()

        mock_response = json.dumps({
            "choices": [{"message": {"content": "Done."}}],
        }).encode()

        captured_kwargs: dict = {}

        def mock_process(output_text, ctx, **kwargs):
            captured_kwargs.update(kwargs)
            return ctx

        with (
            patch("ao_kernel.llm.check_capabilities", return_value=(True, "openai", [])),
            patch("ao_kernel.llm.build_request_with_context", return_value={
                "url": "u", "headers": {}, "body_bytes": b"{}",
            }),
            patch("ao_kernel.llm.execute_request", return_value={
                "status": "OK", "resp_bytes": mock_response, "elapsed_ms": 100,
            }),
            patch("ao_kernel.llm.normalize_response", return_value={"text": "Done.", "tool_calls": []}),
            patch("ao_kernel.llm.extract_usage", return_value=None),
            patch("ao_kernel.llm.process_response_with_context", side_effect=mock_process),
        ):
            client.llm_call(
                messages=[{"role": "user", "content": "test"}],
                provider_id="openai",
                model="gpt-4",
                api_key="k",
                tool_results=[{"name": "get_weather", "output": {"temp": 22}}],
            )

        assert captured_kwargs.get("tool_results") is not None
        assert captured_kwargs["tool_results"][0]["name"] == "get_weather"


# ── Registry graduation ──


class TestCapabilityRegistryGraduation:
    def test_tool_use_supported_for_active_providers(self):
        """tool_use graduated from experimental to supported for 5 providers."""
        from ao_kernel.config import load_default

        registry = load_default("registry", "provider_capability_registry.v1.json")
        providers = registry["providers"]

        for pid in ("claude", "openai", "deepseek", "qwen", "xai"):
            status = providers[pid]["capabilities"]["tool_use"]
            assert status == "supported", f"{pid} tool_use should be 'supported', got '{status}'"

    def test_tool_use_unsupported_for_google(self):
        """Google still unsupported for tool_use (no integration)."""
        from ao_kernel.config import load_default

        registry = load_default("registry", "provider_capability_registry.v1.json")
        assert registry["providers"]["google"]["capabilities"]["tool_use"] == "unsupported"
