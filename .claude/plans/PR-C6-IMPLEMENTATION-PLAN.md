# PR-C6 Implementation Plan v1 — Executor.dry_run_step (Runtime Closure)

**Scope**: FAZ-C runtime closure. `Executor.dry_run_step(step_name, ...) -> DryRunResult` — ayrı `dry_run_execution_context` ile mock sınır: `emit_event` + worktree (`create_worktree`/`cleanup_worktree`) + `invoke_cli`/`invoke_http`. `DryRunResult{predicted_events, policy_violations, simulated_budget_after, simulated_outputs}`. CLI `ao-kernel executor dry-run <workflow_id> <step_name>`.

**Base**: `main 11c54cf` (PR #113 C5 merged). **Branch**: `feat/pr-c6-dry-run-step`.

**Status**: Pre-Codex iter-1 submit.

---

## 1. Problem

Operator bir step'i **gerçekten çalıştırmadan** policy violation / budget impact / expected events preview etmek istiyor. Mevcut `Executor.run_step` side-effect-heavy (evidence emit + worktree build + subprocess invoke). Policy-sim workflow-level benzer bir rol oynuyor ama step-level granularity + mock'lanmış execution surface yok.

**Master plan v5 §C6 + Codex Q4 absorb**: Policy-sim guard **EXTEND DEĞİL** — ayrı `dry_run_execution_context` gerekli. Policy-sim scenario-oriented; dry-run step-oriented. Boundary: `emit_event`, `create_worktree`/`cleanup_worktree`, `invoke_cli`/`invoke_http` mock.

---

## 2. Scope (atomic deliverable)

### 2.1 `DryRunResult` dataclass

**Yeni** (`ao_kernel/executor/dry_run.py` yeni modül):
```python
@dataclass(frozen=True)
class DryRunResult:
    """PR-C6: step-level dry-run result. Capture predicted effects
    without executing real side-effects.

    - predicted_events: tuple of (kind, payload_summary) — evidence
      events that WOULD have been emitted.
    - policy_violations: tuple of policy violation strings detected
      during pre-flight (worktree build + command validate).
    - simulated_budget_after: mock budget state if policy check passed
      (actual budget mutation NOT persisted).
    - simulated_outputs: per-capability artifact paths that WOULD
      have been written (NOT actually materialized).
    """
    predicted_events: tuple[tuple[str, Mapping[str, Any]], ...]
    policy_violations: tuple[str, ...]
    simulated_budget_after: Mapping[str, Any]
    simulated_outputs: Mapping[str, str]
```

### 2.2 `dry_run_execution_context` — mock boundary

**Yeni** (`ao_kernel/executor/dry_run.py`):
```python
@contextmanager
def dry_run_execution_context(
    workspace_root: Path,
    run_id: str,
) -> Iterator[_DryRunRecorder]:
    """Patch side-effect-producing callables to capture-and-skip
    semantics for the duration of the block. Four callables patched:

    1. ``ao_kernel.executor.executor.emit_event`` — record call args
       instead of writing evidence.
    2. ``ao_kernel.executor.worktree_builder.create_worktree`` +
       ``cleanup_worktree`` — return a tmp-dir handle without
       invoking git.
    3. ``ao_kernel.executor.executor.invoke_cli`` + ``invoke_http``
       — return a canned ``InvocationResult(status="ok", extracted_outputs={})``
       simulating a successful adapter call.

    The recorder captures predicted events + simulated_outputs so the
    caller can build a ``DryRunResult``.
    """
    # Implementation: unittest.mock.patch.multiple in stacked
    # context managers; recorder is a small dataclass with append
    # methods.
```

`_DryRunRecorder` accumulates: `predicted_events: list[(kind, payload)]`, `simulated_outputs: dict[capability, path]`.

### 2.3 `Executor.dry_run_step` public method

**Executor** (`ao_kernel/executor/executor.py:83+`):
```python
def dry_run_step(
    self,
    run_id: str,
    step_def: StepDefinition,
    *,
    parent_env: Mapping[str, str] | None = None,
    attempt: int = 1,
) -> DryRunResult:
    """Dry-run a single step: execute the pre-flight + policy checks
    + record predicted events, but MOCK side-effect boundary
    (no evidence write, no worktree build, no subprocess invoke).

    Returns ``DryRunResult`` with predicted events + policy violations
    + simulated budget + simulated outputs. Run state NOT mutated.
    Policy check still runs full — so policy violations surface the
    same way they would in a real run.
    """
    from ao_kernel.executor.dry_run import (
        DryRunResult,
        dry_run_execution_context,
    )
    
    # Read run record for budget + policy derivation (read-only).
    record, _ = load_run(self._workspace_root, run_id)
    
    with dry_run_execution_context(
        self._workspace_root, run_id,
    ) as recorder:
        # Pre-flight guards run real (policy violations must be
        # observable). Dispatch through run_step but the mock
        # boundary captures all side-effects.
        try:
            _ = self.run_step(
                run_id,
                step_def,
                parent_env=parent_env,
                attempt=attempt,
                driver_managed=False,  # single-step dry-run
            )
        except PolicyViolationError as exc:
            recorder.record_policy_violation(str(exc))
    
    return DryRunResult(
        predicted_events=tuple(recorder.predicted_events),
        policy_violations=tuple(recorder.policy_violations),
        simulated_budget_after=recorder.simulated_budget_after,
        simulated_outputs=dict(recorder.simulated_outputs),
    )
```

Pre-flight guards (load_run + workflow_registry.get + step_def validation + policy_check) run REAL — operator sees actual policy violations. Only side-effect-producing boundary mocked.

### 2.4 CLI `ao-kernel executor dry-run <workflow_id> <step_name>`

**`cli.py`**:
```bash
ao-kernel executor dry-run bug_fix_flow invoke_coding_agent \
    --run-id abc-123 \
    --attempt 1 \
    --format json
```

- `workflow_id` + `step_name` positional.
- `--run-id` opsiyonel (default: create temporary UUID).
- `--attempt` default 1.
- `--format` json|text.

CLI handler builds Executor + loads `step_def` from workflow registry + calls `dry_run_step` + prints DryRunResult as JSON/text.

---

## 3. Test Plan

### 3.1 Yeni test (`tests/test_dry_run_step.py`):

**Context manager unit** (3):
- `test_emit_event_captured_not_written` — mock emit_event call + verify no evidence file written.
- `test_worktree_not_built` — mock create_worktree return + no git subprocess executed.
- `test_invoke_cli_returns_canned` — mock invoke_cli → InvocationResult(status="ok"), no subprocess.

**dry_run_step integration** (4):
- `test_returns_dry_run_result` — happy path: adapter step → DryRunResult with predicted events.
- `test_policy_violation_surfaces` — step with bad command_allowlist → policy_violations non-empty.
- `test_budget_not_mutated` — run record's budget unchanged after dry_run_step.
- `test_no_evidence_file_written` — events.jsonl not created.

**CLI** (2):
- `test_cli_dry_run_json_format` — smoke test: subprocess parse JSON output.
- `test_cli_unknown_step_error` — step_def lookup fail → error exit.

---

## 4. Out of Scope

- **Multi-step DAG dry-run** (sequential step chain) — bu PR tek-step. Multi-step dry-run future PR.
- **Semantic semi-execution** (ör. gerçek tokenize edilmiş LLM call ama response mock) — out of scope.
- **Budget projection accuracy**: simulated_budget_after = record.budget copy (no cost estimate computation). C3 merge sonrası gerçek cost estimate entegrasyonu mümkün.
- C3 (post_adapter_reconcile) — paralel PR.

---

## 5. Risk Register

| Risk | L | I | Mitigation |
|---|---|---|---|
| R1 Mock boundary eksik — unmocked side-effect dry-run sırasında çalışır | M | H | 4 mock noktasını stacked context + integration test "no evidence file written" |
| R2 Policy check real path dry_run'da başarısız olabilir | L | M | Policy violations zaten captured; beklenen behavior. Test pozitif case |
| R3 `invoke_cli` return shape mock vs real farklı | M | M | Canned `InvocationResult` contract real shape'i mirror eder |
| R4 CLI dry-run workflow_id lookup mevcut değilse | L | L | `WorkflowDefinitionNotFoundError` surface — CLI error exit |

---

## 6. Codex iter-1 için Açık Sorular

**Q1 — `run_step` vs custom dispatch**: dry_run_step mevcut `run_step`'i MOCK sınırda çağırmalı (pre-flight + dispatch reuse) mi, yoksa ayrı `_dry_run_dispatch` kurmalı mı? v1 reuse (simpler); ayrı dispatch gerekmiyor gibi.

**Q2 — `emit_event` patch site**: Module-level (`executor.evidence_emitter.emit_event`) mi, executor import site mı? C1a'daki `mock_transport` pattern'i executor-alias patching kullandı.

**Q3 — `invoke_cli` canned shape**: `InvocationResult(status="ok", extracted_outputs={}, stdout=b"", stderr=b"", ...)` — real shape'in tüm required field'ları nelerse. Exact shape fact-check gerekecek.

**Q4 — Budget simulation**: `simulated_budget_after = dict(record.get("budget", {}))` — yani raw copy. Cost estimate hesabı C3'e bırakılır (v1 MVP). Acceptable mi?

**Q5 — Run record read-only**: `load_run` read; `update_run` ÇAĞRILMAZ. Mock context manager hiç CAS mutasyonu yapmaz. Bu kontrat test ile pin'lenmeli mi (evet — test_budget_not_mutated).

---

## 7. Implementation Order

1. `DryRunResult` dataclass + `_DryRunRecorder`.
2. `dry_run_execution_context` (4 mock nokta).
3. `Executor.dry_run_step` public method.
4. CLI `executor dry-run` command + handler.
5. 9 test (3 context + 4 integration + 2 CLI).
6. Regression + commit + post-impl review + PR #114.

---

## 8. LOC Estimate

~750 satır (dry_run.py +150, executor.py +30, cli.py +30, cli_handlers.py +60, 9 test +400, docs +80).

---

## 9. Audit Trail

| Iter | Date | Verdict |
|---|---|---|
| v1 (Claude draft) | 2026-04-18 | Pre-Codex iter-1 submit |

**Codex thread**: Yeni (C6-specific).
