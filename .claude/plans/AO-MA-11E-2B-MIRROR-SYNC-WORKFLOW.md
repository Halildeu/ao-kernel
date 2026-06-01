# AO-MA-11E-2b — V5 Mirror Write Sync Workflow (Operator-Dispatched)

> **Statü:** Second sub-slice of AO-MA-11E-2 (V5 manual mirror binding adapter — write path). Builds on 11E-2a read-only drift checker (PR #788 MERGED main 7129bdb).
> **Program:** AO-MA-SPM Master Plan §Faz 2 (AO-MA-11E sub-slice; V5 mirror authoritative resync).
> **Risk:** high (`.github/workflows/` + GitHub write path). Cross-AI peer review + ao-release-gate ile merge edilir; **canlı apply operator-dispatched** (workflow_dispatch UI + typed confirmation chain).
> **Cross-AI consensus:** Codex MCP thread `019e8249` plan-time iter-1 REVISE (7 blockers) → iter-2 AGREE + `ready_for_impl: true`.

## 1. Bağlam

11E-2a runtime smoke (`scripts/ao_ma11e2_v5_mirror_drift.py --allow-network`) main 7129bdb sonrası 17 drift bulgusu verdi:

- **13x `anchor_schema_mismatch`**: Tüm issue body'leri parser scope dışı extra field içeriyor (`risk_class_source` + `evidence_classes`)
- **4x `anchor_sha_format_invalid`**: Issue #773-#776 `plan_digest` value'sunda display suffix `(manifest ...)` — parser SHA pattern reject

Root cause: V5 manual mirror create sırasında issue body'leri parser strict 5-field scope dışında yazıldı; manifest authoritative değil GitHub state authoritative kalmıştı. 11E-2b bu drift'i resolve eder + future-proof sync engine kurar.

## 2. Codex iter-1 REVISE blockers (absorbed in iter-2)

| # | Blocker | Absorb |
|---|---|---|
| 1 | body_anchor migration complete (12/13 missing artifact_sha256 + plan_digest) | Migration: per-issue strict 5-field + explicit copy from `mirror_creation_state.issue_anchor_pin` |
| 2 | metadata field tasarımı | Yeni `metadata` per-issue (risk_class_source + evidence_classes + sub_issues_planned_ref) |
| 3 | Apply mode --apply alone insufficient | Multi-confirmation chain (CLI + workflow + env preflight) |
| 4 | Workflow apply gate single condition insufficient | 7-condition compound `if:` apply step |
| 5 | Environment alone unreliable | Preflight verifies env exists + required_reviewers > 0 |
| 6 | DI caller POST/PATCH only too narrow | 4 method support (GET/POST/PATCH/GraphQL) + read-before-write idempotency |
| 7 | sync_state source write risk | sync_state = SyncReport runtime field; no manifest back-write from workflow |

## 3. Codex iter-2 AGREE sub-decisions

A. Scope: agent author module/CLI/schema/tests/workflow; live apply operator-dispatched.
B. Apply chain: typed confirmation + accepted dry-run digest + workflow inputs + env preflight.
C. Combined PR (manifest migration + sync workflow).
D. Issue body 5-field `## V5 Anchor` + ayrı `## V5 Metadata` heading.
E. Environment preflight artifact'a yazılsın (audit-able).
F. Parser strict 5 fields (no extension; migration brings manifest into scope).
G. Pure `sha256:<64 lowercase hex>` issue body output.
H. Cross-AI review = merge evidence; apply dispatch operator-bound.

Plus iter-2 netleştirme: **label sync mirror-managed namespace only** (foreign labels preserve).

## 4. Manifest migration (this PR)

`first_wave_issues[i].body_anchor` per-issue (13 issues):
- Strict 5 field: `spm_anchor`, `slice_id`, `ao_authority_artifact`, `artifact_sha256`, `plan_digest`
- `artifact_sha256` + `plan_digest` populated from `mirror_creation_state.issue_anchor_pin` (explicit copy, NOT recompute)

`first_wave_issues[i].metadata` new field per-issue:
- `risk_class_source` (from old body_anchor)
- `evidence_classes` (from old body_anchor)
- `sub_issues_planned_ref` (issue id reference, not copy)

## 5. Sync engine (`ao_kernel/_internal/ao_ma/github_mirror_sync.py`)

**Public API:**
```python
def sync_v5_mirror(
    *,
    projection_manifest_path: Path,
    gh_api_caller: Callable[[str, str, dict|None], Any],
    repo_owner: str,
    repo_name: str,
    network_allowed: bool,
    apply_mode: bool,                # default False → dry-run
    confirmation: str | None,        # required for apply: must equal "AO-MA-11E-2B-APPLY"
    accepted_dry_run_report_digest: str | None,  # required for apply: sha256:<hex>
    pre_drift_snapshot: dict | None, # required for apply (from prior 11E-2a run)
) -> SyncReport
```

**Operations (dry-run + apply):**
1. **Issue body re-generate** — per-issue, manifest `body_anchor` (5-field) + `metadata` section
2. **Label sync** — mirror-managed namespace (`epic-*`, `status:*`, `risk:*`, `guard-flip:*`, `mirror:authority`) set-equality; foreign labels preserved
3. **Project item membership sync** — expected URLs vs actual; add missing, remove extra
4. **Milestone link verify** — read-only check (no PATCH; if drift → drift reported, not auto-fixed)

**Disiplin:**
- Pure stdlib core; DI gh_api_caller
- Read-before-write idempotency: GET current → diff with desired → PATCH only diff
- Dry-run: all planned changes recorded in SyncReport.planned_changes; NO write
- Apply: SyncReport.applied_changes + pre/post drift snapshots
- sync_state lifecycle: `not_started` → `dry_run_planned` → `dry_run_complete` / `apply_in_progress` → `applied` / `applied_with_post_drift` / `apply_aborted` / `api_error` / `usage_error`

## 6. Schema (`ao-ma-github-mirror-sync-report.schema.v1.json`)

Draft 2020-12 strict; additionalProperties:false; allOf if/then invariants:
- `sync_state == dry_run_complete` → `applied_changes` empty
- `sync_state == applied` → `applied_changes` non-empty + `pre_drift_snapshot` + `post_drift_snapshot` + `confirmation_provided == "AO-MA-11E-2B-APPLY"`
- `sync_state == apply_aborted` → reason field populated
- `accepted_dry_run_report_digest` SHA256 pattern (if apply mode)

## 7. CLI (`scripts/ao_ma11e2b_v5_mirror_sync.py`)

Dry-run (default):
```
ao_ma11e2b_v5_mirror_sync.py
  --projection-manifest .claude/plans/v5_issue_projection.v1.json
  --github-token-env GH_TOKEN
  --allow-network
  --output sync_report.json
```

Apply (operator-only):
```
ao_ma11e2b_v5_mirror_sync.py
  --apply
  --allow-network
  --confirmation AO-MA-11E-2B-APPLY
  --accepted-dry-run-report PATH
  --accepted-dry-run-report-digest sha256:<64hex>
  --output apply_report.json
```

Plus optional env var second confirmation: `AO_MA_11E_2B_APPLY_ACK=1` (AO-MA-10O pattern).

## 8. Workflow (`.github/workflows/ao-ma-11e-2b-mirror-sync.yml`)

`on.workflow_dispatch.inputs`:
- `dry_run` (boolean, default `true`)
- `allow_apply` (boolean, default `false`)
- `confirmation` (string, required for apply: `"AO-MA-11E-2B-APPLY"`)
- `accepted_dry_run_report_digest` (string, sha256: prefix)

**Dry-run job:** always runs (no environment); produces sync_report.json artifact.

**Apply job:** requires environment + 7-condition compound `if`:
```yaml
if: |
  github.ref == 'refs/heads/main' &&
  github.event_name == 'workflow_dispatch' &&
  github.run_attempt == 1 &&
  inputs.dry_run == 'false' &&
  inputs.allow_apply == 'true' &&
  inputs.confirmation == 'AO-MA-11E-2B-APPLY' &&
  inputs.accepted_dry_run_report_digest != ''
environment: ao-ma-mirror-sync
```

**Environment preflight step (before any write):**
- GET `/repos/{owner}/{repo}/environments/{env}` → exists + required_reviewers count > 0
- Fail-closed if not configured (`::error::environment protection precondition missing`)
- Preflight result → environment_preflight_decision in apply report

## 9. Tests

5 test files:

1. `test_ao_ma11e2b_manifest_migration.py` — manifest migration completeness (13/13 body_anchor 5-field + 13/13 metadata present)
2. `test_ao_ma11e2b_mirror_sync.py` — engine unit (dry-run no-write + apply confirmation chain + idempotency + read-before-write + label namespace preservation)
3. `test_ao_ma11e2b_schema_invariant.py` — sync report schema (Draft 2020-12 + allOf if/then invariants + sync_state enum)
4. `test_ao_ma11e2b_workflow_invariant.py` — workflow YAML (7-condition compound apply gate + environment preflight + strict inputs)
5. `test_ao_ma11e2b_issue_body_template.py` — template (5-field anchor + metadata section boundary; parser does NOT trigger anchor_schema_mismatch on metadata)

## 10. HARD RULE pin

- Pure stdlib core (no requests/httpx/urllib/subprocess/gh)
- Token never in JSON/log/report
- Dry-run default true
- Apply requires 4-input typed confirmation chain
- Environment preflight required before write
- Three guard flags const false
- No back-write to manifest from workflow (sync_state report-only)

## 11. Cross-AI peer review

- **Implementer:** Claude (Anthropic)
- **Plan-time reviewer:** Codex (OpenAI) thread `019e8249` iter-1 REVISE → iter-2 AGREE + `ready_for_impl: true`
- **Post-impl reviewer:** Codex (OpenAI) yeni thread

## 12. Execution order

1. (this PR) Manifest migration + sync module + CLI + schema + workflow + tests + plan doc + evidence
2. Cross-AI Codex post-impl review chain
3. CI ao-release-gate (high-risk path) + merge
4. **Operator dispatches dry-run workflow** → archive sync_report.json → review
5. Operator computes `accepted_dry_run_report_digest = sha256(sync_report.json)`
6. **Operator dispatches apply workflow** with: dry_run=false + allow_apply=true + confirmation=AO-MA-11E-2B-APPLY + accepted_dry_run_report_digest=<sha>
7. Apply mutates 13 issue bodies + label sync + project item sync
8. Re-run 11E-2a drift checker → expected `synced`

## 13. Out-of-scope (this PR)

- AO-MA-11E-2c: scheduled drift check (cron-bound) — LATER
- Manifest back-write from workflow (sync_state to source) — separate evidence PR pattern
- Foreign label namespace management (preserve only; full replacement → ayrı sub-slice)
- v6/v7 multi-version mirror sync — manifest-driven generic engine sufficient

## 14. Karar kuralı (tek cümle)

11E-2b agent-authored sync engine + manifest migration + workflow + tests; canlı apply operator-dispatched 7-condition gate + multi-confirmation chain; sync_state report-only; foreign labels preserve; cross-AI Codex plan-time + post-impl AGREE zorunlu merge.
