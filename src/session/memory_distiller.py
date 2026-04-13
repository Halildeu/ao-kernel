"""Memory distillation: promote stable ephemeral decisions to long-term workspace facts.

Inspired by OpenAI Agents SDK context personalization pattern:
  Session decisions → Distillation → Consolidation → Long-term store

Criteria for promotion:
  - Key appeared in 2+ sessions (cross-session frequency)
  - Key has stable value (not changing every session)
  - Source is "agent" (automated decisions more reliable)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.session.context_store import SessionContextError, SessionPaths, load_context

from src.shared.utils import write_json_atomic

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=True)


def distill_decisions_from_sessions(
    *,
    workspace_root: Path,
    min_occurrences: int = 2,
    min_stability: int = 2,
) -> list[dict[str, Any]]:
    """Extract stable facts from all session decisions.

    Args:
        workspace_root: Workspace root path
        min_occurrences: Minimum sessions where key must appear
        min_stability: Minimum consecutive same-value updates to be "stable"

    Returns:
        List of distilled fact candidates.
    """
    sessions_dir = workspace_root / ".cache" / "sessions"
    if not sessions_dir.exists():
        return []

    # Collect all decisions across sessions
    key_data: dict[str, dict[str, Any]] = {}  # key → {values, sessions, latest_value, ...}

    for session_dir in sorted(sessions_dir.iterdir()):
        if not session_dir.is_dir():
            continue
        session_id = session_dir.name
        sp = SessionPaths(workspace_root=workspace_root, session_id=session_id)
        if not sp.context_path.exists():
            continue

        try:
            ctx = load_context(sp.context_path)
        except SessionContextError:
            continue

        decisions = ctx.get("ephemeral_decisions", [])
        if not isinstance(decisions, list):
            continue

        for d in decisions:
            if not isinstance(d, dict):
                continue
            key = str(d.get("key") or "").strip()
            if not key:
                continue

            val_json = _canonical_json(d.get("value"))
            created = str(d.get("created_at") or "")

            if key not in key_data:
                key_data[key] = {
                    "values": [],
                    "sessions": set(),
                    "latest_value": d.get("value"),
                    "latest_created": created,
                    "first_seen": created,
                    "source": str(d.get("source") or "agent"),
                }

            entry = key_data[key]
            entry["values"].append(val_json)
            entry["sessions"].add(session_id)
            if created > entry["latest_created"]:
                entry["latest_value"] = d.get("value")
                entry["latest_created"] = created

    # Filter: promote stable facts
    distilled: list[dict[str, Any]] = []
    for key, data in key_data.items():
        session_count = len(data["sessions"])
        if session_count < min_occurrences:
            continue

        # Check stability: how many of the last N values are the same?
        values = data["values"]
        if not values:
            continue
        latest_val = values[-1]
        stable_count = 0
        for v in reversed(values):
            if v == latest_val:
                stable_count += 1
            else:
                break

        if stable_count < min_stability:
            continue

        confidence = min(1.0, stable_count / max(len(values), 1) * (session_count / max(min_occurrences, 1)))

        distilled.append({
            "key": key,
            "value": data["latest_value"],
            "confidence": round(confidence, 4),
            "first_seen": data["first_seen"],
            "last_confirmed": data["latest_created"],
            "occurrences": len(values),
            "source_sessions": sorted(data["sessions"]),
        })

    return sorted(distilled, key=lambda x: str(x.get("key") or ""))


def consolidate_facts(
    *,
    workspace_root: Path,
    distilled: list[dict[str, Any]],
) -> dict[str, Any]:
    """Merge distilled facts with existing long-term store.

    Conflict resolution: latest timestamp wins.
    """
    facts_path = workspace_root / ".cache" / "index" / "workspace_facts.v1.json"
    existing_facts: list[dict[str, Any]] = []

    if facts_path.exists():
        try:
            data = json.loads(facts_path.read_text(encoding="utf-8"))
            existing_facts = data.get("facts", []) if isinstance(data, dict) else []
        except Exception:
            pass

    # Merge: existing + distilled, latest wins on same key
    merged: dict[str, dict[str, Any]] = {}
    for f in existing_facts:
        if isinstance(f, dict) and f.get("key"):
            merged[str(f["key"])] = f

    new_count = 0
    updated_count = 0
    for f in distilled:
        key = str(f.get("key") or "")
        if not key:
            continue
        if key in merged:
            existing = merged[key]
            if str(f.get("last_confirmed", "")) >= str(existing.get("last_confirmed", "")):
                # Update with newer data, merge source_sessions
                existing_sessions = set(existing.get("source_sessions", []))
                new_sessions = set(f.get("source_sessions", []))
                f["source_sessions"] = sorted(existing_sessions | new_sessions)
                f["occurrences"] = max(int(f.get("occurrences", 0)), int(existing.get("occurrences", 0)))
                f["first_seen"] = min(str(f.get("first_seen", "")), str(existing.get("first_seen", "")))
                merged[key] = f
                updated_count += 1
        else:
            merged[key] = f
            new_count += 1

    facts_list = sorted(merged.values(), key=lambda x: str(x.get("key") or ""))

    now = _now_iso()
    distillation_runs = 1
    if facts_path.exists():
        try:
            old = json.loads(facts_path.read_text(encoding="utf-8"))
            distillation_runs = int(old.get("distillation_runs", 0)) + 1
        except Exception:
            pass

    store = {
        "version": "v1",
        "generated_at": now,
        "workspace_root": str(workspace_root),
        "total_facts": len(facts_list),
        "distillation_runs": distillation_runs,
        "facts": facts_list,
    }

    facts_path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(facts_path, store)

    return {
        "status": "OK",
        "total_facts": len(facts_list),
        "new_facts": new_count,
        "updated_facts": updated_count,
        "distillation_runs": distillation_runs,
        "facts_path": str(facts_path),
    }


def run_distillation(
    *,
    workspace_root: Path,
    min_occurrences: int = 2,
    min_stability: int = 2,
) -> dict[str, Any]:
    """Full distillation pipeline: extract → consolidate → persist."""
    distilled = distill_decisions_from_sessions(
        workspace_root=workspace_root,
        min_occurrences=min_occurrences,
        min_stability=min_stability,
    )
    result = consolidate_facts(workspace_root=workspace_root, distilled=distilled)
    result["distilled_candidates"] = len(distilled)
    return result
