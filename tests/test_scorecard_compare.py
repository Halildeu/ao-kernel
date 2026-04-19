"""v3.5 D3: scorecard compare math tests (10 pins)."""

from __future__ import annotations

from typing import Any


from ao_kernel._internal.scorecard.compare import (
    compare_scorecards,
    exit_code_for,
    select_regressions,
)


_DEFAULT_POLICY = {
    "fail_action": "warn",
    "regression_threshold": {
        "duration_ms_relative_pct": 30.0,
        "cost_usd_relative_pct": 20.0,
        "review_score_min_delta": -0.1,
    },
}


def _scorecard(*entries: dict[str, Any], git_sha: str = "abc1234") -> dict:
    return {
        "schema_version": "v1",
        "generated_at": "2026-04-18T10:00:00Z",
        "git_sha": git_sha,
        "pr_number": None,
        "benchmarks": list(entries),
    }


def _entry(
    scenario: str,
    *,
    status: str = "pass",
    duration_ms: int | None = 100,
    cost_consumed_usd: float | None = 0.01,
    cost_source: str | None = "mock_shim",
    review_score: float | None = None,
    workflow_completed: bool = True,
) -> dict[str, Any]:
    return {
        "scenario": scenario,
        "status": status,
        "workflow_completed": workflow_completed,
        "duration_ms": duration_ms,
        "cost_consumed_usd": cost_consumed_usd,
        "cost_source": cost_source,
        "review_score": review_score,
    }


class TestHappyPath:
    def test_identical_scorecards_no_regression(self) -> None:
        entry = _entry("governed_bugfix", duration_ms=100, cost_consumed_usd=0.01)
        baseline = _scorecard(entry)
        head = _scorecard(entry)
        diff = compare_scorecards(baseline, head, policy=_DEFAULT_POLICY)
        assert diff.has_regression is False
        assert diff.entries[0].regression is False
        assert diff.entries[0].duration_delta_pct == 0.0


class TestMissingBaseline:
    def test_null_baseline_yields_null_deltas(self) -> None:
        head = _scorecard(_entry("governed_review", review_score=0.9))
        diff = compare_scorecards(None, head, policy=_DEFAULT_POLICY)
        entry = diff.entries[0]
        assert entry.duration_delta_pct is None
        assert entry.cost_delta_pct is None
        assert entry.review_score_delta is None
        assert entry.regression is False
        assert diff.baseline_sha is None


class TestRegressionThresholds:
    def test_duration_over_threshold(self) -> None:
        baseline = _scorecard(_entry("s", duration_ms=100))
        head = _scorecard(_entry("s", duration_ms=140))  # +40% > 30
        diff = compare_scorecards(baseline, head, policy=_DEFAULT_POLICY)
        assert diff.entries[0].regression is True
        assert any("duration_up" in reason for reason in diff.entries[0].regression_reasons)

    def test_cost_over_threshold(self) -> None:
        baseline = _scorecard(_entry("s", cost_consumed_usd=0.01))
        head = _scorecard(_entry("s", cost_consumed_usd=0.013))  # +30% > 20
        diff = compare_scorecards(baseline, head, policy=_DEFAULT_POLICY)
        assert diff.entries[0].regression is True
        assert any("cost_up" in reason for reason in diff.entries[0].regression_reasons)

    def test_review_score_drop_beyond_tolerance(self) -> None:
        baseline = _scorecard(_entry("s", review_score=0.9))
        head = _scorecard(_entry("s", review_score=0.75))  # -0.15 < -0.1
        diff = compare_scorecards(baseline, head, policy=_DEFAULT_POLICY)
        assert diff.entries[0].regression is True
        assert any("review_score_drop" in reason for reason in diff.entries[0].regression_reasons)


class TestFailAction:
    def test_warn_action_keeps_exit_code_0(self) -> None:
        baseline = _scorecard(_entry("s", duration_ms=100))
        head = _scorecard(_entry("s", duration_ms=200))
        diff = compare_scorecards(
            baseline,
            head,
            policy={**_DEFAULT_POLICY, "fail_action": "warn"},
        )
        assert diff.has_regression is True
        assert exit_code_for(diff) == 0

    def test_block_action_exits_1_on_regression(self) -> None:
        baseline = _scorecard(_entry("s", duration_ms=100))
        head = _scorecard(_entry("s", duration_ms=200))
        diff = compare_scorecards(
            baseline,
            head,
            policy={**_DEFAULT_POLICY, "fail_action": "block"},
        )
        assert exit_code_for(diff) == 1


class TestStatusChange:
    def test_pass_to_fail_flags_status_change(self) -> None:
        baseline = _scorecard(_entry("s", status="pass"))
        head = _scorecard(_entry("s", status="fail"))
        diff = compare_scorecards(baseline, head, policy=_DEFAULT_POLICY)
        entry = diff.entries[0]
        assert entry.status_changed is True
        assert entry.regression is True
        assert "status_pass_to_fail" in entry.regression_reasons


class TestScenarioMembership:
    def test_scenario_disappeared_from_head(self) -> None:
        baseline = _scorecard(_entry("gone"), _entry("kept"))
        head = _scorecard(_entry("kept"))
        diff = compare_scorecards(baseline, head, policy=_DEFAULT_POLICY)
        gone_entry = next(entry for entry in diff.entries if entry.scenario == "gone")
        assert gone_entry.regression is True
        assert "scenario_disappeared" in gone_entry.regression_reasons

    def test_new_scenario_in_head_only_is_not_regression(self) -> None:
        baseline = _scorecard(_entry("old"))
        head = _scorecard(_entry("old"), _entry("new_one"))
        diff = compare_scorecards(baseline, head, policy=_DEFAULT_POLICY)
        new_entry = next(entry for entry in diff.entries if entry.scenario == "new_one")
        assert new_entry.regression is False


class TestSelectRegressions:
    def test_returns_only_regression_entries(self) -> None:
        baseline = _scorecard(
            _entry("fast", duration_ms=50),
            _entry("slow", duration_ms=100),
        )
        head = _scorecard(
            _entry("fast", duration_ms=50),
            _entry("slow", duration_ms=200),
        )
        diff = compare_scorecards(baseline, head, policy=_DEFAULT_POLICY)
        regressions = list(select_regressions(diff))
        assert len(regressions) == 1
        assert regressions[0].scenario == "slow"
