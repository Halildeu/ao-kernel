# GP-4.4 — Protected Live Rehearsal Blocked Decision

**Status:** Implemented slice
**Date:** 2026-04-24
**Parent tracker:** [#400](https://github.com/Halildeu/ao-kernel/issues/400)
**Slice issue:** [#410](https://github.com/Halildeu/ao-kernel/issues/410)
**Predecessor:** `GP-4.3` protected environment / secret contract

## Purpose

Record the `GP-4.4` decision for the CI-managed live adapter gate.

The required protected GitHub environment and project-owned Claude Code CLI
credential are not attested, so the correct outcome is an explicit blocked
decision. This slice does not run a live adapter, does not configure secrets,
does not bind a GitHub environment, and does not widen support.

## Live Prerequisite Check

At implementation time the repository environment inventory contains only:

| Environment | Meaning |
|---|---|
| `pypi` | existing publish environment |

The required future live adapter gate environment is not present:

| Required environment | Status |
|---|---|
| `ao-kernel-live-adapter-gate` | not attested |

The required future project-owned credential is also not attested:

| Secret handle | Status |
|---|---|
| `AO_CLAUDE_CODE_CLI_AUTH` | not attested |

## Implemented Surface

1. Schema:
   `ao_kernel/defaults/schemas/live-adapter-gate-rehearsal-decision.schema.v1.json`
2. Runtime helpers:
   `build_live_adapter_gate_rehearsal_decision()`,
   `write_live_adapter_gate_rehearsal_decision()`,
   `validate_live_adapter_gate_rehearsal_decision()`
3. CLI output:
   `scripts/live_adapter_gate_contract.py` now writes:
   - `live-adapter-gate-contract.v1.json`
   - `live-adapter-gate-evidence.v1.json`
   - `live-adapter-gate-environment-contract.v1.json`
   - `live-adapter-gate-rehearsal-decision.v1.json`
4. Workflow artifact upload:
   `.github/workflows/live-adapter-gate.yml` uploads all four JSON files.

## Decision

The new rehearsal decision artifact is intentionally blocked:

1. `overall_status="blocked"`
2. `decision="blocked_no_rehearsal"`
3. `finding_code="live_gate_rehearsal_blocked_missing_protected_prerequisites"`
4. `live_rehearsal_attempted=false`
5. `live_execution_allowed=false`
6. `support_widening=false`

## Support Boundary

No support widening.

`claude-code-cli` remains `Beta (operator-managed)`. A green
`live-adapter-gate` workflow means blocked artifacts were emitted, not that a
live adapter passed.

## Non-Goals

1. No GitHub environment creation.
2. No repository or environment secret values.
3. No workflow `environment:` binding.
4. No `claude` invocation.
5. No support-tier promotion.

## Required Validation

1. Schema self-validation with Draft 2020-12.
2. Builder output validates against the bundled schema.
3. Schema rejects fake `live_rehearsal_attempted=true`.
4. CLI writes the rehearsal decision artifact.
5. Workflow remains manual, has no `secrets.` references, and does not bind a
   GitHub environment.

## Next Slice

`GP-4.5` should close the support-boundary decision: keep
`claude-code-cli` as operator-managed beta unless a future separately approved
protected live gate is configured and attested.
