"""Tests for memory tier enforcement — hot/warm/cold classification."""

from __future__ import annotations

from ao_kernel.context.memory_tiers import classify_tier, enforce_tier_budgets


NOW = "2026-04-19T12:00:00Z"


class TestClassifyTier:
    def test_high_confidence_recent_is_hot(self):
        d = {"confidence": 0.9, "created_at": "2026-04-13T12:00:00Z"}
        assert classify_tier(d, now=NOW) == "hot"

    def test_medium_confidence_is_warm(self):
        d = {"confidence": 0.5, "created_at": "2026-04-01T12:00:00Z"}
        assert classify_tier(d, now=NOW) == "warm"

    def test_old_low_confidence_is_cold(self):
        d = {"confidence": 0.2, "created_at": "2025-01-01T12:00:00Z"}
        assert classify_tier(d, now=NOW) == "cold"

    def test_no_timestamp_defaults_cold(self):
        d = {"confidence": 0.3}
        assert classify_tier(d, now=NOW) == "cold"

    def test_high_confidence_old_is_warm(self):
        d = {"confidence": 0.8, "created_at": "2025-06-01T12:00:00Z"}
        assert classify_tier(d, now=NOW) == "warm"


class TestEnforceTierBudgets:
    def test_within_budget_unchanged(self):
        decisions = [
            {"key": f"k{i}", "confidence": 0.9, "created_at": "2026-04-13T12:00:00Z"}
            for i in range(5)
        ]
        tiers = enforce_tier_budgets(decisions, now=NOW)
        assert len(tiers["hot"]) == 5
        assert len(tiers["warm"]) == 0
        assert len(tiers["cold"]) == 0

    def test_hot_overflow_demotes_to_warm(self):
        decisions = [
            {"key": f"k{i}", "confidence": 0.9, "created_at": "2026-04-13T12:00:00Z"}
            for i in range(35)
        ]
        tiers = enforce_tier_budgets(
            decisions,
            tier_config={"hot": {"max_rules": 30}, "warm": {"max_rules": 50}},
            now=NOW,
        )
        assert len(tiers["hot"]) == 30
        assert len(tiers["warm"]) == 5  # overflow demoted

    def test_warm_overflow_demotes_to_cold(self):
        decisions = [
            {"key": f"k{i}", "confidence": 0.5, "created_at": "2026-03-01T12:00:00Z"}
            for i in range(60)
        ]
        tiers = enforce_tier_budgets(
            decisions,
            tier_config={"hot": {"max_rules": 30}, "warm": {"max_rules": 50}},
            now=NOW,
        )
        assert len(tiers["warm"]) <= 50
        assert len(tiers["cold"]) >= 10

    def test_empty_decisions(self):
        tiers = enforce_tier_budgets([], now=NOW)
        assert tiers == {"hot": [], "warm": [], "cold": []}

    def test_mixed_tiers(self):
        decisions = [
            {"key": "hot1", "confidence": 0.9, "created_at": "2026-04-13T12:00:00Z"},
            {"key": "warm1", "confidence": 0.5, "created_at": "2026-03-01T12:00:00Z"},
            {"key": "cold1", "confidence": 0.1, "created_at": "2025-01-01T12:00:00Z"},
        ]
        tiers = enforce_tier_budgets(decisions, now=NOW)
        assert len(tiers["hot"]) == 1
        assert len(tiers["warm"]) == 1
        assert len(tiers["cold"]) == 1
