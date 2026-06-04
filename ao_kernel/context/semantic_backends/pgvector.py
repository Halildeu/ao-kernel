"""pgvector semantic backend (opt-in; requires ``[pgvector]`` extra).

Lazy imports ``psycopg2`` + ``pgvector`` so the import-time cost stays
zero for installations that do not opt in. If the extras are missing,
:meth:`PgVectorBackend.is_available` returns ``False`` and every other
method raises :class:`SemanticBackendError` with an actionable message.

Schema:

.. code-block:: sql

    CREATE EXTENSION IF NOT EXISTS vector;

    CREATE TABLE IF NOT EXISTS ao_semantic_decisions (
        decision_id TEXT PRIMARY KEY,
        embedding   VECTOR(1536) NOT NULL,
        payload     JSONB NOT NULL,
        updated_at  TIMESTAMPTZ DEFAULT now()
    );

    CREATE INDEX IF NOT EXISTS ao_semantic_decisions_embedding_ivfflat
      ON ao_semantic_decisions USING ivfflat (embedding vector_cosine_ops)
      WITH (lists = 100);

Operator boundary:

- Operator MUST provision the database, create the extension, and run
  the DDL above. This backend does NOT execute DDL at runtime (no
  schema migrations from the governance plane).
- Operator MUST supply the connection string + credentials via the
  environment (NEVER as constructor parameters).
- Default embedding dimension is 1536 (OpenAI text-embedding-3-small).
  Operator may override via ``embedding_dim`` constructor arg.
"""

from __future__ import annotations

import os
import re
from typing import Any

from .base import SemanticBackend, SemanticBackendError, SemanticSearchResult

_TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?$")


class PgVectorBackend:
    """pgvector-backed semantic store. Lazy imports its extras."""

    backend_name: str = "pgvector"

    _MISSING_EXTRAS_MSG = (
        "pgvector backend requires the [pgvector] extra. Install with: pip install 'ao-kernel[pgvector]'"
    )

    def __init__(
        self,
        *,
        dsn_env_var: str = "AO_KERNEL_PGVECTOR_DSN",
        table: str = "ao_semantic_decisions",
        embedding_dim: int = 1536,
    ) -> None:
        if embedding_dim < 1:
            raise ValueError("embedding_dim must be >= 1")
        if not _TABLE_NAME_RE.fullmatch(table):
            raise ValueError("table must be an unquoted SQL identifier or schema-qualified identifier")
        self._dsn_env_var = dsn_env_var
        self._table = table
        self._embedding_dim = embedding_dim
        # Connection is opened lazily so construction never fails on
        # missing extras / missing env / unreachable host.
        self._conn: Any = None
        self._extras_imported = False
        # Lazy import targets (assigned by _import_extras on first call;
        # declared here so mypy can resolve attribute types).
        self._psycopg2_module: Any = None
        self._register_vector: Any = None

    # ---- extras + connection plumbing (lazy) ----------------------------

    def _import_extras(self) -> Any:
        if self._extras_imported:
            return self._psycopg2_module
        try:
            import psycopg2  # noqa: PLC0415
            from pgvector.psycopg2 import register_vector  # noqa: PLC0415
        except ImportError as exc:
            raise SemanticBackendError(self._MISSING_EXTRAS_MSG) from exc
        self._psycopg2_module = psycopg2
        self._register_vector = register_vector
        self._extras_imported = True
        return psycopg2

    def _connect(self) -> Any:
        if self._conn is not None:
            return self._conn
        psycopg2 = self._import_extras()
        dsn = os.environ.get(self._dsn_env_var)
        if not dsn:
            raise SemanticBackendError(
                f"pgvector backend requires {self._dsn_env_var} environment "
                "variable to be set with a libpq DSN; operator-bound."
            )
        try:
            conn = psycopg2.connect(dsn)
        except Exception as exc:  # noqa: BLE001
            raise SemanticBackendError(f"pgvector backend could not connect via {self._dsn_env_var}: {exc}") from exc
        self._register_vector(conn)
        self._conn = conn
        return conn

    # ---- SemanticBackend protocol ---------------------------------------

    def is_available(self) -> bool:
        try:
            self._import_extras()
        except SemanticBackendError:
            return False
        return bool(os.environ.get(self._dsn_env_var))

    def upsert(
        self,
        decision_id: str,
        embedding: list[float],
        payload: dict[str, Any],
    ) -> None:
        if not decision_id:
            raise ValueError("decision_id must be non-empty")
        if len(embedding) != self._embedding_dim:
            raise ValueError(f"embedding length {len(embedding)} != expected {self._embedding_dim}")
        import json

        conn = self._connect()
        sql = (
            f"INSERT INTO {self._table} (decision_id, embedding, payload, updated_at) "
            "VALUES (%s, %s, %s, now()) "
            "ON CONFLICT (decision_id) DO UPDATE SET "
            "embedding = EXCLUDED.embedding, payload = EXCLUDED.payload, "
            "updated_at = now()"
        )
        with conn.cursor() as cur:
            cur.execute(sql, (decision_id, embedding, json.dumps(payload)))
        conn.commit()

    def search(
        self,
        query_embedding: list[float],
        *,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[SemanticSearchResult]:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if len(query_embedding) != self._embedding_dim:
            raise ValueError(f"query_embedding length {len(query_embedding)} != expected {self._embedding_dim}")
        conn = self._connect()
        # pgvector cosine distance: 1 - cosine_similarity. Score = 1 - distance.
        sql = (
            f"SELECT decision_id, payload, 1 - (embedding <=> %s) AS score "
            f"FROM {self._table} "
            f"WHERE 1 - (embedding <=> %s) >= %s "
            f"ORDER BY embedding <=> %s "
            f"LIMIT %s"
        )
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    query_embedding,
                    query_embedding,
                    float(min_score),
                    query_embedding,
                    int(limit),
                ),
            )
            rows = cur.fetchall()
        return [SemanticSearchResult(decision_id=row[0], score=float(row[2]), payload=row[1]) for row in rows]

    def delete(self, decision_id: str) -> None:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM {self._table} WHERE decision_id = %s",
                (decision_id,),
            )
        conn.commit()

    def count(self) -> int:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {self._table}")
            row = cur.fetchone()
        return int(row[0]) if row else 0


# Runtime Protocol conformance (test exercises this via isinstance).
assert isinstance(PgVectorBackend(), SemanticBackend)  # noqa: S101
