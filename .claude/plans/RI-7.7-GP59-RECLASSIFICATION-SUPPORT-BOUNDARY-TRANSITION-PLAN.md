# RI-7.7 — GP-5.9 BC-1..BC-10 Reclassification + Support-Boundary Transition Plan

**Status:** recorded / docs-only transition plan
**Date:** 2026-05-26
**Parent:** `RI-7-REPO-INTELLIGENCE-TIER-PROMOTION-READINESS.md`
**Support impact:** none (plan only; no boundary edit)
**Production platform claim:** false
**Support widening:** false
**Live adapter execution:** false
**Exit decision:** `ri7_gp59_transition_plan_ready`

## 1. Purpose

RI-7.7 closes two readiness-gate rows in a single docs-only transition
plan:

- `gp59_reclassification_plan_missing` — a written reclassification plan
  for the GP-5.9 BC-1..BC-10 baseline blockers (what stays, what would
  change, and what authority is required to change it).
- `support_boundary_transition_plan_missing` — a written transition plan
  for the public support-boundary surfaces (`docs/PUBLIC-BETA.md`,
  `docs/SUPPORT-BOUNDARY.md`, `docs/KNOWN-BUGS.md`) consumed by a future
  RI-7.8 promotion decision PR.

**This slice does not perform any reclassification or transition edit.**
It records the plan and leaves the BC baseline + public docs untouched.
Any actual reclassification or boundary-text change is reserved for an
explicit operator-bound supersession PR (RI-7.8 or later).

## 2. Authority Boundary

GPP-9 is closed under:

```
gpp9_keep_narrow_stable_runtime_authoritative_program_closed_no_live_adapter_execution_no_support_widening_no_production_claim
```

Per GP-5.9, BC-1 (protected live-adapter gate attestation missing) and
BC-10 (real-adapter usage/cost evidence missing) remain explicit blockers.
RI-7.7 leaves the BC baseline intact and explicitly does not authorize:

- flipping `support_widening_allowed`, `production_platform_claim_allowed`,
  or `live_adapter_execution_allowed` in `gpp_status.v1.json`;
- editing `scripts/gp5_platform_claim_decision.py`;
- editing the `BC-1..BC-10` enum or status in any existing source-of-truth;
- promoting repo-intelligence beyond Beta/experimental in
  `docs/PUBLIC-BETA.md` or `docs/SUPPORT-BOUNDARY.md`;
- removing any entry from `docs/KNOWN-BUGS.md`.

## 3. GP-5.9 BC Reclassification Plan

| BC ID | Current status (per GP-5.9) | RI-7.7 reclassification decision (plan-only) | Authority required to change |
|---|---|---|---|
| `BC-1` | blocked (missing protected live-adapter gate attestation) | **retain as blocker**; cannot reclassify without protected live-adapter gate evidence; reserved for operator-bound supersession with real attestation | Operator authorization PR + protected live-adapter gate attestation artifact |
| `BC-2` | covered (governed read-only workflow rehearsal evidence) | **retain as covered**; RI-7.6 cross-lane matrix cites the canonical evidence path; no change | n/a (already covered) |
| `BC-3` | covered (repo-intelligence retrieval evidence contract) | **retain as covered**; RI-7.2 guardrail hardening matrix + RI-7.3 vector backend E2E reinforce existing evidence; no reclassification | n/a (already covered) |
| `BC-4` | covered (agent context handoff contract) | **retain as covered**; RI-7.2 confirms no auto-feed + no MCP exposure invariants; no change | n/a (already covered) |
| `BC-5` | covered (workflow opt-in design contract) | **retain as covered**; no RI-7.x slice mutates the opt-in surface | n/a (already covered) |
| `BC-6` | covered (no-MCP / no-root-export guard) | **retain as covered**; RI-7.2 §3.6 pins the no-MCP exposure regression refs | n/a (already covered) |
| `BC-7` | covered (controlled local patch/test rehearsal evidence) | **retain as covered**; RI-7.6 lane `controlled_write_side` cites the canonical GPP-7 closed decision | n/a (already covered) |
| `BC-8` | covered (disposable PR write rehearsal, sandbox-only) | **retain as covered**; RI-7.6 lane `remote_pr_write` cites the canonical GPP-8 closed decision | n/a (already covered) |
| `BC-9` | covered (full production rehearsal aggregation) | **retain as covered**; RI-7.6 lane `cost_telemetry` cites the canonical GP-5.7a/b + GPP-9 closed decision | n/a (already covered) |
| `BC-10` | blocked (missing real-adapter usage/cost evidence) | **retain as blocker**; cannot reclassify without real-adapter usage/cost artifact; reserved for operator-bound supersession with real attestation | Operator authorization PR + real-adapter usage/cost evidence artifact |

**Net effect of RI-7.7 on the BC baseline**: zero. Eight BC rows remain
`covered` (BC-2..BC-9), two remain `blocked` (BC-1, BC-10). Any change to
BC-1 or BC-10 status requires the operator-bound supersession path
described in §5.

## 4. Support-Boundary Transition Plan

The following public boundary surfaces are **referenced** by this plan
but **not modified**. The plan records the exact text additions a future
RI-7.8 promotion decision PR would need to make, and the conditions
under which each edit is authorized.

### 4.1 `docs/PUBLIC-BETA.md`

Current matrix pins repo-intelligence scan/index/query as Beta/experimental
under the GP-5.9 boundary. The RI-7.8 transition would need to:

- Add a single row for the explicit general-purpose production tier with
  an authority reference to the RI-7.8 operator promotion decision PR.
- Keep every existing Beta/experimental row intact (no removal, no
  reclassification of unrelated tiers).
- Cite the RI-7.6 cross-lane production matrix and the RI-7.5 operator
  runtime semantics record as the consumed evidence.

**RI-7.7 does not write this row.** It only records the contract.

### 4.2 `docs/SUPPORT-BOUNDARY.md`

Current text treats repo-intelligence as Beta/operator-managed or
experimental. The RI-7.8 transition would need to:

- Add a clarifying paragraph distinguishing the operator-managed Beta
  surface from the explicit general-purpose production tier (if and only
  if RI-7.8 records a promote decision).
- Keep the existing operator-managed/experimental notes intact.
- Cross-reference the RI-7.6 lane statuses (six covered, one operator-bound
  deferred).

### 4.3 `docs/KNOWN-BUGS.md`

The transition does not remove or downgrade any existing known-bug entry.
If the RI-7.8 promotion decision is recorded, a new note may be added
linking to the RI-7.5 operator runtime semantics record and the RI-7.6
cross-lane matrix; existing entries remain authoritative.

## 5. Authorization Path (for any later edit)

Any actual BC reclassification or public boundary-text change requires:

1. RI-7.1 explicit operator authorization record.
2. RI-7.5 operator-verified runtime semantics sign-off.
3. RI-7.8 final operator promotion decision PR.
4. Real protected live-adapter gate attestation (for BC-1) and/or
   real-adapter usage/cost evidence (for BC-10), as applicable.

Without all four, RI-7.7 stays a docs-only plan and the BC baseline +
public boundary surfaces remain frozen.

## 6. Forbidden-Change Audit (this slice)

| Surface | Status |
|---|---|
| `.claude/plans/gpp_status.v1.json` | unchanged; guard flags remain false |
| `scripts/gp5_platform_claim_decision.py` | unchanged |
| `.claude/plans/GP-5.9-PRODUCTION-PLATFORM-CLAIM-DECISION.md` | unchanged (RI-7.7 references but does not edit) |
| `docs/PUBLIC-BETA.md` | unchanged (RI-7.7 records contract only) |
| `docs/SUPPORT-BOUNDARY.md` | unchanged |
| `docs/KNOWN-BUGS.md` | unchanged |
| `.github/workflows/` | unchanged |
| `ao_kernel/__init__.py` and public SDK signatures | unchanged |
| `ao_kernel/mcp_server.py` and MCP tool dispatch | unchanged; no repo-intelligence tool exposed |
| `ao_kernel/defaults/policies/` | unchanged |
| Branch protection / ruleset | unchanged |
| BC-1..BC-10 baseline | unchanged (RI-7.7 records reclassification plan only; the baseline itself stays frozen) |

## 7. Evidence Artifact

`.claude/plans/RI-7.7-GP59-RECLASSIFICATION-SUPPORT-BOUNDARY-TRANSITION-PLAN.v1.json`
validates against
`ao_kernel/defaults/schemas/ri7-gp59-transition-plan-evidence.schema.v1.json`.

Required fields:

- `artifact_kind`: `ri7_gp59_reclassification_support_boundary_transition_plan_evidence`
- `decision`: `ri7_gp59_transition_plan_ready`
- `support_widening` / `production_platform_claim` / `live_adapter_execution`: `false`
- `bc_baseline`: array of 10 entries (one per BC-1..BC-10). Each entry
  carries `id`, `current_gp59_status`, `ri77_reclassification_decision`,
  `promotion_readiness_status`, and `authority_required` as required
  fields, plus the optional `current_gp59_blockers`,
  `required_evidence_class`, `required_evidence_refs`, and
  `target_promotion_readiness_status_after_successful_supersession`
  fields (these last four are optional in the general case, but the
  schema's `allOf` pins them as **required** specifically for BC-1
  and BC-10 — both must carry `required_evidence_class=live`, exactly
  two `required_evidence_refs` with const `path`/`ref_status`/
  `owner_slice`/`must_exist_before_reclassification`, and
  `target_promotion_readiness_status_after_successful_supersession=pass`). `current_gp59_status` mirrors the source-truth enum used by
  `scripts/gp5_platform_claim_decision.py` exactly
  (`pass|blocked|exception`). `ri77_reclassification_decision` is one
  of `retain_as_pass` (covered criterion), `retain_as_blocker` (GP-5.9
  still blocks AND promotion still blocks — BC-1), or
  `retain_as_promotion_blocker` (GP-5.9 accepts via exception but
  promotion is still blocked until live evidence — BC-10).
  `promotion_readiness_status` is independent of GP-5.9 and names the
  concrete production-claim blocker if any. No reclassification is
  allowed by this slice — the BC baseline is read-only here; a future
  RI-7.8c promote PR is the only authorized writer.
- B-path vocabulary fix (Codex thread 019e691b iter-2+iter-3): the
  previous single field `current_status` (enum `covered|blocked`)
  collapsed GP-5.9 framework status and production-promotion readiness
  into one ambiguous value. The split above is the canonical schema
  used by RI-7.8c as input.
- `boundary_surfaces`: array of 3 entries (`PUBLIC-BETA.md`,
  `SUPPORT-BOUNDARY.md`, `KNOWN-BUGS.md`) with `path` and
  `ri77_edit_decision` = `unchanged_record_contract_only`.

## 8. Acceptance

RI-7.7 is complete when:

1. ✅ This plan exists and records the BC reclassification plan + boundary
   transition contract.
2. ✅ Schema validates the evidence artifact (zero errors).
3. ✅ Evidence artifact records all 10 BC rows and 3 boundary surfaces
   with the frozen-state decisions documented above.
4. ✅ Doc invariant test pins BC list, boundary surface list, exit
   decision, no-promotion-dilution language, and forbidden-change audit
   surfaces.
5. ✅ Readiness gate continues to report
   `blocked_operator_bound_evidence_required` and three guard flags
   `false`; running with a manifest that flips
   `gp59_reclassification_plan=true` and `support_boundary_transition_plan=true`
   drops both blockers while remaining RI-7.1, 7.5, 7.8 blockers stay.
6. ✅ Forbidden-change audit clean (§6).
7. ✅ Cross-AI peer review AGREE (Codex reviewer, Claude implementer).

## 9. Exit Decision

`ri7_gp59_transition_plan_ready` — RI-7.7 records the GP-5.9 BC-1..BC-10
reclassification plan and the public support-boundary transition contract
without modifying the BC baseline or any boundary surface. **No support
widening. No production platform claim. No live adapter execution. BC-1
and BC-10 remain explicit blockers. Repo-intelligence remains
Beta/experimental pending RI-7.1 operator authorization and the later
RI-7.8 promotion decision PR.**
