"""ao-kernel init — create .ao/ workspace directory."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import ao_kernel


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


def run(workspace_root_override: str | None = None) -> int:
    """Create .ao/ workspace. Idempotent — safe to run multiple times."""
    if workspace_root_override:
        target = Path(workspace_root_override).resolve()
    else:
        target = Path.cwd() / ".ao"

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
