# WP-8.3 — `gh-cli-pr` Side-Effect-Safe Smoke Baseline

**Durum tarihi:** 2026-04-22
**İlişkili issue:** [#199](https://github.com/Halildeu/ao-kernel/issues/199)
**Üst WP:** [#199](https://github.com/Halildeu/ao-kernel/issues/199)

## Amaç

`WP-8.1` ile aday seti netleştikten ve `WP-8.2` ile `claude-code-cli`
lane'i somutlaştıktan sonra ikinci gerçek adapter hattını güvenli bir
sertifikasyon baseline'ına indirmek. Bu slice `gh-cli-pr` adapter'ını
production diye ilan etmez; gerçek remote PR açmadan hangi preflight'ın
gerekli olduğunu yazılı ve çalıştırılabilir hale getirir.

## Bu Slice'ın Sınırı

- odak yalnız `gh-cli-pr`
- helper side-effect-safe olacak; gerçek remote PR açmayacak
- bundled manifest contract'i ile operator-safe smoke birbirine karışmayacak
- tam canlı E2E PR açılışı bu slice'a alınmayacak

## Bugünkü Durum

| Alan | Durum | Not |
|---|---|---|
| Bundled manifest | var | `gh pr create --title ... --body-file ...` dar contract'i korunuyor |
| Operator-safe smoke | **var (ilk cut)** | `python3 scripts/gh_cli_pr_smoke.py` binary/auth/repo/dry-run preflight'ını topluyor |
| Failure-mode testleri | **var (ilk cut)** | binary missing, auth eksik, repo view fail, dry-run fail, manifest mismatch pinli |
| Docs/runtime parity | kısmi | helper ve boundary `docs/ADAPTERS.md` + status dosyasında hizalandı |
| Release gate | yok | helper CI-required değil; operator-managed lane |

## Somutlaştırılan Yüzey

1. **Repo helper**
   - `scripts/gh_cli_pr_smoke.py`
   - çıktılar: `text` veya `json`
   - exit code: tüm zorunlu check'ler `pass` ise `0`, aksi halde `1`
2. **Kod mantığı**
   - `ao_kernel/real_adapter_smoke.py`
   - `gh` binary / version / auth status / manifest contract / repo view /
     `gh pr create --dry-run` sınıflandırması
3. **Davranış testleri**
   - `tests/test_gh_cli_pr_smoke.py`
   - binary missing
   - auth eksik
   - repo view fail
   - dry-run fail
   - manifest contract mismatch
   - clean pass
4. **Contract pinleri**
   - `tests/test_adapter_manifest_loader.py`
   - bundled manifest command + args + stdin contract'i pinli

## Canlı Durum

Bu makinedeki 2026-04-22 canlı kontrolde şu preflight zinciri doğrulandı:

1. `gh auth status --json hosts`
   - `github.com` host'u için aktif login görünür
2. `gh repo view --json nameWithOwner,defaultBranchRef,isPrivate,url`
   - repo `Halildeu/ao-kernel`
   - varsayılan branch `main`
3. `gh pr create --repo Halildeu/ao-kernel --head main --base main --title ... --body ... --dry-run`
   - side effect olmadan başarıyla döndü

Bu kanıt, helper'ın dayandığı güvenli smoke yolunu doğrular; gerçek PR
açılışı için production-tier sertifikasyon anlamına gelmez.

## Auth ve Güvenlik Duruşu

- varsayılan ve hedeflenen yol: mevcut `gh` oturumu
- helper gerçek PR açmaz; `--dry-run` kullanır
- helper repo/binary/auth görünürlüğünü doğrular ama support boundary'yi
  genişletmez

## İlk Kabul Kriterleri

Bu slice tamamlandı sayılabilmek için en az şu çıktılar görünür olmalı:

1. `gh-cli-pr` için operator-safe smoke komutu ve başarı kriteri yazılı
2. En az dört failure-mode senaryosu testte pinli
3. Bundled manifest contract'i ile helper'ın kullandığı güvenli dry-run yolu
   açıkça ayrılmış
4. Public support boundary genişletilmeden status ve docs hizalanmış

## Beklenen Sonraki Adımlar

1. helper sonucunu capability matrix'e taşımak (`WP-8.4`)
2. tam canlı PR açılışının beta mı yoksa deferred mı kalacağını netleştirmek
3. gerekiyorsa disposable remote hedef üzerinde daha güçlü smoke sözleşmesi
   tanımlamak

## Deferred

- gerçek remote PR oluşturma smoke'u
- otomatik CI'da `gh` auth gerektiren canlı lane
- çoklu repo / çoklu host sertifikasyonu
