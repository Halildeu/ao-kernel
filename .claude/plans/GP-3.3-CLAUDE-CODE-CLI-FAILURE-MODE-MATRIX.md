# GP-3.3 — Claude Code CLI Failure-Mode Matrix

**Status:** Completed on branch, pending PR merge
**Date:** 2026-04-24
**Tracker:** [#392](https://github.com/Halildeu/ao-kernel/issues/392)
**Parent tracker:** [#386](https://github.com/Halildeu/ao-kernel/issues/386)
**Lane:** `claude-code-cli` read-only governed workflow

## Purpose

Classify the failure modes that must stay promotion blockers before the
`claude-code-cli` lane can be considered for a production-certified read-only
support claim.

This gate verifies that failure cases are fail-closed, typed, and
operator-actionable instead of silently looking like a successful smoke.

## Scope

Included:

1. Preflight helper failure modes.
2. Governed workflow smoke failure modes.
3. Existing behavior-test coverage audit.
4. Narrow missing assertion coverage for malformed manifest output and workflow
   timeout.
5. Operator-facing failure matrix wording.

Excluded:

1. No runtime behavior change.
2. No version bump, tag, or publish.
3. No support-boundary promotion.
4. No CI-required live `claude-code-cli` execution.
5. No `gh-cli-pr` live-write promotion.

## Failure-Mode Contract

| Mode | Stable finding code | Surface | Evidence |
|---|---|---|---|
| Missing binary | `claude_binary_missing` | helper preflight | `tests/test_claude_code_cli_smoke.py::test_binary_missing_blocks_and_skips_remaining_checks` |
| Auth missing | `claude_not_logged_in` | helper preflight | `tests/test_claude_code_cli_smoke.py::test_auth_status_not_logged_in_blocks_preflight_contract` |
| Auth status malformed | `claude_auth_status_not_json` | helper preflight | `tests/test_claude_code_cli_smoke.py::test_auth_status_non_json_blocks_preflight_contract` |
| Prompt denied despite auth pass | `prompt_access_denied` | helper preflight | `tests/test_claude_code_cli_smoke.py::test_auth_status_pass_prompt_access_fail_blocks_preflight_contract` |
| Invalid bearer token fallback | `prompt_access_denied` with `failure_kind=invalid_bearer_token` | helper preflight | `tests/test_claude_code_cli_smoke.py::test_invalid_bearer_token_is_classified_explicitly` |
| Prompt timeout | `prompt_smoke_timeout` | helper preflight | `tests/test_claude_code_cli_smoke.py::test_prompt_timeout_is_reported_without_crashing` |
| Manifest CLI contract mismatch | `manifest_cli_contract_mismatch` | helper preflight | `tests/test_claude_code_cli_smoke.py::test_manifest_contract_mismatch_is_reported` |
| Manifest timeout | `manifest_smoke_timeout` | helper preflight | `tests/test_claude_code_cli_smoke.py::test_manifest_timeout_is_reported_without_success_promotion` |
| Manifest non-JSON output | `manifest_output_not_json` | helper preflight | `tests/test_claude_code_cli_smoke.py::test_manifest_non_json_output_is_contract_failure` |
| Manifest JSON missing status | `manifest_output_missing_status` | helper preflight | `tests/test_claude_code_cli_smoke.py::test_manifest_json_missing_status_is_contract_failure` |
| Workflow malformed output | `output_parse_failed` | governed workflow smoke | `tests/test_claude_code_cli_workflow_smoke.py::test_workflow_smoke_classifies_output_parse_fail_closed` |
| Workflow policy denied | `policy_denied` | governed workflow smoke | `tests/test_claude_code_cli_workflow_smoke.py::test_workflow_smoke_classifies_policy_denial_before_promotion` |
| Workflow adapter non-zero exit | `adapter_non_zero_exit` | governed workflow smoke | `tests/test_claude_code_cli_workflow_smoke.py::test_workflow_smoke_classifies_adapter_non_zero_exit` |
| Workflow adapter timeout | `adapter_timeout` | governed workflow smoke | `tests/test_claude_code_cli_workflow_smoke.py::test_workflow_smoke_classifies_adapter_timeout` |

## Test Delta

Three behavior assertions were added:

1. `test_auth_status_non_json_blocks_preflight_contract`
   - proves malformed auth status payloads are blocked;
   - pins `claude_auth_status_not_json`.
2. `test_manifest_json_missing_status_is_contract_failure`
   - proves valid JSON with the wrong shape is still blocked;
   - pins `manifest_output_missing_status`.
3. `test_workflow_smoke_classifies_adapter_timeout`
   - proves workflow-level adapter timeout is blocked;
   - pins `adapter_timeout`.

No production code change was required.

## Validation

```bash
python3 -m pytest -q tests/test_claude_code_cli_smoke.py tests/test_claude_code_cli_workflow_smoke.py
```

Result:

```text
21 passed
```

## Decision

The failure-mode matrix is sufficiently classified to move to `GP-3.4`
evidence completeness.

This does not mean the lane is production-certified. It only means the known
failure categories are visible and fail-closed enough for the next gate.

## Support Boundary Impact

No support boundary widening.

Current support tier remains:

1. `claude-code-cli`: `Beta (operator-managed)`
2. production-certified read-only claim: not yet granted
3. stable shipped baseline: unchanged

## Next Gate

`GP-3.4` should verify evidence completeness:

1. artifact contents and schema;
2. event order and required event kinds;
3. adapter log redaction;
4. cost/usage fields or explicit non-claim;
5. operator-readable failure metadata.
