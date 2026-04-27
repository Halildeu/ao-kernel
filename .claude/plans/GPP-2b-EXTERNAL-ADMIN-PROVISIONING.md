# GPP-2b - External Admin Provisioning Tracker

**Status:** partially provisioned; still blocked
**Date:** 2026-04-25
**Issue:** [#482](https://github.com/Halildeu/ao-kernel/issues/482)
**Program head:** `GPP-2` remains blocked
**Support impact:** none
**Runtime impact:** none

## 1. Purpose

Track the non-code prerequisite work required before `GPP-2` runtime binding can
start.

This tracker does not create a secret, does not read a secret value, does not
bind the live-adapter workflow, and does not widen support. It records the
external GitHub admin state that must be changed before a future prerequisite
attestation can exit `prerequisites_ready`.

## 2. Live Evidence

Collected from `origin/main` on 2026-04-25 after PR
[#481](https://github.com/Halildeu/ao-kernel/pull/481) merged:

```bash
git status --short --branch
# ## main...origin/main

git rev-list --left-right --count HEAD...origin/main
# 0 0

python3 scripts/gpp_next.py
# Current WP: GPP-2 - Protected Live-Adapter Gate Runtime Binding
# Current status: blocked
# Live adapter execution allowed: false

gh api repos/Halildeu/ao-kernel/environments --jq '.environments[].name'
# pypi

gh secret list --repo Halildeu/ao-kernel
# empty

gh api 'repos/Halildeu/ao-kernel/collaborators?per_page=100' \
  --jq '.[] | {login:.login, role_name:.role_name}'
# {"login":"Halildeu","role_name":"admin"}
```

Additional partial provisioning completed on 2026-04-25:

```bash
gh api repos/Halildeu/ao-kernel/environments/ao-kernel-live-adapter-gate \
  --jq '{name:.name, can_admins_bypass:.can_admins_bypass, protection_rules:.protection_rules, deployment_branch_policy:.deployment_branch_policy}'
# {"can_admins_bypass":false,"deployment_branch_policy":{"custom_branch_policies":true,"protected_branches":false},"name":"ao-kernel-live-adapter-gate","protection_rules":[{"id":53201958,"node_id":"GA_kwDOSA13rs4DK8wm","type":"branch_policy"}]}

gh api repos/Halildeu/ao-kernel/environments/ao-kernel-live-adapter-gate/deployment-branch-policies \
  --jq '.branch_policies[] | {name:.name, type:.type}'
# {"name":"main","type":"branch"}

gh secret list --env ao-kernel-live-adapter-gate --repo Halildeu/ao-kernel
# empty
```

Fresh post-RI-6 metadata refresh on 2026-04-27 after PR
[#514](https://github.com/Halildeu/ao-kernel/pull/514) merged:

```bash
python3 scripts/live_adapter_gate_attest.py --artifact-path /tmp/gpp-2-post-ri6-attestation.json --output text
# overall_status: blocked
# finding_code: live_gate_credential_handle_missing
# runtime_binding_allowed: false
# live_execution_allowed: false
# support_widening: false
# checks:
# - protected_environment: pass
# - admin_bypass: pass
# - deployment_branch_policy: pass
# - credential_handle: blocked (live_gate_credential_handle_missing)
# - deployment_protection_gate: blocked (live_gate_deployment_protection_missing)
# - support_boundary: pass

gh api /apps/ao-kernel-live-adapter-gate --jq '{slug:.slug,id:.id,name:.name}'
# HTTP 404 Not Found

gh api repos/Halildeu/ao-kernel/environments/ao-kernel-live-adapter-gate/deployment_protection_rules
# {"total_count":0,"custom_deployment_protection_rules":[]}

gh secret list --env ao-kernel-live-adapter-gate --repo Halildeu/ao-kernel --json name,updatedAt
# []
```

## 3. Current Decision

`GPP-2` stays blocked.

The project-owned protected live-adapter gate is not ready because:

1. `ao-kernel-live-adapter-gate` is now present, but only the branch-policy
   protection rule is configured.
2. Deployment branch policy is custom and currently includes `main`.
3. Admin bypass is disabled.
4. `AO_CLAUDE_CODE_CLI_AUTH` is not visible as an environment secret handle.
5. The current selected release-gate model, superseded by GPP-2h/GPP-2i, is a
   GitHub App deployment protection rule; that app rule is not configured.
6. Only one repository collaborator is visible, so the earlier protected
   reviewer model remains unsuitable unless explicitly superseded by a real
   independent release authority.

## 4. Required External/Admin Work

Complete issue [#482](https://github.com/Halildeu/ao-kernel/issues/482):

1. Keep GitHub environment `ao-kernel-live-adapter-gate` present.
2. Keep deployment branch policy restricted to `main`.
3. Configure the selected GitHub App deployment protection rule on
   `ao-kernel-live-adapter-gate` with app slug
   `ao-kernel-live-adapter-gate`.
4. Fork-triggered events must not access protected credentials.
5. Store project-owned Claude Code CLI credential material, or an explicitly
   approved non-API-key equivalent, as environment secret handle
   `AO_CLAUDE_CODE_CLI_AUTH`.
6. Do not commit, print, or read back the secret value.

## 5. Follow-Up Gate

After #482 is complete, open a fresh prerequisite attestation slice. That slice
must collect live evidence that:

1. `gh api repos/Halildeu/ao-kernel/environments --jq '.environments[].name'`
   still includes `ao-kernel-live-adapter-gate`;
2. `gh api repos/Halildeu/ao-kernel/environments/ao-kernel-live-adapter-gate/deployment-branch-policies`
   still includes only the intended `main` policy;
3. `gh secret list --env ao-kernel-live-adapter-gate --repo Halildeu/ao-kernel`
   lists `AO_CLAUDE_CODE_CLI_AUTH`;
4. deployment protection evidence includes the selected enabled GitHub App rule
   with slug `ao-kernel-live-adapter-gate`;
5. fork-triggered contexts cannot read protected credentials.

Only if the follow-up attestation exits `prerequisites_ready` can `GPP-2`
runtime binding begin.

## 6. Forbidden Until Then

1. No runtime binding.
2. No live adapter execution.
3. No support widening.
4. No production-platform claim.
5. No secret value readback.
6. No local operator auth treated as project-owned production evidence.
