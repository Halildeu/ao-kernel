"""Deterministic repo vector write-plan generation for repo intelligence."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

import ao_kernel
from ao_kernel._internal.shared.utils import now_iso8601

JsonDict = dict[str, Any]

VECTOR_PLANNER_NAME = "ao-kernel-repo-vector-planner"
VECTOR_PLANNER_VERSION = "repo-vector-planner.v1"
VECTOR_KEY_PREFIX = "repo_chunk"
VECTOR_SOURCE = "repo_intelligence"
VECTOR_ARTIFACT_KIND = "repo_chunk"


def build_repo_vector_write_plan(
    *,
    repo_chunks: Mapping[str, Any],
    embedding_provider: str,
    embedding_model: str,
    embedding_dimension: int,
    previous_index_manifest: Mapping[str, Any] | None = None,
) -> JsonDict:
    """Build a dry-run vector write plan from a chunk manifest.

    The returned document only records keys, metadata, and stale-key cleanup
    intent. It does not embed source text, open a vector backend, or write
    vectors.
    """
    provider = embedding_provider.strip()
    model = embedding_model.strip()
    if not provider:
        raise ValueError("embedding_provider must be non-empty")
    if not model:
        raise ValueError("embedding_model must be non-empty")
    if embedding_dimension <= 0:
        raise ValueError("embedding_dimension must be positive")

    project = _mapping(repo_chunks.get("project"))
    chunker = _mapping(repo_chunks.get("chunker"))
    project_name = str(project.get("name") or project.get("root_name") or "")
    project_root_identity = str(project.get("root_identity_sha256") or "")
    chunker_version = str(chunker.get("version") or "")
    embedding_space_id = _embedding_space_id(
        provider=provider,
        model=model,
        dimension=embedding_dimension,
        chunker_version=chunker_version,
    )

    planned_upserts = [
        _planned_upsert(
            chunk,
            project_name=project_name,
            project_root_identity=project_root_identity,
            embedding_space_id=embedding_space_id,
            chunker_version=chunker_version,
            embedding_provider=provider,
            embedding_model=model,
            embedding_dimension=embedding_dimension,
        )
        for chunk in _chunk_records(repo_chunks)
    ]
    planned_upserts.sort(key=lambda item: str(item["key"]))
    current_keys = {str(item["key"]) for item in planned_upserts}

    previous_keys, diagnostics = _previous_indexed_keys(
        previous_index_manifest,
        project_root_identity=project_root_identity,
        embedding_space_id=embedding_space_id,
    )
    planned_deletes = [
        {"operation": "delete", "key": key}
        for key in sorted(set(previous_keys) - current_keys)
    ]

    return {
        "schema_version": "1",
        "artifact_kind": "repo_vector_write_plan",
        "generator": {
            "name": "ao-kernel",
            "version": ao_kernel.__version__,
            "generated_at": now_iso8601(),
        },
        "project": dict(project),
        "planner": {
            "name": VECTOR_PLANNER_NAME,
            "version": VECTOR_PLANNER_VERSION,
            "mode": "dry_run",
        },
        "embedding_space": {
            "provider": provider,
            "model": model,
            "dimension": embedding_dimension,
            "chunker_version": chunker_version,
            "embedding_space_id": embedding_space_id,
        },
        "vector_namespace": {
            "key_prefix": VECTOR_KEY_PREFIX,
            "project_root_identity_sha256": project_root_identity,
        },
        "source_artifacts": {
            "repo_chunks_sha256": _stable_document_sha256(repo_chunks),
        },
        "summary": {
            "dry_run": True,
            "chunks": len(planned_upserts),
            "planned_upserts": len(planned_upserts),
            "previous_indexed_keys": len(previous_keys),
            "planned_deletes": len(planned_deletes),
            "embedding_calls": 0,
            "vector_writes": 0,
        },
        "planned_upserts": planned_upserts,
        "planned_deletes": planned_deletes,
        "diagnostics": diagnostics,
    }


def _planned_upsert(
    chunk: Mapping[str, Any],
    *,
    project_name: str,
    project_root_identity: str,
    embedding_space_id: str,
    chunker_version: str,
    embedding_provider: str,
    embedding_model: str,
    embedding_dimension: int,
) -> JsonDict:
    chunk_id = str(chunk["chunk_id"])
    source_path = str(chunk["source_path"])
    content_sha256 = str(chunk["content_sha256"])
    key = _vector_key(
        project_root_identity=project_root_identity,
        embedding_space_id=embedding_space_id,
        chunk_id=chunk_id,
    )
    metadata: JsonDict = {
        "source": VECTOR_SOURCE,
        "artifact_kind": VECTOR_ARTIFACT_KIND,
        "project_name": project_name,
        "project_root_identity_sha256": project_root_identity,
        "source_path": source_path,
        "chunk_id": chunk_id,
        "content_sha256": content_sha256,
        "chunker_version": chunker_version,
        "embedding_provider": embedding_provider,
        "embedding_model": embedding_model,
        "embedding_dimension": embedding_dimension,
        "language": str(chunk["language"]),
        "kind": str(chunk["kind"]),
        "start_line": int(chunk["start_line"]),
        "end_line": int(chunk["end_line"]),
        "token_estimate": int(chunk.get("token_estimate") or 0),
    }
    if chunk.get("module"):
        metadata["module"] = str(chunk["module"])
    if chunk.get("symbol"):
        metadata["symbol"] = str(chunk["symbol"])
    return {
        "operation": "upsert",
        "key": key,
        "chunk_id": chunk_id,
        "source_path": source_path,
        "content_sha256": content_sha256,
        "metadata": metadata,
    }


def _chunk_records(repo_chunks: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    chunks = repo_chunks.get("chunks")
    if not isinstance(chunks, list):
        return []
    records = [item for item in chunks if isinstance(item, Mapping)]
    return sorted(
        records,
        key=lambda item: (
            str(item.get("source_path") or ""),
            int(item.get("start_line") or 0),
            int(item.get("end_line") or 0),
            str(item.get("chunk_id") or ""),
        ),
    )


def _previous_indexed_keys(
    manifest: Mapping[str, Any] | None,
    *,
    project_root_identity: str,
    embedding_space_id: str,
) -> tuple[list[str], list[JsonDict]]:
    if manifest is None:
        return [], []

    diagnostics: list[JsonDict] = []
    previous_project_identity = _previous_project_identity(manifest)
    previous_embedding_space = _previous_embedding_space_id(manifest)
    if not previous_project_identity:
        diagnostics.append(
            {
                "code": "previous_index_manifest_project_identity_missing",
                "message": "prior vector index manifest has no project identity; stale deletes are not planned",
            }
        )
        return [], diagnostics
    if previous_project_identity != project_root_identity:
        diagnostics.append(
            {
                "code": "previous_index_manifest_project_mismatch",
                "message": "prior vector index manifest belongs to a different project identity",
            }
        )
        return [], diagnostics
    if not previous_embedding_space:
        diagnostics.append(
            {
                "code": "previous_index_manifest_embedding_space_missing",
                "message": "prior vector index manifest has no embedding space; stale deletes are not planned",
            }
        )
        return [], diagnostics
    if previous_embedding_space != embedding_space_id:
        diagnostics.append(
            {
                "code": "previous_index_manifest_embedding_space_mismatch",
                "message": "prior vector index manifest belongs to a different embedding space",
            }
        )
        return [], diagnostics

    return _extract_key_list(manifest), diagnostics


def _previous_project_identity(manifest: Mapping[str, Any]) -> str:
    project = _mapping(manifest.get("project"))
    value = project.get("root_identity_sha256") or manifest.get("project_root_identity_sha256")
    return str(value or "")


def _previous_embedding_space_id(manifest: Mapping[str, Any]) -> str:
    embedding_space = _mapping(manifest.get("embedding_space"))
    value = embedding_space.get("embedding_space_id") or manifest.get("embedding_space_id")
    return str(value or "")


def _extract_key_list(manifest: Mapping[str, Any]) -> list[str]:
    for field in ("indexed_keys", "stored_keys"):
        value = manifest.get(field)
        if isinstance(value, list):
            return sorted({str(item) for item in value if isinstance(item, str)})

    vectors = manifest.get("vectors")
    if isinstance(vectors, list):
        keys = {
            str(item["key"])
            for item in vectors
            if isinstance(item, Mapping) and isinstance(item.get("key"), str)
        }
        return sorted(keys)
    return []


def _vector_key(
    *,
    project_root_identity: str,
    embedding_space_id: str,
    chunk_id: str,
) -> str:
    return f"{VECTOR_KEY_PREFIX}::{project_root_identity}::{embedding_space_id}::{chunk_id}"


def _embedding_space_id(
    *,
    provider: str,
    model: str,
    dimension: int,
    chunker_version: str,
) -> str:
    payload = "\n".join([provider, model, str(dimension), chunker_version])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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


__all__ = ["build_repo_vector_write_plan"]
