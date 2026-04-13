from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from ao_kernel._internal.shared.utils import write_json_atomic

BOOTSTRAP_FILES: list[str] = [
    ".cache/ws_customer_default/.cache/reports/system_status.v1.json",
    ".cache/ws_customer_default/.cache/reports/portfolio_status.v1.json",
    ".cache/ws_customer_default/.cache/roadmap_state.v1.json",
    "AGENTS.md",
    "docs/OPERATIONS/CODEX-UX.md",
    "docs/LAYER-MODEL-LOCK.v1.md",
    "roadmaps/SSOT/roadmap.v1.json",
]

_OUTPUT_REL = ".cache/index/agent_context_version.v1.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _file_hash(path: Path) -> tuple[str, bool, int]:
    """Return (sha256_hex, exists, size_bytes)."""
    if not path.exists():
        return ("", False, 0)
    try:
        data = path.read_bytes()
        return (sha256(data).hexdigest(), True, len(data))
    except Exception:
        return ("", False, 0)


def _file_modified_at(path: Path) -> str:
    try:
        mtime = path.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except Exception:
        return ""


def compute_agent_context_version(
    *,
    workspace_root: Path,
    agent_tag: str = "",
    extra_files: list[str] | None = None,
) -> dict[str, Any]:
    """Compute SSOT file hashes and return a version record."""
    workspace_root = workspace_root.resolve()
    tracked = list(BOOTSTRAP_FILES)
    if extra_files:
        tracked.extend(extra_files)

    files: list[dict[str, Any]] = []
    hash_parts: list[str] = []

    for rel in tracked:
        full = workspace_root / rel
        h, exists, size = _file_hash(full)
        entry: dict[str, Any] = {"path": rel, "sha256": h, "exists": exists}
        if exists:
            entry["size_bytes"] = size
            mod = _file_modified_at(full)
            if mod:
                entry["modified_at"] = mod
        files.append(entry)
        hash_parts.append(f"{rel}:{h}")

    aggregate = sha256("|".join(sorted(hash_parts)).encode("utf-8")).hexdigest()

    record: dict[str, Any] = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "files": files,
        "aggregate_sha256": aggregate,
        "stale_files": [],
        "status": "CURRENT",
    }
    if agent_tag:
        record["agent_tag"] = agent_tag
    return record


def verify_agent_context_version(
    *,
    workspace_root: Path,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare current SSOT hashes to a previous record.

    Returns a new version record with ``status`` set to ``CURRENT`` or
    ``STALE_CONTEXT`` and ``stale_files`` listing paths that changed.
    """
    workspace_root = workspace_root.resolve()
    if previous is None:
        previous = load_agent_context_version(workspace_root=workspace_root)

    current = compute_agent_context_version(workspace_root=workspace_root)

    if previous is None:
        return current

    prev_map: dict[str, str] = {}
    for f in previous.get("files") or []:
        if isinstance(f, dict):
            prev_map[str(f.get("path") or "")] = str(f.get("sha256") or "")

    stale: list[str] = []
    for f in current.get("files") or []:
        if not isinstance(f, dict):
            continue
        p = str(f.get("path") or "")
        cur_hash = str(f.get("sha256") or "")
        prev_hash = prev_map.get(p)
        if prev_hash is not None and prev_hash != cur_hash:
            stale.append(p)

    current["stale_files"] = stale
    current["status"] = "STALE_CONTEXT" if stale else "CURRENT"
    return current


def write_agent_context_version(*, workspace_root: Path, record: dict[str, Any]) -> str:
    """Persist the version record and return the relative output path."""
    workspace_root = workspace_root.resolve()
    out = workspace_root / _OUTPUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(out, record)
    return _OUTPUT_REL


def load_agent_context_version(*, workspace_root: Path) -> dict[str, Any] | None:
    """Load the previously persisted version record, or ``None``."""
    workspace_root = workspace_root.resolve()
    path = workspace_root / _OUTPUT_REL
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
