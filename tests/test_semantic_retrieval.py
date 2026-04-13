"""Tests for semantic retrieval — cosine similarity + embedding integration."""

from __future__ import annotations

from ao_kernel.context.semantic_retrieval import cosine_similarity, embed_decision, semantic_search


class TestCosineSimilarity:
    def test_identical_vectors(self):
        assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0

    def test_orthogonal_vectors(self):
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0

    def test_opposite_vectors(self):
        assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == -1.0

    def test_similar_vectors(self):
        sim = cosine_similarity([1.0, 1.0], [1.0, 0.9])
        assert sim > 0.99

    def test_empty_vectors(self):
        assert cosine_similarity([], []) == 0.0

    def test_different_length_returns_zero(self):
        assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0

    def test_zero_vector_returns_zero(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


class TestSemanticSearch:
    def test_search_with_precomputed_embeddings(self):
        decisions = [
            {"key": "runtime.python", "value": "3.11", "_embedding": [1.0, 0.0, 0.0]},
            {"key": "deploy.target", "value": "staging", "_embedding": [0.0, 1.0, 0.0]},
            {"key": "runtime.node", "value": "20", "_embedding": [0.9, 0.1, 0.0]},
        ]
        results = semantic_search(
            "python version",
            decisions,
            query_embedding=[1.0, 0.0, 0.0],
            min_similarity=0.1,
        )
        assert len(results) >= 1
        assert results[0]["key"] == "runtime.python"
        assert results[0]["_similarity"] == 1.0

    def test_search_filters_below_threshold(self):
        decisions = [
            {"key": "a", "value": "x", "_embedding": [1.0, 0.0]},
            {"key": "b", "value": "y", "_embedding": [0.0, 1.0]},
        ]
        results = semantic_search(
            "test",
            decisions,
            query_embedding=[1.0, 0.0],
            min_similarity=0.5,
        )
        assert len(results) == 1
        assert results[0]["key"] == "a"

    def test_search_without_embeddings_returns_empty(self):
        decisions = [
            {"key": "a", "value": "x"},  # no _embedding
        ]
        results = semantic_search(
            "test",
            decisions,
            query_embedding=[1.0, 0.0],
        )
        assert results == []

    def test_search_top_k_limit(self):
        decisions = [
            {"key": f"k{i}", "value": f"v{i}", "_embedding": [float(i) / 10, 1.0]}
            for i in range(20)
        ]
        results = semantic_search(
            "test",
            decisions,
            query_embedding=[1.0, 1.0],
            top_k=5,
            min_similarity=0.0,
        )
        assert len(results) <= 5

    def test_search_no_query_embedding_returns_empty(self):
        decisions = [{"key": "a", "_embedding": [1.0]}]
        results = semantic_search("test", decisions, api_key="")
        assert results == []


class TestEmbedDecision:
    def test_embed_without_api_key_no_crash(self):
        d = {"key": "test", "value": "hello"}
        result = embed_decision(d, api_key="")
        assert "_embedding" not in result  # No API key = no embedding

    def test_embed_preserves_existing(self):
        d = {
            "key": "test",
            "value": "hello",
            "_embedding": [1.0, 2.0],
            "_embedding_hash": "abc",
        }
        # Different hash → would re-embed if API available
        result = embed_decision(d, api_key="")
        # No API key → keeps existing
        assert result.get("_embedding") == [1.0, 2.0]
