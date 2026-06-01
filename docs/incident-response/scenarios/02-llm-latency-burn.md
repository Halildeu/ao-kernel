# Scenario 02: LLM Latency Under 30s Ratio Burn

> **SEV-1** (critical) or **SEV-2** (warning). Indicator: `llm_latency_under_30s_ratio`.
> Per-provider attribution preserved (`sum by (provider)`).
> **Not SLA.** Operator-tunable response.

## Trigger

E-5-5 PrometheusRule alerts (post PR #800 merge):

- `AOSLOLlmLatencyUnder30sRatioBurnRateCritical` — critical burn (14.4x over 1h+5m)
- `AOSLOLlmLatencyUnder30sRatioBurnRateWarning` — warning burn (6x over 6h+30m)
- SLO target: 95.0% under 30s over 30 days

## Plain-language meaning

LLM provider latency exceeded 30s for an unusually large fraction of calls. A
growing share of requests are slow enough to materially degrade user experience.

## Triage Steps (read-only)

1. **Identify which provider.** Filter by `provider` label:
   ```promql
   ao:slo:llm_latency_under_30s_ratio:error_ratio_rate1h
   ```
2. **Bucket distribution.** Look at `ao_llm_call_duration_seconds_bucket`
   histogram per provider to see where the long tail formed.
3. **Per-provider p95 (operator-facing reference).**
   ```promql
   histogram_quantile(
     0.95,
     sum by (provider, le) (rate(ao_llm_call_duration_seconds_bucket[5m]))
   )
   ```
   (Documented dashboard guideline; the bucket-ratio is what the burn-rate
   alert evaluates per E-5-4 absorb.)
4. **Cross-reference OTEL traces (E-5-3a).** Pull recent slow-call traces and
   walk the span tree.
5. **Provider status page check.** Provider transparency vs internal data.

## Mitigation (operator action)

- Provider degradation → vendor escalation handoff (§6.6).
- ao-kernel-side router retry/back-off tuning → operator-tunable; needs
  cross-AI peer review for changes.
- Adapter-specific regression → revert + PR with cross-AI peer review.

## Escalation Path

- **SEV-1 (critical):** ack 15 min; cadence 15 min; MTTR target 60 min.
- **SEV-2 (warning):** ack 30 min; cadence 60 min; MTTR target 240 min.
- Stage 1 → Stage 2 → Stage 3 (operator-defined names).
- Comms policy: `owner_immediate` (SEV-1) or `owner_business_hours` (SEV-2).

## Diagnostic Commands (safe / read-only)

```bash
# Per-provider error ratio (last 1h)
curl -s "http://prometheus:9090/api/v1/query?query=ao:slo:llm_latency_under_30s_ratio:error_ratio_rate1h"

# Per-provider histogram (last 5m)
curl -s "http://prometheus:9090/api/v1/query?query=sum%20by%20(provider%2C%20le)%20(rate(ao_llm_call_duration_seconds_bucket%5B5m%5D))"
```

## Out of Scope (this scenario)

- No live adapter mutation; no concurrent provider failover (operator-owned
  policy).

## References

- E-5-4 catalog: `../../sli-catalog.v1.json` (indicator: `llm_latency_under_30s_ratio`)
- E-5-5 alerts: `../../alertmanager/prometheus-rules.v1.yml` (post PR #800)
- Grafana dashboard panel: `../../grafana/README.md`
- Severity matrix: `../severity-matrix.v1.json` (SEV-1 / SEV-2)
- Post-mortem template: `../incident-template.v1.md`
