---
id: ADR-0004
title: Cross-AI peer review HARD RULE — implementer provider ≠ reviewer provider
status: accepted
date: 2026-05-14
deciders:
  - Operator (gladyatore@hotmail.com)
  - Claude (Anthropic)
  - Codex (OpenAI)
retrospective: true
review_status: back_populated_pending_cross_ai_revalidation
back_populated_at: 2026-06-01T03:00:00Z
slice_ref: AO-MA-11G-1
guard_flags:
  support_widening: false
  production_platform_claim: false
  live_adapter_execution: false
register_authority: evidence_record_only
github_write_authorized: false
---

# ADR-0004: Cross-AI peer review HARD RULE — implementer provider ≠ reviewer provider

## Context

AO-MA slices require independent review before merge. A single-provider
review (e.g. one Claude session reviewing another Claude session's PR)
re-uses the same training distribution and the same blind spots; it
satisfies the *form* of review without producing the *adversarial*
signal that makes review useful. The operator stated this explicitly in
May 2026: "burda yalnızca aynı sağlayıcı olmamalı" — the constraint is
at the **provider** level, not the session / thread / subagent level.

## Decision

Cross-AI review is enforced at the **provider** level. The AI that
implemented a change MUST NOT review or approve it; review is performed
by an AI from a different provider (Anthropic vs. OpenAI vs. Google
vs. xAI vs. MiniMax). Same-provider review — even from a different
session, thread, subagent, or worktree — does not satisfy the rule.

| Implementer provider | May review | May NOT review |
|---|---|---|
| Anthropic (Claude) | Codex (OpenAI), Gemini (Google), Grok (xAI), Mavis (MiniMax) | Any other Claude session/subagent |
| OpenAI (Codex) | Claude, Gemini, Mavis | Any other Codex thread |
| Google (Gemini) | Claude, Codex, Mavis | Any other Gemini session |

Verdict → action:

- **AGREE / `ready_to_merge: true`** → normal squash merge (no admin bypass).
- **REVISE / PARTIAL** → fix iteration; resubmit to the reviewer; merge
  only after AGREE.
- **RED** → escalate to the operator with a direction question.

The PR squash message and the `local-ai-review-evidence.v1.json`
artifact carry explicit `implementer.provider` and `reviewer.provider`
fields; matching providers fail the audit and are not merged.

## Consequences

- Every AO-MA slice is reviewed by a provider with different blind
  spots; the iteration history (REVISE → absorb → REVISE → AGREE) is
  the visible trace of adversarial improvement.
- Multi-session orchestration is unaffected for *implementation* (a
  team of Claude sessions may collaborate on writing code); the
  constraint binds only the *review* role.
- Fabricated thread IDs or reviewer providers are governance violations
  per HARD RULE — No Fake Work; auditors check the cited Codex /
  Gemini / Mavis thread id against the actual MCP / API trace.

## Alternatives Considered

- **Same-provider review across different sessions.** Rejected — see
  context; same training distribution, same blind spots.
- **Human-only review.** Rejected per the operator's pre-production
  full authority + the autonomous program goal (the human approves the
  *plan*, not the code; the AI reviewer adversarially checks the code).

## References

- HARD RULE — Cross-AI Peer Review (CLAUDE.md §15)
- HARD RULE — No Fake Work (CLAUDE.md, 2026-04-25)
- `local-ai-review-evidence.schema.v1.json`
- ao_kernel/ao_release_gate.py acceptance profile (gate-side enforcement)
