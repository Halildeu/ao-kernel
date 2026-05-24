# GPP-2D ao-release-gate Shadow Workflow Observation (2026-05-23)

> Status: shadow / advisory observation slice — no enforce, no branch-protection
> change, no auto-merge, no support widening, no production claim, no live
> adapter execution.

## 1. Purpose

GPP-2D-2c (PR #593, merged as commit `ce3a1d1`) introduced the
`ao-release-gate-shadow` workflow as an advisory check on every pull request.
Before any GPP-2D-3 enforce-mode slice can land, the agent observes the shadow
behavior on a real pull request to confirm:

- the trusted-base gate runs end-to-end and produces both `payload.json` and
  `decision.json`;
- the payload is built only from the GitHub API plus the base-ref
  `gpp_status.v1.json`, never from a PR-committed JSON file;
- the decision is reported as advisory — the job exits 0 regardless of the
  decision body, and the fallback synthesizer is wired so even a transient
  pre-decision failure still produces an auditable artifact;
- the required-check name `ao-release-gate` is not yet posted on any pull
  request; only the distinct advisory job name `ao-release-gate-shadow` runs.

This evidence record is **not**:

- an enforce-mode flip (that is the GPP-2D-3 follow-up slice);
- a branch-protection cutover (that is the GPP-2D-5 operator action);
- a GPP-2 closeout (that is the GPP-2D-7 agent slice, gated on the full
  chain);
- any change to `support_widening_allowed`,
  `production_platform_claim_allowed`, or `live_adapter_execution_allowed`.

## 2. Observation subject

This pull request is itself the observation subject. The shadow workflow runs
on this PR's own checks; the captured artifacts are recorded below after CI
completes.

### 2.1 Pull request

- Repository: `Halildeu/ao-kernel`
- PR: [#594](https://github.com/Halildeu/ao-kernel/pull/594)
- Branch: `codex/gpp2d-shadow-observation`
- Head SHA: `9e709c93a7d958e7203ec79f970fd2eb377632d5`
- Base: `main`
- Diff scope: docs-only (this file).

### 2.2 Shadow workflow run

- Workflow file: `.github/workflows/ao-release-gate.yml`
- Job name: `ao-release-gate-shadow`
- Required-check name reserved (not posted): `ao-release-gate`
- Run URL: <https://github.com/Halildeu/ao-kernel/actions/runs/26357238844/job/77586116936>
- Job conclusion: **`success`** (advisory ✓ — the job exits 0 regardless of
  the decision body, per the GPP-2D-2c shadow contract)
- Required-check `ao-release-gate` on the PR checks list: **skipping** (i.e.
  no real check-run was posted under the reserved required-check name ✓)

### 2.3 payload.json (API-derived release-gate payload)

Captured key fields:

| Field | Value |
|---|---|
| `repository.full_name` | `Halildeu/ao-kernel` |
| `pull_request.number` | `594` |
| `pull_request.head.sha` | `9e709c93a7d958e7203ec79f970fd2eb377632d5` (40-hex) |
| `pull_request.head.ref` | `codex/gpp2d-shadow-observation` |
| `pull_request.base.ref` | `main` |
| `reviewed_slice` | `GPP-2` (from base-ref `gpp_status.current_wp.id`) |
| `issue_url` | `https://github.com/Halildeu/ao-kernel/issues/567` (from base-ref `gpp_status.current_wp.issue`) |
| `changed_paths` | `["docs/evidence/gpp-2d/ao-release-gate-shadow-observation-2026-05-23.md"]` (1) |
| `required_checks` | 20 entries (self-name `ao-release-gate*` excluded ✓) |
| `forbidden_secret_context_detected` | `false` |
| `admin_bypass_requested` | `false` |
| `pat_backed_bot_actor` | `false` |
| `codex_or_claude_release_authority` | `false` |
| `live_adapter_execution_requested` | `false` |

Acceptance checks against the API-derived payload contract:

- [x] `repository.full_name == "Halildeu/ao-kernel"`
- [x] `pull_request.number` populated (`594`)
- [x] `pull_request.head.sha` is a 40-hex SHA
- [x] `pull_request.base.ref == "main"`
- [x] `changed_paths` non-empty (the evidence doc itself)
- [x] `required_checks` non-empty, with `ao-release-gate*` excluded
- [x] `reviewed_slice` equals base-ref `gpp_status.current_wp.id` (`GPP-2`)
- [x] `issue_url` equals base-ref `gpp_status.current_wp.issue`
- [x] `forbidden_secret_context_detected == false`
- [x] `admin_bypass_requested == false`
- [x] `pat_backed_bot_actor == false`
- [x] `codex_or_claude_release_authority == false`
- [x] `live_adapter_execution_requested == false`

### 2.4 decision.json (decision-core output)

Decision summary:

| Field | Value |
|---|---|
| `artifact_kind` | `ao_release_gate_decision` |
| `program_id` | `GPP-2v` |
| `decision` | `deny_missing_evidence` |
| `allow` | `false` |
| `finding_code` | `deny_missing_evidence` |
| `conclusion_mode` | `shadow` |
| `dry_run` | `true` |
| `merge_authority_enabled` | `false` |
| `github_check_run.name` | `ao-release-gate` |
| `github_check_run.status` | `completed` |
| `github_check_run.conclusion` | `neutral` |
| `github_check_run.title` | `ao-release-gate: deny_missing_evidence` |

Findings (3):

1. `ao_release_gate_required_checks_not_green` — at the time the shadow job
   evaluated the payload, the rest of the CI matrix (lint / typecheck /
   test 3.11 / 3.12 / 3.13 / coverage / packaging / container smokes) was
   still `in_progress`, so the `required_checks` aggregate was not green
   yet. See observation note (a) below.
2. `ao_release_gate_review_evidence_missing` — this PR does not commit a
   `local-gpp-gate-evidence.v1.json` to its head; the decision core
   correctly reports the absence and fails closed.
3. `ao_release_gate_review_evidence_context_unverifiable` — the binding
   check correctly emits the **unverifiable** finding (mapping to
   `deny_missing_evidence`), not the **unbound** finding (which would map
   to `deny_untrusted_context`). The conditional-finding logic added by
   the GPP-2D-2b post-impl absorb (Codex thread `019e51b1`) is verified
   on real evidence.

17 of the 20 ao-release-gate checks passed; the 3 above were expected to
block on a docs-only PR with no review evidence and other CI still in
flight. The decision body is internally consistent with the shadow
advisory contract: `allow=false`, `conclusion_mode=shadow`,
`github_check_run.conclusion=neutral`.

### 2.5 Observation notes (for GPP-2D-3 enforce-job slice)

(a) **Pre-decision check timing.** The shadow workflow runs as its own job
in `test.yml` that depends only on `event-gate`. When `ao-release-gate-shadow`
evaluates the payload, the rest of the CI matrix may still be `in_progress`,
so the `required_checks` aggregate is reported as
`ao_release_gate_required_checks_not_green` even on PRs that later turn green.
Design doc §3.5 already calls this out: the enforce job must run **after**
the CI checks it inspects (either via `needs:` or by polling for check
completion). GPP-2D-3 should pin a `needs: [lint, typecheck, test, coverage,
extras-install, release-gate-container-smoke, policy-container-smoke,
packaging-smoke]` list (or equivalent) so the enforce gate evaluates only
after the required matrix has settled.

(b) **Duplicate required-check entries.** The `required_checks` array carries
each check name twice (e.g. `test (3.13)` appears once with status
`in_progress` from the latest workflow run and once again because
`gh api .../check-runs` returns all check-runs on the commit, including ones
cancelled by `concurrency.cancel-in-progress`). For shadow this is harmless
(the gate already de-facto fails closed on duplicates if any of them is not
green). For enforce, `scripts/ao_release_gate_build_payload.py` should
de-duplicate `required_checks` by name keeping the most recent
`completed_at` / `started_at` entry, so a stale cancelled run does not
permanently mark a check as not-green.

These observations are recorded as follow-ups for **GPP-2D-3**. They are
**not** blocking the shadow advisory contract (which works as designed on
this PR).

## 3. Acceptance summary

| # | Check | Expected | Observed |
|---|---|---|---|
| 1 | `ao-release-gate-shadow` job ran on this real PR | yes | ✅ ran, conclusion `success` |
| 2 | `payload.json` artifact uploaded | yes | ✅ uploaded |
| 3 | `decision.json` artifact uploaded | yes | ✅ uploaded |
| 4 | payload was built from the API + base-ref `gpp_status.v1.json` | yes | ✅ (issue_url + reviewed_slice from gpp_status; changed_paths + required_checks from gh API) |
| 5 | decision.json structurally valid | yes | ✅ |
| 6 | `conclusion_mode == "shadow"` | yes | ✅ |
| 7 | `github_check_run.name == "ao-release-gate"` (reserved name in decision body, NOT a posted check-run) | yes | ✅ |
| 8 | Shadow job name on the PR check list is `ao-release-gate-shadow` (not `ao-release-gate`) | yes | ✅ (`ao-release-gate-shadow` `pass`; `ao-release-gate` `skipping` / not posted) |
| 9 | `ao-release-gate` is NOT a required status check on branch protection | yes | ✅ (no branch-protection mutation was performed; it remains unset for `ao-release-gate`) |
| 10 | GPP-2 status remains `blocked` | yes | ✅ |
| 11 | Guard flags remain `false` (support widening / production claim / live adapter) | yes | ✅ |

## 4. Boundary affirmations

- `gpp_status.v1.json::current_wp.id == "GPP-2"` and `current_wp.status ==
  "blocked"` continue to hold.
- `support_widening_allowed == false`,
  `production_platform_claim_allowed == false`,
  `live_adapter_execution_allowed == false`.
- No branch-protection ruleset mutation in this slice.
- No `--admin` merge in this slice.
- No real check-run is posted under the required-check name `ao-release-gate`.
  Only the advisory job `ao-release-gate-shadow` runs; it is never a required
  status check.
- No live adapter dispatched; no testai / smee.io / deployment-protection
  callback evidence is collected here (deferred GPP-2C infrastructure).
- No long-lived secret / PAT / PEM / webhook-secret value is written into this
  observation record; only the ephemeral `GITHUB_TOKEN` already used inside
  the workflow is referenced.

## 5. Next slice recommendation

If the captured shadow decision body and the trusted-base trail look healthy
(acceptance table all green), the next agent-executable slice is **GPP-2D-3**:
introduce the enforce job under the required-check name `ao-release-gate`;
retire the advisory `ao-release-gate-shadow` job (or keep it strictly advisory
under a distinct name). GPP-2D-3 still does **not** flip branch protection
(that is the GPP-2D-5 operator action) and does **not** collect real-PR
success / failure evidence on the enforce job (that is the GPP-2D-4
operator + agent verification slice). GPP-2 remains `blocked`.
