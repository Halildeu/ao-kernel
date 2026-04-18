"""Consultation archive orchestrator (v3.5 D2a).

Scans CNS corpus, snapshots request/response files under
``.ao/evidence/consultations/<CNS-ID>/``, emits events (with
persistent dedupe), builds + writes resolution record, refreshes
integrity manifest + archive-meta.

Idempotent per Codex iter-4 AGREE:
- Same source + same normalizer_version → event append skipped
- Resolution record overwritten only when content digest changes
- Per-CNS file_lock serializes concurrent archive runs
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ao_kernel._internal.shared.lock import file_lock
from ao_kernel._internal.shared.utils import (
    sha256_file,
    write_json_atomic,
)
from ao_kernel.consultation.evidence import (
    ConsultationEventKind,
    append_event,
    preload_event_identities,
)
from ao_kernel.consultation.integrity import (
    write_archive_meta,
    write_consultation_manifest,
)
from ao_kernel.consultation.normalize import (
    NORMALIZER_VERSION,
    build_resolution_record,
    record_to_dict,
)
from ao_kernel.consultation.paths import (
    FileClassification,
    iter_consultation_files,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CnsArchiveResult:
    cns_id: str
    evidence_dir: Path
    events_appended: int
    record_written: bool
    manifest_written: bool
    errors: tuple[str, ...]


@dataclass(frozen=True)
class ArchiveSummary:
    scanned_cns: int
    archived: int
    errors_total: int
    results: tuple[CnsArchiveResult, ...]
    dry_run: bool


def _extract_cns_id(path: Path) -> str | None:
    """Extract the full CNS id from a file.

    SSOT: the ``consultation_id`` field inside the JSON document
    (Codex D2a iter-6 BLOCK absorb — historical corpus has suffixed
    ids like ``CNS-20260416-028v2`` that a naive filename regex
    truncates). Only when the file is unreadable / invalid JSON does
    the function fall back to the filename's first dot-segment, which
    preserves suffixes for INVALID_JSON cases.
    """
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(doc, dict):
            doc_id = doc.get("consultation_id")
            if isinstance(doc_id, str) and doc_id.startswith("CNS-"):
                return doc_id
    except (OSError, json.JSONDecodeError):
        pass
    # Fallback: filename first segment (preserves suffixes like v2)
    first_segment = path.name.split(".", 1)[0]
    if first_segment.startswith("CNS-"):
        return first_segment
    return None


def _evidence_dir(
    workspace_root: Path, cns_id: str,
) -> Path:
    return (
        workspace_root / ".ao" / "evidence" / "consultations" / cns_id
    ).resolve()


def _copy_snapshot(src: Path, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    dest = target_dir / src.name
    shutil.copy2(src, dest)
    return dest


def _group_files_by_cns(
    policy: Mapping[str, Any],
    workspace_root: Path,
    artefact: str,
) -> dict[str, list[tuple[Path, FileClassification]]]:
    """Walk canonical + legacy for ``artefact``, bucket by cns_id.

    Codex D2a iter-7 BLOCK absorb: during the D1 migration window the
    same source filename can appear in BOTH ``.ao/consultations/*``
    (canonical) and ``.cache/...`` (legacy). Without dedupe the
    archive would produce duplicate snapshot copies, duplicate record
    entries, and a last-write-wins overwrite on the snapshot target.
    This function keeps ``origin`` visible and drops the legacy copy
    whenever a canonical sibling with the same filename already
    exists — canonical wins, legacy only when canonical is missing.
    """
    # Gather per (cns_id, filename) with origin metadata so we can
    # apply canonical-wins dedupe after the full walk.
    raw: dict[str, dict[str, tuple[Path, FileClassification, str]]] = {}
    for path, origin, classification in iter_consultation_files(
        policy, artefact, workspace_root=workspace_root,
    ):
        cns_id = _extract_cns_id(path)
        if cns_id is None:
            continue
        per_cns = raw.setdefault(cns_id, {})
        key = path.name
        existing = per_cns.get(key)
        if existing is None:
            per_cns[key] = (path, classification, origin)
            continue
        # Canonical wins; legacy only fills when no canonical entry yet.
        _, _, existing_origin = existing
        if existing_origin == "legacy" and origin == "canonical":
            per_cns[key] = (path, classification, origin)
        # else: keep the first-seen canonical (or first legacy if canonical absent)
    groups: dict[str, list[tuple[Path, FileClassification]]] = {}
    for cns_id, by_name in raw.items():
        groups[cns_id] = [
            (entry[0], entry[1]) for entry in by_name.values()
        ]
    return groups


def _digest_record(record_dict: Mapping[str, Any]) -> str:
    """SHA-256 over canonical-JSON record content."""
    canonical = json.dumps(
        record_dict, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _archive_cns(
    *,
    policy: Mapping[str, Any],
    workspace_root: Path,
    cns_id: str,
    request_paths: list[tuple[Path, FileClassification]],
    response_paths: list[tuple[Path, FileClassification]],
    dry_run: bool,
    renormalize: bool,
) -> CnsArchiveResult:
    """Archive a single CNS: snapshot, emit events, build record,
    refresh manifest + meta."""
    evidence_dir = _evidence_dir(workspace_root, cns_id)
    errors: list[str] = []

    if dry_run:
        return CnsArchiveResult(
            cns_id=cns_id,
            evidence_dir=evidence_dir,
            events_appended=0,
            record_written=False,
            manifest_written=False,
            errors=(),
        )

    evidence_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = evidence_dir / ".archive.lock"

    with file_lock(lock_path):
        events_path = evidence_dir / "events.jsonl"
        seen = preload_event_identities(events_path)
        if renormalize:
            # Operator-triggered: rebuild record even if identity matches.
            # We still keep persistent event dedupe; the record overwrite
            # below unconditionally re-derives.
            pass

        events_appended = 0

        # Snapshot + emit source-based events for requests
        request_snapshots: list[tuple[Path, str]] = []
        for src, classification in sorted(request_paths, key=lambda t: t[0].name):
            snap_dest = _copy_snapshot(src, evidence_dir / "requests")
            rel = str(snap_dest.relative_to(evidence_dir))
            request_snapshots.append((snap_dest, rel))

            # Parse minimum metadata for the initial request
            try:
                doc = json.loads(src.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                doc = {}

            iteration = _iteration_from_name(src.name)
            source_sha = sha256_file(snap_dest)

            kind = (
                ConsultationEventKind.OPENED
                if iteration == 1
                else ConsultationEventKind.REQUEST_REVISED
            )
            payload = {
                "cns_id": cns_id,
                "source_path": rel,
                "source_sha256": source_sha,
                "source_classification": classification.value,
                "iteration": iteration,
                "normalizer_version": NORMALIZER_VERSION,
            }
            if iteration == 1:
                payload["topic"] = str(doc.get("topic", ""))
                payload["from_agent"] = str(doc.get("from_agent", ""))
                payload["to_agent"] = str(doc.get("to_agent", ""))
            if classification == FileClassification.INVALID_JSON:
                kind = ConsultationEventKind.INVALID

            if append_event(events_path, kind=kind, payload=payload, seen=seen):
                events_appended += 1

        # Snapshot + emit response events
        response_snapshots: list[tuple[Path, str]] = []
        for src, classification in sorted(response_paths, key=lambda t: t[0].name):
            snap_dest = _copy_snapshot(src, evidence_dir / "responses")
            rel = str(snap_dest.relative_to(evidence_dir))
            response_snapshots.append((snap_dest, rel))

            iteration = _iteration_from_name(src.name)
            source_sha = sha256_file(snap_dest)

            kind = (
                ConsultationEventKind.INVALID
                if classification == FileClassification.INVALID_JSON
                else ConsultationEventKind.RESPONSE_RECEIVED
            )
            payload = {
                "cns_id": cns_id,
                "source_path": rel,
                "source_sha256": source_sha,
                "source_classification": classification.value,
                "iteration": iteration,
                "normalizer_version": NORMALIZER_VERSION,
            }
            if append_event(events_path, kind=kind, payload=payload, seen=seen):
                events_appended += 1

        # Resolve initial request doc for record metadata
        initial_req_doc: dict[str, Any] = {}
        for src, _cls in request_paths:
            if _iteration_from_name(src.name) == 1:
                try:
                    initial_req_doc = json.loads(src.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    initial_req_doc = {}
                break

        # Build record
        record = build_resolution_record(
            cns_id=cns_id,
            request_snapshots=request_snapshots,
            response_snapshots=response_snapshots,
            request_doc_for_meta=initial_req_doc,
        )
        record_dict = record_to_dict(record)
        record_digest = _digest_record(record_dict)

        record_path = evidence_dir / "resolution.record.v1.json"
        record_written = False
        if not record_path.is_file() or renormalize:
            write_json_atomic(record_path, record_dict)
            record_written = True
        else:
            existing = json.loads(record_path.read_text(encoding="utf-8"))
            existing_digest = _digest_record(existing)
            if existing_digest != record_digest:
                write_json_atomic(record_path, record_dict)
                record_written = True

        # Emit normalized event (identity dedupe on record digest)
        if append_event(
            events_path,
            kind=ConsultationEventKind.NORMALIZED,
            payload={
                "cns_id": cns_id,
                "resolution_record_path": str(
                    record_path.relative_to(evidence_dir),
                ),
                "resolution_record_digest": f"sha256:{record_digest}",
                "final_verdict": record.final_verdict.value,
                "iterations_count": len(record.requests),
                "status": record.status.value,
                "normalizer_version": NORMALIZER_VERSION,
            },
            seen=seen,
        ):
            events_appended += 1

        # Archive meta (always overwritten — drift expected)
        write_archive_meta(evidence_dir)

        # Integrity manifest refresh
        write_consultation_manifest(evidence_dir)

    return CnsArchiveResult(
        cns_id=cns_id,
        evidence_dir=evidence_dir,
        events_appended=events_appended,
        record_written=record_written,
        manifest_written=True,
        errors=tuple(errors),
    )


def _iteration_from_name(name: str) -> int:
    from ao_kernel.consultation.normalize import iteration_from_filename
    return iteration_from_filename(name)


def archive_all(
    policy: Mapping[str, Any],
    *,
    workspace_root: Path,
    dry_run: bool = False,
    renormalize: bool = False,
) -> ArchiveSummary:
    """Walk the CNS corpus + archive each into evidence dir."""
    req_groups = _group_files_by_cns(policy, workspace_root, "requests")
    resp_groups = _group_files_by_cns(policy, workspace_root, "responses")

    all_cns_ids = sorted(set(req_groups.keys()) | set(resp_groups.keys()))
    results: list[CnsArchiveResult] = []
    archived = 0
    errors_total = 0

    for cns_id in all_cns_ids:
        req_paths = req_groups.get(cns_id, [])
        resp_paths = resp_groups.get(cns_id, [])
        result = _archive_cns(
            policy=policy,
            workspace_root=workspace_root,
            cns_id=cns_id,
            request_paths=req_paths,
            response_paths=resp_paths,
            dry_run=dry_run,
            renormalize=renormalize,
        )
        results.append(result)
        errors_total += len(result.errors)
        if (
            result.events_appended > 0
            or result.record_written
            or result.manifest_written
        ):
            archived += 1

    return ArchiveSummary(
        scanned_cns=len(all_cns_ids),
        archived=archived,
        errors_total=errors_total,
        results=tuple(results),
        dry_run=dry_run,
    )


__all__ = [
    "CnsArchiveResult",
    "ArchiveSummary",
    "archive_all",
]
