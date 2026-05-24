# GPP-2D-5 Verification — Negative-Path Probe (DO NOT MERGE)

> This PR is opened intentionally without committing the reviewer
> evidence file `local-ai-review-evidence.v1.json` at the repo
> root. It is the §3.3 negative-path verification for GPP-2D-5:
> the `ao-release-gate` enforce gate must produce
> `decision: deny_missing_evidence` on this PR, and the merge
> button must be blocked by the now-required ruleset.
>
> Once the verification is recorded (in
> `.claude/plans/GPP-2D-5-VERIFICATION-OUTCOMES.md`), this PR is
> **closed without merging**.

## Acceptance signals expected on this PR

* `gh pr view <this PR> --json mergeStateStatus,statusCheckRollup,reviewDecision,mergeable`:
    * `mergeStateStatus == "BLOCKED"` (or `"DIRTY"` if other signals
      are still pending — block must be present in either case).
    * `statusCheckRollup[]` includes an entry with
      `name == "ao-release-gate"` whose `conclusion == "FAILURE"`.
    * `reviewDecision` may be unset or APPROVED; the invariant we
      are pinning is "merge is blocked by ao-release-gate", not
      that no human approved.
* UI: the "Merge pull request" button is greyed with the message
  "Required statuses must pass before merging" or the ruleset
  equivalent.
* `gh pr merge <this PR> --repo Halildeu/ao-kernel --squash`
  rejected with a required-status-check failure (non-zero exit).

## Out of scope

* Branch protection mutation by the agent.
* Any commit that would silently merge this PR — explicit
  `--admin` is forbidden and is not used here.
