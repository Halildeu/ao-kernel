# E-7-4 — Provider rate limit production tuning (per-tenant)

> V5 Epic 7. Slice #886. Guard-flag-independent (request shaping ≠ live-call auth).

## Delivered
- `docs/RATE-LIMIT-TUNING.md` — operator tuning runbook: per-tenant key
  pattern, rps sizing (quota ÷ pods × headroom), retry/circuit-breaker
  interaction, measurement, guard-flag affirmation.
- `ao_kernel/llm.py` — `get_rate_limiter(provider_id, rps=1.0)` facade gains an
  optional `rps` (backward-compatible; `_internal` already supported it) so
  operators can tune per-tenant/per-provider refill rates.
- `tests/test_epic_7_4_rate_limit_tuning.py` — 8 invariants incl. a real
  per-tenant isolation test (draining tenant A does not starve tenant B).

## Boundaries
- Does NOT change the limiter implementation; widens the public facade only.
- Request shaping is independent of live-call authorization; no guard flag.
- Backward-compatible: `rps` defaults to 1.0 (existing callers unaffected).
