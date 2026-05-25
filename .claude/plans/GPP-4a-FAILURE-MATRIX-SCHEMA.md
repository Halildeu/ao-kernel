# GPP-4a — claude-code-cli Failure-Mode Matrix Schema (Faz 1)

> **Status:** schema + simulated coverage ready; decision authority reserved for GPP-4b; live runs reserved for an operator-bound supersession slice.
> **Slice:** `GPP-4a` (Faz 1 of GPP-4).
> **Decision:** `failure_matrix_schema_ready_simulated_coverage_ready_live_runs_pending_no_support_widening`.
> **Issue:** pinned on commit per CC-13.

## Purpose

GPP-4a installs the **failure-mode matrix schema and simulated
coverage** for the claude-code-cli adapter under the autonomous GPP-4
chain. GPP-4 Acceptance §3 demands a matrix that includes seven
canonical failure modes (auth missing, binary missing, timeout,
prompt denied, malformed output, policy denied, redaction); GPP-4a
delivers that matrix at evidence-class `simulated`. Live protected
runs (Acceptance §1 + §2) and the decision artifact (Acceptance §4)
are reserved for **GPP-4b** (closure path decision) and **GPP-4c**
(infazı).

This slice **does NOT**:

- choose between `promote_read_only`, `keep_operator_beta`, or
  `defer` (reserved for GPP-4b)
- modify `scripts/gp5_platform_claim_decision.py` BC criteria
- modify `docs/SUPPORT-BOUNDARY.md` or `docs/KNOWN-BUGS.md` semantics
  beyond a minimal Public Beta row
- execute a live claude-code-cli adapter
- widen support, claim production platform readiness, or authorize
  live adapter execution

## Bundled Schema

`ao_kernel/defaults/schemas/claude-code-cli-failure-mode.schema.v1.json`

The schema is an **aggregate matrix artifact** (Codex plan-time
iter-1 recommendation), not a single failure-mode event. Top-level
fields:

| Field | Constraint |
|---|---|
| `schema_version` | const `claude-code-cli-failure-mode.v1` |
| `artifact_kind` | const `claude_code_cli_failure_mode_matrix` |
| `adapter_id` | const `claude-code-cli` |
| `evidence_class` | enum `[simulated, live]` |
| `overall_status` | enum `[coverage_ready, coverage_ready_live_evidence_pending, live_runs_observed, live_runs_observed_fail_closed_witnessed]` |
| `support_widening` | const `false` |
| `production_platform_claim` | const `false` |
| `live_adapter_execution` | boolean (bound to `evidence_class` via root oneOf) |
| `protected_run` | object with `observed`, optional `run_url`/`check_run_id`/`source_pin_verified` |
| `coverage` | array of length **exactly 7**, unique items, must contain every canonical `failure_mode` via 7 `contains` invariants |
| `observed_at` | ISO 8601 UTC |

Coverage item fields:

| Field | Constraint |
|---|---|
| `failure_mode` | enum `[auth_missing, binary_missing, timeout, prompt_denied, malformed_output, policy_denied, redaction]` |
| `surface` | enum `[helper_preflight, workflow_smoke, evidence_emitter, adapter_runtime, policy_layer, redaction_layer]` |
| `stable_finding_codes` | non-empty array of repo-canonical finding code strings |
| `expected_overall_status` | enum `[blocked, fail_closed, rejected]` |
| `outcome` | enum `[fail_closed, blocked, rejected]` |
| `evidence_refs` | non-empty array of repo-relative paths |

### Root `oneOf` Bind

The schema enforces `evidence_class` ↔ `live_adapter_execution` ↔
`protected_run` consistency:

- `evidence_class=simulated` ⇒ `live_adapter_execution=false`,
  `protected_run.observed=false`, `protected_run.run_url=null`,
  `protected_run.check_run_id=null`,
  `protected_run.source_pin_verified=null`,
  `overall_status ∈ {coverage_ready, coverage_ready_live_evidence_pending}`.
- `evidence_class=live` ⇒ `live_adapter_execution=true`,
  `protected_run.observed=true`, `protected_run.run_url` required
  (URI), `protected_run.check_run_id` required (non-empty),
  `protected_run.source_pin_verified=true`,
  `overall_status ∈ {live_runs_observed, live_runs_observed_fail_closed_witnessed}`.

GPP-4a only emits `evidence_class=simulated`. The live branch is
declared in the schema so a future operator-bound supersession slice
can emit live evidence without a v2 schema bump.

## Bundled Script

`scripts/claude_code_cli_failure_mode_evidence.py`

Two CLI modes:

- `emit-simulated` — emit a schema-valid simulated matrix with all
  seven canonical failure modes pre-populated. The default coverage
  references the existing repo helper / workflow / adapter-runtime
  surfaces (`tests/test_claude_code_cli_helper.py`,
  `tests/test_claude_code_cli_smoke.py`,
  `ao_kernel/governance.py`,
  `ao_kernel/secrets/redaction.py`, etc.) and the repo's stable
  finding codes (`claude_not_logged_in`, `claude_binary_missing`,
  `adapter_timeout`, `prompt_access_denied`, `output_parse_failed`,
  `policy_denied`, `adapter_log_missing_or_unredacted`).
- `validate` — schema-validate an existing artifact.

The script intentionally has **no live-execution mode**. The live
path is operator-bound.

## Drift Guards

`tests/test_claude_code_cli_failure_mode_evidence.py` covers:

- Schema is valid Draft 2020-12.
- emit-simulated produces a schema-valid artifact.
- All seven canonical modes are present.
- `evidence_class=simulated` + `live_adapter_execution=false` +
  `protected_run.observed=false` are simultaneously enforced.
- `observed_at` is ISO-parseable.
- `overall_status="coverage_ready_live_evidence_pending"`.
- validate rejects: missing mode, duplicate mode, support_widening true,
  production_platform_claim true, simulated with live execution true,
  simulated with protected_run.observed true, simulated with live
  overall_status, invalid failure_mode enum, invalid surface enum,
  empty stable_finding_codes / evidence_refs, unknown top-level field,
  wrong adapter_id.
- CLI emit-simulated + validate smoke tests + corrupt-artifact
  rejection.

24 tests in total.

## SSOT Transition

`gpp_status.v1.json`:

- `current_wp` migrates from GPP-3c closed → GPP-4a active.
- GPP-3c closure preserved in `completed_wps` with the GPP-3c BC-10
  exception decision string, issue #618, pr #619, closeout record
  path, closed_at 2026-05-25T09:30:00Z.
- `milestones[M4]` stays `pending`; GPP-4a is a child slice of M4 and
  does not by itself close M4 (M4 closes only when GPP-4b decision
  and GPP-4c infazı both land).
- `progress_estimates`: `completed_wps_count` advances to 41,
  `closed_current_wp_count` returns to 0 (GPP-4a active), total stays
  41, percent stays 82%.
- `allowed_scope` rewrites for GPP-4a: schema + simulated coverage +
  GP-5.9 BC-1 / claude-code-cli promotion blocker preservation +
  defer support widening / production claim / live execution.

## Non-Goals

This slice (GPP-4a) explicitly does NOT:

1. mutate `scripts/gp5_platform_claim_decision.py`
2. remove `claude_code_cli_auth_operator_managed`,
   `kb001_claude_code_cli_operator_managed_auth`, or
   `protected_live_adapter_gate_unattested` from the GP-5.9
   `promotion_blockers` aggregate (Codex iter-1: GPP-4c retains those
   under the `keep_operator_beta` authority rather than clearing them)
3. update `docs/SUPPORT-BOUNDARY.md` or `docs/KNOWN-BUGS.md`
4. close M4 milestone (M4 closes with GPP-4c)
5. execute a live claude-code-cli adapter
6. flip any of the three GP-5/GPP-9 promotion guard flags
7. open GPP-4b or GPP-4c (those are separate slices)

## Cross-References

- `.claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md`
- `.claude/plans/gpp_status.v1.json`
- `.claude/plans/GP-5.9-PRODUCTION-PLATFORM-CLAIM-DECISION.md`
- `.claude/plans/GPP-3c-BC10-EXCEPTION-INFAZ.md`
- `.claude/plans/PROGRAM-CHANGE-CONTROL.md`
- `ao_kernel/defaults/schemas/claude-code-cli-failure-mode.schema.v1.json`
- `scripts/claude_code_cli_failure_mode_evidence.py`
- `scripts/gp5_platform_claim_decision.py` (untouched in GPP-4a)
- `docs/PUBLIC-BETA.md` (minimal GPP-4a row note)

## Audit Trail

| Field | Value |
|---|---|
| Implementer AI | Claude (Anthropic) |
| Reviewer AI | Codex (OpenAI) — thread `019e5eab` plan-time iter-1 AGREE |
| Worktree | `codex/gpp-4a-claude-code-cli-failure-matrix` |
| Base SHA at branch open | `be9944a` |
| Cross-provider AI review HARD RULE | satisfied (CC-2) |
| Non-author code-owner approval | required at merge time (CC-3) |
| Admin bypass attempted | `false` (CC-4) |
