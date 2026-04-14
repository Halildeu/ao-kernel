"""Tests for ao_kernel.context.vector_store_resolver (B1a, CNS-007).

Covers env + policy + constructor precedence with fail-closed flow.
Avoids importing the pgvector C-extension on machines without it by
mocking PgvectorBackend at the import path used by the resolver.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from ao_kernel.context.vector_store import InMemoryVectorStore
from ao_kernel.context.vector_store_resolver import resolve_vector_store
from ao_kernel.errors import VectorStoreConfigError, VectorStoreConnectError


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Start every test with a clean AO_KERNEL_* env."""
    for name in (
        "AO_KERNEL_VECTOR_BACKEND",
        "AO_KERNEL_PGVECTOR_DSN",
        "AO_KERNEL_VECTOR_STRICT",
        "AO_KERNEL_PGVECTOR_TABLE",
        "AO_KERNEL_EMBEDDING_DIMENSION",
    ):
        monkeypatch.delenv(name, raising=False)


class TestDefaultResolution:
    def test_no_env_no_policy_returns_disabled(self):
        backend, owned = resolve_vector_store()
        assert backend is None
        assert owned is False

    def test_explicit_disabled_env(self, monkeypatch):
        monkeypatch.setenv("AO_KERNEL_VECTOR_BACKEND", "disabled")
        backend, owned = resolve_vector_store()
        assert backend is None
        assert owned is False


class TestInjection:
    def test_injected_backend_wins_over_env(self, monkeypatch):
        monkeypatch.setenv("AO_KERNEL_VECTOR_BACKEND", "inmemory")
        injected = InMemoryVectorStore()
        backend, owned = resolve_vector_store(injected=injected)
        assert backend is injected
        assert owned is False, "injected backends are caller-owned"

    def test_injected_bypass_policy_disable(self):
        injected = InMemoryVectorStore()
        backend, owned = resolve_vector_store(injected=injected)
        # Default policy has enabled=false, but injection still wins.
        assert backend is injected
        assert owned is False


class TestInMemoryPath:
    def test_env_inmemory_instantiates(self, monkeypatch):
        monkeypatch.setenv("AO_KERNEL_VECTOR_BACKEND", "inmemory")
        backend, owned = resolve_vector_store()
        assert isinstance(backend, InMemoryVectorStore)
        assert owned is True


class TestPgvectorConfigErrors:
    def test_pgvector_without_dsn_raises(self, monkeypatch):
        monkeypatch.setenv("AO_KERNEL_VECTOR_BACKEND", "pgvector")
        with pytest.raises(VectorStoreConfigError, match="AO_KERNEL_PGVECTOR_DSN"):
            resolve_vector_store()

    def test_invalid_backend_name_raises(self, monkeypatch):
        monkeypatch.setenv("AO_KERNEL_VECTOR_BACKEND", "redis")
        with pytest.raises(VectorStoreConfigError, match="Invalid vector backend"):
            resolve_vector_store()

    def test_invalid_dimension_env_raises(self, monkeypatch):
        monkeypatch.setenv("AO_KERNEL_VECTOR_BACKEND", "pgvector")
        monkeypatch.setenv("AO_KERNEL_PGVECTOR_DSN", "postgresql://x")
        monkeypatch.setenv("AO_KERNEL_EMBEDDING_DIMENSION", "not-a-number")
        with pytest.raises(VectorStoreConfigError, match="positive integer"):
            resolve_vector_store()

    def test_negative_dimension_rejected(self, monkeypatch):
        monkeypatch.setenv("AO_KERNEL_VECTOR_BACKEND", "pgvector")
        monkeypatch.setenv("AO_KERNEL_PGVECTOR_DSN", "postgresql://x")
        monkeypatch.setenv("AO_KERNEL_EMBEDDING_DIMENSION", "-1")
        with pytest.raises(VectorStoreConfigError, match="must be positive"):
            resolve_vector_store()


class TestPgvectorStrictness:
    def test_connect_fail_strict_env_raises(self, monkeypatch):
        monkeypatch.setenv("AO_KERNEL_VECTOR_BACKEND", "pgvector")
        monkeypatch.setenv("AO_KERNEL_PGVECTOR_DSN", "postgresql://x")
        monkeypatch.setenv("AO_KERNEL_VECTOR_STRICT", "1")
        # Force instantiation failure via the pgvector module import path.
        with patch(
            "ao_kernel.context.vector_store_pgvector.PgvectorBackend",
            side_effect=RuntimeError("connect refused"),
        ):
            with pytest.raises(VectorStoreConnectError, match="connect refused"):
                resolve_vector_store()

    def test_connect_fail_non_strict_falls_back(self, monkeypatch, caplog):
        monkeypatch.setenv("AO_KERNEL_VECTOR_BACKEND", "pgvector")
        monkeypatch.setenv("AO_KERNEL_PGVECTOR_DSN", "postgresql://x")
        # Strict explicitly off — existing contract: fall back to deterministic.
        monkeypatch.setenv("AO_KERNEL_VECTOR_STRICT", "0")
        with patch(
            "ao_kernel.context.vector_store_pgvector.PgvectorBackend",
            side_effect=RuntimeError("connect refused"),
        ):
            backend, owned = resolve_vector_store()
        assert backend is None
        assert owned is False

    def test_successful_pgvector_constructs_owned(self, monkeypatch):
        monkeypatch.setenv("AO_KERNEL_VECTOR_BACKEND", "pgvector")
        monkeypatch.setenv("AO_KERNEL_PGVECTOR_DSN", "postgresql://x")
        fake = MagicMock()
        with patch(
            "ao_kernel.context.vector_store_pgvector.PgvectorBackend",
            return_value=fake,
        ) as ctor:
            backend, owned = resolve_vector_store()
        assert backend is fake
        assert owned is True
        # Sanity: dimension env default 1536 was passed through.
        _, kwargs = ctor.call_args
        assert kwargs["dimension"] == 1536
