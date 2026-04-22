# PB-2 — bug_fix_flow + codex-stub patch_preview Closure

**Durum tarihi:** 2026-04-22
**İlişkili issue:** [#222](https://github.com/Halildeu/ao-kernel/issues/222)
**Üst tracker:** [#219](https://github.com/Halildeu/ao-kernel/issues/219)

## Amaç

Deferred bırakılmış `bug_fix_flow` yüzeyi için tek net karar vermek:
bu yol gerçekten çalışır correctness patch akışına dönüşecek mi, yoksa
support boundary'den açıkça dışarıda mı kalacak?

## Bu Slice'ın Sınırı

- bundled `bug_fix_flow` workflow tanımı
- `codex-stub` ile `patch_preview` / patch apply / human gate / devam zinciri
- ilgili runtime test, smoke ve docs parity kararı

## Kapsam Dışı

- `gh-cli-pr` full remote PR opening
- genel amaçlı adapter genişletmesi
- zaman-bağımlı test hygiene taraması
- `cost_usd` reconcile

## Beklenen Çıktılar

1. canlı repro veya deterministik test kanıtı
2. gerçek çalışma mümkünse correctness patch'i
3. mümkün değilse boundary/doküman daraltma kararı
4. ilgili test ve docs hizası

## Kabul Kriterleri

1. Bu yüzey için tek anlamlı durum kalır: ya supported path ya açık deferred path.
2. Workflow repro ve docs aynı şeyi söyler.
3. Human gate / patch_preview / patch apply akışı sessizce fake green üretmez.
4. Public Beta support boundary yanlış genişlemez.

## Beklenen Sonraki Adım

Bu slice kapandıktan sonra doğru hat `PB-3` olacaktır:
deterministic test hygiene / time seam audit.
