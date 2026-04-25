# GPP-2d - Metadata-Only Live Gate Attestation Tool

**Status:** implemented; no support widening
**Date:** 2026-04-25
**Issue:** [#487](https://github.com/Halildeu/ao-kernel/issues/487)
**Program head:** `GPP-2` remains blocked
**Support impact:** none
**Runtime impact:** none

## 1. Purpose

Make protected live-adapter gate attestation repeatable.

Earlier GPP-2b/GPP-2c slices used live `gh` commands and issue comments to
record the gate state. This slice adds a metadata-only tool that emits a
machine-readable attestation artifact without reading secret values, binding the
workflow, running `claude`, or widening support.

## 2. Implemented Surface

1. Helper:
   `ao_kernel.live_adapter_gate.build_live_adapter_gate_attestation()`.
2. Writer:
   `ao_kernel.live_adapter_gate.write_live_adapter_gate_attestation()`.
3. Renderer:
   `ao_kernel.live_adapter_gate.render_live_adapter_gate_attestation_text()`.
4. CLI:
   `python3 scripts/live_adapter_gate_attest.py`.
5. Artifact:
   `live-adapter-gate-attestation.v1.json`.

## 3. Checks

The attestation evaluates metadata only:

1. environment `ao-kernel-live-adapter-gate` exists;
2. admin bypass is disabled;
3. deployment branch policy is restricted to `main`;
4. environment secret handle `AO_CLAUDE_CODE_CLI_AUTH` exists by name;
5. required reviewer gate exists, or an explicitly approved equivalent release
   gate is supplied;
6. support boundary remains closed.

Secret values are never accepted, read, printed, or written.

## 4. Current Expected Result

With current live metadata, the artifact must be `blocked` because:

1. `AO_CLAUDE_CODE_CLI_AUTH` is still missing under the environment;
2. required reviewer protection is still missing;
3. only one collaborator is visible, so a non-self reviewer gate is not yet
   possible.

`runtime_binding_allowed=false`, `live_execution_allowed=false`, and
`support_widening=false` remain the expected result until a future attestation
proves prerequisites ready.

## 5. Non-Goals

1. No runtime binding.
2. No live adapter execution.
3. No secret value readback.
4. No single-admin equivalent gate approval.
5. No support widening.
6. No production-platform claim.

## 6. Validation

1. Unit tests cover the current partial-provisioning blocked state.
2. Unit tests cover a synthetic metadata-ready state.
3. CLI fixture test proves deterministic artifact writing without live GitHub.
4. `python3 scripts/gpp_next.py` still reports `GPP-2` blocked.

