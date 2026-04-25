# Agent Operating Contract

Bu repo'da Codex ve Claude Code aynı program kontratını takip eder. Ajanlar
sohbet hafızasına veya tahmine göre sıradaki işi seçmez.

## Zorunlu Başlangıç

Her yeni oturumda, kod veya doküman değiştirmeden önce:

```bash
git status --short --branch
git rev-list --left-right --count HEAD...origin/main
bash .claude/scripts/ops.sh preflight
python3 scripts/gpp_next.py
```

Son komut GPP programının aktif work package'ını, blocked hatları ve izinli
sonraki adımı gösterir.

## Çalışma Kuralı

1. `origin/main` merge sonrası tek authority'dir.
2. Her iş ayrı worktree ve short-lived `codex/*` branch üzerinde yürür; farklı
   prefix yalnız açık onayla kullanılır, `claude/*` branch'leri kullanılmaz.
3. Her work package tek issue, tek branch, tek PR ve tek exit decision üretir.
4. Primary checkout sadece `main` sync ve doğrulama içindir; feature/runtime
   editleri primary checkout üstünde yapılmaz.
5. Aynı anda GPP status dosyasında izin verilen aktif iş dışında runtime veya
   support-widening işi başlatılmaz.
6. Merge sonrası `origin/main` fast-forward edilir, worktree ve branch
   temizlenir.

## Yasaklar

1. Dirty worktree ile `pull`, `rebase`, `switch`, `checkout` veya worktree
   remove yapılmaz.
2. Local/operator smoke production evidence sayılmaz.
3. Docs-only PR ile support tier genişletilmez.
4. `support_widening=true` veya `production_platform_claim=true` yalnız GPP
   full matrix ve explicit closeout kararı olmadan yazılmaz.
5. GPP-2 live-adapter runtime binding, `GPP-1`/`GPP-1b` kararları aşılmadan
   başlatılmaz.

## Current Program

Makine-okunur durum:

```text
.claude/plans/gpp_status.v1.json
```

İnsan-okur SSOT:

```text
.claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md
```

Aktif kontrat:

```text
GPP-1b - Agent Operating Program Contract
```
