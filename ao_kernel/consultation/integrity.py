"""Consultation integrity manifest (v3.5 D2a).

SHA-256 manifest over snapshots + events + resolution record.
EXCLUDES ``archive-meta.json`` (archive-time drift tolerated) and the
manifest file itself.

Workflow `_internal/evidence/manifest.py` primitives reused via
``sha256_file`` + ``write_json_atomic``; glob/name is
consultation-specific (Codex iter-3 note).
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any, Iterator

from ao_kernel._internal.shared.utils import (
    sha256_file,
    write_json_atomic,
)


_MANIFEST_VERSION = "v1"
_MANIFEST_FILENAME = "integrity.manifest.v1.json"
_ARCHIVE_META_FILENAME = "archive-meta.json"


def _iso_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _iter_consultation_files(cns_dir: Path) -> "Iterator[Path]":
    """Yield snapshots + events + record. Excludes manifest + meta."""
    requests_dir = cns_dir / "requests"
    if requests_dir.is_dir():
        for p in sorted(requests_dir.iterdir()):
            if p.is_file():
                yield p
    responses_dir = cns_dir / "responses"
    if responses_dir.is_dir():
        for p in sorted(responses_dir.iterdir()):
            if p.is_file():
                yield p
    events = cns_dir / "events.jsonl"
    if events.is_file():
        yield events
    record = cns_dir / "resolution.record.v1.json"
    if record.is_file():
        yield record


def compute_consultation_manifest(cns_dir: Path) -> dict[str, Any]:
    """Compute manifest dict — entries keyed by workspace-relative
    path, value = SHA-256 hex digest."""
    entries: dict[str, str] = {}
    for file in _iter_consultation_files(cns_dir):
        rel = str(file.relative_to(cns_dir))
        entries[rel] = sha256_file(file)
    return {
        "version": _MANIFEST_VERSION,
        "generated_at": _iso_now(),
        "entries": entries,
    }


def write_consultation_manifest(cns_dir: Path) -> Path:
    """Compute + atomic write manifest. Returns manifest file path."""
    manifest = compute_consultation_manifest(cns_dir)
    path = cns_dir / _MANIFEST_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    write_json_atomic(path, manifest)
    return path


def verify_consultation_manifest(
    cns_dir: Path,
) -> tuple[bool, list[str]]:
    """Re-hash manifest entries + detect missing/extra files.

    Returns ``(ok, errors)`` — ok=True iff no mismatches, missing
    files, or extras.
    """
    manifest_path = cns_dir / _MANIFEST_FILENAME
    if not manifest_path.is_file():
        return False, [f"manifest missing: {manifest_path}"]

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, [f"manifest unreadable: {exc}"]

    stored = manifest.get("entries") or {}
    errors: list[str] = []

    for rel, expected in stored.items():
        file = cns_dir / rel
        if not file.is_file():
            errors.append(f"missing file: {rel}")
            continue
        actual = sha256_file(file)
        if actual != expected:
            errors.append(
                f"digest mismatch for {rel}: stored={expected} actual={actual}"
            )

    current: set[str] = set()
    for file in _iter_consultation_files(cns_dir):
        current.add(str(file.relative_to(cns_dir)))
    extras = current - set(stored.keys())
    for extra in sorted(extras):
        errors.append(f"extra file not in manifest: {extra}")

    return (not errors), errors


def write_archive_meta(
    cns_dir: Path,
    *,
    config_digest: str | None = None,
    archiver_version: str = "v1",
) -> Path:
    """Write archive-time metadata. Kept separate from
    resolution.record.v1.json so record stays source-stable (config
    changes can't churn the record digest)."""
    path = cns_dir / _ARCHIVE_META_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload: dict[str, Any] = {
        "version": "v1",
        "archived_at": _iso_now(),
        "archiver_version": archiver_version,
    }
    if config_digest is not None:
        payload["config_digest"] = config_digest
    write_json_atomic(path, payload)
    return path


__all__ = [
    "compute_consultation_manifest",
    "write_consultation_manifest",
    "verify_consultation_manifest",
    "write_archive_meta",
]
