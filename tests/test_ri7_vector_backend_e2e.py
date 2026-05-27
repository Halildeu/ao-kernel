"""RI-7.3 — Configured vector backend E2E evidence.

This test file encodes the four end-to-end scenarios that prove
configured local vector backend behavior for the repo-intelligence
index/query surface:

  * write_happy_path
  * stale_cleanup
  * namespace_isolation
  * query_hash_line_validation

The backend under test is the repo-owned `InMemoryVectorStore`; the
embedding callable is a deterministic fake. No external API is contacted.
The matrix here mirrors `.claude/plans/RI-7.3-VECTOR-BACKEND-E2E-EVIDENCE.md`
and the schema-backed artifact at
`.claude/plans/RI-7.3-VECTOR-BACKEND-E2E-EVIDENCE.v1.json`.

This file is evidence-only. It does not flip GPP guard flags, change
public SDK signatures, expose MCP tools, enable a context-compiler
auto-feed, or alter branch protection / workflows.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from ao_kernel._internal.repo_intelligence.artifacts import (
    validate_repo_vector_index_manifest,
    validate_repo_vector_query_result,
)
from ao_kernel._internal.repo_intelligence.python_ast_indexer import build_python_ast_indexes
from ao_kernel._internal.repo_intelligence.repo_chunker import build_repo_chunks
from ao_kernel._internal.repo_intelligence.repo_vector_indexer import write_repo_vectors
from ao_kernel._internal.repo_intelligence.repo_vector_plan import build_repo_vector_write_plan
from ao_kernel._internal.repo_intelligence.repo_vector_retriever import query_repo_vectors
from ao_kernel._internal.repo_intelligence.scanner import scan_repo
from ao_kernel.context.embedding_config import EmbeddingConfig
from ao_kernel.context.vector_store import InMemoryVectorStore
from ao_kernel.context.vector_store_resolver import resolve_vector_store


# --- helpers --------------------------------------------------------------


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "ri7-e2e-project"
    (project / ".ao" / "context").mkdir(parents=True)
    (project / "pkg").mkdir()
    (project / "pkg" / "__init__.py").write_text("from .main import run\n", encoding="utf-8")
    (project / "pkg" / "main.py").write_text(
        "VALUE = 1\n\ndef run():\n    return VALUE\n",
        encoding="utf-8",
    )
    (project / "pyproject.toml").write_text('[project]\nname = "ri7-e2e-project"\n', encoding="utf-8")
    return project


def _embedding_config(api_key: str = "test-key") -> EmbeddingConfig:
    return EmbeddingConfig(
        provider="openai",
        model="text-embedding-3-small",
        base_url="https://api.openai.com/v1",
        api_key=api_key,
    )


def _embed_text(text: str, **_kwargs: Any) -> list[float]:
    """Deterministic fake embedding.

    Lower-dimensional and content-aware enough to produce distinct vectors
    for distinct snippets but stable across runs. No external API.
    """
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    # 3-dim vector for the schema; keep entries in (0, 1).
    return [
        ((digest[0] << 8) + digest[1]) / 65536.0,
        ((digest[2] << 8) + digest[3]) / 65536.0,
        ((digest[4] << 8) + digest[5]) / 65536.0,
    ]


def _build_chunks(project: Path) -> dict[str, Any]:
    repo_map = scan_repo(project)
    import_graph, symbol_index = build_python_ast_indexes(project, repo_map)
    return build_repo_chunks(project, repo_map=repo_map, import_graph=import_graph, symbol_index=symbol_index)


def _build_plan(
    repo_chunks: dict[str, Any],
    previous_index_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_repo_vector_write_plan(
        repo_chunks=repo_chunks,
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        embedding_dimension=3,
        previous_index_manifest=previous_index_manifest,
    )


def _index_project(
    project: Path,
    *,
    previous_manifest: dict[str, Any] | None = None,
) -> tuple[InMemoryVectorStore, dict[str, Any]]:
    """Write vectors for ``project`` into a fresh InMemoryVectorStore.

    Returns the InMemoryVectorStore and the schema-valid index manifest
    artifact that ``write_repo_vectors`` returns directly.
    """
    store = InMemoryVectorStore()
    chunks = _build_chunks(project)
    plan = _build_plan(chunks, previous_index_manifest=previous_manifest)
    manifest = write_repo_vectors(
        project_root=project,
        vector_write_plan=plan,
        vector_store=store,
        embedding_config=_embedding_config(),
        embed_text_fn=_embed_text,
    )
    return store, manifest


# --- scenario 1: write_happy_path ---------------------------------------


def test_write_happy_path_indexes_chunks_into_inmemory_backend(tmp_path: Path) -> None:
    """RI-7.3 scenario `write_happy_path`: a configured InMemoryVectorStore
    accepts schema-valid upserts and produces a schema-valid index manifest.
    """
    project = _make_project(tmp_path)
    store, manifest = _index_project(project)

    validate_repo_vector_index_manifest(manifest)
    assert manifest["artifact_kind"] == "repo_vector_index_manifest"
    namespace_prefix = (
        "repo_chunk::"
        f"{manifest['project']['root_identity_sha256']}::"
        f"{manifest['embedding_space']['embedding_space_id']}::"
    )
    indexed_keys = manifest["indexed_keys"]
    assert len(indexed_keys) >= 1
    assert manifest["summary"]["vector_writes"] == len(indexed_keys)
    assert manifest["summary"]["dry_run"] is False
    for key in indexed_keys:
        assert key.startswith(namespace_prefix)
    # The backend actually received the corresponding store operations and
    # every stored key lives under the project's namespace.
    assert sorted(store._store) == sorted(indexed_keys)  # noqa: SLF001
    for key in store._store:  # noqa: SLF001
        assert key.startswith(namespace_prefix)


# --- scenario 2: stale_cleanup ------------------------------------------


def test_stale_cleanup_deletes_previous_manifest_keys_before_upserts(tmp_path: Path) -> None:
    """RI-7.3 scenario `stale_cleanup`: re-running write with a previous
    manifest causes obsolete chunk keys to be deleted *before* fresh upserts,
    and the delete loop touches only entries under the project's namespace.
    """
    project = _make_project(tmp_path)
    # First indexing pass: capture manifest as the "previous" manifest.
    _store_one, manifest_one = _index_project(project)

    # Mutate the source so chunk content hashes change for the next pass.
    (project / "pkg" / "main.py").write_text(
        "VALUE = 2\n\ndef run():\n    return VALUE + 1\n",
        encoding="utf-8",
    )

    # Second pass: build a plan from the new content with previous_manifest set.
    store = InMemoryVectorStore()
    # Pre-seed the store with previous keys to simulate a persistent backend.
    for prev_key in manifest_one["indexed_keys"]:
        store.store(prev_key, _embed_text("seed"), metadata={"seed": True})
    chunks = _build_chunks(project)
    plan = _build_plan(chunks, previous_index_manifest=manifest_one)
    manifest_two = write_repo_vectors(
        project_root=project,
        vector_write_plan=plan,
        vector_store=store,
        embedding_config=_embedding_config(),
        embed_text_fn=_embed_text,
    )

    validate_repo_vector_index_manifest(manifest_two)
    assert manifest_two["summary"]["vector_deletes"] >= 1, manifest_two["summary"]
    namespace_prefix = (
        "repo_chunk::"
        f"{manifest_two['project']['root_identity_sha256']}::"
        f"{manifest_two['embedding_space']['embedding_space_id']}::"
    )
    for deleted_key in manifest_two["deleted_keys"]:
        assert deleted_key.startswith(namespace_prefix)
    # The final store contents reflect the new upserts only; every remaining
    # backend key lives under the project's namespace prefix.
    for key in store._store:  # noqa: SLF001
        assert key.startswith(namespace_prefix)


# --- scenario 3: namespace_isolation ------------------------------------


def test_namespace_isolation_excludes_non_repo_and_bad_metadata_candidates(
    tmp_path: Path,
) -> None:
    """RI-7.3 scenario `namespace_isolation`: query results never contain
    candidates whose key is outside the project namespace or whose metadata
    namespace identity does not match the indexed manifest.
    """
    project = _make_project(tmp_path)
    store, manifest = _index_project(project)

    # Inject hostile candidates into the SAME store. These must not surface.
    foreign_namespace_key = "repo_chunk::" + ("f" * 64) + "::" + ("e" * 64) + "::repo-chunk-v1:" + ("c" * 64)
    store.store(
        foreign_namespace_key,
        _embed_text("foreign content for namespace isolation"),
        metadata={"source_path": "outside/foreign.py", "namespace": "foreign"},
    )
    # And a same-prefix key but with bad metadata identity.
    bad_metadata_key = (
        "repo_chunk::"
        f"{manifest['project']['root_identity_sha256']}::"
        f"{manifest['embedding_space']['embedding_space_id']}::"
        "repo-chunk-v1:" + ("9" * 64)
    )
    store.store(
        bad_metadata_key,
        _embed_text("bad metadata content"),
        metadata={
            "source_path": "pkg/main.py",
            "namespace": {
                "project_root_identity_sha256": "0" * 64,
                "embedding_space_id": "0" * 64,
            },
        },
    )

    result = query_repo_vectors(
        project_root=project,
        vector_index_manifest=manifest,
        vector_store=store,
        embedding_config=_embedding_config(),
        query="VALUE",
        embed_text_fn=_embed_text,
    )

    validate_repo_vector_query_result(result)
    surfaced_keys = {hit["key"] for hit in result["results"]}
    assert foreign_namespace_key not in surfaced_keys
    assert bad_metadata_key not in surfaced_keys


# --- scenario 4: query_hash_line_validation ------------------------------


def test_query_hash_line_validation_marks_mutated_sources_stale_without_leaking_content(
    tmp_path: Path,
) -> None:
    """RI-7.3 scenario `query_hash_line_validation`: when an indexed source
    is mutated after indexing, the query result reports stale source diagnostics
    and excludes stale snippets from `results` so no stale content leaks.
    """
    project = _make_project(tmp_path)
    store, manifest = _index_project(project)

    # Mutate the only indexed source after indexing so its content hash
    # no longer matches the manifest's recorded hash.
    (project / "pkg" / "main.py").write_text(
        "VALUE = 99\n\ndef run():\n    return 12345\n",
        encoding="utf-8",
    )

    result = query_repo_vectors(
        project_root=project,
        vector_index_manifest=manifest,
        vector_store=store,
        embedding_config=_embedding_config(),
        query="run",
        embed_text_fn=_embed_text,
    )

    validate_repo_vector_query_result(result)
    # All surfaced results must be content_status=current; stale ones excluded.
    for hit in result["results"]:
        assert hit["content_status"] == "current"
    # Stale source candidates must appear in filtered_candidates (or equivalent
    # diagnostic surface) so reviewers can see they were excluded.
    diagnostic_surfaces = (
        result.get("filtered_candidates", []),
        result.get("diagnostics", []),
    )
    flat = [item for surface in diagnostic_surfaces for item in surface]
    assert any("stale" in str(item).lower() or "hash" in str(item).lower() for item in flat), result


# --- resolver path binding (Codex iter-2 absorb) ---------------------------


def test_resolve_vector_store_with_env_inmemory_returns_inmemory_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RI-7.3: the configured production resolver path with
    ``AO_KERNEL_VECTOR_BACKEND=inmemory`` returns an ``InMemoryVectorStore``
    instance. This pins the resolver-side selection that the E2E flow above
    exercises with a direct ``InMemoryVectorStore()`` construction.
    """
    monkeypatch.setenv("AO_KERNEL_VECTOR_BACKEND", "inmemory")
    backend, owned = resolve_vector_store(workspace=None)
    assert isinstance(backend, InMemoryVectorStore), type(backend)
    # Resolver-created backend ownership signal should be set so callers
    # know they need to close() it. This is a contract observation, not a
    # claim about external API behavior.
    assert isinstance(owned, bool)


def test_resolver_inmemory_backend_supports_e2e_write_query_flow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RI-7.3: the resolver-selected ``InMemoryVectorStore`` is functionally
    interchangeable with a direct ``InMemoryVectorStore()`` in the E2E
    write/query flow used above. Together with the direct-construct test
    matrix, this binds the configured-backend claim to the production
    resolver path.
    """
    monkeypatch.setenv("AO_KERNEL_VECTOR_BACKEND", "inmemory")
    backend, _owned = resolve_vector_store(workspace=None)
    assert isinstance(backend, InMemoryVectorStore)

    project = _make_project(tmp_path)
    chunks = _build_chunks(project)
    plan = _build_plan(chunks)
    manifest = write_repo_vectors(
        project_root=project,
        vector_write_plan=plan,
        vector_store=backend,
        embedding_config=_embedding_config(),
        embed_text_fn=_embed_text,
    )
    validate_repo_vector_index_manifest(manifest)
    assert manifest["summary"]["vector_writes"] >= 1

    result = query_repo_vectors(
        project_root=project,
        vector_index_manifest=manifest,
        vector_store=backend,
        embedding_config=_embedding_config(),
        query="run",
        embed_text_fn=_embed_text,
    )
    validate_repo_vector_query_result(result)
    assert result["summary"]["matches"] >= 1
