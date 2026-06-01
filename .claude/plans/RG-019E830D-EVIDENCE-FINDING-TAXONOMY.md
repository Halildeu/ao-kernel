# RG-CONCLUSION-SEMANTICS 019e830d Extension — Evidence Finding Taxonomy

**Status:** Implementing (codex/release-gate-review-evidence-action-required)
**Codex thread:** `019e830d` (plan-time REVISE, `ready_for_impl: true`)
**SSOT:** `ao_kernel/ao_release_gate.py` (`_REVIEW_ACTION_FINDINGS`)
**Related plan:** `RG-CONCLUSION-SEMANTICS C-prime wrapper` (Codex thread `019e65c3`)

## 1. Sorun (V5 P0-4 trigger)

PR #764 (`fix/test-yml-required-no-event-gate` — required test.yml job'ları
shadow-skip etmesini engelleyen küçük workflow düzeltmesi) `ao-release-gate`
gate'inde iki bulgu ile reddedildi:

- `ao_release_gate_review_evidence_not_accepting`
- `ao_release_gate_review_evidence_context_unverifiable`

İki bulgu da mevcut taksonomide `failure` sınıfına düşüyor (sadece
`ao_release_gate_high_risk_human_review_missing` `review_action`).
Sonuç: wrapper exit code 1 → required check kırmızı → merge bloklu.

Functional/runtime/semantic kod değişikliği YOK; sadece CI workflow fix.
GPP closeout (7/7 work package complete, üç guard flag const false,
`keep_narrow_stable_runtime` kararı) sonrası yeni evidence üretimi
beklenmiyor; operatör CODEOWNER review eksik. Bu durum kırmızı CI
sinyaliyle değil, "operatör action required" sinyaliyle gösterilmeli.

## 2. Codex iter-1 (plan-time)

**Verdict:** `REVISE`, `ready_for_impl: true`.

**Kabul edilenler:**

- Fix yönü doğru — bu iki finding `review_action` sınıfına taşınmalı.
- GPP closeout flag ile evidence skip ETME — gate boundary'sini fazla
  gevşetir; GPP-9 closeout "support widening / production claim / live
  adapter yok" demek; review authority ihtiyacını kaldırmaz.
- Bypass riski sadece required-check topology drift ederse açılır.
  `allow=false` kararı değişmez; sadece check-run conclusion + wrapper
  exit code shift olur.

**Reddedilenler:**

- Daha derin refactor şu an gerekli değil.
- "Closed GPP'de review_evidence skip" yanlış yönde.

**Eklenen invariantlar:**

1. `_unbound` (`review_evidence_context_unbound`) failure kalmalı —
   forged / mismatched binding head SHA drift demek; review_action
   değil.
2. `_missing` (`review_evidence_missing`) failure kalmalı — artifact
   YOK; procedural değil.
3. `_schema_invalid` (`review_evidence_schema_invalid`) failure kalmalı
   — broken artifact; procedural değil.
4. Boundary violations review-action ile mixed olduğunda failure +
   exit 1 kalmalı (`admin_bypass_requested`, `forbidden_secret_context`,
   `live_adapter_execution_requested`, `gpp_boundary_open`,
   `pat_backed_bot_actor`, `agent_release_authority`).
5. `build_technical_check_run` `[not_accepting]` enforce → `success`
   (was: `failure`).
6. `build_review_check_run` `[not_accepting]` enforce → `action_required`
   (was: `success`).
7. CLI wrapper exit code testi faydalı olur (atlandı; future-follow-up;
   gerçek Python-level wrapper_exit_code direct çağrı testleri kapsam
   sağlıyor).

## 3. Değişiklik scope

### 3a. Source

`ao_kernel/ao_release_gate.py`:

- `_REVIEW_ACTION_FINDINGS` set'ine iki finding eklenir:
  - `ao_release_gate_review_evidence_not_accepting`
  - `ao_release_gate_review_evidence_context_unverifiable`
- Set docstring'i procedural-evidence semantiğini açıklar.
- `finding_conclusion_kind` docstring genişler (sibling evidence
  failure'ları net listeler).
- `wrapper_exit_code` docstring genişler (procedural vs structural
  evidence failure ayrımı).
- `RG-CONCLUSION-SEMANTICS` block comment "019e830d extension" ile
  güncellenir.

### 3b. Tests

`tests/test_ao_release_gate.py`:

- `TestFindingConclusionKind`:
  - `test_review_missing_is_review_action` (mevcut, kalır)
  - `test_review_evidence_not_accepting_is_review_action` (YENİ)
  - `test_review_evidence_context_unverifiable_is_review_action` (YENİ)
  - `test_branch_stale_is_stale` (mevcut, kalır)
  - `test_real_violation_is_failure` (mevcut — iki finding listeden
    çıkarıldı)
  - `test_structural_evidence_defects_remain_failure` (YENİ — 3 finding)
  - `test_boundary_violations_remain_failure` (YENİ — 6 finding)
  - `test_none_finding_defaults_to_failure` (mevcut)
  - `test_unknown_finding_defaults_to_failure` (mevcut)
- `TestConclusionForFindings`:
  - `test_any_failure_wins` (revize — `not_accepting` yerine
    `forbidden_secret_context` boundary-violation kullan)
  - `test_structural_evidence_failure_wins_over_procedural` (YENİ)
  - `test_evidence_procedural_findings_are_action_required` (YENİ)
  - `test_evidence_procedural_mixed_with_human_review_is_action_required`
    (YENİ)
- `TestWrapperExitCode`:
  - `test_real_violation_returns_one` (revize — `forbidden_secret_context`)
  - `test_structural_evidence_missing_returns_one` (YENİ)
  - `test_structural_evidence_schema_invalid_returns_one` (YENİ)
  - `test_structural_evidence_context_unbound_returns_one` (YENİ)
  - `test_procedural_evidence_not_accepting_returns_zero` (YENİ)
  - `test_procedural_evidence_context_unverifiable_returns_zero` (YENİ)
  - `test_review_plus_procedural_evidence_returns_zero` (YENİ)
  - `test_procedural_evidence_plus_violation_returns_one` (YENİ)
  - `test_procedural_evidence_plus_structural_evidence_returns_one` (YENİ)
  - `test_admin_bypass_violation_returns_one` (YENİ)
- `TestBuildTechnicalCheckRun`:
  - `test_real_violation_is_failure_in_enforce` (revize —
    `forbidden_secret_context`)
  - `test_structural_evidence_missing_is_failure_in_enforce` (YENİ)
  - `test_procedural_evidence_alone_is_success_in_enforce` (YENİ — 2
    finding)
  - `test_review_plus_violation_is_failure_in_enforce` (revize —
    boundary violation kullan)
  - `test_procedural_plus_structural_evidence_is_failure_in_enforce`
    (YENİ)
  - `test_shadow_mode_neutral_for_blocker` (revize — `missing`)
- `TestBuildReviewCheckRun`:
  - `test_real_violation_ignored_in_review_check` (revize —
    `forbidden_secret_context`)
  - `test_structural_evidence_missing_ignored_in_review_check` (YENİ)
  - `test_procedural_evidence_is_action_required_in_review_check` (YENİ)
  - `test_procedural_evidence_is_neutral_in_review_check_shadow` (YENİ)

### 3c. Workflow / Schema / Config

YOK — finding code taksonomisi public API'ya zaten string olarak
yansıyor; type değişikliği yok. Decision JSON shape değişmiyor.

## 4. Out-of-scope

- CLI wrapper exit code subprocess testi (Codex önerdi; mevcut
  Python-level direct çağrı testleri taksonomi shift'i tam kapsadığı
  için future-follow-up).
- Mevcut PR #764 evidence dosyası eklemek (governance hijyeni; bu
  PR'ın amacı taksonomi sertleştirme).
- GPP closeout flag ile review_evidence skip (Codex reddetti; bypass
  riski yüksek).

## 5. Etki

- **PR #764:** taksonomi merge sonrası kendi gate'i kırmızı CI üretmez:
  - Legacy wrapper `ao-release-gate` artık kırmızı dönmez (exit 0).
  - Yeni `ao-release-gate-technical` `success` döner (procedural findings
    filtered out).
  - Yeni `ao-release-gate-review` `action_required` döner — required
    check ise merge **hâlâ bloklu**.
  - Merge için: operatör CODEOWNER review submit eder, VEYA review
    evidence file commit + accept edilir, VEYA context_unverifiable
    sebebi external (network/eventual consistency) ise re-run.
  - Otomatik "rerun + merge" YOK — `action_required` required check
    satisfaction değildir.
- **Gelecek high-risk PR'lar:** sadece `review_evidence_not_accepting`
  veya `review_evidence_context_unverifiable` bulgusu olduğunda
  "kırmızı CI" yerine "operatör action required" gösterir; doğru
  semantik signal.
- **Structural evidence defects** (`review_evidence_missing`,
  `review_evidence_schema_invalid`, `review_evidence_context_unbound`):
  hâlâ failure; kırmızı CI; gate sertliği korunur. Bu durumda
  evidence artifact'in kendisi bozuk veya yok — procedural değil,
  defect; üretilmesi/düzeltilmesi gerek.
- **Boundary violations** (admin bypass, secret context, live adapter,
  GPP boundary open, PAT-backed bot, AI release authority):
  taksonomi taraması dışında; failure kalır.

## 6. Acceptance

- Local test: `pytest tests/test_ao_release_gate.py -x` (111 pass).
- Broader local: `pytest tests/ -k "release_gate or ao_ma10" -x` (440 pass + 2 skip).
- Local lint: `ruff check ao_kernel/ tests/`.
- Local type: `mypy ao_kernel/ scripts/ --ignore-missing-imports`.
- Cross-AI post-impl review (Codex thread `019e830d` reply ile
  `019df...` veya yeni thread).
- PR squash mesajı: `Implementer: Anthropic Claude` /
  `Reviewer: OpenAI Codex` audit trail.

## 6.1. Required-check topology önkoşulu (operatör doğrulama)

Bu fix'in güvenliği, GitHub branch protection / ruleset üzerinde şu
iki check'in required + source-pinned olmasına bağlıdır:

- `ao-release-gate-technical`
- `ao-release-gate-review`

Eğer sadece legacy wrapper `ao-release-gate` required ise, bu patch
wrapper'ı yeşile çevirerek (review-action-only case) merge'i fazla
gevşetebilir. Repo SSOT (ao-ma-10 dual source-pinned model) bu modeli
destekliyor; ancak merge öncesi operatör live ruleset'i doğrulamalı:

```bash
gh api repos/Halildeu/ao-kernel/rules/branches/main \
  --jq '.[] | select(.type=="required_status_checks") | .parameters.required_status_checks[].context'
```

Beklenen output (en az):
```
ao-release-gate-technical
ao-release-gate-review
```

Codex iter-2 absorb: live ruleset bu turda sandbox/TMP/network kısıtı
sebebiyle Codex tarafında doğrulanamadı. Merge öncesi operatör veya
`scripts/ao_release_gate_publish_check_runs.py` kontrolü gerek.

## 7. Bağlantı

- `RG-CONCLUSION-SEMANTICS` C-prime wrapper (thread `019e65c3`) — bu
  extension onun finding sub-classification'ını genişletir.
- V5 P0-4 (PR #764 CI shadow-skip permanent fix) — bu fix unblock
  eder; PR #764 ayrı concern.
- HARD RULE — Uzun Vadeli Kalıcı Çözüm: review_evidence skip yerine
  taksonomi düzeltme (Codex onayı ile).
- HARD RULE — Cross-AI Peer Review: implementer Anthropic Claude;
  reviewer OpenAI Codex.
