"""ao_kernel.experiments — prompt / workflow experiment analysis helpers (v3.12 E2).

Read-only helpers that pair ``intent.metadata.variant_id`` (stamped by
the operator per :mod:`ao_kernel.prompts` E1 contract) with the
review-findings artefact a workflow step produced
(``step_record.capability_output_refs["review_findings"]``).

The module is intentionally namespace-separate from
``ao_kernel.scorecard`` — the latter is tied to benchmark scorecard
JSON (`score` / `method` / `is_exact` fields), whereas this module
deals with variant_id → run_id → capability-artefact pairing for
operator-driven A/B experiments. Codex v3.12 plan-time directive:
keep these concerns apart.

v3.12 E2 ships only the read-only comparison surface. ao-kernel does
NOT orchestrate A/B dispatch — that is deferred per
:mod:`ao_kernel.prompts` docstring + the Codex plan-time precondition
on operator-validated real-adapter smokes.
"""

from __future__ import annotations

from ao_kernel.experiments.compare import (
    VariantComparison,
    VariantComparisonEntry,
    VariantComparisonError,
    compare_variants,
)


__all__ = [
    "VariantComparison",
    "VariantComparisonEntry",
    "VariantComparisonError",
    "compare_variants",
]
