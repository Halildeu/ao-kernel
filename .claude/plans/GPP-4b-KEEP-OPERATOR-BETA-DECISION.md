# GPP-4b — claude-code-cli Read-Only Production Decision (Faz 2)

> **Status:** decision recorded; infazı reserved for GPP-4c.
> **Slice:** `GPP-4b` (Faz 2 of GPP-4).
> **Issue:** pinned on commit per CC-13.
> **Decision:** `gpp4_keep_operator_beta_authoritative_no_live_adapter_execution_no_support_widening_no_production_claim`.
> **Effective:** see `gpp_status.v1.json::current_wp.closeout_at` after merge.

## Purpose

GPP-4b records the **closure path decision** for the claude-code-cli
read-only adapter promotion question under the autonomous GPP-4
chain. GPP-4a installed the schema + simulated failure-mode matrix
(7 canonical modes, evidence_class=simulated). GPP-4b chooses the
authoritative decision among `promote_read_only` /
`keep_operator_beta` / `defer`. GPP-4c executes the chosen path.

This slice **does NOT**:

- mutate `scripts/gp5_platform_claim_decision.py` (BC-1 /
  claude_code_cli_auth_operator_managed / KB-001 promotion blockers
  stay intact until GPP-4c)
- update `docs/SUPPORT-BOUNDARY.md` or `docs/KNOWN-BUGS.md` semantics
- execute a live claude-code-cli adapter
- widen support or claim production platform readiness
- flip any of the three GP-5/GPP-9 promotion guard flags

## Closure Path Comparison

Three options were considered for closing the claude-code-cli
read-only adapter production decision:

### Option X — promote_read_only (deferred, NOT autonomous)

- **What:** operator authorizes claude-code-cli for production-certified
  read-only use. Requires three protected clean live runs (GPP-4
  Acceptance §1), one protected fail-closed live run (§2), and a
  failure-mode matrix exercised against the live adapter (§3).
- **Cost:** explicit `live_adapter_execution_allowed=true` flip
  (operator-only PR per CC-9), GitHub Actions secrets setup,
  cost-cap script, protected workflow dispatch, then a
  `live_adapter_execution_allowed=false` revert PR. Three
  operator-bound coordination points minimum, similar to the GPP-3
  Option X pattern.
- **Outcome if pursued:** `decision_artifact = promote_read_only`,
  BC-1 / claude_code_cli_auth_operator_managed / KB-001 reclassified
  to `pass`, `claude-code-cli` tier widens to production-certified
  read-only.
- **Decision:** **deferred**. Live execution requires operator
  authority and is explicitly outside the autonomous GPP-4 chain. A
  future operator-bound supersession slice may pursue this
  independently; that slice would supersede this GPP-4b decision and
  reclassify the promotion blockers from "retained under
  keep_operator_beta authority" to `pass`.

### Option Y — keep_operator_beta (CHOSEN as authoritative)

- **What:** record `claude-code-cli` lane as **Beta (operator-managed)**
  authoritatively. The current `docs/PUBLIC-BETA.md` and
  `docs/SUPPORT-BOUNDARY.md` wording already pins this tier; GPP-4b
  promotes that wording to a formal GPP-4 closure path decision and
  preserves the GP-5.9 promotion blockers under this authority.
- **Cost:** zero new live execution. GPP-4c will:
  - keep `gp5_platform_claim_decision.py` BC-1 status at `blocked`
    with `claude_code_cli_auth_operator_managed` and KB-001 retained
    as promotion blockers
  - record an explicit "M4 keep_operator_beta closed" line in the
    `success_criterion.summary` text or via a new closure_path field
  - sync `docs/SUPPORT-BOUNDARY.md` and `docs/KNOWN-BUGS.md` to
    reflect the GPP-4 closure path
  - migrate `current_wp` to GPP-4c closed and mark M4 done
- **Outcome:** `decision_artifact = keep_operator_beta`, promotion
  blockers retained but reframed as "M4 closure preserved them under
  keep_operator_beta authority", `live_adapter_execution_allowed=false`,
  `support_widening_allowed=false`, `production_platform_claim_allowed=false`.
- **Decision:** **authoritative** for GPP-4 closure under the
  autonomous path.

### Option Z — defer (REJECTED)

- **What:** record the GPP-4 decision as "deferred" and leave the
  current_wp open. M4 stays pending.
- **Risk:** `defer` is more passive than Y and leaves M4 in a grey
  state. GPP-4 is an upstream gate for GPP-6 (Read-only production
  E2E), so "decision deferred" cascades the M4 drift to M5 / M6 /
  M9.
- **Decision:** **rejected**. The existing repo truth already states
  `claude-code-cli` lane is Beta (operator-managed); the GP-3.5
  decision record (closed under GP-5) made the same call. Promoting
  "defer" over "keep_operator_beta" would re-open a closed question
  without new evidence.

## Decision (Authoritative)

GPP-4 closes under **Option Y — keep_operator_beta** as the
authoritative read-only adapter production decision. Option X
(promote_read_only) remains deferred and operator-bound; Option Z
(defer) is rejected.

Decision string:

```text
gpp4_keep_operator_beta_authoritative_no_live_adapter_execution_no_support_widening_no_production_claim
```

The string asserts:

- Authority is keep_operator_beta (Option Y), not live evidence
- No live adapter execution under this decision
- No support widening
- No production platform claim

## claude-code-cli Lane Reclassification Plan (executed in GPP-4c)

GPP-4c will:

1. Update `scripts/gp5_platform_claim_decision.py` BC-1 criterion
   summary text to cite the GPP-4b closure path (keep_operator_beta
   authoritative) while keeping `status="blocked"` and
   `claude_code_cli_auth_operator_managed` + KB-001 in the blockers
   list (Codex iter-1 recommendation: retained under authority, not
   cleared).
2. Update `docs/SUPPORT-BOUNDARY.md` and `docs/KNOWN-BUGS.md`
   wording for the claude-code-cli lane to reference the GPP-4b
   keep_operator_beta decision.
3. Migrate `current_wp` from GPP-4b active to GPP-4c **closed**.
4. Move GPP-4a + GPP-4b closures into `completed_wps`.
5. Mark `milestones[M4]` status `pending → done` with `closed_at`
   and `evidence_refs` pointing at GPP-4a / GPP-4b / GPP-4c records.
6. Open the GPP-4c CC-13 issue and pin it in `current_wp.issue`.

GPP-4c **MUST NOT**:

- flip `live_adapter_execution_allowed=true` or any other promotion
  guard flag (CC-6 enforcement)
- remove `claude_code_cli_auth_operator_managed` or KB-001 from the
  GP-5.9 promotion_blockers list (those are retained under the
  keep_operator_beta authority; only an operator-bound Option X
  supersession slice may clear them)
- promote the claude-code-cli tier from Beta (operator-managed) to
  production-certified read-only
- run a live claude-code-cli adapter on the autonomous path

## Guard Flag Invariants (unchanged after GPP-4b)

- `support_widening_allowed`: `false`
- `production_platform_claim_allowed`: `false`
- `live_adapter_execution_allowed`: `false`

## Supporting Readiness Evidence

The GPP-4b decision rests on the following readiness evidence
already in the repo:

- `ao_kernel/defaults/schemas/claude-code-cli-failure-mode.schema.v1.json`
  (GPP-4a) — aggregate matrix schema with seven canonical failure
  modes enforced via schema-level `contains` invariants
- `scripts/claude_code_cli_failure_mode_evidence.py` (GPP-4a) —
  emit-simulated + validate CLI modes
- `tests/test_claude_code_cli_failure_mode_evidence.py` (GPP-4a) —
  26 drift guards
- `tests/test_claude_code_cli_smoke.py` and
  `ao_kernel/real_adapter_smoke.py` (auth_missing, binary_missing,
  prompt_denied surfaces)
- `tests/test_claude_code_cli_workflow_smoke.py` and
  `ao_kernel/real_adapter_workflow_smoke.py` (timeout,
  malformed_output, policy_denied, redaction surfaces)
- `docs/PUBLIC-BETA.md` — current `claude-code-cli` Beta
  (operator-managed) tier wording
- `.claude/plans/GP-3.5-CLAUDE-CODE-CLI-SUPPORT-BOUNDARY-DECISION.md`
  — prior GP-3.5 keep_operator_beta decision under GP-5

This evidence stack supports — but does not authorize — production
promotion. Authority comes from the explicit GPP-4b policy decision
in this record.

## Supersession Rules

Option X (promote_read_only) remains available as a future
operator-bound supersession. If a later slice authorizes a live
claude-code-cli adapter run:

1. Operator-only PR flipping `live_adapter_execution_allowed=true`
   with a clear declaration and audit comment
2. Protected workflow + cost-cap + N-call limits + secrets setup
3. Three protected clean live runs + one protected fail-closed run
   with evidence artifacts of `evidence_class=live` against the
   GPP-4a failure-mode matrix schema
4. Operator-only PR flipping `live_adapter_execution_allowed=false`
   back
5. A new decision record (e.g. `GPP-4d-...` or `GPP-5-...`) updating
   `gp5_platform_claim_decision.py` BC-1 to `status="pass"` and
   removing `claude_code_cli_auth_operator_managed` and KB-001 from
   the promotion_blockers list

Until that supersession lands, M4 stays at `keep_operator_beta` and
the guard flags remain `false`.

## Non-Goals

This slice (GPP-4b) explicitly does NOT:

1. mutate `scripts/gp5_platform_claim_decision.py`
2. update `docs/SUPPORT-BOUNDARY.md` or `docs/KNOWN-BUGS.md`
3. close the M4 milestone (M4 closes only after GPP-4c executes)
4. execute a live claude-code-cli adapter
5. flip any guard flag
6. open the GPP-4c issue (deferred to GPP-4c slice)
7. claim that the GPP-4a simulated matrix equals live adapter
   evidence

All of those are GPP-4c work.

## Cross-References

- `.claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md` — program SSOT
- `.claude/plans/gpp_status.v1.json` — machine-readable status
- `.claude/plans/GPP-4a-FAILURE-MATRIX-SCHEMA.md` — Faz 1 record
- `.claude/plans/GP-5.9-PRODUCTION-PLATFORM-CLAIM-DECISION.md` — BC-1..BC-10 baseline
- `.claude/plans/GP-3.5-CLAUDE-CODE-CLI-SUPPORT-BOUNDARY-DECISION.md` — prior keep_operator_beta decision
- `.claude/plans/PROGRAM-CHANGE-CONTROL.md` — CC-1..CC-13
- `ao_kernel/defaults/schemas/claude-code-cli-failure-mode.schema.v1.json`
- `scripts/claude_code_cli_failure_mode_evidence.py`
- `scripts/gp5_platform_claim_decision.py` (to be touched in GPP-4c)

## Audit Trail

| Field | Value |
|---|---|
| Implementer AI | Claude (Anthropic) |
| Reviewer AI | Codex (OpenAI) — thread `019e5eab` plan-time iter-1 AGREE (continues from GPP-4a) |
| Worktree | `codex/gpp-4b-keep-operator-beta-decision` |
| Base SHA at branch open | `aafc222` |
| Cross-provider AI review HARD RULE | satisfied (CC-2) |
| Non-author code-owner approval | required at merge time (CC-3) |
| Admin bypass attempted | `false` (CC-4) |
