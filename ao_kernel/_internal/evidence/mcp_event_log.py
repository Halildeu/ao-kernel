"""MCP tool-call evidence log — append-only JSONL, one event per handler invocation.

Per CLAUDE.md §2 invariant #2, evidence comes in two forms:

* **MCP events** (this module) — JSONL append-only log, fsync'd,
  daily-rotated. **No SHA256 integrity manifest.** The manifest
  machinery is reserved for workspace artefacts (canonical
  decisions, checkpoints, evidence run directories) where files
  live long enough for periodic integrity audits to matter.
* **Workspace artefacts** — JSONL + SHA256 integrity manifest.

Pre-B4 the MCP tools returned envelopes but wrote NO evidence trail;
operators had no way to audit what ran, when, or with what decision.
The manifest gap is a deliberate scope decision recorded in the
Tranche C handoff's technical-debt table — adding an MCP manifest is
queued for Tranche D (v3.1.0+), not C.

Contract:
    - Library mode (no .ao/) => no-op. Evidence is a workspace feature.
    - Event payload is a snapshot of the handler's decision envelope
      with sensitive fields redacted (messages, params with api_key
      substrings, etc.) so the log is safe to ship to operators.
    - Append failures are swallowed (debug-logged). Evidence must never
      block the primary tool call — fail-open for the writer is the
      correct choice under this invariant because the MCP response
      itself is already delivered by the time we log.
    - fsync after every append so a process crash cannot produce a
      truncated JSONL line.
    - Daily rotation keeps a single file per UTC day; concurrent writers
      on the same process append through the same open-and-close pattern
      to minimize overlap.

Path layout:
    .ao/evidence/mcp/YYYY-MM-DD.jsonl
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

logger = logging.getLogger(__name__)

# Keys that may embed secrets or user content; their values are replaced with
# a redaction marker before the event is serialised. Matches by case-insensitive
# key name suffix.
_REDACT_SUFFIXES = (
    "api_key",
    "apikey",
    "token",
    "password",
    "secret",
    "messages",
    "message",
    "content",
    "prompt",
    "query",
)

_REDACTED = "***REDACTED***"

# Keys whose VALUES should never be written at all (e.g. raw tool params).
_DROP_KEYS = frozenset({"params", "raw_messages"})

_SECRET_VALUE_PATTERN = re.compile(r"(sk-[A-Za-z0-9]{16,}|gh[a-z]_[A-Za-z0-9]{16,})")


def _should_redact(key: str) -> bool:
    lowered = key.lower()
    return any(lowered.endswith(suffix) for suffix in _REDACT_SUFFIXES)


def _scrub(value: Any) -> Any:
    """Recursive, conservative redaction — preserves structure for auditors."""
    if isinstance(value, Mapping):
        scrubbed: dict[str, Any] = {}
        for k, v in value.items():
            if k in _DROP_KEYS:
                scrubbed[k] = _REDACTED
                continue
            if _should_redact(str(k)):
                scrubbed[k] = _REDACTED
                continue
            scrubbed[k] = _scrub(v)
        return scrubbed
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    if isinstance(value, str):
        # Redact obvious secret-shaped substrings inside free-form text.
        if _SECRET_VALUE_PATTERN.search(value):
            return _SECRET_VALUE_PATTERN.sub(_REDACTED, value)
        return value
    return value


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _resolve_log_path(workspace: Path | None) -> Path | None:
    """Library mode => None; otherwise compute daily-rotated path."""
    if workspace is None:
        return None
    if not workspace.is_dir():
        return None
    return workspace / ".ao" / "evidence" / "mcp" / f"{_today_utc()}.jsonl"


def record_mcp_event(
    workspace: Path | None,
    tool: str,
    envelope: Mapping[str, Any],
    *,
    params: Mapping[str, Any] | None = None,
    duration_ms: int | None = None,
    extra: Mapping[str, Any] | None = None,
) -> bool:
    """Append a single MCP tool-call event to the daily JSONL log.

    Args:
        workspace: Workspace root (None => library mode => no-op).
        tool: Tool identifier (e.g. "ao_llm_call").
        envelope: Decision envelope returned to the caller. Redacted before write.
        params: Optional params dict the handler received. Written under
            ``params_shape`` (keys + types only, never values) so auditors can
            reconstruct the call surface without leaking content.
        duration_ms: Optional handler wall-time in milliseconds.
        extra: Free-form additional fields merged into the event payload
            (after redaction). Caller-supplied — keep metadata only.

    Returns:
        True when the event was durably appended (and fsynced), False on
        no-op (library mode) or any write failure.
    """
    path = _resolve_log_path(workspace)
    if path is None:
        return False

    event: dict[str, Any] = {
        "ts": _now_iso(),
        "tool": tool,
        "allowed": bool(envelope.get("allowed", False)),
        "decision": envelope.get("decision", "unknown"),
        "reason_codes": list(envelope.get("reason_codes") or []),
        "policy_ref": envelope.get("policy_ref"),
        "api_version": envelope.get("api_version"),
        "data_shape": _shape(envelope.get("data")),
        "error": envelope.get("error"),
    }
    if duration_ms is not None:
        event["duration_ms"] = int(duration_ms)
    if params is not None:
        event["params_shape"] = _shape(params)
    if extra:
        event.update(_scrub(dict(extra)))

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                # fsync may fail on some filesystems (network FS, docker
                # bind mounts). The write itself already landed; treat
                # fsync failure as non-fatal and continue.
                pass
    except Exception as exc:  # noqa: BLE001 — evidence write is best-effort
        logger.debug("mcp_event_log: append failed (%s) for %s", exc, tool)
        return False
    return True


def _shape(value: Any) -> Any:
    """Type-only projection — keys with type names, never values.

    Used to record call-surface shape in evidence without leaking content.
    """
    if isinstance(value, Mapping):
        return {str(k): type(v).__name__ for k, v in value.items()}
    if isinstance(value, list):
        return [type(item).__name__ for item in value[:10]]
    if value is None:
        return None
    return type(value).__name__


__all__ = ["record_mcp_event"]
