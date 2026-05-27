# RI-7 - Repo-Intelligence Tier Promotion Readiness

**Status:** ready for PR / no support widening
**Branch:** `codex/repo-intelligence-tier-promotion-supersession`
**Decision artifact:** `repo_intelligence_tier_promotion_readiness`
**Support impact:** none in this slice

## Purpose

This slice starts the operator-bound supersession path for using the explicit
repo-intelligence scan/index/query surface as part of a future
general-purpose production platform claim.

The requested target is narrow: production-supported explicit handoff for:

1. `repo scan` local repo-intelligence artifact generation;
2. `repo index --dry-run` write planning;
3. `repo index --write-vectors` explicit vector writes with confirmation,
   namespace isolation, and stale cleanup;
4. `repo query` read-only vector retrieval.

This slice does not grant that claim. A repo-intelligence-only evidence package
is not enough for a general-purpose production platform claim; the later
decision must also consume cross-lane production matrix evidence for real
adapter, read-only E2E, controlled write-side, remote PR write, rollback, cost,
and release-governance semantics. This slice also does not make
repo-intelligence a hidden runtime prompt feed.

## Current Authority

GPP-9 is closed under:

```text
gpp9_keep_narrow_stable_runtime_authoritative_program_closed_no_live_adapter_execution_no_support_widening_no_production_claim
```

The current authority keeps these flags closed:

```text
support_widening_allowed=false
production_platform_claim_allowed=false
live_adapter_execution_allowed=false
```

Therefore this readiness slice does not flip those flags and does not edit the
current public support tier. A later promotion decision PR must consume passing
evidence before any public boundary changes.

## Readiness Gate

The read-only gate is:

```bash
python3 scripts/repo_intelligence_tier_promotion_readiness.py --output text
```

Without an evidence manifest, the expected result is blocked:

```text
overall_status: blocked
decision: blocked_operator_bound_evidence_required
support_widening: false
production_platform_claim: false
live_adapter_execution: false
```

The gate can become `ready_for_operator_decision` only when an explicit
evidence manifest records all required gates as true. Even then, the readiness
artifact still carries `support_widening=false` and
`production_platform_claim=false`; the later promotion decision owns any
support-boundary transition and any GP-5.9 BC-1..BC-10 reclassification.

## Required Evidence

Promotion readiness requires:

1. explicit operator authorization for this supersession;
2. explicit operator authorization for the general-purpose production platform
   claim target;
3. guardrail hardening matrix for AST/chunk edge cases, namespace isolation,
   stale vector cleanup, no-root-write, no-auto-feed, and no-MCP exposure;
4. configured vector backend E2E evidence for explicit writes, stale cleanup,
   namespace isolation, read-only query hash/line validation, and fail-closed
   missing-backend paths;
5. wheel-installed scan/index/query packaging smoke outside the source checkout;
6. operator-verified runtime semantics proving the surface does not create
   hidden prompt injection;
7. cross-lane production matrix evidence for all non-repo-intelligence lanes
   required by a general-purpose production platform claim;
8. GP-5.9 BC-1..BC-10 reclassification plan;
9. prepared support-boundary, known-bugs, and platform-claim transition text for
   the later decision PR.

## Tracking Board

Canonical tracking rule: each row below must close with one issue, one
short-lived `codex/*` branch, one PR, one exit decision, and at least one
evidence artifact reference. Rows may close only in order unless a later row is
explicitly marked as independent.

| ID | Status | Purpose | Required artifact | Exit decision |
|---|---|---|---|---|
| `RI-7.0` | ready for PR | Land the no-widening readiness gate and this tracking plan | `scripts/repo_intelligence_tier_promotion_readiness.py`, schema, tests, this plan | `ri7_readiness_gate_landed_blocked_no_support_widening` |
| `RI-7.1` | pending | Record explicit operator authorization for the RI supersession and the general-purpose platform claim target | operator authorization record under `.claude/plans/` plus evidence manifest update | `ri7_operator_authorization_recorded_no_guard_flag_flip` |
| `RI-7.2` | pending | Close repo-intelligence guardrail hardening matrix | matrix report covering AST/chunk edge cases, namespace isolation, stale vector cleanup, no-root-write, no-auto-feed, no-MCP exposure | `ri7_guardrail_hardening_matrix_ready` |
| `RI-7.3` | pending | Prove configured vector backend E2E behavior | vector E2E evidence report for write, stale cleanup, namespace isolation, query hash/line validation, fail-closed missing backend/key | `ri7_vector_backend_e2e_ready` |
| `RI-7.4` | pending | Prove wheel-installed scan/index/query behavior outside the source checkout | packaging smoke report from fresh venv / installed wheel | `ri7_scan_index_query_packaging_smoke_ready` |
| `RI-7.5` | pending | Record operator-verified runtime semantics | operator sign-off plus behavior evidence proving no hidden prompt injection, no auto-feed, no root write | `ri7_runtime_semantics_verified` |
| `RI-7.6` | pending | Close cross-lane production matrix evidence | evidence matrix for real adapter, read-only E2E, controlled write-side, remote PR write, rollback, cost, release governance | `ri7_cross_lane_production_matrix_ready` |
| `RI-7.7` | pending | Prepare GP-5.9 BC-1..BC-10 reclassification and support-boundary transition | BC reclassification plan plus `PUBLIC-BETA`, `SUPPORT-BOUNDARY`, `KNOWN-BUGS`, GP-5.9 transition plan | `ri7_gp59_transition_plan_ready` |
| `RI-7.8` | blocked by `RI-7.1`..`RI-7.7` | Operator promotion decision PR consumes all evidence | passing readiness manifest, GP-5.9 decision update, `gpp_status` flag flips, docs sync | `promote_general_purpose_production_platform` or explicit non-promotion decision |

## Evidence Manifest Contract

The readiness gate consumes a JSON manifest through:

```bash
python3 scripts/repo_intelligence_tier_promotion_readiness.py \
  --evidence-manifest .claude/plans/RI-7-EVIDENCE-MANIFEST.example.json \
  --output text
```

The example manifest is intentionally all `false`; it is a tracking template,
not passing evidence. A row may change from `false` to `true` only in the PR
that lands the named evidence artifact and updates this tracking board.

## Definition Of Done

`RI-7.0` is done when:

1. the readiness gate returns `blocked_operator_bound_evidence_required` without
   an evidence manifest;
2. the schema rejects any readiness artifact that carries
   `support_widening=true`, `production_platform_claim=true`, or
   `live_adapter_execution=true`;
3. this tracking board and the example manifest are present;
4. the focused tests pass;
5. forbidden surfaces remain untouched:
   `.claude/plans/gpp_status.v1.json`,
   `scripts/gp5_platform_claim_decision.py`, `.github/workflows/`, and public
   SDK signatures.

Later rows are done only when their required artifact is present, the evidence
manifest key is `true`, the readiness gate either still reports the remaining
blockers or reaches `ready_for_operator_decision`, and the row's exit decision
is recorded in the row-specific plan or PR.

## Non-Goals

1. no `support_widening_allowed=true` flip;
2. no `production_platform_claim_allowed=true` flip;
3. no `live_adapter_execution_allowed=true` flip;
4. no `PUBLIC-BETA.md` tier promotion;
5. no `SUPPORT-BOUNDARY.md` production claim;
6. no MCP repo-intelligence tool exposure;
7. no context compiler auto-feed;
8. no root authority file write;
9. no mutation of the GP-5.9 platform-claim decision script.

## Exit Decision

This slice exits only with one of:

1. `blocked_operator_bound_evidence_required`;
2. `ready_for_operator_promotion_decision`.

It must not exit with a production claim or support widening decision.
