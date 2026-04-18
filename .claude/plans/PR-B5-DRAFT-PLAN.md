# PR-B5 Draft Plan v1 — Metrics Export (Prometheus Textfile + `[metrics]` Extra)

**Tranche B PR 5/9 — draft** — post CNS-20260417-030 iter-1 Codex advisory: B5 "bounded, tek paralel lane" verdict. Prometheus textfile export primary surface; OTEL bridge NOT in scope (`[metrics]` ve `[otel]` extras independent kalır, `docs/METRICS.md` §5 pin). PR-B0 şeması + dormant policy zaten shipped (commit `fbf7229`); docfix PR #98 B5 scope'u netleştirdi (head `5779609`).

**v1 key absorb (Codex iter-1 advisory — pre-plan):**

- **B5-bounded scope**: tek paralel lane, Prometheus textfile export, `[metrics]` extra. OTEL bridge bu PR'da YOK. `docs/METRICS.md` §5 "does not read OTEL spans or attempt bridge translation" binding — `[metrics]` ve `[otel]` extras **bağımsız installable** (`pip install ao-kernel[metrics]` veya `pip install ao-kernel[otel,metrics]` her ikisi de çalışır; iki yüzey birbirine dokunmaz).
- **Advanced labels schema-gated**: `policy_metrics.v1.json::labels_advanced.allowlist` closed enum (`model | agent_id`) B0'da pinlendi; B5 runtime bunu **enforce** eder (allowlist dışı label schema validation sırasında reject olur, runtime'da şüpheli label emit olmaz — defence in depth).
- **Dormant default + policy-gated emission (B1 pattern)**: bundled `policy_metrics.v1.json` `enabled: false`. `ao-kernel metrics export` CLI dormant policy ile **empty textfile** (sadece `# HELP` / `# TYPE` header'ları + 0-sample comment) üretir. Operatör `.ao/policies/policy_metrics.v1.json` ile opt-in eder.
- **Emit strategy — evidence-derived, NOT direct hook**: `prometheus_client` in-memory registry LLM pipeline hook'ları yerine **evidence timeline tabanlı derivation** ile doldurulur. `ao-kernel metrics export` işlemi tek bir snapshot emit eder: evidence JSONL scan → counter/histogram'a translate → textfile output. Avantajı: (a) `llm.py` ve `executor.py` dokunmuyor (B2 ile conflict yok), (b) evidence taxonomy değişmiyor (24-kind stable), (c) CLI idempotent + stateless (cron-friendly). Trade-off §4'te.
- **PR-B2 conflict resolution**: B5 emit hook'ları eklemediği için B2 commit 4'teki `llm.py` delta ile sıfır satır örtüşüyor. Tek paylaşılan dosya: `docs/METRICS.md` (B5 runtime notes) ve `CHANGELOG.md` `[Unreleased]` — her ikisi de ayrı bölümler. Merge order: B5 B2'den bağımsız; hangisi önce merge olursa, diğeri `[Unreleased]` çakışmasını trivial rebase ile çözer.
- **Grafana scope-in**: dashboard JSON (tek dosya) `docs/grafana/ao_kernel_default.v1.json`. Panel-by-panel advanced-label panelleri commented-out ship (METRICS.md §4 promise). Operator `grafana import` ile kullanır.

## 1. Amaç

PR-B0 foundation kontratını runtime'a bağla: `ao_kernel/metrics/` yeni public package + `[metrics]` optional extra (`prometheus-client` lazy import, no-op fallback — `telemetry.py` OTEL paterninden öğrenilmiş). Prometheus textfile export CLI `ao-kernel metrics export --format prometheus`. Evidence timeline'ı deriving source olarak kullanan stateless snapshot emitter. Dormant default; advanced labels `policy_metrics.v1.json::labels_advanced` opt-in schema-closed enum.

### Kapsam özeti

| Katman | Modül | Satır (est.) |
|---|---|---|
| Public package | `ao_kernel/metrics/__init__.py` | ~40 |
| Policy | `ao_kernel/metrics/policy.py` (typed loader; mirror PR-B1 policy.py) | ~110 |
| Registry adapter | `ao_kernel/metrics/registry.py` (prometheus_client wrappers + lazy import + no-op fallback) | ~180 |
| Evidence → metric | `ao_kernel/metrics/derivation.py` (evidence JSONL scan → counter/histogram populate) | ~260 |
| Textfile emitter | `ao_kernel/metrics/export.py` (Prometheus textfile format serializer) | ~130 |
| Typed errors | `ao_kernel/metrics/errors.py` (4 types) | ~60 |
| CLI handler | `ao_kernel/_internal/metrics/cli_handlers.py` + `ao_kernel/cli.py` delta | ~80 + ~25 delta |
| `pyproject.toml` delta | `[project.optional-dependencies] metrics = ["prometheus-client>=0.20.0"]` | ~5 delta |
| Grafana dashboard | `docs/grafana/ao_kernel_default.v1.json` (default panels + commented advanced) | ~200 |
| Tests | 3 test files (~35 test) — contract + dormant + derivation + empty-textfile + CLI smoke | ~440 |
| Docs | `docs/METRICS.md` runtime notes (§2.5 empty-textfile, §6 CLI exit codes) | ~50 delta |
| CHANGELOG | `[Unreleased]` PR-B5 | ~55 |
| **Toplam** | 1 yeni package + 1 internal helper + 1 code delta + 1 pyproject delta + 1 Grafana + ~35 test + docs | **~1630 satır** |

- Yeni evidence kind: **0** (metrics surface is derived, not emitted)
- Yeni adapter capability: 0
- Yeni core dep: **0** (`prometheus-client` opsiyonel `[metrics]` extra içinde; zorunlu değil)
- Yeni schema: 0 (B0'da shipped)
- Yeni error type: **4** — `MetricsDisabledError`, `MetricsExtraNotInstalledError`, `EvidenceSourceMissingError`, `InvalidLabelAllowlistError`

**LOC hedefi Codex "bounded" ≈ 1000 LOC önerisi altında kalmalı**: asıl runtime kod (~820 LOC) + Grafana JSON (~200) + tests (~440) = toplam ~1630. Codex önerisi "runtime kod" bounded anlamında — test + docs + dashboard scope iç değil. Runtime ≈ 1000 LOC hedefine yakın (800-900 bandında).

## 2. Scope İçi

### 2.1 `ao_kernel/metrics/policy.py`

Mirror of PR-B1 `coordination/policy.py` pattern. `MetricsPolicy` frozen dataclass + `LabelsAdvanced` nested + `load_metrics_policy(workspace_root, *, override=None)`. Schema validate against B0-shipped `policy-metrics.schema.v1.json`. Runtime defence-in-depth guard: `labels_advanced.allowlist` subset of `{"model", "agent_id"}`; override kwarg bypass → `InvalidLabelAllowlistError`.

### 2.2 `ao_kernel/metrics/registry.py` (prometheus_client lazy wrappers)

Lazy import pattern (telemetry.py mirror): `_check_prometheus()` bool cache. `build_registry(policy)` returns `CollectorRegistry` with 6 metrics pre-registered (METRICS.md §2 table). Advanced label expansion: policy `labels_advanced.enabled=true` + `allowlist` contains `"model"` → `ao_llm_*` metrics gain `model` label; `"agent_id"` → `ao_claim_*` gain `agent_id`.

Histogram buckets (default, non-configurable v1): `(0.1, 0.5, 1, 2.5, 5, 10, 30, 60, 300)`.

### 2.3 `ao_kernel/metrics/derivation.py` (evidence → metric)

`derive_metrics_from_evidence(workspace_root, registry, policy, *, run_id_filter=None, since_ts=None)` — scan `.ao/evidence/workflows/**/events.jsonl`, map events to metrics.

**Event → metric mapping:**

| Evidence kind | Metric(s) | Payload |
|---|---|---|
| `adapter_invoked` + `adapter_returned` | `ao_llm_call_duration_seconds` (ts delta) + `ao_llm_tokens_used_total` | provider, tokens |
| `policy_checked` / `policy_denied` | `ao_policy_check_total{outcome}` | kind → outcome |
| `workflow_started` + terminal kind | `ao_workflow_duration_seconds{final_state}` | final_state |
| `claim_acquired` / `claim_released` / `claim_expired` / `claim_takeover` | `ao_claim_active_total` net | — |
| `claim_takeover` | `ao_claim_takeover_total` | (scalar) |

**Invariants:** evidence read fail-open (corrupt JSONL line → skip + warn); missing events dir (`run_id_filter` set ama yok) → `EvidenceSourceMissingError`; empty dir → empty registry. Stateless: fresh scan her CLI çağrısında.

**Cardinality baseline:** 6 provider × 3 direction = 18 LLM token series + 2 policy + 3 workflow + 1 claim ≈ 24 time series.

### 2.4 `ao_kernel/metrics/export.py`

`export_prometheus_textfile(registry, *, include_help=True, include_type=True)` → string. Dormant → metadata-only banner. `registry=None` → `# INACTIVE` banner.

### 2.5 `ao_kernel/metrics/errors.py`

4 type: `MetricsError` (base), `MetricsDisabledError`, `MetricsExtraNotInstalledError`, `EvidenceSourceMissingError`, `InvalidLabelAllowlistError`.

### 2.6 CLI — `ao-kernel metrics export`

argparse subparser: `--format prometheus` (v1 only), `--since ISO-8601`, `--run uuid`, `--output path-or-stdash`.

**Exit codes:** 0 success (incl. dormant empty), 1 user error, 2 internal error, 3 `[metrics]` extra not installed (informational).

**Flow:** `_resolve_workspace` → `load_metrics_policy` → dormant gate (empty textfile + banner) → `is_metrics_available()` → `build_registry` → `derive_metrics_from_evidence` → `export_prometheus_textfile` → stdout or atomic file write.

Cron recipe (docs §6): `*/5 * * * * ao-kernel metrics export --output /var/lib/node_exporter/ao-kernel.prom`.

### 2.7 Grafana dashboard

`docs/grafana/ao_kernel_default.v1.json` — 5 panels (LLM duration p95, token rate stacked, policy allow/deny, workflow duration p95, claim active gauge). Advanced-label panels commented-out (`hide: true`). Test validates minimal Grafana dashboard shape.

### 2.8 `pyproject.toml` delta

```toml
[project.optional-dependencies]
metrics = ["prometheus-client>=0.20.0"]
# enterprise meta genişletir:
enterprise = ["ao-kernel[otel,mcp,pgvector,metrics]"]
```

## 3. DAG — 5-commit structure

1. **Commit 1** (~200 LOC): errors + policy + pyproject + 10 policy tests
2. **Commit 2** (~200 LOC): registry adapter + 8 registry tests
3. **Commit 3** (~450 LOC): derivation + export + CLI handler + 15 tests
4. **Commit 4** (~250 LOC): Grafana dashboard + `__init__.py` public surface + dashboard shape test
5. **Commit 5** (~100 LOC): docs §6/§7 + CHANGELOG

## 4. Evidence-derived vs direct-hook trade-off

| Kriter | Evidence-derived (seçilen) | Direct-hook (reddedilen) |
|---|---|---|
| LLM/executor delta | **0 satır** | ~30 satır (B2 conflict) |
| B2 merge bağımlılığı | **yok** | B5 B2-sonrası |
| Sample recency | bounded `--since` | real-time |
| CLI stateless | **evet** | hayır |
| Evidence fail → metric loss | evet | hayır |
| Cardinality guard | schema + runtime | runtime-only |
| LOC runtime | ~820 | ~1200 (B2 delta dahil) |

**Seçim gerekçesi**: Codex "bounded" + PR-B2 conflict avoidance. Evidence authoritative single-source (CLAUDE.md §2). Dual-source riski yok. Trade-off: scrape latency ~30s; operator real-time isterse OTEL bağımsız surface.

## 5. Acceptance Checklist

### Dormant gate
- [ ] `load_metrics_policy()` dormant → `MetricsPolicy(enabled=False)` (raise YOK)
- [ ] `ao-kernel metrics export` dormant + extra → exit 0, dormant banner
- [ ] dormant + no extra → exit 0, no-extra banner
- [ ] `.ao/policies/policy_metrics.v1.json enabled: true` → full textfile

### Policy (B0 regression)
- [ ] Bundled loads + schema ok
- [ ] Override `allowlist: ["model"]` valid
- [ ] Override `allowlist: ["xyz"]` → ValidationError
- [ ] Override via `override=` dict bypass → `InvalidLabelAllowlistError`
- [ ] `additionalProperties: foo` → ValidationError (closed schema)

### Registry
- [ ] `prometheus-client` installed → valid `CollectorRegistry` + 6 metrics
- [ ] Not installed → None
- [ ] Baseline labels only when `labels_advanced.enabled=false`
- [ ] `enabled=true` + `["model"]` → `ao_llm_*` gains `model`
- [ ] `enabled=true` + `["agent_id"]` → `ao_claim_*` gains `agent_id`

### Derivation
- [ ] Empty evidence → empty registry
- [ ] Single run fixture → expected samples
- [ ] Corrupt JSONL → warn + continue
- [ ] `run_id_filter` → single run scope
- [ ] `since_ts` → time-filtered
- [ ] `claim_takeover` → takeover counter +1, active net 0

### Export
- [ ] Registry + samples → valid Prometheus exposition
- [ ] Dormant → metadata-only / banner
- [ ] `registry=None` → `# INACTIVE` 3-line banner
- [ ] `prometheus_client.parser.text_string_to_metric_families` roundtrip

### CLI
- [ ] `metrics export` → exit 0 + stdout
- [ ] `--output /tmp/x.prom` → atomic write
- [ ] `--run <uuid>` → scoped
- [ ] `--since ISO` → time-filtered
- [ ] `--format openmetrics` → argparse reject
- [ ] No workspace → exit 1

### Grafana
- [ ] Valid JSON
- [ ] 5 panels baseline
- [ ] Advanced panels hidden
- [ ] Dashboard shape test passes

### `[metrics]` extra
- [ ] `pip install ao-kernel[metrics]` → prometheus-client installs
- [ ] `[metrics,otel]` → both independent
- [ ] `[enterprise]` includes metrics

### Regression
- [ ] `TestBundledCodexStubEndToEnd` green (B0)
- [ ] `test_telemetry.py` green (OTEL untouched)
- [ ] B1 coordination tests green
- [ ] `_KINDS` 24 unchanged (B5 emits no new kind)
- [ ] pytest baseline + ~35 new; ruff + mypy strict clean

## 6. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **R1**: Evidence JSONL corrupt → sample loss | Medium | Low-Med | Warn + continue; operator uses `ao-kernel evidence verify-manifest` (PR-A5) |
| **R2**: Large evidence dir → slow export | Medium | Medium | `--since` + `--run` bounded windows; docs §6 recipe |
| **R3**: `prometheus-client` optional → CI fails without | High | Low | CI `pip install ao-kernel[metrics]`; no-op fallback unit test |
| **R4**: Cardinality explosion (`agent_id` → 10k series) | Low | High | Schema closed enum + runtime guard; docs §3 cardinality warning |
| **R5**: Advanced panel Grafana import confusion | Medium | Low | Commented-out panels with inline instructions |
| **R6**: B2 merge-before-B5 conflict | Low | Low | Evidence-derived = zero `llm.py` delta |
| **R7**: Concurrent cron export race | Medium | Low | Read-only evidence; idempotent |
| **R8**: Textfile format non-compliance | Low | High | parser roundtrip test |

## 7. Scope Dışı (post-B5 / FAZ-C+)

- OTEL bridge translation → FAZ-C+
- OpenMetrics format → FAZ-D+
- StatsD/InfluxDB → FAZ-E+
- Histogram bucket policy knob → FAZ-D+
- Push gateway (library HTTP) → NEVER (METRICS.md §1 pin)
- Advanced labels `run_id`/`workflow_id`/`step_id` → FAZ-E+ (cardinality bomb)
- `ao_evidence_emit_failure_total` counter → B8 / FAZ-C+ (Q11 deferred)
- Real-time streaming → FAZ-E+
- Pull-model custom collectors → FAZ-D+

## 8. PR-B2 Conflict Resolution

B2 commit 4 dokunur: `ao_kernel/llm.py` ~120 delta + `executor.py` hook'ları.
B5 commit 3 dokunur: `ao_kernel/metrics/derivation.py` (yeni) + evidence JSONL scan (read-only).

**Sıfır örtüşme**: B5 hiçbir PR-A/B1 dosyasına emit hook eklemiyor. B5 derivation `adapter_invoked`/`adapter_returned` kind'larını okuyor (PR-A3'ten beri var). B2'nin yeni eklediği `llm_cost_estimated` / `llm_spend_recorded` / `llm_usage_missing` kindları **v1 B5'de okunmuyor** (v1.x ileri scope `ao_llm_cost_total` counter'ı).

**CHANGELOG**: `[Unreleased]` altına ayrı başlık; ikinci merge trivial rebase.

**Merge order serbest**: B5 B2-öncesi veya sonrası ok.

## 9. Codex iter-1 için 5 Açık Soru

1. **Evidence-derived strateji onayı**: §4 trade-off tablosunda evidence-derived seçimi onay görür mü (B2 conflict avoidance + stateless CLI + sıfır `llm.py` delta)? Real-time direct-hook'un operational value'su cron 5dk interval yeterli mi?

2. **Dormant CLI UX — graceful vs strict**: PR-B1 dormant API **raise** ederken B5 CLI dormant'ta **graceful empty textfile + exit 0** önerdim (cron-friendly). Tutarlılık için B5 de raise (exit 2) mi olsun?

3. **Histogram bucket policy knob v1**: Default `(0.1, 0.5, 1, 2.5, 5, 10, 30, 60, 300)` yeterli mi, yoksa `policy_metrics.v1.json::buckets_seconds` override knob v1'de eklenmeli mi (LLM p95 8B vs GPT-4 çok farklı)?

4. **`ao_evidence_emit_failure_total`**: Master plan Q11 deferred. B5 v1'de `_safe_emit_coordination_event` warning'lerini metric'leyerek ekleyelim mi, yoksa post-B5 kalsın mı?

5. **Grafana dashboard install CLI**: `ao-kernel metrics dashboard install` recipe'i B5 scope-in mi? Runtime ~1000 LOC hedefini operator UX'ine değiştirmeli mi?

## 10. Audit Trail

| Field | Value |
|---|---|
| Plan version | **v1 (draft)** |
| Head SHA | `5779609` (docfix PR #98 merged) |
| Target branch | `claude/tranche-b-pr-b5` (henüz oluşturulmadı) |
| FAZ-B master ref | `.claude/plans/FAZ-B-MASTER-PLAN.md` §3 B5 (docfix revised) |
| METRICS.md ref | `docs/METRICS.md` (B0 skeleton + docfix §5 OTEL out) |
| Prior art | PR-B1 coordination (dormant-gate, typed policy, fail-closed SSOT / fail-open derived) |
| CNS-030 verdict | iter-1 advisory: "bounded, tek paralel lane, prometheus textfile + [metrics] extra + low-cardinality labels" |
| Infra reuse | `config.load_default`, `file_lock`, PR-A5 evidence timeline JSONL read, `telemetry.py` lazy-import pattern |
| B0 regression guards | schema + policy + METRICS.md §1-§5 unchanged; `_KINDS` 24 unchanged |
| Expected iter-1 verdict | AGREE (bounded + conflict-free + B0 respect) veya PARTIAL (Q1-Q5 clarification) |

**Status:** Plan v1 draft. Kullanıcı onayı sonrası Codex MCP yeni thread ile iter-1 submit.
