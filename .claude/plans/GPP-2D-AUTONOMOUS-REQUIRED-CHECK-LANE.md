# GPP-2D - Autonomous Required-Check Lane

**Status:** planned / design slice - architecture and phased plan, docs only
**Date:** 2026-05-23
**Parent:** `GPP-2 - Protected Live-Adapter Gate Runtime Binding`
**Support impact:** none
**Production platform claim:** false
**Live adapter execution:** false

## 1. Purpose and governance decision

The repo owner has set the GPP-2 end state: a **fully autonomous merge lane**.
Per-PR human approval was a bootstrap-period brake, not the final model. The
end-state merge model is:

```text
AI implementer artifact
  + independent AI reviewer artifact
  + local_gpp_gate evidence
  + ao-release-gate required check (deterministic, repo-owned)
  -> GitHub-native auto-merge
```

Human review is removed for the low-risk lane and retained, via CODEOWNERS, for
a defined high-risk surface set (§5).

This record is the **GPP-2D-1 design slice - documentation only**. It does not
implement the workflow, change branch protection, switch enforce mode, wire any
runtime check, or merge anything. GPP-2 stays `blocked`.

The non-author human-approval flow (the dual-account `@Halildeu` /
`@gladyatore-lab` lane) is hereby recorded as the **bootstrap / fallback** path.
It stays in effect until the autonomous-lane cutover (§6 GPP-2D-5) lands, and it
remains the fallback if the autonomous lane is later paused.

**testai is not required.** The `ao-release-gate` required check is a repo-owned
GitHub Actions job that runs the deterministic decision core in-repo. A
testai-hosted service, an smee.io proxy, an external webhook, or a GitHub App
check-run is **not** required for this lane and is not part of it; that
deployment-protection callback infrastructure stays deferred optional GPP-2C
work.

## 2. The central risk - a self-approving gate

The dominant risk of an autonomous merge lane is a **self-approving gate**: a
pull request that modifies the gate workflow, the gate code, `gpp_status.v1.json`,
the gate payload, or the review evidence so that its own merge evaluates to
`allow_autonomous_merge`. The whole design below is structured to close this.
The safety of the lane rests on `ao-release-gate` being a genuine hard gate that
a bad pull request genuinely cannot pass - which §3 hardens and §6 GPP-2D-4
(success/failure evidence) must prove with a real negative-path failure.

## 3. Architecture

### 3.1 Components

1. **Implementer AI artifact** - records the implementer AI provider and the
   change it produced.
2. **Independent reviewer AI artifact** - `local-ai-review-evidence.v1`, the
   reviewer AI verdict, from a provider different from the implementer.
3. **local_gpp_gate evidence** - `scripts/local_gpp_gate.py` consumes the
   reviewer artifact plus repo state and emits the no-secret
   `local-gpp-gate-evidence.v1` (`operator_may_merge` / `fail_closed`).
4. **ao-release-gate required check** - a new repo-owned GitHub Actions
   workflow `.github/workflows/ao-release-gate.yml` running the deterministic
   decision core (§3.6). The **enforce** job carries the stable,
   branch-protection-pinned name `ao-release-gate` and passes only on
   `allow_autonomous_merge`. The earlier **shadow** job uses the distinct name
   `ao-release-gate-shadow`, so the required-check name `ao-release-gate` is
   never a fail-open advisory check (§3.4, §6).
5. **GitHub-native auto-merge** - `gh pr merge --auto --squash`; GitHub merges
   once required checks pass and branch protection is satisfied.
6. **Branch protection** - requires the `ao-release-gate` check; human review
   removed for the low-risk lane, kept for the high-risk set (§5).

### 3.2 Trusted-base gate (hardening 1)

- The `ao-release-gate` workflow triggers on `pull_request` - **never**
  `pull_request_target` - runs with no secrets and read-only `permissions`, and
  fork-context pull requests fail closed.
- The gate code (`ao_kernel/ao_release_gate.py`), the schemas, and
  `gpp_status.v1.json` are evaluated from the **base / protected ref**, not from
  the pull-request head checkout. The PR head is the diff and evidence under
  inspection; it is never the policy authority. A PR that edits the gate code or
  `gpp_status.v1.json` cannot thereby change the gate that judges it.

### 3.3 Untrusted PR input (hardening 2)

- The release-gate payload is built by the workflow from the **GitHub API**
  (PR number, head SHA, base ref, changed files, check statuses, fork status,
  branch freshness) - never from a PR-committed JSON file. PR-author-supplied
  `allowed_path_prefixes`, `required_checks`, `branch_up_to_date`, or
  `admin_bypass_requested` fields would let a PR self-approve.
- The `local-gpp-gate-evidence.v1` review evidence is treated as **untrusted
  input**: validated against the full `local-gpp-gate-evidence.schema.v1.json`
  and the GPP-2B-3 acceptance profile, and **context-bound** - the gate must
  confirm the evidence is bound to this PR's head SHA, changed-files digest,
  repository, and reviewed slice, and is fresh, so stale, forged, or replayed
  evidence fails closed. The current `local-gpp-gate-evidence.v1` schema has no
  head-SHA / diff-digest / provenance fields; GPP-2D-2 (§6) adds them. Until
  that context-binding lands the required check is weaker than the local gate
  and the lane is not cutover-ready.

### 3.4 Source-pinned required check + high-risk CODEOWNERS (hardening 3)

- Branch protection's required status check must be pinned to the GitHub
  Actions `ao-release-gate` job as its source. If the legacy testai-hosted App
  check-run shares the `ao-release-gate` name, that collision is resolved first
  (pin the source, or move the legacy App check-run to a distinct shadow name)
  so a stale or external check cannot satisfy the requirement.
- The required-check name `ao-release-gate` is **reserved for the enforce job**
  (GPP-2D-3). The shadow job (GPP-2D-2) runs under the distinct name
  `ao-release-gate-shadow` and is never a required check, so branch protection
  can never be satisfied by a fail-open advisory job. GPP-2D-5 verifies the
  required check's source and current enforce behavior before the cutover.
- The gate must not auto-approve changes to itself or to the authority model.
  The **high-risk surface set** keeps human / CODEOWNERS review:
  `.github/**`, `CODEOWNERS`, `AGENTS.md`, `CLAUDE.md`,
  `.claude/plans/gpp_status.v1.json`, the GPP and AO-GATE roadmap/status SSOT
  docs, `ao_kernel/ao_release_gate*.py`, `scripts/ao_release_gate_decision.py`,
  `scripts/local_gpp_gate*.py`, the local-gate and release-gate JSON schemas,
  the deploy/publish workflows, gate host/deploy config, and secret / Vault /
  GitHub App wiring surfaces. These surfaces change the gate itself or the
  governance model; auto-approving them is a self-modification hole.

### 3.5 Check timing

The `ao-release-gate` job must run **after** the CI checks it inspects - via
`needs:` in the same workflow, or by polling for check completion - so it does
not read incomplete check statuses and produce a permanent
`deny_missing_evidence` failure before CI finishes.

### 3.6 What the ao-release-gate job validates and decides

The repo-owned deterministic decision core, run from the base ref, validates:

- **local_gpp_gate evidence** - a present, schema-valid, context-bound
  `local-gpp-gate-evidence.v1` recording `operator_may_merge`.
- **cross-provider review evidence** - the evidence confirms an independent
  reviewer AI of a different provider returned AGREE (`reviewer_agree` and
  `cross_provider_verified`).
- **required tests / checks status** - the PR's required CI checks are
  completed and successful.
- **gpp_status guard** - GPP-2 is `blocked` and the support / production /
  live-adapter guard flags are `false`.
- **scope, secret, and boundary checks** - the existing 18-check
  `build_ao_release_gate_decision` set (diff scope, secret boundary, admin
  bypass, fork/event boundary, etc.).

GPP-2D-2 **extends** the current decision core: today's
`build_ao_release_gate_decision` does not yet read the local_gpp_gate or
cross-AI review evidence (the GPP-2B-3 `cross_ai_review` check is design-only),
so wiring that evidence validation in is part of GPP-2D-2.

Decision mapping for the job outcome:

- `allow_autonomous_merge` -> the `ao-release-gate` job **succeeds**.
- any `deny_*`, missing evidence, reviewer non-AGREE / REVISE, scope violation,
  or secret violation -> the `ao-release-gate` job **fails** (fail-closed).

## 4. forbidden_actions reconciliation - the authority model

The GPP SSOT `forbidden_actions` keeps "treat Codex or Claude output as release
authority". The autonomous lane does not violate it. **AI output is evidence,
not authority.** Raw Codex/Claude output may only be a schema-valid,
context-bound, no-secret evidence *input* to the gate; it never decides a merge.

**Release authority = the repo-owned `ao-release-gate` required check plus
GitHub branch-protection enforcement.** Authority lives in GitHub branch
protection plus the deterministic in-repo gate plus the fail-closed evidence
chain - never in an AI verdict. The SSOT `forbidden_actions` reconciliation
wording is recorded in GPP-2D-7 (closeout), not this design slice.

## 5. Human review model

- **Low-risk lane:** no per-PR human review. The `ao-release-gate` required
  check plus the existing CI required checks gate the merge; GitHub-native
  auto-merge completes it.
- **High-risk lane:** the high-risk surface set (§3.4) keeps CODEOWNERS /
  human review. A PR touching any high-risk path still needs a non-author
  human code-owner approval.
- The first cutover does **not** remove human review wholesale; it removes it
  only for the low-risk lane. Widening the autonomous lane further is a later,
  separate decision.

## 6. Phased plan

| Slice | Scope | Gate | Class |
|---|---|---|---|
| **GPP-2D-1** | This design doc - governance decision, architecture, the three hardenings, the authority model, phased plan. | docs only | agent |
| **GPP-2D-2** | `.github/workflows/ao-release-gate.yml` standing the gate up in **shadow** under the job name `ao-release-gate-shadow`: trusted-base gate, API-built payload, the decision-core wiring (§3.6) including the `local-gpp-gate-evidence.v1` context-binding schema extension; the job runs and reports the decision but always succeeds (advisory) and is never a required check; workflow tests. | code + schema + test | agent |
| **GPP-2D-3** | Introduce the final **enforce** job under the branch-protection-pinned name `ao-release-gate`: a `deny_*` / fail-closed decision makes the job fail; the fail-open `ao-release-gate-shadow` job is retired. Still not a required check until the cutover. | code + test | agent |
| **GPP-2D-4** | success / failure real-PR evidence: one positive pull request the job passes, one negative pull request the job fails. | operator action + agent verification | operator-gated |
| **GPP-2D-5** | operator branch-protection cutover: require the source-pinned `ao-release-gate` job, admin bypass disabled, auto-merge enabled, high-risk CODEOWNERS review. | operator action | operator-gated |
| **GPP-2D-6** | auto-merge smoke: a low-risk PR auto-merges on green required checks; verify a high-risk PR still needs human review. | operator action + agent verification | operator-gated |
| **GPP-2D-7** | AO-GATE-9 GPP-2 closeout: SSOT update, `forbidden_actions` reconciliation, supersede the bootstrap approval flow. | docs | agent (gated on the chain) |

GPP-2D-2 and GPP-2D-3 are agent-executable code slices; the shadow-then-enforce
split lets the job be observed on real pull requests before it can fail one.
GPP-2D-4 onward require operator actions; the agent collects no fabricated
evidence and verifies real evidence after each operator step.

## 7. Hard stops / non-goals

- No `--admin` merge; no branch-protection mutation by the agent - the
  GPP-2D-5 cutover is an operator action.
- No `ao-release-gate` enforce-mode runtime change and no real check-run /
  auto-merge configuration in this design slice.
- No support widening, no production platform claim, no live adapter
  execution; `gpp_status.v1.json` guard flags stay `false`.
- GPP-2 stays `blocked` until the success/failure evidence (GPP-2D-4), the
  cutover (GPP-2D-5), and the AO-GATE-9 closeout (GPP-2D-7) all exist.
- No fabricated or operator-substituted evidence; GPP-2D-4 evidence is
  collected on real pull requests and verified by the agent.
- No testai, smee.io, GitHub App, webhook, or deployment-protection callback
  work; that stays deferred optional GPP-2C infrastructure.
- No long-lived secret / PAT / PEM / webhook-secret value in workflows,
  schemas, tests, or artifacts; the `ao-release-gate` workflow uses only the
  ephemeral GitHub Actions `GITHUB_TOKEN` with minimal read-only permissions.

## 8. Agent / operator boundary

| Step | Agent does | Operator does |
|---|---|---|
| GPP-2D-1, GPP-2D-2, GPP-2D-3 | full (design, workflow, schema, tests, Codex review) | - |
| GPP-2D-4 evidence | build the positive/negative PR pair, verify captured evidence | open / observe the real PRs as required |
| GPP-2D-5 cutover | write the exact branch-protection runbook, verify post-cutover | configure the GitHub ruleset / branch protection |
| GPP-2D-6 auto-merge smoke | prepare the smoke PRs, verify outcomes | observe; confirm high-risk still gates |
| GPP-2D-7 closeout | write the `gpp_status` / SSOT closeout PR | confirm the evidence chain is complete |

## 9. Follow-up

The autonomous required-check lane closes GPP-2 once the GPP-2D-4
success/failure evidence, the GPP-2D-5 cutover, and the GPP-2D-7 AO-GATE-9
closeout exist, with `support_widening`, `production_platform_claim`, and
`live_adapter_execution` all still `false`. The lane does not by itself widen
support or claim production readiness; it changes only the merge-governance
mechanism from bootstrap human approval to a deterministic repo-owned required
check plus GitHub-native auto-merge, with the high-risk surface set still
human-gated.
