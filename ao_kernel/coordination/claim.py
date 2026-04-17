"""Coordination claim record + CAS helpers (PR-B1).

See ``docs/COORDINATION.md`` and ``ao_kernel/defaults/schemas/claim.
schema.v1.json`` for the durable contract. This module provides:

- :class:`Claim` — frozen dataclass mirror of the SSOT JSON shape.
- :func:`claim_revision` — canonical-JSON SHA-256 hash with the
  ``revision`` field omitted (matches ``canonical_store.store_revision``
  pattern).
- :func:`claim_to_dict` / :func:`claim_from_dict` — shape serialise /
  deserialise with fail-closed schema validation.
- :func:`save_claim_cas` — atomic write with ``expected_revision`` guard
  (the primary mutator for heartbeat and takeover flows).

SSOT parse / schema / hash failures raise :class:`ClaimCorruptedError`;
callers do NOT silently recover (W2v2 fail-closed scope).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ao_kernel._internal.shared.utils import write_text_atomic
from ao_kernel.config import load_default
from ao_kernel.coordination.errors import (
    ClaimCorruptedError,
    ClaimRevisionConflictError,
)


_CLAIM_SCHEMA_CACHE: dict[str, Any] | None = None


def _claim_schema() -> dict[str, Any]:
    """Load and cache ``claim.schema.v1.json`` for validation."""
    global _CLAIM_SCHEMA_CACHE
    if _CLAIM_SCHEMA_CACHE is None:
        _CLAIM_SCHEMA_CACHE = load_default("schemas", "claim.schema.v1.json")
    return _CLAIM_SCHEMA_CACHE


@dataclass(frozen=True)
class Claim:
    """A durable per-resource lease record.

    Mirrors ``claim.schema.v1.json``. ``expires_at`` is a DERIVED field
    (written for debug visibility); callers MUST NOT trust it past a
    heartbeat — recompute from ``heartbeat_at + policy.expiry_seconds``
    at evaluation time. ``revision`` is the CAS hash of the record with
    this field omitted (see :func:`claim_revision`).
    """

    claim_id: str
    owner_agent_id: str
    resource_id: str
    fencing_token: int
    acquired_at: str
    heartbeat_at: str
    revision: str
    expires_at: str | None = None


def claim_revision(claim_dict: Mapping[str, Any]) -> str:
    """Compute the canonical CAS revision hash.

    SHA-256 hex digest over ``sort_keys=True`` JSON of the claim dict
    with the ``revision`` field omitted. Matches the pattern used by
    :func:`ao_kernel.context.canonical_store.store_revision`.
    """
    projection = {k: v for k, v in claim_dict.items() if k != "revision"}
    payload = json.dumps(projection, sort_keys=True, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def claim_from_dict(doc: Mapping[str, Any], *, source_path: Path | None = None) -> Claim:
    """Deserialise + validate a claim JSON object.

    Raises :class:`ClaimCorruptedError` on:
        - Missing required fields (claim_id, owner_agent_id, resource_id,
          fencing_token, acquired_at, heartbeat_at, revision)
        - Wrong types
        - ``revision`` field does not match the recomputed canonical hash
          (detects silent edits to on-disk artefacts)

    ``source_path`` is a purely-informational argument used to build a
    meaningful error message; callers pass the path of the JSON file the
    dict came from when known.
    """
    try:
        from jsonschema import Draft202012Validator

        Draft202012Validator(_claim_schema()).validate(doc)
    except Exception as exc:  # jsonschema.exceptions.ValidationError + SchemaError
        raise ClaimCorruptedError(
            str(source_path) if source_path is not None else "<inline>",
            f"schema validation failed: {exc}",
        ) from exc

    stored_revision = doc["revision"]
    computed_revision = claim_revision(doc)
    if stored_revision != computed_revision:
        raise ClaimCorruptedError(
            str(source_path) if source_path is not None else "<inline>",
            f"revision hash mismatch: stored={stored_revision!r} "
            f"computed={computed_revision!r}",
        )

    return Claim(
        claim_id=doc["claim_id"],
        owner_agent_id=doc["owner_agent_id"],
        resource_id=doc["resource_id"],
        fencing_token=int(doc["fencing_token"]),
        acquired_at=doc["acquired_at"],
        heartbeat_at=doc["heartbeat_at"],
        expires_at=doc.get("expires_at"),
        revision=doc["revision"],
    )


def claim_to_dict(claim: Claim) -> dict[str, Any]:
    """Serialise a :class:`Claim` to a plain JSON-safe dict.

    Round-trip guarantee: ``claim_from_dict(claim_to_dict(c)) == c``
    holds for all valid claims (including those with ``expires_at=None``,
    which is serialised as the absent field).
    """
    d: dict[str, Any] = {
        "claim_id": claim.claim_id,
        "owner_agent_id": claim.owner_agent_id,
        "resource_id": claim.resource_id,
        "fencing_token": claim.fencing_token,
        "acquired_at": claim.acquired_at,
        "heartbeat_at": claim.heartbeat_at,
        "revision": claim.revision,
    }
    if claim.expires_at is not None:
        d["expires_at"] = claim.expires_at
    return d


def claim_path(workspace_root: Path, resource_id: str) -> Path:
    """Return the absolute path to the SSOT claim file for a resource."""
    return workspace_root / ".ao" / "claims" / f"{resource_id}.v1.json"


def save_claim_cas(
    workspace_root: Path,
    resource_id: str,
    new_claim_dict: Mapping[str, Any],
    *,
    expected_revision: str,
) -> None:
    """Atomically persist a claim record with a CAS revision guard.

    Contract:
        1. Load the existing on-disk claim (must exist; this helper is
           the heartbeat / takeover / update-in-place mutator).
        2. Compare the loaded revision against ``expected_revision``.
           Mismatch → :class:`ClaimRevisionConflictError`.
        3. Validate that ``new_claim_dict["revision"]`` equals the
           recomputed canonical hash of the new dict (the caller must
           have stamped the new revision before calling).
        4. ``write_text_atomic`` (tempfile + fsync + rename).

    Caller holds ``claims.lock`` for the full load-mutate-write cycle;
    this helper does NOT acquire the workspace lock itself.

    Raises:
        ClaimRevisionConflictError: On CAS mismatch.
        ClaimCorruptedError: If the new dict's stamped revision does
            not match its computed canonical hash (caller bug) or the
            existing on-disk record fails to parse.
    """
    path = claim_path(workspace_root, resource_id)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        # save_claim_cas is the update path; absent file should surface
        # as revision conflict (the claim was released under us).
        raise ClaimRevisionConflictError(
            resource_id,
            expected_revision,
            "<absent>",
        ) from exc
    except OSError as exc:
        raise ClaimCorruptedError(str(path), f"read failed: {exc}") from exc

    try:
        existing = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ClaimCorruptedError(str(path), f"JSON decode failed: {exc}") from exc

    actual_revision = existing.get("revision", "<missing>")
    if actual_revision != expected_revision:
        raise ClaimRevisionConflictError(resource_id, expected_revision, actual_revision)

    # Validate the new dict's stamped revision matches its computed hash.
    stamped = new_claim_dict.get("revision", "<missing>")
    computed = claim_revision(new_claim_dict)
    if stamped != computed:
        raise ClaimCorruptedError(
            str(path),
            f"new_claim_dict stamped revision {stamped!r} does not match "
            f"computed {computed!r} (caller must set revision to "
            f"claim_revision(dict) before calling save_claim_cas)",
        )

    payload = json.dumps(dict(new_claim_dict), sort_keys=True, ensure_ascii=False)
    write_text_atomic(path, payload)
