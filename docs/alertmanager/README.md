# ao-kernel Alertmanager Rule Templates (V5 Epic 5 E-5-5)

> **Not SLA.** **Not a production platform claim.** This package ships
> **template / spec artifacts only** — PrometheusRule CRD YAML,
> AlertmanagerConfig CRD YAML, and an operator runbook. Runtime ingestion
> (Prometheus scrape, Alertmanager deployment, Sloth/Pyrra/Grafana SLO plugin,
> Microsoft Teams webhook provisioning, Power Automate flow setup) remains an
> **operator responsibility**.
>
> **Local/operator smoke is not production evidence.** No live alert delivery
> evidence is claimed. The three guard flags (`support_widening`,
> `production_platform_claim`, `live_adapter_execution`) remain `const false`.
>
> **Operator-owned tunable.** Burn-rate thresholds, SLO targets, alert routing,
> notification cadence — all operator-tunable. The catalog ships proposed
> initial defaults; production tuning is the operator's job after baseline
> measurement.

## 1. Layout

| File | Purpose |
|---|---|
| [`prometheus-rules.v1.yml`](prometheus-rules.v1.yml) | **Generated.** PrometheusRule CRD with recording rules + MWMBR burn-rate alerts. Source-of-truth = [`docs/sli-catalog.v1.json`](../sli-catalog.v1.json). |
| [`alertmanagerconfig.routes.v1.yml`](alertmanagerconfig.routes.v1.yml) | **Active route.** AlertmanagerConfig CRD (Prometheus Operator v1alpha1 dialect) routing severity=critical/warning to Microsoft Teams webhook receivers. |
| [`alertmanager.routes.raw.v1.yml.example`](alertmanager.routes.raw.v1.yml.example) | **Dormant.** Raw Alertmanager YAML fallback for non-Operator deployments. Operator substitutes `__TEAMS_WEBHOOK_URL__` placeholder out-of-band. |
| [`slack-dormant.snippet.v1.yml`](slack-dormant.snippet.v1.yml) | **Dormant.** Slack receiver template, asset-preserved for downstream tenants (HARD RULE Workspace Tooling 2026-05-27). NOT applied by ao-kernel. |
| [`../sli-catalog.v1.json`](../sli-catalog.v1.json) | E-5-4 catalog (semantic SSOT). |
| [`../../scripts/generate_alert_rules.py`](../../scripts/generate_alert_rules.py) | Deterministic generator (catalog → PrometheusRule YAML). |

## 2. SLO Recording Rules

For every ratio SLO in the catalog, the generator emits **8 recording rules**
(4 windows × 2 rule kinds):

| Rule name pattern | Purpose |
|---|---|
| `ao:slo:<name>:sli_ratio_rate<window>` | Raw SLI ratio over `<window>` (windowized from catalog `sli_expr`) |
| `ao:slo:<name>:error_ratio_rate<window>` | Bounded error ratio = `1 - clamp_max(clamp_min(<sli_recording_rule>, 0), 1)` |

Windows: **`5m`**, **`30m`**, **`1h`**, **`6h`** (matching the MWMBR pair pin —
critical 14.4× over 1h/5m and warning 6× over 6h/30m).

Per-provider label propagation is preserved for `llm_latency_under_30s_ratio`
(`sum by (provider)` in source → label flows through recorded SLI and error
ratios → alert labels carry `provider`).

## 3. Burn-rate Alerts (MWMBR — Google SRE Workbook §6)

Each ratio SLO emits **2 alerts** (critical + warning):

| Severity | Burn rate | Long window | Short window | Threshold formula |
|---|---|---|---|---|
| critical | 14.4× | 1h | 5m | `error_ratio_rate1h > 14.4 * (1 - target)` AND `error_ratio_rate5m > 14.4 * (1 - target)` |
| warning | 6× | 6h | 30m | `error_ratio_rate6h > 6 * (1 - target)` AND `error_ratio_rate30m > 6 * (1 - target)` |

Thresholds are **catalog-derived numeric literals** in the generated YAML —
the generator source contains no hardcoded burn thresholds.

Total active alerts: **3 ratio SLOs × 2 severities = 6 active firing alerts**.

## 4. Budget Objective & Advisory SLIs — Recording-Only

Codex 019e83af absorb F2: budget alerts and advisory spike alerts are
**recording-only** in v1.

- **Budget objective** (`monthly_cost_burn_projection_usd`): 1 recording rule;
  **0 active firing alerts**. Operator deploys a separate overlay with their
  own threshold + alarm rule when ready.
- **Advisory SLIs** (`policy_deny_rate`, `coordination_takeover_rate`): 2
  recording rules; **0 active firing alerts**. Spike detection requires
  baseline measurement (30 days production-equivalent traffic) + operator
  decision.

This prevents:
- Fake/default `$X/month` thresholds leaking into production semantics.
- Noisy `> 3*stddev_over_time(...[7d])` pseudo-baselines before real data
  exists.

### Dormant operator overlay for budget alarm (example only — NOT applied)

```yaml
# Operator owns this; ao-kernel does NOT commit it.
- alert: AOSLOMonthlyCostBurnProjectionOverThreshold
  expr: ao:slo:monthly_cost_burn_projection_usd:projection_rate1h > 1000  # operator-set
  for: 15m
  labels:
    severity: warning
    ao_slo: monthly_cost_burn_projection_usd
  annotations:
    summary: "Projected monthly LLM cost exceeds operator-configured budget"
```

## 5. Active Routing — Microsoft Teams Primary (ADR-0029)

The active `AlertmanagerConfig` CRD (`alertmanagerconfig.routes.v1.yml`)
routes:

- `severity=critical` → `ao-kernel-teams-critical` receiver
- `severity=warning` → `ao-kernel-teams-warning` receiver
- Default catch-all → `ao-kernel-teams-default` receiver

All three receivers point to the same Secret-referenced webhook URL
(`ao-kernel-teams-webhook`, key `url`) per HARD RULE Workspace Tooling
(2026-05-27) — **Microsoft Teams primary**.

### Microsoft Teams setup (operator action — NOT autonomous)

1. Operator creates a **Power Automate workflow**:
   - Trigger: "When a HTTP request is received"
   - Action: "Post adaptive card in chat or channel" → Teams channel selection
2. Operator copies the workflow's HTTP POST URL.
3. Operator seeds Vault key `TEAMS_WEBHOOK_URL` via stdin-pipe (D43 pattern):
   ```bash
   printf '%s' "$WEBHOOK" | ssh <cluster> vault kv patch kv/ao-kernel TEAMS_WEBHOOK_URL=-
   unset WEBHOOK
   ```
4. Operator creates Secret `ao-kernel-teams-webhook` via External Secrets
   Operator (ESO) — same namespace as the Alertmanager instance.
5. Alertmanager `webhook_configs` POSTs raw Alertmanager v4 JSON to the Power
   Automate flow; the flow transforms it into a Teams Adaptive Card. The
   ao-kernel snippet does **not** template the body.

### Authentication boundary

The active `AlertmanagerConfig` forbids all authentication mechanisms except
`urlSecret`:

- ❌ `httpConfig.authorization` (token leak risk via committed config)
- ❌ `httpConfig.bearerTokenSecret` (Teams Power Automate is anonymous —
  authentication is the URL secret itself)
- ❌ `httpConfig.basicAuth`
- ❌ `httpConfig.oauth2`

This is enforced by `tests/test_alertmanager_rule_templates.py`.

## 6. Prometheus Operator Deployment Boundary

The committed CRD YAML is for **Prometheus Operator v0.66.0+** with:

- `PrometheusRule` ruleSelector matching `app.kubernetes.io/name=ao-kernel`
- `AlertmanagerConfig` configSelector matching the same label set
- Same namespace as the Prometheus + Alertmanager instances (no cross-namespace
  selector reference in v1 — Epic 4 multi-tenancy prerequisite)

For non-Operator deployments, the `alertmanager.routes.raw.v1.yml.example`
dormant fallback is the substrate. Operator inject path: replace
`__TEAMS_WEBHOOK_URL__` placeholder via Helm value, Kustomize patch, or
Vault-templated Secret injection.

## 7. Slack Reactivation Chain (Dormant — Other Tenants Only)

ao-kernel does NOT use Slack. The `slack-dormant.snippet.v1.yml` exists ONLY
to preserve the reactivation pattern for downstream/multi-tenant deployments
that have an existing Slack workspace (HARD RULE Workspace Tooling 2026-05-27
— "biz teams ile devam edelim, slack altyapısını bozma başka firmalar
kullanıbilir").

### Reactivation chain (operator action; tenant demand-driven trigger)

1. Operator provisions Slack workspace + incoming-webhook URL.
2. Operator seeds Vault key `SLACK_WEBHOOK_URL` via stdin-pipe (D43 pattern):
   ```bash
   printf '%s' "$WEBHOOK" | ssh <cluster> vault kv patch kv/ao-kernel SLACK_WEBHOOK_URL=-
   unset WEBHOOK
   ```
3. Operator creates Secret `ao-kernel-slack-webhook` via ESO from Vault.
4. Operator copies snippet contents into the AlertmanagerConfig CRD
   `spec.receivers` array; adds severity-based routes per channel preference
   (e.g. `#ao-kernel-alerts-critical` + `#ao-kernel-alerts-warning`).
5. Operator applies — **only after explicit tenant demand-driven trigger**
   (no autonomous activation; no parallel delivery to Teams + Slack).

ao-kernel v1 active routes do NOT include any Slack receiver. Tests assert
zero Slack receivers in active routes.

## 8. Out of Scope (E-5-5 follow-up slices)

| Concern | Future slice |
|---|---|
| Sloth / Pyrra integration | E-5-5b (operator choice; current generator is native naming, generator-agnostic) |
| Multi-tenant `tenant_channel` matcher label | E-5-5c (Epic 4 multi-tenancy prerequisite) |
| Advisory spike firing rules | E-5-5d (after 30 days production-equivalent baseline measurement + operator decision) |
| Slack reactivation activation | E-5-5e (tenant demand-driven trigger; operator action only) |
| Alertmanager full deploy + smoke evidence | E-5-5f (operator action; live ingestion) |
| Teams Power Automate payload contract fixture | E-5-5g (mock body example without secrets) |
| `promtool` + `kubeconform` CI integration | E-5-5h (hosted-runner availability dependent) |
| Future uptime SLI | E-5-5i (requires health/freshness metric or Prometheus `up` target — `uptime_status.in_scope: false` in catalog) |

## 9. References

- V5 roadmap: [`../../.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`](../../.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md)
- E-5-4 catalog: [`../sli-catalog.v1.json`](../sli-catalog.v1.json)
- E-5-4 operator doc: [`../SLI-SLO.md`](../SLI-SLO.md)
- Grafana dashboard: [`../grafana/README.md`](../grafana/README.md)
- HARD RULE Workspace Tooling (2026-05-27): Microsoft Teams primary
- ADR-0029 (perf-alertmanager Hibrit D): Teams primary + Slack dormant
- Google SRE Workbook §6 (MWMBR alerting): https://sre.google/workbook/alerting-on-slos/
- Codex cross-AI plan-time AGREE: thread `019e83af` (4 iters: REVISE/REVISE/REVISE/AGREE)
