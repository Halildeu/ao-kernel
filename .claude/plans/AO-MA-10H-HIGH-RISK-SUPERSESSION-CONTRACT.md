# AO-MA-10h - High-Risk Autonomous Supersession Contract

**Status:** planned / contract recorded
**Date:** 2026-05-28
**Parent:** AO-MA-10 low-risk autonomous merge lane
**Trigger evidence:** PR #676 blocked by `ao_release_gate_high_risk_human_review_missing`
**Support impact:** none
**Production platform claim:** false
**Live adapter execution:** false

## Purpose

AO-MA-10h records the contract for replacing mandatory human review on
high-risk PRs with deterministic, repo-owned validation of cross-provider AI
consensus evidence.

The immediate trigger is PR #676: a change to `ao_kernel/ao_release_gate.py`
received independent Claude review and green CI, but correctly remained blocked
because the current authority model requires a non-author/codeowner GitHub
review for high-risk paths. That proves the existing gate is fail-closed, and
also proves the system is not yet end-to-end autonomous for high-risk changes.

AO-MA-10h does **not** activate that autonomy. It records the evidence contract
and acceptance boundary for a later decision-core slice.

## Authority Model

AI output remains evidence, not release authority.

Release authority remains:

```text
ao-release-gate + GitHub branch protection/ruleset
```

The high-risk autonomous path may only satisfy `path_sensitive_human_review`
after the repo-owned `ao-release-gate` validates a strict supersession evidence
artifact. The model output itself never approves the PR. The gate approves or
denies based on deterministic schema, context binding, provider diversity,
freshness, and guard flags.

## Current Behavior

Current high-risk behavior is intentionally conservative:

```text
high-risk path touched
  -> no current non-author/codeowner approval
  -> ao-release-gate-review = action_required
  -> merge blocked
```

This remains unchanged by AO-MA-10h.

## Future Supersession Behavior

The future decision-core extension must support two satisfaction paths:

```text
path_sensitive_human_review satisfied when:
  A. current non-author/codeowner GitHub approval exists
  OR
  B. valid high-risk cross-provider supersession evidence exists
```

The supersession path is valid only when all of the following hold:

1. Required providers include `openai` and `anthropic`.
2. Provider verdicts are from distinct providers.
3. Every required provider verdict is `AGREE`.
4. The generated supersession artifact's top-level `context_binding` is
   fresh-bound to the current PR `head_sha`, `base_ref`, `diff_digest`,
   `changed_files_count`, and exact `high_risk_changed_paths`. Per-provider
   `context_binding` mirrors the top-level binding.
5. Each per-provider verdict declares its `binding_mode` against the raw
   reviewer evidence file's appearance in the current PR's diff:
   - `added` — introducer PR (file ADDED in this PR's diff). Raw evidence
     scope (`work_package`, `base_ref`, `head_ref`, `changed_files`) MUST
     match current PR strictly.
   - `modified` — file MODIFIED/TYPED/COPIED/RENAMED in this PR's diff.
     Raw evidence scope MUST match current PR strictly (prevents
     stale-rebind and PR-head tampering).
   - `unchanged` — file NOT in this PR's diff (byte-identical at base
     SHA). Raw evidence scope binding is the state-at-landing pin from
     the introducer PR's validation. Immutable properties (verdict=AGREE,
     reviewer agent independence, `secrets_recorded=false`, all guard
     flags false, required reviewer providers set, tests + secret_scan
     checks passing, no `FORBIDDEN:` finding) ARE still enforced
     perpetually. Current PR review on this PR's diff is delivered
     separately via the root `local-ai-review-evidence.v1.json` artifact
     (single reviewer, strict-bound to current PR).
6. Each raw reviewer evidence file's reviewer.provider matches the
   path-bound expected provider: `openai.local-ai-review-evidence.v1.json`
   declares provider=openai; `anthropic.local-ai-review-evidence.v1.json`
   declares provider=anthropic. (Audit provenance: prevents provider
   shuffling while the provider set remains overall correct.)
7. Evidence freshness is `fresh` and bounded by `max_age_seconds`.
8. `max_revise_rounds` is `3`.
9. If consensus is not reached after the round budget, the only allowed
   escalation is `operator_human_review_fallback`.
10. `support_widening`, `production_platform_claim`, and
    `live_adapter_execution` are all `false`.
11. `ai_output_release_authority` is `false`.
12. Secrets are not recorded.

## Fail-Closed Cases

The future runtime validator must reject supersession evidence and continue to
require human/codeowner review when any of these occur:

- missing evidence;
- malformed or schema-invalid evidence;
- same provider appears more than once;
- required provider missing;
- any required provider verdict is not `AGREE`;
- any provider context differs from top-level context;
- top-level context differs from the live PR context;
- raw reviewer evidence path is not in the allowlist
  (`ao-ma-10-high-risk-reviews/{openai,anthropic}.local-ai-review-evidence.v1.json`);
- raw reviewer evidence file `DELETED` in this PR's diff (governance break);
- `binding_mode` is `added` or `modified` and current-PR scope strict
  binding fails (work_package, base_ref, head_ref, changed_files);
- `binding_mode` is `unchanged` but any immutable property fails (verdict,
  agent independence, secrets, guard flags, required providers,
  tests/secret_scan checks, FORBIDDEN finding);
- per-provider verdict's `binding_mode` is missing or not in
  `{added, modified, unchanged}`;
- evidence is stale;
- guard flag is true;
- evidence claims AI output as release authority;
- evidence attempts workflow, CODEOWNERS, ruleset, support, production claim,
  live adapter, testai, smee, Vault, or GitHub App work.

## Bootstrap Boundary

AO-MA-10h is deliberately contract-only. It does not change the current
bootstrap problem:

- Current base code cannot consume high-risk supersession evidence yet.
- A PR that changes `ao-release-gate` remains high-risk under current base code.
- GitHub branch protection still requires non-author/codeowner review.

Therefore the first implementation PR that changes the decision core will still
need the current authority path unless a separate, explicit operator-bound
supersession changes repository protection settings.

This is not a contradiction. It is the recorded transition rule:

```text
contract first -> runtime validator -> GitHub enforcement model update -> smoke
```

## Out Of Scope

AO-MA-10h does not:

- mutate `.github/**`;
- mutate CODEOWNERS;
- mutate GitHub rulesets or branch protection;
- activate a merge agent;
- merge PR #676;
- change `gpp_status.v1.json`;
- execute live adapters;
- use testai, smee, webhooks, Vault, GitHub App private keys, or Cloud Run;
- widen support;
- claim production platform readiness.

## Slice Sequence

1. **AO-MA-10h**: contract, evidence schema, fixture, and invariants only.
2. **AO-MA-10i**: decision-core extension that accepts valid supersession
   evidence as an alternative to human/codeowner review. **Done**.
3. **AO-MA-10j**: GitHub enforcement model update. It must generate the
   head-bound supersession artifact at CI runtime from raw, head_sha-free
   reviewer evidence rather than reading a committed head-bound artifact.
4. **AO-MA-10k**: high-risk autonomous smoke with a disposable PR: success path
   and fail-closed path.
5. **AO-MA-10u**: raw high-risk review producer. It may call configured OpenAI
   and Anthropic reviewer commands and write the two raw
   `local-ai-review-evidence.v1` files under
   `ao-ma-10-high-risk-reviews/`. It does not become release authority; it only
   automates evidence production. The trusted-base supersession builder and
   `ao-release-gate` remain the authority that validate provider binding,
   context binding, no-secret posture, guard flags, and consensus.

## Acceptance Criteria

AO-MA-10h is accepted when:

- the supersession evidence schema is valid Draft 2020-12;
- the valid fixture validates;
- schema rejects same-provider, missing-provider, non-AGREE, stale evidence,
  guard flag flips, and AI-as-authority flips;
- invariant tests assert that context equality across provider verdicts is a
  runtime-validator responsibility, not a JSON Schema guarantee;
- AO-MA-10 plan references AO-MA-10h as a recorded contract slice;
- `local-ai-review-evidence.v1.json` records cross-provider review evidence;
- `ao_release_gate.py`, `.github/**`, CODEOWNERS, branch protection, rulesets,
  and `gpp_status.v1.json` are unchanged.
