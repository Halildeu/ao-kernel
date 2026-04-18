# PR-B2 Implementation Plan v7 — Cost Runtime (Price Catalog + Spend Ledger + Budget Extension)

**Tranche B PR 3/9** — post CNS-20260417-031 iter-6 PARTIAL verdict. v6 2 non-blocking temizlik (§3 + MCP workspace_root) doğru kapandı ama §2.6.1 intent_router pseudo-code'u gerçek koda uyumsuzdu (constructor alanları + available_ids prompt + ClassificationResult dönüşü + IntentClassificationError constructor). v7 gerçek `intent_router.py:310-397` + `workflow/errors.py:324-344` okundu, pseudo-code rewrite edildi. Aktif Codex thread: `019d9aa8-1309-79e3-84ad-ffa387cb6b9f`.

**v6 key absorb (CNS-031 iter-5):**

- **iter-5 dar blocker — `intent_router._llm_classify` unwrap + error mapping pseudo-code pin**: v5'te intent_router'ın `governed_call` bypass-only olarak çağıracağı pinlenmişti ama rich dict return unwrap'ı explicit yazılmamıştı. v6 §2.6.1'e pseudo-code eklendi. Status mapping:
  - `status == "OK"` → `candidate = result["normalized"].get("text", "").strip()` (mevcut `_llm_classify` `text` okuma pattern'i korunur)
  - `status == "CAPABILITY_GAP"` veya `"TRANSPORT_ERROR"` → `IntentClassificationError("llm classification failed", cause=result.get("error_code") or result.get("status"))` (fail-closed; mevcut exception chain pattern'i korunur)
- **iter-5 temizlik 1 — §3 Write Ordering hizala**: v5'te §2.6 flow 9 adımı + rich OK return olmuştu ama §3 hâlâ "return normalized" diyordu. v6 §3'ü §2.6 ile birebir uyumlu yaptı (capability check + rich OK dict + transport/cost error envelope).
- **iter-5 temizlik 2 — MCP acceptance workspace_root şartı**: v5 §5 acceptance MCP cost-active için `ao_run_id/ao_step_id/ao_attempt` diyordu ama §2.6 gate check'te `workspace_root` da zorunlu (`all([workspace_root, run_id, step_id, attempt])`). v6 acceptance satırına `workspace_root` eklendi.

**v5'ten devam eden kararlar (iter-5'te onaylandı):**
- B1 governed_call success rich dict (§2.6 + §10 position 15)
- B2 streaming boundary non-streaming only (§2.6 + §10 position 14)
- B3 commit 5b tutarsızlık temizlendi
- B4 build_request_with_context injected_messages additive contract (§2.6 + §10 position 16)

**v5 key absorb (CNS-031 iter-4):**

- **iter-4 B1 — `governed_call` success return rich contract pinlendi**: `normalize_response` mevcut sadece `{text, usage, tool_calls, raw_json, provider_id}` döner ama `client.py:620+` success path'inde `resp_bytes`, `transport_result`, `elapsed_ms` evidence/telemetry/decision_extraction için gerekli. v5'te `governed_call` success path **wrapper-internal rich dict** döndürür: `{"status": "OK", "normalized": dict, "resp_bytes": bytes, "transport_result": dict, "elapsed_ms": int, "request_id": str}`. Caller'lar (client, mcp_server) bu dict'ten kendi final envelope'unu + post-processing'ini (decision extraction, scorecard, telemetry) üretmeye devam eder. `client.py` + `mcp_server.py` success path'indeki envelope inşasında satır sayısı korunur (mevcut pattern dokunulmaz).
- **iter-4 B2 — Streaming boundary pinlendi**: `governed_call` **non-streaming only**. `client.llm_call(stream=True)` mevcut `build → _execute_stream(...)` yolunda kalır (wrapper dışı). Streaming dalı cost tracking'e dahil değil (FAZ-C deferred). `governed_call` imzasında `stream` kwarg YOK; caller stream=True ise governed_call'a hiç inmez. Acceptance + §10 Resolved Position 14 pinlendi.
- **iter-4 B3 — Commit 5b tutarsızlık temizlendi**: v4'te §4 DAG'de hâlâ "intent_router auto-fill identity from run context" + test "workflow run integration" kaldı — §2.6 bypass-only ile çelişiyordu. v5'te DAG satırı "intent_router cost-bypass-only wire (identity=None)" olarak güncellendi; test adı "test_cost_entrypoint_plumbing.py::test_intent_router_bypass_only".
- **iter-4 B4 — `build_request_with_context` `injected_messages` additive return contract**: Mevcut `build_request_with_context` `llm.py:260-340` sadece `build_request()` çıktısını döndürüyor; `injected_messages` field yok. v5'te **additive return contract**: `build_request_with_context` dict'e `injected_messages: list[dict[str, Any]]` ekler (context-injected effective prompt). Plan v4 `effective_messages = req.get("injected_messages", messages)` çağrısı bu contract'a dayanır. Commit 5a'ya ek delta: `llm.py::build_request_with_context` + `context/context_injector.py` (veya compile_context caller noktası) `injected_messages` field'ını return dict'e ekler. Backward compat: mevcut caller'lar bu field'ı okumuyor → absent pre-B2 caller'ı etkilemez; B2 governed_call okur.

**v3/v4'ten devam eden kararlar (iter-3/iter-4'te onaylandı):**
- execute_request transport-only; governed_call composition wrapper (v3 iter-2)
- cost_usd Option A + CostTrackingConfigError (v3 iter-2)
- Writer invariant: tokens_output OMIT / aggregate always (v3 iter-2)
- update_run(max_retries=3) mevcut helper
- Q1-Q5 iter-2 tercih locking (streaming sessiz, MCP ao_ prefix, CAS 3 fixed, cached silent)
- Context-aware build: session_context varsa build_request_with_context (v4 iter-3 B1)
- Capability + transport envelope preserve (v4 iter-3 B2)
- intent_router bypass-only (v4 iter-3 B3)

**v4 key absorb (CNS-031 iter-3):**

- **iter-3 B1 — Client context path korundu**: `governed_call` signature 5 ek context-aware kwarg kabul eder (`session_context`, `profile`, `embedding_config`, `vector_store`, `workspace_root_str`). İçeride `session_context` varsa `build_request_with_context(...)` (context-inject), aksi `build_request(...)` plain. Pre-dispatch cost estimate **effective (context-injected) messages** üstünden hesaplanır (build_request_with_context'in injected messages'ı `req["injected_messages"]`'dan alınır veya re-compile edilir). Detay §2.6.
- **iter-3 B2 — Return contract preserved**: `governed_call` mevcut caller envelope'u korur. Capability check içeride (mevcut `check_capabilities` call) → `{"status": "CAPABILITY_GAP", ...}` envelope döner (transport öncesi, cost öncesi). Transport error → `{"status": "TRANSPORT_ERROR", "error_code", "http_status", "elapsed_ms"}` envelope (mevcut `client.py:608` pattern korunur). Cost-layer error'lar (`BudgetExhaustedError`, `CostTrackingConfigError`, `PriceCatalogNotFoundError`, `LLMUsageMissingError`) **raise** edilir — caller propagate veya try/except. Testler mevcut envelope assertionlarını değiştirmez.
- **iter-3 B3 — `intent_router` bypass-only**: `IntentRouter._llm_classify` API widen YOK. B2'de intent_router `governed_call(..., run_id=None, step_id=None, attempt=None)` çağırır — cost-active olmaz. Rasyonel: standalone classifier workflow-run budget anchor değil; cost-active yapmak API'yi değiştirir ve B2 scope'unu şişirir. FAZ-C'de workflow-run'a bağlı classification senaryosu değerlendirilir.

**v3'ten devam eden karar başlıkları (iter-3'te onaylandı):**
- execute_request transport-only teyit; governed_call composition wrapper seçimi doğru (B1 iter-2)
- cost_usd axis Option A + CostTrackingConfigError (B2 iter-2)
- Writer invariant: tokens_output OMIT / aggregate always (B3 iter-2)
- update_run(max_retries=3) mevcut helper
- Q1-Q5 iter-2 tercih locking

**v3 key absorb (CNS-031 iter-2) — v4'te hâlâ geçerli:**

- **B1 — `execute_request` yerine yeni `llm.governed_call()` helper (fundamental redesign)**: iter-2 blocker'ı `execute_request` signature'ı pinlenmedi. **Gerçek kod okuması** (`llm.py:170`) `execute_request`'in **transport-level** olduğunu gösterdi — kwargs flat: `url`, `headers`, `body_bytes`, `provider_id`, `request_id`. `model` ve `messages` **body_bytes içinde encode edilmiş** (build_request üretir). Cost estimate `model` + `prompt_tokens` input'una ihtiyaç duyuyor → build öncesi veya caller-level info gerekli. Plan v2 "execute_request wrap" çözümü **yanlış noktada** çünkü oraya vardığında `model`/`messages` opak.

  **Fix (v3)**: yeni `ao_kernel/llm.py::governed_call()` wrapper — SHE caller (client, mcp_server, intent_router) bunu çağırır. Tek fonksiyon içinde: route → capability check → estimate → budget reserve → build_request → execute_request → normalize_response → compute actual → reconcile → record_spend. Mevcut `build_request` / `execute_request` / `normalize_response` primitive'leri bozulmaz; `governed_call` onları compose eder. Non-cost caller'lar mevcut primitives'i doğrudan kullanmaya devam eder (dormant opt-out).

  ```python
  def governed_call(
      messages: list[dict[str, Any]],
      *,
      provider_id: str,
      model: str,
      api_key: str,
      base_url: str,
      temperature: float | None = None,
      max_tokens: int | None = None,
      tools: list[dict[str, Any]] | None = None,
      response_format: dict[str, Any] | None = None,
      request_id: str,
      # Cost-tracking identity (all 4 required for cost-active path):
      workspace_root: Path | None = None,
      run_id: str | None = None,
      step_id: str | None = None,
      attempt: int | None = None,
  ) -> dict[str, Any]:
      """Composed LLM call with optional cost governance.
      
      If workspace_root + run_id + step_id + attempt all non-None AND
      cost policy enabled AND budget.cost_usd configured: full cost
      pipeline. Otherwise: pass-through (build + execute + normalize).
      """
  ```

  Caller wire (§2.6'da detay):
  - `client.py::AoKernelClient.llm_call()` → `governed_call(...)` (build/execute/normalize direct çağrıları kaldırılır)
  - `mcp_server.py::handle_llm_call()` → `governed_call(...)` + MCP param `ao_run_id/ao_step_id/ao_attempt` optional widen
  - `workflow/intent_router.py` → `governed_call(...)` (run execution context'ten identity auto-fills)
  - `stream_request()` → DOKUNULMAZ; streaming cost FAZ-C'ye deferred (plan v3 §7 CHANGELOG)

- **B2 — cost_usd axis zorunluluğu: Option A (config error if missing)**: iter-2 blocker'ı `budget.cost_usd: BudgetAxis | None` opsiyonel olunca plan'ın reserve/check/reconcile mantığı tanımsız. **Karar: Option A**. `policy.enabled=true` iken run.budget.cost_usd None → yeni `CostTrackingConfigError(run_id, "policy enabled but run.budget.cost_usd not configured")`. Rasyonel:
  - B2 MVP'nin vaadi "budget cap fail-closed" — ledger-only branch (Option B) bu vaadi zayıflatır.
  - B3 cost-aware routing downstream PR'ı `cost_usd` axis'e zaten bağımlı; Option B bu dependency'yi opsiyonel yapmaz, sadece bir config'de "routing yok" senaryosuna ek zemin üretir.
  - Fail-closed semantic CLAUDE.md §2 ile uyumlu; operator opt-in başarısızsa early config error kabul edilir.
  
  Migration: v3.1.0 operator'ları v3.2.0'a yükseltirken workflow-run'larında `budget.cost_usd` yoksa `policy.enabled=false` (dormant) kalacak. Policy'yi opt-in etmeden önce workflow spec'lere `cost_usd` axis eklemek gerekir (docs COST-MODEL.md §4'te migration step olarak açıklanır).

- **B3 — Aggregate/granular writer invariant pin (exact wire format)**: iter-2 blocker'ı `tokens_output=None` iken "both granular" ne demek belirsizdi + plan `$defs/budget_axis` refactor dedi ama **gerçek schema'da `$defs` yok** (her axis inline tanım, farklı type: tokens integer, time/cost number).
  
  **Fix (v3)**:
  - **Schema refactor YOK**: `$defs/budget_axis` eklemiyoruz (tip heterojen: integer vs number). Additive inline: `tokens_input` ve `tokens_output` yeni property olarak `budget.properties`'e eklenir; tip `tokens` ile aynı (integer axis).
  - **Writer invariant**:
    - **tokens_input HER ZAMAN YAZILIR** (required olmayan ama writer-enforced).
    - **tokens_output None ise OMİT** (null değil, absent property). Schema'da da `additionalProperties: false` kalır; `tokens_output` required listesinde yok.
    - **aggregate `tokens` HER ZAMAN YAZILIR** (Q7 absorb). Legacy-only (`tokens_input` + `tokens_output=None`) durumda aggregate = tokens_input (çünkü sum = input + 0). Normal durumda aggregate = tokens_input + tokens_output.
  - **Reader**:
    - Legacy kayıt `tokens` var, `tokens_input` yok → `tokens_input = BudgetAxis(same as tokens)`, `tokens_output = None`.
    - Yeni kayıt 3'ü de var → granular honored, aggregate recomputed (sanity check).
  - **Schema delta** (`workflow-run.schema.v1.json::budget.properties` additive):
    ```jsonc
    "tokens_input": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "limit": {"type": "integer", "minimum": 1},
        "spent": {"type": "integer", "minimum": 0},
        "remaining": {"type": "integer", "minimum": 0}
      },
      "description": "Prompt token ceiling (B2: granular breakdown of tokens aggregate). Writer always emits when B2 cost pipeline active."
    },
    "tokens_output": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "limit": {"type": "integer", "minimum": 1},
        "spent": {"type": "integer", "minimum": 0},
        "remaining": {"type": "integer", "minimum": 0}
      },
      "description": "Completion token ceiling (B2: granular breakdown). Writer omits when not configured; null serialization is invalid."
    }
    ```
    Schema `required` listesi değişmez (her iki yeni field optional).

- **Temizlik — `WorkflowRunConcurrentMutationError` silindi**: iter-2 not'u "mevcut `WorkflowCASConflictError` + `update_run(max_retries=3)` kullan" kabul edildi. Gerçek kod (`run_store.py:201-223`): `update_run(workspace_root, run_id, *, mutator, max_retries=1)` helper var; `WorkflowCASConflictError` raise edildiğinde `max_retries` tükendiyse. B2 middleware `update_run(..., max_retries=3)` kullanır (3 fixed, Q3'te Codex onayı). Yeni error gereksiz; error count **v2'deki 9'dan 8'e düştü** (ama `CostTrackingConfigError` eklendi → net 9 kalır).

**Q cevaplarının absorb'u (iter-2'de lock edildi):**

- Q3 (iter-1): `estimate_output_tokens(est_in, max_tokens)` = `min(max_tokens, est_in * 0.25)`; `max_tokens` caller kwarg.
- Q6 (iter-1): `load_price_catalog` unconditional; dormant gate `governed_call` içinde.
- Q8 (iter-1): Catalog LRU TTL sabit 300s.
- Q10 (iter-1): B2 merge + 48h smoke → B3 branch.
- **Q1 (iter-2) Streaming messaging**: sessiz bypass + docs/CHANGELOG. `stream_request()` cost aware değil; process başına bir `logger.warning("Streaming cost tracking coming in FAZ-C")` ilk call'da. Evidence emit YOK (log pollution avoidance).
- **Q2 (iter-2) MCP `ao_` prefix**: `ao_run_id` / `ao_step_id` / `ao_attempt` optional MCP tool params. Namespace collision avoidance.
- **Q3 (iter-2) CAS retry**: fixed 3 (`update_run(max_retries=3)`). Policy knob YOK. Mevcut `WorkflowCASConflictError` kullanılır.
- **Q4 (iter-2) Aggregate recompute**: ≡ B3 (§2.5 writer invariant). Writer her çağrıda aggregate = tokens_input + (tokens_output or 0). Legacy-reader → tokens_input = tokens, tokens_output = None; aggregate = tokens_input (sum).
- **Q5 (iter-2) cached_tokens**: silent OK (`compute_cost(cached=0)`). `usage_missing=true` SADECE `tokens_input is None` VEYA `tokens_output is None` tetikler.

**Plan v2'den DEVAM eden onaylı kararlar** (iter-1'de kabul):
- Q4 (iter-1) Ledger rotation: scope-out, FAZ-B ufak follow-up.
- Q5 (iter-1) Reservation holds on error: MVP için yeterli.
- Q9 (iter-1) Write order step 10: ledger → evidence → raise.

## 1. Amaç

B0 foundation (merged #96) + CNS-031 iter-2 gerçek-kod absorb ile `ao_kernel/cost/` package runtime'ını yaz. `governed_call` LLM composition helper (4 caller path'in girişi). `Budget` tokens_input/tokens_output additive widen (BudgetAxis-based). Normalizer strict helper. Ledger canonical digest idempotency. Dormant policy graceful no-op.

**Release gate**: workspace operatörleri bundled catalog + dormant policy override ile cost tracking'i opt-in eder; `policy.enabled=true` + budget.cost_usd yoksa config error; budget exhausted fail-closed; ledger append-only + digest-idempotent; dormant mode → caller `governed_call` bypass branch (transport direct).

### Kapsam özeti (v3 revize)

| Katman | Modül | Satır (est.) |
|---|---|---|
| Public package | `ao_kernel/cost/__init__.py` | ~55 |
| Catalog loader | `ao_kernel/cost/catalog.py` | ~280 |
| Ledger | `ao_kernel/cost/ledger.py` (digest idempotency + corrupt guard) | ~260 |
| Policy | `ao_kernel/cost/policy.py` | ~130 |
| Cost math | `ao_kernel/cost/cost_math.py` | ~100 |
| Middleware | `ao_kernel/cost/middleware.py` (reserve/reconcile/record flow) | ~260 |
| Typed errors | `ao_kernel/cost/errors.py` (9 types) | ~130 |
| Budget widen | `ao_kernel/workflow/budget.py` delta (tokens_input + tokens_output + back-compat) | ~160 delta |
| Normalizer strict | `ao_kernel/_internal/prj_kernel_api/llm_response_normalizer.py` delta | ~60 delta |
| LLM facade — **`governed_call` NEW** | `ao_kernel/llm.py` delta | ~200 delta |
| Client wire | `ao_kernel/client.py` delta (llm_call → governed_call) | ~70 delta |
| MCP wire | `ao_kernel/mcp_server.py` delta (+ MCP tool schema widen `ao_run_id`/etc) | ~80 delta |
| Intent router wire | `ao_kernel/workflow/intent_router.py` delta | ~50 delta |
| Schema widen | `workflow-run.schema.v1.json` (tokens_input/tokens_output) + `spend-ledger.schema.v1.json` (attempt/usage_missing/billing_digest) + `policy-cost-tracking.schema.v1.json` (2 knob) | ~45 delta |
| Tests | 5 test files (~120 test) | ~1450 |
| Docs | `docs/COST-MODEL.md` runtime notes (§4-§7 + §8 identity threading + §9 streaming deferred + §10 migration guide) | ~100 delta |
| CHANGELOG | `[Unreleased]` PR-B2 | ~85 |
| **Toplam** | 6 yeni modül + 5 code delta + 3 schema delta + 1 docs delta + ~120 test | **~3515 satır** |

Codex iter-1 tahmini 2800-3400 bandı; v3 integration reshape + governed_call + caller wire'larla orta-üst bantta. Commit sayısı **7** (iter-2 commit 5 split önerisi absorbe).

- Yeni evidence kind: **3** (24 → 27): `llm_cost_estimated`, `llm_spend_recorded`, `llm_usage_missing`
- Yeni core dep: 0
- Yeni schema: 0; widen only
- Yeni error type: **9** — `PriceCatalogChecksumError`, `PriceCatalogStaleError`, `PriceCatalogNotFoundError`, `SpendLedgerDuplicateError`, `SpendLedgerCorruptedError`, `LLMUsageMissingError`, `CostTrackingDisabledError`, `CostTrackingConfigError` (NEW), `BudgetExhaustedError` (extend from PR-A1 if missing)
- Kullanılan mevcut error (yeni değil): `WorkflowCASConflictError` (CAS retry failure), `WorkflowBudgetExhaustedError` (PR-A1)

## 2. Scope İçi

### 2.1 `ao_kernel/cost/catalog.py`

Plan v2 §2.1 korunur. Dormant check YOK (caller'da); sabit 300s LRU.

### 2.2 `ao_kernel/cost/ledger.py` — canonical billing digest

```python
def _billing_digest(event: SpendEvent) -> str:
    payload = {
        "provider_id": event.provider_id,
        "model": event.model,
        "vendor_model_id": event.vendor_model_id,
        "tokens_input": event.tokens_input,
        "tokens_output": event.tokens_output,
        "cached_tokens": event.cached_tokens,
        "cost_usd": str(Decimal(str(event.cost_usd))),  # Decimal-stable canonicalize
        "usage_missing": event.usage_missing,
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
```

Ledger line'ına `billing_digest` field additive. Idempotency: same key + same digest → no-op warn; different digest → `SpendLedgerDuplicateError`. Corrupt JSONL scan line → `SpendLedgerCorruptedError`.

### 2.3 `ao_kernel/cost/cost_math.py`

```python
def compute_cost(entry, tokens_input, tokens_output, cached_tokens=0) -> Decimal: ...
def estimate_cost(entry, est_tokens_input, est_tokens_output) -> Decimal: ...
def estimate_output_tokens(est_tokens_input: int, max_tokens: int | None) -> int:
    """Q3 fix: min(max_tokens, est_in * 0.25). Caller kwarg."""
    ratio_estimate = int(est_tokens_input * 0.25)
    if max_tokens is None:
        return ratio_estimate
    return min(max_tokens, ratio_estimate)
```

### 2.4 `ao_kernel/cost/policy.py`

Plan v2 korunur. Schema widen (2 knob):

```jsonc
"fail_closed_on_missing_usage": {"type": "boolean", "default": true},
"idempotency_window_lines": {"type": "integer", "minimum": 100, "maximum": 100000, "default": 1000}
```

### 2.5 `ao_kernel/workflow/budget.py` delta — BudgetAxis additive widen

**Shape** (v3 final):
```python
@dataclass(frozen=True)
class Budget:
    tokens: BudgetAxis | None           # aggregate (preserved)
    tokens_input: BudgetAxis | None     # NEW
    tokens_output: BudgetAxis | None    # NEW
    time_seconds: BudgetAxis | None
    cost_usd: BudgetAxis | None
    fail_closed_on_exhaust: bool
```

**Reader** (`budget_from_dict` delta):
- Record has `tokens` but not `tokens_input` → `tokens_input = BudgetAxis(copy same values as tokens)`, `tokens_output = None`. Conservative legacy-to-granular mapping.
- Record has all 3 (new writer path) → granular used as-is; aggregate recomputed as sanity sum check (mismatch → warn-log, not error — reader-side tolerant).

**Writer** (`budget_to_dict` delta):
- `tokens_input` HER ZAMAN yazılır (writer invariant; enforced when B2 cost pipeline active).
- `tokens_output` None ise **omit** (key absent; schema additionalProperties: false respected).
- `tokens` (aggregate) HER ZAMAN yazılır; value = `tokens_input.limit + (tokens_output.limit if tokens_output else 0)` (limit), spent/remaining aynı hesap.
- Null serialization **yasak** — JSON'da `"tokens_output": null` yazılmaz.

**`record_spend` delta** (`run_id` kwarg mevcut — preserved):
```python
def record_spend(
    budget: Budget,
    *,
    tokens: int | None = None,          # aggregate — preserved
    tokens_input: int | None = None,    # NEW
    tokens_output: int | None = None,   # NEW
    time_seconds: float | None = None,
    cost_usd: _AxisNum | None = None,
    run_id: str | None = None,
) -> Budget:
    """B2: tokens_input + tokens_output granular spend. Aggregate auto-adjusts:
    if tokens_input OR tokens_output passed, tokens += (input + output).
    Caller may alternatively pass aggregate 'tokens' directly for legacy flows.
    """
```

Invariant: caller ya granular (input + output) ya aggregate (tokens) geçer; ikisini aynı çağrıda geçmek → `ValueError` (double-counting risk).

**Schema delta** (`workflow-run.schema.v1.json::$defs/$defs — inline extension, no $defs/budget_axis`):
```jsonc
// budget.properties additive:
"tokens_input": { /* inline integer axis, same shape as tokens */ },
"tokens_output": { /* inline integer axis, same shape as tokens */ }
```

`required` listesi değişmez.

### 2.6 Integration — yeni `llm.governed_call()` helper

**Mevcut primitive'ler** (`llm.py:170+`):
```python
def build_request(messages, *, provider_id, model, ...) -> dict       # request assembly
def execute_request(*, url, headers, body_bytes, ...) -> dict          # transport
def normalize_response(resp_bytes, *, provider_id) -> dict             # parse
```

**B2 yeni wrapper** (`ao_kernel/llm.py` delta) — v4 context-aware + envelope-preserving:

```python
def governed_call(
    messages: list[dict[str, Any]],
    *,
    # Core routing (required):
    provider_id: str,
    model: str,
    api_key: str,
    base_url: str,
    request_id: str,
    # Call shape (optional):
    temperature: float | None = None,
    max_tokens: int | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | None = None,
    response_format: dict[str, Any] | None = None,
    # Context-aware build (v4 B1 absorb — required for client session path):
    session_context: dict[str, Any] | None = None,
    workspace_root_str: str | None = None,
    profile: str | None = None,
    embedding_config: Any | None = None,
    vector_store: Any | None = None,
    # Cost-tracking identity (v3 B2 — all 4 required for cost-active path):
    workspace_root: Path | None = None,
    run_id: str | None = None,
    step_id: str | None = None,
    attempt: int | None = None,
) -> dict[str, Any]:
    """Composed LLM call (non-streaming only). Preserves caller envelope
    contract (CAPABILITY_GAP, TRANSPORT_ERROR). Cost governance opt-in via
    identity kwargs; context injection opt-in via session_context kwarg.
    
    STREAMING BOUNDARY (v5 iter-4 B2 absorb): this function is NON-STREAMING
    ONLY. Callers with stream=True intent MUST NOT call governed_call; they
    remain on the existing build + _execute_stream path (client.py:588-596).
    Streaming cost tracking is FAZ-C scope (chunk-level tokenization + partial
    ledger).
    
    Return shape (v5 iter-4 B1 absorb — rich internal dict):
    - On CAPABILITY_GAP: {"status": "CAPABILITY_GAP", "missing": [...], "provider_id", "model", "request_id", "text": ""} — caller envelope-ready.
    - On TRANSPORT_ERROR: {"status": "TRANSPORT_ERROR", "error_code", "http_status", "provider_id", "model", "request_id", "text": "", "elapsed_ms"} — caller envelope-ready (mirrors client.py:609-618).
    - On normal success: {"status": "OK", "normalized": <dict from normalize_response>, "resp_bytes": bytes, "transport_result": <dict from execute_request>, "elapsed_ms": int, "request_id": str}
      → Caller (client.py / mcp_server.py) unwraps: takes `normalized` for
        response fields, `resp_bytes`/`transport_result` for evidence/telemetry,
        `elapsed_ms` for final envelope. Mevcut post-call pipeline (decision
        extraction, scorecard, telemetry) caller'da kalır; governed_call'un
        içinde DUPLICATE EDİLMEZ.
    
    Cost-layer errors RAISE (not envelope):
    - BudgetExhaustedError, CostTrackingConfigError, PriceCatalogNotFoundError, LLMUsageMissingError
    Caller decides propagate or try/except wrap.
    """
    # 1. Capability check (BEFORE cost, BEFORE transport) — preserves client pattern.
    cap_ok, _, missing = check_capabilities(
        provider_id=provider_id, model=model,
        has_tools=bool(tools), has_response_format=bool(response_format),
    )
    if not cap_ok and missing:
        return {
            "status": "CAPABILITY_GAP", "text": "", "missing": missing,
            "provider_id": provider_id, "model": model, "request_id": request_id,
        }
    
    # 2. Cost gate — all 4 identity + ws + policy.enabled
    cost_active = all([workspace_root, run_id, step_id, attempt is not None])
    cost_policy = None
    if cost_active:
        cost_policy = load_cost_policy(workspace_root)
        cost_active = cost_policy.enabled
    
    # 3. Build request (context-aware if session_context present)
    if session_context is not None:
        req = build_request_with_context(
            messages=messages, provider_id=provider_id, model=model,
            base_url=base_url, api_key=api_key,
            session_context=session_context, workspace_root=workspace_root_str,
            profile=profile, embedding_config=embedding_config, vector_store=vector_store,
            temperature=temperature, max_tokens=max_tokens, request_id=request_id,
            tools=tools, tool_choice=tool_choice, response_format=response_format,
        )
        # req["injected_messages"] holds the context-injected effective messages
        # used for cost estimate (B2 iter-3 B1 absorb).
        effective_messages = req.get("injected_messages", messages)
    else:
        req = build_request(
            messages=messages, provider_id=provider_id, model=model,
            base_url=base_url, api_key=api_key,
            temperature=temperature, max_tokens=max_tokens, request_id=request_id,
            tools=tools, tool_choice=tool_choice, response_format=response_format,
        )
        effective_messages = messages
    
    # 4. Cost reserve (uses effective messages for accurate estimate)
    est_cost, catalog_entry = None, None
    if cost_active:
        from ao_kernel.cost.middleware import pre_dispatch_reserve
        est_cost, catalog_entry = pre_dispatch_reserve(
            workspace_root=workspace_root, run_id=run_id, step_id=step_id,
            attempt=attempt, provider_id=provider_id, model=model,
            prompt_messages=effective_messages, max_tokens=max_tokens,
            policy=cost_policy,
        )
        # Raises: BudgetExhaustedError, CostTrackingConfigError, PriceCatalogNotFoundError
        # Emits: llm_cost_estimated (fail-open)
    
    # 5. Transport (existing)
    transport_result = execute_request(
        url=req["url"], headers=req["headers"], body_bytes=req["body_bytes"],
        timeout_seconds=30.0, provider_id=provider_id, request_id=request_id,
    )
    
    # 6. Transport envelope preserve (v4 B2 absorb — mirrors client.py:608)
    if transport_result.get("status") != "OK":
        # Reservation HOLDS (Q5 iter-1 policy — no refund on error).
        # Caller sees TRANSPORT_ERROR envelope; budget already debited.
        return {
            "status": "TRANSPORT_ERROR", "text": "",
            "error_code": transport_result.get("error_code", "UNKNOWN"),
            "http_status": transport_result.get("http_status"),
            "provider_id": provider_id, "model": model, "request_id": request_id,
            "elapsed_ms": transport_result.get("elapsed_ms", 0),
        }
    
    # 7. Normalize
    normalized = normalize_response(transport_result["resp_bytes"], provider_id=provider_id)
    
    # 8. Cost reconcile + record (if active)
    if cost_active:
        from ao_kernel.cost.middleware import post_response_reconcile
        post_response_reconcile(
            workspace_root=workspace_root, run_id=run_id, step_id=step_id,
            attempt=attempt, provider_id=provider_id, model=model,
            catalog_entry=catalog_entry, est_cost=est_cost,
            raw_response_bytes=transport_result["resp_bytes"],
            policy=cost_policy,
        )
        # Raises: LLMUsageMissingError (when policy.fail_closed_on_missing_usage=true AND usage absent)
        # Emits: llm_spend_recorded OR llm_usage_missing (fail-open)
    
    # 9. Return rich internal dict (v5 iter-4 B1 absorb).
    # Caller unwraps: `normalized` for response text/usage, `resp_bytes` +
    # `transport_result` for evidence/telemetry, `elapsed_ms` for final envelope.
    return {
        "status": "OK",
        "normalized": normalized,
        "resp_bytes": transport_result["resp_bytes"],
        "transport_result": transport_result,
        "elapsed_ms": transport_result.get("elapsed_ms", 0),
        "request_id": request_id,
    }
```

**Key properties (iter-3 + iter-4 absorb):**
- Capability gap + transport error envelope mevcut caller kontratı korunur — test regression yok.
- Cost errors raise; caller existing try/except veya propagate pattern'i korur.
- Context path: `session_context` varsa `build_request_with_context` (full PR-A context pipeline), aksi `build_request` plain.
- Effective messages: cost estimate context-injected prompt üstünden hesap — accuracy preserved.
- **Streaming boundary (v5)**: `governed_call` non-streaming only; `stream=True` caller mevcut `_execute_stream` yolunda kalır.
- **Rich return dict (v5)**: success path `{"status": "OK", "normalized", "resp_bytes", "transport_result", "elapsed_ms", "request_id"}`; caller post-processing (decision extraction, scorecard, telemetry) kendi sorumluluğunda.

**`build_request_with_context` return contract widen (v5 iter-4 B4 absorb):**

Mevcut `build_request_with_context` (`llm.py:260-340`) dict return'üne **`injected_messages`** field'ı additive eklenir. `compile_context + inject` sonrası effective messages listesi bu field'a yazılır. `governed_call` bu field'ı `req.get("injected_messages", messages)` ile okur; absent durumda caller'ın raw messages'ına düşer.

Contract:
```python
def build_request_with_context(...) -> dict[str, Any]:
    """... existing docstring ...
    
    Return dict additive fields (v5 iter-4 B4 absorb — B2 cost path uses these):
    - "injected_messages": list[dict[str, Any]] — context-injected effective
      prompt. When session_context=None or compile fails, returns raw messages.
    - (other existing fields: url, headers, body_bytes, ...)
    """
```

Backward compat: pre-B2 caller'lar bu field'ı okumuyor → zarar yok. B2 governed_call explicit okur. Implementation: commit 5a delta, `llm.py::build_request_with_context` sonuna `req["injected_messages"] = compiled_messages` ekle.

### 2.6.1 `intent_router._llm_classify` unwrap + error mapping (v7 iter-6 absorb — gerçek kod uyumlu)

`intent_router._llm_classify` (`intent_router.py:319-397`) mevcut akışı: `resolve_route(intent="FAST_TEXT")` → `build_request + execute_request + normalize_response` üçlüsü → `candidate = resp.text.strip()` → `candidate in available_ids` doğrulaması → `ClassificationResult(workflow_id=candidate, confidence=0.5, ...)` dönüşü. Hata yollarında `IntentClassificationError(intent_text, reason, details)` keyword-only constructor.

v7 delta (commit 5b): `_llm_classify` üçlüyü `governed_call(...)` tek-call ile değiştirir; cost-active DEĞİL (bypass-only). Tüm mevcut semantic korunur — `available_ids` prompt, `candidate in available_ids` validation, `ClassificationResult` dönüşü, `IntentClassificationError` keyword constructor + 4 reason (`llm_extra_missing`, `no_available_workflows`, `llm_transport_error`, `llm_invalid_response`).

Gerçek-kod uyumlu pseudo-code:

```python
def _llm_classify(self, input_text: str) -> ClassificationResult:
    """Delta (v7 iter-6 absorb): mevcut _llm_classify üçlüsünü
    governed_call(...) tek-call'a daraltır; cost bypass-only.
    """
    from ao_kernel.workflow.errors import IntentClassificationError
    try:
        from ao_kernel.llm import governed_call, resolve_route
    except ImportError as exc:
        raise IntentClassificationError(
            intent_text=input_text,
            reason="llm_extra_missing",
            details="llm_fallback requires ao-kernel[llm]",
        ) from exc
    
    available_ids = sorted(self._available_workflow_ids)
    if not available_ids:
        raise IntentClassificationError(
            intent_text=input_text,
            reason="no_available_workflows",
            details="no workflow ids registered for llm_fallback to choose from",
        )
    
    prompt = (
        f"Given the following intent text, return ONLY one of these "
        f"workflow IDs (nothing else): {', '.join(available_ids)}.\n\n"
        f"Intent: {input_text}\n\nWorkflow ID:"
    )
    messages = [{"role": "user", "content": prompt}]
    
    try:
        route = resolve_route(intent="FAST_TEXT")
        result = governed_call(
            messages=messages,
            provider_id=route.get("provider_id", "openai"),
            model=route.get("model", "gpt-4"),
            api_key=route.get("api_key", ""),
            base_url=route.get("base_url", ""),
            request_id="llm_fallback",
            # Bypass-only: cost + context kwargs all None
            session_context=None,
            workspace_root_str=None,
            profile=None,
            embedding_config=None,
            vector_store=None,
            workspace_root=None,
            run_id=None,
            step_id=None,
            attempt=None,
        )
    except Exception as exc:
        raise IntentClassificationError(
            intent_text=input_text,
            reason="llm_transport_error",
            details=str(exc),
        ) from exc
    
    # Status unwrap: governed_call rich dict (v5 iter-4 B1)
    status = result.get("status", "OK")
    if status != "OK":
        # CAPABILITY_GAP or TRANSPORT_ERROR → classify as llm_transport_error
        cause = result.get("error_code") or status
        raise IntentClassificationError(
            intent_text=input_text,
            reason="llm_transport_error",
            details=f"governed_call returned {status!r} (cause={cause!r})",
        )
    
    normalized = result.get("normalized") or {}
    candidate = (normalized.get("text") or "").strip()
    
    if candidate not in available_ids:
        raise IntentClassificationError(
            intent_text=input_text,
            reason="llm_invalid_response",
            details=f"LLM returned {candidate!r}, not in {available_ids}",
        )
    
    return ClassificationResult(
        workflow_id=candidate,
        workflow_version=None,
        confidence=0.5,  # LLM classification → lower confidence
        matched_rule_id="__llm_fallback__",
        match_type="llm_fallback",
    )
```

Key semantic preservations (v7 iter-6 absorb):
- Return type: `ClassificationResult(workflow_id, confidence=0.5, match_type="llm_fallback", ...)` — mevcut PR-A6 B4 kontratı korunur
- `available_ids` prompt gömme — model bu küme içinden birini döndürür
- `candidate in available_ids` doğrulaması — invalid response → `llm_invalid_response` reason
- `IntentClassificationError` 4 reason mevcut: `llm_extra_missing` / `no_available_workflows` / `llm_transport_error` / `llm_invalid_response` — hiçbiri kaldırılmaz
- `IntentClassificationError` keyword constructor `intent_text=..., reason=..., details=...` mevcut workflow/errors.py:334 imzasıyla uyumlu
- Cost-active DEĞİL: governed_call bypass (identity + ws kwargs None)
- CAPABILITY_GAP / TRANSPORT_ERROR → `llm_transport_error` reason mapping (classify as transport problem; downstream IntentClassificationError handling PR-A2 contract'ıyla uyumlu)

**Middleware helpers** (`ao_kernel/cost/middleware.py`):

```python
def pre_dispatch_reserve(*, workspace_root, run_id, step_id, attempt,
                         provider_id, model, prompt_messages, max_tokens,
                         policy) -> tuple[Decimal, PriceCatalogEntry]:
    # 1. catalog = load_price_catalog(ws)   [cached 300s]
    # 2. entry = find_entry(catalog, provider_id, model)
    #    if None: raise PriceCatalogNotFoundError
    # 3. est_in = count_prompt_tokens(prompt_messages, provider_id)
    # 4. est_out = estimate_output_tokens(est_in, max_tokens)
    # 5. est_cost = estimate_cost(entry, est_in, est_out)
    # 6. update_run(ws, run_id, mutator=reserve_mutator, max_retries=3):
    #      - Check run.budget.cost_usd is not None OR raise CostTrackingConfigError
    #      - Check remaining >= est_cost OR raise BudgetExhaustedError
    #      - record_spend(budget, cost_usd=est_cost, run_id=run_id)
    # 7. emit llm_cost_estimated (fail-open)
    # Returns (est_cost, entry) for post-dispatch use.

def post_response_reconcile(*, workspace_root, run_id, step_id, attempt,
                            provider_id, model, catalog_entry, est_cost,
                            raw_response_bytes, policy) -> None:
    # 1. usage = extract_usage_strict(raw_response_bytes)
    # 2. if usage.tokens_input is None OR usage.tokens_output is None:
    #    - event = SpendEvent(usage_missing=true, cost_usd=Decimal("0"))
    #    - record_spend(ws, event, policy)
    #    - emit llm_usage_missing (fail-open)
    #    - if policy.fail_closed_on_missing_usage: raise LLMUsageMissingError
    #    - else: warn-log; return
    # 3. actual = compute_cost(catalog_entry, usage.tokens_input, usage.tokens_output, usage.cached_tokens or 0)
    # 4. delta = actual - est_cost
    # 5. update_run(ws, run_id, mutator=reconcile_mutator, max_retries=3):
    #      - budget = record_spend(budget, cost_usd=delta, tokens_input=usage.tokens_input,
    #                              tokens_output=usage.tokens_output, run_id=run_id)
    # 6. event = SpendEvent(..., billing_digest=computed)
    # 7. record_spend(ws, event, policy)
    # 8. emit llm_spend_recorded (fail-open)
```

**Caller wire (v4 revize)**:

| Caller | Before | After |
|---|---|---|
| `client.py::llm_call` | inline capability + (build \| build_with_context) + execute + normalize | `governed_call(messages, ..., session_context=self._context (if _session_active else None), workspace_root_str=ws_str, profile=profile, embedding_config=self._embedding_config, vector_store=self._vector_store, workspace_root=self._workspace_root, run_id=..., step_id=..., attempt=...)`. Context-aware build preserved; capability + transport envelopes unchanged. Identity kwargs optional → cost bypass. |
| `mcp_server.py::handle_llm_call` | inline build + execute + normalize (no session context) | `governed_call(..., session_context=None, run_id=ao_run_id, step_id=ao_step_id, attempt=ao_attempt)`. MCP tool spec widen: 3 optional params `ao_run_id` (string uuid), `ao_step_id` (string), `ao_attempt` (integer minimum 1). Context injection MCP'de yok (pre-B2 durum korunur). |
| `workflow/intent_router.py` | inline build + execute + normalize | **v4 B3 absorb — bypass-only**: `governed_call(..., session_context=None, workspace_root=None, run_id=None, step_id=None, attempt=None)`. Cost-active DEĞİL (standalone classifier; workspace-run anchor yok). `IntentRouter._llm_classify` API widen edilmez. FAZ-C'de workflow-run'a bağlı classification senaryosu değerlendirilir. |
| `stream_request()` | Unchanged | Unchanged — cost FAZ-C deferred. İlk call process-başına `logger.warning(...)`. |

### 2.7 Normalizer strict

Plan v2 §2.7 korunur. `extract_usage_strict(resp_bytes) → UsagePresence(tokens_input, tokens_output, cached_tokens)` — None sentinel. `_internal/` additive helper.

### 2.8 Evidence Taxonomy

Plan v2 §2.8 korunur. +3 kind → 27 toplam. Emit site `governed_call` (ve middleware helpers).

## 3. Write Ordering (governed_call flow — v6 §2.6 ile hizalı)

```
[caller: client/mcp_server/intent_router]
    ↓ kwargs: messages + route info + context-aware (5) + identity (run_id, step_id, attempt, max_tokens) + workspace_root
[llm.governed_call]  (non-streaming only)
    ↓ 1. Capability check (check_capabilities)
    ↓    FAIL → return {"status": "CAPABILITY_GAP", "missing": [...], ...} envelope (transport + cost touching YOK)
    ↓
    ↓ 2. cost_active = all([workspace_root, run_id, step_id, attempt is not None]) AND load_cost_policy(ws).enabled
    ↓
    ↓ 3. Build request (context-aware branch):
    ↓    a. session_context is not None → req = build_request_with_context(..., injected_messages in return)
    ↓    b. else → req = build_request(...)
    ↓    effective_messages = req.get("injected_messages", messages)
    ↓
    ↓ 4. if cost_active:
    ↓    pre_dispatch_reserve(ws, run_id, step_id, attempt, provider, model, effective_messages, max_tokens, policy)
    ↓    - PriceCatalogNotFoundError / CostTrackingConfigError / BudgetExhaustedError (any → raise; transport ÖNCESİ)
    ↓    - emit llm_cost_estimated (fail-open)
    ↓    - budget CAS-reserved (update_run max_retries=3); returns (est_cost, catalog_entry)
    ↓
    ↓ 5. transport_result = execute_request(url, headers, body_bytes, ...)
    ↓
    ↓ 6. transport_result["status"] != "OK":
    ↓    return {"status": "TRANSPORT_ERROR", "error_code", "http_status", "elapsed_ms", ...} envelope
    ↓    (Cost reservation HOLDS; no refund — Q5 iter-1 policy.)
    ↓
    ↓ 7. normalized = normalize_response(transport_result["resp_bytes"], provider_id)
    ↓
    ↓ 8. if cost_active:
    ↓    post_response_reconcile(...)
    ↓    - extract_usage_strict
    ↓    - usage_missing path: record_spend (usage_missing=true) → emit llm_usage_missing → raise LLMUsageMissingError (or warn)
    ↓    - success path: compute actual → reconcile CAS (update_run max_retries=3) → record_spend (billing_digest) → emit llm_spend_recorded
    ↓    (All emits fail-open; ledger failure fail-closed.)
    ↓
    ↓ 9. RETURN rich dict (v5 iter-4 B1):
    ↓    {"status": "OK", "normalized": normalized, "resp_bytes": bytes, "transport_result": dict, "elapsed_ms": int, "request_id": str}
```

**Caller (client.py/mcp_server.py) success path unwrap** (v6 pattern):
```python
result = governed_call(..., workspace_root=..., run_id=..., step_id=..., attempt=...)
if result["status"] == "CAPABILITY_GAP":
    return result  # envelope as-is
if result["status"] == "TRANSPORT_ERROR":
    return result  # envelope as-is
# status == "OK"
normalized = result["normalized"]
resp_bytes = result["resp_bytes"]
transport_result = result["transport_result"]
elapsed_ms = result["elapsed_ms"]
# decision extraction + scorecard + telemetry caller's existing pattern
```

**Fail-closed anchors**:
- pre-dispatch: catalog miss, config error (cost_usd missing), budget exhausted → BEFORE transport
- post-response: ledger append failure → SpendLedgerCorruptedError / SpendLedgerDuplicateError; usage-missing + fail_closed_on_missing_usage=true → raise AFTER ledger append

**Fail-open**: all 3 evidence emit sites (wrapped via _safe_emit).

**CAS retry**: `update_run(ws, run_id, mutator=..., max_retries=3)` both in reserve and reconcile. Exhaustion → `WorkflowCASConflictError` propagates.

## 4. DAG — 7-commit Shipping Structure (squash-on-merge, v3 revize)

Plan v2 6 commit'ten commit 5 split önerisi absorbe edildi: **5a core + 5b plumbing**.

1. **Commit 1: prep — errors + cost_math + policy loader + schema widens** (~480 LOC)
   - `cost/errors.py` (9 types — +CostTrackingConfigError)
   - `cost/cost_math.py`
   - `cost/policy.py`
   - `policy-cost-tracking.schema.v1.json` update (+2 knobs)
   - `spend-ledger.schema.v1.json` update (+attempt, +usage_missing, +billing_digest)
   - Tests: `test_cost_math.py` (~18), `test_cost_policy.py` (~15)

2. **Commit 2: catalog loader + checksum + stale gate** (~350 LOC)
   - `cost/catalog.py` (unconditional loader + LRU 300s)
   - Tests: `test_cost_catalog.py` (~20)

3. **Commit 3: ledger + canonical billing digest + idempotency** (~400 LOC)
   - `cost/ledger.py` (digest + bounded scan + corrupt guard)
   - Tests: `test_cost_ledger.py` (~25)

4. **Commit 4: Budget widen + normalizer strict + schema delta** (~500 LOC)
   - `workflow/budget.py` delta (+tokens_input, +tokens_output, writer invariant, reader back-compat)
   - `workflow-run.schema.v1.json` delta (+2 axis inline)
   - `llm_response_normalizer.py` delta (+extract_usage_strict, +UsagePresence)
   - Tests: `test_workflow_budget_axes.py` (~22), `test_normalizer_usage_strict.py` (~12)

5. **Commit 5a: middleware core + governed_call + evidence +3** (~650 LOC)
   - `cost/middleware.py` (pre_dispatch_reserve + post_response_reconcile)
   - `llm.py` delta (+governed_call wrapper ~200 LOC)
   - `evidence_emitter.py` delta (+3 kinds → 27)
   - `cost/__init__.py` (public API)
   - Tests: `test_cost_middleware_core.py` (~20 — bypass, enabled success, budget exhaust, catalog miss, config error, usage missing, CAS retry, digest path)

6. **Commit 5b: entrypoint plumbing** (~400 LOC)
   - `client.py` delta (llm_call non-stream branch → governed_call + identity kwargs optional + success dict unwrap; stream=True branch UNCHANGED)
   - `mcp_server.py` delta (handle_llm_call → governed_call + `ao_run_id/ao_step_id/ao_attempt` MCP tool widen + success dict unwrap)
   - `workflow/intent_router.py` delta (governed_call **bypass-only**: session_context=None, workspace_root=None, run_id=None, step_id=None, attempt=None; `_llm_classify` API unchanged)
   - Tests: `test_cost_entrypoint_plumbing.py` (~18):
     - `test_client_llm_call_nonstream_cost_active`
     - `test_client_llm_call_nonstream_cost_bypass`
     - `test_client_llm_call_stream_untouched` (regression — mevcut `_execute_stream` path)
     - `test_client_capability_gap_envelope_preserved`
     - `test_client_transport_error_envelope_preserved`
     - `test_mcp_handle_llm_call_ao_identity_params`
     - `test_mcp_transport_error_envelope_preserved`
     - `test_intent_router_bypass_only` (identity always None, cost-active değil)
     - ...

7. **Commit 6: docs + CHANGELOG** (~140 LOC)
   - `docs/COST-MODEL.md` runtime notes §4-§7 + §8 identity threading + §9 streaming deferred + §10 migration guide
   - `CHANGELOG.md [Unreleased]` PR-B2 entry

**Rationale** (Codex iter-2 absorb):
- Commit 5a = **core behavior** (middleware + facade + evidence) tek logical unit
- Commit 5b = **entrypoint plumbing** (caller wire + MCP schema widen) ayrı concern; review noise azaltılır
- Her commit bağımsız test edilir (green at HEAD)
- Commit 5a en yoğun (650 LOC) ama caller wire olmadan bile middleware çalışır (kendi test fixture'ları)

## 5. Acceptance Checklist (v3)

### Dormant gate (caller-level)

- [ ] `load_price_catalog()` unconditional (bundled fallback)
- [ ] `load_cost_policy()` dormant → `CostTrackingPolicy(enabled=False)` (no raise)
- [ ] `governed_call(...)` with identity kwargs None → bypass (build → execute → normalize only)
- [ ] `governed_call(...)` with all identity + policy.enabled=false → bypass
- [ ] Bypass path → 0 evidence emit, 0 ledger write, 0 budget mutation

### Catalog (plan v2 korunur)

- [ ] Bundled loads + schema ok
- [ ] Workspace override preempts bundled
- [ ] Inline `override=` preempts filesystem
- [ ] Checksum mismatch → `PriceCatalogChecksumError`
- [ ] `strict_freshness=false` + stale → warn, catalog döner
- [ ] `strict_freshness=true` + stale → `PriceCatalogStaleError`
- [ ] Empty entries → `ValidationError`
- [ ] `source=vendor_api` + missing vendor_model_id → `ValidationError`
- [ ] LRU: 2 calls → 1 disk read; 301s sonra → 2 disk read

### Cost math

- [ ] `compute_cost` formula exact (Decimal stable)
- [ ] Cached discount / fallback
- [ ] `estimate_cost` ignores caching
- [ ] `estimate_output_tokens(est_in, max_tokens)` = `min(max_tokens, est_in * 0.25)` when both
- [ ] `estimate_output_tokens(est_in, None)` = `est_in * 0.25`

### Ledger

- [ ] First record_spend creates spend.jsonl
- [ ] Same `(run_id, step_id, attempt)` + same digest → no-op warn
- [ ] Same key + different digest → `SpendLedgerDuplicateError`
- [ ] Corrupt JSONL line → `SpendLedgerCorruptedError`
- [ ] Each event schema-validated
- [ ] `billing_digest` persisted

### Budget (BudgetAxis widen — B3 invariant pin)

- [ ] Legacy record (`tokens` only): reader → `tokens_input = BudgetAxis(same)`, `tokens_output = None`
- [ ] Record with all 3: granular used, aggregate recomputed sanity (mismatch warn-log)
- [ ] Writer: `tokens_input` ALWAYS emitted when B2 pipeline active
- [ ] Writer: `tokens_output=None` → OMIT (key absent, no `null`)
- [ ] Writer: aggregate ALWAYS emitted = tokens_input + (tokens_output or 0)
- [ ] `record_spend(tokens_input=100, tokens_output=50)` → aggregate += 150 auto
- [ ] `record_spend(tokens=150, tokens_input=100)` → ValueError (double-count guard)
- [ ] Decimal precision roundtrip

### Normalizer strict

- [ ] `extract_usage_strict` full usage → all int
- [ ] `extract_usage_strict` missing `input_tokens` → `tokens_input=None`
- [ ] `extract_usage_strict` no usage dict → all None
- [ ] `extract_usage_strict` non-JSON → all None
- [ ] Original `extract_usage` unchanged (PR-A regression)

### Middleware + governed_call (integration)

- [ ] Bypass (identity None): transport executed, no cost hooks
- [ ] Enabled + sufficient budget + cost_usd axis present:
  - llm_cost_estimated emitted
  - budget CAS-updated (update_run max_retries=3)
  - transport executed
  - actual computed, reconciled
  - record_spend with billing_digest
  - llm_spend_recorded emitted
- [ ] Enabled + budget.cost_usd is None → `CostTrackingConfigError` BEFORE transport (B2 Option A)
- [ ] Budget insufficient pre-dispatch → `BudgetExhaustedError` BEFORE transport
- [ ] Catalog missing entry → `PriceCatalogNotFoundError` BEFORE transport
- [ ] Usage missing + `fail_closed_on_missing_usage=true` → `LLMUsageMissingError`; ledger `usage_missing=true`; llm_usage_missing emitted
- [ ] Usage missing + `fail_closed_on_missing_usage=false` → warn-log; ledger entry; no raise
- [ ] CAS conflict x3 → `WorkflowCASConflictError` propagates (no wrap)
- [ ] Transport error mid-call → reservation HOLDS (no refund)

### Caller wire (v4 revize — identity threading + envelope preserve)

- [ ] `client.llm_call(run_id=..., step_id=..., attempt=..., max_tokens=...)` → governed_call cost-active
- [ ] `client.llm_call()` (no identity) → governed_call cost-bypass
- [ ] **v4 B2 absorb — `client.llm_call` capability gap envelope korunur** (`{"status": "CAPABILITY_GAP", "missing": [...], ...}`; test `test_client.py::test_capability_gap_preserved` regression)
- [ ] **v4 B2 absorb — `client.llm_call` transport error envelope korunur** (`{"status": "TRANSPORT_ERROR", "error_code", "http_status", "elapsed_ms", ...}`; test regression)
- [ ] **v4 B1 absorb — `client.llm_call` session-active context injection korunur**: `_session_active=True` + `_context` set → `build_request_with_context` path; normalized response decision-extracted ve scorecard'lı döner (mevcut post-call pipeline dokunulmaz)
- [ ] `mcp_server.handle_llm_call(ao_run_id=..., ao_step_id=..., ao_attempt=..., workspace_root=...)` → cost-active (4 kwarg hepsi non-None zorunlu; eksik biri → bypass)
- [ ] **v4 B2 absorb — `mcp_server.handle_llm_call` transport error envelope korunur** (mevcut shape preserved)
- [ ] MCP tool schema lists 3 new optional params (`ao_run_id`, `ao_step_id`, `ao_attempt`)
- [ ] **v4 B3 absorb — `intent_router` cost-bypass-only**: `governed_call(..., run_id=None, step_id=None, attempt=None)`; `_llm_classify` API unchanged; standalone classifier workflow-run budget anchor'ı değil
- [ ] **v7 iter-6 absorb — `intent_router._llm_classify` gerçek kod semantic preserved**: return type `ClassificationResult(workflow_id, confidence=0.5, match_type="llm_fallback")`; `available_ids` prompt gömme; `candidate in available_ids` doğrulaması; 4 `IntentClassificationError` reason korundu (`llm_extra_missing` / `no_available_workflows` / `llm_transport_error` / `llm_invalid_response`); CAPABILITY_GAP / TRANSPORT_ERROR → `llm_transport_error` reason mapping; keyword-only constructor `intent_text=..., reason=..., details=...`
- [ ] `stream_request()` dokunulmadı; first call process başına warning log
- [ ] **v5 B2 absorb — `client.llm_call(stream=True)` mevcut `_execute_stream` yolu bozulmadı** (regression test `test_client_llm_call_stream_untouched`); governed_call stream=True kabul etmez
- [ ] **v5 B4 absorb — `build_request_with_context` return dict'te `injected_messages` field'ı bulunur** (context-injected effective messages; `session_context=None` durumda raw messages veya absent); governed_call cost estimate bu field'ı okur

### Schema widen regression

- [ ] Legacy workflow-run without tokens_input/tokens_output → loader ok
- [ ] Legacy spend.jsonl without attempt/usage_missing/billing_digest → B2 tools parse ok
- [ ] Policy `fail_closed_on_missing_usage` defaults true
- [ ] Policy `idempotency_window_lines` defaults 1000

### Evidence

- [ ] `_KINDS` = 27
- [ ] 3 new kinds documented
- [ ] Emit failure (disk full mock) → cost path continues (fail-open)

## 6. Risk Register (v3)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **R1**: Bounded scan miss retries | Medium | Low-Med | policy.idempotency_window_lines knob |
| **R2**: CAS retry exhausted | Low-Med | Medium | max_retries=3; caller gets WorkflowCASConflictError |
| **R3**: Stale catalog strict=false → silent overrun | Medium | Medium | Warn every call |
| **R4**: Adapter model string mismatch → catalog miss | Low | High | PriceCatalogNotFoundError; test coverage |
| **R5**: v3.1.0→v3.2.0 upgrade | Low-Med | High | Additive schema + back-compat reader; policy dormant default |
| **R6**: Ledger unbounded growth | Medium | Medium | FAZ-B follow-up rotation |
| **R7**: Estimate overshoot → false BudgetExhausted | Medium | Low | max_tokens caller kwarg + conservative 25% |
| **R8**: `.ao/cost/` perms | Low | Medium | mkdir(mode=0o700) |
| **R9**: Normalizer strict contract leak | Low | Low | Additive helper; both paths unit-tested |
| **R10**: 3-caller identity threading inconsistency | Medium | Medium | Integration test each caller × identity var/yok |
| **R11**: Streaming user expects cost | Medium | Low | CHANGELOG + docs §9; warn log first call |
| **R12**: MCP `ao_` param schema drift | Low | Low | Tool spec documented |
| **R13** (NEW v3): Operator policy.enabled=true forgets cost_usd axis | Medium | Medium | `CostTrackingConfigError` fail-closed on first run; docs §10 migration step |
| **R14** (NEW v3): governed_call signature drift from 3 callers | Medium | High | Strict kwargs-only; caller tests assert exact kwargs forwarded |

## 7. Codex iter-2 Plan-Time Absorb Summary

| iter-2 finding | v3 absorption | Plan section |
|---|---|---|
| B1 execute_request signature pin | REPLACED: governed_call wrapper helper; build/execute/normalize primitives untouched | §2.6 |
| B2 cost_usd axis optionality | Option A pinned: policy.enabled=true + cost_usd is None → CostTrackingConfigError | §0, §2.6, R13 |
| B3 Aggregate/granular writer invariant | tokens_output=None → OMIT (absent); aggregate always emitted; no $defs refactor (inline) | §0, §2.5 |
| Temizlik: WorkflowRunConcurrentMutationError | Silindi; mevcut WorkflowCASConflictError + update_run(max_retries=3) | §0, §2.6 middleware |
| Q1 Streaming messaging | Sessiz bypass + docs + process-başı warning log | §10 (below) |
| Q2 MCP `ao_` prefix | Absorbed | §2.6 caller wire |
| Q3 CAS retry max 3 fixed | Absorbed; existing update_run helper | §2.6 middleware |
| Q4 Aggregate timing | §2.5 writer invariant exact | §2.5 |
| Q5 cached_tokens silent OK | Absorbed | §2.6 reconcile |
| Commit 5 split 5a core + 5b plumbing | DAG 6 → 7 commit | §4 |

## 8. Audit Trail

### CNS iterations

| Iter | Date | Verdict | Absorbed |
|---|---|---|---|
| pre-plan | 2026-04-17 | N/A | CNS-030 strategic review; 4 Q2 blockers |
| v1 → iter-1 | 2026-04-17 | REVISE | CNS-031 iter-1: Budget shape + 4 callers + normalizer + digest |
| v2 → iter-2 | 2026-04-17 | REVISE-AGAIN | CNS-031 iter-2: execute_request signature + cost_usd optionality + writer invariant + commit split |
| v3 → iter-3 | 2026-04-17 | REVISE-AGAIN (dar scope) | CNS-031 iter-3: client context path + wrapper return contract + intent_router auto-fill |
| v4 → iter-4 | 2026-04-17 | REVISE-AGAIN (çok dar, contract-level) | CNS-031 iter-4: governed_call success return + streaming boundary + commit 5b tutarsızlık + build_request_with_context injected_messages |
| v5 → iter-5 | 2026-04-17 | PARTIAL | CNS-031 iter-5: intent_router unwrap/mapping blocker + §3 hizalama + MCP acceptance workspace_root |
| v6 → iter-6 | 2026-04-17 | PARTIAL | CNS-031 iter-6: §2.6.1 pseudo-code intent_router gerçek koduyla uyumsuz (constructor alanları + available_ids prompt + ClassificationResult + IntentClassificationError keyword constructor) |
| v7 → iter-7 | TBD | TBD | v7 submit (same thread) — gerçek kod uyumlu pseudo-code rewrite |

### Plan revision history

| Version | Date | Change |
|---|---|---|
| v1 | 2026-04-17 | Initial; CNS-030 4 blockers absorb; 5-commit DAG; ~2210 LOC |
| v2 | 2026-04-17 | CNS-031 iter-1 absorb: BudgetAxis widen + 4-caller hook + normalizer strict + digest idempotency; 6-commit; ~3335 LOC |
| v3 | 2026-04-17 | CNS-031 iter-2 absorb: governed_call wrapper (new surface), Option A cost_usd config error, writer invariant pin (no $defs refactor), commit 5 split; 7-commit; ~3515 LOC |
| v4 | 2026-04-17 | CNS-031 iter-3 absorb: governed_call signature widen (5 context-aware kwargs), caller envelope preserve (CAPABILITY_GAP + TRANSPORT_ERROR), intent_router cost-bypass-only; delta ~180 LOC; 7-commit DAG; ~3695 LOC toplam |
| v5 | 2026-04-17 | CNS-031 iter-4 absorb: governed_call success rich dict + streaming boundary pin + commit 5b tutarsızlık temizle + build_request_with_context injected_messages additive; delta ~60 LOC (contract-level); 7-commit DAG; ~3755 LOC toplam |
| v6 | 2026-04-17 | CNS-031 iter-5 absorb: intent_router unwrap/error mapping pseudo-code pin (§2.6.1 new) + §3 Write Ordering §2.6 hizalama + §5 MCP acceptance workspace_root şartı; delta ~85 LOC (doc-level precision); 7-commit DAG; ~3840 LOC toplam |
| v7 | 2026-04-17 | CNS-031 iter-6 absorb: §2.6.1 pseudo-code'u gerçek intent_router.py:319-397 + workflow/errors.py:324-344 ile uyumlu yeniden yaz (available_ids prompt + resolve_route + ClassificationResult + IntentClassificationError keyword constructor); delta ~80 LOC; 7-commit DAG; ~3920 LOC toplam |

### B3 stabilization gate (Q10 iter-1)

- B2 merge → 48h CI green smoke window → B3 branch

## 9. Remaining Questions for Codex iter-3

Plan v2'den onaylanmış korunanlar (Q4 rotation, Q5 reservation, Q9 ledger→evidence→raise; Q1-Q5 iter-2) → v3'te hâlâ geçerli. Yeni soru yok.

**Tek explicit iter-3 kararı bekleniyor**: v3 AGREE / ready_for_impl true?

Plan v2'den kalan alt sorular (iter-2'de blocker değildi; v3'te çözüldü):
- Streaming messaging: §10 sessiz bypass pinlendi
- MCP prefix: §2.6 `ao_` pinlendi
- CAS retry: §2.6 fixed 3 pinlendi (existing helper)
- Aggregate timing: §2.5 writer invariant pinlendi
- cached_tokens: §2.6 silent OK pinlendi

## 10. Resolved Positions (v3 lock)

Impl başlarken aşağıdakiler kararlaştı; yeniden açılmaz:

1. **Integration pattern**: yeni `llm.governed_call()` wrapper, `execute_request` etrafı DEĞİL
2. **cost_usd axis**: policy.enabled=true ise zorunlu; yoksa `CostTrackingConfigError`
3. **Writer invariant**: `tokens_output=None` → OMIT; aggregate HER ZAMAN yazılır
4. **CAS retry**: `update_run(max_retries=3)`; yeni error yok
5. **Streaming**: v3.2.0 cost dışı; CHANGELOG + docs §9 + process-başı warning log
6. **MCP param naming**: `ao_run_id`, `ao_step_id`, `ao_attempt` (optional MCP tool params)
7. **cached_tokens**: None → silent OK; `usage_missing` sadece tokens_input/tokens_output None
8. **Commit DAG**: 7 commit (5a core + 5b plumbing split)
9. **Schema delta style**: inline additive; no `$defs/budget_axis` refactor
10. **Ledger rotation**: scope-out (FAZ-B follow-up); cost_usd `$defs/budget_axis` refactor YOK
11. **v4 — `governed_call` error envelopes**: CAPABILITY_GAP + TRANSPORT_ERROR caller-ready envelope döner; cost errors raise (caller propagate veya try/except)
12. **v4 — Context-aware build path**: `session_context` varsa `build_request_with_context(...)` (full PR-A context pipeline), aksi `build_request(...)` plain; `effective_messages` cost estimate input
13. **v4 — `intent_router` cost-bypass-only**: B2 scope'unda API widen YOK; `IntentRouter._llm_classify` dokunulmaz; FAZ-C'de workflow-run anchor değerlendirilir
14. **v5 — Streaming boundary**: `governed_call` non-streaming only; `client.llm_call(stream=True)` mevcut `_execute_stream` yolunda kalır; streaming cost tracking FAZ-C scope
15. **v5 — `governed_call` success return rich dict**: `{status=OK, normalized, resp_bytes, transport_result, elapsed_ms, request_id}`; caller post-processing (decision extract, scorecard, telemetry) caller'da kalır, duplicate edilmez
16. **v5 — `build_request_with_context` additive `injected_messages` return field**: context-injected effective messages; `governed_call` cost estimate input. Backward compat: pre-B2 caller'lar absent bırakır

---

**Next step**: kullanıcı onayı → Codex MCP thread `019d9aa8` aynı thread üzerinden `codex-reply` ile iter-3 submit. Beklenen verdict: AGREE / ready_for_impl=true (3 blocker tamamen gerçek-kod dayanaklı absorbe; yeni surface karar alındı; Q cevapları locked).
