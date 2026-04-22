"""CLI handlers for ``ao-kernel coordination`` subcommands."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from ao_kernel.coordination import ClaimRegistry
from ao_kernel.coordination.claim import claim_to_dict
from ao_kernel.coordination.errors import (
    ClaimConflictError,
    ClaimConflictGraceError,
    ClaimCoordinationDisabledError,
    ClaimCorruptedError,
    ClaimNotFoundError,
)
from ao_kernel.coordination.status import (
    build_coordination_status,
    render_coordination_status,
)


def _resolve_workspace(args: Any) -> Path:
    ws = getattr(args, "workspace_root", None)
    if ws:
        explicit_root = Path(ws).resolve()
        if explicit_root.name == ".ao":
            return explicit_root.parent
        return explicit_root

    from ao_kernel.config import workspace_root

    discovered_root = workspace_root()
    if discovered_root is None:
        print("error: no .ao/ workspace found", file=sys.stderr)
        raise SystemExit(1)
    if discovered_root.name == ".ao":
        return discovered_root.parent
    return discovered_root


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


def _takeover_payload(claim: Any, workspace: Path) -> dict[str, Any]:
    payload = claim_to_dict(claim)
    payload["version"] = "v1"
    payload["workspace_root"] = str(workspace)
    payload["owner_tag"] = payload.pop("owner_agent_id")
    payload["status"] = "TAKEN_OVER"
    return payload


def _render_takeover(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "== coordination takeover ==",
            f"Workspace: {payload['workspace_root']}",
            f"Resource: {payload['resource_id']}",
            f"New owner: {payload['owner_tag']}",
            f"Claim id: {payload['claim_id']}",
            f"Fencing token: {payload['fencing_token']}",
            f"Acquired at: {payload['acquired_at']}",
            f"Heartbeat at: {payload['heartbeat_at']}",
            f"Status: {payload['status']}",
        ]
    )


def cmd_coordination_takeover(args: Any) -> int:
    """Handle ``ao-kernel coordination takeover``."""
    workspace = _resolve_workspace(args)
    registry = ClaimRegistry(workspace)

    try:
        claim = registry.takeover_claim(
            getattr(args, "resource_id"),
            getattr(args, "owner_tag"),
        )
    except ClaimCoordinationDisabledError:
        print(
            "error: coordination disabled — "
            "policy_coordination_claims.enabled=false",
            file=sys.stderr,
        )
        return 1
    except (ClaimConflictError, ClaimConflictGraceError, ClaimNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except ClaimCorruptedError as exc:
        print(f"error: corrupt coordination state — {exc}", file=sys.stderr)
        return 2

    payload_doc = _takeover_payload(claim, workspace)
    if getattr(args, "format", "text") == "json":
        payload = json.dumps(payload_doc, indent=2, sort_keys=True)
    else:
        payload = _render_takeover(payload_doc)

    try:
        _emit_output(payload, args)
    except (OSError, PermissionError) as exc:
        print(f"error: output write failed — {exc}", file=sys.stderr)
        return 1
    return 0


__all__ = ["cmd_coordination_status", "cmd_coordination_takeover"]
