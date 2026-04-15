"""HITL interrupt + governance approval primitives.

Adapter HITL interrupt tokens and governance approval tokens live in
separate domains. The two ``mint_*`` functions share an implementation
(``secrets.token_urlsafe(48)``) but exist as distinct call sites so
domain misuse is visible at the code level and evidence audit can
split the two streams cleanly.

Resume operations (``resume_interrupt``, ``resume_approval``) are
idempotent by payload hash (plan v2 W8 fix): repeating a resume with an
identical payload returns the same record unchanged; repeating with a
different payload raises ``WorkflowTokenInvalidError(reason=
"resumed_with_different_payload")``. Token mismatch raises with
``reason="token_mismatch"``.

Token implementation is stdlib-only (``secrets`` module, plan v2 B4
fix); no new core dependency.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Literal, Mapping

from ao_kernel.workflow.errors import WorkflowTokenInvalidError

_APPROVAL_GATES = frozenset({
    "pre_diff",
    "pre_apply",
    "pre_pr",
    "pre_merge",
    "post_ci",
    "custom",
})

_APPROVAL_DECISIONS = frozenset({"granted", "denied", "timeout"})


def mint_interrupt_token() -> str:
    """Return a 64-character URL-safe opaque token for adapter HITL resume.

    Uses ``secrets.token_urlsafe(48)`` — 48 bytes of OS entropy encoded
    as URL-safe base64 (~64 chars). Stdlib-only. Separate function from
    ``mint_approval_token`` to keep audit domains distinct at call sites.
    """
    return secrets.token_urlsafe(48)


def mint_approval_token() -> str:
    """Return a 64-character URL-safe opaque token for governance approval.

    Same implementation as ``mint_interrupt_token``; separate function
    for type-safety and audit-domain distinction.
    """
    return secrets.token_urlsafe(48)


@dataclass(frozen=True)
class InterruptRequest:
    """Adapter HITL interrupt record.

    Mirrors ``workflow-run.schema.v1.json::$defs/interrupt_request``.
    ``resumed_at`` and ``response_payload`` stay ``None`` until the
    adapter's interrupt is resumed. The ``adapter_id`` identifies which
    adapter raised the interrupt so replay can route resumes correctly.
    """

    interrupt_id: str
    interrupt_token: str
    emitted_at: str
    adapter_id: str
    question_payload: Mapping[str, Any]
    resumed_at: str | None = None
    response_payload: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class Approval:
    """Governance approval record.

    Mirrors ``workflow-run.schema.v1.json::$defs/approval``. ``decision``
    and ``responded_at`` stay ``None`` until the approver responds.
    ``gate`` identifies the orchestrator gate that requested the
    approval so governance audit can correlate deny decisions to
    workflow stages.
    """

    approval_id: str
    approval_token: str
    gate: Literal[
        "pre_diff",
        "pre_apply",
        "pre_pr",
        "pre_merge",
        "post_ci",
        "custom",
    ]
    requested_at: str
    actor: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    decision: Literal["granted", "denied", "timeout"] | None = None
    responded_at: str | None = None


def create_interrupt(
    adapter_id: str,
    question_payload: Mapping[str, Any],
) -> InterruptRequest:
    """Create a fresh interrupt request with a newly minted token."""
    return InterruptRequest(
        interrupt_id=str(uuid.uuid4()),
        interrupt_token=mint_interrupt_token(),
        emitted_at=_now_iso(),
        adapter_id=adapter_id,
        question_payload=question_payload,
    )


def create_approval(
    gate: str,
    actor: str,
    payload: Mapping[str, Any] | None = None,
) -> Approval:
    """Create a fresh approval record with a newly minted token.

    ``gate`` must be one of the allowed literal values; unknown gates
    raise ``ValueError`` rather than silently coerced to ``custom``.
    """
    if gate not in _APPROVAL_GATES:
        raise ValueError(
            f"Unknown approval gate: {gate!r}; known: {sorted(_APPROVAL_GATES)}"
        )
    # Coerce gate to the Literal type via explicit cast-free assignment.
    # ``gate`` guaranteed to be one of the literal values by the check above.
    return Approval(
        approval_id=str(uuid.uuid4()),
        approval_token=mint_approval_token(),
        gate=gate,  # type: ignore[arg-type]
        requested_at=_now_iso(),
        actor=actor,
        payload=payload if payload is not None else {},
    )


def resume_interrupt(
    request: InterruptRequest,
    *,
    token: str,
    response_payload: Mapping[str, Any],
    run_id: str | None = None,
) -> InterruptRequest:
    """Resume ``request`` with ``response_payload``. Idempotent.

    - Raises ``WorkflowTokenInvalidError(reason="token_mismatch")`` if
      ``token`` does not match ``request.interrupt_token``.
    - If ``request`` is already resumed (``resumed_at`` set), compares
      the existing payload hash with the incoming payload hash:
      matching → returns the existing request unchanged (idempotent);
      mismatching → raises with
      ``reason="resumed_with_different_payload"``.
    - On first successful resume, returns a new request with
      ``resumed_at`` and ``response_payload`` set.
    """
    if token != request.interrupt_token:
        raise WorkflowTokenInvalidError(
            run_id=run_id,
            token_kind="interrupt",
            token_value=token,
            reason="token_mismatch",
        )
    if request.resumed_at is not None:
        existing_hash = _payload_hash(request.response_payload or {})
        incoming_hash = _payload_hash(response_payload)
        if existing_hash == incoming_hash:
            return request
        raise WorkflowTokenInvalidError(
            run_id=run_id,
            token_kind="interrupt",
            token_value=token,
            reason="resumed_with_different_payload",
        )
    return replace(
        request,
        resumed_at=_now_iso(),
        response_payload=response_payload,
    )


def resume_approval(
    approval: Approval,
    *,
    token: str,
    decision: Literal["granted", "denied", "timeout"],
    run_id: str | None = None,
) -> Approval:
    """Resume ``approval`` with ``decision``. Idempotent.

    - Raises ``WorkflowTokenInvalidError(reason="token_mismatch")`` if
      ``token`` does not match ``approval.approval_token``.
    - If ``approval.decision`` is already set, compares values:
      matching → returns the existing approval unchanged (idempotent);
      mismatching → raises with
      ``reason="resumed_with_different_payload"``.
    - On first successful resume, returns a new approval with
      ``decision`` and ``responded_at`` set.

    Raises ``ValueError`` if ``decision`` is not one of the allowed
    literal values (defence in depth against caller type errors).
    """
    if decision not in _APPROVAL_DECISIONS:
        raise ValueError(
            f"Unknown approval decision: {decision!r}; "
            f"known: {sorted(_APPROVAL_DECISIONS)}"
        )
    if token != approval.approval_token:
        raise WorkflowTokenInvalidError(
            run_id=run_id,
            token_kind="approval",
            token_value=token,
            reason="token_mismatch",
        )
    if approval.decision is not None:
        if approval.decision == decision:
            return approval
        raise WorkflowTokenInvalidError(
            run_id=run_id,
            token_kind="approval",
            token_value=token,
            reason="resumed_with_different_payload",
        )
    return replace(
        approval,
        decision=decision,
        responded_at=_now_iso(),
    )


def _payload_hash(payload: Mapping[str, Any]) -> str:
    """Deterministic hex digest of a JSON-serializable payload.

    Uses ``json.dumps(..., sort_keys=True, ensure_ascii=False,
    separators=(",", ":"))`` to match the repo canonicalization
    convention (``canonical_store.store_revision``).
    """
    serialized = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    """Return current UTC time as an ISO-8601 string with ``+00:00`` offset."""
    return datetime.now(timezone.utc).isoformat()
