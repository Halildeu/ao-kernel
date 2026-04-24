# GP-5.3d - No-MCP / No-Root-Export Guard

**Status:** Closeout candidate
**Date:** 2026-04-24
**Authority:** `origin/main` at `54de6e9`
**Tracker:** [#424](https://github.com/Halildeu/ao-kernel/issues/424)
**Slice issue:** [#437](https://github.com/Halildeu/ao-kernel/issues/437)
**Branch:** `codex/gp5-3d-no-mcp-root-export`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gp5-3d`
**Decision:** `keep_beta_read_only_negative_boundary_pinned`

## Purpose

`GP-5.3a`, `GP-5.3b`, and `GP-5.3c` made repo-intelligence retrieval,
operator-visible handoff, and future opt-in shape more explicit. This slice
pins the negative boundary before any promotion decision: repo-intelligence
must not silently become an MCP tool, root authority export, root context
export, or hidden workflow/context feed.

## Scope

1. Add regression checks that the MCP tool surface has no repo-intelligence
   tool registration or dispatch entry.
2. Add regression checks that the `repo` CLI public subcommands remain limited
   to `scan`, `index`, and `query`.
3. Add help-text checks that repo-intelligence CLI commands do not advertise
   MCP or root-export flags.
4. Strengthen `repo query` side-effect tests so root authority files, MCP
   config exports, and `.ao/context/repo_export_plan.json` stay absent.
5. Update GP-5 status and support-boundary docs without widening support.

## Non-Goals

1. No MCP repo-intelligence tool implementation.
2. No root export implementation.
3. No `context_compiler` or executor auto-feed.
4. No RI-5 export-plan implementation.
5. No live adapter or protected environment gate change.
6. No support boundary widening.

## Evidence

Targeted local validation:

```bash
pytest -q tests/test_repo_intelligence_no_mcp_root_export_guard.py tests/test_cli_repo_query.py
python3 -m ao_kernel doctor
git diff --check
```

PR validation must include the regular CI gates before merge.

## Support Boundary Impact

Unchanged. Repo intelligence remains `Beta / experimental read-only` for
`repo scan`, `repo index`, and `repo query`. `repo query --output markdown`
remains an operator-visible stdout handoff only. There is still no supported
MCP repo-intelligence tool, no root export, no workflow runtime wiring, and no
automatic `context_compiler` feed.

## RI-5 Interface

`RI-5` continues to own explicit root/context export. `GP-5.3d` does not
consume `.ao/context/repo_export_plan.json`, does not require it, and does not
produce it. This slice only protects the current beta read-only surface from
accidental support widening.

## Next Slice

`GP-5.3e` should decide whether repo-intelligence read-only context can become
a governed workflow building block. That decision remains blocked from claiming
production support until protected live-adapter evidence and later GP-5 gates
exist.
