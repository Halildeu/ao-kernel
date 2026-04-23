# PB-7.1 — gh-cli-pr Live-Write Readiness Guards

**Status:** Active  
**Date:** 2026-04-23  
**Parent milestone:** Post-Beta Correctness and Expansion  
**Tracker:** [#219](https://github.com/Halildeu/ao-kernel/issues/219)  
**Active issue:** [#281](https://github.com/Halildeu/ao-kernel/issues/281)

## Amaç

`PB-6.4c` kararında `stay_preflight` kalan `gh-cli-pr` lane'i için,
preflight-only sınırı bozulmadan live-write readiness kontratını dar ve
fail-closed bir uygulama dilimine çevirmek.

Bu slice **support boundary widening** yapmak için değil, widening öncesi
eksik kapıları yazılı/testli hale getirmek için açılır.

## Kapsam

1. `scripts/gh_cli_pr_smoke.py` preflight default davranışı korunacak.
2. Live-write probe yalnız explicit opt-in modla çalışacak.
3. Live-write modda disposable workspace/branch guard'ları zorunlu olacak.
4. Başarılı live-write probe için rollback (`gh pr close`) zinciri koşulacak.
5. Probe çıktısı live-write metadata ve rollback sonucunu kanıt olarak taşıyacak.
6. Docs/status yüzeyi lane'in hâlâ `deferred/beta` sınırında olduğunu açık
   yazacak.

## Kapsam Dışı

1. `gh-cli-pr` lane support tier'ını bu slice ile yükseltmek.
2. `bug_fix_flow` support boundary widening.
3. `PRJ-KERNEL-API` write-side action widening.
4. Runtime policy semantiğini (`executor` / `policy_enforcer`) değiştirmek.

## Gate'ler ve DoD

### Gate-1: Preflight parity

- Varsayılan komut (`--mode preflight`) mevcut davranışı aynen korur.
- `tests/test_gh_cli_pr_smoke.py` preflight regresyonu yakalar.

### Gate-2: Opt-in safety

- Live-write mode explicit flag olmadan fail-closed kalır.
- Disposable guard'lar (repo/head/base) sağlanmadan write denemesi yapılmaz.

### Gate-3: Rollback + evidence

- Create başarılıysa close adımı koşar (veya explicit keep-open ile atlanır).
- Report payload'ı create/close durumunu ayrı check'lerde taşır.

### Gate-4: Docs parity

- `PUBLIC-BETA`/`SUPPORT-BOUNDARY` live-write lane'i promoted göstermeyecek.
- Bu slice çıktısı "readiness guard implemented" olarak kayıt altına alınacak.

## Test Paketi

Minimum zorunlu testler:

1. `tests/test_gh_cli_pr_smoke.py` (new live-write unit matrix)
2. `tests/test_cli_entrypoints.py` (no regression smoke)
3. `pytest -q tests/test_gh_cli_pr_smoke.py`

İsteğe bağlı canlı doğrulama (operator-managed):

```bash
python3 scripts/gh_cli_pr_smoke.py --output json
python3 scripts/gh_cli_pr_smoke.py --mode live-write --help
```

## Çıkış Kriteri

1. Kod + test + docs/status aynı gerçeği söyler.
2. Varsayılan preflight yolu backward-compatible kalır.
3. Live-write readiness guard'ları testli ve fail-closed olur.
4. Slice kapanışında issue + PR + test kanıtı status dosyasına işlenir.
