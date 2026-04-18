# PR-C3 Implementation Plan v1 — post_adapter_reconcile (Cost Runtime)

**Scope**: FAZ-C runtime closure. `post_adapter_reconcile` middleware — adapter path için `post_response_reconcile` pattern'ının kardeşi. Atomic lock-first: scan_tail duplicate check → fresh path budget drain + ledger append + emit. Reuse `llm_spend_recorded` kind with `source: "adapter_path"` discriminator.

**Base**: `main 9e0be80` (PR #116 C1b.1 merged). **Branch**: `feat/pr-c3-post-adapter-reconcile`.

**Master plan v5 §C3 referans**: iter-6 AGREE'ye yakın spec (atomic lock-first + llm_spend_recorded reuse + cost_actual.tokens_* wire + on-demand catalog lookup).

**Status**: Pre-Codex iter-1 submit. Bu plan master plan v5 §C3 detayları üzerine kurulu + C3 iter-6'da tespit edilen failure-atomicity sorununa pragmatic v1 yaklaşım.

---

## 1. Problem

Adapter path (codex-stub, claude-code-cli, gh-cli-pr) `invoke_cli`/`invoke_http` dönüşünde `cost_actual.{tokens_input, tokens_output, cost_usd}` içerir ama:
- `workflow-run.budget.cost_usd` drenaj edilmez (real reconcile YOK; only B7.1 benchmark shim vardı).
- `spend.jsonl` ledger'a yazılmaz.
- `llm_spend_recorded` event emit edilmez.

Sonuç: adapter-path cost tracking bozuk. B7.1 shim var ama "benchmark-only" (mock_transport layer).

---

## 2. Scope (atomic deliverable)

### 2.1 `_build_adapter_spend_event` builder

**Yeni** (`ao_kernel/cost/middleware.py`):
```python
def _build_adapter_spend_event(
    envelope: Mapping[str, Any],
    *,
    run_id: str,
    step_id: str,
    attempt: int,
    provider_id: str,
    model: str,
    workspace_root: Path,
) -> SpendEvent:
    """Adapter envelope → SpendEvent.
    
    Wire format (master plan v5 iter-5 B3 absorb): tokens under
    ``cost_actual.tokens_input/tokens_output`` (NOT ``usage.*``).
    """
    cost_actual = envelope.get("cost_actual") or {}
    tokens_in_raw = cost_actual.get("tokens_input")
    tokens_out_raw = cost_actual.get("tokens_output")
    cost_raw = cost_actual.get("cost_usd", 0)
    
    usage_missing = (
        tokens_in_raw is None or tokens_out_raw is None
    )
    
    # On-demand catalog lookup for vendor_model_id
    vendor_model_id = None
    try:
        from ao_kernel.cost.policy import load_cost_policy
        cost_policy = load_cost_policy(workspace_root)
        catalog = load_price_catalog(workspace_root, policy=cost_policy)
        entry = find_entry(catalog, provider_id=provider_id, model=model)
        if entry is not None:
            vendor_model_id = entry.vendor_model_id
    except Exception:
        # Unknown/new model → vendor_model_id None (audit-only path).
        pass
    
    return SpendEvent(
        run_id=run_id,
        step_id=step_id,
        attempt=attempt,
        provider_id=provider_id,
        model=model,
        tokens_input=int(tokens_in_raw or 0),
        tokens_output=int(tokens_out_raw or 0),
        cost_usd=Decimal(str(cost_raw)),
        ts=_iso_now(),
        vendor_model_id=vendor_model_id,
        cached_tokens=cost_actual.get("cached_tokens"),
        usage_missing=usage_missing,
    )
```

### 2.2 `post_adapter_reconcile` middleware

**Yeni** (`ao_kernel/cost/middleware.py`):
```python
def post_adapter_reconcile(
    *,
    workspace_root: Path,
    run_id: str,
    step_id: str,
    attempt: int,
    provider_id: str,
    model: str,
    envelope: Mapping[str, Any],
    policy: CostTrackingPolicy,
    elapsed_ms: float | None = None,
) -> None:
    """Adapter-path cost reconcile. Mirrors post_response_reconcile
    but for adapter envelope inputs.
    
    Atomic lock-first order (master plan v5 iter-6):
    1. Acquire ledger file_lock.
    2. Scan ledger tail for duplicate (run_id, step_id, attempt).
    3. If duplicate same-digest: silent warn + return (budget NOT
       drained again; ledger already has the record).
    4. If duplicate different-digest: SpendLedgerDuplicateError.
    5. Fresh path: validate event + append ledger (atomic fsync).
    6. Release lock.
    7. Update budget via CAS (update_run mutator + record_budget_spend).
    8. Emit llm_spend_recorded with source="adapter_path".
    
    Crash-window note (v1 acceptance): if process crashes between
    step 5 (append) and step 7 (update_run), ledger has the event
    but budget not yet drained. Retry: scan finds duplicate → skip
    both append AND budget drain → ghost-charge (ledger says
    spent, budget not deducted). v1 documents this; comprehensive
    fix (adapter_drained_digests schema widen) deferred to
    v3.3.1 or v3.4.0.
    
    This is the INVERSE of the C3 iter-6 concern (double-drain):
    ledger-first ordering avoids double-drain at the cost of
    possible ghost-charge. Ghost-charge is operationally easier
    to detect (ledger as source-of-truth; operator reconciles
    manually via budget audit).
    """
    # Import ledger helpers lazily to keep import cycle clean
    from ao_kernel.cost.ledger import (
        _append_with_fsync,
        _compute_billing_digest,
        _event_to_dict,
        _find_duplicate,
        _ledger_lock_path,
        _ledger_path,
        _scan_tail,
        _validate_event,
    )
    from ao_kernel._internal.shared.lock import file_lock
    from ao_kernel.cost.errors import SpendLedgerDuplicateError
    from dataclasses import replace
    import json as _json
    
    if not policy.enabled:
        return  # dormant
    
    event = _build_adapter_spend_event(
        envelope,
        run_id=run_id, step_id=step_id, attempt=attempt,
        provider_id=provider_id, model=model,
        workspace_root=workspace_root,
    )
    digest = event.billing_digest or _compute_billing_digest(event)
    event = replace(event, billing_digest=digest)
    
    ledger_path = _ledger_path(workspace_root, policy)
    lock_path = _ledger_lock_path(ledger_path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    
    appended = False
    with file_lock(lock_path):
        window = _scan_tail(ledger_path, policy.idempotency_window_lines)
        existing = _find_duplicate(
            window, run_id=run_id, step_id=step_id, attempt=attempt,
        )
        if existing is not None:
            existing_digest = str(existing.get("billing_digest", ""))
            if existing_digest == digest:
                logger.warning(
                    "adapter reconcile idempotent no-op: "
                    "(run_id=%s, step_id=%s, attempt=%d) same-digest",
                    run_id, step_id, attempt,
                )
                return  # Silent no-op (budget already drained at prior call)
            raise SpendLedgerDuplicateError(
                run_id=run_id, step_id=step_id, attempt=attempt,
                existing_digest=existing_digest, new_digest=digest,
            )
        # Fresh path: validate + append inside lock
        doc = _event_to_dict(event)
        _validate_event(doc)
        line = _json.dumps(doc, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":"))
        _append_with_fsync(ledger_path, line)
        appended = True
    
    # CRASH WINDOW — ledger has event, budget not yet drained.
    
    if appended and not event.usage_missing and event.cost_usd > 0:
        # Budget drain via CAS
        def _adapter_mutator(record: dict[str, Any]) -> dict[str, Any]:
            budget_dict = record.get("budget")
            if budget_dict is None:
                # No budget configured — skip silently
                return record
            budget = budget_from_dict(budget_dict)
            if budget.cost_usd is None:
                return record
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
                "adapter reconcile budget drain failed (ledger "
                "entry remains; operator reconcile required): %s",
                exc,
            )
    
    if appended:
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
            "usage_missing": event.usage_missing,
            "ts": event.ts,
        }
        if elapsed_ms is not None:
            payload["duration_ms"] = round(float(elapsed_ms), 3)
        _safe_emit(workspace_root, run_id, "llm_spend_recorded", payload)
```

### 2.3 Call site `Executor.invoke_cli/invoke_http` dönüşü

**executor.py:510-520** adapter path:
```python
invocation_result, budget_after = invoke_cli(...)  # OR invoke_http
# ... existing artifact write + adapter_returned emit ...

# PR-C3: adapter cost reconcile
if policy.enabled and invocation_result.status == "ok":
    envelope_dict = _envelope_from_invocation_result(invocation_result)
    post_adapter_reconcile(
        workspace_root=self._workspace_root,
        run_id=run_id,
        step_id=step_id_for_events,
        attempt=attempt,
        provider_id=manifest.adapter_kind,  # or field mapping
        model=manifest.adapter_id,
        envelope=envelope_dict,
        policy=cost_policy,  # load_cost_policy(workspace_root)
    )
```

`_envelope_from_invocation_result` helper: `InvocationResult.cost_actual` var; map to envelope shape.

### 2.4 B7.1 shim removal

`tests/benchmarks/mock_transport.py::_maybe_consume_budget` silinir. `test_cost_usd_drained_after_happy_review` real path üzerinden pass eder (post_adapter_reconcile runs inside mock_transport canned envelope path).

### 2.5 `llm_spend_recorded` payload discriminator

`source: "adapter_path"` veya `"llm_call"` (existing post_response_reconcile). `docs/evidence-event.schema.v1.json` yoksa documentation-level; `_KINDS` değişmez (reuse).

---

## 3. Test Plan

### 3.1 Yeni test (`tests/test_post_adapter_reconcile.py`):

- `test_happy_path_drains_budget_and_ledger` — envelope with cost → ledger append + budget drain + emit.
- `test_idempotent_same_digest_silent_no_op` — double call → ledger 1 entry + budget single drain.
- `test_different_digest_raises_duplicate_error` — same key different payload → SpendLedgerDuplicateError.
- `test_usage_missing_skips_drain` — cost_actual.tokens_input yok → usage_missing=True, budget untouched.
- `test_dormant_policy_no_op` — policy.enabled=false → skip entirely.
- `test_source_discriminator_on_emit` — llm_spend_recorded payload'ta source="adapter_path".
- `test_cost_actual_wire_format` — envelope.cost_actual.tokens_input NOT envelope.usage.*.

### 3.2 B7.1 shim removal

- `tests/benchmarks/mock_transport.py::_maybe_consume_budget` silinir.
- `tests/benchmarks/test_governed_review.py::test_cost_usd_drained_after_happy_review` pass eder (real path).

### 3.3 Regression

- 2203 + ~8 new = ~2211 green.

---

## 4. Out of Scope

- **Crash-window ghost-charge fix**: `adapter_drained_digests` schema widen → v3.3.1 or v3.4.0 follow-up (master plan v5 iter-6 blocker; v1 accepts documented failure window).
- C6 parity fixup — separate PR.
- C4.1 runtime activation — separate PR.
- C8 release — last.

---

## 5. Risk Register

| Risk | L | I | Mitigation |
|---|---|---|---|
| R1 Crash window ghost-charge | L | M | Documented in docstring; operator reconcile via ledger audit. v1 acceptance. |
| R2 `_build_adapter_spend_event` catalog lookup fail-open | L | L | Try/except → vendor_model_id=None (audit-only). Test covers. |
| R3 `record_spend` iç lock'un dışında ayrı lock | M | H | Direct helper reuse (_scan_tail, _append_with_fsync) without record_spend's lock. Test: no deadlock + atomic guarantee. |
| R4 B7.1 shim removal test_cost_usd_drained_after_happy_review kırar | L | H | Regression gate: mock_transport envelope path'i post_adapter_reconcile tetikler. |

---

## 6. Codex iter-1 için Açık Sorular

**Q1 — Ledger-first crash window acceptable mi**: v1 ledger-first → ghost-charge riski. Alternative: schema widen (`adapter_drained_digests`) + idempotent mutator → tam atomic. v1 document + defer kabul edilebilir mi?

**Q2 — `_envelope_from_invocation_result` helper**: `InvocationResult.cost_actual` mevcut (adapter_invoker.py:69); envelope shape'ine map direct mi, yoksa ayrı builder mi?

**Q3 — `provider_id`/`model` mapping**: Adapter manifest `adapter_id` + `adapter_kind` var; hangisi `provider_id` hangisi `model`? Cost catalog'daki `provider_id`/`model` alanlarıyla nasıl eşleşir?

**Q4 — Call site policy check**: `executor.invoke_cli` dönüşünde `if policy.enabled` check — `load_cost_policy` her çağrıda mı? Yoksa Executor init'te cache?

**Q5 — `llm_spend_recorded` `source` discriminator**: payload'a eklemek yeterli mi, yoksa schema delta gerekli? (Codex master plan v5 iter-6 notu: shipped event schema dosyası yok; `_KINDS` + docs + metrics üzerinden yaşıyor.)

---

## 7. Implementation Order

1. `_build_adapter_spend_event` + imports.
2. `post_adapter_reconcile` middleware.
3. Executor invoke_cli/http return site integration.
4. B7.1 shim removal.
5. 7 yeni test.
6. Regression + commit + post-impl + PR.

---

## 8. LOC Estimate

~700 satır (middleware fn +250, builder +80, executor integration +40, shim remove -30, 7 test +360).

---

## 9. Audit Trail

| Iter | Date | Verdict |
|---|---|---|
| v1 (Claude draft) | 2026-04-18 | Pre-Codex iter-1. Master plan v5 §C3 iter-6 spec temel alındı. |

**Codex thread**: Yeni (C3-specific). Master plan thread `019d9f75` historik referans.
