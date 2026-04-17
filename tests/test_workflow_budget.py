"""Tests for ``ao_kernel.workflow.budget``.

Covers ``budget_from_dict`` / ``budget_to_dict`` roundtrip, ``record_spend``
exhaust semantics (equality valid, strictly-over-raises), Decimal
precision for ``cost_usd``, ``fail_closed_on_exhaust`` enforcement, and
schema-compat of the serialized form.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from ao_kernel.workflow import (
    Budget,
    WorkflowBudgetExhaustedError,
    budget_from_dict,
    budget_to_dict,
    is_exhausted,
    record_spend,
    validate_workflow_run,
)


def _tokens_budget(limit: int = 100) -> Budget:
    return budget_from_dict(
        {
            "tokens": {"limit": limit, "spent": 0, "remaining": limit},
            "fail_closed_on_exhaust": True,
        }
    )


def _full_budget() -> Budget:
    return budget_from_dict(
        {
            "tokens": {"limit": 1000, "spent": 0, "remaining": 1000},
            "time_seconds": {"limit": 60.0, "spent": 0.0, "remaining": 60.0},
            "cost_usd": {"limit": 5.00, "spent": 0.0, "remaining": 5.00},
            "fail_closed_on_exhaust": True,
        }
    )


class TestParse:
    def test_minimal_tokens_only(self) -> None:
        b = _tokens_budget()
        assert b.tokens is not None
        assert b.tokens.limit == 100
        assert b.time_seconds is None
        assert b.cost_usd is None
        assert b.fail_closed_on_exhaust is True

    def test_remaining_derived_when_absent(self) -> None:
        b = budget_from_dict(
            {
                "tokens": {"limit": 50, "spent": 10},
                "fail_closed_on_exhaust": True,
            }
        )
        assert b.tokens is not None
        assert b.tokens.remaining == 40

    def test_cost_internally_decimal(self) -> None:
        b = _full_budget()
        assert b.cost_usd is not None
        assert isinstance(b.cost_usd.limit, Decimal)
        assert isinstance(b.cost_usd.spent, Decimal)
        assert isinstance(b.cost_usd.remaining, Decimal)

    def test_fail_closed_false_rejected(self) -> None:
        with pytest.raises(ValueError, match="fail_closed_on_exhaust"):
            budget_from_dict(
                {
                    "tokens": {"limit": 10, "spent": 0, "remaining": 10},
                    "fail_closed_on_exhaust": False,
                }
            )

    def test_fail_closed_missing_rejected(self) -> None:
        with pytest.raises(ValueError, match="fail_closed_on_exhaust"):
            budget_from_dict(
                {"tokens": {"limit": 10, "spent": 0, "remaining": 10}}
            )


class TestSerialize:
    def test_roundtrip_legacy_tokens_adds_granular_input(self) -> None:
        """PR-B2 v3 iter-2 B3 absorb: legacy records with only aggregate
        ``tokens`` are conservatively mapped to granular on read. Reader
        copies ``tokens`` into ``tokens_input``; writer emits both.
        This is a documented semantic widening; legacy wire round-trip
        is no longer byte-identical but the legacy fields remain
        present and unchanged.
        """
        raw: dict[str, Any] = {
            "tokens": {"limit": 100, "spent": 10, "remaining": 90},
            "fail_closed_on_exhaust": True,
        }
        out = budget_to_dict(budget_from_dict(raw))
        # Aggregate preserved byte-identical
        assert out["tokens"] == raw["tokens"]
        assert out["fail_closed_on_exhaust"] is True
        # New: tokens_input appears as a copy of tokens (conservative mapping)
        assert out["tokens_input"] == raw["tokens"]
        # tokens_output remains absent (None → OMIT invariant)
        assert "tokens_output" not in out

    def test_roundtrip_granular_preserved(self) -> None:
        """When the record declares granular axes explicitly, round-trip
        preserves them as-is (no back-compat synthesis)."""
        raw: dict[str, Any] = {
            "tokens": {"limit": 150, "spent": 0, "remaining": 150},
            "tokens_input": {"limit": 100, "spent": 0, "remaining": 100},
            "tokens_output": {"limit": 50, "spent": 0, "remaining": 50},
            "fail_closed_on_exhaust": True,
        }
        out = budget_to_dict(budget_from_dict(raw))
        assert out == raw

    def test_cost_serialized_as_float(self) -> None:
        b = _full_budget()
        out = budget_to_dict(b)
        assert isinstance(out["cost_usd"]["limit"], float)
        assert isinstance(out["cost_usd"]["spent"], float)
        assert isinstance(out["cost_usd"]["remaining"], float)

    def test_serialized_budget_validates_against_schema(self) -> None:
        """The serialized form must satisfy workflow-run schema $defs/budget."""
        import uuid

        b = _full_budget()
        rec = {
            "run_id": str(uuid.uuid4()),
            "workflow_id": "bug_fix_flow",
            "workflow_version": "1.0.0",
            "state": "created",
            "created_at": "2026-04-15T12:00:00+03:00",
            "revision": "a" * 64,
            "intent": {"kind": "inline_prompt", "payload": "x"},
            "steps": [],
            "policy_refs": [
                "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"
            ],
            "adapter_refs": [],
            "evidence_refs": [".ao/evidence/workflows/x/events.jsonl"],
            "budget": budget_to_dict(b),
        }
        # Should not raise.
        assert validate_workflow_run(rec) is None


class TestRecordSpend:
    def test_happy_tokens_spend(self) -> None:
        b = _tokens_budget(100)
        b2 = record_spend(b, tokens=30, run_id="r1")
        assert b2.tokens is not None
        assert b2.tokens.spent == 30
        assert b2.tokens.remaining == 70

    def test_spend_exact_remaining_valid(self) -> None:
        """Spending exactly the remaining amount leaves remaining == 0; no raise."""
        b = _tokens_budget(10)
        b2 = record_spend(b, tokens=10, run_id="r1")
        assert b2.tokens is not None
        assert b2.tokens.remaining == 0

    def test_spend_over_limit_raises(self) -> None:
        b = _tokens_budget(10)
        with pytest.raises(WorkflowBudgetExhaustedError) as ei:
            record_spend(b, tokens=11, run_id="r1")
        err = ei.value
        assert err.axis == "tokens"
        assert err.attempted_spend == 11
        assert err.run_id == "r1"

    def test_next_spend_after_exact_exhaust_raises(self) -> None:
        b = _tokens_budget(10)
        b2 = record_spend(b, tokens=10, run_id="r1")
        with pytest.raises(WorkflowBudgetExhaustedError):
            record_spend(b2, tokens=1, run_id="r1")

    def test_spend_on_unconfigured_axis_raises(self) -> None:
        b = _tokens_budget(10)  # only tokens configured
        with pytest.raises(ValueError, match="unconfigured axis"):
            record_spend(b, time_seconds=1.0)

    def test_multi_axis_spend(self) -> None:
        b = _full_budget()
        b2 = record_spend(
            b,
            tokens=100,
            time_seconds=5.0,
            cost_usd=Decimal("0.50"),
            run_id="r1",
        )
        assert b2.tokens is not None and b2.tokens.spent == 100
        assert b2.time_seconds is not None and b2.time_seconds.spent == pytest.approx(5.0)
        assert b2.cost_usd is not None and b2.cost_usd.spent == Decimal("0.50")

    def test_decimal_precision_preserved(self) -> None:
        """Three spends of $0.10 each land at exactly $0.30 (no FP drift)."""
        b = _full_budget()
        for _ in range(3):
            b = record_spend(b, cost_usd=Decimal("0.10"), run_id="r1")
        assert b.cost_usd is not None
        assert b.cost_usd.spent == Decimal("0.30")


class TestIsExhausted:
    def test_not_exhausted_returns_false(self) -> None:
        b = _tokens_budget(100)
        exhausted, axis = is_exhausted(b)
        assert exhausted is False
        assert axis is None

    def test_exhausted_after_exact_spend(self) -> None:
        b = record_spend(_tokens_budget(10), tokens=10)
        exhausted, axis = is_exhausted(b)
        assert exhausted is True
        assert axis == "tokens"

    def test_first_exhausted_axis_reported(self) -> None:
        """Multi-axis: reports the first axis (tokens order first)."""
        b = budget_from_dict(
            {
                "tokens": {"limit": 10, "spent": 10, "remaining": 0},
                "time_seconds": {"limit": 60.0, "spent": 0.0, "remaining": 60.0},
                "fail_closed_on_exhaust": True,
            }
        )
        exhausted, axis = is_exhausted(b)
        assert exhausted is True
        assert axis == "tokens"
