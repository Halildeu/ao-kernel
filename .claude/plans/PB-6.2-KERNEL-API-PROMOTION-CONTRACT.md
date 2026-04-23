# PB-6.2 — PRJ-KERNEL-API minimum runtime-backed promotion contract

**Durum tarihi:** 2026-04-23
**İlişkili issue:** [#251](https://github.com/Halildeu/ao-kernel/issues/251)
**Üst program:** [#243](https://github.com/Halildeu/ao-kernel/issues/243)
**Önceki karar:** `PB-6.1b` / [#250](https://github.com/Halildeu/ao-kernel/pull/250)
**Durum:** Active

## Amaç

`PB-6.2`'nin işi, `PRJ-KERNEL-API` için minimum runtime-backed promotion
contract'ını yazmaktır.

Bu slice runtime behavior değiştirmez. Çıktısı, sonraki implementasyon PR'ının
neyi yapıp neyi yapmayacağını netleştiren dar bir promotion contract'tır.

## Başlangıç Gerçeği

`PB-6.1b` kararı:

1. `first`: `PRJ-KERNEL-API`
2. `second`: `PRJ-CONTEXT-ORCHESTRATION`
3. `hold`: `PRJ-RELEASE-AUTOMATION`

Canlı extension truth:

```bash
python3 -m ao_kernel doctor
```

Bugünkü beklenen özet:

1. `runtime_backed=1`
2. `quarantined=18`
3. runtime-backed bundled extension yalnız `PRJ-HELLO`

`PRJ-KERNEL-API` bugün:

1. `truth=quarantined`
2. `runtime_handler_registered=false`
3. `remap=3`
4. `missing=5`
5. manifestte `kernel_api_actions=5`

## Promotion İçin Zorunlu Kapanış

`PRJ-KERNEL-API` ancak şu koşullar birlikte sağlanırsa runtime-backed
sayılabilir:

1. Explicit bundled handler kaydı eklenecek.
   - Tek doğru yol: `ao_kernel/extensions/bootstrap.py`
   - Handler modülü: `ao_kernel/extensions/handlers/prj_kernel_api.py`
   - Otomatik discovery, entry point veya manifest-driven import yok.
2. Manifest support yüzeyi dar ve doğru olacak.
   - İlk tranche tüm 5 action'ı promote etmeyecek.
   - Minimum action set yalnız read-only ve bounded action'lardan oluşacak.
3. Missing runtime refs sıfırlanacak.
   - `docs_ref` bugünkü repo içinde gerçekten var olan bir docs anchor'a
     taşınacak.
   - `ai_context_refs` içindeki legacy `src/prj_kernel_api/adapter.py` ref'i
     ya yaşayan `ao_kernel/_internal/prj_kernel_api/*` yüzeyine remap edilecek
     ya da kaldırılacak.
   - `tests_entrypoints` absent `extensions/PRJ-KERNEL-API/tests/*` yoluna
     bakmayacak; yaşayan test dosyasına veya yeni bounded smoke testine
     bağlanacak.
4. Test/smoke behavior-first olacak.
   - Sadece `registered_count` veya `result is not None` yeterli değil.
   - Action ownership, returned payload, side-effect boundary ve truth summary
     birlikte pinlenecek.

## Minimum Action Set

İlk runtime-backed tranche için action set:

| Action | Karar | Gerekçe |
|---|---|---|
| `system_status` | include | read-only, operator-facing, mevcut policy/schema yüzeylerinde merkezi |
| `doc_nav_check` | include | read-only, bounded smoke için uygun, side effect gerektirmez |
| `project_status` | defer | read-only olabilir, fakat project/workspace artifact sözleşmesi ayrı netleşmeli |
| `roadmap_follow` | defer | roadmap workflow semantiği ve state beklentisi daha geniş |
| `roadmap_finish` | defer | roadmap/write-side kapanış semantiği nedeniyle ilk promotion için fazla geniş |

Bu karar, manifestteki 5 action iddiasını ilk implementation PR'ında 2 action'a
daraltmayı gerektirir. Desteklenmeyen action'lar registry'de görünmemelidir.

## Handler Contract

İlk handler modülü şu sınırla yazılmalı:

1. `EXTENSION_ID = "PRJ-KERNEL-API"`
2. `register(registry)` yalnız şu action'ları register eder:
   - `system_status`
   - `doc_nav_check`
3. Handler callables tek parametre alır:
   - `params: dict[str, Any]`
4. Handler çıktısı stable dict envelope döndürür:
   - `ok`
   - `action`
   - `extension_id`
   - `result`
5. Handler offline ve deterministic olur.
6. Handler workspace write yapmaz.
7. Handler live provider, network veya secret gerektirmez.

## Smoke/Test Contract

Sonraki implementation PR'ı en az şu testleri içermeli:

1. `default_handler_extension_ids()` içinde `PRJ-KERNEL-API` görünür.
2. `register_default_handlers()` sonrası action registry şu action'ları çözer:
   - `system_status`
   - `doc_nav_check`
3. Bu iki action'ın owner'ı `PRJ-KERNEL-API` olur.
4. Handler invocation deterministic payload döndürür.
5. Defer edilen action'lar register edilmez:
   - `project_status`
   - `roadmap_follow`
   - `roadmap_finish`
6. `ExtensionRegistry().load_from_defaults().get("PRJ-KERNEL-API")` için:
   - `runtime_handler_registered=true`
   - `missing_runtime_refs=()`
   - `truth_tier="runtime_backed"`
7. `python3 -m ao_kernel doctor` hedef metriği:
   - `runtime_backed=2`
   - `quarantined=17`
   - `runtime_backed_ids` içinde `PRJ-HELLO`, `PRJ-KERNEL-API`

## Docs Boundary Contract

Support docs ancak implementation PR'ında şu cümleyle genişletilebilir:

> `PRJ-KERNEL-API` runtime-backed olarak yalnız `system_status` ve
> `doc_nav_check` action'ları için desteklenir.

Şunlar açıkça deferred kalır:

1. `project_status`
2. `roadmap_follow`
3. `roadmap_finish`
4. live provider-backed LLM calls
5. write-side roadmap automation

## Sonraki Implementation PR Scope

Bir sonraki PR'ın dar kapsamı:

1. `ao_kernel/extensions/handlers/prj_kernel_api.py`
2. `ao_kernel/extensions/bootstrap.py`
3. `ao_kernel/defaults/extensions/PRJ-KERNEL-API/extension.manifest.v1.json`
4. targeted handler/loader tests
5. docs support boundary update

Kapsam dışı:

1. `PRJ-CONTEXT-ORCHESTRATION`
2. `PRJ-RELEASE-AUTOMATION`
3. `ops` dispatch surface
4. write-side roadmap actions
5. real adapter certification

## Kabul Kriteri

Bu planning slice tamamlandığında:

1. minimum action set yazılı hale gelmiş olacak
2. handler/smoke/docs boundary net olacak
3. sonraki implementation PR'ın dosya kapsamı ve DoD'si belli olacak
4. support widening'in hangi cümleyle yapılacağı ve hangi action'ların
   deferred kalacağı açık olacak
