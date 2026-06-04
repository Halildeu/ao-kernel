# Epic 3 E-3-5 Supersession Consensus Protocol

## Status

- Work package: `E-3-5`
- Scope: process/checklist infrastructure for a future operator-bound Epic 9
  supersession PR
- Runtime impact: none
- Release authority impact: none
- Guard flags:
  - `support_widening=false`
  - `production_platform_claim=false`
  - `live_adapter_execution=false`

## Decision

E-3-5 records the minimum cross-AI consensus and evidence-pack contract that a
future support-widening supersession PR must satisfy before any flag flip can be
considered. The checklist is deliberately insufficient by itself: it is an
input to the later E-3-6 recompute validator and to a future operator-bound
Epic 9 supersession PR.

The checklist explicitly preserves the current narrow stable boundary. It does
not execute a live adapter, widen support, mutate GitHub rulesets, publish a
release, or claim production platform readiness.

## Added Artifacts

- `ao_kernel/defaults/schemas/widening-supersession-checklist.schema.v1.json`
  defines the strict JSON Schema for the checklist artifact.
- `ao_kernel/defaults/widening-supersession-checklist.v1.json` records the
  default machine-checkable checklist and assertion list.
- `tests/test_widening_supersession_checklist.py` validates the schema,
  checklist, bind-field contract, and synthetic negative evidence-pack cases.

## Protocol Minimums

The checklist requires:

1. An explicit `operator_authority.github_login` field. The legacy alias
   `operator_github_login` is rejected by `additionalProperties:false`.
2. An authorization phrase:
   `AUTHORIZE_SUPPORT_WIDENING_SUPERSESSION`.
3. Verified operator commit metadata on the future supersession PR.
4. At least two reviewers from distinct non-implementer AI providers.
5. Reviewer identities and providers disjoint from the operator and
   implementer identities.
6. `evidence_class=live` for every surface being widened.
7. Provider widening backed by at least three live integration tests across a
   seven-day evidence window.
8. Rich `artifacts[]` provenance with `run_id`, `artifact_id`, `sha256`,
   `produced_at`, and `head_sha`.
9. No legacy flat `artifact_sha256[]` field.
10. Provider verdicts pinned to `plan_digest`, `final_diff_digest`, and
    `pr_head_sha`.
11. Raw verdict hashes computed with `raw_verdict_sha256` excluded from the
    canonical payload.
12. Raw verdict transcript artifacts cross-bound through
    `raw_verdict_artifact_ref` and `raw_verdict_artifact_digest`.
13. Verdict completeness derived from raw provider verdict count, not from
    producer-written consensus claims.
14. A rollback decision tree with revert tag, revert flag, and revert evidence
    artifact steps.

## Negative Cases Covered

The test suite covers the E-3-5 adversarial cases recorded in the Epic 3
matrix:

- stale replay
- duplicate reviewer identity
- filtered negative verdict
- denominator manipulation
- seven-day window race
- final diff digest drift
- PR head SHA drift
- workflow run status/head/timestamp mismatch
- orphan artifact
- artifact missing from a declared run
- reviewer hash recomputation mismatch
- verdict binding drift
- raw verdict SHA mismatch
- raw verdict self-reference hash ambiguity
- raw verdict artifact digest mismatch
- dangling raw verdict artifact reference
- raw verdict artifact provenance drift
- operator/implementer/reviewer identity overlap
- implementer/reviewer provider overlap

## E-3-6 Boundary

E-3-5 intentionally does not implement the production recompute validator. Its
tests use a synthetic evaluator to pin the checklist's semantics without live
GitHub API calls. E-3-6 will consume this checklist and implement the actual
recompute-not-trust validator for future evidence packs.

## Non-Goals

- No support widening.
- No production platform claim.
- No live adapter execution.
- No workflow/ruleset mutation.
- No public SDK signature change.
- No GitHub API mutation.
