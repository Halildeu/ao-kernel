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
        decisions = [{"key": f"k{i}", "value": f"v{i}", "_embedding": [float(i) / 10, 1.0]} for i in range(20)]
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


class TestSemanticSearchInMemoryEdges:
    """HYG-PUBLIC-CONTEXT-GAPS-01: in-memory semantic_search edges the audit
    (PR #753 §3) flagged as actionable_offline. No live provider call — the
    provider HTTP path (embed_text) is external and out of scope here.
    """

    def test_search_no_decisions_returns_empty(self):
        # No in-memory decisions + a provided query_embedding → [] (the
        # `if not decisions: return []` branch, semantic_retrieval L191-192).
        results = semantic_search("test", decisions=[], query_embedding=[1.0, 0.0])
        assert results == []

    def test_search_none_decisions_returns_empty(self):
        # decisions=None (default) + query_embedding, no vector_store → [].
        results = semantic_search("test", query_embedding=[1.0, 0.0])
        assert results == []


class TestEmbedDecisionConfigPrecedence:
    """HYG-PUBLIC-CONTEXT-GAPS-01: embed_decision embedding_config precedence
    (semantic_retrieval L98-104). When an embedding_config is supplied, its
    provider/model/base_url/api_key take precedence over positional args. We
    monkeypatch embed_text to capture the resolved provider/model without any
    network call.
    """

    def test_embedding_config_overrides_positional(self, monkeypatch):
        captured = {}

        def fake_embed_text(text, *, provider_id, model, base_url, api_key):
            captured["provider_id"] = provider_id
            captured["model"] = model
            captured["base_url"] = base_url
            captured["api_key"] = api_key
            return [0.1, 0.2, 0.3]

        monkeypatch.setattr("ao_kernel.context.semantic_retrieval.embed_text", fake_embed_text)

        class _Cfg:
            provider = "google"
            model = "text-embedding-004"
            base_url = "https://generativelanguage.googleapis.com"

            def resolve_api_key(self):
                return "resolved-key"

        d = {"key": "k", "value": "v"}
        result = embed_decision(
            d,
            provider_id="openai",
            model="text-embedding-3-small",
            api_key="positional",
            embedding_config=_Cfg(),
        )
        # embedding_config fields win over positional args (provider, model,
        # base_url, and resolved api_key all take precedence).
        assert captured["provider_id"] == "google"
        assert captured["model"] == "text-embedding-004"
        assert captured["base_url"] == "https://generativelanguage.googleapis.com"
        assert captured["api_key"] == "resolved-key"
        assert result["_embedding"] == [0.1, 0.2, 0.3]

    def test_semantic_search_embedding_config_precedence(self, monkeypatch):
        # semantic_search embedding_config precedence (semantic_retrieval
        # L162-168): with no query_embedding supplied, semantic_search calls
        # embed_text using the embedding_config-resolved provider/model/
        # base_url/api_key, not the positional defaults. No network.
        captured = {}

        def fake_embed_text(text, *, provider_id, model, base_url, api_key):
            captured["provider_id"] = provider_id
            captured["model"] = model
            captured["base_url"] = base_url
            captured["api_key"] = api_key
            return [1.0, 0.0]

        monkeypatch.setattr("ao_kernel.context.semantic_retrieval.embed_text", fake_embed_text)

        class _Cfg:
            provider = "google"
            model = "text-embedding-004"
            base_url = "https://generativelanguage.googleapis.com"

            def resolve_api_key(self):
                return "resolved-key"

        decisions = [{"key": "a", "value": "x", "_embedding": [1.0, 0.0]}]
        results = semantic_search(
            "query text",
            decisions,
            query_embedding=None,
            embedding_config=_Cfg(),
            min_similarity=0.1,
        )
        # embed_text was driven by the config-resolved fields
        assert captured["provider_id"] == "google"
        assert captured["model"] == "text-embedding-004"
        assert captured["base_url"] == "https://generativelanguage.googleapis.com"
        assert captured["api_key"] == "resolved-key"
        # and the generated query embedding still yields the in-memory match
        assert results[0]["key"] == "a"

    def test_cache_skip_when_hash_and_model_match(self, monkeypatch):
        # Already-embedded decision with matching text hash + model → skip
        # re-embedding (L109-115). embed_text must NOT be called.
        import hashlib

        called = {"n": 0}

        def fake_embed_text(*a, **k):
            called["n"] += 1
            return [9.9]

        monkeypatch.setattr("ao_kernel.context.semantic_retrieval.embed_text", fake_embed_text)
        text = "k: v"
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        d = {
            "key": "k",
            "value": "v",
            "_embedding": [1.0, 2.0],
            "_embedding_hash": text_hash,
            "_embedding_model": "text-embedding-3-small",
        }
        result = embed_decision(d, api_key="present", model="text-embedding-3-small")
        assert called["n"] == 0  # cache hit → no re-embed
        assert result["_embedding"] == [1.0, 2.0]
