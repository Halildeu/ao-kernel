# GPP-2k - Protected Live Gate Provisioning Runbook

**Status:** closeout candidate
**Date:** 2026-04-27
**Authority:** `origin/main` at `1a3bf8c`
**Issue:** [#517](https://github.com/Halildeu/ao-kernel/issues/517)
**Branch:** `codex/gpp-2k-live-gate-runbook`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gpp-2k-live-gate-runbook`
**Program head:** `GPP-2` remains blocked
**Support impact:** none
**Runtime impact:** docs/status only; no live execution

## 1. Purpose

Add an operator-facing runbook for the external/admin provisioning steps that
still block `GPP-2`.

Decision:

```text
protected_live_gate_provisioning_runbook_ready_no_support_widening
```

This slice does not create a GitHub App, does not configure GitHub environment
protection, does not set or read secrets, does not bind runtime workflows, does
not run a live adapter, and does not widen support.

## 2. Added Runbook

The new runbook is:

```text
docs/LIVE-ADAPTER-GATE-PROVISIONING-RUNBOOK.md
```

It records:

1. selected gate model:
   `github_app_deployment_protection_rule`;
2. required app slug:
   `ao-kernel-live-adapter-gate`;
3. protected environment:
   `ao-kernel-live-adapter-gate`;
4. required environment secret handle:
   `AO_CLAUDE_CODE_CLI_AUTH`;
5. metadata-only verification commands;
6. evidence comment template for #482/#485 or a follow-up attestation PR;
7. rollback/remediation steps for wrong app or wrong secret handle;
8. forbidden actions that keep runtime binding and support widening closed.

## 3. Current Decision

`GPP-2` remains blocked.

This runbook reduces operator ambiguity only. The current blockers are still:

1. `AO_CLAUDE_CODE_CLI_AUTH` is not visible as an environment secret handle;
2. selected GitHub App slug `ao-kernel-live-adapter-gate` is not visible;
3. no deployment protection rule is attached to
   `ao-kernel-live-adapter-gate`.

## 4. Required External/Admin Work

Follow
[`docs/LIVE-ADAPTER-GATE-PROVISIONING-RUNBOOK.md`](../../docs/LIVE-ADAPTER-GATE-PROVISIONING-RUNBOOK.md)
to complete #482/#485 without secret readback.

Only after the selected app gate and credential handle are visible by metadata
should a follow-up prerequisite attestation slice run:

```bash
python3 scripts/live_adapter_gate_attest.py \
  --artifact-path /tmp/gpp-2-post-provisioning-attestation.json \
  --output text
```

Only if that future slice exits `prerequisites_ready` may `GPP-2` runtime
binding begin.

## 5. Forbidden Until Then

1. No `GPP-2` runtime binding.
2. No live adapter execution.
3. No support widening.
4. No production platform claim.
5. No secret value readback.
6. No local operator auth treated as project-owned production evidence.
7. No Claude/MCP advisory response treated as release authority.
8. No product end-user account or PAT-backed bot user treated as release
   authority.
9. No `--equivalent-release-gate-approved` while #489 remains not approved.

## 6. Validation

```bash
python3 -m json.tool .claude/plans/gpp_status.v1.json
pytest -q tests/test_gpp_next.py
pytest -q tests/test_gp5_platform_claim_decision.py
pytest -q tests/test_gp5_operations_support_package.py
python3 scripts/gpp_next.py
git diff --check
```

Expected closeout decision:

```text
protected_live_gate_provisioning_runbook_ready_no_support_widening
```

Recorded closeout decision:

```text
protected_live_gate_provisioning_runbook_ready_no_support_widening
```
