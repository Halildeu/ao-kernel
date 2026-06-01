# Scenario 05: Coordination Takeover Rate Spike

> **SEV-3** (advisory; baseline_required). Indicator: `coordination_takeover_rate`.
> **Recording-only in v1.** No active firing rule until baseline measured.
> **Not SLA.** Observability only.

## Trigger

E-5-4 catalog indicator: `coordination_takeover_rate` (advisory_sli,
baseline_required=true, alerting_kind=spike).

**Important:** E-5-5 ships **NO active firing alert** for this advisory SLI.
Promotion to hard SLO requires 30 days production-equivalent traffic + operator
decision (Codex 019e83af absorb F2).

## Plain-language meaning

Multi-agent coordination claims are being taken over at an unusually high
rate normalized by average active claims. Could indicate contention from
agent thrashing, claim TTL misconfiguration, or genuine multi-tenant
concurrency growth.

## Triage Steps (read-only — observation only in v1)

1. **Snapshot the recording rule:**
   ```promql
   ao:slo:coordination_takeover_rate:rate1h
   ```
2. **Decompose by agent type.** Per-agent breakdown (if labels exist):
   ```promql
   increase(ao_claim_takeover_total[1h])
   ```
3. **Compare against `ao_claim_active_total` trend.** Is total active claim
   count growing? If yes, takeover rate spike may be normal.
4. **Cross-reference with workflow scenario 03.** Coordination spikes often
   precede workflow terminal-state drops.

## Action (operator observation only in v1)

- **No automated remediation** (no alert firing; no live_adapter_execution).
- Operator may open an issue for baseline data collection.
- After 30 days production-equivalent baseline, operator + cross-AI peer
  review may promote to SEV-2 or hard SLO via E-5-5d follow-up slice.

## Escalation Path

- **SEV-3 cadence:** no hard ack/escalation in v1 (operator-defined).
- Comms policy: `operator_only` (no owner / customer comms).

## Diagnostic Commands (safe / read-only)

```bash
# Current advisory recording
curl -s "http://prometheus:9090/api/v1/query?query=ao:slo:coordination_takeover_rate:rate1h"

# Active claim count trend
curl -s "http://prometheus:9090/api/v1/query?query=ao_claim_active_total"
```

## Out of Scope (this scenario)

- Active firing rule (deferred until baseline; E-5-5d slice).
- Automated coordination conflict resolution (runtime change; not in v1).

## References

- E-5-4 catalog: `../../sli-catalog.v1.json` (indicator: `coordination_takeover_rate`)
- E-5-5 README §4 advisory recording-only discipline
- E-5-5d follow-up slice (advisory spike baseline-driven promotion)
- Severity matrix: `../severity-matrix.v1.json` (SEV-3; objective_kind: advisory_sli)
- Post-mortem template: `../incident-template.v1.md`
