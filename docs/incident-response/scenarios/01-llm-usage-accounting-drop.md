# Scenario 01: LLM Usage Accounting Completeness Drop

> **SEV-1** (alert severity=critical). Indicator: `llm_usage_accounting_completeness`.
> **Not SLA.** Operator-tunable response.

## Trigger

E-5-5 PrometheusRule alert (post PR #800 merge):

- Alert name: `AOSLOLlmUsageAccountingCompletenessBurnRateCritical`
- Burn-rate condition: `error_ratio_rate1h > 0.144 AND error_ratio_rate5m > 0.144`
- SLO target: 99.0% over 30 days

## Plain-language meaning

A growing fraction of LLM transport calls is not producing matching usage
accounting events. Either the call succeeded but usage was lost (provider
omitted, schema drift, transport partial), or usage accounting itself broke.

## Triage Steps (read-only)

1. **Identify the gap.** Compute the bounded denominator (E-5-4 catalog form):
   ```promql
   sum(rate(ao_llm_usage_missing_total[5m]))
     / clamp_min(
         sum(rate(ao_llm_call_duration_seconds_count[5m]))
           + sum(rate(ao_llm_usage_missing_total[5m])),
         1e-9)
   ```
2. **Per-provider attribution.** Filter the bounded ratio by provider label.
3. **Inspect missing-counter spikes.** Look for sudden discontinuities in
   `ao_llm_usage_missing_total` per provider over the last 30 minutes.
4. **OTEL trace correlation (E-5-3a).** Pull the W3C `traceparent` from a
   recent missing-usage event and cross-reference the call span tree.
5. **Schema drift check.** Verify the provider's response shape against the
   adapter's parser — schema drift is the most common root cause.

## Mitigation (operator action; read-only diagnostics → owner decision)

- Provider schema drift → adapter parser fix; PR with cross-AI peer review.
- Provider partial outage → vendor escalation handoff (see §6.6 README).
- Transport regression → revert recent transport PR (see Grafana dashboard
  panel for change-point detection).

## Escalation Path

- **SEV-1 cadence:** ack within 15 min; escalate every 15 min.
- Stage 1 (primary on-call) → Stage 2 (secondary) → Stage 3 (engineering manager).
- Comms policy: `owner_immediate` (Microsoft Teams primary).

## Diagnostic Commands (safe / read-only)

```bash
# Snapshot the bounded SLI for the past hour
curl -s "http://prometheus:9090/api/v1/query?query=ao:slo:llm_usage_accounting_completeness:sli_ratio_rate1h"

# Inspect missing-counter delta per provider
curl -s "http://prometheus:9090/api/v1/query?query=increase(ao_llm_usage_missing_total[30m])"
```

## Out of Scope (this scenario)

- No live adapter mutation; no live retry trigger; no branch protection rule
  change. Provider escalation is operator-owned external handoff.

## References

- E-5-4 catalog: `../../sli-catalog.v1.json` (indicator: `llm_usage_accounting_completeness`)
- E-5-5 alert: `../../alertmanager/prometheus-rules.v1.yml` (post PR #800 merge)
- E-5-1 OTEL tunables (PR #791)
- E-5-3a W3C trace context (PR #797)
- Severity matrix: `../severity-matrix.v1.json` (SEV-1)
- Post-mortem template: `../incident-template.v1.md`
