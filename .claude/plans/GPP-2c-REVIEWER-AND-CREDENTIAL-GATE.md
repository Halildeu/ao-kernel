# GPP-2c - Reviewer and Credential Gate Decision

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
2. Required reviewer protection is not configured.
3. A true non-self reviewer gate is not currently possible while only one
   collaborator is visible.

## 4. Acceptable Resolution Paths

### Preferred Path

1. Add or designate a second maintainer reviewer.
2. Configure `ao-kernel-live-adapter-gate` required reviewers with
   prevent-self-review.
3. Set `AO_CLAUDE_CODE_CLI_AUTH` under the environment without printing or
   reading back the secret value.
4. Open a follow-up attestation PR that proves the handle exists and the
   reviewer gate is present.

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
5. reviewer protection or an explicitly approved equivalent release gate is
   present;
6. fork-triggered contexts cannot read protected credentials.

Only then may `GPP-2` runtime binding start.

## 6. Forbidden Until Then

1. No `GPP-2` runtime binding.
2. No live adapter execution.
3. No support widening.
4. No production-platform claim.
5. No secret value readback.
6. No local operator auth treated as project-owned evidence.

