"""Policy-aware regression comparison wrapper (V5 Epic 7x).

Thin policy layer above the existing ``ao_kernel/_internal/scorecard/compare.py``
diff math. Reads head scorecard + baseline + threshold policy + scenario
catalog, produces a replay-ready ``regression-comparison-result.v1.json``
artifact, and computes a policy-driven exit code.

Codex 019e84b7 cross-AI plan-time AGREE (2 iters: REVISE → AGREE).

Discipline:

- **Module boundary** (F5 absorb): reuses existing compare.py; no duplicate
  diff motor. ``scripts/regression_gate.py`` is a thin CLI (~80 LOC) that
  imports from here.
- **Exit semantics** (F2 absorb): policy-driven. ``advisory`` returns 0
  for warn + hard_fail; ``manual_block`` returns 1 only on hard_fail;
  ``ci_block_candidate`` returns 1 on warn or hard_fail. CLI overrides
  ``--advisory-mode`` / ``--strict-mode`` are operator-local and recorded
  in the result artifact (``cli_override_applied``).
- **Metric direction** (F3 absorb): per-policy ``direction``
  (``higher_is_worse`` / ``lower_is_worse``). Edge cases
  (baseline_zero / null / unit_mismatch / non-numeric) produce
  ``status="skip"`` with a structured ``skip_reason`` code.
- **Replay/audit** (F4 absorb): the result records SHA256 of all four
  source artifacts plus benchmark_mode + enforcement_mode_resolved +
  cli_override_applied + generated_at.
- **Catalog filter** (F6 absorb + H4): comparison universe is
  catalog-filtered (mode + ``enforcement == 'policy_threshold'``).
  Head/baseline scenarios outside this universe go to
  ``observed_extra_scenarios`` and never gate the result.
- **Unknown enforcement_mode**: fail-closed; raises ``ValueError`` rather
  than silently falling through (iter-2 residual condition absorb).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = "regression-comparison-result.v1"
ARTIFACT_KIND = "regression-comparison-evidence"

EnforcementMode = str  # advisory | manual_block | ci_block_candidate
CliOverride = str  # advisory | strict
SkipReason = str

_ALLOWED_OVERRIDES = (None, "advisory", "strict")
_ALLOWED_MODES = ("advisory", "manual_block", "ci_block_candidate")


@dataclass(frozen=True)
class ComparisonInputs:
    head_scorecard_path: Path
    baseline_path: Path
    threshold_path: Path
    catalog_path: Path
    benchmark_mode: str
    cli_override: str | None
    generated_at: str


def _sha256_hex(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _scorecard_rows_by_scenario(scorecard: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = scorecard.get("benchmarks") or []
    by_scenario: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, Mapping):
            name = row.get("scenario")
            if isinstance(name, str):
                by_scenario[name] = dict(row)
    return by_scenario


def _baseline_rows_by_id(baseline: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = baseline.get("scenarios") or []
    return {s["id"]: dict(s) for s in rows if isinstance(s, Mapping) and "id" in s}


def _catalog_entries_for_mode(catalog: Mapping[str, Any], benchmark_mode: str) -> list[dict[str, Any]]:
    """Codex F6 + H4 absorb: catalog-filtered universe."""
    entries: list[dict[str, Any]] = []
    for scenario in catalog.get("scenarios") or []:
        if not isinstance(scenario, Mapping):
            continue
        if scenario.get("mode") != benchmark_mode:
            continue
        if scenario.get("enforcement") != "policy_threshold":
            continue
        entries.append(dict(scenario))
    return entries


def _threshold_for_scenario(
    threshold: Mapping[str, Any], scenario_id: str
) -> tuple[float | None, float | None, str | None, str]:
    """Resolve thresholds for a scenario.

    Returns (warn_pct, hard_pct, override_applied, threshold_source).
    """
    scenarios = threshold.get("scenarios") or []
    for entry in scenarios:
        if isinstance(entry, Mapping) and entry.get("id") == scenario_id:
            warn = entry.get("warn_threshold_pct")
            hard = entry.get("hard_fail_threshold_pct")
            override = entry.get("enforcement_override")
            return warn, hard, override, "threshold.scenarios[]"
    defaults = threshold.get("global_defaults") or {}
    return (
        defaults.get("warn_threshold_pct"),
        defaults.get("hard_fail_threshold_pct"),
        None,
        "threshold.global_defaults",
    )


def _direction_for_global(threshold: Mapping[str, Any]) -> str:
    defaults = threshold.get("global_defaults") or {}
    direction = defaults.get("direction") or defaults.get("comparison")
    return str(direction or "higher_is_worse")


def _action_on_missing_baseline(threshold: Mapping[str, Any]) -> str:
    defaults = threshold.get("global_defaults") or {}
    return str(defaults.get("action_on_missing_baseline") or "skip_check")


def _action_on_missing_head(threshold: Mapping[str, Any]) -> str:
    defaults = threshold.get("global_defaults") or {}
    return str(defaults.get("action_on_missing_head_scenario") or "warn")


def _coerce_numeric(value: Any) -> tuple[float | None, str | None]:
    """Return (float, None) on success or (None, skip_reason) on failure."""
    if value is None:
        return None, "missing_baseline_value"
    if isinstance(value, bool):
        return None, "invalid_metric_type"
    if isinstance(value, (int, float)):
        return float(value), None
    return None, "invalid_metric_type"


def _compute_pct_change(baseline_value: float, head_value: float, direction: str) -> float:
    """Direction-aware pct change. Positive value = regression."""
    if direction == "lower_is_worse":
        return (baseline_value - head_value) / baseline_value * 100.0
    # higher_is_worse default
    return (head_value - baseline_value) / baseline_value * 100.0


def _scenario_result(
    catalog_entry: Mapping[str, Any],
    baseline_row: Mapping[str, Any] | None,
    head_row: Mapping[str, Any] | None,
    *,
    direction: str,
    warn_pct: float | None,
    hard_pct: float | None,
    override_applied: str | None,
    threshold_source: str,
    action_missing_baseline: str,
    action_missing_head: str,
    baseline_path: Path,
    head_path: Path,
) -> dict[str, Any]:
    scenario_id = str(catalog_entry["id"])
    base: dict[str, Any] = {
        "id": scenario_id,
        "metric_key": "duration_ms",
        "unit": "ms",
        "direction": direction,
        "baseline_value": None,
        "baseline_source": None,
        "head_value": None,
        "head_source": None,
        "pct_change": None,
        "is_improvement": False,
        "warn_threshold_pct": warn_pct,
        "hard_fail_threshold_pct": hard_pct,
        "threshold_source": threshold_source,
        "override_applied": override_applied,
        "action_on_missing_resolved": None,
        "status": "skip",
        "skip_reason": None,
    }
    if override_applied == "advisory_only":
        base["status"] = "skip"
        base["skip_reason"] = "advisory_only"
        return base
    if baseline_row is None:
        base["action_on_missing_resolved"] = action_missing_baseline
        base["status"] = "skip"
        base["skip_reason"] = "missing_baseline"
        return base
    if head_row is None:
        base["action_on_missing_resolved"] = action_missing_head
        base["status"] = "skip"
        base["skip_reason"] = "missing_head"
        return base

    metric = baseline_row.get("metric") or {}
    baseline_value, baseline_skip = _coerce_numeric(metric.get("value"))
    head_value, head_skip = _coerce_numeric(head_row.get("duration_ms"))

    base["baseline_value"] = baseline_value
    base["baseline_source"] = str(baseline_path)
    base["head_value"] = head_value
    base["head_source"] = f"{head_path}:scenario={scenario_id}"

    if baseline_skip is not None:
        base["skip_reason"] = baseline_skip
        return base
    if head_skip is not None:
        base["skip_reason"] = head_skip
        return base

    baseline_unit = metric.get("unit")
    if baseline_unit and baseline_unit != "ms":
        base["skip_reason"] = "unit_mismatch"
        return base

    assert baseline_value is not None and head_value is not None
    if baseline_value == 0:
        base["skip_reason"] = "baseline_zero"
        return base

    pct = _compute_pct_change(baseline_value, head_value, direction)
    base["pct_change"] = pct
    base["is_improvement"] = pct < 0

    # Status resolution. Improvement is always pass.
    if pct < 0:
        base["status"] = "pass"
        return base
    if hard_pct is not None and pct >= hard_pct:
        base["status"] = "hard_fail"
        return base
    if warn_pct is not None and pct >= warn_pct:
        base["status"] = "warn"
        return base
    base["status"] = "pass"
    return base


def _aggregate_status(scenarios: Iterable[dict[str, Any]]) -> tuple[str, dict[str, int]]:
    counts = {"passed": 0, "warned": 0, "hard_failed": 0, "skipped": 0}
    for s in scenarios:
        status = s["status"]
        if status == "pass":
            counts["passed"] += 1
        elif status == "warn":
            counts["warned"] += 1
        elif status == "hard_fail":
            counts["hard_failed"] += 1
        else:
            counts["skipped"] += 1
    if counts["hard_failed"] > 0:
        overall = "hard_fail"
    elif counts["warned"] > 0:
        overall = "warn"
    elif counts["passed"] > 0:
        overall = "pass"
    else:
        overall = "skip"
    return overall, counts


def _observed_extra_scenarios(
    catalog_ids: set[str],
    head_scenarios: Iterable[str],
    baseline_scenarios: Iterable[str],
) -> list[str]:
    extras = (set(head_scenarios) | set(baseline_scenarios)) - catalog_ids
    return sorted(extras)


def build_comparison_result(
    inputs: ComparisonInputs,
    threshold: Mapping[str, Any],
) -> dict[str, Any]:
    head = _load_json(inputs.head_scorecard_path)
    baseline = _load_json(inputs.baseline_path)
    catalog = _load_json(inputs.catalog_path)

    catalog_entries = _catalog_entries_for_mode(catalog, inputs.benchmark_mode)
    head_rows = _scorecard_rows_by_scenario(head)
    baseline_rows = _baseline_rows_by_id(baseline)

    direction = _direction_for_global(threshold)
    action_missing_baseline = _action_on_missing_baseline(threshold)
    action_missing_head = _action_on_missing_head(threshold)

    scenarios: list[dict[str, Any]] = []
    catalog_ids: set[str] = set()
    for entry in catalog_entries:
        scenario_id = entry["id"]
        catalog_ids.add(scenario_id)
        warn_pct, hard_pct, override_applied, threshold_source = _threshold_for_scenario(threshold, scenario_id)
        baseline_row = baseline_rows.get(scenario_id)
        # Head scorecard rows are keyed by source_scorecard_scenario.
        head_key = str(entry.get("source_scorecard_scenario") or scenario_id)
        head_row = head_rows.get(head_key)
        scenarios.append(
            _scenario_result(
                entry,
                baseline_row,
                head_row,
                direction=direction,
                warn_pct=warn_pct,
                hard_pct=hard_pct,
                override_applied=override_applied,
                threshold_source=threshold_source,
                action_missing_baseline=action_missing_baseline,
                action_missing_head=action_missing_head,
                baseline_path=inputs.baseline_path,
                head_path=inputs.head_scorecard_path,
            )
        )

    overall_status, counts = _aggregate_status(scenarios)
    observed_extra = _observed_extra_scenarios(
        catalog_ids,
        head_rows.keys(),
        baseline_rows.keys(),
    )

    enforcement_mode_resolved = str(threshold.get("enforcement_mode", "advisory"))
    if enforcement_mode_resolved not in _ALLOWED_MODES:
        raise ValueError(f"unknown enforcement_mode: {enforcement_mode_resolved!r}; allowed: {_ALLOWED_MODES}")

    return {
        "schema_version": SCHEMA_VERSION,
        "service": "ao-kernel",
        "artifact_kind": ARTIFACT_KIND,
        "guard_flags": {
            "support_widening_allowed": False,
            "production_platform_claim_allowed": False,
            "live_adapter_execution_allowed": False,
        },
        "claim_boundary": {
            "not_sla": True,
            "not_required_check_yet": True,
            "single_run_candidate_baseline": True,
            "advisory_warn_default": True,
        },
        "compared_from": {
            "head_scorecard_path": str(inputs.head_scorecard_path),
            "head_scorecard_sha256": _sha256_hex(inputs.head_scorecard_path),
            "baseline_path": str(inputs.baseline_path),
            "baseline_sha256": _sha256_hex(inputs.baseline_path),
            "threshold_path": str(inputs.threshold_path),
            "threshold_sha256": _sha256_hex(inputs.threshold_path),
            "catalog_path": str(inputs.catalog_path),
            "catalog_sha256": _sha256_hex(inputs.catalog_path),
            "benchmark_mode": inputs.benchmark_mode,
            "enforcement_mode_resolved": enforcement_mode_resolved,
            "cli_override_applied": inputs.cli_override,
            "generated_at": inputs.generated_at,
        },
        "overall_status": overall_status,
        "counts": counts,
        "scenarios": scenarios,
        "observed_extra_scenarios": observed_extra,
    }


def determine_exit_code(
    result: Mapping[str, Any],
    enforcement_mode: str,
    cli_override: str | None,
) -> int:
    """Policy-driven exit code with explicit override semantics.

    Codex 019e84b7 F2 absorb. iter-2 residual: unknown enforcement_mode is
    fail-closed (ValueError); never silently exits 0.
    """
    if cli_override not in _ALLOWED_OVERRIDES:
        raise ValueError(f"unknown cli_override: {cli_override!r}")
    if enforcement_mode not in _ALLOWED_MODES:
        raise ValueError(f"unknown enforcement_mode: {enforcement_mode!r}")

    status = result["overall_status"]
    if cli_override == "advisory":
        return 0
    if cli_override == "strict":
        return 1 if status in ("warn", "hard_fail") else 0
    if enforcement_mode == "advisory":
        return 0
    if enforcement_mode == "manual_block":
        return 1 if status == "hard_fail" else 0
    # ci_block_candidate
    return 1 if status in ("warn", "hard_fail") else 0


def canonical_json(data: Mapping[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


__all__ = [
    "ARTIFACT_KIND",
    "ComparisonInputs",
    "SCHEMA_VERSION",
    "build_comparison_result",
    "canonical_json",
    "determine_exit_code",
]
