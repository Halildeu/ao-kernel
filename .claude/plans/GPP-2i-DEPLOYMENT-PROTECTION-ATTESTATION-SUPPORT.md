# GPP-2i - Deployment Protection Attestation Support

**Issue:** [#497](https://github.com/Halildeu/ao-kernel/issues/497)
**Date:** 2026-04-26
**Program head:** `GPP-2` remains blocked
**Decision:** `deployment_protection_attestation_supported_gate_still_blocked`
**Support impact:** none
**Runtime impact:** metadata-only attestation support; no live execution

## Purpose

`GPP-2h` selected GitHub App deployment protection as the independent release
gate model. This slice updates the repository's metadata-only attestation
surface to understand that selected model before any external provisioning or
runtime binding starts.

The implementation does not create a GitHub App, does not configure
environment protection, does not set or read secrets, and does not execute
`claude-code-cli`.

## Implemented Contract

The live-adapter prerequisite attestation now carries:

1. `release_gate_model = github_app_deployment_protection_rule`;
2. `required_deployment_protection_app_slug = ao-kernel-live-adapter-gate`;
3. a fail-closed `deployment_protection_gate` check;
4. deployment protection metadata fixture support in
   `scripts/live_adapter_gate_attest.py`;
5. live metadata collection from GitHub's environment deployment protection
   rules endpoint, with failure treated as an empty/missing app gate rather
   than a pass.

The selected gate is only satisfied when the required GitHub App slug is
present and enabled in deployment protection metadata.

## Preserved Guards

1. `GPP-2` remains blocked.
2. `runtime_binding_allowed` remains false on the current live repo because
   the required credential handle and deployment protection app are still not
   attested.
3. `live_execution_allowed` remains false even for ready metadata-only
   fixtures; live execution is a later runtime-binding gate.
4. `support_widening` remains false.
5. `--equivalent-release-gate-approved` does not satisfy the selected
   deployment protection bot gate.
6. A wrong GitHub App slug blocks.
7. PAT-backed bot user reviewer remains forbidden.

## Current Live Result

Current live attestation remains blocked:

```text
credential_handle: blocked (live_gate_credential_handle_missing)
deployment_protection_gate: blocked (live_gate_deployment_protection_missing)
runtime_binding_allowed: false
live_execution_allowed: false
support_widening: false
```

This is the expected result until the external/admin provisioning step creates
or installs the selected GitHub App deployment protection rule and sets
`AO_CLAUDE_CODE_CLI_AUTH` as an environment secret handle.

## Next Step

The next action is external/admin provisioning:

1. create or install the GitHub App/policy service with slug
   `ao-kernel-live-adapter-gate`;
2. attach it as a deployment protection rule to the
   `ao-kernel-live-adapter-gate` environment;
3. set `AO_CLAUDE_CODE_CLI_AUTH` under that environment without secret value
   readback;
4. run a fresh metadata-only prerequisite attestation.

Only after that attestation exits `ready` may `GPP-2` runtime binding begin.

## Exit State

This slice closes as
`deployment_protection_attestation_supported_gate_still_blocked`.

It implements attestation support only. It does not unblock `GPP-2`, does not
run a live adapter, does not configure GitHub, and does not widen support.
