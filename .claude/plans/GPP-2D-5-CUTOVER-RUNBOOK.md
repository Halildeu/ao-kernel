# GPP-2D-5 — Branch-Protection Cutover Runbook

> Status: agent half delivered (runbook + post-cutover verification
> procedure). Operator half is the actual GitHub UI / API change;
> until the operator executes it, `ao-release-gate` is not a
> required status check and the runtime contract is unchanged.
>
> Work package: GPP-2 (still blocked).
> Allowed-scope cell: "cut branch protection or rulesets over to
> require the ao-release-gate status check only after enforce-mode
> evidence is captured, with admin bypass disallowed".
> Hard stops still in force: `support_widening_allowed=false`,
> `production_platform_claim_allowed=false`,
> `live_adapter_execution_allowed=false`.
>
> **This document does NOT mutate branch protection by itself; it
> records the exact steps the operator (gladyatore-lab or another
> repo admin) follows in the GitHub UI / API, plus the
> post-cutover verification procedure the agent runs afterward.
> No `--admin` merge, no automated branch-protection mutation, no
> ruleset change is performed by the agent on the operator's
> behalf.**

## 1. Prerequisites — must all be satisfied before cutover

| # | Condition                                                                | Authority signal                                                                                                                                    |
|---|--------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|
| 1 | GPP-2D-3 enforce job present and authoritative.                          | `main:.github/workflows/test.yml` contains the `ao-release-gate` job; tests/test_ao_release_gate_enforce_job.py drift-guards green.                  |
| 2 | GPP-2D-3 bootstrap-prep merged.                                          | `main:scripts/ao_release_gate_build_payload.py::DEFAULT_ALLOWED_PATH_PREFIXES` includes `local-ai-review-evidence.v1.json` and `local-gpp-gate-evidence.v1.json` (PR #601). |
| 3 | GPP-2D-3 doc-hygiene merged.                                             | `main:.github/workflows/test.yml` ref-validation comment matches the evidence wording (PR #602).                                                     |
| 4 | GPP-2D-4 enforce-mode evidence merged.                                   | `main:.claude/plans/GPP-2D-4-ENFORCE-MODE-EVIDENCE.md` records ≥1 positive (`decision: allow_autonomous_merge`) and ≥1 negative each of `deny_policy_violation` and `deny_missing_evidence` from real PRs (PR #603). |
| 5 | Reviewer evidence integrity check (scope-limited).                       | This cutover-runbook PR and any PR that claims positive / verification-outcomes evidence (the §3.4 positive-path PR and the §3.5 verification outcomes PR) ships a `local-ai-review-evidence.v1.json` that (a) is schema-valid against `ao_kernel/defaults/schemas/local-ai-review-evidence.schema.v1.json`, (b) records `scope_reviewed.changed_files` matching the actual PR diff exactly, (c) carries `reviewer.verdict == "AGREE"` with implementer != reviewer at the **provider** level (cross-AI peer review per HARD RULE), and (d) records `tests: pass` and `secret_scan: pass` in `checks_considered`. The §3.3 negative-path verification PR is **explicitly exempt** from this row — its purpose is to commit missing / stale reviewer evidence so the gate emits `deny_missing_evidence` and the merge button is blocked; demanding schema-valid AGREE evidence there would defeat the negative-path test. |
| 6 | Source-pinned required-check name with API-level pinning.                | `ao-release-gate` is the GitHub Actions check produced by the enforce job in `.github/workflows/test.yml`. **Risk is not hypothetical**: `gpp_status.v1.json` records the historical existence of an external App that emitted a check-run with the same name. Before cutover, the operator runs `gh api repos/Halildeu/ao-kernel/commits/<recent_pr_head>/check-runs --jq '.check_runs[] \| select(.name == "ao-release-gate") \| {app_id: .app.id, app_slug: .app.slug, name: .name}'` and confirms the only matching row has the GitHub Actions `app_slug` (`github-actions`). If any other `app_id` / `app_slug` appears with the same `name`, **stop** — retire / rename the external check-run in its own slice first. |
| 7 | CODEOWNERS / high-risk surface enforcement model: explicit decision.     | The current `.github/CODEOWNERS` uses a broad `* @Halildeu @gladyatore-lab` rule that covers the full repo, so every PR — high-risk or low-risk — currently requires code-owner review. That is **safe but over-restrictive** for the autonomous-lane goal: GPP-2D-6 auto-merge smoke expects a low-risk PR to auto-merge on green required checks without manual code-owner review. This cutover **deliberately keeps the broad CODEOWNERS model in place**; narrowing CODEOWNERS to the high-risk surface set from §3.4 of the design doc is a separate prerequisite slice that lands before GPP-2D-6. The cutover does not weaken any existing reviewer rule. |
| 8 | Cross-AI peer-review chain landed end-to-end.                            | PRs #599 / #601 / #602 / #603 each show implementer claude/anthropic + reviewer codex/openai pairing with `reviewer.verdict: AGREE` recorded in their committed `local-ai-review-evidence.v1.json` files. |
| 9 | No active forbidden-action signal.                                       | `.claude/plans/gpp_status.v1.json::current_wp.status == "blocked"` AND `support_widening_allowed == production_platform_claim_allowed == live_adapter_execution_allowed == false`. `python3 scripts/gpp_next.py` re-confirms each. |

If any row is not satisfied, **stop** — do not start the cutover.
Resolve the missing prerequisite in its own slice first.

## 2. Operator cutover steps (GitHub UI; agent does NOT click these)

### 2.1 Open the branch protection rule for `main`

Repository → Settings → Rules → Rulesets (or "Branches" → branch
protection rule) for the `main` branch. If a ruleset is already in
use, edit it; otherwise edit the legacy branch protection rule —
do not create a second overlapping rule.

### 2.2 Add `ao-release-gate` as a required status check (source-pinned)

Inside the rule:

1. Enable **"Require status checks to pass"** (if not already on).
2. Enable **"Require branches to be up to date before merging"**
   so the gate evaluates against the latest base SHA.
3. In the "Required status checks" search box, type
   `ao-release-gate` and select **the check produced by the
   `.github/workflows/test.yml` workflow**. The source picker in
   the UI should disambiguate the workflow file path.
4. **Source-pinned acceptance** (not just string match): after
   saving, the operator confirms the rule's `app_id` /
   `integration_id` is GitHub Actions, not any external App.
   String context name alone is insufficient — an external App
   that emitted a check-run with the same `name` would otherwise
   silently satisfy the requirement. See §3.1 / §3.2 for the
   API queries that verify the pin.
5. If GitHub shows multiple sources with the same name (e.g. a
   stale testai-hosted App check-run), **do not** select the
   non-workflow source. The §1 row 6 prerequisite required that
   no such collision exists at cutover time; if it surfaces in
   the UI here, **stop** and resolve it in its own slice. If the
   workflow source is not yet shown, it means no run has
   populated the check name yet — open a trivial test PR first
   so GitHub registers the workflow check name, then return to
   this step. Do not pick an external source.

### 2.3 Disable admin bypass

In the same rule:

1. **Disable** "Allow specified actors to bypass required pull
   requests" (or the equivalent ruleset bypass list — for legacy
   branch-protection it is "Do not allow bypassing the above
   settings").
2. Leave **"Restrict who can push to matching branches"** as-is
   (or set per existing policy); the cutover does not change push
   permissions.
3. Leave **"Require linear history"** as-is.

### 2.4 Keep / enable required reviewer rules for high-risk surfaces

The high-risk surface set (§3.4 of the design doc) keeps
human / CODEOWNERS review even with the autonomous lane on. If a
CODEOWNERS file or ruleset rule already enforces this, verify
that:

* `.github/**`, `CODEOWNERS`, `AGENTS.md`, `CLAUDE.md`,
  `.claude/plans/gpp_status.v1.json`, the GPP and AO-GATE
  roadmap/status SSOT docs, `ao_kernel/ao_release_gate*.py`,
  `scripts/ao_release_gate_decision.py`,
  `scripts/local_gpp_gate*.py`, the local-gate and release-gate
  JSON schemas, deploy/publish workflows, gate host/deploy
  config, and secret / Vault / GitHub App wiring surfaces are
  covered.
* The cutover does not weaken any of those reviewer rules.

If high-risk reviewer rules are not yet recorded in `CODEOWNERS`
or in the ruleset, do **not** complete the cutover — handle that
in its own slice first.

### 2.5 Save the rule

Save and confirm the diff GitHub shows is exactly: `ao-release-gate`
added to required status checks, admin bypass off (or list
emptied). Nothing else should change in the same save.

### 2.6 Record the change in the operator audit trail

In a comment on the GPP-2D-5 cutover PR (this PR), the operator
pastes a structured audit block. **All fields are required** —
the agent does not paste this; the operator does. Template:

```
GPP-2D-5 cutover audit
======================
UTC timestamp:           <YYYY-MM-DDTHH:MM:SSZ>
Actor:                   <github_username>  (gladyatore-lab / other admin)
Ruleset / rule name:     <name>
Ruleset / rule id:       <id>
Required checks BEFORE:  <list of context names before save>
Required checks AFTER:   <list of context names after save, includes ao-release-gate>
Selected check source:
  - context:             ao-release-gate
  - app_id:              <GitHub Actions app_id (15368) or equivalent>
  - app_slug:            github-actions
  - integration_id:      <ruleset integration_id, equals GitHub Actions>
Bypass actors BEFORE:    <list or "enforce_admins=false">
Bypass actors AFTER:     []    (or enforce_admins=true for legacy branch protection)
CODEOWNER review:        unchanged  (broad * @Halildeu @gladyatore-lab preserved; narrowing is a separate slice)
Screenshots:             <link to "Required status checks" panel screenshot>
                         <link to "Bypass list" / "Enforce admins" screenshot>
Admin bypass attempted:  false
Other rule changes:      none  (diff was exactly: ao-release-gate added to required checks + admin bypass disabled)
```

If any field is missing or "n/a", the cutover is not recorded
and §3 verification cannot proceed; the operator either
completes the audit block or rolls back per §4.

## 3. Post-cutover verification (agent runs)

Once the operator has saved the rule and recorded the audit
comment, the agent runs the verification chain below. Each step
records its outcome in a follow-up PR or comment; nothing here
mutates branch protection.

### 3.1 Verify `ao-release-gate` is now a source-pinned required check

The verification depends on whether the repo uses the legacy
branch-protection API or the rulesets API. Run **both** and the
matching one returns the populated check; the other returns 404 /
empty.

#### Legacy branch protection

```bash
gh api repos/Halildeu/ao-kernel/branches/main/protection/required_status_checks \
  --jq '{strict: .strict, checks: [.checks[]? | {context, app_id}]}'
```

**Acceptance** (all three must hold):

1. `.strict == true` (require branches to be up to date).
2. `.checks[]` contains exactly one entry with
   `context == "ao-release-gate"`.
3. That entry's `app_id` equals the GitHub Actions integration's
   `app_id`. The historical workaround of only checking
   `contexts` (a flat string list, not source-pinned) is
   **not acceptance** — `contexts` is read for backward-compat
   only; the acceptance signal is `checks[].app_id`.

#### Rulesets

```bash
RULESET_ID=$(gh api repos/Halildeu/ao-kernel/rulesets --jq '.[] | select(.target == "branch") | .id' | head -1)
gh api "repos/Halildeu/ao-kernel/rulesets/$RULESET_ID" \
  --jq '{name, enforcement, conditions: .conditions.ref_name, bypass_actors, required: [.rules[] | select(.type=="required_status_checks") | .parameters.required_status_checks[]? | {context, integration_id}]}'
```

**Acceptance** (all five must hold):

1. `.enforcement == "active"`.
2. `.conditions.ref_name.include` contains the main branch
   pattern (`"refs/heads/main"` or `"~DEFAULT_BRANCH"`).
3. `.bypass_actors == []`.
4. `.required[]` contains exactly one entry with
   `context == "ao-release-gate"`.
5. That entry's `integration_id` equals the GitHub Actions
   integration id (not any other App's `integration_id`).

### 3.2 Verify admin bypass is fully off

Legacy:

```bash
gh api repos/Halildeu/ao-kernel/branches/main/protection/enforce_admins \
  --jq '.enabled'
```

**Acceptance**: `.enabled == true` (legacy reads as
"enforce admins also" — i.e. admins are NOT exempt).

Ruleset: covered by §3.1's `bypass_actors == []` acceptance.

The §3.1 + §3.2 queries together pin both source-attribution
(the required check is the GitHub Actions workflow, not an
external App) and bypass-absence (no admin can sneak around it).

### 3.3 Negative-path live verification PR (agent + operator)

Open a small no-op PR that intentionally omits the reviewer
evidence file at the repo root (or commits a stale variant).

**Step 1 — non-mutating snapshot.** Capture the API view first,
before any merge attempt:

```bash
gh pr view <PR_NUMBER> --repo Halildeu/ao-kernel \
  --json mergeStateStatus,statusCheckRollup,reviewDecision,mergeable
```

Expected fields:

* `mergeStateStatus == "BLOCKED"` (or `"DIRTY"` if other CI
  signals are still pending — block must be present in either
  case).
* `statusCheckRollup[]` contains a `name == "ao-release-gate"`
  entry whose `conclusion == "FAILURE"` (not `NEUTRAL`,
  `PENDING`, `SKIPPED`, or `SUCCESS`).
* `reviewDecision != "APPROVED"` if no manual approve is in
  place, or `"APPROVED"` while still BLOCKED if approval came in
  but the gate is the blocker — that is also acceptable; the
  invariant is "merge is blocked by ao-release-gate".
* `mergeable == "MERGEABLE"` is fine; the gate enforcement comes
  from `mergeStateStatus`, not the diff-mergeable flag.

**Step 2 — UI snapshot.** Take a screenshot of the PR's "Some
checks were not successful" or "Required" panel showing
`ao-release-gate` listed with the failure / red marker. The
"Merge pull request" button must be greyed with the message
"Required statuses must pass before merging" (or the ruleset
equivalent).

**Step 3 — intentional merge rejection.** Attempt the merge to
confirm GitHub actually rejects the API call, not just the UI:

```bash
gh pr merge <PR_NUMBER> --repo Halildeu/ao-kernel --squash
```

Expected: the command exits non-zero with a message referencing
the required-status-check failure. The PR must NOT actually
merge.

**Step 4 — close the verification PR** without merging once the
screenshots and API outputs are captured. Do not leave the
verification PR open dangling.

### 3.4 Positive-path live verification PR (agent + operator)

Open a small no-op PR that ships a valid reviewer evidence file
(implementer claude/anthropic, reviewer codex/openai, AGREE,
`scope_reviewed.changed_files` matching the trivial diff exactly)
and confirm:

* `ao-release-gate` appears as a required check, status `SUCCESS`
  in `gh pr view ... --json statusCheckRollup`.
* GitHub displays "All required checks have passed" in the PR
  conversation panel.
* `gh pr merge --squash` works (or, if GPP-2D-6 lands the
  auto-merge slice, `--auto --squash` enqueues and merges on
  green).
* `gh run view <run_id>` for the `Test / ao-release-gate
  (pull_request)` run shows, in the `Evaluate ao-release-gate
  decision (enforce)` step output:
    * `decision: allow_autonomous_merge`
    * `allow: true`
    * `conclusion_mode: enforce`
    * `github_check_run: ao-release-gate success`
    * `review_evidence: pass`
    * `review_evidence_context_bound: pass`
* The run artifact tab uploads the canonical 4-file set:
  `payload.json`, `decision.json`,
  `local-gpp-gate-evidence.v1.json`,
  `local-gpp-gate.stdout.log`.

The positive PR's record must include the **run id, job name,
and artifact set link** so a future audit can replay the
verification without re-running the cutover. This positive PR
may itself become the GPP-2D-6 auto-merge smoke evidence — that
is a separate slice (see §5).

### 3.5 Record verification outcomes

The agent commits a `.claude/plans/GPP-2D-5-VERIFICATION-OUTCOMES.md`
file (or appends to this runbook with a `## Verification record`
section). The file must contain at minimum:

```
GPP-2D-5 verification outcomes
==============================
Cutover audit comment link:   <link to operator §2.6 comment>
§3.1 / §3.2 API snapshots:
  required_status_checks:     <gh api output>
  enforce_admins:             <gh api output>
  ruleset detail:             <gh api output, if rulesets in use>
Negative-path verification:
  PR url:                     <https://github.com/Halildeu/ao-kernel/pull/...>
  mergeStateStatus:           BLOCKED
  ao-release-gate conclusion: FAILURE
  gh pr merge result:         rejected (exit code, message excerpt)
  Screenshots:                <links>
  PR closed:                  true
Positive-path verification:
  PR url:                     <https://github.com/Halildeu/ao-kernel/pull/...>
  Run id:                     <Actions run id>
  Job name:                   Test / ao-release-gate (pull_request)
  decision:                   allow_autonomous_merge
  conclusion_mode:            enforce
  Artifact set:               4 files (payload / decision / runtime evidence / stdout log)
  Artifact link:              <link>
  PR merged:                  true / not yet (waiting on operator manual merge)
GPP-2 status:                 still blocked (closeout is a separate GPP-2D-7 / AO-GATE-9 slice)
```

The verification outcomes file lands either as a follow-up PR
or as a comment on this PR — operator preference. Either way
it is the canonical post-cutover record; GPP-2D-6 / GPP-2D-7
cannot start without it.

## 4. Rollback procedure

The cutover is rolled back whenever **any §3.1 / §3.2 / §3.3 /
§3.4 acceptance signal fails**, including but not limited to:

* `ao-release-gate` not present in `checks[]` (legacy) or
  `required[]` (ruleset);
* **Source-pin failure**: `checks[].app_id` not equal to GitHub
  Actions on the legacy path, OR `required[].integration_id`
  not equal to GitHub Actions on the ruleset path. Even if the
  context string matches, an external App with the same name
  satisfying the requirement is a rollback trigger.
* **Duplicate `ao-release-gate` source collision**: more than
  one entry in `checks[]` or `required[]` with `context ==
  "ao-release-gate"` (or any sign of source ambiguity).
* Ruleset `enforcement != "active"`;
* Ruleset `conditions.ref_name` does not include the main
  branch pattern (`refs/heads/main` or `~DEFAULT_BRANCH`);
* Admin bypass still allowed: `bypass_actors` non-empty on
  rulesets, or `enforce_admins.enabled == false` on legacy
  branch protection;
* The §3.3 negative-path PR's merge button is NOT blocked, or
  `gh pr merge --squash` is silently accepted by the GitHub
  API;
* The §3.4 positive-path PR's `ao-release-gate` shows as
  `NEUTRAL` / `PENDING` / `SKIPPED` instead of `SUCCESS`, or
  the `Evaluate ao-release-gate decision (enforce)` step output
  does not show `decision: allow_autonomous_merge` /
  `conclusion_mode: enforce`;
* Any required-reviewer rule for the high-risk surface set
  weakened in the same save (CODEOWNER review changed from the
  current broad `* @Halildeu @gladyatore-lab` model without an
  explicit narrow-CODEOWNERS prerequisite slice having merged);
* The audit block from §2.6 is incomplete (missing required
  field) or contradicts the API snapshots in §3.1 / §3.2.

When any of these triggers, the operator **immediately reopens
the branch-protection rule and reverts the §2 change set in the
same UI**. No partial-state leave-as-is. No `--admin` bypass.
The agent records the rollback in `.claude/plans/` and the
cutover slice stays open until §3 produces clean signals.

Rollback is purely an UI / API operation; the agent does not
attempt it via `--admin` or any other bypass.

**Rollback record format** (mandatory; the agent commits it to
`.claude/plans/GPP-2D-5-ROLLBACK-<YYYYMMDD>.md` after the
rollback completes):

```
GPP-2D-5 rollback record
========================
UTC timestamp:           <YYYY-MM-DDTHH:MM:SSZ>
Trigger condition:       <which §3 acceptance signal failed>
Operator actor:          <github_username>
Ruleset / rule id:       <id>
API snapshot BEFORE rollback:
  required_status_checks: <gh api output captured BEFORE the operator reverts>
  enforce_admins:         <gh api output>
  ruleset detail:         <gh api output, if rulesets in use>
API snapshot AFTER rollback:
  required_status_checks: <gh api output captured AFTER the operator reverts>
  enforce_admins:         <gh api output>
  ruleset detail:         <gh api output>
Negative-path PR url:    <link, may be the failing verification PR>
Positive-path PR url:    <link, if positive was attempted>
Screenshots:             <links to before/after rule panel screenshots>
Admin bypass attempted:  false
GPP-2 status:            still blocked (rollback never widens or closes anything)
Next slice:              <what needs to land before the cutover is retried>
```

The rollback record is mandatory whenever §4 is invoked — there
is no "informal rollback" path. The slice stays open with the
rollback file committed until a fresh cutover attempt produces
clean §3 verification.

## 5. Out of scope (intentionally separate slices)

* **GPP-2D-6** — auto-merge smoke: a low-risk PR auto-merges on
  green required checks; a high-risk PR still requires human /
  CODEOWNERS review. This runbook does not enable
  GitHub-native auto-merge as a side effect; the operator may
  enable "Allow auto-merge" in repo settings as part of GPP-2D-6,
  not here.
* **GPP-2D-7 / AO-GATE-9 closeout**: the `gpp_status.v1.json`
  flip from `blocked` to a closed state. Out of scope.
* **`support_widening`, `production_platform_claim_allowed`,
  `live_adapter_execution_allowed`** stay false.
* **Admin bypass authorization** — explicitly forbidden by this
  cutover; the operator must not re-enable bypass during the
  cutover or afterward without an explicit reopen of the slice.
* **External testai-hosted App check-run with the same name** —
  if one exists, it is retired / renamed in its own slice
  before §2.2.

## 6. Closing note

This runbook is the agent half of GPP-2D-5. The operator half
(actually saving the GitHub rule change in §2.5) is what makes
`ao-release-gate` required. Until that happens, GPP-2 stays
`blocked` and the autonomous lane is not yet load-bearing.
Once §3 verification is clean, GPP-2D-6 (auto-merge smoke) and
then GPP-2D-7 / AO-GATE-9 closeout become the next allowed
slices.
