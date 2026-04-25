# GPP-2b - External Admin Provisioning Tracker

**Status:** open external/admin action
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

## 3. Current Decision

`GPP-2` stays blocked.

The project-owned protected live-adapter gate is not ready because:

1. `ao-kernel-live-adapter-gate` is not present in the GitHub environment
   inventory.
2. `AO_CLAUDE_CODE_CLI_AUTH` is not visible as a repository secret handle.
3. Environment-scoped secret attestation cannot pass until the environment
   exists.
4. Only one repository collaborator is visible, so the protected reviewer model
   needs a non-triggering reviewer/admin or an explicitly approved equivalent
   release gate before self-review prevention can be meaningful.

## 4. Required External/Admin Work

Complete issue [#482](https://github.com/Halildeu/ao-kernel/issues/482):

1. Create or designate GitHub environment `ao-kernel-live-adapter-gate`.
2. Configure environment protection to match the existing contract:
   - allowed deployment ref: `main`;
   - required reviewers enabled;
   - prevent self-review enabled;
   - fork-triggered events cannot access protected credentials.
3. Add at least one non-triggering maintainer reviewer, or record an explicitly
   approved release-gate equivalent if the repository remains single-admin.
4. Store project-owned Claude Code CLI credential material, or an explicitly
   approved non-API-key equivalent, as environment secret handle
   `AO_CLAUDE_CODE_CLI_AUTH`.
5. Do not commit, print, or read back the secret value.

## 5. Follow-Up Gate

After #482 is complete, open a fresh prerequisite attestation slice. That slice
must collect live evidence that:

1. `gh api repos/Halildeu/ao-kernel/environments --jq '.environments[].name'`
   includes `ao-kernel-live-adapter-gate`;
2. `gh secret list --env ao-kernel-live-adapter-gate --repo Halildeu/ao-kernel`
   lists `AO_CLAUDE_CODE_CLI_AUTH`;
3. environment protection evidence is compatible with the protected gate
   contract;
4. fork-triggered contexts cannot read protected credentials.

Only if the follow-up attestation exits `prerequisites_ready` can `GPP-2`
runtime binding begin.

## 6. Forbidden Until Then

1. No runtime binding.
2. No live adapter execution.
3. No support widening.
4. No production-platform claim.
5. No secret value readback.
6. No local operator auth treated as project-owned production evidence.

