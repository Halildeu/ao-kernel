"""Workflow run budget accounting.

Immutable ``Budget`` + ``BudgetAxis`` dataclasses plus pure helper
functions for spending, exhaustion detection, and JSON roundtrip. All
arithmetic is side-effect free; mutators return new ``Budget`` instances
so the store's CAS pipeline can diff safely.

Precision policy (plan v2 B5 fix):

- ``tokens`` axis: ``int`` — natural counts.
- ``time_seconds`` axis: ``float`` — wall-clock is naturally fuzzy.
- ``cost_usd`` axis: internal ``Decimal`` (via ``Decimal(str(value))``)
  for aggregation precision. Serialized to JSON as ``float`` per schema
  ``type: number`` at the ``$defs/budget`` boundary. Sub-cent precision
  is NOT guaranteed post-persist; this docstring is the contract.

Exhaustion semantic (plan v2 B6 fix):

- ``record_spend`` raises ``WorkflowBudgetExhaustedError`` iff the
  post-spend ``remaining`` is strictly negative on any axis (spent more
  than allowed).
- Spending the exact remaining amount is valid: post-spend
  ``remaining == 0``; ``is_exhausted`` now reports ``(True, axis)``; the
  next positive-valued spend raises.
- ``fail_closed_on_exhaust`` MUST be ``True`` (matches schema ``const:
  true``); ``budget_from_dict`` raises ``ValueError`` otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

from ao_kernel.workflow.errors import WorkflowBudgetExhaustedError

_AxisNum = int | float | Decimal


@dataclass(frozen=True)
class BudgetAxis:
    """Single budget axis: limit + spent + remaining.

    All three fields MUST use the same numeric type (``int`` for tokens,
    ``float`` for time_seconds, ``Decimal`` for cost_usd). Direct
    construction is allowed but the module-level ``budget_from_dict`` and
    ``record_spend`` helpers enforce the type-per-axis convention.
    """

    limit: _AxisNum
    spent: _AxisNum
    remaining: _AxisNum


@dataclass(frozen=True)
class Budget:
    """Aggregate budget: up to three axes + fail-closed flag.

    Any axis may be ``None`` (not configured for this run). At least one
    axis should be present for a budget to be meaningful; the schema
    enforces no minimum at the ``$defs/budget`` level, so this module
    accepts all-None as a valid edge case.
    """

    tokens: BudgetAxis | None
    time_seconds: BudgetAxis | None
    cost_usd: BudgetAxis | None
    fail_closed_on_exhaust: bool


def budget_from_dict(record: Mapping[str, Any]) -> Budget:
    """Parse the schema ``$defs/budget`` section into a ``Budget`` instance.

    Enforces ``fail_closed_on_exhaust == True`` at the boundary;
    raises ``ValueError`` if absent or False.
    """
    fail_closed = record.get("fail_closed_on_exhaust", False)
    if fail_closed is not True:
        raise ValueError(
            "Budget must have fail_closed_on_exhaust=True "
            f"(got {fail_closed!r})"
        )
    return Budget(
        tokens=_parse_int_axis(record.get("tokens")),
        time_seconds=_parse_float_axis(record.get("time_seconds")),
        cost_usd=_parse_decimal_axis(record.get("cost_usd")),
        fail_closed_on_exhaust=True,
    )


def budget_to_dict(budget: Budget) -> dict[str, Any]:
    """Serialize ``budget`` to a schema-compatible mapping.

    ``cost_usd`` fields are cast to ``float`` at serialization to satisfy
    schema ``type: number``; precision above double-float limits is lost.
    Callers requiring sub-cent precision at rest should not rely on this
    output; the internal Decimal representation remains correct for
    arithmetic in-process.
    """
    out: dict[str, Any] = {
        "fail_closed_on_exhaust": budget.fail_closed_on_exhaust,
    }
    if budget.tokens is not None:
        out["tokens"] = _int_axis_to_dict(budget.tokens)
    if budget.time_seconds is not None:
        out["time_seconds"] = _float_axis_to_dict(budget.time_seconds)
    if budget.cost_usd is not None:
        out["cost_usd"] = _float_axis_to_dict(budget.cost_usd)
    return out


def record_spend(
    budget: Budget,
    *,
    tokens: int | None = None,
    time_seconds: float | None = None,
    cost_usd: _AxisNum | None = None,
    run_id: str | None = None,
) -> Budget:
    """Return a new ``Budget`` with the requested spend applied.

    Raises ``WorkflowBudgetExhaustedError`` if any axis's post-spend
    ``remaining`` would be strictly negative. Spending exactly the
    remaining amount is valid (post-spend ``remaining == 0``); the next
    positive spend on that axis raises.

    Raises ``ValueError`` if asked to spend on an unconfigured axis
    (``budget.<axis> is None``).
    """
    new_tokens = (
        _spend_axis(budget.tokens, "tokens", int(tokens), run_id)
        if tokens is not None
        else budget.tokens
    )
    new_time = (
        _spend_axis(
            budget.time_seconds, "time_seconds", float(time_seconds), run_id
        )
        if time_seconds is not None
        else budget.time_seconds
    )
    new_cost = (
        _spend_axis(
            budget.cost_usd, "cost_usd", _to_decimal(cost_usd), run_id
        )
        if cost_usd is not None
        else budget.cost_usd
    )
    return Budget(
        tokens=new_tokens,
        time_seconds=new_time,
        cost_usd=new_cost,
        fail_closed_on_exhaust=budget.fail_closed_on_exhaust,
    )


def is_exhausted(budget: Budget) -> tuple[bool, str | None]:
    """Return ``(True, axis_name)`` if any axis has ``remaining <= 0``.

    Informational. The fail-closed enforcement happens at spend time in
    ``record_spend``; callers using ``is_exhausted`` are emitting an
    evidence event or choosing not to attempt a further spend.
    """
    for name, axis in (
        ("tokens", budget.tokens),
        ("time_seconds", budget.time_seconds),
        ("cost_usd", budget.cost_usd),
    ):
        if axis is not None and axis.remaining <= 0:
            return True, name
    return False, None


def _spend_axis(
    axis: BudgetAxis | None,
    axis_name: str,
    spend: _AxisNum,
    run_id: str | None,
) -> BudgetAxis:
    """Apply spend to an axis; raise on overshoot. Pure.

    Runtime invariant (enforced by the three ``_parse_*_axis`` parsers
    and ``record_spend`` call sites): all three of ``axis.limit``,
    ``axis.spent``, ``axis.remaining``, and ``spend`` share a consistent
    numeric type per axis — ``int`` for tokens, ``float`` for
    time_seconds, ``Decimal`` for cost_usd. The ``_AxisNum`` union here
    cannot be narrowed without a generic ``BudgetAxis`` (deferred for
    simplicity), so cross-type operator checks are suppressed on the two
    arithmetic lines below.
    """
    if axis is None:
        raise ValueError(
            f"Cannot spend on unconfigured axis: {axis_name}"
        )
    # mypy: consistent numeric type guaranteed at runtime; see docstring.
    new_spent = axis.spent + spend  # type: ignore[operator]
    new_remaining = axis.remaining - spend  # type: ignore[operator]
    if new_remaining < 0:
        raise WorkflowBudgetExhaustedError(
            run_id=run_id,
            axis=axis_name,
            limit=axis.limit,
            attempted_spend=spend,
        )
    return BudgetAxis(
        limit=axis.limit,
        spent=new_spent,
        remaining=new_remaining,
    )


def _parse_int_axis(raw: Mapping[str, Any] | None) -> BudgetAxis | None:
    if raw is None:
        return None
    limit = int(raw["limit"])
    spent = int(raw.get("spent", 0))
    if "remaining" in raw:
        remaining = int(raw["remaining"])
    else:
        remaining = limit - spent
    return BudgetAxis(limit=limit, spent=spent, remaining=remaining)


def _parse_float_axis(raw: Mapping[str, Any] | None) -> BudgetAxis | None:
    if raw is None:
        return None
    limit = float(raw["limit"])
    spent = float(raw.get("spent", 0.0))
    if "remaining" in raw:
        remaining = float(raw["remaining"])
    else:
        remaining = limit - spent
    return BudgetAxis(limit=limit, spent=spent, remaining=remaining)


def _parse_decimal_axis(raw: Mapping[str, Any] | None) -> BudgetAxis | None:
    if raw is None:
        return None
    limit = _to_decimal(raw["limit"])
    spent = _to_decimal(raw.get("spent", 0))
    if "remaining" in raw:
        remaining = _to_decimal(raw["remaining"])
    else:
        remaining = limit - spent
    return BudgetAxis(limit=limit, spent=spent, remaining=remaining)


def _to_decimal(value: _AxisNum | str) -> Decimal:
    """Coerce any numeric-like value to Decimal via str() to avoid FP drift."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _int_axis_to_dict(axis: BudgetAxis) -> dict[str, int]:
    return {
        "limit": int(axis.limit),
        "spent": int(axis.spent),
        "remaining": int(axis.remaining),
    }


def _float_axis_to_dict(axis: BudgetAxis) -> dict[str, float]:
    return {
        "limit": float(axis.limit),
        "spent": float(axis.spent),
        "remaining": float(axis.remaining),
    }
