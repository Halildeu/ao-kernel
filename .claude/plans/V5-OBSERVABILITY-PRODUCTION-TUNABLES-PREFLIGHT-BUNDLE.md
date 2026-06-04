# V5 Observability Production Tunables Preflight Bundle

**Status:** current-state preflight evidence / not final release authority
**Work package:** E-9-1
**Parent matrix:** `.claude/plans/V5-PRODUCTION-READINESS-MATRIX-BLOCKER.md`
**Schema:** `ao_kernel/defaults/schemas/v5-observability-production-tunables-preflight-bundle.schema.v1.json`
**Fixture:** `tests/fixtures/epic9/v5-observability-production-tunables-preflight.current.json`

This document records the current state of the
`observability_production_tunables` dimension in the V5
production-readiness matrix. It binds the committed Grafana dashboard,
SLI/SLO catalog, and performance policy artifacts into one
machine-checkable preflight artifact.

## Non-Authority Boundary

This bundle does not authorize:

- support widening;
- production platform claims;
- live adapter execution;
- final release tagging or publishing;
- opening PR-Xfinal;
- treating advisory dashboard, SLI, or performance policy artifacts as final
  claim-bound smoke evidence.

The current bundle pins `final_release_bound=false`,
`support_widening=false`, `production_platform_claim=false`, and
`live_adapter_execution=false`.

## Current Preflight Evidence

| Surface | Current evidence | Boundary |
|---|---|---|
| Grafana dashboard | `docs/grafana/ao_kernel_default.v1.json`, `docs/grafana/README.md`, `tests/test_grafana_dashboard_shape.py` | 8-panel Prometheus dashboard shape is pinned; import/runtime smoke is not final claim-bound evidence |
| SLI/SLO catalog | `docs/sli-catalog.v1.json`, `docs/SLI-SLO.md`, `tests/test_sli_slo_catalog.py` | 6 indicators exist; uptime remains out of scope and all catalog guard flags remain false |
| Performance policy | `docs/performance/README.md`, `docs/performance/baseline.v1.json`, `docs/performance/performance-regression-threshold.v1.json`, `tests/test_performance_baseline.py` | advisory single-run candidate baseline; not a blocking final-release performance gate |

## Residual Missing Evidence

PR-Xfinal remains blocked for this dimension until a later operator-bound
supersession provides:

- final claim-bound observability smoke;
- alerting or escalation evidence for the promoted tier;
- operator-authorized observability runbook sync bound to PR-Xfinal;
- production-like dashboard import and SLI evaluation evidence bound to the
  final merge candidate.

This is intentionally a preflight artifact. It makes the existing
observability surface auditable without changing the production claim gate.
