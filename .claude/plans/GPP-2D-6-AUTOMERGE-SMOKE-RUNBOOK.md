# GPP-2D-6 - Auto-Merge Smoke Runbook

> Status: accepted / low-risk no-human merge smoke complete under the
> repo-owned workflow executor model.
> Work package: post-GPP-2 closeout hardening.
> Parent lane: GPP-2D - Autonomous required-check lane.
> This runbook records the CODEOWNERS narrowing and legacy
> `enforce_admins=true` hardening slice, the `ao-release-gate`
> path-sensitive human-review gate, and the accepted AO-MA-10q low-risk
> no-human merge smoke. It does not widen support, claim production
> readiness, execute live adapters, or reopen/re-close GPP-2.

## 1. Purpose

GPP-2D-6 proves the near-term no-testai autonomous lane:

```text
cross-provider review evidence
  + local_gpp_gate evidence
  + ao-release-gate required check
  + GitHub branch protection
  -> repo-owned GitHub Actions merge executor for low-risk PRs
```

High-risk PRs must still require human / CODEOWNERS review. AI output is
evidence only; release authority remains the repo-owned `ao-release-gate`
required check plus GitHub branch protection.

## 2. Current governance state

The earlier `.github/CODEOWNERS` file started with a broad default rule:

```text
* @Halildeu @gladyatore-lab
```

That default was safe but blocked the GPP-2D-6 low-risk auto-merge smoke: every
path had a code owner, so every PR remained code-owner gated even when
`ao-release-gate` succeeded.

The GPP-2D-6 hardening slice narrows CODEOWNERS by removing the broad `*`
default owner and keeping code-owner review on governance-sensitive surfaces:

```text
/.github/
/AGENTS.md
/CLAUDE.md
/.claude/
/ao_kernel/ao_release_gate*.py
/scripts/ao_release_gate*.py
/scripts/local_gpp_gate*.py
/ao_kernel/defaults/schemas/*gate*.json
/ao_kernel/defaults/policies/
/deploy/
```

There is also a separate legacy branch-protection review gate. The live
metadata check after the GPP-2D-6 hardening refresh showed:

```text
repository.autoMergeAllowed = false
legacy_branch_protection.enforce_admins = true
required_approving_review_count = 1
require_code_owner_reviews = true
dismiss_stale_reviews = true
```

This means the CODEOWNERS narrowing and `enforce_admins=true` tightening are
necessary but still insufficient for the full GPP-2D-6 acceptance criterion.
Removing the broad `*` owner can stop low-risk files from being code-owner
matched, and `enforce_admins=true` makes the legacy surface stricter for admins;
however `repository.autoMergeAllowed=false` prevents GitHub-native auto-merge,
and a global `required_approving_review_count=1` still keeps low-risk PRs
human-review gated.

The GPP-2D-6b gate slice moves the high-risk human-review requirement into the
repo-owned `ao-release-gate` required check:

```text
low-risk changed paths
  -> AI review evidence + local_gpp_gate + CI + ao-release-gate can pass

high-risk changed paths
  -> ao-release-gate requires a current-head non-author APPROVED GitHub review
```

This lets the future low-risk lane remove the legacy global review requirement
without losing the high-risk human gate. AI output remains evidence only; the
required check is the release authority.

Therefore GPP-2D-6 could not be accepted until these conditions became true:

1. a no-human merge executor path exists for low-risk PRs;
2. the high-risk surface remains human-gated through `ao-release-gate` and
   CODEOWNERS / branch ruleset policy; and
3. the low-risk surface no longer has a global non-author review requirement.

This runbook allows the CODEOWNERS narrowing only because `ao-release-gate` is
already source-pinned as a required check and legacy `enforce_admins=true`
hardening is active. It does not relax the global required-review setting.

Short rule: weakening reviewer coverage is forbidden unless the replacement
mechanical gate is already source-pinned, enforced, and verified.

## 3. Required ordering

1. GPP-2D-5 runbook PR lands. Done.
2. Operator performs the GPP-2D-5 branch-protection / ruleset cutover:
   `ao-release-gate` required, source-pinned to GitHub Actions, admin bypass
   disallowed. Done.

Cutover invariant: admin bypass disallowed.
3. Agent records GPP-2D-5 verification outcomes:
   required-check API evidence, admin-bypass-off evidence, negative-path PR
   blocked by `ao-release-gate`, and positive-path PR allowed by the gate. Done.
4. GPP-2D-7 / AO-GATE-9 closeout records GPP-2 as closed. Done; GPP-2D-6 is
   now a post-closeout hardening slice, not a closeout prerequisite.
5. CODEOWNERS narrowing lands and legacy `enforce_admins=true` is verified.
6. `ao-release-gate` path-sensitive human-review enforcement lands: high-risk
   paths require current-head non-author `APPROVED` GitHub review, while
   low-risk paths do not.
7. The repo-owned workflow executor is selected as the low-risk merge executor
   model because repository-native auto-merge is disabled.
8. Operator selects and applies the low-risk review model: no global
   non-author approval for eligible low-risk paths; high-risk human review is
   enforced through `ao-release-gate-review` and CODEOWNERS/ruleset policy.
9. AO-MA-10q / GPP-2D-6 low-risk no-human merge smoke runs.

Steps 1-9 are complete. The accepted evidence is AO-MA-10q workflow run
`26633091281`, which created and merged disposable low-risk PR #737 through
`app/github-actions` after required checks passed.

## 4. CODEOWNERS narrowing target

The narrowing slice keeps code-owner review on the high-risk surface set from
the GPP-2D design:

```text
/.github/ @Halildeu @gladyatore-lab
/AGENTS.md @Halildeu @gladyatore-lab
/CLAUDE.md @Halildeu @gladyatore-lab
/.claude/ @Halildeu @gladyatore-lab
/ao_kernel/ao_release_gate*.py @Halildeu @gladyatore-lab
/scripts/ao_release_gate*.py @Halildeu @gladyatore-lab
/scripts/local_gpp_gate*.py @Halildeu @gladyatore-lab
/ao_kernel/defaults/schemas/*gate*.json @Halildeu @gladyatore-lab
/ao_kernel/defaults/policies/ @Halildeu @gladyatore-lab
/deploy/ @Halildeu @gladyatore-lab
```

The CODEOWNERS syntax is implemented in this high-risk governance PR and must
be reviewed by a non-author human reviewer. The acceptance criterion is the
behavior: low-risk paths are no longer code-owner-gated; the high-risk paths
above still are.

Narrowing CODEOWNERS is not enough while the legacy branch protection still has
`required_approving_review_count=1`. The smoke must verify the actual GitHub
merge gate, not just the CODEOWNERS file contents.

## 5. Low-risk no-human merge smoke

The accepted low-risk smoke changed only a path outside the high-risk surface
set:

```text
docs/evidence/ao-ma-10l-autonomous-smoke/ao-ma-10l-smoke-20260529-105127z.md
```

The PR included normal review evidence and passed `ao-release-gate`.
For low-risk paths, `ao-release-gate` must not require a human review when the
AI evidence, local gate evidence, CI, and branch freshness checks pass.
The selected executor is the repo-owned GitHub Actions merge path, not
GitHub-native repository auto-merge.

Acceptance:

1. `ao-release-gate` concludes `success`.
2. Required CI checks are green.
3. `ao-release-gate` records no high-risk changed paths.
4. No non-author human review is required for the low-risk path.
5. `app/github-actions` performs the merge after required checks pass.
6. The merge is not performed with `--admin`.
7. The evidence records the PR URL, merge SHA, relevant check run IDs, and the
   no-human merge timeline.

Accepted evidence:

```text
workflow_run_id: 26633091281
artifact: ao-ma10q-dedicated-actor-smoke-26633091281
status: doctor_status=0, runner_status=0
decision: merged
pull_request: https://github.com/Halildeu/ao-kernel/pull/737
merge_commit: 15a1e2f23134b84e0c69cde1fb8adc03e5560a15
merge_actor: app/github-actions
required_checks: observed=true, all_passed=true
admin_bypass: false
support_widening: false
production_platform_claim: false
live_adapter_execution: false
```

## 6. High-risk human-gate smoke

Open a high-risk smoke PR that touches exactly one governance-sensitive path,
for example:

```text
.github/CODEOWNERS
```

Do not merge this PR as part of the smoke unless a real governance change is
intended. The purpose is to prove the gate holds.

Acceptance:

1. `ao-release-gate` fails with
   `ao_release_gate_high_risk_human_review_missing` before a current-head
   non-author approval exists.
2. After a current-head non-author `APPROVED` GitHub review and a rerun,
   `ao-release-gate` may pass if all other evidence is valid.
3. GitHub still reports a code-owner / required-review block until that human
   approval exists.
4. `gh pr view <HIGH_RISK_PR> --json mergeStateStatus,reviewDecision,statusCheckRollup`
   shows the PR is not merge-ready without the required human approval.
5. If `gh pr merge --auto --squash` is attempted before approval, GitHub must
   not auto-merge the PR.

High-risk invariant: GitHub must not auto-merge the PR before required human
approval.
6. The smoke PR is closed or converted into a real reviewed governance PR after
   evidence capture.

## 7. Evidence artifact

GPP-2D-6 completion requires a committed evidence record:

```text
.claude/plans/GPP-2D-6-AUTOMERGE-SMOKE-EVIDENCE.md
```

Required fields:

```text
UTC timestamp
Repository and main head before smoke
GPP-2D-5 verification evidence link
GPP-2D-7 closeout evidence link
Repository auto-merge setting before and after smoke, or the selected
workflow-executor alternative when repository-native auto-merge is disabled
Legacy branch-protection enforce_admins setting before smoke
Legacy branch-protection review setting before smoke
Operator review-model decision and resulting GitHub metadata
CODEOWNERS narrowing PR link and merge SHA
Low-risk PR link, check run IDs, workflow run ID, merge actor, merge SHA
High-risk PR link, code-owner block evidence, merge rejection / blocked status
Admin bypass attempted: false
Support widening: false
Production platform claim: false
Live adapter execution: false
testai / smee dependency: false
GPP-2 status after smoke: remains closed; this slice is a post-closeout
hardening record only
```

## 8. Stop conditions

Stop and do not continue to GPP-2D-7 if any of these are true:

- `ao-release-gate` is not a source-pinned required check.
- Admin bypass is enabled or a bypass actor exists.
- Neither repository-native auto-merge nor the accepted repo-owned workflow
  executor path is available.
- The low-risk smoke still requires code-owner approval or any global
  non-author review approval.
- The high-risk smoke does not require human / CODEOWNERS review.
- Any merge uses `--admin`.
- Any PR claims production readiness or widens support.
- Any smoke executes a live adapter.
- testai, smee, GitHub App webhook callback, or deployment-protection callback
  is reintroduced as an active blocker.
- `support_widening_allowed`, `production_platform_claim_allowed`, or
  `live_adapter_execution_allowed` becomes true.

## 9. Relation to GPP-2D-7

GPP-2D-7 already closed GPP-2 under the no-testai release-governance model.
GPP-2D-6 is therefore a post-closeout hardening record, not a prerequisite for
the current GPP-2 closeout. It is now marked complete because:

1. GPP-2D-5 verification outcomes are committed.
2. GPP-2D-7 closeout is committed.
3. The repo-owned workflow executor alternative to GitHub-native auto-merge is
   recorded and proved by AO-MA-10q.
4. The selected review model is recorded and applied.
5. CODEOWNERS narrowing and legacy `enforce_admins=true` hardening are merged
   and reviewed as a high-risk governance change.
6. `ao-release-gate` path-sensitive high-risk human-review enforcement is
   merged and reviewed as a high-risk governance change.
7. GPP-2D-6 low-risk smoke evidence is committed; high-risk remains guarded by
   `ao-release-gate-review` and CODEOWNERS/ruleset policy.

GPP-2D-6 is complete under the accepted low-risk workflow-executor model, while
GPP-2 remains `closed` and the guard flags remain false.
