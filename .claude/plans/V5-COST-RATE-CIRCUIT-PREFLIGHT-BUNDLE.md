# V5 Cost / Rate / Circuit-Breaker Preflight Bundle

**Status:** current-state preflight / not promotion authority
**Work package:** E-9-1
**Dimension:** `cost_rate_circuit_breaker_evidence` (production readiness matrix dimension 3)
**Parent blocker:** `.claude/plans/V5-PRODUCTION-READINESS-MATRIX-BLOCKER.md`
**Schema:** `ao_kernel/defaults/schemas/v5-cost-rate-circuit-preflight-bundle.schema.v1.json`
**Fixture:** `tests/fixtures/epic9/v5-cost-rate-circuit-preflight.current.json`

This bundle records the cost-control runtime modules that are **already present**
in the repository, binding them into one machine-checkable current-state
artifact for the Gate C (`production_platform_claim`) readiness matrix. The
modules below ship today and are exercised in dry-run / unit form; the bundle
keeps the dimension `partial` because live cost evidence, breach/rollback
evidence from a protected run, and a fresh pricing snapshot are bound to the
future operator PR-Xfinal.

## Non-Authority Boundary

This document and fixture do not authorize:

- support widening;
- production platform claims;
- live adapter execution;
- partial guard-flag flips;
- v5.0.0 tag or publish;
- opening PR-Xfinal.

All three guard flags remain `const false`. AI output is evidence only.
Release authority remains the repo-owned `ao-release-gate` required checks plus
the GitHub branch ruleset.

## Current-State Cost Controls (present today)

| Control | Current state | Module |
|---|---|---|
| Cost ceiling enforcement (soft/hard breach) | active | `ao_kernel/_internal/cost_ceiling.py` + `policy_cost_ceiling.v1.json` |
| Per-provider circuit breaker | active | `ao_kernel/_internal/prj_kernel_api/circuit_breaker.py` |
| Per-provider rate limiter | active | `ao_kernel/_internal/prj_kernel_api/rate_limiter.py` |
| Per-call audit schema | active | `docs/PER-CALL-AUDIT.md` (+ writer) |
| Dry-run cost evidence harness | active | `ao_kernel/_internal/live_adapter_dryrun.py` |

These are current-state, non-live controls: the enforcement, breaker, limiter,
audit, and dry-run harness exist and are unit/dry-run exercised. No real
provider call or live cost is produced by this bundle.

## Residual Evidence Bound to PR-Xfinal

The dimension stays incomplete until the future operator-bound PR-Xfinal supplies:

1. live cost evidence bound to the protected operator window (replacing the
   dry-run harness output);
2. soft and hard breach plus rollback evidence captured from a protected run;
3. a fresh pricing-source snapshot (SHA-256 pinned, not older than 30 days).

## Mirror Issues

`#775`, `#782`, `#895` — GitHub issues are a visibility mirror; repo artifacts
remain the SSOT.
