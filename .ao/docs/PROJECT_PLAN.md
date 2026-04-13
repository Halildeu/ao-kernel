# ao-kernel v0.1.0 — Proje Planı

## 1. Proje Kimliği

| Alan | Değer |
|---|---|
| **Proje Adı** | ao-kernel v0.1.0 Scaffold |
| **Proje Sahibi** | Halil Kocoglu |
| **Başlangıç** | 2026-04-12 |
| **Kaynak Repo** | Halildeu/autonomous-orchestrator (commit a9a792b) |
| **Hedef Repo** | Halildeu/ao-kernel |
| **İstişare Geçmişi** | CNS-001, CNS-002, CNS-003, CNS-004, CNS-005, CNS-20260413-001 |

---

## 2. Vizyon ve Amaç

### 2.1 Problem

`autonomous-orchestrator` reposu 657 Python dosyası, 90 policy, 206 schema, 17 extension manifest içeren monolitik bir AI orchestrator. Bu kod:
- Başka projelere taşınamıyor (repo-bağımlı)
- `pip install` ile kurulamıyor
- CLI aracı yok
- Policy/schema dosyaları paketle birlikte dağıtılamıyor

### 2.2 Çözüm

`ao-kernel`: Governed AI orchestration runtime olarak PyPI'ye dağıtılabilir Python paketi.

### 2.3 Ürün Konumlandırması (CNS-001 R1)

**ao-kernel genel amaçlı agent framework DEĞİLDİR.**

ao-kernel = **governed runtime**. Farkı:
- 90 policy ile fail-closed davranış
- Her side-effect için JSONL evidence trail
- Workspace-based config (migration, doctor)
- Deterministic routing (LLM çağrılarında bile)

| | ao-kernel | LangGraph | CrewAI | Pydantic AI |
|---|---|---|---|---|
| Policy engine | 90 policy | Yok | Yok | Yok |
| Fail-closed | Evet | Hayır | Hayır | Hayır |
| Evidence trail | Self-hosted JSONL | LangSmith SaaS | Yok | Yok |
| Migration CLI | Evet | Yok | Yok | Yok |
| Doctor | Evet | Yok | Yok | Yok |

---

## 3. Kapsam (Scope)

### 3.1 Kapsam İçi (v0.1.0)

| # | Deliverable | Açıklama |
|---|---|---|
| D1 | pyproject.toml | Paket metadata, bağımlılıklar, CLI kayıt |
| D2 | ao_kernel/ facade | 7 Python dosyası — public API, CLI, config, workspace |
| D3 | ao_kernel/defaults/ | 324 bundled JSON (policies, schemas, registry, extensions, operations) |
| D4 | src/ shim | 42 allowlisted Python dosyası — compat katmanı |
| D5 | Doğrulama | 16 kontrol noktası |

### 3.2 Kapsam Dışı (v0.1.0'da YOK)

| # | Özellik | Neden Ertelendi | Hedef |
|---|---|---|---|
| X1 | Streaming | Mimari iş, Faz 1.5 | v0.2.0 |
| X2 | MCP server desteği | Adaptör tasarımı gerekli | v0.2.0 |
| X3 | Checkpoint/resume | LangGraph seviyesi birikim gerekli | v0.3.0 |
| X4 | OTEL native | Opsiyonel extras var, native değil | v0.2.0 |
| X5 | src.* → ao_kernel._legacy | Build-time codemod gerekli (R3) | v2.0.0 |
| X6 | tool_gateway.py | ops.manage dispatch sızıntısı | v0.2.0 |
| X7 | session/ modülü | Legacy workspace referansları | v0.2.0 |
| X8 | evidence/writer.py | Workflow shell bağımlılığı | v0.2.0 |
| X9 | Tam ops/ CLI | ao_kernel/cli.py facade yeterli | v0.2.0 |
| X10 | sdk/ client | subprocess wrapper, yeniden yazılacak | v0.2.0 |

### 3.3 Definition of Done (DoD)

v0.1.0 "tamamlandı" sayılması için:

- [ ] 16 doğrulama kontrolünün tamamı geçer
- [ ] `pip install ao-kernel` ile kurulur ve `ao-kernel version` çalışır
- [ ] `ao-kernel init` workspace oluşturur
- [ ] `ao-kernel doctor` 8 kontrolden en az 7 OK + 1 WARN (opsiyonel deps) kabul edilir
- [ ] Built wheel clean venv'de çalışır
- [ ] Hiçbir test dosyası wheel'a girmez
- [ ] Legacy workspace fallback DeprecationWarning verir
- [ ] src shim importları FutureWarning verir
- [ ] CLAUDE.md güncellenir (PR #76 main merge, governed runtime)

---

## 4. Mimari Kararlar

6 istişare turunda alınan 13 karar ve gerekçeleri.

### 4.1 Facade + Shim Stratejisi (CNS-001 D1)

```
┌─────────────────────────────────┐
│ ao_kernel/   ← PUBLIC FACADE   │
│   cli.py                       │
│   config.py                    │
│   init_cmd.py                  │
│   migrate_cmd.py               │
│   doctor_cmd.py                │
│   errors.py                    │
│   defaults/  ← BUNDLED JSON    │
├─────────────────────────────────┤
│ src/         ← COMPAT SHIM     │
│   shared/                      │
│   prj_kernel_api/              │
│   providers/                   │
│   orchestrator/                │
│   roadmap/                     │
└─────────────────────────────────┘
```

**Neden:** Kaynak repoda 691 import satırı `src.*` kullanıyor. Big-bang rename çok riskli. Facade yeni API sağlar, shim eski importları korur. v2.0.0'da shim kaldırılır.

**Alternatifler ve neden reddedildi:**
- Big-bang rename → 691 import kırılma riski
- Sadece facade, shim yok → mevcut kod çalışmaz
- Sadece shim, facade yok → yeni API yüzeyi olmaz

### 4.2 Katman Bazlı Allowlist (CNS-004 C, CNS-005 B)

657 dosyanın tamamı değil, **42 dosya** alınıyor (src/__init__.py dahil). Neden:

```
Kaynak: 657 dosya
  ├── 267 test dosyası        → EXCLUDE (wheel şişer)
  ├── ~248 repo-spesifik      → EXCLUDE (prj_*, ops/, sdk/)
  ├── ~100 workflow shell      → EXCLUDE (session/, evidence/)
  └── 42 core runtime          → INCLUDE (allowlist)
       ├── src/__init__.py (1) → root + deprecation warning
       ├── shared/ (3)         → SSOT utilities
       ├── prj_kernel_api/ (19)→ LLM control plane (18 + __init__)
       ├── providers/ (5)      → LLM provider abstraction
       ├── orchestrator/ (4)   → Execution engine + eval
       └── roadmap/ (10)       → Change execution kernel
```

**Neden klasör bazlı değil dosya bazlı:**
Aynı klasörde core runtime, CLI wrapper, repo-spesifik kod ve test karışık. Klasör bazlı karar yanlış dosyaları içeri alır. (Codex CNS-004 tespiti)

### 4.3 Tek Zorunlu Bağımlılık (CNS-002 R6)

```
Zorunlu:  jsonschema>=4.23.0    ← policy/schema validation
Extras:
  llm:    tenacity>=9.0.0      ← retry + exponential backoff
          tiktoken>=0.9.0      ← OpenAI token counting
  dev:    pytest, ruff, mypy
  otel:   opentelemetry-*
  pgvector: pgvector, psycopg2-binary
```

**Neden:** Kaynak repo `pyproject.toml` sadece `jsonschema` ilan ediyor. `tenacity` ve `tiktoken` PR #76 ile geldi ama ancak LLM modülleri aktif kullanıldığında gerekli. Zorunlu yapmak gereksiz bağımlılık.

### 4.4 Library Mode + Workspace Mode (CNS-001 R2)

```python
# Library mode — workspace gerekmez
from ao_kernel.config import load_default
policy = load_default("policies", "policy_autonomy.v1.json")

# Workspace mode — .ao/ dizini gerekir
# ao-kernel init    ← workspace oluşturur
# ao-kernel doctor  ← workspace kontrol eder
```

**workspace_root() davranışı:**
```
workspace_root(override="/custom") → Path("/custom")     # Flag öncelikli
workspace_root()                   → Path(".ao/")        # Varsa .ao/
workspace_root()                   → Path(".cache/ws_*") # Legacy + WARNING
workspace_root()                   → None                # Library mode
```

**Neden:** Basit embed senaryosu (`import ao_kernel`) workspace gerektirmemeli. CLI ve governance kullanan ekip workspace açar. Rakiplerde bu esneklik yok.

### 4.5 Legacy Workspace Fallback (CNS-002 R9)

`.cache/ws_customer_default` v1.x boyunca desteklenir ama:
- Her kullanımda `DeprecationWarning` verilir
- v2.0.0'da kaldırılır
- Agent docs (AGENTS.md, .claude/, .gemini/) kırılmasın diye korunur

**Neden:** Codex istişaresi CNS-003'te kesinleşti — sessiz fallback hata ayıklamayı bozar, ama tamamen kaldırmak mevcut kullanıcıları kırar.

### 4.6 Migration Contract (CNS-003 R4)

```
ao-kernel migrate              → plan + rapor üret, uygula
ao-kernel migrate --dry-run    → sadece tespit + plan + rapor
ao-kernel migrate --backup     → değişecek dosyaları yedekle
```

v0.1.0 aksiyon seti:
- workspace.json bootstrap
- Legacy workspace tespiti
- Köprü metadata yazımı

**Neden:** Workspace-merkezli üründe migration yan özellik değil, çekirdek güvenilirlik. (Codex CNS-003 itirazı kabul edildi)

### 4.7 Extension Manifest-Only (CNS-003 R8)

```
ao_kernel/defaults/extensions/
  PRJ-AIRUNNER/extension.manifest.v1.json
  PRJ-DEPLOY/extension.manifest.v1.json
  ... (17 manifest)
```

Sadece JSON manifest paketlenir, Python runtime kodu paketlenmez.

**Neden:** Extension schema ve 17 manifest zaten var. Boş placeholder zayıf kalır (Codex CNS-003 kanıtladı). Ama tam runtime kod taşımak gereksiz — manifest discovery yeterli.

### 4.8 prj_kernel_api/__init__.py Patch (CNS-20260413-001 R11)

Mevcut `__init__.py`:
```python
from .adapter import handle_request
```

`adapter.py` allowlist dışında → `import src.prj_kernel_api` kırılır.

**Çözüm:** Bu import kaldırılır. Modül doğrudan alt dosyalardan import edilir.

### 4.9 docs/OPERATIONS LLM JSON'ları (CNS-20260413-001 R12)

`llm_router.py` ve `llm_probe_runner.py` şu dosyalara bağımlı:
- `docs/OPERATIONS/llm_class_registry.v1.json`
- `docs/OPERATIONS/llm_resolver_rules.v1.json`
- `docs/OPERATIONS/llm_provider_map.v1.json`

**Çözüm:** `ao_kernel/defaults/operations/` altına paketlenir.

### 4.10 src/__init__.py Deprecation Warning (CNS-003 R7)

```python
"""Project source package (WWV) — DEPRECATED: use ao_kernel.* instead."""
import warnings as _w
_w.warn(
    "Importing from 'src.*' is deprecated. Use 'ao_kernel.*' instead. "
    "This shim will be removed in v2.0.0.",
    FutureWarning,
    stacklevel=2,
)
del _w
```

**Neden:** B+C (docs+facade) yeterli değil — doğrudan `from src...` yapan kullanıcıyı uyarmaz. `src/__init__.py` minimum risk, maksimum etki noktası. (Codex CNS-003 ikna etti)

---

## 5. Dosya Envanteri

### 5.1 Yeni Yazılacak Dosyalar (ao_kernel/)

| Dosya | Satır (tahmini) | Açıklama |
|---|---|---|
| `ao_kernel/__init__.py` | ~20 | version + exports |
| `ao_kernel/cli.py` | ~120 | argparse CLI |
| `ao_kernel/config.py` | ~110 | workspace resolver + defaults loader |
| `ao_kernel/init_cmd.py` | ~80 | .ao/ bootstrap |
| `ao_kernel/migrate_cmd.py` | ~120 | migration contract |
| `ao_kernel/doctor_cmd.py` | ~160 | 8 sağlık kontrolü |
| `ao_kernel/errors.py` | ~30 | typed exceptions |
| **Toplam** | **~640** | 800 satır/dosya limitinin altında |

### 5.2 Kopyalanacak Dosyalar (src/ allowlist)

| Modül | Dosya Sayısı | Kaynak |
|---|---|---|
| src/ root | 1 (+patch) | `__init__.py` |
| src/shared/ | 3 | `__init__`, `logger`, `utils` |
| src/prj_kernel_api/ | 19 (+patch) | `__init__` + 18 runtime (guardrails, registry, LLM katmanı) |
| src/providers/ | 5 | `__init__` + 4 runtime (capability, response_parser, structured_output, token_counter) |
| src/orchestrator/ | 4 | `__init__` + 3 runtime (quality_gate, decision_quality, eval_harness) |
| src/roadmap/ | 10 | `__init__` + 9 runtime (change execution kernel) |
| **Toplam** | **42 dosya + 2 patch** | |

### 5.3 Bundled Defaults

| Kategori | Dosya Sayısı | Kaynak |
|---|---|---|
| policies/ | 90 | `autonomous-orchestrator/policies/` |
| schemas/ | 206 | `autonomous-orchestrator/schemas/` |
| registry/ | 8 | `autonomous-orchestrator/registry/` (archives/ hariç) |
| extensions/ | 17 | `autonomous-orchestrator/extensions/PRJ-*/extension.manifest.v1.json` |
| operations/ | 3 | `autonomous-orchestrator/docs/OPERATIONS/llm_*.json` |
| **Toplam** | **324 JSON** | |

### 5.4 ALINMAYAN ve Nedenleri

| Kategori | Dosya Sayısı | Neden |
|---|---|---|
| Test dosyaları | 267 | Wheel boyutu, runtime değil |
| ops/ | 287 | CLI shell, repo-spesifik komutlar |
| prj_airunner/ | 67 | %73 test, repo tick runner |
| prj_github_ops/ | 41 | %76 test, GitHub workflow |
| benchmark/ | 49 | %75 test, gap engine |
| session/ | 10 | Legacy workspace referansları yaygın |
| evidence/ | 4 | workflow shell bağımlılığı |
| sdk/ | 2 | subprocess wrapper, gerçek API değil |
| prj_planner/ | 10 | Repo-spesifik planlama |
| prj_release_automation/ | 7 | Release pipeline |
| utils/ | 2 | shared/ canonical, redundant |
| secrets/ (vault_stub) | 4 | dotenv_loader yeterli |
| learning/ | 5 | Aktif runtime yolunda değil |
| autopilot/ | 2 | Status reporting, çekirdek değil |
| modules/ | 3 | Repo-spesifik workflow modülleri |
| tenant/ | 6 | Startup config, ertelendi |
| src/extensions/ | 6 | Stub'lar, canonical discovery defaults'ta |
| adapter.py, http_gateway.py, codex_home.py, m0_plan.py vb. | 8 | Repo-spesifik, core değil |
| **Toplam dışlanan** | **~615** | 657 - 42 = 615 |

---

## 6. Teknik Tasarım

### 6.1 pyproject.toml Yapısı

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "ao-kernel"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["jsonschema>=4.23.0"]

[project.optional-dependencies]
llm = ["tenacity>=9.0.0", "tiktoken>=0.9.0"]
dev = ["pytest", "ruff", "mypy"]
otel = ["opentelemetry-api", "opentelemetry-sdk", "opentelemetry-exporter-otlp"]
pgvector = ["pgvector", "psycopg2-binary"]

[project.scripts]
ao-kernel = "ao_kernel.cli:main"

[tool.setuptools.packages.find]
include = ["ao_kernel", "ao_kernel.*", "src", "src.*"]
exclude = ["*_test", "*_test.*", "*_contract_test", "*_contract_test.*"]

[tool.setuptools.package-data]
"ao_kernel.defaults" = ["**/*.json"]
```

### 6.2 CLI Akışı

```
ao-kernel --workspace-root /path  ← global flag (opsiyonel)
  ├── init                         ← .ao/ workspace oluştur
  ├── migrate [--dry-run] [--backup] ← versiyon migration
  ├── doctor                       ← sağlık kontrolü
  └── version                      ← versiyon yazdır
```

Dispatch: `argparse.add_subparsers()` + `set_defaults(func=handler)`

### 6.3 Config Resolver Akışı

```
workspace_root(override=None)
  │
  ├─ override verildi? → Path(override) döner
  │
  ├─ CWD'den yukarı .ao/ ara → bulunursa Path döner
  │
  ├─ CWD'den yukarı .cache/ws_customer_default ara
  │     → bulunursa WARNING + Path döner
  │
  └─ hiçbiri yok → None döner (library mode)
```

```
load_default("policies", "policy_autonomy.v1.json")
  │
  └─ importlib.resources.files("ao_kernel.defaults")
       .joinpath("policies")
       .joinpath("policy_autonomy.v1.json")
       .read_text() → json.loads()
```

```
load_with_override("policies", "policy_autonomy.v1.json", workspace=Path(".ao"))
  │
  ├─ .ao/policies/policy_autonomy.v1.json var? → onu yükle
  │
  └─ yoksa → load_default() fallback
```

### 6.4 Doctor Kontrolleri

```
ao-kernel doctor
┌──────────────────────────────────┬────────┐
│ Kontrol                          │ Sonuç  │
├──────────────────────────────────┼────────┤
│ 1. Workspace bulundu             │ OK     │
│ 2. workspace.json geçerli        │ OK     │
│ 3. Bundled defaults erişim       │ OK     │
│ 4. Python >= 3.11                │ OK     │
│ 5. jsonschema yüklü              │ OK     │
│ 6. tenacity/tiktoken (opsiyonel) │ WARN   │
│ 7. src shim import               │ OK     │
│ 8. Extension manifest discovery  │ OK     │
└──────────────────────────────────┴────────┘
```

### 6.5 Migrate Contract

```
ao-kernel migrate --dry-run
┌──────────────────────────────────────────────┐
│ Migration Report                             │
│                                              │
│ workspace_version: 0.1.0                     │
│ package_version:   0.1.0                     │
│ status: UP_TO_DATE                           │
│ mutations: []                                │
│ backup_skipped: no_mutations                 │
│                                              │
│ legacy_workspace_detected: false             │
│ action_items: []                             │
└──────────────────────────────────────────────┘
```

---

## 7. Risk Analizi

### 7.1 Risk Matrisi

| # | Risk | Olasılık | Etki | Mitigasyon |
|---|---|---|---|---|
| R1 | Shim dosyaları repo-kökü path'e bakıyor | Yüksek | Yüksek | config.py resource loader, doctor kontrolü |
| R2 | prj_kernel_api/__init__.py patch kırılma | Orta | Yüksek | Smoke test, adapter kullanımı grep |
| R3 | Recursive policy kopyası eksik dosya | Orta | Orta | find + diff doğrulama |
| R4 | wheel'da test dosyası sızıntısı | Düşük | Orta | zipinfo + grep doğrulama |
| R5 | importlib.resources traversal hatası | Orta | Yüksek | Her alt dizine __init__.py, doctor self-test |
| R6 | Legacy fallback sessiz kalma | Düşük | Orta | DeprecationWarning + doctor uyarısı |
| R7 | Dependency version conflict | Düşük | Yüksek | Minimal deps (sadece jsonschema zorunlu) |
| R8 | docs/OPERATIONS JSON path uyumsuzluğu | Yüksek | Orta | defaults/operations/ + resource loader |
| R9 | Clean venv'de farklı davranış | Orta | Yüksek | Doğrulama #16: built wheel clean venv testi |
| R10 | CLAUDE.md ile kaynak drift | Yüksek | Düşük | SHA referansları sabitle, source manifest |

### 7.2 Risk Hafifletme Stratejisi

**R1 (repo-kökü path):** En kritik risk. `api_guardrails.py`, `provider_guardrails.py`, `quality_gate.py`, `roadmap/*` dosyaları `policies/` ve `schemas/` dizinlerine repo-kökünden erişiyor. **Çözüm (kesin):** Bu dosyalar `ao_kernel.config.load_default()` üzerinden bundled defaults'a yönlendirilecek şekilde patchlenecek. Her dosya için resource-loading noktası tespit edilip `importlib.resources` çağrısına dönüştürülecek. Doctor bu path'lerin çalıştığını doğrulayacak. v0.1.0'da hem editable install hem wheel dağıtımda çalışmalı.

**R8 (docs/OPERATIONS):** `llm_router.py` ve `llm_probe_runner.py` bu 3 JSON'a bağımlı. `ao_kernel/defaults/operations/` altına paketleyip erişim sağlanacak.

---

## 8. Uygulama Planı

### 8.1 Task Sırası ve Bağımlılıklar

```
Wave 1 (paralel — bağımsız dosya işlemleri):
  ├── Task 1: pyproject.toml yaz
  ├── Task 3: ao_kernel/defaults/ oluştur + JSON kopyala
  └── Task 4: src/ allowlist dosyaları kopyala + patch

Wave 2 (sıralı — Wave 1 tamamlanmış olmalı):
  └── Task 2: ao_kernel/ facade modüllerini yaz

Wave 3 (doğrulama):
  └── 16 kontrol noktası çalıştır
```

### 8.2 Task Detayları

#### Task 1: pyproject.toml
**Girdi:** Mimari kararlar (bölüm 4)
**Çıktı:** `pyproject.toml` dosyası
**Kabul kriteri:** `pip install -e ".[dev]"` başarılı
**Tahmini dosya:** 1 dosya, ~50 satır

#### Task 2: ao_kernel/ Facade
**Girdi:** Task 1 tamamlanmış, Task 3 + 4 tamamlanmış
**Çıktı:** 7 Python dosyası
**Kabul kriteri:**
- `ao-kernel version` çalışır
- `ao-kernel init` .ao/ oluşturur
- `ao-kernel doctor` 8 kontrol geçer
- `ao-kernel migrate --dry-run` rapor üretir
- `workspace_root()` → None (library mode)
- Legacy fallback DeprecationWarning
- WorkspaceCorruptedError bozuk JSON'da
**Tahmini:** 7 dosya, ~640 satır

#### Task 3: ao_kernel/defaults/
**Girdi:** Kaynak repo dosyaları (autonomous-orchestrator)
**Çıktı:** 324 JSON + __init__.py dosyaları
**Kabul kriteri:**
- `load_default("policies", "policy_autonomy.v1.json")` çalışır
- `work_intake_fragments/rules/` altındaki dosyalar erişilebilir
- 17 extension manifest erişilebilir
- 3 operations JSON erişilebilir
**Tahmini:** 324 JSON kopyası + ~10 __init__.py

#### Task 4: src/ Allowlist Kopya
**Girdi:** Kaynak repo main (a9a792b)
**Çıktı:** 42 Python dosyası + 2 patch
**Kabul kriteri:**
- `from src.shared.utils import load_json` → OK + FutureWarning
- `import src.prj_kernel_api` → ImportError OLMAZ
- `from src.prj_kernel_api.circuit_breaker import CircuitBreaker` → OK
- `from src.providers.token_counter import ...` → OK
- `from src.orchestrator.eval_harness import ...` → OK
**Tahmini:** 42 dosya kopyası + 2 dosya patch

---

## 9. Başarı Kriterleri

### 9.1 Fonksiyonel Kriterler

| # | Kriter | Doğrulama |
|---|---|---|
| F1 | `pip install ao-kernel` çalışır | `pip install -e ".[dev]"` |
| F2 | `ao-kernel version` versiyon döner | CLI çalıştır |
| F3 | `ao-kernel init` workspace oluşturur | `.ao/` dizini kontrol |
| F4 | `ao-kernel doctor` kontroller geçer | 7 OK + 1 WARN (opsiyonel deps kabul) |
| F5 | `ao-kernel migrate --dry-run` rapor üretir | JSON rapor kontrol |
| F6 | Library mode çalışır (workspace'siz) | `load_default()` testi |
| F7 | Legacy fallback uyarı verir | DeprecationWarning yakalama |
| F8 | src shim importları çalışır | 5 modül import testi |
| F9 | Extension manifest keşfedilebilir | 17 manifest erişim |

### 9.2 Non-Fonksiyonel Kriterler

| # | Kriter | Hedef | Doğrulama |
|---|---|---|---|
| NF1 | Wheel boyutu | < 3 MB | `ls -la dist/*.whl` |
| NF2 | Test sızıntısı | 0 test dosyası wheel'da | `zipinfo *.whl \| grep _test` |
| NF3 | Dosya başına satır | < 800 | Her dosya kontrol |
| NF4 | Zorunlu bağımlılık | Sadece jsonschema | `pip show ao-kernel` |
| NF5 | Python uyumluluk | >= 3.11 | doctor kontrolü |
| NF6 | Clean venv çalışma | wheel'dan kurulum OK | venv + pip install |

---

## 10. Test Planı

### 10.1 Doğrulama Kontrolleri (16 adet)

| # | Kontrol | Komut | Beklenen Sonuç |
|---|---|---|---|
| V1 | Editable install | `pip install -e ".[dev,llm]"` | Exit 0 |
| V2 | Import test | `python -c "import ao_kernel; print(ao_kernel.__version__)"` | `0.1.0` |
| V3 | Shim import + warning | `python -c "from src.shared.utils import load_json"` | OK + FutureWarning |
| V4 | CLI version | `ao-kernel version` | `ao-kernel 0.1.0` |
| V5 | CLI init | `ao-kernel init` | `.ao/` oluşur |
| V6 | CLI doctor | `ao-kernel doctor` | 7 OK + 1 WARN kabul |
| V7 | Wheel contents | `python -m build && zipinfo dist/*.whl \| grep -E '_test\|test_\|tests/'` | Boş çıktı |
| V8 | Recursive JSON | `zipinfo dist/*.whl \| grep work_intake_fragments` | Dosyalar var |
| V9 | Extension manifest | `python -c "from ao_kernel.config import load_default; load_default('extensions/PRJ-AIRUNNER', 'extension.manifest.v1.json')"` | JSON döner |
| V10 | Operations JSON | `python -c "from ao_kernel.config import load_default; load_default('operations', 'llm_class_registry.v1.json')"` | JSON döner |
| V11 | Workspace precedence | `--workspace-root` flag testi | Override çalışır |
| V12 | Legacy warning | `.cache/ws_customer_default` kullanımı | DeprecationWarning |
| V13 | Corrupted workspace | Bozuk workspace.json | WorkspaceCorruptedError |
| V14 | Init idempotency | İki kez `ao-kernel init` | İkisi de başarılı |
| V15 | Migrate dry-run | `ao-kernel migrate --dry-run` | JSON rapor |
| V16 | Clean venv wheel | `python -m venv /tmp/test && pip install dist/*.whl[llm] && ao-kernel init && ao-kernel doctor && python -c "from src.shared.utils import load_json; from src.prj_kernel_api.circuit_breaker import CircuitBreaker"` | OK |

### 10.2 Smoke Test Matrisi (src/ shim)

| Import | Modül | Beklenen |
|---|---|---|
| `from src.shared.utils import load_json, write_json_atomic, now_iso8601` | shared | OK |
| `from src.prj_kernel_api.circuit_breaker import CircuitBreaker` | LLM | OK |
| `from src.prj_kernel_api.llm_request_builder import ...` | LLM | OK |
| `from src.providers.token_counter import ...` | providers | OK |
| `from src.orchestrator.eval_harness import ...` | orchestrator | OK |
| `from src.roadmap.executor import ...` | roadmap | OK |

---

## 11. İstişare Geçmişi

| # | ID | Konu | Codex Verdict | Ana Karar |
|---|---|---|---|---|
| 1 | CNS-001 | Genel mimari | B | Governed runtime, library+workspace mode |
| 2 | CNS-002 | Scaffold review | B | jsonschema-only dep, test exclude |
| 3 | CNS-003 | Detay tartışma | C | Extension manifest, migration contract, __init__ warning |
| 4 | CNS-004 | Modül envanteri | C | Katman bazlı düşün, 39 dosya allowlist |
| 5 | CNS-005 | PR #76 drift | B | Main + uplift (artık tek faz) |
| 6 | CNS-20260413-001 | Final onay | B | __init__ patch, operations JSON, clean venv |

**Toplam itiraz:** Codex 6 turda toplam 23 itiraz verdi. 21'i kabul edildi, 2'si kısmen kabul edildi (secrets/ yükseltme ertelendi, utils/ kaldırma ertelendi).

### 11.1 Revizyon Traceability Matrisi

| Rev | Açıklama | Kaynak | Plan Bölümü | Etkilenen Dosyalar | Doğrulama ID |
|---|---|---|---|---|---|
| R1 | Governed runtime konumlandırması | CNS-001 | 2.3 | CLAUDE.md | — |
| R2 | Library + workspace dual mode | CNS-001 | 4.4, 6.3 | config.py | V11 |
| R3 | src.* → ao_kernel._legacy (Faz 2) | CNS-001 | 3.2 X5 | Ertelendi | — |
| R4 | Migration contract: dry-run/backup/rapor | CNS-002+003 | 4.6, 6.5 | migrate_cmd.py | V15 |
| R5 | Streaming Faz 1'e (ertelendi) | CNS-001 | 3.2 X1 | Ertelendi | — |
| R6 | Sadece jsonschema zorunlu dep | CNS-002 | 4.3, 6.1 | pyproject.toml | V1 |
| R7 | src deprecation warning + test exclude | CNS-002+003 | 4.10 | src/__init__.py, pyproject.toml | V3, V7 |
| R8 | defaults/extensions/ manifest-only | CNS-003 | 4.7, Task 3 | ao_kernel/defaults/extensions/ | V9 |
| R9 | Legacy fallback DeprecationWarning | CNS-002 | 4.5, 6.3 | config.py | V12 |
| R10 | Katman bazlı allowlist (42 dosya) | CNS-004+005 | 4.2, 5.2, Task 4 | 42 src/ dosyası | V3, smoke tests |
| R11 | prj_kernel_api/__init__.py patch | CNS-20260413-001 | 4.8 | src/prj_kernel_api/__init__.py | smoke test |
| R12 | docs/OPERATIONS LLM JSON'ları defaults'a | CNS-20260413-001 | 4.9, Task 3 | ao_kernel/defaults/operations/ | V10 |
| R13 | Built wheel clean venv testi | CNS-20260413-001 | 10.1 V16 | — | V16 |

---

## 12. Sözlük

| Terim | Tanım |
|---|---|
| Facade | `ao_kernel/` — yeni public API katmanı |
| Shim | `src/` — eski importlar için uyumluluk katmanı |
| Allowlist | Paketlenecek 42 dosyanın açık listesi |
| Bundled defaults | `ao_kernel/defaults/` — JSON policy/schema/registry |
| Governed runtime | Policy-driven, fail-closed, evidence-trail'li AI orchestrator |
| Library mode | Workspace olmadan `import ao_kernel` kullanımı |
| Workspace mode | `.ao/` dizini ile CLI + governance kullanımı |
| SSOT | Single Source of Truth |

---

## 13. Güvenlik Denetimi (CNS-20260413-002 sonrası)

### 13.1 Temiz Alanlar
- JSON dosyalarında API key, token, secret **YOK** — tümü env variable referansı
- Python kodunda hardcoded credential **YOK** — `dotenv_loader.py` güvenli pattern
- Extension manifestlerde URL/endpoint **YOK**
- docs/OPERATIONS LLM JSON'larında hassas veri **YOK**

### 13.2 DÜZELTME GEREKLİ (PyPI öncesi)

| # | Dosya | Sorun | Çözüm |
|---|---|---|---|
| S1 | `registry/apps_and_launch_registry.v1.json` | 8 satırda `/Users/halilkocoglu/Documents/...` mutlak yol | Placeholder'a çevir: `"__WORKSPACE_ROOT__"` |
| S2 | `registry/authority_matrix.v1.json` | 1 satırda mutlak yol self-referans | Göreli yola çevir |
| S3 | `policies/policy_harvest.v1.json` | `"Beykent"` forbidden token | Sanitize et veya generic yap |

### 13.3 GÜVENLİ — Ek Önlem Gerekmez
- `.github/CODEOWNERS` paketlenmiyor (sadece repo dosyası)
- `.env` dosyaları `.gitignore`'da
- Test dosyaları wheel'a girmiyor (V7 kontrolü)

---

## 14. Gelecek Notları

### 14.1 Modül Refactoring (v0.2.0 değerlendirmesi)

v0.1.0 scaffold sonrası, kullanım verisine göre değerlendirilecek:
- `ao_kernel.llm` — LLM control plane facade (prj_kernel_api wrap)
- `ao_kernel.policy` — Policy engine facade
- `ao_kernel.workspace` — Workspace management facade
- `ao_kernel.execution` — Orchestrator + roadmap execution facade
- İç modül sınırları kullanım pattern'larına göre netleşecek
- Codex CNS-001: "iç modül sınırları net tanımlanmalı ama tek paket v1 için doğru"

---

## 15. SHA Referansları

| Kaynak | SHA | Not |
|---|---|---|
| autonomous-orchestrator main | `314d396` | PR #74 + PR #76 merge dahil |
| ao-kernel main | `0500370` | Scaffold öncesi |
