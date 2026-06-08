"""Mapping load + schema validation + repo-confined source resolution (internal)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ao_kernel.config import load_default

_SCHEMA_NAME = "context-doc-bridge-mapping.schema.v1.json"
_DEFAULT_MAPPING = "doc_mapping.default.v1.json"

DEFAULT_MAX_FILES = 500
DEFAULT_MAX_BYTES = 1_048_576


def load_mapping(path: str | None = None) -> dict[str, Any]:
    """Load the bundled default mapping (path=None) or a custom mapping file.

    Always schema-validated before return (fail-closed on malformed config).
    """
    if path is None:
        mapping = load_default("context_bridge", _DEFAULT_MAPPING)
    else:
        mapping = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_mapping(mapping)
    return mapping


def validate_mapping(mapping: dict[str, Any]) -> None:
    from jsonschema import Draft202012Validator

    schema = load_default("schemas", _SCHEMA_NAME)
    Draft202012Validator(schema).validate(mapping)


def _pattern_is_safe(pattern: str) -> bool:
    if pattern.startswith("/") or pattern.startswith("~"):
        return False
    return ".." not in pattern.split("/")


def resolve_within_repo(
    repo_root: Path,
    rel: str,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> Path | None:
    """Resolve a single repo-relative path with full fail-closed confinement.

    Returns the path only if it is relative (no absolute / ``~`` / ``..``), not a
    symlink, resolves under ``repo_root``, exists as a file, and is within
    ``max_bytes``; otherwise ``None``. Shared by ingest (glob results) and render
    (provenance ``src`` re-verify) so the security boundary is identical on both
    sides — a source that becomes a symlink or escapes the repo after ingest is
    rejected at render time too.
    """
    if not rel or rel.startswith("/") or rel.startswith("~"):
        return None
    if ".." in rel.split("/"):
        return None
    repo_real = repo_root.resolve()
    p = repo_root / rel
    if p.is_symlink() or not p.is_file():
        return None
    try:
        real = p.resolve()
        real.relative_to(repo_real)
    except (ValueError, OSError):
        return None
    try:
        if real.stat().st_size > max_bytes:
            return None
    except OSError:
        return None
    return p


def resolve_sources(
    repo_root: Path,
    pattern: str,
    *,
    max_files: int = DEFAULT_MAX_FILES,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> list[Path]:
    """Return repo-confined, existing, size-bounded files matching ``pattern``.

    Rejects absolute / ``~`` / ``..`` patterns outright, then applies
    :func:`resolve_within_repo` per match (symlink / escape / oversize skipped),
    caps at ``max_files``, deterministic sort.
    """
    if not _pattern_is_safe(pattern):
        return []
    out: list[Path] = []
    for p in sorted(repo_root.glob(pattern)):
        try:
            rel = str(p.relative_to(repo_root))
        except ValueError:
            continue
        resolved = resolve_within_repo(repo_root, rel, max_bytes=max_bytes)
        if resolved is not None:
            out.append(resolved)
            if len(out) >= max_files:
                break
    return out
