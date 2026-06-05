# V5 Protected Real Provider Live Calls Preflight Bundle

**Status:** current-state preflight evidence only
**Work package:** E-9-1
**Dimension:** `protected_real_provider_live_calls`
**Schema:** `ao_kernel/defaults/schemas/v5-protected-real-provider-live-calls-preflight-bundle.schema.v1.json`
**Fixture:** `tests/fixtures/epic9/v5-protected-real-provider-live-calls-preflight.current.json`

This bundle records the current protected real-provider evidence surface for
the future V5 PR-Xfinal readiness matrix. It binds the existing RI-7.8
operator pre-authorization, BC-10 execution-window contracts, dormant workflow
assets, real-adapter usage/cost schemas, and CLI-only defer decision into one
machine-checkable current-state artifact.

## Non-Authority Boundary

This bundle does not authorize:

- support widening;
- production platform claims;
- live adapter execution;
- workflow dispatch;
- billable provider calls;
- protected secret reference;
- BC-10 aggregate reclassification;
- opening PR-Xfinal.

The fixture pins `final_release_bound=false`, `workflow_dispatched=false`,
`provider_call_performed=false`, `secret_referenced=false`,
`support_widening=false`, `production_platform_claim=false`, and
`live_adapter_execution=false`.

## What Is Currently Proven

The repo has a bounded, operator-owned preflight chain for future protected
real-provider evidence:

1. `RI-7.8a-LIVE-EVIDENCE-PRE-AUTHORIZATION.md` records an operator
   pre-authorization envelope without execution permission.
2. `RI-7.8b-bc10-6a-EXECUTION-WINDOW-AUTHORIZATION.v1.json` records the
   BC-10 execution-window contract and explicitly keeps workflow dispatch,
   provider calls, secret reference, and guard flips unauthorized.
3. `RI-7.8b-bc10-6b-PROTECTED-EXECUTION-WINDOW.v1.json` records the protected
   environment, workflow binding, pricing source, model allowlist, and
   fail-closed activation requirements for the dormant BC-10 workflow.
4. `.github/workflows/bc10-real-adapter-usage-cost.yml`,
   `scripts/ri78b_bc10_activation_window.py`, and
   `scripts/bc10_run_scenarios.py` exist as preserved assets for a future
   API-mode supersession.
5. `RI-7.8b-bc10-6c-DEFER-DECISION.v1.json` and
   `RI-7.8c-FINAL-PROMOTE-DECISION.v1.json` record the current CLI-only
   decision: no billable API calls are made under the current authority, and
   the BC-10 assets remain dormant for future API-mode reactivation.

These are useful current-state assets. They are not live provider evidence.

## Why The Matrix Moves To Partial

Before this bundle, the V5 matrix only pointed this dimension at the final
checklist and marked it `not_ready`. The current repo now has enough
preflight evidence to record a partial current-state surface:

- operator pre-authorization and execution-window contracts exist;
- protected-environment and workflow-binding requirements are explicit;
- dormant workflow/script/schema assets exist and are tested;
- the current CLI-only non-promotion/defer decision is recorded;
- guard flags remain false;
- missing live/operator evidence is explicit.

This moves the dimension to `partial`, not `ready`.

## Residual Missing Evidence

The following evidence is still required for any future PR-Xfinal path:

- live evidence-class provider calls under a fresh operator-bound API-mode
  supersession;
- protected environment reviewer proof for an active execution window;
- per-call and aggregate evidence produced by actual provider calls;
- post-window deauthorization and secret-scope removal evidence;
- operator-attested final release binding for the live evidence artifacts.

Until those are present, the V5 production readiness matrix remains
incomplete.

## Cross-References

- Matrix blocker:
  `.claude/plans/V5-PRODUCTION-READINESS-MATRIX-BLOCKER.md`
- Current matrix fixture:
  `tests/fixtures/epic9/v5-production-readiness-matrix.current.json`
- RI-7.8 pre-authorization:
  `.claude/plans/RI-7.8a-LIVE-EVIDENCE-PRE-AUTHORIZATION.md`
- BC-10 authorization contract:
  `.claude/plans/RI-7.8b-bc10-6a-EXECUTION-WINDOW-AUTHORIZATION.v1.json`
- BC-10 protected execution window:
  `.claude/plans/RI-7.8b-bc10-6b-PROTECTED-EXECUTION-WINDOW.v1.json`
- BC-10 defer decision:
  `.claude/plans/RI-7.8b-bc10-6c-DEFER-DECISION.v1.json`
- Final non-promotion decision:
  `.claude/plans/RI-7.8c-FINAL-PROMOTE-DECISION.v1.json`
