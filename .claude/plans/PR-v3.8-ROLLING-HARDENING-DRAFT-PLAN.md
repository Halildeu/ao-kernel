# v3.8 — Rolling Hardening (DRAFT v1)

**Status:** DRAFT v1 — master plan pending per-PR CNS
**Prior consensus:** Codex 2-round consult (2026-04-19) — AGREE with 3 revisions:
- H4 narrowed to **dead-marker cleanup only** (remove, don't revive)
- H3 **deferred or dropped** (only 2 test call-sites; low payoff as standalone PR)
- H6 kapsamına `publish.yml` pip install adımı da dahil edildi

**Depends on:** v3.7.0 LIVE (benchmark realism scaffolded; real-adapter event-backed cost-source wired).

**Scope optimum:** 5 PRs (H6 + H5 + H4 + H2 + H1). H3 deferred to post-v3.8 or folded into an unrelated cleanup PR if capacity permits.

---

## 1. Problem statement

v3.5–v3.7 were feature-heavy (consultation surfaces, memory loop, benchmark realism). v3.8 clears accumulated hardening debt without net-new features:

- **CI flake class** — v3.7 release saw a one-off `SSL: DECRYPTION_FAILED_OR_BAD_RECORD_MAC` during `pip install`. Not recurring yet, but a retry wrapper is cheap insurance across `test.yml` + `publish.yml`.
- **v3.6 observability undercount** — consultation lines are budget-aware (v3.6 E2 iter-2 absorb) but still excluded from `items_included/items_excluded/selection_log` accounting. Non-contract-breaking but telemetry drift.
- **Dead test-quality marker** — `pyproject.toml::tool.pytest.markers.quality_waiver` was registered but never consumed. Declared-but-unused contract debt.
- **FS lock parity gap** — `_internal/shared/lock.py` exists; atomic write helpers exist; but there's no systematic audit that every stateful write-path uses lock + atomic (or is explicitly test-only).
- **`_internal` coverage opt-out** — `pyproject.toml::coverage.run.omit` still blanket-excludes `ao_kernel/_internal/*`. A tranche-by-tranche narrowing keeps the gate honest.

---

## 2. Non-goals

- **No new features.** Every PR is hardening/cleanup only.
- **No `save_store()` public-symbol removal.** v4.0 scope; v3.8 at most migrates remaining call-sites.
- **No `quality_waiver` revival.** H4 removes the dead registration; reviving would require a full design pass (marker + collection reporter + gate integration) out of scope.
- **No blanket `_internal` coverage enforcement.** H1 is a **tranche**, not full sweep.
- **No retry wrapper on every CI job.** H6 targets the failure mode we observed (`pip install`) only.

---

## 3. PR split (5 PRs per Codex AGREE optimum)

### Sequencing (Codex recommendation)

```
H6 (CI retry)  —|
                ├─ parallel-safe, both MUST ship early
H5 (obs fix)   —|
                ↓
H4 (waiver cleanup)   — after one of {H6, H5} merges
                ↓
H2 (FS lock parity)   — core semantic hardening
                ↓
H1 (_internal coverage tranche)   — post-lock behaviour depends on H2
```

**Parallel rule:**
- Lane 1 (micro): H6
- Lane 2 (micro): H5
- After at least one merges: H4
- Core (serial): H2 → H1
- NEVER parallel: H1 + H4 (both touch `pyproject.toml`); H1 + H2 (test/coverage semantic overlap)

### PR-H6 — CI pip-install retry wrapper (MUST, ship-first)

**Amaç:** v3.7 release'de gördüğümüz `SSL: DECRYPTION_FAILED_OR_BAD_RECORD_MAC` pip-install flake'ini önlemek.

**Kontrat:**
- `.github/workflows/test.yml` — `pip install -e ".[...]"` adımlarını 2-denemeli wrapper'a al (bash while loop + backoff; no third-party action).
- `.github/workflows/publish.yml` — `pip install build twine` adımını aynı pattern ile sar.
- Behavior: ilk deneme fail → 5s bekle → ikinci deneme. İkinci de fail → işlem fail (no retry storm).
- No new action dependencies; pure bash.

**Risk:** düşük — hiç runtime kod değişikliği yok, sadece CI script.

**Exit criteria:**
- Hem `test.yml` hem `publish.yml` retry guard'lı
- Retry logic inline ve okunabilir (bash 3-5 satır)
- Local manual dry-run (`bash -n`) syntax-clean

**Test pin:** YOK (CI-only change; değişiklik `test.yml` içinde kendini doğrular).

**Ship class:** MUST. Plan-time iter: 0 (impl-first + post-impl review).

---

### PR-H5 — v3.6 observability accounting cleanup (MUST, sidecar)

**Amaç:** Consultation lane satırlarının `items_included/items_excluded/selection_log` muhasebesine dahil edilmesi. Codex v3.6 E2 iter-2 post-impl MERGE'te residual not olarak bırakılan telemetry drift.

**Kontrat:**
- `ao_kernel/context/context_compiler.py`:
  - Consultation render akışında `items_included += len(accepted_consultations)` ve `items_excluded += (len(capped) - len(accepted))`
  - Her consultation satırı için `selection_log` entry (lane=`consultation`, score=null, included=True/False, reason=budget/cap)
- `tests/test_context_consultation_lane.py` + `tests/test_context_compiler.py`: 3-4 pin
  - Accepted consultation → `items_included` counter artıyor
  - Dropped consultation → `items_excluded` + `selection_log` reason="budget exceeded"
  - Fresh (empty) consultations → counter değişmiyor
- `docs/CONSULTATION-QUERY.md`: telemetry semantiği notu (küçük ek)

**Risk:** düşük — additive counter değişimi; contract break yok.

**Exit criteria:**
- `items_included + items_excluded` consultation satırlarını da içeriyor
- `selection_log` dropped consultation'ları taşıyor (lane="consultation")
- Mevcut compile tests regression-free

**Test pin:** 3-4 (counter + log entries).

**Ship class:** MUST (v3.6 follow-up). Plan-time iter: 1 (small).

---

### PR-H4 — `quality_waiver` marker dead-cleanup (MUST)

**Amaç:** `pyproject.toml::tool.pytest.markers.quality_waiver` registered ama hiç tüketilmiyor (repo grep: 0 usage). Declared-but-unused contract debt. Kaldır.

**Kontrat:**
- `pyproject.toml`: `quality_waiver` marker entry'sini kaldır
- Herhangi bir docs / memory referansı varsa sil
- Hiçbir test kodu dokunulmaz (kullanımı zaten yok)

**Revizyon (Codex iter-1 AGREE):** Revival kapsam dışı. Enforce etmeye kalkarsan cleanup yerine feature PR'ı olur — bu v3.8 scope değil.

**Risk:** düşük — dead symbol removal.

**Exit criteria:**
- `grep -rn "quality_waiver" .` sadece git history'de; kod/tests/docs'ta 0 match
- Full test suite regression-free

**Test pin:** 0 (silme; mevcut testler regression guard).

**Ship class:** MUST. Plan-time iter: 0 (impl-first).

---

### PR-H2 — FS lock parity audit (MUST, core)

**Amaç:** `_internal/shared/lock.py` + `write_json_atomic` + `write_text_atomic` altyapısı zaten var. Bu PR production write-path'leri tarıyor, her birinin **ya lock+atomic/CAS** kullandığını ya da **açıkça test-only istisna** olarak belgelendiğini doğruluyor.

**Kontrat:**
- Production write-path envanteri (codebase grep for `.write_text(`, `.write_bytes(`, `open(...).write()`, direct json.dump)
- Her birini kategorize et:
  - ✅ Lock+atomic kullanıyor (no-op)
  - ⚠️ Atomic-only (lock eklenmeli veya belgelenmeli)
  - ❌ Direct write (production) → fix
  - 📝 Test-only istisna → fenced with explicit comment
- Fix gereken noktalarda `write_text_atomic` / `write_json_atomic` migration
- Test-only path'lerde `# test-only: direct write (no concurrency)` comment
- Gap-fixing audit table → `docs/ARCHITECTURE.md` içinde (veya yeni `docs/FS-LOCK-PARITY.md`)

**Risk:** ORTA — semantic hardening; write-path değişimi. Her fix'in mevcut behavior'ı korumasına dikkat.

**Exit criteria:**
- Production write-path audit complete + docs
- Zero `.write_text(` veya direct `json.dump(f)` production path (test-only istisnalar hariç)
- Full test suite regression-free
- Codex post-impl review MERGE

**Test pin:** 2-4 (concurrency pin'leri; race regression guards).

**Ship class:** MUST. Plan-time iter: 2+ (daha büyük semantic analiz).

---

### PR-H1 — `_internal` coverage tranche (MUST, core; post-H2)

**Amaç:** `pyproject.toml::coverage.run.omit` listesini tranche bazlı daraltmak. H2 semantic hardening sonrası `_internal/shared/` ve `_internal/secrets/` gibi düşük-kompleks modüllerden başla.

**Kontrat:**
- Tranche 1: `_internal/shared/utils.py`, `_internal/shared/lock.py`, `_internal/secrets/*`
- Tranche başına testler ekle veya mevcut testlerin kapsamını artır
- `pyproject.toml::coverage.run.omit` listesinden bu modülleri çıkar
- Global `fail_under=70` korunur; tranche mevcut kapsamı artırmalı
- Docs: `docs/ARCHITECTURE.md` veya test docs'ta "tranche rollout" tablosu

**Risk:** ORTA — test expectations değişebilir; bazı paths gate'e uyum için refactor gerektirebilir.

**Exit criteria:**
- Tranche 1 `_internal/` modülleri omit'ten çıkmış
- Branch coverage %70+ tranche üzerinde
- Mevcut test suite regression-free
- Docs tablo güncel

**Test pin:** 3-8 (tranche modüllerinde yeni / genişletilmiş pin'ler).

**Ship class:** MUST. Plan-time iter: 2+ (tranche seçimi + coverage math).

---

## 4. Rollout

```
H6 (CI retry)  ──────┐
                      ├─→ both merged
H5 (obs fix)   ──────┘       ↓
                           H4 (waiver cleanup)
                              ↓
                           H2 (FS lock parity)
                              ↓
                           H1 (_internal coverage)
                              ↓
                         release(v3.8.0)
```

**v3.8.0 total estimate:**
- +10-15 test pin
- +2-3 CI workflow line changes (H6)
- +2 docs files (H2 audit + H1 tranche table)
- Code diff: moderate (lock migration + test updates)

---

## 5. Resolved design decisions (Codex iter-1 AGREE)

1. **F3 → v3.8 H5 fold** (not v3.7.1 patch). Bulgu additive observability; correctness/persistence invariant kırmıyor.
2. **H6 kapsam:** `test.yml` + `publish.yml` her ikisi. SSL/TLS flake sadece test workflow'a özgü değil.
3. **H4 revival değil removal.** Marker revival ayrı design PR konusu, v3.8 cleanup dışı.
4. **H3 drop or defer.** 2 test call-site için standalone PR değmez; başka cleanup'la fold edilebilir (v3.8 dışında).
5. **Paralelism hat modeli:** micro-PR lane (H6 + H5) + core lane (H2 → H1), H4 micro'dan biri merge olduktan sonra.
6. **`H1` sonra `H2`** — coverage daralması post-lock behavior'a göre olmalı; sırası mahkum.
7. **Plan-time iter beklentisi:** H5/H6/H4 = 0-1 iter. H2/H1 = 2+ iter.

---

## 6. Explicit non-contracts

- v3.8 runtime feature surface'i büyütmez.
- `save_store()` public symbol v3.8 içinde silinmez (v4.0 scope).
- `_internal` coverage tranche full sweep değildir.
- `quality_waiver` marker kaldırılır; enforcement yok.
