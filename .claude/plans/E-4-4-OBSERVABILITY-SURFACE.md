# E-4-4 — Observability surface (ServiceMonitor + OTEL sidecar)

> V5 Epic 4. Slice #863. Guard-flag-independent. Builds on E-4-1 chart.

## Delivered
- `templates/servicemonitor.yaml` — Prometheus Operator ServiceMonitor CRD,
  gated on `monitoring.serviceMonitor.enabled` (default false), scrapes http port.
- `values.yaml` `monitoring` block — serviceMonitor + otelSidecar (both off).
- `values.schema.json` — closed monitoring block.
- `templates/deployment.yaml` — optional OTEL collector sidecar, gated +
  hardened securityContext, OTLP endpoint via plain env (no secret).
- `tests/test_epic_4_4_observability_surface.py` — 13 invariants.

## Boundaries
- Chart does NOT install Prometheus Operator (operator-owned).
- Alert routing Microsoft Teams primary (no Slack receiver embedded).
- No secret material; no guard flag; no `.github/workflows/` mutation.
