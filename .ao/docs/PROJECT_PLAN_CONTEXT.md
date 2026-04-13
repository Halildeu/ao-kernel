# ao-kernel Bağlam Yönetimi — Proje Planı

## 1. Proje Kimliği

| Alan | Değer |
|---|---|
| **Proje Adı** | ao-kernel Context Management System |
| **Öncelik** | Kritik — governed runtime'ın çekirdek farklılaşması |
| **Bağımlılık** | v0.1.0 scaffold tamamlandı (18 PR, 297 test) |
| **İstişare** | CNS-013, CNS-014, CNS-015, CNS-016, CNS-017 |
| **Sektör Referansları** | JetBrains NeurIPS 2025, Anthropic Context Engineering, OpenAI Agents SDK, Letta/MemGPT, Zep |

---

## 2. Problem

### 2.1 Mevcut Durum

ao-kernel'de 6 session modülü VAR ve kod olarak ÇALIŞIYOR ama **runtime'a bağlı değil**:

```
BUGÜN:
  context_store.py    → Context yazılıyor     → Kimse okumuyor
  compaction_engine.py → Compact fonksiyonu var → Kimse çağırmıyor
  memory_distiller.py  → Fact üretiliyor       → Kimse sorgulamıyor
  cross_session.py     → Aggregate yapılıyor   → Kimse kullanmıyor
```

**Teşhis (Codex CNS-015):** "Ana darboğaz yeni teknik eksikliği değil, orchestration eksikliği. Modüller var, sistem davranışı yok."

### 2.2 3 Acı Noktası

| # | Acı | Etki |
|---|---|---|
| A1 | Context window doluyor | Model performansı düşüyor, hata artıyor |
| A2 | Önceki kararlar unutuluyor | Her oturum sıfırdan başlıyor |
| A3 | Gereksiz bilgi enjekte ediliyor | Model odağını kaybediyor |

### 2.3 3 Hedef Senaryo

| # | Senaryo | Gereksinim |
|---|---|---|
| S1 | Tek agent, çok turn | Kararları hatırla, context'i yönet |
| S2 | Çok agent, paylaşımlı bellek | Claude + Codex karar paylaşımı |
| S3 | Platform SDK | Dış geliştiriciler kendi agentlarında kullanacak |

---

## 3. Vizyon: Governed Context Management

ao-kernel'in farklılaşma noktası: **hiçbir rakipte policy-gated memory yönetimi yok.**

```
                      ┌─────────────────────────┐
                      │   GOVERNANCE LAYER       │
                      │   Policy-gated memory    │
                      │   Budget enforcement     │
                      │   Decision approval      │
                      └────────┬────────────────┘
                               │
    ┌──────────────────────────┼──────────────────────────┐
    │                          │                          │
┌───▼────┐             ┌──────▼──────┐            ┌──────▼──────┐
│ WRITE  │             │  PROCESS    │            │   READ      │
│        │             │             │            │             │
│ Decision│             │ Prune       │            │ Compile     │
│ Extract │             │ Compact     │            │ Score       │
│ Capture │             │ Distill     │            │ Inject      │
│ Store   │             │ Promote     │            │ Budget      │
└─────────┘             └─────────────┘            └─────────────┘
```

### Rakip Karşılaştırma

| Özellik | ao-kernel (hedef) | LangGraph | Mem0 | Letta | Zep |
|---|---|---|---|---|---|
| Policy-gated memory | ✅ | ❌ | ❌ | ❌ | ❌ |
| Otomatik compaction | ✅ | ✅ | ❌ | ✅ | ❌ |
| Decision extraction | ✅ explicit-first | ❌ | ✅ pasif | ✅ self-edit | ❌ |
| Relevance scoring | ✅ profile-aware | ❌ | ❌ | ❌ | ✅ graph |
| Budget enforcement | ✅ governance | ❌ | ❌ | ❌ | ❌ |
| Cross-session facts | ✅ distill+promote | ❌ | ✅ | ✅ | ✅ temporal |
| Canonical karar store | ✅ | ❌ | ❌ | ❌ | ❌ |
| Multi-agent coord | ✅ (Faz 4) | ❌ | ❌ | ❌ | ❌ |

---

## 4. Kapsam

### 4.1 4 Faz (dış teslimat) + 7 İç Checkpoint (CP-0..CP-6)

| Faz | Checkpoint | Teslimat | Senaryo | Acı |
|---|---|---|---|---|
| **Faz 1** | CP-0: Temel doğruluk | Schema path, facade, roundtrip | Altyapı | — |
| | CP-1: Otomatik pipeline | Her turn → kayıt → prune → compact → save | S1 | A2 |
| | CP-2: Explicit capture | JSON/tool-call primary, heuristic fallback | S1 | A2 |
| **Faz 2** | CP-3: Context compiler | Active + canonical + facts → relevance → budget | S1 | A1, A3 |
| | CP-4: Basit profil routing | 2-3 task tipi (STARTUP, TASK, REVIEW) | S1 | A3 |
| **Faz 3** | CP-5: Canonical karar store | Promote/approve, fact≠karar ayrımı | S2 | A2 |
| **Faz 4** | CP-6: Multi-agent + retrieval | Paylaşımlı okuma, gerekirse vector | S2, S3 | A2 |

### 4.2 Kapsam Dışı

| # | Özellik | Neden |
|---|---|---|
| X1 | Tam vector/semantic retrieval | Deterministic relevance önce gelmeli (CNS-014) |
| X2 | Hot/warm/cold auto-evolution | Enforcement olmadan tier teorisi değersiz (CNS-015) |
| X3 | 6 profil tam routing | 2-3 profille başla, genişlet (CNS-016) |
| X4 | Self-editing memory (Letta) | Karmaşıklık/risk oranı yüksek |
| X5 | Temporal knowledge graph (Zep) | pgvector bağımlılığı, erken |
| X6 | Distributed/peer sync | Tek-agent pipeline önce çalışsın |

### 4.3 Definition of Done

**Faz 1 DoD:**
- [ ] `context_store` schema path düzeltildi, facade çalışıyor
- [ ] save/load roundtrip testi geçiyor (%99.9 success)
- [ ] Her LLM turn sonunda otomatik: decision capture → prune → compact (eşik aşılırsa) → save
- [ ] Explicit JSON/tool-call decision capture primary, heuristic fallback
- [ ] Decision capture precision %90+ (etiketli test setinde)
- [ ] Compaction otomatik tetikleniyor (threshold üstü sessionların %95+)
- [ ] Turn-bazlı continuity testi: 5 turn konuşma, 3. turn'de alınan karar 5. turn'de context'te

**Faz 2 DoD:**
- [ ] Context compiler 3 lane birleştiriyor: active session + canonical decisions + workspace facts
- [ ] Relevance score + token budget enforcement
- [ ] Her inject edilen öğe "neden seçildi" metadata'sı taşıyor
- [ ] 2-3 profil tanımlı: STARTUP, TASK_EXECUTION, REVIEW
- [ ] Profil bazlı context yükleme çalışıyor
- [ ] Enjekte edilen token baseline'a göre %30-50 düşmüş
- [ ] "Gereksiz inject" oranı <%20

**Faz 3 DoD:**
- [ ] Canonical decision store: fact ≠ karar ayrımı
- [ ] Promote mekanizması: ephemeral → canonical (otomatik veya onaylı)
- [ ] Cross-session fact paylaşımı çalışıyor
- [ ] Temporal lifecycle: fresh_until, review_after, expires_at
- [ ] Önceki kararlara uyum benchmark'ı baseline'a göre +20 puan

**Faz 4 DoD:**
- [ ] İki agent aynı canonical karar revizyonunu okuyor (%95+ tutarlılık)
- [ ] SDK hook'ları: `record_decision`, `compile_context`, `finalize_session`, `query_memory`
- [ ] 3. parti entegrasyon 1 günde yapılabilir
- [ ] Gerekirse vector retrieval fallback eklendi

---

## 5. Teknik Tasarım

### 5.1 Faz 1: Otomatik Memory Pipeline

#### CP-0: Temel Doğruluk

```
Düzeltilecek:
1. src/session/context_store.py → schema path resource_loader'a yönlendir
2. ao_kernel/session.py → SessionPaths kullanımı düzelt
3. End-to-end roundtrip: new_context → save → load → verify hash
```

#### CP-1: Otomatik Pipeline

```python
# ao_kernel/context/memory_pipeline.py

def process_turn(
    output_text: str,
    context: dict,
    *,
    provider_id: str,
    request_id: str,
    workspace_root: Path,
) -> dict:
    """Her turn sonunda otomatik çalışır. Elle çağırmaya gerek yok.

    1. Decision extract (JSON primary, heuristic fallback)
    2. upsert_decision() her karar için
    3. prune_expired_decisions()
    4. should_compact() → compact_session_decisions() (eşik aşılırsa)
    5. save_context_atomic()

    Returns: updated context
    """
```

```python
# ao_kernel/context/session_lifecycle.py

def start_session(workspace_root: Path, session_id: str, ttl: int = 3600) -> dict:
    """Oturum başlat — context yükle veya yeni oluştur."""

def end_session(context: dict, workspace_root: Path) -> dict:
    """Oturum kapat — son compact + distillation tetikle."""
```

#### CP-2: Explicit Decision Capture

```python
# Decision Extractor güncelleme:
# 1. JSON/tool-call çıktı → confidence 0.95 (primary)
# 2. Structured field extraction → confidence 0.8
# 3. Free-text heuristic → confidence 0.4 (fallback only)

# Yeni: tool_call result'tan otomatik decision
def extract_from_tool_result(tool_name: str, tool_output: dict) -> list[Decision]:
    """Tool sonucundan structured decision çıkar."""
```

### 5.2 Faz 2: Context Compiler + Profil Routing

#### CP-3: Context Compiler

```python
# ao_kernel/context/context_compiler.py

def compile_context(
    session_context: dict,
    *,
    canonical_decisions: dict | None = None,
    workspace_facts: dict | None = None,
    profile: str = "TASK_EXECUTION",
    max_tokens: int = 4000,
) -> CompiledContext:
    """3 lane'den context derle:

    Lane 1: Active session decisions (en güncel)
    Lane 2: Canonical decisions (promote edilmiş, kalıcı)
    Lane 3: Workspace facts (distill edilmiş)

    Her öğe relevance score alır.
    Token budget içinde en yüksek score'lular seçilir.
    """

@dataclass
class CompiledContext:
    preamble: str          # LLM'e gönderilecek metin
    total_tokens: int      # Kullanılan token
    items_included: int    # Dahil edilen karar/fact sayısı
    items_excluded: int    # Hariç tutulan sayı
    selection_reasons: list # Neden bu öğeler seçildi
```

#### CP-4: Basit Profil Routing

```python
# ao_kernel/context/profile_router.py

PROFILES = {
    "STARTUP": {
        "description": "İlk oturum, workspace keşfi",
        "priority_keys": ["workspace.*", "config.*"],
        "max_decisions": 10,
    },
    "TASK_EXECUTION": {
        "description": "Aktif geliştirme/görev",
        "priority_keys": ["runtime.*", "decision.*", "approved.*"],
        "max_decisions": 30,
    },
    "REVIEW": {
        "description": "Kod/plan gözden geçirme",
        "priority_keys": ["review.*", "standard.*", "quality.*"],
        "max_decisions": 20,
    },
}

def detect_profile(messages: list[dict]) -> str:
    """Mesaj içeriğinden profil tahmin et. Basit keyword matching."""

def get_profile_config(profile: str) -> dict:
    """Profil konfigürasyonunu döndür."""
```

### 5.3 Faz 3: Canonical Karar Store

```python
# ao_kernel/context/canonical_store.py

@dataclass
class CanonicalDecision:
    key: str
    value: Any
    category: str          # "architecture" | "runtime" | "user_pref" | "approved_plan"
    promoted_from: str     # session_id
    promoted_at: str       # ISO8601
    confidence: float
    fresh_until: str       # ISO8601
    review_after: str      # ISO8601
    supersedes: str | None # önceki karar key'i
    provenance: dict       # evidence linkage

def promote_decision(ephemeral: dict, *, category: str, approval: str = "auto") -> CanonicalDecision:
    """Ephemeral decision → canonical'e promote et."""

def query_canonical(workspace_root: Path, *, key_pattern: str = "*") -> list[CanonicalDecision]:
    """Canonical kararları sorgula."""
```

### 5.4 Faz 4: Multi-Agent Coordination

```python
# ao_kernel/context/agent_coordination.py

def read_canonical_revision(workspace_root: Path) -> dict:
    """Canonical store'un mevcut revision hash'ini oku."""

def sync_canonical(workspace_root: Path, *, agent_id: str) -> dict:
    """Agent'ın canonical view'ını güncelleştir."""

# SDK hook'ları:
# ao_kernel.context.record_decision(key, value, source)
# ao_kernel.context.compile_context(profile, max_tokens)
# ao_kernel.context.finalize_session()
# ao_kernel.context.query_memory(key_pattern)
```

---

## 6. Risk Analizi

| # | Risk | Olasılık | Etki | Faz | Mitigasyon |
|---|---|---|---|---|---|
| R1 | Pipeline her turn'de çağrılmazsa yine dormant kalır | Yüksek | Kritik | F1 | llm facade'e hardwire — opsiyonel değil |
| R2 | Decision capture false positive | Orta | Orta | F1 | Precision-first (recall sonra), etiketli test seti |
| R3 | Compaction bilgi kaybı | Orta | Yüksek | F1 | Compaction kalite benchmark'ı, archive korunur |
| R4 | Context compiler çok yavaş | Düşük | Orta | F2 | Budget-first tasarım, lazy scoring |
| R5 | Profil yanlış tespit | Orta | Düşük | F2 | Fallback: TASK_EXECUTION default |
| R6 | Canonical store schema drift | Düşük | Yüksek | F3 | Schema validation + migration |
| R7 | Multi-agent conflict | Orta | Yüksek | F4 | Last-write-wins + conflict log |
| R8 | Observation masking sinyal kaybı (JetBrains uyarısı) | Orta | Orta | F2 | Agresiflik policy-controlled |
| R9 | Atomic write corruption (yarım yazma) | Düşük | Kritik | F1 | tmp+fsync+rename pattern, roundtrip hash verify |
| R10 | Restart recovery (crash sonrası context kaybı) | Orta | Yüksek | F1 | Atomic save + recovery test, archive fallback |
| R11 | Schema migration (eski context formatı) | Orta | Yüksek | F3 | schema_version field + migration path |
| R12 | Concurrent writer conflict | Orta | Yüksek | F4 | Revision-based CAS, conflict log, governance gate |
| R13 | Storage bloat (disk büyümesi) | Orta | Orta | F1 | Archive retention limit (max 20), TTL prune |
| R14 | Policy misconfiguration (yanlış memory policy) | Düşük | Yüksek | F2 | Schema validation + doctor check + default fallback |

---

## 7. Başarı Kriterleri

### 7.1 Fonksiyonel (Faz bazlı)

| # | Kriter | Faz | Ölçüm |
|---|---|---|---|
| F1 | save/load roundtrip %99.9 success | 1 | 1000 roundtrip soak test, hash verify her birinde |
| F2 | Decision capture precision %90+ | 1 | 50+ etiketli JSON/text çift, precision = TP/(TP+FP) |
| F3 | Compaction otomatik tetik %95+ | 1 | 20 session oluştur (10 threshold üstü), compact sayısı/beklenen |
| F4 | 5-turn continuity testi geçiyor | 1 | Deterministik 5-turn script, 3.turn karar → 5.turn context'te |
| F5 | Token kullanımı %30-50 düşüş | 2 | 10 gerçek prompt before/after, ortalama token sayımı |
| F6 | Gereksiz inject oranı <%20 | 2 | 20 inject, her birinde selection_reason analizi, insan etiketli |
| F7 | Profil doğru tespit %80+ | 2 | 30 etiketli mesaj seti (10 STARTUP, 10 TASK, 10 REVIEW) |
| F8 | Önceki kararlara uyum +20 puan | 3 | 10 cross-session senaryo, karar tutarlılık skoru |
| F9 | Multi-agent tutarlılık %95+ | 4 | 20 concurrent read/write testi, revision match oranı |
| F10 | SDK entegrasyon <1 gün | 4 | Yeni geliştirici onboarding testi (saat bazlı ölçüm) |

### 7.2 Non-Fonksiyonel

| # | Kriter | Hedef |
|---|---|---|
| NF1 | Pipeline latency | <50ms per turn (compaction hariç) |
| NF2 | Compaction süresi | <500ms |
| NF3 | Context compile süresi | <100ms |
| NF4 | Memory kullanımı | <50MB per session |
| NF5 | Disk kullanımı | <5MB per session (archive dahil) |

### 7.3 Operasyonel SLO (CNS-017 ekleme)

| # | SLO | Hedef |
|---|---|---|
| SLO1 | Save atomicity | 0 partial write (tmp+fsync+rename) |
| SLO2 | Recovery success | Crash sonrası %100 context kurtarma |
| SLO3 | Compile determinism | Aynı input → aynı output (%100) |
| SLO4 | Concurrent read consistency | Okuma sırasında yazma → stale read yok |
| SLO5 | Auditability | Her inject/save/promote için provenance + revision |

---

## 8. Test Planı

### 8.1 Unit Testler (her faz)

| Faz | Test Grubu | Tahmini |
|---|---|---|
| F1 | memory_pipeline, session_lifecycle, explicit_capture, roundtrip | ~30 test |
| F2 | context_compiler, profile_router, budget_enforcement, selection_reasons | ~25 test |
| F3 | canonical_store, promote, query, temporal_lifecycle | ~20 test |
| F4 | agent_coordination, sync, sdk_hooks | ~15 test |

### 8.2 Integration Testler

| # | Test | Faz | Açıklama |
|---|---|---|---|
| I1 | 5-turn continuity | F1 | 5 mesaj, 3.'de karar, 5.'de context'te görünür |
| I2 | Compaction + quality | F1 | 50 karar, compact, sonra LLM kalite kontrolü |
| I3 | Profile-aware injection | F2 | STARTUP vs TASK farklı context üretir |
| I4 | Cross-session fact | F3 | Session A karar verir, Session B fact olarak görür |
| I5 | Multi-agent read | F4 | Agent X yazar, Agent Y okur, aynı değer |

### 8.3 Benchmark Testler

| # | Benchmark | Faz | Baseline | Hedef |
|---|---|---|---|---|
| B1 | Decision recall | F1 | 0% (şu an unutuyor) | %80+ |
| B2 | Token efficiency | F2 | 100% (hepsini inject) | %50-70 |
| B3 | Continuity score | F3 | 0 (cross-session yok) | +20 puan |
| B4 | Agent consistency | F4 | N/A | %95+ |

### 8.4 Chaos/Failure Testler (CNS-017 ekleme)

| # | Test | Faz | Açıklama |
|---|---|---|---|
| C1 | Yarım yazma recovery | F1 | Save sırasında crash simülasyonu, sonra load → recovery |
| C2 | Bozulan store | F1 | context JSON bozuk → graceful fallback |
| C3 | Eski schema migration | F3 | v1 context → v2 schema, migration path |
| C4 | Restart sonrası devam | F1 | Process öldür, tekrar başlat, context sağlam |
| C5 | İki agent aynı anda promote | F4 | Concurrent write, revision conflict detection |
| C6 | Disk dolu | F1 | Disk full simülasyonu → graceful error |

---

## 9. Uygulama Sırası

```
Faz 1: Otomatik Memory Pipeline (~5 gün)
  ├── CP-0: Temel doğruluk
  │   ├── context_store schema path → resource_loader
  │   ├── ao_kernel/session.py facade düzelt
  │   └── roundtrip test (save → load → verify)
  │
  ├── CP-1: Otomatik pipeline
  │   ├── ao_kernel/context/memory_pipeline.py
  │   ├── ao_kernel/context/session_lifecycle.py
  │   ├── process_turn() → extract → prune → compact → save
  │   ├── start_session() / end_session()
  │   └── llm facade'e hardwire (opsiyonel değil)
  │
  └── CP-2: Explicit capture
      ├── Decision Extractor: JSON primary (0.95), tool-call (0.9), heuristic fallback (0.4)
      ├── extract_from_tool_result()
      └── Etiketli test seti (50+ örnek, precision %90+)

Faz 2: Context Compiler + Profil (~4 gün)
  ├── CP-3: Context compiler
  │   ├── ao_kernel/context/context_compiler.py
  │   ├── 3 lane: active + canonical + facts
  │   ├── Relevance scoring + token budget
  │   └── selection_reasons metadata
  │
  └── CP-4: Basit profil routing
      ├── ao_kernel/context/profile_router.py
      ├── 3 profil: STARTUP, TASK_EXECUTION, REVIEW
      ├── detect_profile() — keyword matching
      └── Profile-aware context loading

Faz 3: Canonical Karar Store (~3 gün)
  └── CP-5: Canonical store
      ├── ao_kernel/context/canonical_store.py
      ├── CanonicalDecision dataclass (temporal lifecycle)
      ├── promote_decision() + query_canonical()
      ├── fact ≠ karar ayrımı
      └── Cross-session paylaşım

Faz 4: Multi-Agent + SDK (~3 gün)
  └── CP-6: Coordination + SDK
      ├── ao_kernel/context/agent_coordination.py
      ├── SDK hooks: record/compile/finalize/query
      ├── Revision-based sync
      └── Gerekirse vector retrieval fallback
```

---

## 10. Dosya Planı

### 10.1 Yeni Dosyalar

| Dosya | Faz | Tahmini Satır |
|---|---|---|
| `ao_kernel/context/memory_pipeline.py` | F1 | ~150 |
| `ao_kernel/context/session_lifecycle.py` | F1 | ~80 |
| `ao_kernel/context/context_compiler.py` | F2 | ~200 |
| `ao_kernel/context/profile_router.py` | F2 | ~100 |
| `ao_kernel/context/canonical_store.py` | F3 | ~180 |
| `ao_kernel/context/agent_coordination.py` | F4 | ~120 |
| `tests/test_memory_pipeline.py` | F1 | ~200 |
| `tests/test_context_compiler.py` | F2 | ~150 |
| `tests/test_canonical_store.py` | F3 | ~120 |
| `tests/test_agent_coordination.py` | F4 | ~100 |
| **Toplam** | | **~1400** |

### 10.2 Değiştirilecek Dosyalar

| Dosya | Faz | Değişiklik |
|---|---|---|
| `src/session/context_store.py` | F1 | Schema path → resource_loader |
| `ao_kernel/session.py` | F1 | SessionPaths düzelt |
| `ao_kernel/context/decision_extractor.py` | F1 | JSON primary + tool-call capture |
| `ao_kernel/context/context_injector.py` | F2 | Compiler'a delege et |
| `ao_kernel/llm.py` | F1 | Pipeline hook (opsiyonel değil) |

---

## 11. İstişare Geçmişi

| # | ID | Konu | Verdict |
|---|---|---|---|
| 1 | CNS-013 | Minimal viable context loop | C (Decision Extractor + Injector) |
| 2 | CNS-014 | Sektör stratejisi | C+ (JetBrains + Anthropic + governance) |
| 3 | CNS-015 | Derin analiz — 6 faz | ONCE_PIPELINE_SONRA_RETRIEVAL |
| 4 | CNS-016 | Claude itirazları | mostly_agree (4 faz kabul) |
| 5 | CNS-017 | Plan final review | B (revizyon gerekli → R9-R14, chaos test, SLO, protokol) |

---

## 12. Sektör Referansları

| Kaynak | Anahtar Bulgu | ao-kernel Karşılığı |
|---|---|---|
| JetBrains NeurIPS 2025 | Observation masking, LLM summary kadar etkili | Faz 2 compaction |
| Anthropic Context Engineering | JIT loading + compaction + memory tool | Faz 1 pipeline + Faz 2 compiler |
| OpenAI Agents SDK | Session memory + Last-N + distillation | Faz 1 lifecycle + Faz 3 distill |
| Letta/MemGPT | Self-editing tiered memory | X4 kapsam dışı (karmaşık) |
| Zep | Temporal knowledge graph | Faz 3 temporal lifecycle (basit) |
| Chroma Research | Context rot — performans düşüşü | Faz 2 budget enforcement |
| ByteByteGo Context Guide | Hierarchical memory tiers | Faz 2 profil routing |

---

## 13. Sözlük

| Terim | Tanım |
|---|---|
| Decision | LLM yanıtından çıkarılan yapısal karar (key-value + metadata) |
| Fact | Cross-session promote edilmiş kalıcı bilgi |
| Canonical Decision | Onaylanmış, kalıcı karar (fact'ten farklı: onayla geçer) |
| Compaction | Eski kararları arşivleyip son N'yi tutma |
| Distillation | Birden fazla session'daki kararlari kalıcı fact'e dönüştürme |
| Profile | Task tipi bazlı context yükleme stratejisi (STARTUP, TASK, REVIEW) |
| Context Compiler | 3 lane'den (session + canonical + facts) relevance-scored context üretme |
| Pipeline | Her turn sonunda otomatik çalışan karar kayıt + işleme zinciri |
| Governance | Policy-gated memory: neyin yükleneceğini, saklanacağını, silineceğini policy kontrol eder |
