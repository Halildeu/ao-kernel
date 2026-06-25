# ao-kernel Operator Action Runbooks (V5 E-Ops)

> **Agent-prepared only.** **Operator action required.** **No credential
> material is committed in this repository.** The agent does NOT execute
> external actions (PAT create, environment configure, workflow dispatch);
> the operator does, following these runbooks step-by-step.
>
> **Repository SSOT, not GitHub UI authority.** This document describes
> the *minimal* steps to wire repo-prepared artifacts into the operator's
> GitHub UI. The operator is the SSOT for *organization-level decisions*;
> this repo is the SSOT for *artifact contracts*.
>
> The three guard flags (`support_widening`, `production_platform_claim`,
> `live_adapter_execution`) remain `const false`. This package makes NO
> production-ready claim and confers NO live adapter execution authority.

## 0. Layout

| File | Role |
|---|---|
| [`operator-action-checklist.v1.json`](operator-action-checklist.v1.json) | Schema-backed checklist (4 actions, pending state) |
| [`01-pypi-publish.md`](01-pypi-publish.md) | P0-1: PyPI v4.3.1 publish dispatch |
| [`02-plan-approval-environment.md`](02-plan-approval-environment.md) | AO-MA-11A-2: `ao-ma-plan-approval` environment configure |
| [`03-mirror-pat-secret.md`](03-mirror-pat-secret.md) | AO-MA-11E-2b: `REPO_GH_PAT_PROJECTS_RW` secret seed |
| [`04-mirror-sync-environment.md`](04-mirror-sync-environment.md) | AO-MA-11E-2b: `ao-ma-mirror-sync` environment configure |
| [`05-minimax-mavis-runtime.md`](05-minimax-mavis-runtime.md) | MiniMax/Mavis local runtime workaround + credential gate for high-risk review evidence |
| [`../../ao_kernel/defaults/schemas/operator-action-checklist.schema.v1.json`](../../ao_kernel/defaults/schemas/operator-action-checklist.schema.v1.json) | JSON Schema (Draft 2020-12) |

## 1. Checklist Overview

| # | Action | Workflow | Environment | Secret | ETA |
|---|---|---|---|---|---|
| 1 | PyPI v4.3.1 publish | `publish.yml` | `pypi` | — | 5 min |
| 2 | Plan-approval env configure | `ao-ma-11a-plan-approval.yml` | `ao-ma-plan-approval` | — | 4 min |
| 3 | Mirror PAT secret seed | `ao-ma-11e-2b-mirror-sync.yml` | — (secret-only) | `REPO_GH_PAT_PROJECTS_RW` | 6 min |
| 4 | Mirror-sync env configure | `ao-ma-11e-2b-mirror-sync.yml` | `ao-ma-mirror-sync` | — | 4 min |

**Total operator time: ~19 minutes.**

## 2. Discipline (per Codex 019e84c6 absorb)

### 2.1 Agent boundary

- The agent prepared every artifact in this PR.
- The agent does NOT execute any operator action.
- `agent_executed_external_action: const false` is enforced by the schema and
  by `tests/test_operator_runbooks.py`.

### 2.2 Credential boundary

- NO credential material is committed: not PAT tokens, not webhook URLs,
  not API keys.
- Secret-scan invariants block accidental commits (token-prefix patterns).
- `credential_material_committed: const false` is enforced.

### 2.3 Public-claim boundary

- NO `production-ready`, `we guarantee`, `production SLA`, `guaranteed performance`
  affirmative claims.
- Negative disclaimers (`not production-ready`, `we do NOT guarantee`)
  are explicitly allowed.
- Test scanner uses inline-code-aware semantics; the `forbidden_claims`
  field in the checklist is not flagged.

### 2.4 Authority boundary

- Repository SSOT for artifact contracts.
- Operator SSOT for organization-level decisions (who reviews, when to
  publish, what PAT to mint).
- The runbooks NEVER instruct the operator to take an irreversible action
  without an explicit verification step.

## 3. Action 1 — PyPI v4.3.1 Publish (P0-1)

See [`01-pypi-publish.md`](01-pypi-publish.md).

The repo `publish.yml` workflow enforces a v-tag pattern on the dispatch
`ref` input. The operator dispatches the workflow with a verified tag SHA
matching the main release commit. **Rollback** uses `yank` (not delete)
plus a corrective patch release. **TestPyPI dry-run is NOT supported by
the current `publish.yml`**; verification relies on the v-tag guard plus
the GHCR + PyPI parity check.

## 4. Action 2 — Plan-Approval Environment (AO-MA-11A-2)

See [`02-plan-approval-environment.md`](02-plan-approval-environment.md).

Operator action is **environment create + configure only**. The operator
does NOT dispatch the plan-approval workflow:

- Dispatcher = agent / automation
- Approver = `Halildeu` (or another non-author required reviewer)
- Self-review is guarded by the workflow contract; UI-side operator
  dispatch is NOT supported.

Environment configuration:

- Name (exact): `ao-ma-plan-approval`
- Required reviewers: at least one non-author
- Wait timer: 0
- Environment secrets: none (empty in v1)

## 5. Action 3 — Mirror-Sync PAT Secret (AO-MA-11E-2b)

See [`03-mirror-pat-secret.md`](03-mirror-pat-secret.md).

Repository secret `REPO_GH_PAT_PROJECTS_RW` for the
`ao-ma-11e-2b-mirror-sync.yml` workflow. The runbook ships two PAT options:

- **Classic PAT (recommended)** — scopes `project` + `public_repo`
- **Fine-grained PAT** — Issues: Read+Write; Metadata: Read;
  Pull requests: Read; Projects: operator-verified

The runbook NEVER allows committing the token. The operator seeds the
secret via the **stdin pipe** pattern (HARD RULE D43), never via
`--body` or shell `echo`.

## 6. Action 4 — Mirror-Sync Apply Environment (AO-MA-11E-2b)

See [`04-mirror-sync-environment.md`](04-mirror-sync-environment.md).

The `ao-ma-11e-2b-mirror-sync.yml` workflow apply job is gated by an
`ao-ma-mirror-sync` environment. The operator configures it as a
separate prerequisite. Apply dispatch is dependent on:

1. Action 3 (PAT secret seeded)
2. Action 4 (environment configured)
3. Accepted dry-run report digest (from a prior workflow run)

## 7. Out of Scope (E-Ops follow-up slices)

| ID | Slice |
|---|---|
| E-Ops-2 | TestPyPI workflow input + dry-run integration (`publish.yml` change) |
| E-Ops-3 | Vault integration runbook (operator-deployed Vault) |
| E-Ops-4 | Operator audit trail (sign-off log + status evidence chain) |
| E-Ops-5 | Multi-tenant operator delegation |
| E-Ops-6 | Operator Grafana dashboard |
| E-Ops-7 | Runbook localization (i18n) |

## 8. References

- HARD RULE Tam Otonom Önerme (2026-05-28): agent prepares; operator
  signs off
- HARD RULE Workspace Tooling (2026-05-27): Microsoft Teams primary;
  Slack dormant
- HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14)
- Codex cross-AI plan-time AGREE: thread `019e84c6` (3 iters: REVISE/REVISE/AGREE)
- V5 roadmap: [`../../.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`](../../.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md)
