# Per-Call Audit Evidence (V5 Epic 2 E-2-2)

> Slice #847. One JSONL audit row per (would-be) LLM call. **Infrastructure
> only**: `live_adapter_execution` is `const false`; the writer never makes a
> network call and never flips a guard flag. Builds on the E-2-1 envelope
> (foreign-keys via `envelope_digest`).

## Schema

`ao_kernel/defaults/schemas/per_call_audit.schema.v1.json` (Draft 2020-12,
strict closure on every object). One row records: provider/model/request,
token usage, `actual_cost_usd` (decimal-string, 8 dp, **required**), latency,
a provider-lifecycle `status`, and a **separate** `cost_breach_state`.

`status` vs `cost_breach_state` are deliberately distinct:

| Field | Domain | Meaning |
|---|---|---|
| `status` | `ok` / `error` / `stub_emitted` / `dry_run_emitted` | provider call lifecycle |
| `cost_breach_state` | `ok` / `soft_breached` / `hard_breached` / `not_applicable` | whether cost recording crossed a ceiling threshold |

Conditional invariants (`allOf`), aligned to the E-2-3 breach contract:

- `cost_breach_state == "soft_breached"` ⇒ `cost_breach_handling` required and
  must be the **object** form `{decision, decided_by, decided_at}`
  (`decided_by` ∈ {operator, policy_default, caller_module}).
- `cost_breach_state == "hard_breached"` ⇒ `status == "error"` **and**
  `cost_breach_handling == null` (an unconditional abort row — no caller
  decision; written to both JSONL files).
- `ok` / `not_applicable` ⇒ `cost_breach_handling` is null or absent (a
  populated object is rejected — it is populated only on a soft breach).

Fail-closed: a missing or float `actual_cost_usd` fails schema validation, so
the row is rejected (CLAUDE.md değişmez #1). Timestamps use the same
calendar-coupling RFC3339 regex as E-2-1 (leap-year validity is a recompute-time
concern, see `docs/LIVE-ADAPTER-ENVELOPE.md`).

## Writer

`ao_kernel/_internal/evidence/per_call_audit.py` — `record_call(row, *,
workspace_root=None)` is a **pure serializer**:

- Validates the row and **raises `PerCallAuditValidationError` before any
  write** — a malformed row never lands on disk (fail-closed).
- **Library mode** (`workspace_root=None`): skips persistence, returns
  `{"persisted": False, "mode": "library", "paths": []}` (single-process
  contract).
- **Workspace mode**: appends each row as a single pre-encoded `os.write` to a
  fd opened `O_WRONLY|O_CREAT|O_APPEND` (POSIX guarantees an `O_APPEND` write
  below `PIPE_BUF` is atomic, so concurrent writers never interleave a partial
  line) + best-effort `fsync`, to `evidence/per_call_audit.jsonl`. A
  `hard_breached` row is ALSO appended to `evidence/cost_hard_breach.jsonl` so
  the abort path is cross-referenced. A concurrent-append test asserts N writers
  produce N parseable lines.

The writer does **not** decide breaches and does **not** raise
`CostCeilingExceeded` — that is the E-2-3 cost-ceiling module, which calls this
writer (try-finally) to record the fail-closed row before raising. This keeps
E-2-2 free of a forward dependency on E-2-3.

## What this slice does NOT do

- Does NOT make a real provider call (records would-be calls under stub/dry_run).
- Does NOT enforce a cost ceiling (that is E-2-3, which drives `cost_breach_state`).
- Does NOT flip any guard flag.

## Verification

`tests/test_per_call_audit.py` — schema health, guard pins, strict closure
(parametrized), required-field enforcement (parametrized), const/enum pins,
decimal/sha/timestamp fail-closed, `allOf` conditionals, and writer contract
(fail-closed-before-write, library skip, cumulative append, hard-breach
cross-reference).

## Cross-references

- Envelope (E-2-1): `docs/LIVE-ADAPTER-ENVELOPE.md`
- Cost ceiling (next, E-2-3): drives `cost_breach_state` + raises `CostCeilingExceeded`
- Epic 2 plan: `.claude/plans/EPIC-2-LIVE-ADAPTER-EXECUTION.md` (E-2-2)
