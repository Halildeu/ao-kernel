# GP-3.2 — Claude Code CLI Governed Workflow Repeatability

**Status:** Completed on branch, pending PR merge
**Date:** 2026-04-24
**Tracker:** [#390](https://github.com/Halildeu/ao-kernel/issues/390)
**Parent tracker:** [#386](https://github.com/Halildeu/ao-kernel/issues/386)
**Lane:** `claude-code-cli` read-only governed workflow

## Purpose

Prove that the `claude-code-cli` governed read-only workflow path is not only a
single successful smoke. This gate checks whether repeated independent runs can
complete with the same required evidence shape.

This is still not a production-certified support claim. Repeatability is one
required input for later failure-mode, evidence completeness, runbook, docs, CI,
and support-boundary gates.

## Scope

Included:

1. Three independent governed workflow smoke runs.
2. Clean temporary workspace per run.
3. `--cleanup` enabled for each run.
4. Preflight execution through the workflow smoke helper.
5. Verification of final state, evidence events, `review_findings` artifact,
   redacted adapter log, and schema validity.

Excluded:

1. No runtime code change.
2. No helper contract change.
3. No version bump, tag, or publish.
4. No production-certified support promotion.
5. No `gh-cli-pr` live-write promotion.

## Command

```bash
for i in 1 2 3; do
  python3 scripts/claude_code_cli_workflow_smoke.py \
    --output json \
    --timeout-seconds 60 \
    --cleanup
done
```

## Live Evidence

| Run | Exit code | `overall_status` | `preflight_status` | Final state | Run id |
|---|---:|---|---|---|---|
| 1 | `0` | `pass` | `pass` | `completed` | `41127974-7455-4581-a2cc-cdda3f707a83` |
| 2 | `0` | `pass` | `pass` | `completed` | `6aa8d377-8519-4579-91ef-f282b3549416` |
| 3 | `0` | `pass` | `pass` | `completed` | `9ba81196-febd-4a53-9492-a6cbcb1a98b6` |

Each run reported the same required check set:

1. `final_state`: `pass`
2. `evidence_events`: `pass`
3. `review_findings_artifact`: `pass`
4. `adapter_log`: `pass`
5. `review_findings_schema`: `pass`

No stderr output was produced by any run.

## Decision

`claude-code-cli` governed read-only workflow repeatability is sufficient to
advance to `GP-3.3` failure-mode matrix work.

This decision is narrow:

1. It proves three consecutive smoke runs in this operator environment.
2. It does not prove failure behavior.
3. It does not prove supportability for all operators.
4. It does not widen the stable support boundary.

## Support Boundary Impact

No support boundary widening.

Current support tier remains:

1. `claude-code-cli`: `Beta (operator-managed)`
2. production-certified read-only claim: not yet granted
3. stable shipped baseline: unchanged

## Next Gate

`GP-3.3` should classify failure modes before any promotion decision:

1. missing binary
2. auth missing
3. prompt denied
4. timeout
5. malformed output
6. policy denied

The lane must remain beta if these failures are not fail-closed and
operator-actionable.
