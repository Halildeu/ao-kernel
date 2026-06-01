---
id: ADR-0002
title: Fail-closed invariant + recompute-not-trust on every artifact boundary
status: accepted
date: 2026-05-30
deciders:
  - Claude (Anthropic)
  - Codex (OpenAI; threads 019e7d6d, 019e7e2b, 019e7fce, 019e8028)
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

# ADR-0002: Fail-closed invariant + recompute-not-trust on every artifact boundary

## Context

Across multiple AO-MA slice reviews, Codex repeatedly surfaced the same class
of weakness: a verifier or downstream consumer trusted a flag (`valid=true`,
`all_passed=true`, `slice_passed=true`) that the producer had set, without
re-deriving the flag from the underlying totals or cross-artifact state.
Each time, an attacker (or a buggy producer) could ship a forged flag and
the gate would clear. The pattern was identical across the notifier
(`019e7e2b`), the run governor (`019e7d6d`), the slice evidence registers
(`019e7fce`), and the native worker importer (`019e8028`).

## Decision

Adopt **fail-closed + recompute-not-trust** as a project-wide invariant. Two
rules together:

- **Fail-closed:** governance and policy paths deny by default. Missing
  evidence → deny; missing schema field → deny; unknown action → deny;
  schema-invalid artifact → fatal (no report, no copy). Opt-in subsystems
  (session resume, telemetry) may fall back gracefully, but the gate path
  never silently passes on incomplete inputs.
- **Recompute-not-trust:** every artifact-consuming boundary re-derives the
  outcome from the artifact's own raw fields and from disk state. A
  `valid` / `all_passed` / `slice_passed` flag emitted by the producer is
  ignored by the verifier — the verifier replays the build-side checks and
  compares. A forged flag with mismatched totals or mismatched cross-bind
  is rejected.

Concretely:

- Every `verify_*_binding` function re-loads referenced artifacts from disk,
  re-computes sha256, re-checks cross-id and cross-ref chains, and rejects
  any drift before honoring the producer's status.
- Schemas pin guard flags + authority fields with `const false`; the module
  layer additionally re-asserts the same pin at runtime so a schema-only
  relaxation cannot quietly widen behavior.
- Closeout / completion records bind the SHA of every sibling artifact, and
  verification re-hashes from disk rather than trusting the recorded SHA.

## Consequences

- Verifiers grow from "schema + sha" smoke checks into full build-side
  replays; this is the right complexity bar — anything less is fail-open.
- Producers cannot lie about success: any forged `valid=true` with a `fail`
  check inside the same artifact is rejected by the verifier on the next
  read.
- All cross-artifact integrity (manifest ↔ runner ↔ task_graph ↔ assignment
  ↔ worker_result) is now a binding invariant, not a documentation claim.
- New artifact families inherit the invariant: every new schema MUST pin
  `additionalProperties: false`, every new producer MUST emit
  `_recompute_*` helpers, and every new verifier MUST re-derive the flag.

## Alternatives Considered

- **Trust the producer's flag if the artifact's schema is valid.** Rejected:
  schema validity does not imply semantic consistency; a producer can emit
  a schema-valid artifact whose flags disagree with its body.
- **Verifier-as-smoke (schema + sha + guard only).** Rejected as fail-open
  during Codex iter-2 of `019e8028`: a coherent rebound report with a
  forged semantic chain would pass.

## References

- HARD RULE — No Fake Work / No Cosmetic Operations (CLAUDE.md, 2026-04-25)
- HARD RULE — Uzun Vadeli Kalıcı Çözüm Tercih Edilir (CLAUDE.md, 2026-05-27)
- Codex iter chains: 019e7d6d (run_governor), 019e7e2b (notifier), 019e7fce (slice registers), 019e8028 (native_worker_import)
- PR #762 / #763 / #765 / #766
