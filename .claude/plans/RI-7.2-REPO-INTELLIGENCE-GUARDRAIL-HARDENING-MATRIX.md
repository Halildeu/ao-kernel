# RI-7.2 — Repo-Intelligence Guardrail Hardening Matrix

**Status:** recorded / hardening evidence slice — docs + targeted regression tests + one private-impl path-escape fix
**Date:** 2026-05-26
**Parent:** `RI-7-REPO-INTELLIGENCE-TIER-PROMOTION-READINESS.md`
**Support impact:** none
**Production platform claim:** false
**Support widening:** false
**Live adapter execution:** false
**Exit decision:** `ri7_guardrail_hardening_matrix_ready`

## 1. Purpose

RI-7.2 closes the repo-intelligence **guardrail hardening matrix** required by
the `repo_intelligence_tier_promotion_readiness` gate's
`guardrail_hardening_matrix` blocking row.

This slice is **evidence-only**. It does not flip any GPP guard flag, change
public SDK signatures, expose repo-intelligence via MCP, enable a
context-compiler auto-feed, alter `.github/workflows/`, mutate
`gpp_status.v1.json`, or change `scripts/gp5_platform_claim_decision.py`. The
readiness gate continues to report:

- `support_widening=false`
- `production_platform_claim=false`
- `live_adapter_execution=false`
- `decision=blocked_operator_bound_evidence_required` (remaining RI-7.1, 7.3,
  7.4, 7.5, 7.6, 7.7 evidence still missing)

## 2. Authority Boundary

GPP-9 is closed under:

```
gpp9_keep_narrow_stable_runtime_authoritative_program_closed_no_live_adapter_execution_no_support_widening_no_production_claim
```

RI-7.2 does **not** grant a general-purpose production platform claim. The
later promotion decision (RI-7.8) must consume passing manifests for RI-7.1
through RI-7.7. Repo-intelligence remains Beta/experimental per
`docs/PUBLIC-BETA.md` and `docs/SUPPORT-BOUNDARY.md`.

## 3. Guardrail Matrix

Each row records: current implementation references, regression-test
references, residual gap (if any), and the next slice that owns the gap.

### 3.1 AST / chunk edge cases

| Field | Value |
|---|---|
| **Status** | hardened |
| **Implementation refs** | `ao_kernel/_internal/repo_intelligence/python_ast_indexer.py` (deterministic AST build, syntax-error diagnostic, RI-7.2 path-escape guard via `_resolve_under_root`), `ao_kernel/_internal/repo_intelligence/repo_chunker.py` (`_resolve_under_root`, symlink skip, syntax-error fallback, secret-like / oversized / disabled-language skips) |
| **Regression refs** | `tests/test_repo_intelligence_python_ast_indexer.py::test_build_python_ast_indexes_are_schema_valid_and_deterministic`, `::test_build_python_ast_indexes_record_syntax_errors_without_failing_scan`, `::test_build_python_ast_indexes_skips_repo_map_path_escape_without_reading_outside_root` (RI-7.2), `tests/test_repo_intelligence_chunker.py` (chunk boundaries, secret-like skip, path-escape diagnostic) |
| **Residual gap** | None blocking RI-7.2. Behavioral guard for AST indexer path escape was introduced in this slice (private impl change with no public SDK signature change). |
| **Next slice owner** | RI-7.3 covers configured vector backend behavior; RI-7.4 covers wheel-installed surface; both depend on this slice's manifest determinism. |

### 3.2 Namespace isolation

| Field | Value |
|---|---|
| **Status** | hardened |
| **Implementation refs** | `ao_kernel/_internal/repo_intelligence/repo_vector_plan.py` (vector namespace identity), `ao_kernel/_internal/repo_intelligence/repo_vector_indexer.py` (`_require_namespace_key` enforced on **both** planned_upserts and planned_deletes), `ao_kernel/_internal/repo_intelligence/repo_vector_retriever.py` (query namespace + metadata match) |
| **Regression refs** | `tests/test_repo_intelligence_vector_indexer.py::test_write_repo_vectors_fails_closed_on_key_outside_namespace`, `::test_write_repo_vectors_rejects_delete_key_outside_namespace_without_mutation` (RI-7.2), `tests/test_repo_intelligence_vector_retriever.py` (non-repo namespace + same-prefix metadata mismatch filtered), `tests/test_repo_intelligence_workflow_opt_in_contract.py` (handoff namespace mismatch blocked) |
| **Residual gap** | E2E backend behavior for namespace isolation is a vector-backend lane concern owned by RI-7.3. |
| **Next slice owner** | RI-7.3 |

### 3.3 Stale vector cleanup

| Field | Value |
|---|---|
| **Status** | hardened |
| **Implementation refs** | `ao_kernel/_internal/repo_intelligence/repo_vector_plan.py` (stale deletes planned from previous-manifest delta), `ao_kernel/_internal/repo_intelligence/repo_vector_indexer.py` (deletes before upserts; no mutation on preflight failure), `ao_kernel/_internal/repo_intelligence/repo_vector_retriever.py` (stale source candidates excluded) |
| **Regression refs** | `tests/test_repo_intelligence_vector_plan.py` (stale delete planning, previous-manifest namespace requirement), `tests/test_repo_intelligence_vector_indexer.py::test_write_repo_vectors_deletes_stale_keys_before_upserts`, `::test_write_repo_vectors_does_not_mutate_store_when_preflight_fails`, `tests/test_repo_intelligence_vector_retriever.py` (path escape + stale source chunks excluded) |
| **Residual gap** | E2E backend write+delete sequencing is owned by RI-7.3. |
| **Next slice owner** | RI-7.3 |

### 3.4 No implicit / unconfirmed root authority write

| Field | Value |
|---|---|
| **Status** | hardened |
| **Implementation refs** | `ao_kernel/_internal/repo_intelligence/root_exporter.py` (`RepoRootExportError` raised on any preflight / schema / path-ownership failure; explicit create-only boundary; exact confirmation token required; rollback/release on failure), `ao_kernel/_internal/repo_intelligence/workflow_context.py` (resolved RI context pointer-metadata only; `root_export=false`), `ao_kernel/_internal/repo_intelligence/workflow_opt_in.py` (visible handoff, no implicit feed) |
| **Regression refs** | `tests/test_repo_intelligence_root_exporter.py` (failure paths leave root files untouched), `tests/test_cli_repo_export.py` (missing-confirmation / conflict fail without root write), `tests/test_repo_intelligence_workflow_opt_in_contract.py`, `tests/test_repo_intelligence_workflow_context.py` (runtime handoff `root_export=false`) |
| **Wording** | The guardrail is **no implicit/unconfirmed root authority write** in scan/index/query/workflow handoff. The pre-existing RI-5b explicit root export remains create-only and out of this promotion. |
| **Residual gap** | None blocking RI-7.2. Operator-verified runtime semantics in production environment owned by RI-7.5 (operator sign-off). |
| **Next slice owner** | RI-7.5 |

### 3.5 No auto-feed (no hidden context compiler injection)

| Field | Value |
|---|---|
| **Status** | hardened |
| **Implementation refs** | `ao_kernel/_internal/repo_intelligence/workflow_opt_in.py` (visible handoff, no injection/feed), `ao_kernel/_internal/repo_intelligence/workflow_context.py` (`context_compiler_auto_feed=false`; pointer metadata only; preamble does not auto-ingest), `scripts/gpp5_repo_intelligence_closeout.py` (no hidden context render check) |
| **Regression refs** | `tests/test_context_compiler.py` (compile_context signatures and session payload do not auto-ingest repo intelligence), `tests/test_repo_intelligence_workflow_context.py` (resolved RI context not compiled into preamble), `tests/test_repo_intelligence_workflow_opt_in_contract.py` (handoff opt-in is explicit) |
| **Residual gap** | None. The matrix invariant test (Section 6) re-pins this contract; any future auto-feed regression would also fail the existing `test_context_compiler.py` and `test_repo_intelligence_workflow_context.py` shapes. |
| **Next slice owner** | RI-7.5 owns operator-verified runtime sign-off for this guardrail. |

### 3.6 No MCP exposure

| Field | Value |
|---|---|
| **Status** | hardened |
| **Implementation refs** | `ao_kernel/mcp_server.py` (no `repo_intelligence` / `repo_scan` / `repo_index` / `repo_query` tool registered), `scripts/gpp5_repo_intelligence_closeout.py` (MCP surface guard) |
| **Regression refs** | `tests/test_repo_intelligence_no_mcp_root_export_guard.py::test_repo_intelligence_is_not_exposed_as_mcp_tool`, `::test_repo_intelligence_is_not_registered_in_mcp_tool_gateway`, `::test_repo_cli_has_no_root_export_or_mcp_subcommand`, `::test_repo_cli_help_does_not_advertise_root_export_or_mcp_flags` |
| **Residual gap** | None. Any future MCP tool registration touching repo-intelligence names would fail this guard. |
| **Next slice owner** | RI-7.5 owns operator-verified runtime sign-off. |

## 4. RI-7.2 Behavioral Change

This slice adds **one** behavioral guard in private repo-intelligence code:

- `ao_kernel/_internal/repo_intelligence/python_ast_indexer.py`:
  - New `_resolve_under_root(root, rel_path)` helper mirroring the chunker
    pattern.
  - `build_python_ast_indexes` now skips and records
    `python_path_escape_skipped` diagnostic when a `repo_map` candidate path
    resolves outside the project root, instead of naively reading
    `root / rel_path`.
  - Modules list now excludes escaped paths so import_graph and symbol_index
    summaries reflect only paths under the project root.

No public SDK surface, no facade signature, no schema, and no workflow file
was changed.

## 5. Forbidden-Change Audit (this slice)

The following are explicitly **unchanged** in this slice:

| Surface | Status |
|---|---|
| `.claude/plans/gpp_status.v1.json` | unchanged; guard flags remain false |
| `scripts/gp5_platform_claim_decision.py` | unchanged |
| `.github/workflows/` | unchanged |
| `ao_kernel/__init__.py` and public SDK signatures | unchanged |
| `ao_kernel/mcp_server.py` and MCP tool dispatch | unchanged; no repo-intelligence tool exposed |
| `docs/PUBLIC-BETA.md`, `docs/SUPPORT-BOUNDARY.md`, `docs/KNOWN-BUGS.md` | unchanged in this slice (RI-7.7 owns the transition text) |
| `ao_kernel/defaults/schemas/*` | unchanged |
| Branch protection / ruleset | unchanged |

## 6. Acceptance Criteria

RI-7.2 is complete when:

1. ✅ This matrix document exists with the six guardrail rows recording
   implementation refs, regression refs, residual gap, and the next-slice
   owner.
2. ✅ The two RI-7.2 regression tests exist and pass:
   - `tests/test_repo_intelligence_python_ast_indexer.py::test_build_python_ast_indexes_skips_repo_map_path_escape_without_reading_outside_root`
   - `tests/test_repo_intelligence_vector_indexer.py::test_write_repo_vectors_rejects_delete_key_outside_namespace_without_mutation`
3. ✅ Targeted repo-intelligence test set still passes (vector indexer, vector
   plan, vector retriever, chunker, AST indexer, workflow opt-in, workflow
   context, no-MCP guard, root exporter, tier promotion readiness).
4. ✅ Readiness gate continues to report `blocked_operator_bound_evidence_required`
   and three guard flags `false`.
5. ✅ Doc invariant test pins this matrix doc's existence, the six guardrail
   headings, and the exit decision string.
6. ✅ No support widening, production platform claim, live adapter execution,
   branch-protection mutation, workflow change, or public SDK signature change.

## 7. Exit Decision

`ri7_guardrail_hardening_matrix_ready` — RI-7.2 records the hardening
inventory and the two missing regression pins required by the readiness
matrix. **No support widening. No production platform claim. No live adapter
execution. Repo-intelligence remains Beta/experimental pending RI-7.1
operator authorization and the later RI-7.8 promotion decision PR.**
