# GP-3 — Production-Certified Adapter Promotion Roadmap

**Status:** Completed program, final verdict `close_keep_operator_beta`
**Date:** 2026-04-24
**Tracker:** [#386](https://github.com/Halildeu/ao-kernel/issues/386)
**Parent context:** `v4.0.0` narrow stable live + `GP-2` closeout +
`SM-1..SM-4` stable maintenance baseline

## Purpose

`GP-3` was the first post-stable promotion program for moving one real adapter
lane from `Beta (operator-managed)` toward a production-certified support
claim.

The program closed without widening support. It proved the first lane is
evidence-backed operator-managed beta, but did not prove production-certified
real-adapter support.

## Current Baseline

1. `v4.0.0` narrow stable runtime is live.
2. Stable shipped support remains intentionally narrow.
3. `claude-code-cli` remains `Beta (operator-managed)`.
4. `gh-cli-pr` remains `Beta (operator-managed)` for preflight/readiness and
   deferred for full remote PR opening.
5. General-purpose production platform claim remains out of scope until a
   separate closeout decision proves enough promoted surface.

## Selected First Lane

`claude-code-cli` read-only governed workflow lane is the first candidate.

Reason:

1. it is lower risk than live-write PR creation;
2. it already has helper smoke and governed workflow evidence history;
3. failures can be classified without remote repository side effects;
4. it is the shortest credible path to a production-certified real-adapter
   claim.

## Non-Goals

1. No stable support widening in `GP-3.0`.
2. No version bump, tag, or publish in `GP-3.0`.
3. No `gh-cli-pr` full remote PR opening promotion in this lane.
4. No general-purpose production platform claim until a later closeout gate.
5. No promotion from one-off smoke, manifest inventory, or docs-only changes.

## Slice Plan

| Slice | Goal | Exit |
|---|---|---|
| `GP-3.0` scope freeze | Record promotion boundary, first lane, and gates | completed; roadmap/status PR merged, no runtime change |
| `GP-3.1` prerequisite truth refresh | Re-run `claude-code-cli` binary/auth/prompt-access truth checks | completed; preflight and workflow smoke passed; no support widening |
| `GP-3.2` governed workflow repeatability | Run/read the governed workflow smoke path and pin repeatability requirements | completed; 3 independent workflow smoke runs passed; no support widening |
| `GP-3.3` failure-mode matrix | Classify missing binary, auth missing, prompt denied, timeout, malformed output, policy denied | completed; helper/workflow failure modes fail-closed and typed |
| `GP-3.4` evidence completeness | Verify artifacts, events, cost/usage fields, and operator-readable failure metadata | completed; evidence checks widened and live smoke passed |
| `GP-3.5` support-boundary decision | Decide `promote_read_only`, `keep_operator_beta`, or `defer` | completed; verdict `keep_operator_beta` |
| `GP-3.6` closeout | Record final verdict and next allowed path | completed; verdict `close_keep_operator_beta` |

## Promotion Criteria

A lane may become production-certified read-only only if all criteria pass.

1. The adapter command is real and available through documented prerequisites.
2. Prompt access is verified by an actual prompt smoke, not only auth status.
3. The governed workflow completes in a clean workspace with deterministic
   artifacts and evidence.
4. Failure modes are fail-closed, classified, and operator-actionable.
5. Timeout/cancel behavior is documented or explicitly bounded.
6. Policy events and adapter invocation evidence are complete enough for audit.
7. Docs and support boundary name the exact promoted surface.
8. CI or an explicit release-gate smoke represents the supported path.

## Demotion / No-Promotion Rules

The lane stays `Beta (operator-managed)` if any of these remain true.

1. Access depends on local auth state that cannot be verified repeatably.
2. Prompt access is unavailable in the operator environment.
3. The governed workflow smoke is flaky or requires manual interpretation.
4. Failure metadata is not actionable.
5. The lane cannot be tested without external side effects not covered by a
   rollback/rehearsal contract.

## Required Evidence Package

Every implementation slice must record:

1. command output or structured smoke report;
2. related test command and result;
3. docs/support-boundary impact;
4. known-bug impact;
5. explicit support decision.

## Initial Decision

`GP-3.0` opens the program but does not promote anything. The only accepted
next implementation slice is `GP-3.1` for `claude-code-cli` prerequisite truth
refresh.

## GP-3.1 Evidence Refresh

`GP-3.1` refreshed the current operator-environment truth for
`claude-code-cli`.

1. Decision record:
   `.claude/plans/GP-3.1-CLAUDE-CODE-CLI-PREREQUISITE-TRUTH-REFRESH.md`
2. Tracker: [#388](https://github.com/Halildeu/ao-kernel/issues/388)
3. Preflight command:
   `python3 scripts/claude_code_cli_smoke.py --output json --timeout-seconds 30`
4. Workflow command:
   `python3 scripts/claude_code_cli_workflow_smoke.py --output json --timeout-seconds 60 --cleanup`
5. Result:
   - preflight `overall_status="pass"`
   - workflow `overall_status="pass"`
   - workflow final state `completed`
6. Boundary:
   - no runtime change
   - no version bump, tag, or publish
   - no stable support widening
   - `claude-code-cli` remains `Beta (operator-managed)`

The next accepted implementation slice is `GP-3.2` governed workflow
repeatability. A single passing smoke is not enough for production-certified
support.

## GP-3.2 Repeatability Evidence

`GP-3.2` checked whether the `claude-code-cli` governed read-only workflow can
repeat successfully in independent temp workspaces.

1. Decision record:
   `.claude/plans/GP-3.2-CLAUDE-CODE-CLI-GOVERNED-WORKFLOW-REPEATABILITY.md`
2. Tracker: [#390](https://github.com/Halildeu/ao-kernel/issues/390)
3. Command:
   `python3 scripts/claude_code_cli_workflow_smoke.py --output json --timeout-seconds 60 --cleanup`
4. Repetition:
   - run 1: `overall_status="pass"`, final state `completed`
   - run 2: `overall_status="pass"`, final state `completed`
   - run 3: `overall_status="pass"`, final state `completed`
5. Required checks:
   - `final_state`
   - `evidence_events`
   - `review_findings_artifact`
   - `adapter_log`
   - `review_findings_schema`
6. Boundary:
   - no runtime change
   - no version bump, tag, or publish
   - no stable support widening
   - `claude-code-cli` remains `Beta (operator-managed)`

The next accepted implementation slice is `GP-3.3` failure-mode matrix. Passing
repeatability does not prove failure behavior or general operator support.

## GP-3.3 Failure-Mode Matrix

`GP-3.3` classified the `claude-code-cli` preflight and governed workflow
failure modes that must block promotion.

1. Decision record:
   `.claude/plans/GP-3.3-CLAUDE-CODE-CLI-FAILURE-MODE-MATRIX.md`
2. Tracker: [#392](https://github.com/Halildeu/ao-kernel/issues/392)
3. Covered categories:
   - missing binary
   - auth missing or malformed
   - prompt denied
   - timeout
   - malformed output
   - policy denied
4. Test delta:
   - `manifest_output_missing_status`
   - `adapter_timeout`
5. Validation:
   `python3 -m pytest -q tests/test_claude_code_cli_smoke.py tests/test_claude_code_cli_workflow_smoke.py`
6. Boundary:
   - no runtime behavior change
   - no version bump, tag, or publish
   - no stable support widening
   - `claude-code-cli` remains `Beta (operator-managed)`

The next accepted implementation slice is `GP-3.4` evidence completeness.

## GP-3.4 Evidence Completeness

`GP-3.4` widened the `claude-code-cli` governed workflow smoke evidence checks
and recorded a live pass.

1. Decision record:
   `.claude/plans/GP-3.4-CLAUDE-CODE-CLI-EVIDENCE-COMPLETENESS.md`
2. Tracker: [#394](https://github.com/Halildeu/ao-kernel/issues/394)
3. Added smoke checks:
   - `event_order`
   - `review_findings_contents`
4. Added negative coverage:
   - out-of-order required events
   - adapter log secret-like leak
5. Live smoke:
   - `overall_status="pass"`
   - final state `completed`
   - run id `d269c4f7-78d5-4773-b609-a0891513e464`
6. Cost/usage:
   - explicit non-claim for adapter-path `cost_usd` / token usage completeness
7. Boundary:
   - no stable support widening
   - no version bump, tag, or publish
   - `claude-code-cli` remains `Beta (operator-managed)`

The next accepted implementation slice is `GP-3.5` support-boundary decision.

## GP-3.5 Support-Boundary Decision

`GP-3.5` reconciled all `claude-code-cli` promotion gates and kept the lane at
`Beta (operator-managed)`.

1. Decision record:
   `.claude/plans/GP-3.5-CLAUDE-CODE-CLI-SUPPORT-BOUNDARY-DECISION.md`
2. Tracker: [#396](https://github.com/Halildeu/ao-kernel/issues/396)
3. Verdict: `keep_operator_beta`
4. Fresh evidence:
   - preflight smoke `overall_status="pass"`
   - governed workflow smoke `overall_status="pass"`
   - workflow final state `completed`
   - run id `25af3707-9f8b-497f-bdb1-32cd82e7cd52`
5. Positive gates:
   - prerequisite truth refreshed
   - repeatability proven by three independent runs
   - failure-mode matrix fail-closed
   - evidence completeness checks behavior-tested
6. Blockers to production-certified read-only:
   - external `claude` binary and local session auth remain operator state
   - `KB-001` and `KB-002` remain open
   - no CI-managed live `claude-code-cli` governed workflow gate exists
   - adapter-path `cost_usd` / token usage remains explicit non-claim
7. Boundary:
   - no stable support widening
   - no version bump, tag, or publish
   - `claude-code-cli` remains `Beta (operator-managed)`

The next accepted implementation slice is `GP-3.6` program closeout.

## GP-3.6 Program Closeout

`GP-3.6` closed the promotion program without support widening.

1. Decision record:
   `.claude/plans/GP-3.6-PRODUCTION-CERTIFIED-ADAPTER-PROMOTION-CLOSEOUT.md`
2. Tracker: [#398](https://github.com/Halildeu/ao-kernel/issues/398)
3. Parent tracker: [#386](https://github.com/Halildeu/ao-kernel/issues/386)
4. Final verdict: `close_keep_operator_beta`
5. Result:
   - `claude-code-cli` remains `Beta (operator-managed)`
   - production-certified read-only claim is not granted
   - stable shipped baseline is unchanged
   - no version bump, tag, or publish
6. Reason:
   - external `claude` binary/session auth remains operator state
   - `KB-001` and `KB-002` remain open
   - no CI-managed live `claude-code-cli` governed workflow gate exists
   - adapter-path `cost_usd` / token usage remains explicit non-claim

Future promotion work must open a new scoped lane; it cannot infer widening
from this closeout.
