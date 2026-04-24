# GP-5 - General-Purpose Production Platform Integration

**Status:** Active program setup
**Date:** 2026-04-24
**Authority:** `origin/main` at `33c4d22`
**Tracker:** [#424](https://github.com/Halildeu/ao-kernel/issues/424)
**Branch:** `codex/gp5-platform-integration-roadmap`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gp5-platform-integration`
**Predecessors:** `v4.0.0` stable runtime, `GP-3`, `GP-4`, `RI-4`
closed, `RI-5` opened
**Motto:** Kapsam disiplini: once kanitli entegrasyon, sonra support widening.

## 1. Purpose

`ao-kernel` already has a narrow stable production runtime. This program is
not another broad feature push. Its purpose is to define and execute the
remaining integration gates required before the project can credibly claim to
be a general-purpose production coding automation platform.

The platform claim is allowed only when these surfaces work together with
evidence:

1. repo intelligence can produce trustworthy, bounded context;
2. a real adapter can consume that context under project-owned gate evidence;
3. governed workflows can produce review and patch plans without hidden
   operator assumptions;
4. write-side actions happen only in disposable or controlled environments with
   rollback evidence;
5. docs, runtime, tests, CI, support boundary, and operations runbooks all say
   the same thing.

## 2. Current Baseline

### Stable runtime

The current stable baseline is a narrow governed runtime, not a general-purpose
coding automation platform. The stable claim includes entrypoints, doctor,
policy enforcement, bundled `review_ai_flow`, `codex-stub`, demo review smoke,
packaging smoke, and documented support boundaries.

### Real adapters

`claude-code-cli` remains `Beta (operator-managed)`.

Prior programs proved useful local/operator evidence, but did not grant
production-certified support because no project-owned CI-managed live adapter
gate exists. `GP-4` closed with `close_no_widening_keep_operator_beta`.

`gh-cli-pr` remains a guarded operator-managed / deferred live-write surface.
Disposable rollback rehearsal evidence exists, but full live remote PR opening
is not a shipped production support claim.

### Repo intelligence

Repo intelligence is now a critical platform dependency, not a side project.
The current baseline includes:

1. `repo scan` read-only local artifacts;
2. Python AST import graph and symbol index;
3. deterministic agent context pack;
4. deterministic chunk manifest;
5. vector dry-run and explicit vector write path;
6. `repo query` read-only retrieval;
7. stdout-only Markdown query context output.

It remains `Beta / experimental read-only`. It must not be auto-wired into
context compilation, MCP, root context exports, or live coding workflows until
the gates below close.

`RI-5` is now the separate design gate for explicit root/context export.
GP-5 must coordinate with that work, but must not treat root export as already
available or required for the first repo-intelligence integration slices.

## 3. Non-Negotiable Program Rules

1. `origin/main` is the only authority after each merge.
2. Every slice uses a dedicated worktree and a `codex/` branch.
3. Uncommitted changes are preserved before rebase, pull, switch, or cleanup.
4. At most one runtime-support-widening slice is active at a time.
5. No support boundary widening is inferred from a passing local smoke.
6. No live external side effect is run by default CI or fork-triggered CI.
7. Missing credentials produce `blocked` or `skipped` evidence, not fake green.
8. Repo-intelligence integration is a first-class gate; it must not be left to
   an implicit later session.
9. Every slice ends with a written decision: `promote`, `keep_beta`,
   `defer`, or `retire`.

## 4. Program Phases

### GP-5.0 - Integration Authority Freeze

**Goal:** Freeze the starting truth before widening support.

**Inputs:**

1. `PRODUCTION-STABLE-LIVE-ROADMAP.md`;
2. `SUPPORT-BOUNDARY.md`;
3. `PUBLIC-BETA.md`;
4. `GP-3` and `GP-4` closeouts;
5. `RI-4` repo-intelligence closeout and `RI-5` root/export design gate.

**Work:**

1. Record current shipped / beta / deferred / contract-only integration map.
2. Identify which surfaces are allowed to participate in GP-5.
3. Mark repo-intelligence as a required dependency for context-aware platform
   workflows.
4. Explicitly block any general-purpose production claim until GP-5 closeout.

**DoD:**

1. There is one current GP-5 authority map.
2. No existing beta surface is promoted by wording alone.
3. Repo-intelligence appears in the production integration critical path.

**Release impact:** Documentation / program status only.

### GP-5.1 - Protected Live Adapter Gate Implementation

**Goal:** Convert the GP-4 live-adapter gate design from blocked contract into
an executable protected gate.

**Work:**

1. Bind `.github/workflows/live-adapter-gate.yml` to the protected environment
   `ao-kernel-live-adapter-gate`.
2. Require project-owned credential handle `AO_CLAUDE_CODE_CLI_AUTH`.
3. Run only on protected manual/scheduled/release contexts.
4. Never expose secrets to fork PRs.
5. Emit schema-backed preflight, governed workflow smoke, and environment
   attestation artifacts.
6. Preserve deterministic `blocked` status when prerequisites are absent.

**DoD:**

1. Protected gate can distinguish `pass`, `fail`, `blocked`, and `skipped`.
2. Missing protected environment or credential is not green.
3. Evidence artifact includes adapter identity, workflow identity, policy
   checks, event order, timeout, and redaction status.
4. Support boundary remains unchanged until a later promotion decision.

**Release impact:** CI/governance; no automatic support widening.

### GP-5.2 - Production-Certified Read-Only Adapter Decision

**Goal:** Decide whether `claude-code-cli` can move from
`Beta (operator-managed)` to production-certified read-only.

**Work:**

1. Run repeated protected live preflight and governed workflow smoke.
2. Reconcile `KB-001` and `KB-002` against protected gate behavior.
3. Verify failure-mode matrix under project-owned gate identity.
4. Confirm timeout, cancellation, malformed output, policy deny, auth missing,
   prompt denied, and binary missing semantics.
5. Decide `promote_read_only`, `keep_operator_beta`, or `defer`.

**DoD:**

1. Production-certified support is granted only with repeated protected gate
   evidence.
2. Local operator auth is not treated as project-owned support.
3. The decision updates support docs and known bugs consistently.

**Release impact:** Support boundary decision; possible minor/beta release if
promoted.

### GP-5.3 - Repo Intelligence Integration Gate

**Goal:** Move repo intelligence from standalone query tooling toward governed
workflow context without unsafe auto-injection.

**Why this is critical:**

General-purpose coding automation cannot rely only on a static prompt. It needs
repo-local retrieval, freshness checks, source hash validation, and a bounded
context handoff. Repo intelligence is therefore one of the main platform
integration pillars.

**Allowed starting point:**

1. `repo query` read-only retrieval;
2. stdout-only Markdown context output;
3. validated namespace and source-hash matching;
4. no root authority writes;
5. no automatic `context_compiler` feed.

**Work slices:**

1. `GP-5.3a` - Retrieval evidence quality contract:
   define relevance, stale-result, snippet-boundary, and hash-validation
   assertions for `repo query`.
2. `GP-5.3b` - Agent context handoff contract:
   document and test stdout-only Markdown handoff as explicit operator input,
   not hidden prompt injection.
3. `GP-5.3c` - Workflow opt-in design:
   design a future `context_compiler` opt-in flag that can consume query
   results only with explicit config and behavior tests.
4. `GP-5.3d` - No-MCP/no-root-export guard:
   add regression checks that `repo query` does not write MCP tools, root
   context files, or `.ao/context` query artifacts.
5. `GP-5.3e` - Promotion decision:
   decide whether repo-intelligence read-only context can become a supported
   building block for GP-5 workflows.

**DoD:**

1. Retrieval output is evidence-backed, bounded, and stale-safe.
2. Workflow integration remains explicit and testable.
3. Repo-intelligence context never silently broadens support or pollutes
   authority files.
4. Support docs state exactly whether the surface is standalone beta,
   workflow-beta, or production-supported.

**Release impact:** Beta integration gate first; no automatic production claim.

### GP-5.4 - Governed Read-Only Coding Workflow E2E

**Goal:** Prove the first complete read-only coding automation loop.

**Target chain:**

```text
task input
-> repo intelligence query/context
-> production-certified or protected-gated adapter
-> governed workflow
-> review findings / patch plan artifact
-> evidence timeline
```

**Work:**

1. Define a deterministic task fixture over a disposable repo or fixture repo.
2. Feed repo-intelligence context explicitly into the governed workflow.
3. Run the real adapter through the protected gate if GP-5.2 promoted it;
   otherwise keep this as protected beta evidence only.
4. Assert event order, policy checks, artifacts, redaction, and failure modes.

**DoD:**

1. The workflow produces useful review findings or a patch plan without writes.
2. All inputs, context chunks, adapter output, and artifacts are attributable.
3. The run can fail closed without losing evidence.

**Release impact:** Possible read-only platform beta claim after support
decision.

### GP-5.5 - Controlled Patch/Test Lane

**Goal:** Add write capability only inside a controlled local/disposable
worktree with rollback.

**Work:**

1. Use path-scoped write ownership before patch application.
2. Require diff preview and explicit apply boundary.
3. Apply patches only in disposable or dedicated worktrees.
4. Run targeted tests selected from repo-intelligence and changed paths.
5. Capture rollback and cleanup evidence.
6. Prove idempotency and conflict handling.

**DoD:**

1. Patch application cannot silently modify the operator's active main
   worktree.
2. Test selection is explainable and can fall back to full test gates.
3. Rollback path is verified before any support widening.

**Release impact:** Write-side beta only until live-write PR gates pass.

### GP-5.6 - PR Live-Write Integration Gate

**Goal:** Connect controlled patch output to `gh-cli-pr` only with disposable
sandbox and rollback evidence.

**Work:**

1. Use sandbox repository by default.
2. Require explicit `--allow-live-write` style opt-in.
3. Create -> verify -> rollback remote PR rehearsal.
4. Verify branch cleanup and PR close behavior.
5. Keep `--keep-live-write-pr-open` as an explicitly risky blocked/pending
   support path unless separately approved.

**DoD:**

1. Remote side effects are bounded and reversible in test rehearsal.
2. Evidence proves both creation and rollback.
3. No production support claim is made for arbitrary user repositories.

**Release impact:** Deferred-to-beta decision only after rehearsal evidence.

### GP-5.7 - Full Production Rehearsal

**Goal:** Run the complete platform chain under controlled conditions.

**Target chain:**

```text
issue/task
-> repo scan/index/query
-> context handoff
-> real adapter reasoning
-> patch plan
-> controlled patch
-> tests
-> PR rehearsal
-> rollback/closeout
```

**DoD:**

1. At least three clean rehearsals pass on disposable/supported targets.
2. At least one failure rehearsal proves fail-closed behavior.
3. Artifacts and runbooks are sufficient for another operator to reproduce the
   decision.

**Release impact:** Candidate gate for broader platform beta.

### GP-5.8 - Operations and Support Widening Package

**Goal:** Make the platform operable before making a broader claim.

**Work:**

1. Update incident runbooks for adapter, repo-intelligence, vector backend,
   write-side, PR, and rollback failures.
2. Update known bugs and troubleshooting.
3. Define upgrade notes and rollback procedure for each widened surface.
4. Add support-boundary wording for every promoted tier.
5. Decide branch protection / required check implications.

**DoD:**

1. Operator knows how to diagnose and recover each widened surface.
2. Production claim wording has exact boundaries.
3. Known bug registry has no shipped-blocker affecting the widened claim.

**Release impact:** Required before any production platform claim.

### GP-5.9 - General-Purpose Platform Release Candidate

**Goal:** Decide whether `ao-kernel` can claim general-purpose production coding
automation platform readiness.

**Decision options:**

1. `promote_general_purpose_platform`;
2. `promote_limited_platform_beta`;
3. `keep_narrow_stable_runtime`;
4. `defer_support_widening`.

**Promotion requires all success criteria in Section 5.**

**Release impact:** Version, docs, release notes, tag, publish, post-publish
verification only after gate closeout.

## 5. Program Success Criteria

| ID | Criterion |
|---|---|
| `BC-1` | At least one real adapter is production-certified by protected gate evidence, not local operator state. |
| `BC-2` | Repo-intelligence retrieval is integrated only behind explicit opt-in and has stale/hash/relevance evidence. |
| `BC-3` | Read-only coding workflow E2E produces attributable review/patch-plan artifacts. |
| `BC-4` | Write-side patch/test flow is bounded by worktree isolation, ownership, diff preview, rollback, and tests. |
| `BC-5` | Remote PR live-write is rehearsed only in disposable/sandbox targets with rollback evidence. |
| `BC-6` | Docs, runtime, tests, CI, support boundary, known bugs, and runbooks match. |
| `BC-7` | No fake green: missing auth, missing vector backend, blocked protected env, or denied policy are explicit non-pass states. |

## 6. Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| `R1` repo-intelligence split-brain | Other sessions can advance RI while GP-5 assumes stale state | Treat `origin/main` as authority; refresh before each GP-5 slice; keep RI as explicit dependency. |
| `R2` fake live-adapter evidence | Local operator auth is mistaken for project support | Require protected gate identity and artifact evidence before promotion. |
| `R3` repo retrieval overconfidence | Stale or irrelevant chunks drive bad coding decisions | Hash validation, stale exclusion, relevance assertions, and explicit context handoff. |
| `R4` silent prompt/context injection | Query results alter workflows without visible operator consent | Keep auto-feed disabled until opt-in design and tests exist. |
| `R5` live-write side effects | PR/branch writes leak into non-disposable targets | Default sandbox-only rehearsals, explicit opt-in, rollback evidence. |
| `R6` support overclaim | Docs imply production platform before gates pass | Support-boundary update required in the same PR as any widening decision. |
| `R7` cost/secret exposure | Protected gate leaks credentials or runs too often | Protected environment, manual/scheduled trigger, timeout, cost guard, fork isolation. |
| `R8` merge overwrite | Parallel sessions lose work | Dedicated worktrees, branch sync checks, overlap review, no destructive cleanup. |

## 7. First Backlog

This is the immediate implementation order. Do not skip ahead to runtime
promotion.

| Order | Slice | Output | Notes |
|---:|---|---|---|
| 1 | `GP-5.0` | This program roadmap PR | No runtime change. Establishes the integration authority. |
| 2 | `GP-5.1a` | Protected gate prerequisite audit | Check whether GitHub environment/secret can exist; no secret value in repo. |
| 3 | `GP-5.1b` | Protected workflow binding patch | Bind live gate to protected environment with blocked semantics preserved. |
| 4 | `GP-5.3a` | Repo-intelligence retrieval evidence contract | Use current `repo query` / Markdown context baseline from `RI-4`. |
| 5 | `GP-5.3b` | Agent context handoff contract | Explicit stdout/manual handoff; no `context_compiler` auto-feed. |
| 6 | `GP-5.2a` | `claude-code-cli` protected gate rehearsal | Only after GP-5.1 can produce real protected evidence. |
| 7 | `GP-5.4a` | Read-only E2E workflow rehearsal | Requires repo-intelligence handoff plus adapter gate evidence. |
| 8 | `GP-5.5a` | Controlled patch/test design | No remote side effects. |
| 9 | `GP-5.6a` | Disposable PR write rehearsal | Sandbox-only, rollback required. |
| 10 | `GP-5.9` | Production platform claim decision | Only after all prior gate evidence exists. |

## 8. Standard Slice DoD

Every GP-5 slice must include:

1. branch/worktree identity;
2. scope statement and explicit non-goals;
3. code/docs/tests touched;
4. positive and negative validation;
5. support-boundary impact;
6. known-bug impact;
7. CI or protected-gate evidence;
8. rollback/cleanup evidence if side-effectful;
9. written decision and next slice.

## 9. Current Decision

GP-5 opens with no support widening.

Current product wording remains:

1. stable production runtime: yes, narrow baseline;
2. general-purpose production coding automation platform: not yet;
3. real adapter production-certified support: not yet;
4. repo-intelligence production workflow integration: not yet;
5. next step: merge this roadmap, then start `GP-5.1a`.
