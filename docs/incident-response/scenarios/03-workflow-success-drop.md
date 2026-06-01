# Scenario 03: Workflow Terminal Success Rate Drop

> **SEV-1** (critical) or **SEV-2** (warning). Indicator: `workflow_terminal_success_rate`.
> **Not SLA.** Operator-tunable response.

## Trigger

E-5-5 PrometheusRule alerts (post PR #800 merge):

- `AOSLOWorkflowTerminalSuccessRateBurnRateCritical` — 14.4x burn
- `AOSLOWorkflowTerminalSuccessRateBurnRateWarning` — 6x burn
- SLO target: 99.5% terminal success over 30 days

## Plain-language meaning

A growing fraction of orchestrated workflows is reaching the `failed` or
`cancelled` terminal state rather than `completed`. In-flight workflows are
not counted by this SLI (uptime out of scope per E-5-4 catalog).

## Triage Steps (read-only)

1. **Identify failure pattern.** Per-terminal-state breakdown:
   ```promql
   sum by (final_state) (
     increase(ao_workflow_duration_seconds_count[1h])
   )
   ```
2. **Last error log.** Pull recent workflow run failures from structured logs
   (operator-deployed log layer; not shipped here).
3. **Cross-reference policy denies (advisory).** If `policy_deny_rate` is
   also up, the workflow drop may be a downstream effect of a policy change.
4. **OTEL trace correlation.** Pull a failed workflow trace and walk the span
   tree to find the failure point.
5. **Recent deploy correlation.** Was a workflow-related PR merged in the
   past N hours?

## Mitigation (operator action)

- Workflow definition regression → revert recent workflow PR.
- Policy change cascade → coordinate with policy owner; may require ADR.
- Downstream provider failure → check Scenario 01 / 02 for transport issues.

## Escalation Path

- **SEV-1:** ack 15 min; cadence 15 min; MTTR 60 min.
- **SEV-2:** ack 30 min; cadence 60 min; MTTR 240 min.
- Comms policy: `owner_immediate` or `owner_business_hours`.

## Diagnostic Commands (safe / read-only)

```bash
# Terminal state breakdown
curl -s "http://prometheus:9090/api/v1/query?query=sum%20by%20(final_state)%20(increase(ao_workflow_duration_seconds_count%5B1h%5D))"

# Per-window error ratio
curl -s "http://prometheus:9090/api/v1/query?query=ao:slo:workflow_terminal_success_rate:error_ratio_rate1h"
```

## Out of Scope (this scenario)

- In-flight workflow correctness (no metric in v1 surface).
- Workflow-content authoring or template change (governance scope).

## References

- E-5-4 catalog: `../../sli-catalog.v1.json` (indicator: `workflow_terminal_success_rate`)
- E-5-5 alerts: `../../alertmanager/prometheus-rules.v1.yml` (post PR #800)
- Severity matrix: `../severity-matrix.v1.json` (SEV-1 / SEV-2)
- Post-mortem template: `../incident-template.v1.md`
