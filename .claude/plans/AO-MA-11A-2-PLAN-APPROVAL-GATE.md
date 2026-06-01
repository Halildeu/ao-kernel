# AO-MA-11A-2 — GH Environment Plan Approval Gate (Operator-Bound)

> **Statü:** Second sub-slice of AO-MA-11A (plan consensus + approval workflow gate). Builds on 11A-1 (consensus + approval validator core, MERGED main).
> **Program:** AO-MA-SPM Master Plan §Faz 1 (AO-MA-11A continuation; operator approval gate wiring).
> **Risk:** high (`.github/workflows/**` + GitHub Environment). Cross-AI peer review + ao-release-gate ile merge edilir; **canlı approval operator-dispatched** (workflow_dispatch UI + 7 input + Environment review).
> **Cross-AI consensus:** Codex MCP thread `019e82cc` plan-time iter-1 REVISE (4 binding + 8 sub-decision) → iter-2 REVISE (6 blocker) → iter-3 AGREE + `ready_for_impl: true`.

## 1. Bağlam

11A-1 (consensus + approval schema + validator + tests + plan) MERGED main. Pure-policy core; 4-state gate_status lifecycle (consensus_not_reached / awaiting_operator_approval / approved_autonomous_run_may_start / halted_operator_rejected). Bu slice operator approval kapısı için workflow + GitHub Environment wiring sağlar.

11E-2b (PR #789+#790 MERGED) pattern aynı (environment-protected workflow + operator approval + canonical digest verify) — re-use edilebilir disiplin.

## 2. Codex iter-1 REVISE (4 binding + 8 sub-decision) absorb

| # | Blocker | Absorb |
|---|---|---|
| 1 | plan_path + stale-main guard | inputs.plan_path repo-relative; bundle.plan_binding.base_sha == github.sha |
| 2 | GitHub approval identity proof | gh api /actions/runs/{run_id}/approvals → approving_user + bypass check |
| 3 | Artifact-only approval kaydı | actions/upload-artifact 365d; contents:write yok |
| 4 | CLI canonical gate-report emitter | scripts/ao_ma11a2_plan_approval_gate.py 7-stage |

## 3. Codex iter-2 REVISE (6 blocker) absorb

| # | Blocker | Absorb |
|---|---|---|
| 1 | input count + 10-cond gate | 7 input + 10-condition compound if (all path non-empty + 4 base check) |
| 2 | validate + approve iki job | needs: validate (fail-fast); approve env-protected re-runs all checks |
| 3 | CLI stage order | path → SHA → binding → validate_consensus_bundle → API fetch → approval.json → validate_approval (final) |
| 4 | API response shape + fixtures | gh api shape pinned (user.login + created_at + state + environments[]); 4 test fixture |
| 5 | bypass vs self-review separation | 3 ayrı field (no_bypass_state + self_review_rejected + required_reviewer_configured); bypass_detected = NOT(all 3) |
| 6 | dispatch authority single model | agent dispatches + Halildeu reviews; prevent_self_review=true; UI-side operator dispatch desteklenmez |

## 4. Codex iter-3 AGREE implementation pins (hardening; not blocker)

- gh api /actions/runs/{run_id}/approvals 3-5 deneme retry/backoff (kısa eventual consistency); empty → rejected_identity
- audit_url deterministic = `https://github.com/{repo}/actions/runs/{run_id}` (canonical run URL)
- approval_request_path JSON içeriği consensus_id + plan_digest match (ek hardening)
- Path containment symlink protection: `resolved_path.is_relative_to(repo_root)` (string check ek; symlink kaçış engelle)
- Evidence diff drift pre-merge blocker (changed_files actual diff'le match)

## 5. Two-job workflow (`.github/workflows/ao-ma-11a-plan-approval.yml`)

**Trigger:** `workflow_dispatch` only

**Inputs (7, all required):**

```yaml
inputs:
  confirmation:
    description: 'Typed confirmation; must equal "AO-MA-11A-2-APPROVE"'
    required: true
  plan_path:
    description: 'Repo-relative path to plan file (raw bytes hashed for plan_digest binding)'
    required: true
  consensus_bundle_path:
    description: 'Repo-relative path to consensus bundle JSON'
    required: true
  approval_request_path:
    description: 'Repo-relative path to approval request JSON'
    required: true
  plan_digest:
    description: 'sha256:<hex> of plan_path; matches bundle.plan_digest'
    required: true
  consensus_bundle_sha256:
    description: 'sha256:<hex> of consensus_bundle_path raw bytes'
    required: true
  approval_request_sha256:
    description: 'sha256:<hex> of approval_request_path raw bytes'
    required: true
```

**Permissions:** `contents: read`, `actions: read`, `deployments: read` (NO `contents: write`)

**Jobs:**

### `validate` (unprotected; fail-fast)

```yaml
validate:
  runs-on: ubuntu-latest
  steps:
    - actions/checkout@v6 (ref: refs/heads/main)
    - Setup Python + install
    - CLI --validate-only call (path containment + raw SHA + plan binding + validate_consensus_bundle + env preflight)
    - Upload validate_report.json artifact (90d retention)
```

### `approve` (environment-protected)

```yaml
approve:
  needs: validate
  if: |
    github.ref == 'refs/heads/main' &&
    github.event_name == 'workflow_dispatch' &&
    github.run_attempt == 1 &&
    inputs.confirmation == 'AO-MA-11A-2-APPROVE' &&
    inputs.plan_path != '' &&
    inputs.consensus_bundle_path != '' &&
    inputs.approval_request_path != '' &&
    inputs.plan_digest != '' &&
    inputs.consensus_bundle_sha256 != '' &&
    inputs.approval_request_sha256 != ''
  runs-on: ubuntu-latest
  environment: ao-ma-plan-approval
  steps:
    - actions/checkout@v6 (ref: refs/heads/main)
    - Environment preflight verify (re-run; required_reviewers > 0)
    - Setup Python + install
    - CLI full call (7-stage; --github-run-id ${{ github.run_id }} --allow-network)
    - Upload artifacts: gate_report.json + approval.json + bound inputs (365d retention)
```

## 6. CLI (`scripts/ao_ma11a2_plan_approval_gate.py`)

**7-stage canonical emitter:**

```
1. Path containment validate (3 paths repo-relative; absolute/.. reject; symlink resolve check)
2. Raw SHA recompute (sha256 of plan_path + consensus_bundle_path + approval_request_path)
3. Plan binding + stale-main guard:
   - bundle.plan_binding.repository_full_name == github.repository
   - bundle.plan_binding.base_ref == 'refs/heads/main'
   - bundle.plan_binding.base_sha == github.sha
   - bundle.plan_digest == sha256(plan_path) == inputs.plan_digest
4. validate_consensus_bundle(bundle) — unanimous AGREE check (NOT validate_approval here)
5. GitHub approval review history fetch (gh api /repos/.../actions/runs/{run_id}/approvals) — retry 3-5 if empty
6. Construct approval.json from API response (approved_by + approved_at + bypass detection 3-field)
7. validate_approval(approval.json, bundle, request) — FINAL stage; triple SHA-bind + AGREE + bypass:false
8. Emit gate_report.json (schema-valid) + final_decision enum
```

**API parse contract (Blocker 4 absorb):**
```python
# Find entry: environments[].name == "ao-ma-plan-approval" AND state == "approved"
# Extract: user.login → approval.approved_by, created_at → approval.approved_at
# Empty / no match → fail-closed (rejected_identity)
```

**Bypass detection (Blocker 5 absorb):**
- `no_bypass_state_observed`: API response içinde bypass/admin override field yok
- `self_review_rejected`: triggering_actor.login != approving_user.login
- `required_reviewer_configured`: Environment preflight pass earlier
- `bypass_detected`: NOT (all 3 above)

## 7. Schema (`ao-ma-11a-2-plan-approval-gate-report.schema.v1.json`)

Draft 2020-12 strict; additionalProperties:false; required fields:

- `schema_version` const "ao-ma-11a-2-plan-approval-gate-report.v1"
- `final_decision` enum (9): approved | rejected_path | rejected_sha | rejected_binding | rejected_consensus | rejected_identity | rejected_approval_validator | api_error | usage_error
- 5 stage pass flags: `path_containment_pass`, `sha_recompute_pass`, `plan_binding_pass`, `consensus_validator_pass`, `approval_validator_pass`
- approval API: `approval_api_state` (approved | rejected | pending | empty | wrong_environment), `approving_login`, `approving_at`
- bypass 3-field: `no_bypass_state_observed`, `self_review_rejected`, `required_reviewer_configured`, `bypass_detected` (computed)
- context: `environment_name`, `run_id`, `repository_full_name`, `base_sha`, `triggering_actor`, `audit_url`
- `stage_fail_reason` (optional; populated when final_decision != approved)
- `allOf` if/then: `final_decision == approved → all 5 stages pass + bypass_detected: false`

## 8. Tests (4 dosya)

1. **`test_ao_ma11a2_gate_cli.py`** (CLI 7-stage + 4 API fixture):
   - Happy path (single approved review + bypass:false)
   - Path containment fail (absolute / `..` segment)
   - SHA recompute fail (path mutated)
   - Plan binding fail (stale base_sha mismatch)
   - Consensus validator fail (unanimous NOT_AGREE)
   - API fixture rejected (state=rejected → fail-closed)
   - API fixture empty (no reviews → fail-closed)
   - API fixture wrong_environment (environments[].name mismatch → fail-closed)
   - validate_approval called AFTER approval JSON construction (order pin)
   - bypass 3-field computed correctly (NOT (all 3))

2. **`test_ao_ma11a2_workflow_invariant.py`** (workflow YAML):
   - 7 inputs all required:true
   - 10-condition apply gate
   - `validate` job: no environment, fail-fast steps
   - `approve` job: needs validate, environment ao-ma-plan-approval, re-runs all critical
   - permissions: contents:read + actions:read + deployments:read (NO contents:write)
   - artifact upload 3 paths (gate_report + approval + bound inputs)
   - No admin/force/ruleset/CODEOWNERS mutation

3. **`test_ao_ma11a2_gate_report_schema_invariant.py`** (schema):
   - Draft 2020-12 valid
   - additionalProperties:false (root + nested)
   - 9 final_decision enum
   - 5 stage pass + bypass 3-field + computed bypass_detected
   - allOf invariant: approved → all stages pass + bypass:false

4. **`test_ao_ma11a2_path_containment.py`** (path security):
   - Absolute path reject
   - `..` segment reject
   - Symlink kaçış reject (resolved_path.is_relative_to(repo_root))
   - Repo-relative pass

## 9. HARD RULE pin

- Pure stdlib core (CLI; gh subprocess only at adapter layer)
- Token never in JSON/log/report
- No GitHub write at workflow runtime (artifact-only)
- 7-input typed confirmation chain + Environment required reviewer
- prevent_self_review:true (dispatch authority single model)
- Three guard flags const false
- Foreign label preservation (mirror-managed only)

## 10. Operator setup (manual; one-shot)

1. GitHub Settings → Environments → create `ao-ma-plan-approval`
2. Required reviewer: `Halildeu`
3. `prevent_self_review: true` (defense in depth)
4. `wait_timer: 0`
5. Acceptance: validate job env preflight pass (post-setup)

**Dispatch model:**
- Dispatcher: agent (gh CLI workflow_dispatch with 7 inputs)
- Approver: Halildeu reviews Environment in UI
- UI-side operator dispatch NOT supported (self-review guard breaks single-actor flow)

## 11. Cross-AI peer review

- **Implementer:** Claude (Anthropic)
- **Plan-time reviewer:** Codex (OpenAI) thread `019e82cc` iter-1 REVISE (4 binding + 8 sub-decision) → iter-2 REVISE (6 blocker) → iter-3 AGREE + `ready_for_impl: true`
- **Post-impl reviewer:** Codex (OpenAI) yeni thread

## 12. Execution order

1. (this PR) Plan doc + schema + CLI + workflow + 4 tests + evidence
2. Cross-AI Codex post-impl review chain
3. CI ao-release-gate (high-risk path) + merge
4. **Operator setup**: Environment `ao-ma-plan-approval` create + required reviewer + prevent_self_review:true
5. **Operator dispatch test**: agent triggers workflow_dispatch with sample 7 inputs → Halildeu approves → workflow runs validate_approval → emits approval.json artifact
6. Acceptance: gate_report.json schema-valid + final_decision=approved

## 13. Out-of-scope

- AO-MA-11A-3 (later evidence PR for canonical approval artifact archival)
- Multiple required reviewers (single Halildeu sufficient for E-1-1)
- Push trigger (workflow_dispatch only; no autonomous run on push)

## 14. Karar kuralı (tek cümle)

11A-2 agent-authored workflow + CLI canonical gate emitter; validate + approve iki job; 10-condition compound gate; Environment ao-ma-plan-approval required reviewer; GitHub approval API identity proof; bypass 3-field separation; artifact-only emission; canlı approval operator-dispatched (agent dispatches + Halildeu reviews); cross-AI Codex plan-time iter-3 AGREE + post-impl AGREE zorunlu merge.
