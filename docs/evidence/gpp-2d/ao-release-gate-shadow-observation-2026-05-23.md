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
- PR: (will be filled in after the PR is opened)
- Branch: `codex/gpp2d-shadow-observation`
- Base: `main`
- Diff scope: docs-only (this file).

### 2.2 Shadow workflow run

- Workflow file: `.github/workflows/ao-release-gate.yml`
- Job name: `ao-release-gate-shadow`
- Required-check name reserved (not posted): `ao-release-gate`
- Run URL: (filled after CI)
- Job conclusion: (filled after CI; expected `success`, advisory)

### 2.3 payload.json (API-derived release-gate payload)

Captured from the workflow's `payload.json` upload artifact after the shadow
job completes.

```text
(filled after artifact download)
```

Acceptance checks against the API-derived payload contract:

- [ ] `repository.full_name == "Halildeu/ao-kernel"`
- [ ] `pull_request.number` populated
- [ ] `pull_request.head.sha` is a 40-hex SHA
- [ ] `pull_request.base.ref == "main"`
- [ ] `changed_paths` non-empty (this file)
- [ ] `required_checks` non-empty, with `ao-release-gate*` excluded
- [ ] `reviewed_slice` equals the base-ref `gpp_status.current_wp.id`
- [ ] `issue_url` equals the base-ref `gpp_status.current_wp.issue`
- [ ] `forbidden_secret_context_detected == false`
- [ ] `admin_bypass_requested == false`
- [ ] `pat_backed_bot_actor == false`
- [ ] `codex_or_claude_release_authority == false`
- [ ] `live_adapter_execution_requested == false`

### 2.4 decision.json (decision-core output)

Captured from the workflow's `decision.json` upload artifact after the shadow
job completes.

```text
(filled after artifact download)
```

Decision summary:

- `decision`: (filled)
- `allow`: (filled)
- `finding_code`: (filled)
- `conclusion_mode`: expected `shadow`
- `github_check_run.name`: expected `ao-release-gate`
- `github_check_run.conclusion`: `success` when `allow == true`, `neutral`
  when `allow == false` under shadow mode
- `findings`: (filled)

## 3. Acceptance summary

Filled in after the run completes.

| # | Check | Expected | Observed |
|---|---|---|---|
| 1 | `ao-release-gate-shadow` job ran on this real PR | yes | TBD |
| 2 | `payload.json` artifact uploaded | yes | TBD |
| 3 | `decision.json` artifact uploaded | yes | TBD |
| 4 | payload was built from the API + base-ref `gpp_status.v1.json` | yes | TBD |
| 5 | decision.json structurally valid | yes | TBD |
| 6 | `conclusion_mode == "shadow"` | yes | TBD |
| 7 | `github_check_run.name == "ao-release-gate"` (reserved name in decision body, NOT a posted check-run) | yes | TBD |
| 8 | Shadow job name on the PR check list is `ao-release-gate-shadow` (not `ao-release-gate`) | yes | TBD |
| 9 | `ao-release-gate` is NOT a required status check on branch protection | yes | TBD |
| 10 | GPP-2 status remains `blocked` | yes | TBD |
| 11 | Guard flags remain `false` (support widening / production claim / live adapter) | yes | TBD |

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
