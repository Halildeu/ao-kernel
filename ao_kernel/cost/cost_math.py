"""Pure deterministic cost arithmetic (PR-B2).

No I/O, no policy, no evidence — just math. Caller converts to/from
serializable formats. All computations use ``Decimal`` for precision
stability; callers serialize via ``str(Decimal(...))`` per
:func:`ao_kernel.workflow.budget._float_axis_to_dict` conventions.

See ``docs/COST-MODEL.md`` §5 for the formula contract.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover — import-only
    from ao_kernel.cost.catalog import PriceCatalogEntry


_THOUSAND = Decimal("1000")


def compute_cost(
    entry: "PriceCatalogEntry",
    tokens_input: int,
    tokens_output: int,
    cached_tokens: int = 0,
) -> Decimal:
    """Return the USD cost for a successful invocation.

    Formula (COST-MODEL.md §5)::

        billable_input = tokens_input - cached_tokens
        cost = billable_input * input_cost_per_1k / 1000
             + cached_tokens  * cached_input_cost_per_1k / 1000
             + tokens_output  * output_cost_per_1k / 1000

    When ``entry.cached_input_cost_per_1k`` is ``None``, cached tokens
    are billed at ``input_cost_per_1k`` (safe fallback — "no caching
    discount on file" rather than "free").

    Raises:
    - ``ValueError`` if ``cached_tokens > tokens_input`` (caller bug).
    """
    if cached_tokens < 0 or tokens_input < 0 or tokens_output < 0:
        raise ValueError(
            f"token counts must be non-negative: "
            f"input={tokens_input}, output={tokens_output}, cached={cached_tokens}"
        )
    if cached_tokens > tokens_input:
        raise ValueError(
            f"cached_tokens={cached_tokens} exceeds tokens_input={tokens_input}"
        )

    billable_input = tokens_input - cached_tokens
    input_rate = Decimal(str(entry.input_cost_per_1k))
    output_rate = Decimal(str(entry.output_cost_per_1k))

    # cached_input_cost_per_1k is optional; fall back to full input rate.
    if entry.cached_input_cost_per_1k is not None:
        cached_rate = Decimal(str(entry.cached_input_cost_per_1k))
    else:
        cached_rate = input_rate

    return (
        Decimal(billable_input) * input_rate / _THOUSAND
        + Decimal(cached_tokens) * cached_rate / _THOUSAND
        + Decimal(tokens_output) * output_rate / _THOUSAND
    )


def estimate_cost(
    entry: "PriceCatalogEntry",
    est_tokens_input: int,
    est_tokens_output: int,
) -> Decimal:
    """Pre-dispatch upper-bound estimate.

    Ignores caching — operator-facing budget cap reflects worst-case
    spend. Actual ``compute_cost`` post-response may be lower when the
    provider reports ``cached_tokens``.

    Raises ``ValueError`` on negative inputs.
    """
    if est_tokens_input < 0 or est_tokens_output < 0:
        raise ValueError(
            f"estimate counts must be non-negative: "
            f"input={est_tokens_input}, output={est_tokens_output}"
        )
    input_rate = Decimal(str(entry.input_cost_per_1k))
    output_rate = Decimal(str(entry.output_cost_per_1k))
    return (
        Decimal(est_tokens_input) * input_rate / _THOUSAND
        + Decimal(est_tokens_output) * output_rate / _THOUSAND
    )


def estimate_output_tokens(
    est_tokens_input: int,
    max_tokens: int | None,
) -> int:
    """Conservative output-token estimate for pre-dispatch budget check.

    Contract (PR-B2 v3 iter-1 Q3 absorb):

    - Without a caller-supplied ``max_tokens``: assume generation is
      25% of the prompt size (``est_tokens_input * 0.25``, rounded down).
      This is a blunt default; callers that know better pass ``max_tokens``.
    - With ``max_tokens``: take the minimum of the 25%-of-input estimate
      and the caller's explicit cap. The floor avoids over-estimating
      when the caller asked for a small completion.

    The model router currently does not return ``route.max_output_tokens``,
    so the call-site ``max_tokens`` kwarg is the only meaningful source
    for MVP. Intent-class-aware ratios (``FAST_TEXT`` vs ``CODE_GEN``)
    are deferred post-MVP.
    """
    if est_tokens_input < 0:
        raise ValueError(
            f"est_tokens_input must be non-negative: {est_tokens_input}"
        )
    ratio_estimate = int(est_tokens_input * 0.25)
    if max_tokens is None:
        return ratio_estimate
    if max_tokens < 0:
        raise ValueError(f"max_tokens must be non-negative: {max_tokens}")
    return min(max_tokens, ratio_estimate)


__all__ = [
    "compute_cost",
    "estimate_cost",
    "estimate_output_tokens",
]
