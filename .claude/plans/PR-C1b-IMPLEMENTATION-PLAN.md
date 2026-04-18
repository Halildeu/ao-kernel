# PR-C1b Implementation Plan v1 — Full Bundled bug_fix_flow E2E Benchmark

**Scope**: FAZ-C runtime closure 2. track. C1a'nın adapter artifact surface + context_compile materialisation + envelope plumbing altyapısı üzerine bug_fix_flow 7-step full bundled E2E benchmark. Patch plumbing fallback (`_load_pending_patch_content`) artifact-based. `gh-cli-pr` manifest tutarsızlık fix (C1a iter-1 W1 follow-up).

**Base**: `main cba3e2e` (PR #109 C1a merged). **Branch**: `feat/pr-c1b-bug-fix-flow-e2e`.

**Status**: Pre-Codex iter-1 submit. Master plan v5 §C1b scope'u bu PR'a decouple ediliyor.

---

## 1. Problem

C1a adapter-path output_ref garantisi + context_compile materialisation + `context_pack_ref` plumbing kurdu. Ama:

1. **bug_fix_flow.v1.json** (`ao_kernel/defaults/workflows/bug_fix_flow.v1.json`) 7-step full demo workflow, ama benchmark test yok → full-flow regression gate eksik.
2. **`_load_pending_patch_content`** (`multi_step_driver.py:1749-1763`) yalnız `record.intent.payload.patches[step_name]` okuyor — fixture-only MVP. Adapter-path (codex-stub'ın diff'i output_ref'te) fallback yok. Dolayısıyla gerçek full-flow'da `apply_patch` step'i boş patch alır.
3. **`gh-cli-pr` manifest tutarsızlığı** (`gh-cli-pr.manifest.v1.json:9,15`): `args` `{context_pack_ref}` kullanıyor (`--body-file`) ama `input_envelope` shape sadece `task_prompt` + `run_id` deklare ediyor. Codex iter-1 W1: "C1a envelope resolver `context_pack_ref` plumbing yaptı ama `gh-cli-pr` için body içeriği ≠ context.md — semantic mismatch". Resolver mantığı manifest input_envelope shape'iyle hizasız.

---

## 2. Scope (atomic deliverable)

### 2.1 `_load_pending_patch_content` artifact fallback

**Before** (`multi_step_driver.py:1749-1763`):
```python
def _load_pending_patch_content(
    record: Mapping[str, Any], step_name: str,
) -> str:
    """MVP: test fixtures supply patch via record.intent.payload.patches[step_name]."""
    intent_payload = record.get("intent", {}).get("payload", {})
    if isinstance(intent_payload, Mapping):
        patches = intent_payload.get("patches", {}) or {}
        content = patches.get(step_name) if isinstance(patches, Mapping) else None
        if isinstance(content, str):
            return content
    return ""
```

**After** (v1 — fallback to prior adapter step's artifact):
```python
def _load_pending_patch_content(
    record: Mapping[str, Any],
    step_name: str,
    *,
    workspace_root: Path | None = None,
) -> str:
    """Load pending patch content from (in order):
    1. record.intent.payload.patches[step_name]  — fixture/override.
    2. Prior adapter step's artifact JSON → extracted diff.
    
    PR-C1b: step 2 closes adapter-path for full bundled bug_fix_flow.
    """
    # 1. Fixture/override path (existing behavior).
    intent_payload = record.get("intent", {}).get("payload", {})
    if isinstance(intent_payload, Mapping):
        patches = intent_payload.get("patches", {}) or {}
        content = patches.get(step_name) if isinstance(patches, Mapping) else None
        if isinstance(content, str):
            return content
    
    # 2. Artifact fallback (PR-C1b): scan steps for last completed
    #    adapter step with output_ref → parse artifact JSON → extract diff.
    if workspace_root is None:
        return ""
    run_id = record.get("run_id")
    if not run_id:
        return ""
    for prior in reversed(record.get("steps", [])):
        if (
            prior.get("actor") == "adapter"
            and prior.get("state") == "completed"
            and prior.get("output_ref")
        ):
            run_dir = workspace_root / ".ao" / "evidence" / "workflows" / run_id
            artifact_path = run_dir / prior["output_ref"]
            if artifact_path.is_file():
                try:
                    artifact = json.loads(artifact_path.read_text())
                except (OSError, json.JSONDecodeError):
                    return ""
                # Adapter output canonical shape: extracted_outputs.diff
                # (capability_output_refs path) or top-level diff field.
                extracted = artifact.get("extracted_outputs", {}) or {}
                diff = extracted.get("diff") or artifact.get("diff", "")
                if isinstance(diff, str):
                    return diff
            return ""
    return ""
```

Caller site `multi_step_driver.py:738` güncelleme: `_load_pending_patch_content(record, step_def.step_name, workspace_root=self._workspace_root)`.

### 2.2 `gh-cli-pr` manifest fix

Codex iter-1 W1 flag: manifest `args` `{context_pack_ref}` kullanıyor ama `input_envelope` declarative shape'te yok. İki opsiyon:

**Option A — Declarative input_envelope widen** (minimal):
```json
"input_envelope": {
    "task_prompt": "<PR title>",
    "run_id": "<uuid>",
    "context_pack_ref": "<path to PR body markdown>"
}
```
Envelope resolver zaten C1a'dan beri `context_pack_ref` plumbing yapıyor; sadece manifest'in shape deklarasyonu eksikti.

**Option B — Different placeholder** (`patch_path` veya `pr_body_path`):
```json
"args": ["pr", "create", "--title", "{task_prompt}", "--body-file", "{pr_body_path}"],
"input_envelope": {"task_prompt": "<PR title>", "run_id": "<uuid>", "pr_body_path": "<path>"}
```
Ayrı placeholder + resolver genişletme gerekir.

**v1 karar**: **Option A** (minimal). C1a resolver zaten `context_pack_ref`'i plumb ediyor; gh-cli-pr manifest declaration'ı fix etmek yeterli. PR body olarak context.md mantıklı (run context = PR summary candidate). Eğer gerçek prod'da farklı body gerekiyorsa, bu workflow-level concern (bug_fix_flow'a extra `prepare_pr_body` step eklenebilir — C1b scope dışı, future PR).

### 2.3 Bundled `bug_fix_flow` E2E benchmark test

**Dosya**: `tests/benchmarks/test_governed_bugfix.py` (B7 scope'unda benchmark skeleton vardı; C1b full bundled TestClass ekler).

**Scope**:
- Fixture: `mini_repo` with real `test_smoke.py` (single failing test → codex-stub diff patches it → re-run passes).
- Adapter mock: codex-stub canned envelope with `extracted_outputs.diff` (a canonical patch that fixes the failing test).
- Adapter mock: gh-cli-pr canned envelope with `status=ok` + mock PR URL.
- Drive 7-step flow: compile_context → invoke_coding_agent → preview_diff → ci_gate → await_approval (resume via token) → apply_patch → open_pr.
- Assertions:
  - All steps completed (state per step).
  - Artifact chain: compile_context.output_ref → context.md (C1a contract) → codex-stub invocation → diff artifact → apply_patch reads via `_load_pending_patch_content` fallback → patch applied to worktree.
  - `open_pr` adapter_returned event with `status=ok`.
  - Final workflow_completed event.
  - `capability_output_refs` on relevant steps (PR-B6 contract preserved).

**Bench workspace policy override**: `build_driver(tmp_path, policy_loader=bench_policy_override)` (C1a forward). Dummy git + pytest allowlist + gh allowlist (CI-safe, subprocess actually runs pytest).

### 2.4 Minor: bug_fix_flow workflow fixture exposure

`bug_fix_flow.v1.json` bundled default'ta (`ao_kernel/defaults/workflows/`), `tests/fixtures/workflows/` altında değil. Benchmark test için `copy_workflow_fixture` varsayımı kırılır. İki opsiyon:
- Benchmark test bundled default'u doğrudan load (`_load_ao_workflows(workspace_root)` scan `ao_kernel/defaults/workflows/` fallback).
- Benchmark test bundled default'u `tmp_path/.ao/workflows/`'a kopyalar.

**v1 karar**: İkinci (explicit copy) — benchmark helper fonksiyonuna `install_bundled_workflow("bug_fix_flow")` ekle.

---

## 3. Test Plan

### 3.1 Yeni testler

- `tests/benchmarks/test_governed_bugfix.py::TestFullBundledBugFixFlow`:
  - `test_happy_path_bug_fix_flow_completes` — 7 step green + patch applied + PR opened.
  - `test_patch_artifact_fallback` — patches={} olduğunda prior adapter output_ref'ten diff okunur.
  - `test_ci_gate_failure_blocks_flow` — CI fail → flow `failed`, apply_patch skip.

### 3.2 Updated tests

- Mevcut `tests/benchmarks/test_governed_bugfix.py` (varsa) — C1b ekleme.

### 3.3 Regression gate

- `pytest tests/ -x` — 2151 + 3 new = 2154 green.
- Özellikle `test_patch_errors.py` ve `test_multi_step_driver.py` — `_load_pending_patch_content` yeni fallback pattern backwards-compat.

---

## 4. Out of Scope

- **C2** (parent_env union) — paralel PR.
- **C3** (post_adapter_reconcile) — paralel PR.
- **C6** (dry_run_step) — paralel PR.
- Real `gh pr create` subprocess invocation — mock kalır (CI no-secrets constraint).
- Real `claude-code-cli` subprocess — mock (codex-stub kullanılır).
- Schema changes / new adapter manifest fields — hiçbiri.

---

## 5. Risk Register

| Risk | L | I | Mitigation |
|---|---|---|---|
| R1 `_load_pending_patch_content` yeni `workspace_root` kwarg caller'ları kırar | L | M | Additive optional kwarg, default None → fixture-only path (existing behavior) |
| R2 Artifact JSON'da `extracted_outputs.diff` vs top-level `diff` yerleşimi belirsiz | M | M | İki field'ı da dene (fallback chain); Codex iter-1'de pin'le |
| R3 bug_fix_flow bundled default'u workflow registry scan'e girmiyor | M | M | Explicit `install_bundled_workflow` helper + tmp_path kopyalama |
| R4 Bench mini_repo real pytest subprocess CI'da flaky | M | M | Minimal smoke (single file, single assert); isolated tmp_path worktree |
| R5 gh-cli-pr manifest A opsiyonu body=context.md semantik olarak doğru mu | L | L | Documented: C1b MVP; gerçek prod farklı body için ayrı PR |

---

## 6. Codex iter-1 için Açık Sorular

**Q1 — Artifact JSON diff yerleşimi**: `codex-stub` adapter'ın output canonical JSON'unda diff nerede — `extracted_outputs.diff`, top-level `diff`, yoksa başka bir field mi? `fixtures/codex_stub.py` kaynak doğrulaması gerek.

**Q2 — `gh-cli-pr` Option A body semantiği**: context.md run context (role/constraints/references) PR body olarak doğru mu, yoksa bug_fix_flow için farklı bir body template mı gerek? (ör. diff + summary)

**Q3 — Bench mini_repo real pytest**: `test_smoke.py` tek assert + codex-stub diff ile patch → test pass. Patch content deterministic mi yoksa fixture-specific mi? Subprocess timeout concern?

**Q4 — `copy_workflow_fixture` vs `install_bundled_workflow`**: bundled workflow'u bench'te kopyalamak için yeni helper vs mevcut `copy_workflow_fixture` extend — hangisi convention'a uyar?

**Q5 — `workspace_root` kwarg additive**: `_load_pending_patch_content(record, step_name, *, workspace_root=None)` default None → fallback skip. Mevcut test callers dokunulmaz mı? (Fact-check: grep `_load_pending_patch_content` callers.)

---

## 7. Implementation Order

1. `gh-cli-pr` manifest input_envelope widen (1-line JSON).
2. `_load_pending_patch_content` artifact fallback (+ `workspace_root` kwarg + caller update).
3. Bench helper `install_bundled_workflow("bug_fix_flow")`.
4. `tests/benchmarks/test_governed_bugfix.py::TestFullBundledBugFixFlow` (3 test).
5. Regression `pytest tests/ -x`.
6. Commit + post-impl Codex review + PR #110 + admin merge.

---

## 8. LOC Estimate

~600 satır (plumbing fallback +40, manifest +2, bench helper +30, benchmark class +400, regression ~130).

---

## 9. Audit Trail

| Iter | Date | Verdict |
|---|---|---|
| v1 (Claude draft) | 2026-04-18 | Pre-Codex iter-1 submit |
| iter-1 | TBD | Adversarial plan-review beklenir |

**Codex thread**: Yeni thread (C1b-specific).
