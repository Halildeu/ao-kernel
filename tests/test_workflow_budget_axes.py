"""Tests for PR-B2 Budget widening — tokens_input/tokens_output axes.

Complements ``test_workflow_budget.py`` (PR-A1 aggregate-axis tests).
This file focuses on the granular additions + back-compat invariants
documented in PR-B2 plan v7 §2.5.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from ao_kernel.workflow.budget import (
    Budget,
    BudgetAxis,
    budget_from_dict,
    budget_to_dict,
    is_exhausted,
    record_spend,
)
from ao_kernel.workflow.errors import WorkflowBudgetExhaustedError


def _granular_budget(
    *,
    input_limit: int = 1000,
    output_limit: int = 500,
) -> Budget:
    return Budget(
        tokens=BudgetAxis(
            limit=input_limit + output_limit,
            spent=0,
            remaining=input_limit + output_limit,
        ),
        tokens_input=BudgetAxis(
            limit=input_limit,
            spent=0,
            remaining=input_limit,
        ),
        tokens_output=BudgetAxis(
            limit=output_limit,
            spent=0,
            remaining=output_limit,
        ),
        time_seconds=None,
        cost_usd=None,
        fail_closed_on_exhaust=True,
    )


class TestBackCompatReader:
    def test_legacy_tokens_only_stays_aggregate_only(self) -> None:
        """CNS-032 iter-2 absorb: reader does NOT synthesize
        tokens_input from legacy aggregate. Legacy aggregate-only
        records stay aggregate-only (middleware's aggregate path
        handles spend correctly)."""
        raw: dict[str, Any] = {
            "tokens": {"limit": 500, "spent": 50, "remaining": 450},
            "fail_closed_on_exhaust": True,
        }
        b = budget_from_dict(raw)
        assert b.tokens is not None
        assert b.tokens.limit == 500
        # No synthesis — both granular axes remain None.
        assert b.tokens_input is None
        assert b.tokens_output is None

    def test_granular_record_populates_all(self) -> None:
        raw: dict[str, Any] = {
            "tokens": {"limit": 1500, "spent": 0, "remaining": 1500},
            "tokens_input": {"limit": 1000, "spent": 0, "remaining": 1000},
            "tokens_output": {"limit": 500, "spent": 0, "remaining": 500},
            "fail_closed_on_exhaust": True,
        }
        b = budget_from_dict(raw)
        assert b.tokens_input is not None and b.tokens_input.limit == 1000
        assert b.tokens_output is not None and b.tokens_output.limit == 500

    def test_no_tokens_axes_all_none(self) -> None:
        """Runs without any token budget config remain fully None on all
        token axes — no synthesis from absence."""
        raw: dict[str, Any] = {
            "cost_usd": {"limit": 1.0, "spent": 0.0, "remaining": 1.0},
            "fail_closed_on_exhaust": True,
        }
        b = budget_from_dict(raw)
        assert b.tokens is None
        assert b.tokens_input is None
        assert b.tokens_output is None


class TestWriterInvariant:
    def test_tokens_output_none_is_omitted(self) -> None:
        """Plan v7 §2.5: tokens_output=None → absent key, no null."""
        raw: dict[str, Any] = {
            "tokens": {"limit": 500, "spent": 0, "remaining": 500},
            "fail_closed_on_exhaust": True,
        }
        b = budget_from_dict(raw)
        out = budget_to_dict(b)
        assert "tokens_output" not in out
        # No explicit None key either
        for key, value in out.items():
            assert value is not None, f"{key!r} serialized as None"

    def test_tokens_input_always_emitted_when_configured(self) -> None:
        b = _granular_budget()
        out = budget_to_dict(b)
        assert "tokens_input" in out
        assert out["tokens_input"]["limit"] == 1000

    def test_aggregate_always_emitted(self) -> None:
        b = _granular_budget(input_limit=300, output_limit=200)
        out = budget_to_dict(b)
        assert out["tokens"]["limit"] == 500  # 300 + 200


class TestRecordSpendGranular:
    def test_granular_spend_adjusts_aggregate(self) -> None:
        """tokens_input=100 + tokens_output=50 → aggregate +=150."""
        b = _granular_budget()
        b2 = record_spend(b, tokens_input=100, tokens_output=50)
        assert b2.tokens_input is not None and b2.tokens_input.spent == 100
        assert b2.tokens_output is not None and b2.tokens_output.spent == 50
        assert b2.tokens is not None and b2.tokens.spent == 150

    def test_granular_spend_only_input(self) -> None:
        b = _granular_budget()
        b2 = record_spend(b, tokens_input=200)
        assert b2.tokens_input is not None and b2.tokens_input.spent == 200
        # tokens_output unchanged
        assert b2.tokens_output is not None and b2.tokens_output.spent == 0
        # Aggregate += 200
        assert b2.tokens is not None and b2.tokens.spent == 200

    def test_granular_spend_only_output(self) -> None:
        b = _granular_budget()
        b2 = record_spend(b, tokens_output=100)
        assert b2.tokens_output is not None and b2.tokens_output.spent == 100
        # tokens_input unchanged
        assert b2.tokens_input is not None and b2.tokens_input.spent == 0
        assert b2.tokens is not None and b2.tokens.spent == 100

    def test_double_count_guard(self) -> None:
        """Plan v7 §2.5: passing BOTH aggregate tokens= and granular
        tokens_input= → ValueError."""
        b = _granular_budget()
        with pytest.raises(ValueError, match="EITHER aggregate"):
            record_spend(b, tokens=150, tokens_input=100, tokens_output=50)

    def test_double_count_guard_input_only(self) -> None:
        b = _granular_budget()
        with pytest.raises(ValueError):
            record_spend(b, tokens=100, tokens_input=100)

    def test_double_count_guard_output_only(self) -> None:
        b = _granular_budget()
        with pytest.raises(ValueError):
            record_spend(b, tokens=100, tokens_output=100)

    def test_granular_exhaust_raises(self) -> None:
        """Input axis exhausted → WorkflowBudgetExhaustedError."""
        b = _granular_budget(input_limit=100, output_limit=1000)
        with pytest.raises(WorkflowBudgetExhaustedError) as excinfo:
            record_spend(b, tokens_input=150)
        assert excinfo.value.axis == "tokens_input"

    def test_aggregate_exhaust_after_granular_spend(self) -> None:
        """Aggregate can exhaust before individual axis when sum exceeds."""
        b = Budget(
            tokens=BudgetAxis(limit=100, spent=0, remaining=100),
            tokens_input=BudgetAxis(limit=200, spent=0, remaining=200),
            tokens_output=BudgetAxis(limit=200, spent=0, remaining=200),
            time_seconds=None,
            cost_usd=None,
            fail_closed_on_exhaust=True,
        )
        with pytest.raises(WorkflowBudgetExhaustedError) as excinfo:
            record_spend(b, tokens_input=80, tokens_output=30)  # sum=110 > 100
        assert excinfo.value.axis == "tokens"


class TestRecordSpendLegacy:
    def test_legacy_aggregate_spend_still_works(self) -> None:
        """PR-A callers pass tokens= alone; unchanged behavior."""
        b = Budget(
            tokens=BudgetAxis(limit=500, spent=0, remaining=500),
            tokens_input=None,
            tokens_output=None,
            time_seconds=None,
            cost_usd=None,
            fail_closed_on_exhaust=True,
        )
        b2 = record_spend(b, tokens=100)
        assert b2.tokens is not None and b2.tokens.spent == 100

    def test_cost_spend_independent(self) -> None:
        """cost_usd spend unaffected by granular tokens changes."""
        b = Budget(
            tokens=None,
            tokens_input=None,
            tokens_output=None,
            time_seconds=None,
            cost_usd=BudgetAxis(
                limit=Decimal("1.00"),
                spent=Decimal("0"),
                remaining=Decimal("1.00"),
            ),
            fail_closed_on_exhaust=True,
        )
        b2 = record_spend(b, cost_usd=Decimal("0.10"))
        assert b2.cost_usd is not None and b2.cost_usd.spent == Decimal("0.10")


class TestIsExhausted:
    def test_tokens_input_exhausted(self) -> None:
        b = Budget(
            tokens=None,
            tokens_input=BudgetAxis(limit=100, spent=100, remaining=0),
            tokens_output=None,
            time_seconds=None,
            cost_usd=None,
            fail_closed_on_exhaust=True,
        )
        exhausted, axis = is_exhausted(b)
        assert exhausted is True
        assert axis == "tokens_input"

    def test_tokens_output_exhausted(self) -> None:
        b = Budget(
            tokens=None,
            tokens_input=None,
            tokens_output=BudgetAxis(limit=50, spent=50, remaining=0),
            time_seconds=None,
            cost_usd=None,
            fail_closed_on_exhaust=True,
        )
        exhausted, axis = is_exhausted(b)
        assert exhausted is True
        assert axis == "tokens_output"

    def test_none_exhausted(self) -> None:
        b = _granular_budget()
        exhausted, axis = is_exhausted(b)
        assert exhausted is False
        assert axis is None


class TestSchemaValidation:
    def test_granular_budget_subsection_validates(self) -> None:
        """Schema widen (workflow-run.schema.v1.json::$defs/budget) accepts
        granular axes. Validates the budget sub-schema directly —
        independent of the full run-record envelope's evolving shape."""
        from ao_kernel.config import load_default
        from jsonschema import Draft202012Validator

        schema = load_default("schemas", "workflow-run.schema.v1.json")
        # Extract $defs/budget sub-schema
        budget_schema = schema["$defs"]["budget"]
        serialized = budget_to_dict(_granular_budget())
        # Wire presence: all three token axes + fail_closed
        assert "tokens" in serialized
        assert "tokens_input" in serialized
        assert "tokens_output" in serialized
        # Subschema validator — ensures new fields shape-correct
        Draft202012Validator(budget_schema).validate(serialized)
