# Tranche C — Mid-Session Handoff (2026-04-14)

## TL;DR

**Tranche C is in progress.** CNS-20260414-010 closed with
`final_plan_ready_for_impl: true` after 3 iterations. Three PRs already
merged into main (C0, C5a, C5b). Five more PRs + coverage + release
remain. Everything is unblocked — the next session can open `PR-C6a`
against `origin/main` and keep going.

Previous handoff (post v2.3.0): `SESSION-HANDOFF-2026-04-14-v2.md`.
This doc covers Tranche C progress since then.

---

## Progress Ledger

### CNS-20260414-010 (3-iter adversarial consensus)

10 blocking + 7 warning objections from Codex, all grep-verified and
absorbed. Consensus doc:
`.ao/consultations/CNS-20260414-010.consensus.md`.

Final implementation-ready plan has four deltas from Claude's iter-3
thesis (all in the consensus doc):
1. `ToolSpec.allowed=True` + handler-level deny envelope (NOT `allowed=False + bypass`)
2. Param-aware workspace resolver (`_with_evidence`, implicit promote)
3. Implicit promote policy in **general MCP/tool** scope (not `policy_mcp_memory`)
4. Minimal CAS API surface (no duplicate `*_cas` public helpers)

### Merged this session (3 PRs)

| PR | Scope | Key deliverables |
|---|---|---|
| **#66** C0 | `workspace.project_root()` single source of truth | helper + cross-surface alignment (client / MCP / extension loader) + 8 tests |
| **#67** C5a | CAS mutators + FS lock + unique tmp + fail-closed load | `save_store_cas`, `_mutate_with_cas`, POSIX `file_lock`, `CanonicalStoreCorruptedError`, `CanonicalRevisionConflict` + 13 tests |
| **#68** C5b | `forget()` routes through CAS helper | bypass closed, matching CAS args + 5 tests |

**Main HEAD after PR-C5b:** test suite 922/922 green.

### Still open (5 PRs + release)

Order and scope below. Each assumes branch from latest `origin/main`,
M2 merge pattern (protection approval=0 → merge → approval=1), CI 7/7 first try.

#### PR-C6a — Memory read MCP tool (~200 LOC)

Scope: `ao_memory_read` MCP tool. Read-only, built on existing SDK hooks.

- New module `ao_kernel/defaults/policies/policy_mcp_memory.v1.json`
  - Schema: `{read: {enabled: false, allowed_patterns: ["*"]}, write: {...}, rate_limit: {reads_per_minute: 60, writes_per_minute: 10}}`
  - Read default **disabled** (fail-closed)
- `handle_memory_read(params)` in `mcp_server.py`
  - `ToolSpec(allowed=True)` (NOT `False` + bypass — gateway early-returns; CNS-010 iter-3 blocking-1)
  - Handler-level gate: load `policy_mcp_memory.v1.json` → check `read.enabled` → deny envelope if false
  - Param-aware workspace: `_resolve_workspace_for_call(params, fallback=_find_workspace_root)` (NEW helper — iter-3 blocking-2)
  - Delegate to `ao_kernel.context.query_memory`
  - B4 `_with_evidence` wrapper catches it automatically once wired
- Rate limit: global/workspace-bucket (iter-1 blocking-3: do NOT trust `params.client_id`)
- Tool registration + TOOL_DEFINITIONS entry in `mcp_server.py`
- Tests:
  - Read enabled=true → returns items
  - Read enabled=false → deny envelope
  - `workspace_root` param honored (param-aware resolver)
  - Rate limit triggers after N reads
  - Evidence trail captures read events

#### PR-C6b — Memory write MCP tool (~300 LOC)

Scope: `ao_memory_write` + write policy + reconciliation with existing implicit auto-promote.

- Extend `policy_mcp_memory.v1.json` write block:
  - `write: {enabled: false, allowed_key_prefixes: [], max_value_bytes: 4096, allowed_source_prefixes: ["mcp:"]}`
  - **NO** `min_confidence` field (caller-supplied confidence is untrusted — iter-3 Q9)
- `handle_memory_write(params)` in `mcp_server.py`
  - Write default **disabled** (fail-closed)
  - Handler-level gate: policy enabled + key prefix allowlist + value size + source prefix
  - Server-side fixed confidence (e.g. `confidence=0.75`, not caller-supplied)
  - Param-aware workspace
  - Routes through `canonical_store.promote_decision(..., expected_revision=None, allow_overwrite=True)` so CAS lock is honored
- **Implicit promote migration** (iter-3 warning-4):
  - Current: `mcp_server.py:672-685` hardcoded 0.8 threshold in `call_tool`
  - Move threshold to **general MCP/tool** policy (NOT memory-specific), e.g. extend `policy_mcp_tool_calling.v1.json` with `implicit_canonical_promote: {enabled: true, threshold: 0.8, source_prefix: "mcp:tool_result"}`
  - Threshold remains hardcoded for now; the policy field exists so it can be made configurable without a schema migration
- Rate limit: writes_per_minute bucket
- Tests:
  - Write enabled + matching prefix → succeeds (via CAS)
  - Write disabled → deny envelope
  - Oversized value → deny
  - Bad source prefix → deny
  - Implicit promote still works after refactor
  - Concurrent writes serialize through CAS lock

#### PR-C1 (parallel, can interleave with C6) — `_internal` mypy strict

Scope: remove `ignore_errors=true` overrides from `pyproject.toml` per module. Codex's suggested order (iter-2):

1. `_internal/providers/*` (smallest, fastest wins)
2. `_internal/shared/*`
3. `_internal/secrets/*` (already mostly typed)
4. `_internal/evidence/*`
5. `_internal/session/*` (context_store 610 LOC; hardest)
6. `_internal/orchestrator/*`
7. `_internal/prj_kernel_api/*` (15 files, 3 × 200+ LOC — LAST)

One batch per PR keeps diffs reviewable. No new tests; the gate is `mypy ao_kernel/ --strict`.

#### PR-C2/C3/C4 — Coverage batch

- `_internal/session/context_store.py` 51% → 85% (compaction edges, prune_expired race)
- `_internal/evidence/writer.py` 28% → 85% (run_dir flow, write_node_log, write_provenance, integrity_manifest)
- `ao_kernel/workspace.py` 46% → 85% (find_root edges, init/doctor/migrate wiring)

Ratchet coverage gate: 70 → 75 (after PR-C2) → 80 (after PR-C3) → 85 (after PR-C4).

#### PR-C7a — Manifest hygiene

- Fix the three known duplicate `kernel_api_actions` (`intake_create_plan` / `intake_next` / `intake_status` on PRJ-KERNEL-API vs PRJ-WORK-INTAKE)
- Resolve `PRJ-ZANZIBAR-OPENFGA` schema drift (additionalProperties violations surfaced in B3)
- Audit manifest `ai_context_refs` / `docs_ref` / `tests_entrypoints` — remove stale paths
- Test: `ExtensionRegistry.find_conflicts()` returns empty on bundled set

#### PR-C7b — Handler backfill (opportunistic)

Not blocking the release. Handlers land as their extensions' code
becomes real. Priority per CNS-010 iter-1 Q6:
1. `PRJ-AIRUNNER` (customer-facing agent runtime)
2. `PRJ-KERNEL-API` (`system_status`, `intake_*`)
3. `PRJ-DEPLOY` (release automation)

#### PR-C8 — CLI concurrency tests

- `ao-kernel doctor` from a sub-directory (uses `project_root()`)
- `ao-kernel init` + `ao-kernel migrate --dry-run` happy paths
- Parallel client + MCP write scenarios (lock contention)

#### Release v3.0.0

- CHANGELOG.md [3.0.0] entry covering all C0-C8 breaking + additive changes
- `ao_kernel/__init__.py` + `pyproject.toml` version → `3.0.0`
- `pyproject.toml` classifier `Operating System :: POSIX` (reflect actual support)
- Tag `v3.0.0` → PyPI publish (automatic via GitHub Actions trusted publishing)
- GitHub release notes

---

## Quick-start for Next Session

### 1. Verify state
```bash
git log -1 --format="%h %s"           # 7afed04 or newer — PR-C5b merge
git status --short                     # empty
python3 -m pytest --co -q | tail -1    # 922 tests
mypy ao_kernel/ 2>&1 | tail -1         # Success
ruff check ao_kernel/ tests/           # All checks passed
gh pr list --state merged --limit 3    # #68, #67, #66
```

### 2. Open PR-C6a
```bash
git fetch origin main --quiet
git checkout -b claude/tranche-c-c6a origin/main
# Implement per scope above
```

### 3. After PR-C6a merged, repeat for C6b → C1 batches → C2/C3/C4 → C7 → C8 → release

---

## Key Files / Invariants (do not regress)

- `ao_kernel/_internal/shared/lock.py::file_lock` — POSIX-only, fail-closed on Windows. **Do not add a no-op Windows fallback.**
- `ao_kernel/context/canonical_store.py::_mutate_with_cas` — every new mutator goes through here.
- `ao_kernel/errors.py::CanonicalStoreCorruptedError` — raised, never caught-and-defaulted.
- `ao_kernel/workspace.py::project_root()` — project root = directory containing `.ao/`, NOT `.ao` itself.
- `ToolSpec.allowed=True` + handler-level policy gate — bypass pattern (`allowed=False` + handler) DOES NOT WORK (authorize early-returns; regression test in #67 tests).

---

## Adversarial Consensus Track Record (Tranche B + C so far)

| CNS | Verdict | Blocking | Warning | Claude revisions |
|---|---|---|---|---|
| 007 (B1) | PARTIAL | 4 | 3 | 1 |
| 008 (B3) | DISAGREE | 5 | 1 | 1 |
| 009 (B5) | DISAGREE | 3 | 3 | 1 |
| **010 (C-master)** | PARTIAL (3 iter) | **10** | **7** | **3** |
| **Total** | — | **22** | **14** | **6** |

Claude's first thesis: **0/6 survived untouched**. The "grep before
accepting" rule (project memory) triggered every time.

---

## Technical Debt (acknowledged, not in Tranche C)

| Debt | Where | Who/When |
|---|---|---|
| Windows FS lock support | `lock.py::file_lock` raises | Tranche D (v3.1.0) |
| CLAUDE.md §3 contract language update | — | Release v3.0.0 docs pass |
| `policy_mcp_memory.v1.json` schema validation | new file coming in C6a | Added in C6a |

---

**Session closed cleanly. Next agent opens PR-C6a and keeps going — no blockers, no ambiguity.**
