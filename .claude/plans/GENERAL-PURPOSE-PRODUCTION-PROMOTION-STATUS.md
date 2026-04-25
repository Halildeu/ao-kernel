# General-Purpose Production Promotion Status

**Status:** GPP-2 blocked; GPP-2b external/admin provisioning issue open
**Date:** 2026-04-25
**Authority:** live `origin/main`; run `git rev-parse --short origin/main` for
the current head
**Tracker issue:** [#470](https://github.com/Halildeu/ao-kernel/issues/470)
**Current slice issue:** [#482](https://github.com/Halildeu/ao-kernel/issues/482)
for external/admin provisioning
**Current slice record:** `.claude/plans/gpp_status.v1.json`
**Machine-readable status:** `.claude/plans/gpp_status.v1.json`
**Branch:** none active
**Worktree:** none active
**Mode:** written, trackable, fail-closed promotion program
**Support impact:** none
**Release impact:** none

## 1. Purpose

This document is the execution SSOT for promoting `ao-kernel` from a narrow
stable production runtime toward a general-purpose production coding automation
platform.

The current product is not allowed to claim general-purpose production support
until the work packages below close with evidence. Completing a roadmap or
decision record is not enough; production support requires runtime behavior,
tests, smoke evidence, CI or protected-gate evidence, docs, runbooks, known-bug
state, and support-boundary wording to agree.

## 2. Current Baseline

Last live verification on current `origin/main` showed:

1. `main` synchronized with `origin/main`, divergence `0 0`.
2. `python3 -m ao_kernel version` returned `ao-kernel 4.0.0`.
3. `python3 -m ao_kernel doctor` returned `8 OK, 1 WARN, 0 FAIL`.
4. `python3 scripts/packaging_smoke.py` passed with wheel build, fresh venv
   install, three CLI entrypoint checks, and installed `demo_review.py`
   final state `completed`.
5. `pytest -q` passed with `3076 passed, 2 skipped`.
6. `GP-5.9` claim decision returned `keep_narrow_stable_runtime`,
   `support_widening=false`, and `production_platform_claim=false`.
7. `live_adapter_gate_contract.py` returned `overall_status=blocked` because
   the protected live-adapter gate is still design-only.
8. GitHub environment inventory now includes `ao-kernel-live-adapter-gate`.
   The environment has custom branch policy enabled for `main` and
   `can_admins_bypass=false`.
9. `AO_CLAUDE_CODE_CLI_AUTH` was not attested as a repository or environment
   secret handle.
10. Local `claude-code-cli` operator smoke passed, but that is operator-managed
    local auth, not project-owned production evidence.
11. `gh-cli-pr` preflight passed, but live remote PR write remains explicitly
    guarded and not production-supported.
12. Controlled local patch/test rehearsal passed in a disposable worktree with
    rollback, but `support_widening=false`.
13. GPP-1 live attestation on 2026-04-25 showed only GitHub environment
    `pypi`; at that point `ao-kernel-live-adapter-gate` was absent.
14. `gh secret list --repo Halildeu/ao-kernel` returned no visible repository
    secret handles.
15. `gh secret list --env ao-kernel-live-adapter-gate --repo Halildeu/ao-kernel`
    returns an empty list; the environment exists, but the required credential
    handle is not present.
16. `.github/workflows/live-adapter-gate.yml` still has only
    `workflow_dispatch` among live-gate trigger/secret/environment grep terms;
    no `environment:`, `secrets.`, `pull_request`, or `pull_request_target`
    binding is present.
17. GPP-1b added a machine-readable operator contract so Codex and Claude Code
    read the same current work package and blocked gates from repo state instead
    of chat memory.
18. GPP-2a re-attestation on 2026-04-25 reconfirmed the same then-current
    blocker: `ao-kernel-live-adapter-gate` was absent, environment secret
    lookup returned `HTTP 404`, and `AO_CLAUDE_CODE_CLI_AUTH` was not
    project-owned/attested.
19. GPP-2b opened issue
    [#482](https://github.com/Halildeu/ao-kernel/issues/482) to track the
    external/admin provisioning work. Live collaborator inventory currently
    shows only `Halildeu`, so the protected reviewer model still needs a
    non-triggering reviewer/admin or an explicitly approved equivalent gate.
20. GPP-2b partially provisioned the GitHub environment: the environment exists,
    deployment branch policy includes `main`, and admin bypass is disabled.
    Required reviewer protection and `AO_CLAUDE_CODE_CLI_AUTH` are still
    missing, so `GPP-2` remains blocked.

## 3. Current Verdict

| Claim | Current verdict |
|---|---|
| Narrow stable governed runtime | Yes |
| General-purpose production coding automation platform | No |
| Production-certified real adapter support | No |
| Repo-intelligence production workflow integration | No |
| Production remote PR live-write support | No |
| Controlled local write-side candidate | Rehearsal passed; no support widening |

The final production claim stays closed until `GPP-9` passes.

## 4. Execution Rules

1. `origin/main` is the authority after every merge.
2. Every work package uses a dedicated worktree and a `codex/gpp-*` branch.
3. Every work package has one GitHub issue, one PR, one acceptance surface, and
   one written exit decision.
4. Runtime, docs, tests, CI, support boundary, and runbook wording must move
   together before support is widened.
5. Live external side effects are never run by default CI or fork-triggered CI.
6. Missing credentials, missing protected environments, denied live writes, or
   unavailable evidence produce `blocked`, not fake `pass`.
7. Local operator auth is useful evidence, but it is not project-owned
   production support evidence.
8. A passing rehearsal does not widen support unless the same PR explicitly
   updates the support boundary and production claim decision.
9. No final production claim is allowed before a full matrix run records at
   least three clean chains and one fail-closed chain.

## 5. Work Package Board

| WP | Status | Goal | Exit decision |
|---|---|---|---|
| `GPP-0` | Completed | Create written tracker and acceptance model | `tracker_ready_no_support_widening` |
| `GPP-1` | Completed | Protected live-adapter prerequisite attestation | `blocked_attestation_missing` |
| `GPP-1b` | Completed | Agent operating program contract | `agent_operating_contract_ready_no_support_widening` |
| `GPP-2a` | Completed | Protected live-adapter prerequisite re-attestation | `still_blocked_protected_prerequisites_missing` |
| `GPP-2b` | Partially provisioned / blocked | Protected live-adapter environment and credential provisioning | environment exists; `main` branch policy and admin-bypass-off are set; reviewer protection and credential handle still missing |
| `GPP-2c` | Blocked external/admin decision | Reviewer and credential gate resolution | `AO_CLAUDE_CODE_CLI_AUTH` and non-self reviewer/equivalent gate still missing |
| `GPP-2d` | Implemented / no support widening | Metadata-only live gate attestation tool | repeatable attestation is available; current live gate still blocked |
| `GPP-2` | Blocked | Protected live-adapter gate runtime binding | blocked until a future attestation exits `prerequisites_ready` |
| `GPP-3` | Not started | Real-adapter usage/cost evidence closure | `cost_evidence_ready` / `defer_cost_policy` |
| `GPP-4` | Not started | `claude-code-cli` production-certified read-only decision | `promote_read_only` / `keep_operator_beta` / `defer` |
| `GPP-5` | Not started | Repo-intelligence explicit workflow integration | `workflow_context_ready` / `keep_beta_explicit_handoff` |
| `GPP-6` | Not started | Read-only production E2E over real adapter + repo intelligence | `read_only_e2e_ready` / `blocked_e2e` |
| `GPP-7` | Not started | Controlled write-side production candidate | `write_candidate_ready` / `keep_rehearsal_only` |
| `GPP-8` | Not started | Remote PR live-write promotion candidate | `remote_pr_candidate_ready` / `keep_sandbox_only` |
| `GPP-9` | Not started | Full production matrix + claim decision | `promote_general_purpose_production` / `promote_general_purpose_beta` / `keep_narrow_stable_runtime` |

## 6. GPP-0 - Tracker and SSOT

**Goal:** Make the remaining production promotion work written, discoverable,
and executable step by step.

**Status:** completed on `main` by PR
[#471](https://github.com/Halildeu/ao-kernel/pull/471).

**Entry criteria:**

1. `main` is clean and synchronized with `origin/main`.
2. No open PR conflicts with this docs/status-only tracker.

**Scope:**

1. Add this status file.
2. Link the tracker issue.
3. Record the current baseline and blocker list.
4. Define `GPP-1..GPP-9` with acceptance criteria.

**Acceptance criteria:**

1. This file records that the current product is a narrow stable runtime, not
   a general-purpose production platform.
2. `GPP-1` is identified as the next active work after this tracker merges.
3. No runtime code changes are made.
4. No support boundary is widened.
5. No release tag or PyPI publish is triggered.

**Validation:**

1. `git diff --check`
2. `python3 -m ao_kernel doctor`
3. `python3 -m ao_kernel version`
4. stale-claim grep for accidental production wording

## 7. GPP-1 - Protected Live-Adapter Prerequisite

**Goal:** Establish project-owned protected live-adapter prerequisites before
any workflow binding or support promotion.

**Status:** completed on `main` by PR
[#473](https://github.com/Halildeu/ao-kernel/pull/473).

**Exit decision:** `blocked_attestation_missing`.

**Entry criteria:**

1. `GPP-0` merged.
2. Current `origin/main` remains clean.

**Required decisions:**

1. Protected environment name: `ao-kernel-live-adapter-gate`.
2. Credential handle: `AO_CLAUDE_CODE_CLI_AUTH` or an explicitly approved
   replacement.
3. Secret values are never read; only handle existence is attested.

**Acceptance criteria:**

1. GitHub environment inventory contains `ao-kernel-live-adapter-gate`: met.
2. Deployment branch policy is restricted through custom branch policies and
   includes `main`: met.
3. Admin bypass is disabled on `ao-kernel-live-adapter-gate`: met.
4. Required secret handle is attested at repository or environment scope: not
   met; environment-scoped secret lookup returns an empty list.
5. Required reviewer protection is configured or an explicitly approved
   equivalent release gate is documented: not met.
6. Fork-triggered PR contexts cannot access protected credentials: met for the
   current design-only workflow, because the workflow is `workflow_dispatch`
   only and has no `environment:` or `secrets.` reference.
7. Missing secret or reviewer protection produces `blocked_attestation_missing`: met by
   this slice.
8. Status docs and support boundary still say no support widening: met.

**Validation:**

1. `gh api repos/Halildeu/ao-kernel/environments`
2. `gh secret list --repo Halildeu/ao-kernel`
3. workflow file inspection for no accidental secret exposure
4. schema-backed prerequisite report if implemented

**Decision record:** `.claude/plans/GPP-1-PROTECTED-LIVE-ADAPTER-PREREQUISITE-ATTESTATION.md`

## 8. GPP-1b - Agent Operating Program Contract

**Goal:** Make Codex and Claude Code follow the repo-owned GPP program state
before choosing or implementing the next work package.

**Status:** completed by PR [#475](https://github.com/Halildeu/ao-kernel/pull/475).

**Exit decision target:** `agent_operating_contract_ready_no_support_widening`.

**Scope:**

1. Add `AGENTS.md` startup and execution contract.
2. Add `.claude/plans/gpp_status.v1.json` as the machine-readable GPP status.
3. Add `scripts/gpp_next.py` to print the current/active WP and blocked gates.
4. Add tests that pin the current WP, blocked WP, and no-widening guards.
5. Keep `GPP-2` blocked.

**Acceptance criteria:**

1. `python3 scripts/gpp_next.py` reports `GPP-2` as blocked after the merge.
2. `python3 scripts/gpp_next.py --output json` returns valid JSON.
3. `support_widening_allowed`, `production_platform_claim_allowed`, and
   `live_adapter_execution_allowed` are all `false`.
4. `GPP-2` remains listed as blocked.
5. `AGENTS.md` tells Codex and Claude Code to read repo state before acting.
6. No live adapter execution, credential binding, support widening, release, or
   production claim is introduced.

**Decision record:** `.claude/plans/GPP-1b-AGENT-OPERATING-PROGRAM-CONTRACT.md`

## 9. GPP-2 - Protected Live-Adapter Gate Runtime Binding

**Goal:** Convert the current design-only `live-adapter-gate.yml` into a
protected manual gate that can actually run a real adapter under project-owned
evidence.

**Status:** blocked by GPP-2a re-attestation.

**Entry criteria:**

1. `GPP-1` exit decision is `prerequisites_ready`.
2. Protected environment and credential handle are attested.

Current GPP-2a exit decision is
`still_blocked_protected_prerequisites_missing`, so GPP-2 cannot start yet.

**Acceptance criteria:**

1. Workflow binds to `environment: ao-kernel-live-adapter-gate`.
2. Manual dispatch can run `claude-code-cli` preflight.
3. A governed workflow smoke runs through the protected gate.
4. Evidence artifact records adapter identity, workflow identity, event order,
   timeout, redaction status, artifact paths, and failure mode.
5. Missing auth, missing binary, timeout, prompt denial, malformed output, and
   policy denial are all non-pass states.
6. Default CI and fork PRs do not execute live adapters.
7. `support_widening=false` remains until `GPP-4`.

**Validation:**

1. protected workflow dispatch on `main`
2. downloaded evidence artifacts validate against schema
3. negative/fail-closed runs are recorded
4. local tests for artifact schema and status mapping

## 10. GPP-3 - Real-Adapter Usage and Cost Evidence

**Goal:** Close or explicitly decide the `BC-10` blocker from `GP-5.9`.

**Entry criteria:**

1. `GPP-2` produces protected live-adapter evidence.

**Acceptance criteria:**

1. Every live adapter run records adapter identity and elapsed time.
2. Every live adapter run records token/cost data or an explicit unavailable
   reason such as `usage_missing`, `token_unavailable`, or `cost_unavailable`.
3. Missing usage data is not silently treated as zero cost.
4. Evidence schema, docs, and support boundary agree on the meaning of
   unavailable usage.
5. `GP-5.9` `BC-10` can be reclassified from missing evidence to pass or a
   deliberate policy exception.

**Validation:**

1. schema tests for usage/cost evidence
2. live protected run with successful evidence
3. live or simulated unavailable-usage path
4. support-boundary wording check

## 11. GPP-4 - Production-Certified Read-Only Adapter Decision

**Goal:** Decide whether `claude-code-cli` can move from
`Beta (operator-managed)` to production-certified read-only.

**Entry criteria:**

1. `GPP-2` live protected gate is ready.
2. `GPP-3` usage/cost evidence is ready or explicitly resolved.

**Acceptance criteria:**

1. At least three protected clean read-only adapter runs pass.
2. At least one protected fail-closed run proves non-pass behavior.
3. Failure-mode matrix includes auth missing, binary missing, timeout, prompt
   denied, malformed output, policy denied, and redaction checks.
4. Decision artifact chooses one: `promote_read_only`, `keep_operator_beta`,
   or `defer`.
5. Docs, known-bugs, runbook, and support-boundary update in the same PR.

**Validation:**

1. protected gate run artifacts
2. targeted adapter tests
3. support-boundary grep for tier consistency
4. no production write support is implied

## 12. GPP-5 - Repo-Intelligence Workflow Integration

**Goal:** Move repo intelligence from explicit operator handoff toward
governed workflow integration without hidden prompt injection.

**Entry criteria:**

1. `RI-5b` create-only root export remains Beta/operator-managed.
2. No hidden root export, MCP, or `context_compiler` feed is active by default.

**Acceptance criteria:**

1. Workflow context ingestion is explicit opt-in.
2. Context payload carries source paths, line ranges, source hashes, namespace,
   freshness state, and support tier.
3. Missing metadata, stale sources, hash mismatch, or unknown namespace fail
   closed.
4. No MCP tool, root file write, or context compiler auto-feed is introduced
   without an explicit design gate.
5. Support tier remains clear: beta building block or production read-only
   building block candidate, not final platform claim.

**Validation:**

1. valid handoff test
2. stale handoff test
3. missing metadata test
4. disabled-config test
5. negative grep for hidden MCP/root export/context compiler wiring

## 13. GPP-6 - Read-Only Production E2E

**Goal:** Prove the first complete read-only coding automation chain with real
adapter and repo intelligence.

**Target chain:**

```text
repo scan/index/query
-> explicit context handoff
-> protected real adapter
-> governed workflow
-> review_findings or patch_plan artifact
-> evidence timeline
```

**Entry criteria:**

1. `GPP-4` has a production-certified read-only adapter decision or explicit
   protected beta permission for this rehearsal.
2. `GPP-5` workflow context ingestion is ready.

**Acceptance criteria:**

1. At least three clean read-only E2E runs pass.
2. Each run records context source hashes, adapter evidence, policy events,
   artifact path, redaction status, and final state.
3. At least one fail-closed E2E run is recorded.
4. No write or remote side effect occurs.
5. Evidence can be reproduced by another operator following the runbook.

**Validation:**

1. protected E2E run artifacts
2. schema validation
3. event-order assertions
4. runbook reproduction check

## 14. GPP-7 - Controlled Write-Side Production Candidate

**Goal:** Promote local patch/test from rehearsal-only toward a production
candidate under disposable/dedicated worktree controls.

**Entry criteria:**

1. `GPP-6` read-only E2E is ready.
2. Path-scoped ownership remains enforced.

**Acceptance criteria:**

1. Active main worktree is never modified.
2. Diff preview is mandatory before apply.
3. Explicit apply approval is mandatory.
4. Path-scoped write ownership is acquired and released.
5. Targeted tests are explainable.
6. Full-gate fallback is available.
7. Rollback and idempotency are verified.
8. At least three clean controlled write runs pass.
9. At least one conflict/fail-closed run is recorded.

**Validation:**

1. controlled patch/test reports
2. dirty-main guard tests
3. rollback artifact verification
4. path ownership event checks

## 15. GPP-8 - Remote PR Live-Write Promotion Candidate

**Goal:** Move `gh-cli-pr` from preflight/disposable rehearsal toward a
production candidate without granting arbitrary repository write support by
accident.

**Entry criteria:**

1. `GPP-7` controlled write candidate is ready.
2. Disposable sandbox target is defined.

**Acceptance criteria:**

1. `--allow-live-write` remains required before any remote write.
2. Non-disposable or arbitrary production repositories are blocked by default.
3. At least three sandbox live-write rehearsals pass.
4. Each rehearsal creates, verifies, closes, verifies closed, deletes branch,
   and verifies branch deletion.
5. Failure modes cover auth denied, permission denied, branch exists, PR
   creation failed, PR close failed, and branch delete failed.
6. Support boundary distinguishes sandbox rehearsal from arbitrary user repo
   production support.

**Validation:**

1. sandbox live-write artifacts
2. cleanup verification
3. no side effects remaining
4. docs/runbook/known-bugs parity

## 16. GPP-9 - Full Production Matrix and Claim Decision

**Goal:** Decide the general-purpose production claim with complete evidence.

**Entry criteria:**

1. `GPP-1..GPP-8` have explicit pass/defer decisions.
2. Any deferred item is declared non-blocking with support-boundary wording.

**Required matrix:**

1. three clean full chains;
2. one fail-closed full chain;
3. protected real adapter;
4. repo-intelligence context;
5. controlled patch/test;
6. disposable PR rollback;
7. operations/runbook readiness;
8. support docs parity.

**Acceptance criteria:**

1. Full matrix report validates against schema.
2. `BC-1` and `BC-10` are not blocked.
3. `production_platform_claim_decision` emits one of:
   - `promote_general_purpose_production`
   - `promote_general_purpose_beta`
   - `keep_narrow_stable_runtime`
4. If support widens, the same PR updates docs, known bugs, runbook, support
   boundary, examples, and release notes.
5. If support does not widen, the decision explains the blocker and next
   work package.

**Validation:**

1. `python3 scripts/gp5_full_production_rehearsal.py --matrix-file <matrix>`
2. `python3 scripts/gp5_platform_claim_decision.py --output json`
3. full CI
4. wheel-installed packaging smoke
5. protected live-adapter evidence artifacts

## 17. Current Active Work

No runtime/support-widening work is active. `GPP-2` is the current blocked
program head. GPP-2b is tracked in
[#482](https://github.com/Halildeu/ao-kernel/issues/482) as an external/admin
provisioning action. The environment and `main` branch policy are present, but
reviewer protection and `AO_CLAUDE_CODE_CLI_AUTH` must still be completed
before another prerequisite attestation can attempt to unblock `GPP-2`.
GPP-2c is tracked in
[#485](https://github.com/Halildeu/ao-kernel/issues/485) to resolve the
remaining reviewer and credential gate decision. GPP-2d adds
`scripts/live_adapter_gate_attest.py` so the next prerequisite attestation uses
repeatable metadata-only evidence instead of hand-written command snippets.

## 18. Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| Protected environment never appears | Real-adapter production support stays blocked | Keep `claude-code-cli` Beta/operator-managed; do not widen support |
| Local auth mistaken for project-owned evidence | False production claim | Require protected gate artifacts for GPP-4 |
| Usage/cost remains unavailable | BC-10 stays blocked | Add explicit unavailable policy or defer promotion |
| Repo-intelligence hidden injection | Context trust boundary breaks | Explicit opt-in + metadata fail-closed tests |
| Remote PR writes leak to arbitrary repos | Production side effect risk | Disposable guard + explicit allow flag + rollback evidence |
| Full matrix becomes stale | Fake green promotion | Require fresh artifacts from current `origin/main` |

## 19. Tracking Log

| Date | Event | Notes |
|---|---|---|
| 2026-04-25 | GPP-0 issue opened | Issue [#470](https://github.com/Halildeu/ao-kernel/issues/470) created to track the written production-promotion program. |
| 2026-04-25 | GPP-0 branch opened | Branch `codex/gpp0-production-promotion-tracker` and dedicated worktree opened from `origin/main` at `1b8078f`. |
| 2026-04-25 | GPP-0 merged | PR [#471](https://github.com/Halildeu/ao-kernel/pull/471) merged at `f3823be`; tracker is live on `main`. |
| 2026-04-25 | GPP-1 issue opened | Issue [#472](https://github.com/Halildeu/ao-kernel/issues/472) created for protected live-adapter prerequisite attestation. |
| 2026-04-25 | GPP-1 attestation recorded | Live GitHub environment/secret evidence keeps GPP-1 at `blocked_attestation_missing`; GPP-2 remains blocked. |
| 2026-04-25 | GPP-1 merged | PR [#473](https://github.com/Halildeu/ao-kernel/pull/473) merged at `0ad7209`; protected live-adapter prerequisite remains blocked. |
| 2026-04-25 | GPP-1b issue opened | Issue [#474](https://github.com/Halildeu/ao-kernel/issues/474) created for agent operating program contract. |
| 2026-04-25 | GPP-1b contract added | `AGENTS.md`, `.claude/plans/gpp_status.v1.json`, and `scripts/gpp_next.py` make the current program state machine-readable for Codex/Claude operator sessions. |
| 2026-04-25 | GPP-1b merged | PR [#475](https://github.com/Halildeu/ao-kernel/pull/475) merged at `c579089`; status now holds at `GPP-2` blocked. |
| 2026-04-25 | GPP-1c issue opened | Issue [#476](https://github.com/Halildeu/ao-kernel/issues/476) tracks this status closeout so operator sessions do not see stale `GPP-1b active` state. |
| 2026-04-25 | GPP-1d issue opened | Issue [#478](https://github.com/Halildeu/ao-kernel/issues/478) tracks removal of moving authority SHAs from live status so merge commits do not create stale SSOT drift. |
| 2026-04-25 | GPP-1d merged | PR [#479](https://github.com/Halildeu/ao-kernel/pull/479) merged; live authority head is now read from git signals instead of static status text. |
| 2026-04-25 | GPP-2a issue opened | Issue [#480](https://github.com/Halildeu/ao-kernel/issues/480) created to re-attest protected live-adapter prerequisites before any GPP-2 runtime binding. |
| 2026-04-25 | GPP-2a re-attestation recorded | PR [#481](https://github.com/Halildeu/ao-kernel/pull/481) recorded then-current evidence: only `pypi` environment existed and `ao-kernel-live-adapter-gate` secret lookup returned `HTTP 404`; GPP-2 remained blocked. |
| 2026-04-25 | GPP-2b external/admin issue opened | Issue [#482](https://github.com/Halildeu/ao-kernel/issues/482) tracks protected environment, reviewer, and credential provisioning required before `GPP-2` can start. |
| 2026-04-25 | GPP-2b partial provisioning recorded | `ao-kernel-live-adapter-gate` now exists, custom deployment branch policy includes `main`, and admin bypass is disabled. Reviewer protection and `AO_CLAUDE_CODE_CLI_AUTH` remain missing, so #482 stays open and `GPP-2` stays blocked. |
| 2026-04-25 | GPP-2c issue opened | Issue [#485](https://github.com/Halildeu/ao-kernel/issues/485) tracks the remaining protected reviewer and credential gate: add/designate a non-self reviewer or explicitly approve an equivalent release gate, and set `AO_CLAUDE_CODE_CLI_AUTH` without secret readback. |
| 2026-04-25 | GPP-2d issue opened | Issue [#487](https://github.com/Halildeu/ao-kernel/issues/487) tracks a metadata-only attestation tool for repeatable protected gate evidence. |
