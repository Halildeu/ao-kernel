# E-3-1 — Support Widening Evidence Schema (decision record)

> V5 Epic 3, slice #853. Infrastructure-only. Ships the versioned evidence
> schema + pure parse/recompute/verify module + read-only CLI that make a future
> support-widening decision *decidable* with real evidence — **without flipping
> any guard flag**. `support_widening` is `const false` at the schema AND
> re-asserted at runtime (ADR-0002 recompute-not-trust).

## Deliverables

- `ao_kernel/defaults/schemas/support-widening-evidence.schema.v1.json`
- `ao_kernel/_internal/support_widening/evidence.py` (`parse_v1`, `recompute_v1`, `verify_v1`)
- CLI `ao-kernel support-widening evidence validate <path> [--recompute]` (read-only)
- `tests/test_support_widening_evidence_v1.py` (19 invariants)

## Key design decisions

1. **Per-class shapes live in `$defs`, referenced from the root `allOf`.** The
   discriminated containers (`evidence_dimensions`, `recompute_inputs.raw_dimensions`)
   are bare `{type:object}` at their base and get their closed shape from a
   per-`surface_class` `$defs` entry via `if/then`. A base `additionalProperties:false`
   there would reject the allOf-supplied keys (the JSON-Schema sibling-applicator
   trap). Effective closure is proven by `test_wrong_class_shape_rejected`; every
   *shape-defining* node (one that declares `properties`) carries
   `additionalProperties:false` + `unevaluatedProperties:false`
   (`test_recursive_strict_closure_at_every_shape_defining_node`, which also
   asserts exactly the two known bare delegated containers exist).

2. **No remote `$ref`.** Only local `#/$defs/...`. A remote `$ref` would let a
   controlled endpoint alter the contract at validation time (TOCTOU);
   `test_no_remote_ref` walks the schema and rejects any `http(s)` ref.

3. **`recompute_inputs` is not a widening back-door.** The module
   (`recompute_v1`) walks every key in `recompute_inputs` and rejects any matching
   the forbidden-widening regex, and re-derives `evidence_dimensions` from
   `recompute_inputs.raw_dimensions` (never trusting the stored value).

4. **Guard pins are double-enforced.** Schema `const false` +
   `_RUNTIME_PINS` re-assert in `parse_v1`. To emit `support_widening: true` a
   producer must use a *different* v2 schema (Epic 9 supersession), making the
   policy structurally enforceable, not process-dependent.

5. **`verify_v1` re-hashes on-disk refs from disk** (never trusts a stored hash).

## Out of scope (later slices)

- Harness execution (E-3-2), advisory CI matrix (E-3-3), surface inventory doc
  (E-3-4), consensus checklist (E-3-5), recompute-not-trust validator wiring
  (E-3-6), and the v2 supersession schema (Epic 9). No guard-flag flip anywhere.

## Cross-AI review

Implementer claude (anthropic) → reviewer codex (openai). See PR evidence.
