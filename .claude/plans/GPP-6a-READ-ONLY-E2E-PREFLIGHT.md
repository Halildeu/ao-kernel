# GPP-6a - Read-Only E2E Preflight

**Issue:** [#561](https://github.com/Halildeu/ao-kernel/issues/561)

**Decision:** `read_only_e2e_preflight_ready_execution_blocked_no_support_widening`

**Status:** completed / preparation only / no support widening

**Date:** 2026-04-28

## Scope

Add a preparation-only preflight for the GPP-6 read-only production E2E path.
This slice records the target chain and entry criteria without dispatching a
protected workflow, invoking a live adapter, writing repo-intelligence
artifacts, writing vectors, or performing any remote write.

## Decision

The GPP-6 preflight report is ready, but GPP-6 execution remains blocked by
upstream gates:

1. `GPP-2` protected live-adapter gate remains blocked.
2. `GPP-4` production-certified read-only adapter decision is missing.

The report therefore records:

```text
overall_status=ready
execution_status=blocked_by_upstream_gates
```

This means the preflight itself is usable as preparation evidence, not that
GPP-6 protected E2E execution is authorized.

## Evidence

This work package adds:

1. Preflight script:
   `scripts/gpp6_read_only_e2e_preflight.py`
2. Contract schema:
   `ao_kernel/defaults/schemas/gpp6-read-only-e2e-preflight.schema.v1.json`
3. Behavior tests:
   `tests/test_gpp6_read_only_e2e_preflight.py`

The report checks that GPP-5d closeout evidence is present, records GPP-2 and
GPP-4 as upstream blockers, and pins all side-effect flags closed.

## Non-Goals

1. No protected workflow is dispatched.
2. No live adapter is invoked.
3. No GPP-6 read-only E2E run is executed.
4. No repo-intelligence root export, artifact write, or vector write is
   introduced.
5. No remote write is performed.
6. No support tier is widened.
7. No production platform claim is made.

## Exit Decision

`read_only_e2e_preflight_ready_execution_blocked_no_support_widening`

GPP-6 can continue only as preparation work until GPP-2 protected gate
evidence and GPP-4 read-only adapter decision are ready.
