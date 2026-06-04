# V5 Public Support Matrix Preflight Bundle

**Status:** current-state preflight / not promotion authority
**Work package:** E-9-1
**Dimension:** `public_support_matrix`
**Parent blocker:** `.claude/plans/V5-PRODUCTION-READINESS-MATRIX-BLOCKER.md`
**Schema:** `ao_kernel/defaults/schemas/v5-public-support-matrix-preflight-bundle.schema.v1.json`
**Fixture:** `tests/fixtures/epic9/v5-public-support-matrix-preflight.current.json`

This bundle records the existing support-boundary documents that a future
PR-Xfinal must supersede before any public support tier is promoted. It binds
the current narrow stable boundary, the beta/operator-managed lanes, and the
surface inventory into one machine-checkable current-state artifact.

## Non-Authority Boundary

This document and fixture do not authorize:

- support widening;
- public claim language changes;
- live adapter execution;
- PR-Xfinal opening;
- v5.0.0 tag or publish;
- release notes or public support tier promotion.

The fixture pins `final_release_bound=false`, `support_widening=false`,
`production_platform_claim=false`, and `live_adapter_execution=false`.

## Current Evidence

The current public support boundary is recorded across:

- `docs/PUBLIC-BETA.md`
- `docs/SUPPORT-BOUNDARY.md`
- `docs/SUPPORT-SURFACE-INVENTORY.md`

The stable boundary remains the shipped baseline layer only. Beta,
operator-managed, deferred, contract inventory, and example-only surfaces are
visible as support-boundary context, not as promoted public support.

## Surface Inventory

The preflight fixture records the five support-widening surface classes that a
future PR-Xfinal would have to evaluate:

| Surface class | Current state | Future evidence requirement |
|---|---|---|
| `provider` | inventory or existing boundary only | provider live integration evidence |
| `python_version` | inventory or existing boundary only | full test matrix for every promoted version |
| `os_platform` | inventory or existing boundary only | smoke evidence for every promoted OS or architecture |
| `db_backend` | inventory or existing boundary only | backend round-trip evidence on the test corpus |
| `deployment_topology` | inventory or existing boundary only | deployment and isolation evidence for every promoted topology |

All future widening evidence remains operator-bound and PR-Xfinal-bound.

## Residual Missing Evidence

PR-Xfinal remains blocked until at least these are complete:

1. final v5.0.0 public support matrix with promoted support tier;
2. operator-authorized public claim language sync;
3. support-widening live evidence pack under issue `#776`;
4. PR-Xfinal all-or-none authorization for support widening and production platform claim.

Until those are available, the V5 production readiness matrix must keep
`public_support_matrix` at `partial`.
