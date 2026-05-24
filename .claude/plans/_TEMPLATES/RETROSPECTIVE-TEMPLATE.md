# Retrospective — `<SLICE-ID>` (`<short-description>`)

> **Status:** retrospective record (per `PROGRAM-CHANGE-CONTROL.md` GOV-1)
> **Slice:** `<SLICE-ID>` (e.g. GPP-3a, GPP-4-phase-2)
> **Closeout PR:** `<URL or PR #>`
> **Closeout commit:** `<merge SHA>`
> **Date:** `<YYYY-MM-DD>` (retrospective recorded date)
> **Author(s):** `<agent + operator>`

## Purpose

This template is filled out **after** a slice closes (its decision record and
SSOT updates are merged). The retrospective is a separate artifact; it never
mutates the closed decision record itself.

Format is intentionally five short answers. Aim for one paragraph or one
bullet list per section. Long retrospectives lose readability; short ones
compound into program memory.

---

## 1. What worked

> Concrete patterns, tools, or decisions that produced the expected outcome.
> Cite PRs, files, or specific decisions. Avoid generic statements like
> "everything went well".

`<answer>`

## 2. What was incomplete or superseded

> Items that were planned for this slice but ended up deferred, moved to a
> later slice, or superseded by a different approach. Name the follow-up
> slice or decision record if known.

`<answer>`

## 3. What we learned

> The specific insight that you would carry into the next slice. Often this
> is a sharper articulation of a forbidden action, an additional drift
> guard, or a refined acceptance criterion.

`<answer>`

## 4. Pattern to repeat

> A concrete pattern (cross-AI review iter chain, schema-conformant evidence,
> source-pinned required check, etc.) that should be used by future slices
> in the same area. Cite the slice / file / behavior that demonstrated it.

`<answer>`

## 5. Anti-pattern to retire

> A pattern that this slice tried, accidentally invoked, or witnessed in
> review that should be explicitly avoided going forward. If this anti-
> pattern justifies a new `forbidden_actions` line in `gpp_status.v1.json`,
> open a follow-up governance slice; otherwise document it here so future
> agents recognize and avoid it.

`<answer>`

---

## Cross-References

- `.claude/plans/<closeout-record>.md` — the closeout decision this
  retrospective accompanies
- `.claude/plans/gpp_status.v1.json` — SSOT (`completed_wps` /
  `current_wp` entry for this slice)
- `.claude/plans/PROGRAM-CHANGE-CONTROL.md` — change-control policy
- `docs/ROLLBACK-RUNBOOK.md` — recovery procedures
