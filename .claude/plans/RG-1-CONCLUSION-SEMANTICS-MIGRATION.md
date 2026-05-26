# RG-1 — `ao-release-gate` Conclusion Semantics Migration (C-prime)

**Status:** ready for PR / no support widening
**Branch:** `codex/rg-conclusion-semantics`
**Decision artifact:** `ao_release_gate_conclusion_semantics_c_prime_migration`
**Support impact:** none in this slice

## Purpose

Operator `ao-release-gate`'in `path_sensitive_human_review_missing` durumunda
`failure` conclusion döndürmesi yapısal false-red üretiyor. Operator new
HARD RULE (`feedback_operator_approve_requires_green_ci.md`) gereği failing
check varken approve veremez; gate'in self-referential paradox'u operator
prensibini ihlal eder.

C-prime tasarım (Codex thread `019e65c3` iter-1 + iter-2 absorb):

1. **Eski `ao-release-gate` job ismi korunur** (required check üretmeye devam
   eder; ruleset breaking değil)
2. **Wrapper logic**: decision.json'da **TEK blocker**
   `ao_release_gate_high_risk_human_review_missing` ise → job exit `0`
   (success). Gerçek violation / multi-blocker → exit `1` (failure)
3. **Aynı PR'da** yeni iki Checks API check-run publish edilmeye başlar:
   - `ao-release-gate-technical` — gerçek teknik/governance violations
   - `ao-release-gate-review` — sadece path_sensitive_human_review pending
4. **Conclusion semantik kuralları** (GitHub resmi Checks API conclusion'ları):
   - `success` — tüm OK
   - `failure` — gerçek violation
   - `action_required` — operator action pending (review)
   - `stale` — branch not up-to-date
5. **CODEOWNER review enforcement**: artık gate üzerinden DEĞİL — GitHub'ın
   doğal `require_code_owner_reviews=true` ile sağlanır

Operator paradox kırılır: bu PR'da eski gate "review missing" durumda artık
success döner → CI tamamen yeşil → operator diff'i inceler → approve verir
(prensibe uygun) → CODEOWNER kuralı GitHub native ile zaten enforce edilmiş
→ merge ready.

## Authority

GPP-9 closed under
`gpp9_keep_narrow_stable_runtime_authoritative_program_closed_no_live_adapter_execution_no_support_widening_no_production_claim`.
This slice does **not** flip guard flags:
- `support_widening_allowed=false`
- `production_platform_claim_allowed=false`
- `live_adapter_execution_allowed=false`

Bu RG slice GPP-2D-3c'nin ao-release-gate semantic refactor'üdür; release
authority değişmez (yine `ao-release-gate` ve sonradan iki check-run'ı
required olarak ruleset `16803733`'te enforced).

## Cross-AI Peer Review

**Codex thread `019e65c3-7841-7211-b627-e79e9af48643`:**

**İter-1 (mimari sorular):**
- (i) Single check-run, conclusion ayrımı — yetersiz, Actions job conclusion'u JSON artifact'i görmez
- (ii) **İki check-run** — tercih, Checks API üzerinden post
- (iii) Başka — ❌

**İter-2 (paradox sıralaması):**
- (A) Shadow-first — operator paradox'u kırmaz
- (B) Cutover-first + advisory — advisory failure de operator prensibini ihlal eder
- (C-prime) **Tek PR, wrapper** — eski job ismi korunur, wrapper review-missing finding'ini yeşillendirir; aynı PR'da iki yeni check-run publish edilir → **TERCIH**

**Kritik güvence (Codex):** "Wrapper sadece review-missing finding'ini yeşile
çevirir, policy violation'ı asla yumuşatmaz."

## Schema/Module Changes

### `ao_kernel/ao_release_gate.py`

- `GithubCheckConclusion`: `Literal[success, failure, neutral]` → `Literal[success, failure, neutral, action_required, stale]`
- `AoReleaseGateCheck` TypedDict: `blocker_kind: Literal["failure", "review_action", "stale", None]` ekle
- `_finding_conclusion_kind(finding_code: str) -> str`: her finding'i kategorize et
- `_check_run` (mevcut eski wrapper): C-prime mantığı — TEK blocker review_action ise conclusion `success`
- **Yeni** `build_technical_check_run(decision, findings)`: non-review violations
- **Yeni** `build_review_check_run(decision, findings)`: sadece review-pending
- **Yeni** `wrapper_exit_code(decision, findings) -> int`: C-prime exit logic

### `ao_kernel/ao_release_gate_service.py`

- `check_run_request` → `check_run_requests` (list)
- Multi check-run POST endpoint

### `ao_kernel/ao_release_gate_runtime.py`

- Multi check-run post path

### `scripts/ao_release_gate_decision.py`

- `--wrapper-exit-code` flag: C-prime mantığı (tek review-action blocker → exit 0)
- `--emit-multi-check-runs` flag: iki ayrı check-run artifact yaz

### `.github/workflows/test.yml`

- `ao-release-gate` job: `--fail-on-deny` yerine `--wrapper-exit-code`
- Aynı job içinde yeni iki check-run publish step (Checks API)

## Conclusion Semantics

| Finding code | Conclusion kind | Conclusion value |
|---|---|---|
| `ao_release_gate_review_evidence_not_accepting` | failure | `failure` |
| `ao_release_gate_review_evidence_context_unverifiable` | failure | `failure` |
| `ao_release_gate_review_evidence_schema_invalid` | failure | `failure` |
| `ao_release_gate_review_evidence_missing` | failure | `failure` |
| `ao_release_gate_high_risk_human_review_missing` | **review_action** | **`action_required`** |
| `ao_release_gate_branch_not_up_to_date` | **stale** | **`stale`** |
| `ao_release_gate_wrong_repository` | failure | `failure` |
| `ao_release_gate_untrusted_fork` | failure | `failure` |
| `ao_release_gate_pull_request_target_context` | failure | `failure` |
| `ao_release_gate_diff_scope_*` | failure | `failure` |
| `ao_release_gate_gpp_*_violation` | failure | `failure` |
| `ao_release_gate_secret_*` | failure | `failure` |
| `ao_release_gate_admin_bypass_*` | failure | `failure` |
| `ao_release_gate_live_adapter_*` | failure | `failure` |
| `ao_release_gate_pat_bot_*` | failure | `failure` |
| `ao_release_gate_agent_authority_*` | failure | `failure` |
| `ao_release_gate_payload_not_object` | failure | `failure` |

## Wrapper Logic

```python
def wrapper_exit_code(decision: ReleaseGateDecisionValue, findings: list[str]) -> int:
    """Compatibility wrapper for the legacy ao-release-gate job.

    Returns 0 when the only blocker is review-pending; returns 1 for any
    real violation. This preserves the legacy job's required status check
    name while shifting review-missing semantics off of the failure axis.
    """
    if decision == ALLOW_AUTONOMOUS_MERGE_DECISION:
        return 0
    if findings == ["ao_release_gate_high_risk_human_review_missing"]:
        return 0
    return 1
```

Kritik: `findings == ["..."]` **tam eşleşme** — birden çok finding varsa (review-missing + başka violation) wrapper exit 1 döner. Wrapper sadece **single review-action blocker** durumunda gevşer.

## Test Coverage

Yeni test senaryoları (`tests/test_ao_release_gate.py` + `tests/test_ao_release_gate_service.py`):

1. `test_wrapper_exit_code_review_only_blocker_returns_zero`
2. `test_wrapper_exit_code_real_violation_returns_one`
3. `test_wrapper_exit_code_multi_blocker_returns_one` (review + violation)
4. `test_wrapper_exit_code_branch_stale_returns_one`
5. `test_build_technical_check_run_real_violation_emits_failure`
6. `test_build_technical_check_run_only_review_blocker_emits_success`
7. `test_build_review_check_run_review_missing_emits_action_required`
8. `test_build_review_check_run_review_present_emits_success`
9. `test_build_review_check_run_branch_stale_emits_success` (review check sadece review'a odaklı)
10. `test_check_run_conclusion_action_required_in_literal`
11. `test_check_run_conclusion_stale_in_literal`
12. `test_service_multi_check_run_request_shape`
13. `test_runtime_multi_check_run_post_path`
14. `test_decision_from_findings_preserved` (regression: existing decision logic unchanged)

Plus pre-existing 100+ test geçmeye devam etmeli.

## Forbidden Actions

- Hiçbir `gpp_status.v1.json` mutation
- Hiçbir `scripts/gp5_platform_claim_decision.py` mutation
- Hiçbir `ao_kernel/defaults/policies/` mutation
- Hiçbir branch protection / ruleset mutation **bu PR'da** (operator action — Phase 2)
- Hiçbir `ao_kernel/` public SDK signature break
- Hiçbir tier promotion, support widening, production platform claim, live adapter execution
- Wrapper logic real violation'ları yumuşatmaz (sadece review-missing semantics)

## Migration Phases

**Phase 1 (bu PR — RG-1):**
- Wrapper logic + iki yeni check-run publish + tests
- Eski `ao-release-gate` job ismi korunur (required check intact)
- Yeni check-run'lar shadow gibi yayınlanır (henüz required değil)
- Operator paradox kırılır

**Phase 2 (operator action — UI):**
- Operator ruleset `16803733` required check setini değiştirir:
  - **Ekle:** `ao-release-gate-technical` (source-pinned integration_id 15368)
  - **Ekle:** `ao-release-gate-review` (source-pinned integration_id 15368)
- Audit: bu plan dosyası + bu PR + operator commit/issue

**Phase 3 (follow-up PR — RG-2):**
- Eski `ao-release-gate` job kaldırılır (required değil artık)
- Eski wrapper kod path'i silinir
- Documentation refresh

## Downstream Effect

After RG-1 merge:
- Bekleyen 3 PR (#637, #641, #638) artık operator için doğru sinyal verir
- PR'larda eski `ao-release-gate` yeşillenir (review-missing → success)
- Yeni iki check-run UI'da görünür (shadow; henüz required değil)
- Operator CI yeşil görür → diff'i inceler → approve verir → CODEOWNER GitHub native ile enforce → merge

After Phase 2 cutover:
- Yeni check-run'lar required
- `action_required` semantik UI'da net görünür
- Operator hiçbir paradox'a düşmez
