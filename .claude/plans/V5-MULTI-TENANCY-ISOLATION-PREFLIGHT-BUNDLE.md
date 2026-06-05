# V5 Multi-Tenancy Isolation Preflight Bundle

**Status:** current-state preflight evidence only
**Work package:** E-9-1
**Dimension:** `multi_tenancy_isolation`
**Schema:** `ao_kernel/defaults/schemas/v5-multi-tenancy-isolation-preflight-bundle.schema.v1.json`
**Fixture:** `tests/fixtures/epic9/v5-multi-tenancy-isolation-preflight.current.json`

This bundle records the current repo-local multi-tenancy isolation evidence for
the future V5 PR-Xfinal readiness matrix. It binds the existing Epic 4 advisory
tenant boundary matrix, multi-tenant deployment runbook, per-tenant config
recipe, Helm chart boundary tests, and per-tenant rate-limit evidence into one
machine-checkable current-state artifact.

## Non-Authority Boundary

This bundle does not authorize:

- support widening;
- production platform claims;
- live adapter execution;
- runtime-side tenant isolation claims;
- live cross-tenant attack-test claims;
- opening PR-Xfinal.

The fixture pins `runtime_enforced=false`, `live_validated=false`,
`tenant_isolation_ready=false`, `support_widening=false`,
`production_platform_claim=false`, and `live_adapter_execution=false`.

## What Is Currently Proven

The repo has a current advisory boundary surface for multi-tenancy:

1. `.claude/plans/tenant_isolation_matrix.v1.json` is in
   `e_4_2b_final_seal` state with exactly seven filled dimensions.
2. `docs/MULTI-TENANT-DEPLOYMENT.md` documents the operator-installed
   Kubernetes boundary pattern and explicitly keeps `runtime_enforced=false`
   and `live_validated=false`.
3. `docs/MULTI-TENANT-CONFIG-RECIPE.md` records the namespace-per-tenant,
   database-per-tenant, Secret-per-tenant, NetworkPolicy, ServiceMonitor label,
   and ResourceQuota recipe.
4. `deploy/helm/ao-kernel/` renders namespace-scoped RBAC, `secretKeyRef`
   secret indirection, NetworkPolicy, ServiceMonitor, and pod resource
   requests/limits surfaces that the operator can compose per tenant.
5. `docs/RATE-LIMIT-TUNING.md` and `tests/test_epic_7_4_rate_limit_tuning.py`
   prove the documented `"<tenant>:<provider>"` key pattern creates independent
   process-local limiter buckets.

These are preflight artifacts. They are useful V5 evidence, but they remain
advisory until a later operator-bound PR supplies live tenant-isolation proof.

## Why The Matrix Moves To Partial

Before this bundle, the V5 matrix only pointed `multi_tenancy_isolation` at the
roadmap and marked the dimension `not_ready`. The current repo now has enough
evidence to record a partial current-state surface:

- advisory matrix final seal exists;
- operator runbooks and recipes exist;
- Helm boundary and rate-limit tests exist;
- guard flags remain false;
- missing live/operator evidence is explicit.

This moves the dimension to `partial`, not `ready`.

## Residual Missing Evidence

The following evidence is still required for a future PR-Xfinal path:

- live cluster CNI/RBAC/NetworkPolicy validation evidence;
- cross-tenant leak-prevention or attack-test evidence;
- operator-applied ResourceQuota and LimitRange evidence;
- per-tenant live cost/quota dashboard evidence;
- operator-attested tenant isolation review bound to the final release
  artifact.

Until those are present, the V5 production readiness matrix remains incomplete.

## Cross-References

- Matrix blocker:
  `.claude/plans/V5-PRODUCTION-READINESS-MATRIX-BLOCKER.md`
- Current matrix fixture:
  `tests/fixtures/epic9/v5-production-readiness-matrix.current.json`
- Advisory matrix:
  `.claude/plans/tenant_isolation_matrix.v1.json`
- Final advisory seal:
  `.claude/plans/E-4-2b-MULTI-TENANT-FINAL-SEAL.v1.json`
- Multi-tenant deployment runbook:
  `docs/MULTI-TENANT-DEPLOYMENT.md`
- Multi-tenant config recipe:
  `docs/MULTI-TENANT-CONFIG-RECIPE.md`
- Rate-limit tuning:
  `docs/RATE-LIMIT-TUNING.md`
