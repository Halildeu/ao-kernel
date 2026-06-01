# ao-kernel SLI/SLO Catalog (V5 Epic 5 E-5-4)

> **Not SLA.** **Not a production platform claim.** This document
> defines candidate, **operator-owned** Service Level Indicators
> and Objectives. Targets are tunable defaults, not contractual
> service-level commitments. The three guard flags
> (`support_widening`, `production_platform_claim`,
> `live_adapter_execution`) remain `const false`.
>
> **Local/operator smoke is not production evidence.** Alert
> delivery (Alertmanager → Microsoft Teams Power Automate workflow)
> and Sloth/Pyrra/Grafana SLO plugin deployment are **operator
> responsibilities**; this PR ships catalog spec + schema only.

## 1. Catalog Layout

The machine-readable catalog lives at
[`docs/sli-catalog.v1.json`](sli-catalog.v1.json) and is validated by
the schema at
[`ao_kernel/defaults/schemas/sli-catalog.schema.v1.json`](../ao_kernel/defaults/schemas/sli-catalog.schema.v1.json).

Each indicator declares one of three `objective_kind` values:

| Kind | Meaning | Required fields |
|---|---|---|
| `ratio_slo` | Hard SLO with target ∈ (0, 1) | `slo_target`, `window`, `error_budget_alerts` (≥2 MWMBR) |
| `budget_objective` | USD/time-window budget | `unit`, `threshold_source`, `target_status: placeholder` |
| `advisory_sli` | Observability signal | `hard_slo: false`, `baseline_required: true` |

## 2. Targets (proposed initial defaults — operator-tunable)

| SLI | Kind | Target | Window | Source metric family |
|---|---|---|---|---|
| `llm_usage_accounting_completeness` | ratio_slo | **99.0 %** | 30 d | `ao_llm_call_duration_seconds_count` / (`ao_llm_call_duration_seconds_count` + `ao_llm_usage_missing_total`) — accounted / total |
| `llm_latency_under_30s_ratio` | ratio_slo | **95.0 %** | 30 d | `ao_llm_call_duration_seconds_bucket{le="30"}` / `_count` |
| `workflow_terminal_success_rate` | ratio_slo | **99.5 %** | 30 d | `ao_workflow_duration_seconds_count{final_state="completed"}` / `_count` |
| `policy_deny_rate` | advisory_sli | spike-detect | — | `ao_policy_check_total{outcome="deny"}` / total |
| `monthly_cost_burn_projection_usd` | budget_objective | operator-configured | rolling 1 h × 30 d | `ao_llm_cost_usd_total` |
| `coordination_takeover_rate` | advisory_sli | baseline-required | rolling 1 h | `ao_claim_takeover_total` / `ao_claim_active_total` |

> **Operator-facing latency note.** `llm_latency_under_30s_ratio` is
> the alertable form. The operator-facing target *also* asks for
> `histogram_quantile(0.95, …) < 30s` per provider as a dashboard
> guideline; the bucket-ratio is what the burn-rate alert evaluates
> (Codex 019e8394 absorb — p95 expressions are not numerically
> stable enough to drive MWMBR alerts).

## 3. Burn-rate Alerts (MWMBR)

Every ratio SLO declares the same Google SRE Workbook
multi-window multi-burn-rate alert pair:

| Severity | Burn rate | Long window | Short window | Meaning |
|---|---|---|---:|---|
| critical | 14.4× | 1 h | 5 m | Budget exhausts in ~2 days if sustained |
| warning | 6× | 6 h | 30 m | Budget exhausts in ~5 days if sustained |

Budget objectives use `alerting_kind: budget_alarm` (a single
threshold crossing); advisory SLIs use `alerting_kind: spike`
(deviation from baseline once measured).

## 4. Error Budget

For a 99.0 % ratio SLO on a 30-day window, the error budget is
**0.01 × 30 days = 7.2 hours of failed-event time per month** (in
event-count terms, 1 % of evaluated events). Burn-rate alerts fire
when the rolling consumption rate would exhaust the budget faster
than the window admits.

## 5. Operator Responsibilities

This catalog is a **spec**. Runtime ingestion requires the operator
to deploy:

1. **Prometheus** scraping `ao-kernel metrics export` textfiles (see
   `docs/grafana/README.md` for the textfile collector recipe).
2. **SLO measurement layer**: Sloth / Pyrra / Grafana SLO plugin /
   custom recording rules. The catalog is generator-agnostic.
3. **Alertmanager + delivery** (Microsoft Teams Power Automate
   workflow per ADR-0029 / repo-global HARD RULE) for routing
   `critical` / `warning` severity. *E-5-5 follow-up slice* delivers
   the Alertmanager rule templates; this slice does NOT.
4. **Budget configuration**: `monthly_cost_burn_projection_usd`
   threshold is `operator_configured` (catalog ships placeholder
   only).
5. **Baseline measurement**: `policy_deny_rate` and
   `coordination_takeover_rate` advisory SLIs need at least 30 days
   of production-equivalent traffic before a hard SLO can be proposed.

## 6. Out of Scope (E-5-4 follow-up slices)

| Concern | Slice |
|---|---|
| Service uptime SLI | Future — requires Prometheus `up` target OR a new ao-kernel health/freshness metric (8 v1 metric families do not expose this) |
| Tenant-bound cost budget (`$X/month per tenant`) | Epic 4 multi-tenancy follow-up — no tenant label on `ao_llm_cost_usd_total` in v1 |
| Alertmanager rule templates | E-5-5 |
| Grafana SLO panel rows | E-5-2 follow-up (current dashboard is shape-pinned at 8 panels) |
| Sloth / Pyrra recording rule generation | Future — operator's choice of SLO layer |
| Hard SLO for advisory SLIs | Post-baseline measurement + operator decision |
| `policy_check_total{outcome="error"}` semantics | Runtime metric change — operator/owner decision (Codex 019e8394 absorb — `outcome` enum is `{allow, deny}` only in v1) |

## 7. References

- V5 roadmap: [`.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`](../.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md)
- E-5-2 dashboard: [`docs/grafana/README.md`](grafana/README.md)
- E-5-1 OTEL prod tunables: PR #791 merged
- E-5-3a tracing primitives: PR #797 merged
- Cross-AI peer review thread: Codex `019e8394` (plan-time)
- Google SRE Workbook §6 (MWMBR alerting): https://sre.google/workbook/alerting-on-slos/
