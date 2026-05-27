# RI-7.8b-bc1-6a — Operator Execution-Window Authorization (no execution, no flag flip)

**Status:** authorization-contract-only slice (no execution permission)
**Date:** 2026-05-28
**Parent:** `RI-7-REPO-INTELLIGENCE-TIER-PROMOTION-READINESS.md`
**Predecessor:** `RI-7.8a-LIVE-EVIDENCE-PRE-AUTHORIZATION.md` (PR #673 MERGED, commit `a6cd89c`)
**B-path slice:** 6a of 8 (after RI-7.8a MERGED; 6b activation + 6c closure are separate slices)
**Authority:** explicit operator (`Halildeu`) GitHub PR review + commit trailers + cross-AI peer review
**Decision:** `ri78b_bc1_6a_execution_window_authorization_recorded_no_execution_no_guard_flag_flip`
**Support impact:** none — guard flags const false
**Production platform claim:** false
**Support widening:** false
**Live adapter execution:** false (NOT authorized by this slice; 6b activation only)
**Codex plan-time iter:** thread `019e6ba0-ee03-7e90-b069-057267be13ed` iter-2 AGREE (iter-1 PARTIAL absorbed)

## 1. Purpose

RI-7.8b-bc1-6a records the **operator's execution-window authorization contract** for a future RI-7.8b-bc1 protected live-adapter attestation. This slice is **authorization-contract only**: it does NOT permit workflow dispatch, workflow creation, adapter execution, cost-incurring calls, or any guard flag flip.

This slice does **NOT**:

- flip `support_widening`, `production_platform_claim`, or `live_adapter_execution`
- mutate `.claude/plans/gpp_status.v1.json`
- mutate the 9-key RI-7 readiness manifest (`RI-7-EVIDENCE-MANIFEST.v1.json`)
- mutate `.claude/plans/RI-7.8-EVIDENCE-MANIFEST.v1.json` (submanifest UNCHANGED in 6a — BC-1 key flip belongs to 6c)
- create or touch `.github/workflows/bc1-protected-live-adapter-attestation.yml` (workflow creation belongs to 6b)
- mutate `.github/workflows/`, `ao_kernel/ao_release_gate.py`, `scripts/local_gpp_gate.py`, or `scripts/repo_intelligence_tier_promotion_readiness.py`
- mutate `scripts/gp5_platform_claim_decision.py`
- mutate `ao_kernel/mcp_server.py`, `ao_kernel/__init__.py`, `ao_kernel/defaults/policies/`
- mutate `docs/PUBLIC-BETA.md`, `docs/SUPPORT-BOUNDARY.md`, `docs/KNOWN-BUGS.md`
- mutate `ao_kernel/defaults/schemas/local-gpp-gate-evidence.schema.v1.json`
- mutate `.claude/plans/RI-7.8a-LIVE-EVIDENCE-PRE-AUTHORIZATION.v1.json` (predecessor evidence immutable)

## 2. Authorization Contract Scope

The operator records an **authorization contract envelope** for a bounded future BC-1 execution window:

### Window contract (pre-activation)

- **status**: `authorized_pending_6b_activation` (no active window yet)
- **authorization_valid_until**: 2026-06-04T12:00:00Z (operator-bound, +168h = 7 days)
- **max_activation_delay_hours**: 168 (1 week to activate or contract expires)
- **max_execution_window_duration_hours**: 24 (once activated, window closes within 24h)
- **max_run_count**: 5 (BC-1 attestation runs)
- **max_usd**: 5.00 (bounded spend)
- **actual_start_at**: null (6b sets this on activation)
- **actual_end_at**: null (6c sets this on closure)
- **activation_owner_slice**: `RI-7.8b-bc1-6b`
- **contract_status**: `expected_unresolved_until_6b`

### Protected environment (expected, not observed)

- **env_name**: `ao-kernel-bc1-live-adapter-attestation` (NOT `production-*` — guard flags const false during BC-1 attestation)
- **required_reviewers_expected**: true
- **prevent_self_review_expected**: true
- **allowed_refs_expected**: `[refs/heads/main]`
- **admin_bypass_allowed_expected**: false
- **observed**: false (6a does NOT query live GitHub env API — 6b performs observation)
- **observed_at / observation_source / observed_environment_sha256**: null

### Future workflow contract (expected absent in 6a)

- **workflow_path**: `.github/workflows/bc1-protected-live-adapter-attestation.yml`
- **expected_absent_or_not_touched_in_6a**: true (invariant test verifies)
- **creation_owner_slice**: `RI-7.8b-bc1-6b`
- **workflow_sha**: null (6b binds resolved SHA)
- **allowed_ref**: `refs/heads/main`
- **expected_dispatch_inputs_allowlist**: `["scenario"]`
- **expected_forbidden_inputs**: `["api_key", "token", "secret", "credential", "password", "auth_header"]`
- **contract_status**: `expected_unresolved_until_6b`

### Closure / expiry / revocation (HARD pins)

- **authorization_expiry_action**: `authorization_auto_invalidates_if_not_activated_by_6b_within_validity_window`
- **window_end_action**: `live_adapter_execution_must_remain_false_outside_window`
- **post_window_verifier_owner**: `RI-7.8b-bc1-6c`
- **revocation_action**: `operator_may_revoke_before_6b_activation_via_new_pr_or_supersession_entry`
- **rerun_policy**: `expired_or_exceeded_runs_are_fail_closed_no_silent_retry`

### Activation requirements (6b MUST satisfy ALL)

- **activation_requires_new_operator_confirmation**: true
- **activation_requires_workflow_sha_binding**: true
- **activation_requires_protected_environment_observation**: true
- **activation_requires_guard_flag_policy_resolution**: true (GPP-9 / CC-6 supersession context for any `live_adapter_execution` flip during the window)

## 3. Successor Ownership

The actual execution window activation + live adapter call + evidence recording + closure happen across two later slices:

- `RI-7.8b-bc1-6b`: operator separately authorizes BC-1 execution window activation with fresh operator-confirmation trailer + exact workflow SHA binding + protected environment observation + guard flag policy resolution. Real `workflow_dispatch` runs against the protected environment within the bounded window.
- `RI-7.8b-bc1-6c`: pins per-run evidence (clean-attestation + fail-closed-attestation), records spend ledger, verifies post-window `live_adapter_execution=false`, flips submanifest BC-1 key false → true.

After 6a/6b/6c chain, BC-10 (RI-7.8b-bc10) records real-adapter usage/cost aggregate. After both BCs, RI-7.8c carries the final promotion decision (potentially flipping `production_platform_claim` if promote path).

## 4. Negative Authority Statement (HARD RULE)

This artifact **does not authorize**:

| Forbidden action | Rationale |
|---|---|
| `workflow_dispatch_now` | Workflow doesn't exist in 6a; dispatch belongs to 6b post-activation |
| `adapter_execution_now` | Live adapter calls belong to 6b within bounded activation window |
| `credential_reference` | No credential names or secret material in this slice |
| `cost_incurring_calls_now` | No real provider calls until 6b activation opens |
| `support_widening` | Belongs to RI-7.8c if promotion includes widening |
| `production_platform_claim` | Belongs to RI-7.8c final promote decision |
| `gpp_status_guard_flip` | Touching gpp_status.v1.json is OUT OF SCOPE for this slice |

## 5. Authority Boundary

GPP-9 remains closed under `gpp9_keep_narrow_stable_runtime_authoritative_program_closed_no_live_adapter_execution_no_support_widening_no_production_claim`. RI-7.8b-bc1-6a does NOT change that authority. The execution-window authorization is **contract record**, not authority transfer. Each of `support_widening`, `production_platform_claim`, `live_adapter_execution` remains const false.

## 6. Operator Authority (4 concurrent signals)

1. **Commit identity** — squash-merge commit author is `Halildeu`
2. **Commit trailers**:
   - `Operator-Window-Authorized-By: Halildeu`
   - `Operator-Window-Authorized-At: <ISO 8601 UTC timestamp>`
   - `Authorization-Scope: bc1_6a_execution_window_contract_only`
   - `No-Execution-Permission: true`
   - `No-Guard-Flag-Flip: support_widening=false,production_platform_claim=false,live_adapter_execution=false`
   - `Activation-Requires-Fresh-Operator-Confirmation: true`
3. **GitHub PR review approval** by `Halildeu` (non-author approval via `ao-release-gate-review`)
4. **Cross-AI peer review** final AGREE in both `local-ai-review-evidence.v1.json::reviewer.verdict` AND `RI-7.8b-bc1-6a-EXECUTION-WINDOW-AUTHORIZATION.v1.json::cross_ai_review_ref.final_verdict`

## 7. Schema-Backed Evidence Artifact

`.claude/plans/RI-7.8b-bc1-6a-EXECUTION-WINDOW-AUTHORIZATION.v1.json` validates against `ao_kernel/defaults/schemas/ri7-8b-bc1-6a-execution-window-authorization-evidence.schema.v1.json` (Draft 2020-12, strict, `additionalProperties=false` at every level).

Schema pins:
- `schema_version` / `artifact_kind` / `decision` const
- `authorization_effect` const `execution_window_authorization_recorded_no_execution_no_guard_flag_flip`
- `does_not_authorize` minItems=maxItems=7 (7 forbidden actions enumerated)
- `ri78a_predecessor_ref` (pr_number=673, commit_sha, three SHA-256 digests)
- `operator_authorization_record` (Halildeu + ISO timestamp + auditable source + scope const + no-immediate-execution const + observation_notes)
- `authorization_window_contract` (status const, validity TS, bounded caps, actual_start_at=actual_end_at=null const, owner=RI-7.8b-bc1-6b const, contract_status const)
- `protected_environment_binding` (env_name const NOT production_*, expected fields, observed=false const, null observation fields)
- `future_workflow_contract` (workflow_path const, expected_absent_or_not_touched_in_6a=true const, workflow_sha=null const, expected_* inputs)
- `closure_expiry_and_revocation_clause` (4 const actions)
- `activation_requirements` (4 const true requirements)
- `current_readiness_snapshot` (9/9 manifest true + decision const)
- `current_gpp_guard_snapshot` (all three flags false const)
- `ri78_submanifest_snapshot` (live=true, bc1=false, bc10=false, final=false const)
- `secret_boundary` const "no secret material in repo"
- `stale_replay_guard` (base_ref + head_ref + base_sha + 3 SHA-256 digests + timestamp)
- Guard flags const false (3)
- `submanifest_transition` (before.bc1=false, after.bc1=false const — UNCHANGED 6a aşamasında)
- `forbidden_change_audit.all_unchanged` const true + minItems=maxItems=16 surfaces with `contains+minContains+maxContains` per surface
- `cross_ai_review_ref` (thread_id, implementer_provider const `anthropic`, reviewer_provider const `openai`, final_verdict enum [REVISE, AGREE])

## 8. RI-7.8 Submanifest (UNCHANGED in 6a)

`.claude/plans/RI-7.8-EVIDENCE-MANIFEST.v1.json` keys:

- `live_evidence_pre_authorization_recorded`: true (RI-7.8a recorded)
- `bc1_protected_live_adapter_attestation_recorded`: **false** (HÂLÂ FALSE — 6a UNCHANGED; 6c will flip after evidence record)
- `bc10_real_adapter_usage_cost_aggregate_recorded`: false (owned by RI-7.8b-bc10)
- `final_operator_promotion_decision_recorded`: false (owned by RI-7.8c)

6a aşamasında submanifest **HÜCRE BAŞINA UNCHANGED** — sadece authorization contract artifact ekleniyor, submanifest hiç touch edilmiyor. Invariant test bunu enforce eder.

## 9. Forbidden-Change Audit (16 surfaces, exact set)

`forbidden_change_audit.forbidden_surfaces` (machine-enforced via git diff + schema `contains+minContains+maxContains`):

1. `.claude/plans/gpp_status.v1.json`
2. `scripts/gp5_platform_claim_decision.py`
3. `.github/workflows/` (existing workflows unchanged; new BC-1 workflow tracked via `future_workflow_contract.expected_absent_or_not_touched_in_6a`, not forbidden_change_audit)
4. `ao_kernel/mcp_server.py`
5. `ao_kernel/__init__.py`
6. `ao_kernel/defaults/policies/`
7. `docs/PUBLIC-BETA.md`
8. `docs/SUPPORT-BOUNDARY.md`
9. `docs/KNOWN-BUGS.md`
10. `ao_kernel/defaults/schemas/local-gpp-gate-evidence.schema.v1.json`
11. `ao_kernel/ao_release_gate.py`
12. `scripts/local_gpp_gate.py`
13. `scripts/repo_intelligence_tier_promotion_readiness.py`
14. `.claude/plans/RI-7-EVIDENCE-MANIFEST.v1.json`
15. `.claude/plans/RI-7.8a-LIVE-EVIDENCE-PRE-AUTHORIZATION.v1.json` (predecessor evidence immutable)
16. `.claude/plans/RI-7.8-EVIDENCE-MANIFEST.v1.json` (submanifest UNCHANGED in 6a)

(Note: `local-ai-review-evidence.v1.json` is NOT forbidden — it's per-PR shared cross-AI evidence. The new 6a schema + plan + evidence + invariant test are allowed surfaces.)

## 10. Cross-AI Peer Review (HARD RULE CC-2)

Implementer: claude/anthropic. Reviewer: codex/openai. Codex thread `019e6ba0-ee03-7e90-b069-057267be13ed`:

- iter-1: PARTIAL — 4 critical corrections demanded (6-signal contract, expected_* pattern, future_workflow_contract separation, exact-set forbidden audit)
- iter-2: AGREE — 8 corrections absorbed (added: env_name NOT production_*, observation null fields, expected_dispatch_inputs_allowlist + expected_forbidden_inputs, dual closure consts, activation_requires_* policy resolution, fresh 6b operator signal contract)

Post-impl review will refresh on the actual artifact + tests + schema.

## 11. Definition Of Done

Items tagged `[pre-merge]` / `[ci]` / `[external]` / `[post-merge]` per Codex iter-1 absorb pattern (RI-7.1).

1. `[pre-merge]` This plan exists and records authority + authorization contract scope + negative authority + 4-signal model + forbidden audit + 16 surfaces + cross-AI pattern + activation_requires_* contract
2. `[pre-merge]` Schema-backed evidence artifact validates with zero errors
3. `[pre-merge]` `future_workflow_contract.expected_absent_or_not_touched_in_6a` enforced: workflow file does NOT exist in 6a PR
4. `[pre-merge]` `expected_dispatch_inputs_allowlist ∩ expected_forbidden_inputs == ∅` invariant test
5. `[pre-merge]` 9-key RI-7 readiness manifest untouched (test enforced)
6. `[pre-merge]` RI-7.8 submanifest UNCHANGED in 6a (test enforced — all 4 keys at predecessor values)
7. `[pre-merge]` `gpp_status.v1.json` untouched (test enforced + forbidden surface)
8. `[pre-merge]` RI-7.8a predecessor evidence untouched (test enforced + forbidden surface)
9. `[pre-merge]` Negative schema tests: `authorization_effect != const` rejected; `window_status != "authorized_pending_6b_activation"` rejected; `actual_start_at|actual_end_at != null` rejected; `observed != false` rejected; `support_widening/production_platform_claim/live_adapter_execution=true` rejected
10. `[pre-merge]` Invariant test suite passes (~16 tests)
11. `[external]` Cross-AI peer review final verdict = AGREE in BOTH artifacts (cross-artifact equality enforced)
12. `[ci]` CI fully green (event-gate, lint, typecheck, tests, coverage, packaging-smoke, container-smoke, ao-release-gate-technical, ao-release-gate-review)
13. `[external]` Operator review approval via `ao-release-gate-review`
14. `[post-merge]` Squash commit carries 6 verification trailers
15. `[post-merge]` Readiness gate output unchanged: `ready_for_operator_promotion_decision`, guard flags still all false
16. `[post-merge]` RI-7.8 submanifest STILL has bc1_protected_live_adapter_attestation_recorded=false (6c will flip later)

## 12. Non-Goals

1. No guard flag flip
2. No live adapter execution
3. No workflow_dispatch authorization
4. No workflow file creation/touch (BC-1 workflow path)
5. No credential reference
6. No cost-incurring call
7. No `gpp_status.v1.json` mutation
8. No 9-key readiness manifest mutation
9. No RI-7.8 submanifest mutation (UNCHANGED — 6c will flip BC-1 key)
10. No RI-7.8a predecessor evidence mutation
11. No protected workflow / ao-release-gate runtime change
12. No SDK signature change
13. No public boundary doc edit
14. No MCP repo-intelligence tool exposure
15. No context-compiler auto-feed
16. No root authority file write
17. Repo-intelligence Beta/experimental status unchanged
18. No live GitHub env API query (observation_owner_slice = RI-7.8b-bc1-6b)
19. No workflow SHA binding (workflow_sha=null; binding_owner = RI-7.8b-bc1-6b)
20. No production_* env naming (env_name = ao-kernel-bc1-live-adapter-attestation)

## 13. Exit Decision

`ri78b_bc1_6a_execution_window_authorization_recorded_no_execution_no_guard_flag_flip`
