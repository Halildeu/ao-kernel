# WP-7.3 — Executor-Side Write Ownership Enforcement

**Durum tarihi:** 2026-04-22
**İlişkili issue:** [#198](https://github.com/Halildeu/ao-kernel/issues/198)
**Üst WP:** [#198](https://github.com/Halildeu/ao-kernel/issues/198)

## Amaç

Write-capable patch adımlarında (`patch_apply`, `patch_rollback`),
coordination enabled workspace'lerde path-scoped ownership claim'ini runtime
davranışına bağlamak.

## Bu Slice'ın Kararı

- İlk slice (`PR #209`) `patch_apply` üzerinde merge edildi
- Bu slice enforcement'ı `patch_rollback` yoluna genişletir
- `patch_apply` claim scope'u patch preview'den çıkan `files_changed`
  listesinden türetilir
- `patch_rollback` claim scope'u reverse diff içeriğindeki touched path
  listesinden türetilir
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
- `diff_rolled_back` payload'ına additive audit alanları:
  - `write_claim_areas`
  - `write_claim_resource_ids`

## Definition of Done

1. Coordination enabled iken `patch_apply` ve `patch_rollback` claim
   acquire/release yapar
2. Aynı path alanında ikinci writer deterministic conflict alır
3. Dormant policy altında claim yüzeyi hiç engage olmaz
4. `diff_applied` ve `diff_rolled_back` evidence'ları claim audit alanlarını
   taşır
5. Bu davranış behavior-first pytest ile pinlenir

## Deferred

- `patch_apply` / `patch_rollback` dışındaki write-capable orchestration
  entry'leri
- handoff / takeover ergonomics
- ownership claim'lerinin daha yüksek seviyeli scheduler/orchestrator kararlarına bağlanması
