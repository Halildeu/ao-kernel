"""Cost runtime — price catalog, spend ledger, budget extension (FAZ-B PR-B2).

Public API for the cost governance pipeline. Workspaces opt in by
setting ``policy_cost_tracking.enabled: true`` in their workspace
override; the bundled default ships dormant.

Surface grows across the PR-B2 commit DAG:

- **Commit 1 (this module's initial state)**: typed errors, policy
  loader, deterministic cost math.
- **Commit 2**: price catalog loader with checksum + stale gate.
- **Commit 3**: spend ledger with canonical billing-digest idempotency.
- **Commit 4**: (workflow.budget widen; external to ``cost/``).
- **Commit 5a**: cost middleware + ``llm.governed_call`` wrapper.
- **Commit 5b**: caller entrypoint wire (client + mcp + intent_router).

See ``docs/COST-MODEL.md`` for the contract walk-through.
"""

from __future__ import annotations

from ao_kernel.cost.cost_math import (
    compute_cost,
    estimate_cost,
    estimate_output_tokens,
)
from ao_kernel.cost.errors import (
    BudgetExhaustedError,
    CostTrackingConfigError,
    CostTrackingDisabledError,
    CostTrackingError,
    LLMUsageMissingError,
    PriceCatalogChecksumError,
    PriceCatalogNotFoundError,
    PriceCatalogStaleError,
    SpendLedgerCorruptedError,
    SpendLedgerDuplicateError,
)
from ao_kernel.cost.policy import (
    CostTrackingPolicy,
    RoutingByCost,
    load_cost_policy,
)


__all__ = [
    # Cost math
    "compute_cost",
    "estimate_cost",
    "estimate_output_tokens",
    # Policy
    "CostTrackingPolicy",
    "RoutingByCost",
    "load_cost_policy",
    # Errors
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
]
