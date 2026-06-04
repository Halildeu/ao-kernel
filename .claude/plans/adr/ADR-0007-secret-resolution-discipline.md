---
id: ADR-0007
title: Secret resolution discipline for V5 Epic 2 infrastructure
status: accepted
date: 2026-06-04
deciders:
  - Codex (OpenAI)
  - Claude (Anthropic)
retrospective: false
review_status: original
slice_ref: E-2-5
guard_flags:
  support_widening: false
  production_platform_claim: false
  live_adapter_execution: false
register_authority: evidence_record_only
github_write_authorized: false
---

# ADR-0007: Secret Resolution Discipline For V5 Epic 2 Infrastructure

## Context

V5 Epic 2 remains infrastructure-only. E-2-5 adds a secret discipline primitive
for future live-adapter infrastructure without authorizing live adapter
execution. The Epic 2 plan requires value-based taint tracking as the primary
control and regex redaction only as defense-in-depth.

Legacy secret resolver surfaces still exist for older code paths. This ADR
records the stricter E-2-5 discipline as a new primitive rather than silently
changing legacy behavior.

## Decision

Add `ao_kernel._internal.secrets.SecretResolutionDiscipline` and
`SecretTaintSet`.

The primitive:

1. Resolves secrets from environment variables only.
2. Adds every resolved value to an in-memory taint set immediately.
3. Redacts serialized payloads by resolved value before JSON, JSONL, and log
   output.
4. Applies regex redaction as defense-in-depth for secret-shaped values that
   were not resolved through the primitive.
5. Fails closed when required env-only resolution is missing.
6. Provides provider invalidation for rotation so taints can be cleared for a
   rotated provider.
7. Does not import or call vault providers, MCP parameter resolution, argv,
   stdin, files, or HTTP headers.

## Consequences

- Future live-adapter infrastructure can prove that resolved secret values do
  not appear in serialized envelopes, audit rows, log lines, or telemetry
  payloads.
- Regex-only redaction is not treated as sufficient authority; it is a backup
  layer.
- Existing dual-read API-key resolver behavior is preserved for legacy callers.
  Adoption of E-2-5 is explicit.

## Non-Goals

- No live LLM/provider HTTP call.
- No `live_adapter_execution`, `support_widening`, or
  `production_platform_claim` flip.
- No workflow or branch-protection mutation.
- No vault/runtime secret provider migration for existing callers.

## References

- `.claude/plans/EPIC-2-LIVE-ADAPTER-EXECUTION.md` §2 E-2-5
- `ao_kernel._internal.secrets.discipline`
- `ao_kernel._internal.secrets.taint`
- `tests/test_secret_discipline.py`
