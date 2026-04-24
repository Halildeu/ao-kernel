"""Read-only repo vector retrieval for repo intelligence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

import ao_kernel
from ao_kernel._internal.shared.utils import now_iso8601

JsonDict = dict[str, Any]
EmbedTextFn = Callable[..., list[float] | None]

RETRIEVER_NAME = "ao-kernel-repo-vector-retriever"
RETRIEVER_VERSION = "repo-vector-retriever.v1"


def query_repo_vectors(
    *,
    project_root: str | Path,
    vector_index_manifest: Mapping[str, Any],
    vector_store: Any,
    embedding_config: Any,
    query: str,
    top_k: int = 5,
    candidate_limit: int = 50,
    min_similarity: float = 0.3,
    max_tokens: int = 2000,
    source_path_prefix: str | None = None,
    language: str | None = None,
    symbol: str | None = None,
    max_snippet_chars: int = 1200,
    embed_text_fn: EmbedTextFn | None = None,
) -> JsonDict:
    """Query previously-written repo chunk vectors without mutating state."""
    if vector_store is None:
        raise ValueError("vector_store is required for repo vector query")
    query_text = query.strip()
    if not query_text:
        raise ValueError("repo vector query text must be non-empty")
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    if candidate_limit <= 0:
        raise ValueError("candidate_limit must be positive")
    if candidate_limit < top_k:
        raise ValueError("candidate_limit must be greater than or equal to top_k")
    if min_similarity < 0:
        raise ValueError("min_similarity must be non-negative")
    if max_tokens <= 0:
        raise ValueError("max_tokens must be positive")
    if max_snippet_chars <= 0:
        raise ValueError("max_snippet_chars must be positive")

    api_key = str(embedding_config.resolve_api_key() or "").strip()
    if not api_key:
        raise ValueError("embedding API key is required for repo vector query")

    root = Path(project_root).resolve()
    embedding_space = _mapping(vector_index_manifest.get("embedding_space"))
    embedding_provider = str(embedding_space.get("provider") or "")
    embedding_model = str(embedding_space.get("model") or "")
    embedding_dimension = int(embedding_space.get("dimension") or 0)
    if embedding_provider != str(embedding_config.provider):
        raise ValueError("embedding provider mismatch between index manifest and embedding config")
    if embedding_model != str(embedding_config.model):
        raise ValueError("embedding model mismatch between index manifest and embedding config")
    if embedding_dimension <= 0:
        raise ValueError("embedding dimension must be positive")

    namespace_prefix = _namespace_prefix(vector_index_manifest)
    if not namespace_prefix:
        raise ValueError("repo vector index manifest is missing namespace identity")

    embed = embed_text_fn or _default_embed_text
    query_embedding = embed(
        query_text,
        provider_id=embedding_provider,
        model=embedding_model,
        base_url=str(embedding_config.base_url),
        api_key=api_key,
    )
    if not query_embedding:
        raise ValueError("embedding provider returned no vector for repo vector query")
    if len(query_embedding) != embedding_dimension:
        raise ValueError(
            f"query embedding dimension mismatch: expected {embedding_dimension}, got {len(query_embedding)}"
        )

    raw_results = vector_store.search(
        query_embedding,
        top_k=candidate_limit,
        min_similarity=min_similarity,
    )
    filters = _filters(
        source_path_prefix=source_path_prefix,
        language=language,
        symbol=symbol,
    )
    diagnostics: list[JsonDict] = []
    results: list[JsonDict] = []
    filtered_candidates = 0
    stale_candidates = 0
    truncated_results = 0
    estimated_tokens = 0

    for raw in _sorted_raw_results(raw_results):
        key = str(raw.get("key") or "")
        metadata = _mapping(raw.get("metadata"))
        if not _candidate_matches_namespace(key, metadata, namespace_prefix, vector_index_manifest, embedding_space):
            filtered_candidates += 1
            continue
        if not _candidate_matches_filters(metadata, filters):
            filtered_candidates += 1
            continue

        token_estimate = int(metadata.get("token_estimate") or 0)
        if estimated_tokens + token_estimate > max_tokens:
            diagnostics.append(
                {
                    "code": "repo_vector_query_token_budget_exhausted",
                    "message": "result skipped because it would exceed max_tokens",
                    "key": key,
                }
            )
            continue

        source_status = _read_current_chunk(root, metadata, max_snippet_chars=max_snippet_chars)
        if source_status["status"] != "current":
            stale_candidates += 1
            diagnostics.append(
                {
                    "code": f"repo_vector_query_{source_status['status']}",
                    "message": str(source_status["message"]),
                    "key": key,
                }
            )
            continue

        estimated_tokens += token_estimate
        if bool(source_status["truncated"]):
            truncated_results += 1
        results.append(
            _result_record(
                key=key,
                similarity=float(raw.get("similarity") or 0.0),
                metadata=metadata,
                snippet=str(source_status["snippet"]),
                snippet_truncated=bool(source_status["truncated"]),
            )
        )
        if len(results) >= top_k:
            break

    return {
        "schema_version": "1",
        "artifact_kind": "repo_vector_query_result",
        "generator": {
            "name": "ao-kernel",
            "version": ao_kernel.__version__,
            "generated_at": now_iso8601(),
        },
        "project": dict(_mapping(vector_index_manifest.get("project"))),
        "retriever": {
            "name": RETRIEVER_NAME,
            "version": RETRIEVER_VERSION,
            "mode": "query_vectors",
        },
        "query": {
            "text": query_text,
            "top_k": top_k,
            "candidate_limit": candidate_limit,
            "min_similarity": min_similarity,
            "max_tokens": max_tokens,
            "max_snippet_chars": max_snippet_chars,
            "filters": filters,
        },
        "embedding_space": dict(embedding_space),
        "vector_namespace": dict(_mapping(vector_index_manifest.get("vector_namespace"))),
        "source_artifacts": {
            "repo_chunks_sha256": str(_mapping(vector_index_manifest.get("source_artifacts")).get("repo_chunks_sha256")),
            "repo_vector_index_manifest_sha256": _stable_document_sha256(vector_index_manifest),
        },
        "summary": {
            "matches": len(results),
            "candidate_matches": len(raw_results),
            "filtered_candidates": filtered_candidates,
            "stale_candidates": stale_candidates,
            "embedding_calls": 1,
            "estimated_tokens": estimated_tokens,
            "truncated_results": truncated_results,
        },
        "results": results,
        "diagnostics": diagnostics,
    }


def _default_embed_text(*args: Any, **kwargs: Any) -> list[float] | None:
    from ao_kernel.context.semantic_retrieval import embed_text

    return embed_text(*args, **kwargs)


def _namespace_prefix(manifest: Mapping[str, Any]) -> str:
    namespace = _mapping(manifest.get("vector_namespace"))
    embedding_space = _mapping(manifest.get("embedding_space"))
    project_identity = str(namespace.get("project_root_identity_sha256") or "")
    embedding_space_id = str(embedding_space.get("embedding_space_id") or "")
    if not project_identity or not embedding_space_id:
        return ""
    return f"repo_chunk::{project_identity}::{embedding_space_id}::"


def _filters(
    *,
    source_path_prefix: str | None,
    language: str | None,
    symbol: str | None,
) -> JsonDict:
    filters: JsonDict = {}
    if source_path_prefix:
        filters["source_path_prefix"] = _normalize_path_prefix(source_path_prefix)
    if language:
        filters["language"] = language.strip()
    if symbol:
        filters["symbol"] = symbol.strip()
    return filters


def _normalize_path_prefix(value: str) -> str:
    return value.strip().replace("\\", "/").lstrip("/")


def _sorted_raw_results(raw_results: Any) -> list[Mapping[str, Any]]:
    records = [item for item in raw_results if isinstance(item, Mapping)]
    return sorted(
        records,
        key=lambda item: (
            -float(item.get("similarity") or 0.0),
            str(item.get("key") or ""),
        ),
    )


def _candidate_matches_namespace(
    key: str,
    metadata: Mapping[str, Any],
    namespace_prefix: str,
    manifest: Mapping[str, Any],
    embedding_space: Mapping[str, Any],
) -> bool:
    if not key.startswith(namespace_prefix):
        return False
    namespace = _mapping(manifest.get("vector_namespace"))
    expected_project = str(namespace.get("project_root_identity_sha256") or "")
    required = {
        "source": "repo_intelligence",
        "artifact_kind": "repo_chunk",
        "project_root_identity_sha256": expected_project,
        "embedding_provider": str(embedding_space.get("provider") or ""),
        "embedding_model": str(embedding_space.get("model") or ""),
    }
    for field, expected in required.items():
        if str(metadata.get(field) or "") != expected:
            return False
    if int(metadata.get("embedding_dimension") or 0) != int(embedding_space.get("dimension") or 0):
        return False
    return True


def _candidate_matches_filters(metadata: Mapping[str, Any], filters: Mapping[str, Any]) -> bool:
    source_prefix = str(filters.get("source_path_prefix") or "")
    if source_prefix and not str(metadata.get("source_path") or "").startswith(source_prefix):
        return False
    language = str(filters.get("language") or "")
    if language and str(metadata.get("language") or "") != language:
        return False
    symbol = str(filters.get("symbol") or "")
    if symbol and str(metadata.get("symbol") or "") != symbol:
        return False
    return True


def _read_current_chunk(project_root: Path, metadata: Mapping[str, Any], *, max_snippet_chars: int) -> JsonDict:
    rel_path = str(metadata.get("source_path") or "")
    if not rel_path:
        return {"status": "source_path_missing", "message": "candidate metadata has no source_path"}
    if _has_symlink_component(project_root, rel_path):
        return {"status": "source_path_symlink", "message": "candidate source path is a symbolic link"}
    source_path = _resolve_under_root(project_root, rel_path)
    if source_path is None:
        return {"status": "source_path_escape", "message": "candidate source path resolves outside project root"}
    if not source_path.is_file():
        return {"status": "source_path_missing", "message": "candidate source path is not a file"}

    content_bytes = source_path.read_bytes()
    line_bytes = content_bytes.splitlines(keepends=True)
    if not line_bytes and content_bytes:
        line_bytes = [content_bytes]
    start_line = int(metadata.get("start_line") or 0)
    end_line = int(metadata.get("end_line") or 0)
    if start_line < 1 or end_line < start_line or end_line > len(line_bytes):
        return {"status": "line_range_stale", "message": "candidate line range is outside source file"}
    chunk_bytes = b"".join(line_bytes[start_line - 1 : end_line])
    actual_hash = hashlib.sha256(chunk_bytes).hexdigest()
    expected_hash = str(metadata.get("content_sha256") or "")
    if actual_hash != expected_hash:
        return {"status": "content_hash_stale", "message": "candidate source content hash does not match index"}

    chunk_text = chunk_bytes.decode("utf-8")
    truncated = len(chunk_text) > max_snippet_chars
    snippet = chunk_text[:max_snippet_chars]
    return {
        "status": "current",
        "message": "candidate source content matches index",
        "snippet": snippet,
        "truncated": truncated,
    }


def _result_record(
    *,
    key: str,
    similarity: float,
    metadata: Mapping[str, Any],
    snippet: str,
    snippet_truncated: bool,
) -> JsonDict:
    result: JsonDict = {
        "key": key,
        "similarity": round(similarity, 4),
        "source_path": str(metadata["source_path"]),
        "start_line": int(metadata["start_line"]),
        "end_line": int(metadata["end_line"]),
        "language": str(metadata["language"]),
        "kind": str(metadata["kind"]),
        "chunk_id": str(metadata["chunk_id"]),
        "content_sha256": str(metadata["content_sha256"]),
        "token_estimate": int(metadata.get("token_estimate") or 0),
        "snippet": snippet,
        "snippet_truncated": snippet_truncated,
        "content_status": "current",
    }
    if metadata.get("module"):
        result["module"] = str(metadata["module"])
    if metadata.get("symbol"):
        result["symbol"] = str(metadata["symbol"])
    return result


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


__all__ = ["query_repo_vectors"]
