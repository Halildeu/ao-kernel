# GPP-2ag - Local AI Review Gate Pivot

**Status:** planned / local-only gate design
**Date:** 2026-05-22
**Parent:** `GPP-2 - Protected Live-Adapter Gate Runtime Binding`
**Support impact:** none
**Production platform claim:** false
**Live adapter execution:** false

## 1. Purpose

Record the scope correction for GPP-2 after PHASE 7-8 evidence collection.

The existing local operator workflow already uses the core trust pattern:

```text
implementer AI changes the repo
reviewer AI reviews independently
operator decides whether to merge
repo rules and evidence remain the authority
```

The next near-term goal is to make that local trust pattern explicit,
repeatable, and evidence-backed before continuing the heavier
deployment-protection callback path.

This slice does not retire the GitHub App, webhook, or deployment-protection
work. It splits the program into a smaller sequence:

```text
GPP-2A: local AI review gate evidence
GPP-2B: GitHub required check / release-gate enforcement
GPP-2C: deployment-protection callback / protected workflow gate
```

GPP-2 remains blocked until the existing protected runtime evidence chain is
complete. Local evidence is useful operator evidence, not production readiness.

## 2. Current State

Collected evidence:

1. Hosted public HTTPS health evidence exists for the policy service and
   `ao-release-gate`.
2. GitHub App webhook delivery chain evidence exists through a smee.io
   non-production dry-run proxy.
3. `ao-release-gate` posted a real PR check-run in shadow mode.
4. Shadow/enforce conclusion mode support is implemented.

Remaining protected-runtime blockers:

1. policy App slug reconciliation;
2. production-suitable deployment-protection callback topology;
3. deployment-protection callback review evidence;
4. enforce-mode positive and negative path evidence;
5. branch protection / ruleset cutover;
6. protected workflow evidence rerun.

The heavy callback path is still valid, but it is not the shortest path to
codifying the operator's current local AI-review trust model.

## 3. Decision

Before continuing AO-GATE-7 production callback topology work, define and
implement a local AI review gate.

The local gate must:

1. read the repo operating contract and current GPP state;
2. require an independent reviewer evidence file;
3. validate that reviewer verdict is `AGREE` before allowing an
   operator-merge recommendation;
4. fail closed on missing review, `REVISE`, `BLOCK`, test failure, secret risk,
   forbidden action, or scope mismatch;
5. emit a durable no-secret JSON artifact under `.ao/evidence/local-gate/`;
6. explicitly keep `support_widening=false`,
   `production_platform_claim=false`, and `live_adapter_execution=false`.

## 4. Non-Goals

This local gate does not:

1. configure GitHub Apps;
2. change webhook URLs;
3. use smee.io;
4. alter branch protection;
5. dispatch the protected live-adapter workflow;
6. execute a live adapter;
7. claim production readiness;
8. widen support.

## 5. Proposed Local Gate Contract

### Inputs

```text
AGENTS.md
.claude/plans/gpp_status.v1.json
python3 scripts/gpp_next.py
git status / git diff metadata
test command result metadata
secret scan result metadata
reviewer evidence JSON
```

### Reviewer Evidence Shape

```json
{
  "schema_version": "local-ai-review-evidence.v1",
  "repo": "Halildeu/ao-kernel",
  "work_package": "GPP-2ag",
  "reviewer": {
    "agent": "codex-or-claude",
    "provider": "openai-or-anthropic",
    "verdict": "AGREE"
  },
  "scope_reviewed": {
    "base_ref": "origin/main",
    "head_ref": "codex/example",
    "changed_files": []
  },
  "checks_considered": [],
  "findings": [],
  "secrets_recorded": false,
  "live_adapter_execution": false,
  "support_widening": false,
  "production_platform_claim": false
}
```

### Gate Output Shape

```json
{
  "schema_version": "local-gpp-gate-evidence.v1",
  "decision": "operator_may_merge",
  "repo": "Halildeu/ao-kernel",
  "work_package": "GPP-2ag",
  "checks": {
    "startup_preflight_passed": true,
    "gpp_status_checked": true,
    "scope_allowed": true,
    "tests_passed": true,
    "secret_scan_passed": true,
    "reviewer_agree": true,
    "forbidden_actions_absent": true
  },
  "support_widening": false,
  "production_platform_claim": false,
  "live_adapter_execution": false
}
```

## 6. Initial Implementation Plan

1. Add `scripts/local_gpp_gate.py`.
2. Add a JSON-schema-like validator in code for reviewer evidence.
3. Add unit tests covering:
   - missing reviewer evidence fails;
   - reviewer `REVISE` fails;
   - reviewer `BLOCK` fails;
   - reviewer `AGREE` plus passing checks succeeds;
   - forbidden-action flag fails;
   - `support_widening=true`, `production_platform_claim=true`, or
     `live_adapter_execution=true` fails.
4. Add a sample no-secret fixture under `tests/fixtures/local_gpp_gate/`.
5. Emit evidence only when requested with an explicit output path.
6. Do not wire this to branch protection in this slice.

## 7. Acceptance

The slice is acceptable when:

1. local gate tests pass;
2. `python3 scripts/gpp_next.py` still reports GPP-2 blocked;
3. a demo run can produce a no-secret local evidence artifact;
4. missing/negative reviewer evidence fails closed;
5. docs clearly state this is local operator evidence, not production readiness.

## 8. Follow-Up Split

After GPP-2A local evidence is stable:

1. GPP-2B can map the same local evidence contract to `ao-release-gate`
   required check behavior.
2. GPP-2C can continue production deployment-protection callback evidence when
   a stable endpoint and App slug decision are ready.
