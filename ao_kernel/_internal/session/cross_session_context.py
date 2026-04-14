from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ao_kernel._internal.session.context_store import (
    SessionContextError,
    SessionPaths,
    is_expired,
    load_context,
    prune_expired_decisions,
    save_context_atomic,
)
from ao_kernel._internal.shared.utils import write_json_atomic


def _asdict(value: Any) -> dict[str, Any]:
    """Narrow an ``Any`` to ``dict[str, Any]``; returns ``{}`` otherwise."""
    return value if isinstance(value, dict) else {}


def _aslist(value: Any) -> list[Any]:
    """Narrow an ``Any`` to ``list[Any]``; returns ``[]`` otherwise."""
    return value if isinstance(value, list) else []


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso8601(ts: str) -> datetime | None:
    if not isinstance(ts, str) or not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def _rel_to_workspace(path: Path, workspace_root: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        return str(path)


def _decision_key(item: dict[str, Any]) -> tuple[str, float]:
    key = str(item.get("key") or "")
    created = _parse_iso8601(str(item.get("created_at") or ""))
    ts = created.timestamp() if isinstance(created, datetime) else 0.0
    return (key, ts)


def extract_decision_scope(key: str) -> tuple[str, str]:
    """Split ``scope.key_name`` into ``(scope, key_name)``.

    Returns ``("", key)`` when no scope prefix is present.
    """
    if "." in key:
        parts = key.split(".", 1)
        return (parts[0], parts[1])
    return ("", key)


def _is_session_expired(ctx: dict[str, Any], now_iso: str) -> bool:
    exp = _parse_iso8601(str(ctx.get("expires_at") or ""))
    now = _parse_iso8601(now_iso)
    if exp is None or now is None:
        return True
    return now > exp


def build_cross_session_context(*, workspace_root: Path, session_name_filter: str = "") -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    now_iso = _now_iso8601()
    sessions_root = workspace_root / ".cache" / "sessions"
    out_path = workspace_root / ".cache" / "index" / "session_cross_context.v1.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    loaded_sessions = 0
    scanned_sessions = 0
    skipped_sessions = 0
    decisions_total = 0
    decisions_by_session: dict[str, int] = {}
    decision_rows: list[dict[str, Any]] = []
    provider_rows: list[dict[str, Any]] = []
    compaction_rows: list[dict[str, Any]] = []

    if sessions_root.exists():
        for session_dir in sorted([p for p in sessions_root.iterdir() if p.is_dir()], key=lambda p: p.as_posix()):
            session_id = session_dir.name
            if session_name_filter and session_name_filter not in session_id:
                continue
            scanned_sessions += 1
            sp = SessionPaths(workspace_root=workspace_root, session_id=session_id)
            ctx_path = sp.context_path
            if not ctx_path.exists():
                skipped_sessions += 1
                continue
            try:
                ctx = load_context(ctx_path)
            except SessionContextError:
                skipped_sessions += 1
                continue

            if _is_session_expired(ctx, now_iso):
                skipped_sessions += 1
                continue

            before = json.dumps(ctx, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            prune_expired_decisions(ctx, now_iso)
            after = json.dumps(ctx, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            if before != after:
                try:
                    save_context_atomic(ctx_path, ctx)
                except SessionContextError as exc:
                    import logging
                    logging.getLogger("ao_kernel").warning("cross-session pruned context save failed: %s", exc)

            decisions = _aslist(ctx.get("ephemeral_decisions"))
            provider_state = _asdict(ctx.get("provider_state"))
            if isinstance(provider_state.get("provider"), str) and str(provider_state.get("provider")).strip():
                provider_rows.append(
                    {
                        "session_id": session_id,
                        "provider": str(provider_state.get("provider") or ""),
                        "conversation_id": str(provider_state.get("conversation_id") or ""),
                        "last_response_id": str(provider_state.get("last_response_id") or ""),
                        "wire_api": str(provider_state.get("wire_api") or ""),
                        "updated_at": str(provider_state.get("updated_at") or ""),
                        "summary_ref": str(provider_state.get("summary_ref") or ""),
                    }
                )
            compaction = _asdict(ctx.get("compaction"))
            if isinstance(compaction.get("status"), str) and str(compaction.get("status")).strip() not in {"", "idle"}:
                try:
                    approx_input_tokens = int(compaction.get("approx_input_tokens") or 0)
                except Exception:
                    approx_input_tokens = 0
                compaction_rows.append(
                    {
                        "session_id": session_id,
                        "status": str(compaction.get("status") or ""),
                        "summary_ref": str(compaction.get("summary_ref") or ""),
                        "last_compacted_at": str(compaction.get("last_compacted_at") or ""),
                        "trigger": str(compaction.get("trigger") or ""),
                        "source": str(compaction.get("source") or ""),
                        "approx_input_tokens": approx_input_tokens,
                    }
                )
            # Track predecessor lineage if present
            predecessor = str(ctx.get("predecessor_session_id") or "").strip()
            if predecessor and isinstance(provider_state.get("provider"), str):
                for prow in provider_rows:
                    if prow.get("session_id") == session_id:
                        prow["predecessor_session_id"] = predecessor

            loaded_sessions += 1
            decisions_by_session[session_id] = 0

            for decision in decisions:
                if not isinstance(decision, dict):
                    continue
                key = decision.get("key")
                if not isinstance(key, str) or not key:
                    continue
                row = {
                    "session_id": session_id,
                    "key": key,
                    "value": decision.get("value"),
                    "source": decision.get("source"),
                    "created_at": decision.get("created_at"),
                    "ttl_seconds": decision.get("ttl_seconds"),
                    "expires_at": decision.get("expires_at"),
                }
                decision_rows.append(row)
                decisions_by_session[session_id] += 1

    decisions_total = len(decision_rows)
    latest_by_key: dict[str, dict[str, Any]] = {}
    for row in sorted(decision_rows, key=_decision_key):
        latest_by_key[str(row.get("key"))] = row

    shared_decisions = sorted(latest_by_key.values(), key=lambda x: str(x.get("key") or ""))

    payload = {
        "version": "v1",
        "generated_at": now_iso,
        "workspace_root": str(workspace_root),
        "sessions_scanned": scanned_sessions,
        "sessions_loaded": loaded_sessions,
        "sessions_skipped": skipped_sessions,
        "decisions_total": decisions_total,
        "shared_keys_total": len(shared_decisions),
        "decisions_by_session": {k: int(v) for k, v in sorted(decisions_by_session.items())},
        "shared_decisions": shared_decisions,
        "provider_state_sessions": len(provider_rows),
        "provider_states": sorted(provider_rows, key=lambda item: (str(item.get("provider") or ""), str(item.get("session_id") or ""))),
        "compactions": sorted(compaction_rows, key=lambda item: (str(item.get("session_id") or ""), str(item.get("last_compacted_at") or ""))),
        "notes": ["PROGRAM_LED=true", "SESSION_SCOPED=true"],
    }

    write_json_atomic(out_path, payload)

    return {
        "status": "OK",
        "report_path": _rel_to_workspace(out_path, workspace_root),
        "shared_keys_total": len(shared_decisions),
        "sessions_loaded": loaded_sessions,
    }


def build_hierarchical_context(
    *,
    parent_workspace_root: Path,
    child_workspace_roots: list[Path],
    session_id: str = "default",
) -> dict[str, Any]:
    """Aggregate decisions from parent + all child sessions.

    Parent decisions win on key conflict (SSOT-first principle).
    Output: .cache/index/hierarchical_cross_context.v1.json in parent workspace.
    """
    now_iso = _now_iso8601()
    parent_sp = SessionPaths(workspace_root=parent_workspace_root, session_id=session_id)
    out_path = parent_workspace_root / ".cache" / "index" / "hierarchical_cross_context.v1.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    all_decisions: dict[str, dict[str, Any]] = {}  # key → decision (parent wins)
    sources: dict[str, str] = {}  # key → workspace_root origin

    # Load parent decisions first (these take priority)
    parent_decisions = 0
    if parent_sp.context_path.exists():
        try:
            parent_ctx = load_context(parent_sp.context_path)
            if not is_expired(parent_ctx, now_iso):
                prune_expired_decisions(parent_ctx, now_iso)
                for d in parent_ctx.get("ephemeral_decisions", []):
                    if isinstance(d, dict) and d.get("key"):
                        key = str(d["key"])
                        all_decisions[key] = d
                        sources[key] = str(parent_workspace_root)
                        parent_decisions += 1
        except SessionContextError:
            pass

    # Load child decisions (parent wins on conflict)
    child_stats: list[dict[str, Any]] = []
    for child_ws in child_workspace_roots:
        child_sp = SessionPaths(workspace_root=child_ws, session_id=session_id)
        child_count = 0
        child_inherited = 0
        if child_sp.context_path.exists():
            try:
                child_ctx = load_context(child_sp.context_path)
                if not is_expired(child_ctx, now_iso):
                    prune_expired_decisions(child_ctx, now_iso)
                    for d in child_ctx.get("ephemeral_decisions", []):
                        if isinstance(d, dict) and d.get("key"):
                            key = str(d["key"])
                            child_count += 1
                            if key not in all_decisions:
                                all_decisions[key] = d
                                sources[key] = str(child_ws)
                                child_inherited += 1
            except SessionContextError:
                pass
        child_stats.append({
            "workspace_root": str(child_ws),
            "decisions": child_count,
            "inherited": child_inherited,
        })

    merged = sorted(all_decisions.values(), key=lambda x: str(x.get("key") or ""))

    payload = {
        "version": "v1",
        "generated_at": now_iso,
        "parent_workspace_root": str(parent_workspace_root),
        "child_count": len(child_workspace_roots),
        "parent_decisions": parent_decisions,
        "total_merged_keys": len(merged),
        "merged_decisions": merged,
        "child_stats": child_stats,
        "decision_sources": {k: v for k, v in sorted(sources.items())},
    }

    write_json_atomic(out_path, payload)

    return {
        "status": "OK",
        "report_path": str(out_path),
        "total_merged_keys": len(merged),
        "parent_decisions": parent_decisions,
        "child_count": len(child_workspace_roots),
    }
