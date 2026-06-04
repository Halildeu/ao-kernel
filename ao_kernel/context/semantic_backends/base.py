"""Semantic backend protocol + shared types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


class SemanticBackendError(Exception):
    """Raised when a semantic backend cannot fulfill the requested
    operation (e.g. extras missing, connection refused, schema
    mismatch). Caller may catch + fall back to a different backend."""


@dataclass(frozen=True)
class SemanticSearchResult:
    """One hit returned by :meth:`SemanticBackend.search`."""

    decision_id: str
    score: float
    payload: dict[str, Any]


@runtime_checkable
class SemanticBackend(Protocol):
    """Pluggable backend for storing + querying decision embeddings.

    Implementations MUST be safe to instantiate even if their optional
    extras are missing — they should raise :class:`SemanticBackendError`
    on the first method call that actually requires the extras, not at
    construction time. This keeps import-time discovery cheap.
    """

    backend_name: str
    """Stable identifier (e.g. ``"in_memory"``, ``"pgvector"``)."""

    def is_available(self) -> bool:
        """Return ``True`` if the backend can serve requests right now.

        In-memory backends always return ``True``. Database-backed
        backends should return ``False`` if their extras are missing or
        the connection is unreachable; the caller can then fall back.
        """
        ...

    def upsert(
        self,
        decision_id: str,
        embedding: list[float],
        payload: dict[str, Any],
    ) -> None:
        """Insert or replace an embedding + its payload."""
        ...

    def search(
        self,
        query_embedding: list[float],
        *,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[SemanticSearchResult]:
        """Return the top ``limit`` results above ``min_score``."""
        ...

    def delete(self, decision_id: str) -> None:
        """Remove a decision's embedding + payload, if present."""
        ...

    def count(self) -> int:
        """Total number of stored embeddings."""
        ...
