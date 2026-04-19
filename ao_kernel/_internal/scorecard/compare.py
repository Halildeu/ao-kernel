"""Scorecard compare — baseline vs head diff math.

Pure functions over the scorecard artefact (``urn:ao:scorecard:v1``).
Returns a structured ``ScorecardDiff`` which the render and CLI layers
consume. Policy thresholds drive the ``regression`` flag; the CLI
layer decides whether to exit 1 on ``fail_action=block``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class BenchmarkDiff:
    scenario: str
    baseline_status: str | None
    head_status: str
    status_changed: bool
    duration_delta_pct: float | None
    cost_delta_pct: float | None
    review_score_delta: float | None
    regression: bool
    regression_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "baseline_status": self.baseline_status,
            "head_status": self.head_status,
            "status_changed": self.status_changed,
            "duration_delta_pct": self.duration_delta_pct,
            "cost_delta_pct": self.cost_delta_pct,
            "review_score_delta": self.review_score_delta,
            "regression": self.regression,
            "regression_reasons": list(self.regression_reasons),
        }


@dataclass(frozen=True)
class ScorecardDiff:
    baseline_sha: str | None
    head_sha: str
    pr_number: int | None
    entries: tuple[BenchmarkDiff, ...]
    has_regression: bool
    fail_action: str  # "warn" | "block"
    head_cost_source: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_sha": self.baseline_sha,
            "head_sha": self.head_sha,
            "pr_number": self.pr_number,
            "entries": [entry.to_dict() for entry in self.entries],
            "has_regression": self.has_regression,
            "fail_action": self.fail_action,
            "head_cost_source": self.head_cost_source,
        }


def _index_by_scenario(
    scorecard: Mapping[str, Any] | None,
) -> dict[str, Mapping[str, Any]]:
    if not scorecard:
        return {}
    benchmarks = scorecard.get("benchmarks") or []
    indexed: dict[str, Mapping[str, Any]] = {}
    for entry in benchmarks:
        if isinstance(entry, dict) and isinstance(entry.get("scenario"), str):
            indexed[entry["scenario"]] = entry
    return indexed


def _delta_pct(baseline: float | None, head: float | None) -> float | None:
    """Percent change head over baseline. None when either side is None
    or baseline is 0 (pct undefined)."""
    if baseline is None or head is None:
        return None
    if baseline == 0:
        return None
    return (head - baseline) / baseline * 100.0


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _build_entry(
    scenario: str,
    baseline_entry: Mapping[str, Any] | None,
    head_entry: Mapping[str, Any] | None,
    thresholds: Mapping[str, float],
) -> BenchmarkDiff:
    head_status = (head_entry.get("status") if isinstance(head_entry, Mapping) else None) or "fail"
    baseline_status = baseline_entry.get("status") if isinstance(baseline_entry, Mapping) else None
    status_changed = bool(baseline_status is not None and baseline_status != head_status)

    baseline_duration = _coerce_float((baseline_entry or {}).get("duration_ms"))
    head_duration = _coerce_float((head_entry or {}).get("duration_ms"))
    duration_delta_pct = _delta_pct(baseline_duration, head_duration)

    baseline_cost = _coerce_float((baseline_entry or {}).get("cost_consumed_usd"))
    head_cost = _coerce_float((head_entry or {}).get("cost_consumed_usd"))
    cost_delta_pct = _delta_pct(baseline_cost, head_cost)

    baseline_review = _coerce_float((baseline_entry or {}).get("review_score"))
    head_review = _coerce_float((head_entry or {}).get("review_score"))
    review_delta = head_review - baseline_review if (baseline_review is not None and head_review is not None) else None

    reasons: list[str] = []

    if head_entry is None and baseline_entry is not None:
        reasons.append("scenario_disappeared")
    elif baseline_status == "pass" and head_status == "fail":
        reasons.append("status_pass_to_fail")

    dur_threshold = thresholds.get("duration_ms_relative_pct", 30.0)
    if duration_delta_pct is not None and duration_delta_pct > dur_threshold:
        reasons.append(f"duration_up_{duration_delta_pct:.1f}pct")

    cost_threshold = thresholds.get("cost_usd_relative_pct", 20.0)
    if cost_delta_pct is not None and cost_delta_pct > cost_threshold:
        reasons.append(f"cost_up_{cost_delta_pct:.1f}pct")

    review_min_delta = thresholds.get("review_score_min_delta", -0.1)
    if review_delta is not None and review_delta < review_min_delta:
        reasons.append(f"review_score_drop_{review_delta:+.3f}")

    return BenchmarkDiff(
        scenario=scenario,
        baseline_status=baseline_status,
        head_status=head_status,
        status_changed=status_changed,
        duration_delta_pct=duration_delta_pct,
        cost_delta_pct=cost_delta_pct,
        review_score_delta=review_delta,
        regression=bool(reasons),
        regression_reasons=tuple(reasons),
    )


def compare_scorecards(
    baseline: Mapping[str, Any] | None,
    head: Mapping[str, Any],
    *,
    policy: Mapping[str, Any] | None = None,
) -> ScorecardDiff:
    """Diff two scorecards against policy thresholds.

    Args:
        baseline: Scorecard artefact for the baseline commit, or ``None``
            when no baseline is available (first-run PR).
        head: Scorecard artefact for the HEAD commit under PR review.
        policy: ``policy_scorecard.v1.json`` object; falls back to the
            bundled defaults when ``None``.
    """
    if not isinstance(head, Mapping):
        raise TypeError("head scorecard must be a mapping")

    policy = dict(policy or _default_policy())
    thresholds = dict(policy.get("regression_threshold") or {})
    fail_action = str(policy.get("fail_action") or "warn")

    baseline_idx = _index_by_scenario(baseline)
    head_idx = _index_by_scenario(head)

    scenarios = sorted(set(baseline_idx) | set(head_idx))
    entries: list[BenchmarkDiff] = []
    for scenario in scenarios:
        baseline_entry = baseline_idx.get(scenario)
        head_entry = head_idx.get(scenario)
        entry = _build_entry(
            scenario,
            baseline_entry,
            head_entry,
            thresholds,
        )
        entries.append(entry)

    head_sha = str(head.get("git_sha") or "unknown")
    baseline_sha = str(baseline.get("git_sha")) if isinstance(baseline, Mapping) else None
    pr_raw = head.get("pr_number")
    pr_number = int(pr_raw) if isinstance(pr_raw, int) else None
    head_cost_source: str | None = None
    for head_row in head_idx.values():
        cost_source = head_row.get("cost_source")
        if isinstance(cost_source, str):
            head_cost_source = cost_source
            break

    has_regression = any(entry.regression for entry in entries)
    return ScorecardDiff(
        baseline_sha=baseline_sha,
        head_sha=head_sha,
        pr_number=pr_number,
        entries=tuple(entries),
        has_regression=has_regression,
        fail_action=fail_action,
        head_cost_source=head_cost_source,
    )


def _default_policy() -> dict[str, Any]:
    from ao_kernel.config import load_default

    return load_default("policies", "policy_scorecard.v1.json")


def exit_code_for(diff: ScorecardDiff) -> int:
    """Return 1 when ``fail_action=block`` + at least one regression."""
    if diff.fail_action == "block" and diff.has_regression:
        return 1
    return 0


def select_regressions(diff: ScorecardDiff) -> Sequence[BenchmarkDiff]:
    return tuple(entry for entry in diff.entries if entry.regression)


__all__ = [
    "BenchmarkDiff",
    "ScorecardDiff",
    "compare_scorecards",
    "exit_code_for",
    "select_regressions",
]
