# RI-6.3 - Repo Intelligence Workflow Opt-In Validation

**Status:** closeout candidate
**Date:** 2026-04-27
**Authority:** `origin/main` at `3417670`
**Issue:** [#505](https://github.com/Halildeu/ao-kernel/issues/505)
**Branch:** `codex/ri6-3-workflow-opt-in`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-ri6-3-workflow-opt-in`
**Prior handoff PR:** [#504](https://github.com/Halildeu/ao-kernel/pull/504)
**Support impact:** none
**Production claim impact:** none
**Runtime impact:** no adapter execution, no workflow auto-feed

## 1. Purpose

Implement the next narrow repo-intelligence roadmap slice after RI-6.2:
validate explicit workflow opt-in context before any workflow can treat a
repo-intelligence Markdown handoff as visible input.

This slice adds a read-only validation helper. It does not wire
repo-intelligence into workflow execution, does not add hidden prompt injection,
does not expose an MCP tool, does not feed `context_compiler`, does not perform
root export, and does not widen support.

Expected guard state remains:

```text
support_widening=false
production_platform_claim=false
live_adapter_execution_allowed=false
GPP-2=blocked
```

## 2. Behavior Added

New helper:

```python
validate_repo_intelligence_workflow_opt_in(config, *, project_root)
```

The helper accepts only an explicitly enabled config with:

| Field | Required value |
|---|---|
| `enabled` | `true` |
| `source` | `explicit_handoff_file` |
| `handoff_path` | operator-provided Markdown file under `project_root` |
| `require_fresh` | `true` |
| `expected_namespace` | `repo_chunk::<project>::<embedding_space>::` |
| `support_tier` | `beta_explicit_handoff` |

Absent or disabled config returns a no-op result:

```text
status=disabled
decision=repo_intelligence_context_not_enabled
```

A valid handoff returns:

```text
status=accepted
decision=accepted_repo_intelligence_workflow_opt_in
```

The accepted result records:

1. the handoff file path;
2. deterministic Markdown SHA-256;
3. vector namespace prefix;
4. source artifact SHA-256 values;
5. freshness state and stale candidate count;
6. retrieved source paths and content hashes;
7. explicit safety flags showing no hidden injection, no root export, no MCP
   exposure, no `context_compiler` auto-feed, no vector writes, and no artifact
   writes.

## 3. Fail-Closed Checks

The helper returns:

```text
status=blocked
decision=blocked_repo_intelligence_workflow_opt_in
```

for unsafe or incomplete input, including:

| Finding | Meaning |
|---|---|
| `handoff_path_escape` | handoff path is outside `project_root` |
| `handoff_file_missing` | configured handoff file is absent |
| `handoff_sha256_mismatch` | configured expected digest does not match the file |
| `namespace_mismatch` | handoff namespace does not match explicit config |
| `freshness_not_current_only` | handoff provenance does not report `current_only` |
| `source_artifact_freshness_not_current_only` | source artifact freshness is not current-only |
| `stale_candidates_not_zero` | stale candidates were present |
| `hidden_injection_not_disabled` | handoff boundary was weakened |
| `source_path_escape` | retrieved chunk path escapes the project |
| `chunk_content_status_not_current` | returned chunk is not current |
| `chunk_content_sha256_invalid` | returned chunk lacks a valid content hash |

This is validation-only behavior. It does not consume the handoff in workflow
runtime and does not silently ignore an unsafe enabled config.

## 4. Files Changed

| File | Change |
|---|---|
| `ao_kernel/_internal/repo_intelligence/workflow_opt_in.py` | Adds the explicit opt-in validation helper. |
| `ao_kernel/repo_intelligence/__init__.py` | Exposes the helper through the public repo-intelligence facade. |
| `tests/test_repo_intelligence_workflow_opt_in_contract.py` | Adds accepted, disabled, stale, namespace, digest, path escape, and hidden-injection tests. |
| `.claude/plans/RI-6.3-REPO-INTELLIGENCE-WORKFLOW-OPT-IN.md` | Records this closeout candidate. |

## 5. Validation

Startup and program checks:

```bash
git status --short --branch
git rev-list --left-right --count HEAD...origin/main
bash .claude/scripts/ops.sh preflight
python3 scripts/gpp_next.py
```

Focused tests:

```bash
pytest -q tests/test_repo_intelligence_workflow_opt_in_contract.py
```

Result:

```text
9 passed
```

Related repo-intelligence/context tests:

```bash
pytest -q tests/test_repo_intelligence_workflow_opt_in_contract.py tests/test_repo_intelligence_context_pack_builder.py tests/test_cli_repo_query.py tests/test_context_compiler.py
```

Result:

```text
44 passed
```

Static and guard checks:

```bash
python3 -m ruff check ao_kernel/_internal/repo_intelligence/workflow_opt_in.py ao_kernel/repo_intelligence/__init__.py tests/test_repo_intelligence_workflow_opt_in_contract.py
git diff --check
python3 scripts/gpp_next.py
```

Result:

```text
ruff: All checks passed
git diff --check: clean
GPP-2: blocked, no support widening, no production platform claim
```

## 6. Exit Decision

Decision:

```text
repo_intelligence_workflow_opt_in_validation_ready_no_support_widening
```

Closeout conditions:

| Condition | Status |
|---|---|
| Disabled config is a no-op | satisfied |
| Valid explicit handoff config is accepted and records digest/metadata | satisfied |
| Stale, namespace-mismatched, digest-mismatched, path-escaping, or hidden-injection handoffs fail closed | satisfied |
| Workflow runtime auto-feed | not performed |
| `context_compiler` auto-feed | not performed |
| MCP exposure | not performed |
| Root export | not performed |
| Support widening | not performed |
| Production platform claim | not performed |
| Live adapter execution | not performed |
| GPP-2 blocked state | preserved |

