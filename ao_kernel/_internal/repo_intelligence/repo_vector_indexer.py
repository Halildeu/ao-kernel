"""Explicit repo vector indexing for repo intelligence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

import ao_kernel
from ao_kernel._internal.repo_intelligence.artifacts import validate_repo_vector_write_plan
from ao_kernel._internal.shared.utils import now_iso8601

JsonDict = dict[str, Any]
EmbedTextFn = Callable[..., list[float] | None]

CONFIRM_VECTOR_INDEX = "I_UNDERSTAND_REPO_VECTOR_WRITES"
INDEXER_NAME = "ao-kernel-repo-vector-indexer"
INDEXER_VERSION = "repo-vector-indexer.v1"


def write_repo_vectors(
    *,
    project_root: str | Path,
    vector_write_plan: Mapping[str, Any],
    vector_store: Any,
    embedding_config: Any,
    embed_text_fn: EmbedTextFn | None = None,
) -> JsonDict:
    """Apply an explicit vector write-plan and return an index manifest.

    This function performs real vector backend mutations. Callers must keep the
    CLI confirmation and backend resolution outside this function so tests can
    inject controlled stores and embedding functions.
    """
    if vector_store is None:
        raise ValueError("vector_store is required for repo vector writes")

    validate_repo_vector_write_plan(vector_write_plan)

    api_key = str(embedding_config.resolve_api_key() or "").strip()
    if not api_key:
        raise ValueError("embedding API key is required for repo vector writes")

    root = Path(project_root).resolve()
    embedding_space = _mapping(vector_write_plan.get("embedding_space"))
    embedding_provider = str(embedding_space.get("provider") or "")
    embedding_model = str(embedding_space.get("model") or "")
    embedding_dimension = int(embedding_space.get("dimension") or 0)
    if embedding_provider != str(embedding_config.provider):
        raise ValueError("embedding provider mismatch between write-plan and embedding config")
    if embedding_model != str(embedding_config.model):
        raise ValueError("embedding model mismatch between write-plan and embedding config")
    if embedding_dimension <= 0:
        raise ValueError("embedding dimension must be positive")

    namespace_prefix = _namespace_prefix(vector_write_plan)
    if not namespace_prefix:
        raise ValueError("vector write-plan is missing namespace identity")

    embed = embed_text_fn or _default_embed_text
    prepared_vectors: list[tuple[str, Mapping[str, Any], dict[str, Any], list[float]]] = []
    embedding_calls = 0
    for item in _planned_upserts(vector_write_plan):
        key = str(item["key"])
        _require_namespace_key(key, namespace_prefix)
        metadata = dict(_mapping(item.get("metadata")))
        _validate_upsert_metadata(
            item,
            metadata=metadata,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            embedding_dimension=embedding_dimension,
        )
        text = _read_chunk_text(root, metadata)
        vector = embed(
            text,
            provider_id=embedding_provider,
            model=embedding_model,
            base_url=str(embedding_config.base_url),
            api_key=api_key,
        )
        embedding_calls += 1
        if not vector:
            raise ValueError(f"embedding provider returned no vector for {key}")
        if len(vector) != embedding_dimension:
            raise ValueError(
                f"embedding dimension mismatch for {key}: expected {embedding_dimension}, got {len(vector)}"
            )
        prepared_vectors.append((key, item, metadata, vector))

    deleted_keys: list[str] = []
    delete_missing_keys: list[str] = []
    for item in _planned_deletes(vector_write_plan):
        key = str(item["key"])
        _require_namespace_key(key, namespace_prefix)
        if bool(vector_store.delete(key)):
            deleted_keys.append(key)
        else:
            delete_missing_keys.append(key)

    indexed_keys: list[str] = []
    vector_records: list[JsonDict] = []
    for key, item, metadata, vector in prepared_vectors:
        vector_store.store(key, vector, metadata=metadata)
        indexed_keys.append(key)
        vector_records.append(
            {
                "key": key,
                "chunk_id": str(item["chunk_id"]),
                "source_path": str(item["source_path"]),
                "content_sha256": str(item["content_sha256"]),
            }
        )

    indexed_keys.sort()
    deleted_keys.sort()
    delete_missing_keys.sort()
    vector_records.sort(key=lambda item: str(item["key"]))

    return {
        "schema_version": "1",
        "artifact_kind": "repo_vector_index_manifest",
        "generator": {
            "name": "ao-kernel",
            "version": ao_kernel.__version__,
            "generated_at": now_iso8601(),
        },
        "project": dict(_mapping(vector_write_plan.get("project"))),
        "indexer": {
            "name": INDEXER_NAME,
            "version": INDEXER_VERSION,
            "mode": "write_vectors",
        },
        "embedding_space": dict(embedding_space),
        "vector_namespace": dict(_mapping(vector_write_plan.get("vector_namespace"))),
        "source_artifacts": {
            "repo_chunks_sha256": str(_mapping(vector_write_plan.get("source_artifacts")).get("repo_chunks_sha256")),
            "repo_vector_write_plan_sha256": _stable_document_sha256(vector_write_plan),
        },
        "summary": {
            "dry_run": False,
            "indexed_keys": len(indexed_keys),
            "deleted_keys": len(deleted_keys),
            "delete_missing_keys": len(delete_missing_keys),
            "embedding_calls": embedding_calls,
            "vector_writes": len(indexed_keys),
            "vector_deletes": len(deleted_keys),
        },
        "indexed_keys": indexed_keys,
        "deleted_keys": deleted_keys,
        "delete_missing_keys": delete_missing_keys,
        "vectors": vector_records,
        "diagnostics": list(_diagnostics(vector_write_plan)),
    }


def _default_embed_text(*args: Any, **kwargs: Any) -> list[float] | None:
    from ao_kernel.context.semantic_retrieval import embed_text

    return embed_text(*args, **kwargs)


def _planned_upserts(plan: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    records = [item for item in plan.get("planned_upserts", []) if isinstance(item, Mapping)]
    return sorted(records, key=lambda item: str(item.get("key") or ""))


def _planned_deletes(plan: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    records = [item for item in plan.get("planned_deletes", []) if isinstance(item, Mapping)]
    return sorted(records, key=lambda item: str(item.get("key") or ""))


def _diagnostics(plan: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [item for item in plan.get("diagnostics", []) if isinstance(item, Mapping)]


def _namespace_prefix(plan: Mapping[str, Any]) -> str:
    namespace = _mapping(plan.get("vector_namespace"))
    embedding_space = _mapping(plan.get("embedding_space"))
    project_identity = str(namespace.get("project_root_identity_sha256") or "")
    embedding_space_id = str(embedding_space.get("embedding_space_id") or "")
    if not project_identity or not embedding_space_id:
        return ""
    return f"repo_chunk::{project_identity}::{embedding_space_id}::"


def _require_namespace_key(key: str, namespace_prefix: str) -> None:
    if not key.startswith(namespace_prefix):
        raise ValueError("vector key is outside the repo vector namespace")


def _validate_upsert_metadata(
    item: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any],
    embedding_provider: str,
    embedding_model: str,
    embedding_dimension: int,
) -> None:
    required_equalities = {
        "chunk_id": str(item["chunk_id"]),
        "source_path": str(item["source_path"]),
        "content_sha256": str(item["content_sha256"]),
        "embedding_provider": embedding_provider,
        "embedding_model": embedding_model,
    }
    for field, expected in required_equalities.items():
        if str(metadata.get(field) or "") != expected:
            raise ValueError(f"vector metadata field mismatch: {field}")
    if int(metadata.get("embedding_dimension") or 0) != embedding_dimension:
        raise ValueError("vector metadata embedding_dimension mismatch")


def _read_chunk_text(project_root: Path, metadata: Mapping[str, Any]) -> str:
    rel_path = str(metadata["source_path"])
    if _has_symlink_component(project_root, rel_path):
        raise ValueError("chunk source path is a symbolic link")
    source_path = _resolve_under_root(project_root, rel_path)
    if source_path is None:
        raise ValueError("chunk source path resolves outside project root")
    content_bytes = source_path.read_bytes()
    line_bytes = content_bytes.splitlines(keepends=True)
    if not line_bytes and content_bytes:
        line_bytes = [content_bytes]
    start_line = int(metadata["start_line"])
    end_line = int(metadata["end_line"])
    if start_line < 1 or end_line < start_line or end_line > len(line_bytes):
        raise ValueError("chunk line range is outside source file")
    chunk_bytes = b"".join(line_bytes[start_line - 1 : end_line])
    actual_hash = hashlib.sha256(chunk_bytes).hexdigest()
    expected_hash = str(metadata["content_sha256"])
    if actual_hash != expected_hash:
        raise ValueError("chunk content hash mismatch")
    return chunk_bytes.decode("utf-8")


def _resolve_under_root(root: Path, rel_path: str) -> Path | None:
    candidate = (root / rel_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _has_symlink_component(root: Path, rel_path: str) -> bool:
    current = root
    for part in Path(rel_path).parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _stable_document_sha256(document: Mapping[str, Any]) -> str:
    normalized = _without_generated_at(document)
    content = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _without_generated_at(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _without_generated_at(item)
            for key, item in value.items()
            if str(key) != "generated_at"
        }
    if isinstance(value, list):
        return [_without_generated_at(item) for item in value]
    return value


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


__all__ = ["CONFIRM_VECTOR_INDEX", "write_repo_vectors"]
