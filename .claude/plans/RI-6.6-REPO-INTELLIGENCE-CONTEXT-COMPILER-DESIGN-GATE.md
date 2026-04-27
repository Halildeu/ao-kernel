# RI-6.6 - Repo Intelligence Context Compiler Opt-In Design Gate

**Status:** closeout candidate
**Date:** 2026-04-27
**Authority:** `origin/main` at `65d1613`
**Issue:** [#511](https://github.com/Halildeu/ao-kernel/issues/511)
**Branch:** `codex/ri6-6-context-compiler-gate`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-ri6-6-context-compiler-gate`
**Prior design PR:** [#510](https://github.com/Halildeu/ao-kernel/pull/510)
**Support impact:** none
**Production claim impact:** none
**Runtime impact:** no context compiler auto-feed implementation

## 1. Purpose

Close the RI-6.6 design gate: decide whether repo-intelligence context should
feed `context_compiler` now.

Decision:

```text
no_context_compiler_auto_feed
```

This slice is design and regression coverage only. It does not add a
`context_compiler` repo-intelligence lane, does not auto-load repo query
artifacts, does not expose an MCP tool, does not perform root export, does not
call a live adapter, and does not widen support.

Expected guard state remains:

```text
support_widening=false
production_platform_claim=false
live_adapter_execution_allowed=false
GPP-2=blocked
```

## 2. Current Compiler Boundary

The current `context_compiler` accepts only these context lanes:

1. session decisions;
2. canonical decisions;
3. workspace facts;
4. caller-supplied promoted consultations.

It has no `repo_intelligence_context`, `repo_query_context`, or
`context_compiler_feed` parameter. It also does not scan `.ao/context`, does
not call repo-intelligence query helpers, and does not read handoff files.

This is the correct default while repo intelligence remains Beta explicit
handoff.

## 3. Design Questions

### 3.1 Should repo-intelligence feed `context_compiler` now?

No.

RI-6.2, RI-6.3, and RI-6.4 established the safer supported path:
operator-visible Markdown handoff, explicit workflow opt-in validation, and a
deterministic read-only rehearsal. Feeding `context_compiler` would create a
new hidden prompt path unless policy, validation, provenance, and evidence are
fully specified and tested in a separate implementation slice.

### 3.2 What would be required before a future opt-in feed?

A future implementation would require all of these gates before any compiler
lane can exist:

| Gate | Requirement |
|---|---|
| Workspace policy | explicit `repo_intelligence.context_compiler.enabled=true` |
| Workflow config | exact workflow step requests repo-intelligence context |
| Source mode | only `explicit_handoff_file` or another visible, operator-selected source |
| Freshness | only `current_only` handoffs are accepted |
| Namespace | expected namespace must match configured project identity and embedding space |
| Source hash | source paths, line ranges, and content SHA256 must validate before compile |
| Prompt boundary | compiled output must label repo-intelligence as Beta explicit context |
| Result limits | hard max bytes, snippets, sources, and rendered lines |
| Evidence | compile evidence records policy, digest, source metadata, and denied reason codes |

No such feed is implemented in this slice.

### 3.3 How should disabled config behave?

Disabled or absent config must be a no-op.

Current state is stronger than disabled config: there is no compiler parameter
or loader that can accept repo-intelligence context. Tests now pin that
`repo_intelligence_context`, `repo_query_context`, or `context_compiler_feed`
payloads placed at the session root are ignored by `compile_context`.

### 3.4 How should stale or unknown context fail?

A future implementation must fail closed on:

| Condition | Required outcome |
|---|---|
| Missing explicit enablement | no-op |
| Missing workflow request | no-op |
| Path escape | `blocked` or `failed`, no compiled snippets |
| Stale handoff | `blocked` or `failed`, no compiled snippets |
| Unknown namespace | `blocked` or `failed` |
| Missing source hash | `blocked` or `failed` |
| Content hash mismatch | `blocked` or `failed` |
| Excess payload size | bounded truncation or `blocked` with diagnostic |
| Redaction-required content | omit or redact with diagnostic |
| Hidden injection markers | `blocked` or `failed` |

The existing RI-6.3 validator already handles the explicit handoff validation
side. A compiler feed would need to call that validation explicitly and record
the result before rendering anything.

### 3.5 What evidence would be required?

Future compiler evidence would need:

| Evidence field | Purpose |
|---|---|
| compiler feed policy decision | prove the feed was explicitly allowed |
| workflow step identity | bind context to the requesting workflow step |
| handoff digest | prove exact operator-visible input |
| expected namespace | prove project and embedding-space boundary |
| freshness state | prove current-only result |
| source path and line ranges | preserve reviewable provenance |
| source content hashes | bind rendered snippets to current files |
| rendered byte and item counts | prove bounded prompt contribution |
| denied reason codes | make fail-closed behavior auditable |

This slice emits no compiler-feed evidence because no repo-intelligence compiler
feed exists.

## 4. Current Guard

Regression coverage now pins:

1. `compile_context(...)` has no repo-intelligence feed parameter;
2. `compile_context_sdk(...)` has no repo-intelligence feed parameter;
3. session-root `repo_intelligence_context`, `repo_query_context`, and
   `context_compiler_feed` payloads are not rendered into compiled context.

The current product boundary remains:

| Surface | Status |
|---|---|
| `repo query --output markdown` | beta explicit handoff |
| `validate_repo_intelligence_workflow_opt_in(...)` | beta explicit handoff validation |
| `review_ai_flow + codex-stub` read-only rehearsal | deterministic evidence path |
| repo-intelligence MCP tool | not registered |
| `context_compiler` auto-feed | not registered |
| root export from query/handoff | not registered |

## 5. Files Changed

| File | Change |
|---|---|
| `tests/test_context_compiler.py` | Adds negative guard tests for repo-intelligence context compiler auto-feed surfaces. |
| `.claude/plans/RI-6.6-REPO-INTELLIGENCE-CONTEXT-COMPILER-DESIGN-GATE.md` | Records the design decision and future gate requirements. |

## 6. Validation

Startup and program checks:

```bash
git status --short --branch
git rev-list --left-right --count HEAD...origin/main
bash .claude/scripts/ops.sh preflight
python3 scripts/gpp_next.py
```

Focused context compiler tests:

```bash
pytest -q tests/test_context_compiler.py
```

Related repo-intelligence and workflow opt-in tests:

```bash
pytest -q tests/test_context_compiler.py tests/test_repo_intelligence_workflow_opt_in_contract.py tests/test_repo_intelligence_no_mcp_root_export_guard.py
```

Static and guard checks:

```bash
python3 -m ruff check tests/test_context_compiler.py
git diff --check
python3 scripts/gpp_next.py
```

Observed results:

| Command | Result |
|---|---|
| `pytest -q tests/test_context_compiler.py` | 25 passed |
| `pytest -q tests/test_context_compiler.py tests/test_repo_intelligence_workflow_opt_in_contract.py tests/test_repo_intelligence_no_mcp_root_export_guard.py` | 42 passed |
| `python3 -m ruff check tests/test_context_compiler.py` | passed |
| `git diff --check` | passed |
| `python3 scripts/gpp_next.py` | GPP-2 blocked, support widening false, production platform claim false, live adapter execution false |
| `python3 -m ao_kernel doctor` | 8 OK, 1 WARN, 0 FAIL; existing bundled extension truth warning only |

## 7. Exit Decision

Decision:

```text
repo_intelligence_context_compiler_design_gate_closed_no_auto_feed_no_support_widening
```

Closeout conditions:

| Condition | Status |
|---|---|
| Context compiler feed decision recorded | satisfied |
| Future policy and workflow gates documented | satisfied |
| Freshness, namespace, hash, size, redaction, and hidden injection requirements documented | satisfied |
| Evidence requirements documented | satisfied |
| `context_compiler` repo-intelligence auto-feed | not performed and regression-tested |
| MCP tool implementation | not performed |
| Root export | not performed |
| Support widening | not performed |
| Production platform claim | not performed |
| Live adapter execution | not performed |
| GPP-2 blocked state | preserved |
