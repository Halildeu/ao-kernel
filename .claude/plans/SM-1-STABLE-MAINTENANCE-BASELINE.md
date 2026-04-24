# SM-1 — Stable Maintenance Baseline

**Status:** Completed
**Date:** 2026-04-24
**Tracker:** [#378](https://github.com/Halildeu/ao-kernel/issues/378)
**Parent context:** `GP-2` closeout and `v4.0.0` stable live baseline

## Purpose

Define the default operating mode after `GP-2` closed without stable support
widening.

This is not a runtime implementation tranche. It is the maintenance baseline
that prevents the next work from silently reopening support widening,
promotion, or production-platform claims without a new explicit program.

## Current Stable Baseline

1. `v4.0.0` is the live stable package.
2. The shipped support boundary remains narrow.
3. `review_ai_flow + codex-stub`, entrypoints, doctor, packaging smoke, policy
   command enforcement, and documented read-only kernel API actions are the
   stable supported surface.
4. `claude-code-cli`, `gh-cli-pr`, kernel API write-side actions, and
   real-adapter benchmark full mode remain Beta/operator-managed.
5. `bug_fix_flow` release closure, full remote PR opening, roadmap/spec demo,
   and adapter-path `cost_usd` public support claim remain Deferred.
6. There is no active support-widening runtime gate.

## Maintenance Rules

Stable maintenance work is allowed when it fits one of these categories:

1. bugfix for shipped stable baseline;
2. docs/runtime/test parity correction;
3. CI, packaging, release, or rollback gate hygiene;
4. known-bug registry update;
5. operator runbook clarification;
6. evidence hygiene that does not widen support.

Stable maintenance work must not:

1. promote Beta or Deferred lanes;
2. reinterpret a one-off smoke as production support;
3. open live-write behavior against production repositories;
4. claim general-purpose production coding automation platform readiness;
5. bundle multiple support-widening lanes into one PR.

## Promotion Protocol

Any future support widening must open a new promotion program, likely `GP-3`,
with:

1. one lane only;
2. one tracker issue;
3. one decision record;
4. explicit support-boundary delta;
5. repeatable positive and negative evidence;
6. docs/runtime/tests/CI parity;
7. rollback/incident path when write-side or remote side effects are involved.

No lane may be promoted by editing docs alone.

## Drift Fixed In This Slice

`docs/SUPPORT-BOUNDARY.md`, `docs/OPERATIONS-RUNBOOK.md`, and
`docs/UPGRADE-NOTES.md` described the `gh-cli-pr` live-write probe in some
operator prerequisite text without showing the explicit `--repo
<owner>/<sandbox-repo>` guard. `SM-1` aligns those examples and prerequisite
sentences with the actual helper contract.

## Validation

Minimum validation for this maintenance baseline:

```bash
python3 scripts/truth_inventory_ratchet.py --output json
python3 -m pytest -q tests/test_cli_entrypoints.py tests/test_doctor_cmd.py
git diff --check
```

## Exit Criteria

1. This decision record is merged.
2. Program status references `SM-1` as the current maintenance baseline.
3. Production roadmap says the default path is stable maintenance.
4. Operator-facing docs no longer omit the explicit sandbox repo parameter from
   live-write prerequisite prose.
5. Issue [#378](https://github.com/Halildeu/ao-kernel/issues/378) is closed.
