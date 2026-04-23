# PB-6.3 Context Orchestration Decision

**Date:** 2026-04-23
**Issue:** [#256](https://github.com/Halildeu/ao-kernel/issues/256)
**Parent:** [#243](https://github.com/Halildeu/ao-kernel/issues/243)
**Scope:** decision and owner-boundary record only; no runtime support widening

## Decision

`PRJ-CONTEXT-ORCHESTRATION` remains a later candidate, but it is not ready for
runtime-backed promotion in this slice.

Current classification:

| Axis | Decision | Reason |
|---|---|---|
| Promotion class | `remap-needed` | Live `ao_kernel.context` code exists, but the manifest still points at legacy ops/UI/spec surfaces. |
| Support boundary | keep quarantined | No explicit bundled handler exists and current entrypoints are not registered dispatch actions. |
| Runtime owner | `ao_kernel.context` package for primitives; no extension handler owner yet | The code owner is real, but the extension activation boundary is missing. |
| Next action | manifest/contract cleanup before implementation | Do not widen support until refs, action set, handler contract, tests, and docs line up. |

## Evidence Snapshot

Live inspection of the bundled manifest via `ExtensionRegistry.load_from_defaults()`
shows:

| Field | Value |
|---|---|
| `truth_tier` | `quarantined` |
| `runtime_handler_registered` | `False` |
| `remap_candidate_refs` | 5 |
| `missing_runtime_refs` | 4 |
| `ops` entrypoints | 9 |
| `ops_single_gate` entrypoints | 2 |
| `ui_surfaces` | 2 |
| `kernel_api_actions` | 0 |

Current ref audit:

| Ref | Current status | Decision |
|---|---|---|
| `policies/policy_context_orchestration.v1.json` | remap candidate | Map to `defaults/policies/policy_context_orchestration.v1.json`. |
| `schemas/context-pack-router-result.schema.v1.json` | remap candidate | Map to `defaults/schemas/context-pack-router-result.schema.v1.json`. |
| `schemas/context-pack.schema.v1.json` | remap candidate | Map to `defaults/schemas/context-pack.schema.v1.json`. |
| `schemas/policy-context-orchestration.schema.v1.json` | remap candidate | Map to `defaults/schemas/policy-context-orchestration.schema.v1.json`. |
| `schemas/session-context.schema.json` | remap candidate | Map to `defaults/schemas/session-context.schema.json` only if the file exists in the distribution; otherwise remove or replace. |
| `AGENTS.md` | missing | Do not keep as a bundled package ref unless the file is packaged. |
| `docs/OPERATIONS/EXTENSIONS.md` | missing | Replace with current public support docs or remove until an extension operations page exists. |
| `docs/OPERATIONS/SSOT-MAP.md` | missing | Replace with the current status SSOT or remove until packaged docs exist. |
| `extensions/PRJ-CONTEXT-ORCHESTRATION/tests/contract_test.py` | missing | Replace with real `tests/test_context_*.py` coverage only after a handler contract exists. |

## Owner Boundary

The live runtime primitives are under `ao_kernel.context`. They cover profile
routing, context compilation, session lifecycle, canonical memory, semantic
retrieval, and vector-store resolution. That is a broad surface; promoting the
extension as-is would overstate what is actually callable through the extension
dispatch layer.

Future runtime-backed promotion must introduce an explicit handler module:

```text
ao_kernel/extensions/handlers/prj_context_orchestration.py
```

The handler must be intentionally narrower than the current manifest. It should
start with read-only, offline, behavior-testable actions and must not expose
workspace write paths, session mutation, memory mutation, semantic retrieval
network dependencies, or UI cockpit surfaces in the first tranche.

Acceptable first-tranche action shape:

| Candidate action | Runtime source | Allowed in first tranche? | Reason |
|---|---|---|---|
| `context_profiles_list` | `ao_kernel.context.profile_router.PROFILES` | Yes | Pure read-only metadata; no workspace required. |
| `context_profile_detect` | `ao_kernel.context.profile_router.detect_profile` | Yes | Pure deterministic function over supplied messages. |
| `context_compile_preview` | `ao_kernel.context.context_compiler.compile_context` | Maybe later | Only safe if semantic search is forced off and inputs are caller-supplied. |
| `session_status` / `session_set` / `session_sync` | session lifecycle and workspace state | No | Workspace/state boundary needs a separate write/read contract. |
| `context_pack_build` / `context_reconcile` / `context_drift` | report-producing ops/spec surfaces | No | These are not active extension dispatch handlers today. |
| `cockpit_sections.context_orchestration` | UI surface | No | No shipped cockpit runtime is attached to this extension. |

## Required Contract Before Promotion

Before `PRJ-CONTEXT-ORCHESTRATION` can move from quarantined/contract cleanup to
runtime-backed, a separate implementation contract must define:

1. The exact `kernel_api_actions` action names.
2. The handler module and registration in `ao_kernel/extensions/bootstrap.py`.
3. Behavior-first tests for action registration and action payloads.
4. A package-installed smoke or doctor proof that the extension remains truthful.
5. Manifest ref cleanup from legacy top-level `policies/` and `schemas/` refs to
   package-local `defaults/...` refs, or explicit removal of non-packaged refs.
6. Public docs that say only those read-only actions are supported.

## Closeout

`PB-6.3` closes as a decision slice:

1. No runtime behavior changes.
2. No support boundary widening.
3. `PRJ-CONTEXT-ORCHESTRATION` remains non-shipped until the next implementation
   contract slice remaps refs and narrows action scope.
4. The next active slice should be a manifest/contract cleanup for the same
   extension, not another promotion candidate.
