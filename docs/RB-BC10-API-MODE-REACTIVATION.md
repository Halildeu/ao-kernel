# RB-BC10-API-MODE-REACTIVATION

Operator-facing reactivation **template** for the BC-10 real-adapter usage/cost
chain.

## Status & Scope

- **Status**: operator-facing reactivation **template only**; not executable
  authority; no live API call; no guard flip; no promotion.
- **Authority needed to act on this runbook**: a future operator-bound
  supersession PR with explicit, scoped reactivation permission (see §6).
- **Mode at writing**: CLI-only / no programmatic API. The
  [RI-7.8c Final Promote Decision](../.claude/plans/RI-7.8c-FINAL-PROMOTE-DECISION.v1.json)
  is authoritative under `keep_narrow_stable_runtime` and is **not** overridden
  by anything in this document.
- **What this runbook does NOT ship**:
  - It does NOT reactivate BC-10.
  - It does NOT flip `live_adapter_execution_allowed`, `support_widening_allowed`,
    or `production_platform_claim_allowed`.
  - It does NOT promote ao-kernel to a Beta or Production tier.
  - It does NOT modify any workflow, script, schema, pricing source, guard flag
    JSON, `gpp_status.v1.json`, or existing evidence artifact.
  - It does NOT create rollback by rewriting the existing
    [RI-7.8b-bc10-6c-DEFER-DECISION.v1.json](../.claude/plans/RI-7.8b-bc10-6c-DEFER-DECISION.v1.json).
  - It does NOT widen the model allowlist beyond `openai/gpt-4o-mini`.

## 1. Why this runbook exists

When BC-10 was deferred under CLI-only mode (PR #731 + #736, 2026-05-29), the
real-adapter usage/cost assets were intentionally preserved dormant per the
ADR-0027 mirror discipline (asset-preserved → reactivation chain template,
tenant demand-driven explicit trigger). This document is the **template** that
a future operator would mirror to author a reactivation supersession PR.

It does not authorize execution. It records the exact preconditions, guardrail
binding values, asset chain, gate sequence, and rollback semantics that the
operator must reproduce inside a scoped supersession PR before any live call
can occur.

## 2. Dormant assets inventory

| # | Asset | Role |
|---|---|---|
| 1 | `ao_kernel/defaults/schemas/ri7-8b-bc10-6a-execution-window-authorization-evidence.schema.v1.json` | 6a: authorization contract — defines `manual_protected_environment` authority + `does_not_authorize` enum + `mutations_performed` discipline. |
| 2 | `ao_kernel/defaults/schemas/ri7-8b-bc10-6b-protected-execution-window-evidence.schema.v1.json` | 6b: protected execution window evidence schema — environment observation, supersession entry, distinct-run count. |
| 3 | `ao_kernel/defaults/schemas/ri7-8b-bc10-per-call-runtime-call-marker.schema.v1.json` | per-call runtime call marker contract (pre-secret guard + redacted JSON marker output). |
| 4 | `ao_kernel/defaults/schemas/ri7-8b-bc10-6c-per-call-evidence.schema.v1.json` | 6c per-call evidence schema (token/cost recording per real billable call). |
| 5 | `ao_kernel/defaults/schemas/ri7-8b-bc10-6c-aggregate-evidence.schema.v1.json` | 6c aggregate evidence schema (sum across calls within window). |
| 6 | `ao_kernel/defaults/schemas/ri7-8b-bc10-6c-closure-evidence.schema.v1.json` | 6c closure decision schema (post-window closure decision). |
| 7 | `ao_kernel/defaults/schemas/ri7-8b-bc10-6c-defer-decision-evidence.schema.v1.json` | 6c defer decision schema (current authority — see §6). |
| 8 | `.github/workflows/bc10-real-adapter-usage-cost.yml` | Sequential single-job workflow, `workflow_dispatch` only, environment-bound, 12 pre-secret guards. |
| 9 | `scripts/ri78b_bc10_activation_window.py` | Window authorization activation guard (env observation + branch policy enforcement). |
| 10 | `scripts/bc10_run_scenarios.py` | Per-scenario runner. Fail-closed on zero usage / zero cost. |
| 11 | (pricing source, referenced no-touch guardrail asset) | Pricing source file + `gpp_status.pricing_source.source_digest` binding. |

**Authority references** (separate from the dormant asset inventory):

- [RI-7.8b-bc10-6c-DEFER-DECISION.v1.json](../.claude/plans/RI-7.8b-bc10-6c-DEFER-DECISION.v1.json)
  (PR #731 merged) — currently authoritative defer.
- [RI-7.8c-FINAL-PROMOTE-DECISION.v1.json](../.claude/plans/RI-7.8c-FINAL-PROMOTE-DECISION.v1.json)
  (PR #736 merged) — currently authoritative non-promotion.
- Predecessor merges: PR #695 (6a schema), PR #697 (6b infra + activation guard),
  PR #700 (6c schemas).

## 3. Preconditions

A reactivation supersession PR must record, in order, that **all** of the
following are satisfied before the workflow can be dispatched:

1. **Operator decision**: explicit, scoped, operator-bound supersession PR
   authored and approved through the path-sensitive review gate. Auto-mode
   classifier authority boundary enforced — agents may not flip the scoped
   permission.
2. **API-mode usage decision** (operator): the project is switching, or has
   switched, from CLI-only mode to API mode. The decision is recorded in the
   supersession PR body.
3. **Protected GitHub Environment**: the environment bound by the workflow
   exists and reports, via the Environments API:
   - `required_reviewers` present and non-empty
   - `prevent_self_review` = `true`
   - `admin_bypass` = `false`
   - `allowed_refs` includes only `main` (or `refs/heads/main`)
   - Exactly one deployment-branch-policy of type `branch` with name in
     `{main, refs/heads/main}`
   - `custom_branch_policies` = `true` (the `protected_branches` fallback is
     rejected — see `scripts/ri78b_bc10_activation_window.py::validate_environment_observation`).
4. **main-only branch policy**: the workflow rejects any other ref.
5. **Workflow content SHA binding**: the supersession PR records the SHA-256
   of the workflow content at the time of approval, and the runtime guard binds
   to that digest before any pre-secret guard step.
6. **Pricing source digest binding**: the supersession PR records the SHA-256
   of the pricing source file and binds it via the
   `gpp_status.pricing_source.source_digest` reference; runtime guards reject
   any mismatch.
7. **No-secret / no-raw-response boundary**: the supersession PR explicitly
   asserts that the workflow and scripts emit only redacted JSON markers; no
   provider response body, no token material, no `Authorization` header, no
   API key, no cookie, no signing key may appear in any artifact or log.

## 4. Cost guardrails (mirror the existing dormant assets exactly)

The following bindings are the **only** values authorized in a reactivation
supersession PR that uses this runbook as its template. Any deviation is a
separate, distinct operator-bound supersession PR with its own review.

| Guardrail | Value | Binding location |
|---|---|---|
| `model_allowlist` | `["openai/gpt-4o-mini"]` only | workflow `model` input + runner + `bc10_run_scenarios.py` |
| `max_output_tokens_cap` | `64` | workflow + runner |
| `max_usd` | `5.00` | workflow worst-case ceiling guard (`max_billable_calls_count * max_projected_call_cost <= max_usd`) |
| `max_billable_calls_count` | `4` | workflow worst-case ceiling guard |
| `max_distinct_runs` | `5` | window guard (distinct `workflow_dispatch` runs within the window) |
| `run_attempt` | `== 1` | workflow guard (no reruns) |

A future need for `gpt-4o`, larger `max_output_tokens_cap`, higher `max_usd`,
or more billable calls is **out of scope for this template**. Each such change
requires its own operator-bound supersession PR that explicitly widens the
relevant guardrail and that records the new cost ceiling math.

`gpt-4` and similarly expensive models remain forbidden under this template
regardless of any supersession scope.

## 5. Reactivation chain (ADR-0027 mirror discipline)

This is the **stepwise** authorization sequence. Each step depends on the
previous one being recorded with machine-enforced evidence.

### Step 1 — Operator-bound supersession PR (draft)

The operator authors a scoped supersession PR. The PR body records the
operator decision string and the precondition observations from §3. The PR
does not flip any top-level guard flag; it requests a **scoped** reactivation
permission only. The path-sensitive review gate decides admissibility.

### Step 2 — Pre-flight (cost guardrail decision)

The supersession PR records the §4 values as the active reactivation
guardrails. The PR explicitly confirms that the model allowlist is
`["openai/gpt-4o-mini"]`, that all six guardrails match the dormant asset
bindings, and that `gpt-4o` widening is out of scope for this reactivation.

### Step 3 — Workflow re-enable (workflow_dispatch only)

The `bc10-real-adapter-usage-cost` workflow becomes dispatchable through the
protected GitHub environment. The workflow file content is not modified; the
SHA recorded in Step 1 is the binding. `workflow_dispatch` is the only
trigger; no `push`, no `schedule`, no `pull_request`. `run_attempt == 1` is
enforced; reruns are rejected.

### Step 4 — Per-call evidence emit

Each real billable provider call emits:

- a pre-secret guard pass record (no `OPENAI_API_KEY` referenced before
  guards pass)
- a per-call runtime call marker matching
  `ri7-8b-bc10-per-call-runtime-call-marker.schema.v1.json`
- a per-call evidence record matching
  `ri7-8b-bc10-6c-per-call-evidence.schema.v1.json`
- token + cost recording is structured JSON; no provider response body is
  written

### Step 5 — Aggregate evidence (6c)

Once all dispatched per-call evidence records are written within the active
window, the aggregate record is emitted matching
`ri7-8b-bc10-6c-aggregate-evidence.schema.v1.json`. Aggregation sums token
and cost values; window bounds enforce `max_distinct_runs` and `max_usd`.

### Step 6 — Closure decision (6c)

The aggregate triggers a closure decision emit matching
`ri7-8b-bc10-6c-closure-evidence.schema.v1.json`. The decision is one of the
schema's allowed closure forms; defer remains available via a separate
defer-decision artifact (see §6).

### Step 7 — Scoped reactivation permission close

The scoped reactivation supersession entry transitions to a terminal state
(closed or aborted). This step does **not** flip any top-level guard flag; it
closes the scoped authority that the Step 1 supersession PR opened. The
baseline `live_adapter_execution_allowed=false`,
`production_platform_claim_allowed=false`, and `support_widening_allowed=false`
const pins are preserved across the entire reactivation chain.

## 6. Rollback / abort (supersession-over-reversal)

The repo prinsiple is **supersession over reversal**. The existing
[RI-7.8b-bc10-6c-DEFER-DECISION.v1.json](../.claude/plans/RI-7.8b-bc10-6c-DEFER-DECISION.v1.json)
is an immutable audit-trail artifact and **must not be rewritten**.

If a reactivation supersession PR must abort or roll back, the supersession
records a **new** artifact:

- a new abort / closure supersession record (a separate schema; if such a
  schema does not yet exist, a separate follow-up PR introduces it before any
  reactivation supersession PR can use it)
- the new record references the existing defer artifact by SHA-256 and
  closes the **scoped** reactivation authority that was opened by the
  Step 1 supersession PR
- the new record does **not** flip any top-level guard flag back; the
  baseline `false` const pins are already preserved (they were never flipped),
  so there is no "flip back" semantics — there is only "close the scoped
  authority that was opened"
- the historical defer decision and the historical final non-promotion
  decision remain authoritative as audit records

**Forbidden rollback patterns:**

- ❌ Rewriting `RI-7.8b-bc10-6c-DEFER-DECISION.v1.json`
- ❌ "Flipping `live_adapter_execution_allowed` back to `false`" (it never
  flipped to `true` at the top-level — only a scoped authority opened)
- ❌ Deleting per-call or aggregate evidence records
- ❌ Modifying `gpp_status.v1.json` to remove the supersession entry trace

## 7. Reactivation evidence is not promotion

A successfully completed BC-10 reactivation chain (per §5) produces real
billable usage/cost evidence. **This is not promotion.**

- It does not promote ao-kernel to a Beta tier.
- It does not promote ao-kernel to a Production tier.
- It does not widen `support_widening_allowed`.
- It does not claim `production_platform_claim_allowed`.
- The
  [RI-7.8c Final Promote Decision](../.claude/plans/RI-7.8c-FINAL-PROMOTE-DECISION.v1.json)
  (`ri78c_final_operator_non_promotion_keep_narrow_stable_runtime_authoritative`)
  remains authoritative.

A future production or Beta promotion requires a **separate** operator-bound
promotion supersession PR with its own scope, evidence, and review chain. The
BC-10 reactivation chain produces one of the inputs that such a promotion PR
would reference — but it is not the promotion itself.

## 8. No-touch list for any reactivation supersession PR

A reactivation supersession PR that uses this runbook as its template must
**not** modify the following surfaces:

- `.github/workflows/bc10-real-adapter-usage-cost.yml`
- `scripts/ri78b_bc10_activation_window.py`
- `scripts/bc10_run_scenarios.py`
- `ao_kernel/defaults/schemas/ri7-8b-bc10-*.schema.v1.json`
- `.claude/plans/gpp_status.v1.json` (other than recording a new scoped
  supersession entry under the existing `operator_bound_supersessions`
  collection — never modifying the M0–M6 closure metadata or the top-level
  guard flags)
- `ao_kernel/defaults/pricing/*` (pricing source files)
- Any guard flag JSON or top-level promotion decision artifact
- `.claude/plans/RI-7.8b-bc10-6c-DEFER-DECISION.v1.json` (immutable)
- `.claude/plans/RI-7.8c-FINAL-PROMOTE-DECISION.v1.json` (immutable)

If a reactivation supersession PR needs to widen any of the above, that change
is a **separate** operator-bound supersession PR with its own plan-time
consultation, scope, and review.

## 9. Verification (this runbook PR)

This runbook PR is doc-only. The verification surface is:

- markdown / link sanity (relative links to `.claude/plans/*` resolve)
- no-touch diff: `git diff --name-only` returns only this file
- no schema change
- no workflow change
- no script change
- no live API call
- no GitHub environment mutation
- no `gpp_status.v1.json` mutation
- no guard flag JSON mutation

## 10. Future operator chain

Operators considering reactivation should:

1. Read this template and §3, §4, §5 in full.
2. Author the Step 1 supersession PR.
3. Run the plan-time consultation gate (cross-AI peer review).
4. Confirm all §3 preconditions and §4 guardrail values inside the PR body.
5. Sequence Steps 2 through 7 from §5 with machine-enforced evidence.
6. If aborting, follow §6 supersession-over-reversal.
7. Treat the produced evidence as input to a future promotion supersession,
   not as promotion itself (§7).

---

**Authority refs**

- `.claude/plans/RI-7.8b-bc10-6c-DEFER-DECISION.v1.json` (PR #731 merged)
- `.claude/plans/RI-7.8c-FINAL-PROMOTE-DECISION.v1.json` (PR #736 merged)
- Predecessor merges: PR #695, PR #697, PR #700.

**Out of scope (separate operator-bound supersession PR required)**

- Model allowlist widening (e.g., `gpt-4o`).
- Cost ceiling widening (`max_usd`, `max_billable_calls_count`, etc.).
- Promotion claims (Beta or Production).
- Guard flag flips.
- Any modification to the dormant assets listed in §2.

**Example SHA-256 / digest values** mentioned anywhere inside a future
reactivation supersession PR are bound at the time of that PR's HEAD and are
not authoritative bindings here; this template only describes what must be
bound and where.
