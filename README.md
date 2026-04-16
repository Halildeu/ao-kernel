# ao-kernel

Governed AI orchestration runtime — policy-driven, fail-closed, evidence-trail.

ao-kernel is **not** a general-purpose agent framework. It is a **governed runtime** that enforces policies, records evidence, and provides deterministic LLM routing for production Python teams.

## Installation

```bash
pip install ao-kernel                # Core (only jsonschema dependency)
pip install ao-kernel[llm]           # LLM modules (tenacity + tiktoken)
pip install ao-kernel[mcp]           # MCP server support
pip install ao-kernel[otel]          # OpenTelemetry instrumentation
pip install ao-kernel[llm,mcp,otel]  # Everything
```

Requires Python 3.11+.

## Quick Start

```bash
# Create workspace
ao-kernel init

# Check health
ao-kernel doctor
```

```python
# Library mode (no workspace required)
from ao_kernel.config import load_default
policy = load_default("policies", "policy_autonomy.v1.json")

# LLM routing
from ao_kernel.llm import build_request, normalize_response

request = build_request(
    provider_id="openai",
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}],
    base_url="https://api.openai.com/v1/chat/completions",
    api_key="sk-...",
)

# Streaming
from ao_kernel.llm import build_request as build_req

stream_request = build_req(
    provider_id="claude",
    model="claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": "Hello"}],
    base_url="https://api.anthropic.com/v1/messages",
    api_key="sk-ant-...",
    stream=True,
)
```

## CLI Reference

| Command | Description |
|---|---|
| `ao-kernel init` | Create `.ao/` workspace |
| `ao-kernel doctor` | Workspace health check (8 checks) |
| `ao-kernel migrate [--dry-run] [--backup]` | Version migration |
| `ao-kernel version` | Print version |
| `ao-kernel mcp serve` | Start MCP server (stdio) |
| `ao-kernel evidence timeline --run <id>` | Chronological event timeline (table or `--format json`) |
| `ao-kernel evidence replay --run <id>` | Inferred state trace replay (`--mode inspect\|dry-run`) |
| `ao-kernel evidence generate-manifest --run <id>` | On-demand SHA-256 manifest |
| `ao-kernel evidence verify-manifest --run <id>` | Recompute + verify manifest integrity |

### Quick Demo

```bash
python3 examples/demo_bugfix.py --workspace-root .
```

Runs the governed bug-fix workflow end-to-end with a deterministic stub adapter (no LLM required). See `docs/DEMO-SCRIPT.md` for the full 11-step acceptance flow.

## Python API

### ao_kernel.config

| Function | Description |
|---|---|
| `workspace_root(override=None)` | Resolve workspace (returns `None` in library mode) |
| `load_default(resource_type, filename)` | Load bundled JSON default |
| `load_with_override(resource_type, filename, workspace)` | Workspace override > bundled default |

### ao_kernel.llm

| Function | Description |
|---|---|
| `resolve_route(intent, ...)` | Deterministic LLM routing |
| `build_request(provider_id, model, messages, ...)` | Provider-native HTTP request |
| `normalize_response(resp_bytes, provider_id)` | Extract text + usage + tool_calls |
| `extract_text(resp_bytes)` | Extract text from response |
| `execute_request(url, headers, body_bytes, ...)` | HTTP with retry + circuit breaker |
| `stream_request(url, headers, ...)` | SSE streaming with OK/PARTIAL/FAIL |
| `get_circuit_breaker(provider_id)` | Per-provider circuit breaker |
| `count_tokens(messages, provider_id, model)` | Token counting |

### Supported Providers

| Provider | Streaming | Tool Use | Embedding |
|----------|-----------|----------|-----------|
| Claude | Yes | Yes | No |
| OpenAI | Yes | Yes | Yes |
| Google Gemini | Yes | No | Yes |
| DeepSeek | Yes | Yes | No |
| Qwen | Yes | Yes | No |
| xAI | Yes | Yes | No |

### AoKernelClient — Unified SDK

Full governed pipeline: route → capabilities → context → build → execute → normalize → decisions → eval → telemetry.

```python
from ao_kernel import AoKernelClient

with AoKernelClient(workspace_root=".") as client:
    result = client.llm_call(
        messages=[{"role": "user", "content": "Hello"}],
        intent="FAST_TEXT",
    )
    print(result["text"])
```

## MCP Server

ao-kernel runs as an MCP (Model Context Protocol) server, exposing governance tools:

```bash
ao-kernel mcp serve                          # stdio transport (default)
ao-kernel mcp serve --transport http --port 8080   # HTTP (needs ao-kernel[mcp-http])
```

**Tools:**
- `ao_policy_check` — Validate action against policy (allow/deny)
- `ao_llm_route` — Resolve provider/model for intent
- `ao_llm_call` — Execute governed LLM call (thin executor — see matrix below)
- `ao_quality_gate` — Check output quality
- `ao_workspace_status` — Workspace health
- `ao_memory_read` — Read canonical decisions + workspace facts (policy-gated, fail-closed, read-only)
- `ao_memory_write` — Promote a decision to canonical memory (policy-gated, fail-closed, server-side fixed confidence)

**Resources:**
- `ao://policies/{name}` — Policy JSON
- `ao://schemas/{name}` — Schema JSON
- `ao://registry/{name}` — Registry JSON

### SDK vs MCP — Which one should I use?

`AoKernelClient` (SDK) runs the **full governed pipeline**. `ao_llm_call` (MCP) is a **thin executor** — by design, not a limitation. Pick the surface that matches your trust boundary.

| Stage | `AoKernelClient.llm_call` (SDK) | MCP `ao_llm_call` |
|---|:---:|:---:|
| Route resolution (provider/model) | ✅ | ✅ |
| Capability gap check | ✅ | ✅ (inside build) |
| Context injection (3-lane compile) | ✅ | ❌ |
| Transport + retry + circuit breaker | ✅ | ✅ |
| Normalize (text/usage/tool_calls) | ✅ | ✅ |
| Decision extraction + memory loop | ✅ | ❌ |
| Evidence trail (JSONL) | ✅ | ❌ |
| Eval scorecard (diagnostic) | ✅ | ❌ |
| Quality gates (policy-enforced) | ✅ (`evaluate_quality`) | ✅ (`ao_quality_gate`) |
| OTEL telemetry | ✅ | ❌ |

**Rule of thumb:**
- **SDK** — your own Python process runs the governed loop. Full context, full audit.
- **MCP** — an external agent (Claude Desktop, Cursor, your own MCP client) delegates a single LLM call through the governance boundary. Context, memory, and telemetry stay in the caller's process, not in the server.

Mixing is fine: an MCP client can call `ao_policy_check` and `ao_quality_gate` for governance decisions, run its own LLM, and call back for `ao_workspace_status`. The server stays thin on purpose.

## Context Management

Governed context loop — decisions extracted, scored, and injected automatically.

```python
from ao_kernel.context import start_session, process_turn, compile_context, end_session

# Start session
ctx = start_session(workspace_root=".", session_id="my-session")

# After each LLM turn — automatic extraction + compaction
ctx = process_turn(llm_output, ctx, workspace_root=".", request_id="req-1")

# Compile context for next LLM call (relevance-scored, budget-aware)
compiled = compile_context(ctx, profile="TASK_EXECUTION", max_tokens=4000)
# compiled.preamble → inject into system prompt

# End session — compact + distill + promote
end_session(ctx, workspace_root=".")
```

**SDK Hooks (multi-agent):**
```python
from ao_kernel.context.agent_coordination import record_decision, query_memory

record_decision(ws, key="arch.pattern", value="microservices", confidence=0.9)
items = query_memory(ws, key_pattern="arch.*")
```

**Profiles:** STARTUP (minimal), TASK_EXECUTION (full), REVIEW (quality focus)

## What Makes ao-kernel Different

| | ao-kernel | LangGraph | CrewAI | Pydantic AI |
|---|---|---|---|---|
| Policy engine | 96 policies | No | No | No |
| Fail-closed | Yes | No | No | No |
| Evidence trail | Self-hosted JSONL | LangSmith SaaS | No | No |
| Migration CLI | Yes | No | No | No |
| Doctor | Yes | No | No | No |
| MCP server | Yes | No | No | No |
| Streaming | SSE (6 providers) | Yes | Yes | Yes |

## Architecture

```
ao_kernel/              <- Public facade (clean API)
  client.py             <- AoKernelClient — unified SDK
  llm.py                <- LLM routing, building, normalization
  governance.py         <- Policy SSOT (4 policy types, fail-closed)
  mcp_server.py         <- MCP server (7 tools, 3 resources)
  context/              <- Context pipeline (compile, inject, extract, promote)
  _internal/            <- Private implementation (do not import directly)
  defaults/             <- 338 bundled JSON (policies, schemas, registry, extensions)
```

## Development

```bash
pip install -e ".[dev,llm,mcp]"          # Dev environment
pytest tests/ -x                          # Run tests
ruff check ao_kernel/ tests/              # Lint
mypy ao_kernel/ --ignore-missing-imports  # Type check
```

Coverage target: 70% branch coverage (excluding `_internal`).

## License

MIT
