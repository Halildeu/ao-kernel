# WP-7.5 — Orchestration Coverage Matrix

**Durum tarihi:** 2026-04-22
**İlişkili issue:** [#198](https://github.com/Halildeu/ao-kernel/issues/198)
**Üst WP:** [#198](https://github.com/Halildeu/ao-kernel/issues/198)

## Amaç

Mevcut shipped `ao-kernel` operasyonlarının ownership semantiğini açık ve
testle pinli hale getirmek: hangi orchestration girişleri claim alır, hangileri
bilinçli olarak claim almaz?

## Bu Slice'ın Kararı

- Yeni runtime write semantics eklemez
- Şu anki shipped operasyon matrisi açıkça kilitlenir:
  - `context_compile` -> claim-free
  - `patch_preview` -> claim-free
  - `patch_apply` -> claim-required
  - `patch_rollback` -> claim-required
- Böylece gelecekte yeni write-capable op eklendiğinde ownership wiring'i
  olmadan “sessiz green” kalması zorlaşır

## Public Surface

- Davranışsal pytest matrisi
- Coordination dokümanında operation classification notu
- Yaşayan status dosyasında aktif slice kaydı

## Definition of Done

1. `context_compile` coordination enabled workspace'te claim acquire etmez
2. `patch_preview` coordination enabled workspace'te claim acquire etmez
3. `patch_apply` / `patch_rollback` claim-required yüzey olarak kalır
4. Docs/status bu matrisi shipped gerçeklik olarak anlatır
5. Gelecek write-capable op genişlemesi için açık deferred not bırakılır

## Deferred

- `release` / `handoff` operatör komutları
- path ownership'in future write-capable workflow operasyonlarına genişletilmesi
- operation metadata üstünden otomatik ownership classification enforcement
