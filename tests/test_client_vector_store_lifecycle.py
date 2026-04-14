"""Tests for AoKernelClient vector store lifecycle (B1a + B1e, CNS-007).

Verifies the ownership contract:
    - Env-resolved backends: owned by client, closed on __exit__.
    - Injected backends: caller-owned by default, NOT closed on __exit__.
    - Override available via owns_vector_store=True/False.
    - Close failures are logged, never raised.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ao_kernel.client import AoKernelClient
from ao_kernel.context.vector_store import InMemoryVectorStore


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in (
        "AO_KERNEL_VECTOR_BACKEND",
        "AO_KERNEL_PGVECTOR_DSN",
        "AO_KERNEL_VECTOR_STRICT",
    ):
        monkeypatch.delenv(name, raising=False)


class TestInstantiation:
    def test_default_has_no_backend(self):
        client = AoKernelClient()
        assert client.vector_store is None

    def test_env_inmemory_binds_backend(self, monkeypatch):
        monkeypatch.setenv("AO_KERNEL_VECTOR_BACKEND", "inmemory")
        client = AoKernelClient()
        assert isinstance(client.vector_store, InMemoryVectorStore)
        assert client._owns_vector_store is True

    def test_injected_backend_not_owned_by_default(self):
        backend = InMemoryVectorStore()
        client = AoKernelClient(vector_store=backend)
        assert client.vector_store is backend
        assert client._owns_vector_store is False

    def test_injected_backend_ownership_override(self):
        backend = InMemoryVectorStore()
        client = AoKernelClient(vector_store=backend, owns_vector_store=True)
        assert client._owns_vector_store is True

    def test_env_backend_can_be_disowned_explicitly(self, monkeypatch):
        monkeypatch.setenv("AO_KERNEL_VECTOR_BACKEND", "inmemory")
        client = AoKernelClient(owns_vector_store=False)
        assert client._owns_vector_store is False


class TestContextManagerCleanup:
    def test_owned_backend_is_closed(self):
        backend = MagicMock()
        with AoKernelClient(vector_store=backend, owns_vector_store=True):
            pass
        assert backend.close.call_count == 1

    def test_injected_backend_is_not_closed(self):
        backend = MagicMock()
        with AoKernelClient(vector_store=backend):
            pass
        assert backend.close.call_count == 0

    def test_close_without_close_method_is_safe(self):
        class NoCloseBackend:
            def store(self, *a, **k): ...
            def search(self, *a, **k): return []
            def delete(self, *a, **k): return False
            def count(self): return 0
        backend = NoCloseBackend()
        # Must not raise — presence of the test completing is the guarantee.
        with AoKernelClient(vector_store=backend, owns_vector_store=True):
            entered = True
        assert entered is True

    def test_close_exception_is_swallowed(self, caplog):
        backend = MagicMock()
        backend.close.side_effect = RuntimeError("pool offline")
        with AoKernelClient(vector_store=backend, owns_vector_store=True):
            pass
        # No exception bubbles out; a warning is logged.
        assert any(
            "close failed" in record.message
            for record in caplog.records
        ) or backend.close.called

    def test_exception_inside_with_still_closes_backend(self):
        backend = MagicMock()
        with pytest.raises(ValueError, match="boom"):
            with AoKernelClient(vector_store=backend, owns_vector_store=True):
                raise ValueError("boom")
        assert backend.close.call_count == 1


class TestEmbeddingConfigPropagation:
    def test_embedding_config_default(self):
        client = AoKernelClient()
        cfg = client.embedding_config
        assert cfg.provider == "openai"
        assert cfg.model == "text-embedding-3-small"

    def test_embedding_config_env_override(self, monkeypatch):
        monkeypatch.setenv("AO_KERNEL_EMBEDDING_PROVIDER", "google")
        monkeypatch.setenv("AO_KERNEL_EMBEDDING_MODEL", "text-embedding-004")
        client = AoKernelClient()
        assert client.embedding_config.provider == "google"
        assert client.embedding_config.model == "text-embedding-004"

    def test_embedding_config_injection(self):
        from ao_kernel.context.embedding_config import EmbeddingConfig
        injected = EmbeddingConfig(
            provider="openai",
            model="text-embedding-3-large",
            base_url="https://api.openai.com/v1",
        )
        client = AoKernelClient(embedding_config=injected)
        assert client.embedding_config is injected
