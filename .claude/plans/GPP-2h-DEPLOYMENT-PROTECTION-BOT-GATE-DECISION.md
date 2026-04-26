# GPP-2h - Deployment Protection Bot Gate Decision

**Issue:** [#495](https://github.com/Halildeu/ao-kernel/issues/495)
**Date:** 2026-04-26
**Program head:** `GPP-2` remains blocked
**Decision:** `github_app_deployment_protection_rule_selected`
**Support impact:** none
**Runtime impact:** none

## Purpose

This record supersedes the first provisioning path selected in `GPP-2g`.

The intended release authority is not a second product user account and not a
bot account that clicks approval through a PAT. The selected model is a GitHub
App or policy service connected to GitHub environment deployment protection.
That app evaluates repo-owned evidence and approves protected environment
deployment only when the gate contract is satisfied.

Claude/MCP consultation remains advisory only and is unchanged by this record.

## Decision

The selected independent release gate model for `GPP-2` is:

```text
GitHub App deployment protection rule
```

The model is a policy bot, not a user-like reviewer account.

Rejected models for this lane:

1. product end-user account as release authority;
2. second GitHub user account controlled by the same operator as a rubber
   stamp;
3. PAT-backed bot account listed as required reviewer;
4. Claude/MCP consultation as release authority;
5. `--equivalent-release-gate-approved` while `GPP-2e` remains
   `not_approved`.

Fallback models remain valid only through a future explicit decision:

1. human/team GitHub-native required reviewer;
2. OIDC-backed external secret broker.

## Deployment Protection Bot Contract

The future GitHub App or policy service must approve the protected deployment
only after checking repo-owned evidence. Minimum approval inputs:

1. repository is `Halildeu/ao-kernel`;
2. ref is protected `main`;
3. workflow identity is the approved live-adapter gate workflow;
4. default CI and required checks are green for the approved ref;
5. `scripts/live_adapter_gate_attest.py` or its successor reports a passing
   protected gate prerequisite attestation;
6. `AO_CLAUDE_CODE_CLI_AUTH` exists as an environment secret handle or the
   selected broker handle exists;
7. `support_widening_allowed=false` remains true until a later GPP-9
   production claim decision;
8. `production_platform_claim_allowed=false` remains true until a later GPP-9
   production claim decision;
9. no secret value is read, logged, transformed, echoed, or sent through MCP;
10. fork-triggered or untrusted contexts cannot access protected credentials.

The bot must fail closed. Missing evidence, stale evidence, unrecognized
workflow identity, non-main ref, missing credential handle, or support-boundary
drift must block approval.

## Current Blocking State

`GPP-2` remains blocked after this record.

Current live gate state:

1. `ao-kernel-live-adapter-gate` exists;
2. admin bypass is disabled;
3. deployment branch policy is restricted to `main`;
4. `AO_CLAUDE_CODE_CLI_AUTH` is still not attested as an environment secret
   handle;
5. no GitHub App deployment protection rule is implemented or attested;
6. before GPP-2i, `scripts/live_adapter_gate_attest.py` checked required
   reviewer or equivalent release gate metadata, not the selected deployment
   protection bot metadata shape.

## Next Implementation Slices

The next repo-code slice has been implemented:

```text
GPP-2i - deployment protection attestation support
```

Scope for `GPP-2i`:

1. extend the metadata-only live gate attestation model to represent GitHub App
   deployment protection evidence;
2. keep required reviewer metadata as historical/alternate evidence, not the
   selected path;
3. add tests for missing app, wrong app, stale app/evidence, and app-present
   but credential-missing states;
4. keep all support/runtime/production flags false;
5. do not create the GitHub App, set secrets, or run a live adapter.

`GPP-2i` closes with the live gate still blocked until external/admin
provisioning supplies the selected app gate and credential handle.

The later external/admin provisioning step should configure the GitHub App
deployment protection rule in `ao-kernel-live-adapter-gate`, then set
`AO_CLAUDE_CODE_CLI_AUTH` without secret readback, then run a fresh attestation.

## Exit State

This slice closes as
`github_app_deployment_protection_rule_selected_no_support_widening`.

It selects the release authority model. It does not unblock `GPP-2`, does not
run a live adapter, does not create or read secrets, and does not widen support.
