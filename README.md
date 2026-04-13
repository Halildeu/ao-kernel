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

Supported providers: Claude, OpenAI, Google Gemini, DeepSeek, Qwen, xAI.

## MCP Server

ao-kernel runs as an MCP (Model Context Protocol) server, exposing governance tools:

```bash
ao-kernel mcp serve  # stdio transport
```

**Tools:**
- `ao_policy_check` — Validate action against policy (allow/deny)
- `ao_llm_route` — Resolve provider/model for intent
- `ao_quality_gate` — Check output quality
- `ao_workspace_status` — Workspace health

**Resources:**
- `ao://policies/{name}` — Policy JSON
- `ao://schemas/{name}` — Schema JSON
- `ao://registry/{name}` — Registry JSON

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
ao_kernel/          <- Public facade (clean API)
  cli.py            <- CLI commands
  config.py         <- Workspace + defaults resolver
  llm.py            <- LLM routing, building, normalization
  mcp_server.py     <- MCP server (4 tools, 3 resources)
  telemetry.py      <- OpenTelemetry (lazy no-op fallback)
  defaults/         <- 338 bundled JSON (policies, schemas, registry, extensions, ops)

src/                <- Compat shim (deprecated, use ao_kernel.*)
```

## License

MIT
