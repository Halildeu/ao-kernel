# PR-A4 Implementation Plan v2 — Contract Repair + Patch/CI Primitives + Multi-Step Driver

**Tranche A PR 5/6 (split)** — plan v2 after CNS-023 iter-1 PARTIAL (8 blocker + 7 warning absorbed). Target CNS-023 iter-2 AGREE via MCP reply (same thread `019d928f-978f-7ac2-91cb-b0f286798cbd`).

## Revision History

| Version | Date | Scope |
|---|---|---|
| v1 | 2026-04-15 | Initial draft; CNS-023 iter-1 submission target. Single-PR scope ≈2880 LOC. |
| **v2** | **2026-04-15** | **CNS-023 iter-1 absorption: 8 blocker + 7 warning → split decision `split_2_pr` (A4a + A4b), contract repair (schema + state_machine + evidence taxonomy + bundled workflow + fixtures) landed in worktree pre-iter-2, multi_step_driver ownership netleştirildi (Executor.run_step per-step CAS sahipliği korunur), retry_once `step_record.attempt` append-only model, patch preflight `--check --3way --index` flag eşitlenmiş, CI toolchain `python3 -m <tool>` + policy-controlled PYTHONPATH default, output_ref PR-A4 required-for-durability.** |

---

## 1. Amaç

FAZ-A Tranche A'nın beşinci iş paketi. PR-A3'te ship edilen tek-adım executor primitive'ini (`Executor.run_step`) temel alıp **multi-step governed workflow driver** + **governed diff/patch engine** + **CI gate runner** katmanlarını ekler. `docs/DEMO-SCRIPT.md` 11-step end-to-end flow'unun 4-8 arası adımlarını executable kılar.

**v2 split kararı (CNS-023 iter-1 B3 + Q9 REJECT absorb):** tek PR yerine **iki sıralı PR**:

- **PR-A4a — Contract Repair + Patch/CI Primitives** (bu branch'de hazırlık yapılıyor). Driver'dan önce state/schema/evidence/Executor ownership sözleşmeleri düzeltilir; bağımsız `ao_kernel/patch/` + `ao_kernel/ci/` paketleri ve unit test'ler ship edilir.
- **PR-A4b — Multi-Step Driver + Integration** (A4a merge sonrası). A4a primitives'in üzerine `ao_kernel/executor/multi_step_driver.py` + Executor.run_step içi `output_ref` wiring + e2e integration tests + CHANGELOG + docs polish.

Codex'in 3-parça split önerisi (`split_other` — A4a contract + A4b primitives + A4c driver) reddedildi: contract repair patch/ci primitives ile aynı branch'de doğrulanmazsa interface drift üretir. İki parça split deterministik, review load dengeli.

### Kapsam özeti — A4a

| Katman | Modül / Dosya | Yaklaşık LOC |
|---|---|---|
| Contract repair — state machine | `ao_kernel/workflow/state_machine.py` TRANSITIONS +2 edge | ~10 satır delta |
| Contract repair — schema v1 additive | `ao_kernel/defaults/schemas/workflow-run.schema.v1.json` step_record.attempt | ~12 satır delta |
| Contract repair — schema v1 additive | `ao_kernel/defaults/schemas/workflow-definition.schema.v1.json` step_def.operation + 2 allOf | ~30 satır delta |
| Contract repair — evidence taxonomy | `ao_kernel/executor/evidence_emitter.py` _KINDS 17→18 | ~5 satır delta |
| Contract repair — docs sync | `docs/EVIDENCE-TIMELINE.md` §2.4 + §2 total + §3/§4 refs | ~8 satır delta |
| Contract repair — bundled workflow sync | `ao_kernel/defaults/workflows/bug_fix_flow.v1.json` 4 step + operation | ~4 satır delta |
| Contract repair — fixture sync | `tests/test_workflow_registry.py` `_minimal_definition` + `tests/test_workflow_state_machine.py` `_EXPECTED_TRANSITIONS` | ~20 satır delta |
| Registry parse — operation aware | `ao_kernel/workflow/registry.py` `StepDefinition.operation: str \| None` + parse + cross-ref guard | ~60 satır |
| Patch primitives | `ao_kernel/patch/` 4 modül (errors, diff_engine, apply, rollback, __init__) | ~750 |
| CI primitives | `ao_kernel/ci/` 3 modül (errors, runners, __init__) | ~400 |
| Unit tests | 4 test dosyası (test_patch_*, test_ci_runners) + 5 patch fixtures + 1 micro-repo fixture | ~700 |
| CHANGELOG | `[Unreleased]` → FAZ-A PR-A4a entry | ~50 |
| **A4a Toplam** | — | **~2050** |

### Kapsam özeti — A4b

| Katman | Modül / Dosya | Yaklaşık LOC |
|---|---|---|
| Multi-step driver | `ao_kernel/executor/multi_step_driver.py` | ~600 |
| Executor.run_step output_ref wiring | `ao_kernel/executor/executor.py` B4 fix (adapter output envelope + patch content persist to `{run_dir}/artifacts/`) | ~80 satır delta |
| Executor facade update | `ao_kernel/executor/__init__.py` MultiStepDriver re-export | ~15 satır delta |
| Integration tests | `test_multi_step_driver.py` + `test_multi_step_driver_integration.py` + 3 workflow fixtures | ~1100 |
| CHANGELOG | `[Unreleased]` → FAZ-A PR-A4b entry | ~60 |
| **A4b Toplam** | — | **~1855** |

**Kümülatif A4a + A4b:** ~3900 LOC, ≥100 test (A4a ~70 + A4b ~30), 11 src modül delta + 2 yeni paket. Core dep değişmez (`jsonschema>=4.23.0` tek zorunlu).

- Yeni schema: **0** (mevcut `workflow-run.schema.v1` + `workflow-definition.schema.v1` yeterli; `step.kind` ve `on_failure` enum zaten tanımlı).
- Yeni policy: **0 yeni file**, ancak `policy_worktree_profile.v1` bundled default içindeki `command_allowlist.exact` listesine `pytest` + `ruff` basename eklenebilir (CNS-023 Q5'e bağlı).
- Yeni core dep: **0** (stdlib `subprocess` + `urllib` + `pathlib` + `secrets` + `hashlib`; `jsonschema>=4.23.0` tek zorunlu dep kalır).
- Tahmini yeni test: **≥ 90** (PR-A3 son ciddesinden %30 artış; target 1418+).
- Tahmini ship sonu toplam test: **1418+** (1328 + ≥90).

### Tranche A pozisyonu (v2 split)

- [x] PR-A0 (#87) — docs + schemas + policy bundled default
- [x] PR-A1 (#88) — workflow state machine + run store
- [x] PR-A2 (#89) — intent router + workflow registry + adapter manifest loader
- [x] PR-A3 (#90) — worktree executor + policy enforcement + adapter invocation
- [ ] **PR-A4a** (next) — contract repair + patch/ci primitives + unit tests
- [ ] **PR-A4b** (after A4a merge) — multi_step_driver + integration + output_ref wiring
- [ ] PR-A5 — evidence timeline CLI + SHA-256 manifest generation on demand
- [ ] PR-A6 — demo runnable + adapter fixtures + `[coding]` meta-extra + `[llm]` fallback

PR-A4b sonrası end-to-end governed flow lokal olarak koşulabilir; PR-A5/A6 sadece operatör ergonomisi, dokümantasyon ve release-paketleme katmanları kalır.

---

## 2. Scope Fences

### Scope İçi A4a (contract repair + primitives + unit tests)

- **Contract repair (schema + state + evidence + bundled + fixtures):**
  - `ao_kernel/workflow/state_machine.py` TRANSITIONS +2 edge: `waiting_approval → running` (governance-approved non-patch resume), `verifying → waiting_approval` (post-CI governance gate). `running → running` **eklenmez** (CNS-023 B5 — retry append-only).
  - `ao_kernel/defaults/schemas/workflow-run.schema.v1.json` `step_record.attempt` integer field (opt, default 1, append-only retry model); `output_ref` desc PR-A4 required-for-durability.
  - `ao_kernel/defaults/schemas/workflow-definition.schema.v1.json` `step_def.operation` enum + 2 yeni allOf conditional (ao-kernel/system → required, adapter/human → not allowed).
  - `ao_kernel/executor/evidence_emitter.py` `_KINDS` 17 → 18 (`diff_rolled_back` eklendi).
  - `docs/EVIDENCE-TIMELINE.md` §2.4 Diff (2)→(3), total 18, §3 + §4 atıfları.
  - `ao_kernel/defaults/workflows/bug_fix_flow.v1.json` 4 ao-kernel/system step'ine operation eklendi.
  - `tests/test_workflow_state_machine.py` `_EXPECTED_TRANSITIONS` literal tablo güncellendi; `tests/test_workflow_registry.py` `_minimal_definition` fixture operation eklendi.
- **Registry parse update:**
  - `ao_kernel/workflow/registry.py` `StepDefinition` dataclass `operation: str | None = None` field'ı; parser `raw_step["operation"]` okur; `validate_cross_refs` operation eksikliği için `CrossRefIssue(kind="operation_required")` üretir.
- **Patch primitives:** `ao_kernel/patch/` paketi: `preview_diff` (`git apply --check --3way --index -`) + `apply_patch` (`git apply --3way --index -` + deterministic reverse-diff atomic write) + `rollback_patch` (idempotent via worktree-clean check) + typed errors. Plan v1'deki plain `--check`'ten `--check --3way --index` flag eşitlenmesi CNS-023 B6 absorb.
- **CI primitives:** `ao_kernel/ci/` paketi: `run_pytest` (`python3 -m pytest`) + `run_ruff` (`python3 -m ruff check`) + `run_all` subprocess orkestrasyonu; hermetic env via PR-A3 `SandboxedEnvironment`; policy-controlled `PYTHONPATH` explicit_additions (`worktree_root`, `worktree_root/src` varsa); fail-closed timeout semantics (`CIResult.status='timeout'` döner, exception raise etmez — CNS-023 W7 absorb).
- **Unit tests:** ≥70 test across 4 dosya (test_patch_diff_engine, test_patch_apply, test_patch_rollback, test_ci_runners). Fixtures: 5 patch + 1 micro-repo.
- **Policy gate**: patch + CI için `policy_enforcer.validate_command(command, resolved_args, sandbox, secret_values)` doğru imzayla çağrılır (CNS-023 B8 absorb).
- **CHANGELOG:** `[Unreleased]` → Added — FAZ-A PR-A4a entry.

### Scope İçi A4b (multi-step driver + integration)

- `MultiStepDriver.run_workflow(run_id, definition, ...)` — `definition.steps` üzerinde iterate + step-actor dispatch (adapter → `Executor.run_step`; ao-kernel operation=patch_* → patch primitives; system operation=ci_* → ci primitives; human → waiting_approval gate) + `on_failure` (3 variant: `transition_to_failed` / `retry_once` / `escalate_to_human`) dispatch + budget gating.
- `MultiStepDriver.resume_workflow(run_id, resume_token, payload=None)` — `interrupted` (HITL) veya `waiting_approval` (governance) state'ten kalındığı yerden devam. Resume konumu `definition.steps` sırası + `run_record.steps[]` içindeki terminal (highest attempt) `completed` step_record'lardan türetilir — yeni `current_step_index` field **eklenmez** (CNS-023 B1 absorb). Token eşleşmesi + idempotent payload hash PR-A1 primitives'ten.
- **Executor.run_step output_ref wiring (B4 absorb):** adapter output envelope + patch content + CI result JSON `{run_dir}/artifacts/{step_id}-{attempt}.json` dosyasına atomic write; `step_record.output_ref` = relative path; `adapter_returned` event payload `output_ref` + `payload_hash` taşır. Crash-resume bu path'ten oku.
- **Retry append-only model (B5 absorb):** step failure + `on_failure=retry_once` → yeni step_record (aynı step_name, fresh step_id, attempt=2) `append_step_record(run_id, ...)` ile persist + CAS revision bump. 2. invocation `Executor.run_step(step_def, run_record, attempt=2)` çağrısıyla yapılır. Evidence `step_started` payload `{"attempt": 2}` discriminator. Crash-safety: attempt=2 step_record yoksa + attempt=1 failed + on_failure=retry_once → driver "retry consumed değil, attempt=2'yi başlat" kuralı (B2 absorb).
- **Escalate to human (conflict için değil):** `on_failure=escalate_to_human` adapter step'leri için açık; patch_apply step'lerinde `escalate_to_human` kullanılmaz (partial index/worktree state governance beklemesine taşınmamalı; B3 absorb). Registry validate step'te `actor=ao-kernel AND operation=patch_apply AND on_failure=escalate_to_human` kombinasyonunu `CrossRefIssue` ile reject eder.
- **HITL resume path:** `running → waiting_approval` (gate) → `approval_granted` → `running` (eğer gate=pre_apply haricinde) VEYA `applying` (gate=pre_apply). Post-CI governance gate: `verifying → waiting_approval → completed | cancelled | failed`.
- **Evidence event emission** (A4b dahilinde emit edilenler): `workflow_started`, `workflow_completed`, `workflow_failed` (mevcut 17-kind), ek olarak A4a'da eklenen `diff_rolled_back`. `workflow_interrupted` ve `workflow_waiting_approval` **YOK** — bunlar `step_failed` + `approval_requested` / `interrupt_request` ile zaten kapsanıyor (CNS-023 B2 absorb).
- **Integration tests:** ≥30 test across 2 dosya (test_multi_step_driver, test_multi_step_driver_integration). Fixtures: 3 workflow + bundled micro-repo reuse.
- **CHANGELOG:** `[Unreleased]` → Added — FAZ-A PR-A4b entry.

### Scope Dışı

| Alan | Nereye ertelendi | Neden |
|---|---|---|
| `ao-kernel evidence timeline` CLI | PR-A5 | Operatör ergonomisi; PR-A4 evidence yazma tarafını kapatır, okuma tarafı ayrı PR |
| SHA-256 integrity manifest generation on demand | PR-A5 | Manifest CLI-triggered, PR-A4 sırasında append-only JSONL yeterli (PR-A3 invariant §6) |
| Demo script runnable `.demo/` dizini | PR-A6 | FAZ-A release gate sonlayıcı PR |
| `[coding]` meta-extra aktivasyonu | PR-A6 | `pyproject.toml` extras editing + `[llm]` fallback bundle |
| Bundled adapter manifest fixtures (claude-code-cli, gh-cli-pr, codex-cli) | PR-A6 | `tests/fixtures/adapter_manifests/` zaten negative fixture var; production fixture ayrı PR |
| `[llm]` fallback intent classifier implementation | PR-A6 | PR-A2'de `NotImplementedError` stub, PR-A6'da tenacity tabanlı impl |
| OS-level network sandbox (cgroups / firejail / nsjail) | FAZ-B | Multi-OS surface; PR-A0 `docs/WORKTREE-PROFILE.md §4` deferred |
| Merge conflict AI resolution | FAZ-C #28 write-lite | Agentic editing (FAZ-C C1) ile birlikte |
| Flaky test retry heuristic | Out-of-scope (permanent) | Fail-closed contract; any non-zero exit → step failed |
| Multi-axis budget decomposition (per-step quota) | FAZ-B #7 full | PR-A4'te cumulative single-axis budget yeterli |
| Patch 3-way conflict human-resolve workflow | Scope sınırında — CNS-023 Q3 | `escalate_to_human` mı `failed` mi kararı Codex'ten |
| Agentic multi-file coherent edits (Aider patterns) | FAZ-C #11/#12 adopt+wrap | Diff primitive'i bu PR'da biter, LLM-driven flow FAZ-C |
| PR creation via `gh` CLI | **FAZ-A PR-A6** (adapter manifest fixture) | gh-cli-pr adapter manifest PR-A6'da bundled; PR-A4'te abstract adapter kalır |

### Bozulmaz İlkeler (PR-A4'te korunur)

**PR-A3'ten devralınan (regresyon yok)**

1. **POSIX-only** — `ao_kernel/_internal/shared/lock.py::file_lock` ve `ao_kernel/executor/worktree_builder.py`'deki git worktree davranışı PR-A4'te de aynen geçerli.
2. **`inherit_from_parent=False` strict default** — PR-A4 CI subprocess'leri (pytest, ruff) policy-gated `SandboxedEnvironment` üzerinden çağrılır; host env passthrough yok.
3. **PATH anchoring realpath + policy prefix** — `policy_enforcer.validate_command` `shutil.which(cmd).realpath` değerini policy'nin `command_allowlist.prefixes` listesinden birinin altında olmaya zorlar; basename allowlist alone yeterli DEĞİL.
4. **Per-run `events.jsonl.lock` + monotonic `seq`** — tüm PR-A4 evidence emission'ları PR-A3 `EvidenceEmitter.emit_event` üzerinden; `seq` monotonic invariant.
5. **Cross-ref per-call** — PR-A3 invariant korunur: `Executor.run_step` her adapter adımında `validate_cross_refs` çağırır (no cache; adapter registry mutable). A4b `MultiStepDriver` ADDITIONALLY workflow başında bir kez `validate_cross_refs` çağırır (erken fail + better UX). Double-check kabul edildi (CNS-023 Q4 ACCEPT).
6. **Canonical event order (PR-A3 + PR-A4 genişletilmiş, actor/operation-aware)**:
   ```
   workflow_started
     → validate_cross_refs (workflow-level, once)
     → for step in definition.steps:
         step_started (payload: attempt) → policy_checked → (policy_denied ⇒ abort)
           → actor=adapter:  adapter_invoked → adapter_returned (payload: output_ref)
           → actor=ao-kernel, operation=patch_preview: diff_previewed
           → actor=ao-kernel, operation=patch_apply:   diff_previewed → diff_applied
           → actor=ao-kernel, operation=patch_rollback:diff_rolled_back (non-idempotent-skip only)
           → actor=system, operation=ci_*:             test_executed (per check)
           → actor=human:                              approval_requested → [wait] → approval_granted|approval_denied
           → step_completed | step_failed (payload: attempt)
         → run state CAS (revision bump + terminal step_record append for attempt)
     → workflow_completed | workflow_failed
   ```
   (`workflow_interrupted` / `workflow_waiting_approval` kinds **YOK** — hub events `step_failed + interrupt_request` ve `approval_requested` ile kapsanıyor. CNS-023 B2 absorb.)
7. **JSONPath minimal subset** — `adapter_invoker`'da `$.key(.key)*`; PR-A4'te patch content extraction için JSONPath kullanılırsa aynı subset.
8. **text/plain fallback triple gate** — PR-A3'te zaten adapter_invoker'da; PR-A4'te adapter çıktısı patch_content olarak yorumlanırken aynı gate.

**PR-A4 yeni bozulmaz ilkeler**

9. **Patch pre-flight flag eşitlemesi (CNS-023 B6 absorb)** — `preview_diff` ve `apply_patch` İKİSİ de `git apply --check --3way --index -` ile validate eder (plain `--check` değil; --3way olmadan --check 3-way-resolvable durumları yanlış reject eder). Preview → check pass → apply; check fail → `PatchPreviewError` (apply'a girilmez).
10. **Reverse diff deterministic path** — her başarılı `apply_patch` çağrısı `{run_dir}/patches/{patch_id}.revdiff` dosyasına **atomic write** (tempfile + fsync + rename); `rollback_patch` BU dosyadan okur. Ayrı patch_id → ayrı revdiff; overwrite yok.
11. **Rollback idempotent** — aynı `reverse_diff_id` ile ikinci `rollback_patch` çağrısı `git diff --cached --quiet && git diff --quiet` (index + worktree temiz) ise `RollbackResult(idempotent_skip=True)` döner (no-op, no error, **no new `diff_rolled_back` event**).
12. **CI flaky tolerance = 0** — `run_pytest`/`run_ruff` non-zero exit → `CIResult(status="fail")`; driver fail-closed; retry heuristic kesinlikle yok (retry sadece `on_failure=retry_once` ile workflow step seviyesinde, CI subprocess içinde değil).
13. **Retry append-only model (CNS-023 B5 absorb)** — step failure + `on_failure=retry_once`: önce **CAS içinde** `step_record(attempt=2)` olarak YENİ kayıt append edilir (schema-uyumlu, `steps` array, aynı step_name, fresh step_id); CAS revision bump + state unchanged (`running` kalır, terminal olmadığı için). İkinci invocation `Executor.run_step(..., attempt=2)` çağrısıyla DIŞARIDAN yapılır (dış subprocess CAS içinde atomik olamaz). İkinci fail → hard fail (`transition_to_failed`). Crash-safety: attempt=2 step_record yoksa + attempt=1 failed + `on_failure=retry_once` → driver resume kuralı "retry consumed değil, attempt=2'yi başlat" (CNS-023 B2 fix; yoksa retry sessizce tüketilmiş sayılır).
14. **Multi-step state CAS günlük** — her step bitiminde `run_store.update_run(run_id, mutator, expected_revision=current)` çağrılır; CAS conflict `WorkflowCASConflictError` ise driver tarafından 1 kez retry edilir (re-read + re-mutate); ikinci conflict → `DriverStateConflictError`.
15. **HITL resume idempotent payload** — `resume_workflow(run_id, resume_token, payload)` aynı payload ile 2. çağrı → state mutation yok (PR-A1 `resume_interrupt` idempotency); farklı payload → `WorkflowTokenInvalidError`.
16. **`escalate_to_human` state transition** — adapter step failure + `on_failure=escalate_to_human`: `mint_approval_token(run_id, step_name)` → state `running → waiting_approval` (PR-A1 allowed) → `approval_requested` event (PR-A0 evidence taxonomy) → driver return `DriverResult(interrupted=True, resume_token=...)`. Resume ile `waiting_approval → running` (approval_granted) veya `waiting_approval → cancelled` (approval_denied). **`patch_apply` step'leri için `escalate_to_human` yasaktır (CNS-023 B3 absorb):** registry `validate_cross_refs` `actor=ao-kernel AND operation=patch_apply AND on_failure=escalate_to_human` kombinasyonunu `CrossRefIssue(kind="invalid_on_failure_for_operation")` ile reject eder. Partial index/worktree state governance beklemesine taşınmamalı; patch conflict → `failed` + dirty-state cleanup zorunlu.
17. **`output_ref` durable persistence (CNS-023 B4 absorb)** — adapter output envelope + patch content + CI result JSON `{run_dir}/artifacts/{step_id}-attempt{n}.json` dosyasına **atomic write** (tempfile + fsync + rename). `step_record.output_ref` = `artifacts/{step_id}-attempt{n}.json` (relative); `adapter_returned` event payload `output_ref` + `payload_hash` taşır. Crash-resume bu path'ten okur. A4a: patch + CI primitives kendi artifact'larını yazar (apply_patch → `patch_apply-attempt{n}.json` + reverse-diff ayrı path). A4b: Executor.run_step adapter output envelope'ını aynı mekanizmayla yazar.
18. **Patch conflict dirty-state cleanup (CNS-023 B6 absorb)** — `apply_patch` non-zero exit (conflict veya fail) sonrası: (a) `.rej` file paths ve `git status --porcelain` dirty paths yakalanır; (b) `step_record.error.dirty_state_paths` alanına kaydedilir (evidence); (c) `git reset --hard HEAD` + `.rej` cleanup (forensic kopyası `{run_dir}/artifacts/rejected/{step_id}.tgz` olarak alınır); (d) `PatchApplyConflictError` raise (A4a conflict durumunda `failed` transition; A4b driver `on_failure` dispatch).

---

## 3. Write Order (2-PR DAG)

### PR-A4a Write Order

```
Layer 0 — Contract repair (worktree'de hazır, commit bekliyor)
  [done] ao_kernel/workflow/state_machine.py TRANSITIONS +2 edge
  [done] ao_kernel/defaults/schemas/workflow-run.schema.v1.json step_record.attempt
  [done] ao_kernel/defaults/schemas/workflow-definition.schema.v1.json step_def.operation + 2 allOf
  [done] ao_kernel/executor/evidence_emitter.py _KINDS += diff_rolled_back
  [done] docs/EVIDENCE-TIMELINE.md §2.4 + §2 total + §3/§4 refs
  [done] ao_kernel/defaults/workflows/bug_fix_flow.v1.json 4 step + operation
  [done] tests/test_workflow_state_machine.py _EXPECTED_TRANSITIONS
  [done] tests/test_workflow_registry.py _minimal_definition

Layer 1 — Registry parse update
  1. ao_kernel/workflow/registry.py
     - StepDefinition: operation: str | None = None field
     - parser: raw_step.get("operation")
     - validate_cross_refs: CrossRefIssue(kind="operation_required") when actor in {ao-kernel, system} and operation missing
     - validate_cross_refs: CrossRefIssue(kind="invalid_on_failure_for_operation") when actor=ao-kernel AND operation=patch_apply AND on_failure=escalate_to_human
     - pattern-drift regression test guard (workflow-definition operation enum ↔ registry parser)

Layer 2 — patch/ errors (independent)
  2. ao_kernel/patch/errors.py

Layer 3 — patch/ primitives (independent, stdlib only)
  3. ao_kernel/patch/diff_engine.py    (preview_diff + DiffPreview)
  4. ao_kernel/patch/apply.py          (apply_patch + ApplyResult + dirty-state cleanup)
  5. ao_kernel/patch/rollback.py       (rollback_patch + RollbackResult + idempotent_skip)
  6. ao_kernel/patch/__init__.py

Layer 4 — ci/ errors + primitives
  7. ao_kernel/ci/errors.py
  8. ao_kernel/ci/runners.py           (run_pytest, run_ruff, run_all + CIResult status='timeout' return)
  9. ao_kernel/ci/__init__.py

Layer 5 — unit tests
 10. tests/test_patch_diff_engine.py             (~14 test)
 11. tests/test_patch_apply.py                    (~17 test, dirty-state cleanup dahil)
 12. tests/test_patch_rollback.py                 (~11 test)
 13. tests/test_ci_runners.py                     (~17 test, timeout return behavior dahil)
 14. tests/test_workflow_registry_operation.py    (~10 test, operation parsing + cross-ref issues)
 15. tests/fixtures/patches/{simple_add,multi_file,conflict,binary,malformed}.patch
 16. tests/fixtures/micro_repo/ (1 Python module + pyproject.toml)

Layer 6 — CHANGELOG
 17. CHANGELOG.md [Unreleased] → Added — FAZ-A PR-A4a
```

### PR-A4b Write Order (A4a merge sonrası)

```
Layer 7 — Executor output_ref wiring
 18. ao_kernel/executor/executor.py
     - adapter_returned event payload + output_ref write to {run_dir}/artifacts/{step_id}-attempt{n}.json
     - _write_artifact helper (atomic write, tempfile + fsync + rename, SHA-256 payload_hash)
     - step_record.output_ref populate at CAS mutation
 19. ao_kernel/executor/evidence_emitter.py (helper export maybe not needed)

Layer 8 — driver
 20. ao_kernel/executor/multi_step_driver.py
     - MultiStepDriver + run_workflow + resume_workflow
     - step actor/operation dispatch
     - retry append-only (attempt=2 step_record + crash-safety resume rule)
     - CAS retry logic + WorkflowCASConflictError handling
 21. ao_kernel/executor/__init__.py (re-export MultiStepDriver, DriverResult, errors)

Layer 9 — integration tests
 22. tests/test_multi_step_driver.py               (~20 test)
 23. tests/test_multi_step_driver_integration.py   (~13 test, e2e via codex_stub)
 24. tests/fixtures/workflows/{multi_step_bugfix,retry_once_flow,escalate_flow}.v1.json

Layer 10 — CHANGELOG + docs
 25. CHANGELOG.md [Unreleased] → Added — FAZ-A PR-A4b
 26. docs/EVIDENCE-TIMELINE.md §3 event_id ULID drift → opaque token_urlsafe (W4 absorb)
```

Bağımlılık sırası critical:
- A4a: **Layer 0 → Layer 1 → Layer 2-4 (paralel) → Layer 5 → Layer 6**
- A4b: **A4a merge gerek → Layer 7 → Layer 8 → Layer 9 → Layer 10**

Paralelleşebilen: A4a Layer 2-4 içinde patch/ ve ci/ birbirinden bağımsız.

---

## 4. Module — `ao_kernel/patch/errors.py`

### Public API

```python
class PatchError(Exception):
    """Base for patch package errors."""

class PatchPreviewError(PatchError):
    """`git apply --check` failed; patch cannot be applied."""
    patch_id: str
    files_rejected: tuple[str, ...]
    git_stderr_tail: str

class PatchApplyError(PatchError):
    """`git apply --3way --index` failed non-conflict (permissions, malformed)."""
    patch_id: str
    exit_code: int
    git_stderr_tail: str

class PatchApplyConflictError(PatchError):
    """`git apply --3way` partial; .rej files present."""
    patch_id: str
    conflict_paths: tuple[str, ...]
    rejected_hunks: tuple[str, ...]  # `.rej` dosyalarındaki hunk başlıkları

class PatchRollbackError(PatchError):
    """Reverse diff missing or apply failed."""
    patch_id: str
    reason: str  # "reverse_diff_missing" | "reverse_apply_failed" | "worktree_dirty"

class PatchBinaryUnsupportedError(PatchError):
    """Binary diff detected; policy disallows (PR-A4 scope)."""
    patch_id: str
    binary_paths: tuple[str, ...]
```

### Design decisions

- `PatchError` bağımsız base (ExecutorError'dan türetilmez — patch paketi executor paketinden bağımsız import edilebilsin).
- Keyword-only ctor (`def __init__(self, *, patch_id: str, ...)`) PR-A3 `PolicyViolation` pattern'ini takip eder.
- `git_stderr_tail` son 20 satır; evidence payload size guard (aynı PR-A3 `stderr_tail` 100 satır / 10 KB cap pattern).
- `PatchBinaryUnsupportedError` — PR-A4 `--binary` flag setlemez; binary diff dışarıda (CNS-023 Q7 opsiyonel).

---

## 5. Module — `ao_kernel/patch/diff_engine.py`

### Public API

```python
@dataclass(frozen=True)
class DiffPreview:
    patch_id: str              # secrets.token_urlsafe(32) — evidence'de stable referans
    files_changed: tuple[str, ...]
    lines_added: int
    lines_removed: int
    binary_paths: tuple[str, ...]  # binary diff algılanırsa (scope dışı ama raporlanır)
    conflicts_detected: bool
    git_check_stdout_tail: str
    git_check_stderr_tail: str
    duration_seconds: float

def preview_diff(
    worktree_root: Path,
    patch_content: str,
    policy_env: SandboxedEnvironment,
    *,
    timeout: float = 30.0,
) -> DiffPreview: ...
```

### Flow

1. `patch_id = secrets.token_urlsafe(32)` (URL-safe, 43 char).
2. `git apply --check --numstat --stat -` worktree CWD'de çağrılır; stdin = `patch_content`.
3. `--numstat` output'u parse: per-file `(added, removed, path)` (binary diff için `- - path` yazar — binary paths listesine eklenir).
4. `--check` exit code 0 → conflict yok; non-zero → `PatchPreviewError` raise (git stderr'den `error: patch failed:` satırı extract + `rejected_files` tuple).
5. Subprocess çağrısı `subprocess.run` + `policy_env.env_vars` (hermetic) + `cwd=worktree_root` + `input=patch_content.encode("utf-8")` + `timeout=timeout`.
6. Timeout → `TimeoutExpired` → `PatchPreviewError(reason="timeout")`.

### Design decisions

- **Read-only**: `--check` side-effect yok; preview atomically safe; evidence `diff_previewed` caller (driver) emit eder.
- **Unified diff only**: `git apply` unified diff formatı standardı destekler; diff3/context format dışarıda.
- **Binary reporting, not support**: binary diff algılanırsa `binary_paths` tuple'da raporlanır ama `apply_patch` çağrıldığında `PatchBinaryUnsupportedError` raise olur (scope out).
- **policy_env enforcement**: `git` resolved realpath policy prefix altında olmalı (PR-A3 `validate_command` önceden çağrılmış varsayılır — caller responsibility).

---

## 6. Module — `ao_kernel/patch/apply.py`

### Public API

```python
@dataclass(frozen=True)
class ApplyResult:
    patch_id: str
    applied: bool
    reverse_diff_id: str       # = patch_id; bir-bir eşleme
    reverse_diff_path: Path    # {run_dir}/patches/{patch_id}.revdiff
    files_changed: tuple[str, ...]
    lines_added: int
    lines_removed: int
    applied_sha: str           # post-apply `git rev-parse HEAD` (detached head olabilir)
    duration_seconds: float

def apply_patch(
    worktree_root: Path,
    patch_content: str,
    policy_env: SandboxedEnvironment,
    run_dir: Path,
    *,
    patch_id: str | None = None,     # opsiyonel; verilmezse token_urlsafe(32)
    strategy: Literal["3way"] = "3way",
    timeout: float = 60.0,
) -> ApplyResult: ...
```

### Flow

1. `patch_id = patch_id or secrets.token_urlsafe(32)`.
2. **Pre-flight check** (bozulmaz ilke #9): `git apply --check -` çağrılır; fail → `PatchPreviewError` (apply'a hiç geçilmez).
3. **Apply**: `git apply --3way --index -` + stdin=patch_content + cwd=worktree_root.
4. Exit code:
   - `0` → başarılı; step 5'e devam.
   - `1` ve `.rej` file'ları varsa → `PatchApplyConflictError` + `conflict_paths` (glob `**/*.rej` worktree'de).
   - non-zero without `.rej` → `PatchApplyError`.
5. **Reverse diff üret**: `git diff --cached -R` (staged diff'in tersi) → `reverse_diff_content` string.
6. **Atomic write**: `{run_dir}/patches/` yoksa `mkdir(parents=True, exist_ok=True, mode=0o700)` (PR-A3 `worktree_builder` chmod pattern).
7. Atomic write reverse diff: `write_text_atomic({run_dir}/patches/{patch_id}.revdiff, reverse_diff_content)` (tempfile + fsync + rename; PR-A3 `_internal/shared/atomic.py` patern).
8. `applied_sha = git rev-parse HEAD` capture (orijinal branch'in commit'i; staged ama henüz commit değil → `HEAD` same).
9. `ApplyResult` dön.

### Design decisions

- **patch_id caller-overridable**: driver önceden `preview_diff` ile patch_id üretip daha sonra `apply_patch(..., patch_id=same)` çağırabilsin — evidence'de preview + apply aynı patch_id ile linked.
- **Staged (--index)**: apply hem working tree'ye hem index'e gider; `applied_sha` zaten stable; commit PR-A6 workflow adımında.
- **Reverse diff deterministic path**: `{run_dir}/patches/{patch_id}.revdiff` (bozulmaz ilke #10). Run-dir zaten per-run (`.ao/runs/{run_id}/`).
- **No atomic rename of patch dir**: sadece revdiff file atomic; dizin idempotent mkdir.
- **Conflict reporting**: `.rej` file glob per worktree (hızlı — max few dozen files).

---

## 7. Module — `ao_kernel/patch/rollback.py`

### Public API

```python
@dataclass(frozen=True)
class RollbackResult:
    patch_id: str
    rolled_back: bool
    idempotent_skip: bool      # True → zaten rollback'lendi, no-op
    files_reverted: tuple[str, ...]
    duration_seconds: float

def rollback_patch(
    worktree_root: Path,
    reverse_diff_id: str,       # = patch_id
    policy_env: SandboxedEnvironment,
    run_dir: Path,
    *,
    timeout: float = 60.0,
) -> RollbackResult: ...
```

### Flow

1. `revdiff_path = run_dir / "patches" / f"{reverse_diff_id}.revdiff"`.
2. `revdiff_path.exists()` değilse → `PatchRollbackError(reason="reverse_diff_missing")`.
3. `revdiff_content = revdiff_path.read_text()`.
4. **Idempotency check**: `git diff --cached --quiet` exit code 0 ve `git diff --quiet` exit code 0 (worktree temiz) ise → `RollbackResult(rolled_back=False, idempotent_skip=True)` return (bozulmaz ilke #11).
5. Aksi halde: `git apply --3way --index -` stdin=revdiff_content.
6. Exit code 0 → başarılı; non-zero → `PatchRollbackError(reason="reverse_apply_failed")`.
7. `files_reverted = git diff --cached --name-only` son list.

### Design decisions

- **Idempotency heuristic**: çift `git diff --quiet` (index + worktree) kontrolü `idempotent_skip` tespiti. Conservative — worktree dirty ise skip değil, `PatchRollbackError(reason="worktree_dirty")`.
- **3way uygular**: reverse diff zaten apply sırasında üretilmiş deterministic patch; 3way güvenli.
- **No cascade rollback**: rollback bir patch'i geri alır; diğer patch'lerle bağımsız. Driver çok-patch rollback istiyorsa ardışık `rollback_patch` çağırır (LIFO sırası caller'da).

---

## 8. Module — `ao_kernel/patch/__init__.py`

```python
from .diff_engine import DiffPreview, preview_diff
from .apply import ApplyResult, apply_patch
from .rollback import RollbackResult, rollback_patch
from .errors import (
    PatchError,
    PatchPreviewError,
    PatchApplyError,
    PatchApplyConflictError,
    PatchRollbackError,
    PatchBinaryUnsupportedError,
)

__all__ = [
    "DiffPreview", "preview_diff",
    "ApplyResult", "apply_patch",
    "RollbackResult", "rollback_patch",
    "PatchError", "PatchPreviewError", "PatchApplyError",
    "PatchApplyConflictError", "PatchRollbackError",
    "PatchBinaryUnsupportedError",
]
```

Narrow facade — internal helper'lar (örn: `_extract_rej_files`, `_numstat_parse`) public export EDİLMEZ.

---

## 9. Module — `ao_kernel/ci/errors.py`

### Public API

```python
class CIError(Exception):
    """Base for CI package errors."""

class CITimeoutError(CIError):
    check_name: str            # "pytest" | "ruff" | "mypy" | ...
    timeout_seconds: float
    stdout_tail: str
    stderr_tail: str

class CIGateFailedError(CIError):
    """CI check non-zero exit; fail-closed."""
    check_name: str
    exit_code: int
    stdout_tail: str
    stderr_tail: str

class CIRunnerNotFoundError(CIError):
    """Resolved realpath not under policy command prefixes."""
    check_name: str
    attempted_command: str
    realpath: str
```

### Design decisions

- Keyword-only ctor, `*_tail` 100 satır / 10 KB cap (PR-A3 pattern).
- `CIGateFailedError` attribute'ları `CIResult` ile symmetric — caller `raise from result` yapabilsin.

---

## 10. Module — `ao_kernel/ci/runners.py`

### Public API

```python
@dataclass(frozen=True)
class CIResult:
    check_name: str                  # "pytest" | "ruff"
    command: tuple[str, ...]         # resolved command argv (evidence için)
    status: Literal["pass", "fail", "timeout"]
    exit_code: int
    duration_seconds: float
    stdout_tail: str                 # son 100 satır / 10 KB
    stderr_tail: str

def run_pytest(
    worktree_root: Path,
    policy_env: SandboxedEnvironment,
    *,
    extra_args: tuple[str, ...] = (),
    timeout: float = 300.0,
) -> CIResult: ...

def run_ruff(
    worktree_root: Path,
    policy_env: SandboxedEnvironment,
    *,
    extra_args: tuple[str, ...] = (),
    timeout: float = 60.0,
) -> CIResult: ...

def run_all(
    worktree_root: Path,
    policy_env: SandboxedEnvironment,
    checks: Sequence[Literal["pytest", "ruff"]],
    *,
    fail_fast: bool = False,
    timeouts: Mapping[str, float] | None = None,
) -> list[CIResult]: ...
```

### Flow (run_pytest örneği)

1. Command resolution: default `["python3", "-m", "pytest", *extra_args]` (CNS-023 Q5 sonuna göre `pytest` basename de değerlendirilir).
2. `policy_env.validate_command(command[0])` (PR-A3 `policy_enforcer.validate_command` basename + realpath + prefix).
3. Command not allowlisted → `CIRunnerNotFoundError`.
4. `subprocess.run(command, cwd=worktree_root, env=policy_env.env_vars, capture_output=True, text=True, timeout=timeout)`.
5. Exit 0 → `status="pass"`; non-zero → `status="fail"`.
6. `TimeoutExpired` → `status="timeout"` + `CITimeoutError` raise? — **CNS-023 Q6**: `status="timeout"` döner ama error raise ETMEZ (caller driver seviyesinde `transition_to_failed` yapar, fail-closed).
7. stdout/stderr tail extraction (100 satır cap, UTF-8 decode error → replace).

### Design decisions

- **Subprocess hermeticity**: `policy_env.env_vars` PR-A3'te `inherit_from_parent=False` default olduğu için sadece allowlist + explicit_additions. `PYTHONPATH` — **CNS-023 Q5 pending** — ya policy'ye eklenir ya `run_pytest` `extra_args` içinde `--rootdir=worktree_root` verir ya da test fixture'ı `pip install -e .` ön-koşuluyla çalışır.
- **fail-closed return, not raise**: `CIResult.status="fail"` döner (caller — driver — `CIGateFailedError` raise edebilir veya state transition yapabilir). `CITimeoutError`, `CIRunnerNotFoundError` ise sahiden exception (subprocess bile başlayamadı).
- **Ruff default command**: `ruff check .` veya `ruff check <worktree>` ya da `python3 -m ruff check .` — **CNS-023 Q5**.
- **No stderr concat with stdout**: stdout ve stderr ayrı yakalanır (pytest verbose'unu karıştırmamak için).

---

## 11. Module — `ao_kernel/ci/__init__.py`

```python
from .runners import CIResult, run_all, run_pytest, run_ruff
from .errors import CIError, CIGateFailedError, CIRunnerNotFoundError, CITimeoutError

__all__ = [
    "CIResult", "run_all", "run_pytest", "run_ruff",
    "CIError", "CIGateFailedError", "CIRunnerNotFoundError", "CITimeoutError",
]
```

---

## 12. Module — `ao_kernel/executor/multi_step_driver.py`

### Public API

```python
@dataclass(frozen=True)
class DriverResult:
    run_id: str
    final_state: Literal["running", "waiting_approval", "interrupted", "completed", "failed", "cancelled"]
    steps_executed: tuple[str, ...]     # step names
    steps_failed: tuple[str, ...]
    steps_retried: tuple[str, ...]      # retry_once triggered adımlar
    resume_token: str | None            # waiting_approval / interrupted state'te set
    resume_token_kind: Literal["approval", "interrupt"] | None
    budget_consumed: BudgetAxis | None
    duration_seconds: float

class MultiStepDriver:
    def __init__(
        self,
        workspace_root: Path,
        registry: WorkflowRegistry,
        adapter_registry: AdapterRegistry,
        executor: Executor,
        *,
        policy_config: dict,              # policy_worktree_profile.v1.json yüklenmiş
        evidence_sink: EvidenceEmitter,
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
        payload: Mapping[str, object] | None = None,
    ) -> DriverResult: ...
```

### Core loop (pseudocode)

```python
def run_workflow(self, run_id, workflow_id, workflow_version, *, budget=None, ...):
    definition = self.registry.get(workflow_id, workflow_version)
    run_record = self.run_store.load_run(run_id)  # created state beklenir
    assert run_record["state"] == "created"

    # Initial transition created → running
    run_record, rev = self.run_store._mutate_with_cas(
        workspace_root, run_id,
        mutator=lambda r: {**r, "state": "running", "started_at": now_iso()},
        expected_revision=run_record["revision"],
    )
    self.evidence.emit_event(kind="workflow_started", run_id=run_id, payload={
        "workflow_id": workflow_id, "workflow_version": workflow_version,
    })

    # Cross-ref validate (per-call, PR-A3 invariant korunur)
    cross_ref_issues = self.registry.validate_cross_refs(definition, self.adapter_registry)
    if cross_ref_issues:
        return self._transition_to_failed(run_id, rev, reason="cross_ref", issues=cross_ref_issues)

    # Main loop
    for step_def in definition.steps:
        # Idempotent resume: skip completed
        if step_def.name in run_record.get("completed_steps", []):
            continue

        # Budget gate
        if budget and budget.is_exhausted():
            return self._transition_to_failed(run_id, run_record["revision"],
                reason="budget_exhausted", failed_step=step_def.name)

        # Dispatch step by (actor, gate) combination
        # NOTE: workflow-definition.schema.v1 has step.actor {adapter, ao-kernel, human, system}
        # and step.gate {pre_diff, pre_apply, pre_pr, pre_merge, post_ci, custom}.
        # step.kind DOES NOT EXIST. Driver infers operation from (actor, gate, step_name convention).
        # Open CNS-023 Q8 — prefer actor-based dispatch + optional step.operation enum extension.
        try:
            if step_def.gate is not None:
                # Pre-step governance gate fires BEFORE step work
                approval = self._emit_approval_gate(step_def, run_record)
                if approval.status == "pending":
                    return approval  # waiting_approval return
            if step_def.actor == "adapter":
                step_result = self._run_adapter_step(step_def, run_record, budget, context_preamble)
            elif step_def.actor == "ao-kernel":
                # Internal orchestrator step — patch primitive resolution
                # (proposed: step_name convention OR new step.operation enum)
                step_result = self._run_patch_step(step_def, run_record)
            elif step_def.actor == "system":
                # Automated infra step — CI runner
                step_result = self._run_ci_step(step_def, run_record)
            elif step_def.actor == "human":
                # Pure HITL approval gate (no other work)
                return self._run_human_gate(step_def, run_record)
            else:
                raise WorkflowDefinitionCorruptedError(reason="unknown_actor", actor=step_def.actor)
        except _StepFailed as sf:
            return self._handle_step_failure(step_def, sf, run_record, budget)

        # Step succeeded — CAS update
        run_record = self._record_step_completion(run_id, step_def.name, step_result, run_record["revision"])

    # All steps done
    return self._transition_to_completed(run_id, run_record["revision"])


def _handle_step_failure(self, step_def, failure, run_record, budget):
    on_failure = step_def.on_failure or "transition_to_failed"  # default
    self.evidence.emit_event(kind="step_failed", run_id=run_record["run_id"], payload={
        "step_name": step_def.name, "reason": failure.reason, "attempt": failure.attempt,
    })
    if on_failure == "transition_to_failed":
        return self._transition_to_failed(run_record["run_id"], run_record["revision"],
            reason=failure.reason, failed_step=step_def.name)
    elif on_failure == "retry_once":
        if failure.attempt >= 2:
            return self._transition_to_failed(...)  # hard fail after 1 retry
        # CAS: retry_counter bump, state stays "running"
        run_record = self._bump_retry_counter(run_record["run_id"], step_def.name, run_record["revision"])
        # Recursive single retry
        try:
            step_result = self._run_adapter_step(step_def, run_record, budget, ..., attempt=2)
            run_record = self._record_step_completion(...)
            return self._continue_after_retry(run_record, step_def)  # loop'un devamı
        except _StepFailed:
            return self._transition_to_failed(...)
    elif on_failure == "escalate_to_human":
        token = mint_approval_token(run_record["run_id"], step_def.name)
        run_record = self._transition_to_waiting_approval(run_record, token)
        self.evidence.emit_event(kind="approval_requested", ...)
        return DriverResult(
            run_id=run_record["run_id"],
            final_state="waiting_approval",
            resume_token=token,
            resume_token_kind="approval",
            ...
        )
```

### Design decisions

- **Per-step CAS**: her step bitiminde `_mutate_with_cas(expected_revision=current)` çağrılır; conflict olursa (başka process aynı run'ı mutate etmiş) 1 kez re-read + re-mutate (bozulmaz ilke #14); ikinci conflict → `DriverStateConflictError` raise.
- **Idempotent resume**: `resume_workflow(run_id, token, payload)` aynı payload ile 2. çağrı → `resume_interrupt`/`resume_approval` primitives idempotent dönüş (PR-A1 invariant #15).
- **retry_once attempt counter**: `run_record["steps"][step_name]["retry_counter"]` persistent; driver crash + restart sonrası re-attempt doğru sayılır.
- **Actor-based dispatch** (schema check sonrası revize): `workflow-definition.schema.v1` `step.actor` ∈ `{adapter, ao-kernel, human, system}` + `step.gate` ∈ `{pre_diff, pre_apply, pre_pr, pre_merge, post_ci, custom}`. `step.kind` enum **YOK**. Driver dispatch:
  - `actor=adapter` → `Executor.run_step` (PR-A3 primitive)
  - `actor=ao-kernel` → patch primitive (step_name convention OR yeni `step.operation` alanı — CNS-023 Q8)
  - `actor=system` → CI runner (aynı karar noktası)
  - `actor=human` → waiting_approval
  - `gate != None` → step çalıştırılmadan önce approval gate açılır (waiting_approval return)
- **Cross-ref bir kez, workflow başında**: PR-A3 `Executor.run_step` her adapter adımında da cross-ref çağırıyor (PR-A3 invariant #5). Driver'da başta bir kez + Executor'da her adımda iki kez oluyor. **CNS-023 Q4**: bu double-check kabul mu yoksa driver tek çağrı + executor içi bypass mı (workflow-level zaten valid)?

---

## 13. Module — `ao_kernel/executor/__init__.py`

PR-A3'te shipped edilen public facade'a eklemeler:

```python
# Yeni eklenen:
from .multi_step_driver import (
    DriverResult,
    MultiStepDriver,
    DriverStateConflictError,
    DriverBudgetExhaustedError,
)

__all__ = [
    # ... mevcut PR-A3 exports ...
    "DriverResult", "MultiStepDriver",
    "DriverStateConflictError", "DriverBudgetExhaustedError",
]
```

---

## 14. Test Strategy

### Coverage targets

| Modül | Target branch cov | Min unit cov |
|---|---|---|
| `ao_kernel/patch/diff_engine.py` | 92% | 90% |
| `ao_kernel/patch/apply.py` | 90% | 88% |
| `ao_kernel/patch/rollback.py` | 92% | 90% |
| `ao_kernel/patch/errors.py` | 95% | 95% |
| `ao_kernel/ci/runners.py` | 87% | 85% |
| `ao_kernel/ci/errors.py` | 95% | 95% |
| `ao_kernel/executor/multi_step_driver.py` | 85% | 82% |
| **Overall (post-PR-A4)** | **≥ 85.5%** (gate 85) | — |

### Test file breakdown (target: ≥ 90 new tests)

| Dosya | Tahmini test | Odak |
|---|---|---|
| `tests/test_patch_diff_engine.py` | 14 | preview happy, preview fail (numstat parse), binary detect, timeout, policy command-not-allowed, unified-diff format variants |
| `tests/test_patch_apply.py` | 17 | apply happy, apply conflict (.rej files), apply non-conflict fail, patch_id propagation, reverse diff content, atomic revdiff write, chmod 0o700, pre-flight check blocks apply |
| `tests/test_patch_rollback.py` | 11 | rollback happy, rollback idempotent (no-op), reverse diff missing, worktree dirty, rollback timeout, revdiff path traversal guard |
| `tests/test_ci_runners.py` | 17 | run_pytest pass, run_pytest fail, run_pytest timeout, run_ruff pass/fail, command not allowlisted, subprocess env hermeticity (no host leak), stdout tail cap, stderr tail cap, run_all fail_fast, run_all fail_all, timeouts mapping |
| `tests/test_multi_step_driver.py` | 20 | created→running transition, per-step CAS, retry_once attempt counter, escalate_to_human token mint, transition_to_failed, budget exhaust mid-flow, cross-ref validate at start, idempotent skip (completed steps), resume_workflow approval granted, resume_workflow interrupt payload |
| `tests/test_multi_step_driver_integration.py` | 13 | e2e 3-step bug_fix flow via codex_stub, CI step real pytest subprocess, patch step real git, HITL resume across two process boundaries, state-machine drift regression guard |
| **Toplam** | **92** | |

### Fixtures

- `tests/fixtures/patches/simple_add.patch` — single-file add, 3 satır ekleme
- `tests/fixtures/patches/multi_file.patch` — 3 dosya modification
- `tests/fixtures/patches/conflict.patch` — mevcut HEAD ile çakışacak patch
- `tests/fixtures/patches/binary.patch` — binary diff (unsupported)
- `tests/fixtures/patches/malformed.patch` — `git apply --check` fail
- `tests/fixtures/workflows/multi_step_bugfix.v1.json` — 4-step flow: adapter_invocation → diff_apply → ci_gate → approval_gate
- `tests/fixtures/workflows/retry_once_flow.v1.json` — 2-step, step1 on_failure=retry_once
- `tests/fixtures/workflows/escalate_flow.v1.json` — 2-step, step2 on_failure=escalate_to_human

### CI subprocess test budget

Integration testler gerçek `subprocess.run` çağıracak (pytest, ruff, git). Bütçe:

- Per-test subprocess cap: 3 çağrı (pytest + ruff + git apply)
- Per-test timeout: 10 saniye (CI hermetic shortcut için micro-fixture repo)
- Total CI subprocess count (integration suite): ≤ 30
- Fixture repo: `tests/fixtures/micro_repo/` — 1 Python module + 1 test + pyproject.toml (minimal); `pip install -e .` yerine `sys.path` manipulation (CNS-023 Q5'e göre değişebilir)

### Test quality gate (AST-based)

PR-A3 `conftest.py` BLK-001/002/003 kuralları PR-A4'te de aktif kalır:
- `assert callable(x)` blocked
- `assert True` blocked; tek assertion `assert x is not None` advisory
- `except: pass` test içinde blocked

---

## 15. Acceptance Criteria

### Module + test

- [ ] 8 yeni src modül impl (patch/ 4 + ci/ 3 + multi_step_driver 1)
- [ ] 2 yeni paket (`ao_kernel/patch/`, `ao_kernel/ci/`) `setuptools-discover` edilir (`pyproject.toml` `packages.find` include)
- [ ] ≥ 90 yeni test pass
- [ ] `ruff check ao_kernel/ tests/` clean
- [ ] `mypy ao_kernel/ --ignore-missing-imports` 0 error
- [ ] Branch coverage `--cov-fail-under=85` gate geçer (target ≥ 85.5%)
- [ ] 1418+ total test collect (`pytest --co -q | tail -1`)

### End-to-end acceptance (DEMO-SCRIPT.md steps 4-8)

- [ ] `multi_step_bugfix.v1` workflow 4-step happy path: adapter_invocation → diff_apply → ci_gate → approval_gate → waiting_approval state
- [ ] Resume with approval_granted token → applying state (no actual commit in PR-A4 — commit ayrı adım PR-A6)
- [ ] Retry_once: adapter_invocation step 1. attempt fail, 2. attempt pass, retry_counter=1 run_record'da persistent
- [ ] Escalate_to_human: adapter_invocation on_failure=escalate_to_human → waiting_approval + resume_token + approval_requested event
- [ ] Transition_to_failed: patch_apply conflict → step_failed → transition_to_failed → workflow_failed event
- [ ] Rollback idempotent: apply_patch → rollback → rollback (2.) no-op
- [ ] CI fail-closed: run_pytest fail → ci_gate step_failed → workflow_failed (retry yok)
- [ ] CI timeout: pytest 300s exceed → CIResult.status=timeout → step_failed → workflow_failed

### Regression (PR-A3 invariant suite)

- [ ] PR-A3 test suite (`test_policy_enforcer.py`, `test_evidence_emitter.py`, `test_adapter_invoker.py`, `test_worktree_builder.py`, `test_executor.py`, `test_executor_integration.py`) tamamen pass (değişiklik yok)
- [ ] Cross-ref per-call davranış korunur (Executor.run_step içindeki cross-ref çağrısı silinmez; driver başlangıç çağrısı EK)
- [ ] PATH anchoring `realpath + prefix` korunur (patch/ ve ci/ içinde de enforcer kullanılır)
- [ ] `inherit_from_parent=False` CI subprocess'lerinde de aktif
- [ ] Per-run events.jsonl.lock + monotonic seq; patch + CI + workflow eventleri aynı JSONL'a ardışık seq ile yazılır
- [ ] 17-kind evidence taxonomy: PR-A4 yeni kind ekleMEZ (workflow_*, diff_*, test_*, approval_* zaten PR-A0 docs/EVIDENCE-TIMELINE.md §3'te tanımlı)

---

## 16. Risk & Mitigation

| Risk | Level | Mitigation |
|---|---|---|
| PR-A4 çap tek PR'a sığmaz (~2900 LOC + ≥90 test) | **Orta** | CNS-023 Q1'de Codex'e split önerisi sor: A4a (multi_step_driver + evidence flow) / A4b (patch + ci). Eğer Codex "single PR OK" derse devam; aksi halde split. |
| `git apply --3way` Apple Silicon farklı git sürümlerinde davranış drift | Düşük | `subprocess.run(["git", "--version"])` test setup'ta log + fixture repo git 2.30+ varsayımı CHANGELOG'da yazılı |
| pytest subprocess `PYTHONPATH` / `sys.path` leak | **Orta** | CNS-023 Q5 + fixture `micro_repo/` içinde `pip install -e .` **değil** `sys.path[0]=worktree_root` bootstrap; policy_env `PYTHONPATH=worktree_root` explicit_additions |
| ruff command allowlist'te yok (PR-A0 default) | Düşük | Seçenek 1: bundled policy `command_allowlist.exact` listesine `ruff` ekle. Seçenek 2: `python3 -m ruff check` invoke. **CNS-023 Q5 karar noktası.** Varsayılan: seçenek 2 (yeni policy ship etmeye gerek yok). |
| Reverse diff dosya sistem drift (run_dir silinirse) | Düşük | PR-A3 `worktree_builder.cleanup_worktree` zaten idempotent; run_dir silinirse rollback olanaksız ama `PatchRollbackError(reason="reverse_diff_missing")` deterministic |
| retry_once state machine `running → running` çakışma | Düşük | PR-A1 `state_machine.TRANSITIONS` tabelasında `running → running` allowed (adapters için zaten var). Test: literal transition-table assertion (PR-A1 pattern) |
| HITL + approval token conflation | Düşük | PR-A1 `mint_interrupt_token` vs `mint_approval_token` ayrı domain; `resume_workflow` `resume_token_kind` parametresiyle hangisine gitmesi gerektiğini belirler |
| `escalate_to_human` + approval denied UX eksik | Düşük | Scope: `waiting_approval → cancelled` transition PR-A1'de allowed; `resume_workflow(token, payload={"decision": "deny"})` → `workflow_cancelled` event |
| Binary diff rejection UX | Düşük | `PatchBinaryUnsupportedError` explicit; CHANGELOG'da scope out yazılı; FAZ-C #12 agentic editing ile tekrar bakılır |
| Step-level schema extension (step.kind enum) | **Orta** | **CNS-023 Q8**: mevcut `workflow-definition.schema.v1.json` `step.kind` yoksa schema v1.1 migration gerek mi? Schema patch minör bump yeterli (ek enum); breaking değil. |
| Multi-step workflow'da aynı step_name 2. `step_started` emit (retry) | Düşük | Bozulmaz ilke #6'da `seq` monotonic; payload'da `attempt: 2` discriminator. Test: `test_evidence_emitter.test_retry_attempt_discriminator` |
| Policy command-allowlist drift (workspace override ruff ekler, bundled yok) | Düşük | PR-A3 `policy_enforcer._load_merged_policy` workspace > bundled precedence zaten var; regression test PR-A3'te mevcut |

---

## 17. CNS-023 iter-2 Verification Prompt (micro-fix check)

**Hedef format** (CNS-022 iter-2 pattern): her iter-1 blocker + warning için `{id, fixed: bool, note}` micro verdicts; `new_blocking_objections: []` (ideally); `residual_warnings: [...]` (implementation-time fineprint); `ready_for_impl: true`; `pr_split_recommendation: split_2_pr`.

### Plan v2 absorption map (Codex'e teyit için)

| iter-1 ID | Plan v2 yeri | Çözüm |
|---|---|---|
| **B1** state machine + schema lifecycle | §2 ilke #13 + §3 Layer 0 | TRANSITIONS +2 edge (`waiting_approval→running`, `verifying→waiting_approval`); `running→running` EKLENMEDİ; `step_record.attempt` eklendi; `current_step_index/completed_steps` EKLENMEDİ (resume `definition.steps` sırası + terminal highest-attempt step_record'lardan türetilir) |
| **B2** Evidence taxonomy kapalı | §2 A4a + §3 Layer 0 | `_KINDS` 17→18, `diff_rolled_back` eklendi; `workflow_interrupted/waiting_approval` EKLENMEDİ (`step_failed + approval_requested + interrupt_request` ile kapsanır) |
| **B3** Executor/Driver ownership çakışması | §2 A4b + ilke #16 | Executor.run_step per-step CAS + cleanup sahipliği korunur; MultiStepDriver step sıralaması + on_failure dispatch; `patch_apply` için `escalate_to_human` registry reject (`validate_cross_refs` `CrossRefIssue(kind="invalid_on_failure_for_operation")`) |
| **B4** Adapter output + patch durable değil | §2 ilke #17 + §3 Layer 7 | `{run_dir}/artifacts/{step_id}-attempt{n}.json` atomic write; `step_record.output_ref` + `adapter_returned.payload.output_ref + payload_hash`; Executor.run_step A4b'de wiring |
| **B5** retry_once schema-uyumsuz | §2 ilke #13 + §3 Layer 0 | `step_record.attempt=2` append-only (`steps` array compatible); 2. invocation CAS dışında; crash-safety: attempt=2 yoksa + attempt=1 failed + `on_failure=retry_once` → retry consumed değil, attempt=2 başlatılır |
| **B6** Patch preflight + conflict atomicity | §2 ilke #9 + #18 + §3 Layer 3 | `--check --3way --index -` flag eşitlenmiş; dirty-state cleanup: `.rej` yakala + forensic `{run_dir}/artifacts/rejected/{step_id}.tgz` + `git reset --hard HEAD` |
| **B7** Internal step dispatch explicit operation olmadan fail-closed değil | §3 Layer 0 + Layer 1 | `step_def.operation` enum schema eklendi; allOf conditional (ao-kernel/system→required; adapter/human→not allowed); `StepDefinition.operation: str \| None` + parser + `validate_cross_refs` operation_required issue |
| **B8** CI hermetic toolchain resolution | §2 A4a + §3 Layer 4 | `python3 -m pytest` + `python3 -m ruff check` default; `PYTHONPATH` explicit_additions `worktree_root` + `worktree_root/src` (varsa); `validate_command(command, resolved_args, sandbox, secret_values)` doğru imza |
| W1 Bundled policy stale | §16 Risk | Mevcut policy zaten pytest/ruff içeriyor; risk: realpath prefix + venv uyumu |
| W2 run_store API | §12 impl note | `_mutate_with_cas` → public `update_run` (expected_revision alır) |
| W3 files_reverted yanlış hesaplanabilir | §7 rollback.py | Revdiff parse → files_reverted (canonical source) |
| W4 docs event_id ULID drift | §3 Layer 10 (A4b) | `docs/EVIDENCE-TIMELINE.md` §3 event_id description ULID→opaque token_urlsafe + seq ordering |
| W5 step_def.step_name drift | §12 pseudocode | v2'de `step_def.step_name` dataclass field kullanılıyor |
| W6 resume_approval payload modeli | §2 ilke #15 + A4b impl | A4b driver tarafında payload hash idempotency layer; farklı payload → `WorkflowTokenInvalidError` |
| W7 CIResult error sınıfları | §10 runners.py | `CIResult(status='fail'|'timeout')` döner; sadece preflight exception (`CIRunnerNotFoundError`); `CITimeoutError` → `raise_on_timeout=True` opt-in |

### 4 micro-verification sorusu (iter-2)

**MV1 — retry append-only crash-safety state semantiği.** Retry append-only model'in kuralı: attempt=1 step_record `state=failed` + `on_failure=retry_once` + attempt=2 step_record yoksa, driver resume sırasında attempt=2'yi başlatır. Bu senaryoda **run-level state** nedir? Driver resume terminal `failed → running` transition yapamaz (TRANSITIONS izin vermiyor). Doğru model: attempt=1 failed olduğunda run state `failed`'e taşınmaz; önce `running` kalır + attempt=2 denenir + ikinci fail → terminal `failed`. Bu doğru mu, yoksa alternatif var mı (örn step_record.state=failed ama run.state=running discriminator)?

**MV2 — patch_apply için escalate_to_human yasağı enforcement seviyesi.** Plan v2 §2 #16 yasağı `validate_cross_refs` seviyesinde enforce ediyor. Alternatif: schema-level conditional (`allOf if actor=ao-kernel AND operation=patch_apply then on_failure NOT escalate_to_human`). Schema-level daha erken reject (workflow JSON load). Tercih edilir mi, yoksa registry-level yeterli mi? JSON Schema 2020-12'de yazılabilir mi?

**MV3 — output_ref path + payload_hash + seq koordinasyonu.** Plan v2 §2 #17 `adapter_returned` event'inde `output_ref` + `payload_hash`. Retry senaryosunda aynı step için 2 `adapter_returned` emit edilir (attempt=1 ve attempt=2), farklı seq ama aynı step_name. Replay (PR-A5 CLI) `(step_name, attempt)` discriminator ile artifact eşler. Bu şema replay determinism için yeterli mi, yoksa `adapter_returned.payload.attempt` explicit alan zorunlu mu? (`step_started.payload.attempt` invariant #6'da; `adapter_returned`'da da aynı discriminator olmalı.)

**MV4 — PR split 2-parça (A4a + A4b) vs 3-parça (contract + primitives + driver).** Plan v2 split_2_pr öneriyor: A4a = contract repair + patch/ci primitives + unit tests (~2050 LOC), A4b = driver + integration (~1855 LOC). Codex iter-1 `split_other` önerdi (3 parça). Gerekçem 2-parça: contract repair patch/ci primitives ile aynı branch'de doğrulanırsa interface drift minimize (`StepDefinition.operation` parser'ı primitives tarafında kullanıldığını görür); 3-parça riski: A4a-contract merge olur, primitives olmayınca parser "dead code" kalır. Bu değerlendirme kabul mü, yoksa 3-parça hala önerilir mi?

---

### (v1 historical) CNS-023 iter-1 spec-level sorular

Plan v1'de Codex'e submit edilen 8+1 spec-level sorular:

1. **Multi-step loop resume semantiği**. Happy path'te tüm step'ler bir `run_workflow` çağrısında ardışık mı koşulur yoksa her step sonrası process çıkış / state persist + yeniden giriş mi? (Benim draft: happy path tek çağrıda ardışık; HITL/approval gate'te return; `resume_workflow` ile tek bir sonraki step'ten başla). Driver crash + restart sonrası `completed_steps` listesinden nerede kaldığımızı bulmak doğru mu yoksa açık `current_step_index` run_record field'i mi gerekli?

2. **retry_once state transition atomicity**. `running → running` transition + `retry_counter` bump + ikinci `run_step` invocation → hepsi tek CAS atomic mi yoksa iki ayrı CAS (revision bump önce, sonra retry invocation)? Retry invocation içinde başka crash olursa retry_counter=1 kalır — bu acceptable mi (bir sonraki resume no-op retry sayar)?

3. **Patch 3-way conflict UX**. `git apply --3way` partial apply + `.rej` dosyaları: driver `PatchApplyConflictError` yakalar, state `failed` mi `waiting_approval` (human conflict resolve) mu? Benim draft: `failed` (PR-A4 scope dışı `escalate_to_human`). Ama workflow definition `diff_apply` step.on_failure'ı schema level izin veriyorsa `escalate_to_human` path da açılabilir mi?

4. **Cross-ref double-check**. PR-A3 `Executor.run_step` içinde her adapter adımında cross-ref var (invariant #5). Driver başlangıçta da çağırıyor. Bu double-check acceptable mi yoksa driver başında çağırma bir kez ve executor içi bypass — eğer içeride Executor hala cross-ref istiyorsa optimization olarak cache'leyebilir mi (aynı `definition.revision` hash'ı ile)?

5. **CI subprocess hermeticity**. pytest `sys.path` worktree içindeki paketi nasıl bulacak? Seçenek a: `pip install -e .` fixture setup'ta (yavaş, her test için). Seçenek b: `PYTHONPATH=worktree_root` policy_env explicit_additions. Seçenek c: `python3 -m pytest --rootdir=worktree_root`. Hangisi? Ayrıca `ruff` için: `python3 -m ruff check .` mi `ruff check .` (basename allowlist'te yok) mı?

6. **CI timeout semantiği**. `subprocess.run(timeout=300)` → `TimeoutExpired` — `CIResult.status="timeout"` mı dönelim (caller fail-closed transition yapar) yoksa `CITimeoutError` raise edelim? Benim draft: status="timeout" (workflow step fail-closed transition yapar), `CITimeoutError` sadece caller `run_pytest` doğrudan çağırırsa atılır.

7. **Budget allocation**. Multi-step workflow'un `Budget` axes (tokens, time_seconds, cost_usd) tümü ortak pool mu yoksa per-step quota opsiyonu gerekli mi? Benim draft: ortak pool (PR-A1 `Budget` dataclass immutable + axis-level spend accumulation); per-step quota FAZ-B #7 full cost catalog'a ertelenir. Patch ve CI adımları için de `time_seconds` aynı axis'e spend yazılır mı yoksa ayrı axis ("subprocess_seconds") mı?

8. **Step dispatch modeli — actor + gate + opsiyonel `operation` alanı**. Mevcut `workflow-definition.schema.v1` `step.actor` ∈ `{adapter, ao-kernel, human, system}` + `step.gate` (pre/post approval anchors) içeriyor, ama ao-kernel veya system actor'lü bir step'in hangi internal primitive'i çağıracağı net değil. Üç seçenek:
   - **Seçenek A** (schema değişiklik yok) — step_name convention: `actor=ao-kernel AND step_name startswith "patch_"` → patch primitive; `actor=system AND step_name startswith "ci_"` → CI runner. Esnek ama fragile (ad kontratı schema'da değil).
   - **Seçenek B** (additive schema patch) — `step_def.properties.operation` opsiyonel enum `{patch_preview, patch_apply, patch_rollback, ci_pytest, ci_ruff}` eklenir. Backward compat: eski definition'larda yoksa `actor=ao-kernel` için hata; schema v1.1 minor bump.
   - **Seçenek C** (zaten var olan `required_capabilities` üzerinden) — adapter capabilities ile paralel, ao-kernel internal "capabilities" defne edilir: `required_capabilities: ["_patch_apply"]`; driver içinde hardcoded map. Schema değişmez ama capability_enum kirlenir.
   Hangi seçenek CNS-023 açısından fail-closed + explicit + backward-compatible?

9. **PR-A4 split önerisi**. ~2880 LOC + 92 test tek PR'a sığar mı? Split önerisi: **A4a** patch/ + ci/ paketleri + unit tests (~1380 LOC, bağımsız primitives) + **A4b** multi_step_driver + integration tests (~1500 LOC). A4a önce merge (dependency-free primitive'ler) + A4b sonra merge (primitives + PR-A3 kullanır). Alternatif: tümü A4 tek PR (PR-A3 `pr_split_recommendation=single_pr` pattern). Hangisi CI + review load açısından optimum?

---

## 18. CHANGELOG Update (split_2_pr)

İki ayrı PR için iki CHANGELOG entry. Her biri `[Unreleased]` altında, PR merge sırasında eklenir.

### PR-A4a entry

```markdown
### Added — FAZ-A PR-A4a (contract repair + diff/patch + CI gate primitives)

- **Contract repair (schema + state + evidence + bundled workflow):**
  `ao_kernel/workflow/state_machine.py` TRANSITIONS now allows
  `waiting_approval → running` (governance-approved non-patch resume)
  and `verifying → waiting_approval` (post-CI governance gate). Note:
  `running → running` is intentionally NOT added — retry_once uses
  append-only `step_record(attempt=2)` instead of a state edge.
  `workflow-run.schema.v1.json` adds `step_record.attempt` (int ≥ 1,
  default 1) for append-only retry semantics. `workflow-definition.
  schema.v1.json` adds `step_def.operation` enum (`context_compile`,
  `patch_preview`, `patch_apply`, `patch_rollback`, `ci_pytest`,
  `ci_ruff`, `ci_mypy`) with conditional `allOf` (required when
  actor ∈ {ao-kernel, system}; forbidden when actor ∈ {adapter, human}).
  `ao_kernel/executor/evidence_emitter.py` event kind whitelist
  expanded 17 → 18 with `diff_rolled_back`. Bundled
  `bug_fix_flow.v1.json` updated to declare `operation` on its four
  ao-kernel/system steps.
- `ao_kernel/workflow/registry.py` `StepDefinition` dataclass gains
  `operation: str | None = None` field; parser reads
  `raw_step["operation"]`; `validate_cross_refs` emits
  `CrossRefIssue(kind="operation_required")` when missing for
  ao-kernel/system actors, and
  `CrossRefIssue(kind="invalid_on_failure_for_operation")` when
  `actor=ao-kernel AND operation=patch_apply AND on_failure=
  escalate_to_human` (partial index/worktree state must not enter
  governance wait — CNS-023 B3 resolution).
- `ao_kernel/patch/` new public facade package. `preview_diff` wraps
  `git apply --check --3way --index -` (flag-aligned with `apply_patch`
  to avoid false-reject 3-way-resolvable hunks); `apply_patch` runs
  `git apply --3way --index -` with a deterministic reverse-diff
  stored at `{run_dir}/patches/{patch_id}.revdiff` via atomic write
  (tempfile + fsync + rename); `rollback_patch` replays the reverse
  diff and returns `RollbackResult(idempotent_skip=True)` when both
  index and worktree are clean (no `diff_rolled_back` event emitted
  on skip). Typed errors: `PatchPreviewError`, `PatchApplyError`,
  `PatchApplyConflictError` (reports `.rej` file paths +
  forensic tarball at `{run_dir}/artifacts/rejected/{step_id}.tgz`;
  `git reset --hard HEAD` cleanup protocol), `PatchRollbackError`,
  `PatchBinaryUnsupportedError`. Binary diff detected but not
  supported — scope deferred to FAZ-C agentic editing.
- `ao_kernel/ci/` new public facade package. `run_pytest` defaults to
  `python3 -m pytest`; `run_ruff` defaults to `python3 -m ruff check`;
  both invoke via `subprocess.run` inside a PR-A3
  `SandboxedEnvironment` (hermetic env, `inherit_from_parent=False`),
  with `PYTHONPATH` explicit_additions of `worktree_root` (and
  `worktree_root/src` if present). `run_all` orchestrates multiple
  checks with optional `fail_fast`. `CIResult.status` ∈
  `{pass, fail, timeout}` — all returned, no exception raised for
  fail/timeout (opt-in `raise_on_timeout=True` kwarg for caller
  preference). Typed errors: `CIRunnerNotFoundError` (realpath not
  under policy prefixes; preflight failure only). Flaky test
  tolerance is zero.
- Tests: 70+ new unit tests across 5 files (`test_patch_diff_engine`,
  `test_patch_apply`, `test_patch_rollback`, `test_ci_runners`,
  `test_workflow_registry_operation`). Fixtures: 5 patches + 1
  micro-repo. Coverage: `ao_kernel/patch/` ≥ 90%, `ao_kernel/ci/`
  ≥ 85%. Overall branch coverage gate ≥ 85% retained.
- Invariants (PR-A3 preserved + PR-A4a new): POSIX-only,
  `inherit_from_parent=False` strict, PATH anchoring (realpath +
  policy prefix), per-run `events.jsonl.lock` + monotonic `seq`,
  cross-ref per-call. **New (PR-A4a):** patch preflight flag-aligned
  `--check --3way --index -`; reverse-diff atomic path
  `{run_dir}/patches/{patch_id}.revdiff`; rollback idempotent on
  clean index+worktree; CI flaky tolerance = 0; patch_apply
  dirty-state cleanup protocol; `step_def.operation` required for
  ao-kernel/system actors. No new core dep; `jsonschema>=4.23.0`
  remains sole required.
- Adversarial consensus: CNS-20260415-023 iter-1 PARTIAL (8 blocking
  + 7 warning absorbed in plan v2) → iter-2 AGREE via MCP thread
  `019d928f-978f-7ac2-91cb-b0f286798cbd`. Plan v2 PR split
  recommendation `split_2_pr`.
```

### PR-A4b entry

```markdown
### Added — FAZ-A PR-A4b (multi-step driver + Executor output_ref wiring)

- `ao_kernel/executor/multi_step_driver.py`: `MultiStepDriver` class
  that iterates `workflow_definition.steps` with actor + operation
  dispatch (adapter → `Executor.run_step`; ao-kernel +
  operation=patch_* → patch primitives; system + operation=ci_* →
  CI runners; human → waiting_approval gate), handles `on_failure`
  (three variants), emits workflow-level evidence events
  (`workflow_started`, `workflow_completed`, `workflow_failed`).
  Resume position is derived from `definition.steps` order + terminal
  (highest-attempt) `step_record` entries — no `current_step_index`
  field added to schema. `retry_once` semantics: failure appends a
  new `step_record(attempt=2)` (fresh `step_id`, same `step_name`)
  under CAS before re-invocation; crash-safety rule: absent
  attempt=2 + failed attempt=1 + `on_failure=retry_once` → retry is
  NOT consumed, driver resumes with attempt=2. `escalate_to_human`
  mints an approval token via PR-A1 `mint_approval_token` and
  transitions run state to `waiting_approval` (forbidden for
  `patch_apply` steps by registry rule).
- `ao_kernel/executor/executor.py`: `Executor.run_step` now persists
  adapter output envelope to `{run_dir}/artifacts/{step_id}-
  attempt{n}.json` via atomic write (tempfile + fsync + rename);
  `step_record.output_ref` = relative path; `adapter_returned` event
  payload gains `output_ref` + SHA-256 `payload_hash` fields. Crash
  resume reads canonical patch content from the artifact path. Patch
  and CI primitives write their own artifacts at the same convention
  when invoked via driver (PR-A4a primitives already write reverse
  diffs at `{run_dir}/patches/`).
- Resume primitive integration: `MultiStepDriver.resume_workflow(
  run_id, resume_token, payload)` routes approval tokens to
  `primitives.resume_approval` and interrupt tokens to
  `primitives.resume_interrupt`; idempotent by payload hash, error
  on payload mismatch (PR-A1 invariant preserved). Driver-side
  payload hash layer ensures approval/interrupt semantics both
  support arbitrary payload with idempotency guarantee.
- `docs/EVIDENCE-TIMELINE.md` §3 `event_id` description aligned with
  PR-A3 implementation: opaque `secrets.token_urlsafe(48)`, ordering
  by `seq` (not ULID); manifest on-demand at PR-A5 CLI (already
  reflected in §4.2 as of PR-A3).
- Tests: 30+ new integration tests across 2 files
  (`test_multi_step_driver`, `test_multi_step_driver_integration`).
  Fixtures: 3 workflow definitions (happy path 4-step, retry_once
  flow, escalate_flow). Coverage: `multi_step_driver.py` ≥ 85%.
  End-to-end: `bug_fix_flow.v1` + `codex_stub` adapter + real
  subprocess `pytest`/`ruff` + dry-run PR (no real `gh` call).
- Invariants (PR-A3 + PR-A4a preserved + PR-A4b new): all of the
  above, plus **new**: `output_ref` required for durability across
  adapter + ao-kernel + system actors; retry append-only model;
  driver workflow-level cross-ref check in addition to Executor
  per-step (double-check accepted, CNS-023 Q4 ACCEPT); patch_apply
  `escalate_to_human` forbidden at registry validate.
- Adversarial consensus: plan v2 iter-2 AGREE (same thread as A4a);
  A4a merge gate before A4b impl start.
```

---

## 19. Post-PR-A4 Outlook

**PR-A5** (evidence timeline CLI)
- `ao-kernel evidence timeline --run <run_id>` — JSONL → time-ordered table
- `ao-kernel evidence replay --run <run_id> --mode inspect|dry-run` — deterministic replay
- `ao-kernel evidence verify-manifest --run <run_id>` — SHA-256 manifest on demand + verify

**PR-A6** (demo + meta-extras)
- `.demo/` runnable script: issue → workflow → agent → diff → CI → approval → PR → evidence (11-step)
- `tests/fixtures/adapter_manifests/claude-code-cli.manifest.v1.json` + `codex-cli.manifest.v1.json` + `gh-cli-pr.manifest.v1.json` (production, mevcut negative fixtures'a ek)
- `pyproject.toml` `[coding]` meta-extra = `[llm, code-index, lsp, metrics]` (stub — FAZ-C'de code-index/lsp aktif)
- `[llm]` fallback intent classifier implementation (`IntentRouter.llm_fallback` concrete)
- README integration: demo quickstart + adapter walkthrough links
- v3.1.0 release tag (FAZ-A ship)

---

## 20. Audit Trail

| Field | Value |
|---|---|
| Plan version | **v2 (post-CNS-023 iter-1 absorption)** |
| Head SHA at draft | `c5d0ff0` |
| Base branch | `main` |
| Target branches | **A4a** `claude/tranche-a-pr-a4a`, **A4b** `claude/tranche-a-pr-a4b` (A4a merge sonrası) |
| Reference plans | `.claude/plans/PR-A0..A3-IMPLEMENTATION-PLAN.md` (all v2 final) |
| Strategy source | `.claude/plans/TRANCHE-STRATEGY-V2.md` v2.1.1 §10 FAZ-A release gates |
| Session handoff | `.claude/plans/SESSION-HANDOFF-TRANCHE-A-MID.md` |
| CNS-023 iter-1 | request `CNS-20260415-023.request.v1.json` (9 Q), response `...codex.response.v1.json` (PARTIAL, 8B + 7W) |
| CNS-023 iter-2 | §17 absorption map + 4 MV sorusu; MCP `codex-reply` same thread `019d928f-978f-7ac2-91cb-b0f286798cbd` |
| Worktree | `.claude/worktrees/lucid-cerf` (current session) |
| Contract repair status | **DONE in worktree** (state_machine + 2 schemas + evidence_emitter + 2 docs + bundled workflow + 2 test fixtures); commit bekliyor |
| Total test target | **A4a:** 1398+ (1328 + ≥70); **A4b:** 1428+ (A4a + ≥30) |
| Coverage gate | 85% branch (retained) |
| Core dep | `jsonschema>=4.23.0` (unchanged) |
| PR size estimate | A4a ~2050 LOC, A4b ~1855 LOC |
| iter-2 expected verdict | AGREE (CNS-022 pattern); residual warnings implementation-time |

**Status:** Plan v2 complete. Next: CNS-023 iter-2 via `mcp__codex__codex-reply` (same thread), expect AGREE → start A4a impl on fresh branch `claude/tranche-a-pr-a4a` → Layer 0 commit (contract repair already in worktree) → Layer 1-6 → CI green → M2 merge → A4b branch.
