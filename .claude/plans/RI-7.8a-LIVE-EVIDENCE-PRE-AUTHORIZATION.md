# RI-7.8a — Operator Live-Evidence Pre-Authorization

**Status:** operator-bound pre-authorization slice (no execution permission)
**Date:** 2026-05-28
**Parent:** `RI-7-REPO-INTELLIGENCE-TIER-PROMOTION-READINESS.md`
**B-path slice:** 5 of 8 (after slices 1-3 MERGED + slice 4 checkpoint)
**Authority:** explicit operator (`Halildeu`) GitHub PR review + commit trailers + cross-AI peer review
**Decision:** `ri78a_live_evidence_pre_authorization_recorded_no_guard_flag_flip_no_execution`
**Support impact:** none — guard flags const false
**Production platform claim:** false
**Support widening:** false
**Live adapter execution:** false (NOT authorized by this slice)
**Codex plan-time iter:** thread `019e6b74-d8a6-7e92-9f2a-6064d3d80918` AGREE conditional on the required changes absorbed below

## 1. Purpose

RI-7.8a records the **operator's pre-authorization** for the upcoming live evidence collection chain (RI-7.8b-bc1 + RI-7.8b-bc10). This slice is **pre-authorization only**: it does NOT permit workflow dispatch, protected credential reference, adapter execution, cost-incurring calls, or any guard flag flip.

This slice does **NOT**:

- flip `support_widening`, `production_platform_claim`, or `live_adapter_execution`
- mutate `.claude/plans/gpp_status.v1.json`
- mutate the 9-key RI-7 readiness manifest (`RI-7-EVIDENCE-MANIFEST.v1.json`)
- mutate `.github/workflows/`, `ao_kernel/ao_release_gate.py`, `scripts/local_gpp_gate.py`, or `scripts/repo_intelligence_tier_promotion_readiness.py`
- mutate `scripts/gp5_platform_claim_decision.py`
- mutate `ao_kernel/mcp_server.py`, `ao_kernel/__init__.py`, `ao_kernel/defaults/policies/`
- mutate `docs/PUBLIC-BETA.md`, `docs/SUPPORT-BOUNDARY.md`, `docs/KNOWN-BUGS.md`

## 2. Pre-Authorization Scope

The operator pre-authorizes a **bounded future live evidence collection envelope** for two BCs:

### BC-1 (protected gate attestation)

- **Owner**: RI-7.8b-bc1 (next slice)
- **Scope**: attest protected gate behavior under live `ao-release-gate` workflow
- **Run count**: bounded (max 5 distinct workflow runs)
- **Protected environment**: required (no plaintext credentials in repo)
- **Expected paths**: clean-attestation + fail-closed (each path attested at least once)
- **Artifact schema**: separate per-BC schema in RI-7.8b-bc1 slice

### BC-10 (real-adapter usage/cost)

- **Owner**: RI-7.8b-bc10 (next-next slice)
- **Scope**: aggregate real-adapter usage + cost across approved provider/model allowlist
- **Run count**: bounded (max calls per the execution budget below)
- **Pricing source**: provider canonical pricing reference at evaluation timestamp
- **Spend ledger binding**: required (each call recorded with ts + provider + model + tokens + USD)
- **Artifact schema**: separate per-BC schema in RI-7.8b-bc10 slice

### Execution budget (per BC, pre-authorized envelope)

- `max_calls`: 50 per BC
- `max_usd`: 5.00 per BC, aggregate budget 10.00
- `model_allowlist`: provider canonical defaults (e.g. anthropic + openai), no fine-tuned models
- `validity_window_hours`: 168 (one week from operator signing)
- `expiry_action`: pre-authorization auto-invalidates if BC slices not opened within validity window

## 3. Successor Ownership

The actual live evidence collection slices (RI-7.8b-bc1 + RI-7.8b-bc10) each carry **their own explicit operator execution-window authorization**. This pre-authorization is necessary but NOT sufficient for live execution.

- `RI-7.8b-bc1`: operator separately authorizes BC-1 execution window; flips `live_adapter_execution` to true ONLY during BC-1 evidence collection; pins protected gate attestation evidence with `evidence_class=live`.
- `RI-7.8b-bc10`: operator separately authorizes BC-10 execution window; flips `live_adapter_execution` to true ONLY during BC-10 evidence collection; pins real-adapter usage/cost aggregate with `evidence_class=live`.
- `RI-7.8c`: final promotion decision. `production_platform_claim` flip ONLY here (if promote path); `support_widening` flip ONLY here (if widening path).

## 4. Negative Authority Statement (HARD RULE)

This artifact **does not authorize**:

| Forbidden action | Rationale |
|---|---|
| `protected_workflow_dispatch` | Workflow execution belongs to RI-7.8b execution-window slices |
| `adapter_execution` | Live adapter calls belong to RI-7.8b BC slices |
| `credential_reference` | No credential names or secret material |
| `cost_incurring_calls` | No real provider calls until RI-7.8b execution window opens |
| `support_widening` | Belongs to RI-7.8c if promotion includes widening |
| `production_platform_claim` | Belongs to RI-7.8c final promote decision |
| `gpp_status_guard_flip` | Touching gpp_status.v1.json is OUT OF SCOPE for this slice |

## 5. Authority Boundary

GPP-9 remains closed under `gpp9_keep_narrow_stable_runtime_authoritative_program_closed_no_live_adapter_execution_no_support_widening_no_production_claim`. RI-7.8a does NOT change that authority. The pre-authorization is **scope record**, not authority transfer.

## 6. Operator Authority (4 concurrent signals)

1. **Commit identity** — squash-merge commit author is `Halildeu`
2. **Commit trailers**:
   - `Operator-Pre-Authorized-By: Halildeu`
   - `Operator-Pre-Authorization-At: <ISO 8601 UTC timestamp>`
   - `Pre-Authorization-Scope: BC-1, BC-10`
   - `No-Execution-Permission: true`
   - `No-Guard-Flag-Flip: support_widening=false,production_platform_claim=false,live_adapter_execution=false`
3. **GitHub PR review approval** by `Halildeu` (non-author approval via `ao-release-gate-review`)
4. **Cross-AI peer review** final AGREE in both `local-ai-review-evidence.v1.json::reviewer.verdict` AND `RI-7.8a-LIVE-EVIDENCE-PRE-AUTHORIZATION.v1.json::cross_ai_review_ref.final_verdict`

## 7. Schema-Backed Evidence Artifact

`.claude/plans/RI-7.8a-LIVE-EVIDENCE-PRE-AUTHORIZATION.v1.json` validates against `ao_kernel/defaults/schemas/ri7-8a-live-evidence-pre-authorization-evidence.schema.v1.json` (Draft 2020-12, strict, `additionalProperties=false` at every level).

Schema pins:
- `schema_version` / `artifact_kind` / `decision` const
- `operator.github_login` const `Halildeu` + ISO 8601 UTC timestamp pattern + `no_secret_assertion` const true
- `authorization_effect` const `pre_authorization_only_no_execution_permission`
- `does_not_authorize` minItems=7 (7 forbidden actions enumerated)
- `successor_slices` enum [`RI-7.8b-bc1`, `RI-7.8b-bc10`] minItems=2 maxItems=2
- `bc_scope` per-BC structured object (BC-1 + BC-10)
- `execution_budget` (max_calls, max_usd, model_allowlist, validity_window_hours)
- `required_future_guard_transition` const "actual live collection requires later operator-bound execution-window artifact/PR"
- `current_readiness_snapshot` (9/9 manifest true + digest)
- `current_gpp_guard_snapshot` (all three flags false)
- `secret_boundary` const "no secret material in repo"
- `stale_replay_guard` (base_ref + head_ref + manifest_digest + pr_number + timestamp)
- Guard flags const false
- `forbidden_change_audit.all_unchanged` const true + minItems=14 surfaces
- `cross_ai_review_ref` (thread_id, implementer_provider const `anthropic`, reviewer_provider const `openai`, final_verdict enum [REVISE, AGREE])

## 8. RI-7.8 Submanifest

A separate submanifest tracks the RI-7.8 chain sequencing **without mutating** the 9-key RI-7 readiness manifest:

`.claude/plans/RI-7.8-EVIDENCE-MANIFEST.v1.json`

Keys:
- `live_evidence_pre_authorization_recorded`: false → true (THIS slice)
- `bc1_protected_live_adapter_attestation_recorded`: false (owned by RI-7.8b-bc1)
- `bc10_real_adapter_usage_cost_aggregate_recorded`: false (owned by RI-7.8b-bc10)
- `final_operator_promotion_decision_recorded`: false (owned by RI-7.8c)

This artifact is the schema-validated tracker for RI-7.8 chain progression. The original `RI-7-EVIDENCE-MANIFEST.v1.json` stays at 9/9 true unchanged.

## 9. Forbidden-Change Audit (14 surfaces)

`forbidden_change_audit.forbidden_surfaces` (machine-enforced via git diff):

- `.claude/plans/gpp_status.v1.json`
- `scripts/gp5_platform_claim_decision.py`
- `.github/workflows/`
- `ao_kernel/mcp_server.py`
- `ao_kernel/__init__.py`
- `ao_kernel/defaults/policies/`
- `docs/PUBLIC-BETA.md`
- `docs/SUPPORT-BOUNDARY.md`
- `docs/KNOWN-BUGS.md`
- `ao_kernel/defaults/schemas/local-gpp-gate-evidence.schema.v1.json`
- `ao_kernel/ao_release_gate.py`
- `scripts/local_gpp_gate.py`
- `scripts/repo_intelligence_tier_promotion_readiness.py`
- `.claude/plans/RI-7-EVIDENCE-MANIFEST.v1.json`

(Note: `local-ai-review-evidence.v1.json` is NOT forbidden — it's per-PR shared cross-AI evidence.)

## 10. Cross-AI Peer Review (HARD RULE CC-2)

Implementer: claude/anthropic. Reviewer: codex/openai. Codex thread `019e6b74-d8a6-7e92-9f2a-6064d3d80918` returned plan-time REVISE → AGREE conditional. Required changes absorbed per §1-§9 above; post-impl review will refresh on the actual artifact + tests + schema.

## 11. Definition Of Done

Items tagged `[pre-merge]` / `[ci]` / `[external]` / `[post-merge]` per Codex iter-1 absorb pattern (RI-7.1).

1. `[pre-merge]` This plan exists and records authority + pre-authorization scope + negative authority + 4-signal model + forbidden audit + 14 surfaces + cross-AI pattern
2. `[pre-merge]` Schema-backed evidence artifact validates with zero errors
3. `[pre-merge]` RI-7.8 submanifest validates against its schema; only `live_evidence_pre_authorization_recorded` flips false → true
4. `[pre-merge]` 9-key RI-7 readiness manifest untouched (test enforced)
5. `[pre-merge]` `gpp_status.v1.json` untouched (test enforced + forbidden surface)
6. `[pre-merge]` Negative schema tests: `authorization_effect != pre_authorization_only_no_execution_permission` rejected; `support_widening/production_platform_claim/live_adapter_execution=true` rejected
7. `[pre-merge]` Invariant test suite passes (~14 tests)
8. `[external]` Cross-AI peer review final verdict = AGREE in BOTH artifacts (cross-artifact equality enforced)
9. `[ci]` CI fully green (event-gate, lint, typecheck, tests, coverage, packaging-smoke, container-smoke, ao-release-gate-technical)
10. `[external]` Operator review approval via `ao-release-gate-review`
11. `[post-merge]` Squash commit carries 5 verification trailers
12. `[post-merge]` Readiness gate output unchanged: `ready_for_operator_promotion_decision`, guard flags still all false

## 12. Non-Goals

1. No guard flag flip
2. No live adapter execution
3. No workflow dispatch authorization
4. No credential reference
5. No cost-incurring call
6. No `gpp_status.v1.json` mutation
7. No 9-key readiness manifest mutation
8. No protected workflow / ao-release-gate runtime change
9. No SDK signature change
10. No public boundary doc edit
11. No MCP repo-intelligence tool exposure
12. No context-compiler auto-feed
13. No root authority file write
14. Repo-intelligence Beta/experimental status unchanged

## 13. Exit Decision

`ri78a_live_evidence_pre_authorization_recorded_no_guard_flag_flip_no_execution`
