# GPP-5d - Repo-Intelligence Closeout Preflight

**Issue:** [#559](https://github.com/Halildeu/ao-kernel/issues/559)

**Decision:** `repo_intelligence_read_only_workflow_surface_closed_no_support_widening`

**Status:** completed / no support widening

**Date:** 2026-04-28

## Scope

Close the GPP-5 repo-intelligence read-only workflow surface as a bounded
building block and prepare GPP-6 entry evidence without enabling GPP-6
execution.

This slice adds a schema-backed closeout preflight that checks:

1. GPP-5a product onboarding, GPP-5b explicit workflow context, and GPP-5c
   read-only workflow surface decisions are present in program status.
2. The public repo-intelligence contract surfaces and their JSON schemas are
   present.
3. The context compiler and SDK do not accept hidden repo-intelligence
   auto-feed parameters.
4. Default workflow definitions do not carry hidden repo-intelligence context
   feed tokens.
5. The MCP tool surface still exposes no repo-intelligence or repo query tool.
6. Support widening, production platform claim, and live adapter execution
   remain closed.

## Decision

GPP-5 is closed as a read-only product-workflow building block. The accepted
path is still explicit: GitHub App installation, selected repositories,
optional repo-local configuration, explicit operator-visible handoff, and a
metadata-only workflow surface pointer.

This closeout does not make repo intelligence a hidden prompt feed and does
not authorize runtime ingestion, MCP exposure, root export, artifact/vector
writes, live adapter execution, support widening, or production platform
claims.

## Evidence

This work package adds:

1. Closeout preflight script:
   `scripts/gpp5_repo_intelligence_closeout.py`
2. Contract schema:
   `ao_kernel/defaults/schemas/gpp5-repo-intelligence-closeout.schema.v1.json`
3. Behavior tests:
   `tests/test_gpp5_repo_intelligence_closeout.py`

The report exits `closed` only when all GPP-5a/GPP-5b/GPP-5c records, schemas,
public APIs, negative runtime guards, and program flags pass. It also records
GPP-6 readiness separately.

## GPP-6 Readiness

GPP-6 preparation may use the GPP-5d closeout report as repo-intelligence
evidence, but GPP-6 execution remains blocked by upstream gates:

1. `GPP-2` protected live-adapter gate is still blocked.
2. `GPP-4` production-certified read-only adapter decision is still missing.

The closeout report therefore records `gpp6_readiness.status` as
`blocked_by_upstream_gates` even when GPP-5 itself is closed.

## Non-Goals

1. No GPP-6 protected E2E run is started.
2. No live adapter is invoked.
3. No context compiler auto-feed is introduced.
4. No MCP repo-intelligence tool is exposed.
5. No root export or write-side artifact/vector write is introduced.
6. No end-user Cloud Run, vault, webhook, GitHub App private key, deployment
   protection service, or `ao-release-gate` hosting requirement is added.
7. No support tier is widened.
8. No production platform claim is made.

## Exit Decision

`repo_intelligence_read_only_workflow_surface_closed_no_support_widening`

GPP-5 is closed for read-only workflow-surface purposes. The next allowed
program work is GPP-6 preparation only; GPP-6 execution remains blocked until
GPP-2 protected gate evidence and GPP-4 read-only adapter decision are ready.
