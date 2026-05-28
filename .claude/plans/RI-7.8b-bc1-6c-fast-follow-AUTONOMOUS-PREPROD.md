# RI-7.8b-bc1-6c-fast-follow — Autonomous Pre-Prod Activation Mode

**Status:** fast-follow contract revision (NO live execution, NO trigger file yet)
**Date:** 2026-05-28
**Parent:** `RI-7-REPO-INTELLIGENCE-TIER-PROMOTION-READINESS.md`
**Predecessor:** `RI-7.8b-bc1-6b` (PR #678 MERGED, commit `84d6257`)
**Successor:** `RI-7.8b-bc1-6c-closure` (per-run evidence + trigger file + window closure + BC-1 flip)
**Authority:** explicit operator (`Halildeu`) + cross-AI peer review + scoped operator_bound_supersession
**Decision:** `ri78b_bc1_6c_fast_follow_autonomous_preprod_contract_revised_no_trigger_file_no_run_evidence`

## 1. Purpose

6b shipped the operator-bound (manual protected environment + manual workflow_dispatch) execution window infrastructure. The user mandated **tam otonom AI orchestration** (HARD RULE — Pre-Production Full Authority + Continuous Autonomous Mode). 6c-fast-follow revises the 6b contract to **`operator_delegated_autonomous_preprod`** authority mode without breaking the bounded-window safety envelope.

This slice does **NOT**:

- Yarat the DISPATCH-TRIGGER file (that lives in `RI-7.8b-bc1-6c-closure` after explicit operator authorization, alongside per-run evidence collection)
- Execute any live adapter call (no workflow run fires from this PR)
- Flip the RI-7.8 submanifest BC-1 key (`bc1_protected_live_adapter_attestation_recorded` stays false)
- Mutate top-level `gpp_status.v1.json` guard flags (still all const false)
- Weaken bounded-window limits (max 5 runs, max $5, max 24h preserved)

## 2. Authority Mode Revision

6b contract (literal): `protected_environment_binding.observed=true` + `manual workflow_dispatch` + `Halildeu reviewer required`.

6c-fast-follow contract (revised): `operator_delegated_autonomous_preprod` mode. The merge of the `RI-7.8b-bc1-6c-DISPATCH-TRIGGER.v1.json` schema-pinned file to `main` IS the activation authority. No GitHub-level protected environment approval. Bounded-window code-level guard (`scripts/ri78b_bc1_activation_window.py`) is the sole enforcement layer.

### Why this is acceptable for pre-prod (Codex iter REVISE absorbed)

- Bounded window machine-enforced: max 5 distinct runs, max $5 USD, max 24h duration
- Branch protection: only `refs/heads/main` push triggers workflow
- Schema-pinned trigger file (`ri7-8b-bc1-6c-dispatch-trigger.schema.v1.json`): scenarios allowlist, operator login const, no_secret_assertion
- Workflow content sha256 binding: workflow file digest pinned in gpp_status entry; runtime guard rejects mismatch
- Run attempt restriction: `run_attempt == 1` only; rerun forbidden
- Cross-AI peer review: AGREE from both claude/anthropic + codex/openai required before merge
- Authority source: merge commit of schema-pinned trigger file by Halildeu (commit verification + required-check rollup verifiable via GitHub API in 6c-closure)

### Operator-Bound Supersession Contract Update

In `.claude/plans/gpp_status.v1.json::operator_bound_supersessions[RI-7.8b-bc1-6b]`:

```json
{
  "id": "RI-7.8b-bc1-6b",
  "authority_mode": "operator_delegated_autonomous_preprod",
  "manual_approval_required": false,
  "status": "awaiting_auto_dispatch_trigger_commit",
  "protected_environment_binding": {
    "required": false,
    "mode": "code_level_only_preprod",
    "env_name": null,
    "allowed_refs": ["refs/heads/main"],
    "admin_bypass_allowed": false,
    "superseded_by_slice": "RI-7.8b-bc1-6c-fast-follow"
  },
  "autonomous_trigger_contract": {
    "trigger_event": "push",
    "trigger_branch": "refs/heads/main",
    "trigger_file_path": ".claude/plans/RI-7.8b-bc1-6c-DISPATCH-TRIGGER.v1.json",
    "trigger_file_schema_path": "ao_kernel/defaults/schemas/ri7-8b-bc1-6c-dispatch-trigger.schema.v1.json",
    "operator_github_login": "Halildeu",
    "commit_verification_required": true,
    "required_checks_must_pass": true
  }
}
```

## 3. Workflow File Revision

`.github/workflows/bc1-protected-live-adapter-attestation.yml`:

- **REMOVED:** `environment: ao-kernel-bc1-live-adapter-attestation`
- **ADDED:** `on: push: { branches: [main], paths: ['.claude/plans/RI-7.8b-bc1-6c-DISPATCH-TRIGGER.v1.json'] }`
- **ADDED:** `strategy: matrix: scenario: [clean_attestation, fail_closed_attestation]`
- **PRESERVED:** `workflow_dispatch` fallback (manual override only)
- **PRESERVED:** Validate dispatch context (ref + event_name + run_attempt + scenario allowlist)
- **PRESERVED:** Activation window runtime guard (script invoked pre-step)

## 4. Activation Guard Script Mode-Aware

`scripts/ri78b_bc1_activation_window.py::_find_active_entry`:

```python
authority_mode = entry.get("authority_mode") or "manual_protected_environment"
accepted_statuses_by_mode = {
    "manual_protected_environment": {"awaiting_operator_dispatch", "active"},
    "operator_delegated_autonomous_preprod": {
        "awaiting_auto_dispatch_trigger_commit",
        "active",
    },
}
```

Bounded-window enforcement (workflow_content_sha256 binding, run cap, valid_until, allowed_refs, scenario allowlist) preserved.

## 5. Trigger Schema (Pinned in This PR)

`ao_kernel/defaults/schemas/ri7-8b-bc1-6c-dispatch-trigger.schema.v1.json`:

- `schema_version` const
- `authority_mode` const `operator_delegated_autonomous_preprod`
- `scenarios` const `[clean_attestation, fail_closed_attestation]`
- `operator.github_login` const `Halildeu`
- `operator.no_secret_assertion` const true
- `supersession_entry_id` const `RI-7.8b-bc1-6b`
- `max_distinct_runs` integer 1..5
- `max_run_attempt` const 1
- `max_usd` number 0..5
- `secret_boundary` const

Trigger file **YOK 6c-fast-follow'da**. 6c-closure'da yaratılır.

## 6. Successor Ownership (RI-7.8b-bc1-6c-closure)

| Surface | Owner |
|---|---|
| `.claude/plans/RI-7.8b-bc1-6c-DISPATCH-TRIGGER.v1.json` (trigger file creation) | 6c-closure |
| Per-run evidence `.claude/plans/RI-7.8b-bc1-6c-run-{run_id}.v1.json` | 6c-closure |
| Spend ledger + pricing snapshot | 6c-closure |
| `operator_bound_supersessions[RI-7.8b-bc1-6b].actual_start_at + actual_end_at + status=closed` | 6c-closure |
| RI-7.8 submanifest `bc1_protected_live_adapter_attestation_recorded false→true` | 6c-closure |
| Cross-AI final AGREE | 6c-closure |

## 7. Negative Authority Statement

This artifact **does not authorize**:

- Trigger file creation (delayed-effect execution surface) — belongs to 6c-closure
- Live adapter call from this PR's CI — no workflow run fires
- Submanifest BC-1 flip — belongs to 6c-closure
- Top-level guard flag flip
- Bounded-window limit increase

## 8. Operator Authority (4 concurrent signals, same as 6b)

1. Commit identity Halildeu
2. Commit trailers
3. GitHub PR approval via `ao-release-gate-review`
4. Cross-AI peer review AGREE (claude/anthropic + codex/openai)

## 9. Cross-AI Peer Review (HARD RULE CC-2)

Codex thread `019e6bd4-c650-7c12-83d6-2bd4c28602e7` iter-1 REVISE → iter-2 absorbed:

- Two-PR split (6c-fast-follow + 6c-closure)
- Authority mode revision (not just env removal)
- `authority_mode` field + `manual_approval_required=false` + `protected_environment_binding.mode=code_level_only_preprod`
- Trigger file pinned via schema, not literal trailer
- merged_by_login + commit_verification stronger than commit_trailer alone
- Mode-aware invariant tests

## 10. Definition of Done

1. `[pre-merge]` Plan doc records autonomous pre-prod authority mode + supersession contract revision + scope split
2. `[pre-merge]` Workflow file: env removal + push trigger + matrix
3. `[pre-merge]` Activation guard script: mode-aware status check
4. `[pre-merge]` gpp_status entry: authority_mode + status + autonomous_trigger_contract
5. `[pre-merge]` Trigger schema pinned (no trigger file)
6. `[pre-merge]` Schema-backed evidence artifact validates
7. `[pre-merge]` Invariant test suite passes (mode-aware)
8. `[pre-merge]` 6b invariant test mode-aware update (manual_protected_environment + operator_delegated_autonomous_preprod both accepted)
9. `[external]` Cross-AI peer review final AGREE
10. `[ci]` CI fully green
11. `[external]` Operator review approval
12. `[post-merge]` 6c-closure can begin (trigger file + per-run evidence + closure)

## 11. Non-Goals

1. No trigger file in this PR
2. No live adapter call
3. No submanifest BC-1 flip
4. No top-level guard flag change
5. No bounded-window limit relaxation
6. No 9-key readiness manifest mutation
7. No protected workflow / ao-release-gate runtime change
8. No SDK / MCP / public boundary doc change

## 12. Exit Decision

`ri78b_bc1_6c_fast_follow_autonomous_preprod_contract_revised_no_trigger_file_no_run_evidence`
