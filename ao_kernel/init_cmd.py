"""ao-kernel init — create .ao/ workspace directory."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import ao_kernel
from ao_kernel.config import resolve_workspace_dir


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    """Atomic write: tmp + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def _resolve_init_target(workspace_root_override: str | None) -> Path:
    """Normalize init writes to the same workspace shape the read side accepts.

    Supported override shapes:
    - project root: ``<root>/.ao`` is created/used
    - workspace dir: existing ``workspace.json`` directory is used as-is
    - explicit ``.ao`` path: used as-is even before first init
    """
    if not workspace_root_override:
        return Path.cwd() / ".ao"

    override = Path(workspace_root_override).resolve()
    resolved = resolve_workspace_dir(override)
    if resolved != override:
        return resolved
    if override.name == ".ao":
        return override
    if (override / "workspace.json").is_file():
        return override
    return override / ".ao"


def run(workspace_root_override: str | None = None) -> int:
    """Create .ao/ workspace. Idempotent — safe to run multiple times."""
    target = _resolve_init_target(workspace_root_override)

    if target.is_dir():
        ws_json = target / "workspace.json"
        if ws_json.is_file():
            from ao_kernel.i18n import msg
            print(msg("workspace_already_exists", path=str(target)))
            return 0

    subdirs = ["policies", "schemas", "registry", "extensions"]
    for d in subdirs:
        (target / d).mkdir(parents=True, exist_ok=True)

    ws_data = {
        "version": ao_kernel.__version__,
        "created_at": _now_iso(),
        "kind": "ao-workspace",
    }

    ws_json = target / "workspace.json"
    if not ws_json.is_file():
        _write_json_atomic(ws_json, ws_data)

    from ao_kernel.i18n import msg
    print(msg("workspace_created", path=str(target)))
    return 0
