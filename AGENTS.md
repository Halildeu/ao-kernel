# AGENTS.md — ao-kernel

## 1. Bu Proje Nedir

`ao-kernel` bir **governed AI orchestration runtime** paketidir. Genel amaçlı agent framework DEĞİLDİR — policy-driven, fail-closed, evidence-trail'li bir runtime. `pip install ao-kernel` ile herhangi bir Python projesine kurulur.

**Kaynak repo:** `Halildeu/autonomous-orchestrator` — bu repo o kodun dağıtılabilir PyPI paketi halidir.

**Rakip farkı:** LangGraph, CrewAI ve Pydantic AI'dan farklı olarak ao-kernel built-in policy engine (4 tip, fail-closed), self-hosted JSONL evidence trail ve governed context pipeline sunar. Bu üç özellik rakiplerin hiçbirinde yoktur.

## 2. Değişmezler

Bu ilkeler versiyon fark etmez, her zaman geçerlidir:

1. **Fail-closed:** Policy violation → block. Corrupt session → `SessionCorruptedError`. Policy load error → deny. Ama session resume graceful fallback yapar (yeni session açar).
2. **Evidence:** İki form. MCP events → JSONL append-only log (fsync'li, günlük rotasyon, manifest yok). Workspace artefaktları (canonical_decisions, checkpoint, evidence run_dir) → JSONL + SHA256 integrity manifest. Her iki formda da write failure fail-open side-channel'dir; ana akışı bloklamaz.
3. **Secrets:** ASLA log'a yazılmaz, ASLA MCP parametresi olarak geçilmez, sadece env-var resolution.
4. **Atomic writes:** tmp + fsync + rename — yarım yazılmış dosya oluşmaz.
5. **Sync SDK yüzey:** `AoKernelClient` sync API. Chunk-level streaming: `llm.stream_request()` kullan.
6. **Policy SSOT:** `governance.py` tüm policy check'lerin tek kaynağıdır.
7. **Global state yok:** `workspace_root` her çağrıda explicit geçilir.

## 3. Çalışma Modları

ao-kernel iki modda çalışır:

**Library mode** — `.ao/` dizini yok, `workspace_root()` → `None`. In-memory çalışır: persistence, evidence, checkpoint, canonical store devre dışı. Test ve one-off çağrılar için uygundur.

**Workspace mode** — `ao-kernel init` → `.ao/` dizini oluşturur. Tam pipeline aktif: session persistence, evidence trail, checkpoint/resume, canonical decision store, workspace facts.

**Resolution:** `config.workspace_root()` CWD'den yukarı `.ao/` arar. `AoKernelClient(workspace_root=".")` proje kökünü alır, içinde `.ao/` bulur. Detaylar: `config.py`, `workspace.py`.

## 4. Kullanım Yüzeyleri

### AoKernelClient — Unified SDK

Tam governed pipeline: route → capability check → context inject → build → execute → normalize → extract decisions → eval scorecard → telemetry. Context manager destekler.

```python
from ao_kernel import AoKernelClient

with AoKernelClient(workspace_root=".") as client:
    result = client.llm_call(
        messages=[{"role": "user", "content": "Hello"}],
        intent="FAST_TEXT",
    )
```

Tüm public metotlar ve imzaları için: `client.py`

### MCP Server — Governance Tools

Thin executor pipeline: route → build → execute → normalize. Context injection, eval, quality gate ve telemetry **YOKTUR** — SDK'dan daha hafif bir yüzeydir.

7 governance tool (`ao_policy_check`, `ao_llm_route`, `ao_llm_call`, `ao_quality_gate`, `ao_workspace_status`, `ao_memory_read`, `ao_memory_write`) + 3 resource (`ao://policies/{name}`, `ao://schemas/{name}`, `ao://registry/{name}`). Transport: stdio (varsayılan) + HTTP (`pip install ao-kernel[mcp-http]`).

Tool spec'leri ve inputSchema'lar için: `mcp_server.py`

### CLI

```bash
ao-kernel init             # .ao/ workspace oluştur
ao-kernel doctor           # sağlık kontrolü
ao-kernel migrate          # workspace migration (--dry-run, --backup)
ao-kernel mcp serve        # MCP server (stdio)
ao-kernel mcp serve --transport http --port 8080
ao-kernel version          # versiyon
ao-kernel system-status    # workspace durumu
```

## 5. Mimari Genel Bakış

```
ao_kernel/                ← PUBLIC FACADE
  client.py               ← AoKernelClient — unified SDK
  llm.py                  ← LLM facade (route, build, execute, normalize, stream, count_tokens)
  governance.py            ← Policy SSOT (check_policy, evaluate_quality)
  config.py                ← Workspace resolver + defaults loader
  session.py, policy.py, workspace.py, roadmap.py  ← Domain facades
  tool_gateway.py          ← Policy-gated tool dispatch (ToolSpec, ToolGateway, ToolCallResult)
  mcp_server.py            ← MCP server (7 tool + 3 resource)
  _internal/mcp/           ← Private MCP helper modules (memory_tools, ...)
  telemetry.py             ← OTEL adapter (lazy, no-op fallback)
  errors.py                ← Typed exceptions (SessionCorruptedError, WorkspaceNotFoundError, ...)
  cli.py, i18n.py          ← CLI + localization

  context/                 ← CONTEXT PIPELINE — governed memory loop
    memory_pipeline.py     ← process_turn() orchestration
    context_compiler.py    ← 3-lane compilation (session/canonical/facts)
    profile_router.py      ← 6 profil (STARTUP, TASK_EXECUTION, REVIEW, EMERGENCY, ASSESSMENT, PLANNING)
    memory_tiers.py        ← HOT/WARM/COLD tier enforcement
    self_edit_memory.py    ← Agent-controlled memory (remember/update/forget/recall, 4 importance level)
    semantic_retrieval.py  ← Pure-Python embedding + cosine similarity
    agent_coordination.py  ← Multi-agent SDK hooks (revision tracking, stale detection)
    checkpoint.py          ← Durable checkpoint/resume
    canonical_store.py, decision_extractor.py, context_injector.py, session_lifecycle.py

  _internal/               ← PRIVATE IMPLEMENTATION (import etme)
    prj_kernel_api/        ← LLM transport, router, streaming, tool calling, circuit breaker, rate limiter
    orchestrator/          ← quality_gate (4 gate), eval_harness (6 check)
    session/               ← compaction (sliding window), distillation (cross-session fact promotion)
    evidence/              ← JSONL writer + SHA256 integrity verification
    roadmap/               ← Workflow execution engine
    providers/             ← Capability model, token counter
    secrets/               ← Env provider, vault stub
    shared/, utils/        ← Logger, resource loader, JSON I/O

  defaults/                ← Bundled JSON resources (policies, schemas, registry, extensions, operations)
```

> Güncel sayılar: `pytest --co -q | tail -1` (test), `find ao_kernel/defaults -name "*.json" | wc -l` (bundled JSON), `ls tests/test_*.py | wc -l` (test dosyası)

## 6. Runtime Akışı

### AoKernelClient.llm_call (tam governed pipeline)

```
1. resolve_route()                → provider/model seçimi
2. check_capabilities()           → capability gap kontrolü
3. compile_context + inject       → 3-lane context → messages'a enjekte
4. build_request()                → Provider-native HTTP request body
5. execute_request()              → HTTP + retry (tenacity) + circuit breaker
6. normalize_response()           → text + usage + tool_calls extraction
7. process_turn()                 → Decision extraction + compact + save
8. eval_harness                   → 6 diagnostic check + scorecard (non-blocking)
9. telemetry                      → OTEL spans + metrics
```

### MCP ao_llm_call (thin executor)

```
1. resolve_route()      → provider/model
2. build_request()      → HTTP request body
3. execute_request()    → HTTP transport
4. normalize_response() → text + usage
```

> **ÖNEMLİ:** MCP path'inde context injection, eval harness, quality gate ve telemetry **YOKTUR**. Tam governed pipeline için `AoKernelClient` kullanın.

## 7. Governance — Policy Engine

`governance.py` tüm policy check'lerin SSOT'udur. `_check_rules()` 4 policy tipini otomatik algılar:

| Policy Tipi | Algılama | Kontrol |
|---|---|---|
| **Autonomy** | `intents` + `defaults.mode` var | Intent authorization + mode enforcement |
| **Tool calling** | `allowed_tools` veya `blocked_tools` var | Tool allowlist/blocklist + enabled check |
| **Provider guardrails** | `providers` dict var | Provider/model access control |
| **Generic** | `required_fields` / `blocked_values` / `limits` | Alan doğrulama |

**Fail-closed scope:** Governance ve policy path'lerinde strict deny (missing policy → deny, load error → deny, unknown action → deny). Session resume ve telemetry gibi opsiyonel subsystem'lerde graceful fallback (yeni session aç, metriği atla).

**MCP response envelope** (tüm tool'lar):
```json
{
  "api_version": "0.1.0",
  "tool": "<tool_name>",
  "allowed": true|false,
  "decision": "allow|deny|executed|error",
  "reason_codes": ["..."],
  "data": {...},
  "error": null
}
```
- `allow` — policy check geçti
- `deny` — policy check reddetti veya kaynak bulunamadı
- `executed` — action başarıyla tamamlandı (ao_llm_call)
- `error` — execution denendi ama başarısız (transport error, exception)

## 8. Validation Sistemi

ao-kernel'de iki **ayrı** validation sistemi vardır. Bunlar farklı amaçlara hizmet eder:

### Quality Gates (policy-enforced, fail-closed)

Policy pipeline'ında allow/deny kararı verir. Konfigürasyon: `policy_quality_gates.v1.json`.

- `output_not_empty` → on_fail: **reject** (min_output_chars: 10)
- `schema_valid` → on_fail: **retry**
- `consistency_check` → on_fail: **warn** (son kararlarla çelişki)
- `regression_check` → on_fail: **escalate** (eski değerlere gerileme)

MCP tool: `ao_quality_gate`. Detaylar: `_internal/orchestrator/quality_gate.py`

### Eval Checks (heuristic scoring, fail-open)

Client'ta diagnostic scorecard olarak eklenir. **Execution ASLA bloklanmaz.**

- `json_conformance` — JSON parse + opsiyonel schema validation
- `groundedness` — Context ile word overlap (≥%30) veya embedding cosine similarity (≥0.5)
- `citation_completeness` — Beklenen referansların substring match'i (≥%80)
- `tool_consistency` — Tool output değerlerinin response'ta yansıması (≥%50)
- `refusal_correctness` — Keyword-based refusal detection
- `truncation_safety` — Brace count + sentence termination heuristics

Her check 0.0-1.0 skor döner. İlgili input yoksa check vacuous True döner. Detaylar: `_internal/orchestrator/eval_harness.py`

> **ÖNEMLİ:** Quality gates ≠ eval checks. Gate'ler policy enforcement yapar (allow/deny), eval check'ler diagnostic scoring yapar (0-1 skor). İkisini **ASLA** karıştırma.

## 9. Context Pipeline

### Memory Loop

```
LLM Request:
  compile_context(session_ctx, canonical, facts, messages)
    → inject_context_into_messages(messages, compiled.preamble)
      → build_request()

LLM Response:
  process_turn(llm_output, session_ctx)
    → extract decisions → upsert → compact → save

Tool Result:
  extract_from_tool_result(tool_name, result)
    → promote to canonical (confidence >= 0.8)

Session End:
  compact → distill → promote_from_ephemeral (confidence >= 0.7) → save
```

### 3-Lane Compilation

- **Session decisions** (ephemeral) — session context dict içinde yaşar
- **Canonical decisions** (promoted) — `.ao/canonical_decisions.v1.json`'a yazılır
- **Workspace facts** (distilled) — cross-session fact promotion

### 6 Context Profil

Her profil farklı `max_decisions`, `max_tokens` ve `priority_prefixes` tanımlar:

`STARTUP`, `TASK_EXECUTION` (default), `REVIEW`, `EMERGENCY`, `ASSESSMENT`, `PLANNING`

Profil detayları ve keyword detection kuralları: `context/profile_router.py`

### Memory Tiers

- **HOT:** confidence ≥ 0.7 AND age < 7 gün → her zaman yükle (max 30)
- **WARM:** confidence ≥ 0.4 OR age < 30 gün → match'te yükle (max 50)
- **COLD:** geri kalan → on-demand (max 100, 30 session sonra arşiv)

Detaylar: `context/memory_tiers.py`

### Self-Editing Memory

Agent-controlled memory (Letta/MemGPT ilhamı): `remember/update/forget/recall`. 4 importance seviyesi:

- **critical:** 365 gün fresh, asla auto-expire
- **high:** 90 gün fresh, 365 gün expire
- **normal:** 30 gün fresh, 365 gün expire
- **low:** 7 gün fresh, 90 gün expire

Detaylar: `context/self_edit_memory.py`

### Semantic Retrieval

Pure-Python cosine similarity (numpy YOK). Provider embedding API (varsayılan: OpenAI text-embedding-3-small). Embedding cache ile tekrar embed'i önler. Detaylar: `context/semantic_retrieval.py`

### Multi-Agent Coordination

Canonical store üzerinde revision tracking + stale detection. SDK hooks: `get_revision`, `check_stale`, `read_with_revision`, `record_decision`, `compile_context_sdk`, `finalize_session_sdk`, `query_memory`. Detaylar: `context/agent_coordination.py`

## 10. Streaming & Resilience

**Desteklenen provider'lar:** Codex, OpenAI, Google Gemini, DeepSeek, Qwen, xAI

**3 wire format:** Anthropic Messages API, OpenAI Chat Completions, Google Gemini (DeepSeek/Qwen/xAI → OpenAI-compatible)

**StreamResult durumları:** `OK` (tam), `PARTIAL` (mid-stream fail, veri döner, retry YOK), `FAIL` (kullanılabilir veri yok)

**Circuit breaker:** Per-provider izolasyon (CLOSED → OPEN → HALF_OPEN → CLOSED). `get_circuit_breaker(provider_id)` ile erişim.

**Rate limiter:** Per-provider token bucket. `get_rate_limiter(provider_id)` ile erişim.

**Retry:** Tenacity-based, sadece streaming öncesi. Mid-stream hata → PARTIAL döner, retry yapılmaz. `on_chunk` callback expose EDİLMEZ (D10).

Detaylar: `llm.py`, `_internal/prj_kernel_api/llm_stream.py`, `_internal/prj_kernel_api/llm_stream_transport.py`

## 11. Telemetry

OTEL optional: `pip install ao-kernel[otel]`. Lazy import + no-op fallback (D12). Kurulu değilse tüm metric/span çağrıları sessizce no-op.

- **Span API:** `span(name, attributes)` context manager
- **Metrikler:** 8 record fonksiyonu (LLM duration, token usage, policy check, MCP tool call, stream first token, context compile, decision extraction, canonical promote)
- **Non-OTEL:** JSONL evidence trail workspace mode'da her zaman aktif, OTEL'den bağımsız

Detaylar: `telemetry.py`

## 12. Teknik Kurallar

- Python >= 3.11 (test: 3.11, 3.12, 3.13)
- Core dependency: `jsonschema>=4.23.0` (TEK zorunlu dep)
- Dosya bütçesi: < 800 satır per file
- Type hints zorunlu (public functions)
- Coverage gate: %70 minimum branch coverage (`ao_kernel/_internal` hariç — D13)
- Lint: ruff (line-length 120, py311)
- Type check: mypy (strict)
- Mutation test: mutmut
- Test quality gate (AST-based, `conftest.py`):
  - BLK-001: `assert callable(x)` → **bloklanır** (tautological)
  - BLK-002: `assert True` → **bloklanır**; `assert x is not None` tek assertion → **advisory** (uyarı)
  - BLK-003: `except: pass` test içinde → **bloklanır**

## 13. Geliştirme Akışı

```bash
pip install -e ".[dev,llm,mcp]"     # Geliştirme ortamı
pytest tests/ -x                     # Test
ruff check ao_kernel/ tests/         # Lint
mypy ao_kernel/ --ignore-missing-imports  # Type check
```

**Extras:**

| Extra | İçerik |
|-------|--------|
| `core` | jsonschema (tek zorunlu) |
| `[llm]` | tenacity, tiktoken |
| `[mcp]` | mcp (stdio) |
| `[mcp-http]` | mcp + starlette + uvicorn |
| `[otel]` | opentelemetry-api, -sdk, -exporter-otlp |
| `[pgvector]` | pgvector, psycopg2-binary (henüz backend yok) |

**Release:** `git tag v2.x.y && git push origin v2.x.y` → GitHub Actions → PyPI trusted publishing

## 14. Mimari Kararlar

Bu kararlar Codex + Codex arasında 25+ turda istişare edilerek alındı. Değiştirmek için yeni istişare gerekir.

| # | Karar | Gerekçe |
|---|---|---|
| D1 | **Facade + _internal** | Public facade + private implementation namespace ayrımı |
| D2 | **PyPI dağıtım** | `pip install ao-kernel`, git URL değil |
| D3 | **Monolith + extras** | Tek paket, opsiyonel dependency'ler extras ile |
| D4 | **importlib.resources** | Bundled defaults wheel-safe, path-based okuma kırılmaz |
| D5 | **Workspace resolver** | `config.workspace_root()` → CWD'den yukarı `.ao/` arar; iç router'da legacy path fallback var |
| D6 | **Policy-first** | governance.py SSOT — 4 policy tipi |
| D7 | **Manifest discovery** | entry_points plugin sistemi yok, extensions manifest ile keşfedilir |
| D8 | **Fail-closed** | Governance strict deny, opsiyonel subsystem'ler graceful fallback |
| D9 | **Sync SDK + low-level async** | AoKernelClient sync, stream_request() chunk-level |
| D10 | **on_chunk callback expose EDİLMEZ** | Sync aggregate API, chunk isteyenler `llm.stream_request()` |
| D11 | **API key MCP'de parametre DEĞİL** | Env var'dan çözülür — güvenlik sınırı |
| D12 | **OTEL optional** | `[otel]` extra, lazy import + no-op fallback |
| D13 | **_internal coverage aşamalı** | Public facade önce, internal modüller aşamalı |
| D14 | **Auto-route normalize** | Router `selected_provider` → client `provider_id` dönüşümü |

## 15. Codex İstişare Altyapısı

Bu repo'da Codex ile istişare yapılabilir. Önemli mimari kararlarda istişare ZORUNLU.

```bash
# İstişare dosyası oluştur → .ao/consultations/requests/CNS-YYYYMMDD-NNN.request.v1.json
# Codex'i çağır
codex exec -C . -o .ao/consultations/responses/CNS-YYYYMMDD-NNN.codex.response.v1.json \
  "Bu bir istişare talebidir (CNS-...). <dosya path> oku. <sorular>"
# Yanıtı oku ve değerlendir
```

**JSON request formatı:** `version`, `consultation_id`, `status`, `from_agent`, `to_agent`, `topic`, `question` (title, body, context_refs, options), `created_at`, `branch`, `head_sha`

**Kurallar:**
1. Mimari karar gerektiren konularda istişare AÇ
2. Codex'in itirazlarını ciddiye al — her birini kanıtla kabul/ret
3. İstişare sonucunu memory'ye kaydet
4. Mevcut kararları istişare olmadan değiştirme
5. İstişare geçmişi: `.ao/consultations/` (requests + responses)

## 16. Language

- **Kullanıcıya DAIMA Türkçe yanıt ver** — bu kural istisnasızdır
- Kod, değişken adları, commit mesajları: İngilizce
- Kod yorumları (comments): İngilizce
- Dokümanlar, planlar, raporlar: Türkçe
- Codex istişare soruları: Türkçe
- AGENTS.md, README: Türkçe
