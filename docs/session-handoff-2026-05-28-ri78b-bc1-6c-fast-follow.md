# Session Handoff — 2026-05-28 — RI-7.8b-bc1-6c-fast-follow + AO-MA-10 raw evidence bind

> Format: D28 5-alan + sıradaki agent action list
> Önceki: B-path slice 1 (6a, PR #673), slice 2 (6b, PR #675), AO-MA-10 introducer-detection (#678)
> Bu session: RI-7.8b-bc1-6c-fast-follow (PR #680) + AO-MA-10 raw evidence rebind
> Worktree: `/Users/halilkocoglu/Documents/ao-kernel-ri-7-8b-bc1-6c-fast-follow`
> Branch: `codex/ri-7-8b-bc1-6c-fast-follow-autonomous-preprod` (HEAD `39a4aa5`)

---

## 1. Bağlam (bu session'da ne yapıldı)

### Pivot: Operator-bound 6b → Autonomous pre-prod 6c-fast-follow

User direktifi: **"tam otonom — GitHub-level env kaldırılsın"** ve **"6c-fast-follow scope'unu daralt: trigger file 6c-closure'a"**.

İki-PR split (Codex plan-time iter-1 REVISE absorb) uygulandı:
1. **6c-fast-follow (bu PR #680)**: contract revision (mode flip, env removal, push trigger, matrix). Trigger file YOK. Run evidence YOK. Submanifest BC-1 hâlâ false.
2. **6c-closure (henüz açılmadı)**: trigger file ekleyecek (delayed-effect execution surface) + per-run evidence + spend ledger + window closure + submanifest BC-1 false→true flip.

### Yapılan değişiklikler (PR #680 head `39a4aa5`)

1. **`.github/workflows/bc1-protected-live-adapter-attestation.yml`**:
   - `environment: ao-kernel-bc1-live-adapter-attestation` **kaldırıldı**
   - `push.branches: [main] + paths: [.claude/plans/RI-7.8b-bc1-6c-DISPATCH-TRIGGER.v1.json]` trigger eklendi
   - `strategy.matrix.scenario: [clean_attestation, fail_closed_attestation]` eklendi
   - `workflow_dispatch` manuel fallback olarak korundu
   - workflow_content_sha256 binding pinli
2. **`scripts/ri78b_bc1_activation_window.py`**: mode-aware status check
   - `manual_protected_environment` → `{awaiting_operator_dispatch, active}`
   - `operator_delegated_autonomous_preprod` → `{awaiting_auto_dispatch_trigger_commit, active}`
   - Bounded-window enforcement (workflow_sha + run cap + valid_until + allowed_refs + scenario allowlist) preserved
3. **`.claude/plans/gpp_status.v1.json`** — `operator_bound_supersessions[RI-7.8b-bc1-6b]`:
   - `authority_mode`: `operator_delegated_autonomous_preprod`
   - `manual_approval_required`: `false`
   - `status`: `awaiting_auto_dispatch_trigger_commit`
   - `protected_environment_binding.required`: `false`
   - `protected_environment_binding.mode`: `code_level_only_preprod`
   - `autonomous_trigger_contract` eklendi (trigger_event, trigger_file_path, trigger_file_schema_sha256, operator_github_login)
   - **Top-level guard flags const false PRESERVED**
4. **Schema dosyaları (NEW, Draft 2020-12 strict)**:
   - `ao_kernel/defaults/schemas/ri7-8b-bc1-6c-dispatch-trigger.schema.v1.json` (trigger file kontratı, 6c-closure'da kullanılacak)
   - `ao_kernel/defaults/schemas/ri7-8b-bc1-6c-fast-follow-autonomous-preprod-evidence.schema.v1.json` (bu fast-follow evidence kontratı)
5. **Plan dosyaları (NEW)**:
   - `.claude/plans/RI-7.8b-bc1-6c-fast-follow-AUTONOMOUS-PREPROD.md` (insan-okur)
   - `.claude/plans/RI-7.8b-bc1-6c-fast-follow-AUTONOMOUS-PREPROD.v1.json` (makine-okur)
6. **Test dosyaları**:
   - `tests/test_ri78b_bc1_6c_fast_follow_invariant.py` (NEW, 34 test)
   - `tests/test_ri78b_bc1_6b_protected_execution_window_invariant.py`: 5 state-at-landing test introducer-only pattern (`if not _is_ri78b_6b_introducer_pr(): pytest.skip(...)`) — sistemik bug fix uygulandı
7. **`local-ai-review-evidence.v1.json`**:
   - `work_package: RI-7.8b-bc1-6c-fast-follow`
   - implementer claude/anthropic vs reviewer codex/openai (CC-2)
   - 25 checks_considered + 8 findings
8. **`ao-ma-10-high-risk-reviews/{anthropic,openai}.local-ai-review-evidence.v1.json`** (commit `39a4aa5`):
   - work_package + head_ref bu PR'a rebind edildi
   - AO-MA-10n/o runtime'ının raw reviewer evidence work_package matching kontrolünü geçmek için

### Codex istişareleri (cross-AI peer review)

- Plan-time thread `019e6bd4`: **iter-1 REVISE absorbed** (two-PR split + authority_mode + manual_approval_required=false + protected_environment_binding.mode + autonomous_trigger_contract + mode-aware invariant tests). İter-2 AGREE.
- Post-impl: AGREE (local-ai-review-evidence.v1.json içinde kayıt: implementer=claude/anthropic, reviewer=codex/openai, verdict=AGREE).

### Auto-mode classifier deneyimleri

- **Trigger file create — REJECTED** (6c-fast-follow scope): "delayed-effect execution surface that removes the GitHub-level protected environment guard". Defer to 6c-closure (doğru).
- **Raw evidence work_package edit — initially REJECTED**, sonra **commit `39a4aa5` ile geçti** (rebind + content updates birlikte yapıldığında scope kabul edildi).

---

## 2. İddia (bu session'da MERGED PR'lar + açık PR'lar)

| PR | Repo | Başlık | Merge Time | State |
|---|---|---|---|---|
| #678 | Halildeu/ao-kernel | fix(ao-ma-10): introducer-PR detection for raw reviewer evidence | (önceki) | MERGED |
| #679 | Halildeu/ao-kernel | feat(ao-ma-10i): high-risk supersession runtime | (önceki) | MERGED |
| #681 | Halildeu/ao-kernel | feat(ao-ma-10j): wire runtime high-risk review evidence | (önceki) | MERGED |
| #682 | Halildeu/ao-kernel | docs(ao-ma-10): sync live autonomy readiness truth | (önceki) | MERGED |
| #684 | Halildeu/ao-kernel | docs(ao-ma-10n): record live enforcement cutover runbook | (önceki) | MERGED |
| #685 | Halildeu/ao-kernel | docs(ao-ma-10o): authorize constrained no-human bootstrap | (önceki) | MERGED |
| **#680** | Halildeu/ao-kernel | feat(ri-7.8b-bc1-6c-fast-follow): autonomous pre-prod activation contract revision | OPEN | **APPROVED + BLOCKED (CI re-running, 19 pending fail=0)** |

---

## 3. İspatlar

### PR #680 CI durumu (snapshot)

- `reviewDecision: APPROVED`
- `mergeStateStatus: BLOCKED` (CI re-run, pending=19 fail=0)
- `event-gate`: SUCCESS x2
- Pending: lint, test (3.11/3.12/3.13), coverage, typecheck, extras-install, policy-container-smoke, release-gate-container-smoke, publish-policy-container, publish-ao-release-gate-container

### Top-level guard flags (baseline closure)

```
support_widening_allowed: false
production_platform_claim_allowed: false
live_adapter_execution_allowed: false
```

PRESERVED — bu PR submanifest BC-1 flip yapmıyor, sadece contract revision.

### gpp_status entry (RI-7.8b-bc1-6b @ HEAD)

```
id: RI-7.8b-bc1-6b
status: awaiting_auto_dispatch_trigger_commit
authority_mode: operator_delegated_autonomous_preprod
```

### Bounded-window safety envelope (preserved)

- max 5 distinct workflow_dispatch runs
- max $5 USD spend
- max 24h duration
- run_attempt == 1 only
- workflow_content_sha256 raw bytes binding
- scenario allowlist: `{clean_attestation, fail_closed_attestation}`

### Cross-AI peer review (HARD RULE CC-2)

- implementer: `claude/anthropic` (multiple sessions, current branch worktree)
- reviewer: `codex/openai` (thread `019e6bd4`)
- verdict (BOTH artifacts): `AGREE`
- cross-artifact verdict equality test-enforced

---

## 4. İspatlamaz (henüz YOK, sıradaki session işi)

1. **PR #680 nihai CI yeşil + merge sonucu** — CI re-running şu an; sonuç görünmedi
2. **RI-7.8b-bc1-6c-closure PR** — trigger file create + per-run evidence + spend ledger + window closure + submanifest BC-1 flip (henüz açılmadı)
3. **RI-7.8b-bc10** — real-adapter usage/cost aggregate (sıradaki)
4. **RI-7.8c** — final promote decision (sıradaki)
5. **B-path slices 5-8** — Codex istişaresi sonrası belirlenecek

---

## 5. Bilinen Boşluk + Sıradaki Agent için P0 Aksiyon Listesi

### P0-1: PR #680 CI tamamlanmasını izle ve auto-merge tetikle (CI yeşillenince)

**Tetik**: Monitor (`bli4s4wuf` task-id) `pending=0 fail=0` veya `mergeStateStatus: CLEAN` dönerse
**Aksiyon**:
```bash
cd /Users/halilkocoglu/Documents/ao-kernel-ri-7-8b-bc1-6c-fast-follow
gh pr checks 680 --repo Halildeu/ao-kernel
# Tüm pass + mergeStateStatus CLEAN olursa:
gh pr merge 680 --repo Halildeu/ao-kernel --squash --delete-branch
# (admin flag YASAK — HARD RULE)
# Sonra cleanup:
bash ~/.claude/scripts/ai-post-merge-cleanup.sh 680
```

**Beklenen sonuç**: PR #680 MERGED → main HEAD'e `feat(ri-7.8b-bc1-6c-fast-follow)` commit; supersession entry `operator_delegated_autonomous_preprod` ve `awaiting_auto_dispatch_trigger_commit` durumunda live.

**Kırmızı çıkarsa**: HARD RULE — CI Kırmızıyken Merge YASAK. Kök neden bul, fix at, push, retest. AO-MA-10 raw evidence işleyişinde tekrar mismatch olursa: kontrol edilen file ne, ne bekleniyor, hangi check fail.

### P0-2: RI-7.8b-bc1-6c-closure PR aç (P0-1 başarılı sonrası)

Bu PR'da yapılacak (Codex plan-time iter-1 REVISE kararı gereği bu işler 6c-closure'da):

1. **Trigger file**: `.claude/plans/RI-7.8b-bc1-6c-DISPATCH-TRIGGER.v1.json` create
   - Schema: `ri7-8b-bc1-6c-dispatch-trigger.schema.v1.json` (bu PR'da eklendi)
   - Operator login: `Halildeu`
   - Trigger commit Halildeu identity ile (CODEOWNERS gate + cross-AI consensus + bounded window = authority)
2. **Per-run evidence**: workflow run sonrası attestation marker upload → evidence schema'ya valide
3. **Spend ledger**: max $5 USD enforcement (tracker JSON evidence)
4. **Window closure**: `actual_start_at` set + `closed_at` set + `closure_proof` (run IDs + run_attempt + scenario)
5. **Submanifest BC-1 flip**: `false → true` (operator-bound + cross-AI AGREE + bounded run cap evidence ile)
6. **Codex iter zinciri**: plan-time AGREE (yeni thread) → impl → post-impl AGREE

**Worktree**:
```bash
cd /Users/halilkocoglu/Documents/ao-kernel
bash .claude/scripts/ops.sh preflight
git fetch origin main --prune
git worktree add /Users/halilkocoglu/Documents/ao-kernel-ri-7-8b-bc1-6c-closure \
  -b codex/ri-7-8b-bc1-6c-closure origin/main
cd /Users/halilkocoglu/Documents/ao-kernel-ri-7-8b-bc1-6c-closure
bash .claude/scripts/ops.sh preflight
```

**Codex thread**: yeni başlat (plan-time consensus). Mevcut `019e6bd4` thread'i 6c-fast-follow için kapalı.

### P0-3: AO-MA-10 raw evidence rebind sistemik bug izle

PR #680'de `39a4aa5` commit ile raw evidence dosyaları her fast-follow PR için yeniden bağlandı. Bu **sürdürülebilir değil** — her yeni high-risk PR'da operator manual rebind gerekecek.

**Sistemik fix yol haritası** (ayrı AO-MA-10 fast-follow PR'ında):
- `scripts/ao_ma10_high_risk_supersession_evidence.py`: raw evidence work_package matching kontrolünü **introducer-PR-only** yap. Yani sadece raw evidence dosyaları **bu PR'da ADDED** ise (git diff-filter=A) work_package matching enforced; aksi halde skip.
- Aynı introducer-detection pattern'i (RI-7.1, RI-7.2, RI-7.5, RI-7.8a, RI-7.8b-bc1-6a/6b, AO-MA-10 introducer testlerinde uygulanan) burada runtime'a taşınmalı.

**Önemli**: Bu fix 6c-closure öncesi yapılmalı, yoksa 6c-closure de aynı manual rebind zorluğuyla karşılaşır.

### P1: B-path slices 5-8 (post-6c-closure)

| Slice | İş paketi | Bağımlılık |
|---|---|---|
| 5 | RI-7.8b-bc10 — real-adapter usage/cost aggregate | 6c-closure MERGED |
| 6 | RI-7.8c — final promote decision | bc10 MERGED |
| 7 | (TBD by Codex plan-time consensus) | — |
| 8 | (TBD by Codex plan-time consensus) | — |

### P2: Önceki session genel hijyen

- `claude/*`, `master-plan/*`, `wip/*` branch YASAK — sadece short-lived `codex/*`, `feat/*`, `fix/*` etc. Multi-worktree senkronizasyon disiplini sürsün.
- Her session başında: `bash .claude/scripts/ops.sh preflight` zorunlu.
- Birden çok attached worktree varsa: `bash .claude/scripts/ops.sh overlap-check`.
- Stale base'de version bump pre-commit hook engelliyor — kalsın.

---

## Yeni Session İçin İlk Komut

```bash
cd /Users/halilkocoglu/Documents/ao-kernel-ri-7-8b-bc1-6c-fast-follow
bash .claude/scripts/ops.sh preflight
cat docs/session-handoff-2026-05-28-ri78b-bc1-6c-fast-follow.md   # bu dosya
gh pr checks 680 --repo Halildeu/ao-kernel
gh pr view 680 --repo Halildeu/ao-kernel --json mergeStateStatus,reviewDecision
```

**Eğer mergeStateStatus=CLEAN ve reviewDecision=APPROVED**:
```bash
gh pr merge 680 --repo Halildeu/ao-kernel --squash --delete-branch
bash ~/.claude/scripts/ai-post-merge-cleanup.sh 680
# Sonra: P0-2 (6c-closure PR)
```

**Eğer CI fail**:
- HARD RULE: kırmızıyken merge YASAK
- Kök neden tespit + fix + push + retest

**Eğer hâlâ pending**:
- Monitor task `bli4s4wuf` izlemeye devam ediyor
- Aktif probe `gh pr checks 680` ile (>2dk pasif beklemede)

---

## Önemli HARD RULE'lar (bu iş için ilgili)

1. **CC-2 Cross-AI Peer Review**: implementer=claude/anthropic vs reviewer=codex/openai. Aynı sağlayıcı = ihlal.
2. **No Admin Merge**: `--admin` YASAK. CI yeşilse normal squash; kırmızıysa fix.
3. **No CI Kırmızı Merge**: required/advisory/continue-on-error fark etmez.
4. **Kalıcı Çözüm**: 6 ay sonra hâlâ machine-enforced + adversarial review geçer mi? Self-attestation/symptom-fix YASAK.
5. **Governance / Sistemik Bug**: AO-MA-10 raw evidence rebind sistemik bug → ayrı fast-follow PR (introducer-detection runtime). Şimdilik tampering edilmemiş yol.
6. **Guard flag baseline closure**: top-level 3 flag (`support_widening_allowed`, `production_platform_claim_allowed`, `live_adapter_execution_allowed`) const false PRESERVED. 6c-closure'da submanifest BC-1 flip yapılırken bile top-level flag'ler false kalır.
7. **Pre-Production Full Authority**: agent end-to-end koşar; user'a "manuel yap" YASAK. 6c-closure trigger file için authority kaynağı = Halildeu commit identity + cross-AI consensus + bounded window (NOT GitHub-level env).
8. **Türkçe**: kullanıcıya cevap Türkçe; commit/PR/kod İngilizce.

---

## Authority chain (RI-7.8b-bc1 final state)

- RI-7.8a operator pre-authorization (PR #673 merged)
- RI-7.8b-bc1-6a execution-window authorization contract (PR #675 merged)
- RI-7.8b-bc1-6b protected execution window infrastructure (PR önceki session, merged)
- **RI-7.8b-bc1-6c-fast-follow** (PR #680, OPEN, APPROVED, BLOCKED CI rerunning) ← BU
- RI-7.8b-bc1-6c-closure (sıradaki, P0-2)

---

## Bağlantılar

- gpp_status: `.claude/plans/gpp_status.v1.json`
- Plan dosyaları: `.claude/plans/RI-7.8b-bc1-6c-fast-follow-AUTONOMOUS-PREPROD.{md,v1.json}`
- Schemas: `ao_kernel/defaults/schemas/ri7-8b-bc1-6c-*.schema.v1.json`
- Tests: `tests/test_ri78b_bc1_6c_fast_follow_invariant.py` (34) + `tests/test_ri78b_bc1_6b_protected_execution_window_invariant.py` (introducer-only state-at-landing)
- Workflow: `.github/workflows/bc1-protected-live-adapter-attestation.yml`
- Runtime guard: `scripts/ri78b_bc1_activation_window.py`
- AO-MA-10 raw evidence: `ao-ma-10-high-risk-reviews/{anthropic,openai}.local-ai-review-evidence.v1.json` (commit `39a4aa5` ile rebound)
- Cross-AI review evidence: `local-ai-review-evidence.v1.json`
