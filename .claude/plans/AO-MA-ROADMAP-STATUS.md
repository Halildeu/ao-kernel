# AO-MA-SPM Roadmap Status (insan-okur tracking aynası)

> **Bu dosya nedir:** Operatörün "planda neredeyim?" sorusunun insan-okur cevabı. Makine-okur ikizi: `.claude/plans/ao_ma_status.v1.json` (SSOT). Bu md ondan türer; çelişirse **JSON SSOT esastır** ve `python3 scripts/ao_ma_next.py` drift bildirir.
> **Otorite notu:** Bu dosya da JSON da **tracking index'tir, governance authority DEĞİL** — master plan + merged artifact'lar + ao-release-gate otoritedir.
> **Program SSOT:** `.claude/plans/AO-MA-SPM-MASTER-PLAN.md`. **Statü kaynağı:** AO-MA-11E-1.

## Nasıl bakılır

```bash
python3 scripts/ao_ma_next.py            # özet + sıradaki izinli iş + drift kontrolü
python3 scripts/ao_ma_next.py --next-only  # sadece sıradaki aksiyon
python3 scripts/ao_ma_next.py --format json
```

`ao_ma_next.py` pure-read'dir: shell-out yok, GitHub yok, network yok. Drift varsa exit≠0 (fail-closed: otonomi durdurulur + eskalasyon).

## İlerleme (2026-05-30)

- **Fazlar:** 1/7 done (14%). Tamamlanan: **AO-MA-11I**. Aktif: **AO-MA-11A** + **AO-MA-11E** + **AO-MA-11H** (in_progress).
- **Dilimler (slices):** 3/9 merged (33%).

## Faz Tablosu

| Faz | Başlık | Statü | Dilimler |
|---|---|---|---|
| **AO-MA-11A** | Plan Consensus + Tek Operatör Onay Kapısı | 🟡 in_progress | 11A-1 ✅ merged, 11A-2 ⬜ not_started |
| **AO-MA-11E** | GitHub-Native Operator Tracking Mirror | 🟡 in_progress | 11E-1 ✅ merged, 11E-2 ⬜ not_started |
| **AO-MA-11I** | Autonomous Run Governor | 🟢 done | 11I-1 ✅ merged (#762) |
| **AO-MA-11H** | Notification & Escalation | 🟡 in_progress | 11H-1 🔵 in_progress |
| **AO-MA-11F** | Test/Öneri/Güncelleme Evidence Registers | ⬜ pending | 11F-1 |
| **AO-MA-4.6** | Native Worker Result Import (import-only) | ⬜ pending | 4.6-1 |
| **AO-MA-11G** | SPM Quality Profile Hardening | ⬜ pending | 11G-1 |

## Dilim Tablosu

| Dilim | Statü | Risk | Consensus | Approval | PR | Açıklama |
|---|---|---|---|---|---|---|
| AO-MA-11A-1 | ✅ merged | critical | agreed | approved | #758 | plan_consensus validator + 2 schema |
| AO-MA-11A-2 | ⬜ not_started | high | not_started | not_requested | — | GitHub Environment required-reviewer wiring |
| AO-MA-11E-1 | ✅ merged | critical | agreed | not_requested | #760 | derived tracking SSOT + schema + ao_ma_next + roadmap + drift core |
| AO-MA-11E-2 | ⬜ not_started | high | not_started | not_requested | — | GitHub Projects/Milestone/Issue one-way sync + live drift |
| AO-MA-11I-1 | ✅ merged | critical | agreed | not_requested | #762 | PAUSE kill-switch + budget cap + safe-stop |
| AO-MA-11H-1 | 🔵 in_progress | high | pending | not_requested | — | notifier pure core: intent+receipt schema + decide_notification (bu dilim) |
| AO-MA-11F-1 | ⬜ not_started | normal | not_started | not_requested | — | test/öneri/güncelleme register + closeout |
| AO-MA-4.6-1 | ⬜ not_started | high | not_started | not_requested | — | native worker import-only (no call) |
| AO-MA-11G-1 | ⬜ not_started | normal | not_started | not_requested | — | ADR template + ISO 25010 profile |

## Değişmezler (her dilimde korunur)

`support_widening` / `production_platform_claim` / `live_adapter_execution` = **FALSE** · `release_authority` = ao-release-gate + GitHub ruleset · `--admin` YASAK · risk downgrade YASAK · GitHub mirror tek-yön (authority değil).

## Sıradaki

1. **AO-MA-11H-1** (bu dilim, notifier pure-decision core) merge → `decide_notification` + intent/receipt schema canlı.
2. **AO-MA-11H-2** (side-effect executor: Mavis CLI + `gh` delivery) + **AO-MA-11H-3** (governor `blocked_notification_failed` feedback) — high-risk, ayrı dilimler.
3. **AO-MA-11A-2** (GitHub Environment required-reviewer) + **AO-MA-11E-2** (GitHub mirror sync) — high-risk, ayrı dilimler.

> Bu md, `ao_ma_status.v1.json` her güncellendiğinde elle senkronlanır (11E-1, manuel). 11E-2 sonrası GitHub mirror otomatik akar. Tek gerçek = JSON SSOT; bu md onun okunabilir görünümü.
