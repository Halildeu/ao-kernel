# PB-6.1a — retire/dead-reference confirmatory pass

**Durum tarihi:** 2026-04-23
**İlişkili issue:** [#247](https://github.com/Halildeu/ao-kernel/issues/247)
**Üst slice:** [#245](https://github.com/Halildeu/ao-kernel/issues/245)
**Durum:** In progress

## Amaç

`PB-6.1` içinde retire/dead-reference adayı olarak işaretlenen dört extension'ın
bu hükmü gerçekten hak edip etmediğini dosya seviyesinde teyit etmek.

Bu slice şu soruya cevap verir:

> "Bu dört extension için bundled inventory'de kalmayı savunacak canlı runtime
> karşılığı var mı, yoksa archive/retire kararı artık yazılı olarak
> savunulabilir mi?"

## Hedefler

1. `PRJ-EXECUTORPORT`
2. `PRJ-MEMORYPORT`
3. `PRJ-SEARCH`
4. `PRJ-UI-COCKPIT-LITE`

## Canlı Kanıt Paketi

**Audit tarihi:** 2026-04-23

Kullanılan komutlar:

```bash
python3 -m ao_kernel doctor
python3 - <<'PY'
from ao_kernel.extensions.loader import ExtensionRegistry
...
PY
rg -n "PRJ-(EXECUTORPORT|MEMORYPORT|SEARCH|UI-COCKPIT-LITE)|..."
```

Ortak bulgular:

1. Dördü de `truth=quarantined` ve `runtime_handler_registered=False`.
2. Dördünün `docs_ref` hedefi olan `docs/OPERATIONS/EXTENSIONS.md` bugünkü
   repoda mevcut değildir.
3. Default handler registry bugün yalnız `PRJ-HELLO` içerir; bu dört yüzey için
   explicit handler yoktur.
4. Dört surface de ağırlıklı olarak eski `extensions/*` veya `src/orchestrator/*`
   yollarına bakmaktadır.

## Confirmatory Findings

| Extension | Canlı sinyal | Hüküm | Gerekçe |
|---|---|---|---|
| `PRJ-EXECUTORPORT` | `entrypoints=0`, `ui=0`, `missing=9`, missing refs eski `src/orchestrator/executor_*` ve absent `extensions/PRJ-EXECUTORPORT/tests/*` yoluna gidiyor | Confirmed retire/archive candidate | köprü manifesti kalmış; bugünkü repo içinde ne ops yüzeyi ne runtime handler ne de yaşayan docs/test karşılığı var |
| `PRJ-MEMORYPORT` | `entrypoints=0`, `ui=0`, `missing=9`, missing refs eski `src/orchestrator/memory/*` port katmanına gidiyor | Confirmed retire/archive candidate | legacy memory bridge kabuğu dışında canlı karşılık görünmüyor; bundled defaults'ta kalması support confusion üretiyor |
| `PRJ-SEARCH` | `ops=['search-check']`, ama runtime code/test/readme absent; `extensions/PRJ-SEARCH/*` ve `PRJ-UI-COCKPIT-LITE/keyword_search.py` yok | Confirmed retire/archive candidate | isim olarak canlı görünse de manifestin dayandığı repo yüzeyi yok; başka stale UI yüzeyine bağımlı |
| `PRJ-UI-COCKPIT-LITE` | `cockpit_lite` UI/ops iddiası var, fakat README/server ve 24+ test yolu absent; `missing=29` | Confirmed retire/archive candidate | en ağır stale yük burada; manifested UI surface bugünkü repo gerçeğinde taşınmıyor |

## Neden Downgrade Etmedik

Bu dört extension için "quarantine-keep" veya "remap-needed"e dönüş
gerekçesi çıkmadı çünkü:

1. missing refs'in çoğu taşınmış ama bulunabilir dosyalara değil, doğrudan
   bugünkü ağaçta karşılığı olmayan eski repo segmentlerine bakıyor
2. explicit runtime handler yok
3. support doc anchor'ları bile yok
4. en az ikisinde (`PRJ-EXECUTORPORT`, `PRJ-MEMORYPORT`) entrypoint/UI yüzeyi
   tamamen boş

## Karar

`PB-6.1a` hükmü:

1. Dört hedef de **confirmed retire/archive candidate** olarak kalır.
2. Bunlar için near-term runtime promotion veya support widening hattı
   açılmamalıdır.
3. Sonraki mantıklı hareket ya:
   - bundled defaults / registry içinde görünürlüklerini azaltacak archive planı,
     ya da
   - explicit owner çıkana kadar açıkça archived-candidate statüsü vermektir.

## Beklenen Sonraki Adım

`PB-6.1a` sonrasındaki doğru sıra:

1. `PB-6.1b` promote candidate shortlist
2. `PRJ-CONTEXT-ORCHESTRATION`, `PRJ-KERNEL-API`, `PRJ-RELEASE-AUTOMATION`
   arasından ilk gerçek runtime promotion adayını seçmek
