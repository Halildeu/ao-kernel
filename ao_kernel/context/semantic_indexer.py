"""Semantic write-path — embed and store decisions in the vector store.

This module is the sidecar index maintainer: whenever a decision is
upserted into session context or promoted to canonical, we also embed
its (key, value) text and persist the vector in the configured backend.
Session/canonical JSON stays authoritative for decision payload; the
vector store only holds embedding + minimal metadata for retrieval.

Design contract (CNS-007 consensus):
    - Write-path failures NEVER block the caller. A failed embed or
      store turns into a debug log; the main pipeline continues.
    - Disabled backend or empty api_key is a no-op (expected path in
      default configuration).
    - Namespace scoping (session_id / workspace_id) lives in metadata
      so multiple clients can share a single backend without key
      collisions.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _index_key(raw_key: str, namespace: str | None) -> str:
    """Compose a backend-unique key. Namespace is optional (library mode)."""
    if not namespace:
        return raw_key
    return f"{namespace}::{raw_key}"


def index_decision(
    *,
    key: str,
    value: Any,
    source: str = "agent",
    namespace: str | None = None,
    vector_store: Any | None = None,
    embedding_config: Any | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> bool:
    """Embed a decision and store it in the vector backend.

    Args:
        key: Decision key (unique within namespace).
        value: Decision value (any JSON-serializable payload).
        source: Origin marker ("session", "canonical", "tool", "agent", ...).
        namespace: Optional scope prefix (session_id or workspace_id).
        vector_store: VectorStoreBackend instance or None (no-op if None).
        embedding_config: EmbeddingConfig instance or None (default if None).
        extra_metadata: Additional metadata merged into the backend entry.

    Returns:
        True on successful store, False on skip or failure. Callers
        SHOULD NOT gate logic on the return value — read-path fallback
        handles missing embeddings deterministically.
    """
    if vector_store is None:
        return False

    # Lazy import to keep write-path cold when semantic retrieval is off.
    from ao_kernel.context.embedding_config import resolve_embedding_config
    from ao_kernel.context.semantic_retrieval import embed_text

    config = embedding_config if embedding_config is not None else resolve_embedding_config()
    api_key = config.resolve_api_key()
    if not api_key:
        logger.debug(
            "semantic_indexer: no api_key for provider %r; skip index of %r",
            config.provider, key,
        )
        return False

    text = f"{key}: {value}"
    try:
        vector = embed_text(
            text,
            provider_id=config.provider,
            model=config.model,
            base_url=config.base_url,
            api_key=api_key,
        )
    except Exception as exc:  # noqa: BLE001 — write-path best-effort
        logger.debug("semantic_indexer: embed_text raised for %r: %s", key, exc)
        return False

    if not vector:
        logger.debug("semantic_indexer: embed_text returned empty for %r", key)
        return False

    metadata: dict[str, Any] = {
        "source": source,
        "embedding_model": config.model,
        "embedding_provider": config.provider,
    }
    if namespace:
        metadata["namespace"] = namespace
    if extra_metadata:
        metadata.update(extra_metadata)

    try:
        vector_store.store(
            _index_key(key, namespace),
            vector,
            metadata=metadata,
        )
    except Exception as exc:  # noqa: BLE001 — write-path best-effort
        logger.debug("semantic_indexer: vector_store.store raised for %r: %s", key, exc)
        return False

    return True


__all__ = ["index_decision"]
