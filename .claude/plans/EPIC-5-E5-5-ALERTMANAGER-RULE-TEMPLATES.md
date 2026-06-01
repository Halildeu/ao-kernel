# V5 Epic 5 E-5-5: Alertmanager Rule Templates

> **Cross-AI plan-time AGREE** — Codex thread `019e83af` (4 iters: REVISE/REVISE/REVISE/AGREE)
> **Implementer:** Anthropic Claude
> **Reviewer:** OpenAI Codex (cross-provider per HARD RULE — Cross-AI Peer Review 2026-05-05, 2026-05-14)

## 1. Scope (from V5 roadmap §Epic 5 E-5-5)

Generate PrometheusRule CRD YAML + AlertmanagerConfig CRD routing template +
operator runbook from the E-5-4 SLI/SLO catalog (`docs/sli-catalog.v1.json`).

**In scope:**
- Deterministic generator (catalog → PrometheusRule YAML)
- Recording rules for 3 ratio SLOs (4 windows × {sli, error} = 24 rules)
- MWMBR burn-rate alerts for 3 ratio SLOs (critical + warning = 6 alerts)
- 1 budget recording rule (recording-only; 0 active firing alerts)
- 2 advisory recording rules (recording-only; 0 active firing alerts)
- AlertmanagerConfig CRD routing to Microsoft Teams (HARD RULE Workspace Tooling)
- Raw Alertmanager fallback (`.example` dormant) for non-Operator deployments
- Slack dormant snippet (ADR-0029 mirror; asset-preserved for other tenants)
- Operator runbook (`docs/alertmanager/README.md`)
- 66 test invariants (12 windowizer + 3 generator + 5 CRD structure + 3 naming +
  4 budget + 3 advisory + 4 MWMBR + 4 PromQL whitelist + 5 AlertmanagerConfig +
  2 route matchers + 3 governance + 12 per-window parametrized + 3 dormant +
  1 promtool conditional + 3 utility coverage)

**Out of scope (HARD RULE — Long-term + Pre-Production guard):**
- No Prometheus/Alertmanager deployment
- No Sloth/Pyrra/Grafana SLO plugin integration
- No live alert delivery evidence
- No active budget threshold (operator-configured)
- No advisory spike firing rules (baseline-required)
- No Slack active route
- No tenant routing labels in v1
- No guard flag flip (3 guard flags const false)
- No production platform claim

## 2. Codex Iter Chain (plan-time)

### iter-1 plan-time REVISE — 5 must-close findings

| ID | Severity | Issue | Resolution |
|---|---|---|---|
| F1 | HIGH | Alertmanager receiver dialect ambiguous (`url_secret` not valid upstream); `AlertmanagerConfig` CRD vs raw Alertmanager YAML — pick one | Selected: AlertmanagerConfig CRD `monitoring.coreos.com/v1alpha1` + `urlSecret` SecretKeySelector + filename pin |
| F2 | HIGH | Budget objective active alert with `${MONTHLY_BUDGET_USD}` placeholder unsafe (Prometheus doesn't expand env vars; fake default risk) | Budget = recording-only; 0 active alerts; dormant operator overlay in README only |
| F3 | MEDIUM | Generator windowization sharp edge (blind regex on catalog PromQL) | Constrained allowlist `{5m, 30m, 1h, 6h}` + fail-closed pre/post conditions + subquery reject |
| F4 | MEDIUM | PromQL substring whitelist + `1 -` too weak for alert correctness | Recorded bounded error ratios `1 - clamp_max(clamp_min(sli, 0), 1)` + structural invariants + promtool conditional |
| F5 | LOW | Scope ↔ Option A conflict (generated YAML committed vs not) | Option C: generator + committed YAML + byte-equal drift test |

### iter-2 post-plan REVISE — 1 must-close + 10 hardening

| ID | Severity | Issue | Resolution |
|---|---|---|---|
| F6 | HIGH | Windowization regex doesn't handle label selectors (`{le="30"}`, `{final_state="completed"}`) | Tokenizer-aware regex `(?:\{[^{}]*\})?` + 3 golden tests per catalog ratio SLO |

10 hardening absorb (H1-H10):
- AlertmanagerConfig secret-bearing field discipline (no auth fields)
- Namespace/selector boundary documented in README §6
- Budget threshold leak invariant (FORBIDDEN_BUDGET_TOKENS list)
- Generator source no hardcoded thresholds (literal floats only in generated YAML)
- promtool CRD-aware extraction (`spec.groups` → temp rules file)
- Route matcher CRD object shape pin (v1alpha1)
- Per-provider latency golden assertion
- Auto-generated header completeness (catalog path + schema + generator + regen cmd)
- Raw fallback `.example` dormant pin
- README operator_owned + non-SLA disclaimer

### iter-3 post-impl REVISE — 1 must-close + 1 hardening tighten

| ID | Severity | Issue | Resolution |
|---|---|---|---|
| F7 | HIGH | Post-condition `if "[5m]" in new_expr: raise` breaks `target_window == "5m"` (fails own canonical 5m recording rule) | Target-window-aware check via generic `RANGE_SELECTOR_PATTERN`; `target_window == "5m"` becomes idempotent identity |

H1 tighten (auth full forbidden, not just ao-kernel-prefixed):
- Teams Power Automate is anonymous; no `authorization`, `bearerTokenSecret`, `basicAuth`, `oauth2` allowed in active config

H6 tighten (v1alpha1 object matcher pin, not legacy string):
- `matcher: {name: severity, value: critical|warning, matchType: "="}`

3 golden `target_window=="5m"` tests + parametrize includes 5m.

### iter-4 post-impl AGREE + ready_for_impl:true

```yaml
verdict: AGREE
ready_for_impl: true
must_close_findings: []
```

Codex final: "F7 absorb doğru kapatılmış: artık `5m` hedef pencere
legal/idempotent, label selector'lı catalog ifadeleri destekleniyor,
non-canonical range/subquery/no-rate durumları fail-closed, ve 3 ratio SLO × 4
pencere coverage var. Plan şu haliyle uygulanabilir."

## 3. Implementation Artifacts

| File | Lines | Purpose |
|---|---|---|
| `scripts/generate_alert_rules.py` | ~280 | Deterministic catalog → PrometheusRule YAML generator |
| `docs/alertmanager/prometheus-rules.v1.yml` | ~160 | Generated PrometheusRule CRD (24 + 6 + 1 + 2 = 33 rules) |
| `docs/alertmanager/alertmanagerconfig.routes.v1.yml` | ~50 | Active AlertmanagerConfig CRD (Teams routing) |
| `docs/alertmanager/alertmanager.routes.raw.v1.yml.example` | ~40 | Dormant raw Alertmanager YAML fallback |
| `docs/alertmanager/slack-dormant.snippet.v1.yml` | ~35 | Dormant Slack snippet (ADR-0029 mirror) |
| `docs/alertmanager/README.md` | ~180 | 9-section operator runbook |
| `tests/test_alertmanager_rule_templates.py` | ~700 | 67 invariants (66 + 1 conditional promtool) |
| `.claude/plans/EPIC-5-E5-5-ALERTMANAGER-RULE-TEMPLATES.md` | this | Plan doc + Codex chain audit |

## 4. Invariant Test Sections (67 total)

| Section | Count | Focus |
|---|---|---|
| 1. Windowizer | 12 | F6 + F7 absorb; label selector + target_window=5m idempotent |
| 2. Generator determinism | 3 | Idempotent + drift byte-equal + fail-closed |
| 3. PrometheusRule structure | 5 | apiVersion + kind + header + counts |
| 4. Recording rule naming | 3 | `ao:slo:<name>:<metric>_rate<window>` pattern |
| 5. Budget discipline | 4 | 1 recording, 0 alerts, no $$$ leak, no `${}` |
| 6. Advisory discipline | 3 | 2 recording, 0 alerts |
| 7. MWMBR determinism | 4 | Exact pair pin (14.4/1h/5m + 6/6h/30m) + threshold compute |
| 8. PromQL whitelist | 4 | ao_* families + bounded clamp + no outcome=error + provider label |
| 9. AlertmanagerConfig | 5 | v1alpha1 + urlSecret + no URL + no Slack + no auth |
| 10. Route matchers | 2 | Object form + severity only |
| 11. Governance | 3 | No guard flip + no production claim + README disclaimer |
| 12. Per-window parametrized | 12 | 3 SLO × 4 windows (includes 5m) |
| 13. Dormant artifact discipline | 3 | `.example` + Slack dormant + no real URL |
| 14. promtool conditional | 1 | Skip-if-not-available + CRD spec.groups extract |
| Bonus | 3 | Regex contract + bounded error shape + threshold compute |

## 5. Public Claim Discipline

- Plan doc + operator doc + generated YAML headers: explicit "Not SLA",
  "Not a production platform claim", "operator-tunable"
- 3 guard flags const false (catalog reads + invariant test asserts)
- This PR does NOT flip any guard
- This PR does NOT promote any advisory SLI to hard SLO
- This PR does NOT introduce runtime ingestion (Sloth/Pyrra/Alertmanager deploy)
- This PR does NOT commit any Teams/Slack webhook URL

## 6. Out-of-scope follow-up slices

| ID | Slice |
|---|---|
| E-5-5b | Sloth/Pyrra integration (operator choice) |
| E-5-5c | Multi-tenant `tenant_channel` label expansion (Epic 4 prerequisite) |
| E-5-5d | Advisory spike firing rules baseline-driven (30 days production-equivalent traffic) |
| E-5-5e | Slack reactivation chain (tenant demand-driven trigger) |
| E-5-5f | Alertmanager full deploy + operator smoke evidence (live ingestion) |
| E-5-5g | Teams Power Automate payload contract fixture (mock body example, no secrets) |
| E-5-5h | promtool + kubeconform CI integration hardening (hosted runner availability) |
| E-5-5i | Future uptime SLI (health/freshness metric prereq) |

## 7. References

- V5 roadmap: `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`
- E-5-4 catalog: `docs/sli-catalog.v1.json` (PR #799 MERGED)
- E-5-4 operator doc: `docs/SLI-SLO.md`
- E-5-4 schema: `ao_kernel/defaults/schemas/sli-catalog.schema.v1.json`
- Codex thread: `019e83af-dcdb-7c33-8f58-ed86686f068a` (4-iter REVISE/REVISE/REVISE/AGREE)
- ADR-0029: perf-alertmanager Hibrit D (Teams primary + Slack dormant)
- HARD RULE Workspace Tooling (2026-05-27): Microsoft Teams primary, Slack asset-preserved
- HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14): implementer Anthropic ≠ reviewer OpenAI
- Google SRE Workbook §6 (MWMBR alerting): https://sre.google/workbook/alerting-on-slos/
