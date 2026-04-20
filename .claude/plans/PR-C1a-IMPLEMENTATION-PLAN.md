# PR-C1a Implementation Plan v2 — Adapter Artifact Surface + Context Compile Materialisation

**Scope**: FAZ-C critical-path seri başı. Adapter-path output_ref garantisi + `context_compile` step real materialisation + `build_driver(policy_loader=...)` forward + `context_pack_ref` plumbing. Downstream PR'lar (C1b/C2/C3/C6) bu altyapıya bağımlı.

**Base**: `main 5fb7f31` (PR #108 tooling merged). **Branch**: `feat/pr-c1a-adapter-surface`.

**Status**: iter-1 PARTIAL absorb → iter-2 submit için hazır. Codex thread `019d9fc3-1b0b-76b2-b425-0f3dfd6efc66`.

---

## v2 absorb summary (Codex iter-1 PARTIAL — 3 blocker + 3 warning)

Codex iter-1 fact-check ile v1'deki 3 tasarım hatası düzeltildi (kod-okuma: `adapter_invoker.py:514`, `executor.py:419-422`, `multi_step_driver.py:594-609`, `workflow-definition.schema.v1.json:101`, `registry.py:55`, `context_compiler.py:42`, `utils.py:47`).

| # | iter-1 bulgu | v2 fix |
|---|---|---|
| **B1** | v1 "`InvocationResult.output_ref`" yanlış — alan yok, envelope parser populate etmiyor (`adapter_invoker.py:514`, `agent-adapter-contract.schema.v1.json:299`). Executor zaten `write_artifact()` ile local `output_ref` üretiyor (`executor.py:422`). | v2: `InvocationResult` değişmez. `ExecutionResult.output_ref`, Executor adapter branch'inde mevcut local `output_ref`'tan (line 422 `write_artifact` sonucu) doldurulur. Driver-managed path da aynı pattern. |
| **B2** | v1 `step_def.context_spec` + `input_envelope_template` yüzeyleri yok — `StepDefinition` bunları taşımıyor (`registry.py:55`), workflow schema tanımlı değil (`workflow-definition.schema.v1.json:101`). | v2: Bu yüzeyleri icat etme. `context_compile` **zaten explicit ao-kernel step** olarak modellenmiş (`multi_step_driver.py:594`). Materialisation step handler içinde yapılır — Executor'a spec push edilmez. Adapter invocation sadece referans çözümler. |
| **B3** | v1 `".ao/runs/{run_id}/context.md"` relative path yanlış. Adapter CLI subprocess worktree kökünde çalışır (`adapter_invoker.py:135`, `worktree_builder.py:91`: worktree = `.ao/runs/{run_id}/worktree`). Worktree-relative "../context.md" çözmez. | v2: Mutlak path kullan. `context.md` evidence dir'de yazılır (`.ao/evidence/workflows/{run_id}/context-{step_id}-{attempt}.md`), adapter envelope'ına absolute path geçer. `_substitute_args` plain string replace; absolute path'ı literal geçer, subprocess okuyabilir. |

### v2 absorb warnings

- **W1** (iter-1): `gh-cli-pr` manifest `args` `{context_pack_ref}` kullanıyor ama `input_envelope` shape deklare etmiyor (`gh-cli-pr.manifest.v1.json:9,15`). **C1a out-of-scope**: manifest tutarsızlığı C1b full bundled bug_fix_flow test'inde ortaya çıkacak; C1b kapsamında manifest shape düzeltilecek. C1a dokümantasyonu bu gap'i flag'ler.
- **W2** (iter-1): `build_driver(policy_loader)` sadece Executor'a forward ediyor; driver'ın kendi policy yüzeyi ayrı (`multi_step_driver.py:189,1674`). C1a scope: **Executor-only override**. Plan §2.1 dili "Executor policy override forward" olarak daraltıldı.
- **W3** (iter-1): Repo'da `context_compiler.compile_context()` pipeline mevcut (`context/context_compiler.py:53-90`). v1'in role/constraints/references markdown şablonu bu pipeline ile hizasız. v2: Mevcut `compile_context()` → `CompiledContext.preamble` serialize edilir; v1 şablonu drop.

---

## 1. Problem

FAZ-C master plan iter-1 Codex fact-check + iter-6 C1a decouple karar sonrası tespit edilen 4 runtime gap:

| Kod yüzey | Bugünkü hâl | Gap |
|---|---|---|
| `tests/_driver_helpers.build_driver(root: Path)` | Sadece `root` alır; Executor default bundled policy ile kurulur (`_driver_helpers.py:100-119`). | Benchmark'lar + FAZ-C testleri policy override gerektirir. `Executor.__init__(policy_loader=...)` kwarg zaten var; helper forward etmez. |
| `Executor.ExecutionResult` dataclass | `{new_state, step_state, invocation_result, evidence_event_ids, budget_after}` (`executor.py:68-74`). `output_ref` field YOK. | Executor adapter branch'i zaten local `output_ref` üretiyor (line 422, `write_artifact` dönüşü) ama ExecutionResult'a yansıtmıyor. `multi_step_driver._update_step_record_with_output_ref` `getattr(exec_result, "output_ref", None)` ile okuyor (line 1321-1323) — adapter-path'te hep None. |
| `multi_step_driver._run_ao_kernel_step::context_compile` | A4b stub (`multi_step_driver.py:594-609`): `payload={"stub": True, "context_preamble_bytes": 0}`, `write_artifact` ile canonical JSON yazar, **gerçek preamble üretmez**. | `claude-code-cli` / `gh-cli-pr` manifest `{context_pack_ref}` CLI flag'ına `--prompt-file <path>` olarak geçer (`claude-code-cli.manifest.v1.json:9`). Path placeholder literal kalıyor → adapter prompt-file okuyamaz. |
| `_substitute_args` envelope key resolver (`adapter_invoker.py:702`) | Plain string replace: her envelope key için `"{key}" -> value`. Eksik placeholder literal kalır. | Workflow DAG'da `context_compile` step çıkışı → sonraki adapter step envelope'ında `context_pack_ref` değeri olarak plumb edilmez. |

---

## 2. Scope (atomic deliverable)

### 2.1 `_driver_helpers.build_driver` forward — Executor-only policy override

**Before**:
```python
def build_driver(root: Path) -> MultiStepDriver:
    ...
    executor = Executor(
        workspace_root=root,
        workflow_registry=wreg,
        adapter_registry=areg,
    )
    return MultiStepDriver(...)
```

**After** (additive keyword-only kwarg, default None → current behavior):
```python
def build_driver(
    root: Path,
    *,
    policy_loader: Mapping[str, Any] | None = None,
) -> MultiStepDriver:
    ...
    executor = Executor(
        workspace_root=root,
        workflow_registry=wreg,
        adapter_registry=areg,
        policy_loader=policy_loader,  # Executor-only override forward
    )
    return MultiStepDriver(...)
```

**Scope netleştirme (iter-1 W2 absorb)**: Driver'ın kendi policy yüzeyi (`multi_step_driver.py:189,1674`) bu PR'da dokunulmaz. C1a scope = Executor-layer policy override forward. Driver-level override gerekirse ayrı PR (C1b veya sonraki).

### 2.2 `ExecutionResult.output_ref` additive field (Executor-side source)

**Before**:
```python
@dataclass(frozen=True)
class ExecutionResult:
    new_state: WorkflowState
    step_state: str
    invocation_result: InvocationResult | None
    evidence_event_ids: tuple[str, ...]
    budget_after: Mapping[str, Any]
```

**After** (additive Optional field, default None):
```python
@dataclass(frozen=True)
class ExecutionResult:
    new_state: WorkflowState
    step_state: str
    invocation_result: InvocationResult | None
    evidence_event_ids: tuple[str, ...]
    budget_after: Mapping[str, Any]
    output_ref: str | None = None
```

**Populate policy (iter-1 B1 absorb)**:
- **Adapter path** (`executor.py:422`): Mevcut `output_ref, output_sha256 = write_artifact(...)` satırı; ExecutionResult return satırında `output_ref=output_ref` yansıtılır.
- **Driver-managed path** (`executor.py:601, 696, 800`): Mevcut `output_ref` zaten artifact-level; aynı şekilde ExecutionResult'a yansıtılır.
- **InvocationResult değişmez**: Yeni alan eklenmez (iter-1 B1).
- **Adapter manifest schema değişmez**: `agent-adapter-contract.schema.v1.json::output_ref` field yok, eklenmez (iter-1 B1).

### 2.3 `context_compile` step real materialisation

**Before** (`multi_step_driver.py:594-609`, A4b stub):
```python
if op == "context_compile":
    payload = {
        "operation": "context_compile",
        "stub": True,
        "context_preamble_bytes": 0,
    }
    output_ref, output_sha256 = write_artifact(...)
    return dict(record), {
        "step_state": "completed",
        "output_ref": output_ref,
        "output_sha256": output_sha256,
        "operation": op,
    }
```

**After** (gerçek compile + markdown materialisation):
```python
if op == "context_compile":
    from ao_kernel.context.context_compiler import compile_context
    from ao_kernel.context.canonical_store import load_canonical_decisions
    from ao_kernel.context.workspace_facts import load_workspace_facts
    from ao_kernel._internal.shared.utils import write_text_atomic
    
    # Load 3-lane context (existing pipeline)
    session_context = dict(record.get("session_context") or {})
    canonical = load_canonical_decisions(self._workspace_root)
    facts = load_workspace_facts(self._workspace_root)
    
    compiled = compile_context(
        session_context,
        canonical_decisions=canonical,
        workspace_facts=facts,
        profile="TASK_EXECUTION",  # default; future: from step_def
    )
    
    # Write markdown preamble (absolute path for adapter subprocess)
    context_path = (
        run_dir / f"context-{step_id}-attempt{attempt}.md"
    )
    write_text_atomic(context_path, compiled.preamble)
    
    # Canonical evidence JSON (existing pattern, now with real metadata)
    payload = {
        "operation": "context_compile",
        "stub": False,
        "context_preamble_bytes": len(compiled.preamble.encode("utf-8")),
        "context_path": str(context_path),  # absolute
        "total_tokens": compiled.total_tokens,
        "items_included": compiled.items_included,
        "items_excluded": compiled.items_excluded,
        "profile_id": compiled.profile_id,
    }
    output_ref, output_sha256 = write_artifact(
        run_dir=run_dir, step_id=step_id, attempt=attempt, payload=payload,
    )
    return dict(record), {
        "step_state": "completed",
        "output_ref": output_ref,
        "output_sha256": output_sha256,
        "operation": op,
        "context_path": str(context_path),  # downstream plumbing için
    }
```

**Path semantics (iter-1 B3 absorb)**: `context_path` **absolute path** (`{workspace_root}/.ao/evidence/workflows/{run_id}/context-{step_id}-attempt{attempt}.md`). Adapter subprocess worktree cwd'sinde çalışsa bile absolute path okunur. `run_dir` zaten `_run_ao_kernel_step` içinde hesaplanmış (line 588).

**Helper seçimi (iter-1 Q4 absorb)**: `write_text_atomic` (`_internal/shared/utils.py:47`) — markdown düz dosya için doğru. `write_artifact` canonical JSON + SHA256 + JSONL manifest; context.md için overkill.

**Template shape (iter-1 W3 + Q2 absorb)**: `compile_context()` dönen `CompiledContext.preamble` directly serialize edilir. v1'in role/constraints/references manuel şablonu dropped — mevcut pipeline'ı tekrar icat etmek yanlış.

### 2.4 `context_pack_ref` envelope plumbing

**Before**: Workflow step zincirinde `context_compile` step çıkışı → sonraki adapter step envelope'ında `context_pack_ref` resolver'ı yok. Envelope `{context_pack_ref}` placeholder literal kalır.

**After** (minimum viable plumbing):

`multi_step_driver` içinde adapter step envelope builder:
```python
def _build_adapter_input_envelope(
    self, run_id: str, step_def: StepDefinition, record: Mapping[str, Any],
) -> dict[str, Any]:
    """Build input_envelope for adapter step; resolve context_pack_ref
    from most recent completed context_compile step in the run."""
    envelope = {
        "task_prompt": step_def.task_prompt or "",
        "run_id": run_id,
    }
    # context_pack_ref resolution: scan prior completed steps for
    # `operation == "context_compile"` → take the most recent
    # `context_path`. If none → placeholder stays literal (backwards-
    # compat: zero-prior-context-compile runs still work).
    for prior in reversed(record.get("steps", [])):
        if (
            prior.get("state") == "completed"
            and prior.get("operation") == "context_compile"
            and prior.get("context_path")
        ):
            envelope["context_pack_ref"] = prior["context_path"]
            break
    return envelope
```

**Resolver semantiği (iter-1 Q3 + B3 absorb)**: Adapter envelope'una `context_pack_ref` key'i konulursa, `_substitute_args` (`adapter_invoker.py:702`) plain string replace ile `"{context_pack_ref}"` → absolute path'ı literal geçirir. Key yoksa placeholder literal kalır (zero-prior-context-compile test case — backwards-compat).

**StepDefinition değişmez (iter-1 B2 absorb)**: `context_spec` yeni field yok. `input_envelope_template` yok. Envelope builder workflow record steps history'sinden türetir.

---

## 3. Test Plan

### 3.1 Yeni testler

- `tests/test_driver_helpers_policy_loader.py`:
  - `build_driver(root, policy_loader=custom)` → Executor custom policy kullanır.
  - `build_driver(root)` → default bundled policy (backwards-compat).
- `tests/test_executor_adapter_output_ref.py`:
  - Adapter path mock invocation → `write_artifact` çağrısı → `ExecutionResult.output_ref` populated (run-relative path).
  - Driver-managed path → `ExecutionResult.output_ref` aynı şekilde populated.
- `tests/test_context_compile_materialisation.py`:
  - `context_compile` step → `.ao/evidence/workflows/{run_id}/context-{step_id}-attempt1.md` yazılır.
  - İçerik: `compile_context()` preamble (session_context + canonical + facts).
  - Atomic: tmp file process crash olsa kalmaz.
  - Canonical evidence JSON `stub: false` + `context_preamble_bytes > 0` + `context_path` absolute.
- `tests/test_context_pack_ref_plumbing.py`:
  - 2-step run: `context_compile` → `invoke_adapter`.
  - Adapter envelope `context_pack_ref` = prior step `context_path` (absolute).
  - Zero-prior-context-compile: `{context_pack_ref}` literal kalır.

### 3.2 Regression gate

- `pytest tests/ -x` 2142 test green.
- Özellikle B6 `tests/benchmarks/test_governed_review.py` — `capability_output_refs` plumbing (line 1321-1335) değişmez; ExecutionResult.output_ref ekleme mevcut davranışı kırmaz.
- B7 `tests/benchmarks/test_governed_review.py::TestCostReconcile` — B7.1 cost_usd shim korunur (C3 scope değil).

### 3.3 Coverage

- `ao_kernel.executor.executor::ExecutionResult` — field delta.
- `ao_kernel.executor.multi_step_driver::_run_ao_kernel_step` context_compile branch — compile_context + write_text_atomic yeni path.
- `ao_kernel.executor.multi_step_driver::_build_adapter_input_envelope` (yeni fonksiyon) — context_pack_ref resolver.

---

## 4. Out of Scope

- **C1b** (full bundled `bug_fix_flow` E2E + manifest shape fix `gh-cli-pr` — iter-1 W1) — ayrı PR, C1a merge sonrası.
- **C2** (parent_env union: `allowlist_secret_ids ∪ env_allowlist.allowed_keys`) — C1a merge sonrası paralel.
- **C3** (`cost_usd` reconcile + `post_adapter_reconcile` middleware) — C1a merge sonrası paralel.
- **C6** (`dry_run_step`) — C1a merge sonrası paralel.
- Driver-level policy override (iter-1 W2) — gerekirse ayrı PR.
- Yeni StepDefinition field / workflow schema delta — hiçbiri.
- Yeni InvocationResult field / adapter contract schema delta — hiçbiri.

---

## 5. Risk Register

| Risk | L | I | Mitigation |
|---|---|---|---|
| R1 `compile_context()` pipeline B6/B7 benchmark testlerinde unbounded side-effect üretir | M | M | `profile="TASK_EXECUTION"` bounded token budget + existing pipeline'a smoke test |
| R2 `_build_adapter_input_envelope` scan prior steps performans concern (N-step run'larda O(N)) | L | L | Reverse iteration + early break — FAZ-C workflow'ları ≤10 step |
| R3 `write_text_atomic` tmp dosyası concurrency'de çakışma | L | M | Per-(run_id, step_id, attempt) dosya adı UUID-scoped — çakışma teorik yok |
| R4 B6 `capability_output_refs` plumbing C1a `ExecutionResult.output_ref` ekleme ile kırılır | M | H | Regression gate: `test_governed_review.py` green. B6 `getattr` pattern field eklemeyi tolere eder |
| R5 `context_compile` step olmayan workflow'larda adapter envelope placeholder literal kalır → prod adapter `--prompt-file` okuyamaz | M | H | Placeholder literal = explicit "no context" kontrat; documented in C1a scope. C1b + C2'de real adapter manifest `--prompt-file` conditional (context varsa geçir) |

---

## 6. Implementation Order

1. **`ExecutionResult.output_ref` field** — dataclass delta + Executor adapter + driver-managed branch populate.
2. **`build_driver(policy_loader=)` forward** — tek satır.
3. **`context_compile` step materialisation** — `compile_context()` integration + `write_text_atomic` + metadata evidence.
4. **`_build_adapter_input_envelope` context_pack_ref resolver** — prior steps scan + envelope key populate.
5. **4 yeni test + regression (`pytest -x`)**.
6. **Commit + Codex post-impl review (thread `019d9fc3`) + PR #109 open + admin merge (after CI green + Codex AGREE)**.

---

## 7. LOC Estimate

~500 satır (ExecutionResult +1 field, build_driver +3 satır, context_compile handler +40 satır, envelope builder +20 satır, 4 yeni test ~350 satır, helper imports +5).

---

## 8. Audit Trail

| Iter | Date | Verdict |
|---|---|---|
| v1 (Claude draft) | 2026-04-18 | Pre-Codex submit (`c2b61d9`) |
| iter-1 (thread `019d9fc3`) | 2026-04-18 | **PARTIAL** — 3 blocker (InvocationResult.output_ref yanlış kaynak, context_spec/input_envelope_template yok, relative path runtime'da çözmez) + 3 warning (gh-cli-pr manifest inconsistency, build_driver scope wording, existing context pipeline alignment) + Q1-Q5 net cevaplar |
| **v2 (iter-1 absorb)** | 2026-04-18 | Pre-iter-2 submit. Executor-side output_ref + explicit context_compile step + absolute path + existing compile_context() reuse. |
| iter-2 | TBD | AGREE expected (3 blocker + 3 warning tam absorb; dar scope revisions) |

### Plan revision history

| Ver | Change |
|---|---|
| v1 | 4 gap + 5 Q for Codex; InvocationResult.output_ref varsayımı + context_spec icat + relative path |
| **v2** | iter-1 PARTIAL absorb: output_ref kaynağı Executor `write_artifact` (InvocationResult dokunulmaz), context_compile step handler scope (StepDefinition değişmez), absolute path semantic, mevcut `compile_context()` reuse (role/constraints/references drop), build_driver scope "Executor-only" daraltıldı. |

**Status**: Plan v2 hazır. Codex thread `019d9fc3` iter-2 submit için hazır. 3 blocker tam absorb; 3 warning netleşti. AGREE beklenir.
