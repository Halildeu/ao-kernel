# WP-8.1 — Real Adapter Certification Baseline

**Durum tarihi:** 2026-04-22
**İlişkili issue:** [#199](https://github.com/Halildeu/ao-kernel/issues/199)
**Üst WP:** [#199](https://github.com/Halildeu/ao-kernel/issues/199)

## Amaç

`WP-8` başlamadan önce "hangi adapter'ı gerçekten sertifiye etmeye
çalışıyoruz?" sorusunu tek kaynağa bağlamak. Bu slice yeni runtime semantics
eklemez; aday adapter setini, certification kriterlerini ve bilinen blokajları
yazılı hale getirir.

## Bu Slice'ın Kararı

- İlk bundled gerçek-adapter aday seti:
  - `claude-code-cli`
  - `gh-cli-pr`
- Sertifikasyon DIŞI yüzeyler:
  - `codex-stub` -> deterministik baseline, gerçek-adapter değildir
  - `custom-http-example` ve test fixture manifestleri -> contract/example
    yüzeyidir, bundled production adayı değildir
- `claude-code-cli` ve `gh-cli-pr` bugün **operator-managed / uncertified**
  yüzeylerdir; bu slice onları production diye etiketlemez

## İlk Certification Matrisi

| Adapter | Bugünkü durum | Neden production değil | İlk certification lane |
|---|---|---|---|
| `claude-code-cli` | operator-managed | CI'da canlı smoke yok; auth/runtime drift operatöre bağlı | disposable sandbox smoke + failure-mode suite |
| `gh-cli-pr` | contract exists, live-side-effect risky | gerçek PR yan etkisi ve güvenli smoke yok | side-effect-safe draft/disposable PR smoke kararı |
| `codex-stub` | deterministic baseline | gerçek adapter değil | WP-8 dışında kalır |

## Production-Tier İçin Giriş Kriterleri

Bir adapter production-tier veya production-candidate lane'e ancak şu dörtlü
kanıt paketiyle girer:

1. **Operator-safe smoke**:
   disposable sandbox / disposable target üzerinde tekrar edilebilir smoke
2. **Failure-mode tests**:
   auth eksik, timeout, deny policy, parse failure, idempotent retry gibi en az
   bir negatif set
3. **Evidence completeness**:
   adapter JSONL, workflow events ve nihai artifact şekli denetlenebilir
4. **Docs/runtime parity**:
   support tier dokümanda açık ve runtime davranışıyla uyumlu

## Slice Çıktıları

1. Aday adapter seti tek kaynağa bağlanmış olur
2. `WP-8.2` ve `WP-8.3` için sıralama netleşir
3. `WP-9` öncesi hangi ops/runbook boşluklarının adapter-certification'a bağlı
   olduğu görünür hale gelir

## Sonraki Dilimler

1. `WP-8.2` — `claude-code-cli` operator-safe smoke + failure-mode baseline
2. `WP-8.3` — `gh-cli-pr` certification kararı: safe smoke lane mi, yoksa beta
   tier'de kalacak açık boundary mi?
3. `WP-8.4` — public capability/support matrix hizası

## Deferred

- gerçek vendor-bazlı otomatik CI smoke
- non-bundled custom adapter'ların sertifikasyonu
- multi-vendor scoring/comparison UI
