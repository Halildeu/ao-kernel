# GP-5.5a — Controlled Patch/Test Design

**Issue:** [#443](https://github.com/Halildeu/ao-kernel/issues/443)
**Parent tracker:** [#424](https://github.com/Halildeu/ao-kernel/issues/424)
**Status:** closeout candidate

## Purpose

Define the write-side contract for the first controlled patch/test lane before
any GP-5 runtime patch rehearsal or support widening. This slice does not add a
new write-capable workflow. It records what future GP-5.5 runtime work must
prove.

## Scope Boundary

Included:

1. schema-backed `gp5_controlled_patch_test_contract`;
2. required disposable or dedicated worktree boundary;
3. path-scoped write ownership requirement;
4. diff preview and explicit apply decision requirement;
5. explainable targeted test selection plus full-gate fallback requirement;
6. rollback, cleanup, idempotency, and incident/runbook evidence requirement.

Excluded:

1. runtime patch application support widening;
2. live remote PR creation;
3. real-adapter live-write support;
4. patching the operator's active `main` worktree;
5. production support claim.

## Decision

`design_contract_ready_no_runtime_write_support`

The GP-5 controlled patch/test lane is ready for a future rehearsal design
gate, but not ready for support widening. The next gate is `GP-5.5b`, which
must execute the contract in a disposable or dedicated worktree and produce
real rollback/test evidence.

## Existing Runtime Facts

The repository already has lower-level patch primitives and path-scoped write
ownership enforcement:

1. `patch_preview` is claim-free and does not mutate workspace files.
2. `patch_apply` and `patch_rollback` acquire path-scoped claims when
   coordination is enabled.
3. rollback primitives can use reverse-diff artifacts.

Those facts are not enough to claim a GP-5 general-purpose write lane. GP-5
needs end-to-end target worktree isolation, explicit apply approval,
test-selection evidence, rollback verification, and cleanup evidence in one
controlled rehearsal.

## Evidence Contract

Schema:

```text
ao_kernel/defaults/schemas/gp5-controlled-patch-test-contract.schema.v1.json
```

Required facts:

1. `support_widening=false`;
2. `runtime_patch_application_enabled=false`;
3. `remote_side_effects_allowed=false`;
4. `active_main_worktree_allowed=false`;
5. target worktree is `disposable_worktree` or `dedicated_worktree`;
6. path-scoped claims are required;
7. diff preview artifact is required before apply;
8. explicit operator apply decision is required;
9. targeted tests are explainable and have full-gate fallback;
10. reverse-diff rollback, rollback verification, cleanup, and idempotency are
    required.

## Runbook Skeleton

Future GP-5.5b cannot close unless the operator can answer:

1. Which disposable/dedicated worktree was patched?
2. Which path ownership claims were acquired and released?
3. Which diff preview artifact was approved?
4. Which targeted tests ran, and what full-gate fallback exists?
5. Which rollback artifact was produced and verified?
6. Was cleanup completed without touching the operator's active `main`
   worktree?

## Next Gate

`GP-5.5b` controlled local patch/test rehearsal.

`GP-5.6a` remains later and must not start until GP-5.5 produces local
rollback evidence. `GP-5.1b` remains blocked until protected live-adapter
environment/credential attestation exists.
