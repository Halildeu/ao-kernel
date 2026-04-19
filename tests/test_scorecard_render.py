"""v3.5 D3: scorecard render markdown tests (8 pins)."""

from __future__ import annotations

from typing import Any

from ao_kernel._internal.scorecard.compare import compare_scorecards
from ao_kernel._internal.scorecard.render import SENTINEL, render_diff


_POLICY = {
    "fail_action": "warn",
    "regression_threshold": {
        "duration_ms_relative_pct": 30.0,
        "cost_usd_relative_pct": 20.0,
        "review_score_min_delta": -0.1,
    },
}


def _scorecard(*entries: dict[str, Any], git_sha: str = "abc1234", pr: int | None = None) -> dict:
    return {
        "schema_version": "v1",
        "generated_at": "2026-04-18T10:00:00Z",
        "git_sha": git_sha,
        "pr_number": pr,
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
) -> dict[str, Any]:
    return {
        "scenario": scenario,
        "status": status,
        "workflow_completed": status == "pass",
        "duration_ms": duration_ms,
        "cost_consumed_usd": cost_consumed_usd,
        "cost_source": cost_source,
        "review_score": review_score,
    }


class TestRenderMarkdown:
    def test_sentinel_on_first_line(self) -> None:
        head = _scorecard(_entry("s"))
        diff = compare_scorecards(head, head, policy=_POLICY)
        rendered = render_diff(diff, head_scorecard=head)
        assert rendered.startswith(SENTINEL + "\n")
        assert SENTINEL == "<!-- ao-scorecard -->"

    def test_no_regressions_footer(self) -> None:
        head = _scorecard(_entry("s"))
        diff = compare_scorecards(head, head, policy=_POLICY)
        rendered = render_diff(diff, head_scorecard=head)
        assert "No regressions." in rendered

    def test_regression_banner_has_warning_emoji(self) -> None:
        baseline = _scorecard(_entry("s", duration_ms=100))
        head = _scorecard(_entry("s", duration_ms=300))
        diff = compare_scorecards(baseline, head, policy=_POLICY)
        rendered = render_diff(diff, head_scorecard=head)
        assert "⚠️ 1 regression(s) detected" in rendered
        assert "**Regressions:**" in rendered
        assert "**s**" in rendered

    def test_unicode_arrows_direction(self) -> None:
        baseline = _scorecard(_entry("s", duration_ms=100))
        head = _scorecard(_entry("s", duration_ms=150))
        diff = compare_scorecards(baseline, head, policy=_POLICY)
        rendered = render_diff(diff, head_scorecard=head)
        assert "▲" in rendered  # increase
        head_down = _scorecard(_entry("s", duration_ms=60))
        diff_down = compare_scorecards(baseline, head_down, policy=_POLICY)
        rendered_down = render_diff(diff_down, head_scorecard=head_down)
        assert "▼" in rendered_down

    def test_null_values_render_as_em_dash(self) -> None:
        head = _scorecard(
            _entry(
                "s",
                duration_ms=None,
                cost_consumed_usd=None,
                review_score=None,
            ),
        )
        diff = compare_scorecards(None, head, policy=_POLICY)
        rendered = render_diff(diff, head_scorecard=head)
        # Null cells render as em-dash, not literal "None".
        assert "None" not in rendered
        assert "—" in rendered

    def test_missing_baseline_footer(self) -> None:
        head = _scorecard(_entry("s"))
        diff = compare_scorecards(None, head, policy=_POLICY)
        rendered = render_diff(diff, head_scorecard=head)
        assert "Baseline: _(not found)_" in rendered

    def test_pr_number_in_footer(self) -> None:
        head = _scorecard(_entry("s"), pr=42)
        diff = compare_scorecards(head, head, policy=_POLICY)
        rendered = render_diff(diff, head_scorecard=head)
        assert "PR: #42" in rendered

    def test_cost_source_in_footer(self) -> None:
        head = _scorecard(_entry("s", cost_source="mock_shim"))
        diff = compare_scorecards(head, head, policy=_POLICY)
        rendered = render_diff(diff, head_scorecard=head)
        assert "mock_shim" in rendered
        assert "benchmark-only; not real billing" in rendered

    def test_real_adapter_cost_source_footer(self) -> None:
        """v3.7 F2: `real_adapter` label renders event-backed wording."""
        head = _scorecard(_entry("s", cost_source="real_adapter"))
        diff = compare_scorecards(head, head, policy=_POLICY)
        rendered = render_diff(diff, head_scorecard=head)
        assert "real_adapter" in rendered
        assert "adapter-path reconcile" in rendered
        assert "event-backed" in rendered
        # Do NOT claim vendor-billed external spend (Codex F2 absorb).
        assert "real adapter spend" not in rendered

    def test_none_cost_source_has_no_footer_note(self) -> None:
        """v3.7 F2 fast-mode contract: `cost_source=None` → no cost
        source annotation in the footer."""
        head = _scorecard(_entry("s", cost_source=None))
        diff = compare_scorecards(head, head, policy=_POLICY)
        rendered = render_diff(diff, head_scorecard=head)
        assert "Cost source:" not in rendered
