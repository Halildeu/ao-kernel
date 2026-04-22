# Post-Beta Correctness and Expansion Status

**Durum tarihi:** 2026-04-22
**Amaç:** Public Beta closeout sonrasında kalan correctness debt'ini
fail-closed disiplinle kapatmak, support-surface widening kararlarını kanıtla
yönetmek ve genel amaçlı production çizgisine geçiş için gerçek gap'leri
ayrı ayrı görünür kılmak.
**Yürütme modu:** Kapsam disiplini
**Bu dosyanın rolü:** yaşayan execution backlog + program status SSOT

## 1. SSOT Sınırları

- **Execution status / backlog:** bu dosya
- **Tarihsel closeout snapshot:** `.claude/plans/PRODUCTION-HARDENING-PROGRAM-STATUS.md`
- **Aktif slice planı:** `.claude/plans/PB-4-SUPPORT-SURFACE-WIDENING-DECISIONS.md`
- **Public Beta support boundary:** `docs/PUBLIC-BETA.md`
- **Known bugs registry:** `docs/KNOWN-BUGS.md`
- **GitHub milestone:** [Post-Beta Correctness and Expansion](https://github.com/Halildeu/ao-kernel/milestone/2)
- **GitHub tracker issue:** [#219](https://github.com/Halildeu/ao-kernel/issues/219)
- **Aktif issue:** [#232](https://github.com/Halildeu/ao-kernel/issues/232)

## 2. Başlangıç Gerçeği

- `WP-5` ile `WP-9` production hardening programı `main` üzerinde kapanmıştır.
- Repo bugün dar ama kanıtlı bir Public Beta / governed runtime yüzeyine sahiptir.
- Support boundary hâlâ bilerek dardır; `review_ai_flow + codex-stub` shipped
  baseline, gerçek adapter lane'leri ise operator-managed beta durumundadır.
- Public Beta closeout sonrası aktif program odağı artık defer edilmiş ilk
  correctness boşlukları değil; deterministik test hygiene, support-surface
  widening kararları ve adapter-path cost/evidence completeness gibi kalan
  post-beta işlerdir.
- Repo bugün hâlâ genel amaçlı production coding automation platformu değildir;
  bu programın amacı o iddiayı hemen widen etmek değil, önce kalan debt'i
  kontrollü kapatmaktır.

## 3. Yürütme Kuralları

1. Aynı anda en fazla `1 ana runtime slice` açık olur.
2. Her slice tek branch, tek PR, tek net kabul kriteri ile yürür.
3. Support boundary, code path + davranışsal test/smoke + CI + doc birlikte
   mevcutsa genişletilir; hiçbir tekil kanıt yeterli sayılmaz.
4. Runtime semantics değiştiren slice merge olmadan bir sonraki runtime slice
   başlamaz.
5. Her slice kapanışında zorunlu kayıt:
   - status güncellemesi
   - issue / PR referansı
   - test kanıtı
   - smoke kanıtı gerekiyorsa onun çıktısı
   - kalan deferred notları

## 4. Program Tahtası

| Slice | Durum | Hedef | Zorunlu kanıt |
|---|---|---|---|
| `PB-1` Deferred correctness pack 1 | Completed on `main` ([#220](https://github.com/Halildeu/ao-kernel/issues/220)) | `sanitize.py`, `compiler.py`, `init_cmd.py` correctness boşluklarının zaten kapanmış olduğunu backfill doğrulamak | targeted tests on `main` + status correction |
| `PB-2` `bug_fix_flow + codex-stub patch_preview` closure | Completed on `main` ([#222](https://github.com/Halildeu/ao-kernel/issues/222), [#224](https://github.com/Halildeu/ao-kernel/pull/224)) | `open_pr` adımında PR metadata/evidence boşluğunu kapatmak ve deferred bugfix workflow yüzeyini deterministik integration coverage ile doğrulamak | merged runtime fix + integration tests + green CI |
| `PB-3` deterministic test hygiene / time seams | Completed on `main` ([#226](https://github.com/Halildeu/ao-kernel/issues/226), [#227](https://github.com/Halildeu/ao-kernel/pull/227), [#228](https://github.com/Halildeu/ao-kernel/pull/228), [#229](https://github.com/Halildeu/ao-kernel/pull/229), [#230](https://github.com/Halildeu/ao-kernel/pull/230), [#231](https://github.com/Halildeu/ao-kernel/pull/231)) | zaman-bağımlı test ve zayıf assertion drift'ini sistematik azaltmak | targeted suite proof + residual seam inventory |
| `PB-4` support-surface widening decisions | In progress ([#232](https://github.com/Halildeu/ao-kernel/issues/232)) | `gh-cli-pr` full E2E ve operator lane promotion kararlarını kanıtla vermek | smoke/e2e kanıtı + docs parity |
| `PB-5` adapter-path cost/evidence completeness | Planned | `cost_usd` reconcile ve evidence completeness boşluklarını kapatmak | tests + evidence parity |
| `PB-6` general-purpose expansion gap map | Planned | narrow beta'dan daha geniş production platform çizgisine geçiş için önkoşulları tabloya dökmek | written gap map + ordered backlog |

## 5. Şimdi

### `PB-4` — support-surface widening decisions

**Neden şimdi**
- `PB-3` beş küçük tranche ile kapandı; deterministic test hygiene tarafındaki
  aktif blocker görünür şekilde daraltıldı.
- Doğru sıradaki yeni karar alanı support boundary widening: hangi adapter lane
  ve operator akışlarının daha geniş destek iddiasına çıkabileceği artık canlı
  smoke ve docs/runtime/test parity ile ölçülmeli.
- Bu hat yeni promise eklemeden önce mevcut support surface'i kanıt bazlı
  sınıflandıracaktır.

**Aktif kapsam**
1. `gh-cli-pr` ve ilişkili operator-managed lane'ler için canlı smoke/e2e kanıtı
2. `docs/PUBLIC-BETA.md` ve `docs/ADAPTERS.md` içindeki tier/sınır hizası
3. widen edilmeyen yüzeylerin açık deferred/operator-managed işaretlenmesi

**Definition of Done**
- widening kararı verilen yüzey için canlı smoke veya eşdeğer yüksek-sinyal
  kanıt vardır
- docs/runtime/test/CI tek anlamlı support boundary anlatır
- widen edilmeyen yüzeyler açıkça deferred veya operator-managed olarak yazılır

**Anlık ilerleme**
- ilk tranche canlı smoke tazelemesi tamamlandı:
  - `python3 scripts/claude_code_cli_smoke.py --output text` → `pass`
  - `python3 scripts/gh_cli_pr_smoke.py --output text` → `pass`
- bugünkü kanıt, docs'taki mevcut dar boundary ile uyumlu:
  `claude-code-cli` beta operator-managed, `gh-cli-pr` beta preflight-only,
  gerçek remote PR açılışı deferred
- ikinci tranche kararı netleşti:
  `claude-code-cli` lane'i smoke pass verse de Beta/operator-managed kalır;
  belirleyici sağlık sinyali helper smoke'tur, `claude auth status` tek başına
  yeterli değildir, env-token fallback support widening gerekçesi sayılmaz
- üçüncü tranche kararı da netleşti:
  `gh-cli-pr` helper smoke yalnız dry-run preflight kanıtı üretir; gerçek
  remote PR açılışı disposable sandbox + remote cleanup/rollback runbook'u
  olmadan widening adayı değildir ve deferred kalır
- `PB-4` closeout-ready duruma geldi; sıradaki alt adım closeout değerlendirmesi
  ve issue/status kapanış turudur

## 6. Sonra

`PB-4` kapandıktan sonraki doğru sıra:

1. `PB-5` adapter-path cost/evidence completeness
2. `PB-6` general-purpose expansion gap map

## 7. Riskler

| Risk | Etki | Önlem |
|---|---|---|
| Küçük correctness fix'i support widening gibi sunmak | Orta | status + docs boundary'yi dar tut |
| `PB-1` için stale backlog üzerinde çalışmak | Orta | canlı testle doğrula, sonra status'u düzelt |
| Deterministic test hygiene işinde scope creep | Yüksek | `PB-3`ü seam inventory + küçük tranche fix'ler olarak dilimle |
| Zayıf testlerle fake green oluşması | Yüksek | behavior-first assertions ve smoke kanıtı zorunlu |

## 8. Anlık Öncelik

Bugünden itibaren doğru sıra:

1. `PB-4` support-surface widening decisions

## 9. Güncelleme Protokolü

Her merge sonrası bu dosyada en az şu alanlar güncellenecek:

- aktif slice
- tamamlanan slice'ın durumu
- issue / PR / kanıt referansı
- yeni risk veya deferred notu
- sıradaki tek aktif hat
