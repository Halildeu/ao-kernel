# PR-C4 Implementation Plan v1 — Cross-Class Routing (Additive Facade)

**Scope**: FAZ-C strategic extension (bağımsız). `ao_kernel.llm.resolve_route` facade additive kwarg widen + internal `resolve` cross_class_downgrade consumer + `_KINDS` 27→28 `route_cross_class_downgrade`. Default-off backwards-compat.

**Base**: `main a581fb5` (PR #111 C2 merged). **Branch**: `feat/pr-c4-resolve-route-kwargs`.

**Status**: Pre-Codex iter-1 submit.

---

## 1. Problem

`llm_resolver_rules.v1.json` `soft_degrade.enabled=true` + rules var ama runtime tüketmiyor. `ao_kernel.llm.resolve_route` public facade'ı (`llm.py:23-46`) `budget_remaining`/`cross_class_downgrade`/`soft_degrade` kwarg'larını almıyor.

---

## 2. Scope (atomic deliverable)

### 2.1 `resolve_route` facade additive kwargs

**Before** (`llm.py:23-46`):
```python
def resolve_route(
    *,
    intent: str,
    perspective: str | None = None,
    provider_priority: list[str] | None = None,
    workspace_root: str | None = None,
) -> dict[str, Any]:
```

**After** (v1 — 3 yeni optional kwarg):
```python
def resolve_route(
    *,
    intent: str,
    perspective: str | None = None,
    provider_priority: list[str] | None = None,
    workspace_root: str | None = None,
    budget_remaining: "Budget | None" = None,  # NEW
    cross_class_downgrade: bool = False,       # NEW (runtime-only knob)
    soft_degrade: bool = False,                # NEW (activate rules consumer)
) -> dict[str, Any]:
    ...
    return resolve(
        request={
            "intent": intent,
            "perspective": perspective,
            "provider_priority": provider_priority or [],
            # PR-C4 additive request keys (internal-only):
            "budget_remaining": budget_remaining,
            "cross_class_downgrade": cross_class_downgrade,
            "soft_degrade": soft_degrade,
        },
        workspace_root=workspace_root,
    )
```

**Backwards-compat**: Default-off (`False`, `None`). 4 mevcut caller (`mcp_server.py:150,353`, `client.py:842`, `intent_router.py:364`) dokunulmaz — 3 yeni kwarg'ı geçmedikleri için davranış değişmez.

### 2.2 Internal `resolve` cross_class_downgrade consumer

`_internal/prj_kernel_api/llm_router.py::resolve`:
```python
def resolve(request, repo_root=None, now=None, workspace_root=None):
    ...
    # PR-C4: cross_class_downgrade runtime consumer (default-off)
    cross_class_downgrade = bool(request.get("cross_class_downgrade", False))
    soft_degrade_enabled = bool(request.get("soft_degrade", False))
    budget_remaining = request.get("budget_remaining")
    
    # Determine target class (intent → class via resolver_rules)
    target_class = resolver_rules["intent_to_class"].get(intent)
    original_class = target_class
    downgrade_applied = False
    downgraded_class = None
    
    if (
        cross_class_downgrade
        and soft_degrade_enabled
        and budget_remaining is not None
        and _budget_below_threshold(budget_remaining, target_class)
    ):
        # Iterate soft_degrade.rules for matching from_class + intents
        for rule in resolver_rules.get("soft_degrade", {}).get("rules", []):
            if (
                rule.get("from_class") == target_class
                and intent in rule.get("intents", [])
            ):
                downgraded_class = rule.get("to_class")
                target_class = downgraded_class
                downgrade_applied = True
                break
    
    # ... existing provider+model selection logic against target_class ...
    
    result = {
        "status": "OK" if selected else "FAIL",
        "selected_provider": provider,
        "selected_model": model,
        # PR-C4 additive response fields (default-off → False/None):
        "downgrade_applied": downgrade_applied,
        "original_class": original_class if downgrade_applied else None,
        "downgraded_class": downgraded_class if downgrade_applied else None,
        # ... existing fields ...
    }
    return result
```

`_budget_below_threshold(budget, class)` helper: basit karşılaştırma — policy `cost_policy.routing_by_cost.class_thresholds` (yoksa `{}`) → class için threshold `budget_remaining.cost_usd < threshold`. Threshold yoksa False (downgrade skip). v1 MVP.

### 2.3 `route_cross_class_downgrade` evidence kind

`evidence_emitter.py:46` `_KINDS` frozenset'ine yeni kind ekle: `"route_cross_class_downgrade"`. **27 → 28**.

Callers (run-aware): `governed_call` / `_run_llm_step` gibi — `resolve_route()` çağrısı sonrası return dict'te `downgrade_applied=True` ise `emit_event(run_id, 'route_cross_class_downgrade', {...})`. C4 scope'ta bu emit call-site'ları ayrıntılı incelenecek; v1 için sadece `_KINDS` bump + contract pin (gerçek emit follow-up PR'a kalabilir eğer karmaşıksa).

### 2.4 Docs update

- `docs/POLICY-SIM.md:49-51` `_KINDS` count 27 → 28.
- `docs/COST-MODEL.md §7` (veya yeni §) `routing_by_cost.cross_class_downgrade` knob.
- `docs/MODEL-ROUTING.md §6` (veya yeni §) soft_degrade runtime consumer.

---

## 3. Test Plan

### 3.1 Yeni testler (`tests/test_resolve_route_kwargs.py`)

- `test_defaults_off_preserves_existing_behavior` — mevcut callers (intent only) → existing return dict (downgrade_applied=False).
- `test_additive_kwargs_accept_without_effect` — `budget_remaining=None, cross_class_downgrade=False` → behavior aynı.
- `test_cross_class_downgrade_active_applies_soft_degrade_rule` — `cross_class_downgrade=True + budget_remaining below threshold` → `downgrade_applied=True`, `original_class=BALANCED_TEXT`, `downgraded_class=FAST_TEXT` (DISCOVERY intent için).
- `test_cross_class_downgrade_without_budget_returns_original` — `cross_class_downgrade=True + budget_remaining=None` → downgrade skip.
- `test_kinds_count_is_28` — `len(_KINDS) == 28`, `'route_cross_class_downgrade' in _KINDS`.
- `test_existing_resolve_route_callers_unchanged` — mcp_server / client / intent_router pattern'ini verify (runtime argv inspection).

### 3.2 Regression gate

- `pytest tests/ -x` — 2164 + 6 = ~2170 green.
- Özellikle `test_policy_sim_integration.py::TestKindsInvariant` (27 → 28 update).
- 4 caller: mcp_server + client + intent_router + runtime fail yok.

---

## 4. Out of Scope

- `route_cross_class_downgrade` evidence emit call-site'ları — v1 sadece `_KINDS` bump + return contract. Emit run-aware caller'lara eklenir (follow-up veya C4 scope genişlemesi).
- Cost policy `routing_by_cost.class_thresholds` schema — minimal; v1 default empty dict (threshold yok → downgrade skip).
- C3/C5/C6 — paralel.

---

## 5. Risk Register

| Risk | L | I | Mitigation |
|---|---|---|---|
| R1 `_KINDS` bump mevcut invariant testlerini kırar | M | L | `test_policy_sim_integration.py` + `test_cost_middleware_core.py` + `test_coordination_takeover_prune.py` _KINDS count update |
| R2 `resolve_route` facade additive kwargs mevcut call-sites'a etki | L | H | Default-off; regression test her caller için |
| R3 `_budget_below_threshold` helper empty policy durumu → ne döner | L | M | Threshold yoksa False (skip); test ile pin |
| R4 `downgrade_applied` response key'i mevcut consumer'ları karıştırır | L | L | Additive; mevcut consumer'lar bu key'e bakmıyor |

---

## 6. Codex iter-1 için Açık Sorular

**Q1 — `Budget` import yolu**: `ao_kernel.workflow.Budget` dataclass mi, yoksa `ao_kernel.cost.Budget` mi? Facade'ta type hint için hangisini import etmeli?

**Q2 — `_budget_below_threshold` threshold kaynağı**: `cost_policy.routing_by_cost.class_thresholds` field schema'da var mı yoksa eklenecek mi? Yoksa threshold hardcoded default mu (ör. $0.10)?

**Q3 — Evidence emit site v1 kapsamında mı**: `route_cross_class_downgrade` emit'i `governed_call` / `_run_llm_step` gibi caller'larda mı eklenecek v1'de? Yoksa _KINDS bump + contract yeter mi, emit follow-up?

**Q4 — Internal `resolve` request dict genişlemesi**: `request["cross_class_downgrade"]` etc. dict key olarak geçirmek OK mi, yoksa signature widen (kwargs direct) daha temiz?

**Q5 — `soft_degrade` kwarg gerekli mi**: `soft_degrade` knob'u default-off? Runtime'da `resolver_rules["soft_degrade"]["enabled"]` zaten var. Bu bayrak caller'ın soft_degrade'i AÇIKCA isteyip istemediğini mi gösterir, yoksa override mı?

---

## 7. Implementation Order

1. `_KINDS` bump (`evidence_emitter.py:46-82` — 27 → 28).
2. `llm.resolve_route` additive kwargs.
3. Internal `resolve` consumer (downgrade logic + response fields).
4. Mevcut _KINDS invariant test'leri update.
5. 6 yeni test.
6. Docs update (POLICY-SIM.md, COST-MODEL.md, MODEL-ROUTING.md).
7. Regression + commit + post-impl Codex review + PR #112.

---

## 8. LOC Estimate

~450 satır (_KINDS +1, facade +8, internal resolve +40, 6 test +300, docs +50, mevcut invariant test update +5).

---

## 9. Audit Trail

| Iter | Date | Verdict |
|---|---|---|
| v1 (Claude draft) | 2026-04-18 | Pre-Codex iter-1 submit |

**Codex thread**: Yeni (C4-specific).
