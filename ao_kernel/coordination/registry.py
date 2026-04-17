"""Coordination registry — public facade orchestrating claim lifecycles.

Public API:

- :class:`ClaimRegistry` — workspace-level orchestrator. Thread-safe
  via the sidecar ``claims.lock`` held for the entire read-mutate-write
  cycle of every mutation.

The registry composes the lower primitives (:mod:`.claim`,
:mod:`.fencing`, :mod:`.policy`) under a single workspace-scoped lock.
Takeover + prune + cross-file reconcile land in commit 4; this module
ships the CORE flows — ``acquire_claim``, ``heartbeat``,
``release_claim``, ``get_claim``, ``validate_fencing_token``,
``list_agent_claims``.

Invariants honoured here (see PR-B1 plan v5):

- **Write ordering (B2v2):** fencing state → claim file → ``_index.v1.json``
  on acquire; claim file → fencing audit → ``_index`` on release.
  ``_index`` is always last because it is a derived cache (see W2v2).
- **SSOT fail-closed (W2v2):** corrupt ``{resource_id}.v1.json`` or
  ``_fencing.v1.json`` raises :class:`ClaimCorruptedError` propagating
  to the caller. Corrupt ``_index.v1.json`` triggers silent rebuild
  (fail-open for derived cache).
- **Quota SSOT-reconciled (B1v2 + W3v5):** every acquire call triggers
  ``_ensure_index_consistent`` which recomputes the index hash; drift
  → rebuild from per-resource files; count excludes expired-but-
  unpruned claims (live-count semantic).
- **Unlimited when ``limit=0`` (B1v3):** the enforcement line is
  ``if policy.max_claims_per_agent > 0 and count >= limit: raise``.
- **Release fail-closed order (B3v5):** ``_fencing.v1.json`` is
  loaded + validated BEFORE the claim file is deleted, so a corrupt
  fencing state raises while the claim is still recoverable.
- **Evidence fail-open (B3v2 + B4v3 + W4v4):** registry mutations emit
  through the caller-injected ``evidence_sink``; the wrapper swallows
  emit errors with ``logger.warning`` to protect the coordination
  critical path from evidence I/O failures (CLAUDE.md §2).

Takeover + prune + reconcile + executor fencing entry land in
commit 4 (plan §3 Step 5).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from ao_kernel._internal.shared.utils import write_text_atomic
from ao_kernel._internal.shared.lock import file_lock

from ao_kernel.coordination.claim import (
    Claim,
    claim_from_dict,
    claim_path,
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
)
from ao_kernel.coordination.fencing import (
    FencingState,
)
from ao_kernel.coordination.fencing import (
    empty_fencing_revision,
    fencing_state_revision,
    load_fencing_state,
    next_token,
    save_fencing_state_cas,
    update_on_release,
    validate_fencing_token as _fencing_validate_token,
)
from ao_kernel.coordination.policy import (
    CoordinationPolicy,
    load_coordination_policy,
    match_resource_pattern,
)


logger = logging.getLogger(__name__)


EvidenceSink = Callable[[str, Mapping[str, Any]], Any]


# ---------------------------------------------------------------------------
# resource_id path-traversal guard (B4v2) — runs BEFORE pattern allowlist
# ---------------------------------------------------------------------------

_RESOURCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _validate_resource_id(resource_id: str) -> None:
    """Raise :class:`ClaimResourceIdInvalidError` for unsafe ids.

    Regex: ``^[A-Za-z0-9][A-Za-z0-9._-]*$``. Explicitly rejects anything
    containing path separators (``/``), parent-dir references (``../``
    / ``./``), wildcards (``*``, ``?``, ``[``, ``]``), whitespace, or a
    leading non-alphanumeric character. Runs before the policy's glob
    allowlist so the pattern matcher only ever sees known-safe strings.
    """
    if not isinstance(resource_id, str) or not resource_id:
        raise ClaimResourceIdInvalidError(
            resource_id=str(resource_id),
            rejection_reason="resource_id must be a non-empty string",
        )
    if not _RESOURCE_ID_PATTERN.fullmatch(resource_id):
        raise ClaimResourceIdInvalidError(
            resource_id=resource_id,
            rejection_reason=(
                "resource_id must match regex ^[A-Za-z0-9][A-Za-z0-9._-]*$ "
                "(no path separators, wildcards, whitespace, or leading "
                "non-alphanumeric character)"
            ),
        )


# ---------------------------------------------------------------------------
# _index.v1.json — derived agent → [resource_id] cache
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentClaimIndex:
    """In-memory snapshot of ``_index.v1.json``.

    Derived cache only. The SSOT is the set of per-resource
    ``{resource_id}.v1.json`` files; this index is rebuilt from a file
    scan on any drift detection. Callers MUST NOT treat the index as
    authoritative for correctness-critical decisions (quota counting
    loads each referenced claim and re-checks liveness).
    """

    agents: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    generated_at: str = ""
    revision: str = ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "+00:00")


def _parse_iso(ts: str) -> datetime:
    """Parse an ISO-8601 timestamp into an aware UTC datetime.

    Tolerates the trailing ``Z`` shorthand emitted by some callers by
    normalising to ``+00:00`` before handing off to ``fromisoformat``.
    """
    normalised = ts.replace("Z", "+00:00") if ts.endswith("Z") else ts
    dt = datetime.fromisoformat(normalised)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _claims_dir(workspace_root: Path) -> Path:
    return workspace_root / ".ao" / "claims"


def _claims_lock_path(workspace_root: Path) -> Path:
    return _claims_dir(workspace_root) / "claims.lock"


def _index_path(workspace_root: Path) -> Path:
    return _claims_dir(workspace_root) / "_index.v1.json"


def _compute_index_revision(agents: Mapping[str, tuple[str, ...]]) -> str:
    """Canonical JSON hash over the ``agents`` map."""
    payload_obj = {k: list(v) for k, v in sorted(agents.items())}
    payload = json.dumps(payload_obj, sort_keys=True, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_coordination_sink(
    workspace_root: Path,
    policy: CoordinationPolicy,
    *,
    run_id: str,
    actor: str = "ao-kernel",
) -> EvidenceSink:
    """Build a coordination :class:`EvidenceSink` wired to the ao-kernel
    evidence emitter with policy-bound redaction (W2v5).

    Callers wrap the returned callable into
    ``ClaimRegistry(..., evidence_sink=...)`` to have claim events flow
    through the standard ``ao_kernel.executor.evidence_emitter.emit_event``
    pipeline under a specific ``run_id`` / ``actor`` context. The helper
    explicitly binds ``policy.evidence_redaction`` to the emitter's
    redaction argument so the coordination event payloads are scrubbed
    according to the coordination policy rather than the worktree
    profile (which is a separate concern).

    Why a helper instead of leaving it to the caller:
      - Ensures every coordination sink picks up
        ``policy.evidence_redaction`` (previously easy to forget).
      - Centralises the ``run_id`` / ``actor`` context binding so the
        call site at :meth:`ClaimRegistry.__init__` stays short.
      - The sink closure is a plain function, so ``Callable[[str,
        Mapping[str, Any]], Any]`` typing works under strict mypy.

    Parameters are all keyword-only (``run_id``, ``actor``) except the
    positional ``workspace_root`` + ``policy``. ``actor`` defaults to
    ``"ao-kernel"`` since coordination events are orchestration-level
    rather than adapter-level by construction.
    """
    from ao_kernel.executor.evidence_emitter import emit_event
    from ao_kernel.executor.policy_enforcer import RedactionConfig

    # Translate the policy's EvidenceRedaction dataclass into the
    # RedactionConfig shape the emitter expects. The worktree profile
    # uses the same pattern; we mirror it here so operators can author
    # regex lists in policy_coordination_claims.v1.json with the same
    # semantics.
    #
    # Schema semantic (CNS-029v4 iter-4 absorb): the coordination
    # policy's ``patterns`` field is a *convenience* flat list meaning
    # "apply to any string value in the payload". The emitter's
    # ``_redact_text`` implementation applies ``stdout_patterns``
    # against every payload string value via ``_redact_payload`` —
    # exactly the same scope. Concatenating ``patterns`` into
    # ``stdout_patterns`` is therefore the faithful translation.
    # (``file_content_patterns`` is kept for schema parity with the
    # worktree profile; the emitter does not currently consume it.)
    import re

    combined_stdout = tuple(
        policy.evidence_redaction.stdout_patterns
    ) + tuple(policy.evidence_redaction.patterns)

    redaction = RedactionConfig(
        env_keys_matching=tuple(
            re.compile(p) for p in policy.evidence_redaction.env_keys_matching
        ),
        stdout_patterns=tuple(re.compile(p) for p in combined_stdout),
        file_content_patterns=tuple(
            re.compile(p) for p in policy.evidence_redaction.file_content_patterns
        ),
    )

    def _sink(kind: str, payload: Mapping[str, Any]) -> Any:
        return emit_event(
            workspace_root,
            run_id=run_id,
            kind=kind,
            actor=actor,
            payload=payload,
            redaction=redaction,
        )

    return _sink


def _safe_emit_coordination_event(
    sink: EvidenceSink | None,
    kind: str,
    payload: Mapping[str, Any],
) -> None:
    """Best-effort evidence emission (B3v2 + B4v3).

    Evidence is a fail-open side-channel (CLAUDE.md §2). Coordination
    correctness must not depend on emit success; an I/O or lock failure
    in the evidence layer is logged at ``warning`` level with the kind
    + cause structured into ``extra`` for downstream log parsers.
    """
    if sink is None:
        return
    try:
        sink(kind, payload)
    except Exception as e:
        logger.warning(
            "coordination evidence emit failed: kind=%s, cause=%r",
            kind, e,
            extra={"coordination_kind": kind, "error": repr(e)},
        )


# ---------------------------------------------------------------------------
# ClaimRegistry
# ---------------------------------------------------------------------------


class ClaimRegistry:
    """Workspace-level coordination orchestrator.

    All public mutations acquire ``claims.lock`` for the entire
    read-mutate-write cycle. The registry is the single entry point
    for callers; the underlying primitives
    (:mod:`.claim`, :mod:`.fencing`, :mod:`.policy`) remain pure /
    lock-agnostic so tests can exercise them directly.

    Constructor parameters:
        workspace_root: Project root containing ``.ao/``.
        evidence_sink: Optional callable ``(kind, payload) -> Any``.
            Registry mutations invoke it through
            :func:`_safe_emit_coordination_event` (fail-open). Pass
            ``None`` (default) to run silently — callers building
            evidence integrations wrap
            :func:`ao_kernel.executor.evidence_emitter.emit_event`
            with workspace / run_id / actor context and supply the
            resulting closure here.
    """

    def __init__(
        self,
        workspace_root: Path,
        *,
        evidence_sink: EvidenceSink | None = None,
    ) -> None:
        self._workspace_root = workspace_root
        self._evidence_sink = evidence_sink

    # -- Public API ---------------------------------------------------------

    def acquire_claim(
        self,
        resource_id: str,
        owner_agent_id: str,
        policy: CoordinationPolicy | None = None,
    ) -> Claim:
        """Acquire a fresh or reclaim-able claim on ``resource_id``.

        Preamble (outside the lock):
            1. Load policy (workspace override or bundled default).
            2. Reject disabled coordination (:class:`ClaimCoordinationDisabledError`).
            3. Run ``_validate_resource_id`` path-traversal guard.
            4. Enforce ``policy.claim_resource_patterns`` allowlist.

        Locked section:
            5. Read ``{resource_id}.v1.json`` (fail-closed on corrupt).
            6. If live → emit ``claim_conflict`` + raise.
            7. If in grace → emit ``claim_conflict`` (grace variant) + raise.
            8. If past-grace — defer to takeover (commit 4; for now
               raises :class:`ClaimConflictGraceError` with a sentinel
               because past-grace handling needs ``_takeover_locked``).
            9. Quota SSOT-reconcile via ``_ensure_index_consistent``
               + live-count; enforce if ``max_claims_per_agent > 0``.
           10. Write order: fencing → claim → ``_index``.
           11. Emit ``claim_acquired`` (W1v2: never for takeover path).
        """
        policy = policy or load_coordination_policy(self._workspace_root)
        if not policy.enabled:
            raise ClaimCoordinationDisabledError()
        _validate_resource_id(resource_id)
        if not match_resource_pattern(policy, resource_id):
            raise ClaimResourcePatternError(
                resource_id=resource_id,
                patterns=policy.claim_resource_patterns,
            )
        _claims_dir(self._workspace_root).mkdir(parents=True, exist_ok=True)
        with file_lock(_claims_lock_path(self._workspace_root)):
            return self._acquire_locked(resource_id, owner_agent_id, policy)

    def heartbeat(
        self,
        resource_id: str,
        claim_id: str,
        owner_agent_id: str,
    ) -> Claim:
        """Advance ``heartbeat_at`` for an owned, still-live claim.

        Caller supplies ``(resource_id, claim_id, owner_agent_id)`` so
        the registry does direct O(1) lookup (B v4 contract — no
        reverse index, no O(N) scan). Ownership verification loads the
        claim and asserts both ``claim_id`` and ``owner_agent_id``
        match; mismatch raises :class:`ClaimOwnershipError`.

        Past-grace expired claims raise
        :class:`ClaimAlreadyReleasedError` — the owner lost the
        revival window and must re-acquire. Absent claim also raises
        :class:`ClaimAlreadyReleasedError` (W5v2: second-call RAISE).

        Dormant-policy gate: when ``policy.enabled=false`` the call
        raises :class:`ClaimCoordinationDisabledError` before any
        filesystem access (plan §5 "any public API" contract).
        """
        policy = load_coordination_policy(self._workspace_root)
        if not policy.enabled:
            raise ClaimCoordinationDisabledError()
        _validate_resource_id(resource_id)
        _claims_dir(self._workspace_root).mkdir(parents=True, exist_ok=True)
        with file_lock(_claims_lock_path(self._workspace_root)):
            return self._heartbeat_locked(resource_id, claim_id, owner_agent_id)

    def release_claim(
        self,
        resource_id: str,
        claim_id: str,
        owner_agent_id: str,
    ) -> None:
        """Release an owned claim.

        Fail-closed write order (B3v5): load + validate
        ``_fencing.v1.json`` BEFORE deleting the claim file, so a
        corrupt fencing state raises while the claim is still
        recoverable. After the fencing pre-validation: claim DELETE
        → fencing audit write → ``_index`` removal.

        Second release (claim file already absent) raises
        :class:`ClaimAlreadyReleasedError` (W5v2). Ownership mismatch
        raises :class:`ClaimOwnershipError`. Dormant policy →
        :class:`ClaimCoordinationDisabledError`.
        """
        policy = load_coordination_policy(self._workspace_root)
        if not policy.enabled:
            raise ClaimCoordinationDisabledError()
        _validate_resource_id(resource_id)
        _claims_dir(self._workspace_root).mkdir(parents=True, exist_ok=True)
        with file_lock(_claims_lock_path(self._workspace_root)):
            self._release_locked(resource_id, claim_id, owner_agent_id)

    def get_claim(self, resource_id: str) -> Claim | None:
        """Return the current claim on ``resource_id``, or ``None``.

        Unlike heartbeat / release / acquire this is a read-only
        convenience method; callers use it to introspect state. Corrupt
        ``{resource_id}.v1.json`` still raises
        :class:`ClaimCorruptedError` (SSOT fail-closed) — silent-None
        would mask on-disk damage. ``None`` is returned only when the
        file is genuinely absent. Dormant policy → raises
        :class:`ClaimCoordinationDisabledError` per plan §5
        "any public API" contract.
        """
        policy = load_coordination_policy(self._workspace_root)
        if not policy.enabled:
            raise ClaimCoordinationDisabledError()
        _validate_resource_id(resource_id)
        return self._load_claim_if_exists(resource_id)

    def validate_fencing_token(self, resource_id: str, token: int) -> None:
        """Delegate to :func:`fencing.validate_fencing_token` under lock.

        Raises :class:`ClaimStaleFencingError` on exact-equality
        mismatch (covers both stale takeover-victim tokens and
        fabricated / future tokens). Used by ``Executor.run_step``
        entry check. Dormant policy → raises
        :class:`ClaimCoordinationDisabledError`.
        """
        policy = load_coordination_policy(self._workspace_root)
        if not policy.enabled:
            raise ClaimCoordinationDisabledError()
        _validate_resource_id(resource_id)
        _claims_dir(self._workspace_root).mkdir(parents=True, exist_ok=True)
        with file_lock(_claims_lock_path(self._workspace_root)):
            state = load_fencing_state(self._workspace_root)
            _fencing_validate_token(state, resource_id, token)

    def list_agent_claims(self, owner_agent_id: str) -> list[Claim]:
        """Return the agent's currently-held (non-expired) claims.

        Triggers ``_ensure_index_consistent`` under lock — if the
        derived index drifted from the per-resource SSOT files, it is
        silently rebuilt (fail-open). Live-count filter applies: claims
        whose ``heartbeat_at + policy.expiry_seconds + grace`` has
        passed are excluded even if still present on disk (they are
        candidates for ``prune_expired_claims``). Dormant policy →
        raises :class:`ClaimCoordinationDisabledError`.
        """
        policy = load_coordination_policy(self._workspace_root)
        if not policy.enabled:
            raise ClaimCoordinationDisabledError()
        _claims_dir(self._workspace_root).mkdir(parents=True, exist_ok=True)
        with file_lock(_claims_lock_path(self._workspace_root)):
            self._ensure_index_consistent()
            index = self._load_index()
            now = datetime.now(timezone.utc)
            claims: list[Claim] = []
            for resource_id in index.agents.get(owner_agent_id, ()):
                claim = self._load_claim_if_exists(resource_id)
                if claim is None:
                    continue
                if not self._claim_is_live(claim, policy, now):
                    continue
                claims.append(claim)
            return claims

    def takeover_claim(
        self,
        resource_id: str,
        new_owner_agent_id: str,
        policy: CoordinationPolicy | None = None,
    ) -> Claim:
        """Reclaim a past-grace claim for a new agent.

        B1v5 live/grace gate: ``_takeover_locked`` refuses unless
        ``now > heartbeat_at + expiry + grace``. Live claim → raises
        :class:`ClaimConflictError` + emits ``claim_conflict`` (per
        audit-symmetry decision: caller's explicit takeover attempt on
        a live claim is visible in the audit trail). In-grace claim →
        raises :class:`ClaimConflictGraceError` + same emit. Absent
        resource → raises :class:`ClaimNotFoundError`.

        Preamble mirrors ``acquire_claim`` exactly (B5v3 validator
        parity): dormant check, path-traversal guard, pattern
        allowlist, then locked delegate.
        """
        policy = policy or load_coordination_policy(self._workspace_root)
        if not policy.enabled:
            raise ClaimCoordinationDisabledError()
        _validate_resource_id(resource_id)
        if not match_resource_pattern(policy, resource_id):
            raise ClaimResourcePatternError(
                resource_id=resource_id,
                patterns=policy.claim_resource_patterns,
            )
        _claims_dir(self._workspace_root).mkdir(parents=True, exist_ok=True)
        with file_lock(_claims_lock_path(self._workspace_root)):
            return self._takeover_locked(
                resource_id, new_owner_agent_id, policy, skip_gate=False,
            )

    def prune_expired_claims(
        self,
        policy: CoordinationPolicy | None = None,
        *,
        max_batch: int | None = None,
    ) -> list[str]:
        """Clean up past-grace claims (caller-driven, not a daemon).

        Returns the list of pruned ``resource_id`` values. Per B3v5
        fail-closed order each prune iteration loads + validates the
        fencing state before deleting the claim file; a corrupt
        fencing state raises :class:`ClaimCorruptedError` mid-batch
        with the partial result committed.

        ``max_batch`` caps the number of claims pruned per invocation
        so long prune scans do not hold ``claims.lock`` indefinitely
        in workspaces with many stale claims (Q7v2 caller-driven
        pacing). Callers repaginate by invoking the method again
        until the returned list is empty.

        Warning: callers should schedule prune outside hot acquire
        paths (long-held lock contention delays acquire latency).

        Dormant policy → raises :class:`ClaimCoordinationDisabledError`
        (plan §5 "any public API" contract; prune is a mutation
        pathway, not a read, so dormant mode must refuse).
        """
        policy = policy or load_coordination_policy(self._workspace_root)
        if not policy.enabled:
            raise ClaimCoordinationDisabledError()
        _claims_dir(self._workspace_root).mkdir(parents=True, exist_ok=True)
        pruned: list[str] = []
        with file_lock(_claims_lock_path(self._workspace_root)):
            claims_dir = _claims_dir(self._workspace_root)
            if not claims_dir.is_dir():
                return pruned
            now = datetime.now(timezone.utc)
            for path in sorted(claims_dir.glob("*.v1.json")):
                if max_batch is not None and len(pruned) >= max_batch:
                    break
                name = path.name
                if name.startswith("_"):
                    continue
                resource_id = name[: -len(".v1.json")]
                claim = self._load_claim_if_exists(resource_id)
                if claim is None:
                    continue
                grace_end = _parse_iso(claim.heartbeat_at) + timedelta(
                    seconds=policy.expiry_seconds
                    + policy.takeover_grace_period_seconds,
                )
                if now <= grace_end:
                    continue
                # B3v5 fail-closed order (same as release_claim):
                # fencing load + validate BEFORE delete.
                fencing_state = load_fencing_state(self._workspace_root)
                current_fencing_rev = fencing_state_revision(
                    fencing_state.to_dict(),
                )
                expired_at = now.isoformat()
                new_state = update_on_release(
                    fencing_state,
                    resource_id,
                    claim.owner_agent_id,
                    expired_at,
                )
                path.unlink()
                save_fencing_state_cas(
                    self._workspace_root,
                    new_state,
                    expected_revision=current_fencing_rev,
                )
                self._remove_from_index(resource_id, claim.owner_agent_id)
                _safe_emit_coordination_event(
                    self._evidence_sink,
                    "claim_expired",
                    {
                        "resource_id": resource_id,
                        "last_owner_agent_id": claim.owner_agent_id,
                        "last_heartbeat_at": claim.heartbeat_at,
                        "expired_at": expired_at,
                    },
                )
                pruned.append(resource_id)
        return pruned

    # -- Locked helpers (caller holds claims.lock) --------------------------

    def _acquire_locked(
        self,
        resource_id: str,
        owner_agent_id: str,
        policy: CoordinationPolicy,
    ) -> Claim:
        """Acquire core. Past-grace takeover delegates to commit-4 helper."""
        current = self._load_claim_if_exists(resource_id)
        if current is not None:
            now = datetime.now(timezone.utc)
            effective_expires = _parse_iso(current.heartbeat_at) + timedelta(
                seconds=policy.expiry_seconds,
            )
            if now <= effective_expires:
                self._emit_conflict(
                    resource_id,
                    requesting_agent_id=owner_agent_id,
                    current=current,
                    conflict_kind="CLAIM_CONFLICT",
                    now=now,
                )
                raise ClaimConflictError(
                    resource_id=resource_id,
                    current_owner_agent_id=current.owner_agent_id,
                    current_fencing_token=current.fencing_token,
                )
            grace_end = effective_expires + timedelta(
                seconds=policy.takeover_grace_period_seconds,
            )
            if now <= grace_end:
                self._emit_conflict(
                    resource_id,
                    requesting_agent_id=owner_agent_id,
                    current=current,
                    conflict_kind="CLAIM_CONFLICT_GRACE",
                    now=now,
                )
                raise ClaimConflictGraceError(
                    resource_id=resource_id,
                    current_owner_agent_id=current.owner_agent_id,
                    current_fencing_token=current.fencing_token,
                )
            # Past-grace → delegate to _takeover_locked; outer helper
            # does NOT emit (W3v4 single-emit contract). The delegate
            # bypasses its own live/grace gate (skip_gate=True) because
            # the gate check above already proved past-grace status.
            return self._takeover_locked(
                resource_id, owner_agent_id, policy, skip_gate=True,
            )

        # Absent — fresh acquire
        self._ensure_index_consistent()
        count = self._count_agent_claims_live(owner_agent_id, policy)
        if policy.max_claims_per_agent > 0 and count >= policy.max_claims_per_agent:
            raise ClaimQuotaExceededError(
                owner_agent_id=owner_agent_id,
                current_count=count,
                limit=policy.max_claims_per_agent,
            )
        return self._persist_new_claim(resource_id, owner_agent_id, policy)

    def _heartbeat_locked(
        self,
        resource_id: str,
        claim_id: str,
        owner_agent_id: str,
    ) -> Claim:
        claim = self._load_claim_if_exists(resource_id)
        if claim is None:
            raise ClaimAlreadyReleasedError(
                resource_id=resource_id, claim_id=claim_id,
            )
        if claim.claim_id != claim_id or claim.owner_agent_id != owner_agent_id:
            raise ClaimOwnershipError(
                claim_id=claim_id,
                requesting_agent_id=owner_agent_id,
                current_owner_agent_id=claim.owner_agent_id,
            )
        policy = load_coordination_policy(self._workspace_root)
        now = datetime.now(timezone.utc)
        grace_end = _parse_iso(claim.heartbeat_at) + timedelta(
            seconds=policy.expiry_seconds + policy.takeover_grace_period_seconds,
        )
        if now > grace_end:
            raise ClaimAlreadyReleasedError(
                resource_id=resource_id, claim_id=claim_id,
            )
        updated = {**claim_to_dict(claim)}
        updated["heartbeat_at"] = now.isoformat()
        updated["expires_at"] = (
            now + timedelta(seconds=policy.expiry_seconds)
        ).isoformat()
        updated["revision"] = claim_revision(updated)
        save_claim_cas(
            self._workspace_root,
            resource_id,
            updated,
            expected_revision=claim.revision,
        )
        _safe_emit_coordination_event(
            self._evidence_sink,
            "claim_heartbeat",
            {
                "resource_id": resource_id,
                "owner_agent_id": owner_agent_id,
                "claim_id": claim_id,
                "heartbeat_at": updated["heartbeat_at"],
            },
        )
        return claim_from_dict(updated)

    def _release_locked(
        self,
        resource_id: str,
        claim_id: str,
        owner_agent_id: str,
    ) -> None:
        claim = self._load_claim_if_exists(resource_id)
        if claim is None:
            raise ClaimAlreadyReleasedError(
                resource_id=resource_id, claim_id=claim_id,
            )
        if claim.claim_id != claim_id or claim.owner_agent_id != owner_agent_id:
            raise ClaimOwnershipError(
                claim_id=claim_id,
                requesting_agent_id=owner_agent_id,
                current_owner_agent_id=claim.owner_agent_id,
            )
        # B3v5 fail-closed order: load fencing state + validate BEFORE
        # deleting the claim file. If _fencing.v1.json is corrupt, the
        # load raises ClaimCorruptedError while the claim file is still
        # recoverable on disk.
        fencing_state = load_fencing_state(self._workspace_root)
        current_fencing_rev = fencing_state_revision(fencing_state.to_dict())
        released_at = _now_iso()
        new_state = update_on_release(
            fencing_state, resource_id, owner_agent_id, released_at,
        )

        # 1. Delete claim file (only now, after fencing pre-validated).
        claim_path(self._workspace_root, resource_id).unlink()
        # 2. Fencing audit write.
        save_fencing_state_cas(
            self._workspace_root,
            new_state,
            expected_revision=current_fencing_rev,
        )
        # 3. Index removal (derived cache last).
        self._remove_from_index(resource_id, owner_agent_id)

        _safe_emit_coordination_event(
            self._evidence_sink,
            "claim_released",
            {
                "resource_id": resource_id,
                "owner_agent_id": owner_agent_id,
                "claim_id": claim_id,
                "released_at": released_at,
            },
        )

    def _takeover_locked(
        self,
        resource_id: str,
        new_owner_agent_id: str,
        policy: CoordinationPolicy,
        *,
        skip_gate: bool,
    ) -> Claim:
        """Reclaim a claim for a new agent (B1v5 gate + B1v3 quota).

        ``skip_gate=True`` is set by ``_acquire_locked`` when it has
        already verified past-grace status from the outer
        conflict-dispatch logic (W3v4 single-emit: the outer helper
        does not re-emit after delegating). ``skip_gate=False`` is the
        public ``takeover_claim`` entry — it enforces the gate here.

        Audit-symmetry: when a public takeover hits a live or in-grace
        claim, we emit ``claim_conflict`` (matching the acquire
        dispatch path) before raising, so the caller's intent to
        reclaim is recorded in the trail.
        """
        prev = self._load_claim_if_exists(resource_id)
        if prev is None:
            raise ClaimNotFoundError(resource_id=resource_id)

        now = datetime.now(timezone.utc)
        if not skip_gate:
            effective_expires = _parse_iso(prev.heartbeat_at) + timedelta(
                seconds=policy.expiry_seconds,
            )
            if now <= effective_expires:
                self._emit_conflict(
                    resource_id,
                    requesting_agent_id=new_owner_agent_id,
                    current=prev,
                    conflict_kind="CLAIM_CONFLICT",
                    now=now,
                )
                raise ClaimConflictError(
                    resource_id=resource_id,
                    current_owner_agent_id=prev.owner_agent_id,
                    current_fencing_token=prev.fencing_token,
                )
            grace_end = effective_expires + timedelta(
                seconds=policy.takeover_grace_period_seconds,
            )
            if now <= grace_end:
                self._emit_conflict(
                    resource_id,
                    requesting_agent_id=new_owner_agent_id,
                    current=prev,
                    conflict_kind="CLAIM_CONFLICT_GRACE",
                    now=now,
                )
                raise ClaimConflictGraceError(
                    resource_id=resource_id,
                    current_owner_agent_id=prev.owner_agent_id,
                    current_fencing_token=prev.fencing_token,
                )

        # B1v3 quota enforcement on takeover path (same SSOT-reconciled
        # live-count as acquire).
        self._ensure_index_consistent()
        count = self._count_agent_claims_live(new_owner_agent_id, policy)
        if policy.max_claims_per_agent > 0 and count >= policy.max_claims_per_agent:
            raise ClaimQuotaExceededError(
                owner_agent_id=new_owner_agent_id,
                current_count=count,
                limit=policy.max_claims_per_agent,
            )

        # B2v2 write order: fencing → claim → index.
        fencing_state = load_fencing_state(self._workspace_root)
        current_fencing_rev = fencing_state_revision(fencing_state.to_dict())
        new_token, new_fencing_state = next_token(fencing_state, resource_id)
        save_fencing_state_cas(
            self._workspace_root,
            new_fencing_state,
            expected_revision=current_fencing_rev,
        )
        new_claim_dict = {
            "claim_id": str(uuid.uuid4()),
            "owner_agent_id": new_owner_agent_id,
            "resource_id": resource_id,
            "fencing_token": new_token,
            "acquired_at": now.isoformat(),
            "heartbeat_at": now.isoformat(),
            "expires_at": (
                now + timedelta(seconds=policy.expiry_seconds)
            ).isoformat(),
        }
        new_claim_dict["revision"] = claim_revision(new_claim_dict)
        write_text_atomic(
            claim_path(self._workspace_root, resource_id),
            json.dumps(new_claim_dict, sort_keys=True, ensure_ascii=False),
        )
        # Index: remove previous owner entry, add new. Using the
        # granular helpers keeps the index consistent across the owner
        # flip without a full rebuild.
        self._remove_from_index(resource_id, prev.owner_agent_id)
        self._add_to_index(new_owner_agent_id, resource_id)

        # W1v2 distinct event; W3v4 single-emit path (only here).
        _safe_emit_coordination_event(
            self._evidence_sink,
            "claim_takeover",
            {
                "resource_id": resource_id,
                "new_owner_agent_id": new_owner_agent_id,
                "prev_owner_agent_id": prev.owner_agent_id,
                "new_claim_id": new_claim_dict["claim_id"],
                "prev_claim_id": prev.claim_id,
                "new_fencing_token": new_token,
                "prev_fencing_token": prev.fencing_token,
                "takeover_at": now.isoformat(),
            },
        )
        return claim_from_dict(new_claim_dict)

    def _reconcile_fencing_with_claims_locked(self) -> None:
        """Recover fencing state from per-resource claim file scan.

        Called by callers (ops tooling or integration tests) when they
        suspect fencing / claim drift. Forward-only (B3v3): fencing
        state's ``next_token`` never decreases. Algorithm:

        1. Load current ``FencingState`` (``_fencing.v1.json``). This
           itself will raise ``ClaimCorruptedError`` on SSOT damage.
        2. Scan ``.ao/claims/`` for per-resource claim files. For each
           resource, compute ``recovered_next = max(claim.fencing_token
           for claim in resource_claims) + 1``.
        3. Set the new ``next_token`` to ``max(state.resources[rid].
           next_token, recovered_next)`` — the forward-only guarantee.
           If the current state's value already exceeds the recovered
           value (fencing advanced ahead of any persisted claim), we
           preserve the current value rather than rewind.
        4. Persist the reconciled state under CAS.

        Caller holds ``claims.lock`` for the full cycle.
        """
        state = load_fencing_state(self._workspace_root)
        current_rev = fencing_state_revision(state.to_dict())
        claims_dir = _claims_dir(self._workspace_root)
        # Gather per-resource claim files (there is at most one at
        # steady state; the scan tolerates stray siblings defensively).
        new_state: FencingState = state
        if claims_dir.is_dir():
            for path in sorted(claims_dir.glob("*.v1.json")):
                name = path.name
                if name.startswith("_"):
                    continue
                resource_id = name[: -len(".v1.json")]
                claim = self._load_claim_if_exists(resource_id)
                if claim is None:
                    continue
                recovered_next = claim.fencing_token + 1
                existing = new_state.resources.get(resource_id)
                current_next = existing.next_token if existing else 0
                # Forward-only: never decrease.
                if recovered_next > current_next:
                    from ao_kernel.coordination.fencing import set_next_token
                    new_state = set_next_token(
                        new_state, resource_id, recovered_next,
                    )
        # Only persist if there was a change.
        if new_state is not state:
            save_fencing_state_cas(
                self._workspace_root,
                new_state,
                expected_revision=current_rev,
            )

    # -- Internals ----------------------------------------------------------

    def _load_claim_if_exists(self, resource_id: str) -> Claim | None:
        """Load and validate the SSOT claim file, or return ``None`` if absent.

        SSOT corruption (parse / schema / revision mismatch) propagates
        via :class:`ClaimCorruptedError` (W2v2 fail-closed). The
        distinction between "corrupt" and "absent" matters: absence is
        a normal state transition (pre-acquire, post-release), while
        corruption is an on-disk integrity failure requiring operator
        attention.
        """
        path = claim_path(self._workspace_root, resource_id)
        if not path.exists():
            return None
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ClaimCorruptedError(str(path), f"read failed: {exc}") from exc
        try:
            doc = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ClaimCorruptedError(
                str(path), f"JSON decode failed: {exc}",
            ) from exc
        return claim_from_dict(doc, source_path=path)

    def _claim_is_live(
        self,
        claim: Claim,
        policy: CoordinationPolicy,
        now: datetime,
    ) -> bool:
        """Non-expired (live OR in grace) predicate for quota / listing."""
        grace_end = _parse_iso(claim.heartbeat_at) + timedelta(
            seconds=policy.expiry_seconds + policy.takeover_grace_period_seconds,
        )
        return now <= grace_end

    def _count_agent_claims_live(
        self,
        owner_agent_id: str,
        policy: CoordinationPolicy,
    ) -> int:
        """Live-count per-agent claims (W3v5 non-expired only).

        Loads each resource_id from the ``_index`` entry for the agent,
        opens the SSOT claim file, and applies
        :meth:`_claim_is_live`. Expired-but-unpruned claims are
        filtered out so quota enforcement reflects *current* liveness
        rather than bookkeeping artefacts.
        """
        index = self._load_index()
        now = datetime.now(timezone.utc)
        count = 0
        for resource_id in index.agents.get(owner_agent_id, ()):
            claim = self._load_claim_if_exists(resource_id)
            if claim is None:
                continue  # stale index entry; drift rebuild will fix
            if self._claim_is_live(claim, policy, now):
                count += 1
        return count

    def _load_index(self) -> AgentClaimIndex:
        """Load the derived index, or return an empty snapshot if absent."""
        path = _index_path(self._workspace_root)
        if not path.exists():
            return AgentClaimIndex()
        try:
            raw = path.read_text(encoding="utf-8")
            doc = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            # Derived cache fail-open (W2v2): corrupt index triggers
            # rebuild. Returning an empty snapshot signals the drift
            # check below that a rebuild is needed.
            return AgentClaimIndex()
        agents = {
            agent: tuple(rids) for agent, rids in (doc.get("agents") or {}).items()
        }
        return AgentClaimIndex(
            agents=agents,
            generated_at=str(doc.get("generated_at", "")),
            revision=str(doc.get("revision", "")),
        )

    def _ensure_index_consistent(self) -> None:
        """Rebuild the index if the stored revision does not match the
        recomputed hash (W2v2 fail-open for derived cache).

        Caller holds ``claims.lock``. Rebuild scans all per-resource
        files under ``.ao/claims/`` (SSOT) and rewrites the derived
        cache atomically.
        """
        index = self._load_index()
        computed = _compute_index_revision(index.agents)
        if computed != index.revision or not _index_path(
            self._workspace_root,
        ).exists():
            self._rebuild_index_locked()

    def _rebuild_index_locked(self) -> None:
        """Rebuild ``_index.v1.json`` from a per-resource file scan.

        Fail-open for the derived cache — scan errors on SSOT files
        (which would indicate corruption) still propagate as
        :class:`ClaimCorruptedError`, but the rebuild itself never
        silently absorbs SSOT failures (W2v2 scope). Writes the full
        agent → resource_id map atomically.
        """
        agents: dict[str, list[str]] = {}
        claims_dir = _claims_dir(self._workspace_root)
        if claims_dir.is_dir():
            for path in claims_dir.glob("*.v1.json"):
                name = path.name
                # Skip underscore-prefixed meta files (_index.v1.json,
                # _fencing.v1.json) which are not per-resource SSOT claims.
                if name.startswith("_"):
                    continue
                resource_id = name[: -len(".v1.json")]
                try:
                    doc = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise ClaimCorruptedError(
                        str(path), f"rebuild scan failed: {exc}",
                    ) from exc
                # SSOT validation happens here — claim_from_dict raises
                # ClaimCorruptedError on schema / revision failure.
                claim = claim_from_dict(doc, source_path=path)
                agents.setdefault(claim.owner_agent_id, []).append(resource_id)
        agents_sorted = {k: sorted(v) for k, v in sorted(agents.items())}
        tuple_view = {k: tuple(v) for k, v in agents_sorted.items()}
        revision = _compute_index_revision(tuple_view)
        generated_at = _now_iso()
        payload = {
            "schema_version": "1",
            "agents": agents_sorted,
            "generated_at": generated_at,
            "revision": revision,
        }
        write_text_atomic(
            _index_path(self._workspace_root),
            json.dumps(payload, sort_keys=True, ensure_ascii=False),
        )

    def _add_to_index(self, owner_agent_id: str, resource_id: str) -> None:
        """Incrementally update the index on acquire."""
        index = self._load_index()
        agents = {k: list(v) for k, v in index.agents.items()}
        if resource_id not in agents.get(owner_agent_id, []):
            agents.setdefault(owner_agent_id, []).append(resource_id)
            agents[owner_agent_id].sort()
        self._write_index(agents)

    def _remove_from_index(self, resource_id: str, owner_agent_id: str) -> None:
        """Incrementally update the index on release."""
        index = self._load_index()
        agents = {k: list(v) for k, v in index.agents.items()}
        if resource_id in agents.get(owner_agent_id, []):
            agents[owner_agent_id].remove(resource_id)
            if not agents[owner_agent_id]:
                del agents[owner_agent_id]
        self._write_index(agents)

    def _write_index(self, agents: Mapping[str, list[str]]) -> None:
        normalised = {k: sorted(v) for k, v in sorted(agents.items())}
        tuple_view = {k: tuple(v) for k, v in normalised.items()}
        payload = {
            "schema_version": "1",
            "agents": normalised,
            "generated_at": _now_iso(),
            "revision": _compute_index_revision(tuple_view),
        }
        write_text_atomic(
            _index_path(self._workspace_root),
            json.dumps(payload, sort_keys=True, ensure_ascii=False),
        )

    def _persist_new_claim(
        self,
        resource_id: str,
        owner_agent_id: str,
        policy: CoordinationPolicy,
    ) -> Claim:
        """Write the fencing advance + claim file + index (B2v2 order)."""
        fencing_state = load_fencing_state(self._workspace_root)
        current_fencing_rev = fencing_state_revision(fencing_state.to_dict())
        token, new_fencing_state = next_token(fencing_state, resource_id)
        # 1. fencing FIRST
        # Use empty-baseline revision when this is the first-ever write.
        expected_rev = (
            current_fencing_rev
            if _claims_dir(self._workspace_root).joinpath(
                "_fencing.v1.json",
            ).exists()
            else empty_fencing_revision()
        )
        save_fencing_state_cas(
            self._workspace_root,
            new_fencing_state,
            expected_revision=expected_rev,
        )
        # 2. claim SECOND
        now = datetime.now(timezone.utc)
        claim_dict = {
            "claim_id": str(uuid.uuid4()),
            "owner_agent_id": owner_agent_id,
            "resource_id": resource_id,
            "fencing_token": token,
            "acquired_at": now.isoformat(),
            "heartbeat_at": now.isoformat(),
            "expires_at": (
                now + timedelta(seconds=policy.expiry_seconds)
            ).isoformat(),
        }
        claim_dict["revision"] = claim_revision(claim_dict)
        write_text_atomic(
            claim_path(self._workspace_root, resource_id),
            json.dumps(claim_dict, sort_keys=True, ensure_ascii=False),
        )
        # 3. index LAST (derived)
        self._add_to_index(owner_agent_id, resource_id)

        _safe_emit_coordination_event(
            self._evidence_sink,
            "claim_acquired",
            {
                "resource_id": resource_id,
                "owner_agent_id": owner_agent_id,
                "claim_id": claim_dict["claim_id"],
                "fencing_token": token,
                "acquired_at": claim_dict["acquired_at"],
            },
        )
        return claim_from_dict(claim_dict)

    def _emit_conflict(
        self,
        resource_id: str,
        *,
        requesting_agent_id: str,
        current: Claim,
        conflict_kind: str,
        now: datetime,
    ) -> None:
        _safe_emit_coordination_event(
            self._evidence_sink,
            "claim_conflict",
            {
                "resource_id": resource_id,
                "requesting_agent_id": requesting_agent_id,
                "current_owner_agent_id": current.owner_agent_id,
                "current_fencing_token": current.fencing_token,
                "conflict_kind": conflict_kind,
                "now": now.isoformat(),
            },
        )
