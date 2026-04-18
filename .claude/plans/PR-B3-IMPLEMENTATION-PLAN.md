# PR-B3 Implementation Plan v5 — Cost-Aware Model Routing

**Tranche B PR 3/9 — plan v5, post-Codex iter-4 PARTIAL absorb (loader API gerçekliği + aktif spec alias referans temizliği + checksum terminoloji).**

**Head SHA**: `75c114f` (post-B5 merge). Base branch: `main`. Active branch: `claude/tranche-b-pr-b3`.

---

## v5 absorb summary (Codex CNS-20260418-037 iter-4 PARTIAL — 1 blocker + 2 warnings)

**iter-4 verdict**: PARTIAL — v4 fail-closed triage loader gerçekliğiyle uyuşmuyor; plus aktif spec'te alias referansları + terminoloji drift.

| # | v4 bulgu | v5 fix |
|---|---|---|
| **1 (BLOCKER)** | **§2.4 v4 triage yanlış**: `except FileNotFoundError: cost_policy=None` kolu **unreachable**. Gerçek repo API: `load_cost_policy()` (`ao_kernel/cost/policy.py:149-165`) `ws_path.is_file()` false → bundled fallback (exception YOK); malformed → `json.JSONDecodeError`/`jsonschema.ValidationError` raise. `PolicyLoadNotFoundError` diye exception YOK (repo grep 0 match — sadece plan'da kullanılmıştı). | **Loader'a güven, try/except kaldır**. `load_cost_policy()` missing workspace override için bundled dormant policy döner (cost_policy her zaman non-None); malformed override fail-closed contract'ı (`policy.py:115-116` + `:142-143`) natural-propagates raise eder. Router tarafında sadece tek satır: `cost_policy = load_cost_policy(ws_root_normalized)`. Acceptance testleri güncellendi (3 check: missing override → bundled loaded, malformed JSON → JSONDecodeError propagates, schema invalid → ValidationError propagates). |
| **2 (warning)** | `_MODEL_ALIAS_MAP` **aktif spec'te** hâlâ referanslar: §2.3 (`_MODEL_ALIAS_MAP YOK`, `NO _MODEL_ALIAS_MAP`), §4 alternatif sütun, §5 grep acceptance, §7 scope dışı notu. v4 "temizlik" iddiası tamamlanmamış. | **Aktif spec'ten alias ismi tamamen kaldırıldı**. §2.3 kavramsal cümle ("Uncovered models use unknown-bucket semantics"); §4 alternatif sütun "Model aliasing map with concrete table"; §5 grep check kaldırıldı; §7 "Model aliasing — FAZ-C scope". `_MODEL_ALIAS_MAP` ismi SADECE §10 audit trail + v3/v5 absorb summary'de tarihsel bağlamda geçer. |
| **3 (warning)** | v4 §2.4 exception type listesi "malformed JSON, schema invalid, **checksum**" diyor; ama checksum fail-closed path policy loader'a DEĞİL, catalog loader'a ait (`PriceCatalogChecksumError` B2 domain). | "checksum" kelimesi §2.4'ten çıkarıldı; policy loader için doğru liste: `json.JSONDecodeError` + `jsonschema.ValidationError`. Catalog yüklemesi ayrı bir try/except bloğu ve oradaki `PriceCatalogChecksumError` B2 domain olarak zaten `fail_closed_on_catalog_missing=true` altında `RoutingCatalogMissingError` olarak wrapper'a alınır. |

**Ek nota (Codex iter-4 notes teyit)**: `cost/policy.py:115-116, 142-143` fail-closed contract **mevcut ve yeterli** (iter-4 notes YES). §5 "Single provider unknown" satırı §2.4 none-known branch ile **tutarlı** (iter-4 notes YES). §2.6 C4 docs overwrite strategy **dokümante edilmiş** (iter-4 notes YES).

---

## v3 absorb summary (Codex CNS-20260418-037 iter-2 PARTIAL — 3 bulgu, SÜRÜYOR)

**iter-2 verdict**: PARTIAL — plan v2 generally sound, 3 specific tightenings required.

| # | v2 bulgu | v3 fix |
|---|---|---|
| **1** | **Q3 semantik 4 yerde tutarsız**: üst karar tablosu `skip-missing-if-any-known, fallback-if-none-known`; §2.3 `known_cost + unknown_cost in original order`; §2.4 davranış matrisi unknown bucket selectable; §5 acceptance `append-last / unknown=most expensive` | **Tek semantik**: helper `(known_cost_sorted, unknown_list)` tuple döner. Router tarafında — eğer `known_cost_sorted` non-empty ise unknown'ları DROP eder; `known_cost_sorted` empty ise orijinal `provider_order`'a fallback (skip-eleme, parity preserved). Bu kural §2.3 + §2.4 + §5 + karar tablosunda aynı lafla yazılır. |
| **2** | **`RoutingCatalogMissingError(CostError)` yanlış base**: grep `ao_kernel/cost/errors.py:12` → base sınıf `CostTrackingError`, `CostError` diye sınıf yok. | `RoutingCatalogMissingError(CostTrackingError)` — §2.5'te açık inheritance + `__all__` update; type hint update. |
| **3** | **`_MODEL_ALIAS_MAP` v2 header'da duruyor ama §2.3'te somut tablo yok**; provider alias tek başına coverage gap'i kapatmıyor (3/14 exact match). | **Seçim (A)**: v1'de model aliasing YOK. Header tablosu ve §2.3 helper spec'inden `_MODEL_ALIAS_MAP` kaldır. Uncovered modeller → unknown-cost bucket → yukarıdaki §2.4 semantiği gereği known-cost varsa DROP, yoksa fallback. Model aliasing FAZ-C scope. Explicit not §2.5'te + §7 Scope dışı'nda. |

---

## v2 absorb (Codex CNS-20260418-037 iter-1 REVISE — geçmiş)

- **[Yüksek 1]** Router provider namespace ≠ price catalog namespace → `_PROVIDER_ALIAS_MAP` eklendi (v1→v2)
- **[Yüksek 2]** `provider_priority` açık argüman cost-sort çatışması → caller wins bypass (v2)
- **[Yüksek 3]** `sort_providers_by_cost` sig `provider_map=cls_entry` yanlış → `providers_map: Mapping[str, Any]` (v2)
- **[Orta 1]** `workspace_root` normalize bypass → `_resolve_workspace_root` helper (v2)
- **[Orta 2]** Catalog cache key source-path bağımsız → R9 docs note (v2)
- **[Orta 3]** E2E test boşluğu → `test_governed_call_lowest_cost_e2e` (v2 C3)
- **[Orta 4]** NO_SLOT provider_attempts preserve → stable sort integrity (v2)

---

## 5 Q kararları (Codex CNS-037 iter-1, unchanged)

| Q | v1 tentative | v2 kararı | Gerekçe |
|---|---|---|---|
| Q1 explicit provider_priority | caller wins | **caller wins** (v2 explicit bypass) | Caller exact intent semantiği korunur |
| Q2 cost metric | simple avg | **simple avg v1; op knob yok** | Veri-dayanağı yok; schema yüzeyi büyütme |
| Q3 catalog-miss | append-last | **skip-missing-if-any-known, fallback-if-none-known** (v3 tek yerde netleştirildi) | Exact-match coverage 3/14 riski; unknown-cost model seçimi güvensiz |
| Q4 cache | `--no-cache` yok | **Bilinen limit, docs + R9** | Source-path cache key B3 scope dışı |
| Q5 evidence emit | defer | **defer** (teyit) | `_KINDS == 27` invariant; metric derivation cost-track'li |

---

## B2 dormant pin (değişmedi)

- `policy_cost_tracking.v1.json::routing_by_cost.enabled=false` bundled.
- `RoutingByCost(enabled: bool)` dataclass `ao_kernel/cost/policy.py:64` mevcut.
- B3 bu knob'un runtime aktivasyonunu ekler; dormant semantik korunur.

---

## 1. Amaç

Operatör `policy_cost_tracking.routing_by_cost.{enabled, priority}`'yi override dosyasında etkinleştirdiğinde, LLM router (`resolve_route`) aynı-class içindeki verified modeller arasından **en ucuz olanı** seçer. Dormant default davranış (provider-priority sırası) değişmez.

**Kapsam dışı** (scope dışı bölüm §7):
- Cross-class downgrade (ör. CODE_AGENTIC → FAST_TEXT) — budget exhaustion politikası FAZ-C
- Dynamic mid-run re-routing — her çağrı fresh resolution
- Streaming cost estimation — B2 deferred
- Multi-tier cost aggregation (cached_tokens weighting) — basit input+output per-1k average
- **Model aliasing** — v3'te kaldırıldı; FAZ-C scope

### Kapsam özeti

| Katman | Modül | Satır (est.) |
|---|---|---|
| Schema delta | `policy-cost-tracking.schema.v1.json` (+priority field) | ~15 delta |
| Bundled policy | `policy_cost_tracking.v1.json` (default priority) | ~3 delta |
| Dataclass | `cost/policy.py::RoutingByCost` (+priority) | ~10 delta |
| Router cost-aware | `_internal/prj_kernel_api/llm_router.py::resolve` delta | ~80 delta |
| Cost helpers | `cost/routing.py` (NEW — price lookup + sort helper) | ~130 |
| Tests | `test_cost_routing.py` | ~380 |
| Tests (regression) | `test_llm_router.py` delta (dormant parity) | ~40 delta |
| Docs | `docs/COST-MODEL.md` §N + `docs/MODEL-ROUTING.md` delta | ~60 delta |
| CHANGELOG | `[Unreleased]` PR-B3 | ~40 |
| **Toplam** | 1 yeni internal module + 4 code delta + tests + docs | **~750 satır** |

- Yeni evidence kind: **0**
- Yeni adapter capability: 0
- Yeni core dep: 0
- Yeni error type: **1** (`RoutingCatalogMissingError(CostTrackingError)`)

**Runtime LOC**: ~410 (bounded).

---

## 2. Scope İçi

### 2.1 Schema delta — `policy-cost-tracking.schema.v1.json::routing_by_cost`

Mevcut şema:
```json
"routing_by_cost": {
  "type": "object",
  "additionalProperties": false,
  "required": ["enabled"],
  "properties": {
    "enabled": {"type": "boolean"}
  }
}
```

v1 yeni:
```json
"routing_by_cost": {
  "type": "object",
  "additionalProperties": false,
  "required": ["enabled"],
  "properties": {
    "enabled": {"type": "boolean"},
    "priority": {
      "type": "string",
      "enum": ["provider_priority", "lowest_cost"],
      "default": "provider_priority",
      "description": "Selection strategy. 'provider_priority' (default, pre-B3 behavior) preserves llm_resolver_rules.fallback_order_by_class. 'lowest_cost' sorts the eligible provider set ascending by price-catalog input+output per-1k average before iteration."
    },
    "fail_closed_on_catalog_missing": {
      "type": "boolean",
      "default": true,
      "description": "Activate mode + catalog load failure → RoutingCatalogMissingError. When false, falls back to provider_priority semantics with warn-log."
    }
  }
}
```

Bundled policy `policy_cost_tracking.v1.json` additive:
```json
"routing_by_cost": {
  "enabled": false,
  "priority": "provider_priority",
  "fail_closed_on_catalog_missing": true
}
```

### 2.2 Dataclass delta — `cost/policy.py::RoutingByCost`

```python
@dataclass(frozen=True)
class RoutingByCost:
    enabled: bool
    priority: str = "provider_priority"  # enum via schema
    fail_closed_on_catalog_missing: bool = True
```

`_from_dict` güncellenir: optional field'ları güvenle okur, default değerler bundled schema'ya uyumlu.

### 2.3 `cost/routing.py` — NEW internal helper (v3 revised)

Public yüzey az; B3'ün router'a sızdığı tek nokta bu modül.

**v3 değişiklik** (iter-2 PARTIAL absorb):
- Helper artık **tuple** döner: `(known_cost_sorted: list[str], unknown_list: list[str])`
- Model aliasing v1 scope dışı (FAZ-C). Uncovered modeller → unknown-bucket semantics.

```python
# Router provider_id (llm_provider_map.v1.json) → price catalog provider_id
# (price-catalog.v1.json). Exact-match coverage 3/14 (Codex iter-1 Yüksek 1).
_PROVIDER_ALIAS_MAP: Mapping[str, str] = {
    "claude": "anthropic",     # router uses short name; catalog uses vendor
    "openai": "openai",
    "google": "google",
    "deepseek": "deepseek",    # catalog yoksa: unknown-cost bucket
    "qwen": "qwen",
    "xai": "xai",
}

# Model aliasing intentionally absent in v1 — uncovered models resolve to
# unknown-bucket semantics via helper partition; router §2.4 applies
# drop-if-any-known / fallback-if-none-known. Model aliasing FAZ-C scope.


def sort_providers_by_cost(
    provider_order: Sequence[str],
    *,
    providers_map: Mapping[str, Any],  # providers dict from merged_map[classes][class][providers]
    catalog: PriceCatalog,
) -> tuple[list[str], list[str]]:
    """Partition provider_order into (known_cost_sorted, unknown_list).

    Semantics (v3 iter-2 PARTIAL absorb — tek yerde):
    - For each provider_id in provider_order, resolve (catalog_provider_id,
      pinned_model_id) via _PROVIDER_ALIAS_MAP + providers_map.
    - Catalog lookup via find_entry(catalog, catalog_provider_id,
      pinned_model_id) → cost = compute_model_cost_per_1k(entry) or None.
    - Partition:
      * known_cost: entries whose (provider, model) has a catalog entry → list of (provider_id, cost) tuples
      * unknown_list: providers whose catalog lookup returned None
        (missing catalog entry, no providers_map entry / NO_SLOT,
        no pinned_model_id, model not in catalog)
    - Sort known_cost ascending by cost (stable among equal costs).
    - Return (known_cost_sorted, unknown_list)
      where known_cost_sorted is [provider_id, ...] extracted in sort order
      and unknown_list is in original provider_order.

    **Helper does NOT eliminate unknown providers** — router-side
    §2.4 decides drop-if-any-known vs fallback-if-none-known.

    **Invariant** (Codex iter-1 orta 4): stable sort + partition preserves
    NO_SLOT provider_attempts downstream when router chooses fallback.

    Stable sort (Python built-in `sorted` stable) preserves input order
    among equal-cost + unknown-cost buckets.
    """


def compute_model_cost_per_1k(entry: PriceCatalogEntry) -> float:
    """Simple average of input + output per-1k cost. Used for routing
    comparison only; NOT for billing (billing uses actual token counts
    via compute_cost in cost.math).

    v2: cached_input_cost_per_1k deliberately ignored — routing decision
    fresh-call assumption; cache hit is a per-call property, not a model
    property.
    """


def _resolve_catalog_entry(
    provider_id: str,
    providers_map: Mapping[str, Any],
    catalog: PriceCatalog,
) -> PriceCatalogEntry | None:
    """Helper: (provider_id, pinned_model_id) → PriceCatalogEntry | None.

    Alias-aware: provider_id normalized via _PROVIDER_ALIAS_MAP before
    catalog lookup. Returns None on any missing step (no providers entry,
    no pinned_model_id, catalog miss). v3: no model aliasing — exact
    provider+model match required at catalog level.
    """
```

**Pure, side-effect-free**. Evidence emit yok, ledger yazma yok. **v3 partition-only**: router tarafında semantik uygulanır; helper eleme yapmaz.

### 2.4 Router delta — `_internal/prj_kernel_api/llm_router.py::resolve` (v5 loader-trusted)

Tek genişleme: `order` belirlendikten sonra, routing_by_cost aktifse + explicit provider_priority verilmemişse cost-aware partition + router-side decision.

**v5 fail-closed invariant (iter-4 blocker absorb)**:

- **Policy loader'a güven**. `load_cost_policy()` (`ao_kernel/cost/policy.py:149-165`) gerçek davranışı:
  - Missing workspace override (`ws_path.is_file() == False`) → bundled dormant default döner (no exception)
  - Malformed override → `json.JSONDecodeError` / `jsonschema.ValidationError` natural raise (fail-closed, `policy.py:115-116` + `:142-143` contract)
- Dolayısıyla router seviyesinde `cost_policy` her zaman valid bir policy objesi; try/except YOK. Malformed error'lar doğal olarak caller'a propagate edilir (Fail-closed, `llm.py:32-33` contract).
- **Catalog için ayrı durum**: `load_price_catalog()` missing / malformed catalog için B2 domain error'ları raise edebilir (`PriceCatalogChecksumError` dahil). Bu try/except router'da var ve `fail_closed_on_catalog_missing` ile wrapper'a alınır → `RoutingCatalogMissingError`.

```python
# After: order = provider_priority or fallback_default
# NEW in B3 (v5 absorb):
explicit_provider_priority = bool(request.get("provider_priority"))

# (Orta 1 absorb): use the router's own workspace normalizer, not raw Path().
ws_root_normalized = _resolve_workspace_root(repo_root, workspace_root) if workspace_root is not None else None

cost_policy = None
catalog = None
if ws_root_normalized is not None:
    # v5 iter-4 BLOCKER absorb: loader already fails-closed on malformed override
    # (json.JSONDecodeError / jsonschema.ValidationError) per cost/policy.py:115-116, 142-143.
    # Missing workspace override → bundled dormant fallback (never raises).
    # No try/except; malformed errors propagate naturally to caller.
    from ao_kernel.cost.policy import load_cost_policy
    cost_policy = load_cost_policy(ws_root_normalized)

cost_route_active = (
    cost_policy is not None
    and cost_policy.enabled
    and cost_policy.routing_by_cost.enabled
    and cost_policy.routing_by_cost.priority == "lowest_cost"
)

if cost_route_active and not explicit_provider_priority:  # (Yüksek 2 absorb): caller intent wins
    try:
        from ao_kernel.cost.catalog import load_price_catalog
        catalog = load_price_catalog(ws_root_normalized, policy=cost_policy)
    except Exception as exc:
        if cost_policy.routing_by_cost.fail_closed_on_catalog_missing:
            from ao_kernel.cost.errors import RoutingCatalogMissingError
            raise RoutingCatalogMissingError(
                provider_order=list(order),
                target_class=target_class,
                workspace_root=str(ws_root_normalized),
            ) from exc
        catalog = None  # warn-log; order stays provider_priority

    if catalog is not None:
        from ao_kernel.cost.routing import sort_providers_by_cost
        # (v3 iter-2 PARTIAL absorb): tuple partition + router-side decision
        known_cost_sorted, unknown_list = sort_providers_by_cost(
            provider_order=order,
            providers_map=providers,  # already extracted: providers = cls_entry.get("providers", {})
            catalog=catalog,
        )
        # Decision: drop-if-any-known, fallback-if-none-known (Q3 absorb, tek semantik)
        if known_cost_sorted:
            order = known_cost_sorted  # drop unknowns when any known-cost available
        else:
            order = list(order)  # fallback to original provider_priority (no change)
```

**v3 davranış matrisi** (tek semantik — Q3 absorb):

| Koşul | Sıralama |
|---|---|
| `explicit provider_priority` verildi (caller arg) | Orijinal `order` (caller wins, cost bypass) |
| `cost_policy.enabled=false` | Orijinal `order` (pre-B3 davranış) |
| `cost_policy.enabled=true, routing_by_cost.enabled=false` | Orijinal `order` |
| `routing_by_cost.enabled=true, priority="provider_priority"` | Orijinal `order` |
| `routing_by_cost.enabled=true, priority="lowest_cost"`, no explicit, catalog OK, **known-cost ≥ 1** | `known_cost_sorted` (ascending cost; **unknowns DROPPED**) |
| `routing_by_cost.enabled=true, priority="lowest_cost"`, no explicit, catalog OK, **known-cost = 0** (all unknown) | Orijinal `order` (fallback to provider_priority — **no elimination**) |
| Catalog MISSING + `fail_closed_on_catalog_missing=true` | `RoutingCatalogMissingError` raise |
| Catalog MISSING + `fail_closed_on_catalog_missing=false` | Warn-log + provider_priority fallback |

**Tek semantik net cümle** (karar tablosu, §2.3, §2.4, §5 aynı):
> "If at least one provider in `provider_order` has a catalog cost entry, sort ascending and drop unknowns. If no provider has a catalog entry, fall back to original `provider_order` without elimination."

### 2.5 New error type — `cost/errors.py::RoutingCatalogMissingError`

**v3 fix (iter-2 PARTIAL bulgu 2)**: Inherit from `CostTrackingError`, NOT `CostError` (cost/errors.py:12 gerçek base).

```python
class RoutingCatalogMissingError(CostTrackingError):
    """Routing active + price catalog load failed (strict mode).

    Raised when routing_by_cost.enabled=true + priority=lowest_cost
    but the catalog cannot be loaded (missing file, schema fail, etc.).
    fail_closed_on_catalog_missing=true is the strict branch.

    Inherits from CostTrackingError (the canonical base in
    ao_kernel/cost/errors.py:12). B3 adds it to __all__.
    """
    def __init__(
        self,
        provider_order: list[str],
        target_class: str,
        workspace_root: str,
    ) -> None:
        self.provider_order = provider_order
        self.target_class = target_class
        self.workspace_root = workspace_root
        super().__init__(
            f"routing_by_cost active but price catalog load failed "
            f"(class={target_class!r}, providers={provider_order!r}, "
            f"workspace={workspace_root!r})"
        )
```

`__all__` update: `"RoutingCatalogMissingError"` eklenir.

**Explicit note**: Model aliasing (v3'te kaldırıldı) catalog miss için ayrı error type GEREKLI DEĞİL — `unknown_list` helper'dan doğal şekilde döner, router §2.4 semantiğiyle işlenir.

### 2.6 Docs

- `docs/COST-MODEL.md`: yeni subsection "Cost-Aware Routing (PR-B3)". Policy knob, priority enum, catalog requirement, dormant→operator flip chain, **tek semantik cümlesi** (§2.4 alıntısı). **v4 note (iter-3 Codex note)**: mevcut `docs/COST-MODEL.md:118-126` aralığı PR-B3'ü eski tasarım ("budget-aware fallback") olarak anlatıyor; C4 commit bu bloğu **overwrite** eder (append DEĞİL), yeni routing_by_cost semantiği ile uyumlu hale getirir.
- Yeni `docs/MODEL-ROUTING.md` (veya mevcut routing docu varsa delta): `lowest_cost` algoritması + cost hesap formülü + catalog-miss semantiği.
- `CHANGELOG.md [Unreleased]` PR-B3 entry.

### 2.7 `cost/__init__.py` re-export

`RoutingCatalogMissingError` public surface.

---

## 3. Write Order (4-commit DAG)

1. **C1**: Schema + bundled policy delta + dataclass update + 6 policy tests (~80 LOC)
2. **C2**: `cost/routing.py` helper (tuple partition) + `RoutingCatalogMissingError(CostTrackingError)` + 9 routing helper tests (~220 LOC)
3. **C3**: Router delta (`llm_router.resolve` cost-aware branch + drop-or-fallback) + 13 integration tests (regression + cost-aware scenarios + drop + fallback) (~250 LOC)
4. **C4**: Docs `COST-MODEL.md` + `MODEL-ROUTING.md` + CHANGELOG (~100 LOC)

**Toplam ~650 satır** (800 est. içinde).

---

## 4. Design Trade-offs

| Seçim | Alternatif | Gerekçe |
|---|---|---|
| Sort order by simple input+output avg | Weighted by historical usage | Historical usage = ledger read = B2 runtime coupling; avg = stateless. Yeterince akıllı heuristic. |
| Enum `priority` (string) | Free-form strategy selector | Schema closed-enum → drift reject at load time |
| Separate `cost/routing.py` | Inline in `llm_router.py` | Keeps `_internal` router pure; cost-aware concern isolated; testable without router setup |
| `fail_closed_on_catalog_missing=true` default | Fallback-warn default | Governance-first invariant (CLAUDE.md §2); operators can relax |
| No evidence emit for routing decision | New event kind | Router `manifest.provider_attempts` already captures attempts; cost annotation FAZ-C extension |
| Catalog load inside router | Pre-load at client startup | Client `AoKernelClient` doesn't have lifecycle hooks; lazy load in resolve acceptable (300s cache in catalog.py) |
| **Tuple partition helper** (v3) | Single list with append-last | Router-side semantik netliği; helper pure partition; drop-or-fallback kararı çağıran tarafta açık |
| **No model aliasing in v1** (v3) | Model aliasing map with concrete table | Additional surface; FAZ-C scope. Unknown-bucket semantics already handles gap. |

---

## 5. Acceptance Checklist

### Dormant gate (pre-B3 parity)
- [ ] `cost_policy.enabled=false` → router order = fallback_default (unchanged)
- [ ] `cost_policy.enabled=true, routing_by_cost.enabled=false` → unchanged
- [ ] `routing_by_cost.enabled=true, priority="provider_priority"` → unchanged
- [ ] Workspace without `.ao/policies/policy_cost_tracking.v1.json` → bundled dormant default

### Cost-aware path — tek semantik (v3 Q3 absorb)
- [ ] `routing_by_cost.enabled=true + priority="lowest_cost"` + 2 known-cost providers + catalog has both → ascending cost order (known_cost_sorted), unknowns absent
- [ ] 3 providers in order, 2 known-cost + 1 unknown (catalog miss) → known-cost sorted (2 entries), unknown DROPPED
- [ ] 2 providers in order, both unknown (catalog miss on both) → original `provider_order` preserved (fallback, no elimination)
- [ ] Single provider in order + that provider is unknown (catalog miss) → fallback to original order (1 provider preserved, no elimination; §2.4 none-known branch)
- [ ] Stable sort: equal-cost providers preserve original order among known-cost bucket

### Fail-closed policy loader invariant (v5 iter-4 blocker absorb)
- [ ] `load_cost_policy(ws)` with missing workspace override → returns bundled dormant policy (no exception; `cost_policy` non-None, `enabled=false`)
- [ ] `load_cost_policy(ws)` with malformed JSON override → `json.JSONDecodeError` natural-propagates to caller (fail-closed; honors `cost/policy.py:115-116`)
- [ ] `load_cost_policy(ws)` with schema-invalid override → `jsonschema.ValidationError` natural-propagates (fail-closed; honors `cost/policy.py:142-143`)
- [ ] Router does NOT swallow policy loader exceptions (no try/except around `load_cost_policy` call in cost-aware branch)

### Fail-closed path
- [ ] `routing_by_cost.enabled=true + fail_closed_on_catalog_missing=true` + catalog file missing → `RoutingCatalogMissingError` (inherits `CostTrackingError`)
- [ ] `routing_by_cost.enabled=true + fail_closed_on_catalog_missing=false` + catalog missing → warn-log + provider_priority fallback
- [ ] Catalog schema invalid → same fail-closed path
- [ ] `isinstance(err, CostTrackingError)` holds (inheritance test)

### Schema (B0 + B2 regression)
- [ ] Bundled policy loads + schema valid (new `priority` + `fail_closed_on_catalog_missing` fields)
- [ ] Override with `priority="invalid"` → `ValidationError`
- [ ] Override omitting optional fields → defaults applied
- [ ] B2 test regression green (cost middleware untouched by B3)

### Router integration
- [ ] `resolve_route(intent="FAST_TEXT", workspace_root=ws)` honors routing_by_cost
- [ ] `resolve_route` without workspace_root → bypass routing_by_cost (no cost policy to load)
- [ ] Multi-class: cost-aware applied to correct target_class only
- [ ] `APPLY` intent on `CODE_AGENTIC` → cost-aware + existing probe_kind hardening still enforced
- [ ] Provider_priority arg (explicit override) + routing_by_cost active → explicit order wins (no cost re-sort)

### Model aliasing absence (v3)
- [ ] Model not in catalog under its canonical provider → unknown bucket → §2.4 drop-or-fallback applied
- [ ] `cost/routing.py` contains no model alias map (implementation intentionally omits it for v1; FAZ-C scope)

### Regression (zero-delta guard)
- [ ] B0 policy-cost-tracking schema additive — all existing cost tests pass
- [ ] B1 coordination untouched
- [ ] B2 `governed_call` path untouched
- [ ] B5 metrics unchanged (no new event kind)
- [ ] B6 executor untouched
- [ ] `_KINDS == 27` (no new evidence kind)

---

## 6. Risk Register (v3, 10 risk)

| Risk | L | I | Mitigation |
|---|---|---|---|
| R1 Catalog load latency on router hot path | M | L | 300s cache in `catalog.py` (existing); first call = one-time cost |
| R2 Cost entries stale vs verified models | M | M | Catalog staleness gate (`strict_freshness`); out-of-sync = explicit error |
| R3 Model rename between catalog + provider_map | M | M | v3: provider alias only; catalog-miss → unknown-bucket → §2.4 semantiği (drop-if-any-known) safely handles |
| R4 Explicit `provider_priority` arg overrides cost | Resolved | — | v2 §2.4 explicit bypass check; test pin (caller intent respected) |
| R5 `lowest_cost` for free-tier models (cost=0) | L | L | Avg cost = 0; stable sort preserves original order among zero-cost |
| R6 Catalog schema drift | L | H | B2 schema validation + checksum — already fail-closed |
| R7 Provider_map vs catalog provider_id namespace mismatch | Resolved | — | v2 `_PROVIDER_ALIAS_MAP` (Yüksek 1 absorb) |
| R8 Budget exhaustion mid-call still allowed | M | L | B3 scope = routing-time, not call-time. Budget enforcement = B2 domain |
| R9 Catalog cache key path-path drift | L | M | Bilinen limit: `cache_key = workspace_root.resolve()` only; `price_catalog_path` override swap mid-run → stale 300s. v2: docs note + scope-out fix (FAZ-C+) |
| R10 Auto-route + cost-active e2e gap | M | M | v2 C3'e `test_governed_call_lowest_cost_e2e` (stub transport + cost-active + routing enabled + chain assertion) |

---

## 7. Scope Dışı (post-B3)

- Cross-class downgrade (CODE_AGENTIC → FAST_TEXT) — FAZ-C budget policy
- Dynamic mid-run re-routing — her çağrı fresh resolution; session adaptation FAZ-C+
- Weighted cost sort (cached_tokens boost, response-length prior) — B3.1 iteratif iyileştirme
- Budget-aware routing (remaining cost_usd etkiler) — FAZ-C
- Cost annotation evidence (`route_selected` kind) — FAZ-C
- Multi-workspace catalog sharing — deferred (single workspace scope)
- OpenRouter-style dynamic provider failover by cost — post-FAZ-E
- **Model aliasing** — FAZ-C scope (v1 intentionally omits; uncovered models use unknown-bucket semantics via helper partition)

---

## 8. Cross-PR Conflict Resolution

- **B2 MERGED**: `routing_by_cost.enabled` dormant pin var. B3 pinlenen bu knob'u `priority` ile genişletir. Schema additive; `enabled` field behavior değişmez.
- **B5 MERGED**: metrics registry etkilenmez. Router decisions şu an metric surface'de yok; B5 §2.3 usage-missing counter ile uyumlu (cost events zaten derivation'da kullanılıyor).
- **B6 MERGED**: executor + multi-step driver etkilenmez. Router çağrıları executor'dan DEĞİL (governed_call facade path). B6 output_parse walker + capability artifact yazma B3'ten bağımsız.
- **B1 MERGED**: coordination claims etkilenmez.

**Paylaşılan dosya**:
- `ao_kernel/defaults/schemas/policy-cost-tracking.schema.v1.json` — additive optional fields
- `ao_kernel/defaults/policies/policy_cost_tracking.v1.json` — additive optional defaults
- `ao_kernel/cost/policy.py::RoutingByCost` — field additive (default-safe)
- `ao_kernel/cost/__init__.py` — new error re-export
- `ao_kernel/cost/errors.py` — new error class inheriting `CostTrackingError` (v3 base fix)
- `ao_kernel/_internal/prj_kernel_api/llm_router.py` — `resolve` fn: +~60 LOC branch

---

## 9. Codex iter-4 için açık soru: YOK

Tüm v2 Q kararları netleşti (Q1-Q5), v3 3 absorb tightening uygulandı, v4 fail-closed exception triage + 2 minor absorb. Beklenen verdict: **AGREE**.

---

## 10. Audit Trail

| Iter | Date | Verdict |
|---|---|---|
| v1 (Claude draft) | 2026-04-18 | Pre-Codex iter-1 submit |
| iter-1 (CNS-20260418-037, thread `019d9d8a` expired) | 2026-04-18 | **REVISE** — 3 yüksek + 4 orta bulgu; 5 Q cevaplandı |
| v2 (iter-1 absorb) | 2026-04-18 | Pre-iter-2 submit |
| iter-2 (thread `019d9d8a` expired) | 2026-04-18 | **PARTIAL** — 3 dar bulgu (Q3 tutarsızlık + base error + model-alias belirsizliği) |
| v3 (iter-2 absorb) | 2026-04-18 | Pre-iter-3 submit |
| iter-3 (fresh thread `019d9dc6-c303-7cf2-8274-ede60438951d`) | 2026-04-18 | **PARTIAL** — 1 blocker (fail-closed exception triage) + 2 warnings (alias referans temizliği + §5 muğlak satır) |
| v4 (iter-3 absorb) | 2026-04-18 | Pre-iter-4 submit |
| **iter-4** (thread `019d9dc6`) | 2026-04-18 | **PARTIAL** — 1 blocker (loader gerçek API farkı, `FileNotFoundError` unreachable) + 2 warnings (aktif spec alias referansları + checksum terminoloji) |
| **v5 (iter-4 absorb)** | 2026-04-18 | Pre-iter-5 submit |
| iter-5 | TBD | AGREE expected |

### Plan revision history

| Ver | Change |
|---|---|
| v1 | İlk draft; 4-commit DAG; `priority` enum + `fail_closed_on_catalog_missing` knob; `RoutingCatalogMissingError` yeni; evidence emit yok; 5 açık soru |
| v2 | iter-1 REVISE absorb: `_PROVIDER_ALIAS_MAP` + `_MODEL_ALIAS_MAP` (Yüksek 1); explicit provider_priority caller wins bypass (Yüksek 2); `providers_map` sig fix (Yüksek 3); `_resolve_workspace_root` use (Orta 1); catalog cache key limit docs (Orta 2, R9); e2e test (Orta 3, R10); NO_SLOT preserve (Orta 4); Q3 skip-missing-or-fallback; 5 Q kararlı |
| v3 | iter-2 PARTIAL absorb (3 bulgu): (1) Q3 semantik tek yerde — helper tuple partition + router-side drop-if-any-known/fallback-if-none-known; (2) `RoutingCatalogMissingError(CostTrackingError)` base; (3) `_MODEL_ALIAS_MAP` kaldırıldı (v1 scope dışı). |
| v4 | iter-3 PARTIAL absorb (1 blocker + 2 warnings): (1) `load_cost_policy()` exception triage — FileNotFoundError → None fallback, JSONDecodeError/ValidationError → re-raise (teorik contract); (2) alias referansları audit context dışında temizlendi (kısmi); (3) §5 "1 provider + unknown" satırı netleştirildi. Ek note: `docs/COST-MODEL.md:118-126` C4 overwrite strategy dokümante edildi. |
| **v5** | **iter-4 PARTIAL absorb** (1 blocker + 2 warnings): (1) **Loader gerçekliği absorbe edildi** — v4'ün `except FileNotFoundError` kolu unreachable; `load_cost_policy()` missing workspace override → bundled fallback (no exception), malformed → natural raise. Router tarafında try/except KALDIRILDI; `cost_policy = load_cost_policy(ws_root_normalized)` tek satır. Acceptance 3 check (missing → bundled, JSONDecodeError propagates, ValidationError propagates). (2) Alias referans temizliği **aktif spec dahil tamamlandı** — §2.3 kavramsal cümle, §4 alternatif sütun "Model aliasing map", §5 grep check kaldırıldı, §7 isim olmadan "Model aliasing — FAZ-C scope". (3) "checksum" terminoloji §2.4'ten kaldırıldı — checksum B2 catalog domain, policy loader sadece JSONDecodeError + ValidationError. |

**Status**: Plan v5 hazır. Codex CNS-20260418-037 thread `019d9dc6-c303-7cf2-8274-ede60438951d` iter-5 submit için hazır. AGREE beklenir.
