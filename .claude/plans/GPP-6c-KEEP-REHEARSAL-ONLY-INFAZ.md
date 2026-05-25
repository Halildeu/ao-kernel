# GPP-6c — Read-only E2E keep_rehearsal_only Infazı (Faz 3, M5 closeout)

> **Status:** decision executed; M5 milestone closed.
> **Slice:** `GPP-6c` (Faz 3 of GPP-6; M5 closeout).
> **Issue:** [#629](https://github.com/Halildeu/ao-kernel/issues/629) pinned on commit per CC-13.
> **Decision:** `gpp6_keep_rehearsal_only_executed_m5_closed_no_live_adapter_execution_no_support_widening_no_production_claim`.
> **Effective:** effective on merge; M5 milestone transitions
> `pending → done` and the GPP-6 chain closes under the GPP-6b
> `keep_rehearsal_only` authority.

## Purpose

GPP-6c executes the GPP-6 closure path decision recorded in
GPP-6b. GPP-6a (Faz 1, merged #561) shipped the preflight contract
+ schema (`gpp6-read-only-e2e-preflight.schema.v1.json`,
`scripts/gpp6_read_only_e2e_preflight.py`) with
`execution_status=blocked_by_upstream_gates`. GPP-6b (Faz 2, merged
#628) recorded the authoritative decision string
`gpp6_keep_rehearsal_only_authoritative_no_live_adapter_execution_no_support_widening_no_production_claim`
selecting Option Y (`keep_rehearsal_only`) over Option X
(`authorize_protected_live_e2e`, deferred operator-bound) and Option
Z (defer, rejected). GPP-6c carries that decision into the
documentation/SSOT surfaces and closes the M5 milestone.

This slice **does NOT**:

- flip any of the three GP-5/GPP-9 promotion guard flags
  (`support_widening_allowed`, `production_platform_claim_allowed`,
  `live_adapter_execution_allowed` all stay `false`)
- mutate `scripts/gp5_platform_claim_decision.py` BC-1 status or
  `_promotion_blockers()` (per GPP-6b iter-2 forbidden guard: GPP-6c
  may only sync docs/SSOT closure wording under
  `keep_rehearsal_only` authority unless a separate supersession
  decision authorizes script changes)
- promote the claude-code-cli lane from Beta (operator-managed) to
  production-certified read-only
- execute a live claude-code-cli adapter
- dispatch a protected workflow or reference
  `AO_CLAUDE_CODE_CLI_AUTH`
- reclassify GPP-6a preflight
  `execution_status=blocked_by_upstream_gates` to
  `ready_for_protected_rehearsal`
- mutate branch protection / required status checks
- modify `ao_kernel/` public SDK signatures
- mutate any JSON schema under `ao_kernel/defaults/schemas/`

## Scope (9 maddelik infaz)

1. **`docs/SUPPORT-BOUNDARY.md`** — new GPP-6 closeout paragraph
   appended after the GPP-4 closeout paragraph; the read-only E2E
   lane stays as preparation/rehearsal evidence preserved under
   `keep_rehearsal_only` authority; Option X
   (`authorize_protected_live_e2e`) supersession requirement noted;
   GPP-6 Option X slot independence from GPP-4 Option X slot recorded.
2. **`docs/PUBLIC-BETA.md`** — three locations:
   - new GPP-6 closeout decision row added with full decision string,
     three-Faz chain, and Option X supersession requirement
   - GP-5.4a (read-only workflow rehearsal) row receives a one-sentence
     additive sync: "GPP-6c preserves this as preparation/rehearsal
     evidence under `keep_rehearsal_only`; it remains non-live,
     non-production evidence."
   - GP-5.7a (full production rehearsal contract) + GP-5.7b (full
     production rehearsal execution gate) rows receive a one-sentence
     additive sync each pinning the closure semantics
3. **`docs/KNOWN-BUGS.md`** — new "GPP-6 closeout interpretation"
   subsection appended after the GPP-4 closeout subsection; KB-001
   + KB-002 + all GP-5.9 promotion blockers retained under the
   GPP-4 `keep_operator_beta` authority (GPP-6 closure does not
   touch them); Option X (`authorize_protected_live_e2e` for the
   read-only E2E lane or GPP-4 Option X for the production-certified
   read-only tier promotion) noted as the only path to clear the
   blockers.
4. **`.claude/plans/gpp_status.v1.json`** — SSOT migration:
   - `current_wp` migrated GPP-6b active → GPP-6c **closed**
   - `completed_wps[]` append GPP-6b entry (issue #627, pr #628,
     `closed_at=2026-05-25T17:30:00Z`)
   - GPP-6c **not** added to `completed_wps[]` this slice (current
     closed accounting per program convention; the next M6 opener
     slice migrates GPP-6c)
   - `milestones[M5].status` `pending → done` with
     `closed_at=2026-05-25T17:45:00Z` and three `evidence_refs`
     (GPP-6a + GPP-6b + GPP-6c records)
   - `progress_estimates.milestones`: `done_count` 5 → 6, `percent`
     71 → 86, `next_milestone_id` M5 → M6
   - `progress_estimates.wp_weighted`: `completed_wps_count` 44 →
     45 (GPP-6b moved into), `closed_current_wp_count` 0 → 1 (GPP-6c
     current closed), `completed_or_closed_count` 44 → 46, `percent`
     88 → 92
   - `forbidden_actions[]` appended four GPP-6c specific guards (docs
     sync as production claim; M5 done as Option X authorization;
     aggregate map entry as live evidence; preflight reclassification
     under the infazı)
   - `next_allowed_actions[]` revised: GPP-6 executed line replaces
     the prior "GPP-6 closure path recorded" line; blocker retention
     reworded to reflect executed state; M6 / GPP-7 / GPP-8 / GPP-9
     preparation reserved
5. **`.claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md`**
   header + §0 synced: current slice issue → #629, current slice
   record → `GPP-6c-KEEP-REHEARSAL-ONLY-INFAZ.md`, M5 closeout
   line completed, M5 status `Done` with closed date, §0 progress
   sentence updated to 6/7 milestones (86%) and 46/50 WP-weighted
   (92%); next M6.
6. **`.claude/plans/GPP-6c-KEEP-REHEARSAL-ONLY-INFAZ.md`** — this
   record.
7. **`tests/test_gpp_next.py` + `tests/test_local_gpp_gate.py`** —
   drift guards rewritten for GPP-6c closed state:
   - `current_wp.id=GPP-6c, status=closed` pin
   - `exit_decision` pin
   - `allowed_scope` anchor list (M5 closeout wording)
   - GPP-6b migrated entry assertion in completed_wps (pr=#628,
     `closed_at`)
   - GPP-6c absence from completed_wps invariant
   - `_AGGREGATE_COMPLETION_SOURCES` extended with GPP-6 entry (3
     records) plus comment refreshed to "GPP-2D, GPP-3, GPP-4, GPP-5
     and GPP-6"
   - new `test_gpp_status_m5_done_three_evidence_refs` pinning the
     M5 done state with exact three-record evidence_refs set
   - `test_gpp_status_done_milestones_have_evidence_refs` updated to
     `len(done_milestones) == 6`
   - `test_gpp_status_progress_estimates_present`: milestones
     `done_count=6`, `percent=86`, `next_milestone_id=M6`;
     wp_weighted `45/1/46`, `percent=92`
   - render text "Current WP: GPP-6c", "Current status: closed",
     progress headline "6/7 done (86%; next M6 - Production matrix
     + final claim)"
   - `test_local_gpp_gate.py` `current_wp.id=GPP-6c closed` pin
8. **`local-ai-review-evidence.v1.json`** — cross-AI peer review
   evidence (implementer Claude/Anthropic, reviewer Codex/OpenAI)
   covering guard-flag invariance, docs sync without script
   mutation, SSOT closure accounting, M5 milestone done, CC-13
   issue anchor, and cross-provider verification.

## Decision Recap

Authority is `gpp6_keep_rehearsal_only_authoritative` (Option Y) as
recorded in GPP-6b. The string asserts:

- closure under `keep_rehearsal_only`, not live evidence
- no live adapter execution under this decision
- no support widening
- no production platform claim

Alternative options:

- **Option X — authorize_protected_live_e2e**: deferred operator-bound;
  requires a separate operator-only PR flipping
  `live_adapter_execution_allowed=true`, protected workflow dispatch
  under the protected environment `ao-kernel-live-adapter-gate` and
  the protected secret handle `AO_CLAUDE_CODE_CLI_AUTH`, three
  protected clean read-only E2E runs + one protected fail-closed run
  with `evidence_class=live` artifacts. GPP-6 Option X is independent
  from GPP-4 Option X (the latter governs production-certified
  read-only tier promotion).
- **Option Z — defer**: rejected because GPP-6a preflight + the
  existing rehearsal evidence stack (GP-5.4a, GP-5.7a, GP-5.7b,
  GP-5.8, GP-5.9) is authoritative preparation evidence; defer
  would discard that authority without cause.

## Schema Versioning Discipline (CC-8)

GPP-6c **does not** change any JSON Schema enum, required field, or
contract under `ao_kernel/defaults/schemas/`. The
`gpp6-read-only-e2e-preflight.schema.v1.json` (GPP-6a) and
`gp5-production-platform-claim-decision.schema.v1.json` (GP-5.9)
schemas are unchanged (no enum widening, no required-field change).
`schema_version` stays at `v1` for both.

The CC-8 enum-widening pattern that GPP-3c used (`pass → exception`)
does not apply here because GPP-6c reclassifies no enum value.

## Non-Goals

This slice (GPP-6c) explicitly does NOT:

1. promote the claude-code-cli tier from Beta (operator-managed) to
   production-certified read-only
2. flip any of the three GP-5/GPP-9 promotion guard flags
3. execute a live claude-code-cli adapter
4. dispatch a protected workflow or reference
   `AO_CLAUDE_CODE_CLI_AUTH`
5. mutate `scripts/gp5_platform_claim_decision.py` (CC-8 + GPP-6b
   iter-2 forbidden guard: docs/SSOT closure wording only unless a
   separate supersession decision authorizes script changes)
6. mutate any JSON schema under `ao_kernel/defaults/schemas/`
7. mutate `.github/workflows/` (workflow change requires separate
   ao-release-gate / governance decision)
8. claim that the GPP-6a preflight + simulated rehearsal evidence
   (GP-5.4a / GP-5.7a / GP-5.7b) equals live adapter execution
   evidence
9. reclassify GPP-6a preflight
   `execution_status=blocked_by_upstream_gates` to
   `ready_for_protected_rehearsal`
10. remove `claude_code_cli_auth_operator_managed`,
    `kb001_claude_code_cli_operator_managed_auth`,
    `protected_live_adapter_gate_unattested`,
    `kb002_gh_cli_pr_sandbox_only_live_write`,
    `gh_cli_pr_live_write_not_production_promoted`, or
    `repo_intelligence_context_handoff_not_runtime_auto_fed` from
    the GP-5.9 promotion_blockers list (retained under the GPP-4
    `keep_operator_beta` authority; GPP-6 closure does not touch
    them)
11. open the M6 issue or pre-seed any M6 work
12. mutate branch protection or required status checks
13. modify `ao_kernel/` public SDK signatures

## Guard Flag Invariants (unchanged after GPP-6c)

- `support_widening_allowed`: `false`
- `production_platform_claim_allowed`: `false`
- `live_adapter_execution_allowed`: `false`

## Supersession Rules

Option X (`authorize_protected_live_e2e`) remains available as a
future operator-bound supersession. The supersession chain mirrors
the GPP-6b record:

1. Operator-only PR flipping
   `live_adapter_execution_allowed=true` with an explicit declaration
   and audit comment
2. Protected workflow dispatch with the protected environment
   `ao-kernel-live-adapter-gate` and the secret handle
   `AO_CLAUDE_CODE_CLI_AUTH`
3. Three protected clean read-only E2E runs + one protected
   fail-closed run with `evidence_class=live` artifacts; the runs
   use the GPP-6a preflight contract and the GPP-4a failure-mode
   matrix schema (the latter governs claude-code-cli adapter
   failure-mode coverage)
4. Operator-only PR flipping
   `live_adapter_execution_allowed=false` back
5. A new decision record (e.g. `GPP-6d-...`) updating the M5 closure
   path or providing the live evidence trail; production-certified
   read-only promotion still requires a separate GPP-4 Option X
   supersession slot

Until that supersession lands, M5 stays closed under
`keep_rehearsal_only` and the guard flags remain `false`.

## Cross-References

### Core evidence

- `.claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md` —
  program SSOT
- `.claude/plans/gpp_status.v1.json` — machine-readable status
- `.claude/plans/GPP-6a-READ-ONLY-E2E-PREFLIGHT.md` — Faz 1 record
  (dual reference: M2 preparation evidence + M5 closure-chain
  evidence)
- `.claude/plans/GPP-6b-READ-ONLY-E2E-DECISION.md` — Faz 2 record
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
- `docs/SUPPORT-BOUNDARY.md` (GPP-6 paragraph added)
- `docs/PUBLIC-BETA.md` (GPP-6 closeout row + GP-5.4a/5.7a/5.7b
  additive sync)
- `docs/KNOWN-BUGS.md` (GPP-6 closeout interpretation subsection)

### Pattern precedent (not core)

- `.claude/plans/GPP-3b-BC10-CLOSURE-PATH-DECISION.md` — M3 Faz 2
  X/Y/Z decision path
- `.claude/plans/GPP-3c-BC10-EXCEPTION-INFAZ.md` — M3 Faz 3 closeout

## Audit Trail

| Field | Value |
|---|---|
| Implementer AI | Claude (Anthropic) |
| Reviewer AI | Codex (OpenAI) — thread `019e6020` plan-time iter-1 AGREE for GPP-6c scope (Option X naming preserved, GPP-6c scope minimal docs/SSOT only, M5 evidence_refs cardinality 3, aggregate map GPP-6 entry added in this slice); post-impl iter review continues after PR creation |
| Worktree | `codex/gpp-6c-keep-rehearsal-only-infaz` |
| Base SHA at branch open | `da2f697` |
| Cross-provider AI review HARD RULE | satisfied (CC-2) |
| Non-author code-owner approval | required at merge time (CC-3) |
| Admin bypass attempted | `false` (CC-4) |
