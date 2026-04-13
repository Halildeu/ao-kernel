"""pgvector backend for vector store — PostgreSQL + pgvector extension.

Requires: pip install ao-kernel[pgvector]
    - pgvector
    - psycopg2-binary

Usage:
    from ao_kernel.context.vector_store_pgvector import PgvectorBackend
    store = PgvectorBackend(dsn="postgresql://user:pass@localhost/ao_kernel")
    store.store("key1", [0.1, 0.2, ...], metadata={"source": "agent"})
    results = store.search([0.1, 0.2, ...], top_k=5)
"""

from __future__ import annotations

import json
from typing import Any

from ao_kernel.context.vector_store import VectorStoreBackend


class PgvectorBackend(VectorStoreBackend):
    """PostgreSQL + pgvector vector store backend.

    Uses cosine distance operator (<=>). Creates table and index on first use.
    """

    def __init__(
        self,
        *,
        dsn: str = "",
        table_name: str = "ao_embeddings",
        dimension: int = 1536,
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
        self._dim = dimension
        self._conn = psycopg2.connect(dsn)
        register_vector(self._conn)
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Create embeddings table and index if not exists."""
        with self._conn.cursor() as cur:
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {self._table} (
                    key TEXT PRIMARY KEY,
                    embedding vector({self._dim}),
                    metadata JSONB DEFAULT '{{}}'::jsonb,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self._table}_cosine
                ON {self._table} USING ivfflat (embedding vector_cosine_ops)
            """)
            self._conn.commit()

    def store(self, key: str, embedding: list[float], *, metadata: dict[str, Any] | None = None) -> None:
        meta_json = json.dumps(metadata or {})
        with self._conn.cursor() as cur:
            cur.execute(
                f"""INSERT INTO {self._table} (key, embedding, metadata)
                    VALUES (%s, %s, %s::jsonb)
                    ON CONFLICT (key) DO UPDATE
                    SET embedding = EXCLUDED.embedding, metadata = EXCLUDED.metadata""",
                (key, embedding, meta_json),
            )
            self._conn.commit()

    def search(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 10,
        min_similarity: float = 0.3,
    ) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute(
                f"""SELECT key, 1 - (embedding <=> %s::vector) AS similarity, metadata
                    FROM {self._table}
                    WHERE 1 - (embedding <=> %s::vector) >= %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s""",
                (query_embedding, query_embedding, min_similarity, query_embedding, top_k),
            )
            return [
                {"key": row[0], "similarity": round(float(row[1]), 4), "metadata": row[2]}
                for row in cur.fetchall()
            ]

    def delete(self, key: str) -> bool:
        with self._conn.cursor() as cur:
            cur.execute(f"DELETE FROM {self._table} WHERE key = %s", (key,))
            deleted = cur.rowcount > 0
            self._conn.commit()
            return deleted

    def count(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {self._table}")
            return cur.fetchone()[0]

    def close(self) -> None:
        """Close database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()
