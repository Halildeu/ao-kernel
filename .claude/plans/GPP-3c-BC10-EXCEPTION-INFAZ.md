# GPP-3c — BC-10 Exception İnfazı (Faz 3, Final)

> **Status:** GPP-3 chain closeout; BC-10 reclassified from `blocked` to `exception`.
> **Slice:** `GPP-3c` (Faz 3 of GPP-3).
> **Issue:** pinned on commit per CC-13.
> **Decision:** `bc10_exception_executed_no_live_adapter_execution_no_support_widening_no_production_claim`.
> **Effective:** see `gpp_status.v1.json::current_wp.closeout_at` after merge.

## Purpose

GPP-3c is the **final infaz** (execution) slice of GPP-3 and closes
the BC-10 promotion blocker under the closure path decided in GPP-3b.
This is the only GPP-3 slice that mutates `scripts/gp5_platform_claim_decision.py`,
the gp5 platform claim decision schema, and the public-facing
documentation (Public Beta + Support Boundary + Known Bugs).

After this slice merges, BC-10 carries `status="exception"` with an
empty `blockers` array; the GP-5.9 promotion blockers list no longer
contains `real_adapter_usage_and_cost_evidence_missing`. The
keep-narrow-stable-runtime decision is preserved (BC-1 and other
non-BC-10 blockers still hold), and the three guard flags
(`support_widening_allowed`, `production_platform_claim_allowed`,
`live_adapter_execution_allowed`) remain `false`.

## Mutations Applied in This Slice

### 1. `ao_kernel/defaults/schemas/gp5-production-platform-claim-decision.schema.v1.json`

The `success_criterion.status` enum is widened from
`["pass", "partial", "blocked"]` to
`["pass", "partial", "blocked", "exception"]`. This is an **additive
non-breaking change** per CC-8; the schema_version stays at `v1`
because:

- All previously valid documents remain valid (no field removed, no
  type changed, no required-field added).
- The new `exception` value is only emitted when a closure decision
  records a deliberate policy exception (currently BC-10 only).
- External consumers that did not handle `exception` will treat the
  field as an unrecognized string; downstream code is responsible
  for translating `exception` into the local taxonomy.

### 2. `scripts/gp5_platform_claim_decision.py`

The `BC-10` criterion in `_default_criteria` is rewritten:

- `status`: `blocked` → `exception`
- `summary`: extended to cite the GPP-3b closure path and to call out
  the three options (Y authoritative, Z supporting, X deferred).
- `evidence`: three new references (GPP-3a schema record, GPP-3b
  decision record, GPP-3c infaz record).
- `blockers`: `["real_adapter_usage_and_cost_evidence_missing"]` → `[]`.

The `_promotion_blockers` helper continues to aggregate from the
remaining BC criteria's blockers lists; with BC-10 reporting an empty
list, the aggregate now excludes `real_adapter_usage_and_cost_evidence_missing`.
BC-1 and other criteria are unchanged.

### 3. `tests/test_gp5_platform_claim_decision.py`

`test_gp59_platform_claim_decision_keeps_narrow_runtime` is updated:

- Negative assert: `real_adapter_usage_and_cost_evidence_missing not in promotion_blockers`.
- Positive asserts: BC-10 entry exists, `status == "exception"`, and
  `blockers == []`.

The other tests in the file (decision rejection paths, schema
violations) continue to use the same `keep_narrow_stable_runtime`
fixture; the broader decision string is unchanged.

### 4. `docs/PUBLIC-BETA.md`

The GP-5.9 row is updated to reflect that BC-10 is now `exception`
rather than `blocked`, while making clear that this is **not**
support widening, **not** a production platform claim, **not** live
adapter execution authority, and **not** a substitute for live
adapter evidence in any future operator-bound supersession slice.

### 5. `docs/SUPPORT-BOUNDARY.md`

A new GPP-3c paragraph is added explaining that the no-live
autonomous path treats real-adapter cost/token evidence as a
deliberate policy exception and does **not** extend the supported
runtime tier. The narrow stable runtime boundary is preserved.

### 6. `docs/KNOWN-BUGS.md`

The BC-10 entry is rewritten from "blocked: real-adapter cost/token
evidence is unavailable" to "exception: BC-10 deferred under GPP-3b
policy exception decision; live adapter execution remains
operator-bound and outside the autonomous path." Existing KB-001
and KB-002 entries are untouched.

### 7. `.claude/plans/gpp_status.v1.json`

- `current_wp` migrates GPP-3b active → GPP-3c **closed** (the GPP-3
  chain is now complete).
- GPP-3b closure preserved in `completed_wps` with decision string
  `bc10_policy_exception_authoritative_no_live_adapter_execution_no_support_widening_no_production_claim`.
- `milestones[M3]` transitions from `pending` to `done`; `closed_at`
  set to the GPP-3c merge timestamp; `evidence_refs` cites the three
  GPP-3 record paths (3a/3b/3c).
- `progress_estimates`: `completed_wps_count` advances to 40
  (38 + GPP-3a + GPP-3b); `closed_current_wp_count` = 1 (GPP-3c
  closed); `completed_or_closed_count` = 41; `percent` recomputes to
  82%. Milestone progress advances to 4/7 = 57%; `next_milestone_id`
  becomes M4.
- Two new `forbidden_actions` entries: "treat BC-10 exception as
  authorization to widen support" and "treat BC-10 exception as a
  substitute for live adapter evidence in any future supersession
  slice".

## Non-Goals (still deferred to a future operator-bound slice)

- Execute a live adapter
- Flip `live_adapter_execution_allowed=true`
- Promote `claude-code-cli` to production-certified read-only (GPP-4)
- Run the GPP-6 read-only production E2E
- Open GPP-7 / GPP-8 / GPP-9 scope
- Claim general-purpose production platform readiness

## Guard Flag Invariants (unchanged)

- `support_widening_allowed`: `false`
- `production_platform_claim_allowed`: `false`
- `live_adapter_execution_allowed`: `false`

## Supersession Rules

If a future operator-bound slice authorizes a live adapter execution
and emits a `real-adapter-usage-cost-evidence.v1` artifact with
`evidence_class="live"`, that slice can reclassify BC-10 from
`exception` back to `pass`. The supersession requires:

1. Operator-only PR flipping `live_adapter_execution_allowed=true`
   with a clear declaration and audit comment.
2. Protected workflow + cost-cap + N-call limits.
3. Real evidence artifact with `evidence_class="live"`.
4. Operator-only PR flipping `live_adapter_execution_allowed=false`
   back.
5. A new decision record (e.g. `GPP-3d-...` or `GPP-4-...`) updating
   `gp5_platform_claim_decision.py` BC-10 to `status="pass"` with
   the live evidence references.

Until that supersession lands, BC-10 stays `exception` and the
guard flags remain `false`.

## Cross-References

- `.claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md`
- `.claude/plans/gpp_status.v1.json`
- `.claude/plans/GPP-3a-USAGE-COST-EVIDENCE-SCHEMA.md`
- `.claude/plans/GPP-3b-BC10-CLOSURE-PATH-DECISION.md`
- `.claude/plans/GP-5.9-PRODUCTION-PLATFORM-CLAIM-DECISION.md`
- `.claude/plans/PROGRAM-CHANGE-CONTROL.md` (CC-1..CC-13)
- `ao_kernel/defaults/schemas/gp5-production-platform-claim-decision.schema.v1.json`
- `ao_kernel/defaults/schemas/real-adapter-usage-cost-evidence.schema.v1.json`
- `scripts/gp5_platform_claim_decision.py`
- `scripts/real_adapter_usage_evidence.py`

## Audit Trail

| Field | Value |
|---|---|
| Implementer AI | Claude (Anthropic) |
| Reviewer AI | Codex (OpenAI) — thread `019e5c36` (continues from GPP-3b plan-time iter-1 AGREE) |
| Worktree | `codex/gpp-3c-bc10-exception-infaz` |
| Base SHA at branch open | `477a0b8` |
| Cross-provider AI review HARD RULE | satisfied (CC-2) |
| Non-author code-owner approval | required at merge time (CC-3) |
| Admin bypass attempted | `false` (CC-4) |
