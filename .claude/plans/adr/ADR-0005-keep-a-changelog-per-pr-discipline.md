---
id: ADR-0005
title: Keep-a-Changelog per-PR discipline (Unreleased entry or chore-no-changelog opt-out)
status: accepted
date: 2026-06-01
deciders:
  - Claude (Anthropic)
  - Codex (OpenAI, thread 019e8050)
  - Operator (gladyatore@hotmail.com)
retrospective: false
review_status: original
slice_ref: AO-MA-11G-1
guard_flags:
  support_widening: false
  production_platform_claim: false
  live_adapter_execution: false
register_authority: evidence_record_only
github_write_authorized: false
---

# ADR-0005: Keep-a-Changelog per-PR discipline

## Context

`CHANGELOG.md` already follows the Keep-a-Changelog v1.1.0 format with an
`[Unreleased]` section at the top. What was missing is a per-PR
**discipline rule** that says when a PR must touch the changelog and
when it may opt out. Without that rule the changelog drifts: substantive
behavior changes ship without a user-visible note, and reviewers cannot
tell at a glance whether a PR's "no changelog edit" is intentional or
an oversight.

## Decision

Every PR is one of two states:

1. **Changelog-bearing PR.** `CHANGELOG.md` appears in the PR diff *and*
   the `[Unreleased]` section gained ≥1 new bullet line under a
   canonical Keep-a-Changelog sub-section
   (`Added` / `Changed` / `Deprecated` / `Removed` / `Fixed` / `Security`).
   Heading-only edits, whitespace edits, or re-ordering existing bullets
   do not count.

2. **chore-no-changelog PR.** The PR carries an explicit
   `chore-no-changelog` label *and* a non-empty rationale (minimum 10
   characters) recorded in the PR body or via the
   `ao-kernel quality check-changelog --chore-rationale ...` flag.

A PR that satisfies neither is rejected by
`ao_kernel.orchestration.quality_profile.check_changelog_compliance`,
which produces an
`ao-ma-changelog-discipline.v1` verdict artifact (`decision: pass | fail`).

The verdict module is **pure**: it takes the base-ref and head-ref
CHANGELOG text plus the PR's changed-path list plus the chore opt-out
state, and returns a verdict. The CLI thin wrapper
(`ao-kernel quality check-changelog`) handles disk I/O and exit codes.

## Consequences

- Every substantive change becomes user-visible at release time
  without the maintainer having to remember to backfill the changelog.
- Pure chores (formatting, dependency bumps with no behavior change,
  doc-only fixes) have a sanctioned, recorded opt-out — the rationale
  itself becomes the audit trail for "why no changelog".
- Heading-only or whitespace-only edits cannot game the check; the
  parser compares the bullet-line set of `[Unreleased]` between base
  and head.
- Wiring this into CI / pre-commit so that failing PRs are *blocked*
  (not merely *checked*) is intentionally deferred to AO-MA-11G-2; this
  slice ships the decision core and the operator-runnable CLI so the
  semantic is pinned and dogfooded.

## Alternatives Considered

- **No discipline rule.** Rejected — produced the drift this ADR
  resolves.
- **Per-commit Conventional Commits enforcement only.** Rejected — does
  not produce a release-time human-readable changelog without
  additional tooling, and does not handle the "chore that needs no
  user-visible note" case cleanly.
- **Auto-generate the changelog from commit history.** Deferred — does
  not produce the operator-curated narrative tone Keep-a-Changelog
  asks for; revisit in a separate ADR if 11G-2 dogfooding shows the
  bullet-based discipline is too coarse.

## References

- `CHANGELOG.md` (existing Keep-a-Changelog v1.1.0 file)
- `ao_kernel/orchestration/quality_profile.py::check_changelog_compliance`
- `ao_kernel/defaults/schemas/ao-ma-changelog-discipline.schema.v1.json`
- Codex thread 019e8050 (CNS-20260601-002 plan-time iter-1/2)
- AO-MA-SPM master plan §Faz 7
