"""Cost-aware routing helpers (PR-B3).

Partitions a ``provider_order`` list into known-cost and unknown-cost
buckets using the price catalog. The router (``llm_router.resolve``)
applies drop-if-any-known / fallback-if-none-known semantics per the
plan v5 §2.4 contract.

All helpers are pure: no evidence emission, no ledger write, no
network call. See :mod:`ao_kernel.cost.catalog` for catalog loading
and :mod:`ao_kernel.cost.cost_math` for billing-side cost
computation (this module's ``compute_model_cost_per_1k`` is for
routing comparison only).
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ao_kernel.cost.catalog import PriceCatalog, PriceCatalogEntry, find_entry


# Router provider_id (llm_provider_map.v1.json) → price catalog
# provider_id (price-catalog.v1.json). Exact-match coverage is
# partial; providers without a catalog entry resolve to
# unknown-bucket semantics via :func:`sort_providers_by_cost` and
# are handled by router-side drop-or-fallback logic.
#
# Model aliasing is intentionally absent in v1 — uncovered models
# flow through the unknown bucket. FAZ-C scope.
_PROVIDER_ALIAS_MAP: Mapping[str, str] = {
    "claude": "anthropic",     # router short name → catalog vendor name
    "openai": "openai",
    "google": "google",
    "deepseek": "deepseek",    # no bundled catalog entries → unknown bucket
    "qwen": "qwen",
    "xai": "xai",
}


def compute_model_cost_per_1k(entry: PriceCatalogEntry) -> float:
    """Simple average of ``input_cost_per_1k`` + ``output_cost_per_1k``, USD.

    Used for routing comparison ONLY — never for billing. Billing
    uses actual token counts via
    :func:`ao_kernel.cost.cost_math.compute_cost`.

    ``cached_input_cost_per_1k`` is deliberately ignored: routing
    decisions assume a fresh call; cache hits are a per-call
    property, not a model property.
    """
    return (entry.input_cost_per_1k + entry.output_cost_per_1k) / 2.0


def _resolve_catalog_entry(
    provider_id: str,
    providers_map: Mapping[str, Any],
    catalog: PriceCatalog,
) -> PriceCatalogEntry | None:
    """Resolve (router provider_id) → PriceCatalogEntry | None.

    Alias-aware: the router's short provider name is normalized via
    :data:`_PROVIDER_ALIAS_MAP` before catalog lookup. Returns
    ``None`` on any missing step: no providers_map entry (NO_SLOT),
    no pinned ``pinned_model_id``, or catalog miss on
    ``(provider, model)``.
    """
    provider_entry = providers_map.get(provider_id)
    if not isinstance(provider_entry, Mapping):
        return None

    pinned_model = provider_entry.get("pinned_model_id")
    if not isinstance(pinned_model, str) or not pinned_model:
        return None

    catalog_provider = _PROVIDER_ALIAS_MAP.get(provider_id, provider_id)
    return find_entry(catalog, catalog_provider, pinned_model)


def sort_providers_by_cost(
    provider_order: Sequence[str],
    *,
    providers_map: Mapping[str, Any],
    catalog: PriceCatalog,
) -> tuple[list[str], list[str]]:
    """Partition ``provider_order`` into (known_cost_sorted, unknown_list).

    Semantics (plan v5 §2.3 — tek yerde):

    - For each provider_id in provider_order, resolve
      (catalog_provider_id, pinned_model_id) via
      :data:`_PROVIDER_ALIAS_MAP` + providers_map.
    - Catalog lookup via
      :func:`ao_kernel.cost.catalog.find_entry` →
      cost = :func:`compute_model_cost_per_1k`.
    - Partition:

      * known_cost: entries whose (provider, model) has a catalog
        entry.
      * unknown_list: providers whose catalog lookup returned None
        (missing catalog entry, NO_SLOT, no pinned_model_id).

    - Sort known_cost ascending by cost (stable among equal costs).
    - Return ``(known_cost_sorted, unknown_list)``.

    The helper **does not eliminate** unknowns — router-side decides
    drop-if-any-known vs fallback-if-none-known. Stable sort
    preserves input order among equal-cost entries and the
    unknown_list keeps its original provider_order ordering.
    """
    known_pairs: list[tuple[str, float]] = []
    unknown: list[str] = []

    for provider_id in provider_order:
        entry = _resolve_catalog_entry(
            provider_id,
            providers_map=providers_map,
            catalog=catalog,
        )
        if entry is None:
            unknown.append(provider_id)
        else:
            known_pairs.append(
                (provider_id, compute_model_cost_per_1k(entry)),
            )

    known_pairs.sort(key=lambda pair: pair[1])
    known_sorted = [pair[0] for pair in known_pairs]
    return known_sorted, unknown


__all__ = [
    "compute_model_cost_per_1k",
    "sort_providers_by_cost",
]
