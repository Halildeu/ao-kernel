# AO-MA-SPM Master Plan — Governed Autonomous Multi-AI Yazılım Üretim Sistemi

> **Statü:** AKTİF — program SSOT (insan-okur). Makine-okur durum: `.claude/plans/ao_ma_status.v1.json` (AO-MA-11E ile gelecek).
> **Sürüm:** v1 (2026-05-30).
> **Mutabakat:** 3-AI (Claude/Anthropic + Codex/OpenAI + Mavis/MiniMax) tur-4 TAM AGREE + operatör onayı (tek insan kapısı) alındı.
> **İlişkili:** `AO-MA-11A-PLAN-CONSENSUS-APPROVAL.md` (ilk slice), `AO-MA-1-MULTI-AGENT-ORCHESTRATION-DESIGN.md` (pipeline), `AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.md` (merge lane), `.github/REPO-GOVERNANCE.md` (otorite).
> **Değişmezler:** `live_adapter_execution` / `support_widening` / `production_platform_claim` = FALSE. GPP-9 closed + RI-7.8c non-promotion korunur.

---

## 0. Bu Doküman Nedir

Bu, **otonom multi-AI yazılım üretim sisteminin** uçtan uca master planıdır. Hem **ne inşa ettiğimizi** (sistem) hem **nasıl inşa ettiğimizi** (süreç) hem de **hangi standartlarla** (kalite/kanıt) tanımlar. "Planda neredeyim?" sorusunun insan-okur cevabıdır; makine-okur ikizi AO-MA-11E ile gelir.

Doküman **yaşayan SSOT'tur**: her faz kapandığında statüsü güncellenir. Mimari kararlar değişirse 3-AI consensus + operatör onayı gerekir (Bölüm 7 iş akışı).

---

## 1. Vizyon

### 1.1 Ne inşa ediyoruz

**Governed autonomous multi-AI coding system:** Claude (Anthropic) + Codex (OpenAI) + Mavis (MiniMax) AI'larının, bir hedefi kendi aralarında istişare ederek plana döktüğü, **tek bir insan onay kapısından** geçirdiği, sonrasını **tam otonom** (impl + cross-AI review + verify + merge) yürüttüğü bir sistem. ao-kernel bu akışı **GOVERN eden control-plane**'dir — runtime değil; AI'ların yerine geçmez, üstlerinde durup denetler.

### 1.2 Üç eşzamanlı kullanım

| # | Kullanım | Açıklama |
|---|---|---|
| **(a)** | **Üretim aracı** | AI'lar bu sistemle **dış projeler / yazılımlar** yazar. Sistem genel bir SPM (software project management) motoru olarak çalışır. |
| **(b)** | **Dogfooding** | ao-kernel'in **kendi geliştirmesinde** kullanılır. Kendi ürettiğimiz aracı kendi üzerimizde kullanırız. |
| **(c)** | **Self-hosting / bootstrap** | Sistem **kendi kendini, kendi sistemiyle** inşa eder. Bir faz hayata geçince, sonraki fazlar o fazın makinesiyle üretilir. |

### 1.3 Geçici mod → Sistem modu (bootstrap çerçevesi)

Sistemin merkez fikri: **bugün manuel olan, yarın otomatik.**

- **Geçici mod (şimdi):** İnsan-AI hibrit. Operatör + Claude (uygulayıcı) + Codex/Mavis (istişare) manuel koordine olur. 3-AI consensus chat/CLI üzerinden, evidence elle yazılır. *Bu doküman bu modda yazıldı.*
- **Sistem modu (hedef):** Pipeline kendi yürütür. `plan_consensus` makinesi consensus bundle'ı üretir/doğrular; tek onay GitHub Environment'ta; impl→review→merge AO-MA pipeline'ında; tracking GitHub-native aynaya otomatik akar.

Her faz, geçici modun bir parçasını sistem moduna devreder. "Geçici uygulayıcı" rolü kademeli olarak sisteme geçer.

> **Değişmez kuralı (defensive):** "Geçici mod" hiçbir zaman bir değişmezi gevşetmenin gerekçesi değildir. Bölüm 9'daki invariantlar (3 guard flag FALSE, RI-7.8c, GPP-9, release_authority pin, `--admin` yasağı, risk_class authority — risk downgrade yasak) geçici modda da sistem modunda da aynen geçerlidir. "Şimdilik geçici, sonra düzeltiriz" pattern'i YASAK.

### 1.4 Tek insan gate felsefesi

Operatörün **tek müdahale noktası**: tam-mutabık planın onayı. Öncesi (planlama+istişare) ve sonrası (impl+review+merge) otonomdur. İstisna: strateji/irreversible/guard-flip kararları (Bölüm 9).

---

## 2. Temel İlkeler (best practices + neden)

| İlke | Ne demek | Neden (best practice) |
|---|---|---|
| **Fail-closed** | Şüphe/eksik kanıt → blokla, geçirme | Güvenlik varsayılanı; sessiz başarı (fail-open) en tehlikeli durum |
| **Machine-enforced, no self-attestation** | Kanıt "doğru" diye yazılmaz, **yeniden hesaplanır/doğrulanır** | "Artifact öyle yazıyor" ≠ "öyle". `unanimous_status` provider_verdicts'ten recompute edilir |
| **Cross-provider adversarial review** | Kod yazan sağlayıcı kendi kodunu onaylayamaz | Aynı model ailesi = aynı kör nokta; farklı sağlayıcı gerçek adversarial sinyal |
| **Evidence-based** | Her karar JSONL + SHA256 audit izi bırakır | Replay'lenebilir, denetlenebilir, sahte-yeşil yapılamaz |
| **İki katman SSOT** | Authority (governance) ≠ Mirror (görünürlük) | Düzenlenebilir görünürlük katmanı otoriteyi override edemez |
| **Control-plane, not runtime** | AI'ları govern et, yerlerine geçme | ao-kernel'in nişi; CLI-abonelik modeliyle uyumlu, live-adapter gerekmez |
| **Guard-flag invariant** | 3 flag const FALSE | Scope creep'i schema seviyesinde engeller |
| **Uzun-vadeli kalıcı çözüm** | 6 ay sonra hâlâ doğru + adversarial-geçer | Patch/symptom-fix değil, kök-neden + sistemik |

---

## 3. Mimari

### 3.1 Katmanlar

```
┌─────────────────────────────────────────────────────────────┐
│  OPERATÖR (tek insan gate: tam-mutabık plan onayı)           │
└───────────────────────────┬─────────────────────────────────┘
                            │ GitHub Environment (required-reviewer)
┌───────────────────────────▼─────────────────────────────────┐
│  GOVERNANCE AUTHORITY (fail-closed, makine-enforced)         │
│   ao-release-gate + GitHub ruleset  → release otoritesi       │
│   plan_consensus (11A)              → plan onay kapısı         │
│   JSONL + SHA256 evidence trail     → kanıt SSOT              │
└───────────────────────────┬─────────────────────────────────┘
                            │ tek-yön sync (ao-kernel → GH)
┌───────────────────────────▼─────────────────────────────────┐
│  GÖRÜNÜRLÜK AYNASI (human-facing, authority DEĞİL)            │
│   GitHub Milestone(faz) / Issue(slice) / Projects(board+road) │
│   drift checker: mirror ≠ artifact → DUR + eskalasyon         │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│  AO-MA PIPELINE (otonom yürütme)                             │
│   plan → spawn → invoke → review → verify → integrate → merge │
│   AI native arayüzler: Claude Code / Codex CLI / Mavis        │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Otorite modeli (kritik invariant)

**AI çıktısı = evidence; release otoritesi = `ao-release-gate` + GitHub ruleset.** Hiçbir AI kendi kararını merge edemez. Merge agent bir *executor*'dür; `--admin` yok, bypass actor yok, ruleset mutation yok. `plan_consensus`/approval da otorite değildir — tek gate bir **otonom run-start** yetkilendirir, merge/release değil.

### 3.3 İki katman SSOT (Codex guardrail absorbe)

- **Authority:** ao-kernel JSONL + SHA256 + schema-valid artifact'lar. Fail-closed.
- **Mirror:** GitHub Projects/Issues/Milestones/PR threads. İnsan görünürlüğü.
- **Sync:** Tek-yön `ao-kernel → GitHub`. GH'den governance state import EDİLMEZ.
- **Drift checker:** Mirror digest ≠ artifact digest → `mirror_drift_detected` → otonom DUR + eskalasyon; GH-kaynaklı kanıt reddedilir.
- **Manuel GH edit:** "Görünür not"tur, override değil; operatörün GH-thread kararı ao-kernel approval artifact'ına dönüştürülmeli.

---

## 4. Sektör Standartları Matrisi

| Standart | Ne işe yarar | Mevcut | Faz |
|---|---|---|---|
| **SemVer** | Sürüm anlamı (major.minor.patch) | ✓ | korunur |
| **Conventional Commits** | `feat()/fix()/chore()` commit dilbilgisi | ✓ | korunur |
| **Keep-a-Changelog** | İnsan-okur değişiklik günlüğü | ✓ | korunur |
| **Test pyramid + coverage gate** | unit > integration > e2e; %85 branch (bu repoda ağırlık unit+integration; e2e sınırlı) | ✓ | korunur |
| **AST test quality gate** | BLK-001..004 tautoloji/mock yasağı | ✓ | korunur |
| **CI/CD gate** | ao-release-gate required check + ruleset | ✓ | korunur |
| **Evidence-based audit** | JSONL + SHA256 integrity manifest | ✓ | korunur |
| **Cross-AI review** | implementer ≠ reviewer sağlayıcı | ✓ | korunur |
| **ADR (Architecture Decision Record)** | Mimari kararların izlenebilir kaydı | ✗ | **11G** |
| **ISO/IEC 25010 kalite profili** | Yazılım kalite modeli (referans, sertifika DEĞİL) | ✗ | **11G** |
| **GitHub-native PM** | Milestone/Issue/Projects/Environment-gate | kısmi | **11E** |
| **Run governor (kill-switch/budget)** | Otonom çalışma güvenlik kemeri | ✗ | **11I** |

> Mavis uyarısı (tur-3): ISO 25010 **tam entegrasyonu over-engineering** — sadece profile referansı; sertifikasyon hedefi YOK.

---

## 5. Roadmap — 7 Faz

> Sıra = Codex+Mavis+Claude tur-4 mutabakatı. Her faz: ayrı slice, ayrı worktree+branch, kendi consensus+approval+cross-AI review+CI döngüsü.

### Faz 1 — AO-MA-11A: Plan Consensus + Tek Operatör Onay Kapısı  ✅ 11A-1 DONE
- **Amaç:** Plan-zamanı 3-AI consensus'u sistematik evidence'a dök + tek onay kapısını machine-enforce et.
- **Üretilenler:** `ao-ma-11a-plan-consensus-bundle.schema.v1.json`, `ao-ma-11a-plan-approval.schema.v1.json`, `plan_consensus.py` (pure-decision), 39 test (100% branch).
- **Kabul:** unanimity machine-recompute; triple SHA-bind approval; 4 gate state; AST import-allowlist.
- **Standart bağı:** evidence audit + cross-AI review + fail-closed.
- **Statü:** 11A-1 implement edildi (PR #758, Codex iter-2 AGREE). **11A-2** (GitHub Environment `ao-ma-plan-approval` required-reviewer wiring, `.github` high-risk) follow-up.

### Faz 2 — AO-MA-11E: GitHub-Native Operator Tracking Mirror
- **Amaç:** "Planda neredeyim + yol haritası + izlenebilirlik" — GitHub'ın kendi PM yapısıyla.
- **Üretilenler:** `ao_ma_status.v1.json` + `AO-MA-ROADMAP-STATUS.md` + `scripts/ao_ma_next.py` + `ao-ma-status.schema.v1.json`; Faz→Milestone, Slice→Issue (YAML form + SPM fields), Projects v2 (Board+Roadmap view). Anchor field'lar (`ao_authority_artifact`/`artifact_sha256`/`plan_digest`/`slice_id`/`last_sync_run_id`) + tek-yön sync + drift checker.
- **Kabul:** GH mirror authority değil; manuel edit gate satisfy etmez; drift → DUR.
- **Standart bağı:** GitHub-native PM + traceability.
- **Statü:** sırada (Faz 1 sonrası).

### Faz 3 — AO-MA-11I: Autonomous Run Governor (güvenlik kemeri)
- **Amaç:** Otonom çalışma sırasında runaway/güvenlik koruması.
- **Üretilenler:** `.ao/autonomous/PAUSE` otoriter kill-switch + budget/iteration cap + safe-stop checkpoint. Fail-closed: limit aşımı → DUR + eskalasyon.
- **Kabul:** kill-switch lokal-otoriter (GH status pause sayılmaz); 4.6'dan ÖNCE devrede.
- **Standart bağı:** fail-closed + operator control.
- **Statü:** sırada (4.6'dan önce zorunlu).

### Faz 4 — AO-MA-11H: Notification & Escalation
- **Amaç:** Poll'ü öldür; sistem operatörü sadece gate+eskalasyonda pingler.
- **Üretilenler:** Mavis CLI chat + GitHub-native (@mention/review-request) bildirim. **Harici/Teams YOK.** Kritik eskalasyon teslim hatası → `blocked_notification_failed` → safe-stop.
- **Kabul:** best-effort görünürlük; kritik teslimat governor'a bağlı.
- **Standart bağı:** operator-in-the-loop.
- **Statü:** sırada.

### Faz 5 — AO-MA-11F: Test/Öneri/Güncelleme Evidence Registers
- **Amaç:** "Testler/öneriler/güncellemeler hepsini takip."
- **Üretilenler:** `ao-ma-slice-test-report.v1.json` + `ao-ma-ai-suggestion-register.v1.json` (= PR review threads accept/reject+gerekçe) + `ao-ma-slice-update-ledger.v1.jsonl` + `ao-ma-slice-closeout.v1.json`; `evidence bundle <slice>` SHA-bound audit zinciri.
- **Kabul:** her cross-AI itiraz accept/reject+gerekçe ile kayıtlı (CLAUDE.md §15).
- **Standart bağı:** evidence audit + traceability.
- **Statü:** sırada.

### Faz 6 — AO-MA-4.6: Native Worker Result Import (import-only)
- **Amaç:** Gerçek AI çıktısı (stub değil) — CLI-abonelik modeli ihlal edilmeden.
- **Üretilenler:** Operatör/AI native çıktı üretir; **ao-kernel HİÇBİR ŞEY çağırmaz**, sadece import + schema-validate + provenance-bind. `live_adapter_execution=false` korunur. 11A'ya bağımlı; AO-MA-4.5 stub kalır.
- **Kabul:** import-only; subprocess/API spawn YOK; RI-7.8c uyumlu.
- **Standart bağı:** control-plane (govern, not execute).
- **Statü:** sırada (governor+notification+register sonrası).

### Faz 7 — AO-MA-11G: SPM Quality Profile Hardening
- **Amaç:** "Standarda yazılmalı + sektörün en iyi uygulamaları."
- **Üretilenler:** ADR template formalize + ISO/IEC 25010 kalite **profile referansı** (sertifika DEĞİL) + changelog/release-impact disiplini.
- **Kabul:** ADR mimari kararları izlenebilir; ISO profile over-engineering değil.
- **Standart bağı:** ADR + ISO 25010 + Keep-a-Changelog.
- **Statü:** en son.

---

## 6. Bootstrap / Self-Hosting Mekanizması

"Self-hosting compiler" pattern'i: **sistem kendi kendini kendi makinesiyle inşa eder.**

| Faz | Devreden geçici-mod işi | Sisteme geçen yetenek |
|---|---|---|
| 11A | Manuel 3-AI consensus (chat/CLI) + elle evidence | `plan_consensus` makinesi consensus bundle'ı doğrular; tek onay Environment'ta |
| 11E | "Neredeyiz" sorusunu insan takip eder | GitHub-native mirror + `ao_ma_next.py` otomatik gösterir |
| 11I | Operatör manuel "dur" der | `.ao/autonomous/PAUSE` + budget cap otomatik durdurur |
| 11H | Operatör poll eder | Sistem gate/eskalasyonda otomatik pingler |
| 11F | İncelemeler chat'te kalır | Register'lar + audit bundle otomatik kaydeder |
| 4.6 | Worker = deterministic stub | Gerçek AI native çıktısı import edilir |
| 11G | Kalite ad-hoc | ADR + kalite profili sistematik |

**Geçiş kriteri:** Bir faz "sistem modu"na geçer ancak (a) kendi **DoD'sini (Bölüm 10) tam geçmiş**, (b) merge olmuş, (c) cross-AI AGREE almış, (d) kendi testleri yeşil ve (e) bir sonraki slice o makineden geçirilerek üretilmişse.

**Canlı kanıt semantiği (Codex review absorbe):** Faz N'in sistem moduna geçtiğinin canlı kanıtı, Faz N+1'in *yalnızca* AO-MA-11A consensus bundle'ından geçmesi DEĞİLDİR — bu sadece 11A'nın çalıştığını kanıtlar. Her fazın canlı kanıtı, **kendi ürettiği mekanizmanın** Faz N+1'in acceptance zincirinde fiilen kullanılmasıdır: 11E için mirror sync + drift-check, 11I için pause/budget safe-stop, 11H için escalation delivery, 11F için register update + evidence bundle, 4.6 için import-only provenance-bind, 11G için ADR + kalite profili uygulanması.

---

## 7. Bir Slice'ın Yaşam Döngüsü (iş akışı)

```
1. HEDEF          operatör veya sistem bir iş paketi tanımlar
2. 3-AI CONSENSUS Claude+Codex+Mavis istişare → plan-consensus bundle
                  unanimous_status machine-recompute (AGREE/NOT_AGREE)
3. TEK ONAY       AGREE ise → operatör GitHub Environment'ta approve (tek insan gate)
                  NOT_AGREE → consensus_not_reached, gate açılmaz
4. OTONOM IMPL    ayrı worktree+branch; AI native arayüzle kod
5. CROSS-AI REVIEW implementer ≠ reviewer sağlayıcı; AGREE/REVISE/RED
                  REVISE → absorb + iter; RED → operatöre
6. CI + GATE      ao-release-gate (technical + review); high-risk lane gerekirse
                  cross-provider supersession / non-author approval
7. MERGE          yeşilse squash merge (--admin YOK); forensic cleanup
8. TRACKING       GitHub-native mirror + register'lar otomatik güncellenir
```

**Geçici mod farkı (şimdi):** 2-3-5 adımları manuel (chat/CLI + elle evidence); 4-6-7 yarı-otomatik. **Sistem modu (hedef):** 2-8 otomatik; 3 tek insan kapısı kalır.

---

## 8. Görünürlük ve İzlenebilirlik

- **Faz = Milestone** (due date + otomatik % ilerleme).
- **Slice = Issue** (YAML issue form ile SPM field'ları: quality_targets, required_test_classes, evidence_classes, roadmap_item_id).
- **Board + zaman çizelgesi = Projects v2** (Board view + Roadmap/Gantt view + custom fields: status, faz, risk-lane, consensus-state, coverage-delta, implementer/reviewer AI, evidence-ref).
- **Tek onay kapısı = GitHub Environment** required-reviewer (native + auditable).
- **Öneri/itiraz takibi = PR review threads** (accept/reject + gerekçe).
- **Makine-okur durum:** `ao_ma_status.v1.json` + `scripts/ao_ma_next.py` ("sıradaki izinli iş").
- **Bildirim:** Mavis AI chat + GitHub-native; harici entegrasyon YOK.

---

## 9. Güvenlik Sınırları ve Invariantlar

| Invariant | Değer | Nasıl korunur |
|---|---|---|
| `live_adapter_execution` | FALSE | schema const + validator backstop + RI-7.8c |
| `support_widening` | FALSE | schema const + guard check |
| `production_platform_claim` | FALSE | schema const + guard check |
| `release_authority` | `ao-release-gate+github-ruleset` | schema const pin |
| `ai_output_release_authority` | FALSE | schema const |
| GPP programı | KAPALI (keep_narrow_stable_runtime) | gpp_status + gate boundaries |
| `--admin` merge | YASAK | HARD RULE + ruleset bypass_actors=[] |
| Kill-switch | `.ao/autonomous/PAUSE` | 11I governor (fail-closed) |
| **risk_class / risk-lane otoritesi** | Yalnız `RiskClassifier` / release-gate changed-path classifier | aşağıdaki invariant |

**risk_class / risk-lane otoritesi (Codex review absorbe — kritik invariant):** Risk sınıfı yalnız **protected/base-ref koddan çalışan `RiskClassifier`** ve/veya **`ao-release-gate` changed-path classifier** çıktısından, **gerçek değişen dosya yollarından** türetilir. Plan consensus bundle, AI beyanı, GitHub Issue/Project `risk-lane` alanı veya manuel mirror edit **risk'i DÜŞÜREMEZ** (downgrade yasak). Unknown/empty write-set worker spawn yetkisi üretmez — explicit write-set + computed risk_class gerekir. `high`/`critical` sonuç AO-MA-10 high-risk lane / cross-provider supersession evidence gerektirir. (Bu yüzden `risk_class` AO-MA-11A consensus bundle schema'sında YOK — bkz. `AO-MA-11A-PLAN-CONSENSUS-APPROVAL.md` §7.)

**Operatör kararı gereken istisnalar (tek-gate dışında):** guard-flag flip, irreversible action, stratejik pivot, RI-7.8c supersession. Bunlar ayrı operator-bound PR ister.

---

## 10. Definition of Done (her slice için kalite/kanıt kapısı)

Bir slice "tamamlandı" sayılır ancak ilgili TÜM kalemler sağlanırsa. Bazı kalemler **koşulludur** (slice o yüzeye dokunuyorsa); koşullu kalemler "lifecycle-aware" işaretlidir (Codex review absorbe — evrensel yazım imkânsız gate veya yanlış N/A üretmesin).

**Her slice (zorunlu):**
- [ ] 3-AI plan-consensus bundle AGREE (machine-recompute doğrulandı)
- [ ] Operatör onayı (tek insan gate) — `ao-ma-11a-plan-approval` artifact
- [ ] Testler: unit + negatif + integrity + I/O; ilgili modül ≥%85 branch (hedef 100%)
- [ ] Cross-AI review AGREE (implementer ≠ reviewer sağlayıcı)
- [ ] CI tamamen yeşil (ao-release-gate technical + review); kırmızıyla merge YASAK
- [ ] Guard flag'ler FALSE (schema + backstop)
- [ ] Evidence audit izi (JSONL + SHA256 / local-ai-review-evidence)
- [ ] **Computed risk_class** protected/base RiskClassifier veya release-gate changed-path classifier'dan kayıtlı; GH mirror / manuel risk-lane risk'i DÜŞÜREMEZ
- [ ] `high`/`critical` ise high-risk lane / cross-provider supersession evidence mevcut
- [ ] Consensus/approval/review evidence freshness bağı (base_ref/base_sha/head_sha/diff_digest) korunuyor; stale evidence fail-closed
- [ ] Forensic cleanup
- [ ] Plan doc + bu master plan statüsü güncellendi

**Koşullu (lifecycle-aware — slice o yüzeye dokunuyorsa):**
- [ ] *Yeni/değişen schema varsa:* Draft 2020-12 strict (additionalProperties:false, const-pin, required maksimal)
- [ ] *Yeni/değişen validator varsa:* pure-decision (no LLM/GitHub-write/subprocess — AST-enforced)
- [ ] *11E öncesi:* geçici status/plan kayıtları güncel (milestone/issue manuel). *11E sonrası:* mirror sync + drift checker yeşil

---

## 11. Mevcut Durum + Sonraki Adım

- **AO-MA-SPM §Faz 1-7 ✅ TAMAMLANDI (2026-06-01)** — 7/7 fazlar MERGED (11A-1 #758 + 11E-1 #760 + 11I-1 #762 + 11H-1 #763 + 11F-1 #765 + 4.6-1 #766 + 11G-1 #767). Self-hosting compiler döngüsü kapandı: program kendi makinesiyle inşa edildi.
- **AO-MA-11G-2 release lifecycle LIVE:** PR #769 11G-2a allowlist widening MERGED (`4536a70`); PR #770 11G-2b v4.1.0 release prep MERGED (`4d0aa6d`); tag `v4.1.0` pushed 2026-06-01. **GitHub Actions publish.yml twine check fail** (`dist/` JSON evidence files); fix ayrı PR (`.github/workflows/publish.yml` high-risk operator review gerek); PyPI v4.1.0 yayını publish workflow fix sonrası.
- **Pending follow-up:** PR #764 (CI shadow-skip permanent fix, operator gate), 11A-2 (GH Environment gate wiring), 11E-2 (GH Projects/Milestone/Issue mirror sync), 11G-2c/d (CI/pre-commit changelog enforcement), 4.6-2 (native-import operator dogfooding), retro ADR cross-AI revalidation.

---

## 12. v5.0.0 Full Production Promotion Program (operator-bound supersession yolu)

**Status:** PROPOSED · **Target:** 2026-12-31 (aspirational; exit criteria authoritative)
**Plan doc:** `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`
**Projection manifest:** `.claude/plans/v5_issue_projection.v1.json`
**Consultation:** CNS-20260601-004 · **Codex thread** `019e80b3` (1 tur REVISE → revize 4-PR yapısı + 8 invariant absorb)

### Vizyon

AO-MA-SPM §Faz 1-7 governance plane tamamlandı; v5.0.0 **Full Production Promotion** ile sistem ilk kez `production_platform_claim=true` + `live_adapter_execution=true` + `support_widening=true` (3 guard flag flip) iddiasında bulunabilir hale gelir. Bu **operator-bound supersession decision**'dır; AO-MA-11A normal approval gate'inden geçemez (`ao-ma-11a-plan-approval.schema.v1.json` zaten guard flags const false pin'liyor).

### 9 Epic (parallel + dependency)

| # | Epic | Risk | Guard flip | Bağımlılık |
|---|---|---|---|---|
| **P0** | Promotion governance + visibility source manifest | normal | YOK | — |
| 1 | AO-MA-SPM follow-up (sistem mod tam aktivasyon) | normal | YOK | P0 |
| 2 | Live adapter execution (`live_adapter_execution=true`) | critical | EVET | E-1 |
| 3 | Support widening (`support_widening=true`) | critical | EVET | E-1 + E-2 |
| 4 | Deployment + operations + tenancy | high | YOK | E-1 + E-2 |
| 5 | Observability + production telemetry | normal | YOK | E-2 paralel |
| 6 | Security + compliance | high | YOK | paralel |
| 7 | Performance + scalability | normal | YOK | E-2 + E-5 paralel |
| 8 | Documentation + onboarding | low | YOK | paralel |
| **9** | **Final promotion decision (operator-bound supersession PR)** | **critical** | **EVET (3 flag)** | **Tüm E-1..8 complete** |

### 9-boyutlu production readiness evidence matrix

`production_platform_claim=true` flag flip **production-ready KANITI DEĞIL**; semantic readiness 9 boyutta evidence gerek:
1. Public support matrix net (OS/Python/provider)
2. Real provider live calls protected env'de çalışmış (live adapter envelope)
3. Cost/rate/circuit breaker limits canlı evidence ile doğrulanmış
4. Observability prod tunables (OTEL traces/metrics + dashboards)
5. Security/SBOM/license scans temiz (SOC2/CodeQL/Snyk/Dependabot)
6. Install/deploy lifecycle smoke (k8s/Helm + standalone PyPI)
7. Multi-tenancy isolation (varsa) testli (RBAC + secret + quota + audit)
8. Docs/runbooks güncel (deployment guide + operator runbook + API ref)
9. ao-release-gate + GitHub ruleset bypass-sız geçmiş (autonomous merge trail)

Final epic 9 PR-Xfinal tüm evidence refs'i bağlar; flag flip o PR'da.

### Visibility (one-way mirror, NOT authority)

GitHub Milestone "v5.0.0" + 9 epic + 3 P0 gate issues + Project board ("Roadmap v5.0.0"; Kanban + Roadmap view + custom fields Epic/Risk/Guard/Dependency/Estimate/Consensus/Evidence/Mirror digest/Release impact). Issue forms (YAML) zorunlu anchor fields. Repo artifacts (`.claude/plans/`) SSOT kalır; GitHub'dan governance import YASAK.

### Public claim language

README/badge/project page dili **"v5 production promotion roadmap" kalır**; **"production-ready" public claim FINAL PR'DAN ÖNCE KULLANILMAZ**. Mevcut "narrow stable runtime" framing devam eder. Final promotion sonrası "v5.0.0 — Production-Ready Governed Multi-AI Orchestration Runtime" claim'i public yapılır.

### 4-PR yapısı

| PR | Scope | Guard flip |
|---|---|---|
| **PR-X0** (bu PR) | plan doc + projection manifest + acceptance matrix + master plan amend | YOK |
| **PR-X2** (post-11E-2) | GH mirror sync (Milestone + 9 epic + 3 P0 gate issue + Project board create; created IDs + digest repo evidence'a geri yaz) | YOK |
| **PR-X(epic-N)** | her epic kendi sub-issue + plan-consensus + impl + cross-AI review + merge | YOK (Epic 9 hariç) |
| **PR-Xfinal** | operator-bound supersession decision; 3 guard flag flip + v4.x → v5.0.0 + CHANGELOG release + tag push | **EVET** |

### Bootstrap (AO-MA-SPM 7/7 → v5 promotion)

AO-MA-SPM makinesi v5 epic'lerini yazmak için kullanılır (self-hosting devam): her epic'in sub-issue'su AO-MA-11A plan-consensus + 11E mirror sync + 11I run governor + 11H notification + 11F evidence registers + 4.6 native-import + 11G ADR/ISO/CHANGELOG discipline ile yürür. Yani v5 program AO-MA-SPM'in **kullanıcısı** olur (faz 1-7'nin tüketicisi).

> **v5 karar kuralı (tek cümle):** AO-MA-SPM tamamlanması "production-ready" değildir; v5 promotion 9-boyutlu evidence matrix + operator-bound supersession decision sonucudur; flag flip ANCAK final epic 9 PR-Xfinal'da; visibility mirror authority değil; public claim language final PR'dan önce "roadmap" kalır.
