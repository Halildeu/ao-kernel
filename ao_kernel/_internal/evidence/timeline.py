"""Evidence timeline reader + formatter (PR-A5).

Reads per-run ``events.jsonl``, sorts by ``seq``, filters by kind/actor,
formats as human-readable table or NDJSON.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence


def timeline(
    workspace_root: Path,
    run_id: str,
    *,
    format: str = "table",
    filter_kinds: Sequence[str] | None = None,
    filter_actor: str | None = None,
    limit: int | None = None,
) -> str:
    """Return formatted timeline string.

    Raises ``FileNotFoundError`` when run dir or events.jsonl absent.
    Returns ``"no events"`` for empty JSONL.
    """
    events_path = (
        workspace_root / ".ao" / "evidence" / "workflows" / run_id / "events.jsonl"
    )
    if not events_path.exists():
        raise FileNotFoundError(f"events not found: {events_path}")

    events = _parse_events(events_path)
    if not events:
        return "no events"

    # Sort by seq (monotonic ordering key)
    events.sort(key=lambda e: e.get("seq", 0))

    # Filters
    if filter_kinds:
        allowed = set(filter_kinds)
        events = [e for e in events if e.get("kind") in allowed]
    if filter_actor:
        events = [e for e in events if e.get("actor") == filter_actor]

    # Limit (last N)
    if limit is not None and limit > 0:
        events = events[-limit:]

    if not events:
        return "no events (after filters)"

    if format == "json":
        return "\n".join(
            json.dumps(e, sort_keys=True, ensure_ascii=False) for e in events
        )

    return _format_table(events)


def _parse_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"malformed JSONL at {path}:{lineno}: {exc}"
            ) from exc
    return events


def _format_table(events: list[dict[str, Any]]) -> str:
    header = f"{'seq':>5} | {'ts':24} | {'kind':24} | {'actor':12} | {'step_id':30} | payload_summary"
    sep = "-" * len(header)
    rows = [header, sep]
    for e in events:
        seq = e.get("seq", "?")
        ts = e.get("ts", "")[:24]
        kind = e.get("kind", "")[:24]
        actor = e.get("actor", "")[:12]
        step_id = (e.get("step_id") or "")[:30]
        summary = _payload_summary(e.get("payload", {}))
        rows.append(
            f"{seq:>5} | {ts:24} | {kind:24} | {actor:12} | {step_id:30} | {summary}"
        )
    return "\n".join(rows)


def _payload_summary(payload: dict[str, Any], max_len: int = 96) -> str:
    compact = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    )
    if len(compact) <= max_len:
        return compact
    return compact[: max_len - 3] + "..."
