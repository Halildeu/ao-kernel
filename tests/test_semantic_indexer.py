"""Tests for ao_kernel.context.semantic_indexer (B1c, CNS-007).

Write-path contract: all failures are silent (debug-logged) and return
False; the caller must NEVER gate logic on the return value — this
keeps the deterministic fallback contract intact.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ao_kernel.context.embedding_config import EmbeddingConfig
from ao_kernel.context.semantic_indexer import index_decision


class TestNoOpPaths:
    def test_no_backend_returns_false(self):
        result = index_decision(key="k", value="v", vector_store=None)
        assert result is False

    def test_no_api_key_returns_false(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        backend = MagicMock()
        cfg = EmbeddingConfig()
        assert index_decision(
            key="k", value="v",
            vector_store=backend,
            embedding_config=cfg,
        ) is False
        backend.store.assert_not_called()

    def test_embed_returns_none_returns_false(self):
        backend = MagicMock()
        cfg = EmbeddingConfig(api_key="sk-fake")
        with patch(
            "ao_kernel.context.semantic_retrieval.embed_text",
            return_value=None,
        ):
            assert index_decision(
                key="k", value="v",
                vector_store=backend,
                embedding_config=cfg,
            ) is False
        backend.store.assert_not_called()

    def test_embed_raises_returns_false(self):
        backend = MagicMock()
        cfg = EmbeddingConfig(api_key="sk-fake")
        with patch(
            "ao_kernel.context.semantic_retrieval.embed_text",
            side_effect=RuntimeError("network"),
        ):
            assert index_decision(
                key="k", value="v",
                vector_store=backend,
                embedding_config=cfg,
            ) is False
        backend.store.assert_not_called()

    def test_store_raises_is_swallowed(self):
        backend = MagicMock()
        backend.store.side_effect = RuntimeError("db down")
        cfg = EmbeddingConfig(api_key="sk-fake")
        with patch(
            "ao_kernel.context.semantic_retrieval.embed_text",
            return_value=[0.1, 0.2],
        ):
            assert index_decision(
                key="k", value="v",
                vector_store=backend,
                embedding_config=cfg,
            ) is False


class TestSuccessfulIndex:
    @pytest.fixture
    def backend(self):
        return MagicMock()

    @pytest.fixture
    def cfg(self):
        return EmbeddingConfig(api_key="sk-fake")

    def test_store_called_with_namespace_key(self, backend, cfg):
        with patch(
            "ao_kernel.context.semantic_retrieval.embed_text",
            return_value=[0.1] * 5,
        ):
            result = index_decision(
                key="decision-1",
                value="some payload",
                namespace="session-abc",
                vector_store=backend,
                embedding_config=cfg,
            )
        assert result is True
        args, kwargs = backend.store.call_args
        assert args[0] == "session-abc::decision-1"
        assert args[1] == [0.1] * 5

    def test_no_namespace_passes_raw_key(self, backend, cfg):
        with patch(
            "ao_kernel.context.semantic_retrieval.embed_text",
            return_value=[0.1] * 3,
        ):
            index_decision(
                key="raw-key",
                value="x",
                vector_store=backend,
                embedding_config=cfg,
            )
        args, _ = backend.store.call_args
        assert args[0] == "raw-key"

    def test_metadata_includes_source_model_provider(self, backend, cfg):
        with patch(
            "ao_kernel.context.semantic_retrieval.embed_text",
            return_value=[0.0],
        ):
            index_decision(
                key="k",
                value="v",
                source="canonical:general",
                vector_store=backend,
                embedding_config=cfg,
            )
        _, kwargs = backend.store.call_args
        meta = kwargs["metadata"]
        assert meta["source"] == "canonical:general"
        assert meta["embedding_model"] == cfg.model
        assert meta["embedding_provider"] == cfg.provider

    def test_extra_metadata_merged(self, backend, cfg):
        with patch(
            "ao_kernel.context.semantic_retrieval.embed_text",
            return_value=[0.0],
        ):
            index_decision(
                key="k", value="v",
                vector_store=backend,
                embedding_config=cfg,
                extra_metadata={"confidence": 0.95, "tag": "important"},
            )
        _, kwargs = backend.store.call_args
        meta = kwargs["metadata"]
        assert meta["confidence"] == 0.95
        assert meta["tag"] == "important"
        # Base metadata still present
        assert "source" in meta

    def test_namespace_recorded_in_metadata(self, backend, cfg):
        with patch(
            "ao_kernel.context.semantic_retrieval.embed_text",
            return_value=[0.0],
        ):
            index_decision(
                key="k", value="v",
                namespace="ns-1",
                vector_store=backend,
                embedding_config=cfg,
            )
        _, kwargs = backend.store.call_args
        assert kwargs["metadata"]["namespace"] == "ns-1"
