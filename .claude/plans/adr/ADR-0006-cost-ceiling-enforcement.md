---
id: ADR-0006
title: Cost ceiling enforcement for V5 Epic 2 infrastructure
status: accepted
date: 2026-06-04
deciders:
  - Codex (OpenAI)
  - Claude (Anthropic)
retrospective: false
review_status: original
slice_ref: E-2-3
guard_flags:
  support_widening: false
  production_platform_claim: false
  live_adapter_execution: false
register_authority: evidence_record_only
github_write_authorized: false
---

# ADR-0006: Cost Ceiling Enforcement For V5 Epic 2 Infrastructure

## Context

V5 Epic 2 is infrastructure-only. E-2-1 added the live-adapter envelope schema
and E-2-2 added per-call audit evidence. E-2-3 needs a cost ceiling primitive
that can be reused by dry-run/stub infrastructure and later supersession
evidence without authorizing live adapter execution.

The detailed Epic 2 plan referenced a cost-ceiling ADR as `ADR-0005`, but
`ADR-0005` is already accepted for Keep-a-Changelog per-PR discipline. This
slice therefore records the cost-ceiling decision as `ADR-0006` and preserves
the existing ADR numbering.

## Decision

Add `ao_kernel._internal.cost_ceiling.CostCeiling` plus a public facade export
from `ao_kernel.cost`. The primitive:

1. Uses `Decimal` arithmetic and serializes USD values at 8 decimal places.
2. Returns an explicit `BreachState` for accepted records:
   `ok` or `soft_breached`.
3. Raises `CostCeilingExceeded` when an attempted cumulative total would exceed
   the hard ceiling. The hard-breach attempt is not accepted into the running
   total.
4. In workspace mode, serializes the read-modify-write cycle with a POSIX
   `fcntl` sidecar lock per session and appends state rows to
   `evidence/cost_ceiling_state.jsonl`.
5. In library mode, uses in-memory state and documents the single-process
   contract.
6. Supports the pre-reservation pattern through `reserve()` and
   `Reservation.settle(actual_usd)` for callers that need to reserve estimated
   cost before they know the actual call cost.
7. Optionally records the E-2-2 hard-breach per-call audit row before raising
   when the caller supplies an audit row template.

## Consequences

- Soft breaches become auditable policy decisions rather than implicit status
  changes; callers must still record `cost_breach_handling` in their per-call
  audit rows.
- Hard breaches are fail-closed: the attempted spend does not become accepted
  state, and callers see a typed exception.
- Concurrent workspace recorders cannot race the same session ledger because
  the total read, state append, and hard-breach decision are inside one
  file-lock scope.
- The primitive is reusable by E-2-4 dry-run harness and Epic 9 supersession
  evidence without changing guard flags.

## Non-Goals

- No live LLM/provider HTTP call.
- No `live_adapter_execution`, `support_widening`, or
  `production_platform_claim` flip.
- No workflow or branch-protection mutation.
- No multi-tenant quota semantics; that remains Epic 4.

## References

- `.claude/plans/EPIC-2-LIVE-ADAPTER-EXECUTION.md` §2 E-2-3
- `ao_kernel._internal.evidence.per_call_audit`
- `ao_kernel.defaults.policies.policy_cost_ceiling.v1.json`
- `tests/test_cost_ceiling.py`
