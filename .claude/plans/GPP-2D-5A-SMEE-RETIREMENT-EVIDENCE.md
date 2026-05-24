# GPP-2D-5A - smee / External Check-Run Collision Retirement Evidence

> Status: agent-side retirement evidence.
> Work package: GPP-2 (still blocked).
> Parent: GPP-2D-5 branch-protection cutover prerequisites.
> This slice does not mutate branch protection, rulesets, CODEOWNERS, support
> scope, production claims, or live-adapter execution.

## 1. Why this slice exists

GPP-2D-5 requires the `ao-release-gate` required status check to be
source-pinned to the GitHub Actions enforce job. The cutover runbook explicitly
stops if any non-GitHub-Actions App emits a check-run with the same
`ao-release-gate` name.

After GPP-2D-5 landed, recent PR heads still showed two `ao-release-gate`
sources:

| PR | Head SHA | Source | App ID | App slug | Conclusion |
|---|---|---|---:|---|---|
| #604 | `fd8b058064d5b34b65e8c2265256dd1192d03e98` | external GitHub App | `3800233` | `ao-release-gate` | `neutral` |
| #604 | `fd8b058064d5b34b65e8c2265256dd1192d03e98` | GitHub Actions | `15368` | `github-actions` | `success` |
| #605 | `10a24d4383515b0787e5fabcd448f0dacdcf96bd` | external GitHub App | `3800233` | `ao-release-gate` | `neutral` |
| #605 | `10a24d4383515b0787e5fabcd448f0dacdcf96bd` | GitHub Actions | `15368` | `github-actions` | `success` |

That collision is not safe for branch-protection cutover, even though GitHub
supports source-pinned checks. The non-GitHub-Actions source must stop emitting
the reserved `ao-release-gate` check-run before the operator selects the
required check.

## 2. Retired bridge

The collision was produced by the historical smee.io dry-run bridge used for
GPP-2C / AO-GATE callback evidence. The no-testai GPP-2B/GPP-2D lane no longer
uses that bridge.

On `staging-sw`, the following systemd user services were stopped and disabled:

```text
smee-policy.service
smee-release.service
```

Observed post-action state:

```text
inactive
inactive
disabled
disabled
```

The stopped services were:

```text
smee-policy.service  -> https://smee.io/hsFEyYkShQo2gCaQ -> http://127.0.0.1:18081/github/deployment-protection
smee-release.service -> https://smee.io/UKE8r5guscWMUDC -> http://127.0.0.1:18082/github/ao-release-gate
```

## 3. Verification command for the cutover operator

Before changing branch protection, run this against a recent post-retirement PR
head SHA:

```bash
gh api repos/Halildeu/ao-kernel/commits/<recent_post_retirement_pr_head>/check-runs \
  --jq '.check_runs[] | select(.name == "ao-release-gate") | {name, status, conclusion, app_id: .app.id, app_slug: .app.slug, app_name: .app.name, details_url}'
```

Acceptance:

```text
Exactly one source may emit the reserved required-check name:
app_id:   15368
app_slug: github-actions
app_name: GitHub Actions
name:     ao-release-gate
```

If `app_id=3800233` / `app_slug=ao-release-gate` appears again on a new PR after
this retirement, stop the cutover. The GitHub App webhook URL or check-run
service is still active and must be retired or renamed in its own slice.

## 4. Out of scope

- No branch-protection / ruleset mutation.
- No admin bypass.
- No CODEOWNERS narrowing.
- No auto-merge smoke.
- No GPP-2 closeout.
- No testai / smee active dependency reintroduced.
- No support widening.
- No production platform claim.
- No live adapter execution.

## 5. GPP status

GPP-2 remains `blocked` after this slice. This slice only removes the external
check-run source collision that blocked GPP-2D-5 cutover.
