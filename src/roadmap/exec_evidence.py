from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_bytes(b: bytes) -> str:
    return sha256(b).hexdigest()


def _sha256_file(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _normalize_rel_path(rel: str) -> str:
    rel = str(rel).replace("\\", "/")
    if rel.startswith("./"):
        rel = rel[2:]
    return rel.lstrip("/")


def _snapshot_tree(root: Path, *, ignore_prefixes: list[str] | None = None) -> dict[str, str]:
    ignore_prefixes = ignore_prefixes or []
    cleaned_prefixes: list[str] = []
    for raw in ignore_prefixes:
        p = str(raw).strip().replace("\\", "/").strip("/")
        if p:
            cleaned_prefixes.append(p)

    def ignored(rel: str) -> bool:
        rel = _normalize_rel_path(rel)
        for pref in cleaned_prefixes:
            if rel == pref or rel.startswith(pref + "/"):
                return True
        return False

    snap: dict[str, str] = {}
    if not root.exists():
        return snap

    for p in sorted(root.rglob("*"), key=lambda x: x.as_posix()):
        if not p.is_file():
            continue
        try:
            rel = p.relative_to(root).as_posix()
        except Exception:
            continue
        if ignored(rel):
            continue
        try:
            snap[rel] = _sha256_file(p)
        except Exception:
            snap[rel] = "UNREADABLE"
    return snap


def _git_info(core_root: Path) -> dict[str, Any]:
    try:
        proc_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=core_root,
            text=True,
            capture_output=True,
        )
        commit = (proc_commit.stdout or "").strip() if proc_commit.returncode == 0 else "unknown"
    except FileNotFoundError:
        commit = "unknown"

    dirty = False
    try:
        proc_status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=core_root,
            text=True,
            capture_output=True,
        )
        if proc_status.returncode == 0 and (proc_status.stdout or "").strip():
            dirty = True
    except FileNotFoundError:
        dirty = False

    return {"commit": commit or "unknown", "dirty": bool(dirty)}


def _git_is_clean(core_root: Path) -> bool:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=core_root,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        return False
    if proc.returncode != 0:
        return False
    return not (proc.stdout or "").strip()


def _git_status_porcelain(core_root: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=core_root,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout or ""


def _prepare_readonly_baselines(
    *, core_root: Path, workspace_root: Path, dry_run: bool, dry_run_mode: str
) -> tuple[str | None, dict[str, str] | None]:
    baseline_git_status: str | None = None
    baseline_workspace_snapshot: dict[str, str] | None = None
    if dry_run and dry_run_mode == "readonly":
        baseline_git_status = _git_status_porcelain(core_root)
        if baseline_git_status is None:
            raise ValueError("READONLY_MODE_REQUIRES_GIT")
        if workspace_root != core_root:
            baseline_workspace_snapshot = _snapshot_tree(
                workspace_root,
                ignore_prefixes=[
                    ".cache",
                    "evidence",
                    "dlq",
                    "__pycache__",
                ],
            )
    return (baseline_git_status, baseline_workspace_snapshot)
