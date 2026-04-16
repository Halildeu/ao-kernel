"""On-demand SHA-256 manifest generator + verifier (PR-A5).

Scope (CNS-025 B1+B4 absorb):
  events.jsonl, adapter-*.jsonl, artifacts/**/*.json, patches/*.revdiff
  Excludes: manifest.json, *.lock, *.tmp

Canonical manifest shape:
  {"version":"1","run_id":"...","generated_at":"...","files":[{"path":"...","sha256":"...","bytes":N}]}
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


_INCLUDE_GLOBS = [
    "events.jsonl",
    "adapter-*.jsonl",
    "artifacts/**/*.json",
    "patches/*.revdiff",
]

_EXCLUDE_NAMES = {"manifest.json"}
_EXCLUDE_SUFFIXES = {".lock", ".tmp"}


@dataclass(frozen=True)
class FileEntry:
    path: str  # run-relative
    sha256: str
    bytes: int


@dataclass(frozen=True)
class ManifestResult:
    run_id: str
    generated_at: str
    files: tuple[FileEntry, ...]
    manifest_path: Path


@dataclass(frozen=True)
class VerifyResult:
    run_id: str
    all_match: bool
    manifest_outdated: bool
    mismatches: tuple[str, ...]
    missing: tuple[str, ...]
    extra_in_scope: tuple[str, ...]


def generate_manifest(workspace_root: Path, run_id: str) -> ManifestResult:
    """Scan the run evidence directory and write manifest.json.

    I4-B2 fix: acquires ``events.jsonl.lock`` during scan + write to
    prevent hash race with concurrent ``EvidenceEmitter.emit_event``.
    """
    from ao_kernel._internal.shared.lock import file_lock

    run_dir = workspace_root / ".ao" / "evidence" / "workflows" / run_id
    if not run_dir.is_dir():
        raise FileNotFoundError(f"run dir not found: {run_dir}")

    lock_path = run_dir / "events.jsonl.lock"
    with file_lock(lock_path):
        entries = _scan_files(run_dir)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    manifest = {
        "version": "1",
        "run_id": run_id,
        "generated_at": now,
        "files": [
            {"path": e.path, "sha256": e.sha256, "bytes": e.bytes}
            for e in entries
        ],
    }
    manifest_path = run_dir / "manifest.json"
    _atomic_write_json(manifest_path, manifest)

    return ManifestResult(
        run_id=run_id,
        generated_at=now,
        files=entries,
        manifest_path=manifest_path,
    )


def verify_manifest(
    workspace_root: Path,
    run_id: str,
    *,
    generate_if_missing: bool = False,
) -> VerifyResult:
    """Recompute hashes and compare against existing manifest.

    Exit code semantics (caller maps):
      0 = all_match=True, manifest_outdated=False
      1 = mismatch or missing listed file
      2 = manifest_outdated (new in-scope file not in manifest)
      3 = manifest.json itself missing (unless generate_if_missing)
    """
    run_dir = workspace_root / ".ao" / "evidence" / "workflows" / run_id
    manifest_path = run_dir / "manifest.json"

    if not manifest_path.exists():
        if generate_if_missing:
            generate_manifest(workspace_root, run_id)
        else:
            return VerifyResult(
                run_id=run_id,
                all_match=False,
                manifest_outdated=False,
                mismatches=(),
                missing=("manifest.json",),
                extra_in_scope=(),
            )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    listed: dict[str, dict[str, object]] = {
        f["path"]: f for f in manifest.get("files", [])
    }

    mismatches: list[str] = []
    missing: list[str] = []

    for rel_path, expected in listed.items():
        full = run_dir / rel_path
        if not full.exists():
            missing.append(rel_path)
            continue
        actual_hash = _sha256(full)
        if actual_hash != expected.get("sha256"):
            mismatches.append(rel_path)

    # Outdated detection: scan for in-scope files not in manifest
    current = _scan_files(run_dir)
    current_paths = {e.path for e in current}
    listed_paths = set(listed.keys())
    extra = sorted(current_paths - listed_paths)

    return VerifyResult(
        run_id=run_id,
        all_match=len(mismatches) == 0 and len(missing) == 0 and len(extra) == 0,
        manifest_outdated=len(extra) > 0,
        mismatches=tuple(mismatches),
        missing=tuple(missing),
        extra_in_scope=tuple(extra),
    )


def _scan_files(run_dir: Path) -> tuple[FileEntry, ...]:
    """Collect in-scope files under run_dir, hashing each."""
    entries: list[FileEntry] = []
    for pattern in _INCLUDE_GLOBS:
        for match in sorted(run_dir.glob(pattern)):
            if not match.is_file():
                continue
            if match.name in _EXCLUDE_NAMES:
                continue
            if match.suffix in _EXCLUDE_SUFFIXES:
                continue
            rel = str(match.relative_to(run_dir))
            h = _sha256(match)
            entries.append(FileEntry(path=rel, sha256=h, bytes=match.stat().st_size))
    # Deduplicate (glob patterns may overlap)
    seen: dict[str, FileEntry] = {}
    for e in entries:
        seen.setdefault(e.path, e)
    return tuple(sorted(seen.values(), key=lambda e: e.path))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _atomic_write_json(path: Path, data: Mapping[str, object]) -> None:
    body = json.dumps(
        data, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")
    fd, tmp = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent,
    )
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(body)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
