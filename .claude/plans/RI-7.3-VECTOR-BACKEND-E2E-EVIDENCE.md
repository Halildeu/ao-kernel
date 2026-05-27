# RI-7.3 — Configured Vector Backend E2E Evidence

**Status:** recorded / evidence slice
**Date:** 2026-05-26
**Parent:** `RI-7-REPO-INTELLIGENCE-TIER-PROMOTION-READINESS.md`
**Support impact:** none
**Production platform claim:** false
**Support widening:** false
**Live adapter execution:** false
**Exit decision:** `ri7_vector_backend_e2e_ready`

## 1. Purpose

RI-7.3 closes the readiness gate's `vector_backend_e2e_evidence_missing`
blocking row by providing **configured local vector backend** end-to-end
evidence for the repo-intelligence index/query surface.

This slice is **evidence-only**. It does not:

- enable a live adapter execution (no external API call; deterministic fake
  embedding function is used);
- promote the repo-intelligence tier (Beta/experimental remains);
- mutate `gpp_status.v1.json`, `scripts/gp5_platform_claim_decision.py`,
  `.github/workflows/`, branch protection, or public SDK signatures;
- expose repo-intelligence via MCP or enable a context-compiler auto-feed.

The readiness gate continues to report
`blocked_operator_bound_evidence_required` with
`support_widening=false`, `production_platform_claim=false`, and
`live_adapter_execution=false`.

## 2. Backend Choice

The configured backend used for E2E evidence is the repo-owned
`ao_kernel.context.vector_store.InMemoryVectorStore` (pure-Python, in-process).
This backend is selected because:

- It is a real production-resolver backend. The production resolver
  `ao_kernel.context.vector_store_resolver.resolve_vector_store` returns
  an `InMemoryVectorStore` instance when `AO_KERNEL_VECTOR_BACKEND=inmemory`;
  this slice's E2E test suite pins both the resolver-path selection and the
  direct-construct path so the configured-backend claim is bound to the
  production resolver, not only to a direct class import.
- It is deterministic and does not require any external service or secret.
- It makes the **no live adapter execution** invariant trivial: a fake
  embedding callable is injected; no provider HTTP call occurs.

Pgvector and SQLite backends are explicitly **out of scope** for RI-7.3:
pgvector regression already pins namespace/model/dimension guard contracts
with a mocked DB layer; SQLite is not a current repo backend and adding one
would be unrelated production surface.

## 3. Scenario Matrix

| Scenario | Surface | Evidence |
|---|---|---|
| `write_happy_path` | `write_repo_vectors` + `InMemoryVectorStore` | Schema-valid `vector_index_manifest`; indexed keys live under the project's vector namespace prefix; metadata fields complete |
| `stale_cleanup` | `write_repo_vectors` re-run with previous manifest | Stale key deleted **before** new upserts; deleted_keys reflects only entries under the project's embedding-space namespace |
| `namespace_isolation` | `query_repo_vectors` | Non-repo namespace candidates and bad-metadata candidates excluded from results; `filtered_candidates` records exclusion reasons |
| `query_hash_line_validation` | `query_repo_vectors` after source mutation | Stale source candidates produce a `stale_source` diagnostic and do not surface stale content in `results` |
| `missing_backend_fail_closed_write` | `write_repo_vectors(vector_store=None)` | `ValueError` (no upsert, no embedding call) |
| `missing_backend_fail_closed_query` | `query_repo_vectors(vector_store=None)` | `ValueError` (no embedding call) |
| `missing_api_key_fail_closed_write` | `write_repo_vectors` with `resolve_api_key() -> None` | `ValueError` (no upsert, no embedding call) |
| `missing_api_key_fail_closed_query` | `query_repo_vectors` with `resolve_api_key() -> None` | `ValueError` (no embedding call) |

## 4. Evidence Artifact

A passing run records its outcome in
`.claude/plans/RI-7.3-VECTOR-BACKEND-E2E-EVIDENCE.v1.json`, validated against
`ao_kernel/defaults/schemas/ri7-vector-backend-e2e-evidence.schema.v1.json`.

In addition, this slice introduces the gate-consumable RI-7 evidence manifest
`.claude/plans/RI-7-EVIDENCE-MANIFEST.v1.json` with
`vector_backend_e2e_evidence=true` and every other RI-7.x key still `false`.
Running

```bash
python3 scripts/repo_intelligence_tier_promotion_readiness.py \
  --evidence-manifest .claude/plans/RI-7-EVIDENCE-MANIFEST.v1.json --output json
```

confirms the `vector_backend_e2e_evidence_missing` blocker drops while the
remaining RI-7 blockers (operator authorization, guardrail hardening matrix,
packaging smoke, operator runtime semantics, cross-lane matrix, GP-5.9
reclassification, support-boundary transition) stay.

The artifact MUST include:

- `artifact_kind`: `ri7_vector_backend_e2e_evidence`
- `decision`: `ri7_vector_backend_e2e_ready`
- `backend`: `{type: "inmemory", class_name: "InMemoryVectorStore", external_api_calls: false}`
- `support_widening`: `false`
- `production_platform_claim`: `false`
- `live_adapter_execution`: `false`
- `scenarios`: one entry per row in the matrix above, with `status` and
  `evidence_ref` (test function name)

## 5. Test Refs

The single canonical E2E test file is
`tests/test_ri7_vector_backend_e2e.py`. It encodes each scenario as a
dedicated test function so reviewers can map matrix rows to test runs
one-to-one.

Additional fail-closed regressions for the **direct** call surface (not just
the CLI surface) live alongside the existing focused tests:

- `tests/test_repo_intelligence_vector_indexer.py::test_write_repo_vectors_fails_closed_when_vector_store_is_none`
- `tests/test_repo_intelligence_vector_retriever.py::test_query_repo_vectors_fails_closed_when_vector_store_is_none`
- `tests/test_repo_intelligence_vector_indexer.py::test_write_repo_vectors_treats_none_api_key_as_missing`

The doc invariant test
`tests/test_ri7_vector_backend_e2e_evidence_invariant.py` pins this plan
doc's existence, the eight scenarios, the exit decision, and the evidence
artifact / schema bindings.

## 6. Forbidden-Change Audit (this slice)

| Surface | Status |
|---|---|
| `gpp_status.v1.json` | unchanged; guard flags remain false |
| `scripts/gp5_platform_claim_decision.py` | unchanged |
| `.github/workflows/` | unchanged |
| `ao_kernel/__init__.py` and public SDK signatures | unchanged |
| `ao_kernel/mcp_server.py` and MCP tool dispatch | unchanged; no repo-intelligence tool exposed |
| `ao_kernel/context/vector_store.py` and resolver | unchanged in this slice |
| `docs/PUBLIC-BETA.md`, `docs/SUPPORT-BOUNDARY.md`, `docs/KNOWN-BUGS.md` | unchanged in this slice (RI-7.7 owns transition text) |
| Branch protection / ruleset | unchanged |

## 7. Acceptance

RI-7.3 is complete when:

1. ✅ This plan doc exists and records the eight scenarios + matrix.
2. ✅ Schema `ri7-vector-backend-e2e-evidence.schema.v1.json` exists and the
   artifact passes Draft202012Validator.
3. ✅ Evidence artifact `.claude/plans/RI-7.3-VECTOR-BACKEND-E2E-EVIDENCE.v1.json`
   exists, validates against the schema, records all eight scenarios with
   `status=pass`, and pins the closed boundary flags.
4. ✅ `tests/test_ri7_vector_backend_e2e.py` passes with the configured
   `InMemoryVectorStore` backend covering all eight scenarios.
5. ✅ Direct missing-backend / missing-key regressions added to the focused
   indexer / retriever test files (CLI-only coverage strengthened to
   function-level pins).
6. ✅ Doc invariant test pins this plan doc, the scenario list, the exit
   decision, and the schema/artifact binding.
7. ✅ Readiness gate continues to report
   `blocked_operator_bound_evidence_required` and three guard flags `false`.
8. ✅ Forbidden-change audit clean (Section 6).
9. ✅ PR exit decision: `ri7_vector_backend_e2e_ready`.

## 8. Exit Decision

`ri7_vector_backend_e2e_ready` — RI-7.3 records configured local vector
backend E2E evidence covering eight scenarios. **No support widening. No
production platform claim. No live adapter execution. Repo-intelligence
remains Beta/experimental pending RI-7.1 operator authorization and the
later RI-7.8 promotion decision PR.**
