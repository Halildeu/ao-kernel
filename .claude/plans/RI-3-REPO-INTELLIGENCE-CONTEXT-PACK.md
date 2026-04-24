# RI-3 — Repo Intelligence Deterministic Context Pack

**Status:** In progress
**Date:** 2026-04-24
**Branch:** `codex/repo-intelligence-context-pack`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-repo-intelligence-context-pack`
**Base:** `origin/main` at `bd422dc`
**Rule:** Never work directly on `main`.

## Operational Rules

These rules remain mandatory:

1. Work must happen in a dedicated worktree. Direct work on `main` is
   forbidden.
2. Completed work is integrated through PR review/CI and merge.
3. After a PR is merged, the authoritative source becomes `origin/main`.
4. Active feature worktrees do not update automatically after another PR merges.
5. Uncommitted changes must never be lost during refresh, rebase, branch
   switch, pull, or worktree cleanup.
6. Do not use destructive cleanup commands unless the user explicitly requests
   that exact operation.

## Purpose

Add the third repo-intelligence tranche on top of RI-1 and RI-2:

1. build a deterministic Markdown agent context pack from local artifacts;
2. write the pack only under `.ao/context/`;
3. include the pack in the repo index manifest;
4. keep the feature read-only, local-only, and Beta / experimental.

## Decision

Proceed with RI-3 only if the implementation stays inside this boundary:

1. no LLM calls;
2. no network access;
3. no vector indexing;
4. no MCP tool exposure;
5. no root file writes;
6. no `CLAUDE.md`, `AGENTS.md`, `ARCHITECTURE.md`, or `CODEX_CONTEXT.md`;
7. no target-specific Claude/Codex export;
8. no dynamic import execution.

## New Artifact

RI-3 adds exactly this default artifact:

```text
.ao/context/agent_pack.md
```

The existing manifest is extended to include the Markdown pack:

```text
.ao/context/repo_index_manifest.json
```

`agent_pack.md` includes deterministic sections for:

1. generation boundary;
2. project metadata;
3. repository summary;
4. language counts;
5. Python entrypoint candidates;
6. Python modules;
7. import edges;
8. top-level symbols;
9. diagnostics;
10. source file inventory excerpt;
11. pack limits.

## CLI Contract

The primary command remains:

```bash
python3 -m ao_kernel repo scan --project-root . --output json
```

RI-3 extends the command output by adding `.ao/context/agent_pack.md` to the
artifact list. The command still writes only under `.ao/context/`.

## Planned Files

Implementation:

```text
ao_kernel/_internal/repo_intelligence/context_pack_builder.py
ao_kernel/_internal/repo_intelligence/artifacts.py
ao_kernel/repo_intelligence/__init__.py
ao_kernel/cli.py
```

Tests:

```text
tests/test_repo_intelligence_context_pack_builder.py
tests/test_repo_intelligence_artifacts.py
tests/test_cli_repo_scan.py
```

Docs / support boundary:

```text
docs/PUBLIC-BETA.md
docs/SUPPORT-BOUNDARY.md
```

## Determinism Rules

1. Use repo-relative POSIX paths only.
2. Sort all rendered records deterministically.
3. Do not include generation timestamps in `agent_pack.md`.
4. Use fixed pack limits for large lists.
5. Do not read files while rendering the pack; consume RI-1/RI-2 documents.
6. Do not summarize with an LLM.

## Acceptance Criteria

- [x] Work is on `codex/repo-intelligence-context-pack`, not `main`.
- [x] Work is in `/Users/halilkocoglu/Documents/ao-kernel-repo-intelligence-context-pack`.
- [x] Branch is based on current `origin/main` after RI-2 merge.
- [x] Initial worktree status is clean.
- [x] `python3 -m ao_kernel repo scan --project-root . --output json` writes
      `repo_map.json`, `import_graph.json`, `symbol_index.json`,
      `agent_pack.md`, and `repo_index_manifest.json`.
- [x] `agent_pack.md` is deterministic across repeated scans except upstream
      JSON artifact timestamps do not affect it.
- [x] The manifest records the Markdown artifact with a format reference.
- [x] Root files are not written.
- [x] No LLM, network, vector indexing, MCP surface, target-specific export, or
      root export is added.
- [x] Focused tests pass.
- [x] `ruff check ao_kernel/ tests/` passes.
- [x] `mypy ao_kernel/` passes.
- [x] `python3 scripts/packaging_smoke.py` passes.

## Step-by-Step Plan

### Step 0 — Baseline

- [x] Confirm dedicated worktree.
- [x] Confirm branch is not `main`.
- [x] Confirm base is `origin/main` with RI-2 merged.
- [x] Confirm initial status is clean.
- [x] Inspect RI-1/RI-2 scanner, AST indexer, artifacts, CLI, docs, and tests.

### Step 1 — Context Pack Builder

- [x] Add `context_pack_builder.py`.
- [x] Render project and summary sections.
- [x] Render deterministic language, entrypoint, module, import edge, symbol,
      diagnostic, and file tables.
- [x] Add tests for deterministic output and pack limits.

### Step 2 — Artifact Writer

- [x] Add `AGENT_PACK_FILENAME`.
- [x] Write Markdown with shared `write_text_atomic`.
- [x] Extend manifest artifact records to support `format_ref`.
- [x] Keep existing JSON artifact behavior unchanged.

### Step 3 — CLI

- [x] Wire context pack generation into `repo scan`.
- [x] Keep `--output text|json` behavior stable.
- [x] Ensure command writes only under `.ao/context/`.

### Step 4 — Tests

- [x] Add context pack builder tests.
- [x] Update artifact writer tests.
- [x] Update CLI artifact list tests.
- [x] Cover absence of root file writes.

### Step 5 — Docs / Boundary

- [x] Update public beta docs.
- [x] Update support boundary docs.
- [x] Avoid stable support widening claims.

### Step 6 — Validation

- [x] Run focused RI-3 tests.
- [x] Run CLI smoke.
- [x] Run ruff.
- [x] Run mypy.
- [x] Run packaging smoke.
- [x] Check `git diff --check`.

## Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| Root export creep | Authority docs overwritten | Keep all writes under `.ao/context/` |
| Non-deterministic Markdown | Unstable pack hashes | Sort all records and omit timestamps |
| Over-large pack | Poor agent context ergonomics | Apply fixed excerpt limits |
| Support overclaim | Users expect stable API | Keep docs Beta / experimental |
| Schema/format confusion | Manifest ambiguity | Use `format_ref` for Markdown artifacts |

## Follow-Up Slices

These are explicitly out of RI-3:

1. `RI-4` — repo chunking and vector indexing.
2. `RI-5` — explicit root export with confirm-write.
3. target-specific `.ao/context/claude_context.md` and
   `.ao/context/codex_context.md` exports.

## Tracking Log

| Date | Status | Notes |
|---|---|---|
| 2026-04-24 | Draft | Tracking document created before implementation. |
| 2026-04-24 | Implementation | Added deterministic Markdown context pack builder, manifest format refs, artifact writer integration, CLI wiring, tests, and Beta docs updates. |
| 2026-04-24 | Focused validation | RI-3 focused tests, RI-1/RI-2/RI-3 repo-intelligence tests, CLI smoke, ruff, and mypy passed. |
| 2026-04-24 | Final validation | Doctor returned `8 OK, 1 WARN, 0 FAIL`; packaging smoke passed; `git diff --check` passed; full coverage passed with `2925 passed, 1 skipped`, total coverage `85.64%`. |
| 2026-04-24 | Rebase | Rebased cleanly onto `origin/main` at `bd422dc` after GP-4 support boundary closeout merged. |
| 2026-04-24 | Post-rebase validation | Focused repo-intelligence tests, ruff, mypy, doctor, packaging smoke, `git diff --check`, and full coverage passed. Full coverage: `2926 passed, 1 skipped`, total coverage `85.64%`. |
