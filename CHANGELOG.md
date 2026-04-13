# Changelog

All notable changes to ao-kernel are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Faz 3: SecretsProvider ABC enforcement, MCP HTTP transport tests, memory distiller edge case tests
- Faz 2: Tool use graduation (build_tools_param integration, registry supported), evidence writer client integration, compaction edge case tests

### Fixed
- Streaming evidence was never written (keyword-only arg mismatch + missing model param)
- Compaction tests used wrong context key (`decisions` → `ephemeral_decisions`)
- Obsolete src/* shim references removed from llm.py docstrings

## [2.1.1] - 2026-04-13

### Fixed
- CI: exclude `_internal` from coverage gate to unblock Faz 1-2 test additions

## [2.1.0] - 2026-04-13

### Added
- `AoKernelClient` unified high-level SDK with full governed pipeline
- Self-editing memory (Letta/MemGPT inspired): remember/update/forget/recall
- Semantic vector retrieval with provider embedding + cosine similarity
- Embedding-based groundedness check in eval harness
- End-to-end integration tests (session roundtrip, client pipeline, MCP dispatch)
- Tool use activation: capability loader fix + registry propagation

### Fixed
- 5 integration wiring issues (lifecycle hook, canonical injection, stream tools, MCP desc, vision registry)
- Fail-closed enforcement + policy delegation
- Self-edit memory recall auto-prefix pattern consistency
- 4 ADV-002 advisory warning fixes

### Changed
- CLAUDE.md rewritten: 16 sections, comprehensive and stable

## [2.0.0] - 2026-04-13

### Changed
- **BREAKING:** `src/` shim removed, all internals under `ao_kernel._internal` namespace

### Added
- Hot/warm/cold memory tier enforcement
- MCP HTTP transport (starlette + uvicorn)
- Durable checkpoint/resume for session context
- Tool streaming support (v0.3.0 — tool call deltas reconstructed)
- Chaos/failure smoke tests
- Multi-agent coordination SDK hooks (revision tracking, stale detection)
- Context pipeline: 3-lane compilation, profile routing, decision extraction

## [0.2.0] - 2026-04-12

### Added
- `ao_kernel.llm` public facade: route, build, execute, normalize, stream
- Context management pipeline (compile → inject → extract → promote)
- Canonical decision store with temporal metadata
- Context compiler with 6 profiles (STARTUP, TASK_EXECUTION, REVIEW, EMERGENCY, ASSESSMENT, PLANNING)
- Memory pipeline with governed context loop
- Backlog modules: evidence writer, session management, secrets providers, tool gateway

## [0.1.0] - 2026-04-12

### Added
- Initial release: governed AI orchestration runtime
- Policy engine: 4 types (autonomy, tool calling, provider guardrails, generic)
- Fail-closed governance with JSONL evidence trail
- LLM routing with 6 provider support (Claude, OpenAI, Google, DeepSeek, Qwen, xAI)
- CLI: `ao-kernel init`, `doctor`, `migrate`, `mcp serve`, `version`
- Workspace mode + library mode dual operation
- 324 bundled JSON defaults (policies, schemas, registry, extensions)
