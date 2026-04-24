# GP-5.7b - Full Production Rehearsal Execution Gate

**Status:** Active implementation slice
**Date:** 2026-04-24
**Issue:** [#451](https://github.com/Halildeu/ao-kernel/issues/451)
**Branch:** `codex/gp5-7b-full-rehearsal-gate`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gp5-7b`
**Authority:** `origin/main` at `0a3c2f9` after `GP-5.7a`
**Support impact:** no support widening

## Purpose

`GP-5.7b` is the first executable full production rehearsal gate, but it is not
a production support claim. It aggregates schema-backed reports from the
previous gates and fails closed unless the complete chain has enough evidence:

1. `GP-5.7a` contract report is ready;
2. at least three clean chains pass;
3. at least one failure chain proves fail-closed behavior;
4. every subreport keeps `support_widening=false`;
5. no production platform claim is emitted.

## Inputs

The gate consumes a matrix JSON file:

```json
{
  "contract_report": "contract.json",
  "clean_runs": [
    {
      "run_id": "clean-1",
      "target_kind": "sandbox_repo",
      "read_only_report": "clean-1-read-only.json",
      "controlled_patch_report": "clean-1-patch.json",
      "disposable_pr_report": "clean-1-pr.json"
    }
  ],
  "failure_runs": [
    {
      "scenario_id": "fail-closed-non-disposable-pr-repo",
      "trigger": "non_disposable_pr_repo",
      "report_kind": "disposable_pr_write",
      "report_path": "fail-pr.json"
    }
  ]
}
```

Relative report paths resolve from the matrix file directory.

## Command

```bash
python3 scripts/gp5_full_production_rehearsal.py \
  --matrix-file /tmp/gp57b-matrix.json \
  --output json \
  --report-path /tmp/gp57b-report.json
```

## Output Contract

The output artifact is
`gp5_full_production_rehearsal_report`, validated by
`ao_kernel/defaults/schemas/gp5-full-production-rehearsal-report.schema.v1.json`.

Pass requires:

1. `overall_status=pass`;
2. `decision=pass_full_production_rehearsal_no_support_widening`;
3. `support_widening=false`;
4. `production_platform_claim=false`;
5. `observed_clean_passes >= 3`;
6. `observed_failure_blocks >= 1`.

Blocked output remains schema-valid and includes `blocked_reason`.

## Non-Goals

1. no live remote PR execution by default;
2. no protected real-adapter invocation;
3. no automatic repo-intelligence root export;
4. no support boundary widening;
5. no production platform claim.

## Validation

Required local checks:

```bash
python3 -m pytest -q tests/test_gp5_full_production_rehearsal.py
python3 -m pytest -q \
  tests/test_gp5_full_production_rehearsal.py \
  tests/test_gp5_full_production_rehearsal_contract.py
python3 -m ruff check \
  scripts/gp5_full_production_rehearsal.py \
  tests/test_gp5_full_production_rehearsal.py
python3 scripts/packaging_smoke.py
```

## Decision

Until a later GP-5 closeout explicitly changes the support boundary, this gate
can only produce `pass_full_production_rehearsal_no_support_widening` or
`blocked_full_production_rehearsal_no_support_widening`.
