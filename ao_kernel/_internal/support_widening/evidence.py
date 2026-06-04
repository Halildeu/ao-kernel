"""Support widening evidence v1 — pure parse / recompute / verify (V5 Epic 3 E-3-1).

Infrastructure-only. The schema pins ``support_widening: false`` (and the other
guard flags) as ``const false``; this module **re-asserts** those pins at runtime
(ADR-0002 recompute-not-trust corollary) so a forged payload that somehow slipped a
flipped flag past the schema is still rejected.

  - ``parse_v1(payload, *, schema)`` — JSON-Schema validate + runtime pin re-assert.
  - ``recompute_v1(payload)`` — re-derive ``evidence_dimensions`` from
    ``recompute_inputs.raw_dimensions`` (never trust the stored value) and reject
    any forbidden-widening key inside ``recompute_inputs`` at any depth.
  - ``verify_v1(payload, *, on_disk_refs)`` — re-hash every on-disk ref FROM DISK
    and confirm it matches the declared digest; combine parse + recompute into one
    fail-closed verdict.

No I/O at the parse/recompute boundary; the only disk reads are in ``verify_v1``,
which re-hashes (never trusts a stored hash).
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

# Guard-flag / authority pins re-asserted at runtime (must match the schema consts).
_RUNTIME_PINS: dict[str, Any] = {
    "schema_version": "support_widening_evidence.v1",
    "artifact_kind": "support_widening_evidence",
    "support_widening": False,
    "production_platform_claim": False,
    "live_adapter_execution": False,
    "github_write_authorized": False,
    "register_authority": "evidence_record_only",
    "simulated_only": True,
    "live_call_made": False,
}

# A recompute_inputs key matching this (at any depth) would be a shadow-widening
# back-door; the module rejects it regardless of the stored value.
_FORBIDDEN_WIDENING = re.compile(
    r"(?i)(support[_-]?widening|widening[_-]?authorized|live[_-]?adapter[_-]?execution"
    r"|production[_-]?platform[_-]?claim|github[_-]?write[_-]?authorized)"
)


class SupportWideningEvidenceError(ValueError):
    """Raised when a support-widening evidence payload fails validation (fail-closed)."""


def _iter_keys(obj: Any) -> "list[str]":
    """Every dict key appearing anywhere in ``obj`` (recursive)."""
    found: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            found.append(key)
            found.extend(_iter_keys(value))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_iter_keys(item))
    return found


def parse_v1(payload: dict[str, Any], *, schema: dict[str, Any]) -> dict[str, Any]:
    """Validate ``payload`` against ``schema`` and re-assert the runtime pins.

    Raises ``SupportWideningEvidenceError`` on the first failure (fail-closed).
    Returns ``payload`` unchanged on success.
    """
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda e: list(e.absolute_path))
    if errors:
        joined = "; ".join(f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in errors)
        raise SupportWideningEvidenceError(f"schema validation failed: {joined}")
    for key, expected in _RUNTIME_PINS.items():
        if payload.get(key) != expected:
            raise SupportWideningEvidenceError(
                f"runtime pin re-assert failed: {key!r} must be {expected!r}, got {payload.get(key)!r}"
            )
    return payload


def recompute_v1(payload: dict[str, Any]) -> dict[str, Any]:
    """Re-derive ``evidence_dimensions`` from ``recompute_inputs.raw_dimensions``.

    The stored ``evidence_dimensions`` is NEVER trusted: it must be byte-for-byte
    (canonical-JSON) equal to what we re-derive from the raw inputs. Also rejects any
    forbidden-widening key anywhere inside ``recompute_inputs``.

    Returns the recomputed ``evidence_dimensions``; raises on mismatch / forbidden key.
    """
    recompute_inputs = payload.get("recompute_inputs")
    if not isinstance(recompute_inputs, dict):
        raise SupportWideningEvidenceError("recompute_inputs missing or not an object")

    for key in _iter_keys(recompute_inputs):
        if _FORBIDDEN_WIDENING.search(key):
            raise SupportWideningEvidenceError(
                f"recompute_inputs carries a forbidden widening key: {key!r} (shadow-widening guard)"
            )

    raw = recompute_inputs.get("raw_dimensions")
    if not isinstance(raw, dict):
        raise SupportWideningEvidenceError("recompute_inputs.raw_dimensions missing or not an object")

    # v1 recompute contract: evidence_dimensions is re-derived as the canonical form
    # of the raw inputs (identity-with-validation). v2 adds real aggregation here.
    recomputed: dict[str, Any] = {str(k): v for k, v in raw.items()}
    stored = payload.get("evidence_dimensions")
    if json.dumps(recomputed, sort_keys=True) != json.dumps(stored, sort_keys=True):
        raise SupportWideningEvidenceError(
            "evidence_dimensions does not match recompute_inputs.raw_dimensions (recompute-not-trust)"
        )
    return recomputed


def verify_v1(
    payload: dict[str, Any],
    *,
    schema: dict[str, Any],
    on_disk_refs: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Full fail-closed verification: parse + recompute + re-hash on-disk refs.

    ``on_disk_refs`` maps a declared ``sha256:<hex>`` digest to a filesystem path; each
    path is read and re-hashed FROM DISK and must match the declared digest. Returns a
    report ``{"valid": True, "recomputed": {...}, "refs_verified": [...]}``; raises on
    any failure.
    """
    parse_v1(payload, schema=schema)
    recomputed = recompute_v1(payload)

    verified: list[str] = []
    for declared, path_str in (on_disk_refs or {}).items():
        if not declared.startswith("sha256:"):
            raise SupportWideningEvidenceError(f"on-disk ref digest must be sha256:-prefixed, got {declared!r}")
        path = Path(path_str)
        if not path.is_file():
            raise SupportWideningEvidenceError(f"on-disk ref path missing: {path_str}")
        actual = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != declared:
            raise SupportWideningEvidenceError(
                f"on-disk ref digest mismatch for {path_str}: declared {declared}, recomputed {actual}"
            )
        verified.append(path_str)

    return {"valid": True, "recomputed": recomputed, "refs_verified": verified}
