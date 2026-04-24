from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ao_kernel._internal.repo_intelligence.artifacts import validate_repo_vector_query_result
from ao_kernel._internal.repo_intelligence.python_ast_indexer import build_python_ast_indexes
from ao_kernel._internal.repo_intelligence.repo_chunker import build_repo_chunks
from ao_kernel._internal.repo_intelligence.repo_vector_indexer import write_repo_vectors
from ao_kernel._internal.repo_intelligence.repo_vector_plan import build_repo_vector_write_plan
from ao_kernel._internal.repo_intelligence.repo_vector_retriever import query_repo_vectors
from ao_kernel._internal.repo_intelligence.scanner import scan_repo
from ao_kernel.context.embedding_config import EmbeddingConfig
from ao_kernel.context.vector_store import InMemoryVectorStore


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "vector-query-project"
    (project / ".ao" / "context").mkdir(parents=True)
    (project / "pkg").mkdir()
    (project / "pkg" / "__init__.py").write_text("from .main import run\n", encoding="utf-8")
    (project / "pkg" / "main.py").write_text(
        "VALUE = 1\n\n"
        "def run():\n"
        "    return VALUE\n",
        encoding="utf-8",
    )
    (project / "pyproject.toml").write_text("[project]\nname = \"vector-query-project\"\n", encoding="utf-8")
    return project


def _embedding_config(api_key: str = "test-key") -> EmbeddingConfig:
    return EmbeddingConfig(
        provider="openai",
        model="text-embedding-3-small",
        base_url="https://api.openai.com/v1",
        api_key=api_key,
    )


def _embed_text(*_args: Any, **_kwargs: Any) -> list[float]:
    return [0.1, 0.2, 0.3]


def _indexed_store(project: Path) -> tuple[InMemoryVectorStore, dict[str, Any]]:
    repo_map = scan_repo(project)
    import_graph, symbol_index = build_python_ast_indexes(project, repo_map)
    repo_chunks = build_repo_chunks(project, repo_map=repo_map, import_graph=import_graph, symbol_index=symbol_index)
    vector_write_plan = build_repo_vector_write_plan(
        repo_chunks=repo_chunks,
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        embedding_dimension=3,
    )
    store = InMemoryVectorStore()
    manifest = write_repo_vectors(
        project_root=project,
        vector_write_plan=vector_write_plan,
        vector_store=store,
        embedding_config=_embedding_config(),
        embed_text_fn=_embed_text,
    )
    return store, manifest


def test_query_repo_vectors_returns_schema_valid_current_chunks(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    store, manifest = _indexed_store(project)

    result = query_repo_vectors(
        project_root=project,
        vector_index_manifest=manifest,
        vector_store=store,
        embedding_config=_embedding_config(),
        query="where is run defined",
        top_k=3,
        candidate_limit=10,
        embed_text_fn=_embed_text,
    )

    validate_repo_vector_query_result(result)
    assert result["artifact_kind"] == "repo_vector_query_result"
    assert result["summary"]["matches"] >= 1
    assert result["summary"]["embedding_calls"] == 1
    assert result["results"][0]["content_status"] == "current"
    assert result["results"][0]["source_path"].startswith("pkg/")
    assert "return VALUE" in "".join(item["snippet"] for item in result["results"])


def test_query_repo_vectors_fails_closed_without_embedding_api_key(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    store, manifest = _indexed_store(project)

    with pytest.raises(ValueError, match="embedding API key is required"):
        query_repo_vectors(
            project_root=project,
            vector_index_manifest=manifest,
            vector_store=store,
            embedding_config=_embedding_config(api_key=""),
            query="run",
            embed_text_fn=_embed_text,
        )


def test_query_repo_vectors_treats_none_api_key_as_missing(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    store, manifest = _indexed_store(project)

    class _NoneKeyConfig:
        provider = "openai"
        model = "text-embedding-3-small"
        base_url = "https://api.openai.com/v1"

        def resolve_api_key(self) -> None:
            return None

    with pytest.raises(ValueError, match="embedding API key is required"):
        query_repo_vectors(
            project_root=project,
            vector_index_manifest=manifest,
            vector_store=store,
            embedding_config=_NoneKeyConfig(),
            query="run",
            embed_text_fn=_embed_text,
        )


def test_query_repo_vectors_fails_closed_on_query_embedding_dimension_mismatch(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    store, manifest = _indexed_store(project)

    with pytest.raises(ValueError, match="query embedding dimension mismatch"):
        query_repo_vectors(
            project_root=project,
            vector_index_manifest=manifest,
            vector_store=store,
            embedding_config=_embedding_config(),
            query="run",
            embed_text_fn=lambda *_args, **_kwargs: [0.1, 0.2],
        )


def test_query_repo_vectors_filters_non_repo_namespace_candidates(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    store, manifest = _indexed_store(project)
    store.store(
        f"repo_chunk::{'a' * 64}::{'b' * 64}::repo-chunk-v1:{'c' * 64}",
        [0.1, 0.2, 0.3],
        metadata={
            "source": "canonical_memory",
            "artifact_kind": "decision",
            "source_path": "pkg/main.py",
        },
    )

    result = query_repo_vectors(
        project_root=project,
        vector_index_manifest=manifest,
        vector_store=store,
        embedding_config=_embedding_config(),
        query="run",
        top_k=10,
        candidate_limit=20,
        embed_text_fn=_embed_text,
    )

    validate_repo_vector_query_result(result)
    assert result["summary"]["filtered_candidates"] >= 1
    assert all(item["key"].startswith("repo_chunk::" + manifest["project"]["root_identity_sha256"]) for item in result["results"])


def test_query_repo_vectors_excludes_stale_source_chunks(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    store, manifest = _indexed_store(project)
    (project / "pkg" / "main.py").write_text("VALUE = 2\n", encoding="utf-8")

    result = query_repo_vectors(
        project_root=project,
        vector_index_manifest=manifest,
        vector_store=store,
        embedding_config=_embedding_config(),
        query="run",
        top_k=10,
        candidate_limit=20,
        embed_text_fn=_embed_text,
    )

    validate_repo_vector_query_result(result)
    assert result["summary"]["stale_candidates"] >= 1
    assert all(item["source_path"] != "pkg/main.py" for item in result["results"])
    assert any(item["code"] in {"repo_vector_query_content_hash_stale", "repo_vector_query_line_range_stale"} for item in result["diagnostics"])


def test_query_repo_vectors_applies_path_filter_and_token_budget(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    store, manifest = _indexed_store(project)

    result = query_repo_vectors(
        project_root=project,
        vector_index_manifest=manifest,
        vector_store=store,
        embedding_config=_embedding_config(),
        query="run",
        top_k=10,
        candidate_limit=20,
        source_path_prefix="pkg/main.py",
        max_tokens=500,
        embed_text_fn=_embed_text,
    )

    validate_repo_vector_query_result(result)
    assert result["summary"]["matches"] >= 1
    assert all(item["source_path"] == "pkg/main.py" for item in result["results"])
    assert result["summary"]["estimated_tokens"] <= 500
