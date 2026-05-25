# GPP-6b — Read-only E2E Execution Decision Path (Faz 2)

> **Status:** decision recorded; infazı reserved for GPP-6c.
> **Slice:** `GPP-6b` (Faz 2 of GPP-6; M5 Faz 2).
> **Issue:** [#627](https://github.com/Halildeu/ao-kernel/issues/627) pinned on commit per CC-13.
> **Decision:** `gpp6_keep_rehearsal_only_authoritative_no_live_adapter_execution_no_support_widening_no_production_claim`.
> **Effective:** effective on merge; the GPP-6c slice records the
> formal closeout timestamp via `completed_wps[].closed_at` and
> `milestones[M4].closed_at` once the infazı lands.

## Purpose

GPP-6b records the **closure path decision** for the read-only E2E
execution question under the autonomous GPP-6 chain. GPP-6a (Faz 1,
merged #561) installed the preflight contract + schema with
`execution_status=blocked_by_upstream_gates`. The two upstream blockers
have evolved:

- `GPP-2` protected live-adapter gate — **RESOLVED**: M1 closed
  2026-05-24 (`ao-release-gate` enforced as required check via the
  source-pinned GitHub branch ruleset `integration_id 15368`,
  `bypass_actors=[]`).
- `GPP-4` read-only adapter production decision — **PARTIALLY
  RESOLVED**: M4 closed 2026-05-25 with
  `gpp4_keep_operator_beta_authoritative` (GPP-4a + GPP-4b + GPP-4c).
  claude-code-cli lane remains Beta (operator-managed). It is **not
  production-certified read-only**; that promotion remains deferred to
  a future operator-bound Option X supersession slice.

GPP-6b chooses the authoritative decision among:

- **Option X — authorize_protected_live_e2e** (deferred,
  operator-bound)
- **Option Y — keep_rehearsal_only** (CHOSEN authoritative)
- **Option Z — defer** (REJECTED)

GPP-6c executes the chosen path. M5 milestone closes only after
GPP-6c executes; GPP-6b records the closure path decision and migrates
the GPP-4c current-closed entry into completed_wps.

This slice **does NOT**:

- flip `live_adapter_execution_allowed`, `support_widening_allowed`,
  or `production_platform_claim_allowed` (all stay `false`)
- execute a live `claude-code-cli` adapter
- mutate `scripts/gp5_platform_claim_decision.py` BC-1 status or
  `_promotion_blockers()` (reserved for GPP-6c if needed)
- update `docs/SUPPORT-BOUNDARY.md`, `docs/KNOWN-BUGS.md`, or
  `docs/PUBLIC-BETA.md` semantics for the read-only E2E lane
  (reserved for GPP-6c)
- close M5 milestone (`M5.status=pending` retained; M5 closes only
  after GPP-6c)
- mutate `ao_kernel/` public SDK signatures (CC-1)
- mutate branch protection / required status checks (CC-7)
- promote the claude-code-cli lane from Beta (operator-managed) to
  production-certified read-only

## Closure Path Comparison

Three options were considered for closing the read-only E2E execution
question under the autonomous GPP-6 chain:

### Option X — authorize_protected_live_e2e (deferred, NOT autonomous)

- **What:** operator authorizes GPP-6c to dispatch a protected
  workflow with live `claude-code-cli` adapter under the protected
  environment `ao-kernel-live-adapter-gate` and the protected secret
  handle `AO_CLAUDE_CODE_CLI_AUTH`. GPP-6c then collects three
  protected clean read-only E2E runs and one protected fail-closed
  read-only E2E run, with `evidence_class=live` artifacts.
- **Cost:** explicit `live_adapter_execution_allowed=true` flip
  (operator-only PR per CC-9), GitHub Actions secrets setup,
  cost-cap script, protected workflow dispatch, then a
  `live_adapter_execution_allowed=false` revert PR. Three operator-bound
  coordination points minimum, mirroring the GPP-3 / GPP-4 Option X
  pattern.
- **Outcome if pursued:**
  `decision_artifact = authorize_protected_live_e2e`, GPP-6c runs
  protected live E2E with live evidence. This is a separate
  supersession authority and **does not** by itself promote the
  claude-code-cli lane to production-certified read-only — that
  remains under the GPP-4 Option X supersession slot.
- **Decision:** **deferred**. Live execution requires operator
  authority and is explicitly outside the autonomous GPP-6 chain.
  GPP-6 Option X is a different supersession slot than GPP-4 Option
  X: GPP-4 Option X reclassifies the claude-code-cli lane's
  production tier; GPP-6 Option X authorizes a single protected live
  E2E rehearsal under preserved Beta tier semantics. Both remain
  available as future operator-bound supersession slices.

### Option Y — keep_rehearsal_only (CHOSEN as authoritative)

- **What:** record the GPP-6 closure path as
  **preparation/rehearsal evidence preserved** authoritatively. The
  existing readiness stack already represents what the autonomous
  GPP-6 chain can provide:
  - `GPP-6a` preflight (preparation evidence with
    `execution_status=blocked_by_upstream_gates`)
  - `GP-5.4a` read-only workflow rehearsal (`codex-stub`-only, not a
    live adapter)
  - `GP-5.7a` full production rehearsal contract
  - `GP-5.7b` full production rehearsal execution gate (simulated
    aggregation; not a production support claim)
  - `GP-5.8` operations support package
  - `GP-5.9` production platform claim decision
    (`keep_narrow_stable_runtime`)
  - GPP-4 closure (`gpp4_keep_operator_beta_authoritative`)
- **Cost:** zero new live execution. GPP-6c will:
  - record the M5 closure path explicitly in
    `gpp_status.v1.json`
  - sync `docs/SUPPORT-BOUNDARY.md`, `docs/PUBLIC-BETA.md`, and
    `docs/KNOWN-BUGS.md` for the GPP-6 closure path
  - migrate `current_wp` GPP-6b active → GPP-6c **closed**
  - move `milestones[M4]` (already done) untouched; transition
    `milestones[M5]` `pending → done` with `closed_at` and three
    evidence_refs (GPP-6a + GPP-6b + GPP-6c records)
- **Outcome:**
  `decision_artifact = keep_rehearsal_only`, M5 closed under
  "preparation/rehearsal evidence preserved" authority,
  `live_adapter_execution_allowed=false`,
  `support_widening_allowed=false`,
  `production_platform_claim_allowed=false`. The GPP-6a preflight's
  `execution_status=blocked_by_upstream_gates` remains as authoritative
  preflight semantics; the keep_rehearsal_only closure does **not**
  reclassify the preflight as
  `ready_for_protected_rehearsal`. Preflight authority defines
  blockers; the closure path defines authority over how M5 closes
  without removing those blockers.
- **Decision:** **authoritative** for GPP-6 closure under the
  autonomous path.

### Option Z — defer (REJECTED)

- **What:** record the GPP-6 decision as "deferred" and leave the
  current_wp open. M5 stays pending without a closure path commitment.
- **Risk:** `defer` is more passive than Y and leaves M5 in a grey
  state. GPP-6a preflight + GP-5.4a / GP-5.7a / GP-5.7b /
  GP-5.8 / GP-5.9 already constitute concrete preparation/rehearsal
  evidence. Promoting "defer" over "keep_rehearsal_only" would
  re-open a closed sub-question without new evidence and propagate M5
  drift to M6 (GPP-7, GPP-8, GPP-9).
- **Decision:** **rejected**. The existing preparation/rehearsal
  evidence stack is authoritative preparation evidence under the
  autonomous chain; defer would discard that authority without
  cause.

## Decision (Authoritative)

GPP-6 closes under **Option Y — keep_rehearsal_only** as the
authoritative read-only E2E execution decision. Option X
(`authorize_protected_live_e2e`) remains deferred and operator-bound;
Option Z (defer) is rejected.

Decision string:

```text
gpp6_keep_rehearsal_only_authoritative_no_live_adapter_execution_no_support_widening_no_production_claim
```

The string asserts:

- authority is `keep_rehearsal_only` (Option Y), not live evidence
- no live adapter execution under this decision
- no support widening
- no production platform claim

## Read-only E2E Closure Plan (executed in GPP-6c)

GPP-6c will:

1. Update `docs/SUPPORT-BOUNDARY.md` with a GPP-6 closure paragraph
   noting that the read-only E2E lane stays under the autonomous
   `keep_rehearsal_only` authority; live E2E remains Option X
   territory.
2. Update `docs/PUBLIC-BETA.md` to add a GPP-6 closeout decision row
   (Closeout / no support widening) and align any GP-5.4a / GP-5.7a /
   GP-5.7b rehearsal rows with the explicit "rehearsal evidence
   preserved" semantics.
3. Update `docs/KNOWN-BUGS.md` GP-5.9 closeout interpretation section
   with a GPP-6 closeout interpretation subsection (no blocker rename
   or removal).
4. Migrate `current_wp` from GPP-6b active to GPP-6c **closed**.
5. Move GPP-6b closure into `completed_wps[]`.
6. Mark `milestones[M5]` status `pending → done` with `closed_at` and
   `evidence_refs` pointing at GPP-6a / GPP-6b / GPP-6c records.
7. Open the GPP-6c CC-13 issue and pin it in `current_wp.issue`.

GPP-6c **MUST NOT**:

- flip `live_adapter_execution_allowed=true` or any other promotion
  guard flag (CC-6 enforcement)
- remove `claude_code_cli_auth_operator_managed`,
  `kb001_claude_code_cli_operator_managed_auth`,
  `kb002_gh_cli_pr_sandbox_only_live_write`,
  `gh_cli_pr_live_write_not_production_promoted`,
  `repo_intelligence_context_handoff_not_runtime_auto_fed`, or
  `protected_live_adapter_gate_unattested` from the GP-5.9
  promotion_blockers list (those remain retained under the GPP-4
  keep_operator_beta authority; GPP-6 closure does not touch them)
- promote the claude-code-cli tier from Beta (operator-managed) to
  production-certified read-only
- reclassify GPP-6a preflight `execution_status` to
  `ready_for_protected_rehearsal` (preflight authority defines
  blockers; the closure path defines closure authority, not blocker
  resolution)
- run a live `claude-code-cli` adapter on the autonomous path

## Guard Flag Invariants (unchanged after GPP-6b)

- `support_widening_allowed`: `false`
- `production_platform_claim_allowed`: `false`
- `live_adapter_execution_allowed`: `false`

## Supporting Readiness Evidence

The GPP-6b decision rests on the following readiness evidence already
in the repo:

- `scripts/gpp6_read_only_e2e_preflight.py` (GPP-6a) — preflight
  emitter
- `ao_kernel/defaults/schemas/gpp6-read-only-e2e-preflight.schema.v1.json`
  (GPP-6a) — preflight schema
- `tests/test_gpp6_read_only_e2e_preflight.py` (GPP-6a) — drift
  guards
- `scripts/gp5_read_only_rehearsal.py` (GP-5.4a) — read-only workflow
  rehearsal (`codex-stub`-only)
- `scripts/gp5_full_production_rehearsal.py` (GP-5.7b) — full
  rehearsal execution gate (simulated aggregation)
- `scripts/gp5_operations_support_package.py` (GP-5.8)
- `scripts/gp5_platform_claim_decision.py` (GP-5.9; BC-1 still
  `blocked`)
- `docs/PUBLIC-BETA.md` — current `claude-code-cli` Beta
  (operator-managed) tier wording
- `.claude/plans/GPP-4a-FAILURE-MATRIX-SCHEMA.md` /
  `.claude/plans/GPP-4b-KEEP-OPERATOR-BETA-DECISION.md` /
  `.claude/plans/GPP-4c-KEEP-OPERATOR-BETA-INFAZ.md`
- `.claude/plans/GPP-2D-7-AO-GATE-9-GPP-CLOSEOUT.md` — M1 closeout
  (ao-release-gate enforced)

This evidence stack supports — but does not authorize — protected
live E2E execution. Authority comes from the explicit GPP-6b policy
decision in this record.

## Non-Goals

This slice (GPP-6b) explicitly does NOT:

1. dispatch a protected workflow or invoke a live adapter
2. write protected E2E live evidence artifacts
3. mutate `scripts/gp5_platform_claim_decision.py`
4. update `docs/SUPPORT-BOUNDARY.md`, `docs/KNOWN-BUGS.md`, or
   `docs/PUBLIC-BETA.md` semantics (reserved for GPP-6c)
5. close the M5 milestone (M5 closes only after GPP-6c executes)
6. reclassify the GPP-6a preflight `execution_status`
7. flip any of the three GP-5/GPP-9 promotion guard flags
8. claim that the GPP-6a preflight + simulated rehearsal evidence
   equals live adapter execution evidence
9. promote the claude-code-cli lane from Beta (operator-managed)
10. mutate branch protection / required status checks
11. open the GPP-6c issue (deferred to GPP-6c slice)

All of those are GPP-6c work (or, for items requiring live execution
or production-certified read-only promotion, separate operator-bound
supersession slices).

## Supersession Rules

Option X (`authorize_protected_live_e2e`) remains available as a
future operator-bound supersession. If a later slice authorizes a
protected live read-only E2E rehearsal:

1. Operator-only PR flipping `live_adapter_execution_allowed=true`
   with a clear declaration and audit comment
2. Protected workflow dispatch with the protected environment
   `ao-kernel-live-adapter-gate` and the secret handle
   `AO_CLAUDE_CODE_CLI_AUTH`
3. Three protected clean read-only E2E runs + one protected
   fail-closed read-only E2E run with `evidence_class=live`
   artifacts; the runs use the GPP-6a preflight contract and the
   GPP-4a failure-mode matrix schema
4. Operator-only PR flipping `live_adapter_execution_allowed=false`
   back
5. A new decision record (e.g. `GPP-6d-...`) updating the M5 closure
   path or providing the live evidence trail; production-certified
   read-only promotion still requires a separate GPP-4 Option X
   supersession slot

Until that supersession lands, M5 stays at `keep_rehearsal_only` and
the guard flags remain `false`.

## Cross-References

### Core evidence

- `.claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md` —
  program SSOT
- `.claude/plans/gpp_status.v1.json` — machine-readable status
- `.claude/plans/GPP-6a-READ-ONLY-E2E-PREFLIGHT.md` — Faz 1 record
- `.claude/plans/GPP-5d-REPO-INTELLIGENCE-CLOSEOUT.md` — M2 closure
  (repo-intelligence + explicit handoff)
- `.claude/plans/GP-5.4a-GOVERNED-READ-ONLY-WORKFLOW-REHEARSAL.md` —
  read-only rehearsal contract
- `.claude/plans/GP-5.7a-FULL-PRODUCTION-REHEARSAL-CONTRACT.md` —
  full rehearsal contract
- `.claude/plans/GP-5.7b-FULL-PRODUCTION-REHEARSAL-GATE.md` — full
  rehearsal execution gate (simulated aggregation)
- `.claude/plans/GP-5.8-OPERATIONS-SUPPORT-PACKAGE.md` — operations
  package
- `.claude/plans/GP-5.9-PRODUCTION-PLATFORM-CLAIM-DECISION.md` —
  BC-1..BC-10 baseline
- `.claude/plans/GPP-4a-FAILURE-MATRIX-SCHEMA.md` — claude-code-cli
  failure-mode schema
- `.claude/plans/GPP-4b-KEEP-OPERATOR-BETA-DECISION.md` — M4 Faz 2
- `.claude/plans/GPP-4c-KEEP-OPERATOR-BETA-INFAZ.md` — M4 closeout
- `.claude/plans/GPP-2D-7-AO-GATE-9-GPP-CLOSEOUT.md` — M1 closeout
- `.claude/plans/PROGRAM-CHANGE-CONTROL.md` — CC-1..CC-13
- `docs/SUPPORT-BOUNDARY.md`
- `docs/PUBLIC-BETA.md`
- `docs/KNOWN-BUGS.md`

### Pattern precedent (not core)

- `.claude/plans/GPP-3b-BC10-CLOSURE-PATH-DECISION.md` — M3 Faz 2
  X/Y/Z decision path
- `.claude/plans/GPP-3c-BC10-EXCEPTION-INFAZ.md` — M3 Faz 3 closeout

## Audit Trail

| Field | Value |
|---|---|
| Implementer AI | Claude (Anthropic) |
| Reviewer AI | Codex (OpenAI) — thread `019e6020` plan-time iter-1 PARTIAL absorbed (progress muhasebesi wording + Option X naming `authorize_protected_live_e2e` + GPP-6c scope minimal + 5 forbidden guards added + preflight execution_status not reclassified); plan-time iter-2 AGREE; post-impl iter review continues after PR creation |
| Worktree | `codex/gpp-6b-read-only-e2e-decision` |
| Base SHA at branch open | `4fe2157` |
| Cross-provider AI review HARD RULE | satisfied (CC-2) |
| Non-author code-owner approval | required at merge time (CC-3) |
| Admin bypass attempted | `false` (CC-4) |
