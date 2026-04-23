# PB-6.4d — Kernel API Write-side Widening Preconditions

**Status:** Queued (hold decision)  
**Date:** 2026-04-23  
**Parent:** `PB-6` / `PB-6.4`  
**Parent issue:** [#243](https://github.com/Halildeu/ao-kernel/issues/243)  
**Queue issue:** [#270](https://github.com/Halildeu/ao-kernel/issues/270)

## Amaç

`PRJ-KERNEL-API` write-side action widening için gerekli governance, test ve
support-boundary kapılarını implementation'dan önce yazılı karar dilimi olarak
sabitlemek.

## Kapsam

1. write-side governance/policy contract önkoşulları
2. action-level behavior test ve negative path coverage gereksinimleri
3. support-boundary update gate'leri
4. hold-to-implementation geçiş kriterleri

## Kapsam Dışı

1. bu slice içinde write-side action widening implementation yapmak
2. support tier yükseltmesini doğrudan uygulamak
3. read-only `system_status` / `doc_nav_check` kapsamını değiştirmek

## Başlangıç Durumu

1. `PRJ-KERNEL-API` bugün yalnız read-only iki action ile support boundary'de
   yer alır: `system_status`, `doc_nav_check`
2. `project_status`, `roadmap_follow`, `roadmap_finish` write-side widening
   adayları defer/hold durumundadır

## Hold Kapıları (Draft)

1. governance gate:
   - action-level policy contract fail-closed tanımlı mı?
2. behavior gate:
   - positive + negative + denial path testleri mevcut mu?
3. safety gate:
   - overwrite/conflict/idempotency davranışı açık mı?
4. docs parity gate:
   - support boundary ve runbook dilinde widening sınırı net mi?
5. rollback gate:
   - write-side başarısızlıklarında geri alma/sınırlandırma adımları belirli mi?

## DoD

1. write-side widening için action bazlı gate tablosu finalize edilmiş
2. defer veya implementation kararı tekilleştirilmiş
3. sonraki slice (implementation açılacaksa) kapsamı dar ve ölçülebilir
