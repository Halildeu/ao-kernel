# V5 Cost Rate Circuit Breaker Preflight Bundle

**Status:** current-state preflight evidence / not final release authority
**Work package:** E-9-1
**Parent matrix:** `.claude/plans/V5-PRODUCTION-READINESS-MATRIX-BLOCKER.md`
**Schema:** `ao_kernel/defaults/schemas/v5-cost-rate-circuit-breaker-preflight-bundle.schema.v1.json`
**Fixture:** `tests/fixtures/epic9/v5-cost-rate-circuit-breaker-preflight.current.json`

This document records the current state of the
`cost_rate_circuit_breaker_evidence` dimension in the V5 production-readiness
matrix. It binds the existing cost model, cost ceiling, per-call audit,
simulated usage/cost evidence, rate limiter, circuit breaker, and budget-burn
incident surfaces into one machine-checkable preflight artifact.

## Non-Authority Boundary

This bundle does not authorize:

- support widening;
- production platform claims;
- live adapter execution;
- final release tagging or publishing;
- opening PR-Xfinal;
- treating simulated cost or local dry-run evidence as live provider cost
  evidence;
- treating the dormant cost policy defaults as runtime activation.

The current bundle pins `final_release_bound=false`,
`support_widening=false`, `production_platform_claim=false`, and
`live_adapter_execution=false`.

## Current Preflight Evidence

| Surface | Current evidence | Boundary |
|---|---|---|
| Cost tracking policy | `docs/COST-MODEL.md`, `ao_kernel/defaults/policies/policy_cost_tracking.v1.json`, `tests/test_cost_policy.py` | cost tracking is dormant by default; operators opt in with workspace policy |
| Cost ceiling | `ao_kernel/_internal/cost_ceiling.py`, `ao_kernel/defaults/policies/policy_cost_ceiling.v1.json`, `tests/test_cost_ceiling.py` | soft breach returns explicit state; hard breach fails closed and writes audit/state evidence; not live provider evidence |
| Per-call audit | `docs/PER-CALL-AUDIT.md`, `ao_kernel/defaults/schemas/per_call_audit.schema.v1.json`, `tests/test_per_call_audit.py` | one JSONL row per would-be call; actual cost is decimal string; no provider call |
| Simulated usage/cost evidence | `scripts/real_adapter_usage_evidence.py`, `ao_kernel/defaults/schemas/real-adapter-usage-cost-evidence.schema.v1.json`, `tests/test_real_adapter_usage_cost_evidence.py` | autonomous path emits/validates simulated evidence only; live evidence class remains operator-bound |
| Rate and circuit breaker primitives | `ao_kernel/_internal/prj_kernel_api/rate_limiter.py`, `ao_kernel/_internal/prj_kernel_api/circuit_breaker.py`, `tests/test_rate_limiter.py`, `tests/test_circuit_breaker.py` | local primitives are covered; no final promoted-tier traffic policy evidence |
| Budget-burn incident surface | `docs/incident-response/scenarios/04-cost-burn-breach.md`, `docs/sli-catalog.v1.json` | budget projection is recording-only in v1; operator owns alarm overlay |
| Pricing snapshot | `ao_kernel/defaults/pricing/openai_gpt_4o_mini.v1.json` | operator-pinned snapshot for bounded evidence; final fresh pricing-source snapshot remains missing |

## Residual Missing Evidence

PR-Xfinal remains blocked for this dimension until a later operator-bound
supersession provides:

- live cost evidence bound to the authorized 7-day provider window;
- soft and hard breach evidence from a protected live run;
- rollback evidence and budget follow-up issue automation from that run;
- fresh pricing-source snapshot bound to PR-Xfinal;
- operator-authorized budget alarm overlay and escalation evidence for the
  promoted tier.

This is intentionally a preflight artifact. It makes the existing cost/rate
surface auditable without changing the production claim gate.
