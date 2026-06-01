# RI-7.4 — Scan/Index/Query Packaging Smoke

**Status:** recorded / evidence slice
**Date:** 2026-05-26
**Parent:** `RI-7-REPO-INTELLIGENCE-TIER-PROMOTION-READINESS.md`
**Support impact:** none
**Production platform claim:** false
**Support widening:** false
**Live adapter execution:** false
**Exit decision:** `ri7_scan_index_query_packaging_smoke_ready`

## 1. Purpose

RI-7.4 closes the readiness gate's `scan_index_query_packaging_smoke_missing`
blocking row by providing **packaged-CLI scan/index/query** smoke evidence
covering happy-path execution and fail-closed missing-backend / missing-key
paths.

Evidence-only slice. No flag flip; no public SDK signature change; no MCP
exposure; no context-compiler auto-feed; no root-authority write change; no
branch protection or workflow mutation; no `gpp_status.v1.json` mutation.

## 2. Smoke Surface

The readiness-gate row "wheel-installed scan/index/query smoke passes outside
the source checkout with fail-closed missing-backend paths" is satisfied by
a single extended smoke script that runs `repo scan / index / query` against
a throwaway project from a wheel-installed Python interpreter and an
outside-source-checkout `cwd`:

`scripts/packaging_smoke.py` is extended with `_smoke_repo_intelligence_cli`,
which executes after the existing entry-point and demo-review smokes. The
extended flow:

1. The script builds sdist + wheel from the checkout, creates a fresh
   virtualenv in a `tempfile.TemporaryDirectory`, and installs the built
   wheel **only** (no editable install).
2. After the existing entry-point + demo-review smokes, it creates a
   throwaway `ri7-smoke-project` inside the same outside-source `cwd`.
3. It drives six subprocess scenarios using **the venv's Python**
   (`{venv_python} -m ao_kernel ...`), not the source-checkout interpreter,
   so the smoke proves the wheel-installed surface is reachable.
4. Each scenario asserts the documented exit code + stderr contract, and a
   schema-valid JSON evidence artifact
   (`build/packaging-smoke/ri7-packaging-smoke-evidence.v1.json`) is written for downstream
   review.

A supplementary in-process subprocess test
(`tests/test_ri7_scan_index_query_packaging_smoke.py`) drives the same six
scenarios using the current pytest interpreter so the contract is also
pinned in the unit test surface — this layer is supplementary and does not
replace the wheel-installed evidence above.

The six scenarios prove the documented fail-closed paths. Each scenario
sets a deterministic env shape so the CLI rejects on a specific
prerequisite branch; query scenarios assert the CLI's documented
prerequisite-missing contract (manifest-missing **or** backend-missing
**or** API-key-missing) because the CLI checks the vector index manifest
first and the smoke does not over-claim that any single branch is reached:

   - `repo scan` on a tiny temp repo produces a schema-valid repo map.
   - `repo index --write-vectors --confirm-vector-index <token>` with a
     dummy API key set and `AO_KERNEL_VECTOR_BACKEND=disabled` rejects on
     the **backend** branch with stderr matching
     `repo index --write-vectors requires a configured vector backend`.
   - `repo query --query <text>` with a dummy API key set and
     `AO_KERNEL_VECTOR_BACKEND=disabled` rejects on the CLI's
     prerequisite-missing contract (manifest or backend message,
     depending on ordering).
   - `repo index --write-vectors` with `AO_KERNEL_VECTOR_BACKEND=inmemory`
     and every provider/embedding env scrubbed rejects on the **API-key**
     branch with stderr matching the documented API-key fail-closed
     message.
   - `repo query` with `AO_KERNEL_VECTOR_BACKEND=inmemory` and every
     provider/embedding env scrubbed rejects on the CLI's
     prerequisite-missing contract (any of API-key-missing,
     manifest-missing, or configured-vector-backend, depending on which
     prerequisite the CLI checks first).

The wheel-installed smoke and the supplementary in-process subprocess
test together cover the readiness-gate row description:
"wheel-installed scan/index/query smoke passes outside the source checkout
with fail-closed missing-backend paths".

## 3. Backend / API key envelope

The RI-7.4 fail-closed smoke uses a deterministic minimal env. Only a
PATH/HOME/TMPDIR-style host allowlist is inherited from the parent shell;
every provider/embedding env (`OPENAI_API_KEY`, `AO_KERNEL_OPENAI_API_KEY`,
`AO_KERNEL_EMBEDDING_API_KEY`, `AO_KERNEL_EMBEDDING_PROVIDER`,
`AO_KERNEL_EMBEDDING_MODEL`, `AO_KERNEL_EMBEDDING_BASE_URL`,
`GOOGLE_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`,
`XAI_API_KEY`, `QWEN_API_KEY`) is explicitly scrubbed. Each scenario then
sets a per-scenario envelope:

- Backend-isolation scenarios: dummy `OPENAI_API_KEY=ri7-wheel-smoke-key`
  with `AO_KERNEL_VECTOR_BACKEND=disabled` so the CLI reaches and rejects
  on the backend branch.
- API-key-isolation scenarios: `AO_KERNEL_VECTOR_BACKEND=inmemory` with
  no embedding API key so the CLI reaches and rejects on the API-key
  branch (or, for query, on an earlier prerequisite as documented above).

The smoke must observe the documented error contract and a non-zero exit
code; it must not contact any external service.

## 4. Evidence Artifact

`.claude/plans/RI-7.4-SCAN-INDEX-QUERY-PACKAGING-SMOKE.v1.json` records
the result, validated against
`ao_kernel/defaults/schemas/ri7-scan-index-query-packaging-smoke-evidence.schema.v1.json`.

Required fields:

- `artifact_kind`: `ri7_scan_index_query_packaging_smoke_evidence`
- `decision`: `ri7_scan_index_query_packaging_smoke_ready`
- `support_widening` / `production_platform_claim` / `live_adapter_execution`: `false`
- `entrypoint`: `{module: "ao_kernel", invocation: "python -m ao_kernel"}`
- `scenarios`: one entry per row in the matrix below, with `status` and
  `evidence_ref` pointing to a test function.

## 5. Scenario Matrix

| ID | Surface | Evidence |
|---|---|---|
| `entrypoint_help_exits_zero` | `python -m ao_kernel --help` | exit 0; help text observed |
| `repo_scan_writes_schema_valid_repo_map` | `python -m ao_kernel repo scan` | exit 0; repo_map artifact produced |
| `repo_index_write_vectors_fails_closed_without_backend` | `python -m ao_kernel repo index --write-vectors --confirm-vector-index <token>` | exit 1; stderr matches `requires a configured vector backend` |
| `repo_query_fails_closed_without_manifest_or_backend` | `python -m ao_kernel repo query --query <text>` with backend disabled and no vector manifest | exit 1; stderr matches the CLI's documented prerequisite-missing contract (manifest-missing or configured-vector-backend message; the CLI checks manifest first) |
| `repo_index_write_vectors_fails_closed_without_api_key` | `python -m ao_kernel repo index --write-vectors --confirm-vector-index <token>` with cleared embedding env | exit 1; stderr matches the documented API-key fail-closed message |
| `repo_query_fails_closed_without_api_key` | `python -m ao_kernel repo query --query <text>` with `AO_KERNEL_VECTOR_BACKEND=inmemory` and every provider/embedding env scrubbed | exit 1; stderr matches the CLI's documented prerequisite-missing contract (any of API-key-missing / manifest-missing / configured-vector-backend, depending on which prerequisite the CLI checks first) |

## 6. Forbidden-Change Audit (this slice)

| Surface | Status |
|---|---|
| `.claude/plans/gpp_status.v1.json` | unchanged; guard flags remain false |
| `scripts/gp5_platform_claim_decision.py` | unchanged |
| `.github/workflows/` | unchanged |
| `scripts/packaging_smoke.py` | **extended** with `_smoke_repo_intelligence_cli` — additive new function appended after the existing entry-point/demo smokes; no removal or behavioral change to the pre-existing surface |
| `ao_kernel/cli.py` | unchanged (smoke observes existing fail-closed CLI paths) |
| `ao_kernel/__init__.py` and public SDK signatures | unchanged |
| `ao_kernel/mcp_server.py` and MCP tool dispatch | unchanged; no repo-intelligence tool exposed |
| `ao_kernel/defaults/policies/` | unchanged |
| `docs/PUBLIC-BETA.md`, `docs/SUPPORT-BOUNDARY.md`, `docs/KNOWN-BUGS.md` | unchanged (RI-7.7 owner) |
| Branch protection / ruleset | unchanged |

## 7. Acceptance

RI-7.4 is complete when:

1. ✅ This plan doc exists and records the six scenarios.
2. ✅ Schema `ri7-scan-index-query-packaging-smoke-evidence.schema.v1.json`
   exists and the artifact passes Draft202012Validator.
3. ✅ `.claude/plans/RI-7.4-SCAN-INDEX-QUERY-PACKAGING-SMOKE.v1.json` records
   all six scenarios with `status=pass`.
4. ✅ `tests/test_ri7_scan_index_query_packaging_smoke.py` passes; each
   subprocess assertion observes the documented exit code + stderr
   contract.
5. ✅ Doc invariant test pins this plan, six scenarios, exit decision,
   forbidden-change audit, and schema/artifact binding.
6. ✅ Readiness gate continues to report
   `blocked_operator_bound_evidence_required` and three guard flags `false`;
   running the gate with a manifest that flips
   `scan_index_query_packaging_smoke=true` drops that specific blocker
   while remaining RI-7 blockers stay.
7. ✅ Forbidden-change audit clean (Section 6).
8. ✅ PR exit decision: `ri7_scan_index_query_packaging_smoke_ready`.

## 8. Exit Decision

`ri7_scan_index_query_packaging_smoke_ready` — RI-7.4 records packaged-CLI
scan/index/query smoke evidence covering six scenarios. **No support
widening. No production platform claim. No live adapter execution.
Repo-intelligence remains Beta/experimental pending RI-7.1 operator
authorization and the later RI-7.8 promotion decision PR.**
