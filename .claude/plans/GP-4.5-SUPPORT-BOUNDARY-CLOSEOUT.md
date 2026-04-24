# GP-4.5 — Support-Boundary Closeout

**Status:** Completed decision record
**Date:** 2026-04-24
**Tracker:** [#400](https://github.com/Halildeu/ao-kernel/issues/400)
**Slice issue:** [#413](https://github.com/Halildeu/ao-kernel/issues/413)
**Predecessors:** `GP-4.1`, `GP-4.2`, `GP-4.3`, `GP-4.4`

## Decision

**Verdict:** `close_no_widening_keep_operator_beta`

`GP-4` is closed without support widening. The `claude-code-cli` lane remains
`Beta (operator-managed)`. It is not promoted to shipped baseline,
production-certified read-only support, or general-purpose production platform
support.

## Evidence Considered

| Gate | Evidence | Result |
|---|---|---|
| `GP-4.1` workflow skeleton | `live-adapter-gate-contract.v1.json` | `overall_status="blocked"`, no live execution |
| `GP-4.2` evidence contract | `live-adapter-gate-evidence.v1.json` | required live evidence slots remain blocked |
| `GP-4.3` protected environment contract | `live-adapter-gate-environment-contract.v1.json` | required environment/secret handle documented, not attested |
| `GP-4.4` rehearsal decision | `live-adapter-gate-rehearsal-decision.v1.json` | `decision="blocked_no_rehearsal"` |
| Support docs | `PUBLIC-BETA.md`, `SUPPORT-BOUNDARY.md`, adapter/runbook docs | lane remains operator-managed beta |

## Blocking Gaps

These gaps are intentionally not papered over by GP-4:

1. The required protected GitHub environment
   `ao-kernel-live-adapter-gate` is not attested as configured.
2. The required project-owned credential handle `AO_CLAUDE_CODE_CLI_AUTH` is
   documented but no secret value is read, committed, or verified.
3. No protected live preflight report exists.
4. No protected governed workflow-smoke report exists.
5. No workflow `environment:` binding exists.
6. No live `claude` invocation is made by the gate.
7. `KB-001` and `KB-002` remain open operator-managed lane caveats.

## Support Boundary Impact

No support tier changes:

1. Stable shipped baseline: unchanged.
2. `claude-code-cli`: remains `Beta (operator-managed)`.
3. Production-certified real-adapter support: not granted.
4. General-purpose production coding automation platform claim: not granted.
5. Version, tag, and publish state: unchanged.

## Reopen Conditions

A future support-widening attempt must open a new explicit gate and satisfy all
of the following before promotion can be reconsidered:

1. protected environment is configured and attested;
2. project-owned credential is configured through that protected environment;
3. protected live preflight report is collected;
4. protected governed workflow-smoke report is collected;
5. missing credentials remain explicit `blocked` / `skipped`, never fake green;
6. untrusted fork and pull-request secret exposure remain impossible;
7. docs, support matrix, runbook, tests/smoke, and CI/release gate evidence all
   agree on the promoted surface.

## Non-Changes

This closeout deliberately does not:

1. create GitHub environments;
2. add, read, or commit secret values;
3. bind workflow `environment:`;
4. call `claude`;
5. modify runtime behavior;
6. publish or tag a release;
7. widen support.

## Validation Scope

This slice is a truth/status patch. Required validation:

1. targeted docs/status parity checks;
2. `tests/test_live_adapter_gate_contract.py`;
3. `python3 -m ao_kernel doctor`;
4. `python3 scripts/packaging_smoke.py`.
