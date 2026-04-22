# WP-7.4 — Coordination Takeover Ergonomics

**Durum tarihi:** 2026-04-22
**İlişkili issue:** [#198](https://github.com/Halildeu/ao-kernel/issues/198)
**Üst WP:** [#198](https://github.com/Halildeu/ao-kernel/issues/198)

## Amaç

Coordination runtime içindeki mevcut `takeover_claim(...)` primitive'ini
operatör için doğrudan kullanılabilir ve denetlenebilir bir CLI yüzeyine
bağlamak.

## Bu Slice'ın Kararı

- Yeni write semantics icat etmez; mevcut registry kontratını CLI'ye taşır
- Çıkış yüzeyi `ao-kernel coordination takeover` olur
- Komut yalnız exact `resource_id` ile çalışır; path-area label'ı değil,
  `coordination status` çıktısındaki gerçek claim anahtarı kullanılır
- Live claim, grace claim ve absent claim yolları non-zero exit + stderr ile
  deterministik yüzeye çıkar
- Corrupt SSOT fail-closed kalır ve exit code `2` ile ayrışır

## Public Surface

- `ao-kernel coordination takeover --resource-id <id> --owner-tag <tag>`
- `ao-kernel coordination takeover --format json`

## Definition of Done

1. Past-grace claim takeover CLI üzerinden başarılı çalışır
2. Başarılı yol text ve json output ile pinlenir
3. Live / grace / absent claim yolları behavior-first testlerle pinlenir
4. CLI parser dispatch gerçek `main(...)` çağrısı üzerinden doğrulanır
5. Coordination dokümanı ve program-status yeni yüzeyi anlatır

## Deferred

- release / handoff ayrı operatör komutları
- geçmiş takeover / handoff timeline query yüzeyi
- orchestration entry coverage'ının `patch_apply` / `patch_rollback` ötesine genişlemesi
