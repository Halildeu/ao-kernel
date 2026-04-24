# SM-3 — Program Status Active Section Cleanup

**Status:** Completed
**Date:** 2026-04-24
**Tracker:** [#382](https://github.com/Halildeu/ao-kernel/issues/382)
**Parent context:** `SM-1` stable maintenance baseline + `SM-2` stable
baseline evidence refresh

## Purpose

The living status board already stated that there is no active gate, but
`## 5. Şimdi` still described historical `ST-2` work as active. This created
status drift: the current execution mode was stable maintenance, while an older
section could still be read as an active stable-support-boundary slice.

## Boundary

This cleanup is docs/status only.

1. No runtime behavior change.
2. No support boundary widening.
3. No version bump, tag, or publish.
4. No new promotion program.

## Drift Fixed

1. `## 5. Simdi` no longer calls `ST-2` active.
2. The current mode points to `SM-1` as the maintenance baseline.
3. `SM-2` is recorded as the latest evidence refresh.
4. Historical `ST`, `PB`, and `GP` records remain below as history, not active
   gates.

## Validation

1. Stale active wording search:
   `rg -n "Aktif hat artık|stable support boundary freeze active" .claude/plans/POST-BETA-CORRECTNESS-EXPANSION-STATUS.md`
   returns no stale matches.
2. Targeted tests:
   `python3 -m pytest -q tests/test_cli_entrypoints.py tests/test_doctor_cmd.py`
3. Diff hygiene:
   `git diff --check`

## Decision

Stable maintenance remains the default execution mode. Support widening still
requires a separate promotion issue, decision record, implementation PR, and
evidence package.
