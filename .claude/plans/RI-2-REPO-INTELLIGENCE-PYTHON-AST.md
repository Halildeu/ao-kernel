# RI-2 — Repo Intelligence Python AST Import Graph

**Status:** In progress
**Date:** 2026-04-24
**Branch:** `codex/repo-intelligence-ast`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-repo-intelligence-ast`
**Base:** `origin/main` at `48eeeea`
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

Add the second repo-intelligence tranche on top of RI-1:

1. parse Python files with the standard-library `ast` module;
2. build a deterministic local import graph;
3. build a deterministic top-level symbol index;
4. write the new schema-backed artifacts under `.ao/context/`;
5. keep the feature read-only, local-only, and Beta / experimental.

## Decision

Proceed with RI-2 only if the implementation stays inside this boundary:

1. no LLM calls;
2. no network access;
3. no vector indexing;
4. no context-pack generation;
5. no root file writes;
6. no MCP tool exposure;
7. no cross-language parser;
8. no dynamic import execution;
9. no dependency resolver or environment introspection.

## New Artifacts

RI-2 adds exactly these default artifacts:

```text
.ao/context/import_graph.json
.ao/context/symbol_index.json
```

The existing manifest is extended to include the two new artifacts:

```text
.ao/context/repo_index_manifest.json
```

`import_graph.json` includes:

1. schema version;
2. generator metadata;
3. project metadata copied from `repo_map`;
4. deterministic summary counts;
5. Python modules from RI-1 candidates;
6. AST-derived import edges;
7. parse diagnostics.

`symbol_index.json` includes:

1. schema version;
2. generator metadata;
3. project metadata copied from `repo_map`;
4. deterministic summary counts;
5. top-level classes, functions, async functions, assignments, and imported
   names;
6. parse diagnostics.

## CLI Contract

The primary command remains:

```bash
python3 -m ao_kernel repo scan --project-root . --output json
```

RI-2 extends the command output by adding the new artifacts to the artifact
list. The command still writes only under `.ao/context/`.

## Planned Files

Implementation:

```text
ao_kernel/_internal/repo_intelligence/python_ast_indexer.py
ao_kernel/_internal/repo_intelligence/artifacts.py
ao_kernel/repo_intelligence/__init__.py
ao_kernel/cli.py
```

Schemas:

```text
ao_kernel/defaults/schemas/python-import-graph.schema.v1.json
ao_kernel/defaults/schemas/python-symbol-index.schema.v1.json
```

Tests:

```text
tests/test_repo_intelligence_python_ast_indexer.py
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
2. Sort modules, edges, symbols, and diagnostics deterministically.
3. Parse source files without executing code.
4. Do not follow symlinks.
5. Treat parse errors as diagnostics, not hard command failures.
6. Keep timestamps only in artifact generator metadata.

## Acceptance Criteria

- [x] Work is on `codex/repo-intelligence-ast`, not `main`.
- [x] Work is in `/Users/halilkocoglu/Documents/ao-kernel-repo-intelligence-ast`.
- [x] Branch is based on current `origin/main` after RI-1 merge.
- [x] Initial worktree status is clean.
- [x] `python3 -m ao_kernel repo scan --project-root . --output json` writes
      `repo_map.json`, `import_graph.json`, `symbol_index.json`, and
      `repo_index_manifest.json`.
- [x] All artifacts validate against bundled schemas.
- [x] Import graph is AST-derived, deterministic, and handles relative imports.
- [x] Symbol index is AST-derived, deterministic, and includes top-level
      definitions and imported aliases.
- [x] Python syntax errors are recorded as diagnostics without stopping the
      whole scan.
- [x] Root files are not written.
- [x] No LLM, network, vector indexing, MCP surface, or context-pack generation
      is added.
- [x] Focused tests pass.
- [x] `ruff check ao_kernel/ tests/` passes.
- [x] `mypy ao_kernel/` passes.
- [x] `python3 scripts/packaging_smoke.py` passes.

## Step-by-Step Plan

### Step 0 — Baseline

- [x] Confirm dedicated worktree.
- [x] Confirm branch is not `main`.
- [x] Confirm base is `origin/main` with RI-1 merged.
- [x] Confirm initial status is clean.
- [x] Inspect RI-1 scanner, artifacts, CLI, schemas, and tests.

### Step 1 — Schemas

- [x] Add import graph schema.
- [x] Add symbol index schema.
- [x] Extend manifest schema references through artifact writer output.
- [x] Validate new schemas in tests.

### Step 2 — AST Indexer

- [x] Add `python_ast_indexer.py`.
- [x] Parse only Python source files from RI-1 candidates.
- [x] Build module records.
- [x] Build import edges.
- [x] Build top-level symbol records.
- [x] Record parse/read diagnostics.

### Step 3 — Artifact Writer

- [x] Validate import graph and symbol index.
- [x] Write new artifacts with shared `write_json_atomic`.
- [x] Include all artifacts in `repo_index_manifest.json`.

### Step 4 — CLI

- [x] Wire AST indexing into `repo scan`.
- [x] Keep `--output text|json` behavior stable.
- [x] Ensure command writes only under `.ao/context/`.

### Step 5 — Tests

- [x] Add AST indexer tests.
- [x] Update artifact/schema tests.
- [x] Update CLI artifact list tests.
- [x] Cover syntax-error diagnostics.

### Step 6 — Docs / Boundary

- [x] Update public beta docs.
- [x] Update support boundary docs.
- [x] Avoid stable support widening claims.

### Step 7 — Validation

- [x] Run focused RI-2 tests.
- [x] Run CLI smoke.
- [x] Run ruff.
- [x] Run mypy.
- [x] Run packaging smoke.
- [x] Check `git diff --check`.

## Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| Accidentally executing code | Unsafe scanner behavior | Use only `ast.parse`; never import modules |
| Root export creep | Authority docs overwritten | Keep all writes under `.ao/context/` |
| Vector memory pollution | Stale or wrong memory | No vector indexing in RI-2 |
| Non-deterministic graph output | Unstable artifacts/tests | Sort all records by stable keys |
| Parser failure stops scan | Poor behavior on real repos | Emit diagnostics and continue |
| Support overclaim | Users expect stable API | Keep docs Beta / experimental |

## Follow-Up Slices

These are explicitly out of RI-2:

1. `RI-3` — deterministic agent context pack generation.
2. `RI-4` — repo chunking and vector indexing.
3. `RI-5` — explicit root export with confirm-write.

## Tracking Log

| Date | Status | Notes |
|---|---|---|
| 2026-04-24 | Draft | Tracking document created before implementation. |
| 2026-04-24 | Implementation | Added AST indexer, import graph schema, symbol index schema, artifact writer integration, CLI wiring, tests, and Beta docs updates. |
| 2026-04-24 | Focused validation | RI-2 focused tests, RI-1/RI-2 repo-intelligence tests, CLI smoke, ruff, and mypy passed. |
| 2026-04-24 | Rebase | Rebased cleanly onto `origin/main` at `48eeeea` after GP-4.4 merged. |
| 2026-04-24 | Final validation | Doctor returned `8 OK, 1 WARN, 0 FAIL`; packaging smoke passed; `git diff --check` passed; full coverage passed with `2921 passed, 1 skipped`, total coverage `85.61%`. |
