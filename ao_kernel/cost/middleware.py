"""Cost middleware — pre-dispatch reserve + post-response reconcile
(PR-B2 commit 5a).

Composes the cost-tracking primitives around the LLM transport call:

- :func:`pre_dispatch_reserve` (called BEFORE transport): resolves
  the catalog entry, estimates cost, emits ``llm_cost_estimated``,
  reserves on ``workflow-run.budget.cost_usd`` via CAS-retried
  mutation. Raises fail-closed errors early so the network never
  sees a request that would bust the budget.

- :func:`post_response_reconcile` (called AFTER transport on OK
  status): extracts strict usage, computes actual cost, reconciles
  the reservation (deducts the delta positive, refunds negative),
  appends to the spend ledger with canonical billing digest, emits
  ``llm_spend_recorded``. Handles the usage-missing fail-closed path.

Integration entrypoint :func:`governed_call` lives on
``ao_kernel/llm.py`` (same commit 5a). The middleware functions
below are the building blocks; callers (3 entrypoints — client,
mcp_server, intent_router) interact with ``governed_call`` only.

See ``docs/COST-MODEL.md`` §5 + PR-B2 plan v7 §2.6 for the 18-step
flow spec.
"""

from __future__ import annotations

import datetime as _dt
import logging
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from ao_kernel.cost.catalog import (
    PriceCatalogEntry,
    find_entry,
    load_price_catalog,
)
from ao_kernel.cost.cost_math import (
    compute_cost,
    estimate_cost,
    estimate_output_tokens,
)
from ao_kernel.cost.errors import (
    BudgetExhaustedError,
    CostTrackingConfigError,
    LLMUsageMissingError,
    PriceCatalogNotFoundError,
)
from ao_kernel.cost.ledger import (
    SpendEvent,
    record_spend,
)
from ao_kernel.cost.policy import CostTrackingPolicy
from ao_kernel.workflow.budget import (
    budget_from_dict,
    budget_to_dict,
    record_spend as record_budget_spend,
)
from ao_kernel.workflow.run_store import update_run


logger = logging.getLogger(__name__)


def _count_prompt_tokens(messages: list[Mapping[str, Any]]) -> int:
    """Heuristic prompt-token estimate for pre-dispatch reserve.

    Uses the existing PR-A token counter; no new dependency. Called
    only when cost tracking is active, so the import is lazy.
    """
    from ao_kernel._internal.providers.token_counter import (
        count_tokens_heuristic,
    )

    # Cast Mapping → dict for the counter's type contract; shallow copy
    # preserves the original mapping content.
    return count_tokens_heuristic([dict(m) for m in messages])


def _safe_emit(
    workspace_root: Path,
    run_id: str,
    kind: str,
    payload: Mapping[str, Any],
) -> None:
    """Fail-open evidence emit wrapper (PR-B1 pattern)."""
    try:
        from ao_kernel.executor.evidence_emitter import emit_event

        emit_event(
            workspace_root,
            run_id=run_id,
            kind=kind,
            actor="ao-kernel",
            payload=dict(payload),
        )
    except Exception as exc:  # pragma: no cover — fail-open side-channel
        logger.warning(
            "cost evidence emit failed (fail-open, kind=%s): %s", kind, exc
        )


def _iso_now() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat()


def pre_dispatch_reserve(
    *,
    workspace_root: Path,
    run_id: str,
    step_id: str,
    attempt: int,
    provider_id: str,
    model: str,
    prompt_messages: list[Mapping[str, Any]],
    max_tokens: int | None,
    policy: CostTrackingPolicy,
) -> tuple[Decimal, PriceCatalogEntry]:
    """Pre-dispatch cost estimate + budget reservation.

    Flow (plan v7 §3 steps 3-6):

    1. Load price catalog (LRU 300s, workspace-relative or bundled).
    2. Find entry for (provider_id, model) → ``PriceCatalogNotFoundError``
       if missing (fail-closed, before transport).
    3. Estimate input tokens (heuristic) + output tokens
       (``min(max_tokens, est_in * 0.25)``).
    4. Estimate cost (ignores caching — conservative upper bound).
    5. Emit ``llm_cost_estimated`` (fail-open).
    6. Reserve on run record: check ``budget.cost_usd.remaining >=
       estimate``; if not → ``BudgetExhaustedError``. Else CAS-update
       budget with ``record_spend(cost_usd=estimate)``.
       - If run has ``policy.enabled=true`` AND ``budget.cost_usd is None``
         → ``CostTrackingConfigError`` fail-closed (Option A).

    Returns ``(est_cost, catalog_entry)`` for the caller (governed_call)
    to thread into post-response reconcile.
    """
    catalog = load_price_catalog(workspace_root, policy=policy)
    entry = find_entry(catalog, provider_id, model)
    if entry is None:
        raise PriceCatalogNotFoundError(
            provider_id=provider_id,
            model=model,
            catalog_version=catalog.catalog_version,
        )

    est_input_tokens = _count_prompt_tokens(prompt_messages)
    est_output_tokens = estimate_output_tokens(est_input_tokens, max_tokens)
    est_cost = estimate_cost(entry, est_input_tokens, est_output_tokens)

    _safe_emit(
        workspace_root,
        run_id,
        "llm_cost_estimated",
        {
            "run_id": run_id,
            "step_id": step_id,
            "attempt": attempt,
            "provider_id": provider_id,
            "model": model,
            "est_tokens_input": est_input_tokens,
            "est_tokens_output": est_output_tokens,
            "est_cost_usd": float(est_cost),
            "ts": _iso_now(),
        },
    )

    # CAS-retried reserve. Mutator validates cost_usd axis presence
    # (fail-closed) and raises BudgetExhaustedError on insufficient
    # remaining. The update_run helper handles CAS retry (default 1;
    # we ask for 3 per plan v7 §2.6).
    def _reserve_mutator(record: dict[str, Any]) -> dict[str, Any]:
        budget_dict = record.get("budget")
        if budget_dict is None:
            raise CostTrackingConfigError(
                run_id=run_id,
                details=(
                    "run has no 'budget' field; cost_usd axis is required "
                    "when policy.enabled=true"
                ),
            )
        budget = budget_from_dict(budget_dict)
        if budget.cost_usd is None:
            raise CostTrackingConfigError(
                run_id=run_id,
                details=(
                    "run.budget.cost_usd axis is not configured; workflow "
                    "specs must declare it when policy.enabled=true"
                ),
            )
        # Check remaining >= est_cost BEFORE spending.
        remaining = budget.cost_usd.remaining
        if remaining < est_cost:
            raise BudgetExhaustedError(
                run_id=run_id,
                estimate_usd=str(est_cost),
                remaining_usd=str(remaining),
            )
        new_budget = record_budget_spend(
            budget,
            cost_usd=est_cost,
            run_id=run_id,
        )
        return {**record, "budget": budget_to_dict(new_budget)}

    update_run(
        workspace_root,
        run_id,
        mutator=_reserve_mutator,
        max_retries=3,
    )

    return est_cost, entry


def post_response_reconcile(
    *,
    workspace_root: Path,
    run_id: str,
    step_id: str,
    attempt: int,
    provider_id: str,
    model: str,
    catalog_entry: PriceCatalogEntry,
    est_cost: Decimal,
    raw_response_bytes: bytes,
    policy: CostTrackingPolicy,
    elapsed_ms: float | None = None,
) -> None:
    """Post-response usage extract + reconcile + ledger append.

    Flow (plan v7 §3 steps 7-9):

    1. ``extract_usage_strict`` → ``UsagePresence(None | int)``.
    2. Usage-missing path: record_spend(usage_missing=true, cost=0) +
       emit llm_usage_missing. If ``policy.fail_closed_on_missing_usage``
       → ``LLMUsageMissingError``. Else warn-log.
    3. Success path:
       - ``actual = compute_cost(entry, ti, to, cached or 0)``.
       - Reconcile: CAS-update budget with ``cost_usd = (actual - est)``.
         Positive delta → additional deduct; negative → refund.
         Per plan Q5 iter-1: reservation holds on transport error
         (middleware never reaches this function in that case).
       - record_spend (billing_digest computed).
       - emit llm_spend_recorded (+``duration_ms`` when
         ``elapsed_ms`` passthrough present — PR-B5 C2b absorb).

    Parameters:
        elapsed_ms: Transport wall-clock duration in milliseconds,
            captured by :func:`execute_request` and threaded through
            :func:`ao_kernel.llm.governed_call`. Emitted as
            ``llm_spend_recorded.duration_ms`` so PR-B5 metrics
            derivation can populate ``ao_llm_call_duration_seconds``
            from the canonical LLM-facade timing rather than the
            generic adapter lifecycle events (plan v4 iter-2 fix).
            ``None`` (default) preserves pre-B5 backward compat: the
            emitted event omits ``duration_ms`` entirely and the
            metric histogram skips this call.
    """
    from ao_kernel._internal.prj_kernel_api.llm_response_normalizer import (
        extract_usage_strict,
    )

    usage = extract_usage_strict(raw_response_bytes)

    missing_fields: list[str] = []
    if usage.tokens_input is None:
        missing_fields.append("tokens_input")
    if usage.tokens_output is None:
        missing_fields.append("tokens_output")

    if missing_fields:
        # Usage-missing path: audit-only ledger entry + emit + optional raise.
        event = SpendEvent(
            run_id=run_id,
            step_id=step_id,
            attempt=attempt,
            provider_id=provider_id,
            model=model,
            tokens_input=0,
            tokens_output=0,
            cost_usd=Decimal("0"),
            ts=_iso_now(),
            vendor_model_id=catalog_entry.vendor_model_id,
            usage_missing=True,
        )
        record_spend(workspace_root, event, policy=policy)
        _safe_emit(
            workspace_root,
            run_id,
            "llm_usage_missing",
            {
                "run_id": run_id,
                "step_id": step_id,
                "attempt": attempt,
                "provider_id": provider_id,
                "model": model,
                "missing_fields": list(missing_fields),
                "ts": _iso_now(),
            },
        )
        if policy.fail_closed_on_missing_usage:
            raise LLMUsageMissingError(
                run_id=run_id,
                step_id=step_id,
                attempt=attempt,
                provider_id=provider_id,
                model=model,
                missing_fields=tuple(missing_fields),
            )
        logger.warning(
            "cost reconcile: adapter response missing usage fields %r "
            "for provider=%s model=%s; policy.fail_closed_on_missing_usage="
            "false so continuing (reservation held, no refund)",
            missing_fields,
            provider_id,
            model,
        )
        return

    # Success path. At this point usage.tokens_input / .tokens_output
    # are both non-None ints (narrow here for mypy).
    tokens_input = usage.tokens_input
    tokens_output = usage.tokens_output
    cached = usage.cached_tokens or 0
    # The narrowing above guarantees non-None; cast for static typing.
    assert tokens_input is not None
    assert tokens_output is not None

    actual = compute_cost(
        catalog_entry,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        cached_tokens=cached,
    )
    delta = actual - est_cost

    # Reconcile: add (actual - est) to cost_usd.spent. Negative delta
    # (actual < est) is a refund; record_spend supports negative spend
    # via Decimal arithmetic. Token axes are spent only when configured
    # on the run's budget — unconfigured axes would raise ValueError in
    # _spend_axis.
    def _reconcile_mutator(record: dict[str, Any]) -> dict[str, Any]:
        budget_dict = record.get("budget")
        if budget_dict is None:
            # Middleware already validated on pre_dispatch_reserve; this
            # branch is defensive for CAS-racy mid-reconcile record
            # reshape.
            raise CostTrackingConfigError(
                run_id=run_id,
                details="run.budget dropped between reserve and reconcile",
            )
        budget = budget_from_dict(budget_dict)
        if budget.cost_usd is None:
            raise CostTrackingConfigError(
                run_id=run_id,
                details="run.budget.cost_usd dropped between reserve and reconcile",
            )

        # Compose spend kwargs only for axes actually configured on this
        # run's budget. Unconfigured axes MUST NOT be spent on —
        # _spend_axis raises ValueError for None axes.
        #
        # CNS-032 iter-1 blocker absorb (refined iter-2): legacy
        # workflow-run records with aggregate `tokens` only stay
        # aggregate-only in-memory (no synthesized granular axes). The
        # middleware MUST route legacy token spend through the
        # aggregate axis so completion tokens are actually counted.
        # Three cases emerge:
        #
        # 1. Full granular (both tokens_input + tokens_output set):
        #    spend granular; aggregate auto-adjusts in record_budget_spend.
        # 2. Legacy or partial-with-aggregate (tokens set AND
        #    tokens_output is None): spend the SUM on aggregate — the
        #    tokens_input axis (a back-compat synth or partial config)
        #    is not considered billable-tracking in this mode.
        # 3. Partial granular-only input (tokens_input set but
        #    tokens_output + aggregate both None): track only input.
        spend_kwargs: dict[str, Any] = {"run_id": run_id}
        if delta != 0:
            spend_kwargs["cost_usd"] = delta

        has_full_granular = (
            budget.tokens_input is not None
            and budget.tokens_output is not None
        )
        if has_full_granular:
            spend_kwargs["tokens_input"] = tokens_input
            spend_kwargs["tokens_output"] = tokens_output
        elif budget.tokens is not None:
            # Legacy aggregate-only (or partial granular + aggregate) —
            # aggregate path. Total tokens = input + output.
            spend_kwargs["tokens"] = tokens_input + tokens_output
        elif budget.tokens_input is not None:
            # Partial granular without aggregate: input-only tracking.
            # tokens_output is intentionally unconfigured; operator
            # accepts that output tokens are untracked in this mode.
            spend_kwargs["tokens_input"] = tokens_input
        # else: no token axes anywhere → no token spend.

        # If no axis needs adjustment, skip the call entirely.
        spendable = any(
            k in spend_kwargs
            for k in ("cost_usd", "tokens_input", "tokens_output", "tokens")
        )
        if spendable:
            new_budget = record_budget_spend(budget, **spend_kwargs)
        else:
            new_budget = budget
        return {**record, "budget": budget_to_dict(new_budget)}

    update_run(
        workspace_root,
        run_id,
        mutator=_reconcile_mutator,
        max_retries=3,
    )

    # Ledger append with canonical billing digest.
    event = SpendEvent(
        run_id=run_id,
        step_id=step_id,
        attempt=attempt,
        provider_id=provider_id,
        model=model,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        cost_usd=actual,
        ts=_iso_now(),
        vendor_model_id=catalog_entry.vendor_model_id,
        cached_tokens=cached if cached > 0 else None,
        usage_missing=False,
    )
    record_spend(workspace_root, event, policy=policy)

    # PR-B5 C2b: emit ``duration_ms`` when transport elapsed is known.
    # Canonical source for ``ao_llm_call_duration_seconds`` histogram;
    # omitted on legacy callers (backward-compat per plan v4 R13).
    payload: dict[str, Any] = {
        "run_id": run_id,
        "step_id": step_id,
        "attempt": attempt,
        "provider_id": provider_id,
        "model": model,
        "tokens_input": tokens_input,
        "tokens_output": tokens_output,
        "cached_tokens": cached,
        "cost_usd": float(actual),
        "est_cost_usd": float(est_cost),
        "delta_usd": float(delta),
        "ts": _iso_now(),
    }
    if elapsed_ms is not None:
        payload["duration_ms"] = round(float(elapsed_ms), 3)
    _safe_emit(
        workspace_root,
        run_id,
        "llm_spend_recorded",
        payload,
    )


def _build_adapter_spend_event(
    cost_actual: Mapping[str, Any],
    *,
    run_id: str,
    step_id: str,
    attempt: int,
    provider_id: str,
    model: str,
) -> SpendEvent:
    """Adapter ``cost_actual`` → :class:`SpendEvent` (PR-C3).

    Wire format (master plan v5 iter-5 B3 absorb): tokens live under
    ``cost_actual.tokens_input`` / ``cost_actual.tokens_output`` — NOT
    ``usage.*``. Catalog attribution deferred (v3.3.1+; adapter manifest
    lacks a reliable provider/model → catalog mapping), so
    ``vendor_model_id`` defaults to ``None``. ``cached_tokens`` is NOT
    part of ``agent-adapter-contract.schema.v1.json::cost_record`` —
    builder doesn't read it.
    """
    tokens_in = cost_actual.get("tokens_input")
    tokens_out = cost_actual.get("tokens_output")
    cost_raw = cost_actual.get("cost_usd", 0)
    usage_missing = tokens_in is None or tokens_out is None
    return SpendEvent(
        run_id=run_id,
        step_id=step_id,
        attempt=attempt,
        provider_id=provider_id,
        model=model,
        tokens_input=int(tokens_in or 0),
        tokens_output=int(tokens_out or 0),
        cost_usd=Decimal(str(cost_raw)),
        ts=_iso_now(),
        vendor_model_id=None,
        cached_tokens=None,
        usage_missing=usage_missing,
    )


def post_adapter_reconcile(
    *,
    workspace_root: Path,
    run_id: str,
    step_id: str,
    attempt: int,
    provider_id: str,
    model: str,
    cost_actual: Mapping[str, Any] | None,
    policy: CostTrackingPolicy,
    elapsed_ms: float | None = None,
) -> None:
    """PR-C3: adapter-path cost reconcile.

    Mirrors :func:`post_response_reconcile` for adapter envelopes.
    Called from :meth:`Executor._run_adapter_step` BEFORE the terminal
    ``step_completed``/``step_failed`` event (v5 plan reconcile-before-
    terminal ordering), so a reconcile failure surfaces as a step_failed
    rather than a post-hoc state inconsistency.

    Contract:

    - ``cost_actual is None`` → no-op (adapter did not report usage).
    - ``policy.enabled=false`` → no-op (dormant).
    - ``event.usage_missing=True`` → audit-only ledger entry via
      :func:`record_spend` + ``llm_usage_missing`` evidence emit.
    - Success path: ``record_spend`` (same-digest idempotent) +
      budget CAS (``update_run`` mutator drains ``cost_usd``) +
      ``llm_spend_recorded`` emit with ``source="adapter_path"``.
    - Fail-closed: ledger / budget / config errors propagate
      (:class:`CostTrackingConfigError`, :class:`SpendLedgerDuplicateError`,
      :class:`SpendLedgerCorruptedError` per
      ``docs/COST-MODEL.md`` §7.2); the caller / driver catch
      matrix translates these to ``_StepFailed(category="other")``.
    - Fail-open boundary: ``_safe_emit`` (evidence wrapper)
      remains fail-open — missing evidence doesn't block spend.
    """
    if not policy.enabled:
        return
    if cost_actual is None:
        return

    event = _build_adapter_spend_event(
        cost_actual,
        run_id=run_id,
        step_id=step_id,
        attempt=attempt,
        provider_id=provider_id,
        model=model,
    )

    # Usage-missing: audit-only ledger entry + llm_usage_missing emit
    # (mirror post_response_reconcile contract).
    if event.usage_missing:
        record_spend(workspace_root, event, policy=policy)
        missing_fields = [
            f for f, v in (
                ("tokens_input", cost_actual.get("tokens_input")),
                ("tokens_output", cost_actual.get("tokens_output")),
            ) if v is None
        ]
        _safe_emit(
            workspace_root,
            run_id,
            "llm_usage_missing",
            {
                "source": "adapter_path",
                "run_id": run_id,
                "step_id": step_id,
                "attempt": attempt,
                "provider_id": provider_id,
                "model": model,
                "missing_fields": missing_fields,
                "ts": event.ts,
            },
        )
        return

    # Success path: record spend (idempotent per ledger digest) +
    # CAS-drained budget. Cost errors propagate (fail-closed).
    record_spend(workspace_root, event, policy=policy)

    if event.cost_usd > 0:
        def _adapter_mutator(record: dict[str, Any]) -> dict[str, Any]:
            budget_dict = record.get("budget")
            if budget_dict is None:
                raise CostTrackingConfigError(
                    run_id=run_id,
                    details=(
                        "run.budget dropped between adapter return "
                        "and reconcile"
                    ),
                )
            budget = budget_from_dict(budget_dict)
            if budget.cost_usd is None:
                raise CostTrackingConfigError(
                    run_id=run_id,
                    details=(
                        "run.budget.cost_usd dropped between adapter "
                        "return and reconcile"
                    ),
                )
            new_budget = record_budget_spend(
                budget, cost_usd=event.cost_usd, run_id=run_id,
            )
            return {**record, "budget": budget_to_dict(new_budget)}

        update_run(
            workspace_root, run_id,
            mutator=_adapter_mutator,
            max_retries=3,
        )

    payload: dict[str, Any] = {
        "source": "adapter_path",
        "run_id": run_id,
        "step_id": step_id,
        "attempt": attempt,
        "provider_id": provider_id,
        "model": model,
        "tokens_input": event.tokens_input,
        "tokens_output": event.tokens_output,
        "cost_usd": float(event.cost_usd),
        "ts": event.ts,
    }
    if elapsed_ms is not None:
        payload["duration_ms"] = round(float(elapsed_ms), 3)
    _safe_emit(workspace_root, run_id, "llm_spend_recorded", payload)


__all__ = [
    "pre_dispatch_reserve",
    "post_response_reconcile",
    "post_adapter_reconcile",
]
