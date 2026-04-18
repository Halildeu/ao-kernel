# FAZ-C Master Plan v3 — Runtime Closure (v3.3.0)

## v3 absorb summary (Codex iter-2 PARTIAL — 2 blocker + 3 warning)

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

## v2 absorb summary (Codex CNS-20260418-041 iter-1 REVISE — 6 blocker + 5 warning)

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
| **C2** | Real-adapter full mode — `--benchmark-mode=full` + env-gated + `secrets.allowlist_secret_ids + exposure_modes=['env']` + `context_pack_ref` resolve + env parity | Runtime closure | ~800 | C1a |
| **C3** | `cost_usd` runtime reconcile: `record_spend` idempotency key + adapter transport `_spend_cost` helper | Runtime closure | ~600 | B2 (merged), C1a nice |
| **C4** | Cross-class cost routing: `soft_degrade` runtime consumer + `routing_by_cost.cross_class_downgrade` knob + `route_cross_class_downgrade` evidence kind (`_KINDS` 27→28) | Strategic ext | ~900 | B3 (merged) |
| **C5** | Merge-patch policy-sim (RFC 7396): `apply_merge_patch` + `proposed_policy_patches` arg + CLI `--proposed-patches` | Strategic ext | ~700 | B4 (merged) |
| **C6** | `Executor.dry_run_step` — ayrı `dry_run_execution_context` (emit_event + worktree + invoke_cli/http mock) + `DryRunResult` | Runtime closure | ~1000 | C1a |
| **C8** | Release v3.3.0 (includes B7.1 CHANGELOG) | Release | ~200 | all |

**Toplam**: ~5500 LOC / 8 PR / ~7-8 hafta.

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

### C2 — Real-adapter full mode (v3: parent_env plumbing)

**Problem v3 (Codex iter-2 B2 absorb)**: Driver adapter step'e `parent_env={}` sabit (`multi_step_driver.py:467-476`). `resolve_allowed_secrets(policy, all_env)` host env okur ama `all_env` boş → secrets çözülemez. C2'nin "real full mode" vaadi kırık.

**Scope**:
- `ao_kernel.executor.multi_step_driver._run_adapter_step` — `parent_env = {k: os.environ[k] for k in policy.env_allowlist.allowed_keys if k in os.environ}`. Sandbox allowlist zaten filtrelemeye yapacak; driver tedarik katmanı eksikti.
- `tests/benchmarks/conftest.py::pytest_addoption` `--benchmark-mode=fast|full`.
- `tests/benchmarks/full_mode.py` — env gate + per-adapter required vars (`ANTHROPIC_API_KEY`, `GH_TOKEN`).
- `Executor.run_step` — `secrets.allowlist_secret_ids + exposure_modes=['env']` integration (`build_sandbox` shipped contract). Parent_env forward sonrası contract düzgün çalışır.
- Cost cap env (`AO_BENCHMARK_COST_CAP_USD`, default 0.50).
- Evidence redaction verify (secrets not leaked in evidence logs).

**LOC**: ~800.

### C3 — `cost_usd` runtime reconcile (v3: cost.ledger idempotency)

**Problem v3 (Codex iter-2 B1 absorb)**: `workflow.budget.record_spend` saf fonksiyon + `Budget` dataclass `additionalProperties:false` → idempotency key state tutamaz. **v3 karar**: idempotency `ao_kernel.cost.ledger` katmanında — `SpendLedgerDuplicateError` (canonical billing_digest) zaten var. Budget dataclass/schema DOKUNULMAZ.

**Scope**:
- `ao_kernel.executor.adapter_invoker.invoke_cli/invoke_http` — envelope `cost_actual.cost_usd` mevcutsa `ao_kernel.cost.ledger.record_spend_event(run_id, step_id, attempt, cost_usd=..., provider_id=..., model=...)` çağrısı. Canonical billing_digest otomatik — duplicate call silent warn + skip.
- `ao_kernel.cost.middleware.post_response_reconcile` — aynı ledger path; duplicate-by-digest protection ile double-record engellenir.
- Test: double-call test (`governed_call` + adapter transport aynı step) → tek ledger entry + budget drain tek sefer.
- B7.1 benchmark shim removed; `assert_cost_consumed` runtime path üzerinden pass eder.

**LOC**: ~600.

### C4 — Cross-class cost routing + soft_degrade runtime (v3: facade widen)

**v3 fix (Codex iter-2 W1/W2 absorb)**: Public facade `ao_kernel.llm.resolve_route` bugün `budget_remaining` almıyor; ana çağıranlar facade kullanıyor (`mcp_server.py:149-155`, `client.py:841-846`). Facade widen C4 scope'a explicit.

**Scope**:
- `ao_kernel._internal.prj_kernel_api.llm_router.resolve` — yeni optional `budget_remaining` parametresi.
- **`ao_kernel.llm.resolve_route` facade widen** — same `budget_remaining: Budget | None` kwarg; internal resolver'a pass-through.
- Call-site update: `ao_kernel.mcp_server` + `ao_kernel.client` opt-in `budget_remaining` forward.
- Eğer `cost_policy.routing_by_cost.cross_class_downgrade=true` AND `budget_remaining.cost_usd < estimate_preferred_class_cost` → `soft_degrade.rules` iterate.
- `soft_degrade` runtime consumer eklenir (mevcut JSON bloğu şu an parse edilmiyor).
- `policy_cost_tracking.v1.json::routing_by_cost.cross_class_downgrade` schema delta (dormant default).
- `_KINDS` 27 → 28: yeni `route_cross_class_downgrade` kind.
- `test_policy_sim_integration.py::TestKindsInvariant` 27 → 28.
- **`docs/POLICY-SIM.md:49-51`** exact-count metni 27 → 28 (Codex W2).
- Docs `docs/COST-MODEL.md §7` + `docs/MODEL-ROUTING.md §6`.

**LOC**: ~900.

### C5 — Merge-patch policy-sim (RFC 7396)

**Scope**:
- `ao_kernel.policy_sim.loader::apply_merge_patch(baseline, patch)` stdlib-only RFC 7396 impl.
- `simulate_policy_change::proposed_policy_patches: Mapping[str, Mapping] | None` new kwarg; mutex with `proposed_policies`.
- CLI `ao-kernel policy-sim run --proposed-patches <dir>`.
- Edge-case test suite: null-delete, array-replace, recursive, absent-preserve, scalar-object replace, baseline immutability.

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
| **iter-1** (CNS-20260418-041, thread `019d9f75`) | 2026-04-18 | **REVISE** — 6 blocker (C1 split + `Executor(policy_loader)` already exists + context_compile stub + record_spend duplicate + soft_degrade runtime gap + C7 defer) + 5 warning + Q1-Q6 cevaplar |
| **v2 (iter-1 absorb)** | 2026-04-18 | Pre-iter-2 submit |
| iter-2 | TBD | AGREE expected |

### Plan revision history

| Ver | Change |
|---|---|
| v1 | 8 PR breakdown; 4 workstream; C7 vision/audio included; 6 Q for Codex |
| **v2** | **iter-1 REVISE absorb** (6 blocker + 5 warning + Q1-Q6): C1 split (C1a altyapı + C1b E2E); Executor.policy_loader mevcut → forward/materialization scope; context_compile `.ao/runs/{run_id}/context.md` write; record_spend idempotency_key `(run_id, step_id, attempt, spend_kind)`; soft_degrade runtime consumer + modül adı düzeltme; `_KINDS` 27→28 bump + invariant test update; C6 ayrı `dry_run_execution_context`; C7 → **v3.4.0 defer**; v3.2.1 skip (B7.1 3.3.0'a göm); release aşamalı alpha/rc/final. |

**Status**: Plan v2 hazır. Codex thread `019d9f75` iter-2 submit için hazır. AGREE beklenir.
