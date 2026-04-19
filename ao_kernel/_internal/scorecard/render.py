"""Scorecard render — markdown for PR comment.

Consumes a :class:`ScorecardDiff` and produces a compact markdown
block suitable for `gh pr comment --body-file`. The first line is the
HTML sentinel ``<!-- ao-scorecard -->`` used by the sticky-comment
upsert flow (see ``post_comment.py``).
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from ao_kernel._internal.scorecard.compare import BenchmarkDiff, ScorecardDiff


SENTINEL = "<!-- ao-scorecard -->"
_DASH = "—"


def _fmt_delta_pct(value: float | None) -> str:
    if value is None:
        return _DASH
    if abs(value) < 0.05:
        return "(−)"
    arrow = "▲" if value > 0 else "▼"
    return f"({arrow}{abs(value):.1f}%)"


def _fmt_score_delta(value: float | None) -> str:
    if value is None:
        return _DASH
    if abs(value) < 0.005:
        return "(−)"
    sign = "+" if value > 0 else ""
    return f"({sign}{value:.2f})"


def _fmt_duration(ms: int | None, delta: str) -> str:
    if ms is None:
        return _DASH
    return f"{ms}ms {delta}".strip()


def _fmt_cost(usd: float | None, delta: str) -> str:
    if usd is None:
        return _DASH
    return f"${usd:.4f} {delta}".strip()


def _fmt_review_score(score: float | None, delta: str) -> str:
    if score is None:
        return _DASH
    return f"{score:.2f} {delta}".strip()


def _status_cell(status: str, changed: bool) -> str:
    icon = "✅" if status == "pass" else "❌"
    if changed:
        return f"{icon} {status} ⚠️"
    return f"{icon} {status}"


def render_row(
    entry: BenchmarkDiff,
    head_entry: Mapping[str, Any] | None,
) -> str:
    status = _status_cell(entry.head_status, entry.status_changed)
    dur_delta = _fmt_delta_pct(entry.duration_delta_pct)
    cost_delta = _fmt_delta_pct(entry.cost_delta_pct)
    score_delta = _fmt_score_delta(entry.review_score_delta)

    entry_data: Mapping[str, Any] = head_entry or {}
    dur = _fmt_duration(entry_data.get("duration_ms"), dur_delta)
    cost = _fmt_cost(entry_data.get("cost_consumed_usd"), cost_delta)
    score = _fmt_review_score(entry_data.get("review_score"), score_delta)
    return f"| {entry.scenario} | {status} | {dur} | {cost} | {score} |"


def _render_footer(
    diff: ScorecardDiff,
    regressions: Iterable[BenchmarkDiff],
) -> str:
    baseline = f"`{diff.baseline_sha}`" if diff.baseline_sha else "_(not found)_"
    head = f"`{diff.head_sha}`"
    # v3.7 F2 absorb: footer labels per Codex iter-2 correction.
    # `real_adapter` is event-backed (`llm_spend_recorded.source=
    # "adapter_path"`) — NOT claim vendor-billed external spend.
    # `mock_shim` label only renders for historical artefacts; post-F2
    # fast-mode runs emit `cost_source=None`.
    cost_source_note = ""
    if diff.head_cost_source == "mock_shim":
        cost_source_note = " · Cost source: `mock_shim` (benchmark-only; not real billing)"
    elif diff.head_cost_source == "real_adapter":
        cost_source_note = " · Cost source: `real_adapter` (adapter-path reconcile; event-backed, non-shim)"
    elif diff.head_cost_source:
        cost_source_note = f" · Cost source: `{diff.head_cost_source}`"
    pr_note = ""
    if diff.pr_number is not None:
        pr_note = f" · PR: #{diff.pr_number}"
    regression_list = list(regressions)
    if not regression_list:
        summary = "No regressions."
    else:
        summary = f"⚠️ {len(regression_list)} regression(s) detected."
    return f"_Baseline: {baseline} · HEAD: {head}{pr_note}{cost_source_note} · {summary}_"


def _render_regression_list(regressions: Iterable[BenchmarkDiff]) -> str:
    lines: list[str] = []
    for entry in regressions:
        reasons = ", ".join(entry.regression_reasons) or "regressed"
        lines.append(f"- **{entry.scenario}**: {reasons}")
    if not lines:
        return ""
    return "\n\n**Regressions:**\n\n" + "\n".join(lines)


def render_diff(
    diff: ScorecardDiff,
    *,
    head_scorecard: Mapping[str, Any] | None = None,
) -> str:
    """Render a PR-comment-ready markdown block for ``diff``.

    ``head_scorecard`` is optional; when provided its benchmark entries
    are used to surface absolute values (head duration/cost/score) next
    to the deltas. Pass the parsed head scorecard JSON.
    """
    header = "### 📊 Benchmark Scorecard\n\n"
    table = "| Scenario | Status | Duration | Cost (USD) | Review Score |\n|---|---|---|---|---|\n"
    head_by_scenario: dict[str, Mapping[str, Any]] = {}
    if isinstance(head_scorecard, Mapping):
        for entry in head_scorecard.get("benchmarks") or []:
            if isinstance(entry, Mapping) and isinstance(entry.get("scenario"), str):
                head_by_scenario[entry["scenario"]] = entry

    body_rows: list[str] = []
    regressions: list[BenchmarkDiff] = []
    for entry in diff.entries:
        body_rows.append(render_row(entry, head_by_scenario.get(entry.scenario)))
        if entry.regression:
            regressions.append(entry)

    body = table + "\n".join(body_rows) + "\n"
    footer = _render_footer(diff, regressions)
    regression_list = _render_regression_list(regressions)
    return f"{SENTINEL}\n{header}{body}\n{footer}{regression_list}\n"


__all__ = ["SENTINEL", "render_diff", "render_row"]
