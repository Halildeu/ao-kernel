# GPP-2c - Independent Release Gate and Credential Decision

**Status:** blocked; external/admin decision required
**Date:** 2026-04-25
**Issue:** [#485](https://github.com/Halildeu/ao-kernel/issues/485)
**Parent issue:** [#482](https://github.com/Halildeu/ao-kernel/issues/482)
**Program head:** `GPP-2` remains blocked
**Support impact:** none
**Runtime impact:** none

## 1. Purpose

Capture the remaining protected live-adapter gate blockers after GPP-2b partial
provisioning.

This is deliberately a governance/admin gate, not runtime implementation. It
does not bind `.github/workflows/live-adapter-gate.yml`, does not create or read
secret values, does not execute a live adapter, and does not widen support.

`Reviewer` in the original slice title means GitHub-native release authority,
not an application end-user account. `GPP-2f` supersedes the vocabulary with
the broader independent release gate requirement.

## 2. Current Live Evidence

```bash
gh api repos/Halildeu/ao-kernel/environments/ao-kernel-live-adapter-gate \
  --jq '{name:.name, can_admins_bypass:.can_admins_bypass, protection_rules:.protection_rules, deployment_branch_policy:.deployment_branch_policy}'
# {"can_admins_bypass":false,"deployment_branch_policy":{"custom_branch_policies":true,"protected_branches":false},"name":"ao-kernel-live-adapter-gate","protection_rules":[{"id":53201958,"node_id":"GA_kwDOSA13rs4DK8wm","type":"branch_policy"}]}

gh api repos/Halildeu/ao-kernel/environments/ao-kernel-live-adapter-gate/deployment-branch-policies \
  --jq '.branch_policies[] | {name:.name, type:.type}'
# {"name":"main","type":"branch"}

gh secret list --env ao-kernel-live-adapter-gate --repo Halildeu/ao-kernel
# empty

gh api 'repos/Halildeu/ao-kernel/collaborators?per_page=100' \
  --jq '.[] | {login:.login, id:.id, role_name:.role_name}'
# {"login":"Halildeu","id":186576227,"role_name":"admin"}
```

## 3. Decision

`GPP-2` remains blocked.

The environment shell is now present and partially hardened:

1. `ao-kernel-live-adapter-gate` exists.
2. Deployment branch policy includes `main`.
3. `can_admins_bypass=false`.

The gate is still incomplete:

1. `AO_CLAUDE_CODE_CLI_AUTH` is not present as an environment secret handle.
2. No approved independent release gate is configured.
3. GPP-2g selected the GitHub-native reviewer/team model as the first
   provisioning path.
4. GPP-2h supersedes that path and selects a GitHub App deployment protection
   rule as the active bot gate model.
5. A human/team required reviewer or OIDC-backed secret broker remains an
   acceptable fallback only through a future explicit decision.

## 4. Acceptable Resolution Paths

### Superseded Path

1. Add or designate a release authority reviewer or team.
2. Configure `ao-kernel-live-adapter-gate` required reviewers with
   prevent-self-review.
3. Set `AO_CLAUDE_CODE_CLI_AUTH` under the environment without printing or
   reading back the secret value.
4. Open a follow-up attestation PR that proves the handle exists and the
   independent release gate is present.

### Selected Active Path

1. Implement metadata-only attestation support for GitHub App deployment
   protection evidence. Completed by `GPP-2i`.
2. Configure a GitHub App or policy service as the deployment protection gate
   for `ao-kernel-live-adapter-gate`.
3. Set `AO_CLAUDE_CODE_CLI_AUTH` under the environment without printing or
   reading back the secret value.
4. Open a follow-up attestation PR that proves the handle exists and the
   selected deployment protection bot gate is present.

### Alternative Path

1. Record an explicit single-admin equivalent release-gate decision.
2. Explain why the equivalent gate is acceptable despite lacking a non-self
   GitHub reviewer.
3. Keep that exception scoped to this repository and this protected gate.
4. Still require `AO_CLAUDE_CODE_CLI_AUTH` as an environment secret handle
   before any runtime binding.

The alternative path is not implied by this document. It requires an explicit
operator decision in a follow-up issue/PR before it can unblock anything.

## 5. Follow-Up Attestation Requirement

After either acceptable path is complete, open a fresh prerequisite attestation
slice. That slice must prove:

1. the environment still exists;
2. deployment branch policy still allows only the intended `main` path;
3. `can_admins_bypass=false`;
4. `AO_CLAUDE_CODE_CLI_AUTH` exists under the environment;
5. the selected deployment protection app gate is present, or a future
   explicit decision selects another independent release-gate model;
6. fork-triggered contexts cannot read protected credentials.

Only then may `GPP-2` runtime binding start.

## 6. Forbidden Until Then

1. No `GPP-2` runtime binding.
2. No live adapter execution.
3. No support widening.
4. No production-platform claim.
5. No secret value readback.
6. No local operator auth treated as project-owned evidence.
