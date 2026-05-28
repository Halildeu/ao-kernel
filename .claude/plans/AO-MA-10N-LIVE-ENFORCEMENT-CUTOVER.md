# AO-MA-10N - Live Autonomous Merge Enforcement Cutover

**Status:** planned / blocked on PR #682 landing
**Date:** 2026-05-28
**Tracker:** https://github.com/Halildeu/ao-kernel/issues/683
**Depends on:** PR #682 (`AO-MA-10 live autonomy readiness truth`)
**Support impact:** none
**Production platform claim:** false
**Live adapter execution:** false

## Purpose

AO-MA-10N records the executable cutover path from the current documented
autonomous merge model to the live GitHub enforcement model.

It does not mutate GitHub rulesets, branch protection, CODEOWNERS, workflows,
or pull requests. It is a pre-cutover runbook and invariant record so the next
agent or operator can execute the live change without relying on chat context.

## Current Live Blockers

The live GitHub repository is not yet in the fully autonomous merge state.

The current blockers are:

1. Ruleset `16803733` does not require the release-authority check set.
2. The required release-authority check set must be both:
   - `ao-release-gate-technical`
   - `ao-release-gate-review`
3. Both required checks must be source-pinned to GitHub Actions integration id
   `15368`.
4. The ruleset bypass list must remain exactly `[]`.
5. Native GitHub review / CODEOWNERS must not block the low-risk autonomous
   lane.
6. A merge actor model must be recorded and proven:
   - preferred: non-admin merge-agent identity;
   - fallback: explicit direct-mode supersession if an admin actor remains the
     executor.

## Authority Boundary

AI output is evidence, not release authority.

Release authority is:

```text
ao-release-gate-technical + ao-release-gate-review + GitHub ruleset
```

The legacy compatibility wrapper named `ao-release-gate` is not sufficient by
itself for AO-MA-10 live readiness.

## Required Sequence

### 1. PR #682 must land first

PR #682 updates the repo truth model so AO-MA-10A0/A1 become the current live
readiness authority. No live enforcement mutation should happen before #682 is
merged, unless a new supersession record explicitly says otherwise.

### 2. Capture a pre-change live snapshot

Before changing GitHub settings, collect and attach read-only evidence:

```bash
python3 scripts/ao_ma10_github_readiness_snapshot.py \
  --repository Halildeu/ao-kernel \
  --branch main \
  --output /tmp/ao-ma10-readiness-before-cutover.json
```

Expected pre-change blockers:

- `ao_release_gate_required_check_missing`
- `legacy_required_review_blocks_low_risk_autonomy`
- `merge_actor_admin_permission_observed` unless a non-admin merge identity is
  already active.

### 3. Apply the live GitHub enforcement change

The desired live state is:

```text
ruleset 16803733:
  bypass_actors: []
  required status checks:
    - context: ao-release-gate-technical
      integration_id: 15368
    - context: ao-release-gate-review
      integration_id: 15368
```

Classic CI requirements must remain intact:

- `lint`
- `test (3.11)`
- `test (3.12)`
- `test (3.13)`
- `coverage`
- `typecheck`
- `packaging-smoke`

Low-risk autonomy also requires retiring or narrowing native human-review
requirements so a low-risk PR is not stopped by `required_approving_review_count
= 1` or broad CODEOWNERS ownership.

### 4. CC-9 supersession gap

`PROGRAM-CHANGE-CONTROL.md` CC-9 currently says branch ruleset mutation is
operator-only and forbids agents from mutating branch protection or rulesets.

Therefore there are two valid execution modes:

1. **Operator-bootstrap mode:** the operator applies the one-time GitHub
   settings change; agents verify and then run autonomous merge smoke.
2. **Full no-human bootstrap mode:** a separate supersession PR updates CC-9 to
   allow a constrained merge-admin agent to apply only this exact change via a
   deterministic script with pre/post snapshots, source-pin checks, and
   `bypass_actors=[]`.

Until one of these modes is completed, full no-human autonomy is not proven.

### 5. Post-change snapshot

After the GitHub settings change, collect a second read-only snapshot:

```bash
python3 scripts/ao_ma10_github_readiness_snapshot.py \
  --repository Halildeu/ao-kernel \
  --branch main \
  --output /tmp/ao-ma10-readiness-after-cutover.json
```

Acceptance:

- `rulesets.ao_release_gate_required_check_present == true`
- `rulesets.ao_release_gate_source_pinned_to_actions == true`
- `rulesets.bypass_actors_empty == true`
- legacy native review no longer blocks low-risk autonomy
- guard flags remain false

### 6. High-risk smoke

Create disposable high-risk PRs to prove the review gate behavior:

- positive path: valid OpenAI + Anthropic AGREE evidence causes
  `ao-release-gate-review` success;
- negative path: missing, stale, same-provider, or REVISE evidence causes
  `ao-release-gate-review` failure or blocked state.

### 7. Low-risk direct merge smoke

Create a disposable low-risk PR.

Acceptance:

- no native human review is required;
- classic CI passes;
- `ao-release-gate-technical` passes;
- `ao-release-gate-review` passes;
- merge agent performs a normal squash merge;
- no `--admin` merge;
- no bypass actors;
- merge actor is recorded.

### 8. Activation record

Record AO-MA-10m activation after smoke:

- before/after readiness snapshots;
- PR URLs for positive and negative smoke;
- check-run URLs for both release-authority checks;
- merge actor evidence;
- final statement that this is not support widening, not a production platform
  claim, and not live adapter execution.

## Hard Stops

- No GitHub settings mutation before PR #682 lands.
- No admin bypass.
- No ruleset bypass actors.
- No removal of classic CI requirements.
- No treating Claude, Codex, MiniMax, or any model output as release authority.
- No support widening.
- No production platform claim.
- No live adapter execution.
- No testai/smee/deployment-protection callback dependency.

## Exit Criteria

AO-MA-10N is complete only when:

1. PR #682 is merged;
2. ruleset `16803733` requires both release-authority checks with
   `integration_id=15368`;
3. low-risk PRs can merge without native human review;
4. high-risk PRs fail closed unless valid cross-provider evidence is present;
5. a real low-risk direct merge smoke succeeds;
6. a real high-risk positive and negative smoke is recorded;
7. AO-MA-10m activation evidence is committed.
