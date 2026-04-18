"""Typed error hierarchy for the cost runtime (PR-B2).

See ``docs/COST-MODEL.md`` §§4-10 and PR-B2 plan v7 §2 for the full
semantic contract each error represents. Public API callers key
recovery logic off the subclass type + the structured fields each
subclass carries.
"""

from __future__ import annotations


class CostTrackingError(Exception):
    """Base class for all cost runtime errors.

    Subclasses carry structured fields (``workspace_root``, ``run_id``,
    ``catalog_path``, etc.) so operators can distinguish root causes
    from the exception type alone.
    """


class CostTrackingDisabledError(CostTrackingError):
    """Raised when a cost public API is invoked while policy.enabled=false.

    Callers are expected to guard cost pathways with a dormant-gate
    check. This error signals that the caller skipped the gate and
    invoked the runtime anyway. The cost middleware wraps all public
    pathways behind ``policy.enabled`` and bypasses transparently;
    this error surfaces only when a downstream module skips the
    wrapper.
    """


class CostTrackingConfigError(CostTrackingError):
    """Raised when cost policy is enabled but the workflow-run budget
    lacks the required ``cost_usd`` axis.

    PR-B2 v3 iter-2 B2 absorb (Option A): budget.cost_usd is optional
    at the schema level, but when ``policy.enabled=true`` the run MUST
    declare this axis. Operator migration: workflow specs should add
    ``budget.cost_usd`` before flipping the policy flag. Fail-closed
    early — before transport hits the network, before any ledger write.
    """

    def __init__(self, run_id: str, details: str = "") -> None:
        self.run_id = run_id
        self.details = details
        super().__init__(
            f"run {run_id!r} cost policy is enabled but run.budget.cost_usd "
            f"axis is not configured. {details}".strip()
        )


class PriceCatalogNotFoundError(CostTrackingError):
    """Raised when the price catalog has no entry for ``(provider_id, model)``.

    Fail-closed: the operator enabled cost policy but a specific
    adapter invocation referenced a model absent from the catalog.
    Resolution is catalog-side (add the entry and rev the
    ``catalog_version``) or routing-side (use a model covered by the
    catalog). Raised BEFORE transport — the billable call never hits
    the network.
    """

    def __init__(
        self,
        provider_id: str,
        model: str,
        catalog_version: str,
    ) -> None:
        self.provider_id = provider_id
        self.model = model
        self.catalog_version = catalog_version
        super().__init__(
            f"price catalog version {catalog_version!r} has no entry for "
            f"provider={provider_id!r} model={model!r}"
        )


class PriceCatalogChecksumError(CostTrackingError):
    """Raised when loaded catalog's ``checksum`` does not match the
    recomputed SHA-256 over ``entries[]``.

    Protects against in-place edits that skip ``catalog_version``
    bumps. The catalog on disk is treated as tampered and the loader
    refuses it. Operators must rev the version and compute the new
    checksum via the canonical JSON canon (``sort_keys=True,
    ensure_ascii=False, separators=(",",":")``).
    """

    def __init__(
        self,
        catalog_path: str,
        expected_checksum: str,
        actual_checksum: str,
    ) -> None:
        self.catalog_path = catalog_path
        self.expected_checksum = expected_checksum
        self.actual_checksum = actual_checksum
        super().__init__(
            f"price catalog at {catalog_path!r} checksum mismatch: "
            f"expected {expected_checksum!r}, computed {actual_checksum!r}"
        )


class PriceCatalogStaleError(CostTrackingError):
    """Raised when ``policy.strict_freshness=true`` and the catalog's
    ``stale_after`` timestamp is in the past.

    Default policy (``strict_freshness=false``) emits a warn-level log
    and returns the catalog; operators who want fail-closed on stale
    pricing flip the knob and get this exception instead.
    """

    def __init__(
        self,
        catalog_path: str,
        stale_after: str,
        now: str,
    ) -> None:
        self.catalog_path = catalog_path
        self.stale_after = stale_after
        self.now = now
        super().__init__(
            f"price catalog at {catalog_path!r} is stale "
            f"(stale_after={stale_after!r}, now={now!r}); "
            f"strict_freshness=true blocks use"
        )


class SpendLedgerDuplicateError(CostTrackingError):
    """Raised when the ledger writer sees a duplicate
    ``(run_id, step_id, attempt)`` key with a DIFFERENT billing_digest.

    Idempotent no-op (same digest) is handled silently with a warn
    log; this error surfaces only for real caller bugs (the same
    retry produced a different billable payload). Fail-closed.
    """

    def __init__(
        self,
        run_id: str,
        step_id: str,
        attempt: int,
        existing_digest: str,
        new_digest: str,
    ) -> None:
        self.run_id = run_id
        self.step_id = step_id
        self.attempt = attempt
        self.existing_digest = existing_digest
        self.new_digest = new_digest
        super().__init__(
            f"spend ledger duplicate for "
            f"(run_id={run_id!r}, step_id={step_id!r}, attempt={attempt}): "
            f"existing digest {existing_digest!r} != new {new_digest!r}"
        )


class SpendLedgerCorruptedError(CostTrackingError):
    """Raised when the idempotency scan of the ledger hits a line that
    cannot be parsed as JSON (or fails schema validation).

    Fail-closed: operator must repair the ledger before cost runtime
    can continue. Corruption surfaces early so undetected partial
    writes do not silently block all subsequent record_spend calls.
    """

    def __init__(
        self,
        ledger_path: str,
        line_number: int,
        reason: str,
    ) -> None:
        self.ledger_path = ledger_path
        self.line_number = line_number
        self.reason = reason
        super().__init__(
            f"spend ledger {ledger_path!r} line {line_number} corrupted: {reason}"
        )


class LLMUsageMissingError(CostTrackingError):
    """Raised when the adapter's response lacks ``tokens_input`` or
    ``tokens_output`` AND ``policy.fail_closed_on_missing_usage=true``.

    Audit trail preserved: a ledger line with ``usage_missing=true``
    and ``cost_usd=0`` is recorded before the raise. Operators in
    audit-only environments (billing reconciled out-of-band) can set
    the flag false to warn-log and continue.
    """

    def __init__(
        self,
        run_id: str,
        step_id: str,
        attempt: int,
        provider_id: str,
        model: str,
        missing_fields: tuple[str, ...],
    ) -> None:
        self.run_id = run_id
        self.step_id = step_id
        self.attempt = attempt
        self.provider_id = provider_id
        self.model = model
        self.missing_fields = missing_fields
        super().__init__(
            f"adapter response missing token usage fields "
            f"{missing_fields!r} for provider={provider_id!r} "
            f"model={model!r} (run_id={run_id!r}, step_id={step_id!r}, "
            f"attempt={attempt})"
        )


class BudgetExhaustedError(CostTrackingError):
    """Raised when a pre-dispatch cost estimate exceeds the remaining
    ``budget.cost_usd.remaining`` on the workflow run.

    Fail-closed BEFORE transport: the adapter never hits the network
    when this fires. Distinct from ``WorkflowBudgetExhaustedError``
    (PR-A1) — that one covers aggregate token/time budget triggered
    by ``record_spend`` at any axis; this one is specifically the
    cost axis at pre-dispatch time, before any LLM call cost is
    actually incurred.
    """

    def __init__(
        self,
        run_id: str,
        estimate_usd: str,
        remaining_usd: str,
    ) -> None:
        self.run_id = run_id
        self.estimate_usd = estimate_usd
        self.remaining_usd = remaining_usd
        super().__init__(
            f"budget exhausted for run {run_id!r}: "
            f"estimate={estimate_usd} USD exceeds "
            f"remaining={remaining_usd} USD"
        )


class RoutingCatalogMissingError(CostTrackingError):
    """Raised when cost-aware routing is active (``routing_by_cost.enabled=true``
    + ``priority="lowest_cost"``) AND the price catalog cannot be
    loaded AND ``fail_closed_on_catalog_missing=true``.

    Fail-closed: the router refuses to fall back to
    ``provider_priority`` silently when the operator has opted into
    strict catalog-backed selection. Operators who want warn-log
    fallback flip ``fail_closed_on_catalog_missing=false``.

    Wraps the underlying catalog load failure as ``__cause__``
    (``PriceCatalogNotFoundError``, ``PriceCatalogChecksumError``,
    ``PriceCatalogStaleError``, JSON decode error, schema error,
    etc.) so operators can drill down to the exact remediation.
    """

    def __init__(
        self,
        provider_order: list[str],
        target_class: str,
        workspace_root: str,
    ) -> None:
        self.provider_order = provider_order
        self.target_class = target_class
        self.workspace_root = workspace_root
        super().__init__(
            f"routing_by_cost active but price catalog load failed "
            f"(class={target_class!r}, providers={provider_order!r}, "
            f"workspace={workspace_root!r})"
        )


__all__ = [
    "CostTrackingError",
    "CostTrackingDisabledError",
    "CostTrackingConfigError",
    "PriceCatalogNotFoundError",
    "PriceCatalogChecksumError",
    "PriceCatalogStaleError",
    "SpendLedgerDuplicateError",
    "SpendLedgerCorruptedError",
    "LLMUsageMissingError",
    "BudgetExhaustedError",
    "RoutingCatalogMissingError",
]
