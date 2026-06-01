# E-Ops: Operator Action Runbooks (V5)

> **Cross-AI plan-time AGREE** — Codex thread `019e84c6` (3 iters: REVISE/REVISE/AGREE)
> **Implementer:** Anthropic Claude / **Reviewer:** OpenAI Codex
> **Risk class:** conservative low-risk (docs/schemas/tests only; no operator action execution)

## 1. Scope

4 schema-backed runbooks for the explicit operator-action chain per HARD
RULE Tam Otonom Önerme (2026-05-28). Agent prepares all artifacts;
operator clicks one button per action.

**In scope:**
- 4 runbooks (PyPI publish + plan-approval env + mirror PAT + mirror env)
- Schema + checklist JSON (audit-grade fields)
- 36 invariant tests

**Out of scope (ZERO TOUCH):**
- `.github/workflows/*` (zero-touch repo-contract reuse)
- Actual operator action execution (PAT create, env configure, dispatch)
- Token-bearing material in any committed file

## 2. Codex Iter Chain

### iter-1 plan-time REVISE — 6 BLOCKER

| ID | Issue | Resolution |
|---|---|---|
| MC-1 | Workflow/secret/env name drift | `ao-ma-11e-2b-mirror-sync.yml` + `REPO_GH_PAT_PROJECTS_RW` + `ao-ma-mirror-sync` + `ao-ma-plan-approval` |
| MC-2 | PAT scope wrong | Classic (`project` + `public_repo`) + fine-grained (Issues R/W + PR Read; NOT Write) sections distinct |
| MC-3 | AO-MA-11A-2 dispatch model | Operator does NOT dispatch; dispatcher=agent; approver=Halildeu |
| MC-4 | Mirror apply env scope | `ao-ma-mirror-sync` env as separate 4th action |
| MC-5 | TestPyPI not supported | Removed from PyPI runbook |
| MC-6 | Schema under-specified | 18 audit-grade per-action fields |

### iter-2 plan-time REVISE — 5 BLOCKER + 4 hardening

| ID | Issue | Resolution |
|---|---|---|
| R1 | PyPI env missing | `environment_name: pypi` added to enum allowlist |
| R2 | Secret regex false-positive | sha256 removed; token-prefix-only patterns |
| R3 | Affirmative-claim test self-failing | Negation-aware scanner; forbidden_claims + claim_boundary discipline markers excluded |
| R4 | Fine-grained PAT over-privileged | PR Read only (mevcut workflow); PR Write fail-closed |
| R5 | `external_action_executed` semantic | Rename `agent_executed_external_action: false` |

### iter-3 absorb AGREE + ready_for_impl:true + must_close_findings:[]

3 non-blocking impl notes:
- Modern OpenAI `sk-proj-` pattern coverage in secret scan
- Affirmative-claim scanner token-proximity (current v1 line-level OK)
- `status_evidence_refs` URL allowlist pattern (future)

## 3. Implementation Artifacts

| File | LOC | Purpose |
|---|---|---|
| `ao_kernel/defaults/schemas/operator-action-checklist.schema.v1.json` | ~155 | Draft 2020-12; 18-field per-action |
| `docs/operator-runbooks/operator-action-checklist.v1.json` | ~145 | 4 pending actions |
| `docs/operator-runbooks/README.md` | ~175 | Layout + 4 discipline sub-section + per-action overview |
| `docs/operator-runbooks/01-pypi-publish.md` | ~75 | v-tag guard + yank-not-delete rollback |
| `docs/operator-runbooks/02-plan-approval-environment.md` | ~85 | Operator does NOT dispatch; env configure only |
| `docs/operator-runbooks/03-mirror-pat-secret.md` | ~155 | Classic+Fine-grained PAT sections; stdin pipe pattern |
| `docs/operator-runbooks/04-mirror-sync-environment.md` | ~80 | Apply env; depends on Action 3 |
| `tests/test_operator_runbooks.py` | ~440 | 36 invariants |
| `.claude/plans/E-OPS-OPERATOR-ACTION-RUNBOOKS.md` | this | Plan + Codex chain |

## 4. Checklist Overview

| # | Action | Workflow | Environment | Secret | ETA |
|---|---|---|---|---|---|
| 1 | PyPI v4.1.0 publish | `publish.yml` | `pypi` | — | 5 min |
| 2 | Plan-approval env configure | `ao-ma-11a-plan-approval.yml` | `ao-ma-plan-approval` | — | 4 min |
| 3 | Mirror PAT secret seed | `ao-ma-11e-2b-mirror-sync.yml` | — (secret-only) | `REPO_GH_PAT_PROJECTS_RW` | 6 min |
| 4 | Mirror-sync env configure | `ao-ma-11e-2b-mirror-sync.yml` | `ao-ma-mirror-sync` | — | 4 min |

**Total operator time: ~19 minutes.**

## 5. Test Sections (36 invariants)

| Section | Count | Focus |
|---|---|---|
| 1. Schema validity | 6 | Draft 2020-12 + additionalProperties + const pins + disclaimer + claim_boundary |
| 2. Schema negative | 3 | guard flip + credential_committed + agent_executed reject |
| 3. Checklist content | 5 | validates + 4 actions + unique IDs + workflow paths exist + env allowlist |
| 4. Runbook structure | 4 | 4 files exist + 6 core sections + README links runbooks/checklist/schema |
| 5. Credential discipline | 5 | no PAT in docs/checklist + stdin pipe + forbidden body/echo + classic+fine-grained distinct |
| 6. Plan-approval discipline | 2 | does NOT dispatch + exact env name |
| 7. PyPI discipline | 3 | no TestPyPI + yank not delete + v-tag guard |
| 8. Public claim discipline | 3 | affirmative-claim scanner + agent-prepared statement + no-credential statement |
| 9. Repo-contract | 3 | 3 workflow files exist (drift check) |
| 10. Governance | 2 | no .github/workflows + all actions pending |

## 6. Out-of-scope follow-up slices (6)

| ID | Slice |
|---|---|
| E-Ops-2 | TestPyPI workflow input + dry-run integration |
| E-Ops-3 | Vault integration runbook (operator-deployed) |
| E-Ops-4 | Operator audit trail (sign-off log + evidence chain) |
| E-Ops-5 | Multi-tenant operator delegation |
| E-Ops-6 | Operator Grafana dashboard |
| E-Ops-7 | Runbook localization (i18n) |

## 7. References

- HARD RULE Tam Otonom Önerme (2026-05-28)
- HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14)
- HARD RULE Workspace Tooling (2026-05-27)
- HARD RULE D43 stdin-pipe secret handling
- Codex thread `019e84c6` (3-iter REVISE/REVISE/AGREE)
- V5 roadmap: `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`
