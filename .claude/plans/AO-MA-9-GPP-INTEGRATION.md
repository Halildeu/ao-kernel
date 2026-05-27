# AO-MA-9 — Wire AO-MA artifact chain into the GPP-2D required-check lane (gated closeout; evidence-only)

**Status:** plan-time iter-1 REVISE absorb (Codex thread `019e6a6f-a3f7-7b92-9416-d6464668eafd`). Iter-2 ready_for_impl pending.
**Branch:** `codex/ao-ma-9-wire-aoma-artifacts`
**Decision artifact:** `ao_ma_9_gpp_integration_evidence`
**Parent:** AO-MA-1 §8 phased plan slice AO-MA-9 (last row; class: **gated closeout**)
**Support impact:** none

## Purpose

AO-MA-1 §8 plan row AO-MA-9:

> Wire AO-MA artifacts into the GPP-2D required-check lane after enforce evidence and cutover.

**Gated closeout class** — recorded decision + evidence-only PR. Codex iter-1 REVISE absorb:

1. **Option A LOCKED** — pure evidence/doc PR. Option B (runtime hook into `scripts/ao_release_gate_build_payload.py`) is explicitly **BLOCKED for AO-MA-9** (gate-contract change requires a separate AO-MA-10 / GPP supersession slice with trust-boundary, base-ref-vs-PR-head, workflow input, backward-compat design). Option C (A+B together) is rejected as too broad for a single work package.
2. **Wire = conceptual / evidence-chain wire** — NOT new payload fields. Receipt records the chain:

   ```
   AO-MA schemas (#637)
     -> AO-MA-3 Orchestrator (#645) emits task_graph + manifest
     -> AO-MA-4 WorkerRunner (#648) emits runner_report
     -> AO-MA-4.5 surrogate / worker emits worker_result
     -> AO-MA-6 Reviewer (#655) emits review_verdict
     -> AO-MA-7 Verifier (#657) emits verification_report
     -> AO-MA-5 Integrator (#654) emits integration_report
     -> AO-MA-8 end-to-end smoke (#660) integration_report receipt parity proof
     -> GPP-2D-4 enforce evidence (existing on main)
     -> GPP-2D-5 source-pinned required-check cutover (existing on main)
     -> GPP-2D-7 AO-GATE-9 GPP closeout (existing on main)
   ```

   The required-check lane (`ao-release-gate`) is unchanged; AO-MA-9 records that the AO-MA execution-layer artifacts are now consumable by the existing gate's signal chain — **as evidence, not as authority**.

3. **`wire_mode = "evidence_manifest_only"` const-pin** in the receipt schema so future readers cannot mis-interpret AO-MA-9 as a payload field extension or runtime hook.
4. **Fresh `origin/main` worktree** — implementation already started on a clean `codex/ao-ma-9-wire-aoma-artifacts` branch fast-forwarded to `origin/main` HEAD.

## Existing-state preconditions (already satisfied on main)

- GPP-9 (Final Claim Decision + M6 Closeout) — **closed**; 7/7 milestones done.
- ao-release-gate already enforced as required-check via GitHub branch ruleset (GPP-2D-5 cutover complete).
- AO-MA-2/3/4/5/6/7/8 all merged on main (post-d238e1c).
- guard_flags closed: `support_widening_allowed=false`, `production_platform_claim_allowed=false`, `live_adapter_execution_allowed=false`.

AO-MA-9 does **NOT** alter any of the above. It records the chain in evidence-only form.

## Module layout

```
.claude/plans/AO-MA-9-GPP-INTEGRATION.md                                        # plan doc (this file)
.claude/plans/AO-MA-9-GPP-INTEGRATION-EVIDENCE.v1.json                          # receipt
ao_kernel/defaults/schemas/ao-ma-9-gpp-integration-evidence.schema.v1.json      # receipt schema (Draft 2020-12)
tests/test_ao_ma_9_gpp_integration_invariant.py                                 # invariant test (~10 assertions)
local-ai-review-evidence.v1.json                                                # cross-AI trace
```

NO new runtime module. NO CLI handler change. NO workflow change. NO ruleset/branch-protection change.

## Receipt schema (Draft 2020-12; additionalProperties=false; const-pinned)

```json
{
  "schema_version": "ao-ma-9-gpp-integration-evidence.v1",
  "artifact_kind": "ao_ma_9_gpp_integration_evidence",
  "decision": "ao_ma_9_evidence_chain_wired",
  "wire_mode": "evidence_manifest_only",
  "release_authority_claim": false,
  "support_widening": false,
  "production_platform_claim": false,
  "live_adapter_execution": false,
  "ao_ma_chain_refs": {
    "schemas_pr": "#637",
    "orchestrator_pr": "#645",
    "runner_pr": "#648",
    "integrator_pr": "#654",
    "reviewer_pr": "#655",
    "verifier_pr": "#657",
    "e2e_smoke_pr": "#660"
  },
  "gpp_2d_artifact_refs": {
    "enforce_evidence": ".claude/plans/GPP-2D-4-ENFORCE-MODE-EVIDENCE.md",
    "cutover_runbook": ".claude/plans/GPP-2D-5-CUTOVER-RUNBOOK.md",
    "cutover_verification": ".claude/plans/GPP-2D-5-VERIFICATION-OUTCOMES.md",
    "smee_retirement": ".claude/plans/GPP-2D-5A-SMEE-RETIREMENT-EVIDENCE.md",
    "automerge_smoke": ".claude/plans/GPP-2D-6-AUTOMERGE-SMOKE-RUNBOOK.md",
    "ao_gate_9_closeout": ".claude/plans/GPP-2D-7-AO-GATE-9-GPP-CLOSEOUT.md"
  },
  "ao_ma_8_chain_proof_refs": {
    "smoke_plan": ".claude/plans/AO-MA-8-E2E-SMOKE.md",
    "smoke_receipt": ".claude/plans/AO-MA-8-E2E-SMOKE-EVIDENCE.v1.json",
    "smoke_schema": "ao_kernel/defaults/schemas/ao-ma-8-e2e-smoke-evidence.schema.v1.json",
    "smoke_test": "tests/test_ao_ma_8_e2e_smoke.py"
  },
  "gpp_status_invariants_at_closure": {
    "current_wp_id": "GPP-9",
    "current_wp_status": "closed",
    "milestones_done_total": "7/7",
    "support_widening_allowed": false,
    "production_platform_claim_allowed": false,
    "live_adapter_execution_allowed": false
  },
  "guard_flags": {
    "support_widening": false,
    "production_platform_claim": false,
    "live_adapter_execution": false
  }
}
```

Notes:
- `wire_mode` enum strictly `"evidence_manifest_only"` (Codex iter-1 must_close #2 absorb)
- `release_authority_claim` const `false` (Codex iter-1 hard stop: AO-MA artifacts NOT release authority)
- All three guard_flags + their `_allowed` variants pinned `false`
- PR refs as strings (informational; not URL fields)
- Artifact paths are repo-relative strings; receipt schema's `additionalProperties=false` blocks drift

## Invariant test plan (~10 assertions)

`tests/test_ao_ma_9_gpp_integration_invariant.py`:

| Test | Cover |
|---|---|
| `test_ao_ma_9_receipt_schema_valid_draft_2020_12` | Schema is a valid Draft 2020-12 document |
| `test_ao_ma_9_receipt_validates_against_schema` | Receipt parses + validates |
| `test_ao_ma_9_wire_mode_is_evidence_manifest_only` | Codex iter-1 must_close #2: const pin enforced (NOT payload field, NOT runtime hook) |
| `test_ao_ma_9_release_authority_claim_is_false` | AO-MA artifacts NOT release authority; closeout hygiene |
| `test_ao_ma_9_guard_flags_all_closed` | support_widening, production_platform_claim, live_adapter_execution all false |
| `test_ao_ma_9_ao_ma_chain_refs_record_all_seven_pr_numbers` | #637, #645, #648, #654, #655, #657, #660 |
| `test_ao_ma_9_gpp_2d_artifact_refs_point_to_existing_paths` | 6 GPP-2D docs all exist on disk |
| `test_ao_ma_9_ao_ma_8_chain_proof_refs_point_to_existing_paths` | AO-MA-8 plan + receipt + schema + test all exist |
| `test_ao_ma_9_gpp_status_invariants_match_runtime_authority` | Receipt's gpp_status_invariants_at_closure match the live gpp_status.v1.json (read-only; no mutation) |
| `test_ao_ma_9_no_payload_field_extension_in_release_gate` | Codex iter-1 must_close #3: invariant test does NOT assume payload field added; instead asserts wire is evidence-only (no AO-MA field in `scripts/ao_release_gate_build_payload.py`'s DEFAULT_ALLOWED_PATH_PREFIXES or payload constants) |
| `test_ao_ma_9_pr_scope_only_touches_allowlisted_files` | Codex nice-to-have: static PR-scope pin (4-5 file allowlist, multi-strategy resolver per AO-MA-8 pattern) |
| `test_ao_ma_9_no_subprocess_in_invariant_test_runtime_path` | Test does NOT spawn subprocess in its assertion path (only in PR-scope resolver, mirrored from AO-MA-8) |

## PR scope allowlist (Codex iter-1 nice-to-have #2)

This PR's diff is restricted to:

1. `.claude/plans/AO-MA-9-GPP-INTEGRATION.md` (this plan doc)
2. `.claude/plans/AO-MA-9-GPP-INTEGRATION-EVIDENCE.v1.json` (receipt)
3. `ao_kernel/defaults/schemas/ao-ma-9-gpp-integration-evidence.schema.v1.json` (receipt schema)
4. `tests/test_ao_ma_9_gpp_integration_invariant.py` (invariant test)
5. `local-ai-review-evidence.v1.json` (cross-AI trace)

NO other file may be touched. PR-scope static check `test_ao_ma_9_pr_scope_only_touches_allowlisted_files` enforces in CI (skip outside CI).

## Hard stops (HARD RULE pins; Codex iter-1 absorb expanded)

- **NO** mutation of `scripts/ao_release_gate_build_payload.py`, `scripts/ao_release_gate_decision.py`, `ao_kernel/ao_release_gate*.py` or any release-gate runtime
- **NO** mutation of `.github/**`, `CODEOWNERS`, branch-protection / ruleset / required-check allowlist
- **NO** mutation of `local_gpp_gate` schema or acceptance profile
- **NO** mutation of `ao_kernel/orchestration/**` runtime modules or CLI handler
- **NO** mutation of `.claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md`, `STATUS.md`, `AO-GATE-ROADMAP-TODO.md`, `gpp_status.v1.json`
- **NO** mutation of `AO-MA-1-MULTI-AGENT-ORCHESTRATION-DESIGN.md` (closure of the AO-MA-9 row stays in a separate optional follow-up; AO-MA-8 followed the same discipline)
- **NO** GPP-2C / testai / smee / callback topology change
- **NO** low-risk auto-merge smoke triggered
- **NO** CODEOWNERS narrowing
- **NO** `release_authority` field semantics — receipt explicitly `release_authority_claim: false`
- **NO** LLM call (Codex iter-1 absorb)
- **NO** `subprocess` in invariant test's assertion path (only in PR-scope resolver, mirrored from AO-MA-8)
- **NO** `gh pr` / `git push` / GitHub write
- **NO** support widening / production claim / live adapter execution

## Receipt-vs-runtime drift defense

Invariant test reads the committed receipt and asserts that:

- All `ao_ma_chain_refs` PR numbers match the actually merged AO-MA PR set (string contains check is OK for PR numbers since they're informational)
- All `gpp_2d_artifact_refs` paths exist on disk
- All `ao_ma_8_chain_proof_refs` paths exist on disk
- `gpp_status_invariants_at_closure` fields match the live `gpp_status.v1.json` field values

If any drift surfaces (e.g. someone moves a GPP-2D doc), the test fails and the receipt must be updated.

## Acceptance for AO-MA-9 v1

- ✅ Plan doc lands (this file)
- ✅ Receipt JSON lands (`AO-MA-9-GPP-INTEGRATION-EVIDENCE.v1.json`)
- ✅ Receipt schema lands (`ao-ma-9-gpp-integration-evidence.schema.v1.json`)
- ✅ Invariant test lands with ≥10 assertions
- ✅ Cross-AI Codex iter-N AGREE (plan-time + post-impl)
- ✅ Full test suite no regression
- ✅ ruff + mypy clean
- ✅ All hard-stop targets verifiably unchanged in PR diff (PR-scope allowlist test)
- ✅ AO-MA-1 §8 plan row AO-MA-9 closure stays **out of this PR's scope** (follow-up if needed)
