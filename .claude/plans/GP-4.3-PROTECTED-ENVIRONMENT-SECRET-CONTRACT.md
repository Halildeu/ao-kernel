# GP-4.3 — Protected Environment / Secret Contract

**Status:** Implemented slice
**Date:** 2026-04-24
**Parent tracker:** [#400](https://github.com/Halildeu/ao-kernel/issues/400)
**Slice issue:** [#407](https://github.com/Halildeu/ao-kernel/issues/407)
**Predecessor:** `GP-4.2` live adapter evidence artifact contract

## Purpose

Define the protected GitHub environment, secret handle, and fork-safety
contract required before any project-owned `claude-code-cli` live adapter gate
can run.

This slice is still no-widening. It does not configure secret values, does not
call `claude`, and does not claim production-certified real-adapter support.

## Implemented Surface

1. Schema:
   `ao_kernel/defaults/schemas/live-adapter-gate-environment.schema.v1.json`
2. Runtime helpers:
   `build_live_adapter_gate_environment_contract()`,
   `write_live_adapter_gate_environment_contract()`,
   `validate_live_adapter_gate_environment_contract()`
3. CLI output:
   `scripts/live_adapter_gate_contract.py` now writes:
   - `live-adapter-gate-contract.v1.json`
   - `live-adapter-gate-evidence.v1.json`
   - `live-adapter-gate-environment-contract.v1.json`
4. Workflow artifact upload:
   `.github/workflows/live-adapter-gate.yml` uploads all three JSON files.

## Protected Environment Contract

The required future environment is:

| Field | Value |
|---|---|
| Environment name | `ao-kernel-live-adapter-gate` |
| Allowed refs | `main` |
| Required reviewers | `true` |
| Prevent self-review | `true` |
| Fork secrets | `false` |
| Forbidden events | `pull_request`, `pull_request_target`, `push` |

The required future secret handle is:

| Secret id | Purpose |
|---|---|
| `AO_CLAUDE_CODE_CLI_AUTH` | Project-owned Claude Code CLI auth material or equivalent non-API-key credential for protected live rehearsal |

No secret value is committed or read by this slice.

## Support Boundary

No support widening.

The new environment contract artifact is intentionally blocked:

1. `overall_status="blocked"`
2. `finding_code="live_gate_protected_environment_not_attested"`
3. `live_execution_allowed=false`
4. `support_widening=false`

The current repository environment inventory does not include
`ao-kernel-live-adapter-gate`; only `pypi` exists at implementation time. A
later slice must either configure and attest that environment or record an
explicit release-gate equivalent.

## Non-Goals

1. No GitHub environment creation in code.
2. No repository or environment secret values.
3. No live adapter execution.
4. No `pull_request_target` or fork-accessible secret path.
5. No support-tier promotion.

## Required Validation

1. Schema self-validation with Draft 2020-12.
2. Builder output validates against the bundled schema.
3. Schema rejects fake `live_execution_allowed=true`.
4. CLI writes the environment contract artifact.
5. Workflow remains manual, has no `secrets.` references, and does not bind a
   GitHub environment yet.

## Next Slice

`GP-4.4` may run a protected live rehearsal only after the protected environment
and project-owned credential are configured outside the repository and the run
can attach preflight + governed workflow smoke evidence. If that cannot be
done, `GP-4.4` should record an explicit blocked decision instead of widening
support.
