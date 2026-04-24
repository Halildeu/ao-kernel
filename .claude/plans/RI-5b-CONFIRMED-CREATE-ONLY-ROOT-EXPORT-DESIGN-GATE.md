# RI-5b - Confirmed Create-Only Root Export Design Gate

**Status:** Design gate merged / RI-5b implementation merged
**Date:** 2026-04-24
**Authority:** `origin/main` at `6234476`
**Issue:** [#459](https://github.com/Halildeu/ao-kernel/issues/459) (closed)
**Design PR:** [#460](https://github.com/Halildeu/ao-kernel/pull/460)
**Implementation issue:** [#464](https://github.com/Halildeu/ao-kernel/issues/464) (closed)
**Implementation PR:** [#465](https://github.com/Halildeu/ao-kernel/pull/465)
**Closeout issue:** [#466](https://github.com/Halildeu/ao-kernel/issues/466)
**Design branch:** cleaned after merge
**Design worktree:** cleaned after merge
**Implementation branch:** cleaned after merge
**Implementation worktree:** cleaned after merge
**Base:** `origin/main` at `6234476`
**Previous slice:** RI-5a export-plan preview merged by PR
[#457](https://github.com/Halildeu/ao-kernel/pull/457) and closed out by PR
[#458](https://github.com/Halildeu/ao-kernel/pull/458)
**Next allowed slice:** none active. Overwrite/update, higher-authority target
promotion, MCP/root export tooling, or context compiler wiring requires a new
design gate.
**Support impact:** Beta/operator-managed root export only; no stable support
widening.

## Purpose

RI-5a made root/context export intent explicit by writing only
`.ao/context/repo_export_plan.json`. RI-5b may add an explicit root export write
command, but only after this design gate is merged and the implementation
slice follows the contract below.

This gate exists because root authority files influence future agent behavior.
They must not be created, modified, truncated, or overwritten as a side effect
of scan, index, query, context compilation, MCP exposure, or workflow execution.

## Scope

This slice is documentation and program-status only.

It may:

1. define the RI-5b write contract;
2. pin exact confirmation and create-only defaults;
3. define deny-path tests and rollback evidence requirements;
4. update RI-5 and post-beta status surfaces.

It must not:

1. add `python3 -m ao_kernel repo export`;
2. add a root exporter implementation;
3. write root authority files;
4. widen support boundary;
5. add MCP, workflow runtime, or `context_compiler` integration;
6. call LLMs, network services, vector backends, or external adapters.

## Proposed User Command

The future implementation slice may add this command shape:

```text
python3 -m ao_kernel repo export \
  --project-root . \
  --workspace-root .ao \
  --targets codex,agents \
  --confirm-root-export CONFIRM_RI5B_ROOT_EXPORT_V1
```

The exact confirmation token is:

```text
CONFIRM_RI5B_ROOT_EXPORT_V1
```

No alias, fuzzy match, environment variable, interactive prompt, or default
confirmation is allowed in the first implementation slice.

## Authority Model

Root authority files are human/operator authority unless the operator provides
explicit write intent. Existing root files therefore block writes by default.

Initial targets:

| Target | Root file | First implementation default |
|---|---|---|
| `codex` | `CODEX_CONTEXT.md` | create-only |
| `agents` | `AGENTS.md` | create-only |

Deferred targets:

| Root file | Reason |
|---|---|
| `CLAUDE.md` | high-authority, hand-maintained, higher overwrite risk |
| `ARCHITECTURE.md` | project architecture authority, higher semantic-risk |

## Required Input

RI-5b must consume the existing RI-5a artifact:

```text
.ao/context/repo_export_plan.json
```

The exporter must not silently recompute a hidden write plan. If the plan is
missing, stale, malformed, schema-invalid, or inconsistent with current source
artifacts, the command must fail before any root file write.

## Create-Only Write Algorithm

The first implementation should follow this order:

1. resolve and validate `project_root`;
2. resolve and validate `workspace_root`;
3. parse `--targets` as an explicit allowlist;
4. require exact `--confirm-root-export CONFIRM_RI5B_ROOT_EXPORT_V1`;
5. load `.ao/context/repo_export_plan.json`;
6. validate the artifact against `repo-export-plan.schema.v1.json`;
7. verify recorded source artifact digests against current files;
8. verify requested targets exist in the plan and are supported;
9. verify each target root path is project-root-contained and not a symlink;
10. verify path-scoped ownership is available for each root target;
11. take a before snapshot for each root target path;
12. write only absent target files whose plan action is `create`;
13. verify after snapshots and content digests;
14. emit machine-readable evidence with written, skipped, and denied targets.

No write may happen before steps 1-11 pass for the target.

## Deny Matrix

| Condition | Result | Root write |
|---|---|---:|
| Missing confirmation token | fail closed | No |
| Wrong confirmation token | fail closed | No |
| Missing export plan | fail closed | No |
| Schema-invalid export plan | fail closed | No |
| Stale source artifact digest | fail closed | No |
| Unsupported target | fail closed | No |
| Target absent from plan | fail closed | No |
| Target action is `blocked` | fail closed | No |
| Target action is `update` | fail closed in first slice | No |
| Existing root file differs | fail closed | No |
| Existing root file matches generated content | no-op / unchanged | No |
| Target root path is symlink | fail closed | No |
| Target root path escapes project root | fail closed | No |
| Path ownership unavailable | fail closed | No |
| Snapshot/verification failure | fail closed | No |
| Target action is `create` and file is absent | write allowed | Yes |

## Path-Scoped Ownership Requirement

Before any future root write, RI-5b must check ownership for target root paths.
The root export implementation must not bypass path-scoped write ownership.

Initial ownership scope:

```text
CODEX_CONTEXT.md
AGENTS.md
```

If the ownership layer cannot confirm the current actor may write those paths,
the command must fail closed before writing. The evidence payload must record
the ownership status per target.

## Snapshot And Rollback Evidence

The implementation PR must include tests proving root-file safety:

1. before/after root snapshot is captured;
2. create-only happy path writes only absent target files;
3. existing files are not overwritten;
4. failed verification leaves root paths unchanged;
5. rollback or cleanup restores sandbox test roots after failure;
6. evidence records written, skipped, denied, and unchanged targets.

Live support widening must not be considered until this evidence exists in CI.

## Evidence Shape

The future implementation should emit a machine-readable result with at least:

```json
{
  "schema_version": "1",
  "artifact_kind": "repo_root_export_result",
  "project_root": ".",
  "workspace_root": ".ao",
  "confirmation": {
    "required_token": "CONFIRM_RI5B_ROOT_EXPORT_V1",
    "provided": true
  },
  "targets": [],
  "summary": {
    "written_count": 0,
    "unchanged_count": 0,
    "denied_count": 0
  },
  "support_widening": false
}
```

The exact schema can be added in the implementation slice, but the support
claim must remain false unless a later promotion decision explicitly changes
it.

## Test Requirements For Implementation

The implementation PR must add behavior tests covering:

1. missing confirmation token;
2. wrong confirmation token;
3. missing export plan;
4. schema-invalid export plan;
5. stale source artifact digest;
6. unsupported target;
7. target absent from plan;
8. blocked target action;
9. `update` action denied in create-only mode;
10. existing root file conflict;
11. matching existing root file unchanged no-op;
12. symlink target denial;
13. path escape denial;
14. path ownership denial;
15. create-only happy path;
16. root snapshot unchanged on failure;
17. evidence payload shape.

## Documentation Requirements For Implementation

The implementation PR must update:

```text
docs/PUBLIC-BETA.md
docs/SUPPORT-BOUNDARY.md
CHANGELOG.md
.claude/plans/RI-5-REPO-INTELLIGENCE-ROOT-EXPORT.md
.claude/plans/POST-BETA-CORRECTNESS-EXPANSION-STATUS.md
```

The public docs must keep the surface Beta / operator-managed until write
evidence and rollback evidence are merged and a later support decision grants a
promotion. The shipped stable baseline must not imply automatic root-context
management.

## Acceptance For This Design Gate

- [x] Dedicated branch and worktree are created from current `origin/main`.
- [x] Issue [#459](https://github.com/Halildeu/ao-kernel/issues/459) tracks the
  RI-5b design gate.
- [x] Exact confirmation token is pinned.
- [x] Create-only default is pinned.
- [x] Export-plan-as-input requirement is pinned.
- [x] Deny matrix is pinned.
- [x] Path ownership requirement is pinned.
- [x] Snapshot/rollback evidence requirement is pinned.
- [x] Support boundary remains unchanged.

## Acceptance For Future RI-5b Implementation

- [x] Starts only after this design gate merges.
- [x] Adds runtime code in a separate branch and PR.
- [x] Requires exact confirmation token.
- [x] Requires explicit target allowlist.
- [x] Consumes `.ao/context/repo_export_plan.json`.
- [x] Defaults to create-only root writes.
- [x] Refuses overwrite/update in the first slice.
- [x] Checks path-scoped ownership before any root write.
- [x] Proves root snapshots and rollback/no-corruption behavior.
- [x] Emits machine-readable evidence.
- [x] Keeps `support_widening=false`.

## Tracking Log

| Date | Status | Notes |
|---|---|---|
| 2026-04-24 | Design gate opened | Dedicated branch `codex/ri5b-root-export-design-gate` and worktree `/Users/halilkocoglu/Documents/ao-kernel-ri5b-root-export-design-gate` opened from `origin/main` at `0a6eacb`; issue [#459](https://github.com/Halildeu/ao-kernel/issues/459) created. |
| 2026-04-24 | Design gate merged | PR [#460](https://github.com/Halildeu/ao-kernel/pull/460) merged to `main` at `91c1bc0`; issue [#459](https://github.com/Halildeu/ao-kernel/issues/459) closed; runtime implementation remains gated. |
| 2026-04-24 | Design branch cleanup completed | Local `main` synchronized with `origin/main`; design branch and worktree cleaned. Next allowed slice is RI-5b create-only implementation from current `origin/main`. |
| 2026-04-24 | Implementation started | Issue [#464](https://github.com/Halildeu/ao-kernel/issues/464) and branch `codex/ri5b-create-only-root-export` opened from `origin/main` at `49c4482`; runtime code, CLI, schema, tests, docs, and status updates live in that implementation slice. |
| 2026-04-24 | Implementation local validation passed | Targeted deny/happy-path tests, schema validation, CLI behavior tests, mypy, packaging smoke, fresh-venv installed-wheel `repo export` smoke, doctor, and full coverage gate all passed in the RI-5b implementation worktree. |
| 2026-04-24 | Implementation merged | PR [#465](https://github.com/Halildeu/ao-kernel/pull/465) merged to `main` at `6234476`; issue [#464](https://github.com/Halildeu/ao-kernel/issues/464) closed. |
| 2026-04-24 | Implementation cleanup completed | Local `main` synchronized with `origin/main`; implementation branch/worktree and remote branch cleaned; closeout issue [#466](https://github.com/Halildeu/ao-kernel/issues/466) records status cleanup. |
