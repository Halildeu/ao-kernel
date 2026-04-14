# Changelog

All notable changes to ao-kernel are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.2.0] - 2026-04-14

Safety & Hygiene release. Faz 5 Preflight (operational security) + Tranş A
(productization + honest registry). Also rolls up Faz 4 scaffolds that
landed between v2.1.1 and v2.2.0.

### Added
- `SECURITY.md` — disclosure channel, threat model, secrets best practices,
  operational hardening guide.
- `examples/hello-llm/` — first runnable quickstart (README, main.py,
  requirements.txt, .env.example); zero-to-governed-LLM-call in under 5 min.
- README "SDK vs MCP" capability matrix — makes the thin-executor nature
  of `ao_llm_call` explicit at documentation surface.
- `.githooks/` versioned (pre-commit + pre-push) with secret / large-file /
  direct-main / WIP guards. Repos can opt in via `core.hooksPath=.githooks`.
- `.archive/patches/` — historical `.patch` backups moved out of repo root.
- GitHub `main` branch protection with 6 required checks (lint, test × 3,
  coverage, typecheck). Enforced for admins. Tag ruleset protects `v*`.
- CI: `test.yml` split into `lint` / `test (3.11|3.12|3.13)` / `coverage` /
  `typecheck` / `extras-install` jobs. Typecheck is now a real blocking gate.
- Regression guard test for capability overclaims
  (`test_registry_overclaim_guard.py`).
- Faz 4 scaffolds (from v2.1.1 → v2.2.0 interval):
  - Semantic retrieval feature flag (default OFF, `AO_SEMANTIC_SEARCH=1`)
  - Secrets provider factory + HashiCorp Vault provider (KV v2 HTTP)
  - Extension loader + runtime registry (18 bundled manifests)
  - Vector store abstraction (InMemoryVectorStore + PgvectorBackend)
  - Roadmap checkpoint/resume (SHA256 integrity, JSONL step audit)
  > NOTE: these are **scaffolds**, not yet wired to the production code
  > path. Integration (vector store → semantic_retrieval, secrets factory
  > → LLM transport, extension loader → startup) is tracked for Tranş B.
- Faz 3 additions: SecretsProvider ABC enforcement, MCP HTTP transport
  tests, memory distiller edge case tests.
- Faz 2 additions: tool use graduation (build_tools_param integration,
  registry `supported`), evidence writer client integration, compaction
  edge case tests.

### Fixed
- **Silent failures now visible.** `client.py` evidence writer, eval
  scorecard, and streaming post-processor failures no longer `except: pass`;
  they log structured warnings (`logger.warning` with request_id + provider).
- **Streaming evidence was never written** (keyword-only arg mismatch +
  missing model param). Preserved from Faz 2 fix.
- **Compaction tests** used wrong context key (`decisions` →
  `ephemeral_decisions`). Preserved from Faz 2 fix.
- Obsolete `src/*` shim references removed from `llm.py` docstrings.
- **`client.save_checkpoint` / `resume_checkpoint` real bug.** Public
  methods called the internal API with incompatible keyword arguments
  (`label` vs `session_id`, positional vs keyword-only). Tests only covered
  early-return error paths; happy path was broken. Fixed by realigning to
  the internal contract.
- **Strict mypy.** Resolved 131 type errors across the public facade.
  `_internal/*` remains under per-module `ignore_errors` (D13 phased
  coverage); `mcp_server.py` uses targeted `# type: ignore[...]` for MCP
  SDK's untyped decorators.
- 18 empty `__init__.py` files removed from `ao_kernel/defaults/extensions/
  PRJ-*/` (hyphenated names cannot be Python packages — dead files).
- Unused imports in `ao_kernel/llm.py:279` and
  `tests/test_roadmap_internal.py:12` (new ruff F401).

### Changed
- **PyPI classifier:** `Development Status :: 3 - Alpha` →
  `4 - Beta`. Accurately reflects production-grade core + ongoing
  productization.
- **Behavior change (caller-visible): registry overclaim cleanup.**
  `vision`, `audio`, `code_agentic`, and `structured_output` flags are now
  `unsupported` for every provider. Previously several providers advertised
  these as `supported` or `experimental` without a provider-side
  implementation, producing silent failures. Callers will now receive an
  explicit policy deny. See `provider_capability_registry.v1.json` notes.
- Global git config hardened in this maintainer's workspace (rerere,
  reflog 365d, fetch.prune, push.followTags). Not shipped in the package.

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
