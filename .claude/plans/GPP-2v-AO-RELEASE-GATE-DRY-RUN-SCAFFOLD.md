# GPP-2v - ao-release-gate Dry-Run Scaffold

**Status:** closeout candidate
**Date:** 2026-04-28
**Issue:** [#539](https://github.com/Halildeu/ao-kernel/issues/539)
**Depends on:** [#538](https://github.com/Halildeu/ao-kernel/pull/538)
**Branch:** `codex/gpp-2v-release-gate-dry-run`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gpp-2v-release-gate-dry-run`
**Decision:** `ao_release_gate_dry_run_scaffold_ready_no_support_widening`

## Context

GPP-2u selected `ao-release-gate`, a GitHub App release gate with a required
status check/check-run, as the durable model for no-human-approval program PR
merges. That decision intentionally left implementation and branch-protection
cutover for later slices.

This slice implements the first repo-owned, side-effect-free evaluator that a
future `ao-release-gate` GitHub App can call before posting a check-run. It
does not create the GitHub App, does not post to GitHub, does not change branch
protection, and does not grant merge authority.

## Added Surface

1. `ao_kernel/ao_release_gate.py`
   - Evaluates a PR-shaped release-gate payload and GPP status.
   - Produces a deterministic dry-run decision artifact.
   - Builds a future GitHub check-run shape named `ao-release-gate`.
   - Keeps `merge_authority_enabled=false`.
2. `scripts/ao_release_gate_decision.py`
   - CLI wrapper for local/dry-run artifact generation.
   - Supports `--fail-on-deny` for future CI or App adapter wiring.
3. `tests/test_ao_release_gate.py`
   - Covers allow, stale branch, untrusted fork, missing CI evidence, admin
     bypass, GPP issue mismatch, render/write, and CLI paths.

## Policy Behavior

The evaluator allows only when all required evidence is present:

1. Repository is `Halildeu/ao-kernel`.
2. Base branch is `main`.
3. PR number and head SHA are present.
4. Work-package issue URL is present and matches current GPP status.
5. Branch freshness is explicitly `true`.
6. PR is not from a fork.
7. Event is not `pull_request_target`.
8. Supplied required checks are completed with `success`.
9. Changed paths are inside an explicit work-package allowlist.
10. GPP status keeps support widening, production platform claim, and live
    adapter execution closed.
11. Forbidden secret context, admin bypass, PAT-backed bot actor,
    Codex/Claude release authority, and live adapter execution are explicitly
    false.

Terminal decisions:

1. `allow_autonomous_merge`
2. `deny_policy_violation`
3. `deny_missing_evidence`
4. `deny_stale_branch`
5. `deny_untrusted_context`
6. `error_fail_closed`

The dry-run check-run conclusion is `success` only for
`allow_autonomous_merge`; all deny/error decisions produce `failure`.

## Non-Goals

1. No GitHub App registration or private key handling.
2. No webhook endpoint.
3. No check-run POST to GitHub.
4. No branch protection/ruleset change.
5. No PR auto-merge.
6. No admin bypass.
7. No PAT-backed bot.
8. No Claude/Codex release authority.
9. No live adapter execution.
10. No support widening or production platform claim.

## Remaining Blockers

GPP-2 remains blocked because:

1. `ao-release-gate` is not yet installed as a GitHub App.
2. The dry-run evaluator is not yet wired to a webhook/check-run posting path.
3. Branch protection/rulesets do not yet require `ao-release-gate`.
4. The deployment-protection policy service is still not publicly hosted or
   configured with webhook URL, webhook secret, and GitHub App auth.

## Validation

```bash
python3 -m ruff check ao_kernel/ao_release_gate.py scripts/ao_release_gate_decision.py tests/test_ao_release_gate.py
pytest -q tests/test_ao_release_gate.py
pytest -q tests/test_gpp_next.py
python3 -m json.tool .claude/plans/gpp_status.v1.json
python3 scripts/gpp_next.py
git diff --check
```

## Closeout

`ao-release-gate` now has a repo-owned dry-run decision core and CLI artifact
surface. This is implementation readiness only. It does not unblock GPP-2, does
not authorize human-free merges yet, does not widen support, and does not
permit production platform claims or live adapter execution.
