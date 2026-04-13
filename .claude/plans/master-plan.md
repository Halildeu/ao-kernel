# ao-kernel — Master Proje Planı

**Tarih:** 2026-04-14
**Başlangıç:** main @ PR #50 merged (670 test, v2.1.1)
**İstişareler:** CNS-009, CNS-010, CNS-20260414-001, CNS-20260414-002, CNS-20260414-003, CNS-20260414-004

---

## Context

v2.1.2 patch işleri tamamlandı (PR #46-49). Bu plan kalan TÜM işleri topluyor. 4 faz, öncelik sırasına göre.

Codex CNS-003 (Verdict B) ile plan review edildi. Sonuç:
- 3g ve 3i → Faz 2a'ya taşındı (graduation bağımlılığı)
- 3f (vision/audio) → Faz 4'e atıldı (kod sıfır, erken)
- CI coverage _internal omit → Faz 1 başlangıcına eklendi
- tool_results minimal forwarding → Faz 2a'ya eklendi (CNS-004 Verdict C — orta yol)

### Doğrulanmış Mevcut Durum
- **Test:** 670+
- **README.md:** 172 satır
- **py.typed:** VAR
- **CI/CD:** `test.yml` + `publish.yml` var
- **CHANGELOG.md:** YOK

---

## Faz 0 — v2.2.0 Hazırlık: CI Coverage Düzeltmesi

**Öncelik:** 🔴 BLOCKER — Faz 1-2 testleri coverage gate'te görünmez
**İstişare:** CNS-20260414-003 additions[0]

pyproject.toml `[tool.coverage.run]` omit'i `ao_kernel/_internal/*` tamamen dışlıyor. Faz 1-2'de test yazılacak modüller omit'ten çıkarılmalı.

**Yaklaşım:** Test edilen modülleri omit'ten çıkar, geri kalanı tut.
```
omit = [
    "*/test_*",
    "*/_test*",
    "*/conftest.py",
    # Test edilen _internal modüller omit'ten ÇIKARILDI:
    # ao_kernel/_internal/roadmap/* (Faz 1)
    # ao_kernel/_internal/orchestrator/* (zaten testli)
    # ao_kernel/_internal/evidence/* (zaten testli)
    # ao_kernel/_internal/session/* (Faz 2c)
    # Hâlâ omit:
    "ao_kernel/_internal/prj_kernel_api/*",
    "ao_kernel/_internal/providers/*",
    "ao_kernel/_internal/secrets/*",
    "ao_kernel/_internal/shared/*",
    "ao_kernel/_internal/utils/*",
]
```

**Dosya:** `pyproject.toml`
**Test:** `pytest --cov --cov-fail-under=70` hâlâ geçmeli

---

## Faz 1 — v2.2.0: Roadmap Test Kampanyası (~20 test)

**Öncelik:** 🔴 EN YÜKSEK — 2,497 LOC, 0 gerçek test, safety-critical
**İstişare:** CNS-009, CNS-20260414-001 Q5

### Top-5 Kritik Modül

| # | Modül | Risk | Test Senaryoları |
|---|-------|------|-----------------|
| 1 | `exec_steps.py` | 🔴 | readonly enforcement, DLQ propagation, milestone caps, change_proposal schema |
| 2 | `step_templates.py` | 🔴 | file write safety, subprocess isolation, template dispatch |
| 3 | `executor.py` | 🟠 | dry_run validation, compile→evidence→execute flow, DLQ/summary |
| 4 | `compiler.py` | 🟠 | milestone determinism, invalid schema rejection, preflight injection |
| 5 | `exec_evidence.py` | 🟠 | readonly snapshot baseline, missing git fallback |

**Dosyalar:** `ao_kernel/_internal/roadmap/*.py`, yeni `tests/test_roadmap_internal.py`

---

## Faz 2 — v2.2.0: Entegrasyon Derinleştirme (~18 test)

**Öncelik:** 🟠 YÜKSEK

### 2a. Tool Use Graduation + Registry (~10 test)

**CNS-003 ve CNS-004 ile birleştirildi:** 3g (build_tools_param), 3i (registry), tool_results forwarding

İş kapsamı:
1. Provider başına non-stream build + extract contract testleri
2. build_tools_param → ya request_builder'a entegre et ya dead code kaldır (CNS-003 objection[0])
3. `llm_call(tool_results=...)` opsiyonel parametresi ekle (CNS-004 Verdict C)
4. tool_results'ı process_response_with_context'e forward et (non-stream + stream)
5. 2-3 client roundtrip testi
6. Capability registry: tool_use "experimental" → "supported" (CNS-003 objection[1] — graduation testleriyle aynı PR)

**Çıkış kriteri:** Contract testleri geçiyor + registry graduated + tool_results prod path bağlı + docstring güncel

**Dosyalar:**
- `ao_kernel/client.py` (tool_results parametre + forward)
- `ao_kernel/_internal/prj_kernel_api/tool_calling.py`
- `ao_kernel/_internal/prj_kernel_api/llm_request_builder.py`
- `ao_kernel/defaults/registry/provider_capability_registry.v1.json`
- Yeni: `tests/test_tool_use_contract.py`

### 2b. Evidence Writer Client Entegrasyonu (~4 test)

Non-streaming `llm_call` evidence yazmıyor. Sınır: workspace mode (library mode'da yazma yok). CNS-003 Q2 onaylı.

**Dosyalar:**
- `ao_kernel/client.py` (non-stream path'e evidence)
- `ao_kernel/_internal/evidence/writer.py`
- `tests/test_client.py`

### 2c. Compaction Engine Edge Case (~4 test)

Mevcut: 3 basic test. Eksik: büyük karar seti, threshold sınırı, malformed context, archive.

**Dosyalar:**
- `ao_kernel/_internal/session/compaction_engine.py`
- `tests/test_session_deep.py`

---

## Faz 3 — v2.3.0: Altyapı ve Kalite (7 iş)

**Öncelik:** 🟡 ORTA
**Sıra:** CNS-003 Q3 önerisi: `3b → 3d → 3j → 3a → 3c → 3h → 3e`

### 3b. SecretsProvider ABC Enforcement
- `provider.py` → `abc.ABC` + `@abstractmethod`
- **Not:** Mevcut test `SecretsProvider()` instantiate ediyor → test güncellenmeli (CNS-003 additions[2])
- ~1 test

### 3d. MCP HTTP Transport Testi
- starlette + uvicorn integration test
- ~2 test

### 3j. README.md Güncellemesi
- 172 satır mevcut — güncel özelliklerle karşılaştır

### 3a. CHANGELOG.md Oluşturma
- Keep a Changelog formatı
- v0.1.0 → v2.1.1 notları

### 3c. llm.py Eski Docstring Temizliği
- `src/ shim` referansları kaldır

### 3h. Memory Distiller Edge Case Testleri
- Cross-session fact promotion, threshold testleri
- ~3 test

### 3e. semantic_retrieval Feature Flag
- context_compiler'a opsiyonel semantic scoring
- Varsayılan kapalı, deterministic fallback
- Codex istişaresi gerekli

---

## Faz 4 — v3.0.0+: Ekosistem Genişleme (Uzun Vadeli)

**Öncelik:** 🟢 DÜŞÜK — Codex istişaresi gerekli

### Gerçekçi v3.0.0 adayları (CNS-003 Q5):
| # | Konu | Not |
|---|------|-----|
| 1 | **pgvector backend** | Extra tanımlı, adapter scope ile |
| 2 | **Extension loader** | 18 manifest var, runtime loader yok |
| 3 | **Secrets vault provider** | Minimal provider seam mevcut |
| 4 | **Roadmap checkpoint/resume** | Session checkpoint var, workflow-level ek katman |

### Uzun vadeli (v3.0.0 sonrası):
| # | Konu | Not |
|---|------|-----|
| 5 | **Vision/audio altyapısı** | Registry flag var, kod sıfır (CNS-003: v2.3.0'dan Faz 4'e atıldı) |
| 6 | **Async/await** | Core sync, MCP async — büyük refactor |
| 7 | **Geniş _internal coverage** | ~60 modül, program işi |
| 8 | **Otomatik tool-use loop** | Faz 2a graduation'a bağımlı, max_rounds/fail_policy tasarımı |
| 9 | **Prompt experiments** | A/B/canary/shadow — implementasyon belirsiz |

---

## Toplam Proje Metrikleri

| Faz | İş Sayısı | Test Tahmini | Release |
|-----|-----------|-------------|---------|
| Faz 0 | 1 (CI config) | 0 | v2.2.0 |
| Faz 1 | 1 büyük kampanya | ~20 test | v2.2.0 |
| Faz 2 | 3 iş grubu | ~18 test | v2.2.0 |
| Faz 3 | 7 iş | ~6 test + altyapı | v2.3.0 |
| Faz 4 | 9 uzun vadeli | Belirsiz | v3.0.0+ |
| **TOPLAM** | **21 iş** | **~44 test** | — |

---

## Karar Gerektiren Noktalar

| # | Karar | Faz | Seçenekler |
|---|-------|-----|-----------|
| 1 | semantic_retrieval pipeline entegrasyonu | 3e | Feature flag vs standalone |
| 2 | Vision/audio ilk provider seçimi | 4.5 | OpenAI vs Claude vs Google |
| 3 | Async refactor scope | 4.6 | Sadece LLM transport vs tüm pipeline |
| 4 | Otomatik tool-use loop tasarımı | 4.8 | Max rounds, fail policy, context propagation |

---

## İstişare Geçmişi (Bu Plan)

| ID | Konu | Verdict | Etki |
|---|------|---------|------|
| CNS-009 | Split release planı | D | Faz 1-2 ayrımı, roadmap top-5 |
| CNS-010 | CLAUDE.md review | C | 16 bölüm yeniden yazım |
| CNS-20260414-001 | Entegrasyon durumu | D | 5 kopuk halka tespiti |
| CNS-20260414-002 | Son tur uzlaşma | A | P0/P1/P2 onay |
| CNS-20260414-003 | Master plan review | B | 3g/3i→2a, 3f→Faz4, CI coverage |
| CNS-20260414-004 | tool_results tartışma | C | Minimal forwarding Faz 2'ye |

---

## Doğrulama Kuralları (Her Faz İçin)

1. `pytest tests/ -x -q` → tüm testler geçmeli
2. `ruff check ao_kernel/ tests/` → 0 hata
3. Yeni test sayısı CLAUDE.md'de sabitlenmez — komut referansı yeterli
4. Her faz sonunda memory güncellenir
5. Mimari karar içeren işlerde Codex istişaresi ZORUNLU
6. Test edilen _internal modüller coverage omit'ten çıkarılmalı (Faz 0)
