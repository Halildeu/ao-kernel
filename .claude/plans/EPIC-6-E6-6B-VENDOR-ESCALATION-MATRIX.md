# V5 Epic 6 E-6-6b: Vendor Escalation Matrix

> **Implementer:** Anthropic Claude
> **Reviewer:** OpenAI Codex (cross-provider per HARD RULE Cross-AI Peer Review)
> **Plan-time consultation:** auto-mode classifier denied (cross-AI consultation on uncreated worktree); implementation followed E-6-6 parent plan + Codex parent thread `019e83c3` absorb patterns
> **Risk class:** conservative low-risk (docs/schema/tests; no operator action execution; no workflow)

## 1. Scope

Schema-backed external vendor handoff matrix for the 8 documented
vendors. Operator-owned external handoff; agent prepares the contract.
Follow-up to E-6-6 incident response playbook (PR #801 MERGED); per
Codex parent priority order, vendor escalation matrix is the first
E-6-6 follow-up slice.

**In scope:**
- Schema (Draft 2020-12) with 5-const-true `matrix_disclaimer`
- Matrix instance (8 vendors: 6 LLM providers + GHCR + PyPI)
- Operator runbook (7 sections)
- E-6-6 README §6.6 link extension
- 26 invariant tests
- Plan doc + reviewer evidence

**Out of scope (ZERO TOUCH):**
- Real account manager contact details (`operator_provisioned` const)
- Vendor API integration / runtime outage detection
- Automated ticket creation
- Customer notification (out of v1; legal counsel required)
- `.github/workflows/*`

## 2. Discipline (HARD RULE absorbtion)

### Matrix disclaimer (5 const true)

| Field | Meaning |
|---|---|
| `operator_owned_external_handoff` | Operator decides vendor handoff timing/scope |
| `no_vendor_sla_promise` | ao-kernel does NOT promise vendor SLA terms |
| `no_customer_notification_authority` | ao-kernel does NOT communicate with end-user customers |
| `no_pii_in_repo` | Real human identifiers NEVER committed |
| `operator_legal_counsel_required` | External disclosure requires legal counsel |

### PII boundary

- `account_manager_contact: const "operator_provisioned"` (schema-enforced)
- No real email, phone, or chat handle in any committed file
- Test invariant: targeted email-regex scan with `example.`/`redacted.`/`placeholder.` allowlist

## 3. Implementation Artifacts

| File | LOC | Purpose |
|---|---|---|
| `ao_kernel/defaults/schemas/vendor-escalation-matrix.schema.v1.json` | ~110 | Draft 2020-12; 11 per-vendor fields |
| `docs/incident-response/vendor-escalation-matrix.v1.json` | ~250 | 8 vendors |
| `docs/incident-response/vendor-escalation-runbook.v1.md` | ~85 | 7-section operator runbook |
| `docs/incident-response/README.md` | modify | §6.6 link to matrix + runbook |
| `tests/test_vendor_escalation_matrix.py` | ~310 | 26 invariants |
| `.claude/plans/EPIC-6-E6-6B-VENDOR-ESCALATION-MATRIX.md` | this | Plan doc |

## 4. Vendor Inventory (8 entries)

| ID | Category | SEV mapping |
|---|---|---|
| anthropic-claude | llm_provider | SEV-1 / SEV-2 |
| openai | llm_provider | SEV-1 / SEV-2 |
| google-gemini | llm_provider | SEV-1 / SEV-2 |
| xai-grok | llm_provider | SEV-1 / SEV-2 |
| deepseek | llm_provider | SEV-1 / SEV-2 |
| qwen | llm_provider | SEV-1 / SEV-2 |
| ghcr-container-registry | container_registry | SEV-1 / SEV-2 |
| pypi | package_index | SEV-1 / SEV-2 |

No vendor maps to SEV-3 (v1 conservatism: SEV-3 advisory signals are
internal-only; no vendor handoff required).

## 5. Test Sections (26 invariants)

| Section | Count | Focus |
|---|---|---|
| 1. Schema validity | 5 | Draft 2020-12 + additionalProperties + const pins + guard_flags + 5-disclaimer-const |
| 2. Schema negative | 3 | production_platform_claim + no_pii_committed false + literal email reject |
| 3. Matrix content | 5 | Validates + ≥3 vendors + unique IDs + all 6 LLM providers + workflow step count bounds |
| 4. Severity cross-validation | 3 | E-6-6 severity-matrix present + applicable_severity ⊆ tier IDs + no SEV-3 mapping |
| 5. PII / credential | 3 | Token-prefix secret scan + personal email scan + account_manager_contact const |
| 6. URL pattern | 2 | https:// status page + https:// support portal |
| 7. Runbook structure | 3 | 7 required sections + no vendor SLA promise + legal counsel mention |
| 8. Governance | 2 | guard flags const false + no .github/workflows |

## 6. Out-of-scope follow-up slices (4)

| ID | Slice |
|---|---|
| E-6-6b-2 | Automated vendor outage detection (status page scrape) |
| E-6-6b-3 | Per-vendor SLA tracking dashboard |
| E-6-6b-4 | Vendor incident replay analyzer |
| E-6-6b-5 | Multi-region vendor matrix |

## 7. References

- E-6-6 parent: PR #801 MERGED
- E-6-6 plan-time thread: Codex `019e83c3` (F4 vendor escalation boundary absorb)
- HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14)
- HARD RULE Kullanıcı Aktif Credential'ına Dokunma YASAK (2026-04-29) — PII boundary
- HARD RULE Tam Otonom Önerme (2026-05-28) — agent-prepared operator-owned pattern
- V5 roadmap: `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`
