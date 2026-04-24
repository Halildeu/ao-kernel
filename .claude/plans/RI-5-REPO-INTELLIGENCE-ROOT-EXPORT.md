# RI-5 - Repo Intelligence Explicit Root/Context Export Design Gate

**Status:** RI-5a tracking plan
**Date:** 2026-04-24
**Authority:** `origin/main` at `d7f7b37`
**Planning PR:** [#423](https://github.com/Halildeu/ao-kernel/pull/423)
**Closeout PR:** [#426](https://github.com/Halildeu/ao-kernel/pull/426)
**Planning branch:** cleaned after merge
**Planning worktree:** cleaned after merge
**Tracking branch:** `codex/ri5a-export-plan-tracker`
**Tracking worktree:** `/Users/halilkocoglu/Documents/ao-kernel-ri5a-export-plan-tracker`
**Base:** `origin/main` at `d7f7b37`
**Next slice:** RI-5a export-plan preview implementation
**Implementation:** Not started; this document is the implementation tracker
**Rule:** Never work directly on `main`.

## Operational Rules

These rules remain mandatory:

1. Work must happen in a dedicated worktree. Direct work on `main` is
   forbidden.
2. Completed work is integrated through PR review/CI and merge.
3. After a PR is merged, the authoritative source becomes `origin/main`.
4. Active feature worktrees do not update automatically after another PR
   merges.
5. Uncommitted changes must never be lost during refresh, rebase, branch
   switch, pull, or worktree cleanup.
6. Root authority files must not be overwritten by default.
7. Any root-file write must require explicit command intent and an exact
   confirmation token.

## Current Baseline

Repo intelligence has reached a useful local retrieval boundary:

1. RI-1: deterministic repo scan artifacts.
2. RI-2: Python AST import graph and symbol index artifacts.
3. RI-3: deterministic `.ao/context/agent_pack.md` generation.
4. RI-4a: deterministic chunk manifest.
5. RI-4b: vector write-plan dry-run.
6. RI-4c: explicit vector write path.
7. RI-4d: read-only repo vector retrieval.
8. RI-4e: stdout-only `repo query --output markdown`.

This is enough for manual Claude/Codex use without touching root authority
files. RI-5 must therefore be a separate, explicitly confirmed export tranche,
not a hidden side effect of scan, index, query, or context compilation.

## Decision

RI-5 should be split into two PRs:

1. `RI-5a` - export planning and diff preview only. This PR may produce a
   deterministic export plan under `.ao/context/`, but it must not write root
   files.
2. `RI-5b` - explicit confirmed root export. This PR may write selected root
   files only when the operator passes an exact confirmation token and a target
   allowlist.

Do not start `RI-5b` until `RI-5a` has merged and its output schema, support
boundary, and tests are stable.

## RI-5a - Export Plan Preview

RI-5a should add a deterministic preview command:

```text
python3 -m ao_kernel repo export-plan \
  --project-root . \
  --workspace-root .ao \
  --targets codex,agents \
  --output json
```

The command may read existing repo-intelligence artifacts:

```text
.ao/context/repo_map.json
.ao/context/import_graph.json
.ao/context/symbol_index.json
.ao/context/repo_chunks.json
.ao/context/agent_pack.md
.ao/context/repo_vector_index_manifest.json
```

It may write only:

```text
.ao/context/repo_export_plan.json
```

The plan should include:

1. selected targets;
2. proposed root file paths;
3. source artifact digests;
4. generated content digest per target;
5. existing root file digest if the file exists;
6. action classification: `create`, `update`, `unchanged`, or `blocked`;
7. conflict diagnostics for pre-existing root files;
8. exact RI-5b confirmation token required for a future write.

RI-5a must not create, update, truncate, or delete:

```text
CLAUDE.md
AGENTS.md
ARCHITECTURE.md
CODEX_CONTEXT.md
```

## RI-5a Implementation Tracker

This section is the single tracking surface for RI-5a. Update it in the RI-5a
implementation PR as work progresses. Do not start RI-5b until every RI-5a
acceptance item is checked, CI is green, and the PR is merged into
`origin/main`.

### Scope Lock

| Item | Decision | Status |
|---|---|---|
| Root file writes | Forbidden in RI-5a | Locked |
| `.ao/context/repo_export_plan.json` | Only new generated artifact | Locked |
| `CODEX_CONTEXT.md` | Preview target only | Locked |
| `AGENTS.md` | Preview target only | Locked |
| `CLAUDE.md` | Deferred, not a RI-5a target | Locked |
| `ARCHITECTURE.md` | Deferred, not a RI-5a target | Locked |
| LLM calls | Forbidden | Locked |
| Network access | Forbidden | Locked |
| Vector backend query/write | Forbidden | Locked |
| MCP exposure | Forbidden | Locked |
| `context_compiler` auto-injection | Forbidden | Locked |

### Work Breakdown

| Step | Work | Status | Evidence |
|---|---|---|---|
| 0 | Create dedicated RI-5a worktree from current `origin/main` | [ ] Pending | `git worktree list` |
| 1 | Pin this document to the RI-5a branch/worktree/base | [ ] Pending | Header and tracking log updated |
| 2 | Add `repo-export-plan.schema.v1.json` | [ ] Pending | Schema file and schema validation test |
| 3 | Add deterministic export-plan builder | [ ] Pending | `export_plan.py` unit tests |
| 4 | Add artifact write path for `.ao/context/repo_export_plan.json` only | [ ] Pending | CLI root-write regression test |
| 5 | Add `repo export-plan` CLI | [ ] Pending | CLI help and behavior tests |
| 6 | Export narrow public facade | [ ] Pending | `ao_kernel/repo_intelligence/__init__.py` test/import |
| 7 | Update docs and changelog | [ ] Pending | Support boundary and public beta rows |
| 8 | Run local validation gates | [ ] Pending | Command outputs recorded in tracking log |
| 9 | Open PR and wait for CI | [ ] Pending | PR URL and green CI |
| 10 | Merge, fast-forward local `main`, cleanup branch/worktree | [ ] Pending | `rev-list 0 0`, branch cleanup |

### Artifact Contract

The RI-5a artifact must be deterministic for identical inputs except the
standard `generator.generated_at` timestamp, matching the existing
repo-intelligence artifact pattern. Tests should normalize that timestamp
before comparing repeated runs.

```text
.ao/context/repo_export_plan.json
```

Minimum top-level fields:

```json
{
  "schema_version": "1",
  "artifact_kind": "repo_export_plan",
  "generator": {
    "name": "ao-kernel-repo-export-planner",
    "version": "repo-export-plan.v1",
    "generated_at": "ISO-8601 timestamp"
  },
  "project_root": ".",
  "workspace_root": ".ao",
  "source_artifacts": {},
  "targets": [],
  "confirmation": {},
  "diagnostics": []
}
```

Required source artifact records:

| Field | Meaning |
|---|---|
| `path` | Repo-relative POSIX path |
| `sha256` | Current file digest |
| `required` | Whether RI-5a needs this artifact for the selected targets |
| `present` | Whether the artifact exists |

Required target records:

| Field | Meaning |
|---|---|
| `target` | Stable target id, initially `codex` or `agents` |
| `root_path` | Proposed root file path |
| `action` | `create`, `update`, `unchanged`, or `blocked` |
| `existing_file` | Whether the root file exists now |
| `existing_sha256` | Existing root file digest when present |
| `generated_content_sha256` | Digest of deterministic generated content |
| `generated_byte_count` | Byte count of deterministic generated content |
| `generated_line_count` | Line count of deterministic generated content |
| `content_source` | Source artifact or template version |
| `diagnostics` | Structured reasons for warnings or blocked actions |

### Action Matrix

| Condition | Action | Write allowed in RI-5a |
|---|---|---:|
| Target root file is absent | `create` | No |
| Target root file exists and content digest matches | `unchanged` | No |
| Target root file exists and digest differs | `blocked` | No |
| Target root path is a symlink | `blocked` | No |
| Target root path escapes project root | `blocked` | No |
| Required source artifact is missing | `blocked` | No |
| Target is unsupported | `blocked` or CLI error | No |

`update` may remain in the schema for forward compatibility, but the first
RI-5b write implementation should still default to create-only.

### CLI Contract

Primary command:

```text
python3 -m ao_kernel repo export-plan \
  --project-root . \
  --workspace-root .ao \
  --targets codex,agents \
  --output json
```

Expected behavior:

1. Create `.ao/context` if needed through the existing safe workspace path.
2. Write only `.ao/context/repo_export_plan.json`.
3. Print the same JSON plan to stdout when `--output json` is selected.
4. Use repo-relative POSIX paths.
5. Fail closed on invalid project/workspace roots.
6. Fail closed or mark targets blocked on missing required source artifacts.
7. Never create, update, truncate, or delete root authority files.

### Test Matrix

| Test | Expected proof |
|---|---|
| Missing required source artifact | Fails closed or blocked diagnostics |
| Present source artifacts | Stable source digests in plan |
| Absent `CODEX_CONTEXT.md` | Target action is `create` |
| Existing matching root file | Target action is `unchanged` |
| Existing different root file | Target action is `blocked` |
| Root symlink target | Target action is `blocked` |
| Path escape target | Target action is `blocked` |
| Target order changes | Output order remains deterministic |
| CLI run | Only `.ao/context/repo_export_plan.json` is written |
| CLI root snapshot | `CLAUDE.md`, `AGENTS.md`, `ARCHITECTURE.md`, `CODEX_CONTEXT.md` unchanged |
| Schema validation | Generated plan validates against bundled schema |

### Validation Checklist

Run these before opening the RI-5a implementation PR:

```text
ruff check ao_kernel/ tests/
mypy ao_kernel/
pytest tests/test_repo_intelligence_export_plan.py tests/test_cli_repo_export_plan.py -q
python3 -m ao_kernel repo export-plan --help
python3 -m ao_kernel doctor
python3 scripts/packaging_smoke.py
git diff --check
git ls-files -o --exclude-standard
```

Run the full coverage gate before merge unless the implementation PR is
docs-only:

```text
pytest tests/ --ignore=tests/benchmarks --cov=ao_kernel --cov-branch --cov-report=term-missing
```

### PR Exit Criteria

RI-5a is complete only when:

1. Local validation passes.
2. PR CI passes.
3. `repo_export_plan.json` is schema-backed and deterministic.
4. Tests prove no root authority file is written or modified.
5. Docs still mark this as Beta / experimental preview only.
6. PR is merged to `origin/main`.
7. Local `main` is fast-forwarded to `origin/main`.
8. RI-5a worktree and branch are cleaned only after content parity with
   `main` is verified.

## RI-5b - Explicit Confirmed Root Export

RI-5b may add a write command only after RI-5a merges:

```text
python3 -m ao_kernel repo export \
  --project-root . \
  --workspace-root .ao \
  --targets codex,agents \
  --confirm-root-export I_UNDERSTAND_ROOT_AUTHORITY_FILE_WRITES
```

The write path must be fail-closed:

1. no confirmation token, no root write;
2. no export plan, no root write;
3. stale source artifact digest, no root write;
4. unsupported target, no root write;
5. pre-existing root file conflict, no overwrite unless an explicit
   per-target overwrite flag is added in the same reviewed PR;
6. symlink target, no write;
7. path escaping project root, no write.

The first RI-5b implementation should prefer create-only writes. Overwrite
support can be a later tranche if needed.

## Non-Negotiable Boundaries

1. `repo scan`, `repo index`, and `repo query` must remain free of root export
   side effects.
2. Root exports are not generated by default.
3. Root exports are not generated by `context_compiler`.
4. No LLM call is used to produce root export content.
5. No network access is required.
6. Existing manually authored root files are treated as authority and must not
   be overwritten silently.
7. Export content must be deterministic for the same input artifacts.
8. The support tier remains Beta / experimental until a later promotion
   decision.

## Initial Target Set

The first target set should be small:

| Target | Root file | Default in RI-5a | Default in RI-5b |
|---|---|---:|---:|
| `codex` | `CODEX_CONTEXT.md` | preview | create-only |
| `agents` | `AGENTS.md` | preview | create-only |

`CLAUDE.md` and `ARCHITECTURE.md` should stay deferred. They are higher
authority and more likely to collide with hand-maintained project docs.

## Proposed Files

RI-5a planned files:

```text
ao_kernel/_internal/repo_intelligence/export_plan.py
ao_kernel/defaults/schemas/repo-export-plan.schema.v1.json
ao_kernel/cli.py
ao_kernel/repo_intelligence/__init__.py
tests/test_repo_intelligence_export_plan.py
tests/test_cli_repo_export_plan.py
docs/PUBLIC-BETA.md
docs/SUPPORT-BOUNDARY.md
CHANGELOG.md
```

RI-5b planned files:

```text
ao_kernel/_internal/repo_intelligence/root_exporter.py
ao_kernel/cli.py
tests/test_repo_intelligence_root_exporter.py
tests/test_cli_repo_export.py
docs/PUBLIC-BETA.md
docs/SUPPORT-BOUNDARY.md
CHANGELOG.md
```

## Acceptance - RI-5a

- [ ] Runs in a dedicated worktree.
- [ ] Produces deterministic `.ao/context/repo_export_plan.json`.
- [ ] Validates the export plan against a bundled JSON schema.
- [ ] Uses repo-relative POSIX paths.
- [ ] Records source artifact digests and generated content digests.
- [ ] Detects existing root files without modifying them.
- [ ] Does not write root files.
- [ ] Does not call an LLM.
- [ ] Does not use network access.
- [ ] Does not write vectors or query vector backends.
- [ ] Has unit tests and CLI behavior tests.
- [ ] Updates support-boundary docs as Beta / experimental preview only.

## Acceptance - RI-5b

- [ ] Starts only after RI-5a is merged.
- [ ] Requires exact confirmation token.
- [ ] Requires explicit target allowlist.
- [ ] Writes only supported root files.
- [ ] Refuses symlink targets and path escapes.
- [ ] Refuses stale or missing export plans.
- [ ] Defaults to create-only root writes.
- [ ] Does not call an LLM.
- [ ] Does not use network access.
- [ ] Has unit tests and CLI behavior tests for deny paths and happy path.

## Rejected Approaches

| Approach | Decision | Reason |
|---|---|---|
| Export root files during `repo scan` | Rejected | Scan must stay safe, local, and deterministic. |
| Export root files during `repo query` | Rejected | Query is read-only retrieval and stdout output only. |
| Auto-inject repo intelligence into `context_compiler` | Rejected for RI-5 | This is a separate runtime context policy problem. |
| Generate or rewrite `CLAUDE.md` first | Rejected | `CLAUDE.md` is high-authority and likely hand-maintained. |
| Overwrite existing root files by default | Rejected | Existing root docs are authority and must be protected. |
| Use LLM summarization for root exports | Rejected | Non-deterministic and harder to validate. |

## Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| Root authority corruption | Breaks agent behavior or project docs | RI-5a preview first, RI-5b exact confirmation, create-only default |
| Stale export content | Agents consume outdated repo facts | Source artifact digests and stale-plan denial |
| False sense of support maturity | Users expect production root context management | Keep Beta / experimental docs boundary |
| Symlink/path escape write | Writes outside project root | Refuse symlinks and non-root-contained paths |
| Generated doc conflict | Clobbers human-maintained docs | Conflict diagnostics and blocked default action |

## Tracking Log

| Date | Status | Notes |
|---|---|---|
| 2026-04-24 | Design gate opened | RI-5 is explicitly separated from RI-4 and split into preview-only RI-5a plus confirmed create-only RI-5b. |
| 2026-04-24 | Design gate merged | PR [#423](https://github.com/Halildeu/ao-kernel/pull/423) merged to `main` at `33c4d22`; CI passed including lint, typecheck, coverage, Python 3.11/3.12/3.13 tests, benchmark-fast, packaging-smoke, extras-install, and scorecard. Post-merge branch/worktree cleanup completed and local `main` is synchronized with `origin/main`. |
| 2026-04-24 | RI-5a tracker opened | Dedicated tracking branch `codex/ri5a-export-plan-tracker` and worktree `/Users/halilkocoglu/Documents/ao-kernel-ri5a-export-plan-tracker` opened from `origin/main` at `d7f7b37`. This tracker adds scope lock, work breakdown, artifact contract, CLI contract, test matrix, validation checklist, and PR exit criteria before implementation starts. |
