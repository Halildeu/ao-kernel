# Epic 5 E-5-4 — SLI/SLO Definitions

**Status:** Implementing.
**Codex thread:** `019e8394` (plan-time REVISE, 6 critical absorb).
**Slice:** E-5-4 catalog + schema + doc (this PR).
**Out-of-scope (E-5-4 follow-up slices):** Alertmanager rule
templates (E-5-5), Grafana SLO panel rows, Sloth/Pyrra recording
rules, tenant-bound cost budgets (Epic 4), uptime SLI (requires
health/freshness metric).

## 1. Sorun

V5 Epic 5 E-5-4 plan: "SLI/SLO definitions (uptime, latency, cost
burn-rate)". Mevcut 8 `ao_*` metric ailesi (E-5-1 OTEL + E-5-2
Grafana dashboard + E-5-3a tracing primitives MERGED) — fakat SLI
spec + SLO target catalog + burn-rate alert formula yok. Operatör
production deploy için Sloth/Pyrra/Grafana SLO plugin'i bağlamadan
önce **catalog spec'i** şart.

## 2. Codex iter-1 absorb (REVISE)

| # | Codex bulgu | Absorb |
|---|---|---|
| 1 | "LLM call success rate" yanlış isim (usage accounting completeness farklı kavram) | `llm_usage_accounting_completeness` rename |
| 2 | `policy_check_total{outcome="error"}` mevcut değil — v1 enum `{allow, deny}` only | Hard SLO → advisory `policy_deny_rate` + test enforce `outcome` whitelist |
| 3 | Latency `histogram_quantile(p95)` burn-rate alert için kötü temel | Bucket ratio `{le="30"}` for alertable form; p95 doc-facing target only |
| 4 | Cost burn-rate **budget objective**, ratio SLO değil | Ayrı `objective_kind: budget_objective` + `unit: usd_per_month` + `target_status: placeholder` |
| 5 | Coordination claim takeover baseline yok | `advisory_sli` + `hard_slo: false` + `baseline_required: true` |
| 6 | Uptime out-of-scope (v1 `ao_*` family'de health/up metric yok) | Catalog'a `uptime_status: { in_scope: false, reason: "…" }` |
| 7 | YAML açık schema riskli | Canonical JSON + Draft 2020-12 schema + `additionalProperties: false` her yerde |
| 8 | SLO target değerleri operator-tunable, hard SLA değil | `operator_owned: const true` + `is_contractual_sla: const false` + `target_status` enum |
| 9 | E-5-2 dashboard SLO panel scope dışı | Plan doc §4 follow-up |
| 10 | Alert routing scope dışı | E-5-5 follow-up; bu PR yalnız formula + severity taxonomy |
| 11 | MWMBR pencere çiftleri standart değil | fast `1h/5m 14.4×` + slow `6h/30m 6×` (Google SRE Workbook) |
| 12 | "Production claim sızıntısı riski" | Plan doc guard metni: "candidate, not SLA, operator-owned, no production platform claim" |
| 13 | Runtime SLO measurement layer scope dışı | Bu PR spec + schema + doc; Sloth/Pyrra ayrı slice |

## 3. Değişiklik scope

### 3a. `ao_kernel/defaults/schemas/sli-catalog.schema.v1.json`

Draft 2020-12 + `additionalProperties: false` her yerde. 3
`objective_kind` enum + `allOf if/then` invariants:

| objective_kind | Required ek alanlar | Forbidden |
|---|---|---|
| `ratio_slo` | `slo_target` (0..1 exclusive) + `window` + `error_budget_alerts` (≥2 MWMBR) + `alerting_kind: const mwmbr` + `hard_slo: const true` | — |
| `budget_objective` | `unit: const usd_per_month` + `threshold_source: const operator_configured` + `target_status: const placeholder` + `alerting_kind: const budget_alarm` | `slo_target` |
| `advisory_sli` | `hard_slo: const false` + `baseline_required: const true` + `alerting_kind` | `slo_target` |

Schema-level `operator_owned: const true` + `is_contractual_sla:
const false` her indicator için.

Root `uptime_status.in_scope: const false` (v1 metric surface
sınırı).

### 3b. `docs/sli-catalog.v1.json` (canonical machine-readable)

6 indicator:

| Name | Kind | Target / unit |
|---|---|---|
| `llm_usage_accounting_completeness` | ratio_slo | 99.0% / 30d |
| `llm_latency_under_30s_ratio` | ratio_slo | 95.0% / 30d |
| `workflow_terminal_success_rate` | ratio_slo | 99.5% / 30d |
| `policy_deny_rate` | advisory_sli | spike-detect, baseline required |
| `monthly_cost_burn_projection_usd` | budget_objective | operator-configured placeholder |
| `coordination_takeover_rate` | advisory_sli | spike-detect, baseline required |

### 3c. `docs/SLI-SLO.md`

Operator-facing doc. 6 numbered section: Catalog Layout, Targets,
Burn-rate Alerts, Error Budget, Operator Responsibilities, Out of
Scope. Guard metinleri:
- "**Not SLA.** Not a production platform claim."
- "Operator-owned, operator-tunable"
- "Local/operator smoke is not production evidence"
- 3 guard flag explicit referenced

### 3d. `tests/test_sli_slo_catalog.py`

Invariants:
- Schema exists + Draft 2020-12 valid
- Root + every `$defs` object schema uses `additionalProperties: false`
- Catalog validates against schema
- `schema_version` + `service` const-pinned
- Guard flags const false + uptime out-of-scope
- 3 objective_kind types all present
- Ratio SLO MWMBR alert discipline (≥ 2, severity {critical, warning},
  burn_rate > 0, windows ∈ {5m, 30m, 1h, 6h})
- Ratio target in (0, 1) exclusive
- Budget objective pinned: usd_per_month + operator_configured +
  placeholder + budget_alarm + NO slo_target
- Advisory SLI pinned: hard_slo=false + baseline_required=true +
  spike + NO slo_target
- `operator_owned=true` + `is_contractual_sla=false` per indicator
- PromQL whitelist on 8 ao_* metric families + histogram suffixes
- `outcome="error"` label rejected (v1 enum is allow|deny only)
- Indicator names unique
- Doc has 6 required sections + non-SLA guard language + every
  catalog SLI named in doc
- Plan doc references Codex thread id + 3 objective_kind + guard
  flags + "not an SLA" / "candidate" / "operator-tunable" language

### 3e. Plan doc — this file.

## 4. Out-of-scope (E-5-4 follow-up slices)

| Concern | Slice |
|---|---|
| Service uptime SLI | Future — requires Prometheus `up` target OR a new ao-kernel health/freshness metric (8 v1 metric families do not expose this) |
| Tenant-bound cost budget (`$X/month per tenant`) | Epic 4 multi-tenancy follow-up — no tenant label on `ao_llm_cost_usd_total` in v1 |
| Alertmanager rule templates (PrometheusRule) | E-5-5 — separate slice |
| Grafana SLO panel rows | E-5-2 follow-up — current dashboard is shape-pinned at 8 panels |
| Sloth / Pyrra recording rule generation | Future — operator's choice of SLO layer |
| Hard SLO promotion for advisory SLIs | Post-baseline measurement + operator decision |
| `policy_check_total{outcome="error"}` semantics | Runtime metric change — operator/owner decision (v1 outcome enum is allow / deny only) |

## 5. Risk + Mitigation

| Risk | Mitigation |
|---|---|
| SLO numbers read as SLA | Plan doc + operator doc explicit "Not SLA" guard; `is_contractual_sla: const false` per indicator; `operator_owned: const true` |
| PromQL drift (unknown metric or label) | Test invariant whitelist `_ALLOWED_METRIC_FAMILIES` + `_ALLOWED_POLICY_OUTCOMES` |
| Budget vs ratio confusion | Schema `allOf if/then` invariants enforce kind-specific required fields and forbidden fields |
| MWMBR window drift | Schema enum on `long_window`/`short_window` + severity enum {critical, warning} |
| Uptime claim sızıntısı | Catalog `uptime_status.in_scope: const false` + reason min length |
| Catalog-doc drift | `test_sli_slo_doc_references_every_catalog_indicator` invariant — generator-free coupling |
| Marketing claim sızıntısı | Plan doc + operator doc + 3 guard flag invariants |
| Hard SLO promotion premature | Advisory SLI `baseline_required: const true` + schema-level pin |

## 6. Acceptance

- ✅ `pytest tests/test_sli_slo_catalog.py -x` → all invariants pass local
- ✅ `python3 -c "from jsonschema import Draft202012Validator; ..."` schema valid
- ✅ Plan doc — this file
- ⏳ Cross-AI post-impl review (Codex thread `019e8394` reply)
- ⏳ CI green (reviewer evidence file gerek)
- ⏳ Squash merge audit trail: Implementer Anthropic Claude / Reviewer OpenAI Codex
- ⏳ **Post-merge operator action**: Sloth / Pyrra / Grafana SLO plugin deploy + Alertmanager wiring (E-5-5)
- ⏳ **Post-baseline measurement**: `policy_deny_rate` + `coordination_takeover_rate` advisory SLI → hard SLO decision

## 7. Public claim discipline

> Per Codex 019e8394 absorb — this catalog defines **candidate
> operator SLOs**, not a contractual SLA. Targets are
> **operator-tunable**, not production platform claims:

- `support_widening_allowed=false`
- `production_platform_claim_allowed=false`
- `live_adapter_execution_allowed=false`

> E-5-4 ships catalog spec + schema + operator doc only. Runtime
> SLO ingestion (Sloth / Pyrra / Grafana SLO plugin), Alertmanager
> rule templates, Microsoft Teams Power Automate alert routing, and
> Grafana SLO dashboard rows are operator-responsibilities or
> follow-up slices. The catalog does NOT claim production
> readiness, does NOT enable any guard flag, does NOT promote any
> advisory SLI to a hard SLO.

## 8. Bağlantı

- V5 Epic 5 plan: `V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md` §3
  (Epic 5 Observability).
- Peer: Epic 5 E-5-1 OTEL prod tunables (PR #791 MERGED).
- Peer: Epic 5 E-5-2 Grafana dashboard 8 panels (PR-B5 baseline).
- Peer: Epic 5 E-5-3a W3C tracing primitives (PR #797 MERGED).
- Follow-up: Epic 5 E-5-5 Alertmanager rule templates + Teams routing.
- HARD RULE — Cross-AI Peer Review: implementer Anthropic Claude;
  reviewer OpenAI Codex (thread `019e8394`).
- HARD RULE — Workspace Tooling: Microsoft Teams primary, Slack
  asset-preserved başka tenants için (ADR-0029 mirror disiplini).
- HARD RULE — Uzun Vadeli Kalıcı Çözüm: PromQL whitelist + label
  enum reject + schema `additionalProperties: false` her yerde.
- HARD RULE — Continuous Autonomous Mode: bu turun 7. PR'ı;
  cross-AI peer reviewed sequential chain.
