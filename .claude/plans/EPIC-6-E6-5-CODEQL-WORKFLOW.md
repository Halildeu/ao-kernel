# Epic 6 E-6-5 — CodeQL Security Analysis Workflow

**Status:** Implementing.
**Codex thread:** `019e8350` (plan-time REVISE, `ready_for_impl: true`).
**Slice:** E-6-5 (single PR — workflow + config + invariant tests +
plan doc).

## 1. Sorun

V5 Epic 6 E-6-5 plan'da yazıyor: "CodeQL workflow (GitHub Advanced
Security)". Mevcut `.github/workflows/`'ta CodeQL YOK; static security
analysis baseline kurulmamış.

Hedef: GitHub-native CodeQL static analysis workflow + scope config
+ shape invariant tests + governance disipliniyle plan dokümantasyonu.

## 2. Codex iter-1 absorb (REVISE)

| Konu | Codex bulgu | Absorb |
|---|---|---|
| Query packs | `security-extended,security-and-quality` baseline'da gürültü | Baseline `security-extended` only; `security-and-quality` follow-up |
| Query source-of-truth | Workflow + config'te aynı `queries:` drift riski | Workflow'da `queries:` YOK; sadece `config-file:`; queries config'te |
| `paths-ignore` syntax | Düz path string'ler nested match'i kaçırabilir | Glob form: `tests/**`, `ao_kernel/defaults/**`, `**/__pycache__/**`, `**/*.pyc` |
| Timeout | `360 min` GitHub default — fazla geniş | `30 min` (Python CodeQL beklenen 5-15 min) |
| Permissions | `pull-requests: read` eksik (PR scan future-proof) | Eklendi; `contents: write` ve `id-token: write` YOK |
| Action versions | `init@v3`/`analyze@v3` doğru | Pin'li; `actions/checkout@v6` repo stiline uyumlu |
| `setup-python` | Gereksiz (Python CodeQL build-less) | YOK |
| `persist-credentials: false` | SARIF upload bozar mı? | HAYIR — upload `GITHUB_TOKEN` permissions'a dayanır |
| `pull_request_target` | Fork PR token risk | YASAK + invariant test |
| Required-check promotion | "yeşil = no alerts" yanlış semantik | Advisory baseline; required-check ayrı follow-up exit decision |

## 3. Değişiklik scope

### 3a. `.github/workflows/codeql.yml`
- 4 trigger: `push` main, `pull_request` main, weekly `schedule` (Mon
  03:17 UTC), `workflow_dispatch`.
- Permissions: actions:read + contents:read + pull-requests:read +
  security-events:write. NO contents:write, NO id-token:write.
- Matrix: language `python` (fail-fast: false).
- `timeout-minutes: 30`.
- `actions/checkout@v6` + `persist-credentials: false`.
- `github/codeql-action/init@v3` + `analyze@v3`.
- `config-file: ./.github/codeql/codeql-config.yml` (queries source).
- NO `queries:` inline in workflow (single source-of-truth in config).
- NO `actions/setup-python` (Python CodeQL is build-less).

### 3b. `.github/codeql/codeql-config.yml`
- `disable-default-queries: false` (additive layering).
- `queries: [security-extended]` (baseline only).
- `paths: [ao_kernel, scripts]`.
- `paths-ignore`: glob form `tests/**`, `ao_kernel/defaults/**`,
  `**/__pycache__/**`, `**/*.pyc`.

### 3c. `tests/test_codeql_workflow_shape.py`
24 invariant tests, regex-free plain-text substring matching to
avoid YAML 1.1 boolean trap on `on:` key:

| Invariant | Test |
|---|---|
| Workflow file exists at canonical path | `test_codeql_workflow_exists_at_canonical_path` |
| Workflow name pinned | `test_codeql_workflow_name_pinned` |
| 4 trigger keys present | `test_codeql_workflow_triggers_include_push_pr_schedule_dispatch` |
| Weekly low-traffic cron | `test_codeql_workflow_schedule_uses_weekly_low_traffic_cron` |
| `pull_request_target` rejected | `test_codeql_workflow_rejects_pull_request_target` |
| Minimum permissions set | `test_codeql_workflow_permissions_minimum_set` |
| `contents: write` rejected | `test_codeql_workflow_rejects_contents_write` |
| `id-token: write` rejected | `test_codeql_workflow_rejects_id_token_write` |
| Checkout v6 + persist-credentials false | `test_codeql_workflow_uses_checkout_v6_no_persist_credentials` |
| CodeQL action v3 init + analyze | `test_codeql_workflow_uses_codeql_action_v3` |
| `setup-python` not used | `test_codeql_workflow_does_not_install_python_setup` |
| Matrix language python | `test_codeql_workflow_matrix_pins_python` |
| Timeout <= 30 min | `test_codeql_workflow_timeout_capped_at_30_minutes` |
| Config file referenced | `test_codeql_workflow_references_config_file` |
| Workflow does NOT inline queries | `test_codeql_workflow_does_not_inline_queries_key` |
| Config file exists | `test_codeql_config_file_exists` |
| security-extended query pack | `test_codeql_config_pins_security_extended_query_pack` |
| security-and-quality deferred | `test_codeql_config_defers_security_and_quality_pack` |
| Scope covers runtime code | `test_codeql_config_paths_scope_covers_runtime_code` |
| paths-ignore glob covers noise | `test_codeql_config_paths_ignore_glob_covers_noise` |
| Default queries enabled | `test_codeql_config_default_queries_remain_enabled` |

### 3d. Plan doc — this file.

## 4. Out-of-scope (E-6-5 follow-up slices)

| Konu | Sonra |
|---|---|
| `security-and-quality` query pack | Initial baseline triage sonrası ayrı PR |
| Required-check promotion | Ayrı follow-up exit decision (baseline + main runtime measurement + alert review sonrası) |
| Custom query packs (ao-kernel'e özel) | Epic 6 follow-up — ao-kernel codebase için manual query yazımı |
| GHAS code scanning enablement | Operator action — repo Settings → Code security and analysis → Default setup ya da Advanced; bu PR sadece workflow file ekler |
| First-run runtime measurement | Post-merge — main'de ilk run sonrası ölçüm plan doc'a evidence olarak yazılacak |

## 5. Risk + Mitigation

| Risk | Mitigation |
|---|---|
| Fork PR token risk (security-events:write) | `pull_request_target` YASAK + invariant test |
| Workflow `queries:` ile config drift | Single source-of-truth config file; workflow inline rejected by invariant |
| `paths-ignore` nested match miss | Glob form `**` her path için |
| Long CI runtime | 30-min cap (Python CodeQL build-less; expected 5-15 min) |
| CodeQL alerts "passing" semantik karışıklığı | Plan doc + workflow yorum: "CodeQL green ≠ no alerts"; required-check promotion ayrı follow-up |
| `setup-python` regression | Invariant test workflow'da setup-python kullanımını reject |
| Action version drift | `@v3` + `@v6` pin'li; invariant test |

## 6. Acceptance

- ✅ `pytest tests/test_codeql_workflow_shape.py -x` → 21 pass local
- ✅ `ruff check tests/test_codeql_workflow_shape.py` clean
- ✅ Plan doc — this file
- ⏳ Cross-AI post-impl review (Codex thread `019e8350` reply ile yeni iter)
- ⏳ CI green (PR taksonomi extension gerek PR #793 merge sonrası)
- ⏳ Squash merge audit trail: Implementer Anthropic Claude / Reviewer OpenAI Codex
- ⏳ **Post-merge operator action**: GHAS code scanning enablement (Settings UI)
- ⏳ **Post-merge measurement**: ilk main run runtime — plan doc'a evidence olarak ek

## 7. Public claim discipline

- "Production-ready" marketing claim YOK; CodeQL workflow advisory.
- 3 guard flag (`support_widening`, `production_platform_claim`,
  `live_adapter_execution`) `const false` korunur.
- Bu PR HİÇBİR flag flip yok; sadece static analysis baseline.
- "Security audited" / "SOC2 ready" public iddia YOK; SOC2 paketi
  Epic 6 E-6-3 ayrı slice.

## 8. Bağlantı

- V5 Epic 6 plan: `V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md` §3 (Epic 6
  Security + Compliance).
- HARD RULE — Cross-AI Peer Review: implementer Anthropic Claude;
  reviewer OpenAI Codex (thread `019e8350`).
- HARD RULE — Uzun Vadeli Kalıcı Çözüm: baseline `security-extended`
  only (gürültü kontrolü); config-file single source-of-truth;
  required-check promotion ayrı exit decision (yanlış semantic
  signal'i engelle).
- HARD RULE — Continuous Autonomous Mode: PR #793 + PR #794 + PR #795
  + bu PR autonomous merge chain'inde sıralı; her PR cross-AI peer
  reviewed.
