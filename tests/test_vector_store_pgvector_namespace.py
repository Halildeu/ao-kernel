"""Tests for pgvector model/dimension namespace enforcement (B1d, CNS-007).

All tests use a mocked psycopg2 connection so they run without a live
database or the pgvector C-extension. An end-to-end integration test
lives under an optional CI job (see contributor docs).
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest

from ao_kernel.errors import VectorStoreConfigError


def _make_fake_cursor() -> MagicMock:
    cur = MagicMock()
    cur.__enter__ = MagicMock(return_value=cur)
    cur.__exit__ = MagicMock(return_value=False)
    cur.rowcount = 0
    cur.fetchall = MagicMock(return_value=[])
    cur.fetchone = MagicMock(return_value=(0,))
    return cur


def _install_fake_psycopg2(monkeypatch):
    """Stub psycopg2 + pgvector.psycopg2 so PgvectorBackend can import."""
    fake_psycopg2 = types.ModuleType("psycopg2")
    fake_conn = MagicMock()
    fake_conn.closed = False
    fake_cursor = _make_fake_cursor()
    fake_conn.cursor.return_value = fake_cursor
    fake_psycopg2.connect = MagicMock(return_value=fake_conn)
    monkeypatch.setitem(sys.modules, "psycopg2", fake_psycopg2)

    fake_pgvector_mod = types.ModuleType("pgvector")
    fake_pgvector_psycopg2 = types.ModuleType("pgvector.psycopg2")
    fake_pgvector_psycopg2.register_vector = MagicMock()
    monkeypatch.setitem(sys.modules, "pgvector", fake_pgvector_mod)
    monkeypatch.setitem(sys.modules, "pgvector.psycopg2", fake_pgvector_psycopg2)

    return fake_conn, fake_cursor


@pytest.fixture
def pgvector_env(monkeypatch):
    conn, cur = _install_fake_psycopg2(monkeypatch)
    from ao_kernel.context.vector_store_pgvector import PgvectorBackend
    return PgvectorBackend, conn, cur


class TestDimensionValidation:
    def test_store_dimension_mismatch_raises(self, pgvector_env):
        PgvectorBackend, _, _ = pgvector_env
        backend = PgvectorBackend(dsn="postgresql://x", dimension=4)
        with pytest.raises(VectorStoreConfigError, match="dimension mismatch"):
            backend.store("k", [0.1, 0.2, 0.3])  # len 3 ≠ 4

    def test_search_dimension_mismatch_returns_empty(self, pgvector_env):
        PgvectorBackend, _, _ = pgvector_env
        backend = PgvectorBackend(dsn="postgresql://x", dimension=4)
        out = backend.search([0.1, 0.2])  # len 2 ≠ 4
        assert out == []


class TestModelNamespace:
    def test_store_model_mismatch_raises(self, pgvector_env):
        PgvectorBackend, _, _ = pgvector_env
        backend = PgvectorBackend(
            dsn="postgresql://x",
            dimension=2,
            embedding_model="text-embedding-3-small",
        )
        with pytest.raises(VectorStoreConfigError, match="model mismatch"):
            backend.store(
                "k", [0.0, 0.0],
                metadata={"embedding_model": "text-embedding-3-large"},
            )

    def test_store_defaults_model_tag_from_backend(self, pgvector_env):
        PgvectorBackend, _, cur = pgvector_env
        backend = PgvectorBackend(
            dsn="postgresql://x",
            dimension=2,
            embedding_model="m-v1",
        )
        backend.store("k", [0.0, 0.0])  # no metadata passed
        # Last execute should be the INSERT; the 3rd positional param is
        # the model tag.
        insert_call = [
            c for c in cur.execute.call_args_list
            if "INSERT INTO" in c.args[0]
        ][-1]
        params = insert_call.args[1]
        assert params[2] == "m-v1"

    def test_search_applies_model_filter_when_bound(self, pgvector_env):
        PgvectorBackend, _, cur = pgvector_env
        backend = PgvectorBackend(
            dsn="postgresql://x",
            dimension=2,
            embedding_model="m-v1",
        )
        backend.search([0.1, 0.2])
        select_calls = [
            c for c in cur.execute.call_args_list
            if "SELECT key" in c.args[0]
        ]
        assert select_calls, "no SELECT query executed by search()"
        sql = select_calls[-1].args[0]
        assert "embedding_model = %s" in sql

    def test_search_no_filter_when_unbound(self, pgvector_env):
        PgvectorBackend, _, cur = pgvector_env
        backend = PgvectorBackend(dsn="postgresql://x", dimension=2)
        # embedding_model="" means no namespace binding
        backend.search([0.1, 0.2])
        select_calls = [
            c for c in cur.execute.call_args_list
            if "SELECT key" in c.args[0]
        ]
        assert select_calls, "no SELECT query executed by search()"
        sql = select_calls[-1].args[0]
        assert "embedding_model = %s" not in sql


class TestSchemaMigration:
    def test_ensure_table_emits_alter_add_column(self, pgvector_env):
        PgvectorBackend, _, cur = pgvector_env
        PgvectorBackend(dsn="postgresql://x", dimension=2, embedding_model="m-v1")
        stmts = [c.args[0] for c in cur.execute.call_args_list]
        assert any("ADD COLUMN IF NOT EXISTS embedding_model" in s for s in stmts)
        assert any("idx_ao_embeddings_model" in s for s in stmts)


class TestClose:
    def test_close_releases_connection(self, pgvector_env):
        PgvectorBackend, conn, _ = pgvector_env
        backend = PgvectorBackend(dsn="postgresql://x", dimension=2)
        backend.close()
        assert conn.close.call_count == 1

    def test_close_safe_when_already_closed(self, pgvector_env):
        PgvectorBackend, conn, _ = pgvector_env
        backend = PgvectorBackend(dsn="postgresql://x", dimension=2)
        conn.closed = True
        # Should not raise and should not re-close.
        backend.close()
        assert conn.close.call_count == 0
