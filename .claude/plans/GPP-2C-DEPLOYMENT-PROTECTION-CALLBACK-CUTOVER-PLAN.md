# GPP-2C - Deployment-Protection Callback / Protected-Workflow Cutover Plan

**Status:** planned / planning slice - chain mapping + operator runbook only
**Date:** 2026-05-22
**Parent:** `GPP-2 - Protected Live-Adapter Gate Runtime Binding`
**Pivot record:** `.claude/plans/GPP-2ag-LOCAL-AI-REVIEW-GATE-PIVOT.md`
**Roadmap board:** `.claude/plans/AO-GATE-ROADMAP-TODO.md`
**Support impact:** none
**Production platform claim:** false
**Live adapter execution:** false

## 1. Purpose

The GPP-2ag pivot split `GPP-2` into three slices:

```text
GPP-2A: local AI review gate evidence            - DONE
GPP-2B: ao-release-gate required check / mapping  - DONE (PR #580-#583)
GPP-2C: deployment-protection callback / cutover  - this slice family
```

This record is the **GPP-2C-1 planning slice**. GPP-2C is the final GPP-2 slice
family - it carries the remaining protected-runtime evidence chain to closure.
This record maps that chain step by step, classifies every step as
agent-executable, operator-gated, or decision-blocked, frames the open
decisions, sketches the operator runbook, and defines the phased GPP-2C-1..7
plan.

This slice is **documentation only**: it does not implement the chain, change
branch protection, configure webhooks or GitHub Apps, switch enforce mode,
execute live adapters, produce evidence files, widen support, or claim
production readiness. GPP-2 stays `blocked`.

**Honest boundary up front.** GPP-2 cannot be closed by an autonomous agent
alone. The callback evidence (C3), protected-workflow rerun (C4), enforce-mode
evidence (C6), and branch-protection cutover (C7) require real GitHub events on
real deployments / pull requests and GitHub repository-settings changes -
operator actions the agent does not perform. Fabricating that evidence would
violate No Fake Work and the GPP operating contract. GPP-2C-1's job is to make
every gated step a single, well-specified operator action and to execute
autonomously everything that genuinely can be.

## 2. Source snapshot (2026-05-22)

- `python3 scripts/gpp_next.py`: GPP-2 `blocked`; `support_widening_allowed`,
  `production_platform_claim_allowed`, `live_adapter_execution_allowed` all
  `false`.
- Exit decision:
  `webhook_delivery_chain_and_shadow_dry_run_check_run_collected_policy_callback_and_cutover_blocked_no_support_widening`.
- Authority ref `origin/main` at `7a04f9b`; planning branch even with
  `origin/main` (`0 0`).
- Collected evidence (GPP-2ag §2): policy + `ao-release-gate` decision cores,
  webhook runtimes, containers, GHCR publish, Cloud Run paths, vault secret-id
  contract, operator host bundle, no-secret health probe, public HTTPS health
  evidence, GitHub App webhook delivery chain evidence (via a smee.io
  non-production proxy), `ao-release-gate` shadow dry-run check-run evidence,
  shadow/enforce conclusion-mode support (GPP-2B-4).
- `docs/evidence/ao-gate/` is the roadmap's default evidence target path but is
  **not yet a real evidence surface** - it does not exist on disk. `.ao/evidence/`
  is gitignored, so any evidence artifact `gpp_status.v1.json` references (for
  example the AO-GATE-4 internal-gate-host health artifact) is local-only and is
  not present in a fresh checkout. GPP-2C-1 records target paths only; it
  produces no evidence file.

## 3. Remaining chain - blockers C1-C7

| # | Blocker | Class | Depends on |
|---|---|---|---|
| C1 | policy App slug reconciliation | decision -> protected-contract edit | - |
| C2 | production-suitable callback topology | decision (infrastructure) | - |
| C3 | deployment-protection callback review evidence | operator-gated | C1, C2 |
| C4 | protected-workflow evidence rerun | operator-gated | C1, C2 (paired with C3) |
| C5 | `ao-release-gate` Category-C (cross-AI-review) parity | decision (conditional) | - |
| C6 | enforce-mode positive + negative path evidence | operator-gated | C5 |
| C7 | branch-protection / ruleset cutover | operator-gated | C3, C4, C6 |

**C1 - policy App slug reconciliation.** The repo pins the
protected-environment / deployment-protection App slug as
`ao-kernel-live-adapter-gate` in `ao_kernel/live_adapter_gate.py`
(`PROTECTED_ENVIRONMENT_NAME`, `REQUIRED_DEPLOYMENT_PROTECTION_APP_SLUG`) and in
`ao_kernel/defaults/schemas/live-adapter-gate-environment.schema.v1.json` (two
`const`s). The GitHub App actually created is
`ao-kernel-live-adapter-gate-policy`. The two must agree before any callback
evidence is meaningful. This is **not an ordinary config edit** - the slug is
part of the protected-gate attestation acceptance contract. Resolution is
decision-bound (§4.1); the execution is an agent-doable protected-contract edit
**only** as an isolated GPP-2C-3 PR that migrates the constant / schema / test /
attest-CLI-default / docs surface and **nothing else** (no App config, webhook,
callback, dispatch, or `gpp_status` change).

**C2 - production-suitable callback topology.** Webhook delivery evidence was
collected through historical dry-run infrastructure (`smee.io` and hosted
health probes), but the operator decision for the near-term GPP-2 path is to
remove `testai.acik.com/ao-gate` from the active scope. Public health evidence
remains historical operator-infra evidence; it is not webhook-reachability
evidence and it is not required for GPP-2B. If production callback enforcement
is reopened later, C2 becomes a separate deferred GPP-2C topology decision and
can choose `testai` or another owner-controlled endpoint at that time.

**C3 - deployment-protection callback review evidence.** After C1 + C2: a
controlled `deployment_protection_rule` event (per AO-GATE-7 - `workflow_dispatch`
on `live-adapter-gate.yml`, `target_ref=main`, only when `gpp_next.py` and
`gpp_status.v1.json` both allow the evidence slice); the policy service
validates payload + signature and produces a callback decision. Exit: callback
review evidence, or fail-closed evidence. Inactive / denied / timed-out /
cancelled / failing protection is fail-closed evidence, not approval.
Operator-gated.

**C4 - protected-workflow evidence rerun.** Paired with C3: the same controlled
dispatch produces protected-workflow run evidence confirming live execution
stays governed (run id, policy response, no live adapter execution). C4 runs
**with** C3, not after the cutover. Operator-gated.

**C5 - `ao-release-gate` Category-C parity (conditional).** GPP-2B-3 added the
attested-review-evidence acceptance profile as **design-only** - a future
`cross_ai_review` check, with no `ao_release_gate.py` wiring. Before the cutover
makes `ao-release-gate` the required check, GPP-2C must record an explicit
decision: either (i) ingest `cross_ai_review` into the `ao-release-gate`
runtime so the required check is as strong as the local gate on the
cross-AI-review dimension, or (ii) explicitly defer - the current 18-check
release gate is accepted as sufficient and cross-AI review stays a HARD-RULE
process discipline, not a mechanical GitHub gate. This is a decision (§4.3),
not automatically a blocker; but it must be a recorded decision before C6 / C7.

**C6 - enforce-mode positive + negative path evidence.** A real PR observed
under `conclusion_mode=enforce`: a passing path (`success`) and a failing path
(`failure`) on actual pull requests. The shadow dry-run check-run evidence
already collected is not sufficient for cutover. Operator-gated (real PRs plus a
runtime enforce-mode flip). Depends on C5.

**C7 - branch-protection / ruleset cutover.** Make `ao-release-gate` a required
status check on `main` via GitHub branch-protection / ruleset, with admin
bypass disallowed; prove merge is blocked without a pass and allowed with one.
Operator-gated - a GitHub repository-settings change; the agent does not mutate
branch protection. Depends on C3, C4, C6.

## 4. Open decisions (resolved in GPP-2C-2)

### 4.1 App slug (C1)

- **Option A** - rename the GitHub App `ao-kernel-live-adapter-gate-policy` ->
  `ao-kernel-live-adapter-gate` (operator action in GitHub App settings; no
  repo change).
- **Option B** - migrate the repo constants + schema `const`s + tests +
  attest-CLI defaults + docs from `ao-kernel-live-adapter-gate` to
  `ao-kernel-live-adapter-gate-policy` (agent code PR, GPP-2C-3).

Resolution deferred to GPP-2C-2 plus a Codex consultation.

### 4.2 Callback topology (C2)

The production callback path is removed from the active GPP-2B scope. `testai`
is not selected as the current production webhook endpoint, and the agent must
not repoint GitHub Apps to it in this slice. Any production callback topology
decision is deferred to a later GPP-2C initiative.

### 4.3 Category-C parity (C5)

Decide (i) runtime ingestion of `cross_ai_review` into `ao-release-gate` vs
(ii) explicit deferral with cross-AI review kept as process discipline. Either
way the decision must be recorded before C6 / C7. Deferred to GPP-2C-2 plus a
Codex consultation.

### 4.4 Resolution (GPP-2C-2)

Resolved via Codex consultation (thread `019e511b`).

**§4.1 App slug - Option A (rename the GitHub App).** The protected-environment
and deployment-protection contract is established across the repo on the
canonical `ao-kernel-live-adapter-gate`: `ao_kernel/live_adapter_gate.py`
(`PROTECTED_ENVIRONMENT_NAME`, `REQUIRED_DEPLOYMENT_PROTECTION_APP_SLUG`), the
two `const`s in `live-adapter-gate-environment.schema.v1.json` (the protected
environment `name` and the deployment-protection app slug),
`scripts/live_adapter_gate_attest.py`'s CLI default, plus tests and docs.
Migrating that whole surface to a `-policy` suffix (Option B) is an
unnecessarily wide blast radius on a protected-gate attestation contract.
Resolution: the operator renames the policy GitHub App slug
`ao-kernel-live-adapter-gate-policy` -> `ao-kernel-live-adapter-gate`; the repo
constants / schema / tests / defaults are **not** migrated. Single guard: if a
GitHub App slug collision makes the rename impossible, that collision is
resolved first and only then is Option B reconsidered. Operator verification
after the rename: the App slug and the environment's deployment-protection rule
reference the same App id / slug. GPP-2C-3 records this as an operator action;
under Option A it carries no repo code change.

**§4.2 Callback topology - testai removed from the active scope.** The operator
decision is to keep `testai.acik.com/ao-gate` out of the active GPP-2B / near-term
release-governance path. The `testai` route may remain as historical public
health evidence and optional future infrastructure, but it is **not** selected
as the production callback topology for this slice and it must not be treated as
a remaining active blocker for the simplified local/operator-controlled model.
No GitHub App webhook URL is repointed to `testai` in this slice, and no
deployment-protection callback evidence is required for GPP-2B.

The active near-term path is the no-testai model: cross-provider AI review,
non-author GitHub approval, `local_gpp_gate.py` evidence, and the
`ao-release-gate` mapping / conclusion matrix. `smee.io` remains only historical
dry-run evidence. If the project later reopens public callback enforcement, that
work is a separate deferred GPP-2C / production-topology initiative and can
choose `testai` or another owner-controlled endpoint at that time.

**§4.3 Category-C parity - explicit deferral.** `cross_ai_review` is **not**
taken into the mechanical `ao-release-gate` required check for GPP-2C. The
current 18-check `ao-release-gate` is accepted as sufficient for the C6
enforce-mode evidence and the C7 cutover. Cross-AI peer review remains a
HARD-RULE operator / process discipline (every GPP PR is reviewed by a
different provider). The GPP-2B-3 attested-review-evidence acceptance-profile
schema is **preserved** as a future design artifact - this is a deferral of
runtime ingestion, not a reversal of GPP-2B-3. Runtime ingestion of
`cross_ai_review` into `ao_release_gate.py` is a separate later slice, gated
behind GPP-2 unblock, because it would code into the currently blocked GPP-2
runtime surface.

All three resolutions keep GPP-2 `blocked`; GPP-2C-2 makes no GitHub App,
webhook, branch-protection, ruleset, or runtime change.

## 5. Operator runbook (gated steps - sketch)

GPP-2C-1 records the shape; GPP-2C-2/4/5/6 refine each into an exact runbook
once the §4 decisions land.

- **C3 / C4 (callback + protected-workflow evidence):** confirm policy webhook
  config active -> `workflow_dispatch live-adapter-gate.yml target_ref=main`
  only when `gpp_next.py` allows the slice -> capture webhook id,
  signature-verified flag, callback decision / POST result, workflow run id ->
  record callback review or fail-closed evidence.
- **C6 (enforce-mode evidence):** with `conclusion_mode=enforce`, exercise one
  passing and one failing real PR -> capture both `github_check_run.conclusion`
  outcomes.
- **C7 (branch-protection cutover):** configure the `main` ruleset to require
  the `ao-release-gate` check, admin bypass disallowed -> prove merge blocked
  without a pass and allowed with one -> record ruleset evidence.

Evidence target path: `docs/evidence/ao-gate/` (per the roadmap table). No
evidence file is created by GPP-2C-1.

## 6. Phased GPP-2C plan

| Slice | Scope | Gate | Class |
|---|---|---|---|
| **GPP-2C-1** | This planning record. | docs only | agent |
| **GPP-2C-2** | Resolve §4.1 / §4.2 / §4.3 via Codex consultation; record that `testai.acik.com/ao-gate` is removed from the active GPP-2B scope and deferred as optional future callback infrastructure. Resolved in §4.4. | docs | agent |
| **GPP-2C-3** | Execute the C1 slug resolution. Option A: operator App rename + attestation note. Option B: agent migration of constants / schema / tests / attest-CLI defaults / docs - isolated PR, no runtime / App / webhook change. | docs (+ code/schema/test if Option B) | agent / operator-decision-bound |
| **GPP-2C-4** | C3 + C4: production callback review evidence + protected-workflow rerun evidence. | operator action + agent verification | operator-gated |
| **GPP-2C-5** | C6: `ao-release-gate` enforce-mode positive + negative real-PR evidence. | operator action + agent verification | operator-gated |
| **GPP-2C-6** | C7: branch-protection / ruleset cutover, no admin bypass. | operator action + agent verification | operator-gated |
| **GPP-2C-7** | AO-GATE-9 closeout - `gpp_status.v1.json` + `GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md` update, only after the full evidence chain exists. | docs | agent (gated on the chain) |

GPP-2C-1 and GPP-2C-2 are agent-executable docs slices and may proceed now.
GPP-2C-3 is agent-executable only after §4.1. GPP-2C-4 onward require operator
actions; the agent collects no fabricated evidence and verifies real evidence
after each operator step.

## 7. Hard stops / non-goals

- No GitHub App / webhook URL / branch-protection / ruleset change in any
  **agent** slice.
- No `ao-release-gate` enforce-mode runtime flip by the agent.
- No live adapter execution; no protected-workflow dispatch by the agent (the
  C3 / C4 dispatch is an operator action).
- No `gpp_status.v1.json` guard-flag change; GPP-2 stays `blocked` until the
  full chain plus AO-GATE-9.
- No fabricated or operator-substituted evidence - operator-gated evidence is
  collected by the operator and verified by the agent (the GPP operating
  contract holds that local / operator smoke is not project-owned production
  evidence).
- No `--admin` merge; no support widening; no production-platform claim.
- No secret / token / PAT / PEM / webhook secret in docs, schemas, tests, or
  artifacts.

## 8. Agent / operator boundary

| Step | Agent does | Operator does |
|---|---|---|
| GPP-2C-1, GPP-2C-2 | full (docs, decisions, Codex consult, verification) | - |
| GPP-2C-3 (slug) | Option B: the code / schema / test / doc PR | Option A: rename the GitHub App |
| C2 topology | frame options, verify reachability, write the route map | choose / provision the production endpoint |
| C3 / C4 evidence | pre-flight checks, write the runbook, verify captured evidence | trigger the controlled `deployment_protection_rule` event |
| C6 enforce evidence | write the runbook, verify | flip enforce mode, exercise the real PRs |
| C7 cutover | write the runbook, verify post-cutover | configure the GitHub ruleset |
| GPP-2C-7 closeout | write the `gpp_status` / status-doc update PR | confirm the evidence chain is complete |

## 9. Follow-up

GPP-2C closes GPP-2 once C1-C7 evidence exists and AO-GATE-9 records it with
`support_widening`, `production_platform_claim`, and `live_adapter_execution`
all still `false`. GPP-2C does not by itself widen support or claim production
readiness.
