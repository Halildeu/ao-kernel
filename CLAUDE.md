# CLAUDE.md — ao-kernel

## Bu Proje Nedir

`ao-kernel` bir **governed AI orchestration runtime** paketidir. Genel amaçlı agent framework DEĞİLDİR — policy-driven, fail-closed, evidence-trail'li bir runtime. `pip install ao-kernel` ile herhangi bir Python projesine kurulur.

**Kaynak repo:** `Halildeu/autonomous-orchestrator`. Bu repo o kaynak repo'daki kodun dağıtılabilir Python paketi haline getirilmiş halidir.

**Güncel durum:** v2.1.1 PyPI'de yayında. 18 facade + 13 context + 11 internal paket, 338 bundled JSON default. 567+ test, %82.75 coverage.

## Mimari

### Paket Yapısı (v2.0.0+ — src/ shim kaldırıldı)

```
ao_kernel/              ← PUBLIC FACADE (18 modül)
  __init__.py           ← version="2.1.x" + exports: AoKernelClient, workspace_root, load_default, load_with_override
  client.py             ← AoKernelClient — unified high-level SDK (llm_call, session, tool dispatch, memory, checkpoint)
  cli.py                ← ao-kernel CLI: init, migrate, doctor, version, mcp serve
  config.py             ← workspace resolver + importlib.resources defaults loader
  governance.py         ← POLICY SSOT — check_policy (4 policy tipi), evaluate_quality (6 gate), quality_summary
  llm.py                ← LLM facade — resolve_route, build_request, execute_request, normalize_response, streaming
  mcp_server.py         ← MCP server — 5 tool + 3 resource, stdio + HTTP transport
  tool_gateway.py       ← policy-gated MCP dispatch — ToolGateway, ToolCallPolicy (fail-closed)
  session.py            ← session facade — new_context, save_context, load_context, distill_memory
  telemetry.py          ← OpenTelemetry adapter (lazy import, no-op fallback)
  errors.py             ← SessionCorruptedError, WorkspaceNotFoundError, WorkspaceCorruptedError, DefaultsNotFoundError
  i18n.py               ← CLI mesaj lokalizasyonu (en, tr)
  policy.py             ← policy management facade
  workspace.py          ← workspace management facade
  roadmap.py            ← roadmap execution facade
  init_cmd.py           ← ao-kernel init
  migrate_cmd.py        ← ao-kernel migrate (--dry-run, --backup)
  doctor_cmd.py         ← ao-kernel doctor (8 check)

ao_kernel/context/      ← CONTEXT PIPELINE — governed memory loop (13 modül)
  memory_pipeline.py    ← process_turn() — automatic decision extraction + compaction
  context_compiler.py   ← 3-lane compilation (hot/warm/cold), relevance scoring, token budget
  context_injector.py   ← inject compiled context preamble into LLM messages
  decision_extractor.py ← extract decisions from LLM output + tool results
  canonical_store.py    ← multi-agent promoted decision store (.ao/canonical_decisions.v1.json)
  session_lifecycle.py  ← start_session (fail-closed) / end_session (compact + distill + promote)
  profile_router.py     ← task-type detection: STARTUP, TASK_EXECUTION, REVIEW
  memory_tiers.py       ← hot/warm/cold tier enforcement with TTL
  agent_coordination.py ← multi-agent memory coordination (record_decision, query_memory, finalize_session)
  checkpoint.py         ← durable checkpoint/resume — session context as checkpoint
  self_edit_memory.py   ← self-editing memory (Letta/MemGPT inspired agent-controlled memory)
  semantic_retrieval.py ← semantic vector retrieval — provider embedding + cosine similarity

ao_kernel/_internal/    ← PRIVATE IMPLEMENTATION (public API'den import etme, 11 paket)
  prj_kernel_api/       ← LLM transport, retry (tenacity), circuit breaker, rate limiter, streaming
  providers/            ← capability_model, response_parser, structured_output, token_counter
  orchestrator/         ← eval_harness (6 deterministic check + scorecard), quality_gate
  roadmap/              ← workflow execution engine (exec_steps, step_templates)
  session/              ← context_store, compaction_engine, memory_distiller
  evidence/             ← JSONL append-only evidence trail writer
  secrets/              ← secret management
  shared/               ← shared utilities (logging, resource loading)
  utils/                ← budget tracking, JSON I/O

ao_kernel/defaults/     ← BUNDLED RESOURCES (338 JSON)
  policies/             ← 96 governance policies (autonomy, tool_calling, security, guardrails, ...)
  schemas/              ← 213 JSON Schema definitions
  registry/             ← 8 provider/model registry (llm_class_registry, llm_provider_map, ...)
  extensions/           ← 18 extension manifests (PRJ-AIRUNNER, PRJ-KERNEL-API, PRJ-PLANNER, ...)
  operations/           ← 3 operational definitions
```

### Mimari Kararlar (Codex istişare sonucu)

Bu kararlar Claude + Codex arasında 8+ turda istişare edilerek alındı. Değiştirmek için yeni istişare gerekir.

| # | Karar | Gerekçe |
|---|---|---|
| D1 | **Facade + _internal** | v2.0.0'da src/ shim kaldırıldı → `ao_kernel._internal` namespace |
| D2 | **PyPI dağıtım** | `pip install ao-kernel`, git URL değil |
| D3 | **Monolith + extras** | Tek paket, opsiyonel dependency'ler extras ile |
| D4 | **importlib.resources** | Bundled defaults wheel-safe, path-based okuma kırılmaz |
| D5 | **Dual workspace resolver** | `--workspace-root` > `.ao/` > legacy `.cache/ws_customer_default` |
| D6 | **Policy-first** | governance.py SSOT — 4 policy tipi: autonomy, tool_calling, provider_guardrails, generic |
| D7 | **Manifest discovery** | entry_points plugin sistemi yok (henüz), extensions manifest ile keşfedilir |
| D8 | **Fail-closed** | Policy violation → block, corrupt session → SessionCorruptedError raise |

### MCP Server

**5 Governance Tool:**

| Tool | Açıklama |
|------|----------|
| `ao_policy_check` | Action'ı policy'ye karşı doğrula (4 policy tipi desteği) |
| `ao_llm_route` | Intent için provider/model çöz (deterministic, LLM çağrısı yok) |
| `ao_llm_call` | Governed LLM çağrısı — tam pipeline (route→build→execute→normalize→evaluate) |
| `ao_quality_gate` | LLM output kalitesini kontrol et (fail-closed, consistency/regression checks) |
| `ao_workspace_status` | Workspace sağlık durumu ve konfigürasyonu |

**3 Resource:** `ao://policies/{name}`, `ao://schemas/{name}`, `ao://registry/{name}`

**Transport:** stdio (varsayılan) + HTTP (`pip install ao-kernel[mcp-http]`)

**Response envelope (tüm tool'lar):**
```json
{
  "api_version": "0.1.0",
  "tool": "<tool_name>",
  "timestamp": "ISO8601Z",
  "allowed": true|false,
  "decision": "allow|deny",
  "reason_codes": ["..."],
  "policy_ref": "...",
  "data": {...},
  "error": null
}
```

### AoKernelClient — Unified SDK

```python
from ao_kernel import AoKernelClient

with AoKernelClient(workspace_root=".") as client:
    client.start_session()
    result = client.llm_call(
        messages=[{"role": "user", "content": "Hello"}],
        intent="FAST_TEXT",
    )
    client.end_session()
```

**Public metotlar:** `llm_call()`, `start_session()`, `end_session()`, `register_tool()`, `call_tool()`, `save_checkpoint()`, `resume_checkpoint()`, `remember()`, `forget()`, `recall()`, `check_policy()`, `doctor()`

### Context Pipeline (Governed Memory Loop)

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

**Naming convention:**
- `ephemeral_decisions` = session-scoped, geçici kararlar (session context dict içinde yaşar)
- canonical store `decisions` = promoted, kalıcı kararlar (workspace'e `.ao/canonical_decisions.v1.json` olarak yazılır)
- İki farklı katman — kasıtlı ayrım

**3 profil:** `STARTUP` (session başlangıcı), `TASK_EXECUTION` (görev sırası), `REVIEW` (inceleme)

### Runtime Akışı (AoKernelClient.llm_call)

```
PRE-FLIGHT:
  1. resolve_route()              → provider/model seçimi
  2. check_capabilities()         → capability gap kontrolü
  3. build_request_with_context() → compile_context + inject + request body

EXECUTION:
  4. execute_request()            → HTTP + retry (tenacity) + circuit breaker

POST-FLIGHT:
  5. normalize_response()         → text + usage + tool_calls extraction
  6. process_response_with_context() → process_turn + extract_from_tool_result
  7. eval_harness                 → 6 deterministic check + scorecard
  8. telemetry                    → OTEL spans + JSONL evidence
```

### Governance — Policy Engine

`governance.py` SSOT (Single Source of Truth). `_check_rules()` 4 policy tipini otomatik algılar:

| Policy Tipi | Algılama | Kontrol |
|---|---|---|
| **Autonomy** | `intents` + `defaults.mode` var | Intent authorization + mode enforcement |
| **Tool calling** | `allowed_tools` veya `blocked_tools` var | Tool allowlist/blocklist + enabled check |
| **Provider guardrails** | `providers` dict var | Provider/model access control |
| **Generic** | `required_fields` / `blocked_values` / `limits` | Alan doğrulama |

**Quality gates (6 check):** completeness, consistency, regression, format, length, groundedness

### Desteklenen LLM Provider'lar (6)

Claude, OpenAI, Google Gemini, DeepSeek, Qwen, xAI

## Dağıtım

```bash
pip install ao-kernel              # Core (sadece jsonschema>=4.23.0)
pip install ao-kernel[llm]         # tenacity>=9.0.0, tiktoken>=0.9.0
pip install ao-kernel[mcp]         # mcp>=1.0.0 (stdio transport)
pip install ao-kernel[mcp-http]    # mcp + starlette>=0.36.0 + uvicorn>=0.27.0
pip install ao-kernel[otel]        # opentelemetry-api, -sdk, -exporter-otlp
pip install ao-kernel[pgvector]    # pgvector, psycopg2-binary
```

## Teknik Kurallar

- Python >= 3.11 (test: 3.11, 3.12, 3.13)
- Core dependency: jsonschema>=4.23.0 (TEK zorunlu dep)
- Dosya bütçesi: < 800 satır per file
- **Fail-closed:** policy violation → block. Corrupt session → raise `SessionCorruptedError`. Policy load error → deny
- Evidence: her side-effect JSONL append-only log
- Secrets: ASLA log'a yazılmaz
- Atomic writes: write_json_atomic (tmp + fsync + rename)
- Type hints zorunlu (public functions)
- Coverage gate: %70 minimum branch coverage (`ao_kernel/_internal` hariç)
- Lint: ruff (line-length 120, py311)
- Type check: mypy (strict)
- Mutation test: mutmut

## Geliştirme Akışı

```bash
# Geliştirme
pip install -e ".[dev,llm,mcp]"
pytest tests/ -x

# Lint + type check
ruff check ao_kernel/ tests/
mypy ao_kernel/ --ignore-missing-imports

# CLI
ao-kernel init           # .ao/ workspace oluştur
ao-kernel doctor         # 8 sağlık kontrolü
ao-kernel system-status  # workspace durumu
ao-kernel mcp serve      # MCP server başlat (stdio)
ao-kernel mcp serve --transport http --port 8080  # MCP HTTP

# Release (trusted publishing — tag push tetikler)
git tag v2.x.y
git push origin v2.x.y
# GitHub Actions .github/workflows/publish.yml otomatik PyPI upload yapar
```

## Test Altyapısı

- **508 test**, 34 test dosyası
- **Quality gate:** AST-based anti-pattern tespiti (conftest.py):
  - BLK-001: `assert callable(x)` bloklanır
  - BLK-002: `assert x is not None` tek assertion olarak bloklanır
  - BLK-003: `except: pass` test içinde bloklanır
- **Fixture'lar:** `tmp_workspace`, `empty_dir`, `legacy_workspace`
- **Coverage:** %70 minimum, `ao_kernel/_internal/*` hariç

## Codex İstişare Altyapısı

Bu repo'da Codex (GPT-5.4) ile istişare yapılabilir. Önemli mimari kararlarda istişare ZORUNLU.

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

### İstişare Kuralları

- Mimari karar gerektiren konularda istişare AÇ
- Codex'in itirazlarını ciddiye al — her birini kanıtla kabul/ret
- İstişare sonucunu memory'ye kaydet
- Mevcut kararları istişare olmadan değiştirme

### İstişare Geçmişi

| ID | Konu | Verdict | Sonuç |
|---|---|---|---|
| CNS-001 | Framework karşılaştırma | D (hibrit DIY) | LLM capabilities kendin yap |
| CNS-002 | LLM plan review | B (orta revizyon) | PR0 eklendi, tool calling fail-closed |
| CNS-003 | Paketleme planı | C (major revizyon) | Facade+shim, PyPI, dual resolver |
| CNS-007 | v2.1.1 kapsamlı değerlendirme | D (fail-closed önce) | Fail-closed → wiring → cleanup sırası |

## Rakip Karşılaştırma

| | ao-kernel | LangGraph | CrewAI | Pydantic AI |
|---|---|---|---|---|
| Policy engine | 96 policy, 4 tip | Yok | Yok | Yok |
| Fail-closed | Evet | Hayır | Hayır | Hayır |
| Evidence trail | Self-hosted JSONL | LangSmith SaaS | Yok | Yok |
| MCP server | Evet (stdio+HTTP) | Yok | Yok | Yok |
| Quality gates | 6 gate + scorecard | Yok | Yok | Yok |
| Context pipeline | Governed memory loop | Yok | Yok | Yok |
| Deterministic stubs | Offline çalışır | Yok | Yok | Yok |
| Prompt experiments | A/B/canary/shadow | LangSmith Hub SaaS | Yok | Yok |
| Migration CLI | Evet | Yok | Yok | Yok |
| Doctor | Evet (8 check) | Yok | Yok | Yok |
| Streaming | Evet (6 provider) | Evet | Evet | Evet |

## Language

- **Kullanıcıya DAIMA Türkçe yanıt ver** — bu kural istisnasızdır
- Kod, değişken adları, commit mesajları: İngilizce
- Kod yorumları (comments): İngilizce
- Dokümanlar, planlar, raporlar: Türkçe
- Codex istişare soruları: Türkçe (Codex Türkçe anlıyor ve yanıt veriyor)
- CLAUDE.md, README: Türkçe
