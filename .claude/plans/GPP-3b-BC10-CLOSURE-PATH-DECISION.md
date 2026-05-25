# GPP-3b — BC-10 Closure Path Decision

> **Status:** closure path decided; infaz reserved for GPP-3c.
> **Slice:** `GPP-3b` (Faz 2 of GPP-3).
> **Issue:** to be opened under CC-13 enforcement and pinned on commit.
> **Decision:** `bc10_policy_exception_authoritative_no_live_adapter_execution_no_support_widening_no_production_claim`.
> **Effective:** see `gpp_status.v1.json::current_wp.closeout_at` once Faz 2 lands.

## Purpose

GPP-3b records the closure path for GP-5.9 `BC-10` ("Real-adapter
cost/token evidence is unavailable because protected evidence is
absent") under the autonomous GPP-3 chain. GPP-3a installed the
schema and simulated path. GPP-3b chooses how BC-10 becomes
**not-a-promotion-blocker** without requiring a live adapter run on
the autonomous path. GPP-3c executes the chosen path.

This slice **does NOT**:

- mutate `scripts/gp5_platform_claim_decision.py` (BC-10 stays
  `status="blocked"` until GPP-3c)
- bump `gp5-production-platform-claim-decision.schema.v1.json` (the
  `success_criterion.status` enum addition is reserved for GPP-3c as
  an additive non-breaking widening; ayrı v2 gerekmez)
- execute a live adapter (Option X is operator-bound and outside the
  autonomous path)
- widen support or claim production platform readiness

## Closure Path Comparison

Three options were considered for closing GP-5.9 BC-10:

### Option X — Live Run Authority (deferred, NOT autonomous)

- **What:** operator authorizes a one-shot live adapter execution
  (Anthropic Claude API or selected provider) and emits a
  schema-valid evidence artifact with `evidence_class="live"`.
- **Cost:** explicit `live_adapter_execution_allowed=true` flip
  (operator-only PR per CC-9), GitHub Actions secrets setup, cost-cap
  script ($X / N calls), `live_adapter_execution_allowed=false`
  revert PR. Three operator-bound coordination points minimum.
- **BC-10 outcome:** `status="pass"` with real evidence.
- **Decision:** **deferred**. Live execution requires operator
  authority and is explicitly outside the autonomous GPP-3 chain. A
  future operator-bound slice may pursue this independently; that
  slice would supersede this GPP-3b decision and reclassify BC-10
  from `exception` back to `pass`.

### Option Y — Policy Exception Authority (CHOSEN)

- **What:** record `BC-10` as a deliberate policy exception. The
  decision recognizes that production-platform claim does NOT require
  live adapter evidence under the autonomous path; instead the schema
  + simulated path + cost subsystem (`ao_kernel/cost/ledger.py`,
  `ao_kernel/cost/cost_math.py`, `ao_kernel/cost/catalog.py`) plus
  schema-conformant evidence shape are accepted as **policy-aware
  exception**.
- **Cost:** zero new code or live execution. Only `gp5_platform_claim_decision.py`
  reclassification + schema enum widening + docs/known-bugs/support-boundary wording sync.
- **BC-10 outcome:** `status="exception"` (new enum value, additive
  non-breaking widening of `success_criterion.status`). The promotion
  blocker `real_adapter_usage_and_cost_evidence_missing` is removed
  from BC-10's blocker list.
- **Decision:** **authoritative** for GPP-3 closure.

### Option Z — Extended Simulated Evidence (SUPPORTING, NOT authoritative)

- **What:** generate an extended simulated evidence matrix (e.g.
  10+ permutations of complete + unavailable_reason branches, multiple
  catalog source_types) and propose it as authoritative readiness
  evidence for BC-10.
- **Risk per Codex:** "Z'yi 'simulated evidence sufficient for non-live
  path' diye BC-10 pass gibi sunmak riskli; BC-10'un adı real-adapter
  evidence." Promoting simulated evidence to authority blurs the
  distinction between schema readiness and live execution evidence.
- **Decision:** **supporting only**. The GPP-3a schema + 30 drift
  guards + simulated emitter + ledger converter together constitute
  readiness evidence. Z does not need a separate matrix expansion in
  GPP-3c; the existing 30 tests already exercise complete +
  unavailable branches, format constraints, allOf binds, const-false
  guards, CLI smokes, and ledger-event conversion.

## Decision (Authoritative)

GP-5.9 `BC-10` will be closed under **Option Y — Policy Exception
Authority** with **Option Z as supporting readiness evidence**
(schema + simulated path bundled in GPP-3a). Option X (live run)
remains deferred and operator-bound.

Decision string:

```text
bc10_policy_exception_authoritative_no_live_adapter_execution_no_support_widening_no_production_claim
```

The string asserts:

- Authority is policy exception (Option Y), not live evidence
- No live adapter execution under this decision
- No support widening
- No production platform claim

## BC-10 Reclassification Plan (executed in GPP-3c)

GPP-3c will:

1. Widen `gp5-production-platform-claim-decision.schema.v1.json`
   `success_criterion.status` enum from `["pass", "partial", "blocked"]`
   to `["pass", "partial", "blocked", "exception"]` as an additive
   non-breaking change. Schema_version stays at v1.
2. Update `scripts/gp5_platform_claim_decision.py` to emit
   `BC-10 status="exception"` with summary "policy exception
   accepted for no-live autonomous path" and `blockers=[]`.
3. Update affected tests (`tests/test_gp5_platform_claim_decision.py`)
   to validate the new `exception` enum path.
4. Update `docs/PUBLIC-BETA.md`, `docs/KNOWN-BUGS.md`, and the
   relevant Public Beta support boundary wording to reflect the
   policy exception.
5. Open the GPP-3c decision record under CC-13 with an issue anchor.

GPP-3c **MUST NOT**:

- flip `support_widening_allowed` / `production_platform_claim_allowed`
  / `live_adapter_execution_allowed` (CC-6 enforcement)
- remove BC-1 or any other blocker from `gp5_platform_claim_decision.py`
- claim that simulated evidence is live adapter evidence
- run a live adapter on the autonomous path

## Guard Flag Invariants (unchanged after GPP-3b)

- `support_widening_allowed`: `false`
- `production_platform_claim_allowed`: `false`
- `live_adapter_execution_allowed`: `false`

## Simulated Evidence Sufficiency (Option Z)

The GPP-3a artifact set already provides:

- `real-adapter-usage-cost-evidence.schema.v1.json` — root oneOf
  enforces complete vs unavailable branch invariants
- `scripts/real_adapter_usage_evidence.py emit-simulated` — produces
  schema-valid artifacts with `evidence_class="simulated"` and
  `live_adapter_execution=false`
- `scripts/real_adapter_usage_evidence.py from-ledger-event` — converts
  existing `spend-ledger.v1` events into evidence artifacts
- `tests/test_real_adapter_usage_cost_evidence.py` — 30 drift guards
  (schema, branches, guards, formats, CLI, converter)

The cost subsystem (`ao_kernel/cost/`) computes deterministic costs
from the price catalog (`ao_kernel/cost/catalog.py`) using
`compute_cost` in `ao_kernel/cost/cost_math.py`. The
`ao_kernel/metrics/registry.py::ao_llm_usage_missing_total` counter
and `_apply_usage_missing` derivation already record usage-missing
events at runtime.

This evidence stack supports — but does not authorize — BC-10
exception classification. Authority comes from the explicit policy
decision in this record.

## Supersession Rules

Option X (live run) remains available as a future operator-bound
supersession. If a later slice authorizes live adapter execution:

1. Operator opens an explicit PR flipping
   `live_adapter_execution_allowed=true` with a clear declaration and
   audit comment
2. A protected workflow runs the live adapter with cost-cap + N-call
   limits
3. Real evidence is emitted with `evidence_class="live"` and the
   GPP-3a schema
4. Operator opens a follow-up PR flipping
   `live_adapter_execution_allowed=false` back
5. BC-10 reclassifies from `exception` to `pass` in a separate
   supersession decision record

Until that operator-bound slice lands, BC-10 stays `exception`.

## Non-Goals

This slice (GPP-3b) explicitly does NOT:

1. mutate `scripts/gp5_platform_claim_decision.py`
2. bump `gp5-production-platform-claim-decision.schema.v1.json`
3. update `docs/SUPPORT-BOUNDARY.md` or `docs/KNOWN-BUGS.md`
4. execute a live adapter or run any cost-incurring API call
5. flip any of the three GP-5/GPP-9 promotion guard flags
6. open the GPP-3c issue (deferred to GPP-3c slice)
7. claim that simulated evidence equals live adapter production
   evidence

All of those are GPP-3c work.

## Cross-References

- `.claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md` — program SSOT
- `.claude/plans/gpp_status.v1.json` — machine-readable status
- `.claude/plans/GPP-3a-USAGE-COST-EVIDENCE-SCHEMA.md` — Faz 1 record
- `.claude/plans/GP-5.9-PRODUCTION-PLATFORM-CLAIM-DECISION.md` — BC-1..BC-10 baseline
- `.claude/plans/PROGRAM-CHANGE-CONTROL.md` — CC-1 through CC-13
- `ao_kernel/defaults/schemas/real-adapter-usage-cost-evidence.schema.v1.json` — GPP-3a schema
- `ao_kernel/defaults/schemas/gp5-production-platform-claim-decision.schema.v1.json` — to be widened in GPP-3c
- `scripts/gp5_platform_claim_decision.py` — to be reclassified in GPP-3c

## Audit Trail

| Field | Value |
|---|---|
| Implementer AI | Claude (Anthropic) |
| Reviewer AI | Codex (OpenAI) — thread `019e5c36` plan-time iter-1 AGREE |
| Worktree | `codex/gpp-3b-bc10-closure-path-decision` |
| Base SHA at branch open | `67472c1` |
| Cross-provider AI review HARD RULE | satisfied (CC-2) |
| Non-author code-owner approval | required at merge time (CC-3) |
| Admin bypass attempted | `false` (CC-4) |
