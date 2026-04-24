# SM-4 — Historical Beta Pin Wording

**Status:** Completed
**Date:** 2026-04-24
**Tracker:** [#384](https://github.com/Halildeu/ao-kernel/issues/384)
**Parent context:** `SM-1` stable maintenance baseline + `SM-3` status
truth cleanup

## Purpose

Operator-facing upgrade and rollback docs still showed the `4.0.0b2` Public
Beta pin. The pin is intentionally retained for historical pre-release testing
and rollback, but it must not read like the normal active install path now that
`4.0.0` is the stable channel.

## Boundary

This cleanup is docs/status only.

1. No runtime behavior change.
2. No support boundary widening.
3. No version bump, tag, or publish.
4. No removal of historical beta install information.

## Drift Fixed

1. Upgrade guidance now labels `4.0.0b2` as a historical Public Beta
   pre-release pin, not a normal active beta channel.
2. Rollback guidance now labels the beta rollback path as historical
   pre-release rollback.
3. `PUBLIC-BETA.md` keeps stable `4.0.0` as the default user path and clarifies
   that pre-release installs are intentional operator choices.

## Validation

1. Historical beta pin wording search:
   `rg -n "Historical Public Beta|historical Public Beta|4.0.0b2" docs/PUBLIC-BETA.md docs/UPGRADE-NOTES.md docs/ROLLBACK.md`
2. Targeted tests:
   `python3 -m pytest -q tests/test_cli_entrypoints.py tests/test_doctor_cmd.py`
3. Diff hygiene:
   `git diff --check`

## Decision

Stable `4.0.0` remains the default user path. `4.0.0b2` remains available only
as an intentional historical pre-release pin; it does not widen support and it
does not replace the stable channel.
