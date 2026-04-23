# PB-9.2 — Truth Inventory Debt Ratchet

**Durum:** Active (`PB-9.2`)  
**Issue:** [#306](https://github.com/Halildeu/ao-kernel/issues/306)  
**Tracker:** [#302](https://github.com/Halildeu/ao-kernel/issues/302)  
**Amaç:** `ao-kernel doctor` truth çıktısını support widening kararından
ayırarak, extension debt sırasını ölçülebilir ve tekrar üretilebilir kurala
bağlamak.

## 1) Kapsam Kuralı

Bu belge support boundary widening kararı vermez. Yalnız şu soruyu yanıtlar:

1. bundled extension inventory içindeki debt hangi sırayla ele alınmalı?
2. hangi extension bugün `promotion_candidate` olamaz?

Support claim kararı için tek otorite yine:

1. `docs/PUBLIC-BETA.md`
2. `docs/SUPPORT-BOUNDARY.md`

## 2) Veri Kaynağı (Deterministik)

Ratchet girdisi yalnız aşağıdaki komutlardan üretilir:

```bash
python3 -m ao_kernel doctor
python3 scripts/truth_inventory_ratchet.py --output json
```

Snapshot (2026-04-23):

- `total_extensions=19`
- `runtime_backed=2`
- `contract_only=1`
- `quarantined=16`
- `remap_candidate_refs=61`
- `missing_runtime_refs=152`

## 3) Karar Sınıfları (Ratchet Kuralları)

Bu tranche'ta sıralama şu deterministic kuralla yapılır:

1. `maintain_runtime_backed`
   - `truth_tier=runtime_backed`
2. `promotion_candidate`
   - `truth_tier=contract_only`
   - `missing_runtime_refs=0`
   - `remap_candidate_refs=0`
3. `remap_priority`
   - `truth_tier=quarantined`
   - `missing_runtime_refs<=8`
   - `remap_candidate_refs>=1`
4. `quarantine_keep`
   - `truth_tier=quarantined`
   - `missing_runtime_refs>=9`
   - `(entrypoint_count>0 OR ui_surfaces_count>0)`
5. `retire_candidate`
   - `truth_tier=quarantined`
   - `missing_runtime_refs>=9`
   - `entrypoint_count=0`
   - `ui_surfaces_count=0`

`remap_priority` sınıfı kendi içinde şu skorla sıralanır:

```text
priority_score = (entrypoint_count * 2) + (ui_surfaces_count * 3)
                 - missing_runtime_refs - remap_candidate_refs
```

Skor yalnız debt işlem sırasını etkiler; support tier etkisi yoktur.

## 4) Current Decision Table (2026-04-23)

| Extension | truth_tier | ep | ui | remap | missing | Ratchet sınıfı |
|---|---|---:|---:|---:|---:|---|
| `PRJ-HELLO` | runtime_backed | 1 | 0 | 0 | 0 | `maintain_runtime_backed` |
| `PRJ-KERNEL-API` | runtime_backed | 5 | 0 | 0 | 0 | `maintain_runtime_backed` |
| `PRJ-CONTEXT-ORCHESTRATION` | contract_only | 0 | 0 | 0 | 0 | `promotion_candidate` |
| `PRJ-AIRUNNER` | quarantined | 2 | 0 | 9 | 7 | `remap_priority` |
| `PRJ-DEPLOY` | quarantined | 4 | 2 | 8 | 7 | `remap_priority` |
| `PRJ-GITHUB-OPS` | quarantined | 7 | 2 | 6 | 8 | `remap_priority` |
| `PRJ-M0-MAINTAINABILITY` | quarantined | 3 | 0 | 1 | 7 | `remap_priority` |
| `PRJ-PLANNER` | quarantined | 5 | 0 | 4 | 7 | `remap_priority` |
| `PRJ-RELEASE-AUTOMATION` | quarantined | 8 | 2 | 4 | 6 | `remap_priority` |
| `PRJ-UX-NORTH-STAR` | quarantined | 1 | 0 | 5 | 7 | `remap_priority` |
| `PRJ-WORK-INTAKE` | quarantined | 9 | 0 | 5 | 8 | `remap_priority` |
| `PRJ-PM-SUITE` | quarantined | 1 | 2 | 8 | 9 | `quarantine_keep` |
| `PRJ-SEARCH` | quarantined | 5 | 0 | 0 | 9 | `quarantine_keep` |
| `PRJ-UI-COCKPIT-LITE` | quarantined | 5 | 1 | 0 | 29 | `quarantine_keep` |
| `PRJ-ENFORCEMENT-PACK` | quarantined | 4 | 0 | 3 | 13 | `quarantine_keep` |
| `PRJ-OBSERVABILITY-OTEL` | quarantined | 0 | 0 | 3 | 12 | `retire_candidate` |
| `PRJ-ZANZIBAR-OPENFGA` | quarantined | 0 | 0 | 1 | 5 | `remap_priority` |
| `PRJ-EXECUTORPORT` | quarantined | 0 | 0 | 2 | 9 | `retire_candidate` |
| `PRJ-MEMORYPORT` | quarantined | 0 | 0 | 2 | 9 | `retire_candidate` |

## 5) Ordered Queue (PB-9.2 Çıkışı)

Ratchet sonucu açık işlem sırası:

1. `promotion_candidate`: `PRJ-CONTEXT-ORCHESTRATION`
2. `remap_priority` (score sırasına göre):
   - `PRJ-RELEASE-AUTOMATION`
   - `PRJ-GITHUB-OPS`
   - `PRJ-WORK-INTAKE`
   - `PRJ-DEPLOY`
   - `PRJ-PLANNER`
   - `PRJ-M0-MAINTAINABILITY`
   - `PRJ-ZANZIBAR-OPENFGA`
   - `PRJ-UX-NORTH-STAR`
   - `PRJ-AIRUNNER`
3. `quarantine_keep`: `PRJ-ENFORCEMENT-PACK`, `PRJ-PM-SUITE`, `PRJ-SEARCH`,
   `PRJ-UI-COCKPIT-LITE`
4. `retire_candidate`: `PRJ-EXECUTORPORT`, `PRJ-MEMORYPORT`,
   `PRJ-OBSERVABILITY-OTEL`

## 6) Karar Notu

`PB-9.2` sonunda:

1. truth-tier -> debt-action eşlemesi yazılı ve deterministic hale geldi.
2. support boundary ile çelişen "inventory = support" yorumu engellendi.
3. widening kararı halen `PB-9.3` ve `PB-9.4` kapıları üzerinden verilecek;
   bu belge yalnız backlog sırasını kilitler.
