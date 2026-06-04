# Production benchmark suite + cross-PR regression detection (V5 Epic 7 E-7-1)

> Slice #883. End-to-end runbook binding the existing pieces into one
> production benchmark suite with cross-PR regression detection:
> **scenario catalog → scorecard generation → regression gate → baseline
> update**. Beta; not an SLA; `enforcement_mode: advisory` by default. The
> three guard flags remain `const false`.

## Components (all already in-repo)

| Piece | Path | Role |
|---|---|---|
| Scenario catalog | `docs/performance/performance-scenario-catalog.v1.json` | declares the suite's scenarios |
| Benchmark scenarios | `tests/benchmarks/test_*.py` | run each scenario, emit metrics |
| Scorecard | `benchmark_scorecard.v1.json` | per-run results (duration_ms, status, …) |
| Baseline | `docs/performance/baseline.v1.json` | reference values to compare against |
| Threshold policy | `docs/performance/performance-regression-threshold.v1.json` | allowed drift |
| Regression gate | `scripts/regression_gate.py` (E-7x #806) | head-vs-baseline comparison |

## 1. Run the suite (generate a scorecard)

```bash
# Fast scenarios (governed_review, governed_bugfix) — deterministic, mock transport:
pytest tests/benchmarks -m scorecard_primary -q
# The scorecard is written to benchmark_scorecard.v1.json (scenario, duration_ms,
# status, review_score, workflow_completed).
```

`full_mode_smoke` is advisory (`may_skip_on_prereq_miss: true`) and not part of
the policy-enforced primary set.

## 2. Cross-PR regression detection

```bash
python scripts/regression_gate.py \
  --head benchmark_scorecard.v1.json \
  --baseline docs/performance/baseline.v1.json \
  --threshold docs/performance/performance-regression-threshold.v1.json \
  --out regression-comparison-result.v1.json
```

The gate compares each primary scenario's `duration_ms` (and other primary
metrics) against the baseline, applies the threshold policy, and emits a
verdict. In `advisory` mode a regression is reported but does not hard-fail CI;
promotion to `manual_block` / `ci_block_candidate` is a future enforcement
decision (not flipped here).

## 3. Update the baseline (operator, deliberate)

Only update the baseline when a duration change is **intended and explained**
(e.g. a known algorithmic change). Never silently overwrite to make a
regression "disappear":

```bash
cp benchmark_scorecard.v1.json docs/performance/baseline.v1.json
# Commit with a rationale: WHY the new numbers are the correct reference.
```

## 4. Variance discipline (honest baseline)

Repo baselines are **single-run candidates** (see `policy_disclaimer`). A single
slow CI runner can show false regression. Before treating a reported regression
as real: re-run the suite 2–3× and confirm it persists. Statistical p95/median
aggregation across many runs is acknowledged future work, NOT claimed here.

## 5. Cross-PR detection in practice

- Each PR's CI run can generate a scorecard and compare to `main`'s baseline.
- A persistent duration increase beyond threshold = a real regression to
  investigate (profiling, not baseline-bumping).
- A persistent decrease = an opportunity to tighten the baseline (after
  confirming it's not a measurement artifact).

## 6. What this slice does NOT do

- Does NOT change the benchmark scenarios or the regression gate logic
  (binds the existing pieces into one runbook + integration invariant).
- Does NOT promote enforcement from advisory to blocking (future decision).
- Does NOT claim an SLA or production readiness; does NOT flip a guard flag.

## 7. Cross-references

- Baseline + threshold policy: `docs/performance/README.md` (E-7 baseline)
- Regression gate CLI: `scripts/regression_gate.py` (E-7x #806)
