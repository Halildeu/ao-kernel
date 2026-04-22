# WP-7.3 — Executor-Side Write Ownership Enforcement

**Durum tarihi:** 2026-04-22
**İlişkili issue:** [#198](https://github.com/Halildeu/ao-kernel/issues/198)
**Üst WP:** [#198](https://github.com/Halildeu/ao-kernel/issues/198)

## Amaç

İlk gerçek write noktası olan `patch_apply` adımında, coordination enabled
workspace'lerde path-scoped ownership claim'ini runtime davranışına bağlamak.

## Bu Slice'ın Kararı

- Enforcement ilk dilimde yalnız `patch_apply` üzerinde açılır
- Claim scope, patch preview'den çıkan `files_changed` listesinden türetilir
- Claim acquire/release, mevcut coordination evidence sink üstünden workflow
  event akışına bağlanır
- Conflict veya grace-conflict deterministic `_StepFailed` sinyaline çevrilir
- Coordination disabled workspaces için mevcut dormant semantics korunur

## Runtime Yüzeyi

- `MultiStepDriver._run_patch_step()`
- `claim_acquired` / `claim_conflict` / `claim_released` workflow evidence
- `diff_applied` payload'ına additive audit alanları:
  - `write_claim_areas`
  - `write_claim_resource_ids`

## Definition of Done

1. Coordination enabled iken `patch_apply` claim acquire/release yapar
2. Aynı path alanında ikinci writer deterministic conflict alır
3. Dormant policy altında claim yüzeyi hiç engage olmaz
4. `diff_applied` evidence'ı claim audit alanlarını taşır
5. Bu davranış behavior-first pytest ile pinlenir

## Deferred

- `patch_apply` dışındaki write-capable orchestration entry'leri
- handoff / takeover ergonomics
- ownership claim'lerinin daha yüksek seviyeli scheduler/orchestrator kararlarına bağlanması
