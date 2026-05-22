# GPP-2u - Autonomous GitHub App Release Gate Decision

**Status:** closeout candidate
**Date:** 2026-04-28
**Issue:** [#537](https://github.com/Halildeu/ao-kernel/issues/537)
**Branch:** `codex/gpp-2u-autonomous-release-gate`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gpp-2u-autonomous-release-gate`
**Decision:** `autonomous_github_app_release_gate_selected_no_support_widening`

## Context

GPP-2s made the deployment-protection policy service publishable as a
repo-owned GHCR/container artifact, but the live-adapter gate is still blocked
until a hosted GitHub App policy service responds to deployment protection
callbacks.

The follow-up deployment work also exposed a separate automation blocker:
program PRs can reach green CI but remain blocked by human review requirements.
That blocker must not be solved with admin bypass, a PAT-backed bot user, or by
treating Codex/Claude as release authority. The durable path must preserve
GitHub branch protection and remain fail-closed.

Claude Code was consulted through the ao-kernel MCP boundary as advisory review
only. That consultation did not read secrets, did not write memory, did not call
LLM tools through MCP, and did not approve the release gate.

## Decision

Select a dedicated GitHub App release gate as the autonomous release authority
for program PRs. The working app name is `ao-release-gate`.

The primary enforcement mechanism is a required status check or check-run named
`ao-release-gate`. Branch protection or repository rulesets must require that
check before merge automation can proceed. The app may optionally leave a pull
request review after a dry-run spike proves that GitHub App reviews are counted
by the repository's current branch protection model, but PR review is not the
durable enforcement path until that behavior is proven.

This is separate from the existing `ao-kernel-live-adapter-gate` deployment
protection app:

1. `ao-release-gate` decides whether a PR may merge automatically.
2. `ao-kernel-live-adapter-gate` decides whether protected live-adapter
   workflow jobs may proceed through the environment gate.
3. Neither app is allowed to widen support, approve production platform claims,
   or expose protected credential values.

## Required Policy Checks

The release gate must deny by default. In `enforce` mode (the production
configuration once AO-GATE-8 lands), the check-run conclusion is
`failure` unless every required condition passes. In `shadow` mode (the
default during the dry-run rollout), the same deny path posts a `neutral`
conclusion so the advisory check does not surface as red CI before the
branch-protection cutover. `allow_autonomous_merge` maps to `success`
in either mode. Switching from `shadow` to `enforce` is the AO-GATE-8
prerequisite; the check must not be marked required on `main` until the
hosted runtime is running in `enforce` mode.

Required conditions:

1. Repository is `Halildeu/ao-kernel`.
2. Base branch is `main`.
3. PR branch is up to date with the protected base policy.
4. Required CI checks are successful.
5. The work package has one issue, one branch, one PR, and one written exit
   decision.
6. GPP machine status is internally consistent and still keeps
   `support_widening_allowed=false`,
   `production_platform_claim_allowed=false`, and
   `live_adapter_execution_allowed=false` unless a later explicit GPP-9
   promotion decision changes those flags.
7. The diff stays inside the active work-package scope.
8. Fork and pull request contexts are kept away from protected credentials.
9. No workflow introduces `pull_request_target` credential exposure.
10. No PR references `AO_CLAUDE_CODE_CLI_AUTH` through the GitHub `secrets.`
    context unless a later live-execution slice explicitly permits it.
11. No secret value, private key, webhook secret, installation token, PAT, or
    equivalent credential material is committed or echoed.
12. No admin bypass path is used or requested.
13. No PAT-backed bot user is used as reviewer, merger, or release authority.
14. Claude/Codex output remains implementation input only; it is not release
    authority.
15. Local/operator smoke evidence is not treated as production evidence.
16. The PR does not run a live adapter unless a later protected runtime evidence
    slice explicitly permits live execution.

## Evidence Contract

The app must produce machine-readable evidence for each evaluated PR:

1. GitHub check-run or commit status named `ao-release-gate`.
2. Decision JSON containing `decision`, `allow`, `reason_codes`, checked commit
   SHA, base branch, PR number, issue URL, changed paths, required check
   summary, and policy version.
3. Redacted denial comment on the PR when blocked.
4. No credential values in logs, artifacts, comments, or check output.

Allowed terminal decisions:

1. `allow_autonomous_merge`
2. `deny_policy_violation`
3. `deny_missing_evidence`
4. `deny_stale_branch`
5. `deny_untrusted_context`
6. `error_fail_closed`

Any missing app configuration, webhook failure, timeout, malformed payload, or
GitHub API failure is `error_fail_closed`, not approval.

## Rejected Alternatives

1. Admin bypass is rejected.
2. PAT-backed bot reviewer or merger is rejected.
3. Product end-user accounts remain rejected as release authority.
4. Claude/Codex release authority is rejected.
5. Ruleset bypass actor privileges are rejected for this stage.
6. Auto-merge without an independent policy gate is rejected.
7. Reading back secret values to prove configuration is rejected.

## Follow-Up Sequence

1. `GPP-2v`: scaffold `ao-release-gate` with GitHub App auth, webhook
   signature verification, and dry-run check-run output.
2. `GPP-2w`: implement the policy decision engine and tests for the required
   checks above.
3. `GPP-2x`: run dry-run evidence on real PRs without merge authority.
4. `GPP-2y`: cut branch protection or rulesets over to require
   `ao-release-gate`.
5. `GPP-2z`: prove full autonomous merge on a bounded docs/status work package
   with branch protection preserved.

## Closeout

This decision selects the durable autonomous model but does not unblock GPP-2.
The hosted deployment-protection policy service is still missing, and
`ao-release-gate` is not yet implemented, installed, dry-run validated, or
required by branch protection.

This closeout does not widen support, does not permit production platform
claims, and does not permit live adapter execution.
