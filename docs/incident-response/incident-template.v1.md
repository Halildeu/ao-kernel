# Incident Post-Mortem Template (V5 Epic 6 E-6-6)

> **Blameless RCA** per Google SRE Workbook. **Distribution: operator + owner
> + security-stakeholder only** (v1; public post-mortem deferred to E-6-6e).
> **Not SLA.** **Not a production platform claim.** Operator-owned.

---

## Metadata

| Field | Value |
|---|---|
| Incident ID | `INC-YYYYMMDD-NN` (operator-assigned) |
| Severity | SEV-1 / SEV-2 / SEV-3 |
| Detection source | Alertmanager / Operator / User report |
| Triggering alert | (E-5-5 alert name; e.g. `AOSLOLlmUsageAccountingCompletenessBurnRateCritical`) |
| Impacted indicators | (E-5-4 catalog indicator names) |
| Detection time (UTC) | `YYYY-MM-DDTHH:MM:SSZ` |
| Mitigation time (UTC) | `YYYY-MM-DDTHH:MM:SSZ` |
| Resolution time (UTC) | `YYYY-MM-DDTHH:MM:SSZ` |
| Total impact duration | (mitigation - detection) |
| Author | (operator-defined; redact for distribution if needed) |
| Distribution | operator + owner + security-stakeholder (not public in v1) |

## Impact Summary

> One paragraph: what was affected, who saw it, observable user-facing or
> operator-facing impact. Include error budget burned (E-5-4 catalog SLO
> budget reference if applicable). No PII; redact user identifiers.

## UTC Timeline

| UTC time | Event | Actor | Notes |
|---|---|---|---|
| `YYYY-MM-DDTHH:MM:SSZ` | Alert fired (E-5-5 PrometheusRule) | Alertmanager | (alert name + severity + indicator) |
| `YYYY-MM-DDTHH:MM:SSZ` | Acknowledged | (operator stage name) | within SEV ack_timeout |
| `YYYY-MM-DDTHH:MM:SSZ` | Mitigation applied | (operator stage name) | (mitigation summary) |
| `YYYY-MM-DDTHH:MM:SSZ` | Resolution confirmed | (operator stage name) | (resolution confirmation evidence) |

## Root Cause Analysis (RCA)

> Blameless; technical narrative only. What broke, why it broke, why it was
> not caught earlier. Reference E-5-1 OTEL traces / E-5-3a W3C trace IDs if
> available.

## 5 Whys

1. **Why** did the incident occur?
2. **Why** did that cause the incident?
3. **Why** did that contributing factor exist?
4. **Why** was that systemic cause not addressed earlier?
5. **Why** does the broader system permit this class of failure?

## Contributing Factors

- (List structural / process / tooling / monitoring / dependency factors)

## Corrective Actions

| Action | Owner | Due date (UTC) | Linked artifact |
|---|---|---|---|
| (action 1: e.g. add OTEL span to component X) | (operator-defined) | `YYYY-MM-DD` | ADR / issue / PR link |
| (action 2: e.g. extend Prometheus recording rule) | (operator-defined) | `YYYY-MM-DD` | ADR / issue / PR link |
| (action 3: e.g. update playbook scenario file) | (operator-defined) | `YYYY-MM-DD` | ADR / issue / PR link |

> Every corrective action MUST have owner + due date + linked artifact (ADR,
> GitHub issue, or PR). Open-ended TODOs are not accepted.

## Linked Artifacts

- **ADRs:** (links to architecture decision records)
- **Issues:** (links to GitHub issues opened/closed during incident)
- **PRs:** (links to merged PRs implementing corrective actions)
- **Evidence files:** (OTEL trace IDs, log paths, metric snapshots — redact
  PII / credentials before linking)

## Evidence Links

- Prometheus query: (PromQL link + UTC time range)
- Grafana dashboard panel: (link from E-5-2 dashboard)
- OTEL trace ID: (W3C traceparent from E-5-3a; redact if PII-bearing)
- Workflow run: (GitHub Actions URL if relevant)

## Redaction Attestation

> The author attests that this post-mortem document:
>
> - [ ] Contains NO end-user PII (email, phone, name, IP address, account
>       identifier outside of allowed placeholders).
> - [ ] Contains NO production credentials, webhook URLs, API keys, JWT/Bearer
>       tokens, GitHub PATs, or Vault tokens.
> - [ ] Contains NO third-party vendor escalation case IDs that should not be
>       distributed to the operator+owner+security-stakeholder scope.
> - [ ] Does NOT promise contractual SLA terms or production platform
>       commitments.

Author signature: `_______________`  Date (UTC): `_______________`
