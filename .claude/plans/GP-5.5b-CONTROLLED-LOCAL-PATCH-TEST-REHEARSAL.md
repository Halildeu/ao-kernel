# GP-5.5b — Controlled Local Patch/Test Rehearsal

**Issue:** [#445](https://github.com/Halildeu/ao-kernel/issues/445)
**Parent tracker:** [#424](https://github.com/Halildeu/ao-kernel/issues/424)
**Status:** closeout candidate

## Purpose

Execute the GP-5.5a controlled patch/test contract in a disposable local
worktree and produce real evidence for preview, explicit apply approval,
path-scoped ownership, targeted tests, rollback, idempotency, and cleanup.

This slice does not promote production write support. It proves the local
mechanics required before GP-5.6 can attempt any remote PR rehearsal.

## Scope Boundary

Included:

1. schema-backed `gp5_controlled_patch_test_rehearsal_report`;
2. `scripts/gp5_controlled_patch_test_rehearsal.py`;
3. disposable detached git worktree created from the current checkout `HEAD`;
4. deterministic patch preview and explicit `--approve-apply` boundary;
5. path-scoped claim acquire/release around apply and rollback;
6. targeted verification command and full-gate fallback record;
7. reverse-diff rollback, idempotency verification, and cleanup evidence.

Excluded:

1. active `main` worktree patching;
2. production runtime patch support widening;
3. live remote PR creation;
4. real-adapter live-write support;
5. arbitrary repository patch generation.

## Decision

`pass_controlled_local_patch_test_rehearsal_no_support_widening`

The GP-5 controlled patch/test lane has one local disposable-worktree
rehearsal command. It is sufficient to unblock GP-5.6a disposable PR rehearsal
planning, but not sufficient to claim general-purpose production write support.

## Evidence Contract

Schema:

```text
ao_kernel/defaults/schemas/gp5-controlled-patch-test-rehearsal-report.schema.v1.json
```

Command:

```bash
python3 scripts/gp5_controlled_patch_test_rehearsal.py --approve-apply --output json
```

The report must carry:

1. `support_widening=false`;
2. `runtime_patch_support_widening=false`;
3. `remote_side_effects_allowed=false`;
4. `active_main_worktree_touched=false`;
5. disposable worktree path and dirty-state preflight;
6. diff preview artifact and explicit apply decision artifact;
7. path-scoped apply and rollback claim ids;
8. targeted test command plus full-gate fallback command;
9. rollback verification and rollback idempotency;
10. cleanup evidence.

## No-Approval Boundary

Without `--approve-apply`, the command exits non-zero with a schema-valid
`blocked` report after preview and before write ownership / patch apply. This
keeps the explicit approval gate testable.

## Next Gate

`GP-5.6a` disposable PR write rehearsal.

That gate remains sandbox-only and must not start without using the GP-5.5b
rollback evidence as its local precondition. `GP-5.1b` remains blocked until
protected live-adapter environment/credential attestation exists.
