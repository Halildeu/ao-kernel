"""Canonical shared utilities (SSOT).

Agent'lar yeni dosya yazarken bu modülden import etmelidir.
Bu dosyadaki fonksiyonları başka dosyalarda yeniden tanımlamak YASAKTIR.

Usage:
    from ao_kernel._internal.shared.utils import load_json, write_json_atomic, now_iso8601
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── JSON I/O ──────────────────────────────────────────────────────────


def load_json(path: Path) -> Any:
    """Read and parse a JSON file. Raises on missing file or invalid JSON."""
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_or_default(path: Path, default: Any = None) -> Any:
    """Read and parse a JSON file, returning *default* on any error."""
    if not path.exists():
        return default
    try:
        return load_json(path)
    except Exception:
        return default


def write_json_atomic(path: Path, data: Any, *, indent: int = 2) -> None:
    """Atomically write *data* as pretty-printed JSON to *path*."""
    content = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=indent) + "\n"
    write_text_atomic(path, content)


# ── Atomic File I/O ───────────────────────────────────────────────────


def write_text_atomic(path: Path, content: str) -> None:
    """Write *content* to *path* atomically via tmp-file + fsync + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


def write_bytes_atomic(path: Path, data: bytes) -> None:
    """Write *data* bytes to *path* atomically via tmp-file + fsync + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


# ── Time ──────────────────────────────────────────────────────────────


def now_iso8601() -> str:
    """Return the current UTC time as an ISO-8601 string ending in 'Z'."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso8601(ts: str) -> datetime | None:
    """Parse an ISO-8601 timestamp string. Returns None on failure."""
    if not isinstance(ts, str) or not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except Exception:
        return None


# ── Hashing ───────────────────────────────────────────────────────────


def sha256_text(text: str) -> str:
    """Return the hex SHA-256 digest of a UTF-8 encoded string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    """Return the hex SHA-256 digest of a file's contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_short(text: str, *, length: int = 16) -> str:
    """Return a truncated SHA-256 digest (default 16 hex chars)."""
    return sha256_text(text)[:length]


# ── Environment ───────────────────────────────────────────────────────


def env_true(key: str) -> bool:
    """Return True if the environment variable *key* is truthy (1/true/yes)."""
    v = os.environ.get(key)
    if not isinstance(v, str):
        return False
    return v.strip().lower() in {"1", "true", "yes"}


def env_str(key: str, default: str = "") -> str:
    """Return the environment variable *key* stripped, or *default*."""
    v = os.environ.get(key)
    if not isinstance(v, str):
        return default
    return v.strip() or default


# ── Policy Loading ─────────────────────────────────────────────────────


def load_policy_validated(policy_path: Path, schema_path: Path) -> Any:
    """Load and schema-validate a policy file.

    Raises ValueError on schema violation so callers fail-closed.
    Returns the parsed policy dict on success.
    """
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:
        raise RuntimeError("jsonschema is required for load_policy_validated()") from exc

    schema = load_json(schema_path)
    instance = load_json(policy_path)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: e.json_path)
    if errors:
        msgs = "; ".join(f"{e.json_path}: {e.message}" for e in errors[:3])
        raise ValueError(
            f"Policy {policy_path.name} failed schema validation: {msgs}"
        )
    return instance
