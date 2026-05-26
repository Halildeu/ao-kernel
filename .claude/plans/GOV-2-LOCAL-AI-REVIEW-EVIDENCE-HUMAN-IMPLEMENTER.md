# GOV-2 — Local AI Review Evidence Schema: Human Implementer Extension

**Status:** ready for PR / no support widening
**Branch:** `codex/local-ai-review-evidence-human-implementer-extension`
**Decision artifact:** `local_ai_review_evidence_schema_human_implementer_extension`
**Support impact:** none in this slice

## Purpose

This governance slice extends the `local-ai-review-evidence.v1` schema so a
PR whose implementer is a **human contributor** (not an AI) can still produce
a reviewer-evidence file the `local_gpp_gate.py` accepts, without weakening
the cross-AI peer review HARD RULE.

The pre-extension schema required `implementer.provider` to be one of
`[anthropic, openai, google, xai]`. A PR authored by a human therefore had
**no valid evidence shape**, and the `ao-release-gate` required check blocked
its merge regardless of intent. The change fixes that gap with a strict,
backward-compatible discriminator.

## Authority

GPP-9 is closed under
`gpp9_keep_narrow_stable_runtime_authoritative_program_closed_no_live_adapter_execution_no_support_widening_no_production_claim`.
This slice does **not** flip those guard flags:

- `support_widening_allowed=false`
- `production_platform_claim_allowed=false`
- `live_adapter_execution_allowed=false`

## Cross-AI istişare

Codex thread `019e649c-e36e-7643-bff8-ba493bcdab5d` plan-time iter:

> Tercihim **A**. Kök sorun PR #638 değil, governance modelinin "implementer
> = AI" varsayımı. (...) Doğru sıra: önce küçük governance migration PR'ı,
> sonra PR #638 için fresh, PR-bound evidence. (...) **B** salt
> author/attribution değiştirmekse fake work'tür. (...) **C** önermem.
> Required-check otoritesini delik açar.

Verdict: AGREE for Option A; iskelet provided.

## Schema Change

`ao_kernel/defaults/schemas/local-ai-review-evidence.schema.v1.json` —
`implementer` was previously `$ref: #/$defs/identity` (single AI shape). It is
now `$ref: #/$defs/implementer`, a `oneOf` discriminator:

| Shape | required | provider | kind |
|---|---|---|---|
| AI (legacy / default) | `agent`, `provider` | required, AI enum | optional, must be `"ai"` if present |
| Human (new) | `agent`, `kind` | **forbidden** (`additionalProperties: false`) | required, const `"human"` |

The existing `$defs/identity` is kept verbatim for backward inspection by any
other consumer; the schema's runtime contract is delegated through the new
`$defs/implementer` discriminator.

Reviewer schema is **unchanged**: a reviewer must still declare an AI
`provider` from the registered enum plus an `AGREE` verdict for the gate to
emit `operator_may_merge`.

## Gate Logic Change

`scripts/local_gpp_gate.py::_evaluate_cross_provider`:

| Implementer shape | Cross-provider rule |
|---|---|
| AI (legacy / explicit `kind="ai"`) | `implementer.provider != reviewer.provider`; same-provider fails closed. Unchanged from prior behavior. |
| Human (`kind="human"`) | Reviewer must be a valid AI from the registered set; cross-provider is satisfied automatically because a human is not an AI provider. An unknown or missing reviewer provider fails closed. |

Malformed implementer / reviewer block remains a structural fail-closed.

## Test Coverage

`tests/test_local_gpp_gate.py` adds four scenarios plus one new fixture
(`tests/fixtures/local_gpp_gate/reviewer_agree_human_implementer.v1.json`):

1. `test_human_implementer_with_ai_reviewer_passes_cross_provider` — the
   happy path: human implementer + AI reviewer → `operator_may_merge`,
   `cross_provider_verified=True`.
2. `test_human_implementer_with_invalid_reviewer_provider_schema_rejects`
   — invalid reviewer provider is rejected by the reviewer schema; gate
   treats the file as schema-invalid and fails closed.
3. `test_ai_implementer_explicit_kind_ai_remains_backward_compatible` —
   the AI discriminator label may be added without breaking legacy
   evidence; an opted-in operator stays valid.
4. `test_human_implementer_with_provider_field_schema_rejects` — the
   schema enforces `additionalProperties: false` on the human shape;
   adding `provider` to a human implementer is rejected structurally and
   the gate fails closed.

The pre-existing 52 cases continue to pass (AI legacy compatibility is
covered by `test_reviewer_agree_with_passing_checks_succeeds` and several
neighbours). Total: 56 passed.

## Forbidden Actions

This slice does NOT:

- mutate `.claude/plans/gpp_status.v1.json`
- mutate `scripts/gp5_platform_claim_decision.py`
- mutate `ao_kernel/defaults/policies/`
- mutate `.github/workflows/`
- mutate branch protection / required-check ruleset
- change any `ao_kernel/` public SDK signature
- promote any tier, widen support, claim production platform readiness, or
  execute a live adapter
- weaken the cross-AI peer review HARD RULE — the reviewer is still required
  to be a registered AI provider distinct from the implementer's category

## Downstream Effect

After this slice merges, `PR #638` (`fix/ci-runners-python-executable`, author
halildeu, human) can publish a PR-specific
`local-ai-review-evidence.v1.json` with `implementer.kind="human"` and an
AGREE reviewer from any of the registered AI providers, and the
`ao-release-gate` `review_evidence` / `review_evidence_context_bound` checks
will pass.
