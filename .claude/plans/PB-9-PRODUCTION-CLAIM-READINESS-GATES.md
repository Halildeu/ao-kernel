# PB-9 — Production Claim Readiness Gates

**Status:** Active  
**Date:** 2026-04-23  
**Tracker:** [#302](https://github.com/Halildeu/ao-kernel/issues/302)  
**Execution mode:** Kapsam disiplini, tek aktif runtime tranche

## Amaç

`ao-kernel` için mevcut dar ama kanıtlı Public Beta yüzeyinden,
genel amaçlı production iddiasına geçiş kararını ölçülebilir kapılarla
yönetmek.

Bu programın amacı tek adımda support boundary widening yapmak değildir.
Amaç, widening kararını kişi güveninden çıkarıp kanıt kontratına bağlamaktır.

## Başlangıç Gerçeği

1. `PB-8` kapanmıştır; tracker [#288](https://github.com/Halildeu/ao-kernel/issues/288)
   closed durumdadır.
2. Shipped baseline çalışır ve CI zinciri (`test + coverage + packaging-smoke`)
   zorunludur.
3. `claude-code-cli` ve `gh-cli-pr` lane'leri beta/operator-managed sınırdadır.
4. Deferred sınır korunur:
   - `bug_fix_flow` release closure (`stay_deferred`)
   - live `gh-cli-pr` remote PR opening support claim'i
   - adapter-path `cost_usd` reconcile support claim'i
5. Known bugs (`KB-001`, `KB-002`) açıktır ve support widening kararını etkiler.

## Gate Modeli (Non-Negotiable)

Production-claim seviyesinde herhangi bir widening kararı ancak aşağıdaki
kapılar birlikte geçerse verilir:

1. **G1 — Truth parity:** docs/runtime/test/CI aynı support boundary'yi söyler.
2. **G2 — Prerequisite determinism:** operator prerequisite seti açık ve
   tekrarlanabilir; smoke çıktıları docs ile çelişmez.
3. **G3 — Behavior + evidence completeness:** write/live lane'lerde failure-mode
   ve evidence zinciri pinlenmiştir.
4. **G4 — Rollback/incident readiness:** side-effect lane için geri dönüş yolu
   çalışır ve runbook'ta karar akışı nettir.
5. **G5 — Governance enforcement:** release/merge kapıları GitHub + CI tarafında
   bypass edilmeden uygulanır.
6. **G6 — Decision record:** widening veya `stay_*` kararı yazılı ve test/smoke
   kanıtına bağlıdır.

## Tranche Sırası

### `PB-9.1` — Operator prerequisite contract parity (Completed)

- Issue: [#303](https://github.com/Halildeu/ao-kernel/issues/303) (`closed`)
- PR: [#305](https://github.com/Halildeu/ao-kernel/pull/305)
- Hedef: `claude-code-cli` ve `gh-cli-pr` lane'lerinde prerequisite dilini
  `PUBLIC-BETA`, `SUPPORT-BOUNDARY`, `OPERATIONS-RUNBOOK` ve smoke helper
  çıktılarıyla tek anlamlı yapmak.
- Ana çıktı: operatör aynı prereq bilgisini tüm SSOT yüzeylerde aynı şekilde görür.

### `PB-9.2` — Truth inventory debt ratchet (Completed)

- Issue: [#306](https://github.com/Halildeu/ao-kernel/issues/306) (`closed`)
- PR: [#308](https://github.com/Halildeu/ao-kernel/pull/308)
- Karar notu: `.claude/plans/PB-9.2-TRUTH-INVENTORY-DEBT-RATCHET.md`
- Hedef: doctor truth inventory (`runtime_backed/contract_only/quarantined`)
  üzerinden promotion sırası için ölçülebilir karar tablosu çıkarmak.
- Ana çıktı: widening adayları için objektif ve tekrar üretilebilir ranking.

### `PB-9.3` — Write/live lane evidence rehearsal (Active)

- Issue: [#309](https://github.com/Halildeu/ao-kernel/issues/309)
- Hedef: write/live lane'lerde create->verify->rollback zincirini
  behavior-first kanıtla güçlendirmek.
- Ana çıktı: live side-effect risklerinin incident/rollback açısından
  operatörce savunulabilir olması.

### `PB-9.4` — Production claim decision closeout (Planned)

- Issue: `pending`
- Hedef: `promote` veya `stay_beta_operator_managed` kararını
  tek bir kapanış notuna bağlamak.
- Ana çıktı: support boundary satırları kararla birlikte güncellenir,
  tracker kapanış kriteri netleşir.

## Başarı Kriterleri

1. **BC-1** `PB-9.1` sonrası prerequisite anlatısı tek anlamlıdır.
2. **BC-2** `PB-9.2` sonrası widening aday sırası ölçülebilir hale gelir.
3. **BC-3** `PB-9.3` sonrası write/live lane kanıt paketi incident-ready olur.
4. **BC-4** `PB-9.4` sonrası support boundary kararı yazılı, testli ve izlenebilirdir.
5. **BC-5** production-claim kararı kişisel yargı değil gate kanıtı ile verilir.

## Risk Register

| Risk | Etki | Önlem |
|---|---|---|
| Docs parity kapanmadan widening baskısı | Yüksek | `PB-9.1` bitmeden runtime widening açma |
| Smoke green ama prerequisite drift | Orta | helper output + docs cross-check zorunlu |
| Side-effect lane'lerde eksik rollback prova | Yüksek | `PB-9.3`te rehearsal kanıtı şart |
| Scope creep | Yüksek | tranche dışı değişiklikleri blokla |
| Karar kaydı eksikliği | Orta | `PB-9.4`te zorunlu closeout notu |

## Program Kapanış Koşulu

1. `PB-9.1`..`PB-9.4` için karar kayıtları tamamlanır.
2. `POST-BETA-CORRECTNESS-EXPANSION-STATUS.md` aktif hatı kapatır.
3. Tracker [#302](https://github.com/Halildeu/ao-kernel/issues/302) kapanır.
