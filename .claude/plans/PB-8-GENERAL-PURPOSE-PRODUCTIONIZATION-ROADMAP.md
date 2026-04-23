# PB-8 — General-Purpose Productionization Roadmap

**Status:** Completed  
**Date:** 2026-04-23  
**Tracker:** [#288](https://github.com/Halildeu/ao-kernel/issues/288) (closed)  
**Execution mode:** Kapsam disiplini, tek aktif runtime tranche

## Amaç

`ao-kernel` için dar shipped baseline'dan, write-side ve live side-effect
lane'leri kontrollü şekilde support boundary içine alacak production-grade
widening hattını takip edilebilir bir program planına çevirmek.

Bu programın amacı feature sayısını büyütmek değil; support boundary
genişlemesini ölçülebilir kapılar üzerinden yönetmektir.

## Başlangıç Gerçeği

1. Shipped baseline canlı ve doğrulanmış:
   - `review_ai_flow + codex-stub`
   - `examples/demo_review.py`
   - policy/evidence/packaging gate zinciri
2. `gh-cli-pr` live write lane support boundary dışında (`deferred`).
3. `PRJ-KERNEL-API` write-side action'lar runtime-backed değil (`deferred`).
4. `bug_fix_flow` release closure support boundary dışında (`deferred`).

## Program İlkeleri (non-negotiable)

1. Aynı anda en fazla 1 aktif runtime tranche.
2. Her tranche tek branch + tek PR + tek net DoD ile kapanır.
3. Support widening yalnız 4 kapı birlikte geçerse açılır:
   - runtime path aktif
   - behavior-first testler yeşil
   - CI/smoke kanıtı mevcut
   - docs/support boundary parity sağlanmış
4. Her tranche kapanışında zorunlu kayıt:
   - status SSOT güncellemesi
   - issue/PR/commit referansı
   - test ve smoke çıktısı
   - kalan deferred/risk notu
5. Helper smoke veya manifest varlığı tek başına support claim üretmez.

## Tranche Sırası

### `PB-8.1` — gh-cli-pr live-write productionization

- Issue: [#289](https://github.com/Halildeu/ao-kernel/issues/289)
- Hedef: preflight/readiness lane'den kontrollü live-write support seviyesine
  geçişin runtime/test/safety kapılarını kapatmak.
- Ana çıktı: create/verify/rollback zinciri fail-closed ve testli.

### `PB-8.2` — PRJ-KERNEL-API write-side runtime implementation

- Issue: [#290](https://github.com/Halildeu/ao-kernel/issues/290)
- Hedef: `project_status`, `roadmap_follow`, `roadmap_finish` için runtime owner,
  policy/safety contract ve behavior-first test matrisi.
- Ana çıktı: write-side action'lar kontrollü şekilde runtime-backed.

### `PB-8.3` — bug_fix_flow release closure promotion

- Issue: [#291](https://github.com/Halildeu/ao-kernel/issues/291)
- Hedef: `bug_fix_flow` lane'ini deferred sınırından kanıtla çıkarma
  (veya kapılar geçmezse yazılı `stay_deferred` kararı).
- Ana çıktı: workflow-level side-effect safety + evidence completeness.

### `PB-8.4` — support widening closeout

- Issue: [#292](https://github.com/Halildeu/ao-kernel/issues/292)
- Hedef: widened surface için docs/runbook/release-gate parity kapanışı.
- Ana çıktı: `PUBLIC-BETA` / `SUPPORT-BOUNDARY` / `KNOWN-BUGS` /
  `OPERATIONS-RUNBOOK` / `ROLLBACK` / `UPGRADE-NOTES` tek gerçeğe iner.

## Başarı Kriterleri

1. **BC-1** docs/runtime/test/CI aynı support boundary'yi söyler.
2. **BC-2** live write lane'lerde rollback + evidence + fail-closed güvence
   zorunlu ve doğrulanmış.
3. **BC-3** write-side action'lar behavior-first negatif testlerle pinli.
4. **BC-4** `bug_fix_flow` için release closure kararı kanıtla verilmiş.
5. **BC-5** release kararı kişi güvenine değil CI/smoke/test gate'lerine dayanır.

## Risk Register

| Risk | Etki | Önlem |
|---|---|---|
| Live-write lane'de gizli side-effect | Yüksek | disposable guard + rollback zorunlu |
| Widening sırasında docs drift | Orta | her tranche sonunda docs parity check |
| Testler green ama davranış boş | Yüksek | behavior-first + negatif path zorunlu |
| Scope creep | Yüksek | tranche dışı değişiklikleri blokla |
| Operator env bağımlılığı | Orta | prerequisite'leri runbook'ta explicit pinle |

## Operasyonel Takip Ritmi

1. Her tranche kickoff'unda aktif issue + aktif plan dosyası set edilir.
2. Her PR sonrası status SSOT güncellenir.
3. Haftalık program özetinde yalnız şu dört başlık raporlanır:
   - geçen tranche
   - aktif tranche
   - blocker/risk
   - bir sonraki tranche'a geçiş kararı

## Zamanlama (hedef, değişebilir)

1. `PB-8.1`: 5-7 iş günü
2. `PB-8.2`: 7-10 iş günü
3. `PB-8.3`: 5-8 iş günü
4. `PB-8.4`: 3-5 iş günü

Toplam hedef: 4-6 hafta (dış bağımlılık ve auth/sandbox stabilitesine bağlı).

## Program Kapanış Koşulu

1. `PB-8.1`..`PB-8.4` kapanır.
2. Support widening kararı `PUBLIC-BETA` ve `SUPPORT-BOUNDARY` üzerinde
   açıkça işlenir.
3. `POST-BETA-CORRECTNESS-EXPANSION-STATUS.md` aktif slice'ı kapatır.
4. Tracker [#288](https://github.com/Halildeu/ao-kernel/issues/288) kapanır.

## Closeout Snapshot (2026-04-23)

1. Tüm tranche'lar tamamlandı:
   - `PB-8.1` [#289](https://github.com/Halildeu/ao-kernel/issues/289)
   - `PB-8.2` [#290](https://github.com/Halildeu/ao-kernel/issues/290)
   - `PB-8.3` [#291](https://github.com/Halildeu/ao-kernel/issues/291)
   - `PB-8.4` [#292](https://github.com/Halildeu/ao-kernel/issues/292)
2. `PB-8.3` karar çıktısı `stay_deferred` olarak korunmuştur.
3. `PB-8.4` docs/runbook/release-gate parity closeout'u
   [#300](https://github.com/Halildeu/ao-kernel/pull/300) +
   [#301](https://github.com/Halildeu/ao-kernel/pull/301) ile tamamlanmıştır.
4. Sonraki aktif hat `PB-9` tracker'ına taşınmıştır.
