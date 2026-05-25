# GPP-4c — claude-code-cli keep_operator_beta Infazı (Faz 3, M4 closeout)

> **Status:** decision executed; M4 milestone closed.
> **Slice:** `GPP-4c` (Faz 3 of GPP-4).
> **Issue:** [#625](https://github.com/Halildeu/ao-kernel/issues/625) pinned on commit per CC-13.
> **Decision:** `gpp4_keep_operator_beta_executed_m4_closed_no_live_adapter_execution_no_support_widening_no_production_claim`.
> **Effective:** effective on merge; M4 milestone transitions
> `pending → done` and the GPP-4 chain closes under the GPP-4b
> `keep_operator_beta` authority.

## Purpose

GPP-4c executes the GPP-4 closure path decision recorded in
GPP-4b. GPP-4a (Faz 1) shipped the claude-code-cli failure-mode matrix
schema + simulated coverage as supporting readiness. GPP-4b (Faz 2)
recorded the authoritative decision string
`gpp4_keep_operator_beta_authoritative_no_live_adapter_execution_no_support_widening_no_production_claim`
selecting Option Y (keep_operator_beta) over Option X (promote_read_only,
deferred operator-bound) and Option Z (defer, rejected). GPP-4c carries
that decision into the policy/documentation/SSOT surfaces and closes
the M4 milestone.

This slice **does NOT**:

- flip any of the three GP-5/GPP-9 promotion guard flags
  (`support_widening_allowed`, `production_platform_claim_allowed`,
  `live_adapter_execution_allowed` all stay `false`)
- remove `claude_code_cli_auth_operator_managed`,
  `kb001_claude_code_cli_operator_managed_auth`, or
  `protected_live_adapter_gate_unattested` from the GP-5.9
  promotion_blockers list (those remain retained under the
  keep_operator_beta authority)
- promote the claude-code-cli lane from Beta (operator-managed) to
  production-certified read-only
- execute a live claude-code-cli adapter
- mutate branch protection / required status checks
- modify `ao_kernel/` public SDK signatures

## Scope (9 maddelik infaz)

1. **`scripts/gp5_platform_claim_decision.py` BC-1 summary update.**
   Summary text rewritten to cite the GPP-4 closure path; evidence
   list extended to four entries (GP-5.1a baseline + GPP-4a + GPP-4b +
   GPP-4c records); `status="blocked"` retained; local
   `BC-1.blockers=["protected_live_adapter_gate_unattested"]` retained.
2. **`docs/SUPPORT-BOUNDARY.md`** — new GPP-4 closeout paragraph after
   the GPP-3c paragraph; claude-code-cli lane wording references
   `gpp4_keep_operator_beta_authoritative`.
3. **`docs/KNOWN-BUGS.md`** — new "GPP-4 closeout interpretation"
   subsection appended after GP-5.9; `KB-001` retained as
   `kb001_claude_code_cli_operator_managed_auth` promotion blocker;
   `KB-002` clarified as "operator-managed beta lane known bug; GPP-4c
   does not remove or rename any existing promotion blocker."
4. **`docs/PUBLIC-BETA.md`** — three locations updated:
   - GPP-4a row trailing sentence now points at GPP-4b decision +
     GPP-4c infazı records
   - new GPP-4 closeout decision row added with full decision string,
     three-Faz chain, and Option X supersession requirement
   - claude-code-cli Beta row receives a `GPP-4 closeout kararı
     gpp4_keep_operator_beta_authoritative` line alongside the
     existing GP-3.6 / GP-4.5 verdicts
5. **`.claude/plans/gpp_status.v1.json`** — SSOT migration:
   - `current_wp` migrated GPP-4b active → GPP-4c **closed**
   - `completed_wps[]` append GPP-4b entry (issue #623, pr #624,
     `closed_at=2026-05-25T12:44:16Z`)
   - GPP-4c **not** added to `completed_wps[]` this slice (current
     closed accounting per program convention; the next M5 opener
     slice migrates GPP-4c)
   - `milestones[M4].status` `pending → done` with
     `closed_at=2026-05-25T13:00:00Z` and three `evidence_refs`
     (GPP-4a + GPP-4b + GPP-4c records)
   - `progress_estimates.wp_weighted`: `completed_wps_count=43`,
     `closed_current_wp_count=1`, `completed_or_closed_count=44`,
     `percent=88`
   - `progress_estimates.milestones`: `done_count=5`, `percent=71`,
     `next_milestone_id="M5"`
   - `forbidden_actions[]` appended three GPP-4 specific guards
     (BC-1 summary not blocker removal; closure path not authorization
     for widening/live exec/blocker removal; M4 closure not Option X
     supersession authorization)
   - `next_allowed_actions[]` revised: GPP-4 executed line replaces
     the prior "record the GPP-4b" line; blocker retention line
     reworded to reflect executed state; M5/GPP-6 opening reserved
6. **`.claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md`**
   header + §0 synced: current slice issue → #625, current slice
   record → `GPP-4c-KEEP-OPERATOR-BETA-INFAZ.md`, M4 chain records
   completed line, M4 status `Done` with closed date, §0 progress
   table M4 → Done, current progress sentence updated to 5/7
   milestones (71%) and 44/50 WP-weighted (88%).
7. **`.claude/plans/GPP-4c-KEEP-OPERATOR-BETA-INFAZ.md`** — this
   record.
8. **`tests/test_gpp_next.py` + `tests/test_local_gpp_gate.py`** —
   drift guards rewritten for GPP-4c closed state: `current_wp.id`
   pin, `exit_decision` pin, `allowed_scope` anchor list,
   `forbidden_actions` GPP-4c guards present,
   `next_allowed_actions` execution line present,
   `_AGGREGATE_COMPLETION_SOURCES` extended with
   `"GPP-4": ["GPP-4a", "GPP-4b", "GPP-4c"]` plus comment refreshed
   from "GPP-2D, GPP-3 and GPP-5" to "GPP-2D, GPP-3, GPP-4 and GPP-5",
   M4 evidence_refs cardinality (3) pinned, `completed_wps[]` GPP-4c
   absence asserted, `wp_weighted` triple
   (`completed_wps_count=43`, `closed_current_wp_count=1`,
   `completed_or_closed_count=44`) pinned.
9. **`local-ai-review-evidence.v1.json`** — cross-AI peer review
   evidence (implementer Claude/Anthropic, reviewer Codex/OpenAI)
   covering guard-flag invariance, BC-1 summary update without
   blocker removal, SSOT closure accounting, M4 milestone done,
   docs sync, CC-13 issue anchor, and cross-provider verification.

## Decision Recap

Authority is `gpp4_keep_operator_beta_authoritative` (Option Y) as
recorded in GPP-4b. The string asserts:

- closure under `keep_operator_beta`, not live evidence
- no live adapter execution under this decision
- no support widening
- no production platform claim

Alternative options:

- **Option X — promote_read_only**: deferred operator-bound; requires a
  separate operator-only PR flipping `live_adapter_execution_allowed=true`,
  three protected clean live runs + one protected fail-closed run,
  `evidence_class=live` failure-mode matrix artifact, and a follow-up
  flip back to `false`. Any future supersession would supersede this
  GPP-4 closure and reclassify the BC-1 status from `blocked` to
  `pass`, removing the GP-5.9 promotion blockers listed above.
- **Option Z — defer**: rejected because GP-3.5 and the existing
  `docs/PUBLIC-BETA.md` + `docs/SUPPORT-BOUNDARY.md` wording already
  pin the claude-code-cli lane as Beta (operator-managed); promoting
  "defer" over Option Y would re-open a closed question without new
  evidence.

## Schema Versioning Discipline (CC-8)

GPP-4c **does not** change any JSON Schema enum, required field, or
contract under `ao_kernel/defaults/schemas/`. The
`gp5-production-platform-claim-decision.schema.v1.json` schema
contract is unchanged (no enum widening, no required-field change).
`BC-1.status="blocked"` was already in the enum from the original
schema, and the criterion only receives a longer `summary` string and
a longer `evidence` list. `schema_version` stays at `v1`.

The CC-8 enum-widening pattern that GPP-3c used (`pass → exception`)
does not apply here because GPP-4c reclassifies no enum value.

## Non-Goals

This slice (GPP-4c) explicitly does NOT:

1. promote the claude-code-cli tier from Beta (operator-managed) to
   production-certified read-only
2. flip any of the three GP-5/GPP-9 promotion guard flags
3. execute a live claude-code-cli adapter
4. mutate the failure-mode matrix schema or evidence emitter
5. remove `claude_code_cli_auth_operator_managed`,
   `kb001_claude_code_cli_operator_managed_auth`, or
   `protected_live_adapter_gate_unattested` from the GP-5.9
   promotion_blockers list
6. claim that the GPP-4a simulated matrix equals live adapter evidence
7. open the M5 / GPP-6 issue or pre-seed any M5 work
8. mutate branch protection or required status checks
9. modify `ao_kernel/` public SDK signatures

## Guard Flag Invariants (unchanged after GPP-4c)

- `support_widening_allowed`: `false`
- `production_platform_claim_allowed`: `false`
- `live_adapter_execution_allowed`: `false`

## Supersession Rules

Option X (promote_read_only) remains available as a future
operator-bound supersession. The supersession chain mirrors the
GPP-4b record:

1. Operator-only PR flipping `live_adapter_execution_allowed=true`
   with an explicit declaration and audit comment
2. Protected workflow + cost-cap + N-call limits + secrets setup
3. Three protected clean live runs + one protected fail-closed run
   with `evidence_class=live` failure-mode matrix artifacts against
   the GPP-4a schema
4. Operator-only PR flipping `live_adapter_execution_allowed=false`
   back
5. A new decision record (e.g. `GPP-4d-...` or `GPP-5-...`) updating
   `scripts/gp5_platform_claim_decision.py` BC-1 to `status="pass"`
   and removing the GP-5.9 promotion_blockers entries above

Until that supersession lands, M4 stays at `keep_operator_beta` and
the guard flags remain `false`.

## Cross-References

- `.claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md` — program SSOT
- `.claude/plans/gpp_status.v1.json` — machine-readable status
- `.claude/plans/GPP-4a-FAILURE-MATRIX-SCHEMA.md` — Faz 1 record
- `.claude/plans/GPP-4b-KEEP-OPERATOR-BETA-DECISION.md` — Faz 2 record
- `.claude/plans/GP-5.9-PRODUCTION-PLATFORM-CLAIM-DECISION.md` — BC-1..BC-10 baseline
- `.claude/plans/GP-3.5-CLAUDE-CODE-CLI-SUPPORT-BOUNDARY-DECISION.md` — prior keep_operator_beta decision
- `.claude/plans/PROGRAM-CHANGE-CONTROL.md` — CC-1..CC-13
- `scripts/gp5_platform_claim_decision.py` (BC-1 summary updated)
- `docs/SUPPORT-BOUNDARY.md` (GPP-4 paragraph added)
- `docs/KNOWN-BUGS.md` (GPP-4 closeout interpretation subsection)
- `docs/PUBLIC-BETA.md` (three GPP-4 references synced)

## Audit Trail

| Field | Value |
|---|---|
| Implementer AI | Claude (Anthropic) |
| Reviewer AI | Codex (OpenAI) — thread `019e5f2f` plan-time iter-1 PARTIAL absorbed (`current_wp.status=closed` vs `completed_wps[].id=GPP-4c` mutual exclusion + `closed_current_wp_count=1` + BC-1 summary tightened + KB-002 wording clarified + Option X supersession guard added); plan-time iter-2 AGREE; post-impl iter-1 AGREE (no merge-blocker; 2 hygiene notes absorbed in iter-2 commit: aggregate handling comment + audit trail "post-impl iter-1 AGREE" wording) |
| Worktree | `codex/gpp-4c-keep-operator-beta-infaz` |
| Base SHA at branch open | `58376df` |
| Cross-provider AI review HARD RULE | satisfied (CC-2) |
| Non-author code-owner approval | required at merge time (CC-3) |
| Admin bypass attempted | `false` (CC-4) |
