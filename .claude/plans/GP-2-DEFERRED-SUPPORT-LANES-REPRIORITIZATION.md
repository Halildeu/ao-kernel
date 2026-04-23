# GP-2 — Deferred Support-Lane Backlog Reprioritization

**Status:** Active  
**Date:** 2026-04-23  
**Tracker:** [#329](https://github.com/Halildeu/ao-kernel/issues/329)  
**Execution mode:** Kapsam disiplini, tek aktif planning/runtime tranche

## Amaç

`GP-1` closeout sonrası deferred support-lane backlog'unu tek anlamlı,
kanıt odaklı ve uygulanabilir bir sıraya indirmek.

Bu hattın amacı doğrudan widening implementasyonu değildir.
Amaç, bir sonraki runtime slice açılmadan önce backlog sırasını ve
giriş kapılarını netleştirmektir.

## Başlangıç Gerçeği

1. `GP-1` kapanmıştır ve verdict `stay_beta_operator_managed` olarak
   sabittir.
2. `docs/PUBLIC-BETA.md` içinde şu satırlar deferred durumdadır:
   - `bug_fix_flow` release closure
   - `gh-cli-pr` ile tam E2E remote PR açılışı
   - `docs/roadmap/DEMO-SCRIPT-SPEC.md` üç-adapter akışının canlı destek iddiası
   - adapter-path `cost_usd` reconcile
3. Aktif widening tranche yoktur; yeni runtime işi açılmadan önce
   sıralama ve kanıt boşluğu kararı yazılı olmalıdır.

## Tranche Sırası

### `GP-2.1` — Deferred lane evidence-delta map (Completed)

- Issue: [#331](https://github.com/Halildeu/ao-kernel/issues/331)
- Hedef: her deferred satır için mevcut kanıt, kalan kanıt boşluğu, risk seviyesi
  ve promotion önkoşulunu tek tabloda toplamak.
- Çıktı: `Now / Next / Later` sırası + ilk uygulanabilir tranche önerisi.
- Decision record:
  `.claude/plans/GP-2.1-DEFERRED-LANE-EVIDENCE-DELTA-MAP.md`
- DoD:
  1. Deferred lane tablosu tek anlamlı hale gelir.
  2. İlk aktif runtime tranche açıkça seçilir.
  3. Seçilen tranche için tek issue + tek contract referansı üretilir.
- Kapanış: [#331](https://github.com/Halildeu/ao-kernel/issues/331) closed, PR [#332](https://github.com/Halildeu/ao-kernel/pull/332)

### `GP-2.2` — First runtime slice kickoff (Active)

- Issue: [#333](https://github.com/Halildeu/ao-kernel/issues/333)
- Contract:
  `.claude/plans/GP-2.2-COST-USD-RECONCILE-COMPLETENESS.md`
- Hedef: `GP-2.1` çıktısındaki ilk lane'i dar kapsamlı bir implementation dilimi olarak başlatmak.
- Current candidate lane (from `GP-2.1`): adapter-path `cost_usd` reconcile completeness.
- Kural: yalnız bir lane açılır; diğer deferred satırlar status dosyasında
  `deferred` olarak kalır.

## Gate Modeli

1. **G1 — Truth parity:** docs/runtime/tests/CI aynı support sınırını söylemeli.
2. **G2 — Evidence-first ordering:** runtime değişiklikten önce kanıt boşluğu yazılı olmalı.
3. **G3 — Narrow-slice execution:** birden fazla deferred lane aynı PR hattında açılmaz.
4. **G4 — Decision record:** her promote/stay kararı issue + plan kaydı ile bağlanır.

## Başarı Kriterleri

1. `GP-2.1` sonunda deferred satırların sırasi tartışmasızdır.
2. İlk aktif runtime slice açık issue/contract ile başlatılmıştır.
3. Status SSOT'ta aktif issue/contract alanı günceldir.

## Risk Register

| Risk | Etki | Önlem |
|---|---|---|
| Scope creep | Yüksek | yalnız reprioritization; runtime widening bu tranche'ta yok |
| Overclaim drift | Yüksek | PUBLIC-BETA ve SUPPORT-BOUNDARY parity zorunlu |
| Paralel lane açma | Orta | tek aktif runtime slice kuralı |
| Karar kaydı eksikliği | Orta | issue + contract + status üçlüsü zorunlu |
