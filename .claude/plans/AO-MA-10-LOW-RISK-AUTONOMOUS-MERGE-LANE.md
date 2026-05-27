# AO-MA-10 - Low-Risk Autonomous Merge Lane Cutover Plan

**Status:** planned / docs + schema + invariant test only
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
   Actions integration.
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

- Required providers: OpenAI + Anthropic + MiniMax when available.
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

## GitHub Compatibility

The design stays GitHub-native:

- Required check stays `ao-release-gate`.
- Source-pinned integration remains GitHub Actions.
- Branch protection / ruleset enforcement remains the release authority layer.
- If repository-native auto-merge is disabled, a merge agent may later perform
  `gh pr merge --squash --delete-branch` only after all required gates pass.
- No admin merge and no bypass actors.

## Scope of This Slice

This PR may touch only:

1. `.claude/plans/AO-MA-1-MULTI-AGENT-ORCHESTRATION-DESIGN.md`
2. `.claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.md`
3. `.claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.v1.json`
4. `ao_kernel/defaults/schemas/ao-ma-10-low-risk-autonomous-merge-lane.schema.v1.json`
5. `tests/test_ao_ma10_low_risk_autonomous_merge_lane.py`
6. `local-ai-review-evidence.v1.json`

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
