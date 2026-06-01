# Scenario 04: Monthly Cost Burn Projection Breach

> **SEV-2** (budget objective / operator threshold-driven). Indicator:
> `monthly_cost_burn_projection_usd`. **Recording-only in v1.** **Not SLA.**

## Trigger

E-5-4 catalog indicator: `monthly_cost_burn_projection_usd` (budget objective,
threshold_source: operator_configured, target_status: placeholder).

**Important:** E-5-5 ships **NO active firing alert** for this indicator. A
recording rule exposes the projection; **the operator owns the alarm**
through a separate overlay (see E-5-5 README §4 "Dormant operator overlay
for budget alarm").

If the operator wires up a budget alarm, this scenario describes the
expected triage. Otherwise, this scenario is observability-only.

## Plain-language meaning

Projected monthly LLM cost burn (extrapolating current 1h cost rate over 30
days) is approaching or exceeding the operator-configured budget threshold.
Budget objective is NOT a hard SLO; the threshold is operator-tunable.

## Triage Steps (read-only)

1. **Current projection.** Snapshot the recording rule:
   ```promql
   ao:slo:monthly_cost_burn_projection_usd:projection_rate1h
   ```
2. **Cost source breakdown.** Per-provider, per-model cost rate over last 1h:
   ```promql
   sum by (provider, model) (rate(ao_llm_cost_usd_total[1h]))
   ```
3. **Recent traffic spike correlation.** Was a usage-driving feature flag
   flipped recently? Check audit log for guard / config changes.
4. **Compare to operator budget threshold.** Operator-configured value lives
   outside this repo (Helm value / ConfigMap / external policy).

## Mitigation (operator action)

- Operator decision required (cost is operator-owned tunable).
- Options: throttle traffic, switch to cheaper provider, defer non-critical
  background traffic, raise budget threshold.
- ao-kernel does NOT auto-throttle on budget burn (no auto-mitigation in v1;
  guard flag `live_adapter_execution_allowed=false` precludes runtime
  intervention).

## Escalation Path

- **SEV-2 cadence:** ack 30 min; cadence 60 min; MTTR target 240 min.
- Comms policy: `owner_business_hours`.
- This is not a paging alert in v1; advisory observability + operator alarm
  overlay.

## Diagnostic Commands (safe / read-only)

```bash
# Current projection
curl -s "http://prometheus:9090/api/v1/query?query=ao:slo:monthly_cost_burn_projection_usd:projection_rate1h"

# Per-provider/model cost rate
curl -s "http://prometheus:9090/api/v1/query?query=sum%20by%20(provider%2C%20model)%20(rate(ao_llm_cost_usd_total%5B1h%5D))"
```

## Out of Scope (this scenario)

- Tenant-bound budget enforcement (Epic 4 multi-tenancy; v1 has no tenant
  label on `ao_llm_cost_usd_total`).
- Automated cost throttling (`live_adapter_execution_allowed=false`).
- Real budget threshold value (operator-configured; placeholder in catalog).

## References

- E-5-4 catalog: `../../sli-catalog.v1.json` (indicator: `monthly_cost_burn_projection_usd`)
- E-5-5 README §4 budget recording-only discipline (post PR #800)
- Severity matrix: `../severity-matrix.v1.json` (SEV-2; objective_kind: budget_objective)
- Post-mortem template: `../incident-template.v1.md`
