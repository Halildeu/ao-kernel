# PR-C1a Implementation Plan — Adapter Artifact Surface + Context Compile Materialisation

**Scope**: FAZ-C critical-path seri başı. Adapter-path output_ref garantisi + context_compile gerçek dosya üretimi + `build_driver(policy_loader=...)` forward + `input_envelope.context_pack_ref` resolve. Downstream PR'lar (C1b/C2/C3/C6) bu altyapıya bağımlı.

**Base**: `main 5fb7f31` (PR #108 tooling merged). **Branch**: `feat/pr-c1a-adapter-surface`.

**Status**: Pre-Codex iter-1 submit. FAZ-C master plan v5 `cce30c1` C1a scope'u bu PR'a decouple ediliyor (Codex iter-6 notes: "C1a izole PR başlatılması makul").

---

## 1. Problem

FAZ-C master plan iter-1 Codex fact-check ile tespit edilen 4 runtime gap:

| Kod yüzey | Bugünkü hâl | Gap |
|---|---|---|
| `tests/_driver_helpers.build_driver(root: Path)` | Sadece `root` alır; Executor default bundled policy ile kurulur (`_driver_helpers.py:100-119`). | Benchmark'lar ve FAZ-C testleri policy override gerektirir; `Executor(policy_loader=...)` kwarg zaten var ama driver helper forward etmez. |
| `Executor.ExecutionResult` dataclass | `{new_state, step_state, invocation_result, evidence_event_ids, budget_after}` (`executor.py:68-74`). `output_ref` field YOK. | `multi_step_driver._update_step_record_with_output_ref` `getattr(exec_result, "output_ref", None)` ile okuyor (`multi_step_driver.py:1321-1323`) — driver-managed path'te dolu, adapter-path'te garanti değil. |
| `_context_compile` stub (`multi_step_driver.py`) | Placeholder; `.ao/runs/{run_id}/context.md` üretmez. | `claude-code-cli` / `gh-cli-pr` manifest `context_pack_ref` literal placeholder olarak kalır → adapter envelope input yanlış. |
| `input_envelope` builder | `{context_pack_ref}` placeholder string'i literal geçer (resolve yok). | `context_compile` materialisation sonrası dahi envelope'a relative path geçmez. |

**Sonuç**: Adapter'lar context-driven full-flow'da kırılır (B6 review_ai_flow testinde workaround shim ile geçiyor; real path gap'i C1b full bundled bugfix'te ortaya çıkar).

---

## 2. Scope (atomic deliverable)

### 2.1 `_driver_helpers.build_driver` widen

**Before**:
```python
def build_driver(root: Path) -> MultiStepDriver:
    wreg = WorkflowRegistry()
    wreg.load_workspace(root)
    areg = AdapterRegistry()
    areg.load_workspace(root)
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
    wreg = WorkflowRegistry()
    wreg.load_workspace(root)
    areg = AdapterRegistry()
    areg.load_workspace(root)
    executor = Executor(
        workspace_root=root,
        workflow_registry=wreg,
        adapter_registry=areg,
        policy_loader=policy_loader,  # forward (None → Executor defaults to bundled)
    )
    return MultiStepDriver(...)
```

Callers:
- Mevcut: `tests/benchmarks/conftest.py`, `tests/test_multi_step_driver.py` → tamamen dokunulmaz (kwarg default None, behavior korunur).
- Yeni: `tests/benchmarks/fixtures.py::bench_policy_override()` helper + bench-scope workspace policy override testlerinde kullanılır (C1b + C2 için hazırlık).

### 2.2 `ExecutionResult.output_ref` field

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

**After** (additive Optional field):
```python
@dataclass(frozen=True)
class ExecutionResult:
    new_state: WorkflowState
    step_state: str
    invocation_result: InvocationResult | None
    evidence_event_ids: tuple[str, ...]
    budget_after: Mapping[str, Any]
    output_ref: str | None = None  # run-relative path; driver-managed OR adapter path populated
```

**Executor.run_step adapter path populate**:
Mevcut adapter path'te (`driver_managed=False`) `invocation_result.output_ref` InvocationResult'tan çıkar; yeni kod ExecutionResult.output_ref'e yansıtır. `write_artifact` çağrısı zaten driver-managed path'te var (line 601, 696, 800); adapter-path için aynı pattern:
```python
# executor.py run_step adapter branch
if invocation_result is not None and invocation_result.output_ref:
    exec_output_ref = invocation_result.output_ref  # envelope'tan gelen ref
else:
    exec_output_ref = None
return ExecutionResult(..., output_ref=exec_output_ref)
```

Driver-managed path mevcut davranış korunur (B6 v4 `capability_output_refs` + `output_ref` plumbing değişmez).

### 2.3 `_context_compile` materialisation

**Before** (varsayım — stub/placeholder):
```python
def _context_compile(run_id, context_spec) -> str:
    return "context_placeholder"  # Hypothetical stub
```

**After** (gerçek dosya yazımı, atomic):
```python
def _context_compile(
    workspace_root: Path,
    run_id: str,
    context_spec: Mapping[str, Any],
) -> str:
    """Compile run context to .ao/runs/{run_id}/context.md.
    
    Returns run-relative path (e.g. '.ao/runs/abc123/context.md').
    Content shape: markdown with sections from context_spec (role,
    constraints, references). Atomic write via tmp + rename.
    """
    content = _render_context_markdown(context_spec)
    path = workspace_root / ".ao" / "runs" / run_id / "context.md"
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    write_text_atomic(path, content)  # mevcut shared helper
    return str(path.relative_to(workspace_root))
```

Minimal context_spec shape (v1):
- `role: str` — system prompt benzeri
- `constraints: list[str]` — YAPMAMASI gereken
- `references: list[str]` — context materyali

Markdown template (v1):
```markdown
# Run Context

## Role
{role}

## Constraints
{constraints_bulleted}

## References
{references_bulleted}
```

### 2.4 `input_envelope.context_pack_ref` placeholder resolve

**Before**: `input_envelope` builder `{context_pack_ref}` placeholder'ı literal olarak geçer (test: `tests/test_adapter_envelope_compile.py` placeholder literal beklenir).

**After**: `Executor.run_step` input_envelope builder içinde:
```python
if step_def.context_spec is not None:
    context_ref = _context_compile(
        self._workspace_root, run_id, step_def.context_spec
    )
    input_envelope["context_pack_ref"] = context_ref  # run-relative
else:
    # step'te context_spec yoksa placeholder korunur (backwards-compat)
    pass
```

Placeholder interpolation pattern workflow step definition'daki `input_envelope_template` içinde mevcutsa resolve edilir; yoksa verbatim korunur.

---

## 3. Test Plan

### 3.1 Yeni testler

- `tests/test_driver_helpers_policy_loader.py` — `build_driver(root, policy_loader=override)` Executor'a forward eder; default call backwards-compat.
- `tests/test_executor_adapter_output_ref.py` — Adapter path mock envelope → InvocationResult.output_ref → ExecutionResult.output_ref populate.
- `tests/test_context_compile_materialisation.py` — `_context_compile(root, run_id, spec)` `.ao/runs/{run_id}/context.md` yazar; content role/constraints/references section'ları içerir; atomic write (tmp file kalmaz).
- `tests/test_input_envelope_context_pack_ref.py` — step context_spec varsa `context_pack_ref` = relative path; yoksa placeholder korunur.

### 3.2 Regression gate

- `pytest tests/ -x` tüm mevcut 2142 test green kalmalı.
- Özellikle `tests/benchmarks/test_governed_review.py` (B6/B7) — adapter-path output_ref yeni populate davranışıyla `capability_output_refs` plumbing değişmez.

### 3.3 Coverage

- `ao_kernel.executor.executor` coverage %70+ korunur (ExecutionResult delta).
- `ao_kernel.executor.multi_step_driver` `_context_compile` + `input_envelope` resolver için yeni line coverage.

---

## 4. Out of Scope

- **C1b** (full bundled `bug_fix_flow` E2E) — ayrı PR, C1a merge'den sonra.
- **C2** (real adapter full mode + parent_env union) — C1a merge sonrası paralel.
- **C3** (cost_usd reconcile + `post_adapter_reconcile` middleware) — C1a merge sonrası paralel.
- **C6** (dry_run_step) — C1a merge sonrası paralel.
- Kontrat genişletme, yeni schema, yeni adapter manifest alanları — hiçbiri.

---

## 5. Risk Register

| Risk | L | I | Mitigation |
|---|---|---|---|
| R1 Executor adapter path output_ref adapter envelope schema'sına uygun değil | L | H | Adapter envelope `output_ref` field'ı `agent-adapter-contract.schema.v1.json`'da opsiyonel; mevcut adapter'lar boş bırakıyor → backwards-compat. |
| R2 `_context_compile` atomic write benchmark concurrency'de ortak dir çakışması | L | M | Per-run directory (`.ao/runs/{run_id}/`) — run_id UUID; çakışma teorik yok. |
| R3 B6 `capability_output_refs` plumbing C1a ExecutionResult değişikliği ile kırılır | M | H | B6 pattern `getattr(exec_result, "output_ref", None)` ile oku — yeni field eklemek pattern'i kırmaz. `tests/benchmarks/test_governed_review.py` green kalır. |
| R4 `input_envelope` placeholder resolve mevcut testleri kırar | M | M | Step `context_spec` yoksa placeholder korunur; backwards-compat test eklenir. |

---

## 6. Codex iter-1 için Açık Sorular

**Q1**: `ExecutionResult.output_ref: str | None = None` additive field — frozen dataclass backwards-compat için kwargs ile instantiate edilmeli mi? Mevcut callers positional arg kullanıyorsa dataclass ordering ile çelişir mi?

**Q2**: `_context_compile` markdown template v1 shape (role/constraints/references) `claude-code-cli` + `gh-cli-pr` manifest'lerinin gerçekten beklediği context shape ile uyumlu mu? Bu manifest'ler JSON değil markdown consumes ediyor mu?

**Q3**: `input_envelope.context_pack_ref` placeholder interpolation — mevcut workflow step `input_envelope_template` field'ında `{context_pack_ref}` string placeholder Python f-string formatında mı, yoksa özel interpolation syntax mı? (Mevcut implementasyonu fact-check.)

**Q4**: `write_artifact` vs `write_text_atomic` — C1a context.md yazımı için hangi helper doğru? `write_artifact` SHA256 + JSONL manifest entry üretir; context.md markdown düz dosya. `write_text_atomic` shared helper varsa o daha uygun.

**Q5**: Adapter envelope → `InvocationResult.output_ref` dönüşümü `_invocation_from_envelope` içinde mi, yoksa Executor adapter branch'inde mi? Mevcut `InvocationResult` dataclass'ına `output_ref` field'ı ekliyor muyum?

---

## 7. Implementation Order

1. **`ExecutionResult.output_ref` + `InvocationResult.output_ref`** — dataclass field ekle + adapter envelope extraction.
2. **`build_driver(policy_loader=)` forward** — tek satır değişikliği.
3. **`_context_compile` materialisation** — markdown template + atomic write.
4. **`input_envelope` placeholder resolve** — step context_spec varsa interpolate.
5. **4 yeni test + regression** — pytest green.
6. **Commit + Codex post-impl review + PR #109 open**.

---

## 8. LOC Estimate

~450 satır (dataclass delta + context_compile fn + envelope resolve + 4 test).

---

## 9. Audit Trail

| Iter | Date | Verdict |
|---|---|---|
| v1 (Claude draft) | 2026-04-18 | Pre-Codex iter-1 submit |
| iter-1 | TBD | Adversarial plan-review beklenir |

**Codex thread**: Yeni thread (C1a-specific). FAZ-C master plan thread `019d9f75` bu PR için kapandı (Codex notes'ta C1a bağımsız onaylandı).
