"""Read-only coordination status snapshot for operator visibility.

WP-7.2 scope is intentionally read-only: this module reports the live claim
SSOT as seen under ``claims.lock`` without adding new write semantics or
executor enforcement. The goal is to answer "who currently owns what, and is it
active / in grace / takeover-ready?" using a deterministic snapshot surface.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ao_kernel._internal.shared.lock import file_lock
from ao_kernel.config import load_default
from ao_kernel.coordination.policy import load_coordination_policy
from ao_kernel.coordination.registry import (
    ClaimRegistry,
    _claims_dir,
    _claims_lock_path,
    _parse_iso,
)


def _project_root(workspace_root: Path | str) -> Path:
    resolved = Path(workspace_root).resolve()
    if resolved.name == ".ao":
        return resolved.parent
    return resolved


def _describe_resource(resource_id: str) -> tuple[str, str]:
    if resource_id.startswith("write-area."):
        rest = resource_id.removeprefix("write-area.")
        slug, _, _digest = rest.rpartition(".")
        label = slug or rest or resource_id
        return ("path-area", label)
    return ("generic", resource_id)


def _claim_state(
    heartbeat_at: str,
    *,
    expiry_seconds: int,
    takeover_grace_period_seconds: int,
    now: datetime,
) -> tuple[str, str, str]:
    effective_expires = _parse_iso(heartbeat_at) + timedelta(
        seconds=expiry_seconds,
    )
    grace_deadline = effective_expires + timedelta(
        seconds=takeover_grace_period_seconds,
    )
    if now <= effective_expires:
        state = "ACTIVE"
    elif now <= grace_deadline:
        state = "GRACE"
    else:
        state = "TAKEOVER_READY"
    return (
        state,
        effective_expires.isoformat(),
        grace_deadline.isoformat(),
    )


def build_coordination_status(workspace_root: Path | str) -> dict[str, Any]:
    """Build a machine-readable coordination snapshot.

    The snapshot is derived from the claim SSOT under ``claims.lock``. Dormant
    coordination returns a successful IDLE payload rather than raising: status
    visibility is allowed to say "nothing is active" without forcing an opt-in.
    """
    project_root = _project_root(workspace_root)
    generated_at = datetime.now(timezone.utc).isoformat()
    policy = load_coordination_policy(project_root)

    if not policy.enabled:
        return {
            "version": "v1",
            "generated_at": generated_at,
            "workspace_root": str(project_root),
            "coordination_enabled": False,
            "claims": [],
            "summary": {
                "coordination_enabled": False,
                "total_active": 0,
                "total_reported": 0,
                "by_agent": {},
                "by_claim_state": {
                    "ACTIVE": 0,
                    "GRACE": 0,
                    "TAKEOVER_READY": 0,
                },
                "conflicts": [],
            },
            "status": "IDLE",
        }

    registry = ClaimRegistry(project_root)
    _claims_dir(project_root).mkdir(parents=True, exist_ok=True)

    claims: list[dict[str, Any]] = []
    by_agent: dict[str, int] = {}
    by_claim_state = {
        "ACTIVE": 0,
        "GRACE": 0,
        "TAKEOVER_READY": 0,
    }

    with file_lock(_claims_lock_path(project_root)):
        registry._ensure_index_consistent()
        index = registry._load_index()
        now = datetime.now(timezone.utc)
        for agent_id, resource_ids in sorted(index.agents.items()):
            for resource_id in resource_ids:
                claim = registry._load_claim_if_exists(resource_id)
                if claim is None:
                    continue
                resource_kind, resource_label = _describe_resource(resource_id)
                claim_state, effective_expires_at, grace_deadline_at = _claim_state(
                    claim.heartbeat_at,
                    expiry_seconds=policy.expiry_seconds,
                    takeover_grace_period_seconds=policy.takeover_grace_period_seconds,
                    now=now,
                )
                claims.append(
                    {
                        "work_item_id": resource_id,
                        "claim_id": claim.claim_id,
                        "owner_tag": claim.owner_agent_id,
                        "agent_tag": claim.owner_agent_id,
                        "acquired_at": claim.acquired_at,
                        "ttl_seconds": policy.expiry_seconds,
                        "expires_at": effective_expires_at,
                        "heartbeat_at": claim.heartbeat_at,
                        "grace_deadline_at": grace_deadline_at,
                        "fencing_token": claim.fencing_token,
                        "resource_kind": resource_kind,
                        "resource_label": resource_label,
                        "claim_state": claim_state,
                    }
                )
                by_agent[agent_id] = by_agent.get(agent_id, 0) + 1
                by_claim_state[claim_state] += 1

    claims.sort(
        key=lambda item: (
            item["owner_tag"],
            item["work_item_id"],
            item["claim_id"],
        )
    )
    total_active = by_claim_state["ACTIVE"] + by_claim_state["GRACE"]

    return {
        "version": "v1",
        "generated_at": generated_at,
        "workspace_root": str(project_root),
        "coordination_enabled": True,
        "claims": claims,
        "summary": {
            "coordination_enabled": True,
            "total_active": total_active,
            "total_reported": len(claims),
            "by_agent": dict(sorted(by_agent.items())),
            "by_claim_state": by_claim_state,
            "conflicts": [],
        },
        "status": "IDLE" if not claims else "OK",
    }


def render_coordination_status(snapshot: dict[str, Any]) -> str:
    """Render a human-readable coordination snapshot."""
    summary = snapshot["summary"]
    lines = [
        "== coordination status ==",
        f"Workspace: {snapshot['workspace_root']}",
        f"Generated: {snapshot['generated_at']}",
        f"Coordination enabled: {'yes' if snapshot.get('coordination_enabled') else 'no'}",
        (
            "Claims: "
            f"reported={summary.get('total_reported', 0)} "
            f"active={summary.get('total_active', 0)}"
        ),
        (
            "Claim states: "
            f"ACTIVE={summary['by_claim_state']['ACTIVE']} "
            f"GRACE={summary['by_claim_state']['GRACE']} "
            f"TAKEOVER_READY={summary['by_claim_state']['TAKEOVER_READY']}"
        ),
        f"Status: {snapshot['status']}",
        "",
        "Claims:",
    ]

    claims = snapshot.get("claims", [])
    if not claims:
        if snapshot.get("coordination_enabled"):
            lines.append("  - none")
        else:
            lines.append("  - coordination disabled (policy_coordination_claims.enabled=false)")
        return "\n".join(lines)

    for claim in claims:
        lines.append(
            "  - "
            f"{claim['work_item_id']} "
            f"[{claim.get('resource_kind', 'generic')}:{claim.get('resource_label', claim['work_item_id'])}] "
            f"owner={claim['owner_tag']} "
            f"state={claim.get('claim_state', 'ACTIVE')} "
            f"fencing={claim.get('fencing_token', '?')}"
        )
        lines.append(
            "    "
            f"claim_id={claim['claim_id']} "
            f"acquired_at={claim.get('acquired_at', '')} "
            f"heartbeat_at={claim.get('heartbeat_at', '')} "
            f"expires_at={claim.get('expires_at', '')} "
            f"grace_deadline_at={claim.get('grace_deadline_at', '')}"
        )

    return "\n".join(lines)


def coordination_status_schema() -> dict[str, Any]:
    """Load the bundled status schema for tests and callers."""
    return load_default("schemas", "agent-handoff-status.schema.v1.json")


__all__ = [
    "build_coordination_status",
    "render_coordination_status",
    "coordination_status_schema",
]
