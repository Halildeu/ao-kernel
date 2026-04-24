"""Artifact validation and writing for repo-intelligence scans."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

import ao_kernel
from ao_kernel._internal.shared.utils import now_iso8601, write_json_atomic, write_text_atomic
from ao_kernel.config import load_default

REPO_MAP_FILENAME = "repo_map.json"
PYTHON_IMPORT_GRAPH_FILENAME = "import_graph.json"
PYTHON_SYMBOL_INDEX_FILENAME = "symbol_index.json"
REPO_CHUNKS_FILENAME = "repo_chunks.json"
AGENT_PACK_FILENAME = "agent_pack.md"
REPO_INDEX_MANIFEST_FILENAME = "repo_index_manifest.json"
REPO_MAP_SCHEMA_NAME = "repo-map.schema.v1.json"
PYTHON_IMPORT_GRAPH_SCHEMA_NAME = "python-import-graph.schema.v1.json"
PYTHON_SYMBOL_INDEX_SCHEMA_NAME = "python-symbol-index.schema.v1.json"
REPO_CHUNKS_SCHEMA_NAME = "repo-chunks.schema.v1.json"
REPO_INDEX_MANIFEST_SCHEMA_NAME = "repo-index-manifest.schema.v1.json"
AGENT_PACK_FORMAT_REF = "agent-pack-markdown.v1"

JsonDict = dict[str, Any]


def validate_repo_map(repo_map: Mapping[str, Any]) -> None:
    """Validate a repo map document against the bundled schema."""
    _validate(repo_map, REPO_MAP_SCHEMA_NAME)


def validate_repo_index_manifest(manifest: Mapping[str, Any]) -> None:
    """Validate a repo-index manifest document against the bundled schema."""
    _validate(manifest, REPO_INDEX_MANIFEST_SCHEMA_NAME)


def validate_python_import_graph(import_graph: Mapping[str, Any]) -> None:
    """Validate a Python import graph document against the bundled schema."""
    _validate(import_graph, PYTHON_IMPORT_GRAPH_SCHEMA_NAME)


def validate_python_symbol_index(symbol_index: Mapping[str, Any]) -> None:
    """Validate a Python symbol index document against the bundled schema."""
    _validate(symbol_index, PYTHON_SYMBOL_INDEX_SCHEMA_NAME)


def validate_repo_chunks(repo_chunks: Mapping[str, Any]) -> None:
    """Validate a repo chunks document against the bundled schema."""
    _validate(repo_chunks, REPO_CHUNKS_SCHEMA_NAME)


def write_repo_scan_artifacts(
    *,
    context_dir: str | Path,
    repo_map: Mapping[str, Any],
    import_graph: Mapping[str, Any] | None = None,
    symbol_index: Mapping[str, Any] | None = None,
    repo_chunks: Mapping[str, Any] | None = None,
    agent_pack: str | None = None,
) -> JsonDict:
    """Write repo-intelligence artifacts under an explicit context directory.

    The caller owns workspace discovery and directory creation. This helper
    only accepts explicit output location information and never searches for
    ``.ao``.
    """
    context = Path(context_dir)
    manifest_path = context / REPO_INDEX_MANIFEST_FILENAME

    validate_repo_map(repo_map)
    documents: list[tuple[str, str, Mapping[str, Any]]] = [
        (REPO_MAP_FILENAME, REPO_MAP_SCHEMA_NAME, repo_map),
    ]
    if import_graph is not None:
        validate_python_import_graph(import_graph)
        documents.append((PYTHON_IMPORT_GRAPH_FILENAME, PYTHON_IMPORT_GRAPH_SCHEMA_NAME, import_graph))
    if symbol_index is not None:
        validate_python_symbol_index(symbol_index)
        documents.append((PYTHON_SYMBOL_INDEX_FILENAME, PYTHON_SYMBOL_INDEX_SCHEMA_NAME, symbol_index))
    if repo_chunks is not None:
        validate_repo_chunks(repo_chunks)
        documents.append((REPO_CHUNKS_FILENAME, REPO_CHUNKS_SCHEMA_NAME, repo_chunks))

    artifact_records: list[JsonDict] = []
    for filename, schema_ref, document in documents:
        artifact_path = context / filename
        write_json_atomic(artifact_path, dict(document))
        artifact_records.append(
            _artifact_record(
                path=artifact_path,
                display_path=_display_path(context, filename),
                schema_ref=schema_ref,
            )
        )
    if agent_pack is not None:
        agent_pack_path = context / AGENT_PACK_FILENAME
        content = agent_pack if agent_pack.endswith("\n") else f"{agent_pack}\n"
        write_text_atomic(agent_pack_path, content)
        artifact_records.append(
            _artifact_record(
                path=agent_pack_path,
                display_path=_display_path(context, AGENT_PACK_FILENAME),
                format_ref=AGENT_PACK_FORMAT_REF,
                media_type="text/markdown",
            )
        )

    manifest = {
        "schema_version": "1",
        "artifact_kind": "repo_index_manifest",
        "generator": {
            "name": "ao-kernel",
            "version": ao_kernel.__version__,
            "generated_at": now_iso8601(),
        },
        "schema_refs": [
            *(schema_ref for _filename, schema_ref, _document in documents),
            REPO_INDEX_MANIFEST_SCHEMA_NAME,
        ],
        "artifacts": artifact_records,
    }
    validate_repo_index_manifest(manifest)
    write_json_atomic(manifest_path, manifest)

    manifest_record = _artifact_record(
        path=manifest_path,
        display_path=_display_path(context, REPO_INDEX_MANIFEST_FILENAME),
        schema_ref=REPO_INDEX_MANIFEST_SCHEMA_NAME,
    )
    return {
        "schema_version": "1",
        "artifact_kind": "repo_scan_write_result",
        "artifacts": [*artifact_records, manifest_record],
    }


def _validate(document: Mapping[str, Any], schema_name: str) -> None:
    from jsonschema import Draft202012Validator

    schema = load_default("schemas", schema_name)
    Draft202012Validator(schema).validate(document)


def _artifact_record(
    *,
    path: Path,
    display_path: str,
    schema_ref: str | None = None,
    format_ref: str | None = None,
    media_type: str | None = None,
) -> JsonDict:
    record: JsonDict = {
        "path": display_path,
        "sha256": _sha256_file(path),
        "bytes": path.stat().st_size,
    }
    if schema_ref is not None:
        record["schema_ref"] = schema_ref
    if format_ref is not None:
        record["format_ref"] = format_ref
    if media_type is not None:
        record["media_type"] = media_type
    return record


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(context_dir: Path, filename: str) -> str:
    if context_dir.name == "context" and context_dir.parent.name == ".ao":
        return f".ao/context/{filename}"
    return f"{context_dir.name}/{filename}"
