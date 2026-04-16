# PR-B0 Implementation Plan v7 — FAZ-B Docs + Schemas (Docs-First Foundation)

**Tranche B PR 1/9** — post CNS-028v2 iter-5 AGREE + Codex write-order advisory absorbed. Docs + spec foundation, **2 minor code delta** (config.py loader + adapter_invoker.py extraction).

**v7 key absorb (Codex iter-5 advisory + Q1-Q6 yanıtları):**
- **§3 Write Order eklendi (Codex önerisi):** 7-step contract-first risk-first DAG; her commit yeşil + her commit kendi dependency zincirini kapatır. Plan §3'te detaylı.
- **§2.4 Edge Case Contracts subsection (Q6 absorb — kontrat-level pin, B6 yeniden tasarım önlenir):** 4 edge case (multi-rule same capability → invalid manifest fail-closed; unresolvable schema_ref → fail-closed; null payload → schema-driven; envelope field but no rule → silent ignore).
- **§5 Acceptance test stratejisi (Q4 absorb):** PR-A6 "tek konsolide dosya" pattern'ı yerine **sahiplik-bazlı** dağıtım: mevcut suite'lere ekle (`test_executor_adapter_invoker.py`, `test_config.py`, `test_workflow_registry.py`) + **1 yeni** `tests/test_pr_b0_contracts.py` (yeni schemas/policies/catalog fixture validation). PR-A6 drift tekrarlanmaz.
- **§7 Audit CHANGELOG strategy (Q5 absorb):** `InvocationResult.extracted_outputs` opsiyonel field public surface ([`ao_kernel/executor/__init__.py:59`](ao_kernel/executor/__init__.py:59) re-export); CHANGELOG ana sınıflandırma `Added`, opsiyonel ince `Changed` notu ("invoker now supports typed extracted outputs when declared by manifest"); semver minor uygun (v3.2.0).
- **§3 Commit DAG (Q2 absorb):** Tek PR, 5 DAG-closed commit (squash on merge); review/bisect granularity korunur.

**v6 key absorb (devralındı, CNS-028v2 iter-4):**
- **B4'''' extraction layer pin (adapter_invoker layer):** v5'te `output_parse` walking'i `Executor.run_step` katmanında yapacağız demiştik — ama [`adapter_invoker.py::InvocationResult:55`](ao_kernel/executor/adapter_invoker.py:55) ham envelope ya da extracted payload taşımıyor; [`adapter_invoker.py::_invocation_from_envelope:491`](ao_kernel/executor/adapter_invoker.py:491) bilinmeyen alanları **atıyor** (sabit alanları map ediyor). Çözüm: extraction `adapter_invoker._invocation_from_envelope` içine taşınır (transport-layer parse zaten orada — capability-aware extraction doğal yer). `InvocationResult.extracted_outputs: dict[str, dict]` opsiyonel field eklenir (default empty, backwards compat). `Executor.run_step(driver_managed=True)` `result.extracted_outputs[capability]` doğrudan alıp artifact yazar (schema-agnostic kalır, mevcut PR-A4b pattern korunur).
- **W1''' response_parse vs output_parse ayrımı:** Repo bugün HTTP transport'ta [`response_parse`](ao_kernel/defaults/schemas/agent-adapter-contract.schema.v1.json:180) kullanıyor ([`docs/ADAPTERS.md:141`](docs/ADAPTERS.md:141)). Yeni `output_parse` ile çakışma riski var. Plan §2.4'e bir cümle ile netleştirildi: "**`response_parse` = transport-level canonical envelope extraction (HTTP body → envelope shape); `output_parse` = capability-specific typed artifact extraction (envelope → schema-validated payload).**"
- **W2''' error category map fix:** v5'te "AdapterOutputParseError(category=output_parse_failed)" denilmişti — ama [`executor/errors.py:106`](ao_kernel/executor/errors.py:106) exception'ın `category` field'ı yok. Doğru ifade: "**workflow/run `error.category` `output_parse_failed` olarak map edilir**" (workflow-run schema'daki error.category enum'a referans, exception field'ı değil).
- **W3''' header schema delta sayısı drift:** §1 amaç satırı "2 enum delta" diyordu — scope tablosu doğru olarak 3 schema delta (2 enum + 1 output_parse extension) sayıyor. Header'a sync.
- **W4''' envelope vs payload schema-validation wording:** v5'te "Adapter envelope JSON'unda review_findings field schema-validated" denilmişti — fazla güçlü. `output_envelope` kapalı şekil olarak bırakıldığı için **envelope kendisi** schema-validated değil; schema-valid olan **extract edilen payload** (`schema_ref` ile doğrulanmış). Wording daraltıldı.

**v5 key absorb (devralındı, CNS-028v2 iter-3):**
- **B3''' adapter→orchestrator typed payload kontratı:** v4'te "adapter envelope'da `review_findings` payload field döner" denilmişti — ama mevcut adapter contract'ta `output_envelope.output` veya `review_findings` field'ı **YOK**, [`adapter_invoker.py::InvocationResult:55`](ao_kernel/executor/adapter_invoker.py:55) böyle bir payload taşımıyor, parser sabit alanları map ediyor. Çözüm: **`output_parse` rule extension** (mevcut PR-A3 JSONPath subset'inin capability-aware genişlemesi). `agent-adapter-contract.schema::output_parse[]` rule'una `capability` + `schema_ref` field'ları eklenir; orchestrator JSONPath ile extract eder, capability-specific schema'ya validate eder, `artifacts.write_artifact()` çağırır, `step_record.output_ref` doldurur. Adapter envelope JSON'unda `review_findings: { ... }` field'ı **olur**, schema-validated.
- **W2'' price-catalog conditional semantik fix:** v4'te "if `entries[*].source == vendor_api`" denilmişti — ama `source` catalog-level metadata field, `entries[*]`'de yok. Doğru semantik: "**top-level `source == "vendor_api"` ise her `entries[*].vendor_model_id` zorunlu**".
- **W3'' load_default full filename:** v4'te `load_default("catalogs", "price-catalog")` stem-based çağrı önerilmişti — ama mevcut [`config.py:77`](ao_kernel/config.py:77) full filename bekliyor ([`test_config.py:70`](tests/test_config.py:70) bu pattern'i kullanıyor). Tutarlılık için: `load_default("catalogs", "price-catalog.v1.json")` (full filename, mevcut API uyumlu).
- **W4'' scope table singular drift:** Scope tablosunda kalan `kind="catalog"` singular metni temizlendi (Edit'te bir yerde atlanmıştı; her yerde `catalogs` plural).
- **W5'' v2 absorb duplicate:** v2 absorb bloğu yanlışlıkla 2 kez tekrar ediyordu — ikinci tekrar silindi.

**v4 key absorb (devralındı, CNS-028v2 iter-2):**
- **B1' workflow-definition capability_enum drift:** `agent-adapter-contract.schema::capabilities[]` enum'a `review_findings` eklendi ama `workflow-definition.schema::capability_enum` aynı kapalı kümeyi taşıyor ve repo'da [`test_workflow_registry.py:407`](tests/test_workflow_registry.py:407) bu iki enum'un eşitliğini drift testiyle zorluyor. Aynı satır delta hem schema'ya da işlendi (~3 satır). `review_ai_flow.v1.json` artık schema-valid olur.
- **B2' typed artifact transport via step_record.output_ref:** v3 plan'da hatalı şekilde "adapter `output_envelope.output_ref`" denilmişti — ama `agent-adapter-contract.output_envelope` kapalı şekil ve böyle alan yok. Doğru transport: PR-A4b'de yerleşik **driver-managed mode** pattern'i — adapter envelope'da `review_findings` payload döner, orchestrator `artifacts.write_artifact()` ile yazar + `workflow-run::step_record.output_ref` doldurur. Adapter contract dokunulmuyor (breaking yok).
- **W4 catalog loader plural:** `kind="catalog"` → `kind="catalogs"` (mevcut 5 plural kind'la uyumlu: policies/schemas/registry/extensions/operations).
- **W5 acceptance deterministic equality:** "Aynı object döner" identity hedefi yanlıştı — `load_default` her çağrıda yeni dict üretir (parse). Hedef: deterministic equality on bundled load (sıralı keys, aynı içerik), shared-mutable cache değil.
- **W6 header schema sayısı drift:** "4 docs + 6 schemas" → "4 docs + 8 schemas" (5 data + 3 policy + 2 enum delta).
- **W8 vendor_model_id conditional:** v1'de zorunlu/opsiyonel düalitesi yerine schema-level conditional: `if source=vendor_api then required vendor_model_id` (manual + bundled için optional). Manuel katalog bakımı kırılganlaşmaz.

**v3 key absorb (devralındı, CNS-028v2 iter-1):**
- B1 plan-içi drift (price-catalog array→object, strict_freshness schema, fencing-state inventory) — hepsi senkronize.
- B2 lease/fencing expiry semantics: Otoriter expiry, grace, revival, stale fencing, quota, multi-resource scope — COORDINATION.md "Expiry Authority" bölümünde kilitli. **Bu bölüm CNS-028v2 iter-2'de blocker olmaktan çıktı — AGREE.**
- B3 benchmark typed artifact: `review_ai_flow.v1.json` contract pin (B0), `review-findings.schema.v1.json` typed artifact, `review_findings` capability adapter contract'a eklendi (v4'te workflow-definition'a da eklendi).
- W1 metrics control plane: `policy_metrics.v1.json` 3. policy (dormant); `labels_advanced.enabled` opt-in.
- W2 catalog loader path: `config.py::load_default("catalogs", ...)` extension (W4 ile plural'a çevrildi).

**v2 key absorb (devralındı, CNS-028 iter-1):**
- B1 claim atomicity: workspace-level `claims.lock`; claim `.v1.json` SSOT, `_index.v1.json` derived/rebuildable cache.
- B2 fencing token persistence: `_fencing.v1.json` per-resource state; release claim dosyasını siler ama token state korunur; strictly monotonic, never reset, never wrap.
- B3 price catalog object shape: `{catalog_version, generated_at, source, stale_after, checksum, entries:[...]}`.

## 1. Amaç

FAZ-B ops hardening için foundation: 4 docs + 8 schemas (5 data yeni + 3 policy yeni) + 3 schema delta (2 enum + 1 `output_parse` extension, mevcut schema'lara) + 3 policies + 2 bundled defaults + 2 config/code delta (`config.py` loader + `adapter_invoker.py` extraction). Runtime primitives (lease, cost, metrics, policy sim, benchmarks) PR-B1..B7'de.

### Kapsam

| Layer | Artefact | Est. |
|---|---|---|
| Docs | `docs/COORDINATION.md` — lease/fencing spec + "Expiry Authority" subsection (B2v3) | ~340 satır |
| Docs | `docs/COST-MODEL.md` — price catalog (object shape) + spend ledger + cost-aware routing + checksum/source/vendor_model_id | ~220 satır |
| Docs | `docs/METRICS.md` — metrics export + `policy_metrics` control plane (W1v3) | ~190 satır |
| Docs | `docs/BENCHMARK-SUITE.md` — governed-review (typed artifact) + governed-bugfix benchmark contract (B3v3) | ~180 satır |
| Schema | `ao_kernel/defaults/schemas/claim.schema.v1.json` (`expires_at` derived clarified) | ~85 satır |
| Schema | `ao_kernel/defaults/schemas/fencing-state.schema.v1.json` (B1v3 reinstate) | ~50 satır |
| Schema | `ao_kernel/defaults/schemas/price-catalog.schema.v1.json` (B1v3 array→object) | ~100 satır |
| Schema | `ao_kernel/defaults/schemas/spend-ledger.schema.v1.json` | ~60 satır |
| Schema | `ao_kernel/defaults/schemas/review-findings.schema.v1.json` (B3v3 NEW typed artifact) | ~70 satır |
| Schema | `ao_kernel/defaults/schemas/policy-coordination-claims.schema.v1.json` | ~60 satır |
| Schema | `ao_kernel/defaults/schemas/policy-cost-tracking.schema.v1.json` (B1v3 + `strict_freshness`) | ~50 satır |
| Schema | `ao_kernel/defaults/schemas/policy-metrics.schema.v1.json` (W1v3 NEW) | ~50 satır |
| Schema delta | `agent-adapter-contract.schema.v1.json` `capabilities[]` enum +`review_findings` (B3v3) | ~5 satır |
| Schema delta | `agent-adapter-contract.schema.v1.json` `output_parse[]` rule item shape genişletme (B3'''v5 — capability + schema_ref typed payload extraction) | ~25 satır |
| Schema delta | `workflow-definition.schema.v1.json` `capability_enum` +`review_findings` (B1'v4 — drift test parity) | ~3 satır |
| Bundled | `ao_kernel/defaults/catalogs/price-catalog.v1.json` (W2v3 path-fix; starter catalog) | ~50 satır |
| Bundled | `ao_kernel/defaults/workflows/review_ai_flow.v1.json` (B3v3 contract pin; B6 runtime impl) | ~60 satır |
| Policy | `ao_kernel/defaults/policies/policy_coordination_claims.v1.json` | ~70 satır |
| Policy | `ao_kernel/defaults/policies/policy_cost_tracking.v1.json` (+ `strict_freshness: false` default) | ~50 satır |
| Policy | `ao_kernel/defaults/policies/policy_metrics.v1.json` (W1v3 NEW; dormant) | ~50 satır |
| Code | `ao_kernel/config.py` — `load_default("catalogs", ...)` tipi extension (W2v3 + W4''v5 plural + full filename) | ~12 satır delta |
| Code | `ao_kernel/executor/adapter_invoker.py` — `_invocation_from_envelope` `output_parse` rule walker + `InvocationResult.extracted_outputs: dict[str, dict]` opsiyonel field (B4''''v6 absorb — extraction transport-layer'da) | ~30 satır delta |
| Tests | schema load + cross-ref drift + idempotent + catalog loader + typed artifact validation + adapter_invoker extraction roundtrip + InvocationResult backwards compat | ~40 test |
| CHANGELOG | `[Unreleased]` → FAZ-B PR-B0 entry | ~50 satır |
| **Toplam** | 4 docs + 8 schemas (5 data yeni + 3 policy yeni) + 3 schema delta (2 enum + 1 output_parse extension) + 3 policies + 2 bundled + 2 code delta (`config.py` + `adapter_invoker.py`) + 40 test | **~1760 satır** |

- Yeni evidence kind: **0** (runtime PR'larda; 6 claim_* PR-B1'de → 24-kind taxonomy)
- Yeni core dep: **0** (jsonschema>=4.23.0 unchanged)
- Yeni adapter capability: **1** (`review_findings`); adapter contract `output_parse[]` shape genişletildi + `adapter_invoker._invocation_from_envelope` extraction logic eklendi (backwards compatible — eski rules `capability`/`schema_ref` olmadan da geçerli)
- Test target: 1524 → ~1564 (+40)

## 2. Scope İçi

### 2.1 docs/COORDINATION.md (#4 lease/fencing spec)

**Concept model:** Claim, fencing_token, heartbeat, takeover, CLAIM_CONFLICT, CLAIM_CONFLICT_GRACE, claim revival.

**Claim lifecycle:** acquire → heartbeat (revival in grace) → release | expire → takeover.

**Storage (B1 absorb):** Claim `.v1.json` files = **SSOT**. `_index.v1.json` = derived cache (rebuildable from claim file scan on drift). Single workspace-level `{project_root}/.ao/claims/claims.lock` for all mutations. POSIX-only (Windows fail-closed via `_internal/shared/lock.py`).

**Fencing token (B2 absorb):** Persistent state file `{project_root}/.ao/claims/_fencing.v1.json` — map `resource_id → {next_token: int, last_owner_agent_id, last_released_at}`. Release claim file silinir ama `_fencing.v1.json` korunur. Token: strictly monotonic non-negative int, **never reset, never wrap** (Python int unbounded). Acquire/takeover: read `_fencing.v1.json` → `token = next_token` → inc `next_token` → CAS write.

**Heartbeat:** caller-driven `claim.heartbeat()` — NOT evidence-based (CNS-027 B3 absorb).

#### Expiry Authority (B2v3 absorb — locked-in)

| Karar | Değer | Gerekçe |
|---|---|---|
| **Otoriter expiry alanı** | `effective_expires_at = heartbeat_at + expiry_seconds` (computed at evaluation time) | `expires_at` claim shape'inde **derived** field (CAS write sırasında doldurulur, validation/debug amaçlı). Source-of-truth = `heartbeat_at`. |
| **Takeover threshold** | `now > heartbeat_at + expiry_seconds + takeover_grace_period_seconds` | Grace bitmeden takeover **denenmez** (CLAIM_CONFLICT_GRACE döner). |
| **Grace içinde 2. talep** | `CLAIM_CONFLICT_GRACE` (yeni error variant; CLAIM_CONFLICT'ten ayrı) | Owner hâlâ revive edebilir; takeover prematür değil. |
| **Owner grace içinde heartbeat** | **Claim revival** — `heartbeat_at` güncellenir (CAS `expected_revision`); `effective_expires_at` ileri kayar | Owner liveness'i kanıtlayabildiği sürece claim canlı kalır. |
| **In-flight step stale fencing** | `ClaimStaleFencingError` immediate fail (driver.run_step() başında check) | Stale token = takeover gerçekleşmiş; in-flight side-effect engellenir. |
| **`max_claims_per_agent` sayımı** | Sadece **non-expired** (`now ≤ effective_expires_at + grace`) claim'ler sayılır | Eski expired claim'ler `_index.v1.json`'da olabilir (cleanup cycle'a kadar); quota bu görünür sayıdan değil "live" sayıdan |
| **Multi-resource atomic acquire** | **v1'de unsupported** — `acquire_claim()` tek `resource_id` alır | Atomic multi-acquire FAZ-C scope; B0'da explicit "single-resource per call" kilitlenir |
| **Cleanup cycle** | Caller-driven `prune_expired_claims()` — driver background loop YOK | Liveness kararı correctness-critical; evidence side-channel'a bırakılmaz |

**Driver integration:** `Executor.run_step(driver_managed=True)` checks `fencing_token` at start; stale token → `ClaimStaleFencingError`. Take-over olduktan sonra eski owner'ın step'i side-effect üretmeden fail eder.

**Evidence events (runtime PR-B1):** `claim_acquired`, `claim_released`, `claim_heartbeat`, `claim_expired`, `claim_takeover`, `claim_conflict`. Toplam 24-kind taxonomy.

**Policy binding:** `policy_coordination_claims.v1.json` (ayrı dosya, `policy_multi_agent_coordination.v1.json` dokunulmaz).

### 2.2 docs/COST-MODEL.md (#7 full + price catalog + spend ledger)

**PriceCatalog (B3 + B1v3 absorb — object shape with metadata):**
```json
{
  "catalog_version": "1",
  "generated_at": "2026-04-16T00:00:00+00:00",
  "source": "bundled",
  "stale_after": "2026-07-16T00:00:00+00:00",
  "checksum": "sha256:abc...",
  "entries": [
    {
      "provider_id": "anthropic",
      "vendor_model_id": "claude-3-5-sonnet-20241022",
      "model": "claude-3-5-sonnet",
      "input_cost_per_1k": 0.003,
      "output_cost_per_1k": 0.015,
      "cached_input_cost_per_1k": 0.0003,
      "currency": "USD",
      "billing_unit": "per_1k_tokens",
      "effective_date": "2026-04-16"
    }
  ]
}
```

**Field semantics:**
- `source` — **enum**: `bundled | vendor_api | manual` (free string DEĞİL)
- `checksum` — **canonical JSON SHA-256** of `entries[]` array only (sort_keys=True, ensure_ascii=False, separators=(",",":")), prefixed `sha256:`. Validation: load catalog → recompute checksum on entries → compare. Mismatch → `PriceCatalogChecksumError`.
- `vendor_model_id` — vendor-side identifier (örn. `claude-3-5-sonnet-20241022`); `model` ise short routing key (örn. `claude-3-5-sonnet`). Mapping ayrımı: routing layer `model`'e göre seçer, billing/audit `vendor_model_id`'yi kullanır.
- `currency` — v1 enum: `USD` only (other currencies FAZ-E enterprise scope)
- `billing_unit` — v1 enum: `per_1k_tokens` only (per_request, per_image FAZ-D+ scope)
- `region` — v1'de **yok** (regional pricing FAZ-E enterprise scope; v1 global pricing assumption)

**Stale policy:** Default `warn` on stale catalog (`generated_at + 90d` rule; `stale_after` field optional override); policy opt-in `policy_cost_tracking.strict_freshness: true` → `fail_closed` on stale.

**Versioning:** Full snapshot replacement (versioned), NOT append-only. Bundled `ao_kernel/defaults/catalogs/price-catalog.v1.json` starting catalog (W2v3 path-fix).

**SpendLedger:** `{run_id, step_id, provider_id, vendor_model_id, model, tokens_input, tokens_output, cached_tokens, cost_usd, ts}` append-only JSONL under `.ao/cost/spend.jsonl`.

**BudgetAxis extension (PR-A1 `Budget`):** existing `cost_usd` axis + new `tokens_input` / `tokens_output` (A1 shipped axes: `tokens`, `time_seconds`, `cost_usd`; B2 adds granular).

**Cost cap fail-closed:** B2 runtime checks budget BEFORE adapter invocation; exceeding → `BudgetExhaustedError(category=budget_exhausted)` (A1 primitive).

**Model routing (#21):** B3 `resolve_route(intent, budget_remaining)` — if cost axis remaining < estimated cost (catalog lookup `(provider_id, model) → input_cost_per_1k * estimated_input_tokens / 1000`), falls back to cheaper model in same intent class.

### 2.3 docs/METRICS.md (Prometheus/OTEL export)

**Exposure:** Python `prometheus_client` + `/metrics` textfile collector pattern (no HTTP server in library); operator runs `ao-kernel metrics export --format prometheus`.

**Metrics (low cardinality default):**
- `ao_llm_call_duration_seconds{provider}` (histogram)
- `ao_llm_tokens_used_total{provider,direction}` (counter, direction ∈ {input, output, cached})
- `ao_policy_check_total{outcome}` (counter, outcome ∈ {allow, deny})
- `ao_workflow_duration_seconds{final_state}` (histogram)
- `ao_claim_active_total` (gauge)
- `ao_claim_takeover_total` (counter — B1 runtime'da emit)

**Advanced labels — opt-in (W1v3 absorb — schema-backed):**
- `policy_metrics.v1.json::labels_advanced.enabled: true` aktive eder
- `policy_metrics.v1.json::labels_advanced.allowlist: ["model", "agent_id"]` — operatör hangi label'ları açtığını seçer
- Default `enabled: false` → cardinality-safe baseline; opt-in dormant policy aktive ederse model/agent_id eklenir

**Grafana:** JSON model template shipped in `docs/grafana/` (operator imports).

**OTEL bridge:** existing `ao_kernel/telemetry.py` already has OTEL spans; metrics package `[metrics]` extra provides Prometheus export — `[otel]` and `[metrics]` independent.

### 2.4 docs/BENCHMARK-SUITE.md (governed-review + governed-bugfix benchmarks)

**Scenarios:**
- `tests/benchmarks/governed_bugfix/` — uses **existing** `bug_fix_flow.v1.json` (PR-A2 bundled)
- `tests/benchmarks/governed_review/` — uses **new** `review_ai_flow.v1.json` (B0 contract pin; B6 runtime impl)

**Typed artifact contract (B3v3 + B2'v4 absorb):**
- `agent-adapter-contract.schema.v1.json::capabilities[]` enum'a `review_findings` eklendi (~5 satır delta)
- `workflow-definition.schema.v1.json::capability_enum` enum'a `review_findings` eklendi (~3 satır delta) — drift test parity ([`test_workflow_registry.py:407`](tests/test_workflow_registry.py:407))
- New schema `review-findings.schema.v1.json`:
  ```json
  {
    "schema_version": "1",
    "findings": [
      {
        "file": "path/to/file.py",
        "line": 42,
        "severity": "error|warning|info|note",
        "message": "...",
        "suggestion": "..."
      }
    ],
    "summary": "Reviewed N files, found M issues",
    "score": 0.85
  }
  ```
- **Terminoloji ayrımı (W1'''v6 absorb):** Repo bugün HTTP transport'ta [`response_parse`](ao_kernel/defaults/schemas/agent-adapter-contract.schema.v1.json:180) kullanıyor — bu **transport-level canonical envelope extraction** (HTTP response body → canonical envelope shape). Yeni `output_parse` ise **capability-specific typed artifact extraction** (envelope → schema-validated payload). İki kavram ayrı katmanlardır: `response_parse` envelope üretir, `output_parse` envelope'tan typed payload'ları extract eder. Naming çakışmaz çünkü farklı kontrat seviyeleri.

- **Transport (B2'v4 + B3'''v5 + B4''''v6 absorb):** Artifact, **`output_parse` rule extension** ile schema-validated kanal üzerinden taşınır. Mevcut PR-A3 invariant: "JSONPath minimal subset only `$.key(.key)*`, no indices/wildcards". B0'da bu rule capability-aware genişletilir:
  ```jsonc
  // adapter manifest example (B6'da finalize)
  output_parse: {
    rules: [
      {
        capability: "review_findings",        // YENİ — capability-aware extraction
        json_path: "$.review_findings",       // mevcut JSONPath subset
        schema_ref: "review-findings.schema.v1.json"  // YENİ — typed validation
      }
    ]
  }
  ```
  **Çağrı zinciri (B4''''v6 — extraction transport-layer'da, single-pass):**
  1. Adapter envelope JSON'unda `review_findings: { ... }` field'ı döner. **Wording (W4'''v6 absorb):** envelope kendisi schema-validated DEĞİL (`output_envelope` kapalı şekil, free-form payload taşıyor); schema-valid olan **extract edilen payload** — `schema_ref` ile doğrulanmış hali.
  2. **`adapter_invoker._invocation_from_envelope` `output_parse` rule walker'ı çalıştırır** — her rule için: `json_path` ile envelope'tan extract → `schema_ref` schema'sına validate → fail ise `AdapterOutputParseError` raise (mevcut PR-A3 typed exception). **Error category mapping (W2'''v6 absorb):** Workflow runtime bu exception'ı yakalayıp [`workflow-run.schema::error.category`](ao_kernel/defaults/schemas/workflow-run.schema.v1.json) enum'unda `output_parse_failed` değerine map eder; exception'ın kendisinde `category` field yok ([`executor/errors.py:106`](ao_kernel/executor/errors.py:106)).
  3. Validation pass ise extracted payload `InvocationResult.extracted_outputs[capability]` field'ında `Executor`'a taşınır (default `dict[str, dict] = {}`, backwards compat — eski rules etkilenmez).
  4. `Executor.run_step(driver_managed=True)` `result.extracted_outputs[capability]` doğrudan alır → `artifacts.write_artifact()` canonical JSON yazar (atomic tmp+fsync+rename) → `workflow-run::step_record.output_ref` doldurur.
  5. Pointer `workflow-run.schema.v1.json::step_record.output_ref` üstünden — capability-specific schema validation `output_parse[].schema_ref` üstünden (B6 runtime'da rule walker; B0'da contract pin + invoker delta).

  **Layer separation:**
  - `adapter_invoker` = transport + capability-aware extraction (zaten transport-layer parse var, sabit alanları map ediyor — capability-aware extraction'ı aynı katmanda yapmak doğal)
  - `Executor` = artifact write + step_record CAS (schema-agnostic kalır, mevcut PR-A4b pattern korunur)

- **Adapter contract delta (B3'''v5):** `agent-adapter-contract.schema.v1.json::output_parse[]` rule item shape genişlemesi (~25 satır):
  - Mevcut: `{json_path: str}` (PR-A3 minimal)
  - Yeni: `{json_path: str, capability?: enum_from_capabilities[], schema_ref?: str}` — backwards compatible (eski rules `capability`/`schema_ref` opsiyonel)
  - `capability` value `capabilities[]` enum'a referans (cross-ref: rule'un advertise ettiği capability adapter'da declare edilmiş olmalı)
  - `schema_ref` string — relative path to bundled schema veya workspace override; loader `ao_kernel/defaults/schemas/` + `.ao/schemas/` arar
  - `additionalProperties: false` korunur, closed shape disiplini intact
  - Mevcut PR-A3 invariant'ı korunur: JSONPath subset değişmez (sadece `$.key(.key)*`, no indices/wildcards)

- **InvocationResult shape delta (B4''''v6):** `ao_kernel/executor/adapter_invoker.py::InvocationResult` dataclass:
  - Mevcut field'lar değişmez (backwards compat)
  - **Yeni opsiyonel field:** `extracted_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)` — capability-keyed, schema-validated payload map
  - Default empty dict — `output_parse` rule'u olmayan adapter'lar için noop
  - Type-safe: `dict[capability_name, payload_object]`

- `additionalProperties: false`, `severity` closed enum (4 değer; `critical` eklenmedi — Codex W7: ayrı policy/gate davranışı tetiklemediğinden taxonomy şişirir), `score` optional [0.0, 1.0]

**Benchmark success criteria:**
- `governed_bugfix`: workflow_completed + adapter `status=ok` + CI gate pass + cost under budget
- `governed_review`: workflow_completed + adapter returns valid `review-findings.schema.v1.json` artifact + adapter `status=ok` + cost under budget. **Objective scoring:** `findings.severity` distribution + `score` field (caller-defined threshold)

**Runner:** `pytest tests/benchmarks/ --benchmark-mode=fast|full` (fast = mock adapter returns canned `review-findings` artifact; full = real adapter — ops-only).

**Adapter capability matrix delta:**
- `read_repo` (existing) — required
- `write_diff` (existing) — required for governed_bugfix
- `run_tests` (existing) — required for governed_bugfix
- `review_findings` (NEW) — required for governed_review

**Edge Case Contracts (Q6'v7 absorb — kontrat-level pin, B6 yeniden tasarım önlenir):**

| Edge case | Contract | Hata yeri | Gerekçe |
|---|---|---|---|
| **Multiple `output_parse` rules → same `capability`** | **Invalid manifest, fail-closed** | Manifest load-time (`AdapterManifestCorruptedError`) | `extracted_outputs: dict[capability]` taşıyıcısında order-dependent ambiguity istenmez; rule walker deterministic olmalı |
| **`schema_ref` resolve olmaz** (bundled YOK + workspace override YOK) | **Fail-closed** | Tercihen manifest load-time (`AdapterManifestCorruptedError`); en kötü ihtimal invocation path'te `AdapterOutputParseError → workflow error.category=output_parse_failed` | Schema'sız typed payload contract = boş söz; B6 runtime'da unresolved schema_ref ile validation imkansız |
| **Extracted payload `null`** | Özel yasak yok — **schema ne diyorsa o** (schema `null` accept ediyorsa OK; etmiyorsa `AdapterOutputParseError`) | Validation layer (`schema_ref` JSON Schema validator) | Schema authority — `null` semantics application-specific (e.g. "no findings" valid bir review sonucu olabilir) |
| **Envelope'da capability field var ama `output_parse` rule yok** (örn. adapter `review_findings: {...}` döndürür ama manifest'te rule declare etmemiş) | **Sessizce ignore** — extraction opt-in | — (no error, no warning, no extraction) | Extraction opt-in olmalı; manifest sahibi declare etmemişse warning spam üretmeyiz; backwards compat (eski adapter'lar etkilenmez) |

Bu 4 contract B6 runtime walker için kontrat-level pinli; B6 implementation bu davranışları bozarsa B0 acceptance test'leri (§5'te listelenir) fail eder.

### 2.5 Schemas (8 yeni/delta)

**Data schemas (5):**
- `claim.schema.v1.json`: `claim_id`, `owner_agent_id`, `resource_id`, `fencing_token` (int ≥ 0), `acquired_at`, `heartbeat_at`, `expires_at` (**derived field — validation/debug only; effective expiry computed from heartbeat_at + policy.expiry_seconds**), `revision` (CAS hash). `additionalProperties: false`. `fencing_token` minimum: 0.
- `fencing-state.schema.v1.json` (B1v3 reinstate): top-level `{schema_version: "1", resources: {<resource_id>: {next_token: int, last_owner_agent_id: str|null, last_released_at: ISO8601|null}}}`. Map values `additionalProperties: false`. `resources` map keys validated by claim resource_id pattern.
- `price-catalog.schema.v1.json` (B1v3 array→object + W8v4 conditional + W2''v5 semantik fix): top-level **object** `{catalog_version, generated_at, source enum, stale_after, checksum, entries: [...]}`. `entries[*]` `additionalProperties: false`. `source` enum: `["bundled", "vendor_api", "manual"]` (top-level metadata field). `currency` enum: `["USD"]`. `billing_unit` enum: `["per_1k_tokens"]`. **W8v4 + W2''v5 conditional (doğru semantik):** JSON Schema `if/then` — `if top-level source == "vendor_api" then for each entries[*]: required vendor_model_id`; `bundled` ve `manual` source'lar için `vendor_model_id` opsiyonel (manuel katalog bakımını kırılganlaştırmamak için). **Düzeltme notu:** v4'te yanlışlıkla `entries[*].source` (entry-level) denilmişti; doğrusu `source` catalog-level metadata, conditional top-level value'ya bakar ve tüm entry'lere uygulanır.
- `spend-ledger.schema.v1.json`: JSONL event shape per line; `additionalProperties: false`.
- `review-findings.schema.v1.json` (B3v3 NEW): yukarıdaki shape; `severity` closed enum 4 değer; `findings[]` array, `additionalProperties: false`.

**Policy schemas (3):**
- `policy-coordination-claims.schema.v1.json`: `enabled: bool`, `max_claims_per_agent: int`, `heartbeat_interval_seconds: int`, `expiry_seconds: int`, `takeover_grace_period_seconds: int`, `claim_resource_patterns: [str]` (allowlist), `evidence_redaction: object`. Nested objects da `additionalProperties: false`.
- `policy-cost-tracking.schema.v1.json` (B1v3 + `strict_freshness`): `enabled: bool`, `price_catalog_path: str`, `spend_ledger_path: str`, `fail_closed_on_exhaust: bool`, **`strict_freshness: bool` (default false)**, `routing_by_cost: {enabled: bool}`. Nested `additionalProperties: false`.
- `policy-metrics.schema.v1.json` (W1v3 NEW): `enabled: bool`, `labels_advanced: {enabled: bool, allowlist: [enum: model|agent_id]}`. `additionalProperties: false` everywhere.

**Schema delta (3 mevcut schema'ya):**
- `agent-adapter-contract.schema.v1.json::capabilities[]` enum +`review_findings` (~5 satır — B3v3 absorb).
- `agent-adapter-contract.schema.v1.json::output_parse[]` rule item shape genişletme (B3'''v5 absorb — capability-aware typed payload extraction):
  - Mevcut item shape: `{json_path: str}` (PR-A3 minimal subset)
  - Yeni: `{json_path: str, capability?: enum_from_capabilities[], schema_ref?: str}`
  - `capability` ve `schema_ref` opsiyonel (backwards compatible — eski rules etkilenmez)
  - Cross-ref: `capability` value adapter'ın declare ettiği `capabilities[]` enum'undan biri olmalı (loader-level validation B6'da)
  - `schema_ref` resolve order: bundled `ao_kernel/defaults/schemas/{name}` → workspace override `.ao/schemas/{name}`
  - `additionalProperties: false` korunur, JSONPath subset değişmez
- `workflow-definition.schema.v1.json::capability_enum` enum +`review_findings` (B1'v4 absorb — drift test parity ile zorunlu; iki enum eşit olmalı, [`test_workflow_registry.py:407`](tests/test_workflow_registry.py:407)).

### 2.6 Policies (3 bundled default — 2 mevcut + 1 yeni)

- `policy_coordination_claims.v1.json`: dormant (`enabled: false`); operator override için hazır. Defaults: `heartbeat_interval_seconds: 30`, `expiry_seconds: 90`, `takeover_grace_period_seconds: 15`, `max_claims_per_agent: 5`, `claim_resource_patterns: ["*"]`.
- `policy_cost_tracking.v1.json`: dormant (`enabled: false`); `fail_closed_on_exhaust: true` default; `strict_freshness: false` default; `routing_by_cost.enabled: false` (B3'te aktif olur).
- `policy_metrics.v1.json` (W1v3 NEW): dormant (`enabled: false`); `labels_advanced.enabled: false` default; `labels_advanced.allowlist: []` (operator opt-in).

### 2.7 Bundled Defaults (2 yeni)

- `ao_kernel/defaults/catalogs/price-catalog.v1.json` (W2v3 path-fix): starter catalog with 4-6 mainstream provider/model rows (anthropic, openai, google, deepseek). `source: "bundled"`, `generated_at: 2026-04-16`, `stale_after: 2026-07-16`. Bundled is informational — operator override at `.ao/cost/catalog.v1.json`.
- `ao_kernel/defaults/workflows/review_ai_flow.v1.json` (B3v3 contract pin): minimal workflow declaring `review_findings` capability requirement on adapter step. Runtime impl PR-B6 (review AI workflow). B0'da sadece schema validation pass; integration test PR-B6'da.

### 2.8 Code Delta (~12 satır)

**`ao_kernel/config.py::load_default(kind, name)`** — yeni `kind="catalogs"` tipi (W4v4 plural + W3''v5 full filename absorb):
- Existing kinds (hepsi plural): `policies`, `schemas`, `registry`, `extensions`, `operations`
- Yeni: **`catalogs`** (plural — mevcut isimlendirmeyle uyumlu) → `ao_kernel/defaults/catalogs/{name}`
- **Çağrı imzası (W3''v5 absorb — full filename, mevcut API uyumlu):** `load_default("catalogs", "price-catalog.v1.json")`
- Mevcut [`config.py:77`](ao_kernel/config.py:77) full filename bekliyor; [`test_config.py:70`](tests/test_config.py:70) bu pattern'i kullanıyor — özel durum yaratmıyoruz
- `importlib.resources.files("ao_kernel.defaults.catalogs")` ile resolve
- 1 yeni branch (~10 satır), 1 yeni `Literal` value (`"catalogs"` type alias'a)
- D4 invariant: `importlib.resources` (wheel-safe)

## 3. Write Order + Commit DAG (Codex iter-5 advisory absorb)

**Pattern: contract-first, risk-first.** Saf schema-first ya da saf code-first değil. Önce code'un gerçekten bağlı olduğu çekirdek kontratları yaz, hemen arkasından regresyon riski en yüksek code (`adapter_invoker` extraction) + odaklı testler — fail-fast feedback. Düşük riskli code (`config.py` loader) sonra. Docs iki geçişli: skeleton önce (terminoloji + edge-case kararları + transport/layer separation pin), final polish sonda (examples + cross-links + wording).

### 3.1 7-Step Write Order

| Step | İçerik | Risk | Dependency |
|---|---|---|---|
| **1** | **Docs skeleton:** terminoloji (`response_parse` vs `output_parse`), Q6 edge-case kararları, transport/layer separation; COORDINATION.md "Expiry Authority" subsection; COST-MODEL.md object-shape; METRICS.md control plane; BENCHMARK-SUITE.md typed artifact contract | Düşük | — |
| **2** | **Core schema delta:** `review-findings.schema.v1.json` + `agent-adapter-contract.schema::capabilities[]` enum +`review_findings` + `agent-adapter-contract.schema::output_parse[]` net-yeni contract surface + `workflow-definition.schema::capability_enum` +`review_findings` (drift parity) | Orta (closed shape disiplini, drift test parity) | Step 1 (terminology pin) |
| **3** | **`adapter_invoker.py` extraction + odaklı testler:** `_invocation_from_envelope` rule walker + `InvocationResult.extracted_outputs` opsiyonel field; tests `tests/test_executor_adapter_invoker.py`'a ekle (extraction roundtrip + backwards compat + 4 Q6 edge case fail-fast'i: multi-rule + unresolvable + null + no-rule) | **Yüksek** (regresyon riski en burada — fail-fast `pytest tests/test_executor_adapter_invoker.py`) | Step 2 |
| **4** | **`config.py` catalogs loader + bundled catalog + odaklı testler:** `kind="catalogs"` Literal extension; `ao_kernel/defaults/catalogs/price-catalog.v1.json` starter; tests `tests/test_config.py`'a ekle (full filename: `load_default("catalogs", "price-catalog.v1.json")`) | Düşük | Step 2 |
| **5** | **Kalan data/policy schemas + bundled policies + workflow:** `claim`, `fencing-state`, `price-catalog`, `spend-ledger`, 3 policy schemas, 3 bundled policies (dormant), `review_ai_flow.v1.json` (cap_enum'a bağımlı — Step 2 sonrası) | Düşük (declarative) | Step 2 |
| **6** | **Kalan contract/cross-ref testleri:** `tests/test_pr_b0_contracts.py` (yeni dosya — yeni schema fixture validations + cross-policy field collision + `review_ai_flow` cross-ref drift); `tests/test_workflow_registry.py` capability_enum drift parity test | Orta | Step 3, 4, 5 |
| **7** | **Docs final pass + CHANGELOG:** examples + cross-links + wording polish; CHANGELOG `[Unreleased]` → FAZ-B PR-B0 entry (`Added` ana + opsiyonel `Changed` ince not — Q5 absorb) | Düşük | Step 1-6 |

### 3.2 Commit DAG (Q2 absorb — tek PR, 5 DAG-closed commit)

Atomic 1700-satırlık tek commit önerilmez (bisect zorluğu). Tek PR içinde 5 commit, her biri yeşil + her biri kendi dependency zincirini kapatır:

```
commit 1: core schema delta + review-findings        (Step 1+2: docs skeleton + core schemas)
commit 2: adapter_invoker + extraction + tests       (Step 3: yüksek riskli code, fail-fast)
commit 3: config.py catalogs + bundled catalog       (Step 4: düşük riskli code + bundled)
commit 4: kalan schemas/policies/defaults/workflow   (Step 5: declarative tail)
commit 5: docs final pass + cross-ref tests + CHANGELOG  (Step 6+7: contract tests + polish + release notes)
```

**Squash on merge:** GitHub squash merge ile main'e tek commit olarak iner, history yine review/bisect için temiz kalır.

**Kritik ilke:** Repo hiçbir commit'te invalid workflow/default taşımamalı (örn. `review_ai_flow.v1.json` `workflow-definition.capability_enum` delta'sından önce land etmemeli — commit 4 commit 1'e bağımlı). Her commit kendi dependency'sini kapatır + `pytest --co -q` collect aşamasında fail vermez + mypy strict + ruff temiz.

## 4. Scope Dışı (PR-B1..B7)

| Alan | PR | Not |
|---|---|---|
| `ao_kernel/coordination/` runtime package (claim, fencing, takeover) | B1 | B0 contract'ları kullanır |
| `ao_kernel/cost/` price catalog + spend ledger runtime + checksum verification | B2 | B0 catalog loader extension'ı kullanır |
| `ao_kernel/llm.py` cost-aware routing | B3 | Catalog lookup runtime |
| `ao_kernel/policy_sim/` simulation harness | B4 | Independent track |
| `ao_kernel/metrics/` Prometheus export + `[metrics]` extra | B5 | `policy_metrics` opt-in mekanizmasını kullanır |
| `review_ai_flow.v1.json` runtime + review AI workflow step | B6 | B0'da contract pin var, runtime burada |
| Benchmark suite runner + scenarios | B7 | `review-findings` typed artifact validation B0'dan |
| v3.2.0 release | B8 | — |

## 5. Acceptance

**Test dosya stratejisi (Q4'v7 absorb — sahiplik-bazlı, PR-A6 drift tekrarlanmaz):**
- Mevcut suite'lere ekleme:
  - `tests/test_executor_adapter_invoker.py` — extraction roundtrip + 4 Q6 edge case (multi-rule, unresolvable schema_ref, null payload, no-rule silent ignore) + `InvocationResult.extracted_outputs` backwards compat
  - `tests/test_config.py` — `load_default("catalogs", "price-catalog.v1.json")` + deterministic equality on bundled load
  - `tests/test_workflow_registry.py` — `capability_enum` + adapter `capabilities[]` drift parity ([`test_workflow_registry.py:407`](tests/test_workflow_registry.py:407) mevcut drift test pass olur)
- **Yeni tek dosya:** `tests/test_pr_b0_contracts.py` — yeni 5 data schema + 3 policy schema fixture validations; bundled `price-catalog.v1.json` + `review_ai_flow.v1.json` validates own schema; cross-policy field collision (policy_metrics.labels_advanced.allowlist vs bundled metrics list); `review-findings` typed artifact fixture (happy + sad path).
- Plan'a dosya sayısı vaat edilmez — "existing suites + one new B0 contract suite" pattern'ı.

---

- [ ] 4 docs published, cross-linked (COORDINATION ↔ COST-MODEL ↔ METRICS ↔ BENCHMARK-SUITE)
- [ ] 5 data schemas + 3 policy schemas load via `ao_kernel.config.load_default`
- [ ] 3 bundled policies dormant by default, override documented in each policy file's header comment
- [ ] 2 bundled defaults (catalog + workflow) validate against own schemas
- [ ] **Catalog loader test (W4v4 + W3''v5):** `load_default("catalogs", "price-catalog.v1.json")` returns valid object with `entries` array (full filename — mevcut [`test_config.py:70`](tests/test_config.py:70) pattern uyumlu)
- [ ] **strict_freshness drift guard:** `policy_cost_tracking.schema` includes `strict_freshness` field; doc'taki davranış schema ile uyumlu
- [ ] **Typed artifact validation:** `review-findings.schema.v1.json` validates expected fixture; severity enum closed (4 değer)
- [ ] **Adapter capability cross-ref (B1'v4):** Hem `agent-adapter-contract.schema.v1.json::capabilities[]` hem `workflow-definition.schema.v1.json::capability_enum` enum'larında `review_findings` mevcut. Mevcut [`test_workflow_registry.py:407`](tests/test_workflow_registry.py:407) drift test pass olur.
- [ ] **vendor_model_id conditional (W8v4 + W2''v5):** `price-catalog.schema` if/then ile **top-level** `source=vendor_api` ise tüm `entries[*].vendor_model_id` zorunlu; `bundled`/`manual` source'lar için opsiyonel — fixture testleri her iki yolu kapsar (entry-level değil, catalog-level conditional).
- [ ] **review-findings transport via output_parse rule (B2'v4 + B3'''v5 + B4''''v6):** Plan §2.4'te capability-aware extraction kilitli — `agent-adapter-contract.schema::output_parse[]` rule item shape genişlemesi (~25 satır). Extract edilen payload (envelope kendisi DEĞİL) `schema_ref` ile validate edilir. Layer separation: extraction `adapter_invoker._invocation_from_envelope` içinde (transport-layer); artifact write `Executor.run_step(driver_managed=True)` içinde (schema-agnostic kalır).
- [ ] **output_parse rule extension backwards compat:** Mevcut PR-A3 `output_parse[].json_path` rules `capability`/`schema_ref` olmadan da geçerli kalır (test: minimal rule + extended rule yan yana validate edilir).
- [ ] **InvocationResult backwards compat (B4''''v6):** `extracted_outputs: dict[str, dict] = {}` opsiyonel field; mevcut testler (PR-A3 [`adapter_invoker`](ao_kernel/executor/adapter_invoker.py) suite) değişiklik gerektirmez. Type check: `mypy strict` clean.
- [ ] **adapter_invoker extraction roundtrip test:** Fixture envelope `{review_findings: {...}, status: "ok", ...}` → `_invocation_from_envelope` walks `output_parse` rule → extracts `$.review_findings` → validates against `review-findings.schema.v1.json` → returns `InvocationResult(extracted_outputs={"review_findings": {...}}, ...)`. Failure path: invalid payload → `AdapterOutputParseError` raise → workflow runtime maps to `error.category=output_parse_failed`.
- [ ] **response_parse vs output_parse ayrımı doc'larda netleştirildi (W1'''v6):** `docs/ADAPTERS.md` ve plan §2.4'te bir cümle ile ayrım yazılı (`response_parse` = transport-level envelope; `output_parse` = capability-specific typed artifact extraction).
- [ ] **Cross-ref drift test:** evidence 6 claim_* kinds declared in COORDINATION.md match future `_KINDS` expansion (dummy test passes in B0; enforced in B1)
- [ ] **Deterministic equality on bundled load (W5v4):** `load_default("policies", "policy_metrics")` 2 kez çağrıldığında **deterministic equality** (`==` True, sıralı keys, aynı içerik) — identity DEĞİL (her çağrı yeni dict üretir, shared-mutable cache kontratı icat etmiyoruz)
- [ ] CHANGELOG entry + ruff + mypy strict clean
- [ ] No runtime behavior change (B0 = docs + spec + bundled data + 1 loader extension + 2 enum delta)

## 6. CNS-028v2 Iter-5 Question Candidates (historical — all resolved at AGREE)

**iter-2 + iter-3 + iter-4'te Codex tarafından non-blocking cevaplanan + plan'a absorb edilen sorular** (yeniden sorulmuyor):
- **Q7 (severity enum)** → `critical` eklenmedi; 4 değer benchmark için yeterli (iter-2 W7 cevap)
- **Q8 (claim revival knob)** → v1'de `allow_revival_in_grace` eklenmesin; revival davranışı kilitlendi (iter-3 cevap)
- **Q9 (catalog loader Literal)** → warning seviyesinde public API değişikliği; breaking değil (iter-3 cevap)
- **Q10 (vendor_model_id)** → Conditional: top-level `source=vendor_api` zorunlu, `bundled`/`manual` opsiyonel (iter-2 W8 + v5 semantik düzeltme)
- **Q11 (multi-resource defer)** → FAZ-C defer mantıklı (iter-3 cevap)
- **Q12 (artifact write timing)** → (a) doğru seçim — single-pass driver-managed pattern (iter-3 cevap)
- **Q13 (output_parse rule yeterliliği)** → "Hayır, tek başına yeterli değil" — extraction layer pin gerekli (iter-4 B4'''' blocker, v6'da extraction `adapter_invoker`'a taşındı, layer separation kilitli)

**iter-5 için tek teyit sorusu:**

**Q14 — InvocationResult shape genişlemesi yeterliliği.** B4''''v6 absorption'ı `InvocationResult` dataclass'ına opsiyonel `extracted_outputs: dict[str, dict]` field ekliyor (default empty, backwards compat). Extraction `_invocation_from_envelope` içinde yapılır (rule walk + json_path extract + schema_ref validate). Executor sadece `result.extracted_outputs[capability]` alıp `artifacts.write_artifact()` çağırır. Layer separation: invoker = transport + extraction, executor = artifact write + step_record CAS. Bu shape ve layer separation, `review_findings` capability'sinin adaptörden artifact'a kadar olan zincirini tam pin'liyor mu? B6 runtime impl için yeterli kontrat surface'i var mı?

## 7. Audit Trail

| Field | Value |
|---|---|
| Plan version | **v7** |
| Predecessor chain | v3 (iter-1 PARTIAL: 3B+2W) → v4 (iter-2 PARTIAL: 2B'+4W) → v5 (iter-3 PARTIAL: 1B'''+4W'') → v6 (iter-4 PARTIAL: 1B''''+4W''') → **v7 (iter-5 AGREE + Codex write-order advisory Q1-Q6 absorbed)** |
| Head SHA | `b3b1dce` |
| Base branch | `main` |
| Target branch | `claude/tranche-b-pr-b0` |
| **Active CNS thread** | `019d962d-1592-76b3-8702-b86322b83a6a` (CNS-20260416-028v2) |
| Previous CNS thread (expired) | `019d9528-3a64-7b62-be82-03aa800535bc` (CNS-20260416-028) |
| Master plan ref | `.claude/plans/FAZ-B-MASTER-PLAN.md` (CNS-027 iter-2 AGREE) |
| iter-5 verdict | **AGREE** + `ready_for_impl: true` + 2 non-blocking hardening warnings (WH1 wording "extension" → "net-yeni contract surface"; WH2 missing-path davranışı pin — v7 §2.4 Edge Case Contracts'ta absorb edildi) |
| Codex iter-5 advisory (Q1-Q6) | Write order (Q1-Q3), test dosya stratejisi (Q4), CHANGELOG semver (Q5), edge case contracts (Q6) — hepsi v7'de plan'a işlendi. Advisory non-mandatory; plan-time review-invariant korunur (AGREE seviyesi). |
| CHANGELOG entry plan (Q5 absorb) | Ana sınıflandırma `Added` — yeni schemas + policies + bundled + config.py loader extension + adapter_invoker typed extraction. Opsiyonel `Changed` ince not: "invoker now supports typed extracted outputs when declared by manifest". Semver minor (v3.1.0 → v3.2.0 uygun, v3.2.0 FAZ-B B8 release'de tag). |
| Adversarial pattern note | 5-iter cycle CNS-024/025 4-iter geçmişiyle uyumlu; her iter scope daralıyor, blocker count azalıyor (3→2→1→1→0). Total absorb: 7 blocker + 14 warning + 6 Q advisory (Q1-Q6). |

**Status:** Plan v7 complete. **Ready for implementation** per Codex iter-5 AGREE. İlave review gerekmiyor; hardening warnings v7 §2.4'te absorb edildi. Next: PR-B0 implementation başlat (§3 Write Order + Commit DAG per Codex advisory).
