"""Tests for ``ao_kernel.cost.routing`` — tuple-partition helper
for cost-aware model selection (PR-B3)."""

from __future__ import annotations

from typing import Any, Mapping

from ao_kernel.cost.catalog import PriceCatalog, PriceCatalogEntry
from ao_kernel.cost.routing import (
    _PROVIDER_ALIAS_MAP,
    _resolve_catalog_entry,
    compute_model_cost_per_1k,
    sort_providers_by_cost,
)


def _entry(
    provider_id: str,
    model: str,
    input_cost: float,
    output_cost: float,
) -> PriceCatalogEntry:
    return PriceCatalogEntry(
        provider_id=provider_id,
        model=model,
        input_cost_per_1k=input_cost,
        output_cost_per_1k=output_cost,
        currency="USD",
        billing_unit="per_1k_tokens",
        effective_date="2024-01-01",
    )


def _catalog(entries: tuple[PriceCatalogEntry, ...]) -> PriceCatalog:
    return PriceCatalog(
        catalog_version="test",
        generated_at="2026-04-18T00:00:00+00:00",
        source="bundled",
        stale_after="2099-01-01T00:00:00+00:00",
        checksum="sha256:test",
        entries=entries,
    )


# Bundled reference entries: cost per-1k averages
#   claude-3-5-haiku  : (0.0008 + 0.004)  / 2 = 0.00240
#   gpt-4o-mini       : (0.00015 + 0.0006)/ 2 = 0.000375
#   gemini-1.5-pro    : (0.00125 + 0.005) / 2 = 0.003125
_ENTRIES = (
    _entry("anthropic", "claude-3-5-haiku", 0.0008, 0.004),
    _entry("openai", "gpt-4o-mini", 0.00015, 0.0006),
    _entry("google", "gemini-1.5-pro", 0.00125, 0.005),
)


_PROVIDERS_MAP: Mapping[str, Any] = {
    "claude": {"pinned_model_id": "claude-3-5-haiku"},
    "openai": {"pinned_model_id": "gpt-4o-mini"},
    "google": {"pinned_model_id": "gemini-1.5-pro"},
    "deepseek": {"pinned_model_id": "deepseek-v2"},  # absent from catalog
}


class TestComputeModelCostPer1k:
    def test_simple_average(self) -> None:
        entry = _entry("openai", "gpt-4o-mini", 0.001, 0.003)
        assert compute_model_cost_per_1k(entry) == 0.002

    def test_cached_field_ignored(self) -> None:
        """cached_input_cost_per_1k must not influence the routing cost."""
        entry = PriceCatalogEntry(
            provider_id="anthropic",
            model="claude-3-5-haiku",
            input_cost_per_1k=0.001,
            output_cost_per_1k=0.003,
            currency="USD",
            billing_unit="per_1k_tokens",
            effective_date="2024-01-01",
            cached_input_cost_per_1k=0.0001,
        )
        assert compute_model_cost_per_1k(entry) == 0.002


class TestResolveCatalogEntry:
    def test_direct_match_no_alias_needed(self) -> None:
        """'google' (router) == 'google' (catalog) — no alias hop."""
        catalog = _catalog(_ENTRIES)
        entry = _resolve_catalog_entry(
            "google",
            providers_map=_PROVIDERS_MAP,
            catalog=catalog,
        )
        assert entry is not None
        assert entry.provider_id == "google"
        assert entry.model == "gemini-1.5-pro"

    def test_alias_claude_to_anthropic(self) -> None:
        """Router 'claude' short name maps to catalog 'anthropic'."""
        assert _PROVIDER_ALIAS_MAP["claude"] == "anthropic"
        catalog = _catalog(_ENTRIES)
        entry = _resolve_catalog_entry(
            "claude",
            providers_map=_PROVIDERS_MAP,
            catalog=catalog,
        )
        assert entry is not None
        assert entry.provider_id == "anthropic"
        assert entry.model == "claude-3-5-haiku"

    def test_missing_provider_returns_none(self) -> None:
        """Provider not in providers_map (NO_SLOT) → None."""
        catalog = _catalog(_ENTRIES)
        entry = _resolve_catalog_entry(
            "unknown-provider",
            providers_map=_PROVIDERS_MAP,
            catalog=catalog,
        )
        assert entry is None

    def test_missing_pinned_model_returns_none(self) -> None:
        """providers_map entry without pinned_model_id → None."""
        providers_map = {"claude": {}}  # no pinned_model_id
        catalog = _catalog(_ENTRIES)
        entry = _resolve_catalog_entry(
            "claude",
            providers_map=providers_map,
            catalog=catalog,
        )
        assert entry is None

    def test_catalog_miss_returns_none(self) -> None:
        """deepseek has a pinned model but catalog has no entry for it."""
        catalog = _catalog(_ENTRIES)
        entry = _resolve_catalog_entry(
            "deepseek",
            providers_map=_PROVIDERS_MAP,
            catalog=catalog,
        )
        assert entry is None


class TestSortProvidersByCost:
    def test_all_known_ascending(self) -> None:
        """2+ providers, all in catalog → sorted ascending by avg cost."""
        catalog = _catalog(_ENTRIES)
        known, unknown = sort_providers_by_cost(
            provider_order=["claude", "openai", "google"],
            providers_map=_PROVIDERS_MAP,
            catalog=catalog,
        )
        # Cheapest-first: openai (0.000375) < claude (0.0024) < google (0.003125)
        assert known == ["openai", "claude", "google"]
        assert unknown == []

    def test_mixed_known_unknown_partition(self) -> None:
        """Known → sorted; unknown → original order preserved."""
        catalog = _catalog(_ENTRIES)
        known, unknown = sort_providers_by_cost(
            provider_order=["deepseek", "claude", "qwen", "openai"],
            providers_map=_PROVIDERS_MAP,
            catalog=catalog,
        )
        # claude (0.0024) + openai (0.000375) known → openai before claude
        assert known == ["openai", "claude"]
        # deepseek (catalog miss) and qwen (no providers_map entry) → unknown
        assert unknown == ["deepseek", "qwen"]

    def test_all_unknown_empty_known(self) -> None:
        """No provider has a catalog entry → known empty, unknown
        preserves original provider_order."""
        catalog = _catalog(_ENTRIES)
        known, unknown = sort_providers_by_cost(
            provider_order=["deepseek", "qwen", "xai"],
            providers_map=_PROVIDERS_MAP,
            catalog=catalog,
        )
        assert known == []
        assert unknown == ["deepseek", "qwen", "xai"]

    def test_stable_sort_equal_costs(self) -> None:
        """Providers with identical avg cost preserve input order (stable)."""
        # Two providers, same model cost (0.001 avg)
        entries = (
            _entry("anthropic", "model-a", 0.001, 0.001),
            _entry("openai", "model-b", 0.001, 0.001),
        )
        providers_map = {
            "claude": {"pinned_model_id": "model-a"},
            "openai": {"pinned_model_id": "model-b"},
        }
        catalog = _catalog(entries)

        known, unknown = sort_providers_by_cost(
            provider_order=["openai", "claude"],
            providers_map=providers_map,
            catalog=catalog,
        )
        # Equal cost → input order preserved: openai first (not claude)
        assert known == ["openai", "claude"]
        assert unknown == []

    def test_empty_provider_order(self) -> None:
        """Empty input → empty partition."""
        catalog = _catalog(_ENTRIES)
        known, unknown = sort_providers_by_cost(
            provider_order=[],
            providers_map=_PROVIDERS_MAP,
            catalog=catalog,
        )
        assert known == []
        assert unknown == []
