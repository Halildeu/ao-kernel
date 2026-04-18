# PR-C4 Implementation Plan v2 — Cross-Class Routing (Plumbing-Only, Runtime Dormant)

**Scope**: FAZ-C strategic extension. C4'ün **plumbing katmanı**: `ao_kernel.llm.resolve_route` facade additive kwargs + internal `resolve` request-dict plumbing + `_KINDS` 27→28. **Runtime downgrade dormant**: threshold source schema'da yok (`routing_by_cost.class_thresholds` eksik) + `soft_degrade.rules` directional semantiği pin'lenmemiş. Gerçek downgrade aktivasyonu **follow-up PR C4.1** (threshold schema widen + rule filter).

**Base**: `main a581fb5` (PR #111 C2 merged). **Branch**: `feat/pr-c4-resolve-route-kwargs`.

**Status**: iter-1 PARTIAL absorb → iter-2 submit. Codex thread `019da035-0472-7773-a765-d66a149222a6`.

---

## v2 absorb summary (Codex iter-1 PARTIAL — 3 blocker + 4 warning)

| # | iter-1 bulgu | v2 fix |
|---|---|---|
| **B1** (threshold source yok) | `policy_cost_tracking.schema.v1.json` `routing_by_cost.{enabled, priority, fail_closed_on_catalog_missing}` — `class_thresholds` alanı YOK. `_budget_below_threshold()` kaynağa dayanamaz. | v2: Runtime downgrade **dormant**. Threshold schema widen + `_budget_below_threshold` logic follow-up PR C4.1'e taşındı. v1 plumbing facade kwargs'ı alır, internal resolve request-dict'i okur ama `downgrade_applied=False` her zaman döner (no-op path). |
| **B2** (rules yönsüz) | `soft_degrade.rules` içinde `BALANCED_TEXT→FAST_TEXT` (cost↓) VE `FAST_TEXT→BALANCED_TEXT` (cost↑). Körü körüne iterate yanlış semantik → "downgrade" adında upgrade uygulanabilir. | v2: Runtime rule iteration YOK (dormant path). Directional filter helper (`_is_cost_downgrade(from_class, to_class)` + class cost ordering) C4.1 scope'una taşındı. |
| **B3** (scope gap) | Hedef `CODE_AGENTIC → FAST_TEXT` mevcut ops JSON'da yok; `CODE_AGENTIC` için `degrade_allowed=false`. Plan ops JSON değişimini kapsamıyor. | v2: Scope'u explicit daralt — C4 v1 sadece **plumbing** (facade kwargs + return contract + _KINDS). Ops JSON + threshold + aktif downgrade = C4.1 follow-up. |

### v2 absorb warnings

- **W1** (`soft_degrade` semantic) → **DROP**: `soft_degrade` kwarg kaldırıldı. JSON `resolver_rules["soft_degrade"]["enabled"]` tek authority; caller override etmez.
- **W2** (request-dict doğru tercih) ✅: Internal `resolve` signature dokunulmaz; request dict genişletilir.
- **W3** (_KINDS cascade plan overblown) → daraltıldı: Sadece `test_policy_sim_integration.py:101` + `docs/POLICY-SIM.md:49` exact-count pim'leri update edilecek. `test_cost_middleware_core.py:500` + `test_coordination_takeover_prune.py:377` floor test (auto-28). Docs COST-MODEL.md §7 "24→27" anlatısı "24→28"'e çekilir.
- **W4** (intent_router FAST_TEXT opportunistic fallback) ✅: C4 bu caller'ı düzeltmeye kalkmıyor. Test "existing callers unchanged" davranışsal pin — route success DEĞİL.

---

## 1. Problem (revised)

`ao_kernel.llm.resolve_route` facade'ı `budget_remaining`/`cross_class_downgrade` gibi kwargs'ı ALMIYOR. `_KINDS` 27 kind'ta; cross-class downgrade evidence kind'ı (`route_cross_class_downgrade`) yok. Plumbing katmanı tamamlanmazsa runtime downgrade (C4.1) eklemek için mevcut callers'ı kırmadan genişletme imkansız.

---

## 2. Scope v2 (atomic deliverable — plumbing only)

### 2.1 `resolve_route` facade — 2 additive kwarg (`soft_degrade` drop)

**Before** (`llm.py:23-46`):
```python
def resolve_route(*, intent, perspective=None, provider_priority=None, workspace_root=None):
```

**After** (v2):
```python
def resolve_route(
    *,
    intent: str,
    perspective: str | None = None,
    provider_priority: list[str] | None = None,
    workspace_root: str | None = None,
    # PR-C4 additive, default-off (plumbing-only — runtime dormant):
    budget_remaining: "Budget | None" = None,
    cross_class_downgrade: bool = False,
) -> dict[str, Any]:
    ...
    return resolve(
        request={
            "intent": intent,
            "perspective": perspective,
            "provider_priority": provider_priority or [],
            # Internal-only request keys (dormant v1):
            "budget_remaining": budget_remaining,
            "cross_class_downgrade": cross_class_downgrade,
        },
        workspace_root=workspace_root,
    )
```

Backwards-compat: 4 mevcut caller (mcp_server:150, 353; client:842; intent_router:364) dokunulmaz. Q1 absorb: `Budget` type hint string annotation (TYPE_CHECKING import) — `ao_kernel.workflow.Budget` importlanır; `ao_kernel.cost` export etmez.

### 2.2 Internal `resolve` — request-dict plumbing (dormant)

**`_internal/prj_kernel_api/llm_router.py::resolve`**:
```python
# Existing body unchanged for: intent, perspective, provider_priority.

# PR-C4 plumbing: read but DO NOT act (runtime dormant in v1).
# Real runtime consumer (threshold comparison + rule iteration) =
# follow-up PR C4.1 after policy-cost-tracking schema widens.
_budget_remaining = request.get("budget_remaining")  # ignored in v1
_cross_class_downgrade = bool(
    request.get("cross_class_downgrade", False)
)  # ignored in v1

# ... existing target_class + provider selection logic unchanged ...

result = {
    "status": "OK" if selected else "FAIL",
    "selected_provider": provider,
    "selected_model": model,
    # PR-C4 additive response fields (v1: dormant → always False/None):
    "downgrade_applied": False,
    "original_class": None,
    "downgraded_class": None,
    # ... existing fields ...
}
return result
```

**Dormant invariant**: v1'de `downgrade_applied` her zaman `False`, `original_class`/`downgraded_class` her zaman `None`. Real runtime behavior v4.1'de aktifleşir.

### 2.3 `_KINDS` 27 → 28

`evidence_emitter.py:46` frozenset'ine `"route_cross_class_downgrade"` eklenir. Evidence emit call-site'ları v1'de eklenmez (C4.1 scope).

### 2.4 Test invariant + docs update

- `tests/test_policy_sim_integration.py:101` — `_KINDS` exact-count 27 → 28 + kind listesinde `route_cross_class_downgrade` var.
- `docs/POLICY-SIM.md:49` — `27` → `28`.
- `docs/COST-MODEL.md §7` — "24→27 kinds" anlatısı "24→28 kinds" olur; `route_cross_class_downgrade` açıklama + "C4.1 follow-up: threshold source + rules filter".

---

## 3. Test Plan v2

### 3.1 Yeni testler (`tests/test_resolve_route_kwargs.py`, 5 test):

- `test_defaults_off_preserves_existing_behavior` — 4 mevcut caller pattern'i (`intent="FAST_TEXT"` vb.) + return dict'te yeni alanlar var + default (False/None).
- `test_additive_kwargs_accept_without_runtime_effect` — `budget_remaining=Budget(...)` + `cross_class_downgrade=True` → **DORMANT**: `downgrade_applied=False`, `original_class=None`, `downgraded_class=None`. Test C4 v1 plumbing'in runtime no-op invariant'ını pinler.
- `test_request_dict_plumbing_forwards_kwargs` — mock internal resolve, resolve_route facade'ta geçen kwargs'ın request dict'e map edildiğini verify.
- `test_kinds_count_is_28_and_includes_route_downgrade` — `len(_KINDS) == 28`, `"route_cross_class_downgrade" in _KINDS`.
- `test_invariant_updates_consistent` — mevcut _KINDS invariant test dosyası (`test_policy_sim_integration.py`) güncel pass eder.

### 3.2 Regression gate

- `pytest tests/ -x` — 2164 + 5 = 2169 green.
- `test_policy_sim_integration.py::TestKindsInvariant` — 27→28 update.
- `test_cost_middleware_core.py:500` + `test_coordination_takeover_prune.py:377` — floor test (auto-28 pass).

---

## 4. Out of Scope

- **C4.1 runtime downgrade** — threshold schema widen (`policy-cost-tracking.schema.v1.json` → add `routing_by_cost.class_thresholds`) + `_is_cost_downgrade(from_class, to_class)` directional filter + `soft_degrade.rules` iterate. **Ayrı PR**.
- **Evidence emit call-sites** — `route_cross_class_downgrade` emit'i C4.1'de (run-aware caller'lara eklenir).
- **Ops JSON `CODE_AGENTIC → FAST_TEXT` kuralı** — C4.1 scope.
- C3 / C5 / C6 — paralel.

---

## 5. Risk Register v2

| Risk | L | I | Mitigation |
|---|---|---|---|
| R1 `_KINDS` 27 → 28 invariant test break | M | L | `test_policy_sim_integration.py:101` same-commit update + floor testler auto-pass |
| R2 Facade additive kwargs mevcut callers'a etki | L | M | Default-off; behavioral regression test 4 caller için |
| R3 Dormant path user confusion — "neden downgrade çalışmıyor" | M | L | Return dict docstring + `docs/COST-MODEL.md §7` "C4.1 follow-up" note |
| R4 `Budget` import cycle risk | L | L | `TYPE_CHECKING` string annotation |

---

## 6. Codex iter-2 için Açık Sorular

Bu iter'de yeni Q yok; iter-1 Q1-Q5 absorb edildi. Q2 (threshold source) + Q5 (soft_degrade semantic) özellikle: scope-down ile dormant path + soft_degrade kwarg drop.

---

## 7. Implementation Order

1. `_KINDS` bump (`evidence_emitter.py:46-82`).
2. `llm.resolve_route` additive kwargs (+ TYPE_CHECKING `Budget`).
3. Internal `resolve` request-dict plumbing (dormant).
4. `test_policy_sim_integration.py:101` _KINDS invariant update.
5. `docs/POLICY-SIM.md:49` + `docs/COST-MODEL.md §7` update.
6. 5 yeni test.
7. Regression + commit + post-impl Codex review + PR #112.

---

## 8. LOC Estimate

~300 satır (v1: 450 → v2: 300). _KINDS +1, facade +8, internal resolve +10 (dormant plumbing), _KINDS invariant test update +5, 5 test +200, docs +50.

---

## 9. Audit Trail

| Iter | Date | Verdict |
|---|---|---|
| v1 (Claude draft) | 2026-04-18 | Pre-Codex submit (`4e07cfa`) |
| iter-1 (thread `019da035`) | 2026-04-18 | **PARTIAL** — 3 blocker (threshold source yok, rules yönsüz, scope gap) + 4 warning |
| **v2 (iter-1 absorb)** | 2026-04-18 | Pre-iter-2. Scope-down: plumbing-only + runtime dormant. `soft_degrade` kwarg drop; aktif downgrade C4.1 follow-up. |
| iter-2 | TBD | AGREE expected (dar scope, runtime no-op invariant kod akışıyla pin'li) |

### Plan revision history

| Ver | Change |
|---|---|
| v1 | 3 scope + 5 Q; runtime downgrade aktif, threshold assume, `soft_degrade` kwarg |
| **v2** | iter-1 absorb: scope = plumbing-only; dormant invariant (downgrade_applied=False); soft_degrade kwarg drop; threshold source + rule iterate C4.1 follow-up. |

**Status**: Plan v2 hazır. Dar scope plumbing-only; runtime downgrade invariant no-op. AGREE beklenir.
