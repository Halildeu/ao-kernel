# RI-1 — Repo Intelligence Scan MVP

**Status:** Baseline refreshed / implementation pending
**Date:** 2026-04-24
**Branch:** `codex/repo-intelligence-scan`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-repo-intelligence`
**Rule:** Never work directly on `main`.

## Operational Rules

These rules are mandatory for this tranche and future repo-intelligence slices:

1. Work must happen in a dedicated worktree. Direct work on `main` is
   forbidden.
2. Each implementation slice uses its own `codex/...` branch.
3. Completed work is integrated through PR review/CI and merge, not by local
   direct writes to `main`.
4. After a PR is merged, the authoritative source becomes `origin/main`.
5. Active feature worktrees do not update automatically after another PR merges.
   They must be refreshed from `origin/main` before continuing implementation.
6. Uncommitted changes must never be lost during refresh, rebase, branch switch,
   pull, or worktree cleanup.
7. Before any refresh/rebase/switch/cleanup operation, run `git status
   --short --branch` and identify uncommitted files.
8. If uncommitted changes exist, either commit them intentionally, stash them
   explicitly, or stop and ask for direction. Do not discard them.
9. Never use destructive cleanup commands such as `git reset --hard`,
   `git checkout -- <path>`, or worktree deletion to clear uncommitted changes
   unless the user explicitly requests that exact operation.

## Consultation Notes

Claude MCP consultation was run against the current plan before
implementation. The result was **conditional pass** with one hard gate and
several implementation-contract refinements.

Final ping-pong result:

| Recommendation | Decision | Reason |
|---|---|---|
| Refresh from current `origin/main` before implementation | Accept | Prevents stale-base work and keeps `origin/main` authoritative. |
| Treat `ao_workspace_status` version `3.11.0` as package version | Reject / correct | It is `.ao/workspace.json` metadata, not the package version. |
| Load bundled schemas through `load_default` / resources | Accept | Avoids repo-root-relative schema path drift. |
| Use shared `write_json_atomic` for artifact writes | Accept | Keeps write semantics aligned with existing shared infrastructure. |
| Pin `--output text|json`, default `text` | Accept | Makes CLI behavior testable and stable. |
| Keep coverage gate above repo threshold | Accept | RI-1 should not weaken existing quality gates. |
| Verify `docs/SUPPORT-BOUNDARY.md` before docs edits | Accept | Avoids support-boundary drift. |
| Enumerate public facade exports | Accept | Prevents accidental API widening. |
| Retest low-level atomic writer mechanics in RI-1 tests | Adjust | RI-1 tests verify delegation to `write_json_atomic`; shared writer mechanics are not re-tested here. |
| If `.ao/` is missing, skip artifact writing gracefully | Reject | CLI should fail clearly with an `ao-kernel init` hint; silent skip hides setup errors. |
| Add RI-1 MCP surface | Defer / reject for this slice | MCP tooling is outside the first read-only scan PR. |
| Make `--workspace-root .ao` part of the primary command | Reject for RI-1 | Primary contract is `--project-root`; workspace is derived as `<project-root>/.ao`. |
| Let `artifacts.py` discover `.ao` | Reject | CLI owns workspace validation and context-dir creation; artifact helpers receive explicit paths. |

Clarification from local verification:

1. `ao_workspace_status` may report `.ao/workspace.json` metadata version
   (`3.11.0` in this worktree), which is not the package version.
2. Package version in both `HEAD` and `origin/main` is currently `4.0.0`.
3. The branch is still stale relative to `origin/main`; refresh remains a hard
   gate before code implementation.

## Purpose

Add the first repo-intelligence tranche as a narrow, read-only, deterministic
repo scan.

This slice is not an architecture summarizer, vector indexer, AST graph, MCP
tool, or Claude/Codex export surface. It only produces schema-backed local
artifacts under `.ao/context/`.

## Decision

Proceed with `RI-1` only if the implementation stays inside this boundary:

1. read repo metadata and file layout;
2. detect languages with deterministic rules;
3. identify Python package/module and entrypoint candidates without AST import
   graphing;
4. write artifacts only under `.ao/context/`;
5. validate artifacts against bundled JSON schemas;
6. keep support tier as `Beta / experimental read-only repo intelligence scan`.

## Non-Goals

This slice must not:

1. write root authority files such as `CLAUDE.md`, `AGENTS.md`,
   `ARCHITECTURE.md`, or `CODEX_CONTEXT.md`;
2. call an LLM;
3. use network access;
4. build vector indexes;
5. create AST/import/dependency graphs;
6. generate context packs;
7. expose a new MCP tool;
8. widen stable support claims.

## Planned Files

Implementation:

```text
ao_kernel/_internal/repo_intelligence/
  __init__.py
  artifacts.py
  ignore_rules.py
  language_detector.py
  scanner.py

ao_kernel/repo_intelligence/
  __init__.py
```

Schemas:

```text
ao_kernel/defaults/schemas/repo-map.schema.v1.json
ao_kernel/defaults/schemas/repo-index-manifest.schema.v1.json
```

Tests:

```text
tests/test_repo_intelligence_artifacts.py
tests/test_repo_intelligence_ignore_rules.py
tests/test_repo_intelligence_language_detector.py
tests/test_repo_intelligence_scanner.py
tests/test_cli_repo_scan.py
```

Docs / support boundary:

```text
docs/PUBLIC-BETA.md
docs/SUPPORT-BOUNDARY.md
```

## CLI Contract

Primary command:

```bash
python3 -m ao_kernel repo scan --project-root . --output json
```

Rules:

1. `--project-root` points at the repository root.
2. The command writes to `<project-root>/.ao/context/`.
3. The command does not require or accept root-file export flags in this slice.
4. If `.ao/` is missing, fail clearly and suggest `ao-kernel init`.
5. If `.ao/context/` is missing, create it safely.
6. `--output` supports `text` and `json`; default is `text`.
7. `--output json` prints a machine-readable command summary to stdout.
8. The CLI layer owns `.ao/` presence checks and `.ao/context/` creation.
   `artifacts.py` receives an explicit `context_dir` or explicit output paths
   and must not discover or decide the workspace location.

## Artifacts

The command writes exactly these default artifacts:

```text
.ao/context/repo_map.json
.ao/context/repo_index_manifest.json
```

`repo_map.json` should include:

1. schema version;
2. generator metadata (`ao-kernel` version, generated timestamp);
3. project root identity metadata;
4. deterministic summary counts;
5. included files with repo-relative POSIX paths;
6. ignored path summary;
7. language counts;
8. Python package/module candidates;
9. Python entrypoint candidates;
10. diagnostics for skipped or unreadable files.

`repo_index_manifest.json` should include:

1. schema version;
2. generated timestamp;
3. artifact paths;
4. artifact SHA-256 digests;
5. schema references;
6. generator version.

Artifact writes must use the shared atomic writer:

```python
from ao_kernel._internal.shared.utils import write_json_atomic
```

Schema loading/validation must use bundled defaults through
`ao_kernel.config.load_default("schemas", ...)` or an equivalent
`importlib.resources` path already used by the repo. Do not load bundled
schemas via repo-root-relative filesystem paths.

`artifacts.py` may rely on the shared writer's defensive parent-directory
behavior if that is how the utility is implemented, but RI-1 artifact tests
must not treat parent-directory creation as artifact-layer ownership.

## Determinism Rules

1. Sort all paths lexicographically by repo-relative POSIX path.
2. Do not include nondeterministic object ordering in JSON.
3. Use stable IDs derived from repo-relative paths where IDs are needed.
4. Treat timestamps as artifact metadata only; repeated runs on the same tree
   may differ in `generated_at`, but stable content sections must remain
   deterministically ordered.
5. Do not follow symlinks.
6. Do not read binary file contents.

## Default Ignore Rules

The scanner must ignore at least:

```text
.git
.ao
__pycache__
.pytest_cache
dist
build
.venv
*.egg-info
```

Future slices may add `.gitignore` parsing, but this MVP must not depend on a
third-party ignore parser unless already present in project dependencies.

## Acceptance Criteria

RI-1 is complete only when all items below are true:

- [ ] New work stays on `codex/repo-intelligence-scan`, not `main`.
- [ ] Work is done in the dedicated repo-intelligence worktree.
- [ ] Uncommitted changes are checked and preserved before any branch refresh.
- [ ] Branch is refreshed on current `origin/main` before Step 1 begins.
- [ ] Post-refresh `HEAD` is based on the current `origin/main`.
- [ ] `python3 -m ao_kernel repo scan --project-root . --output json` works.
- [ ] The command writes only under `.ao/context/`.
- [ ] `repo_map.json` validates against bundled schema.
- [ ] `repo_index_manifest.json` validates against bundled schema.
- [ ] Bundled schemas are loaded through `load_default` / `importlib.resources`.
- [ ] Artifact writes use `write_json_atomic` or an equally atomic tmp+fsync+rename path.
- [ ] Artifact-writer tests verify writes delegate to `write_json_atomic`;
      low-level atomic mechanics are not re-tested independently.
- [ ] `--output` default and `--output json` behavior are pinned and tested.
- [ ] Repeated scan on the same tree has deterministic sorted content.
- [ ] `.ao/context/` is created safely when missing.
- [ ] Missing `.ao/` fails with a clear `ao-kernel init` hint.
- [ ] Default ignore rules are covered by tests.
- [ ] Symlinks are not followed.
- [ ] Path output is repo-relative POSIX style.
- [ ] `ao_kernel/repo_intelligence/__init__.py` exposes only pre-approved narrow symbols.
- [ ] Unit tests cover language detection.
- [ ] Unit tests cover ignore rules.
- [ ] Unit tests cover scanner output.
- [ ] Unit tests cover artifact writing and schema validation.
- [ ] CLI behavior test covers the primary command.
- [ ] Docs mark this as `Beta / experimental read-only repo intelligence scan`.
- [ ] Existing shipped baseline docs are not widened accidentally.
- [ ] Overall coverage remains above the repo gate (`--fail-under=85`).
- [ ] Focused tests pass.
- [ ] Packaging smoke passes with `python3 scripts/packaging_smoke.py`.

## Step-by-Step Plan

### Step 0 — Baseline

- [x] Confirm worktree and branch.
- [x] Confirm work is not happening on `main`.
- [x] Run `git status --short --branch` and record uncommitted state.
- [x] Refresh branch on current `origin/main` before implementation begins.
- [x] Preserve any uncommitted changes before refresh/rebase.
- [x] Confirm post-refresh `HEAD` is based on current `origin/main`.
- [x] Verify package version from `pyproject.toml`; do not confuse it with
      `.ao/workspace.json` metadata version.
- [x] Verify `docs/SUPPORT-BOUNDARY.md` exists before planning edits.
- [x] Confirm no uncommitted unrelated implementation/doc changes.
- [x] Inspect current CLI subcommand structure.
- [x] Inspect schema loading / validation patterns.

Step 0 notes:

1. Rebased branch on `origin/main` at `71b456b` (`ops: require separate
   worktrees for feature work`).
2. Post-refresh status is `codex/repo-intelligence-scan...origin/main [ahead
   1]`.
3. `git merge-base --is-ancestor origin/main HEAD` returned success.
4. `git rev-list --left-right --count HEAD...origin/main` returned `1 0`.
5. Package version is `4.0.0` in both `pyproject.toml` and
   `ao_kernel/__init__.py`; `.ao/workspace.json` metadata version must not be
   used as package truth.
6. `docs/SUPPORT-BOUNDARY.md` exists.
7. Existing CLI uses `ao_kernel/cli.py` argparse subcommands with explicit
   dispatcher routing.
8. Existing schema patterns use `load_default("schemas", ...)`,
   `importlib.resources`, and `Draft202012Validator`.
9. The only remaining untracked file is `.ao/canonical_decisions.v1.v1.json.lock`,
   a 0-byte MCP consultation lock. It is preserved, intentionally uncommitted,
   and not part of RI-1.

### Step 1 — Schemas

- [ ] Add `repo-map.schema.v1.json`.
- [ ] Add `repo-index-manifest.schema.v1.json`.
- [ ] Add minimal schema validation tests.
- [ ] Use `load_default("schemas", ...)` / `importlib.resources` for schema loading.

### Step 2 — Internal Primitives

- [ ] Add `ao_kernel/_internal/repo_intelligence/__init__.py`.
- [ ] Add `language_detector.py`.
- [ ] Add `ignore_rules.py`.
- [ ] Add `artifacts.py`.
- [ ] Add `scanner.py`.
- [ ] Use shared `write_json_atomic` for artifact writes.
- [ ] Ensure `artifacts.py` accepts explicit `context_dir` / output paths and
      performs no `.ao` discovery.
- [ ] Keep direct filesystem writes inside `.ao/context/`.

### Step 3 — Public Facade

- [ ] Add `ao_kernel/repo_intelligence/__init__.py`.
- [ ] Expose only stable, narrow functions needed by CLI/tests.
- [ ] Public facade exports are limited to:
  - `scan_repo`
  - `write_repo_scan_artifacts`

### Step 4 — CLI

- [ ] Add `repo` subparser.
- [ ] Add `repo scan` command.
- [ ] Support `--project-root`.
- [ ] Support `--output text|json`, defaulting to `text`.
- [ ] Ensure missing `.ao/` produces a clear error.
- [ ] Ensure CLI owns `.ao/context/` creation before artifact writing.

### Step 5 — Tests

- [ ] Add language detector tests.
- [ ] Add ignore rules tests.
- [ ] Add scanner tests.
- [ ] Add artifact/schema validation tests.
- [ ] Add artifact test proving delegation to `write_json_atomic`.
- [ ] Add CLI behavior test.
- [ ] Add CLI test for missing `.ao/` error with `ao-kernel init` hint.

### Step 6 — Docs / Boundary

- [ ] Update `docs/PUBLIC-BETA.md`.
- [ ] Update `docs/SUPPORT-BOUNDARY.md`.
- [ ] Ensure wording says Beta / experimental read-only.
- [ ] Ensure no stable support widening claim is introduced.

### Step 7 — Validation

- [ ] Run focused test suite for RI-1.
- [ ] Run relevant CLI smoke.
- [ ] Run `python3 -m ao_kernel doctor`.
- [ ] Run `python3 scripts/packaging_smoke.py`.
- [ ] Check `git diff --check`.

## Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| Root file overwrite | Corrupts authority docs | No root export in RI-1 |
| Support boundary drift | Overclaims maturity | Mark Beta / experimental only |
| Vector memory pollution | Stale or wrong embeddings | No vector indexing in RI-1 |
| Scanner nondeterminism | Unstable artifacts and tests | Sorted paths and stable JSON output |
| Workspace confusion | Writes outside intended `.ao/context/` | Use `project_root/.ao/context/` only |
| Docs conflict with GP-4 work | Merge conflict | Keep doc changes minimal and boundary-specific |

## Follow-Up Slices

These are explicitly out of RI-1:

1. `RI-2` — Python AST import graph and symbol index.
2. `RI-3` — deterministic agent context pack generation.
3. `RI-4` — repo chunking and vector indexing.
4. `RI-5` — explicit root export with confirm-write.

## Tracking Log

| Date | Status | Notes |
|---|---|---|
| 2026-04-24 | Draft | Tracking document created before implementation. |
| 2026-04-24 | Baseline note | Worktree branch must be refreshed on latest `origin/main` before code implementation. |
| 2026-04-24 | Workflow rule | Dedicated worktree is mandatory; merged PRs enter `origin/main`; uncommitted changes must be preserved before refresh/rebase/switch/cleanup. |
| 2026-04-24 | Claude MCP review | Conditional pass. Step 0 refresh is a hard gate; schema loading, atomic writes, CLI output behavior, facade exports, and coverage gate were tightened. |
| 2026-04-24 | Claude MCP ping-pong | Accepted valid refinements, rejected the package-version misread and graceful missing-`.ao` skip, and fixed artifact ownership: CLI owns `.ao` checks/context-dir creation; `artifacts.py` receives explicit paths only. |
| 2026-04-24 | Step 0 complete | Plan committed, branch rebased onto `origin/main` at `71b456b`, package version verified as `4.0.0`, support boundary exists, CLI/schema patterns inspected, transient lock preserved outside commit scope. |
