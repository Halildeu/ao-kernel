# ao-kernel — Master Proje Planı

**Tarih:** 2026-04-14
**Başlangıç:** main @ PR #49 merged (670 test, v2.1.1)
**İstişareler:** CNS-009, CNS-010, CNS-20260414-001, CNS-20260414-002

---

## Context

v2.1.2 patch işleri tamamlandı (PR #46-49). Bu plan kalan TÜM işleri — kesinleşmiş, ertelenmiş ve yeni tespit edilmiş — tek bir proje planında topluyor. 4 faz, öncelik sırasına göre.

### Doğrulanmış Mevcut Durum
- **Test:** 670+ (643 → 670, +27 bu session)
- **README.md:** 172 satır (1 satır DEĞİL — eski varsayım yanlış)
- **py.typed:** VAR (eksik DEĞİL)
- **CI/CD:** `test.yml` (lint+test+mypy+coverage) + `publish.yml` (PyPI) — ikisi de var
- **CHANGELOG.md:** YOK

---

## Faz 1 — v2.2.0: Roadmap Test Kampanyası (~20 test)

**Öncelik:** 🔴 EN YÜKSEK — 2,497 LOC, 0 gerçek test, safety-critical kod
**İstişare:** CNS-009 (Codex Verdict D), CNS-20260414-001 Q5 onaylı

### Top-5 Kritik Modül (Codex önerisi)

| # | Modül | LOC | Risk | Test Senaryoları |
|---|-------|-----|------|-----------------|
| 1 | `exec_steps.py` | ~400 | 🔴 | readonly cmd allowlist enforcement, core unlock blocked report, milestone caps, run_cmd failure → DLQ/summary propagation, change_proposal_apply schema failure |
| 2 | `step_templates.py` | ~300 | 🔴 | file write safety, subprocess isolation, template dispatch |
| 3 | `executor.py` | ~300 | 🟠 | dry_run mode validation, compile→evidence→execute flow, DLQ/summary creation |
| 4 | `compiler.py` | ~200 | 🟠 | milestone subset determinism, invalid schema rejection, preflight injection |
| 5 | `exec_evidence.py` | ~150 | 🟠 | readonly snapshot baseline, missing git fallback |

**İkinci dalga (dolaylı kapsanabilir):** `change_proposals.py`, `sanitize.py`, `evidence.py`, `exec_contracts.py`

**Kritik dosyalar:**
- `ao_kernel/_internal/roadmap/exec_steps.py`
- `ao_kernel/_internal/roadmap/step_templates.py`
- `ao_kernel/_internal/roadmap/executor.py`
- `ao_kernel/_internal/roadmap/compiler.py`
- `ao_kernel/_internal/roadmap/exec_evidence.py`
- `tests/test_roadmap_facade.py` (mevcut 4 facade test)

**Tahmini:** ~20 test, yeni `tests/test_roadmap_internal.py`

---

## Faz 2 — v2.2.0: Entegrasyon Derinleştirme (~15 test)

**Öncelik:** 🟠 YÜKSEK — pipeline boşlukları ve test eksikleri

### 2a. Tool Use Graduation Hazırlığı (~8 test)

Tool use şu an "experimental". Codex CNS-20260414-001 Q3 graduation kriteri:
- Provider başına non-stream build + extract contract testleri
- Stream + tools contract testleri (7 test var, yeterli olabilir)
- Tool-result → context roundtrip testi
- build_tools_param callsite bağlantısı veya kaldırılması

**Dosyalar:**
- `ao_kernel/_internal/prj_kernel_api/tool_calling.py`
- `ao_kernel/_internal/prj_kernel_api/llm_request_builder.py` (build_tools_param entegrasyonu)
- `ao_kernel/client.py` (tool_results prod path bağlantısı)
- Yeni: `tests/test_tool_use_contract.py`

### 2b. Evidence Writer Client Entegrasyonu (~3 test)

Non-streaming `llm_call` path evidence yazmıyor (streaming path yazıyor). Gap kapatılmalı.

**Dosyalar:**
- `ao_kernel/client.py` (non-stream path'e evidence yazımı)
- `ao_kernel/_internal/evidence/writer.py`
- `tests/test_client.py` (evidence entegrasyon testi)

### 2c. Compaction Engine Edge Case Testleri (~4 test)

Mevcut: 3 basic test. Eksik: büyük karar seti, threshold sınırı, malformed context, archive oluşturma.

**Dosyalar:**
- `ao_kernel/_internal/session/compaction_engine.py`
- `tests/test_session_deep.py`

---

## Faz 3 — v2.3.0: Altyapı ve Kalite (~10 iş)

**Öncelik:** 🟡 ORTA — doğruluk ve bakım

### 3a. CHANGELOG.md Oluşturma
- Tüm versiyonların (v0.1.0 → v2.1.1) değişiklik notları
- Keep a Changelog formatı
- Her yeni release'de güncelleme

### 3b. SecretsProvider ABC Enforcement
- `provider.py` → `abc.ABC` + `@abstractmethod`
- `env_provider.py`, `vault_stub_provider.py` uyumu doğrulama
- ~1 test

### 3c. llm.py Eski Docstring Temizliği
- `src/ shim` referansları kaldırılacak (CNS-010 bulgusu)

### 3d. MCP HTTP Transport Testi
- stdio test edilmiş, HTTP transport test edilmemiş
- starlette + uvicorn integration test
- ~2 test

### 3e. semantic_retrieval Feature Flag
- context_compiler'a opsiyonel semantic scoring entegrasyonu
- Feature flag ile açılır (varsayılan kapalı)
- Maliyet ve failure policy belirlenmeli
- Codex istişaresi gerekli

### 3f. Vision/Audio Kod Altyapısı (Karar Gerekli)
- Registry flag'leri var (şu an hepsi unsupported), kod yok
- Multimodal request builder tasarımı
- En az 1 provider (OpenAI veya Claude) için vision support
- Codex istişaresi gerekli

### 3g. build_tools_param Callsite Temizliği
- Ya request_builder'a entegre et ya da dead code olarak kaldır
- CNS-20260414-001 bulgusu

### 3h. Memory Distiller Edge Case Testleri
- Cross-session fact promotion
- min_occurrences, min_stability threshold testleri
- ~3 test

### 3i. Capability Registry Güncellemesi
- Tool use "experimental" → "supported" (graduation testleri sonrası)
- Registry versiyonunu güncelle

### 3j. README.md Güncellemesi
- 172 satır mevcut — güncel özelliklerle karşılaştır
- MCP server, SDK client, streaming, context pipeline belgelenmeli

---

## Faz 4 — v3.0.0+: Ekosistem Genişleme (Uzun Vadeli)

**Öncelik:** 🟢 DÜŞÜK — gelecek vizyonu, Codex istişaresi gerekli

| # | Konu | Bağımlılık | Not |
|---|------|-----------|-----|
| 1 | **pgvector backend** | psycopg2, pgvector | Semantic retrieval için kalıcı vector store |
| 2 | **Extension loader** | D7 kararı (manifest discovery) | 18 manifest var, runtime loader yok |
| 3 | **Async/await** | D9 kararı (sync SDK) | MCP async, core sync — büyük refactor |
| 4 | **Secrets vault provider** | AWS Secrets Manager / HashiCorp Vault | Production secrets yönetimi |
| 5 | **Roadmap checkpoint/resume** | Faz 1 testleri önce | Tek yönlü execution → rollback desteği |
| 6 | **Geniş _internal coverage** | D13 kararı (aşamalı) | ~60 modül düşük coverage |
| 7 | **Otomatik tool-use loop** | Faz 2a graduation | client.llm_call içinde auto tool dispatch |
| 8 | **Prompt experiments** | A/B/canary/shadow altyapısı | Rakip tablosunda iddia var ama implementasyon belirsiz |

---

## Toplam Proje Metrikleri

| Faz | İş Sayısı | Test Tahmini | Release |
|-----|-----------|-------------|---------|
| Faz 1 | 1 büyük kampanya | ~20 test | v2.2.0 |
| Faz 2 | 3 iş grubu | ~15 test | v2.2.0 |
| Faz 3 | 10 iş | ~6 test + altyapı | v2.3.0 |
| Faz 4 | 8 uzun vadeli | Belirsiz | v3.0.0+ |
| **TOPLAM** | **22 iş** | **~41 test** | — |

---

## Karar Gerektiren Noktalar

Her biri yeni session'da Codex istişaresi gerektirir:

| # | Karar | Faz | Seçenekler |
|---|-------|-----|-----------|
| 1 | semantic_retrieval pipeline entegrasyonu | 3e | Feature flag vs standalone |
| 2 | Vision/audio ilk provider seçimi | 3f | OpenAI vs Claude vs Google |
| 3 | Async refactor scope | 4.3 | Sadece LLM transport vs tüm pipeline |
| 4 | Otomatik tool-use loop tasarımı | 4.7 | Max rounds, fail policy, context propagation |
| 5 | build_tools_param kaderi | 3g | Entegre et vs kaldır |

---

## Doğrulama Kuralları (Her Faz İçin)

1. `pytest tests/ -x -q` → tüm testler geçmeli
2. `ruff check ao_kernel/ tests/` → 0 hata
3. Yeni test sayısı CLAUDE.md'de sabitlenmez — komut referansı yeterli
4. Her faz sonunda memory güncellenir
5. Mimari karar içeren işlerde Codex istişaresi ZORUNLU
