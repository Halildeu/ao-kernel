# GPP-3a — Real-Adapter Usage and Cost Evidence Schema

> **Status:** schema-ready, simulated-path-ready; BC-10 NOT yet closed.
> **Slice:** `GPP-3a` (Faz 1 of GPP-3).
> **Decision:** `real_adapter_usage_cost_schema_ready_live_run_pending_no_support_widening`.
> **Effective:** see `gpp_status.v1.json::current_wp.closeout_at` once Faz 1 lands.

## Purpose

GPP-3 closes or defers GP-5.9 `BC-10`, the "Real-adapter cost/token
evidence is unavailable because protected evidence is absent" blocker.
Faz 1 (this slice) installs the schema, simulated path, and supporting
docs so that GPP-3b (decision) and GPP-3c (closure infaz) can land
without re-litigating the evidence shape.

This slice **does NOT** close BC-10. `scripts/gp5_platform_claim_decision.py`
still emits `BC-10 blocked` after this slice; only GPP-3c's chosen
closure path (policy exception or extended simulated evidence as
authority) reclassifies BC-10.

## Scope

1. `ao_kernel/defaults/schemas/real-adapter-usage-cost-evidence.schema.v1.json` — new schema
2. `scripts/real_adapter_usage_evidence.py` — emitter + ledger converter + validator (three CLI modes: `emit-simulated`, `from-ledger-event`, `validate`)
3. `tests/test_real_adapter_usage_cost_evidence.py` — schema + script drift guards
4. `docs/PUBLIC-BETA.md` — BC-10 wording update ("schema-ready, not closed")
5. `docs/SUPPORT-BOUNDARY.md` — `unavailable_reason` taxonomy
6. `docs/KNOWN-BUGS.md` — BC-10 status update
7. `.claude/plans/gpp_status.v1.json` — `current_wp` migrates from GPP-2 closed to GPP-3a active; GPP-2 closeout preserved in `completed_wps`; M3 milestone stays `pending`
8. `.claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md` — progress table + section reference
9. `tests/test_gpp_next.py` — drift-guard rewrite for the new `current_wp` truth
10. `local-ai-review-evidence.v1.json` — reviewer evidence for this PR

## Non-Goals

1. No live adapter execution (GPP-3a is the schema/simulated slice; live is reserved for GPP-3c Option X, not on the autonomous path)
2. No `live_adapter_execution_allowed` flag flip (CC-6 enforcement preserved)
3. No `support_widening` or `production_platform_claim` change (both stay `false`; PROGRAM-CHANGE-CONTROL.md CC-6)
4. No `scripts/gp5_platform_claim_decision.py` BC-10 reclassification (deferred to GPP-3c)
5. No spend ledger schema mutation (the existing `spend-ledger.schema.v1.json` is read-only here; evidence schema cross-references its events via `linked_spend_ledger_events`)
6. No GitHub branch ruleset mutation (CC-9 enforcement preserved)

## Schema Contract (`real-adapter-usage-cost-evidence.v1`)

The schema enforces two mutually exclusive evidence shapes via a root `oneOf`:

| Branch | Trigger | Required state |
|---|---|---|
| **Complete** | `unavailable_reason == null` | `prompt_tokens` integer ≥ 0; `completion_tokens` integer ≥ 0; `total_cost_usd` decimal-string (e.g. `"0.00123400"`) |
| **Unavailable** | `unavailable_reason in {usage_missing, token_unavailable, cost_unavailable}` | `prompt_tokens`, `completion_tokens`, `total_cost_usd` all explicitly `null` |

`evidence_class` ↔ `live_adapter_execution` consistency enforced via `allOf` if/then:

- `evidence_class == "simulated"` ⇒ `live_adapter_execution == false`
- `evidence_class == "live"` ⇒ `live_adapter_execution == true`

Three guard fields are `const false`:

- `support_widening`
- `production_platform_claim`
- (live_adapter_execution is `const false` only in the simulated branch via allOf; in the live branch it is `const true`)

The schema cross-references `spend-ledger.v1.json` events via the optional
`linked_spend_ledger_events` array (null on the simulated path; one or
more entries on the live path). Each entry carries `run_id`, `step_id`,
optional `attempt`, and `billing_digest` (sha256 prefix).

The `pricing_source` is a structured object with `source_type` enum
(`bundled_catalog` | `workspace_catalog` | `operator_supplied` |
`simulated_fixture`), `source_ref` string, optional `source_digest`
(sha256), and optional `retrieved_at` (ISO 8601).

## Unavailable Reason Taxonomy

| Reason | Trigger |
|---|---|
| `usage_missing` | The adapter's `normalize_response` did not surface token counts at all (most common with self-hosted or unusual providers) |
| `token_unavailable` | Tokens were reported by the adapter but the values are malformed or incomplete (e.g. `tokens_input` missing while `tokens_output` is present) |
| `cost_unavailable` | Tokens are reported correctly but no price catalog entry matched the model/provider, so `cost_math.compute_cost` cannot run |

All three reasons drop the artifact into the unavailable branch with
`prompt_tokens`, `completion_tokens`, and `total_cost_usd` explicitly
`null`. The schema rejects any artifact that names a reason but still
carries non-null usage/cost data, and any artifact that omits the
reason but lacks usage/cost data.

## Cross-References

| Concept | Path |
|---|---|
| Spend ledger event schema | `ao_kernel/defaults/schemas/spend-ledger.schema.v1.json` |
| Cost math | `ao_kernel/cost/cost_math.py` |
| Cost catalog | `ao_kernel/cost/catalog.py` |
| Usage-missing counter | `ao_kernel/metrics/registry.py::ao_llm_usage_missing_total` |
| Usage derivation | `ao_kernel/metrics/derivation.py::_apply_usage_missing` |
| GP-5.9 BC-10 evaluator | `scripts/gp5_platform_claim_decision.py` (BC-10 hardcoded `status="blocked"` until GPP-3c) |
| Change control | `.claude/plans/PROGRAM-CHANGE-CONTROL.md` (CC-1 through CC-13) |
| Rollback runbook | `docs/ROLLBACK-RUNBOOK.md` |
| Retrospective template | `.claude/plans/_TEMPLATES/RETROSPECTIVE-TEMPLATE.md` |
| Closeout record (GPP-2) | `.claude/plans/GPP-2D-7-AO-GATE-9-GPP-CLOSEOUT.md` |

## Next Slices

| Slice | Purpose | Authority |
|---|---|---|
| GPP-3b | Record BC-10 closure path decision: Option Y (policy exception) or Option Z (extended simulated evidence as supporting readiness) | Codex cross-AI istişare + non-author approval |
| GPP-3c | Execute the chosen path: reclassify `gp5_platform_claim_decision.py` BC-10 from `blocked` to `exception`; sync docs | Cross-AI peer review + non-author approval |

Option X (live run) is operator-bound and lives outside the autonomous
path. It is recorded as deferred-by-design in GPP-3b's decision record.

## Guard Flags (unchanged after GPP-3a)

- `support_widening_allowed`: `false`
- `production_platform_claim_allowed`: `false`
- `live_adapter_execution_allowed`: `false`

These remain `false`. GPP-3a does NOT widen support, claim production
platform readiness, or authorize live adapter execution.

## Audit Trail

| Field | Value |
|---|---|
| Implementer AI | Claude (Anthropic) |
| Reviewer AI | Codex (OpenAI) — thread `019e5c0f` plan-time iter-1 absorb |
| Worktree | `codex/gpp-3a-usage-cost-evidence-schema` |
| Base SHA at branch open | `94bbdec` |
| Cross-provider AI review HARD RULE | satisfied (CC-2) |
| Non-author code-owner approval | required at merge time (CC-3) |
| Admin bypass attempted | `false` (CC-4) |
