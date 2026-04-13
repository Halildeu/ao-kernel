"""Tests for vector store abstraction and in-memory backend."""

from __future__ import annotations

from unittest.mock import MagicMock

from ao_kernel.context.vector_store import InMemoryVectorStore, VectorStoreBackend


class TestInMemoryVectorStore:
    def test_store_and_search_roundtrip(self):
        """Store embeddings and search returns similar results."""
        store = InMemoryVectorStore()
        store.store("python", [1.0, 0.0, 0.0], metadata={"lang": "python"})
        store.store("java", [0.0, 1.0, 0.0], metadata={"lang": "java"})
        store.store("typescript", [0.9, 0.1, 0.0], metadata={"lang": "typescript"})

        results = store.search([1.0, 0.0, 0.0], top_k=2, min_similarity=0.5)
        assert len(results) == 2
        assert results[0]["key"] == "python"
        assert results[0]["similarity"] == 1.0
        assert results[0]["metadata"]["lang"] == "python"
        # typescript should be second (0.9 similarity)
        assert results[1]["key"] == "typescript"

    def test_delete_removes_entry(self):
        """Delete removes embedding and returns True; missing returns False."""
        store = InMemoryVectorStore()
        store.store("key1", [1.0, 0.0])
        assert store.count() == 1
        assert store.delete("key1") is True
        assert store.count() == 0
        assert store.delete("key1") is False

    def test_count_reflects_state(self):
        """Count returns current number of stored embeddings."""
        store = InMemoryVectorStore()
        assert store.count() == 0
        store.store("a", [1.0])
        store.store("b", [0.0])
        assert store.count() == 2

    def test_search_min_similarity_filters(self):
        """Results below min_similarity are excluded."""
        store = InMemoryVectorStore()
        store.store("similar", [1.0, 0.0])
        store.store("different", [0.0, 1.0])

        results = store.search([1.0, 0.0], min_similarity=0.9)
        assert len(results) == 1
        assert results[0]["key"] == "similar"


class TestSemanticSearchWithBackend:
    def test_semantic_search_delegates_to_vector_store(self):
        """When vector_store provided, semantic_search uses it instead of in-memory."""
        from ao_kernel.context.semantic_retrieval import semantic_search

        mock_store = MagicMock(spec=VectorStoreBackend)
        mock_store.search.return_value = [
            {"key": "result1", "similarity": 0.95, "metadata": {"source": "test"}},
        ]

        results = semantic_search(
            "test query",
            query_embedding=[1.0, 0.0],
            vector_store=mock_store,
        )
        mock_store.search.assert_called_once()
        assert len(results) == 1
        assert results[0]["key"] == "result1"
        assert results[0]["_similarity"] == 0.95

    def test_semantic_search_without_backend_unchanged(self):
        """Without vector_store, semantic_search uses in-memory as before."""
        from ao_kernel.context.semantic_retrieval import semantic_search

        decisions = [
            {"key": "lang", "value": "python", "_embedding": [1.0, 0.0, 0.0]},
            {"key": "db", "value": "postgres", "_embedding": [0.0, 1.0, 0.0]},
        ]

        results = semantic_search(
            "test",
            decisions,
            query_embedding=[1.0, 0.0, 0.0],
            min_similarity=0.5,
        )
        assert len(results) == 1
        assert results[0]["key"] == "lang"
