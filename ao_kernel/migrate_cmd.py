"""ao-kernel migrate — workspace version migration.

Contract:
    - Always produces a plan/report
    - --dry-run: detect + plan + report only, no mutations
    - --backup: targeted backup of files that will change
    - Idempotent: safe to run multiple times
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import ao_kernel
from ao_kernel.config import load_workspace_json, workspace_root
from ao_kernel.errors import WorkspaceCorruptedError, WorkspaceNotFoundError


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _detect_legacy_workspace() -> Path | None:
    """Check if legacy .cache/ws_customer_default exists from CWD upward."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / ".cache" / "ws_customer_default"
        if candidate.is_dir():
            return candidate
    return None


def run(
    workspace_root_override: str | None = None,
    *,
    dry_run: bool = False,
    backup: bool = False,
) -> int:
    """Run workspace migration."""
    ws = workspace_root(override=workspace_root_override)
    if ws is None:
        print("Hata: Workspace bulunamadi. Once 'ao-kernel init' calistirin.")
        return 1

    try:
        ws_data = load_workspace_json(ws)
    except WorkspaceCorruptedError as e:
        print(f"Hata: {e}")
        return 1

    ws_version = ws_data.get("version", "0.0.0")
    pkg_version = ao_kernel.__version__
    legacy_ws = _detect_legacy_workspace()

    mutations: list[dict] = []
    action_items: list[str] = []

    if ws_version != pkg_version:
        mutations.append({
            "type": "version_update",
            "from": ws_version,
            "to": pkg_version,
            "file": str(ws / "workspace.json"),
        })

    if legacy_ws is not None and str(legacy_ws) != str(ws):
        action_items.append(
            f"Legacy workspace tespit edildi: {legacy_ws}. "
            ".ao/ workspace'e gecis onerilir."
        )

    report = {
        "timestamp": _now_iso(),
        "workspace_path": str(ws),
        "workspace_version": ws_version,
        "package_version": pkg_version,
        "status": "UP_TO_DATE" if not mutations else "MIGRATION_NEEDED",
        "dry_run": dry_run,
        "mutations": mutations,
        "backup_skipped": "no_mutations" if not mutations else None,
        "legacy_workspace_detected": legacy_ws is not None,
        "action_items": action_items,
    }

    if dry_run or not mutations:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    if backup and mutations:
        backup_dir = ws / ".backup" / _now_iso().replace(":", "-")
        backup_dir.mkdir(parents=True, exist_ok=True)
        for m in mutations:
            src = Path(m["file"])
            if src.is_file():
                dest = backup_dir / src.name
                dest.write_bytes(src.read_bytes())
        report["backup_path"] = str(backup_dir)

    for m in mutations:
        if m["type"] == "version_update":
            ws_data["version"] = pkg_version
            ws_data["migrated_at"] = _now_iso()
            ws_file = Path(m["file"])
            tmp = ws_file.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(ws_data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            tmp.replace(ws_file)

    report["status"] = "MIGRATED"
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0
