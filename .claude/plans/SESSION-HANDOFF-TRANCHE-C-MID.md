# Tranche C — Late-Session Handoff (2026-04-14)

## TL;DR

**Tranche C is in progress.** CNS-20260414-010 (plan level) and
CNS-20260414-011 (PR-C6a implementation level) both closed with
`ready_for_impl: true` after 3 iterations each. **Four PRs merged**
into main: C0, C5a, C5b, **C6a** (#70, `c3fedd1`). Test baseline
**935/935 green**. Four more PRs + coverage + release remain.
Everything is unblocked — the next session can open `PR-C6b`
against `origin/main` and keep going.

Previous handoff (post v2.3.0): `SESSION-HANDOFF-2026-04-14-v2.md`.
This doc covers Tranche C progress since then — now extended past
C6a with CNS-011 deltas folded in.

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

### Merged so far (4 PRs)

| PR | Scope | Key deliverables |
|---|---|---|
| **#66** C0 | `workspace.project_root()` single source of truth | helper + cross-surface alignment (client / MCP / extension loader) + 8 tests |
| **#67** C5a | CAS mutators + FS lock + unique tmp + fail-closed load | `save_store_cas`, `_mutate_with_cas`, POSIX `file_lock`, `CanonicalStoreCorruptedError`, `CanonicalRevisionConflict` + 13 tests |
| **#68** C5b | `forget()` routes through CAS helper | bypass closed, matching CAS args + 5 tests |
| **#70** C6a | `ao_memory_read` MCP tool + policy + param-aware resolver | `_internal/mcp/memory_tools.py`, `policy_mcp_memory.v1.json` + schema, batch docs update, 13 tests — see CNS-011 consensus |

**Main HEAD after PR-C6a:** `c3fedd1`, test suite **935/935 green**.

### Still open (4 PRs + release)

Order and scope below. Each assumes branch from latest `origin/main`,
M2 merge pattern (protection approval=0 → merge → approval=1), CI 7/7 first try.

#### ✅ PR-C6a — Memory read MCP tool (MERGED #70, 2026-04-14)

**Status:** merged; tests 935/935 green. Implementation details below kept
for reference; actual deltas differ slightly from iter-1 sketch — see
`.ao/consultations/CNS-20260414-011.consensus.md` for the final plan and
`.claude/plans/PR-C6a-IMPLEMENTATION-PLAN.md` for the file-level layout.

Scope (merged): `ao_memory_read` MCP tool. Read-only, built on existing SDK hooks.

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

#### ✅ PR-C6b — Memory write MCP tool (landed in the same branch as C6a)

**Status:** Implementation shipped under CNS-20260414-012 (2-iter AGREE,
`ready_for_impl=true`). Consensus: `.ao/consultations/CNS-20260414-012.consensus.md`.
Implementation plan: `.claude/plans/PR-C6b-IMPLEMENTATION-PLAN.md`. Deltas
from the iter-1 sketch:
- `implicit_canonical_promote` block lives in `policy_tool_calling.v1.json`
  (mevcut family), not a new file
- `_IMPLICIT_PROMOTE_SKIP` extends to `{ao_memory_read, ao_memory_write}`
- Server-side fixed confidence = **0.8** (aligned with `promote_decision`
  default; caller-supplied value IGNORED — CNS-010 iter-3 Q9)
- Implicit-promote wiring extracted into
  `memory_tools.run_implicit_promote()` to keep `mcp_server.py` under the
  800-LOC budget

Original iter-1 scope text retained below for reference.

Scope: `ao_memory_write` + write policy + reconciliation with existing implicit auto-promote.

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
git log -1 --format="%h %s"           # c3fedd1 or newer — PR-C6a merge
git status --short                     # empty
python3 -m pytest --co -q | tail -1    # 935 tests
mypy ao_kernel/ 2>&1 | tail -1         # Success
ruff check ao_kernel/ tests/           # All checks passed
gh pr list --state merged --limit 4    # #70, #68, #67, #66
```

### 2. Open PR-C6b
```bash
git fetch origin main --quiet
git checkout -b claude/tranche-c-c6b origin/main
# Implement per C6b scope below. Extend existing
# policy_tool_calling.v1.json with implicit_canonical_promote
# block (NOT a new policy_mcp_tool_calling.v1.json file — repo
# family is policy_tool_calling.v1.json per CNS-011 iter-3 note 3).
```

### 3. After PR-C6b merged, repeat for C1 batches → C2/C3/C4 → C7 → C8 → release

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
| 010 (C-master plan) | PARTIAL→AGREE (3 iter) | 10 | 7 | 3 |
| **011 (C6a impl)** | PARTIAL→AGREE (3 iter) | **5** | **9** | **3** |
| **Total** | — | **27** | **23** | **9** |

Claude's first thesis: **0/9 survived untouched**. The "grep before
accepting" rule (project memory) triggered every time.

---

## Technical Debt (acknowledged, not in Tranche C)

| Debt | Where | Who/When |
|---|---|---|
| Windows FS lock support | `lock.py::file_lock` raises | Tranche D (v3.1.0) |
| CLAUDE.md §3 contract language update | — | Release v3.0.0 docs pass |
| `policy_mcp_memory.v1.json` schema validation | new file coming in C6a | ✅ Added in C6a (CNS-011) |
| MCP evidence SHA256 integrity manifest | `_internal/evidence/mcp_event_log.py` — JSONL+fsync only | Tranche D (v3.1.0+) — scope pivot from CNS-20260414-011 B3 |

---

**Session closed cleanly. Next agent opens PR-C6b and keeps going — no blockers, no ambiguity.**

---

## PR-C6a Post-Merge Reference (2026-04-14)

Final C6a consensus / implementation differs from iter-1 sketch at
four points; these are load-bearing for C6b:

1. **`_resolve_workspace_for_call` fallback = key-absent only.**
   Present-but-invalid → explicit deny (no silent CWD fallback). Scope:
   memory tools + `_with_evidence` + `call_tool` implicit promote only —
   NOT broadcast to the pre-existing governance tools (CNS-011 iter-3 W1).
2. **`_IMPLICIT_PROMOTE_SKIP` is a `mcp_server.call_tool()`-local denylist.**
   Shared `decision_extractor.py` is UNCHANGED to avoid regressing the
   `llm.py` tool-results path (`test_memory_pipeline.py:121-132` locks
   the existing extraction behaviour).
3. **MCP evidence = JSONL append + fsync only.** No SHA256 manifest.
   The manifest machinery is reserved for workspace artefacts; the
   MCP manifest is deferred to Tranche D. `CLAUDE.md` §2 and
   `mcp_event_log.py` docstring reflect this.
4. **`_internal/mcp/memory_tools.py`** is a private sub-module. C6b's
   `handle_memory_write` lands in the same file so `mcp_server.py` stays
   under the 800-LOC budget (CLAUDE.md §12).

For C6b, the implicit-promote hardcoded threshold currently lives at
`mcp_server.py:668-685`. Surface decision from CNS-010 iter-3 warning-4
still stands: move the threshold into the **general**
`policy_tool_calling.v1.json` (**NOT** a new `policy_mcp_tool_calling`
file — repo family is `policy_tool_calling.v1.json`; iter-3 note 3)
as an `implicit_canonical_promote` block. `ao_memory_write` itself
lives alongside `handle_memory_read` in `_internal/mcp/memory_tools.py`.
