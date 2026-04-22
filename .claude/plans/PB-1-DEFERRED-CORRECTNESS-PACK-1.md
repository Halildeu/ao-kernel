# PB-1 — Deferred Correctness Pack 1

**Durum tarihi:** 2026-04-22
**İlişkili issue:** [#220](https://github.com/Halildeu/ao-kernel/issues/220)
**Üst tracker:** [#219](https://github.com/Halildeu/ao-kernel/issues/219)

## Amaç

Public Beta closeout sonrasında bilerek deferred bırakılan üç correctness
boşluğunu küçük ve merge-edilebilir tek runtime slice altında kapatmak.

## Bu Slice'ın Sınırı

- `ao_kernel/_internal/roadmap/sanitize.py:39`
- `ao_kernel/_internal/roadmap/compiler.py:139`
- `ao_kernel/init_cmd.py:30-33`

## Kapsam Dışı

- `bug_fix_flow + codex-stub patch_preview` closure
- `gh-cli-pr` full remote PR opening
- deterministic test hygiene geniş taraması
- adapter-path `cost_usd` reconcile

## Beklenen Çıktılar

1. e-posta regex / raw-string bug fix'i
2. `id` olmayan milestone dict girdileri için kontrollü compiler davranışı
3. `init_cmd.run(..., override=...)` write-side asymmetry fix'i
4. ilgili regression testleri
5. minimal deferred/status/doc hizası

## Kabul Kriterleri

1. Üç defect'in her biri için test vardır ve kırık davranışı yakalar.
2. Fix'ler support boundary'yi widen etmez; correctness patch olarak kalır.
3. İlgili test paketi yeşildir.
4. Defer edilmiş kalan işler açıkça defer olarak kalır; sessizce kapanmış gibi gösterilmez.

## Beklenen Sonraki Adım

Bu slice merge olduktan sonra doğru sıradaki bir sonraki runtime hat
`PB-2` olacaktır: `bug_fix_flow + codex-stub patch_preview` closure.
