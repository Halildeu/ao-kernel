"""v3.5 D3 — Dev Scorecard public facade.

Consumes the PR-B7 benchmark suite output (run_dir events.jsonl + run
state + capability artefacts) and emits a typed scorecard JSON. Three
CLI verbs:

- ``ao-kernel scorecard emit`` — runs benchmarks via pytest + writes
  ``benchmark_scorecard.v1.json`` (honours ``AO_SCORECARD_OUTPUT``).
  Policy-agnostic: always produces output regardless of
  ``policy_scorecard.enabled``.
- ``ao-kernel scorecard compare --baseline ... --head ...`` — diffs two
  scorecards and prints the rendered markdown. Exit 1 on regression
  when ``fail_action=block``; exit 0 + warn banner otherwise.
- ``ao-kernel scorecard render --input ...`` — renders markdown only;
  no policy evaluation, no exit-code gating.
- ``ao-kernel scorecard post-comment --pr N --body-file F --sentinel M``
  — CI-side sentinel-sticky upsert via ``gh``; advisory-only (exit 0
  even on failure).

Canonical scenario input is driven by ``@pytest.mark.scorecard_primary``
on ``tests/benchmarks/test_governed_{bugfix,review}.py``. Duplicate or
missing-primary both fail-close at session finish (§3.3 of the PR-D3
plan).

See ``.claude/plans/PR-D3-DRAFT-PLAN.md`` for the full design contract.
"""

from __future__ import annotations

from ao_kernel._internal.scorecard.collector import (
    DEFAULT_OUTPUT_FILENAME,
    EXPECTED_PRIMARY_SCENARIOS,
    BenchmarkResult,
    PrimarySidecar,
    ScorecardCollectorError,
    ScorecardRegistry,
    build_result,
    build_scorecard,
    finalize_session,
    resolve_output_path,
)
from ao_kernel._internal.scorecard.compare import (
    BenchmarkDiff,
    ScorecardDiff,
    compare_scorecards,
    exit_code_for,
    select_regressions,
)
from ao_kernel._internal.scorecard.post_comment import (
    PostCommentResult,
    upsert_sticky_comment,
)
from ao_kernel._internal.scorecard.render import (
    SENTINEL,
    render_diff,
    render_row,
)


__all__ = [
    "DEFAULT_OUTPUT_FILENAME",
    "EXPECTED_PRIMARY_SCENARIOS",
    "SENTINEL",
    "BenchmarkDiff",
    "BenchmarkResult",
    "PostCommentResult",
    "PrimarySidecar",
    "ScorecardCollectorError",
    "ScorecardDiff",
    "ScorecardRegistry",
    "build_result",
    "build_scorecard",
    "compare_scorecards",
    "exit_code_for",
    "finalize_session",
    "render_diff",
    "render_row",
    "resolve_output_path",
    "select_regressions",
    "upsert_sticky_comment",
]
