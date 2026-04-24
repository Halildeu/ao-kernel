# GP-4.2 — Live Adapter Evidence Artifact Contract

**Status:** Implemented slice
**Date:** 2026-04-24
**Parent tracker:** [#400](https://github.com/Halildeu/ao-kernel/issues/400)
**Slice issue:** [#404](https://github.com/Halildeu/ao-kernel/issues/404)
**Predecessor:** `GP-4.1` CI-safe live adapter gate skeleton

## Purpose

Define the machine-readable evidence artifact contract for the future protected
`claude-code-cli` live adapter gate without running a live adapter and without
widening support.

`GP-4.1` proved that a manual workflow can emit a blocked contract report.
`GP-4.2` makes the next layer explicit: which evidence files must exist before a
future support-boundary decision can even be considered.

## Implemented Surface

1. Bundled schema:
   `ao_kernel/defaults/schemas/live-adapter-gate-evidence.schema.v1.json`
2. Runtime helpers:
   `build_live_adapter_gate_evidence_artifact()`,
   `write_live_adapter_gate_evidence_artifact()`,
   `validate_live_adapter_gate_evidence_artifact()`
3. CLI output:
   `scripts/live_adapter_gate_contract.py` writes both:
   - `live-adapter-gate-contract.v1.json`
   - `live-adapter-gate-evidence.v1.json`
4. Workflow artifact upload:
   `.github/workflows/live-adapter-gate.yml` uploads both JSON files.

## Evidence Slots

The artifact records four promotion-gating requirements:

1. `gate_contract_report`
2. `preflight_report`
3. `governed_workflow_smoke_report`
4. `protected_environment_attestation`

Only the design contract report is present in this slice. The live preflight,
workflow smoke, and protected environment attestation are explicitly `blocked`
with stable finding codes.

## Support Boundary

No support widening.

The artifact schema intentionally requires:

1. `support_widening=false`
2. `promotion_decision.support_widening_allowed=false`
3. `promotion_decision.production_certified=false`

If a future slice wants a promoted/support-widening artifact, it must use a new
schema version and update the support docs through a separate decision gate.

## Non-Goals

1. No repository or environment secrets.
2. No live `claude` invocation.
3. No governed workflow smoke execution inside the manual gate.
4. No production-certified adapter claim.
5. No version bump, tag, publish, or stable support-boundary change.

## Required Validation

1. Schema self-validation with Draft 2020-12.
2. Builder output validates against the bundled schema.
3. Schema rejects fake support-widening artifacts.
4. CLI writes both canonical JSON files.
5. Workflow remains `workflow_dispatch` only and does not reference live smoke
   helpers or secrets.

## Next Slice

`GP-4.3` should define the protected GitHub environment / secret contract and
fork-safety rules. It should still avoid committing secret values and should not
run live adapters unless project-owned credentials and protected dispatch rules
exist.
