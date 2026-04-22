# WP-6.1 — Ops Preflight

**Durum tarihi:** 2026-04-22
**İlişkili issue:** [#197](https://github.com/Halildeu/ao-kernel/issues/197)
**Üst WP:** [#197](https://github.com/Halildeu/ao-kernel/issues/197)

## Amaç

Session başlangıcında branch freshness, current worktree durumu ve diğer aktif
worktree'lerin kısa sağlık özetini tek komutta görünür hale getirmek.

Bu slice merge kaybını tek başına kapatmaz; ama stale branch veya unutulmuş
dirty tree ile sessiz ilerleme riskini operasyonun giriş kapısında görünür
yapar.

## Komut

```bash
bash .claude/scripts/ops.sh preflight
```

## Kapsam

`ops preflight` şu kontrolleri tek akışta çalıştırır:

1. `check-branch-sync.sh` ile branch freshness / forbidden branch pattern / main
   drift kontrolü
2. current worktree için `staged / unstaged / untracked` özeti
3. upstream görünürlüğü (`ahead/behind` veya henüz push edilmemiş branch uyarısı)
4. diğer attached worktree'lerin `clean/dirty` snapshot'ı

## Exit Semantiği

- `0`
  - branch freshness geçti; komut temiz veya warning'li özet verebilir
- `1`
  - branch freshness veya repo bağlamı güvenli değil; oturuma devam etme
- `2`
  - yanlış kullanım

## Bu Slice'ın Kararı

- Dirty worktree şu aşamada **warning**'dir, hard block değildir.
- Hard block yalnız branch freshness / forbidden branch / detached HEAD /
  `main` drift gibi session başlangıcında yanlış base ile çalışmaya yol açan
  koşullarda uygulanır.
- Daha agresif overlap / close / archive akışları `WP-6.2+` kapsamındadır.

## Definition of Done

1. `ops.sh preflight` repo içinde mevcut olmalı
2. `CLAUDE.md` session başlangıç protokolü bu yüzeye işaret etmeli
3. Yaşayan status dosyasında `WP-6` aktif hat olarak görünmeli
4. En az clean + warning + fail path'lerinden örnekler test veya smoke ile pinlenmiş olmalı
