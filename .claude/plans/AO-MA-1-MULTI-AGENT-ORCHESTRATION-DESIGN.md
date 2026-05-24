# AO-MA-1 - Multi-Agent Orchestration Design

**Status:** planned / design slice - documentation and invariant test only
**Date:** 2026-05-24
**Parent:** `GPP-2D - Autonomous Required-Check Lane`
**Support impact:** none
**Production platform claim:** false
**Live adapter execution:** false

## 1. Purpose

AO-MA-1 is a design/docs-only slice; it does not implement runtime
orchestration, change branch protection, switch ao-release-gate enforce mode,
post check-runs, configure webhooks, or enable auto-merge.

AO-MA-1 records the multi-agent execution model that sits above the existing
GPP-2D autonomous required-check lane. The product direction is not "one agent
does one PR and a human approves forever"; the intended operating model is:

```text
operator goal
  -> repo-owned task graph
  -> parallel AI agents with disjoint write scopes
  -> independent review and verification evidence
  -> integrator-owned pull request
  -> ao-release-gate required check
  -> GitHub-native auto-merge when branch protection is satisfied
```

This record is **AO-MA execution layer** design. It does not replace the
**GPP-2D merge / release authority layer**. AO-MA coordinates agents and
evidence. GPP-2D decides whether a pull request may merge.

Primary references:

- `.claude/plans/GPP-2D-AUTONOMOUS-REQUIRED-CHECK-LANE.md` - required-check
  authority model, self-approving-gate risk, and GPP-2D sequencing.
- `.claude/plans/gpp_status.v1.json` - machine-readable GPP SSOT and guard
  flags.
- `.claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md` - human-readable
  program SSOT.
- `.claude/plans/GPP-2B-AO-RELEASE-GATE-REQUIRED-CHECK-MAPPING.md` -
  local-gate / release-gate mapping and review-evidence acceptance profile.
- `.claude/plans/GPP-2ag-LOCAL-AI-REVIEW-GATE-PIVOT.md` - local AI review gate
  as operator/process evidence only.
- `docs/COORDINATION.md`,
  `ao_kernel/defaults/policies/policy_multi_agent_coordination.v1.json`, and
  `ao_kernel/defaults/policies/policy_coordination_claims.v1.json` - existing
  coordination, claim, fencing, and one-agent-one-worktree semantics.

## 2. Authority model

Agent outputs are evidence, not authority.

Release authority = the repo-owned `ao-release-gate` required check plus GitHub branch-protection enforcement.

Raw Codex, Claude, or other AI output may be accepted only as schema-valid,
context-bound, no-secret evidence input. An AI verdict cannot approve a release,
cannot supersede a failing gate, cannot close GPP-2, and cannot widen support.

The AO-MA orchestrator may schedule work, assign scopes, collect artifacts, and
prepare a PR. It must not:

- mutate branch protection;
- admin-merge;
- bypass CODEOWNERS;
- treat a model AGREE as merge authority;
- claim production readiness;
- execute live adapters;
- alter support boundaries.

Claude MCP consultation is advisory review only, not release authority.
`local_gpp_gate` evidence is operator-controlled local trust evidence only; it
does not close GPP-2, change branch protection, execute live adapters, widen
support, or claim production readiness.

GPP-2 stays `blocked` until the GPP-2D evidence, cutover, and closeout chain is
complete.

## 3. Agent roles

| Role | Responsibility | Write authority |
|---|---|---|
| **Orchestrator** | Reads SSOT, creates the task graph, assigns disjoint work, tracks dependencies, and decides when a PR is ready for review. | Task graph and integration metadata only |
| **Planner Agent** | Turns a user goal into slices, dependencies, acceptance criteria, and high-risk scope classification. | Plan artifacts only |
| **Explorer Agent** | Performs read-only codebase, CI, GitHub, or runtime discovery and returns cited findings. | None |
| **Worker / Implementation Agent** | Implements one bounded slice in one worktree with a declared write set. | Declared files only |
| **Reviewer Agent** | Independently reviews the worker result and emits AGREE / REVISE evidence. Provider should differ from the implementer when cross-provider evidence is required. | Review artifact only |
| **Verifier Agent** | Runs tests, scope checks, secret checks, and GPP guard checks that can run in parallel with integration. | Verification artifact only |
| **Integrator** | Owns the final PR, resolves conflicts, rejects unsafe worker output, and emits the integration report. | Final PR branch only |
| **Release Gate** | Runs deterministic `ao-release-gate` logic from trusted repo code and decides required-check outcome. | GitHub check result only |

## 4. Artifact model

AO-MA uses explicit artifacts so coordination is reproducible and auditable.
Schema details are future AO-MA-2 work; this design fixes the minimal contract.

| Artifact | Producer | Purpose |
|---|---|---|
| `task_graph.v1` | Orchestrator | Goal, slices, dependencies, owners, high-risk classification, acceptance criteria |
| `agent_assignment.v1` | Orchestrator | Agent id, role, write scope, branch/worktree, expected outputs |
| `worker_result.v1` | Worker | Changed files, summary, tests run, known gaps, no-secret attestation |
| `review_verdict.v1` | Reviewer | AGREE / REVISE / BLOCK with cited findings and provider metadata |
| `verification_report.v1` | Verifier | Commands, outputs, failed checks, guard state, artifact hashes |
| `integration_report.v1` | Integrator | Conflict handling, accepted/rejected worker outputs, final PR scope |
| `local-gpp-gate-evidence.v1` | Local gate | Context-bound operator/process evidence consumed by release governance |
| `ao-release-gate decision` | Release gate | Deterministic required-check decision for GitHub branch protection |

Artifacts must be no-secret. They may include metadata, hashes, paths, command
names, and redacted evidence, but not PATs, PEMs, webhook secrets, Vault tokens,
or model-provider credentials.

## 5. Parallelism and ownership rules

Parallel execution is allowed only when scopes are explicit and separable.

1. Each worker gets a declared write set before it starts.
2. No two workers may edit the same file unless the orchestrator assigns one
   worker as owner and the other as read-only.
3. Every worker uses a separate worktree and short-lived branch.
4. Shared authority files stay single-owner:
   `.github/**`, `CODEOWNERS`, `AGENTS.md`, `CLAUDE.md`,
   `.claude/plans/gpp_status.v1.json`, GPP/AO status docs,
   `ao_kernel/ao_release_gate*.py`, `scripts/ao_release_gate_decision.py`,
   `scripts/local_gpp_gate*.py`, local-gate / release-gate schemas, deploy /
   publish workflows, and secret / Vault / GitHub App wiring.
5. Conflict resolution is integrator-owned. Workers must not revert or erase
   unrelated edits.
6. If ownership is ambiguous, the orchestrator must fail closed and split the
   task again instead of letting agents race over the same files.
7. Future write-capable orchestration operations must either join the
   claim-required coordination set or explicitly document why they are safely
   claim-free.

## 6. Execution loop

```text
1. Orchestrator reads AGENTS.md, gpp_status.v1.json, and current repo state.
2. Planner Agent creates a task graph and acceptance criteria.
3. Explorer Agents gather non-overlapping read-only evidence in parallel.
4. Worker Agents implement independent slices in separate worktrees.
5. Reviewer Agents inspect worker outputs and emit review evidence.
6. Verifier Agents run tests, GPP guard checks, scope checks, and secret scans.
7. Integrator accepts safe outputs, resolves conflicts, and opens one PR.
8. local_gpp_gate validates local/process evidence.
9. ao-release-gate evaluates the PR as the repo-owned required check.
10. GitHub auto-merges only when branch protection is satisfied.
```

REVISE loops are bounded. A worker may fix reviewer findings, but repeated
REVISE, ownership conflicts, missing evidence, secret risk, or GPP guard drift
stop the autonomous lane and require operator direction.

## 7. GPP-2D integration

AO-MA is an execution accelerator for GPP-2D, not a replacement for it.

- AO-MA can produce implementer, reviewer, verifier, and integration evidence.
- `local_gpp_gate` can validate that evidence as operator/process evidence.
- `ao-release-gate` remains the deterministic merge authority.
- Low-risk PRs may eventually auto-merge only after GPP-2D-5 branch-protection
  cutover makes `ao-release-gate` required.
- High-risk PRs remain CODEOWNERS / human-gated.
- testai, smee.io, public webhooks, and deployment-protection callbacks are
  not required for this AO-MA path; they remain deferred optional GPP-2C
  infrastructure unless explicitly reactivated.

## 8. Phased plan

| Slice | Scope | Class |
|---|---|---|
| **AO-MA-1** | This design doc and invariant test. No runtime change. | docs + test |
| **AO-MA-2** | JSON Schemas for task graph, assignment, worker result, review verdict, verification report, and integration report. | schema + tests |
| **AO-MA-3** | Local orchestrator CLI that reads SSOT and emits a task graph without spawning agents yet. | code + tests |
| **AO-MA-4** | Parallel worktree runner with file ownership enforcement and conflict detection. | code + tests |
| **AO-MA-5** | Integrator policy: accepted/rejected worker outputs, conflict reports, single PR assembly. | code + tests |
| **AO-MA-6** | Reviewer loop contract and bounded REVISE handling. | code + tests |
| **AO-MA-7** | Verifier lane: GPP guard checks, secret scan, diff scope, and artifact hash reporting. | code + tests |
| **AO-MA-8** | End-to-end autonomous low-risk smoke in shadow mode, with no branch-protection change. | evidence |
| **AO-MA-9** | Wire AO-MA artifacts into the GPP-2D required-check lane after enforce evidence and cutover. | gated closeout |

AO-MA-1 does not alter `gpp_status.v1.json`. Later AO-MA slices must continue
to keep `support_widening_allowed=false`,
`production_platform_claim_allowed=false`, and
`live_adapter_execution_allowed=false` unless the GPP program explicitly closes
the relevant promotion gates.

## 9. Hard stops / non-goals

- No support widening.
- No production platform claim.
- No live adapter execution.
- `support_widening=false`.
- `production_platform_claim=false`.
- `live_adapter_execution=false`.
- No branch-protection mutation.
- No branch-protection/ruleset mutation by the agent.
- No `--admin` merge.
- No admin bypass.
- No CODEOWNERS bypass.
- No secret values in chat, logs, repo files, artifacts, tests, or PR comments.
- No fabricated evidence.
- No treating Codex, Claude, or any other model output as release authority.
- No testai or public webhook dependency for the near-term AO-MA lane.
- No testai.acik.com/ao-gate, smee.io, GitHub App webhook, or deployment-protection callback work in AO-MA-1.
- No GPP-2 closeout until GPP-2D enforce evidence, branch-protection cutover,
  auto-merge smoke, and AO-GATE-9 closeout are complete.

If a future AO-MA slice touches GitHub Actions workflow design, the inherited
GPP-2D boundary is: pull_request only, never pull_request_target; read-only
permissions; PR head is untrusted input; base/protected ref remains policy
authority.

## 10. Acceptance for AO-MA-1

AO-MA-1 is complete when:

1. This design record exists on `main`.
2. A test pins the authority separation: AO-MA execution layer vs GPP-2D
   merge / release authority layer.
3. The test pins the required agent roles and parallel worktree ownership rule.
4. The test pins that GPP-2 stays `blocked` and the three guard flags remain
   conceptually closed.
5. No runtime code, workflow enforce mode, branch protection, or
   `gpp_status.v1.json` change lands in this slice.
