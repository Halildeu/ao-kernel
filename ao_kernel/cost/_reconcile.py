"""Shared marker-driven spend reconcile helper (PR-C3.2).

Both ``post_response_reconcile`` (governed_call path) and
``post_adapter_reconcile`` (executor adapter path) now flow through
:func:`apply_spend_with_marker`. The helper unifies three invariants
that previously drifted between the two call sites:

1. **Ledger-first ordering**: :func:`record_spend` runs BEFORE budget
   CAS. Crash window semantics: ledger entry may exist without a
   matching marker, but NEVER the reverse. Audit integrity preserved.

2. **Marker-driven idempotency**: Budget mutation + evidence emit both
   gate on ``workflow-run.cost_reconciled`` — a per-run array keyed by
   ``(source, step_id, attempt, billing_digest)``. Source of truth is
   the run record, NOT the ledger outcome, because a duplicate ledger
   call could race a non-committed budget CAS (v3.3.0 shipped bug).

3. **Path-specific budget mutation**: governed_call needs ``delta +
   token axes``; adapter path needs ``cost_usd only``; usage_missing
   needs ``no-op``. Caller provides the mutation callback; helper owns
   the idempotency envelope.

The helper returns ``True`` when a NEW marker was committed. Callers
use that signal to emit evidence exactly once — duplicate calls (retry,
crash-recovery) silently skip.

Scope: post-reconcile phase idempotency. This PR does NOT address
duplicate ``pre_dispatch_reserve`` (separate problem: reserve keys off
``estimate_cost``, not billing digest).

See ``.claude/plans/`` PR-C3.2 plan v4 for the adversarial Codex
consultation record (CNS-20260418-033 thread).
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any, Callable, Literal

from ao_kernel.cost.ledger import (
    SpendEvent,
    record_spend,
)
from ao_kernel.cost.policy import CostTrackingPolicy
from ao_kernel.workflow.run_store import update_run


BudgetMutator = Callable[[dict[str, Any]], dict[str, Any]]
"""Path-specific budget mutation callback.

The callback is invoked INSIDE the run-store CAS mutator, so it must be
pure (no I/O, no side effects). Raise ``CostTrackingConfigError`` for
fail-closed config gaps; the exception propagates through
``update_run`` to the caller.
"""


ReconcileSource = Literal["adapter_path", "governed_call", "usage_missing"]
"""Discriminator recorded on each marker — lets operators trace which
reconcile path produced a given budget drain."""


def _iso_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.%f+00:00"
    )


def apply_spend_with_marker(
    workspace_root: Path,
    run_id: str,
    event: SpendEvent,
    *,
    policy: CostTrackingPolicy,
    source: ReconcileSource,
    budget_mutator: BudgetMutator,
) -> bool:
    """Ledger append + marker-guarded budget CAS.

    Preconditions:

    - ``event.billing_digest`` MUST be precomputed (non-empty). Callers
      invoke :func:`compute_billing_digest` and use ``dataclasses.replace``
      to populate before calling this helper. A marker key without the
      digest would allow same-cost different-run-scope collisions to
      suppress each other (Codex iter-3 bulgu #2).

    Returns:

    - ``True`` when a NEW marker was committed in the run record. The
      caller SHOULD emit the ``llm_spend_recorded`` / ``llm_usage_missing``
      evidence event.
    - ``False`` when a matching marker already exists. The caller MUST
      NOT emit evidence (duplicate emit would violate audit replay
      invariants — Codex iter-3 bulgu #3).

    Raises:

    - :class:`ValueError` when ``billing_digest`` is empty.
    - :class:`ao_kernel.cost.errors.CostTrackingConfigError` propagated
      from ``budget_mutator`` (fail-closed).
    - :class:`ao_kernel.cost.errors.BudgetExhaustedError` propagated
      from ``record_budget_spend`` inside the mutator.
    - :class:`ao_kernel.cost.errors.SpendLedgerDuplicateError` propagated
      from ``record_spend`` when the caller retries with a different
      digest under the same ``(run_id, step_id, attempt)`` key (caller
      bug, distinct billing payload).

    Crash semantics:

    - Crash after ``record_spend`` and before marker stamp → next call
      succeeds: ``record_spend`` is silent-no-op on matching digest,
      marker is absent, mutator applies budget + stamps marker.
    - Crash after marker stamp and before evidence emit → next call
      returns ``False``: marker is present, mutator is no-op; caller
      correctly skips duplicate emit.

    Note on duplicate-call side effects: the budget + marker array are
    unchanged on a duplicate call, BUT ``update_run`` unconditionally
    stamps ``updated_at`` and recomputes ``revision`` ([run_store.py
    _mutate_with_cas]). That is, a duplicate reconcile is a budget /
    marker / ledger no-op AND an evidence no-op, but it does produce
    one additional revision tick on the run record. This is intentional
    and cheap; callers who care about strict write-once semantics
    should gate the second call higher up.
    """
    if not event.billing_digest:
        raise ValueError(
            "apply_spend_with_marker requires precomputed billing_digest; "
            "call compute_billing_digest() first and rebuild the event"
        )

    # 1. Ledger append — idempotent on (run_id, step_id, attempt,
    #    billing_digest). Runs UNCONDITIONALLY; same-digest duplicate
    #    is a silent warn-log inside record_spend. Marker is the
    #    cursor, not the ledger outcome (Codex iter-2 bulgu #1).
    record_spend(workspace_root, event, policy=policy)

    committed = False

    def _mutator(record: dict[str, Any]) -> dict[str, Any]:
        nonlocal committed
        markers = record.get("cost_reconciled", [])
        marker_key = (
            source,
            event.step_id,
            event.attempt,
            event.billing_digest,
        )
        for existing in markers:
            existing_key = (
                existing.get("source"),
                existing.get("step_id"),
                existing.get("attempt"),
                existing.get("billing_digest"),
            )
            if existing_key == marker_key:
                return record  # already applied, committed stays False

        # Apply path-specific budget mutation. The callback may raise
        # fail-closed errors; the exception bubbles through update_run
        # and this helper to the original caller.
        new_record = budget_mutator(dict(record))

        # Stamp marker AFTER budget success. Two-phase ordering inside
        # a single CAS: the run-store revision lock guarantees atomic
        # commit of both budget + marker.
        new_markers = list(markers) + [
            {
                "source": source,
                "step_id": event.step_id,
                "attempt": event.attempt,
                "billing_digest": event.billing_digest,
                "recorded_at": _iso_now(),
            }
        ]
        new_record["cost_reconciled"] = new_markers
        committed = True
        return new_record

    update_run(
        workspace_root,
        run_id,
        mutator=_mutator,
        max_retries=3,
    )
    return committed


__all__ = [
    "apply_spend_with_marker",
    "BudgetMutator",
    "ReconcileSource",
]
