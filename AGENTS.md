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

Son komut GPP programının current/active work package'ını, blocked hatları ve
izinli sonraki adımı gösterir.

## Çalışma Kuralı

1. `origin/main` merge sonrası tek authority'dir.
2. Her iş ayrı worktree ve short-lived `codex/*` branch üzerinde yürür; farklı
   prefix yalnız açık onayla kullanılır, `claude/*` branch'leri kullanılmaz.
3. Her work package tek issue, tek branch, tek PR ve tek exit decision üretir.
4. Primary checkout sadece `main` sync ve doğrulama içindir; feature/runtime
   editleri primary checkout üstünde yapılmaz.
5. GPP status dosyası blocked durum gösteriyorsa runtime veya support-widening
   işi başlatılmaz.
6. Merge sonrası `origin/main` fast-forward edilir, worktree ve branch
   temizlenir.

## Yasaklar

1. Dirty worktree ile `pull`, `rebase`, `switch`, `checkout` veya worktree
   remove yapılmaz.
2. Local/operator smoke production evidence sayılmaz.
3. Docs-only PR ile support tier genişletilmez.
4. `support_widening=true` veya `production_platform_claim=true` yalnız GPP
   full matrix ve explicit closeout kararı olmadan yazılmaz.
5. GPP-2 live-adapter runtime binding, protected prerequisite attestation
   `prerequisites_ready` olmadan başlatılmaz.

## Current Program

Makine-okunur durum:

```text
.claude/plans/gpp_status.v1.json
```

İnsan-okur SSOT:

```text
.claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md
```

Current program head:

```text
GPP-2 - Protected Live-Adapter Gate Runtime Binding (closed)
```

Recorded GPP sublane:

```text
GPP-2D - Autonomous Required-Check Lane (fully landed)
  GPP-2D-2c shadow workflow recorded
  GPP-2D-3 enforce job + GPP-2D-4 real-PR evidence collected
  GPP-2D-5 branch-protection ruleset cutover landed
    (ruleset id 16803733; required check ao-release-gate
    via integration_id 15368 source-pin; bypass_actors=[])
  GPP-2D-7 AO-GATE-9 GPP-2 closeout recorded
  GPP-2D-6 / AO-MA-10l low-risk auto-merge smoke recorded
    (run 26633091281, PR #737, merged by app/github-actions)
```

Live autonomy readiness:

```text
AO-MA-10A0/A1 are the current authority for whether the repository can
actually run the fully autonomous merge lane today. The accepted live
low-risk evidence is AO-MA-10q workflow run 26633091281: it created
low-risk PR #737, observed required checks pass, and merged through
app/github-actions without human approval or admin bypass.

Low-risk autonomous merge is active for eligible low-risk changes.
High-risk/governance-sensitive changes remain fail-closed unless the
repo-owned ao-release-gate checks receive required cross-provider
review evidence and GitHub ruleset requirements pass.
```

Related orchestration:

```text
AO-MA-1 - Multi-Agent Orchestration Design (docs recorded)
```

Deferred, not an active blocker:

```text
GPP-2C - testai / smee / webhook callback integration
```

Release authority reminder:

```text
AI agent output is evidence, not release authority.
Release authority is the repo-owned ao-release-gate required check plus
GitHub branch protection after the GPP-2D cutover.
```
