# GP-5.3b - Agent Context Handoff Contract

**Status:** Closeout candidate
**Date:** 2026-04-24
**Authority:** `origin/main` at `91fd16f`
**Parent tracker:** [#424](https://github.com/Halildeu/ao-kernel/issues/424)
**Slice issue:** [#433](https://github.com/Halildeu/ao-kernel/issues/433)
**Branch:** `codex/gp5-3b-agent-context-handoff`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gp5-3b`
**Decision:** `keep_beta_explicit_stdout_handoff_contract`

## Purpose

Define the supported handoff boundary for `repo query --output markdown`
before repo-intelligence context is used by governed workflows.

This slice does not add workflow auto-injection. It makes the current
stdout-only Markdown handoff explicit in runtime output, tests, and support
docs.

## Scope

1. Add an operator-visible handoff contract to the Markdown context pack.
2. Pin the handoff contract in context-pack and CLI tests.
3. Keep root/context writes, MCP tools, root exports, and `context_compiler`
   auto-feed out of scope.
4. Keep repo-intelligence support tier at beta read-only retrieval.

## Non-Goals

1. No `context_compiler` integration.
2. No MCP tool registration.
3. No workflow input mutation.
4. No root authority file writes.
5. No `.ao/context` query artifact writes.
6. No production semantic-correctness guarantee.
7. No support boundary widening.

## Handoff Contract

The only supported GP-5.3b handoff is:

1. operator runs `repo query --output markdown`;
2. `ao-kernel` prints a deterministic Markdown context pack to stdout;
3. operator explicitly copies or supplies that stdout as agent input;
4. downstream agent/workflow treats it as visible task context, not hidden
   system memory.

The Markdown pack must say this directly. It must also state what is excluded:
no prompt injection, MCP tool, root export, vector write, or `context_compiler`
auto-feed.

## Behavior Pinned By This Slice

1. `build_repo_query_context_pack()` renders `## Handoff Contract`.
2. The pack states `stdout-only Markdown`.
3. The pack states the input is explicit operator/agent input.
4. The pack states `No hidden injection`.
5. CLI `repo query --output markdown` exposes the same handoff contract.
6. Existing read-only assertions continue to prove no root authority writes.

## RI-5 / GP-5.3 Interface

`GP-5.3b` does not consume RI-5 export artifacts.

| Artifact | GP-5.3b status |
|---|---|
| `.ao/context/repo_export_plan.json` | `not_used` |
| `CLAUDE.md` / `AGENTS.md` root exports | `not_used` |
| stdout Markdown from `repo query --output markdown` | explicit operator-provided input |
| JSON query result | upstream evidence source from `GP-5.3a` |

`RI-5a` may continue independently. A future machine-readable handoff or root
export must be a separate slice with schema, digest, stale-plan behavior, and
behavior tests.

## Support Boundary Impact

No support widening.

`repo query --output markdown` remains beta read-only retrieval context. The
slice improves the handoff contract for agents and operators, but it does not
certify production workflow integration or arbitrary coding-task relevance.

## Next Slice

`GP-5.3c` should design an opt-in workflow/context compiler integration only
after this explicit handoff boundary is accepted. It must remain fail-closed
and cannot silently consume `repo query` output.

## Validation

Required validation for this slice:

1. `pytest -q tests/test_repo_intelligence_context_pack_builder.py tests/test_cli_repo_query.py`
2. `python3 -m ao_kernel doctor`
3. `git diff --check`
4. PR CI
