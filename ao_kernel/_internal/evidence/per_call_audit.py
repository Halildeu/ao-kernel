"""Per-call audit evidence writer (V5 Epic 2 E-2-2).

One JSONL row per (would-be) LLM call. The writer is a pure serializer:

  - It validates every row against ``per_call_audit.schema.v1.json`` and FAILS
    CLOSED (raises) on an invalid row — a missing/float cost, a flipped guard
    flag, or a ``soft_breached`` row without ``cost_breach_handling`` is never
    written (CLAUDE.md değişmez #1, fail-closed evidence path).
  - In **library mode** (``workspace_root is None``) it skips persistence and
    returns a receipt — the single-process contract, no on-disk evidence.
  - In **workspace mode** it appends atomically (fsync) to
    ``evidence/per_call_audit.jsonl``; a ``hard_breached`` row is ALSO appended
    to ``evidence/cost_hard_breach.jsonl`` so the failure path is
    cross-referenced.

The writer does NOT decide cost-ceiling breaches and does NOT raise
``CostCeilingExceeded`` — that is the E-2-3 cost-ceiling module, which calls
this writer (try-finally) to record the fail-closed audit row before raising.
This keeps E-2-2 free of a forward dependency on E-2-3.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default

_SCHEMA_NAME = "per_call_audit.schema.v1.json"
_AUDIT_JSONL = "per_call_audit.jsonl"
_HARD_BREACH_JSONL = "cost_hard_breach.jsonl"


class PerCallAuditValidationError(ValueError):
    """Raised when an audit row does not satisfy the schema (fail-closed)."""


def _validator() -> Draft202012Validator:
    return Draft202012Validator(load_default("schemas", _SCHEMA_NAME))


def _validate(row: dict[str, Any]) -> None:
    errors = sorted(_validator().iter_errors(row), key=lambda e: list(e.absolute_path))
    if errors:
        joined = "; ".join(f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in errors)
        raise PerCallAuditValidationError(f"per_call_audit row failed schema validation: {joined}")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    """Append one row as canonical JSON, fsync best-effort (mirrors the
    evidence writer's append contract: O_APPEND via 'a' + fsync)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            # fsync may be unsupported (network FS, bind mount). The row has
            # landed in the page cache; integrity verification stays the
            # authoritative check (mirrors evidence/writer.py).
            pass


def record_call(row: dict[str, Any], *, workspace_root: Path | None = None) -> dict[str, Any]:
    """Validate and (in workspace mode) persist one per-call audit row.

    Returns a receipt: ``{"persisted": bool, "mode": "library"|"workspace",
    "paths": [...]}``. Raises ``PerCallAuditValidationError`` on a schema-invalid
    row BEFORE any write (fail-closed) — so a malformed row never lands on disk.
    """
    _validate(row)  # fail-closed: invalid row raises before any write

    if workspace_root is None:
        return {"persisted": False, "mode": "library", "paths": []}

    evidence_dir = Path(workspace_root) / "evidence"
    written: list[str] = []

    audit_path = evidence_dir / _AUDIT_JSONL
    _append_jsonl(audit_path, row)
    written.append(str(audit_path))

    # A hard breach is also cross-referenced in a dedicated failure artifact so
    # the unconditional-abort path is auditable on its own (E-2-2 spec / F10).
    if row.get("cost_breach_state") == "hard_breached":
        breach_path = evidence_dir / _HARD_BREACH_JSONL
        _append_jsonl(breach_path, row)
        written.append(str(breach_path))

    return {"persisted": True, "mode": "workspace", "paths": written}
