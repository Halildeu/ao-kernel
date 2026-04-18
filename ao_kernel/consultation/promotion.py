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
from ao_kernel.context.canonical_store import load_store, promote_decision


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
    cns_id: str, record_dig: str,
) -> dict[str, Any]:
    """Workspace-relative pointer + record digest for dereferencing."""
    return {
        "method": "consultation_promotion",
        "cns_id": cns_id,
        "evidence_path": f".ao/evidence/consultations/{cns_id}",
        "resolution_record_path": (
            f".ao/evidence/consultations/{cns_id}/resolution.record.v1.json"
        ),
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
            **counters, errors=tuple(errors), dry_run=dry_run,
        )

    evidence_root = (
        workspace_root / ".ao" / "evidence" / "consultations"
    )
    # Codex iter-3 execution note #2: empty workspace → clean summary
    if not evidence_root.is_dir():
        return PromotionSummary(
            **counters, errors=tuple(errors), dry_run=dry_run,
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
            errors.append(
                f"{cns_dir.name}: resolution.record.v1.json missing"
            )
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
            existing_digest = (
                existing.get("provenance", {}).get("record_digest")
            )
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
        **counters, errors=tuple(errors), dry_run=dry_run,
    )


__all__ = [
    "PromotionSummary",
    "promote_resolved_consultations",
    "verdict_confidence",
]
