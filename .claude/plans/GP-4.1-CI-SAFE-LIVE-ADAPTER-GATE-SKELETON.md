# GP-4.1 — CI-Safe Live Adapter Gate Skeleton

**Status:** Implemented slice
**Date:** 2026-04-24
**Tracker:** [#402](https://github.com/Halildeu/ao-kernel/issues/402)
**Parent tracker:** [#400](https://github.com/Halildeu/ao-kernel/issues/400)
**Program:** `GP-4` CI-managed live adapter gate design

## Purpose

Add the first concrete live-adapter gate surface without granting production
support. This slice gives the repo a manual workflow and machine-readable
artifact shape for the future gate, while intentionally avoiding live adapter
execution.

## Scope

Included:

1. `workflow_dispatch`-only GitHub Actions workflow:
   `.github/workflows/live-adapter-gate.yml`.
2. Deterministic report builder:
   `ao_kernel/live_adapter_gate.py`.
3. Operator wrapper:
   `scripts/live_adapter_gate_contract.py`.
4. Tests for report shape, script output, and workflow trigger safety.
5. Status/docs wording that keeps support unchanged.

Excluded:

1. No repository or environment secrets.
2. No `claude` binary invocation.
3. No `claude_code_cli_smoke.py` or governed workflow smoke from CI.
4. No live external adapter call.
5. No support widening, version bump, tag, or publish.

## Contract

The workflow emits `live-adapter-gate-contract.v1.json` as an artifact. The
current report is expected to say:

| Field | Value |
|---|---|
| `program_id` | `GP-4.1` |
| `adapter_id` | `claude-code-cli` |
| `support_tier` | `Beta (operator-managed)` |
| `overall_status` | `blocked` |
| `finding_code` | `live_gate_not_implemented` |
| `live_execution_attempted` | `false` |
| `support_widening` | `false` |

The GitHub Actions job may pass when it successfully emits this contract. That
does **not** mean the live adapter passed. The artifact itself remains
`blocked` until a later GP-4 slice implements protected live execution.

## Workflow Safety

The skeleton is intentionally narrow:

1. trigger is `workflow_dispatch` only;
2. `target_ref` is restricted to `main`;
3. `adapter_lane` is restricted to `claude-code-cli`;
4. workflow permissions are `contents: read`;
5. no secrets are referenced;
6. no live smoke helper is invoked.

## Support Boundary Impact

No support widening.

`claude-code-cli` remains `Beta (operator-managed)`. Production-certified
real-adapter support is still not granted because the gate does not yet run a
project-owned live adapter identity and does not record live preflight or
governed workflow smoke evidence.

## Next Slice

`GP-4.2` has since added the schema-backed evidence artifact contract in
`.claude/plans/GP-4.2-LIVE-ADAPTER-EVIDENCE-ARTIFACT-CONTRACT.md`, and
`GP-4.3` has added the protected environment / secret contract in
`.claude/plans/GP-4.3-PROTECTED-ENVIRONMENT-SECRET-CONTRACT.md`. `GP-4.4`
has since recorded the protected live rehearsal blocked decision in
`.claude/plans/GP-4.4-PROTECTED-LIVE-REHEARSAL-BLOCKED-DECISION.md`.
