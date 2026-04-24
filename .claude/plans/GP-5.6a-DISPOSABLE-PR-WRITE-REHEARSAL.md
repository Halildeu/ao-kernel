# GP-5.6a - Disposable PR Write Rehearsal

**Status:** Completed on `main`
**Date:** 2026-04-24
**Issue:** [#447](https://github.com/Halildeu/ao-kernel/issues/447)
**Tracker:** [#424](https://github.com/Halildeu/ao-kernel/issues/424)
**Branch:** `codex/gp5-6a-disposable-pr-rehearsal` (merged)
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gp5-6a` (removed after merge)
**Authority:** `origin/main` at `d1097aa`

## Scope

GP-5.6a adds a narrow remote side-effect rehearsal gate for `gh-cli-pr` live
write behavior. It does not promote production remote PR support.

The gate requires a passing GP-5.5b controlled local patch/test report before
it can attempt any remote write. With explicit live-write opt-in, it creates an
ephemeral branch in a disposable sandbox repository, seeds one deterministic
evidence file, runs the existing `gh-cli-pr` live-write smoke to create, verify,
and close a draft PR, verifies the PR is closed, deletes the remote branch, and
verifies branch deletion.

## Non-Goals

1. No production repository PR creation.
2. No arbitrary repository support.
3. No support widening for full remote PR opening.
4. No runtime workflow wiring from controlled patch output to `gh-cli-pr`.
5. No `--keep-live-write-pr-open` promotion path.

## Implemented Artifacts

1. `scripts/gp5_disposable_pr_write_rehearsal.py`
2. `ao_kernel/defaults/schemas/gp5-disposable-pr-write-rehearsal-report.schema.v1.json`
3. `tests/test_gp5_disposable_pr_write_rehearsal.py`

## Required Commands

First generate the GP-5.5b local precondition report:

```bash
python3 scripts/gp5_controlled_patch_test_rehearsal.py \
  --approve-apply \
  --output json \
  --report-path /tmp/gp55b-local-patch-report.json
```

Blocked safety path without remote writes:

```bash
python3 scripts/gp5_disposable_pr_write_rehearsal.py \
  --local-patch-report /tmp/gp55b-local-patch-report.json \
  --repo Halildeu/ao-kernel-sandbox \
  --base main \
  --output json \
  --report-path /tmp/gp56a-blocked.json
```

Sandbox live-write path:

```bash
python3 scripts/gp5_disposable_pr_write_rehearsal.py \
  --local-patch-report /tmp/gp55b-local-patch-report.json \
  --allow-live-write \
  --repo Halildeu/ao-kernel-sandbox \
  --base main \
  --output json \
  --report-path /tmp/gp56a-disposable-pr-write-report.json
```

## Pass Criteria

1. The GP-5.5b local precondition report is schema-valid and `overall_status=pass`.
2. The target repo satisfies the disposable keyword guard, default `sandbox`.
3. Remote writes require explicit `--allow-live-write`.
4. Head branch starts with `smoke/gp56a-`.
5. The remote branch is created and seeded with one evidence file.
6. `gh-cli-pr` live-write smoke creates a draft PR, verifies it open, and
   closes it.
7. GP-5.6a verifies the PR final state is `CLOSED`.
8. GP-5.6a deletes the remote branch and verifies it no longer resolves.
9. The report validates against
   `gp5-disposable-pr-write-rehearsal-report.schema.v1.json`.
10. `support_widening=false`, `production_remote_pr_support=false`, and
    `arbitrary_repo_support=false`.

## Decision

Closeout decision:
`pass_disposable_pr_write_rehearsal_no_support_widening`.

This proves only disposable sandbox create/verify/close/delete discipline. It
does not make `gh-cli-pr` full remote PR opening a stable shipped support
surface.
