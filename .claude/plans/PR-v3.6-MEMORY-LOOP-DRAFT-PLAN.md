# v3.6 — Memory Loop Closure (DRAFT v2)

**Status:** DRAFT v2 — absorbed Codex iter-1 conditional AGREE (8 revisions) → iter-2 AGREE
**Depends on:** v3.5.0 LIVE (D1 + D2a + D2b + D3 merged, consultation infrastructure complete)

---

## 1. Problem statement

v3.5 shipped the producer side of consultation memory:

- D1: canonical paths
- D2a: archive + normalize + integrity manifest
- D2b: opt-in canonical promotion → `consultation.<CNS-ID>` entries land in
  `.ao/canonical_decisions.v1.json`

But the **consumer side** is underdeveloped:

1. Callers who ingest canonical decisions get consultation entries for free
   today (`canonical_store.query(category=None)` already returns them), but
   there is no **type-safe convenience helper** for "just consultations".
   Consumers must string-match on `category="consultation"` or on the
   `consultation.` key prefix — both brittle.

2. The context pipeline (`compile_context`) treats all canonical entries as
   generic decisions. Consultation records carry rich metadata
   (`final_verdict`, `from_agent`, `to_agent`, `resolved_at`,
   `evidence_path` under provenance) that today is silently flattened into
   the compact value blob.

3. The MCP `ao_memory_read` tool returns unpaginated result lists
   (friction #3 in the scope research). A workspace with 100+ promoted
   consultations would blow up MCP payload limits on a wildcard read.

4. Operators enabling `policy_mcp_memory.read.enabled=true` + pattern
   `"consultation.*"` have no documented happy-path guide.

v3.6 closes the loop: reader facade + context-aware consumption +
pagination safeguard + docs.

---

## 2. Non-goals

- **No new MCP write surface.** Promotion flow (v3.5 D2b) stays the only
  path to add consultation entries. `ao_memory_write` already covers
  direct canonical writes for operators who need it.
- **No category registry schema.** Friction #1 from scope research
  (categories stored as scalar string with no validator) is a separate
  v3.7+ candidate — it touches more than consultations.
- **No delta/changelog subscription API.** Friction #5 (revision hash
  only signals "something changed") is a v4.x candidate.
- **No cross-workspace consultation replication.** Workspace-local only.
- **No schema migration for existing decision entries.** Consultation
  entries already ship with the correct shape from D2b.

---

## 3. Design overview (3 sub-PRs)

### E1 — Consultation reader facade (small PR)

**Goal:** type-safe, category-aware read helper consumers can use without
string-matching.

**New public API (`ao_kernel/consultation/promotion.py`):**

```python
@dataclass(frozen=True)
class PromotedConsultation:
    cns_id: str
    topic: str | None            # "unknown" backfill on producer side
    from_agent: str | None
    to_agent: str | None
    final_verdict: str          # "AGREE" or "PARTIAL"
    resolved_at: str | None
    record_digest: str | None   # prefixed "sha256:..." — from provenance
    evidence_path: str | None   # relative — from provenance
    confidence: float           # hydrated from top-level or derived from verdict
    promoted_at: str


def query_promoted_consultations(
    workspace_root: Path,
    *,
    verdict: str | None = None,       # filter AGREE-only etc.
    topic: str | None = None,
    include_expired: bool = False,
) -> tuple[PromotedConsultation, ...]:
    """Query promoted consultations from canonical store as typed
    records. Thin wrapper over `canonical_store.query(category="consultation")`;
    raises nothing on empty store (returns empty tuple).

    Hydration policy (Codex iter-1 revision #1 absorb) — strict core,
    lenient edges:
    - Rows missing ANY of `cns_id`, `final_verdict`, `promoted_at` are
      SKIPPED silently (reader never raises on malformed store content).
    - `topic`/`from_agent`/`to_agent` — producer backfills "unknown"
      (see `normalize.py::334`); reader leaves None-tolerant.
    - `confidence` — reads top-level field first; falls back to
      `verdict_confidence(final_verdict)` derivation.
    - `record_digest`/`evidence_path` — read from `provenance`; None
      when absent. Reader does NOT derive a fallback.

    Rationale: canonical store has no category registry/schema
    validation today; a reader that panics on ANY malformation would
    be the wrong failure mode for the consumer path.
    """
```

Existing `canonical_store.query` call surface unchanged. The facade does
the dataclass hydration + filtering so callers never touch raw dicts.

**Tests (7 pins — +1 for malformed-row skip):**
- Empty store → empty tuple
- Single AGREE entry → one record hydrated
- Mixed AGREE + PARTIAL → both returned, verdict filter works
- Topic filter case-insensitive substring
- `include_expired=False` respects canonical temporal lifecycle
- `include_expired=True` returns expired entries
- **NEW: Malformed row (missing `cns_id`) silently skipped, other
  rows still hydrated.**

### E2 — Context pipeline consultation lane (medium PR)

**Goal:** `compile_context` surfaces promoted consultations as a
first-class lane alongside session/canonical/facts.

**Compiler stays pure (Codex iter-1 revision #1 absorb).** The compiler
MUST NOT perform I/O. Consultation loading happens at the
**caller layer** — specifically in `compile_context_sdk` (which is
the SDK-facing wrapper, already an orchestrator) — which queries via
`query_promoted_consultations` and passes the result list into the
pure compiler as a new `consultations=` parameter.

**Changes (`ao_kernel/context/context_compiler.py` — pure renderer):**
- New optional parameter `consultations: Sequence[PromotedConsultation] = ()`
  on `compile_context(...)`. Compiler does NO loading; it only renders.
- New section header `## Consultations` in `_build_preamble` (reuses
  the existing section-header pattern — NO fresh `[consultation]`
  lane badge per Codex revision #2).
- Entries render as compact refs, e.g.
  `- [CNS-20260418-601] architecture AGREE (claude→codex, 2026-04-18)`
- Budget policy: when `consultations` pushes the preamble over the
  `max_tokens` cap, truncate the consultation block last-added-first-
  dropped before truncating other lanes.

**Changes (`ao_kernel/context/profile_router.py` — SSOT widening per
Codex iter-1 revision #7):**
- `ProfileConfig` dataclass gains `max_consultations: int` field.
- Per-profile defaults:
  - `PLANNING` + `REVIEW` → `max_consultations=10`
  - `STARTUP` + `TASK_EXECUTION` + `ASSESSMENT` → `max_consultations=3`
  - `EMERGENCY` → `max_consultations=0` (lean context invariant)
- Compiler reads this field from the resolved profile when given.

**Changes (`ao_kernel/context/agent_coordination.py::compile_context_sdk` —
I/O layer):**
- Before the pure compile call, query consultations via
  `query_promoted_consultations(workspace_root)`, slice by profile's
  `max_consultations`, prefer `AGREE`-first then `PARTIAL`, sort by
  `promoted_at` desc.
- Pass the resulting tuple into the compiler.

**Tests (8 pins):**
- `compile_context(consultations=())` omits `## Consultations` header
  (no empty-section artifact).
- 3 AGREE consultations passed → header present, 3 entries, sorted desc.
- `PLANNING` profile drives `max_consultations=10` via
  `ProfileConfig`; compile_context_sdk honours it.
- `EMERGENCY` profile → `max_consultations=0`; even populated store
  yields 0 consultations to compiler.
- Lane length budget: oversize preamble → consultations dropped
  before other lanes.
- `profile_router.ProfileConfig.max_consultations` is set per
  profile (SSOT test).
- `compile_context_sdk` wiring: store with 2 AGREE + 1 PARTIAL +
  `PLANNING` profile → all 3 reach compiler.
- **Malformed-store defence (Codex iter-1 revision #7 absorb):**
  two distinct canonical rows (under different store keys) whose
  hydrated `cns_id` values collide → reader dedupes the final set by
  `cns_id`, picking the most recent by `promoted_at`. Rationale:
  canonical key uniqueness is enforced upstream for the happy path,
  but a future store-format drift (or manual operator edit) could
  still produce two rows resolving to the same consultation id;
  reader is the last line of defence.

### E3 — MCP memory_read pagination + docs (small PR)

**Goal:** cap MCP payload size + document the consultation happy-path.

**Changes (`ao_kernel/mcp_server.py` + `_internal/mcp/memory_tools.py`):**
- `ao_memory_read` inputSchema gains (additive, no schema version
  bump — Codex iter-1 revision #4 confirmed):
  - `max_results` (integer, default 50, max 200) — hard cap at 200 to
    respect MCP payload limits.
  - `offset` (integer, default 0) — caller-managed pagination cursor.
- Response `data` block today already returns `{items, count}`
  (confirmed by Codex citing `memory_tools.py:268`). v3.6 widens to
  `{items, count, total, next_offset}` where:
  - `count` = entries in THIS page (unchanged semantics).
  - `total` = post-policy-filter total across the full query.
  - `next_offset` = cursor for the next page, or null when the store
    is exhausted under the current filter.
- Pagination logic lives in the handler (`handle_memory_read`);
  `canonical_store.query()` is NOT widened (Codex iter-1 revision #8
  — transport-level payload cap is out of storage/query concern).
- Rate limiter unchanged.

**Tests (5 pins):**
- Default `max_results=50` honoured when store has 100 entries
- `offset=50` returns second page
- `max_results > 200` clamped to 200
- `total` matches post-policy-filter count (and distinct from `count`
  when pagination kicks in)
- `next_offset` null when result exhausts store

**Docs (Codex iter-1 revision #5 absorb):**
- New `docs/CONSULTATION-QUERY.md` — short guide covering:
  1. Enable MCP memory policy (`read.enabled=true` + `consultation.*`
     pattern) at workspace level.
  2. `query_promoted_consultations` Python API example.
  3. `ao_memory_read` MCP pagination example.
  4. Semantic: AGREE vs PARTIAL confidence pairs.
- **Additional doc updates** (Codex revision #5 scope widening):
  - `CLAUDE.md` §9 Context Pipeline — "3-Lane Compilation" → "4-Lane
    Compilation" (add Consultation lane), link to CONSULTATION-QUERY.
  - `README.md` — bullet list of governance tools + link to query doc.
  - `docs/DEMO-SCRIPT.md` — replace "three-lane" references with
    "four-lane" and show consultation lane in the demo output.
  - `docs/EVIDENCE-TIMELINE.md` — cross-link (producer side → consumer
    side pointer).

---

## 4. Rollout

1. E1 plan-time CNS → AGREE → impl → post-impl review → merge
2. E2 plan-time CNS → AGREE → impl → post-impl review → merge
3. E3 plan-time CNS → AGREE → impl → post-impl review → merge
4. Release PR v3.6.0 (version bump + CHANGELOG + tag + PyPI)

Paralelism option: E1 + E3 independent (different files). E2 depends on
E1's reader facade so sequence is E1 → (E2 + E3 parallel Codex threads).

---

## 5. Resolved design decisions (iter-1 conditional AGREE)

All open questions resolved in iter-2:

1. **PromotedConsultation hydration** — strict core (`cns_id`,
   `final_verdict`, `promoted_at` required — missing rows SKIPPED
   silently), lenient edges (backfilled or derived).
2. **Section header** — reuse `## Consultations` pattern (no fresh
   `[consultation]` lane badge).
3. **EMERGENCY → max_consultations=0** — confirmed; lean-context
   invariant takes priority over "last AGREE always" until incident-
   tagging exists.
4. **Pagination additive-safe** — `data` already returns
   `{items, count}`; widen to add `total` + `next_offset` is pure
   additive. No schema bump needed.
5. **Docs** — dedicated `CONSULTATION-QUERY.md` + scope-widened to
   touch CLAUDE.md 3→4-lane, README, DEMO-SCRIPT.md, EVIDENCE-TIMELINE
   cross-link.
6. **3 sub-PRs** — kept; different risk profiles justify separate
   gates.
7. **Compiler purity** — compiler stays I/O-free; consultation load
   in `compile_context_sdk` + `ProfileConfig.max_consultations` SSOT
   field.
8. **Pagination handler-local** — `canonical_store.query()` NOT
   widened; transport-level payload cap is out of storage/query
   concern.

---

## 6. Scope summary

**IN:**
- `query_promoted_consultations` typed reader facade (E1)
- `compile_context` consultation lane + profile priorities (E2)
- `ao_memory_read` pagination + consultation query doc (E3)

**OUT:**
- Write-side policy changes (already shipped in v3.5 D2b)
- Category registry schema (v3.7+)
- Delta/changelog subscription API (v4.x)
- Cross-workspace replication (out of scope)
- Schema migration (no migration needed; D2b entries already correct shape)
