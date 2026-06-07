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

---

## Execution closeout (2026-06-07)

`retire_candidate` queue executed: the 3 dead contract-only extensions
(`PRJ-EXECUTORPORT`, `PRJ-MEMORYPORT`, `PRJ-OBSERVABILITY-OTEL`) were removed
from `ao_kernel/defaults/extensions/`. Scope = **dead inventory retirement
only**: no support widening, no promotion, no guard-flag change, doctor
`healthy` criterion unchanged. Inventory 19 → 16; `quarantined` 16 → 13; doctor
"Bundled extension truth" WARN remains truthful (13 quarantined with design
intent stay). Audit index: `ao_kernel/defaults/extensions/RETIRED.v1.json`
(restore authority = git history). `classify_bucket()` is now covered by
synthetic fixtures, so the ratchet's bucket logic stays tested with the
`retire_candidate` queue legitimately empty.

`SEARCH` + `UI-COCKPIT-LITE` (PB-6.1a human-confirmed but ratchet `quarantine_keep`
because they declare entrypoints whose targets are absent) are intentionally
**out of scope** here; they need a separate follow-up that either teaches the
ratchet to detect declared-but-dead entrypoints or migrates the PB-6.1a audit
verdict into a deterministic rule before a second retirement.

### Follow-up closeout (2026-06-07) — declared_dead_surface rule

The `retire_candidate` rule was extended with a `declared_dead_surface` sub-reason:
a quarantined manifest that declares an entrypoint/ui surface but has no remap
remediation path (remap=0) AND no registered runtime handler, with
missing_runtime_refs>=9, is now retired alongside the original `dead_shell`
(entrypoints=0, ui=0) sub-reason — both map to the same bucket via a single named
decision. This caught `PRJ-SEARCH` and `PRJ-UI-COCKPIT-LITE` (PB-6.1a
human-confirmed dead), which the prior count-only rule left in `quarantine_keep`
because they declared a (dead) surface. A handler guard keeps a future
live-handler extension with merely broken docs/test refs out of retirement.
Inventory 16 -> 14; quarantined 13 -> 11; `ENFORCEMENT-PACK`/`PM-SUITE` stay
`quarantine_keep` (remap>0 = remediation path). doctor WARN remains truthful (11).
