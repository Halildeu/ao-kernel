"""Typed error hierarchy for the coordination runtime (PR-B1).

See ``docs/COORDINATION.md`` §6 Expiry Authority and PR-B1 plan §2.5
for the full semantic contract each error represents.
"""

from __future__ import annotations


class CoordinationError(Exception):
    """Base class for all coordination runtime errors.

    Public API callers key recovery logic off the subclass type + the
    structured fields each subclass carries (``resource_id``,
    ``current_owner_agent_id``, ``current_fencing_token``, etc.). All
    subclass fields are serialisable so they can be copied into
    ``claim_conflict`` / ``step_failed`` evidence payloads verbatim.
    """


class ClaimConflictError(CoordinationError):
    """A live claim exists on the resource (``now <= effective_expires_at``).

    Distinct from :class:`ClaimConflictGraceError` — the latter signals a
    claim that is past its expiry but still within the revival grace
    window. This class signals a fully active claim.
    """

    def __init__(
        self,
        resource_id: str,
        current_owner_agent_id: str,
        current_fencing_token: int,
    ) -> None:
        super().__init__(
            f"resource {resource_id!r} is held by agent "
            f"{current_owner_agent_id!r} (fencing_token="
            f"{current_fencing_token})"
        )
        self.resource_id = resource_id
        self.current_owner_agent_id = current_owner_agent_id
        self.current_fencing_token = current_fencing_token


class ClaimConflictGraceError(CoordinationError):
    """Claim is past its effective expiry but within takeover grace.

    Owner may still revive via heartbeat; takeover would be premature.
    Callers use the distinct type to choose between "retry later" and
    "give up".
    """

    def __init__(
        self,
        resource_id: str,
        current_owner_agent_id: str,
        current_fencing_token: int,
    ) -> None:
        super().__init__(
            f"resource {resource_id!r} is in takeover grace; owner "
            f"{current_owner_agent_id!r} (fencing_token="
            f"{current_fencing_token}) may still revive"
        )
        self.resource_id = resource_id
        self.current_owner_agent_id = current_owner_agent_id
        self.current_fencing_token = current_fencing_token


class ClaimStaleFencingError(CoordinationError):
    """Supplied fencing token does not match the currently-live issued token.

    Exact-equality semantics: both too-old (stale holder whose claim was
    taken over) and too-new (fabricated / future) tokens are rejected.
    Raised in ``validate_fencing_token`` and at ``Executor.run_step``
    entry, before any side effects.
    """

    def __init__(self, resource_id: str, supplied_token: int, live_token: int) -> None:
        super().__init__(
            f"resource {resource_id!r} stale fencing: supplied_token="
            f"{supplied_token} live_token={live_token}"
        )
        self.resource_id = resource_id
        self.supplied_token = supplied_token
        self.live_token = live_token


class ClaimOwnershipError(CoordinationError):
    """``claim_id`` or ``owner_agent_id`` mismatch on heartbeat / release.

    The claim record exists and is live (or in grace), but the caller
    does not own it. This is distinct from :class:`ClaimAlreadyReleasedError`
    (claim absent or past-grace) and from :class:`ClaimConflictError`
    (acquire attempt on held resource).
    """

    def __init__(
        self,
        claim_id: str,
        requesting_agent_id: str,
        current_owner_agent_id: str,
    ) -> None:
        super().__init__(
            f"claim {claim_id!r} is owned by {current_owner_agent_id!r}, "
            f"not {requesting_agent_id!r}"
        )
        self.claim_id = claim_id
        self.requesting_agent_id = requesting_agent_id
        self.current_owner_agent_id = current_owner_agent_id


class ClaimRevisionConflictError(CoordinationError):
    """CAS ``expected_revision`` check failed on claim or fencing write.

    Raised by ``save_claim_cas`` and ``save_fencing_state_cas``. Callers
    typically re-read the current state, reapply their change, and
    retry — the conflict indicates a concurrent mutation completed
    between this caller's read and write.
    """

    def __init__(
        self,
        resource_id: str,
        expected_revision: str,
        actual_revision: str,
    ) -> None:
        super().__init__(
            f"resource {resource_id!r} CAS conflict: expected "
            f"{expected_revision!r}, actual {actual_revision!r}"
        )
        self.resource_id = resource_id
        self.expected_revision = expected_revision
        self.actual_revision = actual_revision


class ClaimQuotaExceededError(CoordinationError):
    """``max_claims_per_agent`` limit reached.

    Count is SSOT-reconciled (``_ensure_index_consistent`` runs under
    lock before the check). Semantics: ``limit == 0`` ⇒ unlimited
    (quota disabled); ``limit >= 1`` ⇒ hard ceiling.
    """

    def __init__(self, owner_agent_id: str, current_count: int, limit: int) -> None:
        super().__init__(
            f"agent {owner_agent_id!r} has {current_count} active claim(s); "
            f"limit is {limit}"
        )
        self.owner_agent_id = owner_agent_id
        self.current_count = current_count
        self.limit = limit


class ClaimResourcePatternError(CoordinationError):
    """``resource_id`` does not match any allowed pattern.

    Applied AFTER the ``_validate_resource_id`` format check
    (:class:`ClaimResourceIdInvalidError`). Allowlist denial does not
    imply format rejection — the caller's id was well-formed but not
    permitted by policy.
    """

    def __init__(self, resource_id: str, patterns: tuple[str, ...]) -> None:
        super().__init__(
            f"resource_id {resource_id!r} does not match any pattern in "
            f"{list(patterns)!r}"
        )
        self.resource_id = resource_id
        self.patterns = patterns


class ClaimResourceIdInvalidError(CoordinationError):
    """``resource_id`` fails the path-traversal / format validator.

    Regex: ``^[A-Za-z0-9][A-Za-z0-9._-]*$``. Any deviation (path
    separators, wildcards, whitespace, leading/trailing punctuation)
    raises this before the allowlist check.
    """

    def __init__(self, resource_id: str, rejection_reason: str) -> None:
        super().__init__(
            f"resource_id {resource_id!r} invalid: {rejection_reason}"
        )
        self.resource_id = resource_id
        self.rejection_reason = rejection_reason


class ClaimCoordinationDisabledError(CoordinationError):
    """Public registry API called while ``policy.enabled`` is False.

    The dormant-default policy (:file:`policy_coordination_claims.v1.json`
    ships ``enabled: false``) means callers must opt in via workspace
    override before any coordination API will respond.
    """


class ClaimCorruptedError(CoordinationError):
    """SSOT claim or fencing file parse / schema / CAS hash failure.

    Raised for ``{resource_id}.v1.json`` and ``_fencing.v1.json`` —
    the two source-of-truth artefacts. NEVER raised for ``_index.v1.json``,
    which is a derived cache recovered in-place via
    ``_rebuild_index_locked()`` (fail-open for derived state; fail-closed
    for SSOT).
    """

    def __init__(self, path: str, cause: str) -> None:
        super().__init__(f"coordination SSOT corrupt at {path!r}: {cause}")
        self.path = path
        self.cause = cause


class ClaimAlreadyReleasedError(CoordinationError):
    """Release called on absent claim, or heartbeat past-grace.

    Distinct from :class:`ClaimOwnershipError` — there is no claim to
    verify ownership against. Second-call RAISE (not silent no-op) so
    stale-caller bugs surface instead of being masked.
    """

    def __init__(self, resource_id: str, claim_id: str) -> None:
        super().__init__(
            f"claim {claim_id!r} on resource {resource_id!r} is already released"
        )
        self.resource_id = resource_id
        self.claim_id = claim_id


class ClaimNotFoundError(CoordinationError):
    """Public ``takeover_claim`` called on a resource with no claim file.

    Unlike :class:`ClaimAlreadyReleasedError`, which applies to
    heartbeat / release (where the caller previously held the claim and
    now finds it gone), this is the takeover-specific error for an
    attempt to reclaim a resource that never had a claim (or whose
    claim was already released).
    """

    def __init__(self, resource_id: str) -> None:
        super().__init__(f"no claim exists on resource {resource_id!r}")
        self.resource_id = resource_id
