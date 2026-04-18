# PR-C3 Implementation Plan v3 — Narrow Fail-Open + Recovery Spec

**v3 absorb (iter-2 PARTIAL — 2 blocker + 3 warning)**:

1. **Narrow fail-open**: v2 broad fail-open W4'ü fiilen geri alıyordu. **v3 fail-open SADECE evidence emit** (`_safe_emit`'in kendisi). Cost-layer errors — `CostTrackingConfigError`, `SpendLedgerCorruptedError`, digest mismatch, budget update_run failures — **propagate**. Mevcut repo contract'ı (docs/COST-MODEL.md §7.2 + ledger.py:251 fail-closed corrupt) mirror.

2. **"Lost spend after completed step" recovery spec**: Second-CAS ordering'in açtığı failure mode (crash between executor's step_completed CAS and post_adapter_reconcile) explicit kabul + recovery prosedürü. Comprehensive fix (atomic single-CAS via mutator restructure) v3.3.1+. v3 scope: docs/COST-MODEL.md §7.5 yeni bölüm + docstring note.

3. `ExecutionResult.budget_after` stale risk: v3 post-reconcile state re-read → ExecutionResult refresh.

4. `load_cost_policy()` pre-dispatch sequencing: v3 policy load'ı `invoke_cli` öncesine taşı — persisted step completed state'inden sonra config hatası ortaya çıkmasın.

5. `cost_actual is not None` gate: `if cost_actual is not None` (empty `{}` usage_missing path'ine düşer, truthy değil).

---

# (v2 retained for history)

## PR-C3 Implementation Plan v2 — post_adapter_reconcile (Scope-Narrow)

**Scope**: FAZ-C cost runtime reconcile. `post_adapter_reconcile` middleware — adapter-path cost drain via **second CAS cycle** after executor's budget_after write. Scope-narrowed per Codex iter-1: no catalog lookup, minimal wire contract (cost_actual.tokens_*), usage_missing → `llm_usage_missing` event (not llm_spend_recorded).

**Base**: `main 9e0be80`. **Branch**: `feat/pr-c3-post-adapter-reconcile`.

**Status**: iter-1 PARTIAL absorb → iter-2 submit. Codex thread `019da0fc-a2e1-7121-b824-b6b40c5712de`.

---

## v2 absorb summary (Codex iter-1 PARTIAL — 3 blocker + 4 warning)

| # | iter-1 bulgu | v2 fix |
|---|---|---|
| **B1** (budget overwrite) | Executor `update_run(_mutator)` line 633 `current["budget"] = budget_to_dict(budget_after)` koşulsuz yazar. Default (A3) path'te post_adapter_reconcile'ın cost drain'i ezilir. | v2: `post_adapter_reconcile` executor'un mutator'undan AYRI **ikinci CAS cycle** — executor's update_run COMPLETES first (A3 default), THEN post_adapter_reconcile reads latest state + applies cost drain. Driver-managed (B6+) path executor mutator skip'ler (line 595-602) → tek CAS. |
| **B2** (error catch matrix) | Yeni `SpendLedgerDuplicateError` executor/driver catch'te yok → terminal event akışı yarım kalır. | v2: `post_adapter_reconcile` içinde try/except ile fail-open wrap — duplicate → warn log + return. Exception dışarı propagate etmez. |
| **B3** (usage_missing event drift) | v1 `llm_spend_recorded` emit ediyor usage_missing için; mevcut runtime `llm_usage_missing` emit eder. | v2: usage_missing → `llm_usage_missing` event (source="adapter_path"). `llm_spend_recorded` sadece success path. |

### v2 absorb warnings

- **W1** (provider_id/model mapping) → **v2 drop catalog lookup**. `vendor_model_id=None` always; `find_entry` silindi. Catalog attribution v3.3.1+ follow-up (adapter manifest widen gerek).
- **W2** (call-site gate status) → v2: gate `cost_actual is not None` — status='ok' şart değil; declined/interrupted/partial da cost_actual taşıyorsa reconcile eder.
- **W3** (cached_tokens wire contract) → v2: builder `cached_tokens` OKUMAZ (schema'da yok).
- **W4** (`_adapter_mutator` silent skip) → v2: budget/cost_usd None → `CostTrackingConfigError` raise (existing post_response_reconcile pattern mirror).

---

## 1. Scope v2 (atomic deliverable — narrow)

### 1.1 `_build_adapter_spend_event` (cost/middleware.py yeni)

**v2 signature**: `cost_actual: Mapping` (NOT envelope wrapper; Q2 absorb).
```python
def _build_adapter_spend_event(
    cost_actual: Mapping[str, Any],
    *,
    run_id: str,
    step_id: str,
    attempt: int,
    provider_id: str,
    model: str,
) -> SpendEvent:
    """Adapter cost_actual → SpendEvent (v2: no catalog lookup)."""
    tokens_in = cost_actual.get("tokens_input")
    tokens_out = cost_actual.get("tokens_output")
    cost = cost_actual.get("cost_usd", 0)
    usage_missing = tokens_in is None or tokens_out is None
    return SpendEvent(
        run_id=run_id,
        step_id=step_id,
        attempt=attempt,
        provider_id=provider_id,
        model=model,
        tokens_input=int(tokens_in or 0),
        tokens_output=int(tokens_out or 0),
        cost_usd=Decimal(str(cost)),
        ts=_iso_now(),
        vendor_model_id=None,  # v2 W1: catalog attribution deferred
        cached_tokens=None,  # v2 W3: not in wire contract
        usage_missing=usage_missing,
    )
```

### 1.2 `post_adapter_reconcile` (cost/middleware.py yeni)

**v2 signature + flow**:
```python
def post_adapter_reconcile(
    *,
    workspace_root: Path,
    run_id: str,
    step_id: str,
    attempt: int,
    provider_id: str,
    model: str,
    cost_actual: Mapping[str, Any] | None,
    policy: CostTrackingPolicy,
    elapsed_ms: float | None = None,
) -> None:
    """Adapter-path cost reconcile. v2 scope-narrow: no catalog
    lookup; fail-open error handling (SpendLedgerDuplicateError
    warn-log + return, not propagate); usage_missing emits
    llm_usage_missing not llm_spend_recorded.
    
    Order:
    1. Guard: policy.enabled + cost_actual available (Q2 absorb:
       any status if cost_actual present).
    2. Build SpendEvent.
    3. Atomic lock-first ledger append (reuses cost.ledger helpers).
    4. Post-lock: update_run mutator (SECOND CAS cycle; reads latest
       state after executor's budget_after write — B1 absorb).
    5. Emit llm_spend_recorded (source=adapter_path) OR
       llm_usage_missing (source=adapter_path) per event.usage_missing.
    
    Fail-open boundary (B2 absorb):
    - SpendLedgerDuplicateError → logger.warning + return.
    - Any other ledger/budget exception → logger.warning + return.
    Exceptions NEVER propagate to executor/driver catch matrix.
    """
    if not policy.enabled:
        return
    if cost_actual is None:
        return
    
    event = _build_adapter_spend_event(
        cost_actual,
        run_id=run_id, step_id=step_id, attempt=attempt,
        provider_id=provider_id, model=model,
    )
    
    # Usage-missing path (B3 absorb): llm_usage_missing, NOT llm_spend_recorded.
    if event.usage_missing:
        # Audit-only ledger entry (cost_usd=0).
        try:
            record_spend(workspace_root, event, policy=policy)
        except Exception as exc:
            logger.warning(
                "adapter reconcile usage_missing ledger write failed "
                "(fail-open): %s", exc,
            )
        _safe_emit(
            workspace_root, run_id, "llm_usage_missing",
            {
                "source": "adapter_path",
                "run_id": run_id,
                "step_id": step_id,
                "attempt": attempt,
                "provider_id": provider_id,
                "model": model,
                "missing_fields": [
                    f for f, v in [
                        ("tokens_input", cost_actual.get("tokens_input")),
                        ("tokens_output", cost_actual.get("tokens_output")),
                    ] if v is None
                ],
                "ts": event.ts,
            },
        )
        return
    
    # Success path: atomic lock-first ledger append + separate CAS drain.
    from ao_kernel.cost.ledger import (
        _append_with_fsync, _compute_billing_digest,
        _event_to_dict, _find_duplicate, _ledger_lock_path,
        _ledger_path, _scan_tail, _validate_event,
    )
    from ao_kernel._internal.shared.lock import file_lock
    from ao_kernel.cost.errors import SpendLedgerDuplicateError
    from dataclasses import replace
    import json as _json
    
    digest = event.billing_digest or _compute_billing_digest(event)
    event = replace(event, billing_digest=digest)
    
    ledger_path = _ledger_path(workspace_root, policy)
    lock_path = _ledger_lock_path(ledger_path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    
    appended = False
    try:
        with file_lock(lock_path):
            window = _scan_tail(
                ledger_path, policy.idempotency_window_lines,
            )
            existing = _find_duplicate(
                window, run_id=run_id, step_id=step_id, attempt=attempt,
            )
            if existing is not None:
                existing_digest = str(existing.get("billing_digest", ""))
                if existing_digest == digest:
                    logger.warning(
                        "adapter reconcile idempotent no-op (same digest)",
                    )
                    return
                # v2 B2: fail-open on different-digest duplicate
                logger.warning(
                    "adapter reconcile digest mismatch (run=%s step=%s "
                    "attempt=%d) — fail-open skip",
                    run_id, step_id, attempt,
                )
                return
            doc = _event_to_dict(event)
            _validate_event(doc)
            line = _json.dumps(doc, sort_keys=True, ensure_ascii=False,
                                separators=(",", ":"))
            _append_with_fsync(ledger_path, line)
            appended = True
    except Exception as exc:
        logger.warning(
            "adapter reconcile ledger write failed (fail-open): %s",
            exc,
        )
        return
    
    # Second CAS cycle (B1 absorb): budget drain post-executor-write.
    if appended and event.cost_usd > 0:
        def _adapter_mutator(record: dict[str, Any]) -> dict[str, Any]:
            budget_dict = record.get("budget")
            if budget_dict is None:
                # W4: fail-closed mirror post_response_reconcile
                raise CostTrackingConfigError(
                    run_id=run_id,
                    details="run.budget dropped between adapter return "
                            "and reconcile",
                )
            budget = budget_from_dict(budget_dict)
            if budget.cost_usd is None:
                raise CostTrackingConfigError(
                    run_id=run_id,
                    details="run.budget.cost_usd dropped between adapter "
                            "return and reconcile",
                )
            new_budget = record_budget_spend(
                budget, cost_usd=event.cost_usd, run_id=run_id,
            )
            return {**record, "budget": budget_to_dict(new_budget)}
        
        try:
            update_run(
                workspace_root, run_id,
                mutator=_adapter_mutator,
                max_retries=3,
            )
        except Exception as exc:
            logger.warning(
                "adapter reconcile budget drain failed (ledger entry "
                "remains; operator reconcile required): %s",
                exc,
            )
    
    # Success emit (B3 absorb: llm_spend_recorded only for real cost).
    payload: dict[str, Any] = {
        "source": "adapter_path",
        "run_id": run_id,
        "step_id": step_id,
        "attempt": attempt,
        "provider_id": provider_id,
        "model": model,
        "tokens_input": event.tokens_input,
        "tokens_output": event.tokens_output,
        "cost_usd": float(event.cost_usd),
        "ts": event.ts,
    }
    if elapsed_ms is not None:
        payload["duration_ms"] = round(float(elapsed_ms), 3)
    _safe_emit(workspace_root, run_id, "llm_spend_recorded", payload)
```

### 1.3 Call site (`executor.py`)

**v2**: AFTER executor's `update_run(_mutator)` (line 633) — second CAS cycle:
```python
# ... existing adapter path: invoke_cli → write_artifact → adapter_returned emit ...
# ... existing update_run(_mutator) writes budget_to_dict(budget_after) ...

update_run(self._workspace_root, run_id, mutator=_mutator)

# PR-C3: adapter cost reconcile (second CAS cycle; fail-open)
cost_policy = load_cost_policy(self._workspace_root)
if cost_policy.enabled:
    cost_actual = invocation_result.cost_actual
    if cost_actual:
        # W2 absorb: any status if cost_actual present
        post_adapter_reconcile(
            workspace_root=self._workspace_root,
            run_id=run_id,
            step_id=step_id_for_events,
            attempt=attempt,
            provider_id=manifest.adapter_kind,  # or map to catalog later
            model=manifest.adapter_id,
            cost_actual=cost_actual,
            policy=cost_policy,
        )

return ExecutionResult(...)
```

Driver-managed (line 482-488) path'te `update_run` skip edilir (mutator skip'li return); post_adapter_reconcile orada DA çalışır (executor return öncesi). Her iki path'te de cost drain happens.

### 1.4 B7.1 shim removal

`tests/benchmarks/mock_transport.py::_maybe_consume_budget` silinir. `test_cost_usd_drained_after_happy_review` real path (post_adapter_reconcile) üzerinden pass eder.

---

## 2. Test Plan v2 (8 new, +1 default-path integration)

- `test_happy_path_drains_budget_via_second_cas_cycle` — A3 default path: ledger append + budget drain + emit.
- `test_driver_managed_path_drain` — B6 driver-managed: same outcome.
- `test_idempotent_same_digest_silent_no_op` — double call → 1 entry, 1 drain.
- `test_different_digest_fail_open_skip` — different digest → warn log, no raise (B2 absorb).
- `test_usage_missing_emits_llm_usage_missing_not_spend_recorded` — B3 absorb.
- `test_dormant_policy_no_op` — policy.enabled=false.
- `test_source_discriminator_on_both_events` — source="adapter_path" on `llm_spend_recorded` AND `llm_usage_missing`.
- `test_cost_actual_wire_format_no_cached_tokens` — W3: cached_tokens not read.

**Default Executor.run_step() integration test** (Codex iter-1 test gap):
- `test_default_executor_run_step_triggers_adapter_reconcile` — driver-managed=False flow; verify ledger entry + budget drained after executor returns.

**B7.1 regression**: `test_cost_usd_drained_after_happy_review` pass eder.

---

## 3. Out of Scope

- **Catalog attribution** (`vendor_model_id` resolve): v2 drops. Follow-up needs adapter manifest widen.
- **Crash window ghost-charge**: ledger-first acceptance; documented; `adapter_drained_digests` schema widen → v3.3.1+.
- C6 parity / C4.1 / C8 — separate PRs.

---

## 4. LOC Estimate

~650 satır (middleware +280, executor integration +40, shim remove -30, 9 test +360).

---

## 5. Audit Trail

| Iter | Date | Verdict |
|---|---|---|
| v1 | 2026-04-18 | Pre-Codex submit `8532e33` |
| iter-1 (thread `019da0fc`) | 2026-04-18 | **PARTIAL** — 3 blocker (budget overwrite, error catch, usage_missing drift) + 4 warning (provider/model mapping, call gate, cached_tokens, mutator fail-closed) |
| **v2 (iter-1 absorb)** | 2026-04-18 | Pre-iter-2 submit. Second CAS cycle + fail-open errors + llm_usage_missing parity + drop catalog lookup + wire scope narrow. |
| iter-2 | TBD | AGREE expected |
