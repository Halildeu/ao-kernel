# FAZ-C Master Plan v5 — Runtime Closure (v3.3.0)

## v5 absorb summary (Codex iter-5 PARTIAL — 3 C3 blocker + 3 warning)

Iter-5 verdict: C1a/C2/C4 validated ("notes" bölümünde teyit) + 3 yeni C3 blocker + 3 warning. Fact-check: `cost/ledger.py:238-329` (file_lock + scan_tail + digest check sequence), `agent-adapter-contract.schema.v1.json:341-349` (envelope wire format: `cost_actual.tokens_input/tokens_output`, not `usage.*`), `fixtures/codex_stub.py:96-100` (envelope sample confirmation), `executor/evidence_emitter.py:115-145` (`_KINDS` whitelist).

| # | iter-5 bulgu | v5 fix |
|---|---|---|
| **B1** | C3 idempotency sırası bozuk — `update_run(mutator)` then `record_spend(event)` dizisi same-digest ikinci çağrıda budget'ı 2× düşürür (mutator önce drain, ledger sonra "already recorded" der). `test_adapter_reconcile_idempotency.py` beklentisi "single budget drain" sağlanmaz. | C3 v5 atomic order: **ledger lock + duplicate check ÖNCE, budget drain SONRA**. `post_adapter_reconcile` içinde `file_lock(ledger_lock_path)` tek kritik bölge açar; içeride sırasıyla (a) `_scan_tail + _find_duplicate`, (b) same-digest → silent warn + return (budget dokunulmaz), (c) different-digest → `SpendLedgerDuplicateError`, (d) yeni kayıt → `update_run(mutator)` budget drain + `_append_with_fsync` ledger append. `record_spend` fonksiyonunun kendi lock'una gerek yok (bypass edilir); `_scan_tail` + `_append_with_fsync` helper'ları reuse edilir (`cost/ledger.py:164-235`). |
| **B2** | C3 yeni `adapter_spend_recorded` evidence kind'ı için `_KINDS` bump planı eksik. C4 `route_cross_class_downgrade` için 27→28; C3 ayrı kind bump ederse 28→29 cascade gerek. | C3 v5 karar: **mevcut `llm_spend_recorded` kind'ı reuse et**. Event payload'una `source: "adapter_path" \| "llm_call"` discriminator field'ı eklenir (backwards-compat: field yoksa "llm_call" varsayılır). `_KINDS` C3'te bump edilmez; C4'te 27→28 tek bump. Daha az schema churn + metric derivation B5'te mevcut histogram reuse edilir. |
| **B3** | C3 `_build_adapter_spend_event` wire format yanlış — plan "envelope.usage (tokens_input/output)" diyor, ama adapter contract `agent-adapter-contract.schema.v1.json:341-349` tokens'ı `cost_actual.tokens_input/tokens_output` altında taşıyor. | C3 v5 builder spec düzeltildi: `tokens_input = envelope.cost_actual.tokens_input`, `tokens_output = envelope.cost_actual.tokens_output`, `cost_usd = envelope.cost_actual.cost_usd`, `cached_tokens = envelope.cost_actual.cached_tokens` (optional). Envelope'ta `cost_actual` hiç yoksa → `usage_missing=True`, `tokens_{in,out}=0`, `cost_usd=Decimal(0)` audit-only path. Kaynak schema path plan §C3'te explicit yazıldı. |

### v5 absorb warnings

- **W1** (iter-5): C4 `route_cross_class_downgrade` evidence event emit site'ı `resolve_route` içinden YAPILMAZ (stateless, run_id yok). `resolve_route` return dict'e `downgrade_applied: bool` + `original_class: str` + `downgraded_class: str` alanları eklenir; caller (`governed_call` / `multi_step_driver._run_llm_step` gibi run-aware) bu flag'leri görürse `emit_event(run_id, 'route_cross_class_downgrade', ...)` çağırır. §C4 scope'ta emit site açıklaması eklendi.
- **W2** (iter-5): Revision history stale sections — §v3 absorb summary + §v2 absorb summary + §table + §C1a detail bloklarının başlarına **"⚠️ SUPERSEDED — historical; v5 current"** notu eklendi. Tarihi koruma + implementer doğru bölüme yönlendirme.
- **W3** (iter-5): C3 `catalog_entry` provenance netleştirildi: `post_adapter_reconcile` içinde on-demand `load_catalog(workspace_root) + get_entry(provider_id, model)` lookup yapılır. Catalog entry yoksa (yeni/bilinmeyen model) → `vendor_model_id=None`, `usage_missing` davranış mirror; audit-only path. Signature `catalog_entry` parametre yerine `provider_id + model` alır; lookup middleware içindedir.

---

## v4 absorb summary (Codex iter-4 PARTIAL — 4 blocker + 3 warning) — ⚠️ SUPERSEDED by v5

Gerçek kod okumasıyla v3 spec'teki 4 hata giderildi (Codex iter-4 citation doğrulaması: `ao_kernel/cost/ledger.py:63-91`, `ao_kernel/cost/middleware.py:202-437`, `ao_kernel/llm.py:23-46`, `ao_kernel/executor/policy_enforcer.py:90-170, 302-329`, `ao_kernel/executor/executor.py:294-307`).

| # | v3 bulgu | v4 fix |
|---|---|---|
| **B1** | C3 SpendEvent önerisi gerçek şema ile uyumsuz — plan "model_id/time_seconds/timestamp" kullanıyordu; gerçek şema token-based: `{run_id, step_id, attempt, provider_id, model, tokens_input, tokens_output, cost_usd, ts, vendor_model_id?, cached_tokens?, usage_missing, billing_digest}` (`cost/ledger.py:63-91`). `record_spend_event` helper gerek yok — mevcut `record_spend(workspace_root, event, *, policy)` zaten event-based API. | C3 body'de yeni helper iddiası silindi. Mevcut `SpendEvent` dataclass + `record_spend` kullanılır. Adapter path için envelope → `SpendEvent` builder: `cost.middleware._build_adapter_spend_event(envelope, run_id, step_id, attempt, catalog_entry)` fonksiyonu envelope.cost_actual + usage'i okuyup `SpendEvent` üretir. Helper yeri `cost/middleware.py`, post-adapter reconcile path'iyle aynı modülde. |
| **B2** | C3 bütçe drenajı yalnız `record_spend` ile olmaz — ledger append bütçeyi azaltmaz; gerçek path (`post_response_reconcile`, `cost/middleware.py:219-437`) üçlü: `update_run(mutator=_reconcile_mutator)` + `record_budget_spend(cost_usd=delta)` + `record_spend(event)`. | C3 scope'a yeni middleware: `post_adapter_reconcile(*, workspace_root, run_id, step_id, attempt, provider_id, model, envelope, policy)` — `post_response_reconcile` pattern'ini mirror eder: `update_run(mutator=_adapter_reconcile_mutator)` (budget.cost_usd axis drenajı `record_budget_spend(cost_usd=envelope.cost_usd)` üzerinden) + `record_spend(event, policy)` ledger append + `_safe_emit("adapter_spend_recorded")`. Tanım yeri `cost/middleware.py`. Çağrı sitesi `executor/executor.py::invoke_cli/invoke_http` dönüşünde (envelope `cost_actual.cost_usd` mevcutsa). |
| **B3** | C2 `resolve_allowed_secrets()` widen yanlış katman — resolver `allowlist_secret_ids` secret-only; `env_allowlist.allowed_keys` passthrough `build_sandbox()` içinde farklı semantikle çalışıyor. İkisini resolver'da birleştirmek audit riski. | C2 fix caller'a taşındı: `multi_step_driver._run_adapter_step`'te `parent_env = {k: os.environ[k] for k in (set(policy.secrets.allowlist_secret_ids) \| set(policy.env_allowlist.allowed_keys)) if k in os.environ}`. Bu `parent_env` hem `resolve_allowed_secrets(policy, parent_env)` hem `build_sandbox(..., parent_env=parent_env)` çağrılarına beslenir. Resolver secret-only (allowlist_secret_ids) kalır; sandbox env passthrough `env_allowlist.allowed_keys` üzerinden. `resolve_allowed_secrets()` + `build_sandbox()` signature'ları DOKUNULMAZ. |
| **B4** | C4 `resolve_route` widen önerisi `(provider_pref, kind, *, cross_class_downgrade, soft_degrade)` — mevcut imza (`llm.py:23-29`) `(*, intent, perspective, provider_priority, workspace_root)` ile 4 caller'ı kırar (`mcp_server.py:150, 353`, `client.py:842`, `intent_router.py:364`). | C4 additive: mevcut keyword-only imza DOKUNULMAZ. Yeni opsiyonel kwarg'lar eklenir — `budget_remaining: Budget \| None = None`, `cross_class_downgrade: bool = False` (runtime-only knob), `soft_degrade: bool = False`. Default-off → mevcut callers etkilenmez. Internal `resolve()` (`_internal/prj_kernel_api/llm_router.py`) yeni kwarg'ları tüketir: `budget_remaining + cross_class_downgrade` aktifse `soft_degrade.rules` iterate. `_KINDS` 27→28 `route_cross_class_downgrade` kind eklenir (v3'teki gibi korunur). |

### v4 absorb warnings

- **W1** (iter-4): **Plan dosyası workspace'te gerçekten v4'e güncellendi** — iter-3/iter-4 absorption artık prompt-only değil dosyaya yansıdı (`.claude/plans/FAZ-C-MASTER-PLAN.md`).
- **W2** (iter-4): C5 impl-time C4'ten bağımsız. Sadece `docs/POLICY-SIM.md`'deki `cross_class_downgrade` knob dokümantasyonu C4 merge sonrası anlamlı. Merge sırası: C4 → C5 (dokümantasyon için); impl paralel olabilir.
- **W3** (iter-4): LOC tahmini revise — C3 yeni middleware (adapter reconcile + envelope→SpendEvent builder + evidence emit) + C4 facade additive kwarg + test'ler hesaba katılınca ~6000-6500 LOC (5500 iyimserdi).

---

## v3 absorb summary (Codex iter-2 PARTIAL — 2 blocker + 3 warning) — ⚠️ SUPERSEDED by v5

| # | v2 bulgu | v3 fix |
|---|---|---|
| **B1** | C3 `record_spend(idempotency_key=...)` state tutamaz — `Budget` dataclass ve `workflow-run.schema.v1.json::$defs/budget` `additionalProperties: false`; silent noop için key hafızası yok | **C3 scope yeniden**: idempotency **budget değil `ao_kernel.cost.ledger` katmanında** — `SpendLedgerDuplicateError` zaten mevcut (canonical billing_digest). Transport-level `_spend_cost` `cost.ledger.record_spend_event` çağırır; duplicate = silent warn. Budget dataclass/schema DOKUNULMAZ. |
| **B2** | C2 real full mode driver `parent_env={}` sabit (`multi_step_driver.py:467-476`); `resolve_allowed_secrets` host env okur ama driver dolduramaz | **C2 scope'a explicit driver parent_env plumbing**: `multi_step_driver._run_adapter_step` `os.environ`'un `policy.env_allowlist.allowed_keys` subset'ini `parent_env` olarak geçir. Sandbox allowlist zaten filtreliyor; driver tedarik katmanı eksikti |

### v3 absorb warnings

- **W1**: C4 public facade widen **explicit** eklendi — `ao_kernel.llm.resolve_route` signature genişleme + internal mapping; mcp_server + client call sites update.
- **W2**: C4 `_KINDS` bump 27→28 docs update — `docs/POLICY-SIM.md:49-51` exact-count metni C4 scope'a eklendi.
- **W3**: C1 patch fallback tek kanonik surface **`step_record.output_ref`**; `invocation_result.diff` terimi v3'te kaldırıldı.

---



**Hedef release**: **v3.3.0**. Scope: FAZ-B'den sarkan runtime gap'leri kapatmak. Capability expansion (C7) **v3.4.0'a ertelendi** (Codex iter-1 W/Q6 absorb).

**Base SHA**: `e16e8d8` (B7.1 merged). B7.1 zaten main'de; **v3.2.1 tag atlandı** — B7.1 entry v3.3.0 CHANGELOG'una dahil (Codex Q1 absorb — release tax azalt).

**4 workstream / 8 PR target / ~7-8 hafta**. C1 v1'de tek PR idi → v2'de **C1a + C1b split** (Codex blocker 2).

---

## v2 absorb summary (Codex CNS-20260418-041 iter-1 REVISE — 6 blocker + 5 warning) — ⚠️ SUPERSEDED by v5

| # | v1 bulgu | v2 karar |
|---|---|---|
| B1 | `Executor(policy_loader=...)` **zaten var** (`executor.py:83-109`). C1 "new surface" yanlış. Gerçek eksik: (a) `tests/_driver_helpers.build_driver` forward etmez, (b) patch artifact zinciri (`step_record.output_ref` persist), (c) context-pack materialisation | C1 split: **C1a altyapı PR** (driver helper forward + adapter output_ref guarantee + context_compile materialisation) + **C1b üstüne full bundled bugfix E2E** |
| B2 | `_load_pending_patch_content()` sadece `record.intent.payload.patches[step_name]` okuyor; adapter-path `output_ref` garanti değil (`docs/BENCHMARK-SUITE.md:69-70`) | C1a: ExecutionResult `output_ref` adapter path'te populate + `_load_pending_patch_content()` fallback order (`patches[]` → `step_record.output_ref` adapter diff resolve) |
| B3 | `Executor.run_step()` input_envelope sadece `task_prompt + run_id`; `context_compile` stub `.ao/runs/{run_id}/context.md` üretmiyor. `claude-code-cli` / `gh-cli-pr` manifestleri full-flow'da kırılır | C1a scope: `context_compile` gerçek dosya üretimi + `context_pack_ref` resolver |
| B4 | `workflow.budget.record_spend` duplicate koruması YOK (`workflow/budget.py:184-275`). C3 benchmark shim'den önce idempotency key tasarımı şart | C3 önce idempotency key: `(run_id, step_id, attempt, spend_kind)` tuple; record_spend caller-supplied idempotency_key yeni argüman; double-call sessiz noop |
| B5 | `soft_degrade` sadece JSON'da, runtime tüketmez (`llm_resolver_rules.v1.json:25-30`). C4 target modül `ao_kernel.llm_router` yanlış — gerçek resolver `ao_kernel._internal.prj_kernel_api.llm_router.resolve`; public facade `ao_kernel.llm.resolve_route` | C4 scope: soft_degrade runtime'a taşı + modül adı netleşir + test'te public surface çağrısı |
| B6 | C7 vision/audio runtime closure değil; capability expansion. v3.3.0 hedefi ile scope creep | **C7 v3.4.0'a defer edildi** (FAZ-C scope'tan çıkarıldı) |

### v2 absorb warnings

- **W1**: Yeni `route_cross_class_downgrade` kind `_KINDS` 27→28 bump'ı `test_policy_sim_integration.py:101-110` invariant testi günceller. C4'e eklendi.
- **W2**: C1 tek PR çok büyük → C1a/C1b split ile azaltıldı.
- **W3**: LOC ~6500 / 8 PR / ~8 hafta iyimser → C7 defer + C1 split ile ~5500 LOC / 8 PR / ~7-8 hafta gerçekçi.
- **W4**: v3.3.0-alpha1 etiketi salt C1a sonrası erken; C1b (full bundled green) sonrası anlamlı. Release strategy güncellendi.
- **W5**: C4+C5+C7 paralel write ownership tanımı — C7 defer edildiğinden moot; C4 router/llm, C5 policy_sim/CLI, C6 executor.

### v2 Q answers absorb

| Q | Codex cevabı | v2 karar |
|---|---|---|
| Q1 PR ordering | C1a→C1b→C2→C6→C8; C2 plan-time C1a paralel; C3 C1a sonrası; **v3.2.1 skip, 3.3.0'a göm** | Absorbed |
| Q2 metric family update | Zorunlu değil; `_KINDS==27` invariant testi güncellenir | Absorbed (C4 scope) |
| Q3 RFC 7396 edge cases | null-delete, array-replace, recursive merge, absent-key preserve, scalar/object replace, baseline immutability, schema-valid merged; CLI mutex + per-file error | C5 test coverage guide |
| Q4 `Executor.dry_run_step` purity | **Ayrı `dry_run_execution_context`**, policy-sim guard extend değil. Boundary: `emit_event`, `create_worktree`/`cleanup_worktree`, `invoke_cli`/`invoke_http`. `DryRunResult` shape `{predicted_events, policy_violations, simulated_budget_after, simulated_outputs}` | C6 scope netleştirildi |
| Q5 Vision/audio stub | Manifest-driven deterministic template + `input_sha256` metadata; AMA **defer to v3.4.0** | C7 FAZ-C scope dışı |
| Q6 SemVer minor | Doğru; tüm yeni davranışlar default-off additive. C4 soft_degrade aktivasyonu yeni knob arkasında dormant ship | Absorbed |

---

## 1. Context (v2)

FAZ-B v3.2.0 LIVE + B7.1 `e16e8d8` merged (main HEAD). FAZ-C hedef: **4 runtime gap + 3 stratejik genişleme + release** = 8 PR.

**B7.1 release integration**: v3.2.1 tag **atlandı**; B7.1 benchmark-shim + docs §9 recipe + FAZ-C routing CHANGELOG entry'si v3.3.0 release notes'a absorbe edilir (Codex Q1). PR sayısı azalır, kullanıcıya sürüm sürümsüz ara yok.

### Runtime closure (v3.3.0'ın ana teması)

5 PR, critical path:
- **C1a** — Adapter artifact surface + context_compile materialisation (altyapı)
- **C1b** — Full bundled `bug_fix_flow` E2E (üstüne)
- **C2** — Real-adapter full mode (secrets + context_pack_ref + env parity)
- **C3** — `cost_usd` runtime reconcile (adapter transport path + idempotency key)
- **C6** — `Executor.dry_run_step` (ayrı dry_run context; single-step mock composition)

### Stratejik genişleme (paralel tracks)

2 PR, bağımsız:
- **C4** — Cross-class cost routing (soft_degrade runtime + `_KINDS` 27→28)
- **C5** — Merge-patch policy-sim (RFC 7396)

### Release
- **C8** — v3.3.0 tag + PyPI

**C7 vision/audio ertelendi v3.4.0'a.**

---

## 2. Scope (PR breakdown)

| PR | Feature | Workstream | LOC est | Deps |
|---|---|---|---|---|
| **C1a** | Adapter artifact surface + output_ref adapter-path guarantee + context_compile `.ao/runs/{run_id}/context.md` materialisation + `build_driver` policy_loader forward | Runtime closure | ~700 | none |
| **C1b** | Full bundled `bug_fix_flow` E2E — patch plumbing fallback + benchmark `TestFullBundled` class | Runtime closure | ~600 | C1a |
| **C2** | Real-adapter full mode — `--benchmark-mode=full` + env-gated + union parent_env (`allowlist_secret_ids ∪ env_allowlist.allowed_keys`) + `context_pack_ref` resolve + env parity | Runtime closure | ~900 | C1a |
| **C3** | `cost_usd` runtime reconcile: `post_adapter_reconcile` atomic middleware (lock-first duplicate check + drain + ledger + `llm_spend_recorded` emit with `source` discriminator) + envelope.cost_actual wire extraction | Runtime closure | ~850 | B2 (merged), C1a nice |
| **C4** | Cross-class cost routing: additive `resolve_route` kwargs + `downgrade_applied/original_class/downgraded_class` return + caller-side `route_cross_class_downgrade` emit + `_KINDS` 27→28 | Strategic ext | ~900 | B3 (merged) |
| **C5** | Merge-patch policy-sim (RFC 7396): `apply_merge_patch` + `proposed_policy_patches` arg + CLI `--proposed-patches`. Impl-time bağımsız C4'ten (W2). | Strategic ext | ~700 | B4 (merged) |
| **C6** | `Executor.dry_run_step` — ayrı `dry_run_execution_context` (emit_event + worktree + invoke_cli/http mock) + `DryRunResult` | Runtime closure | ~1000 | C1a |
| **C8** | Release v3.3.0 (includes B7.1 CHANGELOG) | Release | ~200 | all |

**Toplam**: ~6150 LOC / 8 PR / ~7-8 hafta. (v5 revise: +50 C3 atomic lock + wire-format test; +100 C4 emit-site caller wiring.)

**~~C7 vision/audio~~** → v3.4.0.

---

## 3. Release Gates

- [ ] C1a: adapter path `output_ref` populated; `context_compile` writes `.ao/runs/{run_id}/context.md`; `build_driver(policy_loader=...)` forward
- [ ] C1b: Full `bug_fix_flow` 7-step end-to-end green
- [ ] C2: `--benchmark-mode=full` env-gated skip-clean; real adapter invocation with `GH_TOKEN` / `ANTHROPIC_API_KEY` via `secrets.allowlist_secret_ids`
- [ ] C3: `cost_usd.remaining` drain via `record_spend` idempotent (double-call = single effect); B7.1 shim removed
- [ ] C4: Cross-class downgrade test: `CODE_AGENTIC` budget insufficient → `FAST_TEXT` + `route_cross_class_downgrade` event (`_KINDS == 28`)
- [ ] C5: RFC 7396 merge-patch edge case suite (null-delete + array-replace + recursive + absent-preserve)
- [ ] C6: `Executor.dry_run_step` — mocked emit/worktree/invoke; returns `DryRunResult{predicted_events, policy_violations, simulated_budget_after, simulated_outputs}`
- [ ] C8: `pip install ao-kernel==3.3.0` smoke + B7.1 notes integrated

---

## 4. Workstream Dependencies (v2)

```
C1a (altyapı — artifact + context_compile + driver policy forward)
├── C1b (full bundled bugfix E2E)
├── C2 (real full mode — plan-time parallel, impl after C1a)
├── C3 (cost_usd reconcile — independent after C1a lands idempotency key design)
└── C6 (dry_run_step — new purity context over C1a base)

C4 (cross-class routing) ← B3 extension; independent
C5 (merge-patch policy-sim) ← B4 extension; independent

C8 (release) ← all
```

**Paralel**:
- C4 + C5 tam bağımsız (paralel plan-time + impl).
- C2 + C3 + C6 C1a sonrası paralel (C1a kontrata dayalı).
- C1a seri kritik-path.

---

## 5. PR Detayları (v2)

### C1a — Adapter artifact surface + context_compile materialisation (altyapı)

**Problem** (Codex B1/B2/B3):
- `_driver_helpers.build_driver` Executor'a `policy_loader` forward etmez (repo gerçeği).
- `step_record.output_ref` persist değil; adapter-path `output_ref` garanti değil.
- `context_compile` stub `.ao/runs/{run_id}/context.md` üretmez; `claude-code-cli` manifest `context_pack_ref` placeholder literal kalır.

**Scope**:
- `tests/_driver_helpers.build_driver` — new optional `policy_loader` kwarg; Executor'a forward.
- `ao_kernel.executor.ExecutionResult` — adapter path için `output_ref` guarantee (driver-managed path'te mevcut; adapter-path extend).
- `ao_kernel.executor.multi_step_driver._context_compile` — `.ao/runs/{run_id}/context.md` write (atomik).
- `Executor.run_step::input_envelope` builder — `context_pack_ref` placeholder resolve (`{context_pack_ref}` → `.ao/runs/{run_id}/context.md` relative path).
- Tests: `test_multi_step_driver` context_compile material + `test_executor_integration` adapter output_ref.

**LOC**: ~700.

**Risk**: Executor çekirdek refactor; B1-B6 regression. Post-impl Codex mandatory.

### C1b — Full bundled `bug_fix_flow` E2E

**Scope**:
- Benchmark `TestFullBundled` class — compile → codex-stub → preview_diff → ci_pytest → await_approval → apply_patch → gh-cli-pr.
- `_load_pending_patch_content()` fallback order (`patches[]` → `step_record.output_ref` via `output_ref`).
- Bench workspace policy override (dummy git + pytest + gh allowlist; C1a'nın `policy_loader` forward desteği ile).
- Fixture: mini_repo with real `test_smoke.py` (gerçek pytest çalışır).

**LOC**: ~600.

### C2 — Real-adapter full mode (v4: union parent_env plumbing)

**Problem v4 (Codex iter-4 B3 absorb)**: v3 fix `parent_env = {... env_allowlist.allowed_keys ...}` subset `GH_TOKEN`/`ANTHROPIC_API_KEY`'ı dışarıda bırakıyor (bu anahtarlar `policy.secrets.allowlist_secret_ids`'te, `env_allowlist.allowed_keys`'te değil). Resolver secret-only; sandbox env passthrough allowlist-only. İkisinin birleşimi driver katmanında gereklidir.

**Scope**:
- `ao_kernel.executor.multi_step_driver._run_adapter_step` — `parent_env = {k: os.environ[k] for k in (set(policy.secrets.allowlist_secret_ids) | set(policy.env_allowlist.allowed_keys)) if k in os.environ}`. Union kuralı: secrets + allowlist-env birleşimi caller katmanında. `resolve_allowed_secrets(policy, parent_env)` ve `build_sandbox(..., parent_env=parent_env)` ikisi de aynı union'dan beslenir; resolver + sandbox builder signature'ları değişmez.
- `tests/benchmarks/conftest.py::pytest_addoption` `--benchmark-mode=fast|full`.
- `tests/benchmarks/full_mode.py` — env gate + per-adapter required vars (`ANTHROPIC_API_KEY`, `GH_TOKEN`).
- `Executor.run_step` — `secrets.allowlist_secret_ids + exposure_modes=['env']` integration (`build_sandbox` shipped contract). Union parent_env sonrası contract düzgün çalışır.
- Cost cap env (`AO_BENCHMARK_COST_CAP_USD`, default 0.50).
- Evidence redaction verify (secrets not leaked in evidence logs).
- Yeni test `test_parent_env_secret_union.py`: policy fixture'da `allowlist_secret_ids=['GH_TOKEN']` + `env_allowlist.allowed_keys=['PATH']` → driver `_run_adapter_step` builds `parent_env={'GH_TOKEN': ..., 'PATH': ...}`, her iki downstream (`resolve_allowed_secrets` + `build_sandbox`) doğru key seti görür.

**LOC**: ~900 (v4: +100 union test + evidence redaction extension).

### C3 — `cost_usd` runtime reconcile (v5: atomic adapter reconcile)

**Problem v5 (Codex iter-5 B1+B2+B3 absorb)**:

1. **Idempotency sırası**: v4 `update_run(mutator) → record_spend(event)` dizisi same-digest ikinci çağrıda budget'ı 2× düşürür (iter-5 B1).
2. **`_KINDS` bump**: Yeni `adapter_spend_recorded` kind iki bump cascade ister (C3 27→28, C4 28→29). Mevcut `llm_spend_recorded` reuse + `source` discriminator daha az schema churn (iter-5 B2).
3. **Envelope wire format**: Tokens `cost_actual.tokens_input/tokens_output` altında, `usage.*` değil (iter-5 B3, `agent-adapter-contract.schema.v1.json:341-349`).
4. **`catalog_entry` provenance**: On-demand lookup `load_catalog + get_entry(provider_id, model)` middleware içinden; yoksa `vendor_model_id=None` audit-only path (iter-5 W3).

**v5 karar**: Atomic lock-first idempotency + kind reuse + correct wire format. Budget drenajı yalnız fresh-append path'inde; duplicate detect budget'a dokunmaz.

**Scope**:

- `ao_kernel.cost.middleware._build_adapter_spend_event(envelope: Mapping, *, run_id, step_id, attempt, provider_id, model) -> SpendEvent`:
  - `cost_actual = envelope.get("cost_actual") or {}`
  - `tokens_input = int(cost_actual.get("tokens_input", 0))`, `tokens_output = int(cost_actual.get("tokens_output", 0))`, `cost_usd = Decimal(str(cost_actual.get("cost_usd", 0)))`, `cached_tokens = cost_actual.get("cached_tokens")`
  - `vendor_model_id` on-demand: `entry = get_entry(load_catalog(ws), provider_id, model); vendor_model_id = entry.vendor_model_id if entry else None`
  - `usage_missing = ("tokens_input" not in cost_actual or "tokens_output" not in cost_actual)`
  - `ts = _iso_now()`, `billing_digest=""` (writer fills).
  - Kaynak schema: `agent-adapter-contract.schema.v1.json:341-349` (cost_actual shape), `spend-ledger.schema.v1.json` (event shape).

- `ao_kernel.cost.middleware.post_adapter_reconcile(*, workspace_root, run_id, step_id, attempt, provider_id, model, envelope, policy) -> None`:
  ```python
  event = _build_adapter_spend_event(envelope, run_id=..., ...)
  digest = event.billing_digest or _compute_billing_digest(event)
  event = replace(event, billing_digest=digest)
  
  ledger_path = _ledger_path(workspace_root, policy)
  lock_path = _ledger_lock_path(ledger_path)
  ledger_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
  
  appended = False
  with file_lock(lock_path):
      window = _scan_tail(ledger_path, policy.idempotency_window_lines)
      existing = _find_duplicate(window, run_id, step_id, attempt)
      if existing is not None:
          existing_digest = str(existing.get("billing_digest", ""))
          if existing_digest == digest:
              logger.warning("adapter reconcile idempotent no-op: ...")
              return  # NO budget drain, NO ledger append, NO emit
          raise SpendLedgerDuplicateError(
              run_id=run_id, step_id=step_id, attempt=attempt,
              existing_digest=existing_digest, new_digest=digest,
          )
      # Fresh append path — drain budget then write ledger, atomically within lock.
      if not event.usage_missing and event.cost_usd > 0:
          update_run(
              workspace_root, run_id,
              mutator=_adapter_reconcile_mutator(event.cost_usd, run_id),
              max_retries=3,
          )
      doc = _event_to_dict(event)
      _validate_event(doc)
      _append_with_fsync(ledger_path, json.dumps(doc, sort_keys=True, ...))
      appended = True
  
  if appended:
      _safe_emit(
          workspace_root, run_id,
          "llm_spend_recorded",  # REUSE existing kind; no _KINDS bump
          {
              "source": "adapter_path",
              "run_id": run_id, "step_id": step_id, "attempt": attempt,
              "provider_id": provider_id, "model": model,
              "tokens_input": event.tokens_input,
              "tokens_output": event.tokens_output,
              "cost_usd": float(event.cost_usd),
              "usage_missing": event.usage_missing,
              "ts": event.ts,
          },
      )
  ```
  - Kritik bölge: tek `file_lock` hem duplicate check hem budget drain hem ledger append'i kapsar. `record_spend`'in içindeki lock BYPASS edilir (double-lock yok; helpers `_scan_tail + _find_duplicate + _event_to_dict + _validate_event + _append_with_fsync` doğrudan reuse).

- `ao_kernel.executor.executor.invoke_cli / invoke_http` — envelope dönüşte `cost_actual.cost_usd` mevcutsa `post_adapter_reconcile(...)` çağrısı. Envelope yoksa no-op.

- `ao_kernel.executor.adapter_invoker._invocation_from_envelope` — envelope extract zaten mevcut; `InvocationResult.cost_actual` field'ı middleware'e forward (mevcut field).

- `llm_spend_recorded` event payload schema delta: `source: "adapter_path" | "llm_call"` discriminator opsiyonel field eklenir (backwards-compat: mevcut emitter'lar `source` yok → "llm_call" varsayılır). `_KINDS` **C3'te bump edilmez**; `ao_kernel/defaults/schemas/evidence-event.schema.v1.json::llm_spend_recorded` payload schema'ya yeni opt field eklenir.

- Test:
  - `test_post_adapter_reconcile.py`: happy path (envelope with cost → budget drained exactly by envelope.cost_actual.cost_usd, ledger appended, `llm_spend_recorded` emitted with `source="adapter_path"`).
  - `test_adapter_reconcile_idempotency.py`: double-call same `(run_id, step_id, attempt)` + same digest → silent warn + **single ledger line + single budget drain** (atomic order kanıtı).
  - `test_adapter_reconcile_digest_conflict.py`: same key + different digest → `SpendLedgerDuplicateError` raise + budget dokunulmaz.
  - `test_adapter_reconcile_usage_missing.py`: envelope.cost_actual.tokens_input yok → `usage_missing=True` event, budget drain SKIP.
  - `test_adapter_reconcile_wire_format.py`: envelope.cost_actual.{tokens_input,tokens_output,cost_usd} correct extraction kanıtı (NOT envelope.usage.*).
  - `test_benchmark_shim_removal.py`: B7.1 `_maybe_consume_budget` shim silinir; `test_cost_usd_drained_after_happy_review` real path üzerinden pass eder.

- B7.1 `tests/benchmarks/mock_transport._maybe_consume_budget` silinir; `_TransportError` sentinel + envelope dispatch korunur.

**LOC**: ~850 (v5: +50 atomic lock design + wire format test + source discriminator).

### C4 — Cross-class cost routing + soft_degrade runtime (v4: additive facade)

**v4 fix (Codex iter-4 B4 absorb)**: Mevcut `ao_kernel.llm.resolve_route` imzası `(*, intent, perspective, provider_priority, workspace_root)` (`llm.py:23-29`). 4 caller kullanıyor: `mcp_server.py:150, 353`, `client.py:842`, `intent_router.py:364`. Signature'ı değiştirmek hepsini kırar. v4: **additive kwarg** stratejisi — mevcut imza dokunulmaz, yeni opsiyonel kwarg'lar eklenir.

**Scope**:
- `ao_kernel.llm.resolve_route` facade additive widen:
  ```python
  def resolve_route(
      *,
      intent: str,
      perspective: str | None = None,
      provider_priority: list[str] | None = None,
      workspace_root: str | None = None,
      # v4 yeni eklemeler (default-off, backwards-compatible):
      budget_remaining: "Budget | None" = None,
      cross_class_downgrade: bool = False,
      soft_degrade: bool = False,
  ) -> dict[str, Any]: ...
  ```
- `ao_kernel._internal.prj_kernel_api.llm_router.resolve` — yeni kwarg'ları tüketir. `cross_class_downgrade=True AND budget_remaining.cost_usd < estimate_preferred_class_cost` → `soft_degrade.rules` iterate + downgraded class seç.
- Mevcut call-sites (`mcp_server.py:150,353`, `client.py:842`, `intent_router.py:364`) **dokunulmaz**. Default-off davranış korunur.
- `policy_cost_tracking.v1.json::routing_by_cost.cross_class_downgrade` schema delta (dormant default: false).
- `_KINDS` 27 → 28: yeni `route_cross_class_downgrade` kind.
- `test_policy_sim_integration.py::TestKindsInvariant` 27 → 28.
- `docs/POLICY-SIM.md:49-51` exact-count metni 27 → 28.
- `docs/COST-MODEL.md §7` + `docs/MODEL-ROUTING.md §6`.
- Yeni test `test_resolve_route_defaults_off.py`: mevcut callers behavior değişmez (kanıt: default kwargs ile karşılaştır).
- Yeni test `test_cross_class_downgrade.py`: `cross_class_downgrade=True + budget_remaining.cost_usd < threshold` → downgraded class + `route_cross_class_downgrade` evidence event.

**v5 Event emit site (iter-5 W1 absorb)**: `resolve_route` stateless + run_id'si yok (`llm.py:23-46`). Downgrade evidence event'ini `resolve_route` emit EDEMEZ. Çözüm: return dict'e 3 yeni alan eklenir:
```python
{
    ...existing fields...,
    "downgrade_applied": bool,       # True iff cross_class_downgrade fired
    "original_class": str | None,    # sadece downgrade_applied=True iken dolu
    "downgraded_class": str | None,  # sadece downgrade_applied=True iken dolu
}
```
Caller (`governed_call` → `_internal/prj_kernel_api/llm_call.py` veya `workflow/multi_step_driver._run_llm_step`) bu flag'leri görürse `emit_event(workspace_root, run_id, 'route_cross_class_downgrade', {original_class, downgraded_class, budget_remaining, ts})` çağırır. Test: `test_cross_class_downgrade_emit.py` — governed_call happy path + downgrade event evidence file'da bulunur.

**LOC**: ~900 (v5: additive +100 emit site + caller wiring + test).

### C5 — Merge-patch policy-sim (RFC 7396)

**v4 clarification (Codex iter-4 W2 absorb)**: C5 impl-time **C4'ten bağımsız** — merge-patch algoritması + CLI + test suite C4 olmadan çalışır ve shippable. Sadece `docs/POLICY-SIM.md`'de `cross_class_downgrade` knob'a referans C4 merge sonrası anlamlı; dokümantasyon sırası C4 → C5 bölümü (dokümantasyon-level). Impl paralel ve bağımsız.

**Scope**:
- `ao_kernel.policy_sim.loader::apply_merge_patch(baseline, patch)` stdlib-only RFC 7396 impl.
- `simulate_policy_change::proposed_policy_patches: Mapping[str, Mapping] | None` new kwarg; mutex with `proposed_policies`.
- CLI `ao-kernel policy-sim run --proposed-patches <dir>`.
- Edge-case test suite: null-delete, array-replace, recursive, absent-preserve, scalar-object replace, baseline immutability.
- `docs/POLICY-SIM.md` update (C4 merge sonrası C5 dokümantasyon PR'ı ile; C5 impl PR C4 merge beklemez).

**LOC**: ~700.

### C6 — `Executor.dry_run_step` (yeni purity context)

**Codex Q4 absorb**: Policy-sim guard EXTEND **değil**. Ayrı `dry_run_execution_context` — mock scope: `emit_event`, `create_worktree`/`cleanup_worktree`, `invoke_cli`/`invoke_http`.

**Scope**:
- `ao_kernel.executor.Executor.dry_run_step(step_name, ...) -> DryRunResult`.
- `DryRunResult{predicted_events: tuple, policy_violations: tuple, simulated_budget_after: dict, simulated_outputs: dict}`.
- CLI `ao-kernel executor dry-run <workflow_id> <step_name>`.

**LOC**: ~1000.

### C8 — Release v3.3.0

**Scope**:
- CHANGELOG `[Unreleased]` → `[3.3.0] — 2026-XX-XX`. B7.1 entry integrated.
- `pyproject.toml::version` 3.2.0 → 3.3.0.
- `ao_kernel.__version__` + `test_pr_a6_features.py::TestVersionBump` literal güncelle.
- Tag `v3.3.0` + push → publish.yml → PyPI.
- GitHub release notes + memory update.

**LOC**: ~200.

---

## 6. Parallelism + Release Strategy (v2)

**Aşamalı release**:
- **v3.3.0-alpha1** (C1a + **C1b green** sonrası — W4 absorb): benchmark maturity alpha.
- **v3.3.0-rc1** (C4 + C5 sonrası): stratejik genişlemeler.
- **v3.3.0** final (C8).

**~~v3.2.1~~** skipped (Codex Q1): B7.1 3.3.0'a gömüldü.

**Paralel Codex threads**:
- C1a seri (kritik path başı).
- C2/C3/C6 plan-time paralel C1a impl'i ile; impl C1a sonrası.
- C4 + C5 tam bağımsız.

---

## 7. Codex iter-2 için Açık Sorular

v1 Q1-Q6 hepsi iter-1'de cevaplandı ve v2 absorb edildi (C7 defer, v3.2.1 skip, soft_degrade runtime, idempotency key, dry_run context ayrı, SemVer minor). **Yeni açık soru yok**.

---

## 8. Risk Register (v2)

| Risk | L | I | Mitigation |
|---|---|---|---|
| R1 C1a executor refactor B1-B6 regression | M | H | Full regression gate + post-impl Codex mandatory |
| R2 C2 CI credential leak | L | H | Env-gated skip; CI no secrets; cost cap |
| R3 C3 idempotency_key double-drain hâlâ | M | M | `(run_id, step_id, attempt, spend_kind)` tuple; test double-call |
| R4 C4 `_KINDS` bump test cascade | M | L | Invariant test + docs update aynı commit |
| R5 C5 RFC 7396 null-delete edge | M | L | Dedicated test suite |
| R6 C6 dry_run_context complexity | M | M | Start lightweight; chaos defer |
| R7 Parallel threads context leak | L | L | Thread ID saklı per-PR |
| R8 LOC (5500) scope fatigue | M | M | PR'lar standalone shippable |
| R9 v3.3.0 window slip | M | L | Alpha/rc aşamalı |
| R10 ~~C7 scope creep~~ | ~~H~~ | ~~H~~ | **Defer v3.4.0** (v2 karar) |

---

## 9. Audit Trail

| Iter | Date | Verdict |
|---|---|---|
| v1 (Claude draft) | 2026-04-18 | Pre-Codex iter-1 submit |
| **iter-1** (CNS-20260418-041, thread `019d9f75`) | 2026-04-18 | **REVISE** — 6 blocker + 5 warning + Q1-Q6 cevaplar |
| **v2 (iter-1 absorb)** | 2026-04-18 | Pre-iter-2 submit |
| iter-2 | 2026-04-18 | **PARTIAL** — 2 blocker (`record_spend(idempotency_key)` state tutamaz, driver `parent_env={}` plumbing) + 3 warning |
| **v3 (iter-2 absorb)** | 2026-04-18 | Pre-iter-3 submit |
| iter-3 | 2026-04-18 | **PARTIAL** — 2 blocker sürmekte: v3 C3 SpendEvent şema uyumsuz + C2 secret source env_allowlist subset yanlış; 3 warning |
| **iter-4 (v3 revize prompt-only)** | 2026-04-18 | **PARTIAL** — 4 blocker (C3 SpendEvent fields, C3 budget drain design, C2 layer, C4 API regression) + 3 warning (plan file not yet updated, C5 coupling, LOC optimistic) |
| **v4 (iter-4 absorb)** | 2026-04-18 | Plan file workspace'te v4'e güncellendi (`0dbb1df`); kod-okuma fact-check. |
| iter-5 | 2026-04-18 | **PARTIAL** — C1a/C2/C4 validated (notes); 3 yeni C3 blocker (idempotency order, _KINDS bump cascade, envelope wire format) + 3 warning (C4 emit site run_id'siz, revision history stale, catalog_entry provenance) |
| **v5 (iter-5 absorb)** | 2026-04-18 | Pre-iter-6 submit. C3 atomic lock design + `llm_spend_recorded` reuse (source discriminator) + `envelope.cost_actual` wire format + C4 emit-site caller-wiring + SUPERSEDED notes. |
| iter-6 | TBD | AGREE expected (C1a/C2/C4 zaten validated; C3 targeted blockers kapatıldı) |

### Plan revision history

| Ver | Change |
|---|---|
| v1 | 8 PR breakdown; 4 workstream; C7 vision/audio included; 6 Q for Codex |
| **v2** | iter-1 REVISE absorb (6 blocker + 5 warning + Q1-Q6): C1 split (C1a+C1b); Executor.policy_loader mevcut → forward/materialization scope; context_compile write; record_spend idempotency_key `(run_id, step_id, attempt, spend_kind)`; soft_degrade runtime + modül adı düzeltme; `_KINDS` 27→28; C6 ayrı dry_run_execution_context; C7 → v3.4.0 defer; v3.2.1 skip; alpha/rc/final release. |
| **v3** | iter-2 PARTIAL absorb (2 blocker + 3 warning): idempotency `cost.ledger` katmanına taşındı (SpendLedgerDuplicateError + billing_digest mevcut); C2 driver `parent_env` plumbing eklendi; C4 public facade `resolve_route` widen explicit; `_KINDS` docs update. |
| **v4** | iter-4 PARTIAL absorb (4 blocker + 3 warning): C3 helper yanlış iddiası silindi (mevcut `record_spend(event)` API kullanılır); C3'e yeni `post_adapter_reconcile` middleware eklendi (CAS mutator + ledger + emit üçlü); C2 union caller katmanına taşındı (resolver+sandbox imzaları dokunulmaz); C4 signature DOKUNULMAZ → additive kwargs; W1 plan dosyası gerçekten v4'e güncellendi; W2 C5 impl-time bağımsız netleşti; W3 LOC revise ~6100. |
| **v5** | iter-5 PARTIAL absorb (3 C3 blocker + 3 warning): C3 atomic lock-first duplicate check (budget drain sadece fresh append path'inde); `llm_spend_recorded` kind reuse + `source` discriminator (C3 `_KINDS` bump etmez); `envelope.cost_actual` wire format (not `usage.*`); C4 emit-site caller-wiring (`resolve_route` return dict'e `downgrade_applied` + caller emit); `catalog_entry` on-demand `load_catalog + get_entry` lookup; SUPERSEDED notes v2/v3 absorb sections. |

**Status**: Plan v5 hazır. Codex thread `019d9f75` iter-6 submit için hazır. C1a/C2/C4 iter-5 notes'ta validated; C3 3 yeni blocker targeted fix'lerle kapatıldı. AGREE beklenir (dar scope iter-6).
