# PR-A4b Implementation Plan v2 — Multi-Step Driver + Executor output_ref Wiring + Integration

**Tranche A PR 5/6b** — plan v2 after CNS-024 iter-1 PARTIAL (5 blocker + 7 warning absorbed). Target CNS-024 iter-2 AGREE via MCP reply (thread `019d92fd-acf3-71d0-bffe-2d4b51e3c531`).

## Revision History

| Version | Date | Scope |
|---|---|---|
| v1 | 2026-04-16 | Initial draft; CNS-024 iter-1 submission target. A4b standalone scope — PR-A4a primitives + contract repair already landed. |
| **v2** | **2026-04-16** | **CNS-024 iter-1 absorption: 5 blocker + 7 warning absorbed. B1: Executor `driver_managed=True` mode — driver owns run-level state, Executor only emits events + writes artifact. B2: run_workflow entry matrix {created, running, waiting_approval/interrupted, terminal}. B3: retry persistence order deterministic (failed attempt=1 CAS + attempt=2 placeholder CAS + invocation). B4: failure reason → schema `error.category` mapping table. B5: approval idempotency decision-only (notes in evidence payload, not token hash). W1-W7 implementation-time clarifications.** |

---

## 1. Amaç

FAZ-A Tranche A'nın beşinci iş paketinin ikinci yarısı. PR-A4a'nın ship ettiği:
- Contract repair (state_machine `waiting_approval → running` + `verifying → waiting_approval`, `step_record.attempt`, `step_def.operation` enum + conditional, evidence `diff_rolled_back`, bundled workflow operation alanları)
- `ao_kernel/patch/` 5 modül (`preview_diff` / `apply_patch` / `rollback_patch` + typed errors + `_ids`)
- `ao_kernel/ci/` 3 modül (`run_pytest` / `run_ruff` / `run_all` + typed errors)
- `ao_kernel/workflow/registry.py` `StepDefinition.operation` + `validate_cross_refs` guards

primitive'lerini kullanarak:
- **`ao_kernel/executor/multi_step_driver.py`** — `workflow_definition.steps` üzerinde actor/operation dispatch eden, `on_failure` (3 variant) handle eden, HITL/approval gate'leri yönlendiren, retry append-only (step_record `attempt=2`) + budget gating + per-step CAS yapan multi-step orchestrator
- **`ao_kernel/executor/executor.py`** — `Executor.run_step`'e `output_ref` wiring: adapter output envelope + CI result JSON `{run_dir}/artifacts/{step_id}-attempt{n}.json` dosyasına atomic write; `step_record.output_ref` populate; `adapter_returned` event payload `output_ref + payload_hash + attempt` alanları (CNS-023 iter-2 MV3 absorb)
- **Integration tests** — driver happy path, retry_once round-trip, escalate_to_human flow, patch+CI chain via codex-stub adapter

`docs/DEMO-SCRIPT.md` 11-step end-to-end flow'un 4-8 arası adımları (intent → workflow → adapter → diff → CI → approval) A4b merge sonrası lokalde executable olur. PR-A5 (evidence CLI) ve PR-A6 (demo runnable + adapter fixtures + `[coding]` meta-extra) kalır.

### Kapsam özeti

| Katman | Modül / Dosya | Yaklaşık LOC |
|---|---|---|
| Multi-step driver | `ao_kernel/executor/multi_step_driver.py` | ~620 |
| Executor output_ref wiring | `ao_kernel/executor/executor.py` delta | ~90 satır delta |
| Executor facade update | `ao_kernel/executor/__init__.py` delta | ~15 satır delta |
| Integration tests | `test_multi_step_driver.py` + `test_multi_step_driver_integration.py` | ~1100 |
| Test fixtures | 3 workflow JSON | ~200 |
| CHANGELOG | `[Unreleased]` → FAZ-A PR-A4b entry | ~80 |
| **Toplam** | **1 yeni src modül + 2 delta + 3 fixture** | **~2100** |

- Yeni schema: **0** (A4a'da operation + attempt eklendi; A4b bunları **kullanır**, extend etmez).
- Yeni policy: **0**.
- Yeni core dep: **0** (stdlib + `jsonschema>=4.23.0`).
- Tahmini yeni test: **≥ 30** (A4a: 1447, A4b target ≥ 1477).
- Evidence kind delta: **0** (A4a'da `diff_rolled_back` 18-kind zaten aktif; A4b `workflow_started`/`workflow_completed`/`workflow_failed`/`step_*`/`adapter_invoked`/`adapter_returned`/`diff_*`/`test_executed`/`approval_requested`/`approval_granted`/`approval_denied` kullanır).

### Tranche A pozisyonu (post-A4a merge)

- [x] PR-A0 (#87) — docs + schemas + policy bundled default
- [x] PR-A1 (#88) — workflow state machine + run store
- [x] PR-A2 (#89) — intent router + workflow registry + adapter manifest loader
- [x] PR-A3 (#90) — worktree executor + policy enforcement + adapter invocation
- [x] PR-A4a (#92) — contract repair + patch/ci primitives + unit tests
- [ ] **PR-A4b** (this) — multi_step_driver + Executor `output_ref` + integration
- [ ] PR-A5 — evidence timeline CLI + SHA-256 manifest on demand
- [ ] PR-A6 — demo runnable + adapter fixtures + `[coding]` meta-extra + `[llm]` fallback

A4b merge sonrası **end-to-end governed flow lokal olarak koşulabilir** (`docs/DEMO-SCRIPT.md` §3 happy path ≥36 event zinciri). PR-A5 operatör ergonomisi + replay CLI, PR-A6 demo paketleme + adapter production fixtures kalır.

---

## 2. Scope Fences

### Scope İçi (A4b)

- **`MultiStepDriver` public sınıf:**
  - `run_workflow(run_id, workflow_id, workflow_version, *, budget, context_preamble)` → `DriverResult`
  - `resume_workflow(run_id, resume_token, payload)` → `DriverResult`
- **Step actor/operation dispatch:** `step.actor + step.operation` tuple'ına göre primitive seçimi — adapter → `Executor.run_step`, ao-kernel + `operation=context_compile|patch_*` → context pipeline / patch primitive, system + `operation=ci_*` → ci runner, human → waiting_approval gate (pure HITL)
- **`step.gate` pre-step governance:** `gate != None` ise step çalıştırılmadan önce approval token mint + state `running → waiting_approval` transition + `DriverResult(final_state="waiting_approval", resume_token=...)` return
- **`on_failure` dispatch** (3 variant):
  - `transition_to_failed` — step_record.state=failed append + run_record state → failed, `workflow_failed` event, `DriverResult(final_state="failed")`
  - `retry_once` — **append-only model**: yeni step_record `attempt=2` + fresh step_id CAS'de persist edilir (ilk CAS), sonra dış subprocess invocation; ikinci fail → hard-fail. Crash-safety: attempt=2 step_record yok + attempt=1 failed + on_failure=retry_once → resume'de attempt=2 başlatılır.
  - `escalate_to_human` — `mint_approval_token(run_id, step_name)` + state `running → waiting_approval` + `approval_requested` event + `DriverResult(interrupted=True, resume_token=...)`. `patch_apply` operation için registry schema/cross-ref zaten reject ediyor (A4a invariant).
- **Per-step state CAS:** her step bitiminde `run_store.save_run_cas(run_id, record, expected_revision=current)` çağrılır; `WorkflowCASConflictError` durumunda driver 1 kez re-read + re-mutate; ikinci conflict → `DriverStateConflictError`.
- **Budget gating:** Budget axes (tokens, time_seconds, cost_usd) ortak pool; her step öncesi `budget.is_exhausted()` check; exhausted → `transition_to_failed(reason="budget_exhausted")`.
- **Cross-ref per-call (PR-A3 invariant korunur):** `Executor.run_step` zaten her adapter adımında cross-ref çağırıyor. A4b driver ADDITIONALLY workflow başında bir kez `WorkflowRegistry.validate_cross_refs(definition, adapter_registry)` çağırır (early fail + better UX; CNS-023 Q4 ACCEPT).
- **HITL/approval resume:**
  - `resume_workflow(token, payload)` token kind'a göre `resume_interrupt` (HITL) veya `resume_approval` (governance) route eder
  - Idempotent payload hash (PR-A1 primitive kontratı)
  - Farklı payload → `WorkflowTokenInvalidError`
- **Executor output_ref wiring (B4 absorb):**
  - `Executor.run_step` artık adapter output envelope'ını `{run_dir}/artifacts/{step_id}-attempt{n}.json` dosyasına **atomic write** (tempfile + fsync + rename) ile persist eder
  - `step_record.output_ref = "artifacts/{step_id}-attempt{n}.json"` (run-relative)
  - `adapter_returned` event payload yeni alanlar: `output_ref` (string), `payload_hash` (SHA-256 hex), `attempt` (integer, default 1) — iter-2 MV3 absorb
  - Crash resume: `output_ref` varsa aynı step_record yeniden okunup driver'a dönülür (no re-invoke)
- **DriverResult dataclass (frozen):**
  - `run_id: str`
  - `final_state: Literal["running", "waiting_approval", "interrupted", "completed", "failed", "cancelled"]`
  - `steps_executed: tuple[str, ...]` (step_name + attempt terminal'leri)
  - `steps_failed: tuple[str, ...]`
  - `steps_retried: tuple[str, ...]` (retry_once tetiklenen step_name'ler)
  - `resume_token: str | None`
  - `resume_token_kind: Literal["approval", "interrupt"] | None`
  - `budget_consumed: Budget | None`
  - `duration_seconds: float`
- **Integration tests (≥30):**
  - Happy path 4-step bugfix flow (`multi_step_bugfix.v1.json`): compile_context → invoke_coding_agent → preview_diff → ci_gate → await_approval → apply_patch → open_pr (7 step)
  - retry_once round-trip (`retry_once_flow.v1.json`): attempt=1 fail + attempt=2 pass
  - escalate_to_human flow (`escalate_flow.v1.json`): adapter step fail + `on_failure=escalate_to_human` → waiting_approval → resume approval_granted → continue
  - Budget exhaust mid-flow → `workflow_failed`
  - CI fail-closed: pytest fail → step_failed → `transition_to_failed`
  - HITL interrupt mid-step + resume (payload hash idempotency)
  - Cross-ref mismatch at workflow start → early fail (no step runs)
  - Post-CI governance gate: `verifying → waiting_approval → completed` (post_ci gate path)
- **CHANGELOG:** `[Unreleased]` → Added — FAZ-A PR-A4b entry.

### Scope Dışı (PR-A5/A6 + FAZ-B+ ertelenmiş)

| Alan | Nereye ertelendi | Neden |
|---|---|---|
| `ao-kernel evidence timeline` CLI | PR-A5 | Operatör ergonomisi; A4b evidence yazma tarafını kapatır, okuma tarafı ayrı PR |
| SHA-256 manifest generation on demand | PR-A5 | Manifest CLI-triggered; A4b append-only JSONL yeterli |
| Demo script runnable `.demo/` | PR-A6 | FAZ-A release-gate sonlayıcı |
| `[coding]` meta-extra aktivasyonu | PR-A6 | `pyproject.toml` extras editing + `[llm]` fallback |
| Production adapter manifest fixtures (claude-code-cli / codex-cli / gh-cli-pr) | PR-A6 | `tests/fixtures/adapter_manifests/` bundled, A4b sadece codex-stub kullanır |
| `IntentRouter.llm_fallback` concrete impl | PR-A6 | PR-A2 stub `NotImplementedError`; `[llm]` extra sonrası concrete |
| `context_compile` step gerçek context pipeline wiring | FAZ-B veya PR-A6 | A4b `actor=ao-kernel + operation=context_compile` stubs with no-op result; gerçek context pipeline wiring ayrı scope |
| OS-level network sandbox | FAZ-B | `docs/WORKTREE-PROFILE.md §4` deferred |
| Multi-axis budget decomposition | FAZ-B #7 | A4b cumulative single-axis yeterli |
| Agentic multi-file coherent edits | FAZ-C #11/#12 | Aider patterns, diff primitive'den sonra |
| PR creation via `gh` CLI (actual invocation) | PR-A6 | `gh-cli-pr` adapter manifest bundled PR-A6; A4b `open_pr` step'i adapter routing üzerinden (dry-run olmayan gerçek `gh` call PR-A6 fixture) |

### Bozulmaz İlkeler (A4b'de korunur + ek)

**A4a'dan devralınan (regresyon yok)**

1. **POSIX-only** — `file_lock` + git worktree + patch primitives POSIX.
2. **`inherit_from_parent=False` strict default.**
3. **PATH anchoring realpath + policy prefix** — `validate_command` every primitive entry.
4. **Per-run `events.jsonl.lock` + monotonic `seq`.**
5. **Cross-ref per-call** — `Executor.run_step` her adapter step'te; A4b driver workflow başında da bir kez (double-check ACCEPT).
6. **Canonical event order** — `workflow_started → validate_cross_refs → for step: step_started(payload.attempt) → policy_checked → (policy_denied ⇒ abort) → actor dispatch → step_completed|step_failed → run state CAS → workflow_completed|workflow_failed`.
7. **JSONPath minimal subset** — `$.key(.key)*`.
8. **text/plain fallback triple gate** — adapter output parse.
9. **Patch preflight flag-aligned** — `--check --3way --index -` (A4a).
10. **Reverse diff deterministic path** — `{run_dir}/patches/{patch_id}.revdiff` atomic.
11. **Rollback idempotent** — `git write-tree` SHA pre/post snapshot (A4a).
12. **CI flaky tolerance = 0.**
13. **Retry append-only** — new step_record(attempt=2); `running → running` state edge YOK.
14. **Multi-step state CAS günlük** — `save_run_cas(..., expected_revision=current)`; 1 retry on conflict.
15. **HITL resume idempotent payload.**
16. **`escalate_to_human` transition.** `patch_apply` için yasak (registry schema-level).
17. **`output_ref` durable persistence** — A4b'de wire edilir: `{run_dir}/artifacts/{step_id}-attempt{n}.json` atomic write.
18. **Patch conflict dirty-state cleanup** — `.rej` forensic tar BEFORE `git reset --hard HEAD`.
19. **Primitive-scoped command preflight** — `validate_command` her public primitive entry'sinde bir kez; helper'lar aynı sandbox PATH paylaşır (A4a iter-4 W4 absorb).

**A4b yeni bozulmaz ilkeler**

20. **Driver authoritative-state kuralı (iter-2 MV1 absorb):** `(step_name, highest_attempt)` üzerinden hesaplanır. Highest attempt `failed` + `on_failure=retry_once` + `attempt < 2` ise run HALA retryable (`running` state kalır). Attempt=2 de `failed` olursa terminal `running → failed`. Crash sonrası attempt=2 step_record yoksa + attempt=1 failed + `on_failure=retry_once` → driver resume attempt=2'yi başlatır (retry "consumed" sayılmaz).
21. **Resume konumu derivation:** `run_record.steps[]` terminal (highest-attempt) `completed` kayıtlarının `step_name` listesi + `workflow_definition.steps` sırası karşılaştırılır; tamamlanan step_name'ler skip edilir. `current_step_index` field schema'ya EKLENMEZ.
22. **`adapter_returned.payload.attempt` explicit alan zorunlu (iter-2 MV3 absorb):** event payload stateful backtracking olmadan replay edilebilsin diye `attempt` discriminator. Ayrıca `payload.output_ref` + `payload.output_sha256` alanları (artifact content hash'i, event envelope'ın `payload_hash`'inden AYRI — adapter_returned payload'a `payload_hash` yazılmaz; W1 absorb).
23. **Budget accounting (W3 absorb):** Mevcut fonksiyonel API korunur — `is_exhausted(budget)` + `record_spend(budget, axis, amount) -> Budget`. Driver iter başında `is_exhausted(budget)` kontrol eder. Spend Executor.run_step / patch / ci primitive'leri içinde yapılır; dönen yeni Budget run record'a persist edilir. Wall-clock + subprocess + HITL bekleme hepsi `time_seconds` axis'ine yazılır. HITL bekleme süresi = `approval.requested_at - approval.responded_at` (resume zamanında difference hesaplanır).
24. **Cross-ref workflow-level bir kez:** Driver `run_workflow` girişinde `validate_cross_refs` çağırır → non-empty `issues` list → `transition_to_failed(category="other", code="CROSS_REF", issues=issues)` + `workflow_failed` event + early return (hiçbir step başlamaz). Executor seviyesinde per-step cross-ref korunur (defense in depth, no cache).

**A4b CNS-024 iter-1 absorb ilkeleri (yeni 25-28)**

25. **Executor driver-managed mode (CNS-024 B1 absorb):** `Executor.run_step(step_def, run_record, *, budget=None, context_preamble=None, attempt=1, driver_managed=False)`. `driver_managed=False` (default, A3 backward compat): mevcut davranış — adapter failure run'ı terminal `failed`'e taşır, step_record append Executor'da. `driver_managed=True`: Executor yalnızca (a) worktree + sandbox kurar, (b) adapter_invoker çağırır, (c) artifact atomic write + adapter_returned event payload populate eder, (d) **normalized `ExecutionResult` döner**. Step_record append, run-level state transition (waiting_approval/applying/verifying/failed/cancelled), on_failure dispatch hep driver'ın sorumluluğunda. Adapter failure bu modda `ExecutionResult(status="failed", reason=...)` döner, istisna atmaz — driver karar verir.
26. **Driver entry matrix (CNS-024 B2 absorb):** `MultiStepDriver.run_workflow(run_id, ...)` entry'de run_record.state'e göre dispatch eder:
    - `created` → `created → running` CAS + `workflow_started` event emit + main loop.
    - `running` → `workflow_started` emit ETMEZ; `_completed_step_names(run_record)` ile resume position derive edilir; main loop kaldığı yerden devam.
    - `waiting_approval` / `interrupted` → `DriverTokenRequiredError` (caller `resume_workflow` kullanmalı).
    - Terminal (`completed` / `failed` / `cancelled`): retryable görünüyorsa (attempt=1 failed + on_failure=retry_once + attempt=2 absent) → `DriverStateInconsistencyError(run_state=..., terminal_step_ok=False)`. Değilse idempotent terminal `DriverResult(final_state=..., ...)` return (önceki run sonucunu reinstantiate).
    - `created → running` CAS ile `workflow_started` emit arasındaki crash penceresi: kabul edilen davranış = workflow_started event idempotent skip (evidence emitter event_id opaque → duplicate detect caller tarafında; emit ile CAS ayrı transactional olmadığı için crash'ta `running` state'te workflow_started görünmeyebilir — resume'de driver workflow_started'ı TEKRAR emit etmez, evidence timeline'da eksik kaldığı kabul edilir — PR-A5 replay tool bu durumu tolerate eder).
27. **Retry append-only persistence sırası (CNS-024 B3 absorb):** Deterministik sıra:
    1. Executor (`driver_managed=True`) attempt=1 invocation → `ExecutionResult(status="failed", ...)` döner (step_record append YOK).
    2. Driver: `step_failed` event emit.
    3. Driver CAS: attempt=1 terminal step_record append (`state="failed"`, terminal kayıt).
    4. on_failure=retry_once ise Driver CAS: fresh `step_id`, attempt=2, `state="running"` placeholder step_record append (invocation öncesi).
    5. Driver: Executor (`driver_managed=True`) attempt=2 invocation.
    6. Başarılı → `step_record(attempt=2).state="completed"` CAS update. Başarısız → `step_record(attempt=2).state="failed"` CAS update + `_transition_to_failed(category="other", code="RETRY_EXHAUSTED")`.
    Resume kuralları: (a) attempt=2 placeholder (`state="running"`) varsa → attempt=2 invocation'ı yeniden yap (placeholder'ı tamamla, attempt=3 yaratma); (b) attempt=2 step_record yok + attempt=1 `state="failed"` + `on_failure="retry_once"` → attempt=2 placeholder CAS append + invoke (retry consumed değil).
28. **Failure reason → schema error.category mapping (CNS-024 B4 absorb):** `workflow-run.schema.v1.json::$defs/error_record.category` kapalı enum. Driver failure'ları bu enum'a map eder + machine-readable detay `error.code` + human-readable `error.message` alanlarında tutulur + evidence payload `reason` ayrı:
    | Driver failure source | error.category | error.code | error.message (örn) |
    |---|---|---|---|
    | Budget exhausted | `budget_exhausted` | `BUDGET_EXHAUSTED` | "budget axis X exhausted" |
    | CI check fail | `ci_failed` | `CI_CHECK_FAILED` | "pytest/ruff non-zero exit" |
    | Patch conflict | `apply_conflict` | `PATCH_APPLY_CONFLICT` | "3-way reject, N files" |
    | Approval denial | `approval_denied` | `APPROVAL_DENIED` | "human reviewer denied" |
    | Cross-ref mismatch | `other` | `CROSS_REF` | "missing adapter X / capability gap Y" |
    | Unsupported operation (e.g. ci_mypy) | `other` | `UNSUPPORTED_OPERATION` | "operation=ci_mypy has no runner" |
    | Driver state inconsistency | `other` | `STATE_INCONSISTENCY` | "terminal failed but retryable" |
    | Retry exhausted | `other` | `RETRY_EXHAUSTED` | "attempt=2 failed, no further retries" |

    Event payload `reason` alanında machine-readable `code` değeri yazılır; `error.category` schema-legal kalır.
29. **Approval idempotency decision-only (CNS-024 B5 absorb):** `MultiStepDriver.resume_workflow(run_id, resume_token, payload)` — approval token durumunda `payload` yalnızca `{"decision": "granted"|"denied", "notes": str | None}` kabul eder; **idempotency key sadece `decision`**. Aynı decision ile tekrar çağrı → no-op idempotent return. Farklı decision → `WorkflowTokenInvalidError`. `notes` alanı `approval_granted`/`approval_denied` event payload'ında redacted metadata olarak emit edilir, **idempotency hash'ine katılmaz**, schema'ya persist edilmez (PR-A1 `Approval` dataclass + primitive kontratına sadık). Interrupt token durumunda ise PR-A1 `resume_interrupt` full payload hash kontratı aynen geçerli (primitive zaten bu kontratı uyguluyor).

---

## 3. Write Order (bağımlılık DAG)

```
Layer 0 — Executor output_ref wiring (prereq)
  1. ao_kernel/executor/executor.py
     - _write_artifact helper (atomic write + SHA-256)
     - Executor.run_step adapter invocation path:
       * adapter_returned event payload: output_ref + output_sha256 + attempt
       * step_record.output_ref CAS update
     - No public API break (attempt parameter kwargs-only, default 1)

Layer 1 — MultiStepDriver
  2. ao_kernel/executor/multi_step_driver.py
     - DriverResult dataclass + DriverStateConflictError + DriverBudgetExhaustedError
     - MultiStepDriver class + run_workflow + resume_workflow
     - Actor/operation dispatch helpers (_run_adapter_step, _run_patch_step,
       _run_ci_step, _run_human_gate)
     - on_failure dispatch (_handle_step_failure)
     - retry append-only (_append_attempt_record)
     - CAS conflict handling (_cas_retry_once)
     - Budget gating + cross-ref workflow-level

Layer 2 — Facade update
  3. ao_kernel/executor/__init__.py
     - Re-export MultiStepDriver + DriverResult + DriverStateConflictError
     - Re-export DriverBudgetExhaustedError

Layer 3 — Fixtures + integration tests
  4. tests/fixtures/workflows/multi_step_bugfix.v1.json  (7-step happy path)
  5. tests/fixtures/workflows/retry_once_flow.v1.json     (2-step, step2 on_failure=retry_once)
  6. tests/fixtures/workflows/escalate_flow.v1.json       (2-step, step2 on_failure=escalate_to_human)
  7. tests/test_multi_step_driver.py                      (~20 test, unit driver behaviors)
  8. tests/test_multi_step_driver_integration.py          (~13 test, e2e via codex_stub
                                                            + real pytest/ruff subprocess)

Layer 4 — CHANGELOG + docs polish
  9. CHANGELOG.md [Unreleased] → Added — FAZ-A PR-A4b
```

Bağımlılık: **Layer 0 → Layer 1 → Layer 2 → Layer 3 → Layer 4**. Layer 0 (Executor delta) A4b'nin B4 absorb'u; driver ona bağımlı.

---

## 4. Module — `ao_kernel/executor/executor.py` delta

### Public API (A4b eklentileri)

```python
# Existing signature (A3):
# def run_step(self, step_def, run_record, *, budget=None, context_preamble=None) -> ExecutionResult

# A4b adds:
def run_step(
    self,
    step_def: StepDefinition,
    run_record: Mapping[str, Any],
    *,
    budget: Budget | None = None,
    context_preamble: str | None = None,
    attempt: int = 1,      # NEW: retry attempt number; default 1 for first attempt
) -> ExecutionResult: ...
```

### Internal additions

- `_write_artifact(run_dir: Path, step_id: str, attempt: int, payload: Mapping[str, Any]) -> tuple[str, str]`
  - Returns `(output_ref, output_sha256)` — `output_ref` is run-relative path `artifacts/{step_id}-attempt{attempt}.json`, `output_sha256` is hex of canonical JSON (`sort_keys=True, ensure_ascii=False`)
  - Atomic write: tempfile in `{run_dir}/artifacts/` + fsync + rename
  - Returns early if file already exists + same content (crash recovery idempotency)

### Behavioural changes

1. Adapter invocation (`invoke_cli` / `invoke_http`) returns output_envelope; `Executor.run_step` passes it through `_write_artifact` before emitting `adapter_returned`.
2. `adapter_returned` event payload gains `output_ref`, `output_sha256`, `attempt` (existing keys preserved).
3. `step_record.output_ref` populated via CAS mutator (`run_store.save_run_cas`).
4. `step_record.attempt` populated from the new `attempt` kwarg (default 1 for first-attempt backward compat).
5. No behavioural change for adapter-less code paths (Executor.run_step is adapter-only; patch/ci invocations handled in driver).

### Design decisions

- **`attempt` kwarg, not positional:** callers that don't pass `attempt` get `1`, preserving A3 behaviour.
- **Artifact path under `artifacts/` (not `patches/`):** reverse diffs live in `patches/` (A4a); generic output envelopes in `artifacts/`. Separate namespaces prevent collision.
- **SHA-256 computed from canonical JSON:** replay tool can verify artifact content without re-parsing stdout.
- **No new evidence event kind:** `adapter_returned` gains payload fields only (existing kind, 18-kind whitelist intact).

---

## 5. Module — `ao_kernel/executor/multi_step_driver.py`

### Public API

```python
@dataclass(frozen=True)
class DriverResult:
    run_id: str
    final_state: Literal["running", "waiting_approval", "interrupted",
                         "completed", "failed", "cancelled"]
    steps_executed: tuple[str, ...]
    steps_failed: tuple[str, ...]
    steps_retried: tuple[str, ...]
    resume_token: str | None
    resume_token_kind: Literal["approval", "interrupt"] | None
    budget_consumed: Budget | None
    duration_seconds: float


class DriverStateConflictError(Exception):
    """Two CAS retries failed — concurrent writer detected."""


class DriverBudgetExhaustedError(Exception):
    """Budget axis went negative mid-step."""


class MultiStepDriver:
    def __init__(
        self,
        workspace_root: Path,
        registry: WorkflowRegistry,
        adapter_registry: AdapterRegistry,
        executor: Executor,
        *,
        policy_config: Mapping[str, Any],
        evidence_sink: EvidenceEmitter,  # PR-A3 type
    ) -> None: ...

    def run_workflow(
        self,
        run_id: str,
        workflow_id: str,
        workflow_version: str,
        *,
        budget: Budget | None = None,
        context_preamble: str | None = None,
    ) -> DriverResult: ...

    def resume_workflow(
        self,
        run_id: str,
        resume_token: str,
        payload: Mapping[str, Any] | None = None,
    ) -> DriverResult: ...
```

### Core loop (pseudocode — v2 invariant-accurate with B1/B2/B3 absorbed)

```python
def run_workflow(self, run_id, workflow_id, workflow_version, *, budget=None, context_preamble=None):
    start = time.monotonic()
    definition = self.registry.get(workflow_id, version=workflow_version)
    run_record = self.run_store.load_run(self.workspace_root, run_id)

    # CNS-024 B2 absorb: driver entry matrix (not a plain `created` assert)
    state = run_record["state"]
    if state == "created":
        run_record = self._cas_state_transition(run_id, run_record, new_state="running",
                                                 extra={"started_at": now_iso()})
        self.evidence.emit_event(
            workspace_root=self.workspace_root, run_id=run_id,
            kind="workflow_started", actor="ao-kernel",
            payload={"workflow_id": workflow_id, "workflow_version": workflow_version},
        )
    elif state == "running":
        # Resume from derived position; do NOT re-emit workflow_started
        # (evidence timeline may be missing it if crash landed between
        # CAS and emit — PR-A5 replay tool tolerates gap).
        pass
    elif state in ("waiting_approval", "interrupted"):
        raise DriverTokenRequiredError(
            run_id=run_id, state=state,
            hint="use resume_workflow(run_id, resume_token, payload)",
        )
    elif state in ("completed", "failed", "cancelled"):
        # Terminal idempotent return OR inconsistency error if
        # (step_name, highest_attempt) says retry is still available.
        if self._is_retryable_terminal(run_record, definition):
            raise DriverStateInconsistencyError(
                run_state=state, terminal_step_ok=False,
                reason="highest-attempt failed + on_failure=retry_once + attempt<2",
            )
        return self._idempotent_terminal_result(run_id, run_record, state, start)
    else:
        raise WorkflowStateCorruptedError(state=state)

    # Workflow-level cross-ref (early fail + better UX; invariant #24)
    issues = self.registry.validate_cross_refs(definition, self.adapter_registry)
    if issues:
        return self._transition_to_failed(run_id, run_record, reason="cross_ref",
                                           issues=[_issue_as_dict(i) for i in issues])

    completed_names = self._completed_step_names(run_record)

    for step_def in definition.steps:
        # Idempotent skip completed
        if step_def.step_name in completed_names:
            continue

        # Budget gate
        if budget and budget.is_exhausted():
            return self._transition_to_failed(run_id, run_record,
                reason="budget_exhausted", failed_step=step_def.step_name)

        # Pre-step governance gate (step_def.gate != None)
        if step_def.gate is not None:
            token = mint_approval_token(run_id=run_id, step_name=step_def.step_name)
            run_record = self._cas_state_transition(run_id, run_record,
                new_state="waiting_approval",
                extra={"approvals": [*run_record.get("approvals", []), _approval_pending(token)]})
            self.evidence.emit_event(..., kind="approval_requested",
                payload={"step_name": step_def.step_name, "gate": step_def.gate})
            return DriverResult(run_id=run_id, final_state="waiting_approval",
                resume_token=token, resume_token_kind="approval",
                steps_executed=tuple(completed_names), ...)

        # Step dispatch by actor/operation
        try:
            attempt = self._next_attempt_number(run_record, step_def.step_name)
            if step_def.actor == "adapter":
                step_result = self._run_adapter_step(step_def, run_record, budget,
                                                     context_preamble, attempt=attempt)
            elif step_def.actor == "ao-kernel":
                step_result = self._run_aokernel_step(step_def, run_record, attempt=attempt)
            elif step_def.actor == "system":
                step_result = self._run_system_step(step_def, run_record, attempt=attempt)
            elif step_def.actor == "human":
                return self._run_human_gate(run_id, run_record, step_def)
            else:
                raise WorkflowDefinitionCorruptedError(reason="unknown_actor",
                                                       actor=step_def.actor)
        except _StepFailed as sf:
            return self._handle_step_failure(run_id, run_record, step_def, sf, budget)

        # Step succeeded — CAS record + continue
        run_record = self._record_step_completion(run_id, run_record, step_def,
                                                   step_result, attempt=attempt)
        completed_names.add(step_def.step_name)

    # All steps done
    return self._transition_to_completed(run_id, run_record,
        duration=time.monotonic() - start, budget=budget)


def _handle_step_failure(self, run_id, run_record, step_def, failure, budget):
    on_failure = step_def.on_failure
    self.evidence.emit_event(..., kind="step_failed",
        payload={"step_name": step_def.step_name, "reason": failure.reason,
                 "attempt": failure.attempt})

    if on_failure == "transition_to_failed":
        return self._transition_to_failed(run_id, run_record, reason=failure.reason,
                                           failed_step=step_def.step_name)

    if on_failure == "retry_once":
        if failure.attempt >= 2:
            # Terminal — RETRY_EXHAUSTED code (B4 mapping)
            return self._transition_to_failed(
                run_id, run_record, failed_step=step_def.step_name,
                category="other", code="RETRY_EXHAUSTED",
                message=f"attempt=2 failed: {failure.reason}",
            )
        # CNS-024 B3 persistence order:
        # 1. Failed attempt=1 terminal step_record append (CAS)
        run_record = self._append_failed_attempt_record(
            run_id, run_record, step_def, attempt=failure.attempt,
            reason=failure.reason,
        )
        # 2. attempt=2 placeholder step_record (fresh step_id, state=running) append BEFORE invocation
        run_record, placeholder_step_id = self._append_attempt_placeholder(
            run_id, run_record, step_def, attempt=2,
        )
        # 3. Invoke attempt=2 through driver-managed Executor (B1)
        try:
            step_result = self._run_step_by_actor(
                step_def, run_record, budget, attempt=2, step_id=placeholder_step_id,
            )
        except _StepFailed as sf2:
            # attempt=2 failed — update placeholder to terminal failed + RETRY_EXHAUSTED
            run_record = self._update_placeholder_to_failed(
                run_id, run_record, placeholder_step_id, reason=sf2.reason,
            )
            return self._transition_to_failed(
                run_id, run_record, failed_step=step_def.step_name,
                category="other", code="RETRY_EXHAUSTED",
                message=f"attempt=2 failed: {sf2.reason}",
            )
        # 4. attempt=2 success — update placeholder to completed
        run_record = self._update_placeholder_to_completed(
            run_id, run_record, placeholder_step_id, step_result, attempt=2,
        )
        return self._continue_loop_after_retry(run_id, run_record, step_def, budget)

    if on_failure == "escalate_to_human":
        token = mint_approval_token(run_id=run_id, step_name=step_def.step_name)
        run_record = self._cas_state_transition(run_id, run_record,
            new_state="waiting_approval",
            extra={"approvals": [*run_record.get("approvals", []),
                                  _approval_pending(token, reason=failure.reason)]})
        self.evidence.emit_event(..., kind="approval_requested",
            payload={"step_name": step_def.step_name, "escalation": True,
                     "failure_reason": failure.reason})
        return DriverResult(run_id=run_id, final_state="waiting_approval",
            resume_token=token, resume_token_kind="approval", ...)
```

### Design decisions

- **`_run_aokernel_step` dispatches by `step_def.operation`:**
  - `operation=patch_preview` → `ao_kernel.patch.preview_diff(...)`
  - `operation=patch_apply` → `ao_kernel.patch.apply_patch(...)` + artifact write via `_write_artifact`
  - `operation=patch_rollback` → `ao_kernel.patch.rollback_patch(...)`
  - `operation=context_compile` → **A4b stub**: returns minimal `StepResult` with empty context preamble (real context pipeline wiring in PR-A6 or FAZ-B)
- **`_run_system_step` dispatches similarly:**
  - `operation=ci_pytest` → `ao_kernel.ci.run_pytest(...)` + artifact write
  - `operation=ci_ruff` → `ao_kernel.ci.run_ruff(...)` + artifact write
  - `operation=ci_mypy` → **A4b rejects explicitly** (CI runner not implemented; falls through to `_StepFailed(reason="unsupported_operation")`)
- **`_next_attempt_number(run_record, step_name)`:** scans `run_record["steps"]` for entries with matching `step_name`, returns `max(attempt) + 1` or `1` if none exist — crash-safe resume support.
- **`_completed_step_names(run_record)`:** returns set of `step_name` where highest-attempt step_record has `state="completed"` — resume position derivation (invariant #21).
- **CAS conflict retry logic (invariant #14):**
  - First CAS attempt uses `expected_revision = run_record["revision"]`
  - On `WorkflowCASConflictError`: reload run_record, re-compute mutation, retry once
  - Second conflict: `DriverStateConflictError` (caller must abort)
- **Budget tracking:** `budget.record_spend(axis, value)` called within adapter_invoker / ci runners (A4a contract); driver only checks `budget.is_exhausted()` between steps (invariant #23).

---

## 6. Module — `ao_kernel/executor/__init__.py` delta

```python
# Existing exports (A3) preserved.
# New exports (A4b):
from .multi_step_driver import (
    DriverBudgetExhaustedError,
    DriverResult,
    DriverStateConflictError,
    MultiStepDriver,
)

__all__ = [
    # ... existing PR-A3 exports ...
    "DriverBudgetExhaustedError",
    "DriverResult",
    "DriverStateConflictError",
    "MultiStepDriver",
]
```

---

## 7. Test Strategy

### Coverage targets

| Modül | Target branch cov |
|---|---|
| `ao_kernel/executor/multi_step_driver.py` | ≥ 85% |
| `ao_kernel/executor/executor.py` delta | ≥ 88% (new `_write_artifact` + output_ref wiring) |
| **Overall (post-A4b)** | **≥ 85.5%** (gate 85 retained) |

### Test file breakdown (target: ≥ 30 new tests, target total 1477+)

| File | ~tests | Focus |
|---|---|---|
| `tests/test_multi_step_driver.py` | 20 | `DriverResult` shape; per-step CAS; retry append-only (new step_record attempt=2); escalate_to_human transition; transition_to_failed; cross-ref early fail; budget exhaust; resume_workflow approval granted; resume_workflow interrupt payload hash; unknown actor rejection; step order idempotency (re-run skips completed); CAS conflict retry-once logic; `DriverStateConflictError` on double conflict; `ci_mypy` rejection; `context_compile` stub behaviour |
| `tests/test_multi_step_driver_integration.py` | 13 | E2E 7-step bug_fix_flow via codex_stub adapter + real subprocess pytest/ruff + workflow_started/completed events; retry_once integration (step1 fail → retry pass → continue); escalate_to_human integration (adapter fail → waiting_approval → resume → continue); patch apply + rollback chain; CI fail-closed workflow_failed |

### Fixtures

- `tests/fixtures/workflows/multi_step_bugfix.v1.json` — 7 steps:
  1. `compile_context` (ao-kernel, `operation=context_compile`)
  2. `invoke_coding_agent` (adapter=codex-stub, capabilities=[read_repo, write_diff])
  3. `preview_diff` (ao-kernel, `operation=patch_preview`)
  4. `ci_gate` (system, `operation=ci_pytest`)
  5. `await_approval` (human, `gate=pre_apply`)
  6. `apply_patch` (ao-kernel, `operation=patch_apply`, `on_failure=retry_once`)
  7. `open_pr` (adapter=gh-cli-pr — A4b uses codex-stub substitute for testing)
- `tests/fixtures/workflows/retry_once_flow.v1.json` — 2 steps: adapter invocation with `on_failure=retry_once`, then completion step.
- `tests/fixtures/workflows/escalate_flow.v1.json` — 2 steps: adapter invocation with `on_failure=escalate_to_human`, then completion step.
- Reuse `tests/_patch_helpers.py::build_test_sandbox` for the sandbox parameter.
- Reuse `ao_kernel/fixtures/codex_stub.py` for deterministic adapter invocation.

### CI subprocess budget (integration tests)

- Per-test subprocess cap: 4 (pytest + ruff + git apply + gh-cli-pr stub)
- Per-test timeout: 15s (hermetic micro-repo)
- Total CI subprocess count across integration suite: ≤ 40
- Micro-repo fixture reused from A4a.

### Test quality gate (A4a + conftest.py ruleset intact)

- BLK-001/002/003 scan applied at collection time.
- Behaviour-first assertions: no `issubclass` hierarchy tests, no default-value-only tests — each new test asserts an observable contract.

---

## 8. Acceptance Criteria

### Module + test

- [ ] 1 yeni src modül (`multi_step_driver.py`) + 2 delta (`executor.py`, `executor/__init__.py`)
- [ ] 3 yeni workflow fixture
- [ ] ≥ 30 yeni test pass
- [ ] `ruff check ao_kernel/ tests/` clean
- [ ] `mypy ao_kernel/ --ignore-missing-imports` 0 error
- [ ] Branch coverage `--cov-fail-under=85` gate geçer
- [ ] 1477+ total test

### End-to-end (docs/DEMO-SCRIPT.md steps 4-8)

- [ ] `multi_step_bugfix.v1` 7-step happy path → `workflow_completed`
- [ ] retry_once: adapter step1 fail + attempt=2 pass → continue → `workflow_completed`
- [ ] escalate_to_human: adapter step1 fail + `on_failure=escalate_to_human` → `waiting_approval` → resume (`approval_granted`) → next step → `workflow_completed`
- [ ] escalate_to_human denial path: resume with `decision=deny` → `workflow_cancelled`
- [ ] transition_to_failed: patch_apply conflict (A4a `PatchApplyConflictError`) → `step_failed` → `workflow_failed`
- [ ] CI fail-closed: pytest fail → `test_executed(status=fail)` → `step_failed` → `workflow_failed`
- [ ] Budget exhaust mid-flow: budget.time_seconds exhausted → `transition_to_failed(reason=budget_exhausted)`
- [ ] Cross-ref mismatch at start: workflow with missing adapter ref → `workflow_failed` + no step_started
- [ ] `adapter_returned` event payload has `output_ref`, `output_sha256`, `attempt`
- [ ] `step_record.output_ref` points to `artifacts/{step_id}-attempt{n}.json` with matching SHA-256

### Regression (A4a + prior invariants)

- [ ] A4a test suite (test_patch_*, test_ci_runners, test_workflow_registry_operation, test_patch_internals) all pass (no flakes)
- [ ] PR-A3 test suite (test_policy_enforcer, test_evidence_emitter, test_adapter_invoker, test_worktree_builder, test_executor, test_executor_integration) all pass
- [ ] Evidence 18-kind whitelist intact (no new kinds added by A4b)
- [ ] Schema v1 files unchanged (operation + attempt from A4a authoritative)
- [ ] `running → running` state edge STILL absent (retry model append-only, not state-loop)

---

## 9. Risk & Mitigation

| Risk | Level | Mitigation |
|---|---|---|
| `ao_kernel/executor/executor.py` output_ref wiring breaks PR-A3 test assumptions | **Orta** | `attempt` kwarg default=1 (backward compat); `output_ref` written only when run_dir present; existing test fixtures don't assert absence of output_ref |
| Driver CAS conflict retry race under concurrent writer | Düşük | 1-retry bound + typed `DriverStateConflictError` surfaces caller; integration test simulates concurrent `save_run_cas` |
| Crash mid-retry — attempt=2 step_record absent after append | **Orta** | Invariant #20: driver resume rule "attempt=2 yoksa + attempt=1 failed + on_failure=retry_once → retry başlat"; integration test simulates crash between `_append_attempt_record` CAS + `_run_step_by_actor` invocation |
| Budget exhaust mid-adapter invocation → partial state | Düşük | Exhaust check is between steps; mid-step exhaust is adapter/primitive's own axis accounting; terminal `step_failed(reason=budget_exhausted)` unified |
| HITL + approval token conflation | Düşük | PR-A1 `mint_interrupt_token` vs `mint_approval_token` ayrı domain; `resume_workflow` token kind discriminator param |
| `context_compile` stub yanıltıcı | Düşük | A4b docstring + PR body explicit "stub: real context pipeline wiring PR-A6/FAZ-B"; integration test asserts empty preamble |
| `ci_mypy` operation in schema but no runner | Düşük (CNS-023 iter-4 W2) | A4b driver raises `_StepFailed(reason="unsupported_operation")` + failure path; integration test asserts this explicit rejection |
| Schema v1 state_enum `skipped` never used by A4b | Düşük | `skipped` reserved for FAZ-D native branching (#9); A4b never emits it |
| `gh-cli-pr` adapter fixture absent in A4b | Düşük (plan scope) | A4b fixture uses codex-stub substitute for `open_pr` step; PR-A6 lands production gh-cli-pr manifest + real adapter |
| Integration subprocess timeouts on slow CI | Düşük | Per-test 15s cap; pytest `--timeout=60` per-test safety net via `pytest-timeout` (dev extra, not runtime) |
| Helper git calls policy scope (W4 from A4a) | Closed | A4a docstring absorb; A4b driver doesn't introduce new git invocations |
| Post-merge docs drift (17/ULID) | Closed | A4a iter-4 W1 absorbed; A4b no evidence taxonomy change |

---

## 10. CNS-024 iter-2 Verification Prompt (micro-fix check)

**Hedef format** (CNS-022 iter-2 pattern): her iter-1 blocker + warning için `{id, fixed: bool, note}` micro verdicts; `new_blocking_objections: []` (ideally); `residual_warnings: [...]`; `ready_for_impl: true`; `pr_split_recommendation: single_pr`.

### Plan v2 absorption map (Codex'e teyit için)

| iter-1 ID | Plan v2 yeri | Çözüm |
|---|---|---|
| **B1** Executor run-level terminal vs driver on_failure | §2 ilke #25 + §3 Layer 0 + §4 API | `Executor.run_step(..., driver_managed=False)` default A3 backward compat; `driver_managed=True` mod: Executor artifact + event + ExecutionResult; step_record + run-level CAS driver'da. Adapter failure `ExecutionResult(status="failed")` döner, istisna atmaz. |
| **B2** Entry matrix `created` assert → multi-state dispatch | §5 Core loop pseudocode + §2 ilke #26 | `created` → başlat; `running` → resume position derive; `waiting_approval/interrupted` → `DriverTokenRequiredError`; terminal retryable → `DriverStateInconsistencyError`; terminal non-retryable → idempotent terminal return. |
| **B3** Retry persistence order | §5 pseudocode _handle_step_failure + §2 ilke #27 | 4-aşamalı deterministik: failed attempt=1 terminal CAS → attempt=2 placeholder CAS (state=running) → invocation → placeholder completed/failed update. Resume: attempt=2 placeholder varsa invocation yeniden; yoksa + attempt=1 failed + on_failure=retry_once → placeholder append + invoke. |
| **B4** Failure reason → schema error.category enum | §2 ilke #28 mapping tablosu | Enum-legal `category` + machine `code` + human `message` + evidence payload `reason` ayrı. 8-satır mapping tablosu §2'de. |
| **B5** Approval notes full-hash idempotency | §2 ilke #29 | Idempotency key = **decision-only**. Notes `approval_granted/denied` event payload'da redacted metadata, hash'e katılmaz, schema'ya persist edilmez. PR-A1 primitive kontratı korunur. |
| W1 `adapter_returned.payload_hash` kalıntısı | §2 ilke #22 netleşti | Adapter payload'a `payload_hash` yazılmaz; event envelope alanı kalır. `output_ref + output_sha256 + attempt`. |
| W2 `_write_artifact` ownership | §3 Layer 0 + §4.5 yeni | `ao_kernel/executor/artifacts.py` package-private helper modülü. Canonical JSON `sort_keys=True, ensure_ascii=False, separators=(",",":")`; directory fsync beklentisi test. |
| W3 Budget API pseudocode drift | §2 ilke #23 güncel | Fonksiyonel API: `is_exhausted(budget)` + `record_spend(budget, axis, value) -> Budget`. Dönen yeni Budget CAS ile persist. |
| W4 State machine pre-apply CI akışı | §2 ilke #28 dispatch map + §9 Risk | Driver dispatch: `patch_preview` / `ci_pytest` / `ci_ruff` → run state `running` kalır (transition yok). `patch_apply` → `running → applying`. Post-apply CI → `applying → verifying`. Post-CI governance gate → `verifying → waiting_approval`. Pre-apply CI için gate=post_ci **kullanılmaz**; pre-apply flow için gate=pre_apply yeterli. |
| W5 `context_compile` stub visibility | §2 ilke #25 + §4.5 artifacts | `step_completed` payload'a `stub: True, operation: "context_compile", context_preamble_bytes: 0` eklenir; evidence noise yok, operatör replay'de stub görünür. |
| W6 Adapter artifact content shape | §2 ilke #22 + §4.5 | Artifact = **normalized InvocationResult dict**: `{status, diff, error, finish_reason, commands_executed, cost_actual, stdout_tail_ref, stderr_tail_ref}`. Canonical JSON hash. Raw envelope fallback değil — deterministic. |
| W7 `ci_mypy` reject — `run_all` skip düşmesin | §2 ilke #28 + §5 dispatch | Driver `operation=="ci_mypy"` explicit `_StepFailed(category="other", code="UNSUPPORTED_OPERATION")`; `run_all` çağrılmaz. |

### 4 micro-verification sorusu (iter-2)

**MV1 — `driver_managed=True` mode backward compat.** A3 test suite hala `driver_managed=False` (default) ile çalışıyor. Bu default davranış Executor.run_step'in mevcut adapter-failure-terminalize yolunu korur. A4b testi `driver_managed=True` ile çalışır. Bu dual-mode acceptable mi, yoksa A4b single-mode (tüm çağrılar `driver_managed=True`) + A3 test suite güncellemesi mi? Draft: dual-mode (A3 contract uncharged, regression zero).

**MV2 — Placeholder state semantiği.** attempt=2 placeholder `state="running"` olarak append ediliyor. Bu per-step state; run-level state zaten `running`. Schema `step_record.state` enum'u `running` kabul ediyor mu? (workflow-run schema state_enum içinde mi yoksa sadece run-level mi?) Draft: per-step state enum aynı — `running` legal. Teyit?

**MV3 — Error mapping "other" category yoğunluğu.** §2 ilke #28 mapping tablosunda 3 satır (CROSS_REF, UNSUPPORTED_OPERATION, STATE_INCONSISTENCY, RETRY_EXHAUSTED) `category="other"` altına düşüyor. `error.category` enum'a yeni değer eklemek yerine (schema breaking), `code` alanı ayrımı yeterli mi? Draft: yeterli. Category = operator triage axis (UI filtering), code = machine-readable detay.

**MV4 — Idempotent terminal return içeriği.** Driver entry matrix'te terminal non-retryable state → `_idempotent_terminal_result(run_id, run_record, state, start)` önceki run sonucunu reconstruct eder. Bunu hangi alanlardan: `final_state=run_record["state"]`, `steps_executed=` tamamlanmış step_name'ler, `duration_seconds=updated_at-started_at`, `budget_consumed=run_record.budget`? Yeterli mi, `steps_retried` + `resume_token` null eksik değil mi?

---

## 10a. (v1 historical) CNS-024 iter-1 spec-level sorular

Plan v1'de Codex'e submit edilen 8 spec-level sorular:

8 spec-level soru. Her biri concrete yanıt isteyen:

**Q1 — Driver authoritative state under retry append-only model.** A4a iter-2 MV1 answered: run remains `running` while attempt=1 is failed + `on_failure=retry_once` + attempt<2. A4b plan encodes this as invariant #20. Driver implementation reads `run_record["state"]` at resume entry — if state is already `failed` (e.g., prior CAS wrote terminal on the wrong path), does the driver surface an inconsistency error, silently retry, or hard-fail? Proposed: inconsistency error (`DriverStateInconsistencyError(run_state=failed, terminal_step_ok=False)`). Acceptable?

**Q2 — CAS conflict retry bound.** Driver does 1 re-read + re-mutate on `WorkflowCASConflictError`. Is one retry enough, or should it be `max_retries: int = 1` kwarg for caller tuning? Proposed: fixed 1 (concurrent writer is a rare edge case; bounded avoids runaway). Reasonable, or make it configurable?

**Q3 — `adapter_returned.payload.output_ref` + `output_sha256` naming.** A4a iter-2 MV3 said: rename avoid collision with event envelope's `payload_hash`. Proposed payload fields: `output_ref` (string, run-relative path), `output_sha256` (hex), `attempt` (integer). Does this naming survive the replay tool's expectations? Should `output_sha256` be namespaced (e.g., `artifact_sha256`) for clarity?

**Q4 — `context_compile` stub behaviour.** A4b scope treats `actor=ao-kernel AND operation=context_compile` as a stub returning empty preamble. Production wiring deferred to PR-A6 or FAZ-B. Should the stub emit a warning log / evidence event to make the stubbing visible, or silently produce an empty `StepResult`? Proposed: silent no-op with docstring warning (evidence would add noise). Which?

**Q5 — `ci_mypy` operation in schema but no runner in A4a/A4b.** A4a CNS-023 iter-4 W2 flagged. Options:
  - (A) A4b driver rejects `ci_mypy` step with explicit `_StepFailed(reason="unsupported_operation")` (fail-closed surface)
  - (B) A4b adds `run_mypy` runner (scope creep)
  - (C) A4b removes `ci_mypy` from enum (schema change, breaks backward compat)
Proposed: (A). Defensible?

**Q6 — Resume workflow payload hash scope.** PR-A1 `resume_interrupt` takes `payload` + hash check; `resume_approval` takes only `decision` (no payload). A4b `resume_workflow` wraps both: interrupt token → full payload hash check; approval token → decision enum + optional notes (notes hashed for idempotency?). Proposed: approval payload = `{"decision": "granted"|"denied", "notes": str | None}`; hash the full dict. Consistent? Or approval should stay decision-only (A4a primitive model)?

**Q7 — Cross-ref double-check performance.** A4b driver adds workflow-level cross-ref + PR-A3 executor per-step cross-ref (CNS-023 Q4 ACCEPT). For a 10-step workflow with 3 adapter invocations, that's 1 (driver) + 3 (executor per adapter) = 4 cross-ref calls. Acceptable overhead, or should driver cache result + pass flag to Executor to skip per-step? Proposed: no cache (A4a invariant — adapter registry mutable; per-step stays as-is). Safe?

**Q8 — PR-A4b single-PR scope recheck.** Plan v2 projected ~1855 LOC for A4b vs A4a's ~2050. Split_2_pr approved. Any reason to split A4b further (e.g., Executor `output_ref` wiring as separate PR-A4b-pre, driver as A4b-main)? Proposed: single A4b PR — the wiring is tightly coupled to the driver's dispatch path; splitting creates interface drift risk (same reason 3-parça was rejected for A4a). Accept?

---

## 11. CHANGELOG Update

`CHANGELOG.md` [Unreleased] altına eklenecek (A4a entry'sinden sonra):

```markdown
### Added — FAZ-A PR-A4b (multi-step driver + Executor output_ref wiring)

- `ao_kernel/executor/multi_step_driver.py`: `MultiStepDriver` class
  that iterates `workflow_definition.steps` with actor + operation
  dispatch (adapter → `Executor.run_step`; ao-kernel +
  operation=context_compile/patch_* → internal primitives; system +
  operation=ci_* → CI runners; human → waiting_approval gate),
  handles `on_failure` (transition_to_failed / retry_once /
  escalate_to_human), emits workflow-level evidence events
  (`workflow_started`, `workflow_completed`, `workflow_failed`), and
  performs per-step CAS via `run_store.save_run_cas` with 1-retry
  conflict handling (`DriverStateConflictError` on double conflict).
  Resume position is derived from `run_record.steps[]` terminal
  (highest-attempt) `completed` entries — no `current_step_index`
  field added to the run schema.
- Retry append-only model: step failure + `on_failure=retry_once`
  appends a new `step_record(attempt=2)` with a fresh `step_id`
  (same `step_name`) under CAS BEFORE re-invocation; crash-safety
  rule: absent attempt=2 + failed attempt=1 + `on_failure=retry_once`
  → driver resume starts attempt=2 (retry is NOT consumed). Run
  state remains `running` while retry is available; only a second
  fail transitions to terminal `failed`.
- `escalate_to_human` flow: failure + `on_failure=escalate_to_human`
  mints an approval token via PR-A1 `mint_approval_token`, emits
  `approval_requested`, transitions run state to `waiting_approval`,
  and returns `DriverResult(final_state="waiting_approval",
  resume_token=..., resume_token_kind="approval")`. `patch_apply`
  combination with `escalate_to_human` is forbidden at the schema +
  registry level (A4a invariant; driver-side re-checks).
- `ao_kernel/executor/executor.py` `Executor.run_step`: new
  kwargs-only `attempt: int = 1` parameter + `_write_artifact`
  helper that persists adapter output envelopes to
  `{run_dir}/artifacts/{step_id}-attempt{n}.json` via atomic write
  (tempfile + fsync + rename). `step_record.output_ref` and new
  `adapter_returned` event payload fields `output_ref`,
  `output_sha256`, `attempt` (CNS-023 iter-2 MV3 absorb) make
  adapter outputs durable across crash/resume and deterministic for
  evidence replay.
- `MultiStepDriver.resume_workflow(run_id, resume_token, payload)`
  routes approval tokens to `primitives.resume_approval` and
  interrupt tokens to `primitives.resume_interrupt`; idempotent by
  payload hash (approval payload = `{"decision", "notes"}` dict;
  interrupt payload = PR-A1 primitive contract). Different payload
  → `WorkflowTokenInvalidError`.
- Workflow-level cross-ref check at driver entry (invariant #24) +
  PR-A3 per-step cross-ref preserved (double-check accepted per
  CNS-023 iter-2 Q4). Mismatch → `workflow_failed` with
  `reason="cross_ref"` + no step_started.
- Budget gating: `Budget.is_exhausted()` between steps; exhaustion
  → `transition_to_failed(reason="budget_exhausted")`. Time +
  subprocess + HITL wait all accounted on the `time_seconds` axis.
- Integration tests: 30+ new tests across
  `test_multi_step_driver.py` (driver unit) and
  `test_multi_step_driver_integration.py` (e2e via codex-stub +
  real pytest/ruff subprocess). Fixtures: 3 workflow definitions
  (`multi_step_bugfix.v1.json` 7-step happy path,
  `retry_once_flow.v1.json`, `escalate_flow.v1.json`). Coverage:
  `multi_step_driver.py` ≥ 85%, `executor.py` delta ≥ 88%. Overall
  branch coverage gate ≥ 85% retained.
- Invariants (A3 + A4a preserved + A4b new):
  * Driver authoritative state via `(step_name, highest_attempt)`;
    run stays `running` while retry is available (invariant #20)
  * Resume derives position from completed step_records — no
    schema `current_step_index` field (invariant #21)
  * `adapter_returned.payload.attempt` explicit discriminator; SHA
    in `payload.output_sha256` (not `payload_hash`; that's event
    envelope scope) (invariant #22)
  * Workflow-level cross-ref once + Executor per-step preserved
    (invariant #24)
  * `ci_mypy` operation explicitly rejected by driver
    (`_StepFailed(reason="unsupported_operation")`); runner lands
    in FAZ-B or later.
  * `context_compile` operation is a stub in A4b (empty preamble
    StepResult); production context pipeline wiring in PR-A6 or
    FAZ-B.
  * No new evidence event kind (18-kind whitelist intact).
  * No new schema (A4a operation/attempt authoritative).
  * No new core dep.
- Adversarial consensus: CNS-20260416-024 iter-1 PARTIAL → iter-2
  AGREE (via fresh MCP thread; A4a thread
  `019d928f-978f-7ac2-91cb-b0f286798cbd` closed at A4a merge);
  post-impl review fired per memory rule
  `feedback_post_impl_review.md`.
```

---

## 12. Post-PR-A4b Outlook

**PR-A5** (evidence timeline CLI)
- `ao-kernel evidence timeline --run <run_id>` — JSONL → time-ordered table
- `ao-kernel evidence replay --run <run_id> --mode inspect|dry-run` — deterministic replay via `replay_safe` flag
- `ao-kernel evidence verify-manifest --run <run_id>` — SHA-256 manifest on demand + verification

**PR-A6** (demo + meta-extras + adapter fixtures)
- `.demo/` runnable script: issue → workflow → agent → diff → CI → approval → PR → evidence
- Production `adapter_manifests/` bundled: claude-code-cli, codex-cli, gh-cli-pr
- `pyproject.toml` `[coding]` meta-extra = `[llm, code-index, lsp, metrics]`
- `IntentRouter.llm_fallback` concrete impl
- `context_compile` operation production wiring (context pipeline integration)
- README integration + adapter walkthrough links
- v3.1.0 release tag

**FAZ-B kickoff** (post-FAZ-A ship)
- Multi-agent lease / fencing design note (CNS-016 recommendation, pre-FAZ-B)
- Metrics export `[metrics]` extra
- Policy simulation harness
- Price catalog + spend ledger
- Benchmark / regression suite

---

## 13. Audit Trail

| Field | Value |
|---|---|
| Plan version | **v2 (post-CNS-024 iter-1 absorption)** |
| Head SHA at draft | `9368e97` (main after PR-A4a merge) |
| Base branch | `main` |
| Target branch | `claude/tranche-a-pr-a4b` |
| Reference plans | `.claude/plans/PR-A0..A4-IMPLEMENTATION-PLAN.md` (all v2 final) |
| Strategy source | `.claude/plans/TRANCHE-STRATEGY-V2.md` v2.1.1 §10 FAZ-A release gates |
| A4a thread (closed) | `019d928f-978f-7ac2-91cb-b0f286798cbd` (CNS-023 iter-1 PARTIAL → iter-2 AGREE → iter-3 PARTIAL → iter-4 PARTIAL docs-only → merged) |
| CNS-024 thread | `019d92fd-acf3-71d0-bffe-2d4b51e3c531` (fresh thread — A4b review) |
| CNS-024 iter-1 | request `CNS-20260416-024.request.v1.json` (8 Q), response `...codex.response.v1.json` (PARTIAL, 5B + 7W) |
| CNS-024 iter-2 | §10 absorption map + 4 MV sorusu; MCP `codex-reply` same thread |
| Worktree | `.claude/worktrees/lucid-cerf` |
| Total test target | 1477+ (1447 A4a baseline + ≥ 30) |
| Coverage gate | 85% branch (retained) |
| Core dep | `jsonschema>=4.23.0` (unchanged) |
| PR size estimate | ~2100 LOC |
| Evidence event delta | 0 (18-kind whitelist intact) |
| Schema delta | 0 (A4a authoritative; `error.category` enum-legal + code/message discriminator) |
| iter-2 expected verdict | AGREE (CNS-022/023 pattern); residual warnings implementation-time |

**Status:** Plan v2 complete. Next: CNS-024 iter-2 via `mcp__codex__codex-reply` (same thread), expect AGREE → implement.
