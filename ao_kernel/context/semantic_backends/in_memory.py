"""In-memory semantic backend (default; no extras required).

Wraps the existing pure-Python cosine similarity path in
``ao_kernel.context.semantic_retrieval``. No new dependency; safe for
every install.
"""

from __future__ import annotations

from typing import Any

from ao_kernel.context.semantic_retrieval import cosine_similarity

from .base import SemanticBackend, SemanticSearchResult


class InMemoryBackend:
    """Process-local dict of decision_id -> (embedding, payload).

    Single-process scope only. Resets on process restart. For
    cross-process / cross-host sharing, use the pgvector backend.
    """

    backend_name: str = "in_memory"

    def __init__(self) -> None:
        self._store: dict[str, tuple[list[float], dict[str, Any]]] = {}

    def is_available(self) -> bool:
        return True

    def upsert(
        self,
        decision_id: str,
        embedding: list[float],
        payload: dict[str, Any],
    ) -> None:
        if not decision_id:
            raise ValueError("decision_id must be non-empty")
        if not embedding:
            raise ValueError("embedding must be non-empty")
        self._store[decision_id] = (list(embedding), dict(payload))

    def search(
        self,
        query_embedding: list[float],
        *,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[SemanticSearchResult]:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if not query_embedding:
            return []
        scored: list[SemanticSearchResult] = []
        for did, (emb, payload) in self._store.items():
            score = cosine_similarity(query_embedding, emb)
            if score >= min_score:
                scored.append(SemanticSearchResult(did, score, dict(payload)))
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:limit]

    def delete(self, decision_id: str) -> None:
        self._store.pop(decision_id, None)

    def count(self) -> int:
        return len(self._store)


# Runtime Protocol conformance (test exercises this via isinstance).
assert isinstance(InMemoryBackend(), SemanticBackend)  # noqa: S101
