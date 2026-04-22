"""CLI handlers for ``ao-kernel coordination`` subcommands."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from ao_kernel.coordination.errors import ClaimCorruptedError
from ao_kernel.coordination.status import (
    build_coordination_status,
    render_coordination_status,
)


def _resolve_workspace(args: Any) -> Path:
    ws = getattr(args, "workspace_root", None)
    if ws:
        resolved = Path(ws).resolve()
        if resolved.name == ".ao":
            return resolved.parent
        return resolved

    from ao_kernel.config import workspace_root

    resolved = workspace_root()
    if resolved is None:
        print("error: no .ao/ workspace found", file=sys.stderr)
        raise SystemExit(1)
    if resolved.name == ".ao":
        return resolved.parent
    return resolved


def _emit_output(payload: str, args: Any) -> None:
    output_path = getattr(args, "output", None)
    if output_path:
        from ao_kernel._internal.shared.utils import write_text_atomic

        write_text_atomic(Path(output_path), payload)
        return
    sys.stdout.write(payload)
    if not payload.endswith("\n"):
        sys.stdout.write("\n")


def cmd_coordination_status(args: Any) -> int:
    """Handle ``ao-kernel coordination status``."""
    workspace = _resolve_workspace(args)

    try:
        snapshot = build_coordination_status(workspace)
    except ClaimCorruptedError as exc:
        print(f"error: corrupt coordination state — {exc}", file=sys.stderr)
        return 2

    if getattr(args, "format", "text") == "json":
        payload = json.dumps(snapshot, indent=2, sort_keys=True)
    else:
        payload = render_coordination_status(snapshot)

    try:
        _emit_output(payload, args)
    except (OSError, PermissionError) as exc:
        print(f"error: output write failed — {exc}", file=sys.stderr)
        return 1
    return 0


__all__ = ["cmd_coordination_status"]
