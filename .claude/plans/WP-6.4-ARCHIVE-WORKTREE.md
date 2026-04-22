# WP-6.4 — Archive Worktree

**Durum tarihi:** 2026-04-22
**İlişkili issue:** [#197](https://github.com/Halildeu/ao-kernel/issues/197)
**Üst WP:** [#197](https://github.com/Halildeu/ao-kernel/issues/197)

## Amaç

Dirty bir yardımcı worktree'yi sessiz veri kaybı olmadan düşürebilmek için
dar, fail-closed bir archive+remove yüzeyi eklemek.

Bu slice `close-worktree` ile çakışmaz. `close-worktree` clean helper target
içindir; `archive-worktree` dirty helper target içindir.

## Komut

```bash
bash .claude/scripts/ops.sh archive-worktree <path>
```

## Archive Modeli

`ops archive-worktree` dirty non-current attached target için şunları üretir:

1. `status.txt`
2. `staged.patch`
3. `unstaged.patch`
4. `untracked-files.txt`
5. `untracked/` altına untracked file snapshot'ı
6. `archive-meta.json`
7. `RESTORE.md`

Arşiv konumu repo worktree içinde değil, common git dir altındadır:

- `<git-common-dir>/ops-worktree-archives/<timestamp>-<branch>-<id>/`

Arşiv yazıldıktan sonra target `git worktree remove --force` ile kaldırılır.

## Exit Semantiği

- `0`
  - dirty non-current attached worktree arşivlendi ve kaldırıldı
- `1`
  - target current worktree
  - target clean worktree
  - target bu repo için attached worktree değil
- `2`
  - yanlış kullanım

## Bu Slice'ın Kararı

- Current worktree arşivlenmez.
- Clean target arşivlenmez; `close-worktree`'ye yönlendirilir.
- Branch silinmez; yalnız dirty state snapshot'ı alınır ve worktree kaldırılır.
- Arşiv repo worktree'sini kirletmez; common git dir altında kalır.

## Definition of Done

1. `ops.sh archive-worktree` repo içinde mevcut olmalı
2. Dirty secondary target için archive+remove başarıyla çalışmalı
3. Clean/current/unknown target fail-closed davranmalı
4. Arşivde patch, untracked snapshot ve meta dosyaları bulunmalı
5. Bu davranış subprocess testleriyle pinlenmiş olmalı
