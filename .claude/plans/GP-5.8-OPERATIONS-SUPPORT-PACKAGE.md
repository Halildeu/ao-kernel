# GP-5.8 - Operations Support Package

**Status:** Active implementation slice
**Date:** 2026-04-24
**Issue:** [#453](https://github.com/Halildeu/ao-kernel/issues/453)
**Branch:** `codex/gp5-8-ops-support-package`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gp5-8`
**Authority:** `origin/main` at `fef3c23` after `GP-5.7b`
**Support impact:** no support widening
**release_gate_impact=none**

## Purpose

`GP-5.8` makes the GP-5 chain operable before any broader platform claim is
considered. It is not a promotion slice. It adds a schema-backed package report
that proves operator runbooks, known-bug interpretation, support-boundary
wording, and branch protection / required checks implications are visible.

## Scope

1. incident runbooks for adapter, repo-intelligence, vector backend,
   write-side, PR rollback, packaging, and GP-5.7b aggregation failures;
2. known-bugs registry interpretation for stable blockers vs beta promotion
   blockers;
3. support-boundary wording for GP-5.8 and the unchanged stable boundary;
4. branch protection / required checks decision note;
5. `gp5_operations_support_package` report and tests.

## Branch Protection / Required Checks Decision

The current required checks already include lint, typecheck, coverage, Python
test matrix, packaging-smoke, benchmark-fast, and scorecard. GP-5.8 does not
add a new always-on CI job and does not change branch protection. The new
script is covered by unit tests and remains an operator/readiness gate.

Decision: keep branch protection unchanged for this slice. Revisit required
checks only if GP-5.9 promotes a broader production claim or turns GP-5.8 into
a release-blocking required check.

## Command

```bash
python3 scripts/gp5_operations_support_package.py \
  --output json \
  --report-path /tmp/gp58-ops-support-package.json
```

## DoD

1. report validates against
   `gp5-operations-support-package.schema.v1.json`;
2. `support_widening=false`;
3. `production_platform_claim=false`;
4. runbook coverage for all GP-5 operational classes is present;
5. known-bugs registry states stable blocker status and beta promotion
   blockers;
6. GP-5.9 remains the first possible production claim decision gate.

## Decision

`GP-5.8` can only close as
`operations_package_ready_no_support_widening` or
`operations_package_blocked_no_support_widening`. It cannot promote real
adapters, live PR writes, repo-intelligence auto-feed, or write-side runtime
support.
