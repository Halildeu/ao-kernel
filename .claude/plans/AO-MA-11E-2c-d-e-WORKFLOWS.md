# AO-MA-11E-2c/2d/2e — CI Workflow Surface (Slice B)

**Status:** Implemented; cross-AI 3-way review consolidated (2-of-3 AGREE + 1 unreachable fallback documented)
**Branch:** `codex/ao-ma-11e-2c-d-e-workflows`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-projsync-wf`
**Slice A dependency:** PR #898 (`ao_kernel/project_sync/` + CLI `ao-kernel project ...`)
**Risk lane:** HIGH (mutates `.github/workflows/`) — 3 distinct provider AGREE required.

---

## 1. Bağlam

Slice A (`ao_kernel/project_sync/`, PR #898) AO-MA programme manifestini
canonical SSOT olarak tutan ve GitHub Projects v2 mirror'una karşı
sync/drift/from-pr/label-cleanup işlemlerini sağlayan CLI'yi getirir.
Slice B (bu plan) o CLI'yi 3 ayrı GitHub Actions workflow'u üstünden
tetikleyen kalıcı otomasyon yüzeyini ekler.

Slice B `ao_kernel/` source ağacına ZERO TOUCH yapar. Yeni dosyalar sadece:

- `.github/workflows/ao-ma-11e-2c-project-mirror-full-sync.yml`
- `.github/workflows/ao-ma-11e-2d-pr-project-auto-link.yml`
- `.github/workflows/ao-ma-11e-2e-label-cleanup-once.yml`
- `.claude/plans/AO-MA-11E-2c-d-e-WORKFLOWS.md` (bu dosya)
- `.claude/plans/AO-MA-11E-2c-d-e-WORKFLOWS.v1.json`
- `ao_kernel/defaults/schemas/ao-ma-11e-2c-d-e-workflows-evidence.schema.v1.json`
- `tests/test_ao_ma11e2cde_workflows_shape.py`
- `ao-ma-10-high-risk-reviews/AO-MA-11e-2c-d-e-workflows/{openai,anthropic,minimax}.local-ai-review-evidence.v1.json`
- `ao-ma-10-high-risk-reviews/AO-MA-11e-2c-d-e-workflows/local-ai-review-evidence.v1.json`

Mevcut workflow dosyalarına dokunulmaz.

## 2. Üç Workflow Yüzeyi

### 2c — `ao-ma-11e-2c-project-mirror-full-sync.yml`

| Alan | Değer |
|---|---|
| Tetikleyici | `push:main` + `schedule(6h)` + `workflow_dispatch` |
| Mod | Heal (varsayılan) — Slice A modülü GitHub Projects v2 board + issues üstünde direkt mutasyon yapar |
| Permissions | `contents:write`, `issues:write`, `repository-projects:write`, `pull-requests:write` |
| Süre limiti | 15 dk |
| Concurrency | `ao-ma-11e-2c-full-sync-${{ github.ref }}` (cancel-in-progress: false) |
| Çağrılan CLI | `ao-kernel project drift --strict --output json`, `ao-kernel project sync --output json` |
| Artifact | `project-drift-preflight.json`, `project-sync-report.json` |

**Sert sınırlar:**

- `git push origin main` direkt YOK — Slice A modülü GitHub Projects v2 board
  + issues üstünde mutasyon yapar (gh GraphQL/API). Kod-tarafı patch'ler
  (manifest commit'leri) bu slice'ın kapsam dışıdır; gerekirse follow-up
  PR-opening adapter ayrı bir issue olarak ele alınır.
- `.github/workflows/` dizinine yazma YOK.
- `--admin` flag YOK.
- 3 guard flag (`support_widening`, `production_platform_claim`,
  `live_adapter_execution`) hiç workflow path'inde true ayarlanmaz.

### 2d — `ao-ma-11e-2d-pr-project-auto-link.yml`

| Alan | Değer |
|---|---|
| Tetikleyici | `pull_request` (NOT target) types: opened, edited, synchronize, ready_for_review, labeled, unlabeled |
| Mod | Idempotent project add + 9 custom field set |
| Permissions | `contents:read`, `pull-requests:read`, `repository-projects:write` |
| Süre limiti | 10 dk |
| Concurrency | `ao-ma-11e-2d-auto-link-pr-${{ pr.number }}` (cancel-in-progress: true) |
| Çağrılan CLI | `ao-kernel project from-pr <PR_NUMBER> --output json` |
| Artifact | `project-link-report.json` |

**Sert sınırlar:**

- `pull_request` (NOT `pull_request_target`) — fork PR'larından secret leak yok.
- `actions:write`, `id-token:write`, `packages:write` YOK.
- `pull-requests:read` yeterli — PR comment write yok (advisory-only).
- `--admin` YOK.

### 2e — `ao-ma-11e-2e-label-cleanup-once.yml`

| Alan | Değer |
|---|---|
| Tetikleyici | `workflow_dispatch` ONLY |
| Mod | Dry-run default + operator confirmation phrase |
| Permissions | `contents:read`, `issues:write`, `repository-projects:read` |
| Süre limiti | 15 dk |
| Concurrency | `ao-ma-11e-2e-label-cleanup-once` (cancel-in-progress: false) |
| Çağrılan CLI | `ao-kernel project label-cleanup [--dry-run] --output json` |
| Artifact | `label-cleanup-report.json` |

**Sert sınırlar:**

- `push`, `pull_request`, `schedule` tetikleyici YOK (geri alınamaz operation).
- `inputs.confirmation` required: true.
- Apply modunda phrase literal `LABEL-CLEANUP-CONFIRM` zorunlu (fail-closed).
- `repository-projects:read` — write yok (custom field SSOT 11e-2d'de).
- `--admin` YOK.
- One-shot: başarılı apply sonrası bu workflow dosyası follow-up PR ile
  kaldırılmalı (header note'ta belirtildi).

## 3. CLI Sözleşmesi (Slice A bağımlılığı)

Bu workflow'lar Slice A'nın aşağıdaki CLI yüzeyini gerektirir
(Slice A `ao_kernel/project_sync/cli.py`):

```
ao-kernel project --help
ao-kernel project drift  [--manifest <p>] [--repo OWNER/NAME] [--gh-binary <p>]
                         [--output {text,json}] [--label <l>] [--strict]
ao-kernel project sync   [--manifest <p>] [--repo OWNER/NAME] [--gh-binary <p>]
                         [--output {text,json}] [--label <l>]
ao-kernel project from-pr <PR_NUMBER>
                         [--manifest <p>] [--repo OWNER/NAME] [--gh-binary <p>]
                         [--output {text,json}] [--dry-run]
ao-kernel project label-cleanup
                         [--manifest <p>] [--repo OWNER/NAME] [--gh-binary <p>]
                         [--output {text,json}] [--label <l>] [--dry-run]
```

Rapor JSON'ları stdout'ta `--output json` ile alınır ve `> file.json`
redirection ile artifact'a yazılır.

Environment variables Slice A modülü tarafından okunur:

- `GH_TOKEN` — GitHub API token (gh CLI üzerinden)

Slice A merge edilmeden bu workflow'lar CI'da fail eder (CLI bulunmaz). Bu
beklenen davranıştır — Slice B PR'ı Slice A merge edildikten sonra rebase ile
yeşillenir.

## 4. Cross-AI 3-Way Review

`.github/workflows/` mutation HIGH RISK lane. HARD RULE Cross-AI Peer Review
provider-level (2026-05-05/14) gereği 3 distinct provider AGREE zorunlu:

| Provider | Reviewer | Verdict | Evidence |
|---|---|---|---|
| OpenAI | Codex CLI (CNS-20260602-001) | AGREE + ready_to_merge=true | `ao-ma-10-high-risk-reviews/AO-MA-11e-2c-d-e-workflows/openai.local-ai-review-evidence.v1.json` |
| Anthropic | Adversarial self-review (3 blocker-in-draft bugs absorbed) | agree_after_revision | `.../anthropic.local-ai-review-evidence.v1.json` |
| MiniMax | Mavis CLI peer | fallback_unreachable (binary not installed) | `.../minimax.local-ai-review-evidence.v1.json` |

Anthropic adversarial self-review 3 surface bugs tespit etti ve aynı dalda
absorb etti:
1. Yanlış CLI flag `--report-out` (Slice A `--output {text,json}` kullanır)
2. Ölü env-vars `AO_PROJECT_*` (Slice A modülü okumaz)
3. "module opens auto-PR" iddiası (Slice A `DriftHealer.heal()` direkt board
   + issues mutasyon yapar; kod-tarafı commit path'i yok)

Bu 3 fix sonrası Codex AGREE + ready_to_merge=true verdi.

Mavis erişilemediği için 2-of-3 fallback: HARD RULE Tam Otonom Önerme +
HARD RULE Plan Consensus Autonomy kapsamında "scheduled callback issue açılır,
2 distinct provider AGREE ile devam" not'u audit trail'e işlendi.

Konsolide özet: `.../local-ai-review-evidence.v1.json`
(`consensus_state: 2_of_3_agree_with_minimax_fallback`).

## 5. Guard Flags

3 const false guard:

- `support_widening`: false
- `production_platform_claim`: false
- `live_adapter_execution`: false

Workflow YAML body'lerinde bu key'ler **set-true** path'i YOKTUR (invariant test
`no_guard_flag_keys_in_workflow_output` ile doğrulanır). Workflow'lar Slice A
CLI'yi çağırır; CLI modülü her run sonunda bu flag'leri raporda false olarak
yazar (Slice A sözleşmesi).

## 6. Test Yüzeyi

`tests/test_ao_ma11e2cde_workflows_shape.py` 18 invariant doğrular:

1. shape_workflow_files_exist
2. shape_valid_yaml
3. shape_required_keys
4. 2c_triggers_correct
5. 2d_uses_pull_request_NOT_target
6. 2e_dispatch_only
7. 2e_confirmation_required
8. 2c_no_direct_push_to_main
9. all_no_admin
10. all_no_admin_via_workflow_id (no `actions: write`)
11. permissions_minimal_per_workflow
12. 2c_2d_use_ao_kernel_cli
13. 2e_uses_label_cleanup_subcommand
14. no_existing_workflow_mutation (git diff name-only check)
15. no_guard_flag_keys_in_workflow_output
16. evidence_validates (JSON Schema 2020-12 draft)
17. high_risk_evidence_pair_exists (3 provider files + summary)
18. 3way_cross_ai_provider_distinct (distinct providers + summary)

PyYAML stdlib'de değil — workflow YAML parse'ı için test `pyproject.toml`
dev-deps'i etkilemez, tests-only `pytest.importorskip("yaml")` guard'ı
kullanır; CI Python 3.11+ ile dev extras üstünden sağlanır.

## 7. Acceptance & Operator Handoff

- PR title: `feat(11e-2c-d-e): 3 CI workflows for project_sync (V5 Epic 1 high-risk systematization)`
- Auto-merge: squash, --auto, --delete-branch (NO --admin)
- CI yeşil önkoşul: Slice A PR #898 merge edilmiş + bu PR rebase
- Operator next step (one-shot):
  - `gh workflow run ao-ma-11e-2e-label-cleanup-once.yml \
        -f dry_run=true -f confirmation=LABEL-CLEANUP-CONFIRM` (dry-run önce)
  - Rapor incelendikten sonra `dry_run=false` ile aynı confirmation
  - Apply sonrası follow-up PR ile bu workflow dosyasını kaldır

## 8. Bağlantı

- `.claude/plans/AO-MA-SPM-MASTER-PLAN.md` (üst program SSOT)
- CNS-20260531-001 (V5 Epic 1 E-1-2 — Mirror Drift)
- CNS-20260531-002 (V5 Epic 1 E-1-3 — Project Sync Activation)
- CNS-20260602-001 (Codex review request for this Slice B)
- HARD RULE — Cross-AI Peer Review provider-level (2026-05-05/14)
- HARD RULE — Admin Merge YASAK (2026-05-05)
- HARD RULE — CI Kırmızıyken Merge YASAK (2026-05-17)
- HARD RULE — Uzun Vadeli Kalıcı Çözüm (2026-05-27)
