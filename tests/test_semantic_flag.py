"""Tests for semantic retrieval feature flag in context compiler."""

from __future__ import annotations

import os
from unittest.mock import patch


class TestSemanticRetrievalFlag:
    def test_default_off_no_semantic_call(self):
        """Default OFF: semantic_search is never called."""
        from ao_kernel.context.context_compiler import compile_context

        ctx = {
            "ephemeral_decisions": [
                {"key": "lang", "value": "python", "source": "agent", "created_at": "2026-01-01T00:00:00Z"},
            ],
        }

        with patch("ao_kernel.context.semantic_retrieval.semantic_search") as mock_ss:
            result = compile_context(
                ctx,
                messages=[{"role": "user", "content": "hello"}],
            )
            mock_ss.assert_not_called()
            assert result.items_included >= 0  # compiles normally

    def test_env_var_enables_semantic(self):
        """AO_SEMANTIC_SEARCH=1 enables semantic reranking."""
        from ao_kernel.context.context_compiler import compile_context

        ctx = {
            "ephemeral_decisions": [
                {"key": "lang", "value": "python", "source": "agent", "created_at": "2026-01-01T00:00:00Z"},
            ],
        }

        with (
            patch.dict(os.environ, {"AO_SEMANTIC_SEARCH": "1"}),
            patch("ao_kernel.context.semantic_retrieval.semantic_search", return_value=[]) as mock_ss,
        ):
            result = compile_context(
                ctx,
                messages=[{"role": "user", "content": "what language should I use?"}],
            )
            mock_ss.assert_called_once()
            assert result.items_included >= 0

    def test_explicit_param_overrides_env(self):
        """enable_semantic_search=False overrides env var."""
        from ao_kernel.context.context_compiler import compile_context

        ctx = {
            "ephemeral_decisions": [
                {"key": "lang", "value": "python", "source": "agent", "created_at": "2026-01-01T00:00:00Z"},
            ],
        }

        with (
            patch.dict(os.environ, {"AO_SEMANTIC_SEARCH": "1"}),
            patch("ao_kernel.context.semantic_retrieval.semantic_search") as mock_ss,
        ):
            result = compile_context(
                ctx,
                messages=[{"role": "user", "content": "hello"}],
                enable_semantic_search=False,
            )
            mock_ss.assert_not_called()
            assert result.items_included >= 0

    def test_no_api_key_graceful_fallback(self):
        """When semantic_search returns empty (no API key), deterministic order preserved."""
        from ao_kernel.context.context_compiler import compile_context

        decisions = [
            {"key": "arch.pattern", "value": "microservices", "source": "agent",
             "created_at": "2026-01-01T00:00:00Z", "confidence": 0.9},
            {"key": "lang", "value": "python", "source": "agent",
             "created_at": "2026-01-02T00:00:00Z", "confidence": 0.5},
        ]
        ctx = {"ephemeral_decisions": decisions}

        # Without semantic: compile deterministically
        result_off = compile_context(ctx, messages=[{"role": "user", "content": "hello"}])

        # With semantic enabled but returning empty (no API key)
        with patch("ao_kernel.context.semantic_retrieval.semantic_search", return_value=[]):
            result_on = compile_context(
                ctx,
                messages=[{"role": "user", "content": "hello"}],
                enable_semantic_search=True,
            )

        # Same result — deterministic fallback preserved
        assert result_off.items_included == result_on.items_included
        assert result_off.preamble == result_on.preamble
