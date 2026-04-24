from __future__ import annotations

from pathlib import Path
from typing import Any

from ao_kernel._internal.repo_intelligence.context_pack_builder import (
    build_agent_context_pack,
    build_repo_query_context_pack,
)
from ao_kernel._internal.repo_intelligence.python_ast_indexer import build_python_ast_indexes
from ao_kernel._internal.repo_intelligence.repo_chunker import build_repo_chunks
from ao_kernel._internal.repo_intelligence.scanner import scan_repo


def _make_context_pack_repo(tmp_path: Path) -> Path:
    project = tmp_path / "context-pack-project"
    (project / ".ao").mkdir(parents=True)
    (project / "pkg").mkdir()
    (project / "pkg" / "__init__.py").write_text("from .main import run\n", encoding="utf-8")
    (project / "pkg" / "main.py").write_text(
        "\n".join(
            [
                "import os",
                "from .worker import Worker",
                "VALUE = 1",
                "class App:",
                "    pass",
                "def run():",
                "    return Worker()",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (project / "pkg" / "worker.py").write_text("class Worker:\n    pass\n", encoding="utf-8")
    (project / "README.md").write_text("# Context Pack\n", encoding="utf-8")
    (project / "pyproject.toml").write_text(
        "[project]\nname = \"context-pack-project\"\n[project.scripts]\ncontext-pack = \"pkg.main:run\"\n",
        encoding="utf-8",
    )
    return project


def _stable_artifacts(project: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    repo_map = scan_repo(project)
    import_graph, symbol_index = build_python_ast_indexes(project, repo_map)
    repo_chunks = build_repo_chunks(project, repo_map=repo_map, import_graph=import_graph, symbol_index=symbol_index)
    return repo_map, import_graph, symbol_index, repo_chunks


def test_build_agent_context_pack_is_deterministic_and_omits_timestamps(tmp_path: Path) -> None:
    project = _make_context_pack_repo(tmp_path)
    repo_map, import_graph, symbol_index, repo_chunks = _stable_artifacts(project)

    first = build_agent_context_pack(
        repo_map=repo_map,
        import_graph=import_graph,
        symbol_index=symbol_index,
        repo_chunks=repo_chunks,
    )
    repo_map["generator"]["generated_at"] = "2099-01-01T00:00:00Z"
    import_graph["generator"]["generated_at"] = "2099-01-01T00:00:01Z"
    symbol_index["generator"]["generated_at"] = "2099-01-01T00:00:02Z"
    repo_chunks["generator"]["generated_at"] = "2099-01-01T00:00:03Z"
    second = build_agent_context_pack(
        repo_map=repo_map,
        import_graph=import_graph,
        symbol_index=symbol_index,
        repo_chunks=repo_chunks,
    )

    assert first == second
    assert "generated_at" not in first
    assert first.endswith("\n")


def test_build_agent_context_pack_renders_core_sections(tmp_path: Path) -> None:
    project = _make_context_pack_repo(tmp_path)
    repo_map, import_graph, symbol_index, repo_chunks = _stable_artifacts(project)

    pack = build_agent_context_pack(
        repo_map=repo_map,
        import_graph=import_graph,
        symbol_index=symbol_index,
        repo_chunks=repo_chunks,
    )

    assert "# Agent Context Pack" in pack
    assert "## Generation Boundary" in pack
    assert "| Name | context-pack-project |" in pack
    assert "| Python |" not in pack
    assert "| python | 3 |" in pack
    assert "| console_script | context-pack | pyproject.toml | pkg.main:run | project.scripts |" in pack
    assert "| pkg.main | pkg/main.py | module |" in pack
    assert "| pkg.main | pkg.worker.Worker | from_import |" in pack
    assert "| pkg.main.App | class | pkg/main.py |" in pack
    assert "## Repo Chunks" in pack
    assert "| pkg/main.py | symbol | pkg.main | App |" in pack
    assert "| README.md | markdown |" in pack
    assert "No LLM summary" not in pack
    assert "LLM summary" in pack


def test_build_repo_query_context_pack_is_deterministic_and_agent_readable() -> None:
    query_result = _query_result()

    first = build_repo_query_context_pack(query_result=query_result)
    query_result["generator"]["generated_at"] = "2099-01-01T00:00:00Z"
    second = build_repo_query_context_pack(query_result=query_result)

    assert first == second
    assert first.endswith("\n")
    assert "generated_at" not in first
    assert "# Repo Query Context Pack" in first
    assert "## Generation Boundary" in first
    assert "## Handoff Contract" in first
    assert "stdout-only Markdown" in first
    assert "explicit agent input" in first
    assert "No hidden injection" in first
    assert "context_compiler" in first
    assert "| Text | where is run defined |" in first
    assert "| Matches | 1 |" in first
    assert "### 1. `pkg/main.py:3-4`" in first
    assert "| Symbol | run |" in first
    assert "```python\n" in first
    assert "def run():" in first
    assert "return VALUE" in first
    assert "| repo_vector_query_token_budget_exhausted | repo_chunk::demo::space::old | skipped |" in first


def test_build_repo_query_context_pack_expands_fence_for_backticks() -> None:
    query_result = _query_result()
    query_result["results"][0]["snippet"] = "```\ncode\n```\n"

    pack = build_repo_query_context_pack(query_result=query_result)

    assert "````python\n```\ncode\n```\n````" in pack


def test_build_repo_query_context_pack_preserves_retrieval_rank_order() -> None:
    query_result = _query_result()
    query_result["results"].append(
        {
            "key": "repo_chunk::demo::space::repo-chunk-v1:2",
            "similarity": 0.1111,
            "source_path": "aaa/early_path.py",
            "start_line": 1,
            "end_line": 1,
            "language": "python",
            "kind": "file_slice",
            "chunk_id": "repo-chunk-v1:2",
            "content_sha256": "f" * 64,
            "token_estimate": 3,
            "snippet": "VALUE = 1\n",
            "snippet_truncated": False,
            "content_status": "current",
        }
    )

    pack = build_repo_query_context_pack(query_result=query_result)

    assert pack.index("pkg/main.py:3-4") < pack.index("aaa/early_path.py:1-1")


def _query_result() -> dict[str, Any]:
    return {
        "schema_version": "1",
        "artifact_kind": "repo_vector_query_result",
        "generator": {
            "name": "ao-kernel",
            "version": "4.0.0",
            "generated_at": "2026-04-24T00:00:00Z",
        },
        "project": {
            "root": ".",
            "root_name": "context-pack-project",
            "name": "context-pack-project",
            "root_identity_sha256": "a" * 64,
        },
        "retriever": {
            "name": "ao-kernel-repo-vector-retriever",
            "version": "repo-vector-retriever.v1",
            "mode": "query_vectors",
        },
        "query": {
            "text": "where is run defined",
            "top_k": 5,
            "candidate_limit": 50,
            "min_similarity": 0.3,
            "max_tokens": 2000,
            "max_snippet_chars": 1200,
            "filters": {
                "source_path_prefix": "pkg/",
                "language": "python",
                "symbol": "run",
            },
        },
        "embedding_space": {
            "provider": "openai",
            "model": "text-embedding-3-small",
            "dimension": 1536,
            "embedding_space_id": "b" * 64,
        },
        "vector_namespace": {
            "key_prefix": "repo_chunk::demo::space::",
            "project_root_identity_sha256": "a" * 64,
        },
        "source_artifacts": {
            "repo_chunks_sha256": "c" * 64,
            "repo_vector_index_manifest_sha256": "d" * 64,
        },
        "summary": {
            "matches": 1,
            "candidate_matches": 3,
            "filtered_candidates": 1,
            "stale_candidates": 0,
            "embedding_calls": 1,
            "estimated_tokens": 12,
            "truncated_results": 0,
        },
        "results": [
            {
                "key": "repo_chunk::demo::space::repo-chunk-v1:1",
                "similarity": 0.9876,
                "source_path": "pkg/main.py",
                "start_line": 3,
                "end_line": 4,
                "language": "python",
                "kind": "symbol",
                "module": "pkg.main",
                "symbol": "run",
                "chunk_id": "repo-chunk-v1:1",
                "content_sha256": "e" * 64,
                "token_estimate": 12,
                "snippet": "def run():\n    return VALUE\n",
                "snippet_truncated": False,
                "content_status": "current",
            }
        ],
        "diagnostics": [
            {
                "code": "repo_vector_query_token_budget_exhausted",
                "message": "skipped",
                "key": "repo_chunk::demo::space::old",
            }
        ],
    }
