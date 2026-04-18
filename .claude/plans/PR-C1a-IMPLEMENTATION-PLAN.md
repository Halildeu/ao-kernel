# PR-C1a Implementation Plan v5 — Adapter Artifact Surface + Context Compile Materialisation

**v5 absorb (iter-4 PARTIAL — 3 blocker + 2 warning, all text-level)**: `exec_result` (not `step_state`) in `_record_step_completion`; canonical key is `"key"` (not `"decision_id"`); `parent_env` removed from `_run_adapter_step` example (stays `{}` — scope unchanged); test `>= 0` consistency; `_build_adapter_envelope_with_context` rename sync throughout.

---

# (v4 retained for history)

## PR-C1a Implementation Plan v4 — Adapter Artifact Surface + Context Compile Materialisation

**Scope**: FAZ-C critical-path seri başı. Adapter-path output_ref garantisi + `context_compile` step real materialisation + `build_driver(policy_loader=...)` forward + `context_pack_ref` plumbing. Downstream PR'lar (C1b/C2/C3/C6) bu altyapıya bağımlı.

**Base**: `main 5fb7f31` (PR #108 tooling merged). **Branch**: `feat/pr-c1a-adapter-surface`.

**Status**: iter-3 PARTIAL absorb → iter-4 submit için hazır. Codex thread `019d9fc3-1b0b-76b2-b425-0f3dfd6efc66`.

---

## v4 absorb summary (Codex iter-3 PARTIAL — 4 blocker + 2 warning)

Iter-3 fact-check ile 4 API/attribute isim hatası + handler return dict eksik:

| # | iter-3 bulgu | v4 fix |
|---|---|---|
| **B1** | Driver call `driver_managed=False` yanlış — driver contract `driver_managed=True` (`multi_step_driver.py:434,468`, `executor.py:129,478`). | v4: `driver_managed=True` override. Driver-owned CAS + capability artifact akışı korunur. |
| **B2** | Resolver repo gerçekleriyle uyuşmuyor: `self._workflow_registry` yok (`self._registry`), `record["steps"]` liste (dict değil), `output_ref` run-relative `artifacts/...` (workspace-relative değil). | v4: `self._registry`, list iteration, artifact path = `workspace_root/.ao/evidence/workflows/{run_id}/{output_ref}`. |
| **B3** | `canonical_store.query(workspace_root: Path, *, ...)` — `limit` kwarg yok; list döner. `compile_context()` `canonical_decisions` için `.items()` çağırıyor (dict bekler). | v4: `query(self._workspace_root)` signature fix + list → dict wrap: `{item["decision_id"]: item for item in canonical_list}`. |
| **B4** | Handler return dict `context_preamble_bytes` + `context_path` taşımıyor; `_record_step_completion` `step_state.get()` ile okuyor → mismatch. Test `bytes > 0` empty-fixture'da fail olur. | v4: Handler return dict'e `context_preamble_bytes` + `context_path` eklenir. Test assertion `bytes >= 0` + `context_path.is_file()` (dosya varlık kontratı). |

### v4 absorb warnings

- **W1** (iter-3): Resolver `compile_step_names[0]` "ilk tanımlı" step seçiyor → çok-adımlı flow'larda yanlış context seçme riski. v4: Workflow step execution ORDER'ına göre (workflow_def.steps listesi topological order) + completion filter; "en son completed context_compile before current step" semantik. Dar-scope test `test_multi_context_compile_steps.py` eklenir (MVP 1 context_compile; ama semantik pin'li).
- **W2** (iter-3): Master plan v5 drift follow-up item. v4 §5'te açık: C1a merge sonrası master plan v6 docs sync commit (ayrı 1-satır PR). PR body'de explicit drift note.

---

---

## v3 absorb summary (Codex iter-2 PARTIAL — 3 blocker + 3 warning)

Iter-2 kod-okuması ile v2'de kaçırdığım 3 coupling hatası:

| # | iter-2 bulgu | v3 fix |
|---|---|---|
| **B1** | v2 resolver `record["steps"]` üzerinde `operation` + `context_path` aradı — ama `step_record` schema `additionalProperties=false` (`workflow-run.schema.v1.json:154`), bu field'lar persist edilmiyor (`multi_step_driver.py:1414`). | v3: Resolver **artifact JSON read** — workflow_def'ten `operation=="context_compile"` step_name bul → `record.steps[step_name].output_ref` oku → o canonical JSON'un `context_path` field'ını parse et. Schema widen YOK. |
| **B2** | v2 `_build_adapter_input_envelope()` mevcut çağrı zincirine bağlı değil. Envelope bugün `Executor.run_step()` içinde üretiliyor (`executor.py:383`); driver override vermiyor. Ayrıca `step_def.task_prompt` yok — kaynak `record.intent.payload` (`executor.py:384`). | v3: `Executor.run_step(..., input_envelope_override: Mapping \| None = None)` **additive kwarg** widen. Driver pre-compute + override pass. `task_prompt` kaynağı `record.intent.payload` pin (schema+kod contract). |
| **B3** | v2 `context_compile` gerçek hale gelse bile `_record_step_completion()` `operation=="context_compile"` gördüğünde `payload.stub=True` + `context_preamble_bytes=0` hardcode ediyor (`multi_step_driver.py:1392`). Test bunu assert ediyor (`test_multi_step_driver.py:55`). | v3: §3 `_record_step_completion` hardcode absorb — step handler dönüş dict'inden gerçek değerler okunur. `test_context_compile_stub_emits_stub_marker` testi güncellenir (stub=False, bytes>0, context_path). |

### v3 absorb warnings

- **W1** (iter-2): v2 helper isimleri `load_canonical_decisions` / `load_workspace_facts` yok. Gerçek: `ao_kernel.context.canonical_store::query/load_store` (`agent_coordination.py:202` pattern) + workspace facts `.cache/index/workspace_facts.v1.json` direct JSON read. Run schema top-level `session_context` taşımıyor (`workflow-run.schema.v1.json:22`) → MVP `session_context={}`. v3 §2.3 code örneği düzeltildi.
- **W2** (iter-2): Master plan v5 hâlâ `".ao/runs/{run_id}/context.md"` diyor (`FAZ-C-MASTER-PLAN.md:129`); C1a plan absolute evidence-dir path kullanıyor. Drift var. **Çözüm**: C1a merge ile birlikte master plan v6 ayrı commit — bu PR'dan sonra ya da paralel docs PR. C1a PR description'da drift not edilir.
- **W3** (iter-2): `gh-cli-pr` manifest tutarsızlığı C1a out-of-scope. PR description'a explicit disclaimer: "C1a closes adapter artifact surface + context materialisation; `open_pr` chain full-flow proof C1b'de".

---

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
    from ao_kernel.context.canonical_store import query
    from ao_kernel._internal.shared.utils import write_text_atomic
    import json as _json
    
    # MVP: session_context = {} (workflow-run schema top-level taşımıyor)
    session_context: dict[str, Any] = {}
    
    # Canonical decisions: query signature (workspace_root: Path, *, ...)
    # returns list; compile_context() expects dict with .items() so wrap.
    canonical_list = query(self._workspace_root)
    canonical = {
        item.get("key", f"_idx_{idx}"): item
        for idx, item in enumerate(canonical_list)
    }
    
    # Workspace facts: direct JSON read
    facts_path = (
        self._workspace_root / ".cache" / "index" / "workspace_facts.v1.json"
    )
    facts = _json.loads(facts_path.read_text()) if facts_path.is_file() else {}
    
    compiled = compile_context(
        session_context,
        canonical_decisions=canonical,
        workspace_facts=facts,
        profile="TASK_EXECUTION",
    )
    
    # Write markdown preamble (absolute path for adapter subprocess)
    context_path = (
        run_dir / f"context-{step_id}-attempt{attempt}.md"
    )
    write_text_atomic(context_path, compiled.preamble)
    
    # Canonical evidence JSON with real metadata (stub=False)
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
        # v4 B4 absorb: propagate to step_state so _record_step_completion
        # reads real values (not stub hardcode).
        "context_preamble_bytes": len(compiled.preamble.encode("utf-8")),
        "context_path": str(context_path),
    }
```

**`_record_step_completion` hardcode absorb (iter-2 B3)**:

`multi_step_driver.py:1392` mevcut kod context_compile için stub=True hardcode ediyor. v3 değişikliği:
```python
# Before (multi_step_driver.py:1392-1400):
if step_def.operation == "context_compile":
    payload = {"stub": True, "context_preamble_bytes": 0}

# After (v3):
if step_def.operation == "context_compile":
    # Step handler dönüş dict'inden gerçek değerler
    # Handler artifact JSON yazdı; burada artifact'ı re-read etmek
    # yerine exec_result dict'inden (handler return'dan) çekeriz.
    # Handler return dict'i zaten output_ref içeriyor; ek metadata
    # için artifact JSON parse edilebilir ama daha pahalı.
    # Minimal çözüm: handler return dict'ine payload alanlarını ekle
    # (handler zaten yaratıyor; sadece propagate edilir).
    payload = {
        "stub": False,
        "context_preamble_bytes": exec_result.get(
            "context_preamble_bytes", 0
        ),
        "context_path": exec_result.get("context_path"),
    }
```

Bu değişiklik test `test_context_compile_stub_emits_stub_marker` kontratını günceller — artık assertion (v4 B4 absorb — empty-fixture tolerant):
```python
# Before
assert payload["stub"] is True
assert payload["context_preamble_bytes"] == 0
# After (v4 — empty canonical/facts fixture için bytes 0 olabilir)
assert payload["stub"] is False
assert payload["context_preamble_bytes"] >= 0  # empty fixture tolerates
assert payload["context_path"] is not None
assert Path(payload["context_path"]).is_file()  # dosya gerçekten var
```

Step handler return dict'i `context_preamble_bytes` + `context_path` taşır (§2.3 "After" kod örneğinde eklendi).

**Path semantics (iter-1 B3 absorb)**: `context_path` **absolute path** (`{workspace_root}/.ao/evidence/workflows/{run_id}/context-{step_id}-attempt{attempt}.md`). Adapter subprocess worktree cwd'sinde çalışsa bile absolute path okunur. `run_dir` zaten `_run_ao_kernel_step` içinde hesaplanmış (line 588).

**Helper seçimi (iter-1 Q4 absorb)**: `write_text_atomic` (`_internal/shared/utils.py:47`) — markdown düz dosya için doğru. `write_artifact` canonical JSON + SHA256 + JSONL manifest; context.md için overkill.

**Template shape (iter-1 W3 + Q2 absorb)**: `compile_context()` dönen `CompiledContext.preamble` directly serialize edilir. v1'in role/constraints/references manuel şablonu dropped — mevcut pipeline'ı tekrar icat etmek yanlış.

### 2.4 `context_pack_ref` envelope plumbing

**Before**: Workflow step zincirinde `context_compile` step çıkışı → sonraki adapter step envelope'ında `context_pack_ref` resolver'ı yok. Envelope `{context_pack_ref}` placeholder literal kalır.

**After** (v3 — artifact JSON read + Executor override widen):

**B1.1 — `Executor.run_step` additive `input_envelope_override` kwarg** (`executor.py:383`):
```python
def run_step(
    self,
    run_id: str,
    step_def: StepDefinition,
    *,
    parent_env: Mapping[str, str] | None = None,
    attempt: int = 1,
    driver_managed: bool = False,
    input_envelope_override: Mapping[str, Any] | None = None,  # YENI
    ...
) -> ExecutionResult:
    ...
    if input_envelope_override is not None:
        input_envelope = dict(input_envelope_override)
    else:
        # Existing behavior: task_prompt = record.intent.payload 
        input_envelope = {
            "task_prompt": record.get("intent", {}).get("payload", ""),
            "run_id": run_id,
        }
    ...
```

Backwards-compat: `input_envelope_override=None` → mevcut davranış. Mevcut caller'lar etkilenmez.

**B1.2 — Driver resolver `MultiStepDriver._build_adapter_envelope_with_context` (yeni method)**:
```python
def _build_adapter_envelope_with_context(
    self, run_id: str, step_def: StepDefinition, record: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Resolve context_pack_ref from most recent completed
    context_compile step in the run. Returns envelope override dict
    OR None if no context available (caller falls back to Executor
    default envelope)."""
    # 1. Workflow tanımından context_compile step_name'lerini bul
    #    (v4 B2 absorb: self._registry — self._workflow_registry değil)
    workflow_def = self._registry.get(
        record["workflow_id"], record["workflow_version"],
    )
    compile_step_names = {
        sd.step_name for sd in workflow_def.steps
        if sd.operation == "context_compile"
    }
    if not compile_step_names:
        return None
    
    # 2. steps LIST iteration (v4 B2 absorb: record["steps"] is list)
    #    En son tamamlanan context_compile step (reverse order)
    compile_record = None
    for prior in reversed(record.get("steps", [])):
        if (
            prior.get("step_name") in compile_step_names
            and prior.get("state") == "completed"
            and prior.get("output_ref")
        ):
            compile_record = prior
            break
    if compile_record is None:
        return None
    
    # 3. Artifact path = evidence run_dir + run-relative output_ref
    #    (v4 B2 absorb: output_ref is run-relative "artifacts/..."
    #    per artifacts.py:50,108 — NOT workspace-relative)
    run_dir = (
        self._workspace_root / ".ao" / "evidence" / "workflows" / run_id
    )
    artifact_path = run_dir / compile_record["output_ref"]
    if not artifact_path.is_file():
        return None
    
    artifact = _json.loads(artifact_path.read_text())
    context_path = artifact.get("context_path")
    if not context_path:
        return None
    
    # 4. Envelope (task_prompt = record.intent.payload; iter-2 B2 pin)
    return {
        "task_prompt": record.get("intent", {}).get("payload", ""),
        "run_id": run_id,
        "context_pack_ref": context_path,  # absolute
    }
```

**Çok-adımlı workflow semantiği (iter-3 W1 absorb)**: Reverse iteration + completion filter → "en son completed context_compile before current step" semantiği. MVP workflow'larda 1 context_compile; ama çok-adımlı pattern desteklenir.

**B1.3 — Driver `_run_adapter_step` override forward** (`multi_step_driver.py:467`):
```python
# Inside _run_adapter_step (before executor.run_step call)
envelope_override = self._build_adapter_envelope_with_context(
    run_id, step_def, record,
)
execution_result = self._executor.run_step(
    run_id,
    step_def,
    # parent_env kept as {} per current contract (C2 scope widens later).
    parent_env={},
    attempt=attempt,
    driver_managed=True,  # v4 B1 absorb: driver contract
    input_envelope_override=envelope_override,  # None | dict
)
```

**Resolver semantiği (iter-1 Q3 + iter-2 B1 absorb)**: Adapter envelope'una `context_pack_ref` absolute path konulursa, `_substitute_args` (`adapter_invoker.py:702`) plain string replace ile `"{context_pack_ref}"` → absolute path'ı literal geçirir. Resolver `None` dönerse Executor default envelope kullanılır (placeholder literal kalır — zero-prior-context-compile test case).

**StepDefinition değişmez (iter-1 B2 absorb)**: `context_spec` + `input_envelope_template` icat yok. `step_record` schema değişmez (iter-2 B1 absorb): `operation` / `context_path` alanları eklenmez. Context path discovery artifact JSON'dan türetilir (step_record.output_ref pointer).

**`task_prompt` kaynağı pin (iter-2 B2 absorb)**: `record.intent.payload` — mevcut kontrat (`executor.py:384`).

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
  - Canonical evidence JSON `stub: false` + `context_preamble_bytes >= 0` (empty-fixture tolerant) + `context_path` absolute + `Path(context_path).is_file()`.
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
| R2 `_build_adapter_envelope_with_context` scan prior steps performans concern (N-step run'larda O(N)) | L | L | Reverse iteration + early break — FAZ-C workflow'ları ≤10 step |
| R3 `write_text_atomic` tmp dosyası concurrency'de çakışma | L | M | Per-(run_id, step_id, attempt) dosya adı UUID-scoped — çakışma teorik yok |
| R4 B6 `capability_output_refs` plumbing C1a `ExecutionResult.output_ref` ekleme ile kırılır | M | H | Regression gate: `test_governed_review.py` green. B6 `getattr` pattern field eklemeyi tolere eder |
| R5 `context_compile` step olmayan workflow'larda adapter envelope placeholder literal kalır → prod adapter `--prompt-file` okuyamaz | M | H | Placeholder literal = explicit "no context" kontrat; documented in C1a scope. C1b + C2'de real adapter manifest `--prompt-file` conditional (context varsa geçir) |

---

## 6. Implementation Order

1. **`ExecutionResult.output_ref` field** — dataclass delta + Executor adapter + driver-managed branch populate.
2. **`build_driver(policy_loader=)` forward** — tek satır.
3. **`context_compile` step materialisation** — `compile_context()` integration + `write_text_atomic` + metadata evidence.
4. **`_build_adapter_envelope_with_context` context_pack_ref resolver** — prior steps scan + envelope key populate.
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
| iter-1 (thread `019d9fc3`) | 2026-04-18 | **PARTIAL** — 3 blocker (InvocationResult.output_ref yanlış, context_spec/input_envelope_template yok, relative path runtime'da çözmez) + 3 warning + Q1-Q5 net cevaplar |
| v2 (iter-1 absorb) | 2026-04-18 | `734b81f` commit |
| iter-2 | 2026-04-18 | **PARTIAL** — 3 blocker (step_record schema `operation`/`context_path` persist etmiyor, `_build_adapter_envelope_with_context` çağrı zincirinde yok + `step_def.task_prompt` yok, `_record_step_completion` stub hardcode) + 3 warning (helper names, master plan drift, gh-cli-pr disclaimer) |
| **v3 (iter-2 absorb)** | 2026-04-18 | Pre-iter-3 submit. Artifact JSON read resolver + `input_envelope_override` widen + `_record_step_completion` hardcode absorb + helper names (canonical_store.query) + session_context={} MVP. |
| iter-3 | TBD | AGREE expected (3 blocker concrete fix'ler + warnings netleşti) |

### Plan revision history

| Ver | Change |
|---|---|
| v1 | 4 gap + 5 Q for Codex; InvocationResult.output_ref varsayımı + context_spec icat + relative path |
| v2 | iter-1 absorb: output_ref kaynağı Executor write_artifact (InvocationResult dokunulmaz), context_compile step handler scope, absolute path, compile_context() reuse, build_driver Executor-only daraltıldı |
| **v3** | iter-2 absorb: resolver artifact JSON read (step_record schema değişmez), `Executor.run_step(input_envelope_override=None)` additive widen, driver `_build_adapter_envelope_with_context` yeni method, `task_prompt` = `record.intent.payload` pin, `_record_step_completion` stub hardcode absorb + `test_context_compile_stub_emits_stub_marker` test kontrat güncellenir, helper names `canonical_store.query/load_store`, workspace_facts direct JSON read, `session_context={}` MVP (workflow-run schema genişletme gerekmez). |

**Status**: Plan v3 hazır. Codex thread `019d9fc3` iter-3 submit için hazır. 3 blocker concrete fix'ler (artifact read, envelope override, stub absorb); 3 warning netleşti. AGREE beklenir.
