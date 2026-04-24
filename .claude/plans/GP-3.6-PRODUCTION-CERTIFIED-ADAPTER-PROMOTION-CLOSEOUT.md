# GP-3.6 — Production-Certified Adapter Promotion Closeout

**Status:** Completed decision
**Date:** 2026-04-24
**Tracker:** [#398](https://github.com/Halildeu/ao-kernel/issues/398)
**Parent tracker:** [#386](https://github.com/Halildeu/ao-kernel/issues/386)
**Program:** `GP-3` production-certified adapter promotion

## Purpose

Close the `GP-3` promotion program after evaluating the first real-adapter
candidate lane, `claude-code-cli` governed read-only workflow.

## Final Verdict

**Decision:** `close_keep_operator_beta`

`GP-3` is complete. It does not widen the stable shipped support boundary and
does not create a production-certified real-adapter support claim.

The `claude-code-cli` lane remains:

1. useful and evidence-backed;
2. helper-smokeable and governed-workflow-smokeable;
3. fail-closed for known negative paths;
4. still `Beta (operator-managed)`;
5. not production-certified read-only.

## Evidence Summary

| Slice | Result |
|---|---|
| `GP-3.1` prerequisite truth refresh | preflight and governed workflow smoke passed |
| `GP-3.2` repeatability | three independent governed workflow smoke runs passed |
| `GP-3.3` failure-mode matrix | helper/workflow failure classes pinned fail-closed |
| `GP-3.4` evidence completeness | event order, artifact semantics, schema, and redaction checks recorded |
| `GP-3.5` support-boundary decision | verdict `keep_operator_beta` |

Fresh closeout evidence:

1. `python3 scripts/claude_code_cli_smoke.py --output json --timeout-seconds 30`
   returned `overall_status="pass"`.
2. `python3 scripts/claude_code_cli_workflow_smoke.py --output json --timeout-seconds 60 --cleanup`
   returned `overall_status="pass"` and final state `completed`.
3. Governed workflow run id:
   `58939f02-2efc-4d0d-ac55-b3418fcbe7ae`.
4. Required evidence checks passed:
   `evidence_events`, `event_order`, `review_findings_artifact`,
   `adapter_log`, `review_findings_schema`, and
   `review_findings_contents`.

## Why The Program Closes Without Promotion

`GP-3` proved that the lane is not fake-green. It did not prove that ao-kernel
can own production-certified support for the lane.

The blocking gaps are:

1. external `claude` PATH binary remains outside the package;
2. local Claude Code session auth and prompt access remain operator state;
3. `KB-001` remains open: auth status can be green while prompt access is
   blocked;
4. `KB-002` remains open: long-lived token fallback is not a reliable primary
   recovery path;
5. no CI-managed live `claude-code-cli` governed workflow gate exists;
6. adapter-path `cost_usd` / token usage completeness remains an explicit
   non-claim.

## Support Boundary Impact

No support widening.

Current supported boundary after closeout:

1. stable shipped baseline remains the narrow `v4.0.0` support set;
2. `claude-code-cli` remains `Beta (operator-managed)`;
3. `gh-cli-pr` remains `Beta (operator-managed)` for preflight/readiness and
   deferred for full remote PR opening;
4. `PRJ-KERNEL-API` write-side actions remain `Beta (operator-managed)`;
5. general-purpose production coding automation platform claim remains out of
   scope.

## Allowed Next Work

New work must not reopen `GP-3` implicitly.

Allowed next lanes:

1. stable maintenance / evidence refresh slices;
2. a new explicit CI-managed live-adapter gate design if production-certified
   real-adapter support is still desired;
3. separate support-lane programs for another adapter only if they start with
   scope freeze and support-boundary criteria.

Disallowed inference:

1. A passing local `claude-code-cli` smoke does not widen support.
2. A runbook or manifest does not widen support.
3. GP-3 closeout does not make ao-kernel a general-purpose production coding
   automation platform.

## Closeout Action

Close parent tracker [#386](https://github.com/Halildeu/ao-kernel/issues/386)
after the closeout PR merges.
