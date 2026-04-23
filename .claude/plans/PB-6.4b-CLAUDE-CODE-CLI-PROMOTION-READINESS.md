# PB-6.4b — Claude Code CLI Lane Promotion Readiness (Decision Slice)

**Status:** Active (decision)  
**Date:** 2026-04-23  
**Parent:** `PB-6.4`  
**Parent issue:** [#263](https://github.com/Halildeu/ao-kernel/issues/263)  
**Active issue:** [#267](https://github.com/Halildeu/ao-kernel/issues/267)

## Amaç

`claude-code-cli` lane'i için "operator-managed beta" seviyesinden
promotion-candidate değerlendirmesine geçip geçemeyeceğini, yalnız kanıt ve
risk kapılarıyla karar altına almak.

## Kapsam

1. Lane-specific promotion checklist (minimum kanıt seti)
2. Failure-mode matrisi ve recovery kararları
3. Known bugs (`KB-001`, `KB-002`) etkisinin decision logic'e bağlanması
4. Karar çıktısı: `stay_beta` veya `promotion_candidate`

## Kapsam Dışı

1. Runtime widening implementation açmak
2. `PUBLIC-BETA` support tier satırını bu slice içinde doğrudan yükseltmek
3. Adapter invocation/policy davranışı değiştirmek

## Canlı Baseline Kanıtı (Bu tur)

Komut:

`python3 scripts/claude_code_cli_smoke.py --output json`

Gözlem (2026-04-23):

1. `overall_status = pass`
2. `version`, `auth_status`, `prompt_access`, `manifest_invocation` adımları
   geçti
3. `api_key_env_present = false` (session auth lane aktif)

Not:

Bu başarı tek başına promotion kararı üretmez; known-bug etkisi ve tekrar
edilebilirlik kapıları ayrıca aranır.

## Promotion Readiness Checklist (Draft)

Her madde için durum `pass/fail/inconclusive` olarak işaretlenecek:

1. **Binary + auth baseline**
   - `claude --version` geçmeli
   - `claude auth status` geçmeli
2. **Canlı prompt erişimi**
   - `claude -p` smoke geçmeli
3. **Manifest invocation**
   - bundled manifest ile smoke invocation geçmeli
4. **Known-bug etkisi**
   - `KB-001`/`KB-002` için güncel durum + workaround doğrulaması yazılı olmalı
5. **Support parity**
   - `PUBLIC-BETA`, `SUPPORT-BOUNDARY`, `KNOWN-BUGS` aynı tier dilini konuşmalı
6. **Repeatability gate**
   - en az 2 bağımsız çalıştırmada smoke başarısı veya deterministik fail
     pattern'i kanıtlanmalı

## Failure-Mode Matrisi (Draft)

| Failure mode | Etki | Karar |
|---|---|---|
| `auth_status` pass ama `prompt_access` fail (`KB-001` sınıfı) | Yanlış güven | `stay_beta`; known-bug güncellemesi zorunlu |
| Fallback token route `Invalid bearer token` (`KB-002`) | Recovery zayıf | `stay_beta`; session-auth zorunlu notu korunur |
| Manifest invocation fail, prompt smoke pass | Lane kısmi | `stay_beta`; adapter contract/parsing incelemesi açılır |
| Tüm smoke adımları tekrar edilebilir şekilde pass | Risk düşer | Promotion-candidate değerlendirmesi açılabilir (otomatik promotion değil) |

## Karar Çıkışı Şablonu

Bu slice kapanışında yalnız bir karar üretilecek:

1. `stay_beta`:
   - gerekçe: hangi gate(ler) eksik
   - sonraki adım: dar fix tranche veya ek evidence turu
2. `promotion_candidate`:
   - gerekçe: tüm gate'ler nasıl karşılandı
   - sonraki adım: support widening implementation için ayrı dar tranche

## DoD

1. Checklist + failure-mode matrisi finalize edilmiş
2. Bu tur canlı smoke çıktısı decision girdisi olarak yazılmış
3. `KB-001`/`KB-002` etkisi karar metninde açık
4. Tekil karar çıktısı ve bir sonraki adım net
