# GP-5.3e - Repo-Intelligence Workflow Building-Block Decision

**Status:** Closeout candidate
**Date:** 2026-04-24
**Authority:** `origin/main` at `7f937ec`
**Tracker:** [#424](https://github.com/Halildeu/ao-kernel/issues/424)
**Slice issue:** [#439](https://github.com/Halildeu/ao-kernel/issues/439)
**Branch:** `codex/gp5-3e-workflow-building-block`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gp5-3e`
**Decision:** `promote_beta_explicit_handoff_building_block`

## Decision

Repo-intelligence read-only retrieval may be used as a GP-5 workflow building
block only through explicit operator-visible handoff.

The allowed handoff is:

1. operator runs `repo scan`, `repo index`, and `repo query`;
2. `repo query --output markdown` emits a bounded context pack to stdout;
3. operator supplies that Markdown as visible input to a later governed
   workflow rehearsal.

This is a beta building-block promotion, not a production support widening.

## Why This Is Allowed

The preceding slices closed the minimum guard set:

1. `GP-5.3a` pins retrieval evidence quality: source artifact hashes,
   `min_similarity`, current-only candidates, snippet hash checks, stale-source
   diagnostics, path-escape exclusion, and read-only CLI behavior.
2. `GP-5.3b` pins the handoff mode as stdout-only Markdown supplied by the
   operator as explicit agent input.
3. `GP-5.3c` proves current workflows and `context_compiler` do not ingest
   repo-intelligence context automatically.
4. `GP-5.3d` proves repo-intelligence is not exposed as an MCP tool and does
   not create root authority exports or `.ao/context/repo_export_plan.json`.

Together, these make repo-intelligence usable as controlled input for a future
read-only workflow rehearsal without adding hidden side effects.

## What Is Still Not Supported

1. No automatic prompt injection.
2. No MCP repo-intelligence tool.
3. No root authority export.
4. No `context_compiler` auto-feed.
5. No workflow schema/runtime consumption.
6. No production semantic-correctness guarantee.
7. No protected real-adapter or live-write support widening.

## Evidence Required For The Next Slice

`GP-5.4a` may use this building block only if the rehearsal records:

1. exact repo-intelligence commands run;
2. source artifact hashes and vector namespace;
3. the rendered Markdown handoff bytes or digest;
4. workflow run id and adapter identity;
5. proof that the context was operator-provided input, not hidden runtime
   injection;
6. evidence timeline entries for workflow start, adapter invocation, artifacts,
   and final state;
7. a no-write/no-remote-side-effect assertion.

If any of these are missing, the rehearsal is `blocked` or `incomplete`, not
green.

## Support Boundary Impact

Support boundary changes only at the beta-building-block wording level:

1. `repo query --output markdown` remains beta read-only.
2. It may be referenced as an explicit input source for future GP-5 read-only
   workflow rehearsals.
3. It does not become production-certified workflow integration.

## RI-5 Interface

`RI-5` still owns explicit root/context export. `GP-5.3e` does not consume
`.ao/context/repo_export_plan.json`, does not require it, and does not produce
it. Future root-export work must remain a separate RI-5 slice.

## Next Slice

`GP-5.4a` should implement the first governed read-only workflow rehearsal
using the explicit handoff boundary above. `GP-5.1b` remains blocked until the
protected environment and credential handle are attested.
