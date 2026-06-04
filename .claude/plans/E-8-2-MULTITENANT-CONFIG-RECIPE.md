# E-8-2 — Multi-tenant production config recipe

> V5 Epic 8. Slice #890. Delegates to Epic 4 (E-4-2a/E-4-3/E-4-4/E-4-5).
> Doc-only; no new chart feature; guard-flag-independent.

## Delivered
- `docs/MULTI-TENANT-CONFIG-RECIPE.md` — namespace-per-tenant isolation recipe:
  namespace + PSS label, per-tenant PG + Secret, per-tenant values overlay
  (postgresql/networkPolicy/monitoring/PSS/resources), install, ResourceQuota,
  isolation checklist.
- `tests/test_epic_8_2_multitenant_config_recipe.py` — 8 invariants.

## Boundaries
- Delegates mechanics to Epic 4 slices; introduces no new chart feature.
- Namespace-level isolation (not in-process tenant partitioning).
- secretKeyRef-only in overlay (no inline password); no guard flag enabled.
