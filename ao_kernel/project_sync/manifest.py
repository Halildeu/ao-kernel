"""Projection manifest load/save/digest helpers.

The projection manifest (``.claude/plans/v5_issue_projection.v1.json`` and
sibling files) is the authority binding between repo slices and the GitHub
mirror surface. This module treats it as a read-mostly dataclass with a
deterministic digest so drift checks and add-slice records can pin a stable
hash without re-implementing canonical JSON serialisation in each caller.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ao_kernel.project_sync.errors import ProjectSyncError


@dataclass(frozen=True)
class ProjectionManifest:
    """In-memory view of a v5 projection manifest.

    Frozen so callers cannot mutate the in-process copy. Round-trip via
    :py:meth:`save` to persist edits — the dataclass is intentionally a
    snapshot, not a live binding.
    """

    path: Path
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "ProjectionManifest":
        """Load a manifest from disk.

        Raises :class:`ProjectSyncError` if the file is missing or does not
        parse as a JSON object — fail-closed per CLAUDE.md §2.
        """
        if not path.is_file():
            raise ProjectSyncError(f"projection manifest not found: {path}")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ProjectSyncError(f"projection manifest is not valid JSON: {path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ProjectSyncError(f"projection manifest must be a JSON object: {path}")
        return cls(path=path, payload=raw)

    def save(self, *, indent: int = 2) -> None:
        """Persist the payload back to ``self.path`` deterministically.

        Uses canonical key order so the resulting file diff is stable across
        runs even when callers mutate via :py:meth:`with_payload`.
        """
        text = json.dumps(self.payload, indent=indent, sort_keys=True, ensure_ascii=False) + "\n"
        self.path.write_text(text, encoding="utf-8")

    def with_payload(self, payload: dict[str, Any]) -> "ProjectionManifest":
        """Return a new manifest pointing at the same path with new payload.

        ``ProjectionManifest`` is frozen, so callers building a sync mutation
        produce a fresh instance instead of in-place edits.
        """
        return ProjectionManifest(path=self.path, payload=payload)

    def digest(self) -> str:
        """Stable SHA-256 of the canonical JSON payload.

        Used by add-slice records to pin "the manifest looked like this when
        I added the slice" — drift checkers compare against this digest to
        decide whether to re-derive fields.
        """
        canonical = json.dumps(self.payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return "sha256:" + hashlib.sha256(canonical).hexdigest()

    def project_node_id(self) -> str | None:
        """Best-effort project board node id for downstream GraphQL calls.

        Returns ``None`` when the manifest has not been bound to a runtime
        project yet (e.g. first-time creation path).
        """
        runtime = self.payload.get("runtime_created_state")
        if not isinstance(runtime, dict):
            return None
        board = runtime.get("project_board")
        if not isinstance(board, dict):
            return None
        node_id = board.get("node_id")
        return node_id if isinstance(node_id, str) and node_id else None

    def project_number(self) -> int | None:
        """Best-effort project board number (used by ``gh project`` commands)."""
        runtime = self.payload.get("runtime_created_state")
        if not isinstance(runtime, dict):
            return None
        board = runtime.get("project_board")
        if not isinstance(board, dict):
            return None
        number = board.get("number")
        return number if isinstance(number, int) else None

    def issues_created(self) -> dict[str, int]:
        """Map of slice id (e.g. ``E-1``) to issue number.

        Empty dict when the runtime state has not been populated yet.
        """
        runtime = self.payload.get("runtime_created_state")
        if not isinstance(runtime, dict):
            return {}
        issues = runtime.get("issues_created")
        if not isinstance(issues, dict):
            return {}
        out: dict[str, int] = {}
        for key, value in issues.items():
            if isinstance(key, str) and isinstance(value, int):
                out[key] = value
        return out
