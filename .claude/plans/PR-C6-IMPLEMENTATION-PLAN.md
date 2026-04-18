# PR-C6 Implementation Plan v3 — Explicit Policy-Denied Branch + CLI Registry API Fix

**v3 absorb (iter-2 PARTIAL — 1 blocker + 2 warning)**:
1. **Policy-denied branch explicit**: Dry-run adapter dispatch içinde `PolicyViolationError` caught + `policy_checked` + `policy_denied` + `step_failed` events recorder'a yazılır; `DryRunResult.policy_violations` dolar; exception dışarı çıkmaz.
2. **CLI registry API kwargs**: `workflow_registry.get(workflow_id, version=workflow_version)` — keyword-only. Registry `load_bundled()` + `load_workspace(project_root)` ile populate.
3. **Adapter log absent**: Test pin — `adapter-<id>.jsonl` dry-run sonrası YOK (mock boundary tam kapandığı kanıtı).

---

# (v2 retained for history)

## PR-C6 Implementation Plan v2 — Executor.dry_run_step (Refactored Shared Pre-flight)

**Scope**: FAZ-C runtime closure. `Executor.dry_run_step(run_id, step_def, ...) -> DryRunResult` — **shared pre-flight extracted**, separate dry-run tail (no CAS, no write_artifact, no update_run). Mock boundary: `emit_event` + worktree + `invoke_cli`/`invoke_http` via executor alias-patch. CLI `ao-kernel executor dry-run <run_id> <step_name>`.

**Base**: `main 11c54cf` (PR #113 C5 merged). **Branch**: `feat/pr-c6-dry-run-step`.

**Status**: iter-1 PARTIAL absorb → iter-2 submit. Codex thread `019da099-e692-7fa1-b2f4-e429a6beb0de`.

---

## v2 absorb summary (Codex iter-1 PARTIAL — 3 blocker + 4 warning)

| # | iter-1 bulgu | v2 fix |
|---|---|---|
| **B1** (`write_artifact` kaçak) | `run_step` adapter path `write_artifact` (`executor.py:422`) çağırır — `invoke_cli` mock'u onu kapsamıyor. Black-box reuse artifact yazar. | v2: `run_step` reuse DEĞİL. Shared pre-flight fn (pre-flight + step resolution + policy check) + ayrı `_dry_run_tail` (no write_artifact, no update_run, no artifact write). |
| **B2** (update_run + placeholder coupling) | `run_step` 3 update_run call-site'ı (success `:512`, placeholder `:583`, fail `_fail_run:647`). `driver_managed=True` sadece success CAS skip eder + duplicate-completed guard kaybolur. | v2: Dry-run kendi tail'i; `update_run` hiç çağırmaz. Duplicate-completed guard preflight'ta reuse edilir (shared fn). |
| **B3** (CLI workflow_id mismatch) | Method `run_id` + `step_def` alır; CLI `workflow_id` + `step_name` alır. İkisi farklı context. | v2: CLI `run_id` bazlı — `ao-kernel executor dry-run <run_id> <step_name>`. `workflow_id` run_id'den türetilir (`load_run(run_id).workflow_id`). |

### v2 absorb warnings

- **W1** (alias patch site) → v2 §2.2: 4 mock nokta executor module alias: `ao_kernel.executor.executor.emit_event`, `invoke_cli`, `invoke_http`, `create_worktree`, `cleanup_worktree`.
- **W2** (`emit_event` stub shape) → v2 §2.2: Stub `EvidenceEvent`-benzeri obje döner (`.event_id`, `.ts`, `.seq` attrs). Dummy UUID + iso timestamp.
- **W3** (`invoke_cli` canned shape) → v2 §2.2: `(InvocationResult, Budget)` tuple. `InvocationResult` 10 required field (`status, diff, evidence_events, commands_executed, error, finish_reason, interrupt_token, cost_actual, stdout_path, stderr_path`) + optional `extracted_outputs={}`. Budget real obje — `budget_from_dict(record["budget"])`.
- **W4** (read-only invariant weak) → v2 §3.1 test pinleri güçlendirildi: full record dict byte-for-byte unchanged + `revision` unchanged + `steps` length unchanged + `error` unchanged + `events.jsonl` absent + `artifacts/` dir empty.

---

## 1. Problem

(Aynı, v1'den.)

---

## 2. Scope v2 (atomic deliverable — refactored)

### 2.1 `DryRunResult` dataclass

`ao_kernel/executor/dry_run.py` yeni modül — aynı v1 tanımı.

### 2.2 Shared pre-flight + dry-run tail

**`Executor._preflight_and_resolve(run_id, step_def)` yeni private method** (refactor out of `run_step`):
```python
def _preflight_and_resolve(
    self,
    run_id: str,
    step_def: StepDefinition,
    *,
    attempt: int,
    driver_managed: bool,
    fencing_token: int | None,
    fencing_resource_id: str | None,
) -> tuple[Mapping[str, Any], WorkflowDefinition]:
    """Shared pre-flight — called by BOTH run_step and dry_run_step.
    
    Runs (in order):
    1. Fencing entry check (if token supplied).
    2. load_run — fails on missing run_id.
    3. Terminal-state guard.
    4. Resolve pinned definition.
    5. step_def-in-definition guard.
    6. Duplicate-completed guard (skipped in driver_managed=True).
    7. Adapter cross-ref validation for adapter steps.
    
    Returns ``(record, definition)`` — no side-effects beyond
    read-only disk I/O for load_run.
    """
```

`run_step` mevcut pre-flight body'sini `_preflight_and_resolve` çağrısıyla değiştirir (refactor, behavior unchanged).

**`Executor.dry_run_step`** method:
```python
def dry_run_step(
    self,
    run_id: str,
    step_def: StepDefinition,
    *,
    parent_env: Mapping[str, str] | None = None,
    attempt: int = 1,
) -> DryRunResult:
    """Dry-run: shared pre-flight + separate dry-run tail.

    Contract:
    - Run record NOT mutated (no update_run).
    - No evidence file written (emit_event mocked).
    - No worktree built (create_worktree mocked).
    - No adapter subprocess (invoke_cli/http mocked).
    - No artifact file written (write_artifact mocked).
    - Policy violations + predicted events surface in DryRunResult.
    """
    from ao_kernel.executor.dry_run import (
        DryRunResult,
        dry_run_execution_context,
    )

    try:
        record, definition = self._preflight_and_resolve(
            run_id, step_def,
            attempt=attempt,
            driver_managed=False,
            fencing_token=None,
            fencing_resource_id=None,
        )
    except PolicyViolationError as exc:
        return DryRunResult(
            predicted_events=(),
            policy_violations=(str(exc),),
            simulated_budget_after=dict(
                record.get("budget", {}) if "record" in dir() else {}
            ),
            simulated_outputs={},
        )

    with dry_run_execution_context(
        self._workspace_root, run_id,
    ) as recorder:
        # Dry-run dispatch: call actor branch but bypass CAS/artifact.
        # v3 (iter-2 B1 absorb): policy evaluation runs inside adapter
        # dispatch; PolicyViolationError caught here records the full
        # step_started → policy_checked → policy_denied → step_failed
        # event sequence and returns violations in DryRunResult without
        # raising.
        try:
            if step_def.actor == "adapter":
                self._dry_run_adapter_dispatch(
                    run_id=run_id,
                    record=record,
                    step_def=step_def,
                    parent_env=parent_env or {},
                    attempt=attempt,
                    recorder=recorder,
                )
            else:
                self._dry_run_placeholder(
                    run_id=run_id,
                    record=record,
                    step_def=step_def,
                    recorder=recorder,
                )
        except PolicyViolationError as exc:
            # Mock'd emit_event already captured step_started +
            # policy_checked; record policy_denied + step_failed
            # here to match real executor's denial sequence.
            recorder.record_policy_violation(str(exc))
            recorder.predicted_events.append((
                "policy_denied",
                {"step_name": step_def.step_name, "reason": str(exc)},
            ))
            recorder.predicted_events.append((
                "step_failed",
                {"step_name": step_def.step_name, "reason": "policy_violation"},
            ))

    return DryRunResult(
        predicted_events=tuple(recorder.predicted_events),
        policy_violations=tuple(recorder.policy_violations),
        simulated_budget_after=dict(record.get("budget", {})),
        simulated_outputs=dict(recorder.simulated_outputs),
    )
```

**`_dry_run_adapter_dispatch`** + **`_dry_run_placeholder`** — ayrı tail'ler; CAS mutations, write_artifact, update_run hiç çağrılmaz. Sadece mock'd `invoke_cli`, `emit_event`, `create_worktree`, `cleanup_worktree` çağrılır (recorder'a yazılır).

### 2.3 `dry_run_execution_context` — 5 mock nokta (v2: +1 write_artifact)

```python
@contextmanager
def dry_run_execution_context(
    workspace_root: Path,
    run_id: str,
) -> Iterator[_DryRunRecorder]:
    """5-patch boundary. All patches target executor module aliases
    per W1 absorb."""
    from unittest.mock import patch
    
    recorder = _DryRunRecorder()
    
    def _mock_emit(ws, run_id, kind, actor, payload, **kwargs):
        recorder.predicted_events.append((kind, dict(payload)))
        # Return EvidenceEvent-like stub (W2 absorb)
        return _StubEvidenceEvent(
            event_id=f"dry-run-{len(recorder.predicted_events)}",
            ts=datetime.now(timezone.utc).isoformat(),
            seq=len(recorder.predicted_events),
        )
    
    def _mock_invoke_cli(*, manifest, input_envelope, sandbox,
                         worktree, budget, workspace_root, run_id):
        # (InvocationResult, Budget) tuple per W3 absorb
        return (_canned_invocation_result(manifest), budget)
    
    def _mock_invoke_http(*args, **kwargs):
        return _mock_invoke_cli(*args, **kwargs)
    
    def _mock_create_worktree(*args, **kwargs):
        return _DummyWorktree(path=workspace_root / ".dry-run-stub")
    
    def _mock_cleanup_worktree(*args, **kwargs):
        return None
    
    def _mock_write_artifact(*, run_dir, step_id, attempt, payload):
        # B1 absorb: write_artifact patched too — recorder captures
        # would-be path; no disk write.
        stub_ref = f"artifacts/{step_id}-attempt{attempt}.json"
        recorder.simulated_outputs[step_id] = stub_ref
        stub_sha = "dry-run-sha256-stub"
        return (stub_ref, stub_sha)
    
    with patch.multiple(
        "ao_kernel.executor.executor",
        emit_event=_mock_emit,
        invoke_cli=_mock_invoke_cli,
        invoke_http=_mock_invoke_http,
        create_worktree=_mock_create_worktree,
        cleanup_worktree=_mock_cleanup_worktree,
        write_artifact=_mock_write_artifact,
    ):
        yield recorder
```

### 2.4 CLI `ao-kernel executor dry-run <run_id> <step_name>`

**CLI v2**: run_id bazlı (B3 absorb):
```bash
ao-kernel executor dry-run \
    <run_id> \
    <step_name> \
    --attempt 1 \
    --format json
```

Handler (v3 — registry API kwarg fix):
1. Registry populate: `wreg = WorkflowRegistry(); wreg.load_bundled(); wreg.load_workspace(project_root)`.
2. Adapter registry populate similarly.
3. `load_run(project_root, run_id)` → record with `workflow_id` + `workflow_version`.
4. `definition = wreg.get(workflow_id, version=workflow_version)` (**v3 kwarg; registry.py:362 kontratı**).
5. `step_def = next((s for s in definition.steps if s.step_name == step_name), None)` — None → error exit.
6. `Executor(project_root, workflow_registry=wreg, adapter_registry=areg, policy_loader=...).dry_run_step(run_id, step_def, attempt=args.attempt)`.
7. Print `DryRunResult` JSON/text.

---

## 3. Test Plan v2

### 3.1 Yeni test (`tests/test_dry_run_step.py`):

**Context manager unit** (5, W1-W3 absorb):
- `test_emit_event_captured_not_written` — mock emit call + returns EvidenceEvent-like stub + no events.jsonl write.
- `test_invoke_cli_returns_canned_tuple` — canned (InvocationResult, Budget) tuple; all 10 required fields present.
- `test_worktree_mock_returns_stub` — create_worktree returns DummyWorktree; no git subprocess.
- `test_write_artifact_captured_not_written` — write_artifact mock returns stub_ref; artifacts/ dir empty.
- `test_emit_event_stub_has_required_attrs` — event.event_id + event.ts attrs (executor.py:292, 501).

**dry_run_step integration** (6, B2+W4 absorb):
- `test_adapter_step_returns_dry_run_result` — happy path.
- `test_placeholder_step_returns_dry_run_result` — non-adapter actor.
- `test_policy_violation_surfaces` — bad policy → violations tuple non-empty.
- `test_read_only_invariant_full_record_unchanged` — record dict byte-for-byte + revision + steps length + error unchanged.
- `test_no_evidence_file_written` — events.jsonl absent post-dry_run.
- `test_no_artifact_directory_written` — run_dir/artifacts/ absent or empty.
- `test_no_adapter_log_written` (v3 W3 absorb) — `adapter-<id>.jsonl` absent post-dry_run (mock boundary tam kapandı kanıtı).
- `test_policy_denied_records_full_event_sequence` (v3 B1 absorb) — bad policy adapter step → DryRunResult.policy_violations non-empty + predicted_events içinde `step_started` + `policy_checked` + `policy_denied` + `step_failed` 4'lü sıra (exception DIŞARI çıkmaz).

**Shared pre-flight refactor regression** (2):
- `test_run_step_preflight_behavior_unchanged` — existing run_step callers pass existing behavior (load_run + guards).
- `test_duplicate_completed_guard_preserved` — A3 mode duplicate-completed ValueError hâlâ raise.

**CLI** (2):
- `test_cli_dry_run_by_run_id_json` — `ao-kernel executor dry-run <run_id> <step> --format json` subprocess smoke.
- `test_cli_unknown_step_error_exit` — step_name not in workflow → error exit.

---

## 4. Out of Scope

- Multi-step DAG dry-run — v1 tek step.
- Cost estimate computation (C3 merge sonrası integration mümkün).
- `update_run` dry-run mock — hiç çağrılmaz kontrat. Mock yerine code path avoidance.
- C3/C4.1/C8 — paralel.

---

## 5. Risk Register v2

| Risk | L | I | Mitigation |
|---|---|---|---|
| R1 Shared preflight refactor mevcut run_step testlerini kırar | M | H | Regression test: `test_run_step_preflight_behavior_unchanged` pin. 16 mevcut run_step test suite preserve edilir. |
| R2 `update_run` dry-run'da hâlâ çağrılır | L | H | Separate tail; mock'da update_run YOK (unlike emit_event vs). Test: record dict unchanged pin. |
| R3 `_dry_run_adapter_dispatch` gerçek adapter invocation path'inden sapar | M | M | Mock boundary Codex iter-1 aliases. Test: 5 context-level test + integration test policy+event predictions. |
| R4 CLI `load_run(run_id)` fail gracefully (bad run_id) | L | L | Error exit code + stderr msg |

---

## 6. Implementation Order

1. `_preflight_and_resolve` extract (refactor `run_step`).
2. `DryRunResult` + `_DryRunRecorder` + `_StubEvidenceEvent` + `_canned_invocation_result` helpers (`dry_run.py`).
3. `dry_run_execution_context` (5 mock patch.multiple).
4. `Executor.dry_run_step` + `_dry_run_adapter_dispatch` + `_dry_run_placeholder`.
5. CLI `executor dry-run` + handler.
6. 15 test (5 context + 6 integration + 2 refactor regression + 2 CLI).
7. Regression full suite + commit + post-impl review + PR #114.

---

## 7. LOC Estimate v2

~900 satır (refactor +50, dry_run.py +200, executor dry_run_step +80, cli +40, handler +70, 15 test +460).

---

## 8. Audit Trail

| Iter | Date | Verdict |
|---|---|---|
| v1 (Claude draft) | 2026-04-18 | Pre-Codex submit (`4cc4232`) |
| iter-1 (thread `019da099`) | 2026-04-18 | **PARTIAL** — 3 blocker (write_artifact kaçak, update_run coupling, CLI workflow_id mismatch) + 4 warning |
| **v2 (iter-1 absorb)** | 2026-04-18 | Pre-iter-2. Shared pre-flight refactor + separate dry-run tail + 5 mock nokta (write_artifact added) + CLI run_id-based + stub EvidenceEvent + (InvocationResult, Budget) tuple. |
| iter-2 | 2026-04-18 | **PARTIAL** — 1 blocker (policy-denied branch explicit gerekli) + 2 warning (CLI registry kwarg + adapter log absent test) |
| **v3 (iter-2 absorb)** | 2026-04-18 | Pre-iter-3. Policy-denied try/except explicit recorder events + CLI `wreg.get(id, version=...)` + adapter log absent pin. |
| iter-3 | TBD | AGREE expected |
