# Using ao-kernel in Your Project

This guide shows how to install `ao-kernel` into **your own repository** and use
it as a **governed control-plane** for AI-assisted work. The core load-bearing
claims and documented surfaces below (fail-closed policy, governed context
persistence, the `doctor` health check, the CLI subcommand surface, and the MCP
tool set) are covered by a doc-bound smoke test
(`tests/test_using_ao_kernel_in_your_project_doc.py`), run against the installed
package with no network and no API key, so this walkthrough stays true to the
shipped package rather than aspirational.

## 1. What ao-kernel is (and is not)

ao-kernel is a **governed AI orchestration runtime** you drop into any Python
project. Its differentiators over general agent frameworks:

- **Fail-closed policy engine** — policy violations and missing/broken policies
  deny by default.
- **Self-hosted JSONL evidence trail** — append-only, integrity-manifested.
- **Governed context pipeline** — decision capture, canonical promotion, tiers.

**It is NOT** a general-purpose agent framework, and it does **not** claim to be a
general-purpose "production coding automation platform". It is a governed runtime
with a deliberately narrow, stable support boundary. These guard flags are
**const false** and stay false:

| Guard flag | State | Meaning |
|---|---|---|
| `live_adapter_execution` | false | ao-kernel does not make programmatic provider API calls on its own |
| `support_widening` | false | the narrow stable support boundary is kept |
| `production_platform_claim` | false | no general-purpose production-platform claim |

## 2. The operating model: your CLI subscriptions, ao-kernel governs

ao-kernel is a **control-plane**, not a provider-API client. The intended model:

- Your AI assistants (Claude Code, Codex, etc.) do the actual work through
  **their own CLI subscriptions / native interfaces**.
- ao-kernel **governs** that work: policy checks, decision capture, evidence,
  consultation, orchestration artifacts.
- **No provider API key is required** for the governance core. You keep using the
  monthly CLI subscriptions you already have.

## 3. Install

```bash
pip install ao-kernel                 # Core (only jsonschema dependency)
pip install ao-kernel==4.1.0          # Exact pin
pip install ao-kernel[mcp]            # + MCP server over stdio (governance tools for AI agents)
pip install ao-kernel[mcp-http]       # + MCP server over HTTP (adds starlette + uvicorn)
pip install ao-kernel[llm]            # + LLM modules (tenacity + tiktoken)
pip install ao-kernel[otel]           # + OpenTelemetry instrumentation
```

The base install gives you the full governance core (policy engine, evidence,
governed context, CLI). The `mcp` extra is only needed to run the MCP server;
`llm` only for token counting / LLM transport helpers.

## 4. Initialize the workspace

```bash
cd your-project
ao-kernel init        # creates .ao/ (session persistence, evidence, canonical store)
ao-kernel doctor      # health check
```

Without `.ao/`, ao-kernel runs in **library mode** (in-memory, no persistence).
After `ao-kernel init` you are in **workspace mode** with the full pipeline.

`ao-kernel doctor` reports `OK` / `WARN` / `FAIL`. A base install shows a `WARN`
for the optional `tenacity/tiktoken` extra and a `WARN` for bundled-extension
truth (the narrow support boundary) — both expected, neither a `FAIL`.

## 5. Use the governance core (Python)

The fail-closed policy engine and governed context work with **no API key**:

```python
from pathlib import Path
from ao_kernel import AoKernelClient, governance

ws = Path(".")

# Fail-closed policy engine: a missing policy denies by default.
result = governance.check_policy("nonexistent_policy", {"action": "x"}, workspace=ws)
assert result["decision"] == "deny"          # fail-closed

# Governed context pipeline: capture and recall decisions.
with AoKernelClient(workspace_root=".") as client:
    client.record_decision("db_choice", "postgres", confidence=0.9)
    hits = client.query_memory("db_choice")  # -> list of decision records
    # A bundled policy is evaluated by the engine, not bypassed:
    client.check_policy("policy_cost_tracking", {"action": "llm_call"})
```

`record_decision` persists to `.ao/canonical_decisions.v1.json`; `query_memory`
reads it back. This is the governed memory loop your AI work runs inside.

## 6. CLI surfaces

```bash
ao-kernel policy-sim run ...     # dry-run a proposed policy change (fail-closed engine)
ao-kernel evidence timeline ...  # self-hosted JSONL evidence: timeline / replay / manifest
ao-kernel consultation ...       # cross-AI consultation (CNS) artefacts
ao-kernel orchestration ...      # multi-agent orchestration artifact emission (read-only)
ao-kernel quality ...            # ADR / quality-profile / CHANGELOG discipline checks
```

## 7. MCP governance tools for your AI agents

To let an MCP-capable agent call ao-kernel's governance tools directly:

```bash
# stdio transport (default):
pip install ao-kernel[mcp]
ao-kernel mcp serve

# HTTP transport needs the separate mcp-http extra (adds starlette + uvicorn):
pip install ao-kernel[mcp-http]
ao-kernel mcp serve --transport http --port 8080
```

This exposes governance tools (`ao_policy_check`, `ao_llm_route`,
`ao_quality_gate`, `ao_workspace_status`, `ao_memory_read`, `ao_memory_write`,
…) so your agent's actions are policy-gated and evidence-logged.

> The MCP server is a **thin executor** (route → build → execute → normalize). It
> does **not** add context injection, eval, or quality-gate enforcement — for the
> full governed pipeline use `AoKernelClient` in-process.

## 8. Support boundary

- Supported, API-keyless core: policy engine, evidence trail, governed context,
  CLI (`init`, `doctor`, `evidence`, `policy-sim`, `consultation`,
  `orchestration`, `quality`).
- `mcp` / `llm` / `otel` are **opt-in extras**.
- ao-kernel is a **governed control-plane**, not a production-platform; the three
  guard flags above remain false. See `docs/SUPPORT-BOUNDARY.md` for the full
  matrix and `.claude/plans/EPIC-9-PR-XFINAL-SUPERSESSION-CLOSEOUT.md` for the
  scope decision behind it.
