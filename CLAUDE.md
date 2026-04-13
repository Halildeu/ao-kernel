# CLAUDE.md — ao-kernel

## Bu Proje Nedir

`ao-kernel` bir **governed AI orchestration runtime** paketidir. Genel amaçlı agent framework DEĞİLDİR — policy-driven, fail-closed, evidence-trail'li bir runtime. `pip install ao-kernel` ile herhangi bir Python projesine kurulur.

**Kaynak repo:** `Halildeu/autonomous-orchestrator` (main HEAD: `314d396`, PR #76 merge dahil). Bu repo o kaynak repo'daki seçili dosyaların katman bazlı allowlist ile dağıtılabilir Python paketi haline getirmektir.

**Güncel durum:** v2.1.1 PyPI'de yayında. ao_kernel/ facade (18 dosya) + ao_kernel/_internal/ (64 dosya) + ao_kernel/context/ (11 dosya) + bundled defaults (338 JSON). 567 test, %82.75 coverage.

## Mimari Kararlar (8 istişare sonucu — CNS-001..005, CNS-20260413-001/002)

Bu kararlar Claude + Codex arasında 8 turda istişare edilerek alındı. 13 revizyon (R1-R13) uygulandı. Değiştirmek için yeni istişare gerekir. Detaylı proje planı: `.ao/docs/PROJECT_PLAN.md`

### 1. Paket Yapısı: Facade + Shim (Big-bang rename DEĞİL)

```
ao_kernel/           ← PUBLIC FACADE (yeni, temiz API)
  __init__.py        ← version + public exports
  cli.py             ← ao-kernel CLI entrypoint
  config.py          ← workspace resolver + importlib.resources loader
  init_cmd.py        ← ao-kernel init
  migrate_cmd.py     ← ao-kernel migrate
  doctor_cmd.py      ← ao-kernel doctor

src/                 ← COMPAT SHIM (kaynak repo'dan kopyalanır, kademeli göç)
  shared/            ← SSOT utils (load_json, write_json_atomic, now_iso8601)
  orchestrator/      ← workflow engine, quality gate, decision quality
  providers/         ← LLM backends (claude, openai, google, deepseek, qwen, xai)
  prj_kernel_api/    ← LLM katmanı (request builder, transport, retry, circuit breaker)
  ops/               ← CLI commands (system-status, policy-check, etc.)
  session/           ← context/memory management
  evidence/          ← evidence writer
  tools/             ← tool gateway
  sdk/               ← public SDK (OrchestratorClient)
  extensions/        ← optional extensions (airunner, github-ops, planner)
```

**NEDEN facade+shim:** Kaynak repo'da 691 import satırı `src.*` kullanıyor. Big-bang rename çok riskli. Facade yeni public API sağlar, shim eski importları korur. v2.0.0'da shim kaldırılır.

**v0.1.0 shim:** 657 dosyanın tamamı değil, katman bazlı allowlist ile 42 dosya (CNS-004/005). `src/__init__.py` FutureWarning verir. `src/shared/resource_loader.py` bundled defaults'a köprü sağlar.

### 2. Dağıtım: PyPI (git URL değil)

```bash
pip install ao-kernel           # PyPI'den kur (sadece jsonschema dep)
pip install ao-kernel[llm]      # LLM modülleri (tenacity + tiktoken)
pip install ao-kernel[otel]     # opsiyonel OTEL desteği
pip install ao-kernel[pgvector] # opsiyonel pgvector memory
```

### 3. Workspace: `.ao/` dizini

```bash
ao-kernel init          # .ao/ workspace oluşturur
ao-kernel system-status # workspace'i kullanır
ao-kernel migrate       # versiyon yükseltme sonrası migration
ao-kernel doctor        # workspace sağlık kontrolü
```

**Workspace resolver sırası:** `--workspace-root` > `.ao/` > legacy `.cache/ws_customer_default`

### 4. Bundled Defaults: `importlib.resources`

Policy/schema/registry dosyaları `ao_kernel/defaults/` altında paketlenir. Workspace override varsa o kullanılır, yoksa paket defaults.

### 5. Versiyonlama: Semver

```
MAJOR: Breaking change (config format, CLI arg, Python API)
MINOR: Yeni feature (backward compat)
PATCH: Bug fix
```

### 6. Extension: Manifest discovery (entry_points DEĞİL)

İlk fazda `entry_points` plugin sistemi yok. Extensions `ao_kernel/defaults/extensions/` altında manifest ile keşfedilir.

## Kaynak Repo'dan Transfer Edilecek Kod

Kaynak: `/Users/halilkocoglu/Documents/autonomous-orchestrator/`

### Zaten Implement Edilen (PR #76, 530 test)

| Modül | Kaynak Dosya | Açıklama |
|---|---|---|
| llm_request_builder | src/prj_kernel_api/llm_request_builder.py | Provider-native request body+headers |
| llm_transport | src/prj_kernel_api/llm_transport.py | HTTP execution + retry + circuit breaker |
| llm_response_normalizer | src/prj_kernel_api/llm_response_normalizer.py | Text + usage + tool_calls extraction |
| llm_post_processors | src/prj_kernel_api/llm_post_processors.py | Evidence write, output save, payload |
| response_parser | src/providers/response_parser.py | DRY JSON extraction + schema validation |
| structured_output | src/providers/structured_output.py | Provider-native response_format |
| llm_retry | src/prj_kernel_api/llm_retry.py | Tenacity exponential backoff |
| circuit_breaker | src/prj_kernel_api/circuit_breaker.py | Per-provider CLOSED→OPEN→HALF_OPEN |
| rate_limiter | src/prj_kernel_api/rate_limiter.py | Token bucket rate limiting |
| tool_calling | src/prj_kernel_api/tool_calling.py | Claude/OpenAI tool format + extraction |
| tool_gateway | src/prj_kernel_api/tool_gateway.py | Typed allowlist, cycle detection, fail-closed |
| capability_model | src/providers/capability_model.py | Provider capability SSOT + negotiation |
| token_counter | src/providers/token_counter.py | tiktoken + heuristic + budget tracking |
| eval_harness | src/orchestrator/eval_harness.py | 6 deterministic heuristic-based eval checks + scorecard |
| prompt_registry | src/prj_kernel_api/prompt_registry.py | Experiment governance (A/B/canary/shadow) |

### Runtime Akışı (llm_call_live)

```
PRE-FLIGHT:
  1. check_capabilities_before_request()  → capability gap log
  2. count_tokens()                       → pre-flight token estimate
  3. rate_limiter.acquire()               → rate limit enforcement

EXECUTION:
  4. build_live_request()                 → provider-native body+headers
  5. execute_http_request_with_resilience() → retry+circuit breaker

POST-FLIGHT:
  6. process_live_response()              → evidence+payload
  7. run_eval_suite() + eval_scorecard()  → output quality check
  8. extract_usage()                      → actual token usage
  9. record_decision_quality()            → telemetry (JSONL)
  10. record_prompt_lineage()             → prompt×model×run tracking
```

## Rakip Karşılaştırma

| | ao-kernel | LangGraph | CrewAI | Pydantic AI |
|---|---|---|---|---|
| Policy engine | ✅ 60+ policy | ❌ | ❌ | ❌ |
| Fail-closed | ✅ | ❌ | ❌ | ❌ |
| Evidence trail | ✅ self-hosted JSONL | ⚠️ LangSmith SaaS | ❌ | ❌ |
| Migration CLI | ✅ | ❌ | ❌ | ❌ |
| Doctor | ✅ | ❌ | ❌ | ❌ |
| Deterministic stubs | ✅ offline | ❌ | ❌ | ❌ |
| Prompt experiments | ✅ A/B/canary/shadow | ⚠️ LangSmith Hub SaaS | ❌ | ❌ |
| Streaming | ❌ Faz 2 | ✅ | ✅ | ✅ |
| PyPI downloads | Yeni | 47M/ay | 5.2M/ay | — |

## AI Trend Gap'leri (2026)

- **MCP server desteği:** ao-kernel MCP server olarak çalışabilir olmalı
- **Streaming:** Faz 1'e çekilmeli (2026'da varsayılan)
- **OTEL export:** Varsayılan yapılmalı

## Teknik Kurallar

- Python >= 3.11
- Dependencies: jsonschema, tenacity, tiktoken (3 paket, minimal)
- Dosya bütçesi: < 800 satır per file
- Fail-closed: policy violation → block (default)
- Evidence: her side-effect JSONL append-only log
- Secrets: ASLA log'a yazılmaz
- Atomic writes: write_json_atomic (tmp + fsync + rename)
- Type hints zorunlu (public functions)

## Geliştirme Akışı

```bash
# Geliştirme
pip install -e ".[dev]"
pytest tests/ -x

# Test
ao-kernel doctor
ao-kernel system-status

# Release (trusted publishing — tag push tetikler)
git tag v2.x.y
git push origin v2.x.y
# GitHub Actions .github/workflows/publish.yml otomatik PyPI upload yapar
```

## Codex İstişare Altyapısı

Bu repo'da Codex (GPT-5.4) ile istişare yapılabilir. Önemli mimari kararlarda istişare ZORUNLU.

### İstişare Nasıl Yapılır

```bash
# 1. İstişare dosyası oluştur
# .ao/consultations/requests/CNS-YYYYMMDD-NNN.request.v1.json

# 2. Codex'i çağır
codex exec -C . -o .ao/consultations/responses/CNS-YYYYMMDD-NNN.codex.response.v1.json \
  "Bu bir istişare talebidir (CNS-...). <dosya path> oku. <sorular>"

# 3. Yanıtı oku ve değerlendir
```

### İstişare Formatı

Request:
```json
{
  "version": "v1",
  "consultation_id": "CNS-YYYYMMDD-NNN",
  "status": "OPEN",
  "from_agent": "claude",
  "to_agent": "codex",
  "topic": "architecture|planning|review|decision",
  "question": {
    "title": "Kısa başlık",
    "body": "Detaylı soru",
    "context_refs": ["dosya/yolları"],
    "options": [{"option_id": "A", "title": "...", "pros": "...", "cons": "..."}]
  },
  "created_at": "ISO-8601",
  "branch": "main",
  "head_sha": "abc1234"
}
```

Response:
```json
{
  "agent": "codex",
  "responded_at": "ISO-8601",
  "verdict": "A|B|C",
  "body": "Detaylı yanıt",
  "agreements": ["Doğru bulunan noktalar"],
  "objections": ["İtirazlar"],
  "additions": ["Yeni öneriler"]
}
```

### İstişare Dizinleri

```
.ao/consultations/
  requests/    ← istişare talepleri
  responses/   ← Codex yanıtları
```

### İstişare Geçmişi (autonomous-orchestrator'dan)

| ID | Konu | Verdict | Sonuç |
|---|---|---|---|
| CNS-001 | Framework karşılaştırma | D (hibrit DIY) | LLM capabilities kendin yap |
| CNS-002 | LLM plan review | B (orta revizyon) | PR0 eklendi, tool calling fail-closed |
| CNS-003 | Paketleme planı | C (major revizyon) | Facade+shim, PyPI, dual resolver |
| CNS-004 | Derin değerlendirme | Timeout | Tamamlanamadı |

### İstişare Kuralları

- Mimari karar gerektiren konularda istişare AÇ
- Codex'in itirazlarını ciddiye al — her birini kanıtla kabul/ret
- İstişare sonucunu memory'ye kaydet
- Mevcut kararları (project_decisions.md) istişare olmadan değiştirme

## Language

- **Kullanıcıya DAIMA Türkçe yanıt ver** — bu kural istisnasızdır
- Kod, değişken adları, commit mesajları: İngilizce
- Kod yorumları (comments): İngilizce
- Dokümanlar, planlar, raporlar: Türkçe
- Codex istişare soruları: Türkçe (Codex Türkçe anlıyor ve yanıt veriyor)
- CLAUDE.md, README: Türkçe
