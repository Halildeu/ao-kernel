# WP-7.2 — Claim Visibility

**Durum tarihi:** 2026-04-22
**İlişkili issue:** [#198](https://github.com/Halildeu/ao-kernel/issues/198)
**Üst WP:** [#198](https://github.com/Halildeu/ao-kernel/issues/198)

## Amaç

Path-scoped ownership claim’lerinin canlı durumunu operatöre görünür yapmak:
kim neyi tutuyor, claim active mi, grace içinde mi, takeover-ready mi?

## Bu Slice’ın Kararı

- Bu dilim **read-only visibility** üretir
- Yeni write semantics veya executor enforcement eklemez
- Çıkış yüzeyi `ao-kernel coordination status` olur
- JSON output mevcut `agent-handoff-status.schema.v1.json` üstüne genişletilmiş
  claim-state alanlarıyla şekillenir

## Public Surface

- `ao_kernel.coordination.status`
- `ao-kernel coordination status --format {text,json}`

## Definition of Done

1. Coordination disabled workspace için başarılı `IDLE` snapshot dönmeli
2. Enabled workspace aktif claim’leri owner/resource/state ile göstermeli
3. `ACTIVE`, `GRACE`, `TAKEOVER_READY` sınıflandırması görünür olmalı
4. CLI text ve json output testle pinlenmeli
5. Status/coordination docs yeni yüzeyi anlatmalı

## Deferred

- geçmiş release/takeover/handoff event geçmişi
- executor-side hard enforcement
- gerçek handoff primitive’i
