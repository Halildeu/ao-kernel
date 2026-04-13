"""Semantic retrieval — embedding-based similarity for context decisions.

Provider embedding + local cache + pure-Python cosine similarity.
No numpy/pgvector dependency — pure stdlib math for small corpus.

Embedding strategy:
    - Embed on write (decision/fact creation) → cache alongside record
    - Embed query once on retrieval → cosine against cached embeddings
    - Fallback to deterministic scoring if no embeddings available

Usage:
    from ao_kernel.context.semantic_retrieval import embed_decision, semantic_search
"""

from __future__ import annotations

import hashlib
import math
from typing import Any


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Pure-Python cosine similarity. No numpy needed for small vectors."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def embed_text(
    text: str,
    *,
    provider_id: str = "openai",
    model: str = "text-embedding-3-small",
    base_url: str = "https://api.openai.com/v1",
    api_key: str = "",
) -> list[float] | None:
    """Get embedding vector for text using LLM provider API.

    Returns embedding vector or None if unavailable/error.
    Uses existing ao_kernel LLM infrastructure.
    """
    if not api_key or not text.strip():
        return None

    try:
        from ao_kernel._internal.prj_kernel_api.llm_request_builder import build_embeddings_request
        from ao_kernel._internal.prj_kernel_api.llm_transport import execute_http_request
        from ao_kernel._internal.prj_kernel_api.llm_response_normalizer import extract_embeddings

        req = build_embeddings_request(
            provider_id=provider_id,
            model=model,
            input_text=text,
            base_url=base_url,
            api_key=api_key,
        )
        result = execute_http_request(
            url=req["url"],
            headers=req["headers"],
            body_bytes=req["body_bytes"],
            timeout_seconds=10.0,
            max_response_bytes=1_000_000,
        )
        if result["status"] != "OK":
            return None
        return extract_embeddings(result["resp_bytes"], provider_id=provider_id)
    except Exception:
        return None


def embed_decision(
    decision: dict[str, Any],
    *,
    provider_id: str = "openai",
    model: str = "text-embedding-3-small",
    base_url: str = "https://api.openai.com/v1",
    api_key: str = "",
) -> dict[str, Any]:
    """Embed a decision and attach embedding metadata.

    Modifies decision in-place, adding:
        _embedding: list[float]
        _embedding_model: str
        _embedding_hash: str (hash of input text)

    Returns the decision (with embedding attached).
    """
    text = f"{decision.get('key', '')}: {decision.get('value', '')}"
    text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]

    # Skip if already embedded with same hash
    if decision.get("_embedding_hash") == text_hash and decision.get("_embedding"):
        return decision

    embedding = embed_text(
        text, provider_id=provider_id, model=model,
        base_url=base_url, api_key=api_key,
    )

    if embedding:
        decision["_embedding"] = embedding
        decision["_embedding_model"] = model
        decision["_embedding_hash"] = text_hash

    return decision


def semantic_search(
    query: str,
    decisions: list[dict[str, Any]] | None = None,
    *,
    top_k: int = 10,
    min_similarity: float = 0.3,
    query_embedding: list[float] | None = None,
    provider_id: str = "openai",
    model: str = "text-embedding-3-small",
    base_url: str = "https://api.openai.com/v1",
    api_key: str = "",
    vector_store: Any | None = None,
) -> list[dict[str, Any]]:
    """Search decisions by semantic similarity.

    If vector_store provided, delegates to backend (scales to large corpora).
    Otherwise falls back to in-memory search over decisions list.

    If query_embedding not provided, generates it via API.
    Only considers decisions that have _embedding attached.
    Falls back to empty list if no embeddings available.

    Returns decisions sorted by similarity (highest first), with
    _similarity score attached.
    """
    # Get query embedding
    if query_embedding is None:
        query_embedding = embed_text(
            query, provider_id=provider_id, model=model,
            base_url=base_url, api_key=api_key,
        )

    if not query_embedding:
        return []  # No embedding = fallback to deterministic

    # Use vector store backend if provided
    if vector_store is not None:
        raw_results = vector_store.search(
            query_embedding, top_k=top_k, min_similarity=min_similarity,
        )
        return [
            {"key": r["key"], "_similarity": round(r["similarity"], 4), **r.get("metadata", {})}
            for r in raw_results
        ]

    # In-memory search (default)
    if not decisions:
        return []

    results = []
    for d in decisions:
        d_emb = d.get("_embedding")
        if not d_emb or not isinstance(d_emb, list):
            continue
        sim = cosine_similarity(query_embedding, d_emb)
        if sim >= min_similarity:
            result = dict(d)
            result["_similarity"] = round(sim, 4)
            results.append(result)

    results.sort(key=lambda x: x.get("_similarity", 0), reverse=True)
    return results[:top_k]


__all__ = [
    "cosine_similarity",
    "embed_text",
    "embed_decision",
    "semantic_search",
]
