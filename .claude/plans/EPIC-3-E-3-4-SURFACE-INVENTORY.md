# E-3-4 — Support Surface Inventory (decision record)

> V5 Epic 3, slice #856. Docs-only. A narrative companion to
> `docs/SUPPORT-BOUNDARY.md` that **restates** today's narrow-stable boundary,
> inventories the five future-widening surface dimensions, and lists per-dimension
> **prerequisites** — while announcing **no** widening. No guard-flag flip.

## Deliverables

- `docs/SUPPORT-SURFACE-INVENTORY.md` (5 sections: current boundary restated;
  surface dimensions inventoried; prerequisites per dimension; boundary
  disclaimer; cross-references).
- `tests/test_support_surface_inventory_doc.py` (9 invariants: presence, five
  surface classes, boundary reference, prerequisites, no-announcement disclaimer,
  expanded no-production-claim language guard, no guard-flag flip, no workflow
  mutation, and no public boundary / beta tier mutation).

## Key decisions

1. **Restate, don't re-claim.** §1 points to `SUPPORT-BOUNDARY.md` §1.1 as the
   single source of truth for the ST-2 freeze; this doc is a pointer, not a second
   authority. Out of scope: any change to `SUPPORT-BOUNDARY.md` §1.1 freeze
   language or `PUBLIC-BETA.md` tier rows (Epic 9 supersession-only).
2. **Prerequisites, not promises.** §3 reads the per-class evidence thresholds
   from the E-3-1 v1 schema and frames them as what widening *would require*, not
   what is planned.
3. **No-announcement disclaimer** (§4) defers all widening authority to the Epic 9
   operator-bound supersession PR; the test asserts the **exact** disclaimer
   sentence plus the "Epic 9" defer.
4. **No claim language.** The test rejects the expanded Epic 3 F7 phrase set:
   production-ready, production-safe, production-certified, production-grade,
   fully-supported, `GA`, generally available, officially supported, stable
   support, beta exit, supported today, and ready for production.
5. **Prerequisites bound per row.** The test reads each prerequisite from the §3
   table row for its own `surface_class` (not anywhere in the doc) and enforces
   the provider `≥ 3` live-test threshold (Codex E-3-4 absorb).

## Cross-AI review

Implementer codex (openai) → reviewer claude (anthropic). See local review
evidence and PR evidence.
