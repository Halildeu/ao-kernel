# GP-4 — CI-Managed Live Adapter Gate Design

**Status:** Completed with no support widening
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

**Decision:** `close_no_widening_keep_operator_beta`

This program closed after `GP-4.5` without support widening. It does not:

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
| `GP-4.1` workflow design stub | Add non-secret workflow skeleton or documented manual gate contract | implemented by `.github/workflows/live-adapter-gate.yml`; report remains `blocked`; no live secrets, no live calls, CI-safe |
| `GP-4.2` evidence artifact contract | Define/upload JSON report shapes for live gate | implemented by schema-backed `live-adapter-gate-evidence.v1.json`; local tests validate schema; no live execution or support widening |
| `GP-4.3` protected environment contract | Document required GitHub environment/secrets and fork safety | implemented by schema-backed `live-adapter-gate-environment-contract.v1.json`; no repository secret values, no live execution, no support widening |
| `GP-4.4` live rehearsal decision | Run protected manual gate once, or record blocked decision if prerequisites are absent | implemented as blocked decision artifact; no protected environment/credential attested, no live execution |
| `GP-4.5` support-boundary decision | Decide promote/keep beta/defer | completed with verdict `close_no_widening_keep_operator_beta` |

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

## GP-4.1 Implementation

`GP-4.1` adds a manual contract skeleton:

1. workflow: `.github/workflows/live-adapter-gate.yml`;
2. report builder: `ao_kernel/live_adapter_gate.py`;
3. script wrapper: `scripts/live_adapter_gate_contract.py`;
4. expected artifact: `live-adapter-gate-contract.v1.json`.

The report intentionally says `overall_status="blocked"` and
`finding_code="live_gate_not_implemented"`. A successful workflow run means
the contract artifact was emitted; it does not mean the live adapter passed.

## GP-4.2 Implementation

`GP-4.2` adds the schema-backed evidence artifact contract for the manual gate:

1. schema: `ao_kernel/defaults/schemas/live-adapter-gate-evidence.schema.v1.json`;
2. helper: `build_live_adapter_gate_evidence_artifact()`;
3. validator: `validate_live_adapter_gate_evidence_artifact()`;
4. expected artifact: `live-adapter-gate-evidence.v1.json`.

The artifact records the required future evidence slots:

1. gate contract report;
2. protected live preflight report;
3. protected governed workflow-smoke report;
4. protected environment attestation.

The current artifact is intentionally blocked. It may be schema-valid and
uploaded by CI, but it still says `support_widening=false` and
`production_certified=false`.

## GP-4.3 Implementation

`GP-4.3` adds the schema-backed protected environment / secret contract:

1. schema: `ao_kernel/defaults/schemas/live-adapter-gate-environment.schema.v1.json`;
2. helper: `build_live_adapter_gate_environment_contract()`;
3. validator: `validate_live_adapter_gate_environment_contract()`;
4. expected artifact: `live-adapter-gate-environment-contract.v1.json`.

The contract names the future protected GitHub environment
`ao-kernel-live-adapter-gate`, requires maintainer review, forbids fork and
pull-request secret exposure, and names `AO_CLAUDE_CODE_CLI_AUTH` as the
project-owned Claude Code CLI auth handle. It does not create the environment,
read a secret, call `claude`, or widen support.

## GP-4.4 Implementation

`GP-4.4` records the protected live rehearsal decision:

1. schema:
   `ao_kernel/defaults/schemas/live-adapter-gate-rehearsal-decision.schema.v1.json`;
2. helper: `build_live_adapter_gate_rehearsal_decision()`;
3. validator: `validate_live_adapter_gate_rehearsal_decision()`;
4. expected artifact: `live-adapter-gate-rehearsal-decision.v1.json`.

The decision is `blocked_no_rehearsal` because the required protected
environment and project-owned credential are not attested. The workflow still
does not create environments, read secrets, bind `environment:`, call `claude`,
or widen support.

## GP-4.5 Closeout

`GP-4.5` closes the program with verdict
`close_no_widening_keep_operator_beta`.

Evidence considered:

1. `GP-4.1` contract artifact remains blocked;
2. `GP-4.2` evidence artifact records missing live preflight, governed
   workflow-smoke, and protected-environment evidence slots;
3. `GP-4.3` records required protected environment and secret handle, but does
   not attest either as configured;
4. `GP-4.4` records `decision="blocked_no_rehearsal"`;
5. support docs still identify `claude-code-cli` as
   `Beta (operator-managed)`.

Final impact:

1. no stable support widening;
2. no production-certified real-adapter support;
3. no general-purpose production platform claim;
4. no version bump, tag, publish, secret, environment binding, or live
   `claude` invocation.

## Next Step

There is no active GP-4 widening gate after this closeout. A future widening
attempt must open a new explicit gate only after the protected environment,
project-owned credential, protected live preflight, protected governed workflow
smoke, docs parity, and release/CI evidence all exist.
