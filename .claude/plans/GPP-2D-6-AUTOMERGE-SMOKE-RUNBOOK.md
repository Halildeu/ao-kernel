# GPP-2D-6 - Auto-Merge Smoke Runbook

> Status: planned / verification contract only.
> Work package: GPP-2 (still blocked).
> Parent lane: GPP-2D - Autonomous required-check lane.
> This slice does not mutate branch protection, does not edit
> `.github/CODEOWNERS`, does not enable auto-merge, and does not close GPP-2.

## 1. Purpose

GPP-2D-6 proves the near-term no-testai autonomous lane:

```text
cross-provider review evidence
  + local_gpp_gate evidence
  + ao-release-gate required check
  + GitHub branch protection
  -> GitHub-native auto-merge for low-risk PRs
```

High-risk PRs must still require human / CODEOWNERS review. AI output is
evidence only; release authority remains the repo-owned `ao-release-gate`
required check plus GitHub branch protection.

## 2. Current CODEOWNERS state

The current `.github/CODEOWNERS` file starts with a broad default rule:

```text
* @Halildeu @gladyatore-lab
```

That default is safe but blocks the GPP-2D-6 low-risk auto-merge smoke: every
path has a code owner, so every PR remains human-review gated even when
`ao-release-gate` succeeds.

Therefore GPP-2D-6 cannot be honestly accepted until a separate, reviewed
CODEOWNERS narrowing slice lands after the GPP-2D-5 cutover verification. The
narrowing must remove the broad `*` default and keep explicit ownership only on
the high-risk surface set.

This runbook intentionally does not change CODEOWNERS. Weakening reviewer
coverage before `ao-release-gate` is source-pinned as a required check would
reduce governance before the mechanical gate is live.

Short rule: Weakening reviewer coverage before `ao-release-gate` is source-pinned
is forbidden.

## 3. Required ordering

1. GPP-2D-5 runbook PR lands.
2. Operator performs the GPP-2D-5 branch-protection / ruleset cutover:
   `ao-release-gate` required, source-pinned to GitHub Actions, admin bypass
   disallowed.

Cutover invariant: admin bypass disallowed.
3. Agent records GPP-2D-5 verification outcomes:
   required-check API evidence, admin-bypass-off evidence, negative-path PR
   blocked by `ao-release-gate`, and positive-path PR allowed by the gate.
4. A high-risk CODEOWNERS narrowing PR lands with non-author human approval.
5. GPP-2D-6 auto-merge smoke runs.
6. GPP-2D-7 / AO-GATE-9 closeout records the final GPP-2 state only after the
   smoke evidence exists.

Steps 1-3 must complete before any CODEOWNERS narrowing. Steps 1-5 must complete
before GPP-2 closeout.

## 4. CODEOWNERS narrowing target

The first narrowing slice keeps code-owner review on the high-risk surface set
from the GPP-2D design:

```text
/.github/ @Halildeu @gladyatore-lab
/AGENTS.md @Halildeu @gladyatore-lab
/CLAUDE.md @Halildeu @gladyatore-lab
/.claude/plans/gpp_status.v1.json @Halildeu @gladyatore-lab
/.claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md @Halildeu @gladyatore-lab
/.claude/plans/AO-GATE-ROADMAP-TODO.md @Halildeu @gladyatore-lab
/.claude/plans/GPP-* @Halildeu @gladyatore-lab
/.claude/plans/AO-* @Halildeu @gladyatore-lab
/ao_kernel/ao_release_gate*.py @Halildeu @gladyatore-lab
/scripts/ao_release_gate*.py @Halildeu @gladyatore-lab
/scripts/local_gpp_gate*.py @Halildeu @gladyatore-lab
/ao_kernel/defaults/schemas/*gate*.json @Halildeu @gladyatore-lab
/ao_kernel/defaults/policies/ @Halildeu @gladyatore-lab
/deploy/ @Halildeu @gladyatore-lab
```

The exact CODEOWNERS syntax is implemented in the future narrowing PR and must
be reviewed as a high-risk governance change. The acceptance criterion is the
behavior, not this draft text: low-risk paths are no longer code-owner-gated;
the high-risk paths above still are.

## 5. Low-risk auto-merge smoke

After the narrowing PR lands, open a low-risk smoke PR that changes only a path
outside the high-risk surface set. Example candidate:

```text
docs/smoke/gpp2d6-low-risk-automerge-smoke.md
```

The PR must include normal review evidence and must pass `ao-release-gate`.
Then enable GitHub-native auto-merge:

```bash
gh pr merge <LOW_RISK_PR> --repo Halildeu/ao-kernel --auto --squash
```

Acceptance:

1. `ao-release-gate` concludes `success`.
2. Required CI checks are green.
3. No non-author human review is required for the low-risk path.
4. GitHub performs the merge after required checks pass.
5. The merge is not performed with `--admin`.
6. The evidence records the PR URL, merge SHA, relevant check run IDs, and the
   auto-merge timeline.

## 6. High-risk human-gate smoke

Open a high-risk smoke PR that touches exactly one governance-sensitive path,
for example:

```text
.github/CODEOWNERS
```

Do not merge this PR as part of the smoke unless a real governance change is
intended. The purpose is to prove the gate holds.

Acceptance:

1. `ao-release-gate` may pass if the evidence is valid.
2. GitHub still reports a code-owner / required-review block.
3. `gh pr view <HIGH_RISK_PR> --json mergeStateStatus,reviewDecision,statusCheckRollup`
   shows the PR is not merge-ready without the required human approval.
4. If `gh pr merge --auto --squash` is attempted before approval, GitHub must
   not auto-merge the PR.

High-risk invariant: GitHub must not auto-merge the PR before required human
approval.
5. The smoke PR is closed or converted into a real reviewed governance PR after
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
CODEOWNERS narrowing PR link and merge SHA
Low-risk PR link, check run IDs, auto-merge enabled timestamp, merge SHA
High-risk PR link, code-owner block evidence, merge rejection / blocked status
Admin bypass attempted: false
Support widening: false
Production platform claim: false
Live adapter execution: false
testai / smee dependency: false
GPP-2 status after smoke: still blocked until GPP-2D-7 closeout
```

## 8. Stop conditions

Stop and do not continue to GPP-2D-7 if any of these are true:

- `ao-release-gate` is not a source-pinned required check.
- Admin bypass is enabled or a bypass actor exists.
- The low-risk smoke still requires code-owner approval.
- The high-risk smoke does not require human / CODEOWNERS review.
- Any merge uses `--admin`.
- Any PR claims production readiness or widens support.
- Any smoke executes a live adapter.
- testai, smee, GitHub App webhook callback, or deployment-protection callback
  is reintroduced as an active blocker.
- `support_widening_allowed`, `production_platform_claim_allowed`, or
  `live_adapter_execution_allowed` becomes true.

## 9. Relation to GPP-2D-7

GPP-2D-7 may close GPP-2 only after:

1. GPP-2D-5 verification outcomes are committed.
2. CODEOWNERS narrowing is merged and reviewed as a high-risk change.
3. GPP-2D-6 low-risk and high-risk smoke evidence is committed.
4. `python3 scripts/gpp_next.py` is updated in the closeout slice to reflect the
   new evidence.

Until then, GPP-2 remains `blocked`.
