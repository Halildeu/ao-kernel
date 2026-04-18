"""Consultation migration (v3.5 D1).

Copy-forward migration from legacy `.cache/...` consultation directories
to the canonical `.ao/consultations/` layout. Idempotent + reversible:

- Source files are COPIED (not moved) so the operator retains a legacy
  backup until cutover.
- Pre-existing canonical files are NOT overwritten unless the operator
  passes ``--force``.
- A ``.ao/consultations/.migration_backup/`` directory receives a
  timestamped manifest of every file touched so the migration can be
  audited or reversed.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ao_kernel.consultation.paths import (
    FileClassification,
    is_file_artefact,
    iter_consultation_files,
    load_consultation_paths,
)


logger = logging.getLogger(__name__)


_ARTEFACT_TYPES = ("requests", "state", "responses", "config")


@dataclass(frozen=True)
class MigrationEntry:
    """Single file copy action (or skip)."""

    artefact: str
    source: Path
    target: Path
    status: str  # "copied" | "skipped_exists" | "skipped_invalid"
    classification: FileClassification


@dataclass(frozen=True)
class MigrationResult:
    entries: tuple[MigrationEntry, ...]
    backup_manifest: Path | None
    dry_run: bool

    @property
    def copied_count(self) -> int:
        return sum(1 for e in self.entries if e.status == "copied")

    @property
    def skipped_existing(self) -> int:
        return sum(1 for e in self.entries if e.status == "skipped_exists")

    @property
    def skipped_invalid(self) -> int:
        return sum(1 for e in self.entries if e.status == "skipped_invalid")


def _iso_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _backup_dir(workspace_root: Path) -> Path:
    return workspace_root / ".ao" / "consultations" / ".migration_backup"


def _write_backup_manifest(
    backup_dir: Path, entries: list[MigrationEntry],
) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    timestamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    manifest_path = backup_dir / f"migration-{timestamp}.json"
    payload = {
        "version": "v1",
        "migrated_at": _iso_now(),
        "entries": [
            {
                "artefact": e.artefact,
                "source": str(e.source),
                "target": str(e.target),
                "status": e.status,
                "classification": e.classification.value,
            }
            for e in entries
        ],
    }
    manifest_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return manifest_path


def migrate_consultations(
    policy: Mapping[str, Any],
    *,
    workspace_root: Path,
    dry_run: bool = False,
    force: bool = False,
    include_invalid: bool = False,
) -> MigrationResult:
    """Copy-forward legacy consultation artefacts to the canonical layout.

    Args:
        policy: Loaded ``policy_agent_consultation.v1.json`` dict.
        workspace_root: Absolute path to the workspace whose consultations
            need migrating.
        dry_run: When True, report actions without touching disk. Still
            reads legacy directories + classifies files.
        force: When True, overwrite pre-existing canonical files. By
            default the migration is non-destructive — canonical wins.
        include_invalid: When True, copy files flagged as INVALID_JSON
            anyway (so the operator can inspect them under canonical).
            Default False — invalid files surface in the result but are
            not copied.

    Returns a :class:`MigrationResult` summarizing every file touched
    plus the path to the backup manifest (None on dry-run).
    """
    paths = load_consultation_paths(policy, workspace_root=workspace_root)
    entries: list[MigrationEntry] = []

    for artefact in _ARTEFACT_TYPES:
        canonical = paths.canonical(artefact)
        # Directory artefacts → mkdir the directory;
        # File artefacts    → mkdir the parent only (not the file path).
        if not dry_run:
            if is_file_artefact(artefact):
                canonical.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            else:
                canonical.mkdir(parents=True, exist_ok=True, mode=0o700)

        for path, origin, classification in iter_consultation_files(
            policy, artefact, workspace_root=workspace_root,
        ):
            if origin != "legacy":
                continue  # already canonical

            # File artefact: target is the canonical path itself (fixed
            # filename); directory artefact: target = canonical/<name>.
            target = (
                canonical if is_file_artefact(artefact)
                else canonical / path.name
            )

            if classification == FileClassification.INVALID_JSON and not include_invalid:
                entries.append(MigrationEntry(
                    artefact=artefact,
                    source=path,
                    target=target,
                    status="skipped_invalid",
                    classification=classification,
                ))
                continue

            if target.exists() and not force:
                entries.append(MigrationEntry(
                    artefact=artefact,
                    source=path,
                    target=target,
                    status="skipped_exists",
                    classification=classification,
                ))
                continue

            if not dry_run:
                shutil.copy2(path, target)

            entries.append(MigrationEntry(
                artefact=artefact,
                source=path,
                target=target,
                status="copied",
                classification=classification,
            ))

    backup_manifest: Path | None = None
    if not dry_run and entries:
        backup_manifest = _write_backup_manifest(
            _backup_dir(workspace_root), entries,
        )

    return MigrationResult(
        entries=tuple(entries),
        backup_manifest=backup_manifest,
        dry_run=dry_run,
    )


__all__ = [
    "MigrationEntry",
    "MigrationResult",
    "migrate_consultations",
]
