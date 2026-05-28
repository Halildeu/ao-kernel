# RI-7.8b-bc1-6b — Protected Execution Window Infrastructure

**Status:** infrastructure slice (operator-bound activation, no live execution in PR)
**Date:** 2026-05-28
**Parent:** `RI-7-REPO-INTELLIGENCE-TIER-PROMOTION-READINESS.md`
**Predecessor:** `RI-7.8b-bc1-6a-EXECUTION-WINDOW-AUTHORIZATION.md` (PR #675 MERGED, commit `2d49f427`)
**B-path slice:** 6b of 8
**Authority:** explicit operator (`Halildeu`) GitHub PR review + commit trailers + cross-AI peer review
**Decision:** `ri78b_bc1_6b_protected_execution_window_infrastructure_recorded_dispatch_pending_no_run_evidence_no_submanifest_flip`
**Support impact:** none — top-level guard flags const false
**Production platform claim:** false
**Support widening:** false
**Live adapter execution in PR:** false (operator dispatch post-merge)
**Codex plan-time iter:** thread `019e6bcb-6a95-7e11-8619-d1d57f2208c1` iter-2 AGREE (iter-1 PARTIAL + iter-2 REVISE absorbed)

## 1. Purpose

RI-7.8b-bc1-6b creates the **protected execution window INFRASTRUCTURE** for the upcoming BC-1 live-adapter attestation. This slice:

- Adds the new protected workflow file `.github/workflows/bc1-protected-live-adapter-attestation.yml`
- Adds the runtime activation guard `scripts/ri78b_bc1_activation_window.py`
- Adds a scoped `operator_bound_supersessions[]` entry to `.claude/plans/gpp_status.v1.json`
- Pins schema + evidence + invariant tests + cross-AI peer review

This slice does **NOT**:

- run the protected workflow (operator triggers `workflow_dispatch` post-merge)
- emit any live adapter call from CI of this PR
- record per-run evidence (lives in RI-7.8b-bc1-6c)
- flip the RI-7.8 submanifest BC-1 key (lives in RI-7.8b-bc1-6c)
- flip top-level `gpp_status` guard flags (baseline closure preserved)
- mutate the 9-key RI-7 readiness manifest (`RI-7-EVIDENCE-MANIFEST.v1.json`)

## 2. Scoped Operator-Bound Supersession Pattern (Codex iter-2 AGREE)

Top-level `gpp_status.v1.json` guard flags remain **const false** under the existing `gpp9_keep_narrow_stable_runtime_authoritative_program_closed_no_live_adapter_execution_no_support_widening_no_production_claim` decision.

Effective `live_adapter_execution_allowed` is granted **only within the scoped supersession entry**, evaluated by `scripts/ri78b_bc1_activation_window.py` at workflow runtime:

```json
"operator_bound_supersessions": [
  {
    "id": "RI-7.8b-bc1-6b",
    "status": "awaiting_operator_dispatch",
    "scope": "bc1_protected_live_adapter_attestation_only",
    "supersedes_decision": "gpp9_keep_narrow_stable_runtime_...",
    "operator_authority": {
      "operator_github_login": "Halildeu",
      "activation_recorded_at": "2026-05-28T07:08:16Z",
      "activation_source": "github.com/Halildeu/ao-kernel/pull/675#ri78b-bc1-6b-successor"
    },
    "guard_flag_policy_resolution": {
      "support_widening_allowed": false,
      "production_platform_claim_allowed": false,
      "live_adapter_execution_allowed": true,
      "effective_only_for": "RI-7.8b-bc1",
      "expires_at_iso": "2026-06-04T07:08:16Z"
    },
    "actual_start_at": null,
    "valid_until": "2026-06-04T07:08:16Z",
    "actual_end_at": null,
    "max_run_count": 5,
    "max_run_attempt": 1,
    "max_usd": 5.0,
    "max_execution_window_duration_hours": 24,
    "protected_environment_binding": {
      "env_name": "ao-kernel-bc1-live-adapter-attestation",
      "required_reviewers_required": true,
      "prevent_self_review_required": true,
      "allowed_refs": ["refs/heads/main"],
      "admin_bypass_allowed": false
    },
    "future_workflow_contract": {
      "workflow_path": ".github/workflows/bc1-protected-live-adapter-attestation.yml",
      "workflow_content_sha256": "b37d79c6...",
      "allowed_ref": "refs/heads/main",
      "expected_dispatch_inputs_allowlist": ["scenario"],
      "expected_forbidden_inputs": ["api_key", "token", "secret", "credential", "password", "auth_header"]
    },
    "closure_owner_slice": "RI-7.8b-bc1-6c",
    "rerun_policy": "expired_or_exceeded_runs_are_fail_closed_no_silent_retry"
  }
]
```

## 3. Workflow Security Contract

`.github/workflows/bc1-protected-live-adapter-attestation.yml`:

- **Trigger:** `workflow_dispatch` only (no `push`, no `pull_request`, no `schedule`)
- **Environment:** `ao-kernel-bc1-live-adapter-attestation` (GitHub protected env with required reviewer + admin_bypass=false)
- **Branch:** `refs/heads/main` only (validated at step 1)
- **Run attempt:** 1 only (reruns forbidden — fail-closed)
- **Inputs:** single `scenario` choice in `{clean_attestation, fail_closed_attestation}`
- **Forbidden inputs (HARD pin):** `api_key`, `token`, `secret`, `credential`, `password`, `auth_header`
- **Permissions (minimal):** `contents: read`, `actions: read`, `deployments: read`
- **Concurrency:** group `ri78b-bc1-protected-live-adapter-attestation`, no cancel-in-progress
- **Timeout:** 10 minutes
- **Output:** redacted JSON marker artifact only (no provider response bodies)

## 4. Runtime Fail-Closed Controls (11)

Runtime guard `scripts/ri78b_bc1_activation_window.py` exits non-zero on any of:

1. `github.ref != refs/heads/main`
2. `github.event_name != workflow_dispatch`
3. `github.run_attempt != 1`
4. `scenario` input not in `{clean_attestation, fail_closed_attestation}`
5. `workflow_content_sha256` mismatch with active supersession entry binding
6. No active supersession entry `id=RI-7.8b-bc1-6b scope=bc1_protected_live_adapter_attestation_only`
7. Entry status not in `{awaiting_operator_dispatch, active}`
8. `now_utc >= entry.valid_until` (window expired)
9. Distinct `workflow_dispatch` run count on `main` > 5 (via GitHub Actions API)
10. Top-level guard flags drift from `false` (baseline closure violated)
11. Scoped guard policy resolution drift (`support_widening=true` OR `production_platform_claim=true`)

## 5. Successor Ownership

| Slice | Owns |
|---|---|
| **RI-7.8b-bc1-6c** | Per-run evidence collection (clean + fail-closed), spend ledger, runtime fail-closed proof, window closure (`actual_end_at` + entry status="closed"), RI-7.8 submanifest BC-1 false→true flip |
| **RI-7.8b-bc10** | Real-adapter usage/cost aggregate across all approved provider/model allowlist |
| **RI-7.8c** | Final promote decision (potentially flips `production_platform_claim` if promote path) |

## 6. Negative Authority Statement (HARD RULE)

This artifact **does not authorize**:

| Forbidden action | Rationale |
|---|---|
| `submanifest_bc1_flip_now` | Submanifest BC-1 flip belongs to 6c after evidence record + closure |
| `automatic_workflow_dispatch_without_operator_action` | Workflow only runs on operator `workflow_dispatch`; CI cannot trigger it |
| `credential_reference_in_repo` | No credential names, tokens, or secret material in PR |
| `cost_incurring_calls_outside_dispatched_window` | Live calls only during operator-dispatched bounded window |
| `support_widening` | Belongs to RI-7.8c if promotion includes widening |
| `production_platform_claim` | Belongs to RI-7.8c final promote decision |

## 7. Operator Authority (4 concurrent signals)

1. **Commit identity** — squash-merge commit author is `Halildeu`
2. **Commit trailers**:
   - `Operator-Activation-Confirmed-By: Halildeu`
   - `Operator-Activation-Confirmed-At: 2026-05-28T07:08:16Z`
   - `Activation-Scope: bc1_protected_live_adapter_attestation_only`
   - `No-Live-Execution-In-PR: true`
   - `Scoped-Supersession-Entry-Id: RI-7.8b-bc1-6b`
   - `Top-Level-Guard-Flags-Const-False: true`
3. **GitHub PR review approval** by `Halildeu` (non-author approval via `ao-release-gate-review`)
4. **Cross-AI peer review** final AGREE in both `local-ai-review-evidence.v1.json::reviewer.verdict` AND `RI-7.8b-bc1-6b-PROTECTED-EXECUTION-WINDOW.v1.json::cross_ai_review_ref.final_verdict`

## 8. Schema-Backed Evidence Artifact

`.claude/plans/RI-7.8b-bc1-6b-PROTECTED-EXECUTION-WINDOW.v1.json` validates against `ao_kernel/defaults/schemas/ri7-8b-bc1-6b-protected-execution-window-evidence.schema.v1.json` (Draft 2020-12, strict, `additionalProperties=false` at every level).

Schema pins:
- `decision` / `authorization_effect` const
- `does_not_authorize` minItems=maxItems=6 enum
- `ri78a_predecessor_ref` (pr=673, digest pinned)
- `ri78b_6a_predecessor_ref` (pr=675, digest pinned)
- `operator_activation_confirmation` (Halildeu const + ISO 8601 UTC + auditable source + 6-signal)
- `workflow_binding` (workflow_path const, content sha256 raw bytes, allowed_ref const, allowlist+forbidden inputs, permissions minimal, concurrency_group const, run_attempt_one_only const)
- `protected_environment_observation` (env_name NOT production_*, required_reviewers const, admin_bypass false const, operator_manual_setup_required const, observed_at_runtime_by_6c const)
- `run_budget` (max_distinct_runs ≤ 5, max_run_attempt const 1, max_usd ≤ $5)
- `guard_flag_policy_resolution_evidence` (top-level baseline preserved const, scoped entry id/scope const, scoped flags const)
- `runtime_fail_closed_controls` minItems=9
- `current_readiness_snapshot` (9/9 true)
- `current_gpp_guard_snapshot` (all 3 false)
- `ri78_submanifest_snapshot` (predecessor state)
- `secret_boundary` const
- `stale_replay_guard` (5 sha256 digests + workflow_content_sha256 + base_sha + timestamp)
- `support_widening`, `production_platform_claim`, `live_adapter_execution` const false
- `submanifest_transition` (before=after=false; UNCHANGED in 6b)
- `forbidden_change_audit` (exact 13 surfaces, contains+minContains+maxContains per surface, all_unchanged const true)
- `cross_ai_review_ref` (provider split const)

## 9. RI-7.8 Submanifest (UNCHANGED in 6b)

`.claude/plans/RI-7.8-EVIDENCE-MANIFEST.v1.json`:
- `live_evidence_pre_authorization_recorded`: true
- `bc1_protected_live_adapter_attestation_recorded`: **false** (still — 6c will flip after evidence + closure)
- `bc10_real_adapter_usage_cost_aggregate_recorded`: false
- `final_operator_promotion_decision_recorded`: false

## 10. Forbidden-Change Audit (13 surfaces)

`forbidden_change_audit.forbidden_surfaces` machine-enforced via git diff + schema `contains+minContains+maxContains`:

1. `scripts/gp5_platform_claim_decision.py`
2. `ao_kernel/mcp_server.py`
3. `ao_kernel/__init__.py`
4. `ao_kernel/defaults/policies/`
5. `docs/PUBLIC-BETA.md`
6. `docs/SUPPORT-BOUNDARY.md`
7. `docs/KNOWN-BUGS.md`
8. `ao_kernel/defaults/schemas/local-gpp-gate-evidence.schema.v1.json`
9. `ao_kernel/ao_release_gate.py`
10. `scripts/local_gpp_gate.py`
11. `scripts/repo_intelligence_tier_promotion_readiness.py`
12. `.claude/plans/RI-7-EVIDENCE-MANIFEST.v1.json`
13. `.claude/plans/RI-7.8-EVIDENCE-MANIFEST.v1.json`

(Note: `.github/workflows/` is NOT forbidden in 6b — this PR creates the new BC-1 protected workflow. `.claude/plans/gpp_status.v1.json` is NOT forbidden — this PR adds the scoped supersession entry without flipping top-level guard flags. Existing workflows in `.github/workflows/` (event-gate, lint, test, coverage etc.) remain untouched.)

## 11. Operator Manual Setup (Pre-Dispatch Checklist)

**Operator must configure BEFORE first `workflow_dispatch`:**

1. **GitHub Settings → Environments → New environment** name: `ao-kernel-bc1-live-adapter-attestation`
2. **Required reviewers:** add `Halildeu`
3. **Prevent self-review:** **DISABLE** (single-operator dispatch+review model — `Halildeu` is both `workflow_dispatch` actor AND required reviewer; enabling self-review prevention would deadlock the run). Justified by the bounded window + run cap + content-sha256 binding + window expiry + 6c post-window restoration of baseline.
4. **Deployment branches and tags:** Selected branches → `main` only
5. **Admin bypass:** DISABLE
6. **Provider secrets** (if used by live adapter step in 6c):
   - Stored under environment secret scope (NOT repo-level)
   - Names redacted from workflow file (loaded via secrets context only)

RI-7.8b-bc1-6c verifies this manual setup via `gh api .../environments/...` at runtime and pins observation evidence including:
- `can_admins_bypass=false` (API field)
- branch policy returns `main` only
- reviewer login set includes `Halildeu`
- dispatch actor login (run trigger)
- `prevent_self_review=false` (consistent with single-operator model)

## 12. Cross-AI Peer Review (HARD RULE CC-2)

Implementer: claude/anthropic. Reviewer: codex/openai. Codex thread `019e6bcb-6a95-7e11-8619-d1d57f2208c1`:

- iter-1: PARTIAL — top-level live_adapter_execution_allowed=true YASAK, scoped supersession + workflow_content_sha256 raw bytes + run_attempt==1 + GitHub API run count + permissions minimal
- iter-2: REVISE absorbed — additive `operator_bound_supersessions[]` (schema not strict), permissions `actions: read` + `deployments: read`, run cap via `gh api` not `run_number`
- iter-2 cont: AGREE

Post-impl review will refresh on the actual artifact + tests + workflow file + activation guard script.

## 13. Definition Of Done

1. `[pre-merge]` This plan exists and records authority + infrastructure scope + negative authority + 4-signal model + forbidden audit + 13 surfaces + cross-AI pattern + operator manual setup checklist
2. `[pre-merge]` Schema-backed evidence artifact validates with zero errors
3. `[pre-merge]` Protected workflow file `.github/workflows/bc1-protected-live-adapter-attestation.yml` created with security contract enforced
4. `[pre-merge]` Runtime activation guard `scripts/ri78b_bc1_activation_window.py` created with 11 fail-closed controls
5. `[pre-merge]` `.claude/plans/gpp_status.v1.json` scoped `operator_bound_supersessions[]` entry added; top-level guard flags const false KALIYOR
6. `[pre-merge]` 9-key RI-7 readiness manifest untouched
7. `[pre-merge]` RI-7.8 submanifest UNCHANGED in 6b
8. `[pre-merge]` Negative schema tests: `top_level_baseline_preserved.live_adapter_execution_allowed=true` rejected; `scoped_live_adapter_execution_allowed=false` rejected; `submanifest_transition.after.bc1=true` rejected; guard flags const false rejected if drifted
9. `[pre-merge]` Invariant test suite passes
10. `[external]` Cross-AI peer review final verdict = AGREE in BOTH artifacts
11. `[ci]` CI fully green
12. `[external]` Operator review approval via `ao-release-gate-review`
13. `[post-merge]` Squash commit carries 6 verification trailers
14. `[post-merge]` Top-level gpp_status guard flags STILL all false
15. `[post-merge]` RI-7.8 submanifest STILL has bc1=false
16. `[post-dispatch]` Operator manually creates protected environment per §11
17. `[post-dispatch]` Operator dispatches workflow with scenario=clean_attestation (1+ runs)
18. `[post-dispatch]` Operator dispatches workflow with scenario=fail_closed_attestation (1+ runs)
19. `[deferred-to-6c]` Per-run evidence collection + spend ledger + window closure + submanifest BC-1 flip

## 14. Non-Goals

1. No live adapter execution in 6b PR
2. No CI-triggered run of the new workflow
3. No top-level guard flag flip
4. No submanifest BC-1 flip
5. No 9-key readiness manifest mutation
6. No production_* env naming (env_name = ao-kernel-bc1-live-adapter-attestation)
7. No protected env API observation (lives in 6c)
8. No spend ledger recording (lives in 6c)
9. No SDK / MCP / public boundary doc change
10. No `scripts/gpp_next.py` mutation (additive field unread is non-blocking; render update deferred)
11. No `scripts/local_gpp_gate.py` mutation (enforcement semantics preserved)
12. No `scripts/repo_intelligence_tier_promotion_readiness.py` mutation
13. No `ao_kernel/ao_release_gate.py` mutation

## 15. Exit Decision

`ri78b_bc1_6b_protected_execution_window_infrastructure_recorded_dispatch_pending_no_run_evidence_no_submanifest_flip`
