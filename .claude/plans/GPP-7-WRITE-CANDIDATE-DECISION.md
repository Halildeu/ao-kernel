# GPP-7 — Controlled Write-Side keep_rehearsal_only Decision (M6 Faz 1)

> **Status:** decision recorded + executed (single PR consolidated).
> **Slice:** `GPP-7` (M6 Faz 1; first of three M6 slices).
> **Issue:** [#631](https://github.com/Halildeu/ao-kernel/issues/631) pinned on commit per CC-13.
> **Decision:** `gpp7_keep_rehearsal_only_authoritative_no_write_side_production_candidate_no_live_adapter_execution_no_support_widening_no_production_claim`.
> **Effective:** effective on merge; M6 milestone stays `pending` until
> GPP-8 + GPP-9 close (GPP-9 records the M6 closeout).

## Purpose

GPP-7 closes the **controlled write-side production candidate**
question under the autonomous GPP chain. The existing readiness stack
already provides preparation/rehearsal evidence:

- `gp5-controlled-patch-test-contract.schema.v1.json` (GP-5.5a) —
  design contract: disposable worktree, path-scoped ownership, diff
  preview, explicit apply approval, explainable tests with full-gate
  fallback, rollback + idempotency, cleanup evidence
- `scripts/gp5_controlled_patch_test_rehearsal.py` +
  `gp5-controlled-patch-test-rehearsal-report.schema.v1.json`
  (GP-5.5b) — local disposable patch/test rehearsal with at-least-3
  clean runs + 1 fail-closed run capability
- `scripts/gp5_disposable_pr_write_rehearsal.py` +
  `gp5-disposable-pr-write-rehearsal-report.schema.v1.json` (GP-5.6a)
  — disposable sandbox PR write rehearsal
- `gp5-full-production-rehearsal-contract.schema.v1.json` (GP-5.7a)
  + `scripts/gp5_full_production_rehearsal.py` +
  `gp5-full-production-rehearsal-report.schema.v1.json` (GP-5.7b)
  — full rehearsal aggregation gate

GPP-7 chooses among:

- **Option X — write_candidate_ready** (deferred, operator-bound)
- **Option Y — keep_rehearsal_only** (CHOSEN authoritative)
- **Option Z — defer** (REJECTED)

This slice is the first of three M6 slices (GPP-7 + GPP-8 + GPP-9).
M6 milestone closure is reserved for GPP-9 with evidence_refs
[GPP-7 + GPP-8 + GPP-9].

This slice **does NOT**:

- flip `live_adapter_execution_allowed`, `support_widening_allowed`,
  or `production_platform_claim_allowed` (all stay `false`)
- mutate `scripts/gp5_platform_claim_decision.py` BC-1 status or
  `_promotion_blockers()`
- mutate `scripts/gp5_controlled_patch_test_rehearsal.py` or any
  rehearsal report schema
- modify `ao_kernel/` public SDK signatures
- mutate any JSON schema under `ao_kernel/defaults/schemas/`
- mutate `.github/workflows/`
- execute a live adapter
- mutate branch protection / required status checks
- close the M6 milestone (M6 closes only after GPP-9 executes)
- promote `bug_fix_flow` / live remote PR write to shipped baseline
- promote the controlled patch/test lane from rehearsal to
  production-certified write-side tier

## Closure Path Comparison

### Option X — write_candidate_ready (deferred, NOT autonomous)

- **What:** operator authorizes the controlled patch/test rehearsal
  stack to produce **production-targeted** controlled write evidence:
  three clean controlled write runs + one fail-closed run on
  production-targeted artifacts, with operator-verified write
  semantics. The existing `scripts/gp5_controlled_patch_test_rehearsal.py`
  already produces the rehearsal report shape; Option X reframes the
  evidence as production candidate by adding an explicit operator
  authorization marker, target audit binding, and reclassification of
  the controlled patch/test lane from rehearsal-only to
  production-certified write-side tier.
- **Cost:** operator-only PR to flip a new
  `controlled_patch_test_production_candidate_allowed=true` flag (or
  equivalent) + production-target write run evidence. Operator
  authority required because production candidate claim is a
  governance decision, not an evidence aggregation.
- **Outcome if pursued:**
  `decision_artifact = write_candidate_ready`,
  `gp5-controlled-patch-test-*` evidence reclassified to production
  candidate, lane tier widened from rehearsal-only to controlled
  write production candidate.
- **Decision:** **deferred**. Operator authorization is explicitly
  outside the autonomous GPP-7 chain. A future operator-bound
  supersession slice may pursue this independently; that slice would
  supersede this GPP-7 decision and reclassify the controlled
  patch/test lane.

### Option Y — keep_rehearsal_only (CHOSEN as authoritative)

- **What:** record the GPP-7 closure path as
  **preparation/rehearsal evidence preserved** authoritatively, under
  the same autonomous-chain authority as `GP-5.9
  keep_narrow_stable_runtime` and `GPP-6 keep_rehearsal_only`. The
  existing GP-5.5a/5.5b/5.6a/5.7a/5.7b stack is preparation/rehearsal
  evidence; the controlled patch/test lane remains rehearsal-only;
  the write-side production candidate claim is not granted.
- **Cost:** zero new evidence or runtime work. This PR carries the
  decision recording + SSOT/test closure + docs sync.
- **Outcome:**
  `decision_artifact = keep_rehearsal_only`, M6 Faz 1 closed under
  preparation/rehearsal evidence preserved authority,
  `live_adapter_execution_allowed=false`,
  `support_widening_allowed=false`,
  `production_platform_claim_allowed=false`. The controlled
  patch/test lane support tier remains rehearsal-only. The
  `gp5-controlled-patch-test-*` evidence stack stays as preparation
  evidence and is not reclassified to production candidate.
- **Decision:** **authoritative** for GPP-7 closure under the
  autonomous path.

### Option Z — defer (REJECTED)

- **What:** record the GPP-7 decision as "deferred" and leave the M6
  closure path commitment open.
- **Risk:** `defer` is more passive than Y and propagates the
  M6 closure ambiguity to GPP-8 and GPP-9. The existing
  preparation/rehearsal evidence stack is authoritative preparation
  evidence under the autonomous chain; promoting defer over
  keep_rehearsal_only would re-open a closed sub-question without new
  evidence.
- **Decision:** **rejected**.

## Decision (Authoritative)

GPP-7 closes under **Option Y — keep_rehearsal_only** as the
authoritative controlled write-side production candidate decision.
Option X (`write_candidate_ready`) remains deferred and
operator-bound; Option Z (defer) is rejected.

Decision string:

```text
gpp7_keep_rehearsal_only_authoritative_no_write_side_production_candidate_no_live_adapter_execution_no_support_widening_no_production_claim
```

The string asserts:

- closure under `keep_rehearsal_only`, not write-side production
  candidate evidence
- no write-side production candidate claim
- no live adapter execution
- no support widening
- no production platform claim

## Scope (single PR consolidated)

1. **`.claude/plans/GPP-7-WRITE-CANDIDATE-DECISION.md`** — this
   record (decision + closure narrative + supersession rules + audit
   trail).
2. **`.claude/plans/gpp_status.v1.json`** — SSOT migration:
   - `current_wp` migrate GPP-6c closed → GPP-7 closed (consolidated
     decision+infazı slice)
   - `completed_wps[]` append GPP-6c entry (issue #629, pr #630,
     closed_at=2026-05-25T~~~~Z)
   - GPP-7 **not** in completed_wps this slice (current-closed
     convention; the next M6 opener slice — GPP-8 — migrates GPP-7)
   - `progress_estimates.wp_weighted`: `completed_wps_count` 45 → 46
     (GPP-6c migrated), `closed_current_wp_count` stays 1 (GPP-7
     current closed), `completed_or_closed_count` 46 → 47, `percent`
     92 → 94
   - `progress_estimates.milestones`: **unchanged** (`done_count=6`,
     `next_milestone_id=M6`, M6 stays pending)
   - `forbidden_actions[]` appended GPP-7 specific guards
   - `next_allowed_actions[]` revised: GPP-7 executed line + GPP-8 /
     GPP-9 preparation reserved
3. **`.claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md`**
   — header sync to GPP-7 closed; M6 chain records line started
   (GPP-7); §0 progress sentence updated (M6 in progress: GPP-7
   closed; GPP-8 + GPP-9 reserved)
4. **`docs/SUPPORT-BOUNDARY.md`** — new GPP-7 closure paragraph
   appended after the GPP-6 closeout paragraph
5. **`docs/PUBLIC-BETA.md`** — new GPP-7 closure decision row (no
   support widening); minimal additive sync on GP-5.5a / GP-5.5b /
   GP-5.6a / GP-5.7a / GP-5.7b rows for "preparation/rehearsal
   evidence preserved under GPP-7 `keep_rehearsal_only`" wording
6. **`docs/KNOWN-BUGS.md`** — new "GPP-7 closeout interpretation"
   subsection appended after the GPP-6 closeout subsection (no
   blocker rename or removal)
7. **`tests/test_gpp_next.py`** — drift guards rewritten for GPP-7
   closed state:
   - `current_wp.id=GPP-7, status=closed` pin
   - `exit_decision` pin
   - `allowed_scope` anchor list
   - GPP-6c migrated entry assertion in completed_wps (pr=#630,
     `closed_at`)
   - GPP-7 absence from completed_wps invariant
   - `wp_weighted` triple (46/1/47/94) pin
   - render text "Current WP: GPP-7", "Current status: closed",
     progress headline "6/7 done (86%; next M6 - Production matrix +
     final claim)" preserved
   - M6 stays pending, evidence_refs=[]
   - **No** `_AGGREGATE_COMPLETION_SOURCES` GPP-7 entry yet
     (M6 pending; aggregate entries are added at milestone closure
     slice — GPP-9 will add GPP-7+8+9 entry as part of M6 done)
8. **`tests/test_local_gpp_gate.py`** — `current_wp.id=GPP-7 closed`
   pin
9. **`local-ai-review-evidence.v1.json`** — cross-AI peer review
   evidence

## Guard Flag Invariants (unchanged after GPP-7)

- `support_widening_allowed`: `false`
- `production_platform_claim_allowed`: `false`
- `live_adapter_execution_allowed`: `false`

## Schema Versioning Discipline (CC-8)

GPP-7 **does not** change any JSON Schema enum, required field, or
contract under `ao_kernel/defaults/schemas/`. The
`gp5-controlled-patch-test-contract.schema.v1.json`,
`gp5-controlled-patch-test-rehearsal-report.schema.v1.json`,
`gp5-disposable-pr-write-rehearsal-report.schema.v1.json`,
`gp5-full-production-rehearsal-contract.schema.v1.json`, and
`gp5-full-production-rehearsal-report.schema.v1.json` schemas are
all unchanged. `schema_version` stays at `v1` for each. The CC-8
enum-widening pattern that GPP-3c used (`pass → exception`) does not
apply here because GPP-7 reclassifies no enum value.

## Non-Goals

This slice (GPP-7) explicitly does NOT:

1. promote the controlled patch/test lane from rehearsal-only to
   production-certified write-side tier
2. flip any of the three GP-5/GPP-9 promotion guard flags
3. execute a live adapter
4. dispatch a protected workflow or reference
   `AO_CLAUDE_CODE_CLI_AUTH`
5. mutate `scripts/gp5_platform_claim_decision.py` BC-1 status or
   `_promotion_blockers()` list
6. mutate `scripts/gp5_controlled_patch_test_rehearsal.py`,
   `scripts/gp5_disposable_pr_write_rehearsal.py`, or
   `scripts/gp5_full_production_rehearsal.py`
7. mutate any JSON schema under `ao_kernel/defaults/schemas/`
8. mutate `.github/workflows/`
9. close the M6 milestone (M6 closes only after GPP-9 executes;
   `M6.status=pending` retained, `evidence_refs=[]` retained)
10. add a `_AGGREGATE_COMPLETION_SOURCES` GPP-7 entry to
    `tests/test_gpp_next.py` (aggregate map entries are added at the
    milestone closure slice — GPP-9 will add the GPP-7+8+9 aggregate
    entry as part of M6 done)
11. claim that the GP-5.5b / GP-5.6a / GP-5.7b rehearsal evidence
    equals production write-side candidate evidence
12. reclassify the controlled patch/test lane from rehearsal-only to
    production-certified write-side tier
13. close the M6 milestone or update `milestones[M6].evidence_refs`
14. mutate branch protection or required status checks
15. modify `ao_kernel/` public SDK signatures
16. treat the GPP-7 closure as an entry-criteria pass for GPP-8 or
    GPP-9 — GPP-8 (remote PR keep_sandbox_only) and GPP-9 (final
    claim) each record their own decisions explicitly

## Supersession Rules

Option X (`write_candidate_ready`) remains available as a future
operator-bound supersession. If a later slice authorizes a
production-targeted controlled write evidence chain:

1. Operator-only PR adding an explicit production-candidate
   authorization flag and reclassifying the controlled patch/test
   evidence accordingly
2. Three clean controlled write runs + one fail-closed run on
   production-targeted artifacts with operator-verified write
   semantics
3. A new decision record (e.g. `GPP-7d-...`) updating
   `scripts/gp5_platform_claim_decision.py` if needed (any BC-N
   reclassification or new promotion_blockers entry must be in the
   supersession slice, not in GPP-7)

Until that supersession lands, GPP-7 stays at `keep_rehearsal_only`
and the controlled patch/test lane support tier remains
rehearsal-only.

## Cross-References

### Core evidence

- `.claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md` —
  program SSOT
- `.claude/plans/gpp_status.v1.json` — machine-readable status
- `.claude/plans/GPP-6c-KEEP-REHEARSAL-ONLY-INFAZ.md` — M5 closeout
- `.claude/plans/GP-5.5a-CONTROLLED-PATCH-TEST-CONTRACT.md` (if
  present) — controlled patch/test contract precedent
- `.claude/plans/GP-5.5b-CONTROLLED-LOCAL-PATCH-TEST-REHEARSAL.md` —
  controlled local patch/test rehearsal script
- `.claude/plans/GP-5.6a-DISPOSABLE-PR-WRITE-REHEARSAL.md` —
  disposable sandbox PR write rehearsal
- `.claude/plans/GP-5.7a-FULL-PRODUCTION-REHEARSAL-CONTRACT.md` —
  full rehearsal contract
- `.claude/plans/GP-5.7b-FULL-PRODUCTION-REHEARSAL-GATE.md` — full
  rehearsal execution gate (simulated aggregation)
- `.claude/plans/GP-5.9-PRODUCTION-PLATFORM-CLAIM-DECISION.md` —
  BC-1..BC-10 baseline
- `.claude/plans/PROGRAM-CHANGE-CONTROL.md` — CC-1..CC-13
- `docs/SUPPORT-BOUNDARY.md`
- `docs/PUBLIC-BETA.md`
- `docs/KNOWN-BUGS.md`

### Pattern precedent (not core)

- `.claude/plans/GPP-3b-BC10-CLOSURE-PATH-DECISION.md` — M3 Faz 2
  X/Y/Z decision path
- `.claude/plans/GPP-4b-KEEP-OPERATOR-BETA-DECISION.md` — M4 Faz 2
- `.claude/plans/GPP-6b-READ-ONLY-E2E-DECISION.md` — M5 Faz 2

## Audit Trail

| Field | Value |
|---|---|
| Implementer AI | Claude (Anthropic) |
| Reviewer AI | Codex (OpenAI) — thread `019e617b` plan-time iter-1 AGREE for GPP-7 (single PR consolidated decision+infazı; Option Y authoritative; M6 pending; no aggregate entry yet; 5 forbidden actions appended); post-impl iter review continues after PR creation |
| Worktree | `codex/gpp-7-write-candidate-decision` |
| Base SHA at branch open | `28ad107` |
| Cross-provider AI review HARD RULE | satisfied (CC-2) |
| Non-author code-owner approval | required at merge time (CC-3) |
| Admin bypass attempted | `false` (CC-4) |
