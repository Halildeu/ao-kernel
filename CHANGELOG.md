# Changelog

All notable changes to ao-kernel are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — FAZ-A PR-A0 (docs + spec, no code)

- Agent adapter contract schema (`ao_kernel/defaults/schemas/agent-adapter-contract.schema.v1.json`). Defines how external coding agent runtimes (Claude Code CLI, Codex, Cursor background agent, GitHub Copilot cloud agent, gh CLI PR connector, custom CLI/HTTP) integrate with ao-kernel. 8 `adapter_kind` variants + 6 `capabilities` + `cli`/`http` invocation + input/output envelopes + evidence/policy refs. Referential integrity with workflow-run and worktree policy is narrative at PR-A0; loader-level validation lands in Tranche A PR-A2.
- Workflow run canonical state schema (`ao_kernel/defaults/schemas/workflow-run.schema.v1.json`). Durable 9-state machine with CAS revision token, checkpoint refs, budget (fail-closed on exhaust), HITL interrupt + governance approval tokens as separate domains, and allowed-transition table documented inline.
- Worktree execution profile policy (`ao_kernel/defaults/policies/policy_worktree_profile.v1.json`). CNS-016 D4 expanded minimum — per-agent worktree + sanitized env allowlist + secret deny-by-default with explicit `allowlist_secret_ids` + command allowlist (POSIX prefixes incl. Apple Silicon `/opt/homebrew/bin/`) + cwd confinement + evidence redaction (6 P0 patterns: `sk-`, `sk-ant-`, `ghp_`, `xoxb-`, `Bearer`, `Basic`). Three rollout tiers: dormant (bundled default) / report_only / block. SSH agent forwarding, network/egress OS sandbox, and extended redaction catalog (AWS / Google / xAI / structured JWT) deferred to FAZ-A PR-A5 or FAZ-B.
- Docs: `docs/ADAPTERS.md` (adapter contract human-readable + 3 walkthroughs), `docs/WORKTREE-PROFILE.md` (operator-facing sandbox guide + demo override example), `docs/EVIDENCE-TIMELINE.md` (17-event taxonomy across 8 categories + replay contract + JSONL layout), `docs/DEMO-SCRIPT.md` (FAZ-A release-gate 11-step end-to-end demo), `docs/COMPETITOR-MATRIX.md` (9-row live competitor / adapter matrix per CNS-016 W3, prevents "rakipsiz" regression).
- Adversarial consensus: CNS-20260415-019 iter-1 PARTIAL (2 blocking + 18 warning) → iter-2 AGREE (`ready_for_impl: true`). All blocking and 14 high-value warnings absorbed into plan v2 before implementation; 4 warnings relocated as scope / defer decisions.
- Foundation for FAZ-A governed demo MVP (v3.1.0 ship target). Implementation lands in Tranche A PR-A1 through PR-A6.

### Added — FAZ-A PR-A1 (workflow state machine + run store)

- `ao_kernel/workflow/` package: public facade for workflow run lifecycle. Seven modules, narrow re-export surface (private helpers `_mutate_with_cas`, `_run_path`, `_lock_path`, `_get_validator`, `load_workflow_run_schema` intentionally hidden).
- State machine (`state_machine.py`): 9-state transition table from PR-A0 `workflow-run.schema.v1.json` as pure functions + immutable `TRANSITIONS` mapping. Literal expected-table test (no schema-narrative parsing) covers all 9 × 9 transition pairs.
- Run store (`run_store.py`): CAS-backed CRUD mirroring `canonical_store.py` pattern. POSIX `file_lock` held for the whole load-mutate-write cycle. Atomic writes via `write_text_atomic` (tempfile + fsync + `os.replace`). `run_revision` hashes a projection of the record with the `revision` field omitted (self-reference-free content addressing). `_mutate_with_cas(workspace_root, run_id, *, mutator, expected_revision=None, allow_overwrite=False) -> tuple[dict, str]` is the single canonical write path (CNS-20260414-010 invariant). `create_run`, `save_run_cas`, and `update_run` all route through it. `run_id` validated as UUIDv4 (explicit `parsed.version == 4`) before use as a path component — path-traversal guard.
- Budget (`budget.py`): immutable `Budget` + `BudgetAxis` dataclasses. `cost_usd` tracked as `Decimal` internally for precision; serialized as `float` on persist per schema `type: number`. `fail_closed_on_exhaust: true` raises `WorkflowBudgetExhaustedError` when the post-spend `remaining` would be strictly negative; spending exactly the remaining amount is valid (next positive spend raises).
- Primitives (`primitives.py`): `InterruptRequest` / `Approval` dataclasses with separate `mint_interrupt_token` / `mint_approval_token` functions (distinct HITL vs governance audit domains). Tokens are `secrets.token_urlsafe(48)` (64-char URL-safe, stdlib — no new core dep). Resume operations are idempotent for repeat calls with identical payload; payload mismatch raises `WorkflowTokenInvalidError`.
- Typed errors (`errors.py`): `WorkflowError` hierarchy + `WorkflowRunIdInvalidError` for path-traversal guard + `WorkflowSchemaValidationError.errors: list[dict]` with `json_path`, `message`, `validator` (utils.py pattern).
- Schema validator (`schema_validator.py`): Draft 2020-12 wrapper around `workflow-run.schema.v1.json`; schema + validator cached via `functools.lru_cache`. Validation runs only at load / save boundaries (perf-safe).
- Tests: 180 new tests across 6 files + 1 fixture (`tests/fixtures/workflow_bug_fix_stub.json`). Per-module coverage: `state_machine`, `primitives`, `schema_validator`, `__init__` at 100%; `errors` 97%, `budget` 94%, `run_store` 89%. Package total 95%.
- Adversarial consensus: CNS-20260415-020 iter-1 PARTIAL (7 blocking + 11 warning absorbed) → iter-2 AGREE (`ready_for_impl=true`, `pr_split_recommendation=single_pr`). Residual impl-time fixes applied in this PR: lock-path `with_name`, UUIDv4 version check, post-stamp validation order, canonicalization aligned with `canonical_store.store_revision`.

### Added — FAZ-A PR-A2 (intent router + workflow registry + adapter manifest loader)

- `ao_kernel/workflow/registry.py`: `WorkflowRegistry` loads bundled `ao_kernel/defaults/workflows/*.v1.json` plus workspace `<workspace_root>/.ao/workflows/*.v1.json`, validates each against the new `workflow-definition.schema.v1.json`, indexes by `(workflow_id, workflow_version)`. Workspace-over-bundled precedence applies only for identical keys; different versions from different sources coexist and `get(id, version=None)` returns the highest SemVer across sources (local comparator, no new runtime dep). `validate_cross_refs(definition, adapter_registry)` returns a structured `list[CrossRefIssue]` with `kind`, `workflow_id`, `step_name`, `adapter_id`, and `missing_capabilities` fields so callers can triage missing-adapter vs capability-gap issues.
- `ao_kernel/workflow/intent_router.py`: rule-first `IntentRouter` with keyword / regex / combined match types, priority-ordered evaluation with duplicate-priority-match detection at classify time, bundled `default_rules.v1.json`. Three fallback strategies: `error_on_no_match` returns `None`; `use_default` requires a non-null `default_workflow_id` (schema conditional) and returns a result with `matched_rule_id='__default__'`; `llm_fallback` raises `NotImplementedError` (interface for PR-A6 `[llm]` extra). Duplicate `rule_id` and regex compile failures are loader-level `IntentRulesCorruptedError` exceptions.
- `ao_kernel/adapters/` new public facade package: `AdapterRegistry` loads `<workspace_root>/.ao/adapters/*.manifest.v1.json`, validates each against PR-A0 `agent-adapter-contract.schema.v1.json`, exposes `get`, `list_adapters`, `supports_capabilities`, and `missing_capabilities(adapter_id, required) -> frozenset[str]`. Filename convention: stem (minus `.manifest.v1.json`) must exactly equal `raw["adapter_id"]` — no underscore↔dash normalization, to prevent typosquatting. `LoadReport.skipped` carries a 6-reason taxonomy (`json_decode`, `schema_invalid`, `adapter_id_mismatch`, `read_error`, `not_an_object`, `duplicate_adapter_id`).
- Schemas: `workflow-definition.schema.v1.json` (closed contract — `additionalProperties: false` at top level and in every `$defs` object; `expected_adapter_refs` and `steps[*].adapter_id` items pinned to the PR-A0 adapter-id pattern; `on_failure` enum closed to `transition_to_failed` / `retry_once` / `escalate_to_human`; `actor=adapter` conditionally requires `adapter_id`). `intent-classifier-rules.schema.v1.json` (conditional validation ties `match_type` to non-empty `keywords` / `regex_any`; `fallback_strategy=use_default` conditionally requires a non-null `default_workflow_id`; optional per-rule `workflow_version` pin).
- Bundled defaults: `ao_kernel/defaults/workflows/bug_fix_flow.v1.json` and `ao_kernel/defaults/intent_rules/default_rules.v1.json`.
- Errors: extended `ao_kernel/workflow/errors.py` with `WorkflowDefinitionNotFoundError`, `WorkflowDefinitionCorruptedError`, `WorkflowDefinitionCrossRefError`, `IntentRulesCorruptedError`. New `ao_kernel/adapters/errors.py` with `AdapterError` hierarchy.
- Tests: 76 new tests across 4 files (`test_workflow_registry.py`, `test_intent_router.py`, `test_adapter_manifest_loader.py`, `test_pr_a2_integration.py`) plus 9 manifest fixtures (4 happy, 5 negative including `bad-id-mismatch`, `bad-schema`, `bad-not-object`, and two `bad-duplicate-*` manifests demonstrating filename-id matching). Pattern-drift regression guards cross-check `workflow_id` / `workflow_version` / `adapter_id` patterns and the `capability_enum` between workflow-definition, workflow-run, and agent-adapter-contract schemas.
- Adversarial consensus: CNS-20260415-021 iter-1 PARTIAL (7 blocking + 10 warning absorbed in plan v2) → iter-2 AGREE (`ready_for_impl=true`, `pr_split_recommendation=single_pr`).

### Fixed

- `agent-adapter-contract.schema.v1.json`: removed `additionalProperties: false` from the top-level `invocation` object so the `oneOf` discriminator over `invocation_cli` / `invocation_http` can validate transport-specific fields. The branch schemas retain their own `additionalProperties: false`, so extras at each branch level are still rejected. Bug surfaced the first time PR-A2 tests ran a real manifest through the validator; shipping alongside PR-A2.

## [3.0.0] - 2026-04-14

**Tranche C release.** Ships the memory MCP surface (read + write),
finishes the CAS-based write path, opts every `_internal` submodule
into strict mypy, raises the coverage gate to 85, and declares
POSIX-only support. Every PR passed through an adversarial Codex
consultation (CNS-20260414-010 / 011 / 012); 16 blocking + 22 warning
objections were grep-verified and absorbed.

### Breaking changes

- **POSIX-only contract.** `pyproject.toml` classifier flipped to
  `Operating System :: POSIX`. `ao_kernel/_internal/shared/lock.py`
  raises `LockPlatformNotSupported` on Windows. Windows support
  remains a Tranche D follow-up.
- **`CanonicalStoreCorruptedError`** is now raised when the canonical
  store file cannot be parsed (previously the reader returned an
  empty default). Callers that relied on the silent fallback must
  catch the new error or restore a healthy file.
- **`save_store` deprecated.** Production write paths must route
  through `save_store_cas(...)` or the `canonical_store` mutator
  helpers; `save_store()` emits a `DeprecationWarning` since v3.0.0
  and will be removed in v4.0.0.
- **Evidence contract clarified.** CLAUDE.md §2 now documents the
  dual form: MCP events land in JSONL (fsync-only, daily-rotated),
  while workspace artefacts keep the SHA256 integrity manifest. The
  MCP manifest is deferred to Tranche D.

### Added — Memory MCP surface (C6a + C6b, CNS-20260414-011 / 012)

- `ao_memory_read` MCP tool. Policy-gated, fail-closed, read-only
  canonical / fact query with per-workspace rate limiting and a
  param-aware workspace resolver.
- `ao_memory_write` MCP tool. Policy-gated, server-side fixed
  confidence (caller-supplied `confidence` is ignored per CNS-010
  iter-3 Q9), JSON-encoded value size guard, prefix allowlists.
- `ao_kernel/_internal/mcp/memory_tools.py` private sub-module
  carries both handlers, the strict resolver, the per-workspace
  rate-limit registry, and the validated policy loaders.
- `policy_mcp_memory.v1.json` + matching JSON schema (fail-closed
  defaults).
- `policy_tool_calling.v1.json` gains an optional
  `implicit_canonical_promote` block so operators can tune the
  promotion threshold + source prefix per workspace without code
  changes; the hard-coded 0.8 threshold was removed.

### Added — CAS write path (C5a / C5b, CNS-20260414-010)

- `canonical_store.save_store_cas(...)` public low-level writer.
- `canonical_store._mutate_with_cas(...)` private helper — **the**
  canonical write path; every mutator routes through it.
- POSIX FS lock (`ao_kernel/_internal/shared/lock.py::file_lock`).
- `write_text_atomic` now uses unique temp names (`mkstemp`) to
  eliminate the old fixed-suffix race.

### Added — Workspace contract (C0, CNS-20260414-010)

- `ao_kernel/workspace.py::project_root()` single source of truth;
  `mcp_server._find_workspace_root` delegates. Project root = the
  directory that contains `.ao/`, **not** `.ao/` itself.

### Changed — Strict typing & coverage (C1 / C2 / C3 / C4)

- Every `_internal/*` submodule opted into strict mypy (D13 staged
  plan completed): providers, shared, secrets, evidence, session,
  orchestrator, prj_kernel_api.
- Branch-coverage gate ratcheted 70 → 75 → 80 → 85 alongside new
  tests for `_internal/session/context_store`,
  `_internal/evidence/writer`, and `ao_kernel/workspace`.
- `ao_kernel/telemetry.py` moved into the coverage omit list — OTEL
  stays optional (D12), so CI without the `[otel]` extra cannot
  exercise the observability branches.

### Changed — Extension manifests (C7a)

- `intake_*` entrypoints now live solely on `PRJ-WORK-INTAKE`;
  `PRJ-KERNEL-API` no longer duplicates them.
- `PRJ-ZANZIBAR-OPENFGA` manifest rewritten to satisfy the
  extension-manifest schema (`semver`, `origin`, `owner`,
  `layer_contract`, `policies`, `ui_surfaces`, corrected `version`
  enum).
- `ExtensionRegistry.find_conflicts()` now returns `[]` on the
  bundled set (regression test added).

### Added — CLI + concurrency invariants (C8)

- `tests/test_cli_concurrency.py` exercises
  - `doctor` from a sub-directory (C0 / `project_root()` invariant)
  - `init` + `migrate --dry-run` happy path
  - parallel `promote_decision` through `_mutate_with_cas` FS lock

### Docs

- CLAUDE.md §2 invariant rewritten (evidence dual form).
- CLAUDE.md §5 architecture section updated for 7 MCP tools and
  the new `_internal/mcp/` package.
- README MCP-tool matrix expanded to 7 tools.
- Handoff + plan files under `.claude/plans/` track each PR.

### Adversarial consensus — Tranche C stats

| CNS | Topic | Iterations | Blocking | Warning |
|---|---|---|---|---|
| 010 | master plan + C0/C5/C6 | 3 | 10 | 7 |
| 011 | C6a implementation | 3 | 5 | 9 |
| 012 | C6b implementation | 2 | 1 | 6 |

Claude's first thesis survived 0/8 times — the "grep before
accepting" rule (see `feedback_codex_consultations.md`) fired on
every iteration.

## [2.3.0] - 2026-04-14

**Faz 4 Wiring release.** Closes Tranche B — every scaffold that shipped
in v2.2.0 now has a real production path, validated via adversarial
Codex consultations (CNS-007, CNS-008, CNS-009). 12 blocking + 7 warning
objections surfaced, every one verified with grep and absorbed into the
implementation.

### Added — Vector store pipeline (B1, CNS-007)
- `AoKernelClient(vector_store=..., owns_vector_store=..., embedding_config=...)`
  — explicit backend injection for tests / advanced use.
- `EmbeddingConfig` dataclass resolved via precedence
  constructor > policy > env > default. Decoupled from the chat route
  because most chat providers (Anthropic, DeepSeek, xAI) have no
  embeddings endpoint — propagating chat provider/model there would
  silently break semantic retrieval.
- Env surface: `AO_KERNEL_VECTOR_BACKEND`, `AO_KERNEL_PGVECTOR_DSN`,
  `AO_KERNEL_VECTOR_STRICT`, `AO_KERNEL_PGVECTOR_TABLE`,
  `AO_KERNEL_EMBEDDING_DIMENSION`, `AO_KERNEL_EMBEDDING_PROVIDER`,
  `AO_KERNEL_EMBEDDING_MODEL`, `AO_KERNEL_EMBEDDING_BASE_URL`.
- Policy `semantic_retrieval` block in `policy_context_memory_tiers.v1.json`
  (enable + backend.strict/fail_action + embedding.provider/model).
- Errors: `VectorStoreConfigError`, `VectorStoreConnectError`.
- `VectorStoreBackend.close()` default no-op so subclass authors don't
  have to bring their own. `PgvectorBackend` overrides for real cleanup.
- pgvector schema now carries `embedding_model` (BTREE-indexed). Store
  rejects dimension OR model mismatches; search transparently filters
  when bound so vectors from different embedding spaces never mingle.
- Sidecar write-path: `memory_pipeline.process_turn` and
  `canonical_store.promote_decision` now embed + index every decision
  via `semantic_indexer.index_decision` when a backend is configured.
  Write-path failures are silent by contract (deterministic fallback
  preserved).

### Added — Secrets dual-read (B2, CNS-005 D0.3)
- `ao_kernel/_internal/secrets/api_key_resolver.py`:
  `resolve_api_key(provider_id, *, environ=, secrets_provider=, audit=)`
  — factory-first, env fallback. `@overload` typed audit for mypy strict.
- Provider aliases: `claude` ↔ `ANTHROPIC_API_KEY`/`CLAUDE_API_KEY`,
  `google`/`gemini` ↔ `GOOGLE_API_KEY`/`GEMINI_API_KEY`,
  `qwen` ↔ `DASHSCOPE_API_KEY`/`QWEN_API_KEY`,
  `xai`/`grok` ↔ `XAI_API_KEY`. Unknown providers fall back to
  `{PROVIDER}_API_KEY` (pre-D0.3 behavior).
- `EnvSecretsProvider._SECRET_ID_TO_ENV` expanded from 1 to 9 entries.
- `mcp_server.py` `ao_llm_call` uses the resolver; `MISSING_API_KEY`
  now lists every env name that was checked so operators know which to
  set.

### Added — Extension activation (B3, CNS-008)
- `AoKernelClient.extensions` (ExtensionRegistry) + `client.action_registry`
  (ActionRegistry) + `client.call_action(name, params)`.
- `ao_kernel/extensions/dispatch.py` — explicit `ActionRegistry` with
  duplicate-registration protection. D7 preserved: no importlib magic,
  no setuptools `entry_points`.
- `ao_kernel/extensions/bootstrap.py` — `register_default_handlers()`
  with an explicit module list. Adding a bundled handler is a two-line
  change; failure in one handler never blocks the others.
- `PRJ-HELLO` reference extension + `hello_world` kernel_api_action.
- `ExtensionManifest` is now lossless — schema-required fields (owner,
  ui_surfaces, compat) plus discovery metadata (docs_ref, ai_context_refs,
  tests_entrypoints) all round-trip. `manifest_path`, `content_hash`,
  `source`, `activation_blockers`, `stale_refs` populated at load.
- `ExtensionRegistry.find_conflicts()` surfaces duplicate entrypoint
  declarations. Bundled set has three known conflicts
  (`intake_create_plan/next/status` between PRJ-KERNEL-API and
  PRJ-WORK-INTAKE); first-wins is deterministic across runs thanks to
  sorted iteration.
- Compat gate: manifests whose `core_min`/`core_max` excludes the running
  `ao_kernel.__version__` stay in `list_all()` but drop out of
  `list_enabled()` and receive `activation_blockers`.
- Workspace-root semantic normalized: loader expects the PROJECT ROOT
  (directory containing `.ao/`), matching `AoKernelClient` semantics.
- Schema accepts additional properties (`additionalProperties: true`)
  so forward-compat vendor fields don't gate the whole registry.

### Added — MCP evidence trail (B4)
- `ao_kernel/_internal/evidence/mcp_event_log.py` —
  `record_mcp_event(workspace, tool, envelope, params=, duration_ms=, extra=)`.
  Daily-rotated JSONL at `.ao/evidence/mcp/YYYY-MM-DD.jsonl`.
- Every MCP tool dispatch now emits one event (wrapper pattern;
  `TOOL_DISPATCH[name].__wrapped__` keeps test-facing handler identity).
- Redaction: keys matching `api_key`/`token`/`secret`/`messages`/
  `content`/`prompt` suffixes have values replaced with `***REDACTED***`;
  secret-shaped substrings (`sk-…`, `ghp_…`) scrubbed from free text.
- Shape projection for `params`/`data` fields — type names only, values
  never land in the log. Auditors can reconstruct the call surface
  without leaking content.
- Writer robustness: `_append_text` and `_append_jsonl` now `flush()` +
  `os.fsync()` with atomic parent `mkdir`. Integrity manifest is
  meaningful under crash.

### Added — Agent coordination SDK (B5, CNS-009)
- `ao_kernel.context` re-exports every coordination hook:
  `record_decision`, `query_memory`, `get_revision`, `has_changed`
  (new canonical name), `check_stale` (back-compat alias),
  `read_with_revision`, `compile_context_sdk`, `finalize_session_sdk`.
- `AoKernelClient` gains matching wrapper methods that auto-thread the
  client's `session_id` and `workspace_root` — canonical provenance
  (`promoted_from`) is no longer empty for client-driven writes.
  Library mode (no workspace) refuses memory ops with a clear error
  instead of silently failing later.
- `client.compile_context_sdk(...)` builds a preamble WITHOUT issuing
  an LLM call (handoff, audit, prompt-cache warming).
- `client.finalize_session(auto_promote, promote_threshold)` — single
  finalize primitive. Returns the canonical delta count.

### Changed — Agent coordination contracts (B5, CNS-009)
- **Breaking for direct callers of `agent_coordination`:**
  `record_decision(auto_promote=False)` no longer silently writes a
  short-TTL canonical entry. It now writes to the supplied session
  context (ephemeral) or reports `destination="dropped"` when no
  context is supplied. Flag name and behavior now agree.
- `get_revision()` returns the full 64-character SHA-256 hex digest
  instead of a 16-character truncation. Callers must treat the token as
  opaque; tests should not assert on its length.
- `session_lifecycle.end_session` gained `auto_promote` +
  `promote_threshold` parameters; `finalize_session_sdk` delegates
  promotion to `end_session` instead of running a second pass. Fixes
  silent double-promotion and threshold-mismatch bug where
  `auto_promote=False` was ignored.

### Fixed
- Extension loader previously dropped `owner`, `ui_surfaces`, and
  `compat` fields silently; schema-invalid manifests were accepted with
  defaulted values. Both paths now surface via `LoadReport.skipped` with
  a `schema_invalid` reason.
- `context_compiler.compile_context` now accepts `embedding_config=` and
  `vector_store=` so `_apply_semantic_reranking` can reach the
  embedding pipeline. Previously `semantic_search(api_key="")` returned
  an empty embedding every time — semantic reranking was effectively
  dead.
- `embed_decision` cache-invalidation now also keys on the configured
  model. Previously a model upgrade silently kept stale embeddings.
- `.gitignore` covers `.ao/canonical_decisions*.json`, `.ao/evidence/`,
  `.ao/sessions/`, `.ao/cache/`, and the defensive `.ao/.ao/` nested
  directory so runtime artefacts stop leaking into commits.

### Scope fences (deliberately deferred)
- OS-level filesystem lock / CAS for concurrent canonical writers —
  tracked as "multi-tenant write safety" CNS per CNS-009 consensus.
  `has_changed()` is ADVISORY ONLY and documents this limitation.
- MCP `ao_memory_*` tools — scope creep; the MCP surface needs
  dedicated governance review before memory read/write tools land.
- Integration back-fill of the other 17 bundled extensions — PRJ-HELLO
  is the first reference; others register as their code lands.
- `_internal/*` mypy coverage — remains on the D13 phased plan.

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
