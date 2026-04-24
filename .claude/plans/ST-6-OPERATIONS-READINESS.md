# ST-6 — Operations Readiness

**Durum:** Implementation PR active via
[#351](https://github.com/Halildeu/ao-kernel/issues/351)
**Umbrella:** [#329](https://github.com/Halildeu/ao-kernel/issues/329)
**Precondition:** `ST-5` completed via
[#350](https://github.com/Halildeu/ao-kernel/pull/350).

## 1. Amaç

Stable `4.0.0` release candidate öncesi dar shipped runtime baseline'ın
işletilebilir olduğunu doğrulamak. Bu gate runtime feature eklemez; operator'ın
kurulum, smoke, rollback, publish ve incident durumlarında ne yapacağını tek
anlamlı hale getirir.

## 2. Kapsam

| Yüzey | Karar sorusu | Kaynak |
|---|---|---|
| Incident runbook | Shipped baseline ve beta lane incident ayrımı açık mı? | `docs/OPERATIONS-RUNBOOK.md` |
| Rollback | Package rollback, fix-forward ve support boundary ilişkisi açık mı? | `docs/ROLLBACK.md` |
| Upgrade | Beta/stable install ve validation komutları doğru mu? | `docs/UPGRADE-NOTES.md` |
| Support boundary | Stable shipped, beta, deferred, known bugs ayrımı tutarlı mı? | `docs/SUPPORT-BOUNDARY.md`, `docs/PUBLIC-BETA.md` |
| Known bugs | Stable shipped blocker status açık mı? | `docs/KNOWN-BUGS.md` |
| Release gates | Required checks, packaging smoke ve publish verify yazılı mı? | `.github/workflows/*`, roadmap docs |

## 2.1 Implementation Decision

ST-6 implementation PR'i runtime feature eklemez. Karar:

1. Operator incident akışı `OPERATIONS-RUNBOOK.md` içinde command-first hale
   getirilecek.
2. Rollback dokümanı merge, failed publish, bad published package, yank ve
   beta-only regression kararlarını ayıracak.
3. Upgrade dokümanı release doğrulamasında editable install yerine fresh venv
   exact package install ve `scripts/packaging_smoke.py` kullanacağını yazacak.
4. `KNOWN-BUGS.md` stable shipped blocker sorusunu release gate olarak açık
   soracak.
5. `SUPPORT-BOUNDARY.md` operational readiness'ın support boundary'yi
   genişletmediğini yazacak.

No support widening, no stable tag, no publish.

## 3. Kapsam Dışı

- Stable `4.0.0` tag veya PyPI publish.
- Support widening.
- Real-adapter production certification.
- Live-write rollback rehearsal.

## 4. DoD

`ST-6` tamamlandığında:

1. Operator install/demo/doctor/policy/package/publish failure için ilk
   bakacağı dokümanı ve komutu biliyor.
2. Rollback/yank/fix-forward seçenekleri support boundary ile çelişmiyor.
3. Known bugs registry stable shipped baseline etkisini açık yazıyor.
4. Required checks ve packaging smoke release readiness yüzeyinde temsil
   ediliyor.
5. `ST-7` stable release candidate açılmadan önce kalan operasyonel blocker
   yok veya açıkça stable dışı.

## 5. Validation Plan

Contract PR:

```bash
git diff --check
```

Readiness implementation PR:

```bash
git diff --check
python3 -m ao_kernel doctor
python3 scripts/packaging_smoke.py
```
