"""Minimal .env loader for PRJ-KERNEL-API (stdlib-only, deterministic)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Iterable, Tuple


def _find_repo_root(start: Path) -> Path | None:
    for p in [start] + list(start.parents):
        if (p / ".git").exists() and (p / "AGENTS.md").exists():
            return p
    return None


def _parse_env_file(path: Path, *, source_label: str) -> Tuple[Dict[str, str], list[str]]:
    data: Dict[str, str] = {}
    errors: list[str] = []
    if not path.exists():
        return data, errors
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].lstrip()
        if "=" not in stripped:
            errors.append(f"{source_label}_LINE_{idx}_INVALID")
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            errors.append(f"{source_label}_LINE_{idx}_INVALID")
            continue
        if value.startswith(("\"", "'")) and value.endswith(("\"", "'")) and len(value) >= 2:
            value = value[1:-1]
        data[key] = value
    return data, errors


def _load_env_sources(workspace_root: str, *, repo_root: Path | None) -> Tuple[Dict[str, str], Dict[str, str], list[str]]:
    ws_env = Path(workspace_root) / ".env"
    ws_data, ws_errors = _parse_env_file(ws_env, source_label="WORKSPACE_ENV")
    repo_data: Dict[str, str] = {}
    repo_errors: list[str] = []
    if repo_root is not None:
        repo_env = repo_root / ".env"
        repo_data, repo_errors = _parse_env_file(repo_env, source_label="REPO_ENV")
    return ws_data, repo_data, ws_errors + repo_errors


def load_env_presence(
    workspace_root: str,
    expected_keys: Iterable[str] | None = None,
    *,
    repo_root: Path | None = None,
    env_mode: str = "dotenv",
) -> Dict[str, object]:
    if env_mode == "process":
        proc_keys = sorted(expected_keys) if expected_keys else []
        proc_present: set[str] = {k for k in proc_keys if os.environ.get(k)}
        proc_missing = [k for k in proc_keys if k not in proc_present]
        return {
            "present_keys": proc_present,
            "missing_expected_keys": proc_missing,
            "source_used": "process_env" if proc_present else "none",
            "parse_errors": [],
        }

    repo_root = repo_root or _find_repo_root(Path(__file__).resolve())
    ws_data, repo_data, parse_errors = _load_env_sources(workspace_root, repo_root=repo_root)
    keys = sorted(expected_keys) if expected_keys else sorted(set(ws_data) | set(repo_data))

    present_keys: set[str] = set()
    for key in keys:
        if ws_data.get(key):
            present_keys.add(key)
        elif repo_data.get(key):
            present_keys.add(key)

    missing_expected = [k for k in keys if k not in present_keys]
    source_used = "none"
    if any(ws_data.get(k) for k in present_keys):
        source_used = "workspace_env"
    elif any(repo_data.get(k) for k in present_keys):
        source_used = "repo_env"

    return {
        "present_keys": present_keys,
        "missing_expected_keys": missing_expected,
        "source_used": source_used,
        "parse_errors": parse_errors,
    }


def resolve_env_presence(
    key_name: str,
    workspace_root: str,
    *,
    repo_root: Path | None = None,
    env_mode: str = "dotenv",
) -> Tuple[bool, str]:
    if env_mode == "process":
        value = os.environ.get(key_name)
        return (value is not None and value != ""), "process_env" if value else "none"

    repo_root = repo_root or _find_repo_root(Path(__file__).resolve())
    ws_data, repo_data, _errors = _load_env_sources(workspace_root, repo_root=repo_root)
    if ws_data.get(key_name):
        return True, "workspace_env"
    if repo_data.get(key_name):
        return True, "repo_env"
    return False, "none"


def resolve_env_value(
    key_name: str,
    workspace_root: str,
    *,
    repo_root: Path | None = None,
    env_mode: str = "dotenv",
) -> Tuple[bool, str | None]:
    if env_mode == "process":
        value = os.environ.get(key_name)
        return (value is not None and value != ""), value

    repo_root = repo_root or _find_repo_root(Path(__file__).resolve())
    ws_data, repo_data, _errors = _load_env_sources(workspace_root, repo_root=repo_root)
    if ws_data.get(key_name):
        return True, ws_data.get(key_name)
    if repo_data.get(key_name):
        return True, repo_data.get(key_name)
    return False, None
