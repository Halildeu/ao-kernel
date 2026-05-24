# Rollback and Recovery Runbook

> **Status:** active operational runbook (GOV-1)
> **Scope:** General-Purpose Production Promotion program + protected gate +
> ao-release-gate + GitHub branch ruleset + repo-owned services
> **Authority:** `origin/main` + operator (Halildeu) for ruleset / repo settings
> **Last reviewed:** 2026-05-25

## Purpose

This runbook documents failure-mode-based recovery procedures. It is not a
deployment script — it is a reference of "what to do if X breaks" with each
scenario carrying a clear trigger, owner, forbidden action set, recovery
steps, evidence to attach, and the kind of supersession PR that closes the
incident.

## General Recovery Principles

1. **No destructive history rewrite.** `git push --force` against `main` or
   any protected branch is forbidden. Recover via archive tag and forward PR.
2. **Archive tag preservation.** Every merged PR has an annotated tag
   `archive/YYYY/MM/<branch>-pr<N>` pushed to the remote; recovery starts from
   there.
3. **Operator authority is preserved.** Ruleset / branch protection / repo
   settings changes are operator-only via the GitHub UI. Agents do not call
   `gh api` against these surfaces, even during recovery.
4. **Supersession over reversal.** A bad decision is closed via a new
   decision record that supersedes it; original records stay as audit trace.
5. **Evidence before action.** Capture the failing state (logs, ruleset API
   replay, CI conclusion, decision string) before mutating anything.

## Cross-Machine Recovery

```bash
git fetch --tags origin
git tag --list 'archive/*' | grep <pr-number-or-branch-fragment>
git checkout -b recovery/<issue-or-pr> archive/YYYY/MM/<branch>-pr<N>
```

This works on a fresh clone or a new laptop. The archive tag is the durable
recovery handle for 1+ year horizons; reflog-only recovery is not relied on.

---

## Scenario A — Ruleset / Branch Protection Operator Error

**Trigger:** The "Protect main" ruleset (id `16803733`) is accidentally
modified (e.g. `bypass_actors` populated, `ao-release-gate` removed from
required checks, `block_force_pushes` disabled), or the legacy main branch
protection is mis-edited.

**Owner:** Operator (`Halildeu`, repo owner / admin).

**Forbidden:**
- Agent calls to `gh api repos/Halildeu/ao-kernel/rulesets/*`.
- Agent calls to `gh api repos/Halildeu/ao-kernel/branches/main/protection`.
- Admin bypass merges to "fix it forward".

**Steps:**

1. Capture the current API state for both ruleset + legacy protection (agent
   may read these; only the operator writes).
   ```bash
   gh api repos/Halildeu/ao-kernel/rulesets/16803733 > /tmp/ruleset-before.json
   gh api repos/Halildeu/ao-kernel/branches/main/protection > /tmp/protection-before.json
   ```
2. Operator opens GitHub UI → Settings → Rules → "Protect main" → reverts
   the bad field to the documented value:
    - `Required status checks`: `ao-release-gate` (source-pinned via
      GitHub Actions `integration_id 15368`)
    - `Bypass actors`: empty
    - `Strict required status checks`: enabled
    - `Block force pushes`: enabled
3. Operator pastes a structured audit comment in the relevant PR (or a new
   incident PR) that mirrors the §2.6 format from
   `.claude/plans/GPP-2D-5-CUTOVER-RUNBOOK.md`.
4. Agent verifies post-revert state.
   ```bash
   gh api repos/Halildeu/ao-kernel/rulesets/16803733 > /tmp/ruleset-after.json
   diff /tmp/ruleset-before.json /tmp/ruleset-after.json
   ```

**Evidence to attach:**
- Before / after API JSON replays
- Operator audit comment URL
- Incident timestamp (UTC)

**Supersession PR:** Opens an incident decision record under
`.claude/plans/` (e.g. `INCIDENT-YYYY-MM-DD-RULESET-DRIFT.md`) referencing the
GPP-2D-5 cutover runbook and the GPP-2D-7 closeout invariants.

---

## Scenario B — Workflow / Code Regression on `main`

**Trigger:** A merged PR introduces a runtime regression on `main` (e.g.
`ao-release-gate` enforce job miscalibrated, schema validator broken,
`local_gpp_gate.py` fails closed for valid inputs).

**Owner:** Implementer agent + cross-AI reviewer + non-author code-owner.

**Forbidden:**
- `git push --force origin main` to "undo" the bad commit.
- `git revert` on `main` without a PR.
- Re-merging the broken commit via `--admin` bypass.

**Steps:**

1. Capture failing-state evidence (CI logs, pytest output, runtime trace).
2. Open a fresh `codex/<incident-id>-rollback` branch from current
   `origin/main`.
3. Either:
    - **Forward fix**: write a fix commit on the new branch, run pytest,
      ensure `ao-release-gate` passes;
    - **Targeted revert**: `git revert <bad-commit>` on the new branch (this
      creates a forward-only revert commit, not a history rewrite).
4. Open PR → cross-AI review (Codex/Claude opposite of implementer) →
   non-author code-owner approval → CI green → squash merge.
5. Run `ai-post-merge-cleanup.sh` to push the archive tag for the fix.

**Evidence to attach:**
- Pre-fix failing CI run URL
- Post-fix passing CI run URL
- Reviewer evidence JSON
- Decision record naming the regression + cause

**Supersession PR:** The fix / revert PR is itself the closeout artifact.
If the regression came from a closed slice, an addendum decision record is
opened.

---

## Scenario C — Cross-Machine / Laptop Failure Recovery

**Trigger:** Operator switches machines, loses local clone, or needs to
recover work from before a session.

**Owner:** Operator + agent.

**Forbidden:**
- Restoring local-only branches without remote backing (rely on `archive/*`
  tags pushed to origin).
- Treating reflog as the primary recovery surface (90-day TTL is too short).

**Steps:**

1. Fresh clone on the new machine.
   ```bash
   git clone https://github.com/Halildeu/ao-kernel.git
   cd ao-kernel
   ```
2. Fetch all tags.
   ```bash
   git fetch --tags origin
   ```
3. List archive tags by date / PR.
   ```bash
   git tag --list 'archive/*' | sort
   ```
4. Check out a specific historical state.
   ```bash
   git checkout -b recovery/inspect-pr611 archive/2026/05/codex-gpp2d-7-ao-gate-9-closeout-pr611
   ```
5. Inspect or re-export work; cherry-pick onto current `main` via a normal
   PR if forward recovery is needed.

**Evidence to attach:**
- Archive tag SHA
- `git log --oneline` on the recovery branch
- New PR (if forward recovery is opened)

**Supersession PR:** None required for read-only recovery; only the
forward-recovery PR if state must be replayed onto current `main`.

---

## Scenario D — Closeout Reversal (e.g. GPP-2 Reopen)

**Trigger:** A closed slice (e.g. GPP-2, GPP-5d) needs to be reopened because
new evidence supersedes the closeout decision (e.g. discovery that
`ao-release-gate` ruleset binding was insufficient).

**Owner:** Operator (strategic decision) + implementer agent + cross-AI
reviewer.

**Forbidden:**
- Editing the existing closeout record to reverse its meaning.
- Removing the closeout entry from `gpp_status.v1.json` `completed_wps` or
  `current_wp.closeout_at`.
- Force-pushing `main` to "back out" the original closeout commit.

**Steps:**

1. Open a new decision record `.claude/plans/<SLICE>-REOPEN-DECISION.md` that:
    - Names the superseded closeout (e.g. "Supersedes
      `GPP-2D-7-AO-GATE-9-GPP-CLOSEOUT.md` as of `YYYY-MM-DD`");
    - Records the trigger evidence (new requirement, discovered drift,
      compliance update);
    - Defines the new `current_wp` shape and new `ready_after` cluster.
2. Open a PR that:
    - Adds the new decision record;
    - Updates `gpp_status.v1.json` to move the affected slot from `closed`
      back to a defined `reopened` state (or migrates `current_wp` to the
      new active wp);
    - Updates the `milestones[]` entry to `status: "reopened"` + reason;
    - Updates STATUS.md §0 and the relevant section to reflect the new
      state.
3. Cross-AI review + non-author approval + CI green + squash merge.

**Evidence to attach:**
- Original closeout record path (preserved unchanged)
- New decision record
- Reviewer evidence
- Closeout supersession audit comment

**Supersession PR:** This PR is itself the supersession; no separate
addendum is required.

---

## Scenario E — Live Execution Mishap / Incident Freeze

**Trigger:** A live adapter execution slice (e.g. GPP-3 Phase 3 Option X)
unexpectedly runs against a non-disposable target, leaks a secret, or
produces an unintended write to a production-like surface.

**Owner:** Operator + agent + non-author reviewer; if secret leak,
also any external security contact named in `docs/SUPPORT-BOUNDARY.md`.

**Forbidden:**
- Hiding the incident (e.g. force-deleting a branch, deleting logs).
- Continuing other slices in parallel during the freeze.
- Setting `live_adapter_execution_allowed` back to `false` without an
  incident record (the flag flip is itself evidence).

**Steps:**

1. **Freeze.** Stop all in-flight slices that depend on live adapter or
   secret material. Tag the current `main` SHA as
   `incident/YYYY-MM-DD-<slug>-frozen`.
2. **Capture.** Collect:
    - All workflow run logs touching the incident.
    - Secret rotation timeline (which secrets, when rotated).
    - Affected artifact paths.
    - Operator + agent action timeline (UTC).
3. **Revert live flag.** Operator opens a PR that flips
   `live_adapter_execution_allowed` back to `false` in `gpp_status.v1.json`,
   updates the closeout record of the offending slice with an `## Incident`
   section, and tightens any forbidden-action lines that the incident
   exposed.
4. **Rotate.** Any secret material that may have been exposed is rotated by
   the operator (vault, GitHub App private key, webhook secret); the rotation
   is recorded in a no-secret-value attestation file.
5. **Retrospective.** A retrospective using
   `.claude/plans/_TEMPLATES/RETROSPECTIVE-TEMPLATE.md` is filled out and
   committed alongside the incident decision record.

**Evidence to attach:**
- Incident freeze tag
- Workflow run URLs
- Operator + agent timeline
- Secret rotation attestation
- Filled retrospective

**Supersession PR:** Incident decision record + tightened
`forbidden_actions` + flag flip back to `false` constitute the supersession.
Re-enabling live execution requires a brand-new slice with a new exit
decision and cross-AI review.

---

## What This Runbook Does NOT Cover

- **Vendor / cloud outage** (GitHub Actions runner unavailability, npm
  registry outage). Treat external outage as a wait-and-retry signal; the
  branch ruleset is configured to require a green required check, which
  naturally pauses merges until the external service returns.
- **Operator credential loss** (lost GitHub admin password, lost vault
  token). This is out of scope for the program and is handled by the
  operator's own account-recovery process.
- **Repo-wide compromise** (e.g. unauthorized push that bypassed all gates).
  This requires a separate security incident response coordinated by the
  operator with GitHub support.

## Cross-References

- `.claude/plans/PROGRAM-CHANGE-CONTROL.md` — change-control rules
- `.claude/plans/GPP-2D-5-CUTOVER-RUNBOOK.md` — operator cutover §2.6 audit format
- `.claude/plans/GPP-2D-7-AO-GATE-9-GPP-CLOSEOUT.md` — current closeout invariants
- `~/.claude/scripts/ai-post-merge-cleanup.sh` — archive tag emission
- `~/.claude/logs/git-cleanup.log` — host-wide audit log
- `AGENTS.md` — agent startup contract
