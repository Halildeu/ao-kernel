# AO-MA-11E-2a — GitHub Mirror Drift Checker (Read-Only Adapter)

> **Statü:** First sub-slice of AO-MA-11E-2 (V5 manual mirror binding adapter). Read-only GitHub state vs projection manifest reconciler. Write sync workflow (anchor injection, `sync_state` lifecycle) deferred to 11E-2b (operator-bound).
> **Program:** AO-MA-SPM Master Plan §Faz 2 (AO-MA-11E continuation; sub-slice for V5 manual mirror create binding).
> **Risk:** normal (read-only; no GitHub write; no guard flag flip; no secrets leakage).
> **Cross-AI consensus:** Codex MCP thread `019e8230` plan-time REVISE (AGREE-with-revisions: 6 absorb) → `ready_for_impl: true`.
> **Değişmezler:** `support_widening`/`production_platform_claim`/`live_adapter_execution` = FALSE; no GitHub write (read-only); no secret payload in report/log.

## 1. Bağlam

V5 manual mirror create chain (PR #771 + #772 + #786) tamamlandı:

- Milestone #3 (`v5.0.0 — Full Production Promotion`, due 2026-12-31)
- 23 V5 label (10 epic + 5 status + 4 risk + 3 guard-flip + 1 mirror)
- 13 V5 issue (#773-#785) anchor field markdown body
- Project #3 (`Roadmap v5.0.0`) + 13 item

`.claude/plans/v5_issue_projection.v1.json` `mirror_creation_path=manual_now_with_manifest_driven_binding` + `drift_checker_binding_deferred_to=AO-MA-11E-2`. Bu slice o adapter'ı kurar: GitHub state ↔ manifest reconcile.

AO-MA-11E plan doc §7 11E-2 scope: "GitHub Projects v2 + Milestone + Issue tek-yön sync workflow · anchor injection · canlı mirror drift · `sync_state` synced/mirror_drift_detected". Bu slice (11E-2a) **read-only drift checker** kısmını kurar; write sync workflow (11E-2b) guard-flipped/operator-bound LATER.

## 2. Codex consensus absorb (thread 019e8230)

| # | Soru | Codex REVISE → Karar |
|---|---|---|
| A | Scope | 11E-2a read-only checker (BU PR); 11E-2b write sync workflow LATER; 11E-2c scheduled binding LATER |
| B | Network | `gh_api_caller` callable DI + `--allow-network` explicit CLI flag + mock-only tests + token never in log/report/JSON |
| C | Anchor parse | Markdown strict regex (5 alan); duplicate→anchor_mismatch; missing→anchor_mismatch; unknown→anchor_schema_mismatch; SHA format `sha256:[0-9a-f]{64}`; placeholder rejection |
| D | Severity | Tüm semantic drift fail-closed (exit ≠ 0); severity tier sadece rapor ergonomi (info/blocker); no warning tier (exit semantics bulanıklaşmasın) |
| E | Future-proofing | Generic engine `github_mirror_drift.py` + V5-specific CLI `ao_ma11e2_v5_mirror_drift.py` (manifest path/expected counts manifest-driven) |
| F | Module naming | `ao_kernel/_internal/ao_ma/github_mirror_drift.py` (generic core, AO-MA-SPM internal package); CLI V5-specific |

## 3. Modüller

### 3.1 `ao_kernel/_internal/ao_ma/__init__.py`

Yeni internal package. AO-MA-SPM çevresinde 11E + 11G + 11I + 11H + 11F kapsamı için.

### 3.2 `ao_kernel/_internal/ao_ma/github_mirror_drift.py`

**Public API (sync):**

```python
def check_github_mirror_drift(
    *,
    projection_manifest_path: Path,
    gh_api_caller: Callable[[str, str], dict],
    repo_owner: str = "Halildeu",
    repo_name: str = "ao-kernel",
    network_allowed: bool = False,
) -> DriftReport
```

**Disiplin:**
- No `import requests`/`httpx`/`urllib`/`subprocess`/`gh`. Only stdlib (`hashlib`, `json`, `re`, `pathlib`, `dataclasses`, `typing`, `enum`).
- `gh_api_caller` dependency injection — testlerde mock; CLI'da gh CLI wrapper.
- Token zorunluluğu yok core'da; CLI katmanı handle eder.
- `network_allowed=False` → drift check çalışmaz; `exit_decision=network_not_allowed` ile rapor üretir.

**Comparator list (her biri fail-closed):**

1. **Milestone presence + metadata**: Expected (manifest'ten) milestone title + due_on vs actual API response.
2. **Issue inventory**: Expected issue numbers (`runtime_created_state.issues_created` 13 issue) vs actual milestone-bound issues. Missing/extra → blocker drift entry.
3. **Issue labels**: Each expected issue's labels (`first_wave_issues[i].labels` from manifest) vs actual issue labels. Mismatch → `label_mismatch` drift.
4. **Issue body anchors**: Markdown strict parser extracts 5 fields (`spm_anchor`, `slice_id`, `ao_authority_artifact`, `artifact_sha256`, `plan_digest`) per issue. Missing/duplicate/unknown → `anchor_mismatch`/`anchor_schema_mismatch`. SHA format validate. Placeholder (`{computed_at_...}`) rejection.
5. **Project presence + items**: Expected project (`runtime_created_state.project_board.number`) vs actual API. Expected 13 items vs actual count + URL match.

### 3.3 `scripts/ao_ma11e2_v5_mirror_drift.py`

CLI thin wrapper:

```
ao_ma11e2_v5_mirror_drift.py
  [--projection-manifest .claude/plans/v5_issue_projection.v1.json]
  [--github-token-env GH_TOKEN]
  [--allow-network]
  [--output drift_report.json]
  [--repo-owner Halildeu]
  [--repo-name ao-kernel]
```

Token resolution: env-var only (HARD RULE secret payload YASAK). Token presence boolean reported in JSON; token value NEVER appears in output.

**gh_api_caller adapter**: gh CLI subprocess wrapper (only CLI layer; core stays clean).

## 4. Schema: `ao-ma-github-mirror-drift-report.v1.json`

Draft 2020-12 strict; additionalProperties:false; required fields:

- `schema_version` const `ao-ma-github-mirror-drift-report.v1`
- `projection_manifest` path
- `manifest_sha256` (sha256:[0-9a-f]{64})
- `checked_at` ISO-8601
- `network_allowed` bool
- `token_env` (env var name only; never value)
- `token_present` bool
- `github_owner`, `github_repo`
- `expected_counts` (issues, labels, project_items)
- `drift` array (per-finding object; category enum; severity enum {blocker, info}; object_type, object_id, expected, actual)
- `exit_decision` enum (`synced`, `mirror_drift_detected`, `network_not_allowed`, `api_error`, `usage_error`)

## 5. Exit codes

- `0`: synced (no drift)
- `1`: drift detected (fail-closed; halt_autonomy_and_escalate per 11E plan §6)
- `2`: usage/config/schema/token/network-not-allowed error
- `3`: GitHub API error fail-closed (unavailable/incomplete response)

## 6. HARD RULE pin'leri

- No GitHub write (read-only)
- No subprocess/network/requests/httpx in core module (DI callable)
- Token never in JSON/log/report (only env-var name + boolean presence)
- Three guard flags (`support_widening`, `production_platform_claim`, `live_adapter_execution`) const false unchanged
- Markdown anchor parser strict (duplicate/missing/unknown reject)
- Placeholder digest (`{computed_at_PR-X2_runtime}`) rejected
- Pre-commit + pre-push hook discipline respected

## 7. Tests

`tests/test_ao_ma11e2a_mirror_drift_checker.py`:

1. **Happy path**: All 13 issues + milestone + project synced → `exit_decision: synced`, exit 0
2. **Missing milestone**: API returns 404 → blocker drift + exit 1
3. **Missing issue**: Issue #774 not in milestone → blocker drift + exit 1
4. **Extra issue**: Unexpected issue #999 in milestone → blocker drift + exit 1
5. **Label mismatch**: Issue #774 missing `epic-1` label → blocker drift + exit 1
6. **Anchor missing**: Issue body lacks `spm_anchor` → blocker drift + exit 1
7. **Anchor duplicate**: Issue body has 2 `spm_anchor` fields → blocker drift + exit 1
8. **Anchor unknown field**: Issue body has extra `unauthorized_field` → blocker drift + exit 1
9. **SHA format invalid**: `artifact_sha256: invalid-hex` → blocker drift + exit 1
10. **Placeholder digest**: `plan_digest: {computed_at_PR-X2_runtime}` → blocker drift + exit 1
11. **Project missing**: Project #3 not found → blocker drift + exit 1
12. **Project item count mismatch**: Project has 12 items (expected 13) → blocker drift + exit 1
13. **Network not allowed**: `network_allowed=False` → `exit_decision: network_not_allowed` + exit 2
14. **Token secret redaction**: Report JSON never contains token value (regex check)
15. **API error**: gh_api_caller raises → `exit_decision: api_error` + exit 3
16. **Pagination**: Mock multi-page label/issue response handled correctly

## 8. Cross-AI peer review

- **Implementer:** Claude (Anthropic)
- **Plan-time reviewer:** Codex (OpenAI) thread `019e8230` → REVISE absorbed (6 sub-decisions) → `ready_for_impl: true`
- **Post-impl reviewer:** Codex (OpenAI) — yeni thread post-impl review

## 9. Sıradaki (out-of-scope, future slices)

- **11E-2b**: Write sync workflow (anchor injection, `last_sync_run_id` + `mirror_projection_sha256` populate, `sync_state` lifecycle); guard-flipped/operator-bound (because `.github/**` + `gh` write)
- **11E-2c**: Scheduled CI binding (drift checker as periodic check; cron-bound)

## 10. Yaşayan dosyalar

- Plan: `.claude/plans/AO-MA-11E-2A-MIRROR-DRIFT-CHECKER.md` (this)
- Schema: `ao_kernel/defaults/schemas/ao-ma-github-mirror-drift-report.schema.v1.json`
- Core module: `ao_kernel/_internal/ao_ma/github_mirror_drift.py`
- CLI: `scripts/ao_ma11e2_v5_mirror_drift.py`
- Tests: `tests/test_ao_ma11e2a_mirror_drift_checker.py`
- Evidence: `local-ai-review-evidence.v1.json` (work_package=AO-MA-11E-2A-MIRROR-DRIFT-CHECKER)

## 11. Karar kuralı (tek cümle)

11E-2a read-only GitHub mirror drift checker; generic engine + V5-specific CLI; strict anchor parse + fail-closed exit codes; no GitHub write (deferred to 11E-2b); no secret in output; cross-AI Codex plan-time AGREE-with-revisions + post-impl AGREE zorunlu merge.
