# PR v3.5 D3 — Dev Scorecard (benchmark compare + PR comment)

**Status:** DRAFT v2 — absorbed Codex iter-1 PARTIAL (3 revisions + 7 Q&A)
**Scope:** v3.5.0 release track, final D-series PR before version bump
**Depends on:** D1 (paths), D2a (archive), D2b (promotion) — all merged
**Parallel to:** none (single-track plan)

---

## 1. Problem statement

`tests/benchmarks/` emits run-dir JSONL events and capability artifacts, but
there is no surface that:

1. Aggregates benchmark outputs into a single compact "scorecard" JSON.
2. Compares a PR's scorecard vs the main-branch baseline scorecard.
3. Posts the scorecard + delta as a PR comment.

Without a scorecard surface, benchmark regressions are visible only in full CI
logs — easy to miss. D3 closes this gap as the final v3.5.0 commitment.

**Not in v1:** multi-commit trend / sparkline visualisation. Draft title
was trimmed from "benchmark compare + trend + PR comment" to "benchmark
compare + PR comment" (iter-2 absorb of Codex revision #4). Trend is
deferred to v3.6+ as a read-side-only extension of the same scorecard
artifacts.

---

## 2. Non-goals

- **No new benchmark scenarios** — D3 consumes B7's two existing flows
  (`governed_bugfix` + `governed_review`). New scenarios are B7.x+ work.
- **No CI-gate enforcement (bundled policy)** — D3 v1 ships bundled
  `policy_scorecard.v1.json` with `fail_action: "warn"`; CI never fails
  the PR on scorecard regressions. (The `compare` CLI **does** support
  `block` for local/manual use — regression + `fail_action=block` →
  exit 1; but the bundled policy stays `warn`. Iter-2 absorb of
  Codex revision #3 — CLI/bundled split made explicit.)
- **No repo-committed history** — trend window reads from GHA artifacts,
  never mutates the repo.
- **No scorecard promotion into canonical store** — scorecards are CI
  surface; the D2b canonical promotion pipeline stays consultation-only.
- **No real-adapter mode changes** — `--benchmark-mode=full` is FAZ-C scope;
  D3 reads whatever fast-mode produces.
- **Does NOT duplicate the existing `policy_benchmark.v1.json`** — that
  policy governs the *maturity-tracking* benchmark (unrelated legacy
  surface with different artifacts). D3 is the *runtime benchmark suite*
  scorecard (PR-B7 flows). Naming is deliberately distinct.

---

## 3. Design overview

### 3.1 Module layout

```
ao_kernel/
  scorecard.py                      # PUBLIC facade
  _internal/scorecard/
    __init__.py
    collector.py                    # pytest plugin — walks benchmark run_dirs
    compare.py                      # baseline diff math
    render.py                       # markdown renderer for PR comment
  defaults/
    policies/policy_scorecard.v1.json
    schemas/scorecard.schema.v1.json
cli.py                              # add `scorecard` subcommand
tests/
  test_scorecard_collector.py
  test_scorecard_compare.py
  test_scorecard_render.py
  test_scorecard_cli.py
```

### 3.2 Scorecard schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "urn:ao:scorecard:v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "generated_at", "git_sha", "benchmarks"],
  "properties": {
    "schema_version": { "const": "v1" },
    "generated_at": { "type": "string", "format": "date-time" },
    "git_sha": { "type": "string", "pattern": "^[0-9a-f]{7,40}$" },
    "git_ref": { "type": "string" },
    "pr_number": { "type": ["integer", "null"] },
    "benchmarks": {
      "type": "array",
      "items": { "$ref": "#/$defs/benchmark_result" }
    }
  },
  "$defs": {
    "benchmark_result": {
      "type": "object",
      "additionalProperties": true,
      "required": ["scenario", "status", "workflow_completed"],
      "properties": {
        "scenario": { "type": "string" },
        "status": { "enum": ["pass", "fail"] },
        "workflow_completed": { "type": "boolean" },
        "duration_ms": { "type": ["integer", "null"] },
        "cost_consumed_usd": { "type": ["number", "null"] },
        "cost_source": {
          "type": ["string", "null"],
          "description": "Where cost_consumed_usd came from. v1: 'mock_shim' (B7 benchmark-only shim). Post-C3 real-adapter runs: 'real_adapter'."
        },
        "review_score": { "type": ["number", "null"], "minimum": 0, "maximum": 1 }
      }
    }
  }
}
```

`additionalProperties: true` on `benchmark_result` — forward-extensible.
`additionalProperties: false` on top-level — strict contract.

### 3.3 Collector — pytest plugin + canonical marker

**Canonical input (Codex iter-1 revision #1 absorb).** The benchmark suite
has multiple tests per scenario (parametrized review threshold pass/fail,
cost-consumption tests, transport-error negatives, contract pins —
see `tests/benchmarks/test_governed_{bugfix,review}.py`). Only ONE
happy-path run per scenario feeds the scorecard; the rest stay
exclusive to their own assertions.

**Marker mechanism:**
- New pytest marker `@pytest.mark.scorecard_primary` registered in
  `tests/benchmarks/conftest.py` via `pytest_configure`.
- Exactly one primary test per scenario; collector refuses the session
  (session-fail diagnostic, no scorecard written) if `>1` primary tests
  are found for the same `scenario_id`.
- The primary test's fixture exposes its `run_dir` + `scenario_id` via
  a `benchmark_primary_sidecar` fixture that the plugin consumes.
- D3 marks the actual primary tests with `@pytest.mark.scorecard_primary`:
  - `tests/benchmarks/test_governed_review.py::TestHappyPath::test_review_findings_flow_completes`
  - `tests/benchmarks/test_governed_bugfix.py::TestHappyPath::test_end_to_end_completes`

  One-line decorator change in each file, no fixture churn.

- **Zero-primary is also fail-closed** (Codex AGREE tighten #3): if
  the session finishes with ZERO tests carrying
  `@scorecard_primary` AND at least one canonical scenario is
  expected (registered list of scenario ids the collector knows
  about), emit `session-fail diagnostic + no scorecard`. Duplicate
  and missing both silent-misconfiguration paths close.

**Implementation:**

`ao_kernel/_internal/scorecard/collector.py` registers a pytest plugin via
`conftest.py` at `tests/benchmarks/conftest.py` (extend existing file).

Key hook: `pytest_sessionfinish(session, exitstatus)` reads the primary
sidecars recorded during the session and emits one `BenchmarkResult`
per scenario. Results persist to `AO_SCORECARD_OUTPUT` (env var, default
`benchmark_scorecard.v1.json` under CWD).

**Rationale for env-var output path:** CI sets it explicitly; local dev uses
the default. No CLI flag required — pytest stays pure.

**Extraction rules (deterministic):**
- `scenario` = scenario_id declared on the primary sidecar; fallback to
  test module basename (`test_governed_review` → `governed_review`).
- `status` = "pass" if `workflow_completed` event present AND no
  `workflow_failed` event; else "fail".
- `workflow_completed` = bool presence of event kind.
- `duration_ms` = `(last_event.ts - first_event.ts)` in ms; null if empty.
- `cost_consumed_usd` = `limit - remaining` on `budget.cost_usd` axis in the
  final run-state snapshot; null if unseeded.
- `review_score` = captured only for `governed_review` via the
  `review-findings.v1.json` capability artifact's `score` field; null
  otherwise.
- `cost_source` (new extensible field, always populated v1) =
  `"mock_shim"` (hard-coded v1 — B7 benchmark shim). Render footer
  surfaces this so baseline drift isn't misread as real billing.

### 3.4 Compare — baseline diff

`ao_kernel/_internal/scorecard/compare.py`:

```python
@dataclass(frozen=True)
class ScorecardDiff:
    baseline_sha: str | None
    head_sha: str
    entries: tuple[BenchmarkDiff, ...]

@dataclass(frozen=True)
class BenchmarkDiff:
    scenario: str
    status_changed: bool  # pass→fail or fail→pass
    duration_delta_pct: float | None
    cost_delta_pct: float | None
    review_score_delta: float | None
    regression: bool  # True if any threshold breached
```

Policy thresholds (from `policy_scorecard.v1.json`):
- `duration_ms_relative_pct` — default 30%
- `cost_usd_relative_pct` — default 20%
- `review_score_min_delta` — default -0.1 (score can drop by ≤0.1)

Missing baseline → `baseline_sha=None`; all diffs are null; regression=False.

### 3.5 Render — markdown

`ao_kernel/_internal/scorecard/render.py` produces:

```markdown
<!-- ao-scorecard -->
### 📊 Benchmark Scorecard

| Scenario | Status | Duration | Cost (USD) | Review Score |
|---|---|---|---|---|
| governed_bugfix | ✅ pass | 245ms (▼5%) | $0.002 (−) | — |
| governed_review | ✅ pass | 312ms (▲12%) | $0.003 (+3%) | 0.87 (−0.03) |

_Baseline: `abc1234` (main) · HEAD: `def5678` · Cost source: mock_shim
(benchmark-only; not real billing) · No regressions._
```

**HTML sentinel `<!-- ao-scorecard -->` on first line** — consumed by
the sticky-comment upsert script (§3.7) to locate the existing bot
comment and PATCH instead of appending.

Unicode arrows ▲/▼ for directional cues, plain `−` for null. Regression
line switches to `⚠️ <N> regression(s) detected:` with bullet list.

**Cost source footer** (Codex iter-1 Q5 absorb) explicitly names the
`cost_source` field from the scorecard's benchmark entries. When the
first post-C3 scorecard lands with `cost_source="real_adapter"`, the
footer updates automatically.

### 3.6 CLI

`ao-kernel scorecard emit [--output PATH]` — runs benchmarks via pytest
subprocess + writes scorecard. Default output
`./benchmark_scorecard.v1.json`. Always produces output (policy-agnostic
per §3.8).

`ao-kernel scorecard compare --baseline PATH --head PATH [--policy PATH]`
— diffs two scorecards, prints render, exits based on policy:
- `fail_action=warn` (default / bundled) → exit 0 always; regressions
  surface in rendered banner.
- `fail_action=block` → exit 0 on clean diff, exit 1 on any regression.
  Useful for local pre-push / manual gates; CI bundled policy stays
  `warn` (§2 non-goal).

`ao-kernel scorecard render --input PATH [--baseline PATH]` — just
renders markdown to stdout; no exit-code gating, no policy read.

`ao-kernel scorecard post-comment --pr N --body-file FILE --sentinel MARKER`
— small CI-only subcommand that handles the sticky-comment upsert
(finds existing comment with MARKER via `gh api`; PATCH if found,
POST otherwise). Pinned to `gh` CLI; delegates auth to env
`GH_TOKEN`. Exits 0 even on upsert failure (advisory-only).

### 3.7 CI workflow integration

**SSOT fix (Codex iter-1 revision #2 absorb).** The scorecard job MUST NOT
re-run the benchmark suite. Canonical benchmark run stays in the existing
`benchmark-fast` job; the collector writes `benchmark_scorecard.v1.json`
there and uploads it as an artifact. The new `scorecard` job only
downloads + diffs + comments.

**Changes to existing `benchmark-fast` job** (minimal extension — env var
+ upload step):

```yaml
benchmark-fast:
  name: benchmark-fast
  runs-on: ubuntu-latest
  needs: [test]
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: { python-version: "3.13" }
    - name: Install
      run: pip install -e ".[dev,llm,mcp,metrics]"
    - name: Run PR-B7 benchmarks (fast mode) + emit scorecard
      env: { AO_SCORECARD_OUTPUT: benchmark_scorecard.v1.json }
      run: pytest tests/benchmarks/ -q
    - name: Upload head scorecard
      uses: actions/upload-artifact@v4
      with:
        name: scorecard-${{ github.sha }}
        path: benchmark_scorecard.v1.json
    - name: Upload main baseline (main push only)
      if: github.ref == 'refs/heads/main'
      uses: actions/upload-artifact@v4
      with: { name: scorecard-main, path: benchmark_scorecard.v1.json }
```

**New `scorecard` job — compare + comment only:**

```yaml
scorecard:
  name: scorecard
  runs-on: ubuntu-latest
  needs: [benchmark-fast]
  if: github.event_name == 'pull_request'
  permissions:
    pull-requests: write
    contents: read
    actions: read
  continue-on-error: true    # advisory — comment failure never reds the PR
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: { python-version: "3.13" }
    - name: Install
      run: pip install -e ".[dev,llm,mcp,metrics]"
    - name: Download head scorecard
      uses: actions/download-artifact@v4
      with:
        name: scorecard-${{ github.sha }}
        path: head/
    - name: Download main baseline scorecard
      uses: dawidd6/action-download-artifact@<commit-sha-pin>
      with:
        workflow: test.yml
        branch: main
        name: scorecard-main
        path: ./baseline/
        if_no_artifact_found: warn
    - name: Compose scorecard comment
      run: |
        ao-kernel scorecard compare \
          --baseline baseline/benchmark_scorecard.v1.json \
          --head head/benchmark_scorecard.v1.json \
          > scorecard_comment.md
    - name: Post PR comment (sticky)
      env: { GH_TOKEN: ${{ secrets.GITHUB_TOKEN }} }
      run: |
        # Sentinel-based upsert (Codex iter-1 Q3 improvement over
        # `--edit-last`). Find existing comment containing the
        # `<!-- ao-scorecard -->` marker; PATCH if found, POST if not.
        ao-kernel scorecard post-comment \
          --pr ${{ github.event.pull_request.number }} \
          --body-file scorecard_comment.md \
          --sentinel '<!-- ao-scorecard -->' || true
```

**Third-party action pin (Codex iter-1 Q2 absorb).**
`dawidd6/action-download-artifact` must be pinned to a full commit SHA,
not `@v6`. Impl step resolves the latest release's SHA at PR-open time
and pins it. Alternative considered: `gh run download` via `gh api`
(official surface), rejected for v1 because branch-filter ergonomics
cost more code than a SHA-pinned third-party. Revisit at v3.6+.

**Comment failure is non-blocking.** `continue-on-error: true` +
`|| true` in the post-comment step means a permission issue on fork PRs
(secrets absent) or a transient `gh` error cannot red-check the PR.
Scorecard is an advisory surface.

### 3.8 Policy

`ao_kernel/defaults/policies/policy_scorecard.v1.json`:

```json
{
  "version": "v1",
  "enabled": true,
  "post_pr_comment": true,
  "regression_threshold": {
    "cost_usd_relative_pct": 20.0,
    "duration_ms_relative_pct": 30.0,
    "review_score_min_delta": -0.1
  },
  "fail_action": "warn"
}
```

**Policy scope clarification (Codex iter-1 Q6 absorb).**
`enabled` gates `compare` + comment posting only. The `emit` CLI
command (and the pytest plugin that writes the scorecard on
`pytest_sessionfinish`) always produces output regardless of the flag
— benchmark scorecard generation is decoupled from policy gating.
Rationale: scorecard JSON is raw CI artefact data; compare/comment is
the opinion layer.

Schema: `$id: urn:ao:policy-scorecard:v1` (Codex iter-1 Q7 —
consistent with `urn:ao:scorecard:v1`). File:
`policy-scorecard.schema.v1.json` — strict (`additionalProperties:
false` top-level + on `regression_threshold`).

---

## 4. Test pins

### 4.1 `test_scorecard_collector.py` (11 pins — +2 for canonical marker)

- Seeds fixture run_dirs with deterministic event timelines; asserts
  extraction maps per §3.3.
- Missing `workflow_completed` → status=fail.
- Missing `budget.cost_usd` → null.
- Missing `review-findings` capability artifact → `review_score=null`.
- Empty run_dir → `workflow_completed=false`, status=fail, durations null.
- Scenario id fallback to module basename.
- Multi-scenario run → multiple `BenchmarkResult` entries, sorted by
  scenario name.
- Env var `AO_SCORECARD_OUTPUT` honored + atomic write.
- Session exitstatus≠0 → scorecard still written (fail-open diagnostic).
- **NEW: Canonical marker enforcement** — duplicate
  `@pytest.mark.scorecard_primary` on same scenario → session-fail
  diagnostic; no scorecard written.
- **NEW: `cost_source` field always populated** — hard-coded
  `"mock_shim"` v1; schema accepts the field.

### 4.2 `test_scorecard_compare.py` (10 pins)

- Happy path: identical scorecards → regression=False, deltas≈0.
- Null baseline → all deltas null, regression=False.
- Duration regression >30% → regression=True on that entry.
- Cost regression >20% → regression=True.
- Review score drop >0.1 → regression=True.
- `fail_action=warn` policy → diff object carries `regression=True` but
  compare() return tuple signals "warn" (no exit code).
- `fail_action=block` policy → compare() signals "block" (CLI exit 1
  tested in §4.4).
- Pass→fail status_changed flagged independently.
- Missing scenario in head but present in baseline → flagged as
  `status_changed=True` + `regression=True` (scenario disappearance).
- Missing scenario in baseline but present in head → no regression (added).

### 4.3 `test_scorecard_render.py` (8 pins — +2 for sentinel + cost source)

- Happy empty diff → "No regressions" footer.
- Regression rendered with ⚠️ banner.
- Unicode arrows correct direction.
- Null values render as `—` dash, not "None".
- Missing baseline → "Baseline: _(not found)_" footer.
- PR number in footer when present.
- **NEW: HTML sentinel `<!-- ao-scorecard -->` on first line.**
- **NEW: Cost source surfaces in footer (`mock_shim` labelled clearly
  as "benchmark-only; not real billing").**

### 4.4 `test_scorecard_cli.py` (8 pins — +2 for post-comment subcommand)

- `emit` writes file at expected path.
- `emit` always produces output regardless of `enabled=false`.
- `compare` prints markdown to stdout; exit 0 on no regression.
- `compare` with regression + `fail_action=warn` → exit 0 + stderr warn line.
- `compare` with regression + `fail_action=block` → exit 1.
- `render` ignores policy; always exit 0.
- Missing baseline file handled gracefully.
- **NEW: `post-comment --sentinel X` finds existing comment with X +
  PATCHes (mocked `gh api` layer); POSTs if absent; exits 0 on either
  outcome and on upsert failure.**

### 4.5 `test_scorecard_schema.py` (3 pins)

- Draft202012Validator accepts example scorecard.
- Rejects unknown top-level key.
- Benchmark entry forward-extensible (unknown key accepted in `benchmarks[]`).

**Total: 40 pins** (collector 11 + compare 10 + render 8 + cli 8 + schema 3).
Up from v1's 34-pin estimate after iter-2 absorb of canonical marker,
sentinel-based sticky comment, and CLI/bundled split for `block`/`warn`.

---

## 5. Resolved design decisions (iter-1 + AGREE iter-2)

All v1 open questions have been resolved in-plan; this section records
the decisions for future reference.

1. **Collector =** pytest plugin + explicit `@scorecard_primary`
   marker + `benchmark_primary_sidecar` fixture. Not post-run CLI
   (run_dir discovery would be ambiguous on multi-test scenarios).

2. **Baseline fetch =** `dawidd6/action-download-artifact` pinned to
   a full commit SHA. `gh run download` considered; branch-filter
   ergonomics cost more code than a SHA pin. Revisit at v3.6+ if the
   third-party surface becomes problematic.

3. **Sticky comment =** HTML sentinel `<!-- ao-scorecard -->` on the
   first line of the rendered markdown + `ao-kernel scorecard
   post-comment --sentinel` CLI subcommand that lists existing
   comments via `gh api`, PATCHes if a sentinel-bearing comment is
   found, POSTs otherwise. Replaces the earlier `--edit-last`
   proposal.

4. **Trend window =** out of scope for v1; problem statement + title
   updated (§1 "Not in v1" block). Same `scorecard-*` artefact
   surface can grow trend display in v3.6+.

5. **`cost_consumed_usd` =** mock-shim drift signal is meaningful in
   v1. New `cost_source` schema field labels the source unambiguously
   so baselines from mock-shim are not misread as real billing;
   render footer surfaces the label explicitly.

6. **Policy `enabled` scope =** gates `compare` + comment posting
   only. `emit` is policy-agnostic and always produces output.
   Bundled default `enabled: true`, `fail_action: "warn"` (§2
   non-goal: CI never reds on scorecard regressions in v1).

7. **Schema `$id` namespace =** `urn:ao:scorecard:v1` (data) +
   `urn:ao:policy-scorecard:v1` (policy). Consistent with the
   existing `urn:ao:agent-adapter-contract:v1` family.

---

## 6. Rollout

1. Plan-time iter → AGREE.
2. Impl: module + schema + policy + CLI + tests + CI workflow.
3. Local fast-mode benchmark run → validate scorecard shape.
4. Manual `ao-kernel scorecard compare` round-trip with two hand-edited
   scorecards → validate render + exit codes.
5. Post-impl Codex review gate.
6. PR open against main → CI must generate scorecard artifact (first run
   will have no baseline; comment states so).
7. Merge → main-push uploads `scorecard-main` baseline.
8. First subsequent PR will show first real diff.
9. v3.5.0 release tag + CHANGELOG finalize.
