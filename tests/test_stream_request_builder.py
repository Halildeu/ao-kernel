"""Tests for streaming request builder changes."""

from __future__ import annotations

import json

import pytest

from src.prj_kernel_api.llm_request_builder import build_live_request


class TestStreamRequestBuilder:
    def test_stream_true_adds_flag(self):
        req = build_live_request(
            provider_id="openai",
            model="gpt-4",
            messages=[{"role": "user", "content": "hi"}],
            base_url="https://api.openai.com/v1/chat/completions",
            api_key="sk-test",
            stream=True,
        )
        body = req["body_json"]
        assert body["stream"] is True

    def test_stream_false_no_flag(self):
        req = build_live_request(
            provider_id="openai",
            model="gpt-4",
            messages=[{"role": "user", "content": "hi"}],
            base_url="https://api.openai.com/v1/chat/completions",
            api_key="sk-test",
            stream=False,
        )
        body = req["body_json"]
        assert "stream" not in body

    def test_stream_with_tools_raises(self):
        with pytest.raises(ValueError, match="stream=True with tools"):
            build_live_request(
                provider_id="openai",
                model="gpt-4",
                messages=[{"role": "user", "content": "hi"}],
                base_url="https://api.openai.com/v1/chat/completions",
                api_key="sk-test",
                stream=True,
                tools=[{"type": "function", "function": {"name": "test"}}],
            )

    def test_google_stream_endpoint(self):
        req = build_live_request(
            provider_id="google",
            model="gemini-pro",
            messages=[{"role": "user", "content": "hi"}],
            base_url="https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent",
            api_key="key-test",
            stream=True,
        )
        assert "streamGenerateContent" in req["url"]
        assert "alt=sse" in req["url"]

    def test_anthropic_stream(self):
        req = build_live_request(
            provider_id="claude",
            model="claude-3-opus",
            messages=[{"role": "user", "content": "hi"}],
            base_url="https://api.anthropic.com/v1/messages",
            api_key="sk-ant-test",
            stream=True,
        )
        body = req["body_json"]
        assert body["stream"] is True
        assert req["headers"]["anthropic-version"] == "2023-06-01"
