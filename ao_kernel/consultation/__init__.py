"""Consultation surface — CNS (adversarial agent consultation) contract.

This package provides the canonical path + schema + validation helpers
for the CNS workflow. Historical pre-v3.5 workspaces used `.cache/...`
directories for consultation artefacts; v3.5 canonicalizes the layout
under `.ao/consultations/` and keeps the old paths as read-only
fallbacks during a copy-forward migration.

Public surface:

- :mod:`ao_kernel.consultation.paths` — canonical path resolver +
  legacy-read fallback
- :func:`ao_kernel.consultation.paths.resolve_consultation_dir` — return
  the canonical directory for a given artefact type
- :func:`ao_kernel.consultation.paths.iter_consultation_files` — walk
  canonical + legacy locations, classify by shape
"""

from __future__ import annotations

from ao_kernel.consultation.migrate import (
    MigrationEntry,
    MigrationResult,
    migrate_consultations,
)
from ao_kernel.consultation.paths import (
    ConsultationPaths,
    FileClassification,
    iter_consultation_files,
    load_consultation_paths,
    resolve_consultation_dir,
)


__all__ = [
    "ConsultationPaths",
    "FileClassification",
    "MigrationEntry",
    "MigrationResult",
    "iter_consultation_files",
    "load_consultation_paths",
    "migrate_consultations",
    "resolve_consultation_dir",
]
