# GPP-5c - Repo-Intelligence Read-Only Workflow Surface

**Issue:** [#557](https://github.com/Halildeu/ao-kernel/issues/557)

**Decision:** `repo_intelligence_read_only_workflow_surface_ready_no_support_widening`

**Status:** completed / no support widening

**Date:** 2026-04-28

## Scope

Add the output contract layer after GPP-5b. This slice turns an accepted
explicit repo-intelligence workflow context into a read-only workflow surface
payload that can be inspected by workflow runtime code without hidden prompt
injection or automatic context ingestion.

## Decision

The read-only workflow surface is accepted only when:

1. the upstream workflow context is already accepted;
2. the visible handoff file remains under the project root;
3. the current handoff file digest matches the accepted context digest;
4. namespace, source artifact hashes, freshness state, stale candidate count,
   source paths, line ranges, and source content hashes are present and valid;
5. the output contract carries no Markdown body or snippet text;
6. automatic prompt injection, context compiler auto-feed, MCP exposure, root
   export, vector writes, artifact writes, live adapter execution, support
   widening, and production platform claims remain disabled.

The surface is a pointer and metadata contract. Operators still have to provide
the Markdown handoff as visible agent input.

## Evidence

This work package adds:

1. Runtime builder:
   `ao_kernel/_internal/repo_intelligence/workflow_surface.py`
2. Public facade:
   `ao_kernel.repo_intelligence.build_repo_intelligence_read_only_workflow_surface`
3. Contract schema:
   `ao_kernel/defaults/schemas/repo-intelligence-read-only-workflow-surface.schema.v1.json`
4. Behavior tests:
   `tests/test_repo_intelligence_workflow_surface.py`

The behavior tests cover accepted schema-valid output, disabled/no-op config,
hash mismatch fail-closed behavior, missing metadata/unknown namespace
fail-closed behavior, and the negative guarantee that `compile_context()` does
not automatically ingest the read-only workflow surface or repo-query context.

## Non-Goals

1. No workflow runtime ingestion is enabled by default.
2. No Markdown body is embedded into the output payload.
3. No MCP repo-intelligence surface is added.
4. No root export, vector write, or artifact write is introduced.
5. No live adapter execution is enabled.
6. No support tier is widened.
7. No production platform claim is made.

## Exit Decision

`repo_intelligence_read_only_workflow_surface_ready_no_support_widening`

GPP-5 can continue into read-only workflow surface closeout and later GPP-6
preparation, but GPP-2 remains blocked and this slice does not authorize
live-adapter execution or any support/production promotion.
