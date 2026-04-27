# GPP-2l - Protected Live Gate Prerequisites Ready

**Status:** closeout candidate
**Date:** 2026-04-27
**Authority:** `origin/main` at `b1bf64a`
**Issue:** [#519](https://github.com/Halildeu/ao-kernel/issues/519)
**Branch:** `codex/gpp-2l-prereq-ready`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gpp-2l-prereq-ready`
**Program head:** `GPP-2` prerequisites ready; runtime binding not started
**Support impact:** none
**Runtime impact:** metadata-only attestation; no live execution

## 1. Purpose

Record the metadata-only prerequisite attestation after external/admin
provisioning supplied the selected GitHub App deployment protection rule and
the required environment secret handle.

Decision:

```text
protected_live_gate_prerequisites_ready_runtime_binding_not_started
```

This slice does not bind `.github/workflows/live-adapter-gate.yml` to the
protected environment, does not execute a live adapter, does not read secret
values, does not widen support, and does not claim production-platform
readiness.

## 2. Live Metadata Evidence

Collected from `origin/main` on 2026-04-27 after PR
[#518](https://github.com/Halildeu/ao-kernel/pull/518) merged and external
admin provisioning completed.

Startup checks:

```bash
git status --short --branch
# ## main...origin/main

git rev-list --left-right --count HEAD...origin/main
# 0 0

bash .claude/scripts/ops.sh preflight
# Preflight clean

python3 scripts/gpp_next.py
# Current WP: GPP-2 - Protected Live-Adapter Gate Runtime Binding
# Current status: blocked
# Support widening allowed: false
# Production platform claim allowed: false
# Live adapter execution allowed: false
```

Environment metadata:

```bash
gh api repos/Halildeu/ao-kernel/environments/ao-kernel-live-adapter-gate \
  --jq '{name:.name, can_admins_bypass:.can_admins_bypass, protection_rules:.protection_rules, deployment_branch_policy:.deployment_branch_policy}'
# {"can_admins_bypass":false,"deployment_branch_policy":{"custom_branch_policies":true,"protected_branches":false},"name":"ao-kernel-live-adapter-gate","protection_rules":[{"id":53201958,"node_id":"GA_kwDOSA13rs4DK8wm","type":"branch_policy"}]}
```

Deployment protection rule metadata:

```bash
gh api repos/Halildeu/ao-kernel/environments/ao-kernel-live-adapter-gate/deployment_protection_rules
# {"total_count":1,"custom_deployment_protection_rules":[{"id":53336469,"node_id":"GA_kwDOSA13rs4DLdmV","app":{"id":3522435,"node_id":"A_kwDOCx7tY84ANb-D","slug":"ao-kernel-live-adapter-gate","integration_url":"https://api.github.com/apps/ao-kernel-live-adapter-gate"},"enabled":true}]}
```

Environment secret handle metadata:

```bash
gh secret list --env ao-kernel-live-adapter-gate --repo Halildeu/ao-kernel --json name,updatedAt
# [{"name":"AO_CLAUDE_CODE_CLI_AUTH","updatedAt":"2026-04-27T17:17:12Z"}]
```

Metadata-only live-adapter gate attestation:

```bash
python3 scripts/live_adapter_gate_attest.py \
  --artifact-path /tmp/gpp-2-post-provisioning-attestation.json \
  --output text
# program_id: GPP-2d
# gate_id: ci-managed-live-adapter-gate
# adapter_id: claude-code-cli
# overall_status: ready
# finding_code: none
# runtime_binding_allowed: true
# live_execution_allowed: false
# support_widening: false
# checks:
# - protected_environment: pass
# - admin_bypass: pass
# - deployment_branch_policy: pass
# - credential_handle: pass
# - deployment_protection_gate: pass
# - support_boundary: pass
```

## 3. Current Decision

`GPP-2` is no longer blocked by missing protected prerequisites.

Passing checks:

1. protected environment exists;
2. admin bypass is disabled;
3. custom deployment branch policy includes `main`;
4. selected GitHub App deployment protection rule is enabled with slug
   `ao-kernel-live-adapter-gate`;
5. `AO_CLAUDE_CODE_CLI_AUTH` exists as an environment secret handle by
   metadata;
6. attestation reports `overall_status=ready`.

Still closed:

1. no runtime workflow binding has been applied;
2. no live adapter has been executed;
3. `live_execution_allowed=false`;
4. `support_widening=false`;
5. `production_platform_claim=false`.

## 4. Next Runtime Binding Slice

The next controlled slice may start `GPP-2` runtime binding from the ready
prerequisite state. That slice must remain fail-closed and should not treat
this metadata-ready state as live service certification.

Minimum scope for the next slice:

1. bind `.github/workflows/live-adapter-gate.yml` to
   `environment: ao-kernel-live-adapter-gate`;
2. reference `AO_CLAUDE_CODE_CLI_AUTH` only by handle;
3. keep fork and pull-request contexts away from protected credentials;
4. keep live execution disabled until protected workflow evidence is recorded;
5. preserve `support_widening=false` and `production_platform_claim=false`.

If the deployment protection app webhook/policy endpoint is not active when
that slice runs, the protected deployment must remain blocked. That is a
correct fail-closed result, not permission to bypass the gate.

## 5. Forbidden After This Slice

1. No secret value readback.
2. No local operator auth treated as project-owned production evidence.
3. No Claude/MCP advisory response treated as release authority.
4. No product end-user account or PAT-backed bot user treated as release
   authority.
5. No `--equivalent-release-gate-approved` while #489 remains not approved.
6. No live adapter execution until a later protected runtime evidence slice
   explicitly permits it.
7. No support widening.
8. No production platform claim.

## 6. Validation

```bash
python3 -m json.tool .claude/plans/gpp_status.v1.json
pytest -q tests/test_gpp_next.py
python3 scripts/live_adapter_gate_attest.py --artifact-path /tmp/gpp-2-post-provisioning-attestation.json --output text
python3 scripts/gpp_next.py
git diff --check
```

Expected closeout decision:

```text
protected_live_gate_prerequisites_ready_runtime_binding_not_started
```

Recorded closeout decision:

```text
protected_live_gate_prerequisites_ready_runtime_binding_not_started
```
