# PB-6.1 — extension truth rationalization

**Durum tarihi:** 2026-04-23
**İlişkili issue:** [#245](https://github.com/Halildeu/ao-kernel/issues/245)
**Üst slice:** [#243](https://github.com/Halildeu/ao-kernel/issues/243)
**Durum:** In progress

## Amaç

`PB-6.1`'in işi, bundled extension inventory için "hepsi quarantine" gibi kaba
bir resim yerine extension-bazlı karar yüzeyi üretmektir.

Bu slice şu soruya cevap verir:

> "Her bundled extension bugün neden runtime-backed değildir ve bundan sonra
> promote, remap, quarantine veya retire hattına mı gitmelidir?"

## Canlı Baseline

**Audit tarihi:** 2026-04-23

Ölçüm girdileri:

```bash
python3 -m ao_kernel doctor
python3 - <<'PY'
from ao_kernel.extensions.loader import ExtensionRegistry
reg = ExtensionRegistry(); reg.load_from_defaults()
for ext in sorted(reg.list_all(), key=lambda e: e.extension_id):
    ...
PY
```

Özet:

1. `doctor` sonucu:
   - `runtime_backed=1`
   - `quarantined=18`
   - `remap_candidate_refs=69`
   - `missing_runtime_refs=161`
2. `ao_kernel.extensions.bootstrap.default_handler_extension_ids()`
   bugün yalnız `PRJ-HELLO` döndürüyor.
3. Geri kalan bütün bundled extension'lar explicit runtime handler'sız ve
   çeşitli seviyelerde stale ref/remap debt taşıyor.

## Karar Rubriği

### `promote candidate`

Bu bucket yalnız şunu söyler:

1. surface stratejik olarak bugünkü repo yönüyle hizalı
2. entrypoint/UI/policy yüzeyi anlamlı
3. debt yüksek olsa bile "ölü yüzey" değildir; dedicated runtime slice'ı hak eder

Bu bucket support widening anlamına gelmez.

### `remap-needed`

Bu bucket şu durumda kullanılır:

1. extension kavramsal olarak hâlâ relevant görünür
2. bugünkü blokajın büyük kısmı path drift / moved schema / moved policy /
   stale repo layout debt'idir
3. support tartışmasından önce ref normalization gerekir

### `quarantine-keep`

Bu bucket şu durumda kullanılır:

1. surface tamamen silinecek kadar anlamsız değildir
2. ama near-term runtime promotion için yeterli sahipliği/kanıtı yoktur
3. registry'de kalabilir, fakat quarantine dışına çıkarma planı yoktur

### `retire/dead-reference candidate`

Bu bucket şu durumda kullanılır:

1. extension'ın aktif runtime karşılığı görünmez
2. no-op köprü/port/UI kabuğu gibi davranır
3. missing refs çoğunlukla eski repo yapısına veya artık taşınmayan dosyalara
   işaret eder

Bu bucket da otomatik silme değildir; fakat bundled inventory'de kalmasının
gerekçesi ayrıca ispat edilmelidir.

## Bucket Özeti

| Bucket | Sayı | Extension'lar |
|---|---:|---|
| already runtime-backed | 1 | `PRJ-HELLO` |
| promote candidate | 3 | `PRJ-CONTEXT-ORCHESTRATION`, `PRJ-KERNEL-API`, `PRJ-RELEASE-AUTOMATION` |
| remap-needed | 7 | `PRJ-AIRUNNER`, `PRJ-DEPLOY`, `PRJ-GITHUB-OPS`, `PRJ-PLANNER`, `PRJ-PM-SUITE`, `PRJ-UX-NORTH-STAR`, `PRJ-WORK-INTAKE` |
| quarantine-keep | 4 | `PRJ-ENFORCEMENT-PACK`, `PRJ-M0-MAINTAINABILITY`, `PRJ-OBSERVABILITY-OTEL`, `PRJ-ZANZIBAR-OPENFGA` |
| confirmed retire/archive candidate | 4 | `PRJ-EXECUTORPORT`, `PRJ-MEMORYPORT`, `PRJ-SEARCH`, `PRJ-UI-COCKPIT-LITE` |

## Extension Bazlı Karar Tablosu

### Already runtime-backed baseline

| Extension | Sinyal | Karar |
|---|---|---|
| `PRJ-HELLO` | `truth=runtime_backed`, `remap=0`, `missing=0`, explicit handler var | referans baseline; PB-6.1 kapsamında yeniden sınıflandırılmayacak |

### Promote candidate

| Extension | Sinyal | Karar gerekçesi | Sonraki gate |
|---|---|---|---|
| `PRJ-CONTEXT-ORCHESTRATION` | `entrypoints=12`, `ui_surfaces=2`, `remap=5`, `missing=4` | orchestration yüzeyi hâlâ merkezi; debt büyük ölçüde taşınmış policy/schema/test referanslarında | runtime owner + ref repair sonrası dedicated promotion slice |
| `PRJ-KERNEL-API` | `kernel_api_actions=5`, `remap=3`, `missing=5`, repo içinde `ao_kernel/_internal/prj_kernel_api/*` kodu mevcut | runtime karşılığına en yakın extension'lardan biri; stale test/docs refs var ama yüzey ölü değil | handler registration + action smoke + docs boundary kararı |
| `PRJ-RELEASE-AUTOMATION` | `ops=6`, `ui_surfaces=2`, `remap=4`, `missing=6` | repo’nun release/governance yönüyle hizalı; support widening’e aday bir ops yüzeyi | release ops runtime owner + bounded smoke + rollback pack |

### Remap-needed

| Extension | Sinyal | Karar gerekçesi | Öncelikli iş |
|---|---|---|---|
| `PRJ-AIRUNNER` | `remap=9`, `missing=7`, policy dosyalarında çok sayıda `suggested_extension` referansı var | stratejik olarak canlı ama repo taşınması nedeniyle ağır drift taşıyor | policies/schemas/src path normalization |
| `PRJ-DEPLOY` | `remap=8`, `missing=7`, deploy ops ve UI yüzeyi var | kavramsal yüzey korunmuş, fakat implementasyon referansları dağılmış | deploy contract refs ve runtime module hedeflerinin yeniden eşlenmesi |
| `PRJ-GITHUB-OPS` | `remap=6`, `missing=8`, work-intake policy parçalarında sıkça öneriliyor | canlı orkestrasyon değeri var ama current repo layout ile eşleşmiyor | manifest/docs/src ref temizliği |
| `PRJ-PLANNER` | `remap=4`, `missing=7`, ops yüzeyi mevcut ama Airunner bağımlı stale refs içeriyor | tek başına promote edilemez; önce komşu dependency drift'i kapanmalı | planner-airunner dependency remap'i |
| `PRJ-PM-SUITE` | `remap=8`, `missing=9`, contract/policy dosyaları hâlâ repo policy'lerinde geçiyor | contract var, runtime sahipliği yok; debt önce ref tarafında | contract path normalization + owner kararı |
| `PRJ-UX-NORTH-STAR` | `remap=5`, `missing=7`, policy/schema referansları taşınmış | ideolojik/contract değeri var ama runtime yüzey yok | contract asset remap + scope daraltma kararı |
| `PRJ-WORK-INTAKE` | `remap=5`, `missing=8`, `entrypoints=9`, aktif policy parçaları bunu işaret ediyor | bugünkü repo yönü için önemli, fakat build/check script refs stale | modular policy/tooling ref repair |

### Quarantine-keep

| Extension | Sinyal | Karar gerekçesi | Şimdilik tutum |
|---|---|---|---|
| `PRJ-ENFORCEMENT-PACK` | `missing=13`, `remap=3`, no handler | cross-cutting fikir var ama near-term promotion kanıtı yok | quarantine'de kalsın; owner çıkmadan promote tartışılmasın |
| `PRJ-M0-MAINTAINABILITY` | `missing=7`, `remap=1`, internal CI hygiene paketi | dış support surface değil; shipped product widening için yanlış aday | quarantine'de kalsın, runtime promotion hedeflenmesin |
| `PRJ-OBSERVABILITY-OTEL` | `missing=12`, `remap=3`, no entrypoint/ui | observability önemli ama bundled extension olarak canlı runtime iz düşümü zayıf | quarantine'de kalsın; önce concrete handler/ops planı gerekir |
| `PRJ-ZANZIBAR-OPENFGA` | `missing=5`, `remap=1`, entrypoint yok | mimari/roadmap izi var fakat aktif runtime surface yok | quarantine'de kalsın; security/domain owner olmadan widen edilmesin |

### Confirmed retire / archive candidate

| Extension | Sinyal | Karar gerekçesi | Sonraki karar |
|---|---|---|---|
| `PRJ-EXECUTORPORT` | `entrypoints=0`, `ui=0`, `missing=9`, missing refs eski `src/orchestrator/*` portlarına gidiyor | köprü kabuğu kalmış, bugünkü repo yönünde canlı yüzey görünmüyor | archive veya bundled defaults dışına çıkarma kararı |
| `PRJ-MEMORYPORT` | `entrypoints=0`, `ui=0`, `missing=9`, eski `src/orchestrator/memory/*` port refs | legacy bridge gibi davranıyor; runtime promotion gerekçesi yok | archive veya retire değerlendirmesi |
| `PRJ-SEARCH` | `missing=9`, `remap=0`, `extensions/PRJ-SEARCH/*` ve `PRJ-UI-COCKPIT-LITE/keyword_search.py` gibi absent dosyalara bağlı | kendi canlı runtime'ı yok; başka stale UI yüzeyine bağımlı | retire adayı; ancak explicit owner çıkarsa yeniden açılır |
| `PRJ-UI-COCKPIT-LITE` | `missing=29`, `remap=0`, büyük absent UI/server/test ağacı | en yüksek stale yük; bundled inventory'de en zayıf canlılık sinyali | archive/dead-reference doğrulama turu açılmalı |

## `PB-6.1a` Confirmatory Pass

`PB-6.1a` bu slice altında hedefli olarak çalıştırıldı:

- plan: `.claude/plans/PB-6.1a-RETIRE-DEAD-REFERENCE-CONFIRMATION.md`
- issue: [#247](https://github.com/Halildeu/ao-kernel/issues/247)

Teyit sonucu:

1. `PRJ-EXECUTORPORT`
2. `PRJ-MEMORYPORT`
3. `PRJ-SEARCH`
4. `PRJ-UI-COCKPIT-LITE`

bu tur sonunda **confirmed retire/archive candidate** olarak kaldı.

Ortak kanıt:

1. dördünün de `docs_ref` hedefi bugünkü repoda yok
2. explicit runtime handler yok
3. ref setleri ağırlıkla absent `extensions/*` veya eski `src/orchestrator/*`
   katmanına bakıyor
4. downgrade gerektirecek canlı runtime eşdeğeri bulunmadı

## İlk Hüküm

1. General-purpose readiness'i bugün en çok yavaşlatan şey "çok extension var"
   olması değil; **hangi extension'ın neden hâlâ quarantine'de olduğu
   bilinmeden** inventory'nin bundled kalmasıdır.
2. `PRJ-HELLO` dışındaki 18 extension aynı muameleyle ele alınmamalıdır.
3. Bir sonraki doğru hareket hepsine runtime yazmak değil; önce
   `promote candidate` grubundan hangisinin gerçekten owner + smoke + handler
   hattına gireceğini seçmektir.

## Önerilen Sonraki Sıra

1. `PB-6.1b` promote candidate shortlist kararı
   - `PRJ-CONTEXT-ORCHESTRATION`
   - `PRJ-KERNEL-API`
   - `PRJ-RELEASE-AUTOMATION`
2. Bu shortlist'ten sonra ancak `PB-6.2`/`PB-6.3` widening slice'ları
   güvenli sıraya konabilir
