# PR-B5 Implementation Plan v4 — Metrics Export (Prometheus Textfile + `[metrics]` Extra)

**Tranche B PR 5/9 — plan v4, post-Codex iter-2 PARTIAL absorb.** v3 iter-2 2 dar bulgu: (1) `duration_ms` source `transport_result.elapsed_ms` (pre_dispatch_reserve entry değil); (2) `--since` timezone-aware contract.

**v4 key absorb (Codex iter-2 PARTIAL)**:

- **`duration_ms` canonical source = `transport_result["elapsed_ms"]`**: v3'te `pre_dispatch_reserve()` entry'den monotonic delta idi — reserve/normalize/reconcile overhead dahil, saf LLM transport süresi değil. v4 fix: `execute_request()` zaten `elapsed_ms` döndürüyor (llm.py:541); `governed_call` bunu `post_response_reconcile(..., elapsed_ms=...)` kwarg'ı olarak middleware'e geçer. Middleware emit'te `"duration_ms": elapsed_ms` (pre-computed transport value).

- **`--since` timezone-aware contract**: `_internal/shared/utils.py:116` `parse_iso8601` helper naive kabul ediyor; evidence ts aware → naive/aware kıyaslama TypeError veya semantic drift. v4 fix: debug-query `--since` input'u timezone zorunlu (`Z` veya `+HH:MM`); naive string → argparse error `--since: timezone required, use Z or +HH:MM offset`.

- **Docs note**: `usage_missing` path `llm_spend_recorded` emit etmez (cost/middleware.py:261-290), dolayısıyla duration histogram'a usage_missing çağrıları girmez. R14 risk (Low) + docs §6 not.

**v3 key absorb (Codex iter-1 REVISE, taşınan):**

**Head SHA:** `ac12e25` (PR #100 B2 e2e merge sonrası). Base branch: `main`. Active branch: `claude/tranche-b-pr-b5` (oluşturuldu).

**v3 key absorb (Codex iter-1 REVISE):**

- **§2 LLM duration source yanlış — `adapter_invoked/returned` generic executor event**: LLM facade metric değil; `attempt` join guarantee yok. v3 fix: `llm_spend_recorded.duration_ms` (B2 event'ine +1 field additive). Ayrı `llm_invoked/returned` event pair X2 alternatifi değerlendirildi; X1 (minimal delta) seçildi. Cost-dormant → LLM metric family absent.

- **§2.6 `--since`/`--run` Prometheus textfile semantiğini bozuyor**: windowed/run-scoped export → counter reset. v3 fix: default textfile mode cumulative-only; `--since`/`--run` taşındı → ayrı `ao-kernel metrics debug-query` subcommand (JSON output, non-textfile).

- **§2 LLM metrics cost policy'ye bağımlı — plan açıkça söylemiyor**: v3 fix: `metrics=true + cost=false` → LLM metric family absent (provider label present etmez, zero-synthetic değil). Docs: "LLM observability requires cost tracking enabled".

- **§2.3 usage_missing source plan çelişkili**: mapping'te `llm_spend_recorded`, checklist'te `llm_usage_missing` event. Checklist doğru; v3 fix: mapping'de `llm_usage_missing` event-source olarak netleştirildi.

- **§2.8 Grafana "8 panel + shape test" yetersiz**: v3 fix: §2.8'e panel→metric/query matrix table eklendi.

- **Histogram LLM bucket upper 300 → 600**: GPT-4-turbo 450s outlier overflow tolerance.

- **Cardinality hard warning**: `agent_id`/`model` free-string. v3 METRICS.md §6: "asla ephemeral/uniq-per-request kullanmayın" uyarısı sert.

- **`--since` ISO-8601 only** (debug-query'de): `_internal/shared/utils.py:116` parse helper kullan.

- **`live_claims_count()` LOC 15 → 20-30**: lock/index reconcile realistik.

**v3 5 Q Codex kararları (plan §9'da detaylı):**

| Q | Karar | Gerekçe |
|---|---|---|
| Q1 claim gauge | **A** (live-count helper) | Evidence-net race-prone; registry single source |
| Q2 dormant CLI | **exit 0 + banner** | B1 parity yanlış analogy; observability surface |
| Q3 workflow_cancelled | **A** (state.v1.json.completed_at) | Yeni event ihtiyaç yok |
| Q4 extract_usage_strict | **skip** | Canonical source = B2 evidence; duplicate SOT riski |
| Q5 bucket knob | **Yok v1'de; upper 300→600** | Knob deferred; default expand |

**v2 key absorb (v1 code verification — aynı, v3'e taşınan):**

**v2 key absorb (code verification — v1 hataları):**

- **v1 §2.3 metric mapping yanlış — `policy_checked` outcome**: Her step'te `policy_checked` emit olur (violations_count içerir); `policy_denied` ayrıca violations>0 durumunda emit. v2 doğru mapping: `violations_count==0 → outcome="allow"`, `>0 → outcome="deny"` (tek event tarama).

- **v1 §2.3 LLM metric source yanlış**: `adapter_invoked`/`adapter_returned` payloadları `provider`/`tokens` içermez — duration `(returned.ts − invoked.ts)`'den; tokens/provider/cost **B2 `llm_spend_recorded`** event'inden (`provider_id`, `model`, `tokens_input`, `tokens_output`, `cached_tokens`, `cost_usd`).

- **v1 §2.3 fail-open corrupt JSONL yanlış — timeline.py fail-closed**: `timeline.py:70-74` `json.JSONDecodeError → ValueError`. v2 fix: `EvidenceSourceCorruptedError` fail-closed. CLAUDE.md §2 audit-trail invariant.

- **v1 `_KINDS 24` outdated**: B2 sonrası **27** (+3 cost kinds).

- **v1 `extract_usage_strict` derivation'da kullanılamaz**: raw response bytes okur; evidence event'te bytes yok. B2 middleware tokens'ı zaten event payload'a yazar. v2 pin: derivation yalnız event payload okur.

- **v1 `claim_active` gauge net-count yanlış**: `sum(acquired)−sum(released)−sum(expired)` expired/takeover race'de negatif olabilir. v2 default A: coordination registry `live_claims_count()` helper (~15 LOC). Codex Q1.

- **v1 cost derivation deferred — gereksiz**: B2 shipped; `llm_spend_recorded` read-only ücretsiz. v2 scope-in: `ao_llm_cost_usd_total{provider}` + `ao_llm_usage_missing_total{provider}`.

**Scope genişletmeler (v2):**

- `ao_llm_usage_missing_total` metrik (B2 usage-miss audit observability)
- `ao_llm_cost_usd_total` metrik (B2 cost shipped)
- `EvidenceSourceCorruptedError` error type (fail-closed semantic)
- `workflow_cancelled` final_state gap tespiti (Q3 Codex'e)
- Histogram buckets LLM vs workflow ayrımı (workflow insan onay saatlik olabilir)
- Cron recipe + `docs/grafana/README.md` operator UX

**v1'den devam eden (doğrulandı) kararlar:**

- Prometheus textfile primary; OTEL bridge YOK (METRICS.md §5 + docfix #98)
- `[metrics]` ve `[otel]` bağımsız extras
- Low-cardinality default labels; advanced schema-closed enum `{model, agent_id}` (B0 pin)
- Dormant default `enabled=false`
- Evidence-derived strategy (B2 conflict-free)
- Stateless CLI snapshot (cron-friendly)
- Grafana dashboard scope-in

## 1. Amaç

PR-B0 foundation kontratını runtime'a bağla: `ao_kernel/metrics/` yeni public package + `[metrics]` optional extra (lazy import, no-op fallback — `telemetry.py` mirror). Prometheus textfile export CLI. **Evidence-derived derivation** (events.jsonl read-only scan) + **B2 cost events shipped** (cost metrics scope-in). Dormant default; advanced labels opt-in schema-closed enum.

### Kapsam özeti (v3)

| Katman | Modül | Satır (est.) |
|---|---|---|
| Public package | `ao_kernel/metrics/__init__.py` | ~40 |
| Policy | `ao_kernel/metrics/policy.py` | ~110 |
| Registry adapter | `ao_kernel/metrics/registry.py` | ~200 |
| Evidence → metric | `ao_kernel/metrics/derivation.py` | ~310 (+`completed_at` cancel derive) |
| Textfile emitter | `ao_kernel/metrics/export.py` | ~140 |
| Debug-query CLI (v3 yeni) | `ao_kernel/_internal/metrics/debug_query.py` | ~110 |
| Typed errors | `ao_kernel/metrics/errors.py` (5 types) | ~70 |
| CLI handler | `ao_kernel/_internal/metrics/cli_handlers.py` + `cli.py` delta | ~130 + ~40 delta |
| Coordination delta | `coordination/registry.py::live_claims_count()` (Q1 A) | ~25 delta (realistic) |
| **B2 cost/middleware delta (v3)** | `llm_spend_recorded.duration_ms` additive field | ~10 delta + ~1 test update |
| `pyproject.toml` delta | `[metrics]` extra + `enterprise` widen | ~6 delta |
| Grafana dashboard | `docs/grafana/ao_kernel_default.v1.json` | ~220 |
| Tests | ~45 test, 5 test dosyası (+debug-query) | ~580 |
| Docs | `docs/METRICS.md` §2/§6/§7 delta (+cost-disjunction, cardinality warn) + `docs/grafana/README.md` (NEW) | ~110 delta + 20 new |
| CHANGELOG | `[Unreleased]` PR-B5 | ~60 |
| **Toplam** | 1 yeni package + 1 internal debug-query + 3 code delta + 1 Grafana + ~45 test + docs | **~2000 satır** |

- Yeni evidence kind: **0** (B5 emit YAPMAZ; B2 event'e 1 field additive)
- Yeni adapter capability: 0
- Yeni core dep: 0
- Yeni error type: **5** (+`EvidenceSourceCorruptedError`)

**Runtime LOC**: ~900 (bounded ~1000 Codex hedefi altında).

## 2. Scope İçi

### 2.1 `policy.py` — `coordination/policy.py` mirror

`MetricsPolicy(enabled, labels_advanced, version)` + `load_metrics_policy(workspace_root, *, override=None)`. B0 schema validate. Runtime defence-in-depth: `allowlist` subset of `{"model", "agent_id"}`; bypass → `InvalidLabelAllowlistError`.

### 2.2 `registry.py` — prometheus_client lazy wrappers

`telemetry.py` mirror. `_check_prometheus()` cached bool; `is_metrics_available()`; `build_registry(policy)` → `CollectorRegistry | None`.

**8 metrik** (v3; +`duration_ms` canonical source change from v2):

| Metric | Type | Default labels | Advanced | Source (v3) |
|---|---|---|---|---|
| `ao_llm_call_duration_seconds` | histogram | `provider` | `model` | **`llm_spend_recorded.duration_ms`** (v3: B2 event +1 field additive) |
| `ao_llm_tokens_used_total` | counter | `provider`, `direction` | `model` | `llm_spend_recorded.tokens_input/tokens_output` |
| `ao_llm_cost_usd_total` | counter | `provider` | `model` | `llm_spend_recorded.cost_usd` |
| `ao_llm_usage_missing_total` | counter | `provider` | `model` | **`llm_usage_missing` event** (v3: ayrı event, `llm_spend_recorded` değil) |
| `ao_policy_check_total` | counter | `outcome` | — | `policy_checked.violations_count` (==0/>0) |
| `ao_workflow_duration_seconds` | histogram | `final_state` | — | `workflow_started` + terminal **veya `state.v1.json.completed_at`** (v3: cancelled run_store read) |
| `ao_claim_active_total` | gauge | — | `agent_id` | `coordination.registry.live_claims_count()` (Q1 A) |
| `ao_claim_takeover_total` | counter | — | — | `claim_takeover` |

**v3 Cost-disjunction**: `metrics.enabled=true` + `cost.enabled=false` → ao_llm_* metric family **absent** (provider label yaratılmaz, sample emit edilmez). Metric family metadata dahi üretilmez (prometheus_client `Counter` registration lazy — hiç kaydedilmez). Docs §6 açık: "LLM observability requires cost tracking enabled".

**Histogram buckets (v3):**
- LLM: `(0.1, 0.5, 1, 2.5, 5, 10, 30, 60, 300, 600)` (v3: upper 300→600 GPT-4-turbo outlier)
- Workflow: `(1, 5, 15, 60, 300, 900, 3600, 7200)` (insan onay saatlik olabilir)

### 2.3 `derivation.py` — events.jsonl scan → metric population

`derive_metrics_from_evidence(workspace_root, registry, policy) -> DerivationStats`.

**Not (v3)**: `run_id_filter` ve `since_ts` parametreleri kaldırıldı (Prometheus textfile counter-reset semantik ihlali). Textfile export cumulative full scan. Debug/windowed sorgu için ayrı `debug-query` subcommand (§2.6b).

**Fail-closed on malformed JSONL**: `timeline.py` pattern mirror (`ao_kernel/_internal/evidence/timeline.py:69` — iter-1 doğrulandı internal path) → `EvidenceSourceCorruptedError`. Missing workspace → empty registry (dormant-mode parity, no raise).

**Event → metric mapping (v3 source-of-truth)**:
- `llm_spend_recorded.duration_ms` → `ao_llm_call_duration_seconds{provider[, model]}` histogram **(v3 canonical; adapter_invoked/returned DEĞİL)**
- `llm_spend_recorded.{tokens_input, tokens_output, cached_tokens}` → `ao_llm_tokens_used_total{provider, direction[, model]}` counter (direction ∈ {input, output, cached})
- `llm_spend_recorded.cost_usd` → `ao_llm_cost_usd_total{provider[, model]}` counter (Decimal→float cast; ≥0 assert)
- `llm_usage_missing` event count → `ao_llm_usage_missing_total{provider[, model]}` counter **(v3 fix: ayrı event, llm_spend_recorded değil)**
- `policy_checked.violations_count` → `ao_policy_check_total{outcome}` (outcome = `allow` if ==0, `deny` if >0)
- `workflow_started` + terminal event (`workflow_completed` / `workflow_failed`) → `ao_workflow_duration_seconds{final_state}` histogram
  - **Cancelled runs (Q3 A)**: `workflow_cancelled` event YOK (denial yalnız `approval_denied` emit eder, run state'i cancelled yapar). Cancelled duration için `state.v1.json.completed_at` okunur. Yeni internal helper: `list_terminal_runs(workspace_root)` → `[(run_id, final_state, started_at, completed_at)]` (`ao_kernel/workflow/run_store.py` internal scope).
- `claim_takeover` event → `ao_claim_takeover_total` counter (label-less)
- **`live_claims_count()` snapshot** → `ao_claim_active_total{agent_id?}` gauge (Q1 A)

**v3 invariant**: derivation yalnız evidence payload okur (raw response bytes YOK — `extract_usage_strict` çağrılmaz; Q4 cevabı). İki doğruluk kaynağı riski elimine edildi.

### 2.4 `export.py` — Prometheus textfile serializer

`generate_latest()` wrapper + metadata banner (dormant + extra-missing pre-prefix). Parser roundtrip test zorunlu.

### 2.5 `errors.py` — 5 types

`MetricsError` (base), `MetricsDisabledError`, `MetricsExtraNotInstalledError`, `EvidenceSourceMissingError`, `EvidenceSourceCorruptedError` (v2 yeni), `InvalidLabelAllowlistError`.

### 2.6 CLI — `ao-kernel metrics export` (v3 cumulative-only textfile)

argparse subparser; `--format prometheus` (default ve **tek** format textfile mode için), `--output` (path; default stdout). **`--since`/`--run` bayrakları kaldırıldı (v3)** — Prometheus textfile counter reset semantik ihlali.

Exit codes:
- 0 success (registry populate edilmiş veya dormant-graceful banner)
- 1 user error (ör. output path yazılamaz)
- 2 internal (corrupt JSONL, schema violation)
- 3 extra-missing informational (banner emitted; prometheus_client yok)

**Dormant UX** (Q2 karar): exit 0 + textfile banner comment (`# ao-kernel metrics: dormant (policy_metrics.enabled=false)`). Grafana "No data" görünür; hard fail değil.

**Cost-dormant UX**: exit 0 + banner comment (`# ao-kernel metrics: cost tracking dormant, LLM metrics absent`).

### 2.6b Debug-query subcommand (v3 NEW, v4 timezone-aware) — `ao-kernel metrics debug-query`

Windowed/run-scoped ad-hoc sorgu için ayrı subcommand. **NON-Prometheus format** (JSON only).

argparse:
- `--since ISO8601` (**v4: timezone zorunlu**; naive input → argparse error)
- `--run <run_id>` (optional filter)
- `--format json` (tek format; openmetrics reject)

**v4 `--since` timezone contract**:
- Kabul edilir: `2026-04-17T18:30:00Z`, `2026-04-17T18:30:00+00:00`, `2026-04-17T21:30:00+03:00`
- Reject edilir: `2026-04-17T18:30:00` (naive) → error: `--since: timezone required, use 'Z' or '+HH:MM' offset`
- Reject edilir: `1713376200` (epoch int) → error: `--since: ISO-8601 string required (epoch not accepted)`

Parse: `_internal/shared/utils.py:116` `parse_iso8601` helper wrap edilir; naive sonucu `raise ValueError("timezone required")` ile reject eden thin wrapper `parse_iso8601_strict(value)` eklenir.

Amaç: operator debug (ör. "son saatteki tüm LLM çağrıları" — scrape semantik kırmıyor çünkü Prometheus textfile değil). Grafana'ya bağlanmaz; human-readable snapshot.

~120 LOC + ~9 test (+1 timezone enforcement test).

### 2.7 `coordination/registry.py::live_claims_count()` helper (Q1 A)

```python
def live_claims_count(workspace_root: Path) -> dict[str, int]:
    """Return {agent_id: count} of currently-held claims (not expired).
    Read-only snapshot; scans .ao/claims/*.json respecting expires_at
    + takeover_grace_period_seconds invariants; reconciles with
    claim index + lease lock ordering."""
```

~20-30 LOC (v3: 15 LOC iyimser — lock/index reconcile dahil realistik). Alternatif B (evidence-derived net) reddedildi: expired/takeover race'de negatif count.

### 2.8 Grafana dashboard — panel→metric matrix (v3 genişletildi)

`docs/grafana/ao_kernel_default.v1.json` — **8 default panel** (advanced-label paneller commented-out + ~N advanced).

**Panel→metric/query matrix** (dashboard shape test bunu assert eder):

| Panel | Metric | Query (PromQL) | Visualization |
|---|---|---|---|
| LLM call duration p95 | `ao_llm_call_duration_seconds` | `histogram_quantile(0.95, sum(rate(ao_llm_call_duration_seconds_bucket[5m])) by (provider, le))` | Time series |
| LLM tokens/s | `ao_llm_tokens_used_total` | `sum(rate(ao_llm_tokens_used_total[5m])) by (provider, direction)` | Time series |
| LLM cost/h | `ao_llm_cost_usd_total` | `sum(rate(ao_llm_cost_usd_total[1h])) by (provider) * 3600` | Stat |
| LLM usage-miss rate | `ao_llm_usage_missing_total` | `sum(rate(ao_llm_usage_missing_total[5m])) by (provider)` | Time series |
| Policy deny rate | `ao_policy_check_total` | `sum(rate(ao_policy_check_total{outcome="deny"}[5m]))` | Time series |
| Workflow duration p95 | `ao_workflow_duration_seconds` | `histogram_quantile(0.95, sum(rate(ao_workflow_duration_seconds_bucket[5m])) by (final_state, le))` | Time series |
| Active claims | `ao_claim_active_total` | `ao_claim_active_total` | Stat |
| Claim takeover count | `ao_claim_takeover_total` | `increase(ao_claim_takeover_total[1h])` | Stat |

Shape test: dashboard JSON parse → her 8 panel için `panel.targets[0].expr` unique metric name içermeli. `docs/grafana/README.md` import recipe + 3 provisioning senaryosu (local file, K8s ConfigMap, Grafana API).

### 2.9 `pyproject.toml` delta

`[metrics] = ["prometheus-client>=0.20.0"]`; `enterprise` meta `+metrics`.

## 3. Write Order (v3 5+1-commit DAG)

1. **C1**: policy + errors + pyproject + 10 policy tests (~210 LOC)
2. **C2**: registry adapter + 8 registry tests (~230 LOC)
3. **C2b (v3 NEW)**: B2 `cost/middleware.py` `llm_spend_recorded.duration_ms` additive field + existing cost test update + 2 new tests (`duration_ms` present/≥0/float) (~40 LOC total)
4. **C3**: derivation + export + CLI export handler + coordination live-count + run_store terminal helper + 17 tests (~560 LOC)
5. **C3b (v3 NEW)**: debug-query subcommand + 8 tests (~160 LOC)
6. **C4**: Grafana dashboard + README + panel→metric matrix shape test (~260 LOC)
7. **C5**: docs METRICS.md §2/§6/§7 delta (+cost-disjunction, cardinality hard-warn) + CHANGELOG (~150 LOC)

## 4. Evidence-derived vs direct-hook trade-off (v3)

| Kriter | Evidence-derived (seçilen) | Direct-hook (reddedilen) |
|---|---|---|
| LLM/executor/cost delta | **~10 satır** (B2 event +1 field additive) | ~40+ satır B2 conflict |
| B2 merge bağımlılığı | B2 merged; v3 B5 tek-field additive patch | B2-sonrası zorunlu |
| CLI stateless | evet (cumulative textfile) | hayır |
| Evidence corrupt → metric | fail-closed | fail-open |
| LOC runtime | ~900 | ~1200 |

**v3 note**: "Evidence-derived" kapsamı yumuşatıldı — tek canonical delta `llm_spend_recorded.duration_ms`. Bu additive field B2 schema invariant'ı korur (optional, ≥0 float, missing backward-compatible).

## 5. Acceptance Checklist (v3)

### Dormant gate
- [ ] `load_metrics_policy()` dormant → no raise
- [ ] CLI dormant + extra installed → exit 0 + textfile dormant banner comment
- [ ] CLI dormant + extra missing → exit 3 informational banner
- [ ] Operator opt-in → full textfile

### Cost-disjunction (v3 NEW)
- [ ] `metrics=true + cost=false` → `ao_llm_*` metric family metadata DEĞİL (zero-synthetic yasak)
- [ ] Textfile output ao_llm_* prefix bulunmaz (metadata+sample yok)
- [ ] CLI cost-dormant banner comment emitted
- [ ] `metrics=true + cost=true` + no spend events → metric metadata present, sample yok (family registered)

### Policy (B0 regression + v3 runtime defence)
- [ ] Bundled loads + schema ok
- [ ] Override valid allowlist
- [ ] Override invalid enum → ValidationError
- [ ] Runtime bypass via override kwarg → InvalidLabelAllowlistError
- [ ] B0 test green

### Registry
- [ ] prometheus-client installed → 8 metric registry
- [ ] Not installed → None
- [ ] Baseline labels
- [ ] Advanced `model` expand
- [ ] Advanced `agent_id` expand
- [ ] Buckets LLM upper=600 verify; workflow vs LLM ayrı

### B2 event delta (v3 NEW)
- [ ] `llm_spend_recorded.duration_ms` field present in event payload
- [ ] `duration_ms ≥ 0.0` float assert
- [ ] `llm_usage_missing` event field set değişmez (no duration_ms)
- [ ] Backward compat: eski event'ler (duration_ms olmadan) okunduğunda derivation duration histogram skip eder (ValueError yerine log warn + counter increment)

### Derivation
- [ ] Empty evidence → empty registry (no raise)
- [ ] Corrupt JSONL → `EvidenceSourceCorruptedError` **fail-closed**
- [ ] Missing workspace → empty registry (dormant parity, no raise)
- [ ] `llm_spend_recorded.duration_ms` → duration histogram (v3 canonical; adapter_invoked/returned YOK)
- [ ] `llm_spend_recorded.{tokens_input, tokens_output, cached_tokens}` → tokens counter 3 direction
- [ ] `llm_spend_recorded.cost_usd` → cost counter
- [ ] `llm_usage_missing` count → usage_missing counter (v3 fix: ayrı event)
- [ ] `policy_checked.violations_count==0/>0` → outcome allow/deny
- [ ] `workflow_started + workflow_completed/failed` → duration histogram
- [ ] **`state.v1.json.completed_at` ile cancelled run duration** (Q3 A)
- [ ] `claim_takeover` → takeover counter
- [ ] `live_claims_count()` snapshot → active gauge (Q1 A)
- [ ] `extract_usage_strict` çağrısı YOK (Q4 pin)
- [ ] `run_id_filter`/`since_ts` parametresi derivation signature'da YOK (v3 API constraint)

### Export (cumulative-only textfile, v3)
- [ ] Valid Prometheus exposition (0.0.4 format)
- [ ] Parser roundtrip clean (prometheus_client parse)
- [ ] Dormant comment banner
- [ ] Cost-dormant comment banner
- [ ] Cumulative (same input → same output, no run_id/since filter)

### CLI `metrics export` (v3)
- [ ] exit 0 + stdout textfile
- [ ] --output atomic write (tmp+fsync+rename)
- [ ] --format openmetrics reject
- [ ] --since/--run flags reject with argparse error (v3 explicit block)
- [ ] No workspace → exit 1
- [ ] Corrupt JSONL → exit 2
- [ ] Extra missing → exit 3 banner

### CLI `metrics debug-query` (v3 NEW, v4 timezone-strict)
- [ ] --since ISO-8601 parse (valid `Z` or `+HH:MM`)
- [ ] --since epoch int → argparse error
- [ ] **--since naive ISO (no tzinfo) → argparse error `timezone required`** (v4)
- [ ] --run filter scopes events
- [ ] JSON output schema valid
- [ ] exit 0 success; exit 1 user error; exit 2 internal
- [ ] --format openmetrics reject (non-prometheus only)

### Grafana
- [ ] Valid JSON + shape
- [ ] 8 visible default panels + N commented-out advanced
- [ ] Panel→metric matrix: her 8 panel için `targets[0].expr` unique metric name içermeli (shape test)

### Regression (zero-delta guard, v3)
- [ ] B0 TestBundledCodexStubEndToEnd green
- [ ] test_telemetry green
- [ ] B1 coordination green (live_claims_count additive)
- [ ] **B2 cost test delta**: `llm_spend_recorded` payload assertion `duration_ms` field tolerate eder
- [ ] `_KINDS == 27` unchanged (B5 yeni event kind EKLEMEZ)

## 6. Risk Register (v4, 14 risk)

| Risk | L | I | Mitigation |
|---|---|---|---|
| R1 Corrupt JSONL → export abort | M | M | Fail-closed + evidence verify-manifest recovery; no --run fallback |
| R2 10k+ runs slow export | M | M | B5.1 streaming future (cumulative-only textfile acceptable perf for MVP) |
| R3 prometheus-client optional → CI | H | L | Matrix install + no-op fallback test |
| R4 Cardinality explosion (ephemeral agent_id/model) | M | **H** | **v3: Docs hard warn + METRICS.md §6 "asla ephemeral" uyarısı + B0 schema label-name closed enum (değer kapatılamaz)** |
| R5 Grafana import UX | M | L | `docs/grafana/README.md` step-by-step + panel→metric matrix |
| R6 B2 conflict | Resolved | — | B2 merged; v3 tek-field additive delta |
| R7 Concurrent cron race | M | L | Read-only; atomic output write |
| R8 Textfile non-compliance | L | H | Parser roundtrip test + cumulative-only semantic |
| R9 workflow_cancelled gap | Resolved | — | Q3 A: state.v1.json.completed_at read helper |
| R10 Claim gauge inconsistency | Resolved | — | Q1 A: live-count helper |
| R11 B1/B2 dormant → empty metrics | L | L | Docs §6 operator verification |
| **R12 (v3 NEW) Cost dormant + LLM metrics expectation mismatch** | M | M | Docs §6 explicit: "LLM observability requires cost tracking"; cost-dormant banner + zero-synthetic yasak |
| **R13 (v3 NEW) `duration_ms` backward-compat** | L | M | Eski `llm_spend_recorded` events (no duration_ms) → derivation log warn + counter increment, histogram skip; test kapsar |
| **R14 (v4 NEW) `usage_missing` duration exclusion** | L | L | Usage_missing path `llm_spend_recorded` emit etmez; duration histogram usage-miss çağrılarını hariç tutar (doğru davranış). Docs §6 + test.|

## 7. Scope Dışı (post-B5)

- OTEL bridge → FAZ-C+
- OpenMetrics → FAZ-D+
- Push gateway → NEVER
- Advanced labels `run_id/workflow_id/step_id` → FAZ-E+ (cardinality bomb)
- `ao_evidence_emit_failure_total` counter → B8+
- Real-time HTTP endpoint → FAZ-E+
- Bucket knob → FAZ-D+ (Codex Q5)
- Streaming cost → FAZ-C (B2 deferred)

## 8. PR-B2 Conflict Resolution (v3)

**B2 MERGED (#99 + #100 e2e)** → B5 = read-only consumer **+ tek-field additive event extension**.

**v4 B5-touches-B2 delta** (small, additive, backward-compat):
- **`execute_request()` return passthrough**: llm.py `governed_call` path `execute_request()` return dict'teki `elapsed_ms` field'ını capture eder.
- `post_response_reconcile(...)` yeni kwarg: `elapsed_ms: float | None` (None → backward-compat, duration_ms emit edilmez).
- `ao_kernel/cost/middleware.py:425-443` `llm_spend_recorded` emit block: `elapsed_ms is not None` ise `"duration_ms": round(elapsed_ms, 3)` field eklenir. Pre-computed; re-capture gerek yok.
- Backward compat: eski event'ler (`duration_ms` yok) derivation'da histogram skip; log warn + counter increment (R13).
- Test: yeni `llm_spend_recorded` event `duration_ms` present, ≥0, float assert (2 new tests in existing cost test file + 1 new `governed_call` → middleware propagation test).
- Schema invariant: `llm_spend_recorded` şeması opaque payload (schema file yok); JSON schema validation yok; runtime type check sufficient.
- **Not (v4)**: `usage_missing` path (`cost/middleware.py:261-290`) `llm_spend_recorded` emit etmez → duration_ms de taşımaz. Duration histogram usage-miss çağrılarını hariç tutar (doğru davranış; R14 docs note).

**Paylaşılan dosya (v4)**:
- `ao_kernel/llm.py` — `governed_call` 1 line delta: `execute_request()` return'den `elapsed_ms` capture (~3 LOC)
- `ao_kernel/cost/middleware.py` — `post_response_reconcile` kwarg + emit block (~10 LOC)
- `docs/METRICS.md` §2 tablosu 6→8 additive + §6 cost-disjunction + cardinality warn
- `docs/COST-MODEL.md` §N event schema — `duration_ms` field dokümante edilir (1 satır additive) + usage_missing duration absence note

## 9. Codex iter-1 5 Q → v3 Kararlar

| Q | Soru | v3 Karar (Codex AGREE) | Gerekçe |
|---|---|---|---|
| Q1 | Claim active gauge source | **A** (live-count helper) | Evidence-net race-prone; registry single source; ~20-30 LOC realistic |
| Q2 | Dormant CLI UX | **exit 0 + textfile banner comment** | B1 parity yanlış analogi; observability surface; Grafana "No data" acceptable |
| Q3 | workflow_cancelled derivation | **A** (state.v1.json.completed_at read) | Yeni event gereksiz; run_store zaten terminal_state tutuyor |
| Q4 | extract_usage_strict call | **SKIP** | Canonical source = B2 evidence; raw parse duplicate SOT riski |
| Q5 | Histogram bucket knob | **Yok v1'de; LLM upper 300→600** | Knob deferred; default expand yeterli; policy_metrics.buckets_seconds_* FAZ-D |

## 10. Audit Trail

| Iter | Date | Verdict |
|---|---|---|
| v1 (subagent draft) | 2026-04-17 | N/A |
| v2 (code-verification) | 2026-04-17 | Pre-Codex iter-1 submit |
| **iter-1** (CNS-20260417-035, thread `019d9cec`) | 2026-04-17 | **REVISE** — LLM duration source + textfile semantics + cost disjunction + Grafana matrix + 5 Q cevaplandı |
| v3 (iter-1 absorb) | 2026-04-17 | Pre-iter-2 submit |
| **iter-2** (thread `019d9cec`) | 2026-04-17 | **PARTIAL** — `duration_ms` source `transport_result.elapsed_ms`; `--since` timezone-aware; usage_missing duration-exclusion docs |
| **v4 (iter-2 absorb)** | 2026-04-17 | Pre-iter-3 submit |
| iter-3 | TBD | AGREE bekleniyor |

### Plan revision history

| Ver | Change |
|---|---|
| v1 | Subagent draft; 6 metrik; 7 code-level hata |
| v2 | 7 hata düzeltildi; 3 scope genişletme; 8 metrik; fail-closed corrupt; 5 açık soru keskinleştirildi |
| v3 | iter-1 REVISE absorb: LLM duration `llm_spend_recorded.duration_ms` (B2 additive patch); `--since/--run` textfile'dan kaldırıldı → `debug-query` subcommand; cost-disjunction docs + zero-synthetic yasak; usage_missing source fix; Grafana panel→metric matrix; LLM bucket upper 300→600; `live_claims_count()` LOC 15→25; 5 Q kararlı |
| **v4** | iter-2 PARTIAL absorb: duration_ms source = `transport_result.elapsed_ms` (execute_request pre-computed); `--since` timezone-aware contract (naive reject); usage_missing duration-exclusion docs (R14) |

**Status**: Plan v4 hazır. Codex CNS-20260417-035 thread `019d9cec` iter-3 submit için hazır.
