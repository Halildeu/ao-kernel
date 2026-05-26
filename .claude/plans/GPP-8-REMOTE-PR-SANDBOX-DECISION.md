# GPP-8 — Remote PR Sandbox-Only Decision (M6 Faz 2)

> **Status:** decision recorded + executed (single PR consolidated).
> **Slice:** `GPP-8` (M6 Faz 2; second of three M6 slices).
> **Issue:** [#633](https://github.com/Halildeu/ao-kernel/issues/633) pinned on commit per CC-13.
> **Decision:** `gpp8_keep_sandbox_only_authoritative_no_remote_pr_production_candidate_no_live_adapter_execution_no_support_widening_no_production_claim`.
> **Effective:** effective on merge; M6 milestone stays `pending` until
> GPP-9 closes (GPP-9 records the M6 closeout with three
> evidence_refs covering GPP-7 + GPP-8 + GPP-9).

## Purpose

GPP-8 closes the **remote PR live-write promotion candidate**
question under the autonomous GPP chain. The existing readiness stack
already provides preparation/rehearsal evidence:

- `gp5-disposable-pr-write-rehearsal-report.schema.v1.json` (GP-5.6a)
  — sandbox-guarded PR create → verify → close → delete rehearsal
  report schema
- `scripts/gp5_disposable_pr_write_rehearsal.py` (GP-5.6a) —
  disposable sandbox PR write rehearsal script with sandbox-guard
  keyword enforcement
- `gp5-full-production-rehearsal-contract.schema.v1.json` (GP-5.7a)
  + `scripts/gp5_full_production_rehearsal.py` (GP-5.7b)
  + `gp5-full-production-rehearsal-report.schema.v1.json` (GP-5.7b)
  — full rehearsal aggregation gate

GPP-8 chooses among:

- **Option X — remote_pr_candidate_ready** (deferred, operator-bound)
- **Option Y — keep_sandbox_only** (CHOSEN authoritative)
- **Option Z — defer** (REJECTED)

This slice is the second of three M6 slices (GPP-7 + GPP-8 + GPP-9).
M6 milestone closure is reserved for GPP-9 with evidence_refs
[GPP-7 + GPP-8 + GPP-9].

This slice **does NOT**:

- flip `live_adapter_execution_allowed`, `support_widening_allowed`,
  or `production_platform_claim_allowed` (all stay `false`)
- mutate `scripts/gp5_platform_claim_decision.py` BC-1 status or
  `_promotion_blockers()`
- mutate `scripts/gp5_disposable_pr_write_rehearsal.py`,
  `scripts/gp5_full_production_rehearsal.py`, or any rehearsal
  report schema
- modify `ao_kernel/` public SDK signatures
- mutate any JSON schema under `ao_kernel/defaults/schemas/`
- mutate `.github/workflows/`
- execute a live adapter or dispatch a protected workflow
- authorize non-sandbox repo remote PR live-write or remove the
  sandbox-guard keyword requirement
- mutate branch protection / required status checks
- close the M6 milestone (M6 closes only after GPP-9 executes)
- promote the remote PR live-write lane from sandbox/disposable-only
  to production-certified

## Closure Path Comparison

### Option X — remote_pr_candidate_ready (deferred, NOT autonomous)

- **What:** operator authorizes the disposable sandbox PR write
  rehearsal stack to produce **production-targeted** remote PR
  live-write evidence: three clean production-targeted remote PR
  runs + one fail-closed run on non-sandbox repositories with
  operator-verified remote write semantics. The existing
  `scripts/gp5_disposable_pr_write_rehearsal.py` already produces
  the rehearsal report shape; Option X reframes the evidence as
  production candidate by adding an explicit operator authorization
  marker, removing the sandbox-guard keyword requirement for
  authorized targets, and reclassifying the remote PR live-write
  lane from sandbox/disposable-only to production-certified.
- **Cost:** operator-only PR to flip a new
  `remote_pr_production_candidate_allowed=true` flag (or
  equivalent) + production-target remote PR run evidence. Operator
  authority required because production candidate claim is a
  governance decision, not an evidence aggregation. Branch
  protection considerations apply if the production-targeted runs
  hit protected repositories.
- **Outcome if pursued:**
  `decision_artifact = remote_pr_candidate_ready`,
  `gp5-disposable-pr-write-rehearsal-*` evidence reclassified to
  remote PR production candidate, lane tier widened from
  sandbox/disposable-only to remote PR production candidate.
- **Decision:** **deferred**. Operator authorization is explicitly
  outside the autonomous GPP-8 chain. A future operator-bound
  supersession slice may pursue this independently; that slice
  would supersede this GPP-8 decision and reclassify the remote PR
  live-write lane.

### Option Y — keep_sandbox_only (CHOSEN as authoritative)

- **What:** record the GPP-8 closure path as
  **preparation/rehearsal evidence preserved** authoritatively, under
  the same autonomous-chain authority as `GP-5.9
  keep_narrow_stable_runtime` and `GPP-7 keep_rehearsal_only`. The
  existing GP-5.6a + GP-5.7a/5.7b stack is preparation/rehearsal
  evidence; the remote PR live-write lane remains
  sandbox/disposable-only; the production-certified remote PR
  support claim is not granted.
- **Cost:** zero new evidence or runtime work. This PR carries the
  decision recording + SSOT/test closure + docs sync.
- **Outcome:**
  `decision_artifact = keep_sandbox_only`, M6 Faz 2 closed under
  preparation/rehearsal evidence preserved authority,
  `live_adapter_execution_allowed=false`,
  `support_widening_allowed=false`,
  `production_platform_claim_allowed=false`. The remote PR
  live-write lane support tier remains sandbox/disposable-only. The
  `gp5-disposable-pr-write-rehearsal-*` and
  `gp5-full-production-rehearsal-*` evidence stack stays as
  preparation evidence and is not reclassified to remote PR
  production candidate. Sandbox-guard keyword requirement preserved
  on the disposable PR write rehearsal script.
- **Decision:** **authoritative** for GPP-8 closure under the
  autonomous path.

### Option Z — defer (REJECTED)

- **What:** record the GPP-8 decision as "deferred" and leave the M6
  closure path commitment open.
- **Risk:** `defer` is more passive than Y and propagates the
  M6 closure ambiguity to GPP-9. The existing
  preparation/rehearsal evidence stack is authoritative preparation
  evidence under the autonomous chain; promoting defer over
  keep_sandbox_only would re-open a closed sub-question without new
  evidence.
- **Decision:** **rejected**.

## Decision (Authoritative)

GPP-8 closes under **Option Y — keep_sandbox_only** as the
authoritative remote PR live-write promotion candidate decision.
Option X (`remote_pr_candidate_ready`) remains deferred and
operator-bound; Option Z (defer) is rejected.

Decision string:

```text
gpp8_keep_sandbox_only_authoritative_no_remote_pr_production_candidate_no_live_adapter_execution_no_support_widening_no_production_claim
```

The string asserts:

- closure under `keep_sandbox_only`, not remote PR production
  candidate evidence
- no remote PR production candidate claim
- no live adapter execution
- no support widening
- no production platform claim

## Scope (single PR consolidated)

1. **`.claude/plans/GPP-8-REMOTE-PR-SANDBOX-DECISION.md`** — this
   record (decision + closure narrative + supersession rules + audit
   trail).
2. **`.claude/plans/gpp_status.v1.json`** — SSOT migration:
   - `current_wp` migrate GPP-7 closed → GPP-8 closed (consolidated
     decision+infazı slice)
   - `completed_wps[]` append GPP-7 entry (issue #631, pr #632,
     closed_at=2026-05-26T00:22:00Z)
   - GPP-8 **not** in completed_wps this slice (current-closed
     convention; the next M6 slice — GPP-9 — migrates GPP-8 as part
     of M6 closeout)
   - `progress_estimates.wp_weighted`: `completed_wps_count` 46 → 47
     (GPP-7 migrated), `closed_current_wp_count` stays 1 (GPP-8
     current closed), `completed_or_closed_count` 47 → 48, `percent`
     94 → 96
   - `progress_estimates.milestones`: **unchanged** (`done_count=6`,
     `next_milestone_id=M6`, M6 stays pending)
   - `forbidden_actions[]` appended 10 GPP-8 specific guards
   - `next_allowed_actions[]` revised: GPP-7 + GPP-8 executed lines
     + GPP-9 reserved
3. **`.claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md`**
   — header sync to GPP-8 closed; M6 chain records line extended
   (GPP-7 + GPP-8); §0 progress sentence updated (M6 in progress:
   GPP-7 + GPP-8 closed; GPP-9 reserved); §5 Work Package Board
   row for GPP-8 updated from "Not started" to "Closed / no support
   widening | Remote PR live-write promotion candidate |
   keep_sandbox_only authoritative (Option Y); Option X
   remote_pr_candidate_ready deferred operator-bound"
4. **`docs/SUPPORT-BOUNDARY.md`** — new GPP-8 closure paragraph
   appended after the GPP-7 closure paragraph
5. **`docs/PUBLIC-BETA.md`** — new GPP-8 closure decision row (no
   support widening); minimal additive sync on GP-5.6a + GP-5.7a +
   GP-5.7b rows for "preparation/rehearsal evidence preserved under
   GPP-8 `keep_sandbox_only`" wording
6. **`docs/KNOWN-BUGS.md`** — new "GPP-8 closeout interpretation"
   subsection appended after the GPP-7 closeout subsection (no
   blocker rename or removal)
7. **`tests/test_gpp_next.py`** — drift guards rewritten for GPP-8
   closed state:
   - `current_wp.id=GPP-8, status=closed` pin
   - `exit_decision` pin
   - `allowed_scope` anchor list
   - GPP-7 migrated entry assertion in completed_wps (pr=#632,
     closed_at=2026-05-26T00:22:00Z)
   - GPP-8 absence from completed_wps invariant
   - `wp_weighted` triple (47/1/48/96) pin
   - render text "Current WP: GPP-8", "Current status: closed",
     progress headline "6/7 done (86%; next M6 - Production matrix
     + final claim)" preserved
   - M6 stays pending, evidence_refs=[]
   - **No** `_AGGREGATE_COMPLETION_SOURCES` GPP-8 entry yet
     (M6 pending; aggregate entries added at milestone closure slice
     — GPP-9 will add GPP-7+8+9 entry as part of M6 done)
   - new `test_allowed_scope_reflects_gpp8_keep_sandbox_only_decision`
8. **`tests/test_local_gpp_gate.py`** — `current_wp.id=GPP-8 closed`
   pin
9. **`local-ai-review-evidence.v1.json`** — cross-AI peer review
   evidence

## Guard Flag Invariants (unchanged after GPP-8)

- `support_widening_allowed`: `false`
- `production_platform_claim_allowed`: `false`
- `live_adapter_execution_allowed`: `false`

## Schema Versioning Discipline (CC-8)

GPP-8 **does not** change any JSON Schema enum, required field, or
contract under `ao_kernel/defaults/schemas/`. The
`gp5-disposable-pr-write-rehearsal-report.schema.v1.json`,
`gp5-full-production-rehearsal-contract.schema.v1.json`, and
`gp5-full-production-rehearsal-report.schema.v1.json` schemas are
all unchanged. `schema_version` stays at `v1` for each.

## Non-Goals

This slice (GPP-8) explicitly does NOT:

1. promote the remote PR live-write lane from sandbox/disposable-only
   to production-certified
2. flip any of the three GP-5/GPP-9 promotion guard flags
3. execute a live adapter or dispatch a protected workflow
4. authorize non-sandbox repo remote PR live-write
5. remove the sandbox-guard keyword requirement on the disposable PR
   write rehearsal script
6. mutate `scripts/gp5_platform_claim_decision.py` BC-1 status or
   `_promotion_blockers()` list
7. mutate `scripts/gp5_disposable_pr_write_rehearsal.py` or
   `scripts/gp5_full_production_rehearsal.py`
8. mutate any JSON schema under `ao_kernel/defaults/schemas/`
9. mutate `.github/workflows/` or branch protection / required-check
   ruleset
10. close the M6 milestone (M6 closure is reserved for GPP-9 with
    three evidence_refs)
11. add a `_AGGREGATE_COMPLETION_SOURCES` GPP-8 entry to
    `tests/test_gpp_next.py` (deferred to GPP-9 milestone closure)
12. claim that the GP-5.6a / GP-5.7b sandbox rehearsal evidence
    equals remote PR production candidate evidence
13. reclassify the disposable sandbox PR write rehearsal lane
14. modify `ao_kernel/` public SDK signatures
15. treat the GPP-8 closure as an entry-criteria pass for GPP-9 —
    GPP-9 (final claim keep_narrow_stable_runtime) records its own
    decision explicitly

## Supersession Rules

Option X (`remote_pr_candidate_ready`) remains available as a future
operator-bound supersession. If a later slice authorizes a
production-targeted remote PR live-write evidence chain:

1. Operator-only PR adding an explicit production-candidate
   authorization flag and reclassifying the disposable PR write
   evidence accordingly
2. Three clean production-targeted remote PR runs + one fail-closed
   run on non-sandbox repositories with operator-verified remote
   write semantics
3. A new decision record (e.g. `GPP-8d-...`) updating
   `scripts/gp5_platform_claim_decision.py` if needed (any BC-N
   reclassification or new promotion_blockers entry must be in the
   supersession slice, not in GPP-8)

Until that supersession lands, GPP-8 stays at `keep_sandbox_only`
and the remote PR live-write lane support tier remains
sandbox/disposable-only.

## Cross-References

### Core evidence

- `.claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md` —
  program SSOT
- `.claude/plans/gpp_status.v1.json` — machine-readable status
- `.claude/plans/GPP-7-WRITE-CANDIDATE-DECISION.md` — M6 Faz 1
- `.claude/plans/GP-5.6a-DISPOSABLE-PR-WRITE-REHEARSAL.md` (if
  present) — disposable sandbox PR write rehearsal precedent
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
- `.claude/plans/GPP-7-WRITE-CANDIDATE-DECISION.md` — M6 Faz 1

## Audit Trail

| Field | Value |
|---|---|
| Implementer AI | Claude (Anthropic) |
| Reviewer AI | Codex (OpenAI) — thread `019e61ab` plan-time iter-1 AGREE for GPP-8 (single PR consolidated; Option Y authoritative; M6 pending; no aggregate entry yet; 10 forbidden actions appended including non-sandbox repo live-write + branch protection mutation guards); post-impl iter review continues after PR creation |
| Worktree | `codex/gpp-8-remote-pr-sandbox-decision` |
| Base SHA at branch open | `4c6a186` |
| Cross-provider AI review HARD RULE | satisfied (CC-2) |
| Non-author code-owner approval | required at merge time (CC-3) |
| Admin bypass attempted | `false` (CC-4) |
