# RI-6.5 - Repo Intelligence MCP Read-Only Design Gate

**Status:** closeout candidate
**Date:** 2026-04-27
**Authority:** `origin/main` at `c599014`
**Issue:** [#509](https://github.com/Halildeu/ao-kernel/issues/509)
**Branch:** `codex/ri6-5-mcp-design-gate`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-ri6-5-mcp-design-gate`
**Prior rehearsal PR:** [#508](https://github.com/Halildeu/ao-kernel/pull/508)
**Support impact:** none
**Production claim impact:** none
**Runtime impact:** no MCP tool implementation

## 1. Purpose

Close the RI-6.5 design gate: decide whether repo-intelligence should expose a
read-only MCP tool now.

Decision:

```text
no_mcp_repo_intelligence_tool
```

This slice is design and regression coverage only. It does not add an MCP tool,
does not expose repo-intelligence through `ToolGateway`, does not feed
`context_compiler`, does not perform root export, does not call a live adapter,
and does not widen support.

Expected guard state remains:

```text
support_widening=false
production_platform_claim=false
live_adapter_execution_allowed=false
GPP-2=blocked
```

## 2. Design Questions

### 2.1 Which read-only operation would be exposed?

Candidate operation:

```text
ao_repo_query_readonly
```

Possible contract:

1. accept an explicit query string;
2. read existing repo vector index metadata;
3. retrieve current chunks only;
4. return the same bounded source metadata already used by
   `repo query --output markdown`;
5. emit tool-call evidence.

Decision for this slice:

```text
not_implemented
```

Reason: RI-6.2 and RI-6.3 already provide the safer operator-visible path:
stdout Markdown handoff plus explicit workflow opt-in validation. An MCP tool
would create a new hidden-context risk unless its evidence, policy, freshness,
namespace, redaction, and prompt-boundary behavior are fully specified and
tested.

### 2.2 Which policy gates apply?

A future implementation would require all of these gates before registration:

| Gate | Requirement |
|---|---|
| Workspace policy | explicit `repo_intelligence.mcp.read.enabled=true` |
| Tool policy | allowlist includes the exact tool name |
| Project root | resolved workspace root must match the requested project root |
| Vector backend | read-only backend configuration only |
| Result limits | hard max query length, result count, and snippet size |
| Freshness | only `content_status=current` chunks may be returned |
| Namespace | vector keys must match the expected `repo_chunk::<project>::<space>::` prefix |
| Source validation | source path, line range, and content SHA256 must validate before return |
| Evidence | every call emits non-secret tool-call evidence |

No such policy gate is implemented in this slice because no MCP tool is
registered.

### 2.3 How are path escapes, stale artifacts, namespace mismatches, limits,
redaction, and source hashes enforced?

A future MCP implementation must fail closed on:

| Condition | Required outcome |
|---|---|
| Path escape | `DENIED` or `ERROR`, no snippets returned |
| Stale artifacts | `DENIED` or `ERROR`, no stale chunks returned |
| Namespace mismatch | `DENIED` or `ERROR` |
| Missing source hash | `DENIED` or `ERROR` |
| Content hash mismatch | `DENIED` or `ERROR` |
| Excess result count | bounded truncation with explicit diagnostic |
| Excess snippet size | bounded truncation with explicit diagnostic |
| Redaction-required content | omit or redact with explicit diagnostic |

Current implemented path remains CLI/operator handoff plus
`validate_repo_intelligence_workflow_opt_in(...)`; that helper already rejects
path escape, stale freshness, namespace mismatch, hash mismatch, and hidden
injection in explicit handoff files.

### 2.4 How does the tool avoid hidden prompt injection?

A future MCP tool must not directly write to prompts, session memory,
`context_compiler`, root authority files, or workflow inputs.

Minimum safe shape:

1. tool result is data only;
2. result carries support tier and provenance;
3. caller must explicitly pass the result as visible workflow input;
4. no implicit memory write;
5. no automatic `context_compiler` feed;
6. no root export;
7. no adapter execution.

Current decision keeps this simpler:

```text
no MCP repo-intelligence result exists
```

Therefore there is no new hidden injection surface in this slice.

### 2.5 What evidence is emitted for tool calls?

Future evidence would need:

| Evidence field | Purpose |
|---|---|
| tool name and version | identify exact MCP surface |
| policy decision | prove read policy allowed the call |
| project root identity | bind result to repo identity |
| query digest | avoid logging sensitive full query by default |
| namespace prefix | prove vector namespace boundary |
| source artifact hashes | bind result to repo chunks/index |
| result count and truncation | prove bounded output |
| freshness state | prove current-only result |
| denied reason codes | make fail-closed decisions auditable |

This slice emits no MCP evidence because no repo-intelligence MCP tool is
registered.

## 3. Current Guard

The current product boundary is:

| Surface | Status |
|---|---|
| `repo query --output markdown` | beta explicit handoff |
| `validate_repo_intelligence_workflow_opt_in(...)` | beta explicit handoff validation |
| `review_ai_flow + codex-stub` read-only rehearsal | deterministic evidence path |
| repo-intelligence MCP tool | not registered |
| `context_compiler` auto-feed | not registered |
| root export from query/handoff | not registered |

Regression coverage now pins both MCP registration surfaces:

1. `TOOL_DEFINITIONS` / `TOOL_DISPATCH`;
2. runtime `create_tool_gateway().list_tools()`.

## 4. Files Changed

| File | Change |
|---|---|
| `tests/test_repo_intelligence_no_mcp_root_export_guard.py` | Adds a ToolGateway-level guard proving repo-intelligence is not registered as an MCP tool. |
| `.claude/plans/RI-6.5-REPO-INTELLIGENCE-MCP-DESIGN-GATE.md` | Records the design decision and future gate requirements. |

## 5. Validation

Startup and program checks:

```bash
git status --short --branch
git rev-list --left-right --count HEAD...origin/main
bash .claude/scripts/ops.sh preflight
python3 scripts/gpp_next.py
```

Focused guard tests:

```bash
pytest -q tests/test_repo_intelligence_no_mcp_root_export_guard.py
```

Related MCP/tool tests:

```bash
pytest -q tests/test_repo_intelligence_no_mcp_root_export_guard.py tests/test_tool_gateway.py tests/test_mcp_server.py
```

Static and guard checks:

```bash
python3 -m ruff check tests/test_repo_intelligence_no_mcp_root_export_guard.py
git diff --check
python3 scripts/gpp_next.py
```

Observed results:

| Command | Result |
|---|---|
| `pytest -q tests/test_repo_intelligence_no_mcp_root_export_guard.py` | 8 passed |
| `pytest -q tests/test_repo_intelligence_no_mcp_root_export_guard.py tests/test_tool_gateway.py tests/test_mcp_server.py` | 130 passed |
| `python3 -m ruff check tests/test_repo_intelligence_no_mcp_root_export_guard.py` | passed |
| `git diff --check` | passed |
| `python3 scripts/gpp_next.py` | GPP-2 blocked, support widening false, production platform claim false, live adapter execution false |
| `python3 -m ao_kernel doctor` | 8 OK, 1 WARN, 0 FAIL; existing bundled extension truth warning only |

## 6. Exit Decision

Decision:

```text
repo_intelligence_mcp_design_gate_closed_no_tool_no_support_widening
```

Closeout conditions:

| Condition | Status |
|---|---|
| Exact read-only MCP operation decision recorded | satisfied |
| Future policy gates documented | satisfied |
| Path/freshness/namespace/hash/redaction requirements documented | satisfied |
| Hidden injection avoidance documented | satisfied |
| Future evidence requirements documented | satisfied |
| MCP tool implementation | not performed |
| ToolGateway repo-intelligence registration | not performed and regression-tested |
| `context_compiler` auto-feed | not performed |
| Root export | not performed |
| Support widening | not performed |
| Production platform claim | not performed |
| Live adapter execution | not performed |
| GPP-2 blocked state | preserved |
