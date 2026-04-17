"""Debug-query subcommand (PR-B5 C3b) — non-Prometheus JSON query surface.

``ao-kernel metrics debug-query --since <ISO8601> [--run <id>]`` emits
a JSON document with filtered evidence events and summary aggregates.
Never emits Prometheus textfile — the design explicitly separates the
cumulative-only textfile export (``metrics export``) from the
windowed / run-scoped ad-hoc query surface so operators can debug
live workspaces without breaking scrape counter semantics.

Plan v4 iter-2 absorb: ``--since`` is strict timezone-aware. The
underlying :func:`ao_kernel._internal.shared.utils.parse_iso8601`
helper accepts naive ISO strings but evidence timestamps are
always aware — mixing the two produces silent semantic drift, so
this module adds :func:`parse_iso8601_strict` that enforces the
contract at the CLI boundary.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ao_kernel._internal.shared.utils import parse_iso8601
from ao_kernel.metrics.errors import (
    EvidenceSourceCorruptedError,
    EvidenceSourceMissingError,
)


def parse_iso8601_strict(value: str) -> datetime:
    """Parse an ISO-8601 timestamp with mandatory timezone information.

    Wraps :func:`ao_kernel._internal.shared.utils.parse_iso8601` and
    tightens the contract:

    - Naive input (``tzinfo is None``) is rejected. Operators must
      supply ``Z`` or an explicit ``+HH:MM`` offset.
    - Non-string input is rejected (``argparse type=parse_iso8601_strict``
      converts anyway, but the guard keeps the error message tight).
    - Epoch integers are rejected implicitly because ``parse_iso8601``
      only accepts strings.

    Raises:
        ValueError: Either the string cannot be parsed or the parsed
            datetime is naive. The argparse dispatcher surfaces the
            raised message as a CLI error.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            "--since: ISO-8601 string required (got empty / non-string)"
        )
    parsed = parse_iso8601(value)
    if parsed is None:
        raise ValueError(
            f"--since: ISO-8601 parse failed for {value!r}; "
            f"expected e.g. '2026-04-17T18:00:00Z' or "
            f"'2026-04-17T18:00:00+00:00'"
        )
    if parsed.tzinfo is None:
        raise ValueError(
            f"--since: timezone required, use 'Z' or '+HH:MM' offset "
            f"(got {value!r})"
        )
    return parsed


def cmd_metrics_debug_query(args: Any) -> int:
    """Handle ``ao-kernel metrics debug-query``.

    Returns JSON to stdout (default) or ``--output``. The output is a
    single JSON object with three top-level keys:

    - ``filter``: the applied filters (since, run_id, applied_at).
    - ``summary``: event counts by kind.
    - ``events``: list of matching events sorted by (ts, seq).

    Exit codes:

    - 0 success (events list may be empty).
    - 1 user error (invalid --since, --run not found).
    - 2 internal (corrupt JSONL).
    """
    workspace = _resolve_workspace(args)
    since = getattr(args, "since", None)
    run_filter = getattr(args, "run", None)

    # --since is argparse-validated by the type=parse_iso8601_strict
    # callback, so we receive either None or a tz-aware datetime.
    try:
        events = _collect_events(
            workspace, since=since, run_filter=run_filter,
        )
    except EvidenceSourceCorruptedError as exc:
        print(f"error: corrupt evidence JSONL — {exc}", file=sys.stderr)
        return 2
    except EvidenceSourceMissingError as exc:
        print(f"error: evidence source missing — {exc}", file=sys.stderr)
        return 1

    summary = _summarize(events)
    payload: dict[str, Any] = {
        "filter": {
            "since": since.isoformat() if since else None,
            "run_id": run_filter,
            "applied_at": datetime.now(timezone.utc).isoformat(),
        },
        "summary": summary,
        "events": events,
    }

    serialized = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, indent=2,
    )
    output_path = getattr(args, "output", None)
    if output_path:
        from ao_kernel._internal.shared.utils import write_text_atomic

        write_text_atomic(Path(output_path), serialized + "\n")
    else:
        sys.stdout.write(serialized + "\n")
    return 0


def _collect_events(
    workspace: Path,
    *,
    since: datetime | None,
    run_filter: str | None,
) -> list[dict[str, Any]]:
    root = workspace / ".ao" / "evidence" / "workflows"
    if not root.is_dir():
        if run_filter:
            raise EvidenceSourceMissingError(
                f"no evidence directory at {root}"
            )
        return []

    if run_filter:
        targets = [root / run_filter]
        if not targets[0].is_dir():
            raise EvidenceSourceMissingError(
                f"run {run_filter!r} has no evidence at {targets[0]}"
            )
    else:
        targets = [d for d in sorted(root.iterdir()) if d.is_dir()]

    results: list[dict[str, Any]] = []
    for run_dir in targets:
        events_path = run_dir / "events.jsonl"
        if not events_path.is_file():
            continue
        text = events_path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                event = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise EvidenceSourceCorruptedError(
                    f"malformed JSONL at {events_path}:{lineno}: {exc}"
                ) from exc
            if since is not None and not _event_at_or_after(event, since):
                continue
            results.append(event)
    results.sort(
        key=lambda e: (str(e.get("ts") or ""), e.get("seq") or 0),
    )
    return results


def _event_at_or_after(event: dict[str, Any], since: datetime) -> bool:
    ts_value = event.get("ts")
    if not isinstance(ts_value, str):
        return False
    parsed = parse_iso8601(ts_value)
    if parsed is None:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed >= since


def _summarize(events: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for event in events:
        kind = str(event.get("kind") or "unknown")
        counts[kind] = counts.get(kind, 0) + 1
    return {
        "total": len(events),
        "by_kind": dict(sorted(counts.items())),
    }


def _resolve_workspace(args: Any) -> Path:
    ws = getattr(args, "workspace_root", None)
    if ws:
        return Path(ws)
    from ao_kernel.config import workspace_root

    resolved = workspace_root()
    if resolved is None:
        print("error: no .ao/ workspace found", file=sys.stderr)
        sys.exit(1)
    return resolved


__all__ = [
    "cmd_metrics_debug_query",
    "parse_iso8601_strict",
]
