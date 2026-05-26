from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from ao_kernel._internal.repo_intelligence.artifacts import validate_repo_vector_index_manifest
from ao_kernel._internal.repo_intelligence.python_ast_indexer import build_python_ast_indexes
from ao_kernel._internal.repo_intelligence.repo_chunker import build_repo_chunks
from ao_kernel._internal.repo_intelligence.repo_vector_indexer import write_repo_vectors
from ao_kernel._internal.repo_intelligence.repo_vector_plan import build_repo_vector_write_plan
from ao_kernel._internal.repo_intelligence.scanner import scan_repo
from ao_kernel.context.embedding_config import EmbeddingConfig


class FakeVectorStore:
    def __init__(self, existing_keys: set[str] | None = None) -> None:
        self.existing_keys = set(existing_keys or set())
        self.operations: list[tuple[str, str]] = []
        self.stored: dict[str, dict[str, Any]] = {}

    def store(self, key: str, embedding: list[float], *, metadata: dict[str, Any] | None = None) -> None:
        self.operations.append(("store", key))
        self.stored[key] = {
            "embedding": embedding,
            "metadata": metadata or {},
        }

    def delete(self, key: str) -> bool:
        self.operations.append(("delete", key))
        if key in self.existing_keys:
            self.existing_keys.remove(key)
            return True
        return False


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "vector-index-project"
    (project / ".ao" / "context").mkdir(parents=True)
    (project / "pkg").mkdir()
    (project / "pkg" / "__init__.py").write_text("from .main import run\n", encoding="utf-8")
    (project / "pkg" / "main.py").write_text(
        "VALUE = 1\n\ndef run():\n    return VALUE\n",
        encoding="utf-8",
    )
    (project / "pyproject.toml").write_text('[project]\nname = "vector-index-project"\n', encoding="utf-8")
    return project


def _build_chunks(project: Path) -> dict[str, Any]:
    repo_map = scan_repo(project)
    import_graph, symbol_index = build_python_ast_indexes(project, repo_map)
    return build_repo_chunks(project, repo_map=repo_map, import_graph=import_graph, symbol_index=symbol_index)


def _build_plan(repo_chunks: dict[str, Any], previous_index_manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    return build_repo_vector_write_plan(
        repo_chunks=repo_chunks,
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        embedding_dimension=3,
        previous_index_manifest=previous_index_manifest,
    )


def _embedding_config(api_key: str = "test-key") -> EmbeddingConfig:
    return EmbeddingConfig(
        provider="openai",
        model="text-embedding-3-small",
        base_url="https://api.openai.com/v1",
        api_key=api_key,
    )


def _embed_text(*_args: Any, **_kwargs: Any) -> list[float]:
    return [0.1, 0.2, 0.3]


def test_write_repo_vectors_indexes_chunks_and_writes_schema_valid_manifest(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    repo_chunks = _build_chunks(project)
    plan = _build_plan(repo_chunks)
    store = FakeVectorStore()

    manifest = write_repo_vectors(
        project_root=project,
        vector_write_plan=plan,
        vector_store=store,
        embedding_config=_embedding_config(),
        embed_text_fn=_embed_text,
    )

    validate_repo_vector_index_manifest(manifest)
    assert manifest["artifact_kind"] == "repo_vector_index_manifest"
    assert manifest["summary"]["dry_run"] is False
    assert manifest["summary"]["embedding_calls"] == len(plan["planned_upserts"])
    assert manifest["summary"]["vector_writes"] == len(plan["planned_upserts"])
    assert manifest["summary"]["vector_deletes"] == 0
    assert manifest["deleted_keys"] == []
    assert sorted(store.stored) == manifest["indexed_keys"]

    first_key = manifest["indexed_keys"][0]
    metadata = store.stored[first_key]["metadata"]
    assert metadata["source"] == "repo_intelligence"
    assert metadata["artifact_kind"] == "repo_chunk"
    assert metadata["embedding_provider"] == "openai"
    assert metadata["embedding_model"] == "text-embedding-3-small"
    assert metadata["embedding_dimension"] == 3
    assert not metadata["source_path"].startswith("/")


def test_write_repo_vectors_deletes_stale_keys_before_upserts(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    repo_chunks = _build_chunks(project)
    current_plan = _build_plan(repo_chunks)
    stale_key = (
        "repo_chunk::"
        f"{current_plan['vector_namespace']['project_root_identity_sha256']}::"
        f"{current_plan['embedding_space']['embedding_space_id']}::"
        f"repo-chunk-v1:{'a' * 64}"
    )
    previous = {
        "project": deepcopy(current_plan["project"]),
        "embedding_space": deepcopy(current_plan["embedding_space"]),
        "indexed_keys": [current_plan["planned_upserts"][0]["key"], stale_key],
    }
    plan = _build_plan(repo_chunks, previous_index_manifest=previous)
    store = FakeVectorStore(existing_keys={stale_key})

    manifest = write_repo_vectors(
        project_root=project,
        vector_write_plan=plan,
        vector_store=store,
        embedding_config=_embedding_config(),
        embed_text_fn=_embed_text,
    )

    validate_repo_vector_index_manifest(manifest)
    assert manifest["deleted_keys"] == [stale_key]
    assert manifest["summary"]["vector_deletes"] == 1
    assert store.operations[0] == ("delete", stale_key)
    assert all(operation == "store" for operation, _key in store.operations[1:])


def test_write_repo_vectors_fails_closed_without_embedding_api_key(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    plan = _build_plan(_build_chunks(project))

    with pytest.raises(ValueError, match="embedding API key is required"):
        write_repo_vectors(
            project_root=project,
            vector_write_plan=plan,
            vector_store=FakeVectorStore(),
            embedding_config=_embedding_config(api_key=""),
            embed_text_fn=_embed_text,
        )


def test_write_repo_vectors_fails_closed_on_embedding_provider_mismatch(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    plan = _build_plan(_build_chunks(project))

    with pytest.raises(ValueError, match="embedding provider mismatch"):
        write_repo_vectors(
            project_root=project,
            vector_write_plan=plan,
            vector_store=FakeVectorStore(),
            embedding_config=EmbeddingConfig(
                provider="google",
                model="text-embedding-3-small",
                base_url="https://api.openai.com/v1",
                api_key="test-key",
            ),
            embed_text_fn=_embed_text,
        )


def test_write_repo_vectors_fails_closed_on_embedding_dimension_mismatch(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    plan = _build_plan(_build_chunks(project))

    with pytest.raises(ValueError, match="embedding dimension mismatch"):
        write_repo_vectors(
            project_root=project,
            vector_write_plan=plan,
            vector_store=FakeVectorStore(),
            embedding_config=_embedding_config(),
            embed_text_fn=lambda *_args, **_kwargs: [0.1, 0.2],
        )


def test_write_repo_vectors_fails_closed_on_source_content_hash_mismatch(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    plan = _build_plan(_build_chunks(project))
    (project / "pkg" / "main.py").write_text("VALUE = 2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="chunk content hash mismatch|chunk line range"):
        write_repo_vectors(
            project_root=project,
            vector_write_plan=plan,
            vector_store=FakeVectorStore(),
            embedding_config=_embedding_config(),
            embed_text_fn=_embed_text,
        )


def test_write_repo_vectors_does_not_mutate_store_when_preflight_fails(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    repo_chunks = _build_chunks(project)
    current_plan = _build_plan(repo_chunks)
    stale_key = (
        "repo_chunk::"
        f"{current_plan['vector_namespace']['project_root_identity_sha256']}::"
        f"{current_plan['embedding_space']['embedding_space_id']}::"
        f"repo-chunk-v1:{'e' * 64}"
    )
    previous = {
        "project": deepcopy(current_plan["project"]),
        "embedding_space": deepcopy(current_plan["embedding_space"]),
        "indexed_keys": [stale_key],
    }
    plan = _build_plan(repo_chunks, previous_index_manifest=previous)
    store = FakeVectorStore(existing_keys={stale_key})
    (project / "pkg" / "main.py").write_text("VALUE = 3\n", encoding="utf-8")

    with pytest.raises(ValueError, match="chunk content hash mismatch|chunk line range"):
        write_repo_vectors(
            project_root=project,
            vector_write_plan=plan,
            vector_store=store,
            embedding_config=_embedding_config(),
            embed_text_fn=_embed_text,
        )

    assert store.operations == []
    assert store.existing_keys == {stale_key}
    assert store.stored == {}


def test_write_repo_vectors_fails_closed_on_symlink_source_path(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    plan = _build_plan(_build_chunks(project))
    link_path = project / "pkg" / "main_link.py"
    try:
        link_path.symlink_to(project / "pkg" / "main.py")
    except OSError as exc:
        pytest.skip(f"symlink setup unavailable: {exc}")
    rel_link = "pkg/main_link.py"
    plan["planned_upserts"][0]["source_path"] = rel_link
    plan["planned_upserts"][0]["metadata"]["source_path"] = rel_link

    with pytest.raises(ValueError, match="symbolic link"):
        write_repo_vectors(
            project_root=project,
            vector_write_plan=plan,
            vector_store=FakeVectorStore(),
            embedding_config=_embedding_config(),
            embed_text_fn=_embed_text,
        )


def test_write_repo_vectors_fails_closed_on_key_outside_namespace(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    plan = _build_plan(_build_chunks(project))
    plan["planned_upserts"][0]["key"] = f"repo_chunk::{'b' * 64}::{'c' * 64}::repo-chunk-v1:{'d' * 64}"

    with pytest.raises(ValueError, match="outside the repo vector namespace"):
        write_repo_vectors(
            project_root=project,
            vector_write_plan=plan,
            vector_store=FakeVectorStore(),
            embedding_config=_embedding_config(),
            embed_text_fn=_embed_text,
        )


def test_write_repo_vectors_rejects_delete_key_outside_namespace_without_mutation(
    tmp_path: Path,
) -> None:
    """RI-7.2 guardrail: planned_deletes must enforce the same namespace key
    guard as planned_upserts; an outside-namespace delete key fails closed
    before any vector_store.delete or store call mutates the backend.
    """
    project = _make_project(tmp_path)
    # Seed an existing stale key that would otherwise be deleted on a real
    # previous-manifest re-index. We do not depend on the plan recording it
    # because we add an explicit out-of-namespace delete entry below.
    outside_namespace_delete_key = f"repo_chunk::{'1' * 64}::{'2' * 64}::repo-chunk-v1:{'3' * 64}"
    store = FakeVectorStore(existing_keys={outside_namespace_delete_key})
    plan = _build_plan(_build_chunks(project))
    # Inject a planned delete whose key lives outside this project's repo
    # vector namespace. The implementation must reject this before any
    # backend mutation, matching the upsert-side namespace contract.
    plan.setdefault("planned_deletes", []).append(
        {
            "operation": "delete",
            "key": outside_namespace_delete_key,
        }
    )

    # RI-7.2 guardrail: namespace pre-validation must reject the delete key
    # BEFORE any embedding provider call. A test-side embed_text counter
    # asserts zero embedding calls (no API cost) on the fail-closed path.
    embed_calls: list[tuple[Any, ...]] = []

    def _counting_embed(*args: Any, **kwargs: Any) -> list[float]:
        embed_calls.append((args, kwargs))
        return [0.1, 0.2, 0.3]

    with pytest.raises(ValueError, match="outside the repo vector namespace"):
        write_repo_vectors(
            project_root=project,
            vector_write_plan=plan,
            vector_store=store,
            embedding_config=_embedding_config(),
            embed_text_fn=_counting_embed,
        )

    # No vector_store mutation and no embedding cost must have occurred:
    # the outside-namespace key is still present in the backend, no
    # store/delete operations were recorded, and embed_text_fn was never
    # invoked (fail-closed before any provider call).
    assert outside_namespace_delete_key in store.existing_keys
    assert store.operations == []
    assert store.stored == {}
    assert embed_calls == []


def test_write_repo_vectors_fails_closed_when_vector_store_is_none(tmp_path: Path) -> None:
    """RI-7.3: direct write surface fails closed when no backend is configured.

    The CLI surface enforces this via the resolver; this regression pins the
    same contract at the core function level so callers that bypass the CLI
    cannot accidentally write vectors without a configured backend.
    """
    project = _make_project(tmp_path)
    plan = _build_plan(_build_chunks(project))
    embed_calls: list[Any] = []

    def _counting_embed(*args: Any, **kwargs: Any) -> list[float]:
        embed_calls.append((args, kwargs))
        return [0.1, 0.2, 0.3]

    with pytest.raises(ValueError, match="vector_store"):
        write_repo_vectors(
            project_root=project,
            vector_write_plan=plan,
            vector_store=None,
            embedding_config=_embedding_config(),
            embed_text_fn=_counting_embed,
        )
    # Fail-closed must happen before any embedding call.
    assert embed_calls == []


def test_write_repo_vectors_treats_none_api_key_as_missing(tmp_path: Path) -> None:
    """RI-7.3: an embedding config whose ``resolve_api_key()`` returns None
    is treated as a missing API key at the write surface (parity with the
    existing query-side regression).
    """
    project = _make_project(tmp_path)
    plan = _build_plan(_build_chunks(project))

    class _NoneKeyConfig:
        provider = "openai"
        model = "text-embedding-3-small"
        base_url = "https://api.openai.com/v1"

        def resolve_api_key(self) -> None:
            return None

    embed_calls: list[Any] = []

    def _counting_embed(*args: Any, **kwargs: Any) -> list[float]:
        embed_calls.append((args, kwargs))
        return [0.1, 0.2, 0.3]

    with pytest.raises(ValueError, match="API key|api key|api_key"):
        write_repo_vectors(
            project_root=project,
            vector_write_plan=plan,
            vector_store=FakeVectorStore(),
            embedding_config=_NoneKeyConfig(),
            embed_text_fn=_counting_embed,
        )
    assert embed_calls == []
