"""Behavioral tests for ``build_request_with_context`` — ``injected_messages``
return field.

CNS-032 post-merge scope absorb: v5 iter-4 B4 added ``injected_messages``
to the return dict of ``build_request_with_context`` so cost middleware can
estimate prompt tokens over the effective (context-injected) prompt rather
than the caller-supplied raw messages. The field is currently pinned via a
docstring-guard regression test; this file upgrades to an observable
behavioral contract — the dict shape and content are asserted directly.
"""

from __future__ import annotations

from typing import Any

from ao_kernel.llm import build_request_with_context


def _base_kwargs() -> dict[str, Any]:
    return dict(
        provider_id="anthropic",
        model="claude-3-5-sonnet",
        base_url="https://api.anthropic.test/v1",
        api_key="test-key",
        request_id="req-injected-1",
    )


class TestInjectedMessagesFieldPresence:
    def test_field_present_with_session_context(self) -> None:
        """When session_context is non-empty, the return dict carries
        an ``injected_messages`` field."""
        messages = [{"role": "user", "content": "hello"}]
        session_context = {
            "ephemeral_decisions": [
                {
                    "key": "api.endpoint",
                    "value": "/v1/users",
                    "confidence": 0.9,
                    "created_at": "2026-04-17T10:00:00+00:00",
                },
            ],
        }

        result = build_request_with_context(
            messages=messages,
            session_context=session_context,
            **_base_kwargs(),
        )

        assert "injected_messages" in result
        assert isinstance(result["injected_messages"], list)

    def test_field_present_without_session_context(self) -> None:
        """When session_context is None, ``injected_messages`` is still
        populated (reflecting the unmodified input messages) so callers
        never have to branch on presence."""
        messages = [{"role": "user", "content": "hi"}]
        result = build_request_with_context(
            messages=messages,
            **_base_kwargs(),
        )

        assert "injected_messages" in result
        assert result["injected_messages"] == messages


class TestInjectedMessagesRoundtrip:
    def test_decisions_inject_system_preamble(self) -> None:
        """session_context with ephemeral_decisions → compile_context
        produces a non-empty preamble → injected_messages prepends a
        system message that differs from the raw input."""
        raw_messages = [
            {"role": "user", "content": "list users"},
        ]
        session_context = {
            "ephemeral_decisions": [
                {
                    "key": "api.endpoint",
                    "value": "/v1/users",
                    "confidence": 0.9,
                    "created_at": "2026-04-17T10:00:00+00:00",
                },
                {
                    "key": "api.method",
                    "value": "GET",
                    "confidence": 0.85,
                    "created_at": "2026-04-17T10:01:00+00:00",
                },
            ],
        }

        result = build_request_with_context(
            messages=raw_messages,
            session_context=session_context,
            **_base_kwargs(),
        )

        injected = result["injected_messages"]
        assert injected != raw_messages, (
            "session decisions must change the effective prompt"
        )
        # System preamble is the first element.
        assert injected[0].get("role") == "system"
        preamble = injected[0].get("content", "")
        assert "api.endpoint" in preamble
        assert "/v1/users" in preamble
        assert "api.method" in preamble
        # Original user turn is preserved (tail intact).
        assert injected[-1] == raw_messages[-1]

    def test_existing_system_message_merged_not_replaced(self) -> None:
        """If the caller already has a system message, the preamble is
        prefixed to it rather than replacing it (both pieces survive)."""
        raw_messages = [
            {"role": "system", "content": "You are a concise assistant."},
            {"role": "user", "content": "hello"},
        ]
        session_context = {
            "ephemeral_decisions": [
                {
                    "key": "tone.preference",
                    "value": "terse",
                    "confidence": 0.8,
                    "created_at": "2026-04-17T10:00:00+00:00",
                },
            ],
        }

        result = build_request_with_context(
            messages=raw_messages,
            session_context=session_context,
            **_base_kwargs(),
        )

        injected = result["injected_messages"]
        assert injected[0]["role"] == "system"
        merged = injected[0]["content"]
        # Original system content retained.
        assert "concise assistant" in merged
        # Preamble prepended with the decision.
        assert "tone.preference" in merged or "terse" in merged

    def test_empty_session_context_is_identity(self) -> None:
        """session_context with no decisions → compile_context yields an
        empty preamble → injected_messages == raw input (no mutation)."""
        raw_messages = [{"role": "user", "content": "hi"}]
        session_context: dict[str, Any] = {"ephemeral_decisions": []}

        result = build_request_with_context(
            messages=raw_messages,
            session_context=session_context,
            **_base_kwargs(),
        )

        assert result["injected_messages"] == raw_messages


class TestInjectedMessagesBackwardCompat:
    def test_caller_can_ignore_extra_field(self) -> None:
        """Pre-B2 callers extract ``body_bytes``/``url``/``headers`` and
        never read ``injected_messages``; the additive field does not
        break the existing dict contract."""
        messages = [{"role": "user", "content": "hello"}]
        result = build_request_with_context(
            messages=messages,
            session_context={"ephemeral_decisions": []},
            **_base_kwargs(),
        )

        for required_key in ("url", "headers", "body_bytes"):
            assert required_key in result, (
                f"build_request_with_context must preserve {required_key!r} "
                f"even with injected_messages field added"
            )
