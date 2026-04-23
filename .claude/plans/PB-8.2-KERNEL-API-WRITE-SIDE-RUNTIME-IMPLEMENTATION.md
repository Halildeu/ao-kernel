# PB-8.2 — PRJ-KERNEL-API Write-side Runtime Implementation

**Status:** Active  
**Date:** 2026-04-23  
**Parent tracker:** [#288](https://github.com/Halildeu/ao-kernel/issues/288)  
**Active issue:** [#290](https://github.com/Halildeu/ao-kernel/issues/290)

## Amaç

`PRJ-KERNEL-API` içindeki write-side action'ları
`project_status`, `roadmap_follow`, `roadmap_finish`
runtime owner + behavior-first safety contract ile üretim çizgisine yaklaştırmak.

Bu slice, support boundary widening'i otomatik açmaz; önce runtime/test/docs
parity kapılarını kapatır.

## Kapsam

1. Runtime action registration:
   - `project_status`
   - `roadmap_follow`
   - `roadmap_finish`
2. Action-level safety contract:
   - `workspace_root` zorunlu
   - varsayılan `dry_run=true`
   - gerçek yazma için explicit `confirm_write` token
3. Behavior-first test matrisi:
   - positive
   - deny (`workspace_root`, `confirm_write`)
   - idempotency
   - conflict
   - partial failure rollback
4. Docs/runtime parity:
   - `PUBLIC-BETA`
   - `SUPPORT-BOUNDARY`
   - `OPERATIONS-RUNBOOK`
   - status SSOT

## Kapsam Dışı

1. `bug_fix_flow` widening
2. `gh-cli-pr` full remote live-write widening
3. `PB-8.4` final support-boundary closeout

## DoD

1. Üç write-side action runtime registry'de `PRJ-KERNEL-API` owner ile kayıtlı.
2. Dispatch/loader testleri yeni action setini pinliyor.
3. Conflict/idempotency/deny/rollback negatif path testleri yeşil.
4. Docs ve status yüzeyi write-side lane'i doğru support tier ile anlatıyor.
