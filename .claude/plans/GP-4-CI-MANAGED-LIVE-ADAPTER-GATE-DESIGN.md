# GP-4 — CI-Managed Live Adapter Gate Design

**Status:** Active design program
**Date:** 2026-04-24
**Tracker:** [#400](https://github.com/Halildeu/ao-kernel/issues/400)
**Predecessor:** `GP-3` closeout

## Purpose

Define the missing gate that blocked `claude-code-cli` from becoming
production-certified in `GP-3`.

`GP-3` proved that the lane is evidence-backed and operator-managed, but it did
not prove ao-kernel-owned production support because live adapter execution was
not managed by CI or an equivalent release gate. `GP-4` exists to design that
gate before any future support widening is attempted.

## Current Decision

**Decision:** `design_only_no_widening`

This slice does not:

1. add CI secrets;
2. run live external adapter calls in default CI;
3. promote `claude-code-cli`;
4. change runtime behavior;
5. publish or tag a release.

## Required Gate Properties

A future live-adapter gate may support production-certified real-adapter claims
only if it satisfies all properties below.

| Property | Requirement |
|---|---|
| Controlled identity | The live adapter account/session is owned by the project or release process, not by an arbitrary local operator shell. |
| Explicit trigger | The gate is never accidentally invoked by forks or untrusted PRs. It is scheduled, manual, protected-branch-only, or release-gate-only. |
| Secret isolation | Secrets are scoped to the smallest workflow/environment and never exposed to pull_request from forks. |
| Deterministic skip/block semantics | Missing credentials produce `skipped` or `blocked` with explicit finding codes, not green success. |
| Evidence artifacts | The gate uploads machine-readable preflight and governed workflow smoke reports. |
| Policy parity | The same policy/event/evidence assertions used by local helper smoke are checked in the gate. |
| Cost/budget guard | The gate has timeout and cost/run-count boundaries; cost fields remain non-claim until separately reconciled. |
| Branch protection decision | Promotion requires deciding whether the gate is a required check, release-only check, or advisory scheduled check. |

## Candidate Gate Models

### Model A — Required PR Check

Runs on every protected-branch PR.

Verdict: **not accepted now**.

Reason: live external adapter credentials would need to be available to PR
workflows. That creates unnecessary secret and cost exposure unless the gate is
heavily restricted. It is also too expensive and brittle for routine docs/test
changes.

### Model B — Protected Manual / Scheduled Workflow

Runs via `workflow_dispatch` or schedule on protected branches using a GitHub
environment with restricted secrets.

Verdict: **preferred design direction**.

Reason: it can exercise the live adapter under project-managed credentials
without exposing secrets to untrusted PRs. It can upload evidence artifacts and
be referenced by a release or promotion decision.

Minimum constraints:

1. only `main` or protected release branches;
2. only maintainers can dispatch;
3. no fork-triggered execution;
4. timeout lower than the local helper default unless explicitly justified;
5. artifact upload includes preflight JSON, workflow-smoke JSON, and run
   metadata;
6. failure codes mirror local helper finding codes.

### Model C — Release-Gate Operator Attestation

Release manager runs the existing local helpers and attaches structured output
to a release decision record.

Verdict: **acceptable fallback, not enough for production-certified support by
itself**.

Reason: it is better than ad-hoc local smoke, but it still depends on local
operator state. It can support beta confidence, not project-owned production
certification.

## Required Implementation Slices

Future implementation must be split. No slice below should promote support by
itself.

| Slice | Goal | Exit |
|---|---|---|
| `GP-4.1` workflow design stub | Add non-secret workflow skeleton or documented manual gate contract | no live secrets, no live calls, CI-safe |
| `GP-4.2` evidence artifact contract | Define/upload JSON report shapes for live gate | local tests validate report schema |
| `GP-4.3` protected environment contract | Document required GitHub environment/secrets and fork safety | no repository secret values committed |
| `GP-4.4` live rehearsal | Run protected manual gate once and record artifacts | only if project-owned credentials exist |
| `GP-4.5` support-boundary decision | Decide promote/keep beta/defer | requires all prior slices and docs parity |

## Promotion Preconditions

The `claude-code-cli` lane may be reconsidered only after:

1. a protected live gate exists or an explicit release-gate equivalent is
   approved;
2. live gate evidence includes preflight and governed workflow smoke JSON;
3. missing credentials do not create fake green CI;
4. the gate cannot run on untrusted forks;
5. support docs name the exact promoted surface;
6. `KB-001` and `KB-002` are either resolved or explicitly bounded by the new
   gate;
7. cost/usage support remains explicitly out of scope unless separately
   reconciled.

## Support Boundary Impact

No support widening.

Current tier remains:

1. `claude-code-cli`: `Beta (operator-managed)`;
2. production-certified real-adapter support: not granted;
3. shipped stable baseline: unchanged;
4. general-purpose production coding automation platform claim: not granted.

## Next Step

The next implementation slice should be `GP-4.1`: add a CI-safe manual workflow
design stub or a narrower written workflow contract. It must not introduce live
secrets or run live adapter calls by default.
