"""Tests for ``ao_kernel.cost.cost_math`` — pure deterministic arithmetic."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from ao_kernel.cost.cost_math import (
    compute_cost,
    estimate_cost,
    estimate_output_tokens,
)


def _entry(**overrides):
    """Build a minimal duck-typed catalog entry.

    ``PriceCatalogEntry`` dataclass lands in commit 2; these tests use
    a lightweight namespace so the math module can be validated
    independently.
    """
    base = dict(
        provider_id="anthropic",
        model="claude-3-5-sonnet",
        vendor_model_id="claude-3-5-sonnet-20241022",
        input_cost_per_1k=0.003,
        output_cost_per_1k=0.015,
        cached_input_cost_per_1k=0.0003,
        currency="USD",
        billing_unit="per_1k_tokens",
        effective_date="2024-10-22",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestComputeCost:
    def test_no_caching_standard(self) -> None:
        """Straight formula: 1000 input + 500 output.

        cost = 1000 * 0.003 / 1000 + 500 * 0.015 / 1000
             = 0.003 + 0.0075 = 0.0105 USD
        """
        cost = compute_cost(_entry(), tokens_input=1000, tokens_output=500)
        assert cost == Decimal("0.0105")

    def test_with_caching_discount(self) -> None:
        """200 cached @ 0.0003/1k + 800 billable @ 0.003/1k + 100 output @ 0.015/1k.

        cost = 800 * 0.003 / 1000 + 200 * 0.0003 / 1000 + 100 * 0.015 / 1000
             = 0.0024 + 0.00006 + 0.0015 = 0.00396 USD
        """
        cost = compute_cost(
            _entry(), tokens_input=1000, tokens_output=100, cached_tokens=200
        )
        assert cost == Decimal("0.00396")

    def test_cached_fallback_when_no_cached_rate(self) -> None:
        """When ``cached_input_cost_per_1k`` is None, cached tokens bill
        at the full input rate (safe fallback — no free caching)."""
        entry = _entry(cached_input_cost_per_1k=None)
        cost = compute_cost(entry, tokens_input=1000, tokens_output=0, cached_tokens=200)
        # All 1000 input tokens billed at 0.003/1k = 0.003
        assert cost == Decimal("0.003")

    def test_cached_exceeds_input_raises(self) -> None:
        with pytest.raises(ValueError, match="cached_tokens=200 exceeds"):
            compute_cost(_entry(), tokens_input=100, tokens_output=0, cached_tokens=200)

    def test_negative_input_raises(self) -> None:
        with pytest.raises(ValueError, match="must be non-negative"):
            compute_cost(_entry(), tokens_input=-1, tokens_output=0)

    def test_negative_output_raises(self) -> None:
        with pytest.raises(ValueError, match="must be non-negative"):
            compute_cost(_entry(), tokens_input=0, tokens_output=-1)

    def test_zero_tokens_zero_cost(self) -> None:
        cost = compute_cost(_entry(), tokens_input=0, tokens_output=0)
        assert cost == Decimal("0")

    def test_decimal_precision_not_float(self) -> None:
        """Five sequential spends of 0.1 USD each accumulate exactly to 0.5
        (Decimal aggregation). Float would drift."""
        total = Decimal("0")
        entry = _entry(input_cost_per_1k=100, output_cost_per_1k=0, cached_input_cost_per_1k=None)
        for _ in range(5):
            # 1 input token @ 100/1k = 0.1
            total += compute_cost(entry, tokens_input=1, tokens_output=0)
        assert total == Decimal("0.5")


class TestEstimateCost:
    def test_basic_estimate(self) -> None:
        """500 est input + 200 est output."""
        cost = estimate_cost(_entry(), est_tokens_input=500, est_tokens_output=200)
        # 500 * 0.003 / 1000 + 200 * 0.015 / 1000 = 0.0015 + 0.003 = 0.0045
        assert cost == Decimal("0.0045")

    def test_ignores_caching(self) -> None:
        """Estimate upper-bounds the cost; caching discount only post-response."""
        entry_with_cache = _entry(cached_input_cost_per_1k=0.0003)
        entry_no_cache = _entry(cached_input_cost_per_1k=None)
        # Estimate does NOT look at cache rate — both entries give same estimate.
        assert estimate_cost(entry_with_cache, 1000, 0) == estimate_cost(entry_no_cache, 1000, 0)

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            estimate_cost(_entry(), est_tokens_input=-1, est_tokens_output=0)


class TestEstimateOutputTokens:
    def test_quarter_of_input_when_max_none(self) -> None:
        """est_out = est_in * 0.25 when max_tokens is None."""
        assert estimate_output_tokens(1000, None) == 250
        assert estimate_output_tokens(100, None) == 25
        assert estimate_output_tokens(4, None) == 1  # int floor

    def test_min_with_max_tokens(self) -> None:
        """min(max_tokens, est_in * 0.25)."""
        # 1000 * 0.25 = 250; max_tokens=100 wins.
        assert estimate_output_tokens(1000, 100) == 100
        # 1000 * 0.25 = 250; max_tokens=500 loses (250 wins).
        assert estimate_output_tokens(1000, 500) == 250

    def test_zero_input_returns_zero(self) -> None:
        assert estimate_output_tokens(0, None) == 0
        assert estimate_output_tokens(0, 100) == 0

    def test_negative_input_raises(self) -> None:
        with pytest.raises(ValueError, match="must be non-negative"):
            estimate_output_tokens(-1, None)

    def test_negative_max_tokens_raises(self) -> None:
        with pytest.raises(ValueError, match="must be non-negative"):
            estimate_output_tokens(100, -1)

    def test_max_tokens_zero_wins(self) -> None:
        """max_tokens=0 means caller explicitly asks for no output; estimate honors."""
        assert estimate_output_tokens(1000, 0) == 0
