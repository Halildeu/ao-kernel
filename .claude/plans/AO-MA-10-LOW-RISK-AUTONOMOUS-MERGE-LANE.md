# AO-MA-10 - Low-Risk Autonomous Merge Lane Cutover Plan

**Status:** planned / AO-MA-10a1 eligibility checker recorded
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

AO-MA-10 is **planning-only**. It does not activate a merge agent, change
CODEOWNERS, mutate GitHub rulesets, alter workflows, or grant release
authority to AI output.

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
AO-MA-10a2  context-bound evidence bundle + registered-provider consensus schemas
AO-MA-10b   ao-release-gate payload + decision integration
AO-MA-10d   negative fail-closed suite before any real merge
AO-MA-10c   merge-agent identity + dry-run executor
AO-MA-10e   positive disposable low-risk autonomous merge smoke
AO-MA-10f   activation/cutover
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

## Merge Agent Activation Lock

The merge agent is **not active** under this AO-MA-10 plan slice. The receipt
pins every activation prerequisite as `not_started`.

The future activation slice must independently prove:

1. Low-risk path/risk classifier implementation.
2. CODEOWNERS or ruleset model compatible with low-risk autonomy.
3. Merge-agent identity and permissions.
4. Positive low-risk autonomous merge smoke.
5. Negative high-risk blocked smoke.
6. Stale-evidence blocked smoke.
7. Same-provider review blocked smoke.
8. Missing-verifier blocked smoke.
9. `--admin` and bypass actors absent.
10. A dedicated cutover record confirming no support widening, no production
    platform claim, and no live adapter execution.

Until those prerequisites are completed in a later PR, AO-MA-10 is a plan and
invariant record only.

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

Current AO-MA-10a0 live result is `blocked`, which is the correct fail-closed
state. Recorded blockers:

1. `ao_release_gate_required_check_missing`
2. `legacy_required_review_blocks_low_risk_autonomy`
3. `merge_actor_admin_permission_observed`
4. `ssot_live_required_check_drift_detected`

Recorded warnings:

1. `repository_auto_merge_disabled_merge_agent_direct_mode_required`
2. `some_nominal_low_risk_prefixes_still_codeowned`

This does not mean the autonomous lane is abandoned. It means the next slices
must resolve authority and enforcement mechanics before the merge agent can run.
The live GitHub snapshot is the AO-MA-10a0 source of truth for readiness; any
broader status document that still describes `ao-release-gate` as source-pinned
in ruleset `16803733` must be reconciled in a separate follow-up before
AO-MA-10a1 can treat the repository as ready.

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

The current committed A1 artifact is intentionally `blocked` because live
GitHub enforcement still lacks the dual required-check set, legacy review still
blocks low-risk autonomy, the current actor is admin, and the broader SSOT/live
required-check drift remains unresolved. That is the correct fail-closed state.

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

## Hard Stops

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
- No merge-agent activation in this slice.
- No auto-merge execution in this slice.

## Acceptance

AO-MA-10 is complete when:

1. This plan record exists.
2. The receipt JSON validates against its schema.
3. Invariant tests prove the receipt pins low-risk criteria, high-risk bounded
   consensus, and activation prerequisites.
4. Invariant tests prove this PR did not touch workflows, rulesets, CODEOWNERS,
   release-gate runtime, local-gate runtime, `gpp_status.v1.json`, support
   boundary docs, or live-adapter surfaces.
5. All guard flags remain false.
6. Cross-provider advisory review records `AGREE`.
