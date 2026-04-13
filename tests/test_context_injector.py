"""Tests for Context Injector — preamble building + message injection."""

from __future__ import annotations

from ao_kernel.context.context_injector import (
    build_context_preamble,
    inject_context_into_messages,
)


class TestBuildContextPreamble:
    def test_empty_context_returns_empty(self):
        assert build_context_preamble({}) == ""
        assert build_context_preamble(None) == ""

    def test_decisions_formatted(self):
        context = {
            "decisions": [
                {"key": "runtime.python", "value": "3.11", "source": "agent", "created_at": "2026-01-01T00:00:00Z"},
                {"key": "deploy.target", "value": "staging", "source": "user_chat", "created_at": "2026-01-02T00:00:00Z"},
            ],
        }
        preamble = build_context_preamble(context)
        assert "runtime.python" in preamble
        assert "3.11" in preamble
        assert "deploy.target" in preamble
        assert "Prior Decisions" in preamble

    def test_relevance_filter(self):
        context = {
            "decisions": [
                {"key": "runtime.python", "value": "3.11", "created_at": "2026-01-01T00:00:00Z"},
                {"key": "deploy.target", "value": "staging", "created_at": "2026-01-01T00:00:00Z"},
            ],
        }
        preamble = build_context_preamble(context, relevance_filter="runtime.")
        assert "runtime.python" in preamble
        assert "deploy.target" not in preamble

    def test_token_budget_enforced(self):
        context = {
            "decisions": [
                {"key": f"key_{i}", "value": "x" * 100, "created_at": "2026-01-01T00:00:00Z"}
                for i in range(100)
            ],
        }
        preamble = build_context_preamble(context, max_tokens=50)
        # 50 tokens * 4 chars = 200 chars max
        assert len(preamble) <= 250  # some margin for truncation marker

    def test_provider_state_included(self):
        context = {
            "provider_state": {
                "conversation_id": "conv-123",
                "last_response_id": "resp-456",
                "memory_strategy": "hybrid",
            },
        }
        preamble = build_context_preamble(context)
        assert "conv-123" in preamble
        assert "Session State" in preamble

    def test_workspace_facts_plugin(self):
        context = {"decisions": []}
        facts = {
            "facts": {
                "runtime.python": {"value": "3.11", "confidence": 0.95},
                "team.size": {"value": 5, "confidence": 0.8},
            }
        }
        preamble = build_context_preamble(context, include_facts=facts)
        assert "Workspace Facts" in preamble
        assert "runtime.python" in preamble
        assert "3.11" in preamble


class TestInjectContextIntoMessages:
    def test_prepend_to_existing_system(self):
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]
        context = {
            "decisions": [
                {"key": "mode", "value": "production", "created_at": "2026-01-01T00:00:00Z"},
            ],
        }
        result = inject_context_into_messages(messages, context)
        assert result[0]["role"] == "system"
        assert "mode: production" in result[0]["content"]
        assert "You are helpful." in result[0]["content"]
        assert len(result) == 2

    def test_insert_system_if_missing(self):
        messages = [{"role": "user", "content": "Hello"}]
        context = {
            "decisions": [
                {"key": "lang", "value": "en", "created_at": "2026-01-01T00:00:00Z"},
            ],
        }
        result = inject_context_into_messages(messages, context)
        assert len(result) == 2
        assert result[0]["role"] == "system"
        assert "lang: en" in result[0]["content"]

    def test_no_context_returns_original(self):
        messages = [{"role": "user", "content": "Hello"}]
        result = inject_context_into_messages(messages, {})
        assert result == messages

    def test_does_not_mutate_input(self):
        messages = [{"role": "system", "content": "Original"}]
        context = {
            "decisions": [{"key": "k", "value": "v", "created_at": "2026-01-01T00:00:00Z"}],
        }
        result = inject_context_into_messages(messages, context)
        assert messages[0]["content"] == "Original"  # Not mutated
        assert "k: v" in result[0]["content"]
