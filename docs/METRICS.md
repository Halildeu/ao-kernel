# Metrics — Prometheus / OTEL Export Surface

**Status:** FAZ-B PR-B0 contract pin (docs skeleton). Runtime implementation: PR-B5 (`ao_kernel/metrics/` + `[metrics]` extra).

## 1. Overview

ao-kernel exposes governance and runtime metrics in two orthogonal channels:

1. **Prometheus textfile export** (PR-B5) — low-cardinality default label set; operators scrape via `ao-kernel metrics export --format prometheus`. Ships under `[metrics]` optional extra.
2. **OTEL span bridge** (existing, [PR-A telemetry](../ao_kernel/telemetry.py)) — unchanged; `[metrics]` and `[otel]` extras are independent, installable separately.

The `[metrics]` extra has no hard dependency on `[otel]`. The library never runs an HTTP server; operators who want push-to-Prometheus run the CLI in their own cron or sidecar.

## 2. Default Metric Set

Low-cardinality labels only. See §3 for opt-in expansion.

| Metric | Type | Labels | Fired by |
|---|---|---|---|
| `ao_llm_call_duration_seconds` | histogram | `provider` | PR-A `llm` facade |
| `ao_llm_tokens_used_total` | counter | `provider`, `direction` ∈ `{input, output, cached}` | PR-A `llm` facade |
| `ao_policy_check_total` | counter | `outcome` ∈ `{allow, deny}` | PR-A `governance.check_policy` |
| `ao_workflow_duration_seconds` | histogram | `final_state` ∈ `{completed, failed, cancelled}` | PR-A4b `MultiStepDriver` |
| `ao_claim_active_total` | gauge | (none — scalar) | PR-B1 coordination |
| `ao_claim_takeover_total` | counter | (none — scalar) | PR-B1 coordination |

**Deliberately excluded by default:** `model`, `agent_id`, `run_id`, `workflow_id`, `step_id`. Each would produce O(100) – O(10k) distinct values in a reasonable deployment, and Prometheus cardinality costs scale multiplicatively. Exposing them without an opt-in would create a silent storage bomb.

## 3. Advanced Labels (Schema-Backed Opt-In)

`policy_metrics.v1.json` is the control plane for advanced labels. Operators opt in by setting the policy `enabled: true` and listing the labels they want in `labels_advanced.allowlist`.

```json
{
  "enabled": true,
  "labels_advanced": {
    "enabled": true,
    "allowlist": ["model", "agent_id"]
  }
}
```

Allowlist values are constrained to a closed enum (`model | agent_id`) at schema level. Unknown values fail schema validation at load; typos do not silently enable anything.

The `enabled` flag on the top-level policy gates metrics emission altogether. The `labels_advanced.enabled` flag specifically gates the advanced label set. Both default `false` in the bundled policy.

## 4. Grafana Integration

Reference dashboard JSON ships under `docs/grafana/` (PR-B5). Operators import into their own Grafana instance; the library does not host Grafana.

Dashboard panels target the default metric set; advanced-label panels ship commented-out so importing the dashboard does not break when `labels_advanced.enabled: false`.

## 5. OTEL Bridge

[`ao_kernel/telemetry.py`](../ao_kernel/telemetry.py) already emits OTEL spans for the same code paths under the `[otel]` extra. The metrics package introduces parallel Prometheus counters/histograms; it does not read OTEL spans or attempt bridge translation.

Operators who want both can install both extras (`pip install ao-kernel[otel,metrics]`); the two surfaces do not interfere.

## 6. CLI

`ao-kernel metrics export --format prometheus` (PR-B5) emits the current metric set in Prometheus textfile format on stdout. Typical integration: cron → file → Prometheus `textfile` collector.

Future formats (OpenMetrics, StatsD, InfluxDB) are not in scope for B5; they are deferred to post-FAZ-E if demanded.

## 7. Cross-References

- Schema: [`policy-metrics.schema.v1.json`](../ao_kernel/defaults/schemas/policy-metrics.schema.v1.json)
- Policy: [`policy_metrics.v1.json`](../ao_kernel/defaults/policies/policy_metrics.v1.json) (PR-B0 commit 4 — dormant default)
- OTEL spans: [`ao_kernel/telemetry.py`](../ao_kernel/telemetry.py), docstrings therein
- Runtime (scope out of B0): PR-B5 `ao_kernel/metrics/` package + `[metrics]` extra

## 8. Document Status

Skeleton in PR-B0 commit 1. Panel-by-panel Grafana walkthrough, cardinality-tuning case study, and PR-A evidence → metric extraction recipe land in PR-B0 commit 5 (docs final pass).
