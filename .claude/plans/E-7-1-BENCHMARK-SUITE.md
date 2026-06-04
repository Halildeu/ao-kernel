# E-7-1 — Production benchmark suite + cross-PR regression detection

> V5 Epic 7. Slice #883. Binds existing pieces; guard-flag-independent.

## Delivered
- `docs/performance/BENCHMARK-SUITE.md` — end-to-end runbook: scenario catalog
  → scorecard generation → regression gate (cross-PR) → baseline update +
  variance discipline.
- `tests/test_epic_7_1_benchmark_suite.py` — 7 integration invariants verifying
  the pieces are mutually consistent (catalog↔test modules↔baseline↔gate).

## Existing pieces bound (all in-repo)
- Scenario catalog + 3 benchmark scenarios (governed_review/bugfix/full_mode)
- benchmark_scorecard.v1.json + baseline.v1.json + threshold policy
- scripts/regression_gate.py (E-7x #806) cross-PR comparison

## Boundaries
- Does NOT change scenarios or gate logic (binds + integration-tests them).
- Does NOT promote enforcement advisory→blocking (future decision).
- No SLA claim; no guard flag.
