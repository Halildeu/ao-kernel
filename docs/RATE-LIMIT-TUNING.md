# Provider rate limit production tuning (per-tenant) — V5 Epic 7 E-7-4

> Slice #886. Operator tuning guide for the built-in per-provider token-bucket
> rate limiter, including a **per-tenant** isolation pattern. This is a tuning
> **runbook** over the existing `ao_kernel.llm.get_rate_limiter` surface — it
> introduces no new runtime guard and flips no flag. Live adapter execution
> stays `const false`; these limits govern the request-shaping layer, not any
> live-call authorization.

## 1. What the limiter does

`ao-kernel` ships a thread-safe **token-bucket** rate limiter
(`get_rate_limiter(provider_id, rps)`). Each distinct `provider_id` gets its
own bucket in a process-local registry. `acquire()` blocks up to a timeout;
`try_acquire()` is non-blocking. Refill is continuous at `rps` tokens/second,
capped at `max(1.0, rps)` burst.

## 2. Per-tenant isolation pattern

The registry key is a free-form string. To isolate tenants **within one
process**, namespace the key as `"<tenant>:<provider>"`:

```python
from ao_kernel.llm import get_rate_limiter

# Per-tenant, per-provider bucket (recommended for multi-tenant hosts):
limiter = get_rate_limiter(f"{tenant_id}:{provider_id}", rps=tenant_rps)
if not limiter.try_acquire():
    # shed / queue / 429 this tenant's request without starving others
    ...
```

For the **deployment-level** multi-tenancy model (one pod per tenant; see
`docs/MULTI-TENANT-CONFIG-RECIPE.md`), each tenant already has its own process
and registry, so the plain `provider_id` key suffices — the per-tenant key is
for hosts that fan multiple tenants through a single process.

## 3. Choosing production `rps` values

Start from the provider's published quota, then divide by concurrency and
leave headroom. Worked example:

| Provider quota | Pods sharing quota | Headroom | Per-pod `rps` |
|---|---|---|---|
| 60 req/min (1 rps) | 1 | 20% | 0.8 |
| 600 req/min (10 rps) | 4 | 20% | 2.0 |
| 3000 req/min (50 rps) | 10 | 30% | 3.5 |

Rules of thumb:

- **Divide by the number of pods/processes** sharing the same provider quota.
  The limiter is process-local; N pods each at `rps=R` burst to `N×R`.
- **Leave 20–30% headroom** for retries, bursts, and clock skew.
- **Tune per tenant** when tenants have differentiated SLAs: a premium tenant
  may get a higher `rps` than a free-tier tenant against the same provider.
- **Never exceed the provider quota in aggregate** — the limiter shapes your
  side; the provider still hard-rejects (429) past its ceiling, which the
  circuit breaker (`get_circuit_breaker`) then trips on.

## 4. Interaction with retries + circuit breaker

The request path is: **rate limiter → transport (tenacity retry) → circuit
breaker**. Set `rps` so steady-state stays under quota; the circuit breaker is
the *failure* backstop (per-provider OPEN/HALF_OPEN), not the primary throttle.
Tuning `rps` too high just moves the rejection from your limiter to the
provider's 429 + your breaker — wasted round-trips.

## 5. Measuring

- Watch the per-provider `rate_limit` telemetry counter (OTEL, if installed)
  for `acquire` timeouts — sustained timeouts mean `rps` is too low for load.
- Watch provider 429 rate — any 429 means aggregate `rps` (across pods) is too
  high; reduce per-pod `rps` or add pods with proportionally lower `rps`.
- Re-tune after every concurrency change (HPA scale, new tenant onboarding).

## 6. What this slice does NOT do

- Does NOT change the limiter implementation (`_internal`); it documents the
  existing public `get_rate_limiter` surface.
- Does NOT enable live adapter execution or any guard flag (request shaping is
  independent of live-call authorization).
- Does NOT claim production readiness (beta tuning guidance).

## 7. Cross-references

- Public surface: `ao_kernel.llm.get_rate_limiter` / `get_circuit_breaker`
- Multi-tenant deployment: `docs/MULTI-TENANT-CONFIG-RECIPE.md` (E-8-2)
- Streaming/resilience: CLAUDE.md §10 (circuit breaker + rate limiter)
