# WP-8.2 — `claude-code-cli` Smoke + Failure-Mode Baseline

**Durum tarihi:** 2026-04-22
**İlişkili issue:** [#199](https://github.com/Halildeu/ao-kernel/issues/199)
**Üst WP:** [#199](https://github.com/Halildeu/ao-kernel/issues/199)

## Amaç

`WP-8.1` ile aday seti netleştikten sonra ilk gerçek adapter lane'ini
çalıştırılabilir backlog'a indirmek. Bu slice'ın amacı `claude-code-cli`
adapter'ı production diye ilan etmek değil; hangi smoke'un güvenli, hangi
failure-mode setinin zorunlu ve hangi canlı blokajların hâlâ açık olduğunu tek
kaynakta toplamak.

## Bu Slice'ın Sınırı

- odak yalnız `claude-code-cli`
- canlı vendor erişimi gerektiren "gerçek başarılı smoke" ile
  auth/environment drift'i birbirine karıştırmamak
- production-tier etiketi vermemek; önce certification baseline'ı çıkarmak
- `gh-cli-pr` ve diğer adapter lane'lerini bu slice'a taşımamak

## Bugünkü Durum

| Alan | Durum | Not |
|---|---|---|
| Bundled manifest | var | aday gerçek adapter olarak tanımlı |
| Operator-safe smoke | **var (ilk cut)** | `python3 scripts/claude_code_cli_smoke.py` ile version/auth/prompt/manifest preflight somutlaştı |
| Failure-mode testleri | **var (guncel)** | binary yok, auth deny, manifest CLI mismatch ve temiz pass senaryolari testte pinli |
| Docs/runtime parity | kısmi | support boundary henüz public capability matrix'e çevrilmedi |
| Release gate | yok | smoke CI-required değil |

## Somutlaştırılan Yüzey

1. **Repo helper**
   - `scripts/claude_code_cli_smoke.py`
   - çıktılar: `text` veya `json`
   - exit code: bütün zorunlu check'ler `pass` ise `0`, aksi halde `1`
2. **Kod mantığı**
   - `ao_kernel/real_adapter_smoke.py`
   - binary / version / auth status / prompt access / manifest smoke sınıflandırması
3. **Davranış testleri**
   - `tests/test_claude_code_cli_smoke.py`
   - binary missing
   - prompt access denied
   - manifest CLI contract mismatch
   - clean pass
4. **Contract pinleri**
   - `tests/test_adapter_manifest_loader.py`
   - bundled manifest version + invocation argv yüzeyi pinli

## Canlı Bulunan Blokajlar

Bu makinedeki 2026-04-22 canlı kontrolde repo tarafındaki
`manifest_cli_contract_mismatch` kapatıldı. Güncel blocker:

1. `prompt_access_denied`
   - `claude auth status` logged-in görünmesine rağmen `claude -p` çağrısı
     "Your organization does not have access to Claude" ile fail ediyor
   - bundled manifest smoke da artık aynı noktada bloklanıyor; parser/argv
     uyuşmazlığı kalmadı

## Çıkarılacak Baseline Paketi

1. **Smoke sözleşmesi**
   - `python3 scripts/claude_code_cli_smoke.py`
   - success kriteri: `overall_status=pass`
   - network/auth gereksinimi: prompt-access smoke ile binary-only varlıktan ayrılır
2. **Failure-mode matrisi**
   - CLI binary missing
   - auth erişimi yok
   - manifest CLI contract mismatch
   - policy deny
   - timeout / non-zero exit
   - parse/evidence bozulması
3. **Evidence paketi**
   - workflow events
   - adapter JSONL / stderr/stdout yüzeyi
   - nihai artifact beklentisi
4. **Boundary notu**
   - bu lane geçmeden `claude-code-cli` production-tier değildir

## İlk Kabul Kriterleri

Bu slice tamamlandı sayılabilmek için en az şu çıktılar görünür olmalı:

1. `claude-code-cli` için operator-safe smoke komutu ve başarı kriteri yazılı
2. En az dört failure-mode senaryosu açıkça listelenmiş ve test/repro hedefi
   bağlanmış
3. Hangi senaryoların lokal/dev-only, hangilerinin CI-uygun olduğu ayrılmış
4. Public support boundary'yi genişletmeden status dokümanı güncellenmiş
5. Repo tarafındaki manifest/CLI contract drift'i kapanmış

## Beklenen Sonraki Adımlar

1. auth/access blocker için operator prerequisite ve workaround yolunu netleştirmek
2. disposable workspace üstünde gerçek success smoke elde etmek
3. gerekiyorsa API-key auth rotasını ayrıca doğrulamak
4. `WP-8.3` öncesi `claude-code-cli` lane'inin beta mı, candidate mı
   kalacağına karar

## Deferred

- vendor-backed sürekli CI smoke
- çoklu organizasyon/auth varyantı sertifikasyonu
- rate-limit / quota exhaustion senaryoları
