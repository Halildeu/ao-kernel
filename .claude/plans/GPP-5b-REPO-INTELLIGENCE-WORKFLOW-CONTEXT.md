# GPP-5b - Repo-Intelligence Explicit Workflow Context

**Issue:** [#555](https://github.com/Halildeu/ao-kernel/issues/555)

**Decision:** `repo_intelligence_explicit_workflow_context_ready_no_support_widening`

**Status:** completed / no support widening

**Date:** 2026-04-28

## Scope

Compose the GPP-5a product onboarding contract with the existing explicit
repo-query handoff validator so a workflow can resolve repo-intelligence
context only through an explicit, read-only, operator-visible handoff.

## Decision

The workflow-level repo-intelligence context surface is accepted only when:

1. product onboarding accepts the end-user path as GitHub App installation,
   selected repositories, and optional repo-local `.ao/*` configuration;
2. workflow opt-in accepts a current `repo query --output markdown` handoff;
3. the handoff is operator-visible and not automatically injected into prompts;
4. context compiler auto-feed remains disabled;
5. MCP exposure, root export, vector writes, artifact writes, live-adapter
   execution, support widening, and production platform claims all remain
   disabled.

The resolver returns handoff metadata and a visible handoff pointer. It does
not return hidden prompt content, write files, expose MCP tools, call adapters,
or change workflow runtime defaults.

## Evidence

This work package adds:

1. Runtime resolver:
   `ao_kernel/_internal/repo_intelligence/workflow_context.py`
2. Public facade:
   `ao_kernel.repo_intelligence.resolve_repo_intelligence_workflow_context`
3. Contract schema:
   `ao_kernel/defaults/schemas/repo-intelligence-explicit-workflow-context.schema.v1.json`
4. Behavior tests:
   `tests/test_repo_intelligence_workflow_context.py`

The behavior tests cover disabled/no-op config, valid visible handoff pointer
resolution, stale handoff fail-closed behavior, unsafe onboarding fail-closed
behavior, auto-feed rejection, and the negative guarantee that
`compile_context()` does not automatically ingest resolved repo-intelligence
workflow context.

## Non-Goals

1. No GitHub App runtime or webhook hosting is added in this slice.
2. No context compiler ingestion path is enabled by default.
3. No MCP repo-intelligence exposure is added.
4. No root export, vector write, or artifact write is introduced.
5. No live adapter execution is enabled.
6. No support tier is widened.
7. No production platform claim is made.

## Exit Decision

`repo_intelligence_explicit_workflow_context_ready_no_support_widening`

GPP-5 can continue into output contract and read-only workflow surface work.
GPP-2 remains blocked, and this slice does not authorize live-adapter
execution or any support/production promotion.
