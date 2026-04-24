# GP-2 — Deferred Support-Lane Backlog Reprioritization Closeout

**Status:** Completed
**Date:** 2026-04-24
**Tracker:** [#329](https://github.com/Halildeu/ao-kernel/issues/329)
**Parent context:** post-`v4.0.0` stable support-lane cleanup

## Verdict

`GP-2` is complete. The deferred support-lane backlog was reprioritized,
evidence gaps were made explicit, and the selected post-stable lanes were
closed without widening the stable shipped support boundary.

Final outcome:

1. `claude-code-cli` remains `Beta (operator-managed)`.
2. `gh-cli-pr` preflight/live-write readiness remains `Beta (operator-managed)`.
3. `gh-cli-pr` full remote PR opening is not stable shipped support.
4. `bug_fix_flow` release closure remains deferred.
5. Adapter-path `cost_usd` reconcile remains deferred as a public support claim.
6. General-purpose production platform claim remains out of scope until a
   separate promotion program supplies repeatable adapter/write-side evidence.

## Completed Slices

| Slice | Issue | Result |
|---|---|---|
| `GP-2.1` evidence-delta map | [#331](https://github.com/Halildeu/ao-kernel/issues/331) | deferred lane order recorded |
| `GP-2.2` `cost_usd` reconcile completeness | [#333](https://github.com/Halildeu/ao-kernel/issues/333) | no runtime patch required; claim remains deferred |
| `GP-2.3` post-stable entry decision | [#361](https://github.com/Halildeu/ao-kernel/issues/361) | first certification lane selected |
| `GP-2.4` `claude-code-cli` read-only certification | [#363](https://github.com/Halildeu/ao-kernel/issues/363) | final verdict `operator_managed_beta_keep` |
| `GP-2.5` `gh-cli-pr` rollback contract | [#373](https://github.com/Halildeu/ao-kernel/issues/373) | contract recorded |
| `GP-2.5a` sandbox rehearsal | [#375](https://github.com/Halildeu/ao-kernel/issues/375) | verdict `rehearsal_pass_keep_beta` |

## Evidence Summary

`claude-code-cli`:

1. helper preflight, governed workflow smoke, and failure-mode matrix were
   recorded under `GP-2.4`;
2. `auth_status` and `prompt_access` both must pass for operator-managed use;
3. the final decision did not promote the lane to production-certified read-only.

`gh-cli-pr`:

1. side-effect-safe preflight passed;
2. fail-closed guard for same `--head` / `--base` passed;
3. disposable sandbox live-write create -> verify -> rollback passed against
   `Halildeu/ao-kernel-sandbox`;
4. created PR `https://github.com/Halildeu/ao-kernel-sandbox/pull/1` ended
   `CLOSED`;
5. ephemeral head branch cleanup was verified;
6. repo override helper regression was fixed and pinned.

## Support Boundary Decision

No stable support widening is granted by `GP-2`.

Reason:

1. a single sandbox rehearsal proves the guard/rollback path works, but does
   not prove production-grade remote PR opening across repositories;
2. `gh-cli-pr` and `claude-code-cli` still depend on operator-managed external
   PATH binaries and auth state;
3. the shipped stable baseline remains intentionally narrow and already live as
   `v4.0.0`;
4. support widening requires its own promotion decision PR, docs parity, CI
   evidence, repeatable smoke, and rollback/runbook coverage.

## Next Allowed Paths

After `GP-2`, there is no active support-widening runtime slice.

Allowed next paths:

1. **Maintenance path:** keep `v4.0.0` stable baseline narrow and only fix bugs
   under normal patch-release discipline.
2. **Promotion path:** open a new promotion program, likely `GP-3`, for one
   lane at a time.
3. **Do not do:** silently widen `gh-cli-pr`, `claude-code-cli`, `bug_fix_flow`,
   or extension surfaces based only on inventory presence or one-off smoke.

## Closeout Criteria

`GP-2` closes when:

1. this decision record is merged;
2. `.claude/plans/GP-2-DEFERRED-SUPPORT-LANES-REPRIORITIZATION.md` is marked
   completed;
3. `.claude/plans/POST-BETA-CORRECTNESS-EXPANSION-STATUS.md` no longer lists an
   active GP-2 gate;
4. issue [#329](https://github.com/Halildeu/ao-kernel/issues/329) is closed;
5. support boundary docs still say no automatic stable widening occurred.
