---
id: ADR-0001
title: AO-MA-SPM 7-phase governed autonomous multi-AI program adoption
status: accepted
date: 2026-05-30
deciders:
  - Claude (Anthropic)
  - Codex (OpenAI, thread 019e758e)
  - Mavis (MiniMax, mvs_ba774375)
  - Operator (gladyatore@hotmail.com)
retrospective: true
review_status: cross_ai_validated
back_populated_at: 2026-06-01T03:00:00Z
slice_ref: AO-MA-11G-1
cross_ai_revalidation:
  schema_version: ao-ma-adr-cross-ai-revalidation.v1
  revalidated_at: 2026-06-02T00:00:00Z
  scope: retrospective_attestation_only
  decision_mutation: false
  reviewers:
    - provider: openai
      agent: codex
      reviewed_at: 2026-06-02T00:00:00Z
      verdict: AGREE
      rationale: "AO-MA-SPM 7-phase adoption sound: plan consensus + status SSOT + governor + notification + evidence registers + native import-only + quality profile sequencing pins the governance plane onto an explicit program; guard flags support_widening, production_platform_claim, live_adapter_execution stay false; cross-provider review + ao-release-gate model embedded per slice."
      thread_ref: "019e874f"
    - provider: anthropic
      agent: claude-opus-reviewer
      reviewed_at: 2026-06-02T00:00:00Z
      verdict: AGREE
      rationale: "The 7-phase ordering is internally coherent and Decision section anchors the operator's single intervention to the GitHub Environment review on the plan-consensus bundle (not on code merges). Consequences correctly identifies that no slice can re-open the guard flags without an explicit GPP-style operator-bound supersession; phase ordering (11A plan-consensus -> 11I run-governor -> 4.6 native import) is causally sound."
  consensus: cross_ai_validated
guard_flags:
  support_widening: false
  production_platform_claim: false
  live_adapter_execution: false
register_authority: evidence_record_only
github_write_authorized: false
---

# ADR-0001: AO-MA-SPM 7-phase governed autonomous multi-AI program adoption

## Context

The operator's stated goal is fully-autonomous multi-AI code writing with a
single human approval gate: the AIs (Claude + Codex + Mavis / MiniMax) reach
consensus on a plan; the operator approves the consented plan exactly once;
the rest (implementation, cross-AI review, CI, merge) is autonomous. ao-kernel
must be the **control plane that governs this flow**, not a generic agent
framework. The three guard flags (`support_widening`, `production_platform_claim`,
`live_adapter_execution`) must remain `false` end-to-end, and `gh` automation
must stay on the low-risk lane (no admin bypass, no branch-protection mutation).

Without an explicit program, every contributor (human or AI) had to re-derive
which capabilities ship in which order, how the operator gate fits in, and
where the boundary against support widening lives. This produced repeated
proposals that conflated worker spawn (live adapter) with worker result
import-only, and CI fixes that drifted into ungated workflow changes.

## Decision

Adopt the 7-phase **AO-MA-SPM** program with the order Codex+Mavis+Claude
agreed in their tur-4 consensus:

1. **AO-MA-11A** — Plan Consensus + single operator approval gate (`ao-ma-plan-consensus-bundle.v1`, `ao-ma-plan-approval.v1`, `plan_consensus.py`; GitHub Environment `ao-ma-plan-approval` required-reviewer).
2. **AO-MA-11E** — GitHub-native operator tracking mirror (Milestone/Issue/Projects); one-way sync ao-kernel → GH; drift checker.
3. **AO-MA-11I** — Autonomous run governor (`.ao/autonomous/PAUSE` kill-switch, budget + iteration caps, safe-stop).
4. **AO-MA-11H** — Notification + escalation (Mavis CLI chat + GitHub native; no Teams/Slack).
5. **AO-MA-11F** — Test / suggestion / update evidence registers (SHA-bound audit chain).
6. **AO-MA-4.6** — Native worker result import-only (operator/AI produces `worker_result.v1.json` externally; ao-kernel only imports + validates + provenance-binds).
7. **AO-MA-11G** — SPM quality profile hardening (ADR + ISO 25010 reference + CHANGELOG discipline).

Each phase ships as one or more slices; every slice has its own
plan-consensus consultation, cross-provider AI review (implementer provider
≠ reviewer provider), and ao-release-gate-driven autonomous merge. The
operator's only required intervention is the GitHub Environment approval on
the plan-consensus bundle once per slice.

## Consequences

- The program is now machine-readable: `.claude/plans/AO-MA-SPM-MASTER-PLAN.md`
  + `.claude/plans/ao_ma_status.v1.json` + `scripts/ao_ma_next.py` produce
  "where are we / what's next / what drifted" without human spelunking.
- Each slice is its own short-lived branch / worktree / PR; stacked PRs are
  rare. Branch hygiene (HARD RULE 2026-04-20) keeps stale state from drifting
  the consensus.
- The guard flags + the live-adapter boundary stay closed across all 7 phases
  by construction; no slice can re-open them without an explicit GPP-style
  operator-bound supersession.
- The operator now approves a **plan**, not a code change; this is one human
  decision per slice, recorded as an `ao-ma-plan-approval.v1` artifact and a
  GitHub Environment review.

## Alternatives Considered

- **Inline-merge: ad-hoc AI proposals without a phased program.** Rejected: it
  produced the drift this ADR resolves.
- **Single AI implementer with no cross-provider review.** Rejected per HARD
  RULE (Cross-AI Peer Review): same-provider review re-uses the same
  training-distribution blind spots; cross-provider review is the binding
  adversarial check.
- **Operator-merge each PR manually.** Rejected: the operator gate is on the
  *plan*, not the implementation; otherwise the autonomous loop collapses to
  manual code review.

## References

- `.claude/plans/AO-MA-SPM-MASTER-PLAN.md` (master plan)
- PR #759 (master plan adoption)
- PR #758 (AO-MA-11A-1 — plan consensus core)
- PRs #760 (11E-1), #762 (11I-1), #763 (11H-1), #765 (11F-1), #766 (4.6-1)
- Codex consultation threads: 019e758e (program tur-4), 019e765b (master plan), 019e7633 (11A-1)
- HARD RULE — Cross-AI Peer Review (CLAUDE.md §15)
- HARD RULE — Pre-Production Full Authority (CLAUDE.md, 2026-04-29)
