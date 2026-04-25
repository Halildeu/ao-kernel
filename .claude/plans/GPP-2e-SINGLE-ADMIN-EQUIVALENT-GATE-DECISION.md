# GPP-2e - Single-Admin Equivalent Release-Gate Decision

**Issue:** [#489](https://github.com/Halildeu/ao-kernel/issues/489)
**Date:** 2026-04-25
**Program head:** `GPP-2` remains blocked
**Decision:** `not_approved`
**Support impact:** none
**Runtime impact:** none

## Purpose

This record defines the decision boundary for using a single-admin equivalent
release gate instead of a true non-self GitHub environment reviewer for the
protected live-adapter gate.

The reviewer term here refers to a GitHub-native release authority model, not a
product end-user account. `GPP-2f` broadens the accepted future architecture to
an independent release gate: GitHub-native release authority, GitHub App
deployment protection, or OIDC-backed external secret broker.

It does not approve that equivalent gate. It prevents the
`--equivalent-release-gate-approved` attestation option from being used as an
implicit shortcut.

## Current Evidence

The live gate currently has these properties:

1. GitHub environment `ao-kernel-live-adapter-gate` exists.
2. Admin bypass is disabled.
3. Deployment branch policy is restricted to `main`.
4. Environment secret handle `AO_CLAUDE_CODE_CLI_AUTH` is absent.
5. Required reviewer protection is absent.
6. Only one collaborator, `Halildeu`, is visible through the GitHub
   collaborators API.

The repeatable attestation tool reports:

```text
overall_status: blocked
finding_code: live_gate_credential_handle_missing
runtime_binding_allowed: false
live_execution_allowed: false
support_widening: false
```

## Decision

The single-admin equivalent release gate is **not approved**.

The preferred resolution remains:

1. Add or designate an independent release authority.
2. Configure required reviewers on `ao-kernel-live-adapter-gate`.
3. Enable prevent-self-review or an equivalent non-self approval mechanism.
4. Add `AO_CLAUDE_CODE_CLI_AUTH` as an environment secret handle without
   reading back, printing, or committing the secret value.
5. Re-run metadata-only attestation and record the result in a follow-up PR.

An equivalent single-admin release gate can only be used after a future explicit
decision changes this record from `not_approved` to `approved`.

## Contract

Until a future explicit approval exists:

1. `scripts/live_adapter_gate_attest.py --equivalent-release-gate-approved`
   must not be used for production prerequisite attestation.
2. `GPP-2` runtime binding must not start.
3. Live adapter execution remains forbidden.
4. Support widening remains forbidden.
5. Production-platform claim remains forbidden.
6. Local operator auth remains non-production evidence.

## Exit State

This slice closes as `decision_recorded_not_approved_no_support_widening`.

It improves governance clarity only. It does not unblock `GPP-2`.
