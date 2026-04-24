# GP-5.7a - Full Production Rehearsal Contract

**Status:** Active contract slice / no support widening
**Date:** 2026-04-24
**Issue:** [#449](https://github.com/Halildeu/ao-kernel/issues/449)
**Tracker:** [#424](https://github.com/Halildeu/ao-kernel/issues/424)
**Branch:** `codex/gp5-7a-full-rehearsal-contract`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gp5-7a`
**Authority:** `origin/main` at `d1097aa`

## Scope

GP-5.7a turns the broad GP-5.7 "full production rehearsal" goal into an
executable contract. It does not run the full rehearsal and does not widen the
support boundary.

The contract defines the minimum evidence required before GP-5.7b can execute
the full chain:

```text
issue/task
-> repo scan/index/query
-> explicit context handoff
-> adapter reasoning
-> patch plan
-> controlled patch
-> tests
-> disposable PR rehearsal
-> rollback/closeout
```

## Implemented Artifacts

1. `ao_kernel/defaults/schemas/gp5-full-production-rehearsal-contract.schema.v1.json`
2. `tests/test_gp5_full_production_rehearsal_contract.py`
3. GP-5 roadmap/status/runbook/support-boundary wording for the new gate.

## Contract Requirements

The schema-backed GP-5.7 contract must require:

1. `support_widening=false`;
2. `production_platform_claim=false`;
3. protected real-adapter promotion still gated on GP-5.1b attestation;
4. precondition references for GP-5.3e, GP-5.4a, GP-5.5b, and GP-5.6a;
5. exactly the expected target chain and no hidden extra step;
6. at least three clean rehearsals on disposable/sandbox/supported candidate
   targets;
7. at least one fail-closed rehearsal scenario;
8. explicit repo-intelligence handoff, not hidden prompt injection;
9. controlled patch/test rollback evidence;
10. disposable PR rehearsal and remote rollback evidence;
11. adapter identity and usage/cost evidence or an explicit unavailable reason.

## Non-Goals

1. No live production support widening.
2. No arbitrary user-repository write support.
3. No hidden repo-intelligence auto-injection, MCP export, or root export.
4. No protected live adapter execution in this contract slice.
5. No promotion of `claude-code-cli` beyond Beta/operator-managed.
6. No promotion of `gh-cli-pr` beyond bounded rehearsal evidence.

## Decision

Expected closeout decision:
`contract_ready_no_support_widening`.

This slice can only unblock GP-5.7b execution planning. It cannot make
`ao-kernel` a general-purpose production coding automation platform by itself.

## GP-5.7b Entry Criteria

GP-5.7b may start only after this slice lands on `origin/main` and the next
operator can build a contract artifact that validates against
`gp5-full-production-rehearsal-contract.schema.v1.json`.

GP-5.7b must then execute, not merely describe:

1. three clean rehearsals;
2. one failure rehearsal;
3. schema-backed reports for each run;
4. runbook-ready rollback/closeout evidence;
5. a final decision of either `promote_limited_platform_beta`,
   `keep_narrow_stable_runtime`, or `defer_support_widening`.
