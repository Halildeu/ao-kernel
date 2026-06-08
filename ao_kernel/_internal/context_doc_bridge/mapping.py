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


def resolve_sources(
    repo_root: Path,
    pattern: str,
    *,
    max_files: int = DEFAULT_MAX_FILES,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> list[Path]:
    """Return repo-confined, existing, size-bounded files matching ``pattern``.

    Fail-closed confinement:
        * reject absolute / ``~`` / ``..`` patterns outright,
        * skip symlinks (even if the target is in-repo),
        * skip any match whose resolved real path escapes ``repo_root``,
        * skip files over ``max_bytes``,
        * cap at ``max_files``, deterministic sort.
    """
    if not _pattern_is_safe(pattern):
        return []
    repo_real = repo_root.resolve()
    out: list[Path] = []
    for p in sorted(repo_root.glob(pattern)):
        if p.is_symlink() or not p.is_file():
            continue
        try:
            real = p.resolve()
            real.relative_to(repo_real)
        except (ValueError, OSError):
            continue
        try:
            if real.stat().st_size > max_bytes:
                continue
        except OSError:
            continue
        out.append(p)
        if len(out) >= max_files:
            break
    return out
