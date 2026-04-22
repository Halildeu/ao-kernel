# PB-4 — support-surface widening decisions

**Durum tarihi:** 2026-04-22
**İlişkili issue:** [#232](https://github.com/Halildeu/ao-kernel/issues/232)
**Üst tracker:** [#219](https://github.com/Halildeu/ao-kernel/issues/219)
**Durum:** In progress

## Amaç

Post-beta correctness hattında bir sonraki karar noktası, support surface'i
gerçekten widen edip etmeyeceğimizi kanıt bazlı belirlemektir. Bu slice yeni
runtime özelliği eklemek için değil; shipped / beta / deferred sınırını canlı
smoke, docs parity ve operator prerequisite doğrulaması ile karar seviyesine
indirmek için vardır.

## Başlangıç Gerçeği

Bugünkü ana gerçek:

1. shipped baseline hâlâ bundled `review_ai_flow` + bundled `codex-stub`
   yoludur
2. `claude-code-cli` lane'i helper-backed, operator-managed beta durumundadır
3. `gh-cli-pr` lane'i helper-backed dry-run preflight durumundadır; gerçek
   remote PR açılışı bugün support claim değildir
4. `docs/PUBLIC-BETA.md`, `docs/ADAPTERS.md`, `docs/SUPPORT-BOUNDARY.md`,
   `docs/OPERATIONS-RUNBOOK.md` ve `docs/UPGRADE-NOTES.md` bu ayrımı tek
   anlamlı söylemelidir

Bu slice'ın işi, bu başlangıç gerçeğini ya kanıtla widen etmek ya da bilinçli
olarak aynı sınırda tutup nedenini yazılı hale getirmektir.

## Bu Slice'ın Sınırı

- `claude-code-cli` helper-backed beta lane için canlı smoke doğrulaması
- `gh-cli-pr` helper-backed preflight lane için canlı smoke doğrulaması
- `gh-cli-pr` tam E2E PR açılışının promote edilebilir olup olmadığının kararı
- support boundary dokümanlarının tek anlamlı hale getirilmesi
- widen edilmeyen yüzeyler için açık deferred/operator-managed işaretleme

## Kapsam Dışı

- shipped baseline'ı `review_ai_flow + codex-stub` dışına çıkarmak
- yeni adapter runtime capability eklemek
- `cost_usd` / evidence completeness closure
- genel amaçlı production platform iddiasını widen etmek
- `bug_fix_flow` yeniden release closure yüzeyine taşımak

## Karar Kuralları

1. Tekil smoke başarıları support promotion için yeterli değildir.
2. Bir yüzey ancak code path + smoke/e2e + docs parity + operator prerequisite
   anlatımı birlikte tutarlıysa widen edilebilir.
3. Güvenli disposable ortam olmadan gerçek remote PR açılışı support claim
   olamaz.
4. Sonuç yalnızca “promote” değildir; “beta olarak kal”, “defer et” ve
   “operator-managed boundary'yi daha da daralt” da geçerli kararlardır.

## Aday Yüzeyler

### Aday A — `claude-code-cli` helper-backed lane

- Bugünkü durum: Beta (operator-managed)
- Mevcut kanıt aracı: `python3 scripts/claude_code_cli_smoke.py --output text`
- Karar sorusu:
  canlı prompt smoke + bundled manifest contract + operator prerequisite
  anlatımı, bu lane'i bugünkü beta seviyesinde doğruluyor mu; yoksa boundary
  daha da daraltılmalı mı?

### Aday B — `gh-cli-pr` helper-backed preflight lane

- Bugünkü durum: Beta (operator-managed preflight only)
- Mevcut kanıt aracı: `python3 scripts/gh_cli_pr_smoke.py --output text`
- Karar sorusu:
  auth/repo visibility + `gh pr create --dry-run` zinciri, bu lane'in bugün
  beta-preflight olarak kalmasını destekliyor mu?

### Aday C — `gh-cli-pr` tam E2E PR açılışı

- Bugünkü durum: Deferred
- Gerekli ek koşul:
  disposable sandbox repo + side-effect-safe operator runbook + açık rollback
  hikayesi
- Karar sorusu:
  bu koşullar bugün gerçekten mevcut mu; yoksa yüzey açıkça deferred kalmalı mı?

## Tranche Sırası

## İlk Tranche

1. `docs/PUBLIC-BETA.md`, `docs/ADAPTERS.md`, `docs/SUPPORT-BOUNDARY.md`,
   `docs/OPERATIONS-RUNBOOK.md`, `docs/UPGRADE-NOTES.md` üzerinde support-tier
   söylemini yan yana doğrulamak
2. `claude-code-cli` ve `gh-cli-pr` helper komutlarını çalıştırıp canlı smoke
   çıktısını toplamak
3. issue üzerinde “başlangıç gerçeği” notunu kanıtla kaydetmek

## İkinci Tranche

1. `claude-code-cli` lane'i için operator prerequisite / known bug / smoke
   başarısı arasındaki tutarlılığı değerlendirmek
2. eğer bugünkü beta sınırı yanlışsa ilgili docs yüzeylerini daraltmak veya
   netleştirmek
3. widen edilmeyecekse bunu açık karar notuna çevirmek

## Üçüncü Tranche

1. `gh-cli-pr` lane'i için preflight-only boundary ile deferred full-E2E
   boundary'yi ayrı ayrı doğrulamak
2. gerçek remote PR açılışının promote edilmesi için gereken disposable sandbox
   ve rollback koşullarını yazılı kontrol listesine çevirmek
3. koşullar eksikse yüzeyi bilinçli olarak deferred bırakmak

## Kabul Kriterleri

1. Her aday yüzey için karar durumu açıktır:
   - promote
   - beta olarak kal
   - deferred
   - boundary daralt
2. Canlı smoke veya eşdeğer yüksek-sinyal kanıt issue/comment veya plan notunda
   referanslanır.
3. `docs/PUBLIC-BETA.md` ve `docs/ADAPTERS.md` başta olmak üzere operator-facing
   yüzeyler aynı support tier'i söyler.
4. `gh-cli-pr` gerçek remote PR açılışı ancak disposable sandbox ve rollback
   yolu açıkça yazıldıysa widening adayı olabilir; aksi halde deferred kalır.

## Beklenen Kanıt Komutları

```bash
python3 scripts/claude_code_cli_smoke.py --output text
python3 scripts/gh_cli_pr_smoke.py --output text
```

Gerekirse karşılaştırma amaçlı shipped baseline doğrulaması:

```bash
python3 examples/demo_review.py --cleanup
```

## Riskler

| Risk | Etki | Önlem |
|---|---|---|
| Tek bir başarılı smoke ile overclaim yapmak | Yüksek | karar kuralı: smoke + docs + prerequisite + safe operation birlikte gerekir |
| Operator-managed lane'i shipped gibi anlatmak | Yüksek | PUBLIC-BETA ve ADAPTERS parity zorunlu |
| Gerçek remote PR açılışını güvenli sandbox olmadan denemek | Yüksek | disposable repo + rollback olmadan E2E promotion yok |
| Support widening işi scope creep ile runtime feature işine dönmek | Orta | slice boundary dışı maddeleri açık dışarıda tut |

## Beklenen Sonraki Adım

İlk tranche ile canlı smoke kanıtını tazelemek ve support-tier dokümanlarının
tek anlamlı olup olmadığını yeniden doğrulamaktır.
