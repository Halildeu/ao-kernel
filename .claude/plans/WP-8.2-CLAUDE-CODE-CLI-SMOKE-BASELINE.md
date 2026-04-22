# WP-8.2 — `claude-code-cli` Smoke + Failure-Mode Baseline

**Durum tarihi:** 2026-04-22
**İlişkili issue:** [#199](https://github.com/Halildeu/ao-kernel/issues/199)
**Üst WP:** [#199](https://github.com/Halildeu/ao-kernel/issues/199)

## Amaç

`WP-8.1` ile aday seti netleştikten sonra ilk gerçek adapter lane'ini
çalıştırılabilir backlog'a indirmek. Bu slice'ın amacı `claude-code-cli`
adapter'ı production diye ilan etmek değil; hangi smoke'un güvenli, hangi
failure-mode setinin zorunlu ve hangi canlı blokajların hâlâ açık olduğunu tek
kaynakta toplamak.

## Bu Slice'ın Sınırı

- odak yalnız `claude-code-cli`
- canlı vendor erişimi gerektiren "gerçek başarılı smoke" ile
  auth/environment drift'i birbirine karıştırmamak
- production-tier etiketi vermemek; önce certification baseline'ı çıkarmak
- `gh-cli-pr` ve diğer adapter lane'lerini bu slice'a taşımamak

## Bugünkü Durum

| Alan | Durum | Not |
|---|---|---|
| Bundled manifest | var | aday gerçek adapter olarak tanımlı |
| Operator-safe smoke | yok | disposable target ve güvenli success kriteri henüz yazılı değil |
| Failure-mode testleri | kısmi / dağınık | auth yok, binary yok, deny policy, timeout davranışı tek pakette değil |
| Docs/runtime parity | kısmi | support boundary henüz public capability matrix'e çevrilmedi |
| Release gate | yok | smoke CI-required değil |

## Çıkarılacak Baseline Paketi

1. **Smoke sözleşmesi**
   - hangi disposable workspace kullanılacak
   - success kriteri ne olacak
   - network/auth gereksinimi nasıl ayrılacak
2. **Failure-mode matrisi**
   - CLI binary missing
   - auth erişimi yok
   - policy deny
   - timeout / non-zero exit
   - parse/evidence bozulması
3. **Evidence paketi**
   - workflow events
   - adapter JSONL / stderr/stdout yüzeyi
   - nihai artifact beklentisi
4. **Boundary notu**
   - bu lane geçmeden `claude-code-cli` production-tier değildir

## İlk Kabul Kriterleri

Bu slice tamamlandı sayılabilmek için en az şu çıktılar görünür olmalı:

1. `claude-code-cli` için operator-safe smoke komutu ve başarı kriteri yazılı
2. En az dört failure-mode senaryosu açıkça listelenmiş ve test/repro hedefi
   bağlanmış
3. Hangi senaryoların lokal/dev-only, hangilerinin CI-uygun olduğu ayrılmış
4. Public support boundary'yi genişletmeden status dokümanı güncellenmiş

## Beklenen Sonraki Adımlar

1. smoke harness / disposable workspace seçimi
2. negatif senaryoların test dosyalarına bağlanması
3. gerekiyorsa `claude` binary + auth erişimi için operator prerequisites notu
4. `WP-8.3` öncesi `claude-code-cli` lane'inin beta mı, candidate mı
   kalacağına karar

## Deferred

- vendor-backed sürekli CI smoke
- çoklu organizasyon/auth varyantı sertifikasyonu
- rate-limit / quota exhaustion senaryoları
