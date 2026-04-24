# GP-2.3 — Post-Stable Adapter Certification Entry Decision

**Status:** Active
**Date:** 2026-04-24
**Tracker:** [#361](https://github.com/Halildeu/ao-kernel/issues/361)
**Parent:** `.claude/plans/GP-2-DEFERRED-SUPPORT-LANES-REPRIORITIZATION.md`

## Amaç

`v4.0.0` stable runtime live olduktan sonra ilk support-widening giriş
kapısını seçmek. Bu slice runtime implementasyonu değildir; support boundary
genişletmez, yeni stable adapter claim'i üretmez ve release/publish işi
yapmaz.

## Başlangıç Gerçeği

1. `v4.0.0` stable PyPI üzerinde canlıdır.
2. Dar stable runtime claim geçerlidir: package install, entrypoint'ler,
   `doctor`, `review_ai_flow + codex-stub`, policy command enforcement ve
   packaging smoke kanıtlıdır.
3. Genel amaçlı production coding automation platform claim'i hâlâ açık
   değildir; gerçek adapter sertifikasyonu ve live-write rollback kanıtları
   olmadan kullanılmayacaktır.
4. `claude-code-cli` ve `gh-cli-pr` repo tarafından kurulan binary'ler değildir;
   operator ortamındaki PATH/auth prerequisite'lerine dayanır.
5. `codex-stub` repo-native deterministic stub'dır; production adapter olarak
   sınıflandırılmayacaktır.

## Aday Giriş Kapıları

| Aday | Varsayılan karar | Gerekçe | Ana risk |
|---|---|---|---|
| `ST-3` `claude-code-cli` read-only real-adapter certification | **Now** | gerçek adapter hattı, live-write side effect yok, operator tercihi Claude Code CLI yönünde | auth/session drift, operator prerequisite, failure-mode evidence |
| `ST-4` `gh-cli-pr` live-write rollback rehearsal | **Next** | write-side production iddiası için zorunlu kapı | remote side effect, disposable sandbox, rollback/idempotency |
| extension/support widening | **Later** | platform yüzeyini genişletir | inventory genişliği, dead-ref/partial-ref drift, overclaim riski |

## Karar

İlk post-stable implementation/verification hattı
`claude-code-cli` read-only real-adapter certification olacaktır.

Bu karar `claude-code-cli` lane'ini stable shipped veya production-certified
yapmaz. Bir sonraki slice yalnız sertifikasyon kanıt paketini çıkarır ve
sonuç şu üç karardan birine bağlanır:

1. `production_certified_read_only`
2. `operator_managed_beta_keep`
3. `stay_deferred`

## Bir Sonraki Slice İçin Minimum Contract

`claude-code-cli` certification slice'ı açılmadan önce kontrat şu soruları
tek tek cevaplamalıdır:

1. Operator prerequisite: `claude` PATH binary, auth/session ve prompt access
   nasıl doğrulanır?
2. Workflow path: hangi governed workflow read-only smoke olarak koşar?
3. Evidence completeness: run/step/event kayıtlarında hangi alanlar zorunlu?
4. Failure-mode matrix: missing binary, auth fail, timeout, non-zero exit,
   malformed output ve policy deny nasıl yüzeye çıkar?
5. Retry/cancel/idempotency: read-only lane için hangi davranışlar required,
   hangileri not-applicable?
6. Support boundary: lane geçse bile docs hangi tier'e yükselir veya neden
   beta/deferred kalır?

## Out of Scope

- Runtime support widening.
- Live-write PR creation.
- `gh-cli-pr` remote side-effect execution.
- Extension promotion.
- Version bump, tag, publish veya release.

## Definition of Done

1. `GP-2` roadmap `GP-2.2`yi active göstermiyor.
2. Status SSOT `GP-2.3` issue/contract'ını aktif karar slice'ı olarak
   gösteriyor.
3. `Now / Next / Later` sırası yazılı:
   - Now: `claude-code-cli` read-only real-adapter certification
   - Next: `gh-cli-pr` live-write rollback rehearsal
   - Later: extension/support widening
4. Stable support boundary unchanged kalıyor.
5. Bir sonraki slice için uygulanacak contract soruları açık.

## Kanıt Komutları

Bu slice docs/status-only olduğu için runtime smoke zorunlu değildir.
Minimum doğrulama:

```bash
python3 scripts/truth_inventory_ratchet.py --output json
python3 -m pytest -q tests/test_cli_entrypoints.py tests/test_doctor_cmd.py
```
