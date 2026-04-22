# WP-9 — Ops / Runbook / Incident Readiness

**Durum tarihi:** 2026-04-22
**İlişkili issue:** [#200](https://github.com/Halildeu/ao-kernel/issues/200)
**Üst WP:** [#200](https://github.com/Halildeu/ao-kernel/issues/200)

## Amaç

Ürünü yalnız çalışan değil, işletilebilir ve savunulabilir hale getirmek.
Bu slice runtime semantics değiştirmez; operator-facing operasyon paketini
çıkarır.

## Bu Slice'ın Sınırı

- incident runbook
- rollback yolu
- upgrade notes
- support boundary anlatısı
- non-empty known bugs registry

## Çıktı Paketi

1. `docs/OPERATIONS-RUNBOOK.md`
2. `docs/SUPPORT-BOUNDARY.md`
3. `docs/UPGRADE-NOTES.md`
4. `docs/ROLLBACK.md`
5. `docs/KNOWN-BUGS.md`
6. `docs/PUBLIC-BETA.md` known-bugs + operations cross-links
7. `README.md` operations/support docs link yüzeyi

## Kabul Kriterleri

1. Operator shipped baseline ile beta/operator-managed lane'i karıştırmaz
2. Incident anında ilk 5 dakikada çalıştırılacak komutlar yazılıdır
3. Package-level rollback ile source-level rollback ayrı anlatılmıştır
4. `Known Bugs` tablosu boş değildir ve workaround içerir
5. `PUBLIC-BETA.md`, `README.md` ve status SSOT bu pakete link verir

## Beklenen Sonraki Adım

WP-9 merge sonrası production hardening ana programında yeni aktif hat,
post-beta correctness backlog veya yeni runtime genişletme işi olur; ops
hazırlık paketi artık ayrı açık boşluk olarak kalmaz.
