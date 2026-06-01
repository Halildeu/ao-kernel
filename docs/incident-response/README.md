# ao-kernel Incident Response Playbook (V5 Epic 6 E-6-6)

> **Not SLA.** **Not a production platform claim.** This playbook defines a
> proposed, operator-owned incident response process — severity matrix,
> escalation policy, post-mortem template, scenario runbooks. MTTR targets
> are tunable defaults; **not contractual service-level commitments**. The
> three guard flags (`support_widening`, `production_platform_claim`,
> `live_adapter_execution`) remain `const false`.
>
> **Local/operator smoke is not production evidence.** This package ships
> **docs / schema / tests only** — no live PagerDuty/Opsgenie integration,
> no ChatOps bot, no automated incident dispatch, no real Teams/Slack
> webhook URLs, no customer/regulatory disclosure authority. Microsoft Teams
> is the primary internal channel (HARD RULE Workspace Tooling 2026-05-27 +
> ADR-0029).
>
> **Operator-owned tunable.** Concrete on-call assignments, contact paths,
> webhook URLs, integration tokens — all operator responsibility. This
> repository ships the **process contract** (schema-backed); it does not
> ship secrets, contacts, or live dispatch.

## 1. Prerequisites

E-6-6 consumes E-5-5 alert receipt. Active references:

- [`../alertmanager/prometheus-rules.v1.yml`](../alertmanager/prometheus-rules.v1.yml)
  — PrometheusRule CRD with MWMBR burn-rate alerts (post **PR #800** merge).
- [`../alertmanager/alertmanagerconfig.routes.v1.yml`](../alertmanager/alertmanagerconfig.routes.v1.yml)
  — Microsoft Teams routing CRD.
- [`../sli-catalog.v1.json`](../sli-catalog.v1.json) — E-5-4 SLI/SLO catalog
  (6 indicators across 3 objective_kind variants).
- [`../SLI-SLO.md`](../SLI-SLO.md) — E-5-4 operator-facing SLI/SLO doc.

If PR #800 has not landed yet at the time you read this, see PR status at:
https://github.com/Halildeu/ao-kernel/pull/800. This playbook references
exact alert names from PR #800; if those paths are absent in your checkout,
treat E-6-6 references as deferred placeholders.

## 2. Layout

| File | Purpose |
|---|---|
| [`severity-matrix.v1.json`](severity-matrix.v1.json) | **Schema-backed.** 3-tier severity classification (SEV-1/2/3) with typed bridge from Alertmanager severity + E-5-4 objective_kind. |
| [`escalation-policy.v1.yml`](escalation-policy.v1.yml) | **Schema-bearing.** 3-stage on-call ladder + severity-specific cadence + comms boundary. |
| [`incident-template.v1.md`](incident-template.v1.md) | Blameless post-mortem template (Google SRE). |
| [`scenarios/01-llm-usage-accounting-drop.md`](scenarios/01-llm-usage-accounting-drop.md) | SEV-1 triage runbook. |
| [`scenarios/02-llm-latency-burn.md`](scenarios/02-llm-latency-burn.md) | SEV-1/SEV-2 per-provider latency triage. |
| [`scenarios/03-workflow-success-drop.md`](scenarios/03-workflow-success-drop.md) | SEV-1/SEV-2 terminal-state failure triage. |
| [`scenarios/04-cost-burn-breach.md`](scenarios/04-cost-burn-breach.md) | SEV-2 budget objective / operator threshold-driven. |
| [`scenarios/05-coordination-takeover-spike.md`](scenarios/05-coordination-takeover-spike.md) | SEV-3 advisory observability. |
| [`scenarios/06-policy-deny-spike.md`](scenarios/06-policy-deny-spike.md) | SEV-3 advisory security observability. |
| [`../../ao_kernel/defaults/schemas/severity-matrix.schema.v1.json`](../../ao_kernel/defaults/schemas/severity-matrix.schema.v1.json) | JSON Schema (Draft 2020-12) for `severity-matrix.v1.json`. |

## 3. Severity Matrix (3 Tiers)

3 tiers map 1-to-1 with Alertmanager severity + E-5-4 objective_kind:

| Tier | Alertmanager severity | E-5-4 objective_kind | MTTR target | Ack timeout | Cadence | Comms |
|---|---|---|---|---|---|---|
| **SEV-1** | `critical` | `ratio_slo` | 60 min | 15 min | 15 min | `owner_immediate` |
| **SEV-2** | `warning` | `ratio_slo` + `budget_objective` | 240 min | 30 min | 60 min | `owner_business_hours` |
| **SEV-3** | `advisory` | `advisory_sli` | operator-defined | operator-defined | operator-defined | `operator_only` |

MTTR targets, ack timeouts, and escalation cadences are **operator-tunable
proposals**, not contractual SLA commitments.

## 4. Escalation Policy (3 Stages)

Per `escalation-policy.v1.yml`:

1. **Primary on-call** — receives Alertmanager → Microsoft Teams
   notification first.
2. **Secondary on-call** — escalation target if primary fails to ack within
   tier cadence.
3. **Engineering manager** — final escalation stage for SEV-1 unack chain.

Concrete person/team assignment is operator responsibility (NOT shipped in
this repo). Notification channels:

- **Primary:** Microsoft Teams (operator-provisioned Power Automate webhook
  per HARD RULE Workspace Tooling 2026-05-27 + ADR-0029).
- **Secondary:** Operator-provisioned email SMTP fallback.

## 5. Incident Lifecycle

1. **Detection.** E-5-5 PrometheusRule MWMBR alert fires → Alertmanager
   route by `severity` matcher → Microsoft Teams Power Automate webhook →
   Adaptive Card in operator Teams channel.
2. **Acknowledge.** Primary on-call ack within tier cadence (SEV-1 15 min,
   SEV-2 30 min, SEV-3 operator-defined).
3. **Triage.** Follow the relevant scenario runbook (see `scenarios/`).
4. **Mitigation.** Operator decides; ao-kernel does NOT auto-mitigate
   (`live_adapter_execution_allowed=false`).
5. **Resolution.** Operator confirms recovery; alert auto-clears.
6. **Post-mortem.** Use `incident-template.v1.md`; blameless RCA;
   distribution operator+owner+security-stakeholder only (v1).
7. **Corrective action.** Each post-mortem corrective action MUST have
   owner + due date + linked artifact (ADR, GitHub issue, or PR).

## 6. Communication Policy

### 6.1 Internal (operator ↔ owner)

- **Primary channel:** Microsoft Teams (HARD RULE Workspace Tooling
  2026-05-27 + ADR-0029).
- **Slack status:** dormant asset-preserved (for downstream tenants only;
  see [`../alertmanager/slack-dormant.snippet.v1.yml`](../alertmanager/slack-dormant.snippet.v1.yml)
  post PR #800 merge).
- **Cadence:** SEV-1 = immediate during incident; SEV-2 = business hours;
  SEV-3 = operator-only observation.

### 6.2 External (operator-owned; out of scope for v1)

- Stakeholder / customer communications are **out of scope for E-6-6 v1**.
- ao-kernel does not template, send, or store customer-facing comms.

### 6.3 PII Handling

- Incident artifacts (post-mortems, scenarios, evidence) MUST NOT contain
  end-user PII (email, phone, IP, account identifiers).
- Allowed placeholders: `REDACTED`, `PLACEHOLDER`, `TBD`, `__SECRET__`,
  `example.com`, `redacted.example`.
- Test invariant (`test_incident_artifacts_have_no_secrets_or_pii`) scans
  artifacts with a targeted secret/PII scanner.

### 6.4 Credential Handling

- No real Microsoft Teams webhook URL, no Slack webhook URL, no Vault
  token, no GitHub PAT, no API key, no JWT/Bearer token, no AWS access
  key may appear in incident artifacts.
- Operator owns credential provisioning (Vault stdin-pipe pattern D43;
  see E-5-5 README §5).

### 6.5 Regulatory Disclosure Boundary (Codex F4 absorb)

This playbook does NOT include legal/regulatory disclosure templates or
authority. Regulatory disclosure (GDPR breach notification, SOC2 incident
reporting, HIPAA, jurisdiction-specific obligations) is jurisdiction-
specific and requires **legal/security-owner decision**. Operator MUST
consult legal/compliance counsel before any external disclosure. ao-kernel
ships no regulatory promise.

### 6.6 Vendor Escalation Boundary (Codex F4 absorb)

For provider outages (LLM provider transport failure, embedding API down),
the playbook references vendor escalation as an external handoff:

- Operator opens vendor support ticket out-of-band.
- Operator updates SEV-1 timeline with vendor case ID.
- Operator does NOT promise vendor SLA terms in ao-kernel incident comms.
- Customer comms about vendor outage = operator/owner decision (out of
  scope for v1).

## 7. Operator Deployment Boundary

This package ships **process contract + templates + schema + tests**. The
operator owns the following deployment substrate:

1. **Alertmanager + Microsoft Teams Power Automate flow** (see E-5-5 README
   §5 for setup chain).
2. **On-call rotation tool** (operator choice: e.g. PagerDuty, Opsgenie,
   manual rotation calendar; v1 does NOT integrate).
3. **Incident tracker** (operator choice: Linear, Jira, GitHub Issues; v1
   does NOT mandate).
4. **Post-mortem distribution** (operator choice: Confluence, Notion, repo
   wiki; v1 ships template only).
5. **Concrete contact paths** (NOT shipped in repo; operator owns
   `escalation-policy.v1.yml` overlay or supplementary config).

## 8. Cross-AI Peer Review Discipline

Per HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14):

- Implementer Anthropic Claude → Reviewer OpenAI Codex (this PR).
- Plan-time consensus required for any change to severity matrix,
  escalation policy schema, or scenarios contract.
- Codex iter chain audit trail in
  [`../../.claude/plans/EPIC-6-E6-6-INCIDENT-RESPONSE-PLAYBOOK.md`](../../.claude/plans/EPIC-6-E6-6-INCIDENT-RESPONSE-PLAYBOOK.md).

## 9. Out of Scope (E-6-6 follow-up slices)

| ID | Slice | Rationale |
|---|---|---|
| **E-6-6b** | Vendor escalation matrix (concrete) | Provider outage handoff directly tied to LLM latency/transport incidents; prioritized first per Codex 019e83c3 absorb. |
| E-6-6c | PagerDuty / Opsgenie integration | Operator choice; v1 does not mandate. |
| E-6-6d | ChatOps bot (interactive triage) | Live interactive layer; out of v1 scope. |
| E-6-6e | Public post-mortem template | Stakeholder-facing version; v1 keeps distribution operator+owner+security only. |
| E-6-6f | Regulatory disclosure template | Jurisdiction-specific; requires legal counsel input. |
| E-6-6g | Customer comms template (PII-safe) | Operator-owned; deferred. |

## 10. References

- V5 roadmap: [`../../.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`](../../.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md)
- E-5-4 catalog: [`../sli-catalog.v1.json`](../sli-catalog.v1.json) (PR #799)
- E-5-4 operator doc: [`../SLI-SLO.md`](../SLI-SLO.md)
- E-5-5 alerts (post PR #800): `docs/alertmanager/` directory
- E-5-1 OTEL tunables (PR #791)
- E-5-3a W3C trace context (PR #797)
- ADR-0029: perf-alertmanager Hibrit D (Teams primary + Slack dormant)
- HARD RULE Workspace Tooling (2026-05-27): Microsoft Teams primary
- HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14)
- Google SRE Workbook §13 (Postmortem culture): https://sre.google/workbook/postmortem-culture/
- Codex cross-AI plan-time AGREE: thread `019e83c3` (2 iters: REVISE → AGREE)
