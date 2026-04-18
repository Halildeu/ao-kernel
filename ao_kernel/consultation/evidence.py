"""Consultation evidence emit + persistent dedupe (v3.5 D2a).

Dedicated evidence surface for CNS (Codex iter-2 advice: workflow
`evidence_emitter` NOT reused). Append-only JSONL at
``.ao/evidence/consultations/<CNS-ID>/events.jsonl`` with per-kind
identity dedupe so repeat ``archive`` runs don't grow the stream.

Per-kind identity contract (Codex iter-4):

- ``OPENED / REQUEST_REVISED / RESPONSE_RECEIVED / INVALID`` →
  ``(kind, source_path, source_sha256, normalizer_version)``
- ``NORMALIZED`` → ``(kind, cns_id, resolution_record_digest,
  normalizer_version)``

Same identity → skip append. Different identity → append.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


logger = logging.getLogger(__name__)


class ConsultationEventKind(str, Enum):
    OPENED = "CONSULTATION_OPENED"
    REQUEST_REVISED = "CONSULTATION_REQUEST_REVISED"
    RESPONSE_RECEIVED = "CONSULTATION_RESPONSE_RECEIVED"
    NORMALIZED = "CONSULTATION_NORMALIZED"
    INVALID = "CONSULTATION_INVALID"


_ALL_KINDS = frozenset(k.value for k in ConsultationEventKind)


def _iso_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _identity_for_event(event: Mapping[str, Any]) -> tuple[Any, ...]:
    """Per-kind dedupe key — source-based events use source_sha256,
    normalized event uses resolution_record_digest."""
    kind = event.get("kind")
    normalizer_version = event.get("normalizer_version")
    if kind == ConsultationEventKind.NORMALIZED.value:
        return (
            kind,
            event.get("cns_id"),
            event.get("resolution_record_digest"),
            normalizer_version,
        )
    return (
        kind,
        event.get("source_path"),
        event.get("source_sha256"),
        normalizer_version,
    )


def preload_event_identities(events_path: Path) -> set[tuple[Any, ...]]:
    """Read existing events.jsonl (if any) and build the identity set
    for persistent dedupe across process restarts."""
    if not events_path.is_file():
        return set()
    identities: set[tuple[Any, ...]] = set()
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        identities.add(_identity_for_event(event))
    return identities


def append_event(
    events_path: Path,
    *,
    kind: ConsultationEventKind,
    payload: Mapping[str, Any],
    seen: set[tuple[Any, ...]],
) -> bool:
    """Append an event if its identity hasn't been seen.

    Returns ``True`` when the event was written, ``False`` when the
    identity was a duplicate (persistent or run-local). Callers pass
    the same ``seen`` set across a single archive run so both
    preload-seen and in-run-seen identities are honored.
    """
    if kind.value not in _ALL_KINDS:
        raise ValueError(f"unknown consultation event kind: {kind!r}")

    event: dict[str, Any] = {"kind": kind.value, **payload}
    event.setdefault("ts", _iso_now())

    identity = _identity_for_event(event)
    if identity in seen:
        return False

    events_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with events_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")
    seen.add(identity)
    return True


__all__ = [
    "ConsultationEventKind",
    "preload_event_identities",
    "append_event",
]
