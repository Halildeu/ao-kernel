"""Artifact validation and writing for repo-intelligence scans."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

import ao_kernel
from ao_kernel._internal.shared.utils import now_iso8601, write_json_atomic
from ao_kernel.config import load_default

REPO_MAP_FILENAME = "repo_map.json"
REPO_INDEX_MANIFEST_FILENAME = "repo_index_manifest.json"
REPO_MAP_SCHEMA_NAME = "repo-map.schema.v1.json"
REPO_INDEX_MANIFEST_SCHEMA_NAME = "repo-index-manifest.schema.v1.json"

JsonDict = dict[str, Any]


def validate_repo_map(repo_map: Mapping[str, Any]) -> None:
    """Validate a repo map document against the bundled schema."""
    _validate(repo_map, REPO_MAP_SCHEMA_NAME)


def validate_repo_index_manifest(manifest: Mapping[str, Any]) -> None:
    """Validate a repo-index manifest document against the bundled schema."""
    _validate(manifest, REPO_INDEX_MANIFEST_SCHEMA_NAME)


def write_repo_scan_artifacts(*, context_dir: str | Path, repo_map: Mapping[str, Any]) -> JsonDict:
    """Write RI-1 artifacts under an explicit context directory.

    The caller owns workspace discovery and directory creation. This helper
    only accepts explicit output location information and never searches for
    ``.ao``.
    """
    context = Path(context_dir)
    repo_map_path = context / REPO_MAP_FILENAME
    manifest_path = context / REPO_INDEX_MANIFEST_FILENAME

    validate_repo_map(repo_map)
    write_json_atomic(repo_map_path, dict(repo_map))

    repo_map_record = _artifact_record(
        path=repo_map_path,
        display_path=_display_path(context, REPO_MAP_FILENAME),
        schema_ref=REPO_MAP_SCHEMA_NAME,
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
            REPO_MAP_SCHEMA_NAME,
            REPO_INDEX_MANIFEST_SCHEMA_NAME,
        ],
        "artifacts": [repo_map_record],
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
        "artifacts": [repo_map_record, manifest_record],
    }


def _validate(document: Mapping[str, Any], schema_name: str) -> None:
    from jsonschema import Draft202012Validator

    schema = load_default("schemas", schema_name)
    Draft202012Validator(schema).validate(document)


def _artifact_record(*, path: Path, display_path: str, schema_ref: str) -> JsonDict:
    return {
        "path": display_path,
        "schema_ref": schema_ref,
        "sha256": _sha256_file(path),
        "bytes": path.stat().st_size,
    }


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
