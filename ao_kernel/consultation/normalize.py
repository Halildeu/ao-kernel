"""Consultation verdict normalization + resolution record (v3.5 D2a).

Heterogeneous consultation response corpus → deterministic
`NormalizedVerdict` enum + source-stable `ResolutionRecord`. Codex
plan v4 AGREE (iter-4 closed):

- Verdict mapping handles string / object (`option_id`) / whitespace
  / case variants. Free-text body heuristics NOT used (false-positive
  risk in review corpus).
- `ResolutionRecord` carries ONLY source-derived fields —
  ``resolved_at`` from last normalized response's ``responded_at``;
  archive-time metadata (``config_digest``, ``archived_at``) lives in
  the separate ``archive-meta.json`` artefact so record digests stay
  source-stable across re-runs.
- Status limited to ``resolved | pending``. Abandonment determination
  (TTL-based) is a v3.6 runtime concern.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from ao_kernel._internal.shared.utils import parse_iso8601, sha256_file


NORMALIZER_VERSION = "v1"


class NormalizedVerdict(str, Enum):
    AGREE = "AGREE"
    PARTIAL = "PARTIAL"
    REVISE = "REVISE"
    REJECT = "REJECT"
    UNCLASSIFIED = "UNCLASSIFIED"


class ResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    PENDING = "pending"
    # ``abandoned`` intentionally omitted — v3.6 concern.


_VERDICT_MAP: dict[str, NormalizedVerdict] = {
    # AGREE family
    "agree": NormalizedVerdict.AGREE,
    "merge": NormalizedVerdict.AGREE,
    "green": NormalizedVerdict.AGREE,
    "approve": NormalizedVerdict.AGREE,
    "approved": NormalizedVerdict.AGREE,
    # PARTIAL family
    "partial": NormalizedVerdict.PARTIAL,
    "amber": NormalizedVerdict.PARTIAL,
    "mostly_agree": NormalizedVerdict.PARTIAL,
    "phased-core": NormalizedVerdict.PARTIAL,
    "phased": NormalizedVerdict.PARTIAL,
    # REVISE family
    "revise": NormalizedVerdict.REVISE,
    "revise-again": NormalizedVerdict.REVISE,
    "scope_cut": NormalizedVerdict.REVISE,
    "needs_changes": NormalizedVerdict.REVISE,
    "b": NormalizedVerdict.REVISE,
    "c": NormalizedVerdict.REVISE,
    "d": NormalizedVerdict.REVISE,
    # REJECT family (BLOCK merged into REJECT per Codex iter-2)
    "reject": NormalizedVerdict.REJECT,
    "red": NormalizedVerdict.REJECT,
    "block": NormalizedVerdict.REJECT,
    "disagree": NormalizedVerdict.REJECT,
    "rejected": NormalizedVerdict.REJECT,
}


def _parse_multi_answer_token(raw: str) -> str:
    """Extract first answer token from a multi-answer verdict string.

    Historical corpus includes shapes like ``"1:C,3:B,7:C"`` and
    ``"S1:C,S2:A,S3:C,S4:B"`` — a leading question identifier followed
    by a ``:`` + option letter, comma-separated. This helper peels off
    the first segment and returns the token after ``:`` so the caller
    can map it via the regular verdict matrix. Returns the input
    unchanged when no ``,``/``:`` structure is present.
    """
    first_segment = raw.split(",", 1)[0].strip()
    if ":" in first_segment:
        return first_segment.split(":", 1)[1].strip()
    return first_segment


def normalize_verdict(raw: Any) -> NormalizedVerdict:
    """Map a heterogeneous raw verdict to the 5-bucket enum.

    Accepts strings (case-insensitive, whitespace-tolerant), multi-
    answer strings like ``"1:C,3:B,7:C"`` (first answer token wins),
    and objects with an ``option_id`` field. All other shapes →
    UNCLASSIFIED. Body-text heuristics deliberately NOT used (false
    positives on review-style corpus).
    """
    if isinstance(raw, str):
        key = raw.strip().lower()
        direct = _VERDICT_MAP.get(key)
        if direct is not None:
            return direct
        # Multi-answer fallback (Codex D2a iter-5 BLOCK absorb)
        if "," in raw or ":" in raw:
            token = _parse_multi_answer_token(raw).lower()
            multi = _VERDICT_MAP.get(token)
            if multi is not None:
                return multi
        return NormalizedVerdict.UNCLASSIFIED
    if isinstance(raw, Mapping):
        option_id = raw.get("option_id")
        if isinstance(option_id, str):
            return _VERDICT_MAP.get(
                option_id.strip().lower(),
                NormalizedVerdict.UNCLASSIFIED,
            )
    return NormalizedVerdict.UNCLASSIFIED


def _extract_raw_verdict(response_doc: Mapping[str, Any]) -> Any:
    """Pick the most likely verdict field from a heterogeneous response.

    Priority: ``overall_verdict``, ``verdict``, ``status`` (last resort
    because status is inconsistent — OPEN/CLOSED/ANSWERED). Unknown →
    ``""`` (will map to UNCLASSIFIED).
    """
    for key in ("overall_verdict", "verdict", "resolution"):
        if key in response_doc:
            return response_doc[key]
    status = response_doc.get("status")
    if isinstance(status, str) and status.strip().upper() not in (
        "OPEN", "CLAIMED", "RUNNING", "",
    ):
        return status
    return ""


@dataclass(frozen=True)
class RequestEntry:
    iteration: int
    path_rel: str
    sha256: str
    created_at: str | None


@dataclass(frozen=True)
class ResponseEntry:
    iteration: int
    agent: str
    path_rel: str
    sha256: str
    raw_verdict: str
    normalized_verdict: NormalizedVerdict
    responded_at: str | None


@dataclass(frozen=True)
class ResolutionRecord:
    """Source-stable normalized record for a single CNS.

    Archive-time metadata (config_digest, archived_at) lives in
    ``archive-meta.json``; this record contains ONLY source-derived
    fields so the digest stays stable across re-runs with unchanged
    sources.
    """

    version: str
    cns_id: str
    topic: str
    from_agent: str
    to_agent: str
    requests: tuple[RequestEntry, ...]
    responses: tuple[ResponseEntry, ...]
    final_verdict: NormalizedVerdict
    status: ResolutionStatus
    resolved_at: str | None
    normalizer_version: str


def iteration_from_filename(filename: str) -> int:
    """Parse iteration number from a CNS filename like
    ``CNS-20260414-010.iter2.request.v1.json`` or the initial
    ``CNS-20260414-010.request.v1.json`` (iteration 1)."""
    parts = filename.split(".")
    for part in parts:
        if part.startswith("iter") and part[4:].isdigit():
            return int(part[4:])
    return 1


def _agent_from_response_filename(filename: str) -> str:
    """Extract agent id from ``CNS-....codex.response.v1.json`` etc."""
    parts = filename.split(".")
    # Typical pattern: CNS-YYYYMMDD-NNN[.iterN].<agent>.response.v1.json
    for i, part in enumerate(parts):
        if part == "response" and i > 0:
            # agent is the token immediately before "response"
            candidate = parts[i - 1]
            if candidate.startswith("iter") and candidate[4:].isdigit():
                # No agent token; return empty string (fallback)
                return ""
            return candidate
    return ""


def _build_request_entry(
    path: Path, snapshot_rel: str,
) -> RequestEntry:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        doc = {}
    return RequestEntry(
        iteration=iteration_from_filename(path.name),
        path_rel=snapshot_rel,
        sha256=sha256_file(path),
        created_at=(
            doc.get("created_at")
            if isinstance(doc.get("created_at"), str) else None
        ),
    )


def _build_response_entry(
    path: Path, snapshot_rel: str,
) -> ResponseEntry:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        doc = {}
    raw_verdict = _extract_raw_verdict(doc)
    raw_str = (
        raw_verdict if isinstance(raw_verdict, str) else json.dumps(raw_verdict)
    )
    return ResponseEntry(
        iteration=iteration_from_filename(path.name),
        agent=_agent_from_response_filename(path.name),
        path_rel=snapshot_rel,
        sha256=sha256_file(path),
        raw_verdict=raw_str,
        normalized_verdict=normalize_verdict(raw_verdict),
        responded_at=(
            doc.get("responded_at") or doc.get("answered_at")
            if isinstance(
                doc.get("responded_at") or doc.get("answered_at"), str,
            ) else None
        ),
    )


def _order_responses(
    responses: list[ResponseEntry],
) -> tuple[ResponseEntry, ...]:
    """Deterministic ordering: iteration > parsed-timestamp > filename.

    Codex iter-4 mikro: parse_iso8601 used for timestamp tie-break —
    naive string comparison fails on offset-aware ISO variants.
    """
    def _key(r: ResponseEntry) -> tuple[int, float, str]:
        ts_val = parse_iso8601(r.responded_at) if r.responded_at else None
        return (
            r.iteration,
            ts_val.timestamp() if ts_val is not None else 0.0,
            r.path_rel,
        )
    return tuple(sorted(responses, key=_key))


def _derive_resolved_at(responses: tuple[ResponseEntry, ...]) -> str | None:
    """Last normalizable response's ``responded_at`` (or None)."""
    normalized = [
        r for r in responses
        if r.normalized_verdict != NormalizedVerdict.UNCLASSIFIED
    ]
    if not normalized:
        return None
    # Pick the latest by the same deterministic ordering
    def _sort_key(r: ResponseEntry) -> tuple[int, float, str]:
        ts_val = parse_iso8601(r.responded_at) if r.responded_at else None
        return (
            r.iteration,
            ts_val.timestamp() if ts_val is not None else 0.0,
            r.path_rel,
        )
    last = max(normalized, key=_sort_key)
    return last.responded_at


def build_resolution_record(
    *,
    cns_id: str,
    request_snapshots: list[tuple[Path, str]],
    response_snapshots: list[tuple[Path, str]],
    request_doc_for_meta: Mapping[str, Any],
) -> ResolutionRecord:
    """Assemble a ResolutionRecord from snapshot file pairs.

    Args:
        cns_id: The consultation id (e.g. ``CNS-20260418-042``).
        request_snapshots: ``[(abs_snapshot_path, relative_path), ...]``
            for each request iteration.
        response_snapshots: Same shape for responses.
        request_doc_for_meta: Parsed initial request JSON — provides
            ``topic``, ``from_agent``, ``to_agent``.
    """
    requests = tuple(
        _build_request_entry(p, rel) for p, rel in request_snapshots
    )
    responses_unordered = [
        _build_response_entry(p, rel) for p, rel in response_snapshots
    ]
    responses = _order_responses(responses_unordered)

    final_verdict = NormalizedVerdict.UNCLASSIFIED
    for r in reversed(responses):  # last normalizable wins
        if r.normalized_verdict != NormalizedVerdict.UNCLASSIFIED:
            final_verdict = r.normalized_verdict
            break

    has_any_response = len(responses) > 0
    status = (
        ResolutionStatus.RESOLVED
        if final_verdict != NormalizedVerdict.UNCLASSIFIED
        else ResolutionStatus.PENDING
    )
    # Pending even if responses present but all UNCLASSIFIED
    if has_any_response and final_verdict == NormalizedVerdict.UNCLASSIFIED:
        status = ResolutionStatus.PENDING

    topic = str(request_doc_for_meta.get("topic", "")) or "unknown"
    from_agent = str(request_doc_for_meta.get("from_agent", "")) or "unknown"
    to_agent = str(request_doc_for_meta.get("to_agent", "")) or "unknown"

    return ResolutionRecord(
        version="v1",
        cns_id=cns_id,
        topic=topic,
        from_agent=from_agent,
        to_agent=to_agent,
        requests=requests,
        responses=responses,
        final_verdict=final_verdict,
        status=status,
        resolved_at=_derive_resolved_at(responses),
        normalizer_version=NORMALIZER_VERSION,
    )


def record_to_dict(record: ResolutionRecord) -> dict[str, Any]:
    """Serialize to JSON-friendly dict (enum values as strings)."""
    return {
        "version": record.version,
        "cns_id": record.cns_id,
        "topic": record.topic,
        "from_agent": record.from_agent,
        "to_agent": record.to_agent,
        "requests": [
            {
                "iteration": r.iteration,
                "path_rel": r.path_rel,
                "sha256": r.sha256,
                "created_at": r.created_at,
            }
            for r in record.requests
        ],
        "responses": [
            {
                "iteration": r.iteration,
                "agent": r.agent,
                "path_rel": r.path_rel,
                "sha256": r.sha256,
                "raw_verdict": r.raw_verdict,
                "normalized_verdict": r.normalized_verdict.value,
                "responded_at": r.responded_at,
            }
            for r in record.responses
        ],
        "final_verdict": record.final_verdict.value,
        "status": record.status.value,
        "resolved_at": record.resolved_at,
        "normalizer_version": record.normalizer_version,
    }


__all__ = [
    "NORMALIZER_VERSION",
    "NormalizedVerdict",
    "ResolutionStatus",
    "RequestEntry",
    "ResponseEntry",
    "ResolutionRecord",
    "iteration_from_filename",
    "normalize_verdict",
    "build_resolution_record",
    "record_to_dict",
]
