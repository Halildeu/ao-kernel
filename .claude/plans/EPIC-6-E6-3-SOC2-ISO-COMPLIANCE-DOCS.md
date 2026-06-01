# V5 Epic 6 E-6-3: SOC2/ISO Compliance Documentation

> **Cross-AI plan-time AGREE** — Codex thread `019e83d1` (2 iters: REVISE → AGREE)
> **Implementer:** Anthropic Claude
> **Reviewer:** OpenAI Codex

## 1. Scope

Control-reference mapping + evidence index for SOC2 Trust Service Categories
and ISO 27001:2022 Annex A. Schema-backed canonical JSON SSOT +
deterministic Markdown renders + invariant test suite enforcing wording
discipline.

**In scope:**
- 13-entry SOC2 control coverage (CC1-CC9 + A + C + PI + P)
- 14-entry ISO 27001 Annex A coverage (A.5 through A.18)
- Schema (Draft 2020-12) with guard flag + disclaimer + wording discipline pins
- 2 Markdown renders (deterministic, drift-tested byte-equal)
- Operator-facing README (10 sections)
- 39 invariant tests (schema + content + parity + wording + governance)

**Out of scope (HARD RULE Long-term):**
- Compliance claims, certification/attestation language, audit-ready wording
- Vendor questionnaire responses, pen-test reports, audit report templates
- Customer compliance commitments
- HIPAA, GDPR DPIA, PCI-DSS, NIST CSF (follow-up slices)
- Live audit engagement (operator action)

## 2. Codex Iter Chain

### iter-1 plan-time REVISE — 6 must-close findings

| ID | Severity | Issue | Resolution |
|---|---|---|---|
| F1 | HIGH | SOC2 CC1, CC3, CC4 silent omission risk | Explicit rows for all 13 SOC2 entries |
| F2 | HIGH | CC5 label "Risk Mitigation" wrong; CC9 is Risk Mitigation | CC5 = Control Activities, CC9 = Risk Mitigation |
| F3 | HIGH | "covered" + "control implemented" wording public claim risk | Status enum: documented/partial/out_of_scope/not_applicable; wording dictionary |
| F4 | MEDIUM | Availability out_of_scope too narrow | A = `partial` + explicit uptime/deployment/BCP gaps |
| F5 | MEDIUM | A.16 "covered" overclaim | A.16 = `partial`; operator execution boundary explicit |
| F6 | HIGH | "audit-ready" wording risk | Forbidden token; replacement: "audit-preparation reference" / "control-reference mapping" / "evidence index" |

### iter-2 absorb AGREE + ready_for_impl:true + must_close_findings:[]

```yaml
verdict: AGREE
ready_for_impl: true
must_close_findings: []
```

**Codex implementation guardrails (acceptance criteria, not new findings):**
- G1 Claim negation scope narrowed to `{certified, audited}` only (other 8 tokens fail unconditionally)
- G2 `local-ai-review-evidence.v1.json` post-impl freshness (not pre-baked)

## 3. Implementation Artifacts

| File | Lines | Purpose |
|---|---|---|
| `ao_kernel/defaults/schemas/control-evidence-catalog.schema.v1.json` | ~140 | Draft 2020-12 schema; guard + disclaimer + wording const pins |
| `docs/compliance/control-evidence-catalog.v1.json` | ~330 | Canonical SSOT (SOC2 13 + ISO 14) |
| `docs/compliance/soc2-trust-services-criteria-mapping.v1.md` | ~120 | SOC2 Markdown render (deterministic) |
| `docs/compliance/iso-27001-controls-mapping.v1.md` | ~120 | ISO Markdown render (deterministic) |
| `docs/compliance/README.md` | ~210 | 10-section operator-facing overview |
| `scripts/render_compliance_docs.py` | ~130 | JSON → Markdown deterministic generator |
| `tests/test_compliance_documentation.py` | ~500 | 39 invariants |
| `.claude/plans/EPIC-6-E6-3-SOC2-ISO-COMPLIANCE-DOCS.md` | this | Plan doc |

## 4. Test Sections (39 invariants)

| Section | Count | Focus |
|---|---|---|
| 1. Schema validity | 8 | Draft 2020-12 + additionalProperties:false + const pins + enums |
| 2. Schema negative | 4 | Reject production_claim/contractual_sla/bad status/bad type |
| 3. Catalog content | 6 | Schema validation + 2 frameworks + 13 SOC2 + 14 ISO + CC5/CC9 labels |
| 4. Status F4/F5 | 3 | Availability partial, A.16 partial, Privacy out_of_scope |
| 5. JSON ↔ Markdown parity | 4 | Drift byte-equal + control_id presence + status rendered |
| 6. Wording discipline | 5 | Claim scanner (prose-only) + audit-ready + certified/audited negation + prohibited_claims list + audit report language |
| 7. Evidence refs | 3 | Doc/test/source paths exist + PR ref format + hard_rule date |
| 8. Disclaimer parity | 3 | "Not certified" + "Not audited" + "documentation only" + guard flags |
| 9. Governance | 3 | Catalog guard flags + compliance disclaimer + no .github/workflows |

## 5. Public Claim Discipline

10 forbidden claim tokens enforced by `test_no_compliance_claim_language`:

| Token | Negation allowed? |
|---|---|
| `we comply with` | NO |
| `soc2 compliant` | NO |
| `iso compliant` | NO |
| `meets soc2` | NO |
| `meets iso 27001` | NO |
| `certification-ready` | NO |
| `audit-ready` | NO |
| `certified` | YES (in negation prose) |
| `audited` | YES (in negation prose) |
| `control implemented` | NO |

Scanner uses prose-mode (fenced code blocks skipped, inline backticks
stripped, discipline-documentation lines skipped). Tokens shown as inline
code in this document are documentation, not claims.

## 6. Out-of-scope follow-up slices

| ID | Slice |
|---|---|
| E-6-3b | HIPAA mapping |
| E-6-3c | GDPR DPIA template |
| E-6-3d | PCI-DSS mapping |
| E-6-3e | NIST CSF mapping |
| E-6-3f | Vendor security questionnaire response template (operator-context) |
| E-6-3g | SOC2 Type II audit engagement runbook (operator action) |
| E-6-3h | ISO Statement of Applicability operator template (operator action) |

## 7. References

- V5 roadmap: `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`
- E-5-4 catalog: PR #799 MERGED
- E-5-5 alerts: PR #800 (pipeline)
- E-6-6 incident: PR #801 (pipeline)
- HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14)
- HARD RULE No Fake Work / No Cosmetic Operations (2026-04-25)
- Codex thread `019e83d1` (2-iter REVISE → AGREE)
