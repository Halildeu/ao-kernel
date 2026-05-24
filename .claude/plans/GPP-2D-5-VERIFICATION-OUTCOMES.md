# GPP-2D-5 Verification Outcomes — Post-Cutover Acceptance Record

> Status: cutover landed AND post-cutover verification passed.
>
> Work package: GPP-2 (still blocked).
> Allowed-scope cell: "cut branch protection or rulesets over to
> require the ao-release-gate status check only after enforce-mode
> evidence is captured, with admin bypass disallowed".
>
> This file is the canonical post-cutover acceptance record that
> the GPP-2D-5 runbook §3.5 demands before GPP-2D-6 / GPP-2D-7 can
> open. No GitHub setting is changed by this PR — the cutover save
> was performed by the operator on the GitHub UI; this PR only
> records the acceptance signals the agent collected afterward.

## 1. Cutover audit (operator action)

The operator (`Halildeu`, repo owner / admin) saved a new branch
ruleset named **"Protect main"** in the GitHub UI / Rulesets API
on 2026-05-24. Ruleset id: `16803733`.

Before/after summary (from the API state captured immediately
after the save):

* **Enforcement**: `active`
* **Target branches**: `~DEFAULT_BRANCH` (main)
* **Required status checks**:
    * `ao-release-gate` (integration_id `15368` — GitHub Actions,
      source-pinned)
* **Strict (require branches up to date)**: `true`
* **Block force pushes**: `true`
* **Bypass actors**: `[]` (admin bypass disallowed on this ruleset)

Pre-existing legacy branch-protection rule on `main` was NOT
modified by this cutover and is preserved as-is for the other
7 CI required-check contexts (lint / test (3.11) / test (3.12) /
test (3.13) / coverage / typecheck / packaging-smoke). Its
`enforce_admins.enabled` flag is `false` — this is a
pre-existing surface that does NOT affect `ao-release-gate`'s
enforcement (the gate is enforced by the new ruleset whose
`bypass_actors == []`). Tightening the legacy `enforce_admins`
flag is an optional later hardening slice; it is explicitly out
of scope for GPP-2D-5.

No `--admin` merge attempted. No other rule changed in the same
save.

## 2. Pre-cutover source-pin check (runbook §1 row 6)

Before the cutover the operator ran the source-pin probe
recommended by the runbook to rule out an external App emitting
a check-run with the same name:

```
gh api "repos/Halildeu/ao-kernel/commits/cb47507/check-runs?per_page=100" \
  --jq '.check_runs[] | select(.name == "ao-release-gate") | {app_id: .app.id, app_slug: .app.slug, name: .name}'
```

Output:

```
{"app_id":15368,"app_slug":"github-actions","name":"ao-release-gate"}
```

Single row, `app_slug == "github-actions"`. No external App
collision. Safe to proceed.

## 3. Post-cutover API acceptance (runbook §3.1 + §3.2)

The agent ran the runbook §3.1 + §3.2 queries immediately after
the operator saved the ruleset. Output:

```bash
gh api "repos/Halildeu/ao-kernel/rulesets/16803733"
```

Acceptance signals (all must hold):

| Signal | Expected | Actual | ✓ |
|---|---|---|---|
| `enforcement` | `active` | `active` | ✅ |
| `conditions.ref_name.include` | covers main | `["~DEFAULT_BRANCH"]` | ✅ |
| `bypass_actors` | `[]` | `[]` | ✅ |
| `required_checks[].context` | includes `ao-release-gate` | `["ao-release-gate"]` | ✅ |
| `required_checks[].integration_id` | GitHub Actions | `15368` | ✅ |
| Strict (require up-to-date) | `true` | `true` | ✅ |
| Block force pushes | rule active | `true` | ✅ |

Legacy `enforce_admins.enabled` is `false` (pre-existing, not
modified). Documented as an optional later hardening; the
ruleset's `bypass_actors == []` is the acceptance signal that
matters for `ao-release-gate` enforcement.

## 4. Negative-path verification PR (runbook §3.3) — PR #607

PR #607 ships a trivial doc file at `.claude/plans/` with NO
reviewer evidence file at the repo root. The cutover-now-required
`ao-release-gate` enforce gate must reject the merge.

Acceptance signals (all observed):

* PR url: `https://github.com/Halildeu/ao-kernel/pull/607`
* Branch: `codex/gpp2d-5-verification-negative-path` (head `5fac138`)
* Actions run id: `26369184385` (`Test / ao-release-gate (pull_request)`)
* `gh pr view 607 --json mergeStateStatus,statusCheckRollup`:
    * `mergeStateStatus == "BLOCKED"` ✅
    * `statusCheckRollup[].ao-release-gate.conclusion == "FAILURE"` ✅
* `Evaluate ao-release-gate decision (enforce)` step output:
    * `decision: deny_missing_evidence` ✅
    * `allow: false` ✅
    * `conclusion_mode: enforce` ✅
    * `github_check_run: ao-release-gate failure` ✅
    * `review_evidence: blocked (ao_release_gate_review_evidence_not_accepting)` ✅
* `gh pr merge 607 --repo Halildeu/ao-kernel --squash` rejected
  by the GitHub API with the message: *"Pull request
  Halildeu/ao-kernel#607 is not mergeable: the base branch
  policy prohibits the merge."* ✅
* The CLI's "use `--admin` to bypass" suggestion was NOT taken
  (HARD RULE forbids `--admin` merge; the ruleset `bypass_actors`
  is empty regardless).

PR #607 is closed without merging as part of this verification
slice cleanup.

## 5. Positive-path verification PR (runbook §3.4) — PR #608

PR #608 ships a trivial doc plus a schema-valid
`local-ai-review-evidence.v1.json` at the repo root with
`reviewer.verdict: AGREE`, cross-provider (implementer
claude/anthropic, reviewer codex/openai),
`scope_reviewed.changed_files` matching the actual PR diff
exactly. The cutover-now-required `ao-release-gate` enforce gate
must accept the PR.

Acceptance signals (all observed):

* PR url: `https://github.com/Halildeu/ao-kernel/pull/608`
* Branch: `codex/gpp2d-5-verification-positive-path` (head `69a909e`)
* Actions run id: `26369236624` / job id `77618585276`
  (`Test / ao-release-gate (pull_request)`, completed in 21s)
* `gh pr view 608 --json statusCheckRollup`:
    * `statusCheckRollup[].ao-release-gate.conclusion == "SUCCESS"` ✅
* `Evaluate ao-release-gate decision (enforce)` step output:
    * `decision: allow_autonomous_merge` ✅
    * `allow: true` ✅
    * `conclusion_mode: enforce` ✅
    * `github_check_run: ao-release-gate success` ✅
    * `head_sha: 69a909e1476c9bddad9997cd2cbefeddbb665b83` ✅
      (runtime head SHA bound to the gate evidence, exactly as
      the iter-4 dual-ref contract from GPP-2D-3c demands)
    * `review_evidence: pass` ✅
* Audit artifact: full 4-file set uploaded
  (`payload.json` + `decision.json` +
  `local-gpp-gate-evidence.v1.json` +
  `local-gpp-gate.stdout.log`).

PR #608's `mergeStateStatus == "BLOCKED"` reflects code-owner
review still required (legacy branch protection's
`required_pull_request_reviews.require_code_owner_reviews:
true`). `ao-release-gate` itself did NOT block — it passed.
This is exactly the contract: the gate enforces but does not
override the high-risk CODEOWNERS reviewer rule.

PR #608 is closed without merging as part of this verification
slice cleanup. (We do not merge the probe; the GPP-2D-5 runbook
already merged in `cb47507`; this probe only proves the enforce
gate now accepts well-formed evidence post-cutover.)

## 6. Coverage matrix

The §3 verification chain proved each enforce-contract property
the GPP-2D-5 runbook needed to land:

| Runbook signal | Source | Result |
|---|---|---|
| Ruleset is the active source of `ao-release-gate` requirement | §3.1 ruleset detail API | ✅ |
| `ao-release-gate` is source-pinned to GitHub Actions | §3.1 `required_checks[].integration_id == 15368` | ✅ |
| Admin bypass disallowed on the ruleset path | §3.1 `bypass_actors == []` | ✅ |
| `ao-release-gate` failure blocks the merge button | §3.3 PR #607 `mergeStateStatus == BLOCKED` + UI | ✅ |
| GitHub API rejects merge of a deny PR | §3.3 PR #607 `gh pr merge --squash` rejected | ✅ |
| `ao-release-gate` success matches the post-cutover happy path | §3.4 PR #608 SUCCESS + `decision: allow_autonomous_merge` | ✅ |
| Runtime gate evidence binds to head SHA at runtime | §3.4 PR #608 `head_sha == 69a909e1...` | ✅ |
| Full audit artifact set produced on positive runs | §3.4 PR #608 4-file artifact upload | ✅ |
| High-risk CODEOWNER review preserved (broad model held this slice) | PR #608 `mergeStateStatus: BLOCKED` due to `reviewDecision: REVIEW_REQUIRED` (legacy code-owner rule still active) | ✅ |

## 7. Out of scope (intentionally separate slices)

* **GPP-2D-6 auto-merge smoke**: low-risk PR auto-merges on
  green required checks; high-risk PR still requires
  CODEOWNER review. This requires CODEOWNERS narrowing first
  (broad `* @Halildeu @gladyatore-lab` model currently blocks
  low-risk auto-merge by demanding a code-owner review on
  every PR). Not in this slice.
* **GPP-2D-7 / AO-GATE-9 closeout**: flip `gpp_status.v1.json`
  `current_wp.status` from `blocked` to a closed state, reconcile
  `forbidden_actions`, and supersede the bootstrap approval flow.
  Not in this slice.
* **Legacy `enforce_admins.enabled = true` hardening**: the
  legacy branch-protection rule's admin-enforce flag is `false`;
  documented as an optional later hardening (does not affect
  `ao-release-gate` enforcement, but tightens the legacy
  7-check surface). Not in this slice.
* **Probe PR merging**: PRs #607 and #608 are verification
  probes; both are closed without merging.
* **`support_widening`, `production_platform_claim_allowed`,
  `live_adapter_execution_allowed`**: all stay false.
* No `--admin` merge attempted. No branch-protection mutation
  by the agent. The ruleset save in §1 was an operator UI
  action.

## 8. Closing note

GPP-2D-5 is now fully landed end-to-end:

* GPP-2D-5 runbook (agent half, PR #605 `cb47507`) records the
  exact UI / API steps.
* The operator cutover (this slice §1) saved the "Protect main"
  ruleset with `ao-release-gate` source-pinned and bypass empty.
* The agent post-cutover verification (this slice §3-§5)
  produced API-pinned + live-PR acceptance signals.

`ao-release-gate` is now a required, source-pinned, no-bypass
status check on `main`. Cross-AI peer review remains the merge
prerequisite for evidence-bearing PRs; the merge button is now
gated by both the gate and the existing code-owner review rule.

GPP-2 stays `blocked` until GPP-2D-6 (auto-merge smoke + the
CODEOWNERS narrowing it depends on) and GPP-2D-7 (AO-GATE-9
closeout) land in their own slices.
