"""Sliding window compaction engine for session decisions.

Inspired by JetBrains NeurIPS 2025 research: observation masking + summary hybrid.
Keeps last N decisions in full detail, archives older ones.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ao_kernel._internal.shared.utils import write_json_atomic


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_compaction_policy(workspace_root: Path) -> dict[str, Any]:
    """Load compaction policy with defaults."""
    defaults = {
        "enabled": True,
        "strategy": "sliding_window",
        "trigger": "decision_count",
        "trigger_threshold": 30,
        "keep_recent_count": 10,
        "archive_older": True,
        "max_archive_files": 20,
    }
    policy_path = workspace_root / "policies" / "policy_compaction.v1.json"
    if not policy_path.exists():
        # Check repo root
        repo_root = Path(__file__).resolve().parents[2]
        policy_path = repo_root / "policies" / "policy_compaction.v1.json"
    if policy_path.exists():
        try:
            obj = json.loads(policy_path.read_text(encoding="utf-8"))
            if isinstance(obj, dict):
                for k, v in defaults.items():
                    if k not in obj:
                        obj[k] = v
                return obj
        except Exception as exc:
            import logging
            logging.getLogger("ao_kernel").warning("compaction policy load failed, using defaults: %s", exc)
    return defaults


def should_compact(context: dict[str, Any], *, policy: dict[str, Any] | None = None) -> bool:
    """Check if session decisions should be compacted based on policy thresholds."""
    if policy is None:
        policy = {}
    if not policy.get("enabled", True):
        return False

    decisions = context.get("ephemeral_decisions", [])
    if not isinstance(decisions, list):
        return False

    trigger = str(policy.get("trigger", "decision_count"))
    threshold = int(policy.get("trigger_threshold", 30))

    if trigger == "decision_count":
        return len(decisions) >= threshold

    return False


def compact_session_decisions(
    context: dict[str, Any],
    *,
    policy: dict[str, Any] | None = None,
    workspace_root: Path | None = None,
    session_id: str = "default",
) -> dict[str, Any]:
    """Apply sliding window compaction to session decisions.

    - Keep last N decisions in full detail
    - Archive older decisions to .cache/sessions/{id}/compaction_archive/
    - Update compaction metadata in context

    Returns: {compacted: bool, kept: int, archived: int, archive_path: str}
    """
    if policy is None:
        policy = _load_compaction_policy(workspace_root) if workspace_root else {}

    decisions = context.get("ephemeral_decisions", [])
    if not isinstance(decisions, list):
        return {"compacted": False, "kept": 0, "archived": 0, "reason": "no_decisions"}

    keep_count = int(policy.get("keep_recent_count", 10))
    archive_enabled = bool(policy.get("archive_older", True))

    if len(decisions) <= keep_count:
        return {"compacted": False, "kept": len(decisions), "archived": 0, "reason": "below_threshold"}

    # Sort by created_at (newest last) to determine recency
    sorted_decisions = sorted(
        decisions,
        key=lambda d: str(d.get("created_at") or "") if isinstance(d, dict) else "",
    )

    to_archive = sorted_decisions[:-keep_count] if keep_count > 0 else sorted_decisions
    to_keep = sorted_decisions[-keep_count:] if keep_count > 0 else []

    archive_path = ""
    if archive_enabled and workspace_root and to_archive:
        archive_dir = workspace_root / ".cache" / "sessions" / session_id / "compaction_archive"
        archive_dir.mkdir(parents=True, exist_ok=True)

        # Limit archive files
        max_files = int(policy.get("max_archive_files", 20))
        existing = sorted(archive_dir.glob("*.v1.json"))
        if len(existing) >= max_files:
            # Remove oldest
            for old in existing[: len(existing) - max_files + 1]:
                old.unlink(missing_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        archive_file = archive_dir / f"compact_{timestamp}.v1.json"
        archive_data = {
            "version": "v1",
            "compacted_at": _now_iso(),
            "session_id": session_id,
            "decisions_archived": len(to_archive),
            "decisions": to_archive,
        }
        write_json_atomic(archive_file, archive_data)
        archive_path = str(archive_file)

    # Update context with kept decisions only
    to_keep.sort(key=lambda x: str(x.get("key") or ""))
    context["ephemeral_decisions"] = to_keep
    context["updated_at"] = _now_iso()

    # Update compaction metadata
    from ao_kernel._internal.session.context_store import compute_context_sha256

    if "compaction" not in context or not isinstance(context.get("compaction"), dict):
        context["compaction"] = {}
    context["compaction"]["status"] = "completed"
    context["compaction"]["last_compacted_at"] = _now_iso()
    context["compaction"]["trigger"] = "decision_count"
    context["compaction"]["source"] = "sliding_window"

    if "hashes" not in context or not isinstance(context.get("hashes"), dict):
        context["hashes"] = {}
    context["hashes"]["session_context_sha256"] = compute_context_sha256(context)

    return {
        "compacted": True,
        "kept": len(to_keep),
        "archived": len(to_archive),
        "archive_path": archive_path,
    }
