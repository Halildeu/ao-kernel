"""Vector store abstraction — pluggable backends for embedding storage and search.

Provides:
    VectorStoreBackend — Abstract interface for vector storage
    InMemoryVectorStore — Pure-Python in-memory implementation (default)
"""

from __future__ import annotations

import abc
from typing import Any

from ao_kernel.context.semantic_retrieval import cosine_similarity


class VectorStoreBackend(abc.ABC):
    """Abstract interface for vector storage backends."""

    @abc.abstractmethod
    def store(self, key: str, embedding: list[float], *, metadata: dict[str, Any] | None = None) -> None:
        """Store embedding with optional metadata."""
        ...

    @abc.abstractmethod
    def search(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 10,
        min_similarity: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Search by embedding similarity.

        Returns list of {key, similarity, metadata}.
        """
        ...

    @abc.abstractmethod
    def delete(self, key: str) -> bool:
        """Delete embedding by key. Returns True if existed."""
        ...

    @abc.abstractmethod
    def count(self) -> int:
        """Return number of stored embeddings."""
        ...


class InMemoryVectorStore(VectorStoreBackend):
    """Pure-Python in-memory vector store. Suitable for small corpora."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def store(self, key: str, embedding: list[float], *, metadata: dict[str, Any] | None = None) -> None:
        self._store[key] = {
            "embedding": embedding,
            "metadata": metadata or {},
        }

    def search(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 10,
        min_similarity: float = 0.3,
    ) -> list[dict[str, Any]]:
        results = []
        for key, entry in self._store.items():
            sim = cosine_similarity(query_embedding, entry["embedding"])
            if sim >= min_similarity:
                results.append({
                    "key": key,
                    "similarity": round(sim, 4),
                    "metadata": entry["metadata"],
                })
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    def count(self) -> int:
        return len(self._store)
