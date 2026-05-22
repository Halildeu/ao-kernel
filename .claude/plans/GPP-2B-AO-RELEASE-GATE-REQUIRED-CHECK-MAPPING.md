# GPP-2B - ao-release-gate Required-Check / Local Gate Evidence Mapping

**Status:** planned / planning slice — contract mapping documentation only
**Date:** 2026-05-22
**Parent:** `GPP-2 - Protected Live-Adapter Gate Runtime Binding`
**Pivot record:** `.claude/plans/GPP-2ag-LOCAL-AI-REVIEW-GATE-PIVOT.md`
**Support impact:** none
**Production platform claim:** false
**Live adapter execution:** false

## 1. Purpose

The GPP-2ag pivot split `GPP-2` into three slices:

```text
GPP-2A: local AI review gate evidence            — DONE (PR #576 + #577)
GPP-2B: ao-release-gate required check / mapping  — this slice
GPP-2C: deployment-protection callback / topology — deferred optional infra
```

This record is the **GPP-2B planning slice**. It maps the two repo-owned merge
gates onto each other so a later GPP-2B implementation slice — and eventually
the AO-GATE-8 branch-protection cutover — can make the `ao-release-gate`
required check enforce the same governance the local AI review gate already
validates.

This slice is **documentation only**: a contract mapping, a gap analysis, and a
phased plan. It does **not** implement the mapping, change branch protection,
switch `ao-release-gate` to enforce mode, configure webhooks or GitHub Apps,
execute live adapters, widen support, or claim production readiness. GPP-2
stays `blocked`.

## 2. The two gates

### 2.1 Local AI Review Gate — GPP-2A / LOCAL-GATE-1

- Surface: `scripts/local_gpp_gate.py`; schemas
  `ao_kernel/defaults/schemas/local-ai-review-evidence.schema.v1.json`
  (input) and `local-gpp-gate-evidence.schema.v1.json` (output).
- Runs **locally**, operator-controlled. Consumes an independent reviewer-AI
  evidence file plus local repo state (`AGENTS.md`, `gpp_status.v1.json`, the
  real `git diff`).
- Emits a durable no-secret `local-gpp-gate-evidence.v1` artifact.
- Eight fail-closed checks; `decision = operator_may_merge` only when all eight
  pass, otherwise `fail_closed`.
- It is operator-local trust evidence. It does not post to GitHub, does not
  gate merges mechanically, and does not close GPP-2.

### 2.2 ao-release-gate — GPP-2u / GPP-2v / GPP-2w

- Surface: `ao_kernel/ao_release_gate.py` (`build_ao_release_gate_decision`);
  CLI `scripts/ao_release_gate_decision.py`; service/runtime
  `ao_kernel/ao_release_gate_service.py` + `ao_release_gate_runtime.py`.
- A repo-owned GitHub App release gate. Consumes a PR-shaped GitHub payload
  plus the GPP status JSON. Emits an `ao-release-gate` GitHub check-run.
- Eighteen checks; `decision = allow_autonomous_merge` only when all pass,
  otherwise one of `deny_policy_violation`, `deny_missing_evidence`,
  `deny_stale_branch`, `deny_untrusted_context`, `error_fail_closed`.
- Check-run conclusion is mode-aware (`ConclusionMode`): `allow_autonomous_merge`
  → `success` in both modes; any deny/error → `neutral` in `shadow` (default,
  advisory) and `failure` in `enforce`.
- Currently dry-run / shadow only: not hosted as a required status check, no
  branch-protection cutover (AO-GATE-8 not done).

## 3. Contract mapping

### 3.1 Check correspondence

| Local gate check (8) | ao-release-gate check(s) (20) | Category |
|---|---|---|
| `startup_preflight_passed` | `payload_shape`, `repository` | A — evaluation context is structurally valid |
| `gpp_status_checked` | `gpp_status`, `gpp_closed_boundaries` | A — GPP-2 blocked + support/production/live-adapter guards false |
| `scope_allowed` | `diff_scope` | A — changed-file scope within bounds |
| `tests_passed` | `required_checks` | A — tests/CI pass (local: reviewer-recorded `tests`; ao-gate: live required CI checks) |
| `secret_scan_passed` | `secret_boundary` | A — no secret material |
| `forbidden_actions_absent` | `admin_bypass_boundary`, `bot_boundary`, `agent_authority_boundary`, `live_adapter_boundary` | A — no forbidden action / authority |
| `reviewer_agree`, `cross_provider_verified` | `review_evidence` | A — cross-AI reviewer AGREE + cross-provider verdict consumed by ao-release-gate via the local-gpp-gate-evidence acceptance profile (GPP-2D-2b) |
| *(none)* | `pull_request`, `issue_link`, `base_ref`, `branch_freshness`, `fork_boundary`, `event_boundary`, `gpp_issue_consistency`, `review_evidence_context_bound` | B — GitHub PR-context checks, ao-release-gate-only |

- **Category A** — both gates verify the same governance condition from
  different vantage points (local repo state vs. GitHub PR payload). These are
  the directly mappable checks. Some pairings are approximate vantage-point
  correspondences, not strict equivalences — notably `startup_preflight_passed`
  ↔ `payload_shape` / `repository`, which both stand for "the evaluation
  context is structurally valid."
- **Category B** — GitHub-PR-context checks (fork, event, branch freshness,
  base/issue link, plus `gpp_issue_consistency`, which matches the PR payload's
  issue URL against the current GPP work package, and
  `review_evidence_context_bound`, which binds the local-gate evidence to the
  PR head SHA, repository, reviewed slice, diff digest, and changed-files
  count). The local gate has no PR payload and cannot perform these; they are
  inherently ao-release-gate-only and require no reconciliation.
- **Category C** — historical: the cross-AI peer review verdict was previously
  unmappable (local-only) and tracked in §4 as the substantive gap. GPP-2D-2b
  closes that gap by wiring the ao-release-gate decision core to consume the
  local-gate evidence under the §5.1 acceptance profile, so the C rows are now
  Category A. See §4 for the gap-closure record.

### 3.2 Decision-value mapping

| Local gate `decision` | ao-release-gate `decision` |
|---|---|
| `operator_may_merge` | `allow_autonomous_merge` |
| `fail_closed` | one of `deny_policy_violation` / `deny_missing_evidence` / `deny_stale_branch` / `deny_untrusted_context` / `error_fail_closed` |

The local gate collapses every failure into a single `fail_closed` plus
per-check booleans and gate-authored `findings`. `ao-release-gate` classifies
failures into typed deny reasons. The mapping is therefore one-to-many in the
fail direction: the single local `fail_closed` value expands into the typed
`ao-release-gate` deny reasons — a local `fail_closed` whose failing check is
`forbidden_actions_absent` corresponds to `deny_policy_violation`; a failing
`gpp_status_checked` / `scope_allowed` / `tests_passed` / `secret_scan_passed`
corresponds to `deny_missing_evidence` or `deny_policy_violation` depending on
the finding. Both gates are fail-closed: a malformed or absent input yields the
deny/closed side, never allow.

## 4. Gap analysis

- **Category B is not a gap.** GitHub-context checks belong to the
  GitHub-side gate by construction; the local gate is not expected to perform
  them.
- **Category C is the substantive gap.** The local gate's distinguishing
  value — the **cross-AI peer review** verdict (`reviewer_agree`,
  `cross_provider_verified`) — has no counterpart in `ao-release-gate`. The
  `ao-release-gate` decision core evaluates PR evidence, CI, scope, and
  boundary signals autonomously; it does not consume a reviewer-AI verdict.

If `ao-release-gate` becomes a required status check while the cross-AI review
verdict remains outside its inputs, the GitHub-enforced gate would be strictly
weaker than the local gate on the cross-AI-review dimension. GPP-2B must record
how that dimension is handled before any AO-GATE-8 cutover.

## 5. Gap-handling options

The gap-resolution decision is **not made in this slice**. A later GPP-2B
implementation slice resolves it after a cross-AI consultation. The candidate
options:

1. **Required attested review evidence.** `ao-release-gate` gains a check that
   consumes an attested cross-AI review evidence artifact committed to or
   attached to the PR. The artifact should be the **no-secret
   `local-gpp-gate-evidence.v1` gate output** (or a new minimal attestation
   derived from it) — **not** the raw `local-ai-review-evidence.v1` reviewer
   file, which carries raw reviewer free text. A PR without a present,
   schema-valid `local-gpp-gate-evidence.v1` recording `operator_may_merge`
   (which itself already requires `reviewer_agree` + `cross_provider_verified`)
   would map to `deny_missing_evidence`. This makes the required check enforce
   cross-AI review mechanically while preserving the LOCAL-GATE-1 no-secret
   guarantee.
2. **Operator-local process discipline.** The cross-AI review stays a
   pre-PR operator-local step validated by the local gate; `ao-release-gate`
   does not check it. The required check then enforces only CI + scope +
   boundaries + GPP status, and cross-AI review remains a HARD RULE process
   discipline, not a mechanical GitHub gate.

Recommendation for the implementation slice: Option 1, consuming the no-secret
`local-gpp-gate-evidence.v1` gate output (never the raw reviewer file), because
it keeps the required check from being weaker than the local gate without
reintroducing raw-reviewer-text leakage. The final choice is deferred to the
GPP-2B implementation slice (GPP-2B-3) plus a Codex consultation.

### 5.1 Resolution (GPP-2B-3)

Resolved via Codex consultation (thread `019e50c8`): **Option 1**.

**Decision.** `ao-release-gate` will eventually require attested cross-AI
review evidence. Option 2 would leave the required check deliberately weaker
than the local gate on the Category-C dimension. GPP-2B-3 closes the gap's
**design decision** only — the runtime enforcement gap closes later, when
`ao-release-gate` actually consumes the artifact and enters the
required-check / enforce chain. GPP-2 stays `blocked`.

**Accepted artifact.** The existing no-secret `local-gpp-gate-evidence.v1`
gate output, consumed as-is. No new evidence artifact is introduced, and no
replacement for `local-gpp-gate-evidence.schema.v1.json` is introduced —
`local-gpp-gate-evidence.v1` remains the evidence SSOT. It already encodes
`reviewer_agree`, `cross_provider_verified`, and `operator_may_merge`, and is
no-secret by schema construction. A second evidence artifact would duplicate it
and risk drift. (The acceptance-profile schema added by this slice, described
next, is a consumption contract — not an evidence schema.)

**Acceptance-profile schema.** GPP-2B-3 adds one design-only schema,
`ao_kernel/defaults/schemas/ao-release-gate-review-evidence-input.schema.v1.json`.
It is an *acceptance profile*, not a standalone structural validator: it
constrains only the acceptance-critical fields (`decision` =
`operator_may_merge`; `checks.reviewer_agree` and `checks.cross_provider_verified`
= `true`; the closed GPP guard flags) and permits the artifact's other fields.
It deliberately omits a `$ref` / `allOf` to `local-gpp-gate-evidence.schema.v1.json`
because the bundled-schema loader resolves single files only and builds no
registry for an external `$ref`. The future check therefore validates in two
steps: **first** the full `local-gpp-gate-evidence.schema.v1.json`, **then**
this acceptance profile.

**Future check (design only — not implemented in this slice).** A future
`ao-release-gate` check named `cross_ai_review` would verify that the review
evidence is present, structurally valid against
`local-gpp-gate-evidence.schema.v1.json`, conformant to the acceptance profile,
and context-consistent:

- `repo` equals the normalized PR repository;
- `work_package` equals the PR's explicitly declared reviewed slice — it is
  **not** equated blindly to `gpp_status.current_wp.id`, since the current work
  package may be the parent `GPP-2` while a valid artifact carries a slice id
  such as `GPP-2B-3` — and implies no work outside the parent `GPP-2` scope;
- `gpp_2_status` is `blocked`.

Missing, schema-invalid, non-accepting, or context-mismatched evidence maps to
`deny_missing_evidence`, with granular finding codes:
`ao_release_gate_cross_ai_review_evidence_missing`,
`ao_release_gate_cross_ai_review_evidence_schema_invalid`,
`ao_release_gate_cross_ai_review_evidence_not_accepting`,
`ao_release_gate_cross_ai_review_evidence_context_mismatch`.

**Scope.** Design only: no `ao_release_gate.py` change, no service wiring, no
payload-field handling, no webhook or GitHub App config, no enforce-mode
switch, no branch-protection cutover, no `gpp_status.v1.json` change. GPP-2
stays `blocked`; the guard flags stay `false`.

## 6. GPP-2B implementation plan (phased)

All slices are docs/schema/test scope. No cutover, no enforce-mode switch, no
webhook/App configuration, no live adapter.

| Slice | Scope | Gate |
|---|---|---|
| **GPP-2B-1** | This mapping record (this PR). | docs only |
| **GPP-2B-2** | A machine-checkable mapping test pinning the §3.1 table to both gates' live check sets: every local-gate check (8, from `local-gpp-gate-evidence.schema.v1.json`) and every `ao-release-gate` check (18, from `build_ao_release_gate_decision`) must appear in the table with a documented counterpart or an explicit `local-only` marker, so the mapping cannot silently drift on either side. Implemented as `tests/test_gpp2b_mapping_drift_guard.py`. | docs + test |
| **GPP-2B-3** | Resolve the Category-C gap (§5) via Codex consultation; if Option 1 is selected, design the attested-review-evidence schema/contract (design only — no service wiring). Resolved as Option 1 in §5.1; acceptance-profile schema `ao_kernel/defaults/schemas/ao-release-gate-review-evidence-input.schema.v1.json` + contract test `tests/test_gpp2b3_review_evidence_input_schema.py`. | docs + schema + test |
| **GPP-2B-4** | Unit/schema-level conclusion-mapping test against the side-effect-free decision core: assert `build_ao_release_gate_decision(..., conclusion_mode=...)` maps decisions to GitHub conclusions correctly — `allow_autonomous_merge` → `success`; `deny_*` / `error_fail_closed` → `neutral` under `shadow` and `failure` under `enforce`. Pure in-process unit test; the hosted runtime mode is not changed, no check-run is posted to any PR, branch protection is untouched. Implemented as `tests/test_ao_release_gate.py::test_check_run_conclusion_mapping` (6 decisions x shadow/enforce). | docs + test |

Real enforce-mode evidence on live PRs — switching the hosted runtime to
`conclusion_mode="enforce"` and observing a positive (`success`) and a negative
(`failure`) path on actual pull requests — is now the active no-testai GPP-2B
follow-up after the mapping/test contract exists. The AO-GATE-8
branch-protection cutover (making `ao-release-gate` a required status check)
must still wait for that real enforce-mode evidence, but it no longer waits on
deployment-protection callback topology, `testai.acik.com/ao-gate`, smee.io, or
policy App slug reconciliation. Those are deferred optional GPP-2C
infrastructure.

## 7. Hard stops / non-goals

- No branch protection / ruleset mutation in this planning record.
- No `ao-release-gate` enforce-mode switch in this planning record
  (`DEFAULT_CONCLUSION_MODE` stays `shadow`).
- No real PR check-run posting and no runtime `conclusion_mode` env flip; no
  enforce-mode evidence collection on live PRs in this planning record. A
  GPP-2B-4 unit test may pass `conclusion_mode="enforce"` to the in-process
  decision function only; a later evidence slice collects real enforce-mode PR
  evidence before cutover.
- No webhook URL or GitHub App configuration change.
- No live adapter execution.
- No `--admin` merge.
- No support widening; no production-platform claim.
- GPP-2 stays `blocked`; `gpp_status.v1.json` guard flags stay `false`.
- No secret / token / PAT / PEM in docs, schemas, tests, or artifacts.

## 8. Follow-up

The active no-testai path continues with `ao-release-gate` enforce-mode
success/failure evidence on real PRs, then branch-protection / ruleset cutover
to require that status check with admin bypass disabled, then AO-GATE-9 closeout.
Deployment-protection callback evidence, production-suitable callback topology
(including `testai.acik.com/ao-gate` or any replacement endpoint), smee.io
delivery, and policy App slug reconciliation are deferred optional GPP-2C
infrastructure and are not active GPP-2B blockers.
