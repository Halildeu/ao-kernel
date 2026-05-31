# CI-FIX — test.yml required jobs must not be event-gated (shadow-skip → blocked)

**Consultation:** CNS-20260531-001 · **Codex thread** `019e7f84` (plan ready_for_impl=true → post-impl AGREE) · **Risk:** high (`.github/` CODEOWNER-protected)

## Problem (observed live on PR #763)

`test.yml` triggers on `pull_request: types: [..., edited]`. The `event-gate`
job sets `should_run=false` for a non-retarget `edited` event. Every required
job carried `if: needs.event-gate.outputs.should_run == 'true'`, so a plain PR
body/title edit (e.g. `gh pr edit --body`) re-fires the workflow on the **same
head SHA** and those jobs **skip**. GitHub records the conclusion=skipped
check-run as the *latest* for that context, shadowing the earlier success. With
strict classic branch protection the PR flips to `mergeStateStatus=blocked` —
even though CI is **not red** (0 failures). Recurs on every edit.

Live evidence: PR #763 went `blocked` after a `gh pr edit`; `gh pr checks`
showed `test` + `typecheck` NEUTRAL (skipping) while all real runs passed. A
`workflow_dispatch` / `synchronize` re-run cleared it (and the autonomous merge
executor then merged #763) — but the bug recurs without a permanent fix.

## Fix (Codex-recommended: required = always run; only true non-required gated)

1. **Classic-required jobs ungated** — removed `needs: [event-gate]` +
   `if: should_run` from `lint`, `test`, `coverage`, `typecheck`,
   `packaging-smoke`. They always run a real gate; a required context can never
   regress success→skipped. `packaging-smoke` keeps
   `needs: [test, coverage, lint, typecheck]`.
2. **ao-release-gate ungated** — removed the `should_run` clause from its `if:`
   (now `if: always() && (pull_request || pull_request_review)`). It posts the
   ruleset-required `ao-release-gate-technical` / `-review` check-runs, so it
   must run on every PR/review event. Its `needs:` chain and the fail-closed
   `needs.*.result != 'success'` short-circuit are preserved.
3. **ao-release-gate upstream container smokes ungated** — `policy-container-smoke`
   and `release-gate-container-smoke` are `needs:` of ao-release-gate and it
   fail-closes on their non-success, so they back the required ruleset contexts
   (de-facto required). Ungated so a cosmetic edit cannot skip them and thereby
   fail-close the gate (which would turn the required ruleset contexts RED — the
   same shadow-block class). This was the post-impl REVISE blocker Codex caught.
4. **Only benchmark-fast stays event-gated** — it is the one expensive job that
   backs no required / release-gate chain, so its skip is harmless.
5. **concurrency added** — `group: test-${{ pr.number || ref }}`,
   `cancel-in-progress: true`, so a force-push / rapid edit cannot leave two
   runs racing on the same head SHA.

## Why not the alternatives (Codex verdicts)

- Drop `edited` from triggers → loses retarget re-gate.
- Make skipped jobs report success-neutral / last-known → **fail-open**
  (a not-run gate would report success); forbidden.
- Codex's plan-time "rename shadow-skip" suffix → also valid, but ungate is
  *stronger* (no skipped check-run at all) and simpler; Codex AGREEd the
  divergence.

## Fail-closed property

No `if: always()` / `continue-on-error` on any required job. A required job
either runs a real gate or does not exist for that SHA; an `edited` event is the
same SHA, so it runs. ao-release-gate keeps `always()` only so a failed upstream
still surfaces a `failure` verdict (never a silent skip). No path makes a not-run
gate report success.

## Test invariants (`tests/test_ci_required_jobs_not_event_gated.py`, 10 tests)

required NOT gated; required have no fail-open; packaging-smoke needs chain;
benchmark-fast stays gated; concurrency cancels; event-gate retarget guard
preserved; ao-release-gate not should_run-gated + always() + needs required;
ao-release-gate fail-closed short-circuit preserved (raw-text check —
yaml.safe_dump re-escapes the quotes); required contexts run on
pull_request + pull_request_review; ao-release-gate upstream container smokes
ungated + still in ao-release-gate.needs.

## Evidence

- 10/10 invariant tests pass; full suite 5018 / 0 fail (JUnit XML).
- test.yml YAML valid; no required or release-gate-chain job depends on
  event-gate (asserted); ruff clean; **no `ao_kernel/` behavior change**
  (workflow + meta-test only).
- Cross-AI: implementer Claude (Anthropic); reviewer Codex (OpenAI) thread
  `019e7f84` — plan-time ready_for_impl=true → post-impl REVISE (container-smoke
  blocker) → AGREE after the fix.

## Follow-up

After merge, any open PR will have its required contexts always reflect real
runs. Consider consolidating classic branch protection + ruleset
required-context lists into one layer (Codex side-note) — separate slice.
