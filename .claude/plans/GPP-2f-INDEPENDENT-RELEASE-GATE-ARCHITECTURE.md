# GPP-2f - Independent Release Gate Architecture Decision

**Issue:** [#491](https://github.com/Halildeu/ao-kernel/issues/491)
**Date:** 2026-04-26
**Program head:** `GPP-2` remains blocked
**Decision:** `independent_release_gate_required`
**Support impact:** none
**Runtime impact:** none

## Purpose

This record replaces the ambiguous "real reviewer" wording with an explicit
trust-boundary requirement for the protected live-adapter gate.

The required control is not a product end-user account. The required control is
an independent release authority that prevents the same automation/session from
both creating or triggering a change and opening access to live adapter
credentials.

## Decision

`GPP-2` requires an **independent release gate** before runtime binding can
start.

Acceptable models are:

1. **GitHub-native release authority**
   - A required GitHub environment reviewer or team.
   - The reviewer/team represents release authority, not an application
     end-user.
   - Self-review must be prevented or equivalently controlled.
2. **GitHub App deployment protection rule**
   - A GitHub App or policy service evaluates repo-owned evidence.
   - The app approves only after branch, CI, attestation, support-boundary, and
     runtime-binding prerequisites pass.
3. **OIDC-backed external secret broker**
   - The workflow receives no long-lived live adapter secret directly.
   - A broker releases credential material only after repository, ref,
     workflow, and attestation checks pass.

The previous single-admin equivalent gate remains **not approved**. It cannot
be used as the independent release gate unless a future explicit decision
supersedes `GPP-2e`.

## Current Blocking State

The protected environment is partially provisioned:

1. `ao-kernel-live-adapter-gate` exists.
2. Admin bypass is disabled.
3. Deployment branch policy is restricted to `main`.

The gate remains blocked because:

1. `AO_CLAUDE_CODE_CLI_AUTH` is not present as an environment secret handle.
2. No approved independent release gate model is implemented.
3. The single-admin equivalent gate is `not_approved`.

## Contract

Until a future explicit approval and attestation exist:

1. `GPP-2` runtime binding must not start.
2. Live adapter execution remains forbidden.
3. Support widening remains forbidden.
4. Production-platform claim remains forbidden.
5. `--equivalent-release-gate-approved` remains forbidden while `GPP-2e`
   remains `not_approved`.
6. Product end-user accounts must not be treated as release authority.

## Future Implementation Slices

The next implementation slice must choose one model:

1. `GPP-2g-github-release-authority`
2. `GPP-2g-deployment-protection-app`
3. `GPP-2g-oidc-secret-broker`

Only after a model is implemented and `AO_CLAUDE_CODE_CLI_AUTH` or the selected
broker handle is attested may a follow-up prerequisite attestation attempt to
unblock `GPP-2`.

## Exit State

This slice closes as `independent_release_gate_required_no_support_widening`.

It improves the trust-boundary model only. It does not unblock `GPP-2`.
