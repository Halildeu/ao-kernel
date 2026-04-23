# PB-6 — general-purpose expansion gap map

**Durum tarihi:** 2026-04-23
**İlişkili issue:** [#243](https://github.com/Halildeu/ao-kernel/issues/243)
**Üst tracker:** [#219](https://github.com/Halildeu/ao-kernel/issues/219)
**Durum:** In progress

## Amaç

`ao-kernel` bugün dar ama kanıtlı bir Public Beta support surface'e sahiptir.
`PB-6`'nın amacı bu support boundary'yi hemen widen etmek değildir; dar
baseline ile genel amaçlı production coding automation platform iddiası
arasındaki gerçek boşlukları kanıt bazlı haritalamaktır.

Bu slice şu soruya cevap vermelidir:

> "Bugünkü repo, hangi somut eksikler nedeniyle hâlâ general-purpose
> production-grade platform değildir ve bu eksikler hangi sırayla kapanmalıdır?"

## Başlangıç Gerçeği

Bugünkü measured baseline:

1. `docs/PUBLIC-BETA.md` ve `docs/SUPPORT-BOUNDARY.md` narrow shipped baseline
   tanımlar:
   - module entrypoint'ler
   - `ao-kernel doctor`
   - bundled `review_ai_flow` + bundled `codex-stub`
   - `examples/demo_review.py`
   - packaging smoke
2. Real-adapter lane'ler bugün helper-backed ve operator-managed durumdadır.
3. Bundled extension / adapter / registry inventory'si runtime-backed support
   claim ile aynı şey değildir.
4. General-purpose platform iddiası için yalnız adapter binary varlığı veya tek
   makinede geçen smoke yeterli değildir.

## Canlı Baseline Kanıtı

**Audit tarihi:** 2026-04-23

Çalıştırılan komutlar:

```bash
python3 -m ao_kernel doctor
python3 scripts/claude_code_cli_smoke.py --output json
python3 scripts/gh_cli_pr_smoke.py --output json
```

Özet:

1. `python3 -m ao_kernel doctor`
   - `8 OK, 1 WARN, 0 FAIL`
   - `runtime_backed=1`
   - `contract_only=0`
   - `quarantined=18`
   - `remap_candidate_refs=69`
   - `missing_runtime_refs=161`
   - tek runtime-backed bundled extension: `PRJ-HELLO`
2. `python3 scripts/claude_code_cli_smoke.py --output json`
   - `overall_status="pass"`
   - binary / auth / prompt_access / manifest_invocation check'leri geçti
3. `python3 scripts/gh_cli_pr_smoke.py --output json`
   - `overall_status="pass"`
   - binary / auth / manifest_contract / repo_view / `gh pr create --dry-run`
     check'leri geçti

Hüküm:

1. Operator helper lane'ler bugün canlı smoke verebiliyor.
2. Buna rağmen repo hâlâ general-purpose production platform değildir; çünkü
   runtime-backed support yüzeyi çok dardır ve inventory'nin büyük kısmı
   quarantined durumdadır.

## Bu Slice'ın Sınırı

- general-purpose readiness için gap sınıflandırması
- support widening önkoşullarının yazılı hale gelmesi
- bundled inventory, real-adapter workflow ve write-side orchestration
  boşluklarının tek tabloda görünür kılınması
- ordered tranche backlog üretmek

## Kapsam Dışı

- doğrudan support boundary widening
- `PB-6` içinde gerçek adapter lane promotion'ı tek PR'da gerçekleştirmek
- deferred `bug_fix_flow` benzeri eski correctness işlerini yeniden açmak
- yalnız doc güzelleştirme yapmak ama ölçülebilir gap tanımlamamak

## Gap Haritası

| Gap bucket | Bugünkü kanıt | Açık boşluk | Production-grade için gereken |
|---|---|---|---|
| Extension/runtime truth gap | `doctor` yalnız `PRJ-HELLO`yu runtime-backed görüyor; `quarantined=18` | Bundled inventory'nin çoğu runtime-backed değil, remap/missing ref debt yüksek | extension bazlı promote / quarantine / retire kararı + ölçülebilir truth target |
| Real-adapter workflow graduation gap | `claude-code-cli` helper smoke yeşil | helper smoke workflow-driven support kanıtı değildir | end-to-end workflow smoke, failure-mode matrisi, support docs promotion kararı |
| Write-side / PR orchestration gap | `gh-cli-pr` dry-run smoke yeşil | gerçek remote PR opening hâlâ deferred; disposable sandbox/rollback contract dar | side-effectful PR lane için bounded E2E kanıt ve rollback güvencesi |
| Support boundary vs contract inventory gap | docs boundary dürüst, ama inventory çok geniş | operator bir manifest gördüğünde onu destekli yüzey sanabilir | contract inventory ile supported surface arasında daha sert sınıflandırma ve mapping |
| Ops / incident / rollback widening gap | narrow baseline runbook mevcut | widened surface'ler için incident class, rollback, auth expiry, secret hygiene operasyonu eksik | operator lane bazlı runbook + known-bug + rollback + exit criteria paketleri |

## İlk Verdict

`PB-6` için en kritik açık bugün feature eksikliği değil, **bundled inventory ile
gerçek runtime-backed surface arasındaki açıklığın büyüklüğüdür**.

Bu nedenle doğru ilk tranche:

1. extension/runtime truth gap'i sayısal ve extension-bazlı bir tabloya indirmek
2. ardından yalnız gerçekten canlı smoke taşıyan adapter/workflow lane'ler için
   graduation kriterlerini yazmak
3. en son write-side ve ops widening kararlarına geçmek

## Önerilen Tranche Sırası

### `PB-6.1` Extension truth rationalization

Amaç:

1. Bundled extension inventory'yi `runtime_backed / contract_only / quarantined`
   yanında eylem odaklı sınıflara indirmek:
   - promote candidate
   - quarantine-keep
   - remap-needed
   - retire/dead-reference
2. `doctor` WARN yüzeyini yalnız sayım değil, karar girdisi haline getirmek

DoD:

1. bundled extension bazlı karar tablosu
2. hangi extension'ların PB-6 içinde promotion adayı bile olmadığı yazılı
3. quarantine azaltma veya explicit quarantine kabulü için sayısal hedef

### `PB-6.2` Real-adapter workflow graduation criteria

Amaç:

1. `claude-code-cli` helper smoke ile gerçek workflow-backed support claim
   arasındaki farkı kapatmak için gereken kanıt setini yazmak
2. benchmark full-mode, helper smoke, workflow smoke ve shipped demo
   yüzeylerini karıştırmamak

DoD:

1. `claude-code-cli` için promotion checklist
2. failure-mode matrisi
3. support-tier promotion için minimum smoke/test/doc şartları

### `PB-6.3` Write-side / PR lane graduation criteria

Amaç:

1. `gh-cli-pr` dry-run preflight'tan gerçek remote PR opening'e geçişin
   önkoşullarını netleştirmek
2. disposable sandbox, rollback ve side-effect boundary'sini yazmak

DoD:

1. safe preflight ile live write lane arasındaki sınır net
2. remote PR opening için rollback ve evidence koşulları yazılı

### `PB-6.4` Support mapping hardening

Amaç:

1. contract inventory'deki yüzeylerin support-tier mapping'ini daha sert hale
   getirmek
2. doctor/report/docs aynı sınıfları konuşsun

DoD:

1. inventory-to-support mapping tablosu
2. dead-reference veya aspirational manifest confusion riski düşürülmüş

### `PB-6.5` Ops readiness for widened lanes

Amaç:

1. widened lane'ler için incident / rollback / known-bug / auth-expiry
   işletme paketini tanımlamak

DoD:

1. widened lane operator runbook exit criteria
2. support widening sonrası incident handling boşluğu kalmıyor

## Başarı Kriterleri

1. `PB-6` sonunda "general-purpose readiness" lafı soyut kalmaz; her gap somut
   kanıta bağlanır.
2. Her bundled yüzey için "neden bugün supported değil?" sorusuna kısa yazılı
   cevap vardır.
3. Sonraki runtime slice'lar rastgele değil, ordered tranche backlog'tan çıkar.
4. Support widening kararı helper smoke veya manifest varlığına indirgenmez.

## `PB-6.1` Başlatma Notu

`PB-6.1` bu slice altında aktif alt hat olarak başlatıldı:

- plan: `.claude/plans/PB-6.1-EXTENSION-TRUTH-RATIONALIZATION.md`
- issue: [#245](https://github.com/Halildeu/ao-kernel/issues/245)

İlk karar:

1. `PRJ-HELLO` dışındaki 18 extension tek blok olarak ele alınmayacak
2. bucket ayrımı artık yazılı:
   - `promote candidate`
   - `remap-needed`
   - `quarantine-keep`
   - `retire/dead-reference candidate`
3. `PB-6` içindeki sonraki widening kararı, `PB-6.1` karar tablosu olmadan
   alınmayacak

## Aktif Durum Notu (2026-04-23)

Bu dosya `PB-6` için başlangıç gap map ve tranche tasarımını taşır.
Canlı yürütme sırası bundan sonra aşağıdaki SSOT'tan takip edilir:

- `.claude/plans/POST-BETA-CORRECTNESS-EXPANSION-STATUS.md`

Özet:

1. `PB-6.1a`, `PB-6.1b`, `PB-6.2`, `PB-6.2b`, `PB-6.3`, `PB-6.3b` tamamlandı.
2. `PB-6.4` karar/ordering slice tamamlandı (issue: [#263](https://github.com/Halildeu/ao-kernel/issues/263)).
3. `PB-6.4c` ve `PB-6.4d` karar dilimleri tamamlandı:
   - `PB-6.4c`: `stay_preflight` ([#271](https://github.com/Halildeu/ao-kernel/issues/271))
   - `PB-6.4d`: `stay_deferred` ([#270](https://github.com/Halildeu/ao-kernel/issues/270))
4. `PB-6.4` karar/ordering contract:
   `.claude/plans/PB-6.4-REAL-ADAPTER-WRITE-SIDE-GRADUATION-ORDER-CONTRACT.md`
5. Yeni aktif alt hat `PB-6.5`:
   - issue: [#275](https://github.com/Halildeu/ao-kernel/issues/275)
   - plan: `.claude/plans/PB-6.5-OPS-READINESS-FOR-WIDENED-LANES.md`
