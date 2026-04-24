# GP-3 — Production-Certified Adapter Promotion Roadmap

**Status:** Active program, scope freeze recorded
**Date:** 2026-04-24
**Tracker:** [#386](https://github.com/Halildeu/ao-kernel/issues/386)
**Parent context:** `v4.0.0` narrow stable live + `GP-2` closeout +
`SM-1..SM-4` stable maintenance baseline

## Purpose

`GP-3` is the first post-stable promotion program for moving one real adapter
lane from `Beta (operator-managed)` toward a production-certified support
claim.

The program does not widen support by being opened. Promotion requires code
path evidence, behavior tests, smoke, docs parity, runbook guidance, and CI
evidence to agree.

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
| `GP-3.0` scope freeze | Record promotion boundary, first lane, and gates | roadmap/status PR merged, no runtime change |
| `GP-3.1` prerequisite truth refresh | Re-run `claude-code-cli` binary/auth/prompt-access truth checks | pass/fail evidence recorded; blockers mapped |
| `GP-3.2` governed workflow repeatability | Run/read the governed workflow smoke path and pin repeatability requirements | smoke contract updated or lane remains beta |
| `GP-3.3` failure-mode matrix | Classify missing binary, auth missing, prompt denied, timeout, malformed output, policy denied | behavior assertions or helper contract updates merged |
| `GP-3.4` evidence completeness | Verify artifacts, events, cost/usage fields, and operator-readable failure metadata | evidence gaps closed or deferred explicitly |
| `GP-3.5` support-boundary decision | Decide `promote_read_only`, `keep_operator_beta`, or `defer` | docs/status/support matrix updated |
| `GP-3.6` closeout | Record final verdict and next allowed path | tracker closed or next lane opened intentionally |

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
