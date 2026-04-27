# GPP-2m - Protected Live Gate Runtime Binding

**Status:** closeout candidate
**Date:** 2026-04-27
**Authority:** `origin/main` at `fe8b61c`
**Issue:** [#521](https://github.com/Halildeu/ao-kernel/issues/521)
**Branch:** `codex/gpp-2m-runtime-binding`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gpp-2m-runtime-binding`
**Program head:** `GPP-2` protected workflow bound; live execution not started
**Support impact:** none
**Runtime impact:** protected environment binding only; no live adapter call

## 1. Purpose

Bind the manual live-adapter gate workflow to the protected GitHub environment
after GPP-2l recorded ready prerequisite metadata.

Decision:

```text
protected_workflow_bound_live_execution_still_disabled
```

This slice does not invoke `claude`, does not read or reference secret values,
does not add `push`, `pull_request`, or `pull_request_target` triggers, does
not widen support, and does not claim production-platform readiness.

## 2. Scope

Changed workflow:

```text
.github/workflows/live-adapter-gate.yml
```

The `live-adapter-gate-contract` job now has a job-level binding:

```yaml
environment:
  name: ao-kernel-live-adapter-gate
```

The workflow remains `workflow_dispatch` only and keeps `permissions:
contents: read`. It still emits blocked design/evidence artifacts through
`scripts/live_adapter_gate_contract.py`; it does not run the live adapter.

## 3. Fail-Closed Interpretation

GitHub environment deployment protection is now on the execution path for the
manual gate job. If the GitHub App deployment protection webhook or policy
service is inactive, denies the deployment, times out, or fails, the workflow
must remain blocked or failed.

That is the expected fail-closed result. It is not approval to bypass the
environment, use a PAT-backed bot reviewer, use `--equivalent-release-gate-approved`,
or treat local operator auth as project-owned production evidence.

## 4. Secret Boundary

`AO_CLAUDE_CODE_CLI_AUTH` remains only an environment secret handle attested by
metadata. This slice intentionally does not use `secrets.AO_CLAUDE_CODE_CLI_AUTH`
or any other `secrets.` expression.

Future live execution requires a separate issue, branch, PR, and evidence
slice that explicitly permits the live adapter run while preserving redaction
and support-boundary guards.

## 5. Current Decision

Passing checks after this slice:

1. protected environment prerequisites are ready by GPP-2l;
2. `.github/workflows/live-adapter-gate.yml` is bound to
   `ao-kernel-live-adapter-gate`;
3. workflow triggers remain manual-only;
4. workflow has no `secrets.` expression;
5. workflow has no live adapter invocation;
6. `live_execution_allowed=false`;
7. `support_widening=false`;
8. `production_platform_claim=false`.

Still closed:

1. no protected workflow dispatch evidence has been collected in this slice;
2. no live adapter has executed;
3. no production support claim is made.

## 6. Next Slice

The next controlled slice may collect protected workflow evidence from `main`.
It must treat deployment protection inactivity, denial, timeout, or failure as
fail-closed evidence, not approval.

Minimum scope for the next slice:

1. dispatch `.github/workflows/live-adapter-gate.yml` from `main`;
2. record whether the environment deployment protection app approves, denies,
   blocks, times out, or fails;
3. download and validate artifacts only if the protected job reaches its
   artifact-producing steps;
4. keep `live_execution_allowed=false` unless a later explicit live-execution
   slice changes that guard;
5. keep `support_widening=false` and `production_platform_claim=false`.

## 7. Validation

```bash
python3 -m json.tool .claude/plans/gpp_status.v1.json
pytest -q tests/test_live_adapter_gate_contract.py
pytest -q tests/test_gpp_next.py
python3 scripts/live_adapter_gate_attest.py --artifact-path /tmp/gpp-2m-attestation.json --output text
python3 scripts/gpp_next.py
git diff --check
```

Expected closeout decision:

```text
protected_workflow_bound_live_execution_still_disabled
```

Recorded closeout decision:

```text
protected_workflow_bound_live_execution_still_disabled
```
