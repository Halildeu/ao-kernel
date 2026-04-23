# ST-5 — Deferred Correctness Closure

**Durum:** Closeout PR active via
[#348](https://github.com/Halildeu/ao-kernel/issues/348)
**Umbrella:** [#329](https://github.com/Halildeu/ao-kernel/issues/329)
**Precondition:** `ST-2` support boundary freeze completed via
[#346](https://github.com/Halildeu/ao-kernel/pull/346) and
[#347](https://github.com/Halildeu/ao-kernel/pull/347).

## 1. Amaç

Stable `4.0.0` kararı öncesi deferred correctness yüzeylerini belirsizlikten
çıkarmak. Bu gate'in varsayılanı support widening değildir; her kalem tam olarak
bir kategoriye düşer:

- `ship`
- `beta`
- `deferred`
- `retire`

## 2. Kapsam

| Kalem | Mevcut tier | ST-5 karar sorusu | Varsayılan eğilim |
|---|---|---|---|
| `bug_fix_flow` release closure | Deferred | Stable shipped baseline'a alınacak kadar kanıtlı mı? | `deferred` veya ayrı runtime closure PR |
| `gh-cli-pr` full E2E remote PR opening | Deferred | Disposable sandbox + rollback olmadan support claim olabilir mi? | `deferred` |
| Roadmap/spec demo live-support | Deferred/spec-only | Canlı demo yüzeyine çevrilecek mi, yoksa spec-only kalacak mı? | `retire` veya `deferred` |
| Adapter-path `cost_usd` public support | Deferred | Internal hook + behavior evidence public support claim için yeterli mi? | Açık promotion kanıtı yoksa `deferred` |
| Yeni shipped-baseline bug | Unknown | Stable blocker mı? | Fix edilene veya scope dışına alınana kadar blocker |

## 2.1 Closeout Decision

ST-5 decision inventory:

| Kalem | Final kategori | Kanıt / gerekçe | Sonraki gate |
|---|---|---|---|
| `bug_fix_flow` release closure | `deferred` | `PB-8.3` ve `GP-1.3` kararları `stay_deferred`; `open_pr` adımı explicit opt-in guard arkasında, ancak disposable/live rollback zinciri stable support kanıtı değil | Ayrı runtime closure + rollback gate gerekir |
| `gh-cli-pr` full E2E remote PR opening | `deferred` | Preflight ve live-write readiness probe operator-managed beta; gerçek remote PR açılışı support claim değil | ST-4 tarzı live-write rollback rehearsal gerekir |
| Roadmap/spec demo live-support | `deferred` / spec-only | `docs/roadmap/DEMO-SCRIPT-SPEC.md` canlı demo kontratı değil; shipped demo `examples/demo_review.py` olarak kalır | Yeni demo yüzeyi istenirse ayrı shipped-smoke PR gerekir |
| Adapter-path `cost_usd` public support | `deferred` | `GP-2.2` runtime/evidence completeness doğrulandı, ama public support boundary genişletilmedi | Public support promotion için docs + behavior + operator evidence PR gerekir |
| Yeni shipped-baseline bug | None known | `docs/KNOWN-BUGS.md` shipped baseline blocker status `none currently known` diyor | Yeni blocker bulunursa stable gate durur |

Sonuç: ST-5 kapsamında stable shipped baseline'a yeni yüzey eklenmedi.
Deferred kalemlerin hiçbiri stable `4.0.0` dar runtime claim'ini bloklamaz,
çünkü `ST-2` boundary bu yüzeyleri stable dışına almıştır.

## 3. Kapsam Dışı

- Real-adapter production certification (`ST-3` parked for support widening).
- Live-write rollback rehearsal (`ST-4` parked for support widening).
- Genel amaçlı production coding automation platform claim'i.
- Stable release tag/publish.

## 4. Karar Kuralı

Bir kalem `ship` yapılmak istenirse aynı PR içinde veya bağlı evidence PR'inde
şunlar gerekir:

1. Runtime/code path açık.
2. Behavior-first test veya smoke mevcut.
3. Docs/support matrix aynı şeyi söylüyor.
4. Upgrade/rollback etkisi yazılı.
5. Known-bugs registry ile çelişki yok.

Bu beşli yoksa kalem `ship` olamaz; `beta`, `deferred` veya `retire` olarak
kapatılır.

## 5. DoD

`ST-5` tamamlandığında:

1. Kapsam tablosundaki her kalem tam olarak bir kategoriye düşer.
2. İki kategoriye birden yazılan support surface kalmaz.
3. Stable shipped baseline'ı bozan açık blocker varsa stable gate durur.
4. Stable dışı kalan her kalemin gerekçesi ve sonraki gate'i yazılıdır.
5. `docs/PUBLIC-BETA.md`, `docs/SUPPORT-BOUNDARY.md`,
   `docs/KNOWN-BUGS.md`, `docs/UPGRADE-NOTES.md` ve `docs/ROLLBACK.md`
   kararlarla uyumludur.

## 6. Riskler

| Risk | Etki | Önlem |
|---|---|---|
| Deferred item'ı kanıtsız stable'a almak | Yüksek | `ship` için beşli evidence rule |
| Runtime closure işini docs-only kapatmak | Orta | Her kalemde karar tipi açık: `ship` değilse support widening yok |
| Live-write yan etkisini yanlışlıkla stable yapmak | Yüksek | ST-4 rollback gate'i olmadan live-write stable olmaz |
| `bug_fix_flow` kapsamının tekrar büyümesi | Orta | Ayrı runtime closure PR gerektir |

## 7. Validation Plan

Contract PR:

```bash
git diff --check
```

Runtime/docs karar PR'i:

```bash
git diff --check
python3 -m pytest -q <touched-targeted-tests>
python3 scripts/packaging_smoke.py  # only if shipped package behavior changes
```
