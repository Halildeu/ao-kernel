"""Read-only variant comparison helper (v3.12 E2).

Shape (v3.12 minimal, per Codex plan-time):

- :class:`VariantComparisonEntry` — per-run row: ``variant_id``,
  ``run_id``, optional ``experiment_id``, optional ``review_findings``
  payload loaded from ``step_record.capability_output_refs``.
- :class:`VariantComparison` — wrapper: ``entries`` (list), plus a
  ``by_variant`` mapping for quick operator lookup.
- :func:`compare_variants` — load each run record, extract variant
  metadata + capability artefact, package into the comparison.

The helper does NOT score. Operators write their own diff / threshold
tooling on top; runbook (E3) gives walkthrough patterns. Additive
helpers (``differing_findings()`` etc.) stay out of scope for v3.12.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence


class VariantComparisonError(ValueError):
    """Raised when a run record cannot be paired with a variant_id
    (missing intent.metadata.variant_id) or when an artefact ref
    cannot be resolved / parsed."""


@dataclass(frozen=True)
class VariantComparisonEntry:
    """Single row in the variant comparison.

    ``review_findings`` is ``None`` when the run either didn't produce
    a ``review_findings`` capability artefact or the artefact file is
    missing / malformed. The operator can inspect ``review_findings_ref``
    and ``load_error`` to understand why.
    """

    run_id: str
    variant_id: str
    experiment_id: str | None
    review_findings_ref: str | None
    review_findings: Mapping[str, Any] | None
    load_error: str | None = None


@dataclass(frozen=True)
class VariantComparison:
    """Bundle of :class:`VariantComparisonEntry` rows.

    ``entries`` is in the same order as the ``run_ids`` argument to
    :func:`compare_variants`. ``by_variant`` groups by ``variant_id``
    (the common operator query).
    """

    entries: tuple[VariantComparisonEntry, ...]
    by_variant: Mapping[str, tuple[VariantComparisonEntry, ...]] = field(default_factory=dict)


def _load_run_record(workspace_root: Path, run_id: str) -> Mapping[str, Any]:
    """Thin wrapper so tests can monkeypatch the loader without touching
    the ao_kernel.workflow public surface.
    """
    from ao_kernel.workflow import load_run

    record, _ = load_run(workspace_root, run_id)
    return record


def _extract_review_findings_ref(
    record: Mapping[str, Any],
) -> str | None:
    """Return the first ``capability_output_refs["review_findings"]``
    path from the record's step list, or ``None`` if no step emitted
    one.
    """
    steps = record.get("steps") or []
    if not isinstance(steps, list):
        return None
    for step in steps:
        if not isinstance(step, Mapping):
            continue
        refs = step.get("capability_output_refs")
        if isinstance(refs, Mapping):
            ref = refs.get("review_findings")
            if isinstance(ref, str) and ref:
                return ref
    return None


def _read_artefact(workspace_root: Path, ref: str) -> tuple[Mapping[str, Any] | None, str | None]:
    """Resolve ``ref`` against ``workspace_root`` and JSON-parse it.

    Returns ``(payload, None)`` on success, ``(None, reason)`` on any
    I/O or parse failure. Fail-open semantics — the comparison row
    still ships, just without the payload.
    """
    try:
        path = (workspace_root / ref).resolve()
        if not path.is_file():
            return None, f"artefact file not found: {ref!r}"
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, Mapping):
            return None, f"artefact is not a JSON object: {ref!r}"
        return data, None
    except Exception as exc:  # noqa: BLE001 — fail-open load for analysis helper
        return None, f"artefact load failed: {type(exc).__name__}: {exc}"


def compare_variants(
    run_ids: Sequence[str],
    *,
    workspace_root: Path,
) -> VariantComparison:
    """Pair ``variant_id`` with ``review_findings`` artefacts across runs.

    Args:
        run_ids: Run identifiers to include. Order is preserved in
            :attr:`VariantComparison.entries`.
        workspace_root: The workspace that holds the run records +
            artefacts (typically the project root that has ``.ao/``).

    Raises :class:`VariantComparisonError` if any run record lacks
    ``intent.metadata.variant_id`` — that field is the contract
    stamp operators use to mark a variant run. Unstamped runs do not
    belong in an experiment comparison; the call fails closed.

    Artefact load failures are NOT raised — they're packaged into
    :attr:`VariantComparisonEntry.load_error` so the operator sees
    which runs produced analyzable payloads and which didn't.
    """
    entries: list[VariantComparisonEntry] = []
    by_variant: dict[str, list[VariantComparisonEntry]] = {}

    for run_id in run_ids:
        record = _load_run_record(workspace_root, run_id)
        intent = record.get("intent") or {}
        metadata = intent.get("metadata") if isinstance(intent, Mapping) else None
        if not isinstance(metadata, Mapping):
            raise VariantComparisonError(f"run {run_id!r} has no intent.metadata — cannot pair with a variant")
        variant_id = metadata.get("variant_id")
        if not isinstance(variant_id, str) or not variant_id:
            raise VariantComparisonError(f"run {run_id!r} is missing intent.metadata.variant_id")
        experiment_id = metadata.get("experiment_id")
        if not isinstance(experiment_id, str):
            experiment_id = None

        ref = _extract_review_findings_ref(record)
        payload: Mapping[str, Any] | None = None
        load_error: str | None = None
        if ref is None:
            load_error = "no step emitted review_findings artefact"
        else:
            payload, load_error = _read_artefact(workspace_root, ref)

        entry = VariantComparisonEntry(
            run_id=run_id,
            variant_id=variant_id,
            experiment_id=experiment_id,
            review_findings_ref=ref,
            review_findings=payload,
            load_error=load_error,
        )
        entries.append(entry)
        by_variant.setdefault(variant_id, []).append(entry)

    by_variant_frozen: dict[str, tuple[VariantComparisonEntry, ...]] = {k: tuple(v) for k, v in by_variant.items()}
    return VariantComparison(entries=tuple(entries), by_variant=by_variant_frozen)


__all__ = [
    "VariantComparison",
    "VariantComparisonEntry",
    "VariantComparisonError",
    "compare_variants",
]
