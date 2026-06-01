# Scenario 06: Policy Deny Rate Spike

> **SEV-3** (advisory; baseline_required). Indicator: `policy_deny_rate`.
> **Recording-only in v1.** No active firing rule until baseline measured.
> **Not SLA.** Security observability only.
> **Codex 019e83c3 F5 absorb:** dedicated scenario for Epic 6 security context.

## Trigger

E-5-4 catalog indicator: `policy_deny_rate` (advisory_sli,
baseline_required=true, alerting_kind=spike).

**Important:** Per E-5-4 absorb, `outcome` enum is `{allow, deny}` only —
`outcome="error"` is NOT exposed by the v1 metric surface. A deny is a
**policy decision**, NOT a transport error or system failure.

E-5-5 ships **NO active firing alert** for this advisory SLI.

## Plain-language meaning

The fraction of policy checks resulting in `deny` is rising. This may
reflect:

- **Legitimate policy enforcement** (e.g. correct denials against unsafe
  requests, expected during attack patterns).
- **Configuration drift** (policy unexpectedly too strict; legitimate
  requests denied).
- **Policy schema regression** (recent PR introducing a stricter rule).

This is a **security observability signal**, not necessarily a problem.

## Triage Steps (read-only)

1. **Snapshot the deny ratio:**
   ```promql
   ao:slo:policy_deny_rate:rate1h
   ```
2. **Decompose by policy intent / rule.** Per-policy breakdown:
   ```promql
   sum by (policy_name, decision) (
     rate(ao_policy_check_total[5m])
   )
   ```
3. **Recent policy PR correlation.** Was a policy / governance PR merged in
   the past 24 hours? Check `extensions/*/contract/` and policy schema
   change history.
4. **Per-actor anomaly check.** If actor labels exist, look for unusual
   per-actor deny concentration (may indicate adversarial pattern).
5. **Cross-reference workflow scenario 03.** Workflow drops may be caused
   by upstream policy changes.

## Action (operator + security-stakeholder observation only in v1)

- **No automated remediation** (no alert firing; no live_adapter_execution).
- Operator + security-stakeholder review whether the deny rate change is:
  - Expected (legitimate enforcement of new policy)
  - Anomalous (configuration drift; revert / amend ADR)
  - Suspicious (adversarial probing; escalate to security-stakeholder)

## Escalation Path

- **SEV-3 cadence:** no hard ack/escalation in v1 (operator-defined).
- Comms policy: `operator_only` (no owner / customer comms in advisory tier).
- If security-stakeholder review confirms suspicious pattern, operator may
  open a security incident under separate ADR / process (out of E-6-6 v1
  scope).

## Diagnostic Commands (safe / read-only)

```bash
# Current deny ratio
curl -s "http://prometheus:9090/api/v1/query?query=ao:slo:policy_deny_rate:rate1h"

# Per-policy/decision breakdown
curl -s "http://prometheus:9090/api/v1/query?query=sum%20by%20(policy_name%2C%20decision)%20(rate(ao_policy_check_total%5B5m%5D))"
```

## Out of Scope (this scenario)

- Authorization failure handling (`outcome="error"` not exposed in v1 metric
  surface).
- Adversarial / abuse-mitigation workflow (separate security incident
  scope).
- Active firing rule (deferred until baseline; E-5-5d follow-up slice).
- Automated policy rollback (governance change; cross-AI peer review
  required).

## References

- E-5-4 catalog: `../../sli-catalog.v1.json` (indicator: `policy_deny_rate`)
- E-5-5 README §4 advisory recording-only discipline
- HARD RULE Governance / Sistemik Bug (2026-05-05): policy bypass YASAK
- Severity matrix: `../severity-matrix.v1.json` (SEV-3; objective_kind: advisory_sli)
- Post-mortem template: `../incident-template.v1.md`
