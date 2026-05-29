# AO-MA-10 - Low-Risk Autonomous Merge Lane Cutover Plan

**Status:** low-risk live autonomy accepted / high-risk consensus gated
**Date:** 2026-05-27
**Parent:** AO-MA-1 multi-agent orchestration design
**Depends on:** AO-MA-8 shadow smoke and AO-MA-9 evidence-chain wiring
**Support impact:** none
**Production platform claim:** false
**Live adapter execution:** false

## Purpose

AO-MA-10 records the cutover plan for making **low-risk pull requests**
mergeable without per-PR human intervention while preserving fail-closed
governance for high-risk changes.

The target operating model is:

```text
operator goal
  -> orchestrator task graph
  -> parallel worker agents in owned worktrees
  -> independent reviewer + verifier artifacts
  -> integrator PR
  -> local_gpp_gate evidence validation
  -> ao-release-gate required check
  -> merge agent performs gh pr merge when all branch-protection gates pass
```

The original AO-MA-10 planning slice was **planning-only**. Successor slices
have since activated the low-risk lane through the repo-owned GitHub Actions
merge executor while keeping high-risk changes fail-closed behind
`ao-release-gate` and GitHub ruleset requirements. AI output is still evidence,
not release authority.

## Current accepted low-risk state

AO-MA-10q workflow run `26633091281` is the accepted live evidence for the
low-risk lane:

- disposable PR: [#737](https://github.com/Halildeu/ao-kernel/pull/737);
- required checks: observed and passed, including source-pinned
  `ao-release-gate-technical` and `ao-release-gate-review`;
- merge actor: `app/github-actions`;
- merge command: attempted by the repo-owned workflow executor;
- human approval: not required for the eligible low-risk PR;
- admin bypass: not used;
- guard flags: `support_widening=false`, `production_platform_claim=false`,
  `live_adapter_execution=false`.

The local operator-shell AO-MA-10a0 snapshot can still report `blocked` when the
viewer is `Halildeu/admin`; that is a local operator context signal, not a
contradiction of the accepted workflow-executor evidence. Current live low-risk
readiness is proven only by the pair of checks:

```text
AO-MA-10A0/A1 ready evidence inside the workflow context
  + AO-MA-10q merged-smoke evidence
```

## Three-Provider Consultation Result

The first implementation order was reviewed after AO-MA-10 landed.

| Provider | Result | Material finding |
|---|---|---|
| Codex / OpenAI | REVISE | Do not jump directly to merge-agent implementation. First record live GitHub readiness truth, then add a separate autonomous eligibility checker, then integrate the release gate, then run negative and positive smoke. |
| Claude / Anthropic | REVISE | Low-risk classification must not be trusted from a PR-authored artifact. The classifier must run from protected/base-ref code in GitHub Actions, and release-gate payload/decision wiring must exist before any positive smoke. |
| MiniMax | unavailable | Desktop app exists, but the consultation request was blocked by provider/gateway policy. MiniMax remains a provider-integration prerequisite before it can be mandatory in high-risk ping-pong consensus. |

The revised sequence is therefore fail-closed:

```text
AO-MA-10a0  GitHub readiness snapshot (read-only, this slice)
AO-MA-10a1  autonomous_merge_eligibility checker (separate from RiskClassifier)
AO-MA-10a2  context-bound evidence bundle + registered-provider consensus schemas (recorded)
AO-MA-10b   ao-release-gate payload + decision integration
AO-MA-10d   negative fail-closed suite before any real merge
AO-MA-10h   high-risk cross-provider supersession contract
AO-MA-10i   high-risk supersession decision-core validator
AO-MA-10j   required-check runtime high-risk supersession wiring
AO-MA-10k   disposable real-PR high-risk smoke
AO-MA-10c   merge-agent identity + dry-run executor
AO-MA-10l   positive disposable low-risk autonomous merge smoke
AO-MA-10m   activation/cutover
```

AO-MA-10a0 is deliberately first because GitHub branch protection, rulesets,
source-pinned required checks, CODEOWNERS, and merge actor permission are the
actual enforcement surface. The readiness snapshot is evidence only; it does not
change repository settings.

## Authority Model

AI output is evidence, not release authority.

Release authority remains:

```text
ao-release-gate + GitHub ruleset
```

The merge agent is an executor, not an authority. It may merge only after the
repo-owned required check and GitHub branch protection are satisfied. It must
not use `--admin`, add bypass actors, weaken rulesets, or treat model output as
approval.

## Lane Split

AO-MA-10 defines two lanes.

| Lane | Purpose | Merge behavior |
|---|---|---|
| Low-risk autonomous lane | Small, bounded, non-authority changes that satisfy schema-pinned criteria. | Merge agent may merge after required checks pass. |
| High-risk consensus lane | Changes touching governance, release authority, workflows, CODEOWNERS, security, runtime adapters, support boundaries, or production claims. | No silent auto-merge. Cross-provider ping-pong is required; escalation occurs after bounded rounds. |

## Low-Risk Criteria

The low-risk criteria are schema-pinned in
`.claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.v1.json`.
They are not prose-only.

Low-risk candidates must satisfy all of the following:

1. Changed paths are inside the allowed low-risk path prefixes.
2. Changed paths do not match any prohibited path pattern.
3. `ao-release-gate` required check succeeds from the source-pinned GitHub
   Actions integration. Under the dual-check migration, the future dry-run
   eligibility checker treats source-pinned `ao-release-gate-technical` plus
   source-pinned `ao-release-gate-review` as the safe required-check set; the
   legacy `ao-release-gate` compatibility wrapper is not sufficient by itself.
4. All required CI checks pass.
5. A cross-provider reviewer artifact is present and context-bound to the PR
   `head_sha`, `base_ref`, `diff_digest`, and changed file set.
6. A verifier artifact passes deterministic checks.
7. `local_gpp_gate` accepts the local/process evidence.
8. No secrets, live adapter execution, support widening, production platform
   claim, ruleset mutation, CODEOWNERS bypass, or admin merge is requested.

Examples of allowed low-risk prefixes:

- `.claude/plans/AO-MA-*.md`
- `.claude/plans/AO-MA-*.v1.json`
- `ao_kernel/defaults/schemas/ao-ma-*.json`
- `tests/test_ao_ma*.py`
- `tests/fixtures/ao_ma_*/`
- `docs/evidence/`
- `local-ai-review-evidence.v1.json`

Examples of prohibited paths:

- `.github/**`
- `.github/CODEOWNERS`
- `AGENTS.md`
- `CLAUDE.md`
- `.claude/plans/gpp_status.v1.json`
- release-gate and local-gate runtimes or schemas
- public SDK signatures
- deployment, secret, Vault, GitHub App, or workflow wiring
- support-boundary or production-claim documents

## High-Risk Ping-Pong

High-risk PRs require bounded cross-provider consensus. The autonomous loop is
not unbounded:

- Required providers: OpenAI + Anthropic.
- Optional registered provider: MiniMax, promoted to mandatory only after its
  callable transport is verified and schema-pinned in a later slice.
- Maximum autonomous revise rounds: `3`.
- If consensus is not reached within the round budget, the lane stops and
  escalates to a human/operator decision.
- A single model `AGREE` is never enough for high-risk merge.
- Same-provider self-review is rejected.
- Missing reviewer or verifier evidence blocks merge.

## AO-MA-10h High-Risk Supersession Contract

AO-MA-10h records the future contract for replacing mandatory human/codeowner
review on high-risk PRs with deterministic validation of cross-provider AI
consensus evidence.

This contract does not activate the path. It records the narrow acceptance
boundary for a later runtime slice:

```text
path_sensitive_human_review satisfied when:
  current non-author/codeowner approval exists
  OR valid high-risk cross-provider supersession evidence exists
```

The future supersession evidence must be context-bound to the current PR, must
include distinct `openai` and `anthropic` provider verdicts, must be unanimous
`AGREE`, and must keep `support_widening`, `production_platform_claim`,
`live_adapter_execution`, and `ai_output_release_authority` false.

AO-MA-10h intentionally does not mutate `.github/**`, CODEOWNERS, rulesets,
branch protection, `ao_release_gate.py`, `gpp_status.v1.json`, live adapters,
testai, smee, Vault, or GitHub App configuration.

## Merge Agent Activation Lock

The merge agent is active only for eligible low-risk PRs under the repo-owned
workflow executor model. The original AO-MA-10 plan receipt now marks the
low-risk activation prerequisites that were proven by successor slices as
`done`; high-risk autonomous supersession remains gated and requires separate
evidence.

The activation chain proved:

1. Low-risk path/risk classifier implementation.
2. CODEOWNERS or ruleset model compatible with low-risk autonomy.
3. Merge-agent identity and permissions (`github-actions[bot]` /
   `app/github-actions`).
4. Positive low-risk autonomous merge smoke (#737).
5. Negative high-risk blocked smoke.
6. Stale-evidence blocked smoke.
7. Same-provider review blocked smoke.
8. Missing-verifier blocked smoke.
9. `--admin` and bypass actors absent.
10. A cutover/evidence record confirming no support widening, no production
    platform claim, and no live adapter execution.

AO-MA-10 is therefore live for eligible low-risk PRs. It is not a production
platform claim and does not authorize live adapter execution or support
widening.

## AO-MA-10a0 GitHub Readiness Snapshot

AO-MA-10a0 adds a read-only snapshot artifact:

```text
.claude/plans/AO-MA-10A0-GITHUB-READINESS-SNAPSHOT.v1.json
```

It is generated by:

```text
scripts/ao_ma10_github_readiness_snapshot.py
```

The script uses GitHub API reads only. It records:

- repository merge settings, including whether native auto-merge is enabled;
- branch protection required review and required-check configuration;
- ruleset bypass actors and default-branch rules;
- whether `ao-release-gate` is a source-pinned required check in the
  **GitHub ruleset authority surface**; legacy branch-protection checks are
  recorded but are not sufficient for AO-MA-10 readiness;
- CODEOWNERS broad-default and governance-surface ownership;
- current gh actor permission class;
- GitHub API collection errors, including repository settings, viewer identity,
  permissions, branch protection, rulesets, branch rules, and CODEOWNERS reads,
  which are blockers rather than silent defaults.
- whether the broader SSOT claims a ruleset-required `ao-release-gate` check
  while the live GitHub API snapshot does not show that rule.

The committed AO-MA-10a0 artifact is a historical local operator-shell snapshot.
It was `blocked`, which was the correct fail-closed state for that context. It
is no longer the only current live evidence because AO-MA-10q produced a
workflow-context readiness + merged-smoke artifact. Historical recorded
blockers:

1. `ao_release_gate_required_check_missing`
2. `legacy_required_review_blocks_low_risk_autonomy`
3. `merge_actor_admin_permission_observed`

Recorded warnings:

1. `repository_auto_merge_disabled_merge_agent_direct_mode_required`
2. `some_nominal_low_risk_prefixes_still_codeowned`

These historical blockers explain why the lane pivoted to the repo-owned
workflow executor. Historical GPP records remain useful audit evidence, but
the accepted low-risk readiness proof is AO-MA-10q run `26633091281`.

## AO-MA-10a1 Autonomous Merge Eligibility Checker

AO-MA-10a1 adds a deterministic read-only checker:

```text
scripts/ao_ma10_autonomous_merge_eligibility.py
```

and records the current fail-closed evidence artifact:

```text
.claude/plans/AO-MA-10A1-AUTONOMOUS-MERGE-ELIGIBILITY.v1.json
```

The checker consumes the AO-MA-10a0 GitHub readiness snapshot and a candidate
changed-file set. It does not call GitHub write APIs, mutate branch protection,
change CODEOWNERS, alter workflows, or merge PRs.

AO-MA-10a1 requires all of the following before returning
`ready_for_low_risk_dry_run`:

1. The AO-MA-10a0 snapshot has no blockers and reports
   `readiness.decision=ready_for_dry_run`.
2. `ao-release-gate-technical` is present as a source-pinned GitHub Actions
   required check in the default-branch ruleset.
3. `ao-release-gate-review` is present as a source-pinned GitHub Actions
   required check in the default-branch ruleset.
4. Ruleset bypass actors are empty.
5. Legacy global PR review and code-owner review requirements are disabled for
   the low-risk lane; high-risk human review must instead be enforced through
   `ao-release-gate-review`.
6. The merge actor is a dedicated non-admin actor with no admin-write
   capability observed.
7. Candidate changed files are non-empty, repo-relative, allowed by the
   AO-MA-10 low-risk prefixes, do not match prohibited patterns, and do not
   match repo-owned `HIGH_RISK_PATH_PATTERNS` from `ao_kernel.ao_release_gate`.
8. Release authority and guard flags remain unchanged:
   `ao-release-gate+github-ruleset`, AI output is not release authority, and
   support widening / production platform claim / live adapter execution stay
   false.

The committed A1 artifact is a historical local operator-shell artifact. In the
accepted AO-MA-10q run, A1 reported `ready_for_low_risk_dry_run` for the
disposable low-risk PR before the merge executor ran.

## AO-MA-10a2 Evidence Bundle + Provider Consensus Schemas

AO-MA-10a2 records the context-bound evidence contract for later release-gate
integration. It adds:

```text
ao_kernel/defaults/schemas/ao-ma-10-provider-consensus.schema.v1.json
ao_kernel/defaults/schemas/ao-ma-10-evidence-bundle.schema.v1.json
scripts/ao_ma10_evidence_bundle.py
```

The provider consensus artifact records one registered provider's verdict and
the exact context binding. The evidence bundle aggregates registered provider
verdicts and requires the current hard baseline providers:

```text
openai + anthropic
```

MiniMax remains registered but optional until its callable transport is verified
and schema-pinned in a later provider-integration slice.

AO-MA-10a2 is still read-only. It does not mutate GitHub settings, activate a
merge agent, integrate `ao-release-gate`, or execute an autonomous merge. It
creates the evidence shape that AO-MA-10b can later consume.

## AO-MA-10b Release-Gate Payload + Decision Integration

AO-MA-10b wires the AO-MA-10a2 evidence bundle into the existing
`ao-release-gate` decision core without activating the merge agent.

The integration adds six decision checks:

```text
ao_ma10_autonomous_request
ao_ma10_evidence_bundle
ao_ma10_evidence_bundle_schema
ao_ma10_consensus
ao_ma10_context_bound
ao_ma10_authority_boundary
```

The checks are backward-compatible:

- existing `ao-release-gate` decisions do not require an AO-MA-10 bundle unless
  `payload.low_risk_autonomous_merge_requested=true`;
- if a caller explicitly supplies an AO-MA-10 bundle, it is validated
  fail-closed even when the autonomous lane flag is false;
- malformed autonomous request flags, missing, schema-invalid, non-AGREE,
  authority-boundary-open, or context-mismatched AO-MA-10 bundle evidence
  blocks the future autonomous lane;
- the bundle is evidence only; release authority remains
  `ao-release-gate+github-ruleset`.

AO-MA-10b still does not mutate GitHub settings, workflows, CODEOWNERS,
rulesets, branch protection, or execute a merge. It only records the
decision-core and payload/CLI contract needed before AO-MA-10d negative tests
and AO-MA-10c merge-agent dry-run work.

## AO-MA-10d Negative Fail-Closed Suite

AO-MA-10d records the negative suite that must pass before any merge-agent
dry-run or real autonomous merge smoke. It keeps the lane fail-closed by
pinning four activation-prerequisite smokes:

```text
negative_high_risk_blocked_smoke
stale_evidence_blocked_smoke
same_provider_review_blocked_smoke
missing_verifier_blocked_smoke
```

The suite is end-to-end through `build_ao_release_gate_decision`; it does not
trust prose-only model output. It specifically blocks:

- high-risk/prohibited path requests without the required human review surface;
- stale, missing, or schema-invalid AO-MA-10 evidence;
- same-provider self-review, including duplicate `provider_id` verdicts or a
  missing required provider verdict;
- missing or non-accepting local verifier evidence;
- authority-boundary drift such as support widening, production-platform
  claims, live-adapter execution, secret recording, mutation claims, or release
  authority changes;
- replay/context drift across repository, refs, head SHA, diff digest, and
  changed-file count;
- malformed or conflicting autonomous-request flags.

AO-MA-10d intentionally does not change workflows, CODEOWNERS, GitHub rulesets,
branch protection, testai/smee/webhook/Vault/GitHub App configuration, or any
merge-agent runtime. The only runtime hardening is the same-provider
fail-closed check in `ao-release-gate`, because the schema can require the
provider list shape but cannot prove semantic uniqueness across nested
`provider_verdicts`.

## GitHub Compatibility

The design stays GitHub-native:

- The future safe required-check set for autonomous low-risk dry-run is
  `ao-release-gate-technical` plus `ao-release-gate-review`, both
  source-pinned to GitHub Actions. The legacy `ao-release-gate` wrapper remains
  compatibility evidence but is not enough to remove human review globally.
- Source-pinned integration remains GitHub Actions.
- Branch protection / ruleset enforcement remains the release authority layer.
- If repository-native auto-merge is disabled, a merge agent may later perform
  `gh pr merge --squash --delete-branch` only after all required gates pass.
- No admin merge and no bypass actors.

## Scope of Original AO-MA-10 Planning Slice

The original planning PR touched only:

1. `.claude/plans/AO-MA-1-MULTI-AGENT-ORCHESTRATION-DESIGN.md`
2. `.claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.md`
3. `.claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.v1.json`
4. `ao_kernel/defaults/schemas/ao-ma-10-low-risk-autonomous-merge-lane.schema.v1.json`
5. `tests/test_ao_ma10_low_risk_autonomous_merge_lane.py`
6. `local-ai-review-evidence.v1.json`

## Scope of AO-MA-10a0 Readiness Slice

AO-MA-10a0 may touch only:

1. `.claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.md`
2. `.claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.v1.json`
3. `.claude/plans/AO-MA-10A0-GITHUB-READINESS-SNAPSHOT.v1.json`
4. `ao_kernel/defaults/schemas/ao-ma-10-github-readiness-snapshot.schema.v1.json`
5. `scripts/ao_ma10_github_readiness_snapshot.py`
6. `tests/test_ao_ma10_low_risk_autonomous_merge_lane.py`
7. `tests/test_ao_ma10_github_readiness_snapshot.py`
8. `tests/fixtures/ao_ma_10/github_readiness_snapshot.blocked.valid.json`

## Scope of AO-MA-10a1 Eligibility Slice

AO-MA-10a1 may touch only:

1. `.claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.md`
2. `.claude/plans/AO-MA-10A1-AUTONOMOUS-MERGE-ELIGIBILITY.v1.json`
3. `ao_kernel/defaults/schemas/ao-ma-10-autonomous-merge-eligibility.schema.v1.json`
4. `scripts/ao_ma10_autonomous_merge_eligibility.py`
5. `tests/test_ao_ma10_autonomous_merge_eligibility.py`
6. `tests/fixtures/ao_ma_10/autonomous_merge_eligibility.blocked.valid.json`
7. `tests/fixtures/ao_ma_10/autonomous_merge_eligibility.ready.valid.json`
8. `local-ai-review-evidence.v1.json`

## Scope of AO-MA-10a2 Evidence Schema Slice

AO-MA-10a2 may touch only:

1. `.claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.md`
2. `.claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.v1.json`
3. `.claude/plans/AO-MA-10A2-EVIDENCE-SCHEMAS.md`
4. `.claude/plans/AO-MA-10A2-EVIDENCE-SCHEMAS.v1.json`
5. `ao_kernel/defaults/schemas/ao-ma-10-provider-consensus.schema.v1.json`
6. `ao_kernel/defaults/schemas/ao-ma-10-evidence-bundle.schema.v1.json`
7. `scripts/ao_ma10_evidence_bundle.py`
8. `tests/test_ao_ma10_evidence_schemas.py`
9. `tests/fixtures/ao_ma_10a2/`
10. `local-ai-review-evidence.v1.json`

## Scope of AO-MA-10b Release-Gate Integration Slice

AO-MA-10b may touch only:

1. `.claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.md`
2. `.claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.v1.json`
3. `.claude/plans/GPP-2B-AO-RELEASE-GATE-REQUIRED-CHECK-MAPPING.md`
4. `ao_kernel/ao_release_gate.py`
5. `scripts/ao_release_gate_decision.py`
6. `scripts/ao_release_gate_build_payload.py`
7. `tests/test_ao_release_gate.py`
8. `tests/test_ao_release_gate_build_payload.py`
9. `tests/test_gpp2b_mapping_drift_guard.py`

The scope intentionally excludes `.github/**`, CODEOWNERS, rulesets,
branch-protection mutation, merge-agent activation, live adapter execution,
support widening, and production platform claims.

## Scope of AO-MA-10d Negative Fail-Closed Suite

AO-MA-10d may touch only:

1. `.claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.md`
2. `.claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.v1.json`
3. `ao_kernel/defaults/schemas/ao-ma-10-low-risk-autonomous-merge-lane.schema.v1.json`
4. `ao_kernel/ao_release_gate.py`
5. `tests/test_ao_ma10_negative_fail_closed.py`
6. `tests/test_ao_ma10_low_risk_autonomous_merge_lane.py`
7. `tests/test_ri78b_bc1_6a_execution_window_authorization_invariant.py`
8. `local-ai-review-evidence.v1.json`

The RI-7.8b invariant touch is a compatibility fix only: its cross-artifact
verdict equality check applies when `local-ai-review-evidence.v1.json` belongs
to RI-7.8b-bc1-6a, and skips when the global local evidence file belongs to a
new active PR work package.

The scope intentionally excludes `.github/**`, CODEOWNERS, rulesets,
branch-protection mutation, merge-agent activation, live adapter execution,
support widening, production platform claims, and testai/smee/webhook/Vault/
GitHub App work.

## Historical planning-slice hard stops

- No workflow mutation.
- No ruleset or branch-protection mutation.
- No CODEOWNERS mutation.
- No runtime orchestration mutation.
- No release-gate or local-gate runtime mutation.
- No `gpp_status.v1.json` mutation.
- No support widening.
- No production platform claim.
- No live adapter execution.
- No testai, smee, webhook callback, Vault, GitHub App, or Cloud Run work.
- The original AO-MA-10 planning slice did not activate the merge agent.
- The original AO-MA-10 planning slice did not execute auto-merge.

## Acceptance

The original AO-MA-10 planning slice was complete when:

1. This plan record exists.
2. The receipt JSON validates against its schema.
3. Invariant tests prove the receipt pins low-risk criteria, high-risk bounded
   consensus, and activation prerequisites.
4. Invariant tests prove this PR did not touch workflows, rulesets, CODEOWNERS,
   release-gate runtime, local-gate runtime, `gpp_status.v1.json`, support
   boundary docs, or live-adapter surfaces.
5. All guard flags remain false.
6. Cross-provider advisory review records `AGREE`.
