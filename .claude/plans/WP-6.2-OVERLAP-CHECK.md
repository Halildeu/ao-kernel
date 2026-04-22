# WP-6.2 — Overlap Check

**Durum tarihi:** 2026-04-22
**İlişkili issue:** [#197](https://github.com/Halildeu/ao-kernel/issues/197)
**Üst WP:** [#197](https://github.com/Halildeu/ao-kernel/issues/197)

## Amaç

Birden fazla attached worktree açıkken aynı path alanına sessizce dokunulmasını
operasyon seviyesinde görünür yapmak.

Bu slice ownership enforcement değildir. Ama merge öncesi veya paralel çalışma
başlamadan önce aynı dosya ya da aynı üst alan üzerinde çakışma riski olup
olmadığını tek komutta görünür kılar.

## Komut

```bash
bash .claude/scripts/ops.sh overlap-check
```

## Overlap Modeli

`ops overlap-check` her attached worktree için değişiklik kümesini şu dört
kaynaktan üretir:

1. base ref'e göre committed path farkı
2. staged path'ler
3. unstaged path'ler
4. untracked path'ler

Base çözümleme sırası:

1. `main` branch'i için upstream, sonra `origin/main`, sonra `main`
2. kısa ömürlü non-main branch'ler için `origin/main`, sonra `main`
3. yalnız mainline ref bulunamazsa branch upstream'i fallback olur

Komut iki seviye sinyal üretir:

- **exact file overlap**
  - aynı relative path birden fazla açık worktree'de değişiyor
- **shared top-level area**
  - aynı üst klasör/alan altında paralel değişim var

## Exit Semantiği

- `0`
  - komut çalıştı; overlap bulunsa da görünürlük amacıyla warning semantiğinde
    kalır
- `2`
  - yanlış kullanım

## Bu Slice'ın Kararı

- Overlap bu aşamada **görünürlük** üretir; hard block değildir.
- Exact file overlap daha güçlü sinyaldir; shared area overlap daha zayıf ama
  yine de koordinasyon ihtiyacını gösterir.
- Hard enforcement / claim / release / takeover akışları `WP-7` kapsamındadır.

## Definition of Done

1. `ops.sh overlap-check` repo içinde mevcut olmalı
2. Attached worktree'ler için changed-path seti görünür olmalı
3. Exact file overlap ve shared area overlap ayrı raporlanmalı
4. En az clean ve overlap path'leri subprocess testleriyle pinlenmiş olmalı
