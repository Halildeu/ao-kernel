# AO-MA-10j - Required-Check High-Risk Supersession Wiring

**Status:** implementation slice
**Date:** 2026-05-28
**Parent:** AO-MA-10 high-risk autonomous merge path
**Predecessor:** AO-MA-10i decision-core support for high-risk supersession evidence
**Support impact:** none
**Production platform claim:** false
**Live adapter execution:** false

## Purpose

AO-MA-10j connects the AO-MA-10i decision-core capability to the real
`ao-release-gate` GitHub Actions required-check path.

The key transition is:

```text
decision core can validate supersession evidence
  -> required-check workflow can produce and pass that evidence
```

This slice does **not** activate a merge bot, mutate branch protection, mutate
CODEOWNERS, use testai/smee, or claim production readiness.

## Runtime Evidence Model

The high-risk supersession artifact contains `head_sha`, `diff_digest`, and
`high_risk_changed_paths`. Committing that artifact directly to the PR head
would re-open the same head-SHA self-reference problem that GPP-2D-3c solved for
`local-gpp-gate-evidence.v1.json`.

Therefore AO-MA-10j uses this model:

```text
PR head commits raw reviewer evidence only
  ao-ma-10-high-risk-reviews/openai.local-ai-review-evidence.v1.json
  ao-ma-10-high-risk-reviews/anthropic.local-ai-review-evidence.v1.json

trusted base workflow resolves live base/head/diff
  -> scripts/ao_ma10_high_risk_supersession_evidence.py
  -> base/high-risk-supersession-evidence.v1.json
  -> scripts/ao_release_gate_decision.py --high-risk-supersession-evidence ...
```

The raw reviewer files use the existing `local-ai-review-evidence.v1` schema and
carry no `head_sha`. The generated artifact is uploaded as audit evidence.

## Acceptance Criteria

AO-MA-10j is accepted when:

1. `ao-release-gate` workflow locates both raw OpenAI and Anthropic reviewer
   files under the exact `ao-ma-10-high-risk-reviews/` folder.
2. A partial raw-review pair fails closed before decision evaluation.
3. Trusted-base code generates `high-risk-supersession-evidence.v1.json` at CI
   runtime using the live PR base/head/diff.
4. The decision invocation passes the generated artifact through
   `--high-risk-supersession-evidence` when present.
5. The workflow never reads `head/local-gpp-gate-evidence.v1.json` or
   `head/ao-ma-10-high-risk-supersession-evidence.v1.json`.
6. The payload builder allows raw high-risk review evidence paths but does not
   allow a committed root high-risk supersession artifact.
7. Targeted tests prove positive generation and fail-closed provider/scope
   mismatch cases.

## Roadmap After This Slice

| Slice | Purpose | Status |
|---|---|---|
| AO-MA-10h | Evidence contract | Done |
| AO-MA-10i | Decision-core validator/runtime support | Done |
| AO-MA-10j | Required-check workflow wiring | This slice |
| AO-MA-10k | Disposable real-PR smoke: positive + negative high-risk paths | Next |
| AO-MA-10l | Low-risk end-to-end auto-merge smoke / merge actor hardening | Later |

## Hard Stops

- No branch protection/ruleset/CODEOWNERS mutation.
- No admin bypass.
- No support widening.
- No production platform claim.
- No live adapter execution.
- No testai, smee, webhook, Vault, Cloud Run, or GitHub App private-key work.
