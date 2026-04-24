# GP-5.3c - Workflow Opt-In Design Contract

**Status:** Closeout candidate
**Date:** 2026-04-24
**Authority:** `origin/main` at `5eedaa0`
**Parent tracker:** [#424](https://github.com/Halildeu/ao-kernel/issues/424)
**Slice issue:** [#435](https://github.com/Halildeu/ao-kernel/issues/435)
**Branch:** `codex/gp5-3c-workflow-opt-in`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gp5-3c`
**Decision:** `design_only_no_runtime_auto_feed`

## Purpose

Define the future opt-in shape for repo-intelligence workflow/context-compiler
integration without enabling runtime auto-feed.

`GP-5.3a` made retrieval evidence trustworthy enough to reference.
`GP-5.3b` made stdout Markdown handoff explicit. `GP-5.3c` records the next
contract boundary: if a workflow ever consumes repo-intelligence context
directly, it must be explicit, schema-backed, behavior-tested, and still
read-only.

## Scope

1. Add a contract-only schema for future repo-intelligence workflow context
   opt-in.
2. Require explicit opt-in, source evidence, current-only freshness, and
   safety flags.
3. Prove current bundled workflows do not declare repo-intelligence auto-feed.
4. Prove current `compile_context()` does not ingest arbitrary
   `repo_query_context` from session input.
5. Update support docs and GP-5 status without widening support.

## Non-Goals

1. No workflow-definition schema widening.
2. No executor integration.
3. No `context_compiler` parameter for repo query context.
4. No hidden prompt injection.
5. No MCP tool registration.
6. No root export or `.ao/context` query artifact writes.
7. No production semantic-correctness claim.
8. No support boundary widening.

## Contract Shape

The contract-only schema is:

`ao_kernel/defaults/schemas/repo-intelligence-workflow-context-opt-in.schema.v1.json`

A valid future opt-in must carry:

1. `enabled=true`;
2. `support_tier="beta_read_only_context"`;
3. `handoff_mode` of `operator_markdown_stdout` or `query_result_json_artifact`;
4. operator-visible input with `automatic_prompt_injection=false`;
5. `context_compiler_feed.enabled=true` plus explicit workflow config and
   behavior-test requirements;
6. source artifact hashes and namespace key prefix;
7. `content_status="current_only"`;
8. safety flags proving no root writes, context artifact writes, MCP exposure,
   vector writes, or hidden prompt injection.

This schema is intentionally not wired into workflow runtime in this slice.
Accepting a config while silently ignoring it would create a new truth gap.

## Behavior Pinned By This Slice

1. The schema self-validates.
2. A valid explicit contract passes validation.
3. Missing source evidence fails validation.
4. Hidden prompt injection fails validation.
5. Production support-tier claim fails validation.
6. Current bundled workflow definitions do not declare
   `repo_intelligence_context` or `repo_query_context`.
7. Current `compile_context()` ignores arbitrary `repo_query_context` in
   session input.

## RI-5 / GP-5.3 Interface

`GP-5.3c` does not consume RI-5 export artifacts.

| Artifact | GP-5.3c status |
|---|---|
| `.ao/context/repo_export_plan.json` | `not_used` |
| `CLAUDE.md` / `AGENTS.md` root exports | `not_used` |
| stdout Markdown from `repo query --output markdown` | explicit operator-provided input remains supported beta handoff |
| JSON query result | future opt-in evidence source, not runtime-consumed here |
| opt-in schema | contract-only, not wired into workflow runtime |

`RI-5a` may continue independently. A future runtime slice can reference this
schema only if it also updates workflow schema/runtime, behavior tests, docs,
and support boundary together.

## Support Boundary Impact

No support widening.

Repo intelligence remains beta read-only retrieval/context. Workflow
integration is still design-only and must not be described as shipped runtime
behavior.

## Next Slice

`GP-5.3d` should add explicit no-MCP/no-root-export guards around the query and
handoff surfaces, or `GP-5.1b` can proceed first if protected live-adapter gate
environment and credential-handle attestation is provided.

## Validation

Required validation for this slice:

1. `pytest -q tests/test_repo_intelligence_workflow_opt_in_contract.py tests/test_context_compiler.py`
2. `python3 -m ao_kernel doctor`
3. `git diff --check`
4. PR CI
