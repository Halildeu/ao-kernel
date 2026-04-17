"""Coordination runtime — multi-agent lease, fencing, takeover (FAZ-B PR-B1).

Public API for ``.ao/claims/``-rooted lease primitives. Workspaces
opt in by setting ``policy_coordination_claims.enabled: true``; the
bundled default ships dormant.

Re-exports the public surface the registry exposes plus the typed
error hierarchy callers key recovery logic off. Private helpers
(``claim_path``, ``_safe_emit_coordination_event``, etc.) live in
their modules and are NOT part of the stable public API.

See ``docs/COORDINATION.md`` for the contract + lifecycle walkthrough.
"""

from __future__ import annotations

from ao_kernel.coordination.claim import (
    Claim,
    claim_from_dict,
    claim_revision,
    claim_to_dict,
    save_claim_cas,
)
from ao_kernel.coordination.errors import (
    ClaimAlreadyReleasedError,
    ClaimConflictError,
    ClaimConflictGraceError,
    ClaimCoordinationDisabledError,
    ClaimCorruptedError,
    ClaimNotFoundError,
    ClaimOwnershipError,
    ClaimQuotaExceededError,
    ClaimResourceIdInvalidError,
    ClaimResourcePatternError,
    ClaimRevisionConflictError,
    ClaimStaleFencingError,
    CoordinationError,
)
from ao_kernel.coordination.fencing import (
    FencingState,
    ResourceFencingState,
    empty_fencing_revision,
    fencing_state_revision,
    load_fencing_state,
    next_token,
    save_fencing_state_cas,
    set_next_token,
    update_on_release,
    validate_fencing_token,
)


__all__ = [
    # Claim
    "Claim",
    "claim_from_dict",
    "claim_revision",
    "claim_to_dict",
    "save_claim_cas",
    # Fencing
    "FencingState",
    "ResourceFencingState",
    "empty_fencing_revision",
    "fencing_state_revision",
    "load_fencing_state",
    "next_token",
    "save_fencing_state_cas",
    "set_next_token",
    "update_on_release",
    "validate_fencing_token",
    # Errors
    "ClaimAlreadyReleasedError",
    "ClaimConflictError",
    "ClaimConflictGraceError",
    "ClaimCoordinationDisabledError",
    "ClaimCorruptedError",
    "ClaimNotFoundError",
    "ClaimOwnershipError",
    "ClaimQuotaExceededError",
    "ClaimResourceIdInvalidError",
    "ClaimResourcePatternError",
    "ClaimRevisionConflictError",
    "ClaimStaleFencingError",
    "CoordinationError",
]
