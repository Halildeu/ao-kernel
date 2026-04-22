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

## İlk Tranche — Canlı Kanıt Tazelemesi

**Koşu tarihi:** 2026-04-22

Çalıştırılan komutlar:

```bash
python3 scripts/claude_code_cli_smoke.py --output text
python3 scripts/gh_cli_pr_smoke.py --output text
```

Özet sonuç:

1. `claude-code-cli` helper smoke: `pass`
   - `claude --version`: geçti
   - `claude auth status`: geçti
   - canlı `claude -p` prompt access: geçti
   - bundled manifest invocation smoke: geçti
2. `gh-cli-pr` helper smoke: `pass`
   - `gh --version`: geçti
   - `gh auth status --json hosts`: geçti
   - bundled manifest contract smoke: geçti
   - `gh repo view`: geçti
   - `gh pr create --dry-run`: geçti

İlk tranche kararı:

1. Bugünkü canlı kanıt, `docs/PUBLIC-BETA.md` ve `docs/ADAPTERS.md` içinde
   yazan dar boundary ile uyumludur.
2. `claude-code-cli` lane'i bugün için **Beta (operator-managed)** statüsünde
   kalabilir; daraltma gerektiren bir smoke bulgusu oluşmadı.
3. `gh-cli-pr` lane'i bugün için **Beta (operator-managed preflight only)**
   statüsünde kalabilir; helper smoke yalnız dry-run preflight'i doğruladı.
4. `gh-cli-pr` tam E2E remote PR açılışı için hâlâ ayrı disposable sandbox +
   rollback kanıtı yok; bu yüzey **Deferred** kalır.

İlk tranche sonucu olarak docs üzerinde zorunlu boundary düzeltmesi gerekmedi;
bir sonraki doğru adım ikinci tranche ile `claude-code-cli` lane'inin operator
prerequisite / known bug / smoke tutarlılığını karar notuna çevirmektir.

## İkinci Tranche

1. `claude-code-cli` lane'i için operator prerequisite / known bug / smoke
   başarısı arasındaki tutarlılığı değerlendirmek
2. eğer bugünkü beta sınırı yanlışsa ilgili docs yüzeylerini daraltmak veya
   netleştirmek
3. widen edilmeyecekse bunu açık karar notuna çevirmek

## İkinci Tranche — `claude-code-cli` Karar Notu

**Karar tarihi:** 2026-04-22

İncelenen yüzeyler:

1. `docs/PUBLIC-BETA.md`
2. `docs/ADAPTERS.md`
3. `docs/SUPPORT-BOUNDARY.md`
4. `docs/OPERATIONS-RUNBOOK.md`
5. `docs/KNOWN-BUGS.md`
6. `docs/BENCHMARK-REAL-ADAPTER-RUNBOOK.md`
7. ilk tranche canlı smoke kanıtı:
   `python3 scripts/claude_code_cli_smoke.py --output text`

Karar:

1. `claude-code-cli` yüzeyi bugün için **Beta (operator-managed)** olarak
   kalır; shipped baseline'a promote edilmez.
2. Bu kararın nedeni smoke başarısızlığı değil, support boundary disiplinidir:
   helper smoke geçse bile bu lane hâlâ operator-managed prerequisite'lere ve
   hesap/organizasyon erişimine bağlıdır.
3. `claude auth status` tek başına yeterli sağlık sinyali değildir.
   Belirleyici sinyal yalnız helper'ın gerçek `claude -p` prompt access ve
   bundled manifest invocation sonucudur.
4. Varsayılan auth yolu **Claude Code session auth** olarak kalır.
   Env-token fallback (`ANTHROPIC_API_KEY` / `CLAUDE_API_KEY`) support widening
   gerekçesi sayılmaz.
5. `KB-001` ve `KB-002` bu yüzden açık kalır:
   - `KB-001`: auth-status yeşil olsa da gerçek prompt access bloklu olabilir
   - `KB-002`: uzun ömürlü token fallback güvenilir recovery yolu değildir

Bugünkü tutarlılık hükmü:

1. `PUBLIC-BETA.md` satırı doğru: helper-backed preflight + canlı prompt smoke
   vardır, ama varsayılan shipped demo değildir.
2. `ADAPTERS.md` satırı doğru: current tier `Beta (operator-managed)` ve
   beklenen prerequisite session auth'tur.
3. `KNOWN-BUGS.md` ile runbook uyumludur: smoke `pass` sonucu bug'ları
   silmez; yalnız bugünkü operatör ortamında lane'in çalıştığını gösterir.
4. Zorunlu bir docs daraltması veya tier düzeltmesi gerekmedi.

İkinci tranche sonucu:

1. `claude-code-cli` lane'i için yazılı karar artık nettir:
   smoke pass + session auth sağlıklı ise lane kullanılabilir, fakat support
   claim hâlâ Beta/operator-managed sınırındadır.
2. Bu lane shipped baseline'a widen edilmemiştir.
3. Sonraki doğru adım üçüncü tranche ile `gh-cli-pr` preflight-only boundary ve
   deferred full-E2E remote PR açılışını ayrı karar notuna çevirmektir.

## Üçüncü Tranche

1. `gh-cli-pr` lane'i için preflight-only boundary ile deferred full-E2E
   boundary'yi ayrı ayrı doğrulamak
2. gerçek remote PR açılışının promote edilmesi için gereken disposable sandbox
   ve rollback koşullarını yazılı kontrol listesine çevirmek
3. koşullar eksikse yüzeyi bilinçli olarak deferred bırakmak

## Üçüncü Tranche — `gh-cli-pr` Karar Notu

**Karar tarihi:** 2026-04-22

İncelenen yüzeyler:

1. `docs/PUBLIC-BETA.md`
2. `docs/ADAPTERS.md`
3. `docs/SUPPORT-BOUNDARY.md`
4. `docs/ROLLBACK.md`
5. `scripts/gh_cli_pr_smoke.py`
6. `ao_kernel.real_adapter_smoke.run_gh_cli_pr_smoke(...)`
7. ilk tranche canlı smoke kanıtı:
   `python3 scripts/gh_cli_pr_smoke.py --output text`

Karar:

1. `gh-cli-pr` helper-backed lane bugün için **Beta (operator-managed
   preflight only)** olarak kalır.
2. Bunun nedeni helper smoke'un gerçek remote PR açmaması ve bunu özellikle
   yapmamasıdır:
   - helper `gh pr create --dry-run` kullanır
   - helper bundled manifest dışından `--repo`, `--head`, `--base`, `--dry-run`
     ekler
   - doğruladığı şey auth, repo visibility ve CLI contract'tır; gerçek remote
     side effect değildir
3. `gh-cli-pr` tam E2E remote PR açılışı bugün için **Deferred** kalır.
4. Bu deferred kararının nedeni yalnız smoke eksikliği değil; güvenli operator
   prosedür eksikliğidir:
   - disposable sandbox clone kullanımı ayrı belgelenmiş support runbook'u
     seviyesinde pinli değildir
   - `docs/ROLLBACK.md` paket ve source-repo rollback'ini anlatır, fakat yanlış
     açılmış remote PR'ı kapatma / temizleme / repo-side cleanup akışını
     tanımlamaz
   - bu yüzden yanlış bir live smoke, uzak GitHub durumunda yan etki
     bırakabilir

Bugünkü tutarlılık hükmü:

1. `PUBLIC-BETA.md` satırı doğru: helper-backed lane preflight-only'dir,
   gerçek remote PR açmaz.
2. `ADAPTERS.md` satırı doğru: current tier `Beta (operator-managed preflight
   only)` ve tam live PR açılışı ayrı deferred yüzeydir.
3. `SUPPORT-BOUNDARY.md` satırı doğru: helper-backed dry-run lane beta,
   live `gh-cli-pr` PR opening deferred kabul edilir.
4. `ROLLBACK.md` bugünkü shipped baseline için yeterlidir, fakat remote PR
   cleanup runbook'u olmadığı için full-E2E promotion için tek başına yeterli
   değildir.

Üçüncü tranche sonucu:

1. `gh-cli-pr` için yazılı karar artık nettir:
   - dry-run helper smoke = beta preflight kanıtı
   - gerçek remote PR açılışı = deferred
2. Full-E2E promotion önkoşulları da nettir:
   - disposable sandbox clone prosedürü
   - remote PR cleanup / close / recovery runbook'u
   - bu akışın canlı operator kanıtı
3. Bu tranche sonunda zorunlu docs düzeltmesi çıkmadı; mevcut boundary anlatısı
   bugünkü kanıtla tutarlı kaldı.
4. `PB-4` teknik olarak closeout-ready duruma gelmiştir; ayrı closeout/issue
   kapanış turu ile tamamlanabilir.

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

`PB-4` closeout değerlendirmesi yapıp issue/status yüzeyinde tamamlandı
işaretlemek; ardından `PB-5` adapter-path cost/evidence completeness hattına
geçmektir.
