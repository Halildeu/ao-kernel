"""Consultation canonical promotion (v3.5 D2b).

Adapter between D2a's `resolution.record.v1.json` artefacts and the
existing canonical decision store (``ao_kernel.context.canonical_store``).
Opt-in (policy flag `promotion.enabled=false` by default); `--force`
bypasses only the flag, not integrity/safety gates.

Codex plan-time CNS: 3 iterations → AGREE.

Pipeline (per CNS):

1. Integrity gate — ``verify_consultation_manifest(cns_dir)`` must pass
2. Load ``resolution.record.v1.json``; skip if missing (reported as
   integrity error so operator sees the gap)
3. Eligibility — ``status == "resolved"`` AND ``final_verdict in
   {AGREE, PARTIAL}``
4. Idempotency — compute record SHA-256, compare against
   ``canonical_decisions.decisions[key].provenance.record_digest``
5. Promote via ``canonical_store.promote_decision(...)`` with compact
   value + relative-path provenance pointer
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ao_kernel.consultation.integrity import verify_consultation_manifest
from ao_kernel.consultation.normalize import record_digest
from ao_kernel.context.canonical_store import (
    load_store,
    promote_decision,
    query as canonical_query,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PromotionSummary:
    scanned: int
    eligible: int
    promoted: int
    updated: int
    skipped_same_digest: int
    skipped_integrity: int
    skipped_ineligible: int
    skipped_disabled: int
    skipped_missing_record: int
    errors: tuple[str, ...]
    dry_run: bool


_PROMOTABLE_VERDICTS = frozenset({"AGREE", "PARTIAL"})


def verdict_confidence(verdict: str) -> float:
    """Map promotable normalized verdicts to canonical store confidence.

    Only ``AGREE`` / ``PARTIAL`` entries reach this function (others
    are filtered at the eligibility gate); unknown values fall to 0.0
    as a defensive default.
    """
    return {"AGREE": 1.0, "PARTIAL": 0.7}.get(verdict, 0.0)


def _store_key(cns_id: str) -> str:
    """Canonical store key for a consultation promotion — namespaced
    so it cannot collide with unrelated decision keys (Codex iter-2
    pin: bare `CNS-...` key forbidden)."""
    return f"consultation.{cns_id}"


def _compact_value(record: Mapping[str, Any]) -> dict[str, Any]:
    """Metadata-only value. The full response corpus lives on disk
    under the evidence directory — canonical store carries an
    index-shaped pointer plus provenance."""
    return {
        "cns_id": record["cns_id"],
        "topic": record.get("topic", ""),
        "from_agent": record.get("from_agent", ""),
        "to_agent": record.get("to_agent", ""),
        "final_verdict": record["final_verdict"],
        "resolved_at": record.get("resolved_at"),
    }


def _provenance(
    cns_id: str,
    record_dig: str,
) -> dict[str, Any]:
    """Workspace-relative pointer + record digest for dereferencing."""
    return {
        "method": "consultation_promotion",
        "cns_id": cns_id,
        "evidence_path": f".ao/evidence/consultations/{cns_id}",
        "resolution_record_path": (f".ao/evidence/consultations/{cns_id}/resolution.record.v1.json"),
        "record_digest": record_dig,
    }


def _load_record(cns_dir: Path) -> Mapping[str, Any] | None:
    record_path = cns_dir / "resolution.record.v1.json"
    if not record_path.is_file():
        return None
    try:
        parsed: Any = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def promote_resolved_consultations(
    workspace_root: Path,
    policy: Mapping[str, Any],
    *,
    dry_run: bool = False,
    force: bool = False,
) -> PromotionSummary:
    """Scan evidence directories and promote eligible CNS records.

    Args:
        workspace_root: Workspace root (``.ao/evidence/consultations``
            relative paths resolve under this).
        policy: Consultation policy dict (``promotion.enabled`` gates
            the operation unless ``force=True``).
        dry_run: When True, counts what WOULD be promoted without
            invoking ``promote_decision``.
        force: When True, bypasses the ``promotion.enabled=false``
            policy gate. Does NOT bypass integrity, eligibility, or
            idempotency checks.
    """
    promotion_cfg = policy.get("promotion") or {}
    enabled = bool(promotion_cfg.get("enabled", False))

    counters = {
        "scanned": 0,
        "eligible": 0,
        "promoted": 0,
        "updated": 0,
        "skipped_same_digest": 0,
        "skipped_integrity": 0,
        "skipped_ineligible": 0,
        "skipped_disabled": 0,
        "skipped_missing_record": 0,
    }
    errors: list[str] = []

    if not enabled and not force:
        counters["skipped_disabled"] = 1
        return PromotionSummary(
            **counters,
            errors=tuple(errors),
            dry_run=dry_run,
        )

    evidence_root = workspace_root / ".ao" / "evidence" / "consultations"
    # Codex iter-3 execution note #2: empty workspace → clean summary
    if not evidence_root.is_dir():
        return PromotionSummary(
            **counters,
            errors=tuple(errors),
            dry_run=dry_run,
        )

    store = load_store(workspace_root)
    existing_decisions = store.get("decisions", {}) or {}

    for cns_dir in sorted(evidence_root.iterdir()):
        if not cns_dir.is_dir() or cns_dir.name.startswith("."):
            continue
        counters["scanned"] += 1

        # Integrity gate
        ok, verify_errors = verify_consultation_manifest(cns_dir)
        if not ok:
            counters["skipped_integrity"] += 1
            for err in verify_errors:
                errors.append(f"{cns_dir.name}: {err}")
            continue

        # Load record (Codex iter-3 note #3 — visible counter, not silent)
        record = _load_record(cns_dir)
        if record is None:
            counters["skipped_missing_record"] += 1
            errors.append(f"{cns_dir.name}: resolution.record.v1.json missing")
            continue

        # Eligibility
        if record.get("status") != "resolved":
            counters["skipped_ineligible"] += 1
            continue
        final_verdict = record.get("final_verdict")
        if final_verdict not in _PROMOTABLE_VERDICTS:
            counters["skipped_ineligible"] += 1
            continue
        counters["eligible"] += 1

        cns_id = record["cns_id"]
        key = _store_key(cns_id)
        digest_hex = record_digest(record)
        prefixed_digest = f"sha256:{digest_hex}"

        # Idempotency
        existing = existing_decisions.get(key)
        is_update = False
        if isinstance(existing, dict):
            existing_digest = existing.get("provenance", {}).get("record_digest")
            if existing_digest == prefixed_digest:
                counters["skipped_same_digest"] += 1
                continue
            is_update = True

        if dry_run:
            # Still differentiate "would-promote" vs "would-update"
            if is_update:
                counters["updated"] += 1
            else:
                counters["promoted"] += 1
            continue

        promote_decision(
            workspace_root,
            key=key,
            value=_compact_value(record),
            category="consultation",
            source="consultation_archive",
            confidence=verdict_confidence(final_verdict),
            provenance=_provenance(cns_id, prefixed_digest),
        )
        if is_update:
            counters["updated"] += 1
        else:
            counters["promoted"] += 1

    return PromotionSummary(
        **counters,
        errors=tuple(errors),
        dry_run=dry_run,
    )


# ─── v3.6 E1 — Consumer-side reader facade ──────────────────────────────


@dataclass(frozen=True)
class PromotedConsultation:
    """Typed record for a promoted consultation entry in the canonical
    store.

    Hydration policy (strict core, lenient edges — v3.6 plan §3.E1 +
    Codex iter-1 revision #1 absorb):

    - ``cns_id``, ``final_verdict`` and ``promoted_at`` are STRICT
      CORE: any missing field causes the row to be silently SKIPPED
      in :func:`query_promoted_consultations`.
    - ``topic`` / ``from_agent`` / ``to_agent`` are None-tolerant here
      because the producer already backfills ``"unknown"`` for missing
      request metadata (see ``normalize.py::334``).
    - ``confidence`` is read from the top-level canonical entry; if
      absent, the reader derives it via :func:`verdict_confidence`.
    - ``record_digest`` / ``evidence_path`` come from
      ``provenance``; None when absent (no fallback derivation).

    Rationale: canonical store has no category registry / schema
    validation today (v3.7+ scope). A reader that panics on any
    malformation would be the wrong failure mode for the consumer
    path — it would propagate upstream producer bugs as hard failures
    in context compilation and MCP query surfaces.
    """

    cns_id: str
    topic: str | None
    from_agent: str | None
    to_agent: str | None
    final_verdict: str
    resolved_at: str | None
    record_digest: str | None
    evidence_path: str | None
    confidence: float
    promoted_at: str


_HYDRATION_REQUIRED = ("cns_id", "final_verdict", "promoted_at")


def _hydrate_consultation(
    entry: Mapping[str, Any],
) -> PromotedConsultation | None:
    """Hydrate a canonical-store row into a ``PromotedConsultation``.

    Returns ``None`` when any strict-core field is missing; callers
    skip those rows silently.
    """
    value = entry.get("value") or {}
    if not isinstance(value, Mapping):
        return None

    cns_id = value.get("cns_id") if isinstance(value.get("cns_id"), str) else None
    final_verdict = value.get("final_verdict") if isinstance(value.get("final_verdict"), str) else None
    promoted_at = entry.get("promoted_at") if isinstance(entry.get("promoted_at"), str) else None
    if not cns_id or not final_verdict or not promoted_at:
        return None

    provenance = entry.get("provenance") or {}
    if not isinstance(provenance, Mapping):
        provenance = {}

    # Lenient edge fields — nullable when absent.
    topic_raw = value.get("topic")
    topic: str | None = topic_raw if isinstance(topic_raw, str) and topic_raw else None
    from_agent_raw = value.get("from_agent")
    from_agent: str | None = from_agent_raw if isinstance(from_agent_raw, str) and from_agent_raw else None
    to_agent_raw = value.get("to_agent")
    to_agent: str | None = to_agent_raw if isinstance(to_agent_raw, str) and to_agent_raw else None
    resolved_at_raw = value.get("resolved_at")
    resolved_at: str | None = resolved_at_raw if isinstance(resolved_at_raw, str) else None
    record_digest_raw = provenance.get("record_digest")
    record_digest: str | None = record_digest_raw if isinstance(record_digest_raw, str) else None
    evidence_path_raw = provenance.get("evidence_path")
    evidence_path: str | None = evidence_path_raw if isinstance(evidence_path_raw, str) else None

    confidence_raw = entry.get("confidence")
    if isinstance(confidence_raw, (int, float)):
        confidence = float(confidence_raw)
    else:
        confidence = verdict_confidence(final_verdict)

    return PromotedConsultation(
        cns_id=cns_id,
        topic=topic,
        from_agent=from_agent,
        to_agent=to_agent,
        final_verdict=final_verdict,
        resolved_at=resolved_at,
        record_digest=record_digest,
        evidence_path=evidence_path,
        confidence=confidence,
        promoted_at=promoted_at,
    )


def query_promoted_consultations(
    workspace_root: Path,
    *,
    verdict: str | None = None,
    topic: str | None = None,
    include_expired: bool = False,
) -> tuple[PromotedConsultation, ...]:
    """Query promoted consultations from the canonical store as typed
    records.

    Thin, consumer-safe wrapper over
    :func:`ao_kernel.context.canonical_store.query` with
    ``category="consultation"``. Rows that cannot be hydrated (strict
    core field missing) are silently SKIPPED — the reader never
    raises on malformed store content (v3.6 plan §3.E1 hydration
    policy).

    When two canonical rows resolve to the same ``cns_id``, the
    more recent ``promoted_at`` wins — a last line of defence
    against future store-format drift (Codex iter-1 revision #7
    absorb). Canonical key uniqueness is enforced upstream on the
    happy path, so this dedup is rarely exercised but guards the
    contract.

    Args:
        workspace_root: Workspace root (``.ao/canonical_decisions.v1.json``
            lives under this).
        verdict: Optional filter (``AGREE`` / ``PARTIAL``); case-
            sensitive match against ``final_verdict``.
        topic: Optional case-insensitive substring filter on the
            ``topic`` field (``None`` topic rows never match).
        include_expired: When True, expired entries are included;
            default False respects the canonical temporal lifecycle.

    Returns:
        Tuple of :class:`PromotedConsultation` records sorted by
        ``promoted_at`` descending (newest first). Empty tuple when
        the store is empty or has no consultation entries.
    """
    raw = canonical_query(
        workspace_root,
        key_pattern="consultation.*",
        category="consultation",
        include_expired=include_expired,
    )

    by_id: dict[str, PromotedConsultation] = {}
    for row in raw:
        hydrated = _hydrate_consultation(row)
        if hydrated is None:
            continue
        if verdict is not None and hydrated.final_verdict != verdict:
            continue
        if topic is not None:
            haystack = (hydrated.topic or "").lower()
            if topic.lower() not in haystack:
                continue
        existing = by_id.get(hydrated.cns_id)
        if existing is None or hydrated.promoted_at > existing.promoted_at:
            by_id[hydrated.cns_id] = hydrated

    sorted_records = sorted(
        by_id.values(),
        key=lambda rec: rec.promoted_at,
        reverse=True,
    )
    return tuple(sorted_records)


__all__ = [
    "PromotedConsultation",
    "PromotionSummary",
    "promote_resolved_consultations",
    "query_promoted_consultations",
    "verdict_confidence",
]
