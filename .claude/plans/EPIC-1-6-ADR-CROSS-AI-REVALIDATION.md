# V5 Epic 1 E-1-6: Retro ADR Cross-AI Revalidation

> **Cross-AI revalidation AGREE** — Codex thread `019e874f` + Anthropic Plan sub-agent (independent)
> **Implementer:** Anthropic Claude / **Reviewer:** OpenAI Codex (post-impl, cross-AI peer review)
> **Risk class:** conservative low-risk (frontmatter + schema additive; decision body byte-equal)

## 1. Scope

Promote 4 retrospective ADRs from `back_populated_pending_cross_ai_revalidation`
to `cross_ai_validated` by recording per-provider cross-AI revalidation
verdicts in the front-matter. Schema is extended with a typed
`cross_ai_revalidation` block; the parse layer is updated to coerce YAML
implicit-timestamp datetime objects to ISO strings for the new
`revalidated_at` + `reviewers[].reviewed_at` fields. Decision bodies are
byte-equal (revalidation is review-only).

**In scope:**
- 4 ADR frontmatter updates (ADR-0001..0004 → `cross_ai_validated`)
- Schema additive extension: `cross_ai_revalidation` block + 2 new `review_status` enum values
- Parse-layer datetime normalization for the new block
- 33 invariant tests (8 schema validity + 3 schema negative + 5 instance content + 2 governance)

**Out of scope (ZERO TOUCH):**
- ADR-0005 (Keep-a-Changelog) — separate revalidation slice, deferred
- New ADR creation — review-only
- ADR decision body mutation (byte-equal enforced by `test_no_adr_decision_section_mutation`)
- `.github/workflows/*`
- Mavis (MiniMax) reviewer — not spawnable in this session; optional follow-up

## 2. Cross-AI Revalidation Verdicts

| ADR | Codex (OpenAI) thread `019e874f` | Anthropic Plan sub-agent | Consensus |
|---|---|---|---|
| ADR-0001 AO-MA-SPM adoption | AGREE | AGREE | `cross_ai_validated` |
| ADR-0002 Fail-closed + recompute-not-trust | AGREE | AGREE | `cross_ai_validated` |
| ADR-0003 Native import-only contract | AGREE | AGREE | `cross_ai_validated` |
| ADR-0004 Cross-AI implementer ≠ reviewer provider | AGREE | AGREE | `cross_ai_validated` |

Both reviewers cite specific text from each ADR (Decision section line numbers, Consequences, Alternatives Considered). The Anthropic reviewer is structurally compliant with ADR-0004 itself (independent Anthropic session, distinct from implementer Claude session).

## 3. Schema Extension (additive)

**New `review_status` enum values (per Codex Q6 revise):**
- `cross_ai_revalidation_revise_required` — at least one reviewer REVISE
- `cross_ai_revalidation_red_blocked` — at least one reviewer RED

**New `cross_ai_revalidation` block (per Codex Q5 revise):**
- `schema_version: const "ao-ma-adr-cross-ai-revalidation.v1"`
- `revalidated_at`: RFC3339 UTC
- `scope: const "retrospective_attestation_only"`
- `decision_mutation: const false`
- `reviewers: minItems 2 + uniqueItems` (each with provider/agent/reviewed_at/verdict/rationale + optional thread_ref/evidence_ref)
- `consensus`: enum (derived from reviewer verdicts — recompute-not-trust per ADR-0002)

**allOf if/then guards:**
- `review_status in {cross_ai_validated, ..._revise_required, ..._red_blocked}` → `cross_ai_revalidation` REQUIRED
- `review_status in {original, back_populated_pending_cross_ai_revalidation}` → `cross_ai_revalidation` FORBIDDEN

## 4. Parse Layer Normalization

`ao_kernel/orchestration/quality_profile.py::parse_adr` extended to coerce
PyYAML implicit-timestamp objects to ISO strings for:
- `cross_ai_revalidation.revalidated_at` (datetime → RFC3339)
- `cross_ai_revalidation.reviewers[].reviewed_at` (datetime → RFC3339)

Mirrors the existing pattern for `back_populated_at`. The existing
`test_bundled_adrs_parse_and_index_valid` test continues to pass.

## 5. Implementation Artifacts

| File | LOC | Purpose |
|---|---|---|
| `ao_kernel/defaults/schemas/ao-ma-adr.schema.v1.json` | +75 | `cross_ai_revalidation` block + 2 enum values + 2 allOf branches + `$defs/cross_ai_reviewer` |
| `.claude/plans/adr/ADR-0001-...md` | +18 lines | Frontmatter only (decision body byte-equal) |
| `.claude/plans/adr/ADR-0002-...md` | +18 lines | Frontmatter only |
| `.claude/plans/adr/ADR-0003-...md` | +18 lines | Frontmatter only |
| `.claude/plans/adr/ADR-0004-...md` | +18 lines | Frontmatter only |
| `ao_kernel/orchestration/quality_profile.py` | +25 | Parse-layer datetime normalization for new block |
| `tests/test_adr_cross_ai_revalidation.py` | ~290 | 33 invariants |
| `.claude/plans/EPIC-1-6-ADR-CROSS-AI-REVALIDATION.md` | this | Plan doc |

## 6. Test Sections (33 invariants)

| Section | Count | Focus |
|---|---|---|
| 1. Schema validity | 8 | Draft 2020-12 + 5-value enum + block additionalProperties:false + 3 const pins + reviewer $defs + reviewers minItems=2 + 3-value consensus enum + 3 guard flags const false |
| 2. Schema negative | 3 | cross_ai_validated without block + block when pending + reviewer with invalid verdict |
| 3. ADR instance content (parametrized 5×4=20) | 5 | 4 ADRs reach cross_ai_validated + 2 distinct provider reviewers (openai + anthropic) AGREE + each ADR validates against schema + 3 guard flags preserved + consensus matches reviewers (recompute-not-trust per ADR-0002) |
| 4. Governance ZERO TOUCH | 2 | No `.github/workflows/` mutation + no ADR decision body mutation (frontmatter-only diff) |

## 7. Why Cross-AI Revalidation Was Recordable Now

ADR-0004 (Cross-AI peer review HARD RULE) was enforced retrospectively
for ADR-0001..0004 themselves: the original adoption was Claude +
Codex + Operator. The revalidation evidence is the **second
adversarial sweep** ADR-0004 prescribes for any code/governance change.
The recompute-not-trust invariant of ADR-0002 is reflected in the
`consensus` field — the schema lists it but tests recompute it from
per-reviewer verdicts.

## 8. References

- Codex revalidation thread: `019e874f`
- HARD RULE Cross-AI Peer Review (2026-05-05 + 2026-05-14)
- HARD RULE No Fake Work / Uzun Vadeli Kalıcı Çözüm
- ADR-0002 (recompute-not-trust) reflected in test `test_adr_consensus_matches_reviewers`
- ADR-0004 (cross-AI HARD RULE) reflected in test `test_adr_has_two_reviewers_distinct_provider`
