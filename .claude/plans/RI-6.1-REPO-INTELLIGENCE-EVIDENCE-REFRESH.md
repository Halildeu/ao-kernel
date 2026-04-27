# RI-6.1 - Repo Intelligence Evidence Refresh

**Status:** closeout candidate
**Date:** 2026-04-27
**Authority:** `origin/main` at `2c2b765`
**Issue:** [#501](https://github.com/Halildeu/ao-kernel/issues/501)
**Branch:** `codex/ri6-1-evidence-refresh`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-ri6-1-evidence-refresh`
**Prior roadmap PR:** [#500](https://github.com/Halildeu/ao-kernel/pull/500)
**Support impact:** none
**Production claim impact:** none
**Runtime impact:** none

## 1. Purpose

Refresh evidence for the current repo-intelligence Beta surfaces before any
workflow integration or handoff-hardening implementation starts.

This slice records command behavior only. It does not change runtime code,
does not add a repo-intelligence MCP tool, does not feed `context_compiler`,
does not perform root auto-export, does not run a live adapter, and does not
widen support.

Expected guard state remains:

```text
support_widening=false
production_platform_claim=false
live_adapter_execution_allowed=false
GPP-2=blocked
```

## 2. Commands Run

Startup and program checks:

```bash
git status --short --branch
git rev-list --left-right --count HEAD...origin/main
bash .claude/scripts/ops.sh preflight
python3 scripts/gpp_next.py
```

Repo-intelligence refresh commands:

```bash
python3 -m ao_kernel repo scan --project-root . --output json
python3 -m ao_kernel repo index --project-root . --workspace-root .ao --dry-run --output json
python3 -m ao_kernel repo export-plan --project-root . --workspace-root .ao --targets codex,agents --output json
python3 -m ao_kernel repo query --project-root . --workspace-root .ao --query "repo intelligence roadmap" --output json
```

Doctor:

```bash
python3 -m ao_kernel doctor
```

Isolated export smoke:

```bash
mktemp -d
PYTHONPATH="$PWD" python3 -m ao_kernel repo scan --project-root "$tmp_project" --output json
PYTHONPATH="$PWD" python3 -m ao_kernel repo export-plan --project-root "$tmp_project" --workspace-root .ao --targets codex,agents --output json
PYTHONPATH="$PWD" python3 -m ao_kernel repo export --project-root "$tmp_project" --workspace-root .ao --targets codex --confirm-root-export CONFIRM_RI5B_ROOT_EXPORT_V1 --output json
```

The isolated project had a temporary `.ao/policies/policy_coordination_claims.v1.json`
with `enabled=true` because confirmed root export requires path-scoped
coordination. The primary checkout and its `.ao/` directory were not export
targets.

## 3. Results

### 3.1 Repo Scan

Command:

```bash
python3 -m ao_kernel repo scan --project-root . --output json
```

Result: `status=ok`.

Summary:

| Field | Value |
|---|---:|
| included_files | 1141 |
| included_directories | 90 |
| ignored_paths | 10 |
| diagnostics | 0 |
| python_modules | 443 |
| python_packages | 48 |
| python_entrypoints | 20 |

Language counts:

| Language | Count |
|---|---:|
| python | 491 |
| json | 417 |
| markdown | 196 |
| yaml | 3 |
| shell | 5 |
| toml | 1 |
| unknown | 28 |

Artifacts generated under `.ao/context/` during the command:

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `repo_map.json` | 254646 | `27315d3c7ca91654d609224a9569003680335f962775f9fd80cdbcd534eb7b5a` |
| `import_graph.json` | 1641566 | `483f0cde7497d9248629b9ff222e35cf63a48fd8132b4a9058cba6ba59994311` |
| `symbol_index.json` | 2536521 | `2827b1fda1eb811eaea3c8daf07c4241f787ec75a4a009a89ed27fb40fc6716b` |
| `repo_chunks.json` | 2635336 | `09e84df1c6f8998eae9451db87197bb05c37ed273e663a9b711d64b3db9f398b` |
| `agent_pack.md` | 96075 | `d897aba66f5f36e385347b8d8f9dbe3435e63d44ccf4021d2ef8808bd97b604a` |
| `repo_index_manifest.json` | 1545 | `c379275652cb131d75a74d71057186cfe93e7c72d1dc4a4c083f428008182837` |

These generated artifacts were removed before commit and are not part of this
PR.

### 3.2 Repo Index Dry Run

Command:

```bash
python3 -m ao_kernel repo index --project-root . --workspace-root .ao --dry-run --output json
```

Result: `status=ok`, `dry_run=true`.

Summary:

| Field | Value |
|---|---:|
| chunks | 5084 |
| planned_upserts | 5084 |
| planned_deletes | 0 |
| previous_indexed_keys | 0 |
| embedding_calls | 0 |
| vector_writes | 0 |

Embedding space:

| Field | Value |
|---|---|
| provider | `openai` |
| model | `text-embedding-3-small` |
| dimension | `1536` |
| chunker_version | `repo-chunker.v1` |
| embedding_space_id | `73b4cca3b97cfaa558022368898c125c9432566dc289c881b615b793e31bf880` |

Artifact generated during the command:

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `repo_vector_write_plan.json` | 7303378 | `792895fdb5ed98f93c9489cf60dfd9eb5583e544af564f7cd92ff93083d24cb6` |

No embedding call, network vector write, MCP tool, root write, or support
widening occurred.

### 3.3 Repo Export Plan

Command:

```bash
python3 -m ao_kernel repo export-plan --project-root . --workspace-root .ao --targets codex,agents --output json
```

Result: `status=ok` at command level, with one expected blocked target.

Summary:

| Field | Value |
|---|---:|
| target_count | 2 |
| create | 1 |
| blocked | 1 |
| unchanged | 0 |
| update | 0 |
| missing_required_source_artifacts | 0 |

Targets:

| Target | Root path | Action | Reason |
|---|---|---|---|
| `codex` | `CODEX_CONTEXT.md` | `create` | root file absent |
| `agents` | `AGENTS.md` | `blocked` | existing file has different content |

Diagnostic:

```text
root_file_conflict: AGENTS.md already exists with different content
```

This is expected fail-closed behavior. No root file was created by
`repo export-plan`.

### 3.4 Repo Query Without Vector Index Manifest

Command:

```bash
python3 -m ao_kernel repo query --project-root . --workspace-root .ao --query "repo intelligence roadmap" --output json
```

Result: exited non-zero as expected.

Observed stderr:

```text
repo vector index manifest not found: /Users/halilkocoglu/Documents/ao-kernel-ri6-1-evidence-refresh/.ao/context/repo_vector_index_manifest.json. Run 'ao-kernel repo index --write-vectors' first.
```

This is the expected fail-closed result when no vector index manifest exists.
This slice did not run `repo index --write-vectors`.

### 3.5 Isolated Repo Export Smoke

First control observation:

```text
repo export failed: path ownership unavailable: ClaimCoordinationDisabledError
```

This occurred in an isolated temporary workspace without enabled coordination
policy and is expected fail-closed behavior.

Happy-path isolated smoke then used a temporary project under `mktemp -d` with
an explicit `.ao/policies/policy_coordination_claims.v1.json` override setting
`enabled=true`.

Command result: `status=ok` equivalent JSON payload with
`artifact_kind=repo_root_export_result`.

Summary:

| Field | Value |
|---|---:|
| target_count | 1 |
| written_count | 1 |
| unchanged_count | 0 |
| denied_count | 0 |
| skipped_count | 0 |
| support_widening | false |

Target:

| Target | Root path | Result | Ownership |
|---|---|---|---|
| `codex` | `CODEX_CONTEXT.md` | `written` | claim acquired and released |

The temporary project was deleted after the command. The primary checkout and
the RI-6.1 worktree root were not export targets.

### 3.6 Doctor

Command:

```bash
python3 -m ao_kernel doctor
```

Result:

```text
8 OK, 1 WARN, 0 FAIL
```

The warning is the existing bundled extension truth inventory warning:

```text
runtime_backed=2 contract_only=1 quarantined=16
```

This is not a repo-intelligence evidence-refresh blocker.

## 4. GPP Status

Command:

```bash
python3 scripts/gpp_next.py
```

Result remains:

```text
Current WP: GPP-2 - Protected Live-Adapter Gate Runtime Binding
Current status: blocked
Support widening allowed: false
Production platform claim allowed: false
Live adapter execution allowed: false
```

## 5. Files And Artifact Hygiene

Generated `.ao/context/` artifacts were produced only as command evidence and
then removed from the RI-6.1 worktree before commit.

This PR intentionally commits only this written evidence record.

No root authority file was created in the primary checkout or RI-6.1 worktree.
The only root export write happened inside a deleted temporary project.

## 6. Decision

RI-6.1 closes as:

```text
repo_intelligence_evidence_refreshed_no_support_widening
```

The evidence refresh supports starting a later `RI-6.2` explicit handoff
hardening slice, subject to its own issue, branch, PR, validation record, and
closeout decision.

This decision does not authorize:

1. repo-intelligence MCP tool implementation;
2. `context_compiler` auto-feed;
3. root auto-export;
4. live adapter execution;
5. remote PR live-write support;
6. support widening;
7. production platform claim.
