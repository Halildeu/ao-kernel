"""Persistent fencing-token state for coordination (PR-B1).

See ``docs/COORDINATION.md`` §4 Fencing Token and ``ao_kernel/defaults/
schemas/fencing-state.schema.v1.json`` for the durable contract. This
module is the authority for per-resource token issuance:

- :class:`FencingState` — in-memory immutable snapshot of
  ``_fencing.v1.json``.
- :func:`load_fencing_state` — parse + validate with SSOT fail-closed
  semantics.
- :func:`next_token` — pure function; returns issued token + new state
  snapshot (caller CAS-writes).
- :func:`update_on_release` — pure function; preserves ``next_token``,
  updates audit fields.
- :func:`validate_fencing_token` — **exact-equality** check: the
  supplied token must equal the currently-live issued token
  (``next_token - 1``); both stale and future tokens raise.
- :func:`fencing_state_revision` — runtime-only CAS hash (B0 schema is
  closed; ``revision`` field is NOT persisted).
- :func:`save_fencing_state_cas` — atomic write with CAS revision guard.

Invariants:
- Token is strictly monotonic non-negative int; never reset, never wraps
  (Python int is unbounded).
- Release deletes the claim file but RETAINS the per-resource fencing
  entry; only audit fields (``last_owner_agent_id``, ``last_released_at``)
  update. The token authority outlives any single claim lifetime.
- Takeover advances ``next_token`` by 1 (same flow as acquire).
- Forward-only recovery: the reconcile helper computes
  ``new_next = max(current_next_token, max_claim_fencing_token + 1)``;
  fencing state NEVER decreases.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from ao_kernel._internal.shared.utils import write_text_atomic
from ao_kernel.config import load_default
from ao_kernel.coordination.errors import (
    ClaimCorruptedError,
    ClaimRevisionConflictError,
    ClaimStaleFencingError,
)


_FENCING_SCHEMA_CACHE: dict[str, Any] | None = None


def _fencing_schema() -> dict[str, Any]:
    """Load and cache ``fencing-state.schema.v1.json`` for validation."""
    global _FENCING_SCHEMA_CACHE
    if _FENCING_SCHEMA_CACHE is None:
        _FENCING_SCHEMA_CACHE = load_default("schemas", "fencing-state.schema.v1.json")
    return _FENCING_SCHEMA_CACHE


@dataclass(frozen=True)
class ResourceFencingState:
    """Per-resource fencing state.

    ``next_token`` is the token that WOULD be issued on the next acquire
    or takeover. The currently-live issued token is ``next_token - 1``
    (see :func:`validate_fencing_token`). ``last_*`` are audit fields
    for ops visibility.
    """

    next_token: int
    last_owner_agent_id: str | None = None
    last_released_at: str | None = None


@dataclass(frozen=True)
class FencingState:
    """In-memory snapshot of ``_fencing.v1.json``.

    Immutable: all mutators return a new snapshot. Callers persist via
    :func:`save_fencing_state_cas` with the revision they observed at
    load time.
    """

    resources: Mapping[str, ResourceFencingState]

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dict matching the schema."""
        return {
            "schema_version": "1",
            "resources": {
                rid: {
                    "next_token": s.next_token,
                    "last_owner_agent_id": s.last_owner_agent_id,
                    "last_released_at": s.last_released_at,
                }
                for rid, s in self.resources.items()
            },
        }


def _fencing_path(workspace_root: Path) -> Path:
    return workspace_root / ".ao" / "claims" / "_fencing.v1.json"


def load_fencing_state(workspace_root: Path) -> FencingState:
    """Load + validate ``_fencing.v1.json``.

    Semantics:
        - File absent → return empty :class:`FencingState` (first-write
          bootstrap).
        - File present but unreadable / unparseable / schema-invalid →
          raise :class:`ClaimCorruptedError` (SSOT fail-closed per
          W2v2 scope).
    """
    path = _fencing_path(workspace_root)
    if not path.exists():
        return FencingState(resources={})
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ClaimCorruptedError(str(path), f"read failed: {exc}") from exc
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ClaimCorruptedError(str(path), f"JSON decode failed: {exc}") from exc

    try:
        from jsonschema import Draft202012Validator

        Draft202012Validator(_fencing_schema()).validate(doc)
    except Exception as exc:
        raise ClaimCorruptedError(
            str(path), f"schema validation failed: {exc}"
        ) from exc

    resources: dict[str, ResourceFencingState] = {}
    for rid, entry in doc["resources"].items():
        resources[rid] = ResourceFencingState(
            next_token=int(entry["next_token"]),
            last_owner_agent_id=entry.get("last_owner_agent_id"),
            last_released_at=entry.get("last_released_at"),
        )
    return FencingState(resources=resources)


def next_token(state: FencingState, resource_id: str) -> tuple[int, FencingState]:
    """Pure function: return ``(issued_token, new_state)``.

    - New resource (no prior entry): issued token = ``0``; new state has
      ``next_token = 1``.
    - Existing resource: issued token = current ``next_token``; new
      state advances ``next_token`` by 1.

    Caller persists the new state via :func:`save_fencing_state_cas`
    under ``claims.lock``. This function is pure / does not touch the
    filesystem.
    """
    current = state.resources.get(
        resource_id,
        ResourceFencingState(next_token=0),
    )
    issued = current.next_token
    advanced = replace(current, next_token=issued + 1)
    new_resources = dict(state.resources)
    new_resources[resource_id] = advanced
    return issued, FencingState(resources=new_resources)


def update_on_release(
    state: FencingState,
    resource_id: str,
    agent_id: str,
    released_at: str,
) -> FencingState:
    """Return a new state with release audit fields set.

    Preserves ``next_token`` so the token authority outlives the claim
    lifetime. Only ``last_owner_agent_id`` and ``last_released_at``
    change. If the resource has no prior entry (release of a never-
    acquired resource — programmer error), this creates one with
    ``next_token=0``; the registry's release flow guards against that
    case before reaching here.
    """
    current = state.resources.get(
        resource_id,
        ResourceFencingState(next_token=0),
    )
    updated = replace(
        current,
        last_owner_agent_id=agent_id,
        last_released_at=released_at,
    )
    new_resources = dict(state.resources)
    new_resources[resource_id] = updated
    return FencingState(resources=new_resources)


def set_next_token(
    state: FencingState,
    resource_id: str,
    new_next_token: int,
) -> FencingState:
    """Return a new state with ``next_token`` forced to the given value.

    Used by the forward-only reconcile helper (B3v3). Callers MUST
    ensure monotonicity (``new_next_token >= current.next_token``); this
    function does NOT enforce the invariant itself — the reconcile
    caller is responsible for computing ``max(current, recovered+1)``.
    """
    current = state.resources.get(
        resource_id,
        ResourceFencingState(next_token=0),
    )
    updated = replace(current, next_token=new_next_token)
    new_resources = dict(state.resources)
    new_resources[resource_id] = updated
    return FencingState(resources=new_resources)


def validate_fencing_token(
    state: FencingState,
    resource_id: str,
    token: int,
) -> None:
    """Exact-equality check against the currently-live issued token.

    The live issued token is ``next_token - 1``. Any mismatch — whether
    the supplied token is stale (takeover happened) or future
    (fabricated / programmer bug) — raises
    :class:`ClaimStaleFencingError`. A missing resource entry also
    raises (no token has ever been issued for this resource).

    Callers (e.g. :class:`Executor.run_step` entry check) invoke this
    under ``claims.lock`` so the read is consistent with any in-flight
    acquire / takeover write.
    """
    entry = state.resources.get(resource_id)
    if entry is None:
        raise ClaimStaleFencingError(
            resource_id=resource_id,
            supplied_token=token,
            live_token=-1,  # sentinel: no token ever issued
        )
    live_token = entry.next_token - 1
    if token != live_token:
        raise ClaimStaleFencingError(
            resource_id=resource_id,
            supplied_token=token,
            live_token=live_token,
        )


def fencing_state_revision(state_dict: Mapping[str, Any]) -> str:
    """Compute a runtime-only CAS revision hash.

    The ``_fencing.v1.json`` schema is closed (does NOT carry a
    ``revision`` field — B0 invariant). We compute the CAS token
    out-of-band at load/save time by hashing the canonical-JSON
    serialisation of the ``resources`` map. The hash is NEVER written
    to disk; it lives only as a caller-held token passed between
    :func:`load_fencing_state` and :func:`save_fencing_state_cas`.
    """
    resources = state_dict.get("resources", {})
    payload = json.dumps(
        resources,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def save_fencing_state_cas(
    workspace_root: Path,
    state: FencingState,
    *,
    expected_revision: str,
) -> None:
    """Atomically persist fencing state with a CAS revision guard.

    Contract (mirrors :func:`ao_kernel.coordination.claim.save_claim_cas`):
        1. Load the existing on-disk state (may be absent on first
           write; treated as matching the empty-state revision).
        2. Compute the observed revision.
        3. If ``expected_revision`` does not match → raise
           :class:`ClaimRevisionConflictError`.
        4. ``write_text_atomic`` the new state.

    Caller holds ``claims.lock``; this helper does NOT acquire it.
    """
    path = _fencing_path(workspace_root)

    # Compute the on-disk revision (or empty-state revision if absent).
    if path.exists():
        try:
            existing_raw = path.read_text(encoding="utf-8")
            existing_doc = json.loads(existing_raw)
        except (OSError, json.JSONDecodeError) as exc:
            raise ClaimCorruptedError(str(path), f"read/parse failed: {exc}") from exc
        actual_revision = fencing_state_revision(existing_doc)
    else:
        # Empty-state baseline; compute the canonical revision of an
        # empty resources map so callers can supply the matching token
        # on first write.
        actual_revision = fencing_state_revision({"resources": {}})

    if actual_revision != expected_revision:
        raise ClaimRevisionConflictError(
            resource_id="<fencing-state>",
            expected_revision=expected_revision,
            actual_revision=actual_revision,
        )

    payload = json.dumps(state.to_dict(), sort_keys=True, ensure_ascii=False)
    write_text_atomic(path, payload)


def empty_fencing_revision() -> str:
    """Revision of the baseline empty-resources fencing state.

    Convenience for first-write callers who have not yet loaded any
    existing state: use this value as ``expected_revision`` for the
    initial :func:`save_fencing_state_cas` call when
    :func:`load_fencing_state` returned an empty snapshot.
    """
    return fencing_state_revision({"resources": {}})
