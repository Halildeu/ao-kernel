"""pgvector backend for vector store — PostgreSQL + pgvector extension.

Requires: pip install ao-kernel[pgvector]
    - pgvector
    - psycopg2-binary

Usage:
    from ao_kernel.context.vector_store_pgvector import PgvectorBackend
    store = PgvectorBackend(dsn="postgresql://user:pass@localhost/ao_kernel")
    store.store("key1", [0.1, 0.2, ...], metadata={"source": "agent"})
    results = store.search([0.1, 0.2, ...], top_k=5)

Embedding model namespace (B1d, CNS-007):
    Each row carries the embedding model identifier (e.g. ``text-embedding-3-small``).
    Mismatched models are refused at store() time and ignored at search() time
    to prevent mingling incompatible embedding spaces in a single table.
"""

from __future__ import annotations

import json
from typing import Any

from ao_kernel.context.vector_store import VectorStoreBackend
from ao_kernel.errors import VectorStoreConfigError


class PgvectorBackend(VectorStoreBackend):
    """PostgreSQL + pgvector vector store backend.

    Uses cosine distance operator (<=>). Creates table and index on first use.

    Model namespace enforcement:
        - ``store()`` rejects vectors whose dimension ≠ configured dimension
          or whose ``metadata["embedding_model"]`` differs from the model
          this backend was bound to.
        - ``search()`` filters by ``embedding_model`` when the backend was
          bound to one, so queries cannot accidentally match vectors from
          a different embedding space.
    """

    def __init__(
        self,
        *,
        dsn: str = "",
        table_name: str = "ao_embeddings",
        dimension: int = 1536,
        embedding_model: str | None = None,
    ) -> None:
        try:
            import psycopg2
            from pgvector.psycopg2 import register_vector
        except ImportError:
            raise ImportError(
                "pgvector backend requires psycopg2 and pgvector. "
                "Install with: pip install ao-kernel[pgvector]"
            ) from None

        self._dsn = dsn
        self._table = table_name
        self._dim = int(dimension)
        self._embedding_model = embedding_model or ""
        self._conn = psycopg2.connect(dsn)
        register_vector(self._conn)
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Create embeddings table and index if not exists.

        Schema (B1d) carries ``embedding_model`` so that a single table can
        host vectors from multiple models without semantic collisions. A
        btree index on (embedding_model) accelerates filtered queries.
        """
        with self._conn.cursor() as cur:
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {self._table} (
                    key TEXT PRIMARY KEY,
                    embedding vector({self._dim}),
                    embedding_model TEXT NOT NULL DEFAULT '',
                    metadata JSONB DEFAULT '{{}}'::jsonb,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            # Best-effort column add for upgrades from a pre-B1d schema.
            cur.execute(f"""
                ALTER TABLE {self._table}
                ADD COLUMN IF NOT EXISTS embedding_model TEXT NOT NULL DEFAULT ''
            """)
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self._table}_cosine
                ON {self._table} USING ivfflat (embedding vector_cosine_ops)
            """)
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self._table}_model
                ON {self._table} (embedding_model)
            """)
            self._conn.commit()

    def _validate_vector(self, embedding: list[float], metadata_model: str) -> None:
        """Reject mismatched dimension or embedding model (B1d)."""
        if len(embedding) != self._dim:
            raise VectorStoreConfigError(
                f"Embedding dimension mismatch: backend bound to {self._dim}, "
                f"got vector of length {len(embedding)}. Reconfigure via "
                f"AO_KERNEL_EMBEDDING_DIMENSION or use a separate table."
            )
        if self._embedding_model and metadata_model and metadata_model != self._embedding_model:
            raise VectorStoreConfigError(
                f"Embedding model mismatch: backend bound to {self._embedding_model!r}, "
                f"got vector tagged {metadata_model!r}. Use a dedicated backend "
                f"per model, or drop the embedding_model tag to store anonymously."
            )

    def store(self, key: str, embedding: list[float], *, metadata: dict[str, Any] | None = None) -> None:
        meta = dict(metadata or {})
        # Default to backend-bound model if caller did not tag the vector.
        model_tag = str(meta.get("embedding_model") or self._embedding_model or "")
        if "embedding_model" not in meta and model_tag:
            meta["embedding_model"] = model_tag
        self._validate_vector(embedding, model_tag)

        meta_json = json.dumps(meta)
        with self._conn.cursor() as cur:
            cur.execute(
                f"""INSERT INTO {self._table} (key, embedding, embedding_model, metadata)
                    VALUES (%s, %s, %s, %s::jsonb)
                    ON CONFLICT (key) DO UPDATE
                    SET embedding = EXCLUDED.embedding,
                        embedding_model = EXCLUDED.embedding_model,
                        metadata = EXCLUDED.metadata""",
                (key, embedding, model_tag, meta_json),
            )
            self._conn.commit()

    def search(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 10,
        min_similarity: float = 0.3,
    ) -> list[dict[str, Any]]:
        if len(query_embedding) != self._dim:
            # Dimension mismatch on read == no valid matches in this space.
            return []

        # When the backend is bound to a model, filter to that namespace so
        # queries cannot cross the embedding-space boundary.
        if self._embedding_model:
            model_filter = "AND embedding_model = %s"
            params: tuple[Any, ...] = (
                query_embedding, query_embedding, min_similarity,
                self._embedding_model, query_embedding, top_k,
            )
        else:
            model_filter = ""
            params = (
                query_embedding, query_embedding, min_similarity,
                query_embedding, top_k,
            )

        sql = f"""
            SELECT key, 1 - (embedding <=> %s::vector) AS similarity, metadata
            FROM {self._table}
            WHERE 1 - (embedding <=> %s::vector) >= %s
              {model_filter}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            return [
                {"key": row[0], "similarity": round(float(row[1]), 4), "metadata": row[2]}
                for row in cur.fetchall()
            ]

    def delete(self, key: str) -> bool:
        with self._conn.cursor() as cur:
            cur.execute(f"DELETE FROM {self._table} WHERE key = %s", (key,))
            deleted: bool = cur.rowcount > 0
            self._conn.commit()
            return deleted

    def count(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {self._table}")
            row = cur.fetchone()
            return int(row[0]) if row else 0

    def close(self) -> None:
        """Close database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()
