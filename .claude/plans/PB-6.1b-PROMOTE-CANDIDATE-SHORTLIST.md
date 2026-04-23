# PB-6.1b — promote candidate shortlist

**Durum tarihi:** 2026-04-23
**İlişkili issue:** [#249](https://github.com/Halildeu/ao-kernel/issues/249)
**Üst slice:** [#245](https://github.com/Halildeu/ao-kernel/issues/245)
**Program:** [#243](https://github.com/Halildeu/ao-kernel/issues/243)
**Durum:** Closeout drafted

## Amaç

`PB-6.1b`'nin işi, `PB-6.1` karar tablosundaki üç `promote candidate`
extension arasından widening sırasını belirsizlik bırakmadan seçmektir.

Bu slice şu soruya cevap verir:

> "Hangi aday ilk runtime widening hattını hak ediyor, hangisi ikinci sırada
> beklemeli ve hangisi bugün `not now` olarak tutulmalı?"

Bu slice **promotion uygulamaz**; yalnız shortlist ve sıra kararı üretir.

## Aday Kümesi

1. `PRJ-CONTEXT-ORCHESTRATION`
2. `PRJ-KERNEL-API`
3. `PRJ-RELEASE-AUTOMATION`

## Girdi Kanıtları

1. `.claude/plans/PB-6.1-EXTENSION-TRUTH-RATIONALIZATION.md`
   - extension-bazlı karar tablosu
   - bucket ayrımı
   - aday başına sinyal kümeleri
2. `.claude/plans/PB-6.1a-RETIRE-DEAD-REFERENCE-CONFIRMATION.md`
   - retire/archive tarafının netleşmiş olması
3. canlı baseline
   - `python3 -m ao_kernel doctor`
   - `python3 scripts/claude_code_cli_smoke.py --output json`
   - `python3 scripts/gh_cli_pr_smoke.py --output json`

## İlk Canlı Sinyal

İlk repo taraması sonunda üç aday için başlangıç resmi şöyledir:

| Aday | Canlı sinyal | İlk okuma |
|---|---|---|
| `PRJ-CONTEXT-ORCHESTRATION` | `truth=quarantined`, `runtime_handler_registered=false`, `remap=5`, `missing=4`, güçlü ops/UI yüzeyi var; yaşayan iz daha çok `ao_kernel/context/*` + default policy/schema katmanında | stratejik olarak güçlü ama blast radius geniş; bounded widening için önce gerçek runtime owner çizgisi netleşmeli |
| `PRJ-KERNEL-API` | `truth=quarantined`, `runtime_handler_registered=false`, `remap=3`, `missing=5`; repo içinde yaşayan `ao_kernel/_internal/prj_kernel_api/*` kodu ve yoğun test izi var | ilk bakışta en somut promotion adayı; canlı kod en yakın burada görünüyor |
| `PRJ-RELEASE-AUTOMATION` | `truth=quarantined`, `runtime_handler_registered=false`, `remap=4`, `missing=6`; policy/schema ve ops yüzeyi var ama manifestte işaret edilen `src/prj_release_automation/release_engine.py` repo içinde yok | repo yönüyle hizalı ama immediate runtime promotion adayı olmaktan çok governance/ops contract adayı gibi duruyor |

Bu tablo **nihai shortlist değildir**; yalnız ilk kanıt turunun working
hypothesis'ini yazar.

## Sıkı Karşılaştırma Kanıtı

### Ortak gerçek

Canlı doğrulama:

```bash
python3 -m ao_kernel doctor
```

Sonuç:

1. `8 OK, 1 WARN, 0 FAIL`
2. `runtime_backed=1`
3. `quarantined=18`
4. tek runtime-backed bundled extension hâlâ `PRJ-HELLO`

Handler kontratı:

1. `ao_kernel/extensions/bootstrap.py` otomatik discovery yapmıyor.
2. Bundled runtime promotion için explicit handler kaydı gerekiyor.
3. `_DEFAULT_HANDLERS` bugün yalnız `PRJ-HELLO` içeriyor.
4. İlk aktif dispatch yüzeyi `kernel_api_actions`; `ops` yüzeyleri için aynı
   derecede dar ve hazır handler kontratı yok.

Bu nedenle "manifestte entrypoint var" tek başına promotion kanıtı değildir.
Promotion adayı, explicit handler + bounded smoke + docs boundary kurmaya en
yakın yüzey olmalıdır.

### Aday karşılaştırması

| Aday | Runtime yakınlığı | Handler/smoke kurulabilirliği | Blast radius | Hüküm |
|---|---|---|---|---|
| `PRJ-KERNEL-API` | En güçlü. Repo içinde `ao_kernel/_internal/prj_kernel_api/*` altında 15 Python modülü ve public `ao_kernel.llm`/client kullanım izi var. | En düşük riskli. Mevcut dispatch modeli zaten `kernel_api_actions` için tasarlanmış; manifestteki 5 action bounded handler smoke'a çevrilebilir. | Düşük/orta. İlk promotion yalnız action registration + read-only smoke ile sınırlandırılabilir. | **first / promote-now candidate** |
| `PRJ-CONTEXT-ORCHESTRATION` | Güçlü ama dağınık. `ao_kernel/context/*` altında yaşayan kod ve çok sayıda test var; fakat manifestteki ops/UI entrypoint'ler doğrudan hazır dispatch yüzeyine bağlanmıyor. | Orta/yüksek riskli. Önce `ops` handler kontratı veya context-specific action mapping netleşmeli. | Yüksek. Context yüzeyi session, memory, retrieval ve orchestration katmanlarına yayılıyor. | **second / later candidate** |
| `PRJ-RELEASE-AUTOMATION` | Zayıf. Policy/schema var, fakat manifestte işaret edilen `src/prj_release_automation/release_engine.py` bugünkü repoda yok. | Zayıf. Runtime module ve handler owner önce kurulmadan smoke anlamlı olmaz. | Orta. Repo governance yönüyle hizalı ama extension promotion bugünkü runtime gerçeğini aşırı genişletir. | **hold / not-now** |

### Ek sayısal sinyal

İlk tarama sayımları:

1. `PRJ-KERNEL-API`
   - `ao_kernel/_internal/prj_kernel_api`: 15 Python modülü
   - ilgili test izi: 22 test dosyası
   - manifest: `kernel_api_actions=5`, `ops=0`
2. `PRJ-CONTEXT-ORCHESTRATION`
   - `ao_kernel/context`: 18 Python modülü
   - ilgili test izi: 55 test dosyası
   - manifest: `ops=9`, `ops_single_gate=2`, `ui_surfaces=2`
3. `PRJ-RELEASE-AUTOMATION`
   - dedicated runtime module: yok
   - manifest: `ops=6`, `ui_surfaces=2`
   - canlı iz: default policy/schema ve repo governance süreci; extension
     runtime kodu değil

## Karar Soruları

### `PRJ-CONTEXT-ORCHESTRATION`

1. Bugünkü repoda gerçekten owner atanabilecek yaşayan runtime yüzeyi var mı?
2. Mevcut debt daha çok remap/policy/test ref temizliği mi, yoksa handler
   eksikliği mi?
3. Bu aday önce seçilirse `PB-6.2` ve `PB-6.3` için blast radius kabul
   edilebilir mi?

### `PRJ-KERNEL-API`

1. `ao_kernel/_internal/prj_kernel_api/*` kodu bounded bir promotion hattı için
   yeterli çekirdeği sağlıyor mu?
2. Minimal handler registration + action smoke paketi diğer adaylardan daha mı
   düşük riskli?
3. Operator-facing support boundary en temiz burada mı kurulabilir?

### `PRJ-RELEASE-AUTOMATION`

1. Repo yönüyle hizası güçlü olsa da extension promotion için runtime yüzey
   gerçekten mevcut mu?
2. Bu aday widening yerine governance/docs karakteri ağır basan bir yüzey mi?
3. Promotion seçilirse rollback ve operator prerequisites net biçimde
   taşınabilir mi?

## Karar Ekseni

Her aday şu eksenlerde kıyaslanacak:

1. **Runtime yakınlığı:** yaşayan kod, handler'a yakınlık, invocation yüzeyi
2. **Owner sinyali:** repo yönü, sorumluluk sınırı, operator anlamlılığı
3. **Kanıt kurulabilirliği:** bounded smoke/test/docs boundary kurulabilir mi?
4. **Blast radius:** yanlış sırada seçildiğinde geri dönüş maliyeti
5. **Bağımlılık yükü:** `PB-6.2` ve `PB-6.3` sırasını ne kadar zorlar?

## Beklenen Çıktı

1. `first / second / hold` formatında ranked shortlist
2. Her aday için kısa ama savunulabilir `promote-now / later / not-now`
   gerekçesi
3. Shortlist sonucunun `PB-6.2` ve `PB-6.3` sırasını nasıl etkilediği
4. Status SSOT ve issue yüzeyinin bu kararla hizalanması

## Kapsam Dışı

1. Runtime handler implementasyonu
2. Support boundary widening
3. Adapter certification veya yeni smoke ekleme
4. `retire/archive` kararını yeniden açma

## Kabul Kriteri

1. Üç adayın hiçbiri "genel his" ile değil, repo içi kanıtla sıralanmış olacak.
2. Çıktı sonunda widening için tek bir "ilk aday" açıkça seçilmiş olacak.
3. `PB-6.2` ve `PB-6.3` için hangi adayın hangi sırayı tetiklediği yazılı
   hale gelecek.
4. Yaşayan status dosyası bu slice'ı aktif iş olarak gösterecek.

## Closeout Kararı

### Ranked shortlist

| Sıra | Aday | Karar | Gerekçe |
|---|---|---|---|
| `first` | `PRJ-KERNEL-API` | `promote-now candidate` | yaşayan internal runtime kodu, mevcut `kernel_api_actions` dispatch modeli ve bounded action smoke kurulabilirliği diğer adaylardan daha güçlü |
| `second` | `PRJ-CONTEXT-ORCHESTRATION` | `later candidate` | canlı context kodu güçlü fakat manifest ops/UI yüzeyi geniş; önce handler/owner sınırı ve remap planı netleşmeli |
| `hold` | `PRJ-RELEASE-AUTOMATION` | `not-now` | repo governance yönüyle hizalı ama dedicated runtime module yok; promotion bugün gerçek runtime yüzeyini olduğundan büyük gösterir |

### Sonraki hat etkisi

`PB-6.1b` sonucu provisional `PB-6.2`/`PB-6.3` sırasını daraltır:

1. Sıradaki runtime widening hattı `PRJ-KERNEL-API` olmalıdır.
2. İlk implementasyon slice'ı support claim'i genişletmemeli; yalnız
   `PRJ-KERNEL-API` için promotion criteria, handler boundary ve smoke
   tasarımını yazmalıdır.
3. `PRJ-CONTEXT-ORCHESTRATION`, `PRJ-KERNEL-API` hattı kapandıktan sonra ayrı
   remap/owner slice'ına girmelidir.
4. `PRJ-RELEASE-AUTOMATION`, dedicated runtime module veya explicit owner
   çıkana kadar hold kalmalıdır.

### DoD durumu

1. Üç aday repo içi kanıtla sıralandı.
2. İlk widening adayı açıkça `PRJ-KERNEL-API` seçildi.
3. İkinci aday `PRJ-CONTEXT-ORCHESTRATION`, hold adayı
   `PRJ-RELEASE-AUTOMATION` olarak kaydedildi.
4. Bu closeout runtime behavior değiştirmez; yalnız sıradaki expansion hattını
   seçer.
