# RI-7.1 — Explicit Operator Authorization Record

**Status:** operator-bound authorization slice
**Date:** 2026-05-27
**Parent:** `RI-7-REPO-INTELLIGENCE-TIER-PROMOTION-READINESS.md`
**B-path slice:** 2 of 8 (after slice-1 BC vocabulary fix, before RI-7.5 runtime semantics)
**Authority:** explicit operator (`Halildeu`) GitHub PR review + commit trailer + cross-AI peer review
**Decision:** `ri7_operator_authorization_recorded_no_guard_flag_flip`
**Support impact:** none — guard flags stay false
**Production platform claim:** false
**Support widening:** false
**Live adapter execution:** false

## 1. Purpose

RI-7.1 closes the readiness gate's **operator authorization** row by recording the named operator's explicit authorization for two independent semantics:

1. **RI supersession authorization** — the operator authorizes the repo-intelligence subsystem (`ao-kernel repo scan`, `repo index`, `repo query`) to be evaluated as a contributor to a general-purpose production platform claim under the RI-7.x program. This authorization lets RI-7.5..RI-7.8 begin collecting evidence; it does NOT itself grant a production claim.
2. **General-purpose platform claim target authorization** — the operator authorizes the general-purpose platform claim as the TARGET that RI-7.8c may evaluate (promote or non-promote). This is NOT the claim itself; the claim is granted only by RI-7.8c if its evidence chain passes.

This slice flips the corresponding two manifest keys:

- `explicit_operator_authorization`: false → true
- `general_purpose_platform_claim_authorization`: false → true

No other manifest keys are touched. The readiness gate continues to report `support_widening=false`, `production_platform_claim=false`, `live_adapter_execution=false` because this slice does not flip any guard flag.

## 2. Authority Boundary

GPP-9 remains closed under `gpp9_keep_narrow_stable_runtime_authoritative_program_closed_no_live_adapter_execution_no_support_widening_no_production_claim`. RI-7.1 does not change that authority; it only records the explicit operator authorization for downstream slices to evaluate against. The actual promotion decision belongs to RI-7.8c.

Repo-intelligence remains Beta/experimental per `docs/PUBLIC-BETA.md` and `docs/SUPPORT-BOUNDARY.md`. No public boundary surface is edited by this slice.

## 3. Authorization Record

The operator authorizes by:

1. **Commit identity** — the squash-merge commit author is `Halildeu` (the GitHub repo owner login pinned by schema `operator.github_login=const "Halildeu"`).
2. **Commit trailers** in the squash commit:
   - `Operator-Authorized-By: Halildeu`
   - `Operator-Authorization-Scope: ri_supersession,general_purpose_platform_claim_target`
   - `Operator-Authorization-At: <ISO 8601 UTC timestamp>`
   - `No-Guard-Flag-Flip: support_widening=false,production_platform_claim=false,live_adapter_execution=false`
3. **GitHub PR review approval** by `Halildeu` (non-author approval also accepted via path-sensitive review gate). The `ao-release-gate-review` required check enforces this.
4. **Cross-AI peer review** (HARD RULE CC-2): implementer claude/anthropic; reviewer codex/openai. The `local-ai-review-evidence.v1.json` artifact records the cross-AI verdict; the schema accepts `REVISE` during the iter cycle and `AGREE` on the final commit. Final AGREE is pending until the iter loop completes; the same final verdict MUST land in both `local-ai-review-evidence.v1.json::reviewer.verdict` AND `RI-7.1-OPERATOR-AUTHORIZATION.v1.json::cross_ai_review_ref.final_verdict`. The invariant test `test_ri71_cross_ai_verdicts_match_review_evidence` enforces no drift between the two artifacts.

The combination of these four signals constitutes the authority. None of them in isolation is sufficient.

## 4. Schema-Backed Evidence Artifact

`.claude/plans/RI-7.1-OPERATOR-AUTHORIZATION.v1.json` validates against `ao_kernel/defaults/schemas/ri7-operator-authorization-evidence.schema.v1.json` (Draft 2020-12, strict, `additionalProperties=false` at every level).

Required artifact fields (schema-pinned):

- `schema_version` const `ri7-operator-authorization-evidence.v1`
- `artifact_kind` const `ri7_operator_authorization_evidence`
- `decision` const `ri7_operator_authorization_recorded_no_guard_flag_flip`
- `operator.github_login` const `Halildeu`
- `operator.authorization_timestamp` ISO 8601 date-time
- `operator.no_secret_assertion` const true
- `authorization_scope` array `[ri_supersession, general_purpose_platform_claim_target]`, exactly 2 unique items
- `ri_supersession_authorized` const true
- `general_purpose_platform_claim_target_authorized` const true
- Guard flags (`support_widening`, `production_platform_claim`, `live_adapter_execution`) const false
- `context_binding.repo` const `Halildeu/ao-kernel`
- `context_binding.base_ref` const `refs/heads/main`
- `context_binding.head_ref` const `refs/heads/codex/ri-7-1-operator-authorization`
- `manifest_transition.before` and `manifest_transition.after` both pinned
- `forbidden_change_audit.all_unchanged` const true with ≥8 protected surfaces enumerated
- `cross_ai_review_ref.implementer_provider` const `anthropic`, `cross_ai_review_ref.reviewer_provider` const `openai`, `cross_ai_review_ref.final_verdict` const `AGREE`

## 5. Manifest Flip

`.claude/plans/RI-7-EVIDENCE-MANIFEST.v1.json` after this slice:

```json
{
  "explicit_operator_authorization": true,
  "general_purpose_platform_claim_authorization": true,
  "operator_verified_runtime_semantics": false,
  ...
}
```

The remaining `operator_verified_runtime_semantics` blocker is owned by RI-7.5 (next slice).

## 6. Forbidden-Change Audit

`forbidden_change_audit.forbidden_surfaces` enumerates the protected surfaces this slice MUST NOT touch:

- `.claude/plans/gpp_status.v1.json`
- `scripts/gp5_platform_claim_decision.py`
- `.github/workflows/`
- `ao_kernel/mcp_server.py`
- `ao_kernel/__init__.py`
- `ao_kernel/defaults/policies/`
- `docs/PUBLIC-BETA.md`
- `docs/SUPPORT-BOUNDARY.md`
- `docs/KNOWN-BUGS.md`

Machine-enforced via the invariant test `test_ri71_forbidden_surfaces_actually_unchanged_in_diff` (CI fail-closed in PR context).

## 7. Cross-AI Peer Review (HARD RULE CC-2)

Implementer: claude/anthropic. Reviewer: codex/openai. The Codex MCP thread id is captured in `RI-7.1-OPERATOR-AUTHORIZATION.v1.json::cross_ai_review_ref.thread_id` (the `local-ai-review-evidence.v1.json` schema does not carry a separate cross-AI ref field — it records the reviewer verdict directly in `reviewer.verdict`). The same final verdict value lands in BOTH artifacts on the final commit: `local-ai-review-evidence.v1.json::reviewer.verdict` AND `RI-7.1-OPERATOR-AUTHORIZATION.v1.json::cross_ai_review_ref.final_verdict`. During the iter loop, both carry the interim verdict (`REVISE`); the cross-artifact equality is enforced by the invariant test `test_ri71_cross_ai_verdicts_match_review_evidence`. Final AGREE is pending until the iter loop completes.

## 8. Definition Of Done

RI-7.1 is complete when ALL of the items below are checked. Items marked `[pre-merge]` are verified by the agent before PR open; `[ci]` by the workflow; `[external]` by the operator/GitHub; `[post-merge]` by the squash-merge metadata after merge lands. None are marked as already done in this plan doc — production-grade tracking treats these as runtime gates, not authoring claims (Codex iter-1 absorb).

1. `[pre-merge]` This plan exists and records the authority boundary, schema, manifest flip, forbidden-change audit, and cross-AI review pattern
2. `[pre-merge]` Schema-backed evidence artifact validates against schema with zero errors
3. `[pre-merge]` Manifest flip lands in the same PR
4. `[pre-merge]` Invariant test suite passes locally (schema valid, evidence validates, manifest transition pinned, forbidden surfaces unchanged in `git diff` against base, plan doc structure, cross-AI verdicts match, no_secret_assertion required, timestamp pattern enforced, parent plan decision string match)
5. `[external]` Cross-AI peer review final verdict = AGREE (recorded in both `local-ai-review-evidence.v1.json::reviewer.verdict` AND `RI-7.1-OPERATOR-AUTHORIZATION.v1.json::cross_ai_review_ref.final_verdict`; the invariant test asserts equality)
6. `[ci]` CI fully green (all required checks pass)
7. `[external]` Operator review approval landed via `ao-release-gate-review` required check
8. `[post-merge]` Squash-merge commit carries the four authorization trailers
9. `[post-merge]` Readiness gate output: `explicit_operator_authorization_missing` and `general_purpose_platform_claim_authorization_missing` blockers drop; `operator_verified_runtime_semantics_missing` remains (owned by RI-7.5)

## 9. Non-Goals

1. No guard flag flip (`support_widening`, `production_platform_claim`, `live_adapter_execution` all stay false)
2. No production platform claim — that decision is in RI-7.8c
3. No public boundary surface edit
4. No `gpp_status.v1.json` or `scripts/gp5_platform_claim_decision.py` change
5. No `.github/workflows/` change
6. No MCP repo-intelligence tool exposure
7. No context-compiler auto-feed
8. No root authority file write
9. Repo-intelligence Beta/experimental status remains unchanged

## 10. Exit Decision

`ri7_operator_authorization_recorded_no_guard_flag_flip`
