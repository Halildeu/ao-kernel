# WP-6.3 — Close Worktree

**Durum tarihi:** 2026-04-22
**İlişkili issue:** [#197](https://github.com/Halildeu/ao-kernel/issues/197)
**Üst WP:** [#197](https://github.com/Halildeu/ao-kernel/issues/197)

## Amaç

Yardımcı worktree kapanışını çıplak `git worktree remove` çağrısından çıkarıp
fail-closed bir operasyon yüzeyine taşımak.

Bu slice branch cleanup veya değişiklik arşivleme yapmaz. Ama yanlış target'ı
kapatma ve dirty tree'yi sessizce düşürme riskini azaltır.

## Komut

```bash
bash .claude/scripts/ops.sh close-worktree <path>
```

## Kapanış Modeli

`ops close-worktree` şu sırayla karar verir:

1. target path attached worktree mi?
2. target current worktree mi?
3. target dirty mi? (`staged`, `unstaged`, `untracked`)
4. ancak bunlar güvenliyse `git worktree remove <path>`

## Exit Semantiği

- `0`
  - target clean non-current attached worktree idi ve kapatıldı
- `1`
  - target current worktree
  - target dirty worktree
  - target bu repo için attached worktree değil
- `2`
  - yanlış kullanım

## Bu Slice'ın Kararı

- Current worktree asla kapatılmaz.
- Dirty target kapatılmaz; önce kullanıcı bilinçli olarak temizlemeli veya daha
  sonra gelecek archive akışına gitmelidir.
- Branch silinmez; bu slice yalnız worktree lifecycle'ın kapanış kısmını
  standartlaştırır.

## Definition of Done

1. `ops.sh close-worktree` repo içinde mevcut olmalı
2. Clean secondary worktree başarıyla kapanmalı
3. Dirty ve current target fail-closed davranmalı
4. Bu kararlar subprocess testleriyle pinlenmiş olmalı
