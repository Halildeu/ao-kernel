"""Consultation path resolver (v3.5 D1).

Resolves CNS artefact locations from ``policy_agent_consultation.v1.json``.
v3.5 canonicalizes the layout under ``.ao/consultations/`` (matching the
repo practice that had drifted from the pre-v3.5 `.cache/...` policy
declaration). Legacy `.cache/...` paths are preserved as read-only
fallbacks during the copy-forward migration window.

Read order (for any artefact type):
1. Canonical path (`.ao/consultations/<type>/`)
2. Legacy fallback (`.cache/...`) when the policy declares one

Write order:
- Canonical only. Writes never go to legacy paths (copy-forward, not
  in-place move). The migration script (``ao-kernel migrate
  consultations``) moves historical files to canonical and keeps a
  backup.

Scope boundary:
- This module resolves PATHS and classifies file shapes only.
- It does NOT emit evidence, normalize verdicts, or promote to the
  canonical decision store. Those live in future PRs (v3.5 D2a/D2b).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterator, Mapping


logger = logging.getLogger(__name__)


_ARTEFACT_KEYS = ("requests", "state", "responses", "config")

# Artefact shape: request/state/response are DIRECTORIES containing one
# JSON file per consultation; `config` is a SINGLE FILE (the agent
# dispatcher settings). Callers must not treat them symmetrically —
# resolver + migrator branch on `is_file_artefact`.
_FILE_ARTEFACTS = frozenset({"config"})


def is_file_artefact(artefact: str) -> bool:
    """Return True iff ``artefact`` is modeled as a single file, False
    if it is a directory of JSON files."""
    return artefact in _FILE_ARTEFACTS


@dataclass(frozen=True)
class ConsultationPaths:
    """Resolved directory layout for consultation artefacts.

    Attributes map each artefact type to its canonical workspace-relative
    path plus an optional legacy fallback. The policy loader populates
    this dataclass; callers pass it to helpers like
    :func:`iter_consultation_files`.
    """

    requests: Path
    state: Path
    responses: Path
    config: Path
    legacy_fallbacks: Mapping[str, Path]

    def canonical(self, artefact: str) -> Path:
        mapping = {
            "requests": self.requests,
            "state": self.state,
            "responses": self.responses,
            "config": self.config,
        }
        if artefact not in mapping:
            raise KeyError(
                f"unknown artefact type {artefact!r}; expected one of "
                f"{sorted(mapping)}"
            )
        return mapping[artefact]

    def legacy(self, artefact: str) -> Path | None:
        return self.legacy_fallbacks.get(artefact)


class FileClassification(str, Enum):
    """Shape assessment for a consultation response file.

    - ``VALID_CURRENT``: parses as JSON and matches the current shape
      (has ``consultation_id``, ``overall_verdict`` or equivalent).
    - ``LEGACY_SHAPE``: parses as JSON but is missing required keys the
      current schema mandates (e.g. no ``consultation_id``). Safe to
      archive via the migration script; NOT safe to promote.
    - ``INVALID_JSON``: fails to parse as JSON entirely. Surfaced as an
      error in migration output so the operator can repair by hand.

    Request files use a stricter gate (see
    :func:`classify_request_file`) — they are either valid or failed;
    there is no intermediate "legacy" bucket because requests have
    always carried ``consultation_id``.
    """

    VALID_CURRENT = "valid_current"
    LEGACY_SHAPE = "legacy_shape"
    INVALID_JSON = "invalid_json"


def load_consultation_paths(
    policy: Mapping[str, Any],
    *,
    workspace_root: Path,
) -> ConsultationPaths:
    """Parse the ``paths`` section of a consultation policy doc.

    Accepts either the v3.5 schema (with ``legacy_fallbacks``) or the
    pre-v3.5 shape (no fallbacks) — in the latter case the returned
    ``legacy_fallbacks`` mapping is empty. This keeps the helper
    forward-compat for workspaces that ship an older override.
    """
    paths_doc = policy.get("paths") or {}
    missing = [k for k in _ARTEFACT_KEYS if k not in paths_doc]
    if missing:
        raise ValueError(
            f"consultation policy.paths missing required keys: {missing!r}"
        )

    def _abs(rel: str) -> Path:
        return (workspace_root / rel).resolve()

    legacy_raw = paths_doc.get("legacy_fallbacks") or {}
    legacy_fallbacks: dict[str, Path] = {}
    for key in _ARTEFACT_KEYS:
        if key in legacy_raw:
            legacy_fallbacks[key] = _abs(legacy_raw[key])

    return ConsultationPaths(
        requests=_abs(paths_doc["requests"]),
        state=_abs(paths_doc["state"]),
        responses=_abs(paths_doc["responses"]),
        config=_abs(paths_doc["config"]),
        legacy_fallbacks=legacy_fallbacks,
    )


def resolve_consultation_dir(
    policy: Mapping[str, Any],
    artefact: str,
    *,
    workspace_root: Path,
    prefer_legacy: bool = False,
) -> Path:
    """Return the effective DIRECTORY for a directory-shaped artefact.

    Only defined for ``requests``/``state``/``responses``. For
    ``config`` (single-file artefact), use
    :func:`resolve_consultation_path` instead.

    ``prefer_legacy=False`` (default, write path) — always returns the
    canonical path, even if the legacy directory is the only one that
    currently exists on disk. Callers that want to read from wherever
    content lives should pass ``prefer_legacy=True`` or use
    :func:`iter_consultation_files`.
    """
    if is_file_artefact(artefact):
        raise ValueError(
            f"artefact {artefact!r} is modeled as a file, not a directory; "
            "call resolve_consultation_path() instead"
        )
    paths = load_consultation_paths(policy, workspace_root=workspace_root)
    canonical = paths.canonical(artefact)
    if not prefer_legacy:
        return canonical
    if canonical.is_dir():
        return canonical
    legacy = paths.legacy(artefact)
    if legacy is not None and legacy.is_dir():
        return legacy
    return canonical  # does not exist yet; caller will mkdir


def resolve_consultation_path(
    policy: Mapping[str, Any],
    artefact: str,
    *,
    workspace_root: Path,
    prefer_legacy: bool = False,
) -> Path:
    """Return the effective FILE path for a file-shaped artefact.

    Only defined for ``config``. Canonical by default; falls back to
    legacy file path when ``prefer_legacy=True`` and the canonical
    file does not exist.
    """
    if not is_file_artefact(artefact):
        raise ValueError(
            f"artefact {artefact!r} is modeled as a directory, not a file; "
            "call resolve_consultation_dir() instead"
        )
    paths = load_consultation_paths(policy, workspace_root=workspace_root)
    canonical = paths.canonical(artefact)
    if not prefer_legacy:
        return canonical
    if canonical.is_file():
        return canonical
    legacy = paths.legacy(artefact)
    if legacy is not None and legacy.is_file():
        return legacy
    return canonical


def _iter_dir(path: Path) -> Iterator[Path]:
    if not path.is_dir():
        return
    yield from sorted(path.iterdir())


def classify_response_file(path: Path) -> FileClassification:
    """Shape classification for a response JSON file.

    Requires ``consultation_id`` for ``VALID_CURRENT``; files that parse
    but lack that key fall to ``LEGACY_SHAPE``.
    """
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return FileClassification.INVALID_JSON
    if not isinstance(doc, dict):
        return FileClassification.LEGACY_SHAPE
    if "consultation_id" not in doc:
        return FileClassification.LEGACY_SHAPE
    return FileClassification.VALID_CURRENT


def classify_request_file(path: Path) -> FileClassification:
    """Shape classification for a request JSON file.

    Request corpus is homogeneous historically; either the file parses
    with ``consultation_id`` (``VALID_CURRENT``) or it fails validation
    (``INVALID_JSON``). No ``LEGACY_SHAPE`` bucket.
    """
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return FileClassification.INVALID_JSON
    if not isinstance(doc, dict) or "consultation_id" not in doc:
        return FileClassification.INVALID_JSON
    return FileClassification.VALID_CURRENT


def iter_consultation_files(
    policy: Mapping[str, Any],
    artefact: str,
    *,
    workspace_root: Path,
) -> Iterator[tuple[Path, str, FileClassification]]:
    """Walk canonical + legacy locations for ``artefact``.

    Yields ``(path, origin, classification)`` tuples where ``origin`` is
    ``"canonical"`` or ``"legacy"``. Handles both directory artefacts
    (requests/state/responses — iterates children) and the single-file
    ``config`` artefact (yields the file itself if present).

    Classification uses the request/response classifier based on
    artefact type; ``state`` and ``config`` are reported as
    ``VALID_CURRENT`` when parseable.
    """
    paths = load_consultation_paths(policy, workspace_root=workspace_root)

    def _classify(path: Path) -> FileClassification:
        if artefact == "requests":
            return classify_request_file(path)
        if artefact == "responses":
            return classify_response_file(path)
        # state / config — best-effort parse
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return FileClassification.INVALID_JSON
        return FileClassification.VALID_CURRENT

    canonical = paths.canonical(artefact)
    legacy = paths.legacy(artefact)

    if is_file_artefact(artefact):
        # Single-file artefact: yield the file itself if present on
        # either side. Do not iterate children.
        if canonical.is_file():
            yield canonical, "canonical", _classify(canonical)
        if legacy is not None and legacy.is_file():
            yield legacy, "legacy", _classify(legacy)
        return

    # Directory artefact: iterate children on both sides.
    for path in _iter_dir(canonical):
        if path.is_file():
            yield path, "canonical", _classify(path)
    if legacy is not None:
        for path in _iter_dir(legacy):
            if path.is_file():
                yield path, "legacy", _classify(path)
