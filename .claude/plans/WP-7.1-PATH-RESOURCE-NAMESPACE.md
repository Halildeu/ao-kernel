# WP-7.1 — Path Resource Namespace

**Durum tarihi:** 2026-04-22
**İlişkili issue:** [#198](https://github.com/Halildeu/ao-kernel/issues/198)
**Üst WP:** [#198](https://github.com/Halildeu/ao-kernel/issues/198)

## Amaç

Path-scoped write ownership için yeni paralel bir lock sistemi yazmadan,
mevcut claim/fencing runtime’ı üstüne kanonik resource namespace katmanı
eklemek.

## Bu Slice’ın Kararı

- v1 write ownership granularity’si **top-level area** olacak
  - `pkg/a.py` ve `pkg/sub/b.py` aynı ownership alanına düşer
- Area -> `resource_id` dönüşümü deterministik ve collision-safe olacak
- Multi-area acquire **atomic olmayacak**
  - sorted sequential acquire
  - sonradan conflict olursa önceki acquire’lar reverse sırada rollback edilir

## Public Surface

- `ao_kernel.coordination.path_ownership`
- `normalize_workspace_relative_path(...)`
- `build_path_write_scopes(...)`
- `acquire_path_write_claims(...)`
- `release_path_write_claims(...)`

## Definition of Done

1. Aynı top-level area için tek claim resource namespace üretiliyor olmalı
2. Relative ve absolute path input’ları aynı kanonik scope’a çözülmeli
3. Aynı area’da ikinci writer conflict almalı
4. Multi-area sequential acquire conflict’inde partial acquire rollback olmalı
5. Bu davranış pytest ile pinlenmiş olmalı

## Deferred

- executor/orchestration girişinde hard enforcement
- takeover/handoff ergonomics
- daha dar granularity (`exact path`, `directory prefix`) seçenekleri
