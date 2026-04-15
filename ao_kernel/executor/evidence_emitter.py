"""Evidence event emitter.

Appends workflow events to
``<workspace_root>/.ao/evidence/workflows/<run_id>/events.jsonl`` under
a per-run file lock, assigning a monotonic ``seq`` field that is the
authoritative replay ordering key.

Plan v2 (CNS-20260415-022 iter-1) decisions:

- **Per-run lock.** File ``events.jsonl.lock`` is taken via the shared
  POSIX ``file_lock`` helper for the read-last-seq + append + fsync
  cycle. Prevents interleaved seq assignment under concurrent writers
  (B3).
- **Monotonic seq.** Each event carries ``seq = last_seq + 1``. When
  the JSONL file is absent or empty, seq starts at 1.
- **Opaque event_id.** ``event_id = secrets.token_urlsafe(48)`` — a
  64-char URL-safe random string. Unique but NOT monotonic; consumers
  sort by ``(run_id, seq)``, never by event_id (B5).
- **Manifest NOT updated here.** The SHA-256 integrity manifest is
  generated on demand by the PR-A5 evidence-timeline CLI. PR-A3 is
  append-only (B4; see ``docs/EVIDENCE-TIMELINE.md §5`` revised).
- **Kind whitelist.** Events outside the 18-kind taxonomy raise
  ``ValueError``. The closed set matches
  ``docs/EVIDENCE-TIMELINE.md §2``.
- **Redaction at emission.** String values in ``payload`` that match
  any pattern in ``redaction.stdout_patterns`` are replaced with
  ``***REDACTED***`` before JSONL serialization. Env-key regex scrubs
  ``env`` subkeys whose names match ``env_keys_matching``.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final, Literal, Mapping

from ao_kernel._internal.shared.lock import file_lock
from ao_kernel.executor.errors import EvidenceEmitError
from ao_kernel.executor.policy_enforcer import RedactionConfig


_KINDS: Final[frozenset[str]] = frozenset({
    "workflow_started",
    "workflow_completed",
    "workflow_failed",
    "step_started",
    "step_completed",
    "step_failed",
    "adapter_invoked",
    "adapter_returned",
    "diff_previewed",
    "diff_applied",
    # PR-A4 addition: rollback of a previously applied patch. Idempotent
    # at the driver layer; emitted only when an actual reverse-diff apply
    # occurs (not on idempotent_skip no-ops).
    "diff_rolled_back",
    "approval_requested",
    "approval_granted",
    "approval_denied",
    "test_executed",
    "pr_opened",
    "policy_checked",
    "policy_denied",
})

_REDACTED: Final[str] = "***REDACTED***"


@dataclass(frozen=True)
class EvidenceEvent:
    """One workflow evidence event.

    ``event_id`` is opaque + unique (``secrets.token_urlsafe(48)``);
    consumers MUST NOT assume monotonicity. ``seq`` is the monotonic
    per-run ordering key — replay and timeline tools sort by
    ``(run_id, seq)``.
    """

    event_id: str
    seq: int
    run_id: str
    step_id: str | None
    ts: str
    actor: Literal["adapter", "ao-kernel", "human", "system"]
    kind: str
    payload: Mapping[str, Any]
    payload_hash: str
    replay_safe: bool


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def emit_event(
    workspace_root: Path,
    *,
    run_id: str,
    kind: str,
    actor: str,
    payload: Mapping[str, Any],
    step_id: str | None = None,
    redaction: RedactionConfig | None = None,
    replay_safe: bool = True,
) -> EvidenceEvent:
    """Append one event to the per-run JSONL under a per-run file lock.

    Raises:
    - ``ValueError`` when ``kind`` is outside the 18-event taxonomy.
    - ``EvidenceEmitError`` on lock / write / fsync failure.
    """
    if kind not in _KINDS:
        raise ValueError(
            f"Unknown evidence event kind: {kind!r}; allowed: "
            f"{sorted(_KINDS)}"
        )
    if actor not in {"adapter", "ao-kernel", "human", "system"}:
        raise ValueError(
            f"Unknown evidence actor: {actor!r}; allowed: adapter, "
            f"ao-kernel, human, system"
        )

    events_dir = workspace_root / ".ao" / "evidence" / "workflows" / run_id
    events_path = events_dir / "events.jsonl"
    lock_path = events_dir / "events.jsonl.lock"

    try:
        events_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise EvidenceEmitError(
            run_id=run_id,
            detail=f"could not create events dir {events_dir}: {exc}",
        ) from exc

    redacted_payload = _redact_payload(dict(payload), redaction)
    payload_hash = _hash_payload(redacted_payload)
    now_iso = datetime.now(timezone.utc).isoformat()
    event_id = secrets.token_urlsafe(48)

    try:
        with file_lock(lock_path):
            next_seq = _read_last_seq(events_path) + 1
            event = EvidenceEvent(
                event_id=event_id,
                seq=next_seq,
                run_id=run_id,
                step_id=step_id,
                ts=now_iso,
                # actor validated above; assign as-is for the dataclass
                actor=actor,  # type: ignore[arg-type]
                kind=kind,
                payload=redacted_payload,
                payload_hash=payload_hash,
                replay_safe=replay_safe,
            )
            line = _serialize_event(event)
            _append_line_with_fsync(events_path, line)
    except OSError as exc:
        raise EvidenceEmitError(
            run_id=run_id,
            detail=f"events.jsonl append failed: {exc}",
        ) from exc

    return event


def emit_adapter_log(
    workspace_root: Path,
    *,
    run_id: str,
    adapter_id: str,
    captured_stdout: str,
    captured_stderr: str,
    redaction: RedactionConfig,
) -> Path:
    """Write redacted stdout/stderr to
    ``.ao/evidence/workflows/<run_id>/adapter-<adapter_id>.jsonl`` as
    a single structured record.

    Returns the path. One adapter invocation writes one JSONL line; a
    second call appends another line. No lock (single-writer during an
    invocation); fsync after append.
    """
    adapter_log_path = (
        workspace_root
        / ".ao"
        / "evidence"
        / "workflows"
        / run_id
        / f"adapter-{adapter_id}.jsonl"
    )
    try:
        adapter_log_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise EvidenceEmitError(
            run_id=run_id,
            detail=(
                f"could not create adapter log dir "
                f"{adapter_log_path.parent}: {exc}"
            ),
        ) from exc

    record = {
        "adapter_id": adapter_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "stdout": _redact_text(captured_stdout, redaction),
        "stderr": _redact_text(captured_stderr, redaction),
    }
    line = json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n"

    try:
        _append_line_with_fsync(adapter_log_path, line)
    except OSError as exc:
        raise EvidenceEmitError(
            run_id=run_id,
            detail=f"adapter log append failed: {exc}",
        ) from exc
    return adapter_log_path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _read_last_seq(events_path: Path) -> int:
    """Return the seq value of the last line in the JSONL, or 0 if
    the file does not exist or is empty."""
    if not events_path.exists():
        return 0
    try:
        with events_path.open("rb") as f:
            try:
                f.seek(-1, 2)
            except OSError:
                return 0
            file_size = f.tell() + 1
            if file_size == 0:
                return 0
            # Scan backwards for the last newline; typical events are
            # small so a linear last-line read is fine.
            block = 1024
            offset = max(0, file_size - block)
            f.seek(offset, 0)
            data = f.read()
        # data is bytes; decode and find the last non-empty line
        text = data.decode("utf-8", errors="replace").rstrip()
        if not text:
            return 0
        last_line = text.splitlines()[-1]
        try:
            record = json.loads(last_line)
        except json.JSONDecodeError:
            # Corrupted line; treat as fresh. Full recovery is a PR-A5
            # concern.
            return 0
        seq_val = record.get("seq")
        if isinstance(seq_val, int) and seq_val >= 0:
            return seq_val
        return 0
    except OSError:
        return 0


def _append_line_with_fsync(path: Path, line: str) -> None:
    """Append ``line`` to ``path`` and fsync the file descriptor."""
    with path.open("a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        import os  # local import keeps module-level imports tidy

        os.fsync(f.fileno())


def _serialize_event(event: EvidenceEvent) -> str:
    record = {
        "event_id": event.event_id,
        "seq": event.seq,
        "run_id": event.run_id,
        "step_id": event.step_id,
        "ts": event.ts,
        "actor": event.actor,
        "kind": event.kind,
        "payload": dict(event.payload),
        "payload_hash": event.payload_hash,
        "replay_safe": event.replay_safe,
    }
    return json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n"


def _redact_payload(
    payload: dict[str, Any],
    redaction: RedactionConfig | None,
) -> dict[str, Any]:
    """Return a new dict with regex-matched substrings replaced.

    Env subkeys matching ``env_keys_matching`` have their values wholly
    replaced. All other string values are scrubbed via
    ``stdout_patterns``. Non-string values pass through verbatim.
    """
    if redaction is None:
        return dict(payload)
    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        if key == "env" and isinstance(value, dict):
            redacted[key] = _redact_env_mapping(value, redaction)
            continue
        if isinstance(value, str):
            redacted[key] = _redact_text(value, redaction)
        elif isinstance(value, dict):
            redacted[key] = _redact_payload(value, redaction)
        elif isinstance(value, list):
            redacted[key] = [
                _redact_text(v, redaction) if isinstance(v, str) else v
                for v in value
            ]
        else:
            redacted[key] = value
    return redacted


def _redact_env_mapping(
    env: Mapping[str, Any],
    redaction: RedactionConfig,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in env.items():
        if any(p.search(k) for p in redaction.env_keys_matching):
            out[k] = _REDACTED
        elif isinstance(v, str):
            out[k] = _redact_text(v, redaction)
        else:
            out[k] = v
    return out


def _redact_text(text: str, redaction: RedactionConfig) -> str:
    result = text
    for pattern in redaction.stdout_patterns:
        result = pattern.sub(_REDACTED, result)
    return result


def _hash_payload(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = [
    "EvidenceEvent",
    "emit_event",
    "emit_adapter_log",
]
