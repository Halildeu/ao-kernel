# V5 Epic 6 E-6-3c: GDPR DPIA Operator Template

> **Cross-AI plan-time AGREE** — Codex thread `019e84fb` (2 iters: REVISE → AGREE)
> **Implementer:** Anthropic Claude / **Reviewer:** OpenAI Codex
> **Risk class:** conservative low-risk (additive; ZERO TOUCH E-6-3 + E-6-3b)

## 1. Scope

Schema-backed GDPR Article 35 DPIA operator template. Additive to E-6-3
SOC2/ISO compliance docs (PR #802 MERGED) and E-6-3b HIPAA control
mapping (PR #809). Repo ships the template structure + an operator
runbook + a deterministic Markdown render; ao-kernel itself does NOT
perform DPIA filing, lawful basis determination, or data subject
notice content.

**In scope:**
- GDPR DPIA template schema + canonical JSON + Markdown render
- Operator runbook (how to fill, when DPIA is required, Article 36)
- 48 invariant tests
- README §3.6 GDPR DPIA reference

**Out of scope (ZERO TOUCH):**
- E-6-3 SOC2/ISO catalog + schema + Markdown renders
- E-6-3b HIPAA mapping + schema + Markdown render
- Real personal data samples (email, phone, IP, SSN, name-like)
- Customer-facing privacy notice template
- Real DPIA filing or DPA submission to supervisory authority
- Legal counsel advice text
- DPA (Data Processing Agreement) contract template
- Lawful basis determination, consent validity, controller/processor
  role conclusion
- `.github/workflows/*` mutation

## 2. Codex Iter Chain

### iter-1 plan-time REVISE — 7 BLOCKER

| ID | Issue | Resolution |
|---|---|---|
| F1 | Repo-level "DPIA triggers YOK" overclaim; Art. 35(3)/(4) operator-owned | Section 0 `dpia_trigger_assessment` object with 8 const pins separating repo baseline (false) from operator assessment (true) |
| F2 | Generic `sections: [{ id, title, fields: [...] }]` too loose for legal template drift | `prefixItems` + fixed-order + per-section `$defs` + `additionalProperties: false`; each section carries section-specific `fields` object |
| F3 | `example@example.com` + John Doe placeholders look like personal-data samples | Replaced with non-data placeholders `<operator-controller-name>`, `<no-personal-data-in-repo-baseline>`, etc.; scanner fail-closed on email/phone/IP/SSN/name |
| F4 | `not_certified (no GDPR certification body)` conflicts with Art. 42 | Renamed to `not_gdpr_certification`, `not_regulatory_approval`, `not_actual_dpia_filing`, `not_legal_advice`, `documentation_only`, `operator_legal_counsel_required` |
| F5 | Token list missed common marketing variants | Expanded to 26 prohibited tokens (`GDPR ready`, `DPIA-ready`, `Article 35 compliant`, `DPO approved`, `ICO/CNIL/supervisory authority approved`, `privacy compliant`, `consent obtained`, etc.) |
| F6 | Section E consultation evidence forced as mandatory | Per-field enum `{not_applicable_repo_baseline, operator_to_determine, completed_operator_reference, not_required_operator_assessment}` for DPO advice, data subject views, supervisory authority Art. 36 prior consultation |
| F7 | Baseline "all risks not_applicable" emptied risk model | Risk `status` enum + `allOf if/then`: `not_applicable` requires null likelihood/severity/score/mitigation; applicable status requires non-null minLength fields |

### iter-2 absorb AGREE + ready_for_impl:true + must_close_findings:[]

5 hardening (H10–H14, all enforced):

- H10: Personal-data-like scanner walks BOTH JSON SSOT and Markdown
  artifacts; GDPR public-claim scanner walks Markdown prose only
- H11: 26 prohibited tokens flattened to literal constants (parity test
  asserts JSON catalog matches scanner literals)
- H12: Applicable risk branch schema requires non-null minLength
  likelihood/severity/score/mitigation
- H13: Contract scanner 6 patterns (`agreement shall`, `controller shall`,
  `processor shall`, `the parties agree`, `data processing agreement`,
  `standard contractual clauses`)
- H14: Runbook Art. 36 boundary wording: "remains operator and DPO/counsel
  responsibility"

## 3. Implementation Artifacts

| File | LOC | Purpose |
|---|---|---|
| `ao_kernel/defaults/schemas/gdpr-dpia-template.schema.v1.json` | ~280 | Draft 2020-12 + 6 const-false guard flags + 6 const-true disclaimers + 5 const personal-data disclosure + 7-section prefixItems + risk enum + Section E enum |
| `docs/compliance/gdpr-dpia-template.v1.json` | ~165 | Canonical SSOT (7 sections, 6 risks all not_applicable baseline) |
| `docs/compliance/gdpr-dpia-template.v1.md` | ~115 | Generated Markdown (byte-equal drift-tested) |
| `docs/compliance/gdpr-dpia-operator-runbook.v1.md` | ~110 | Operator runbook (when DPIA, how to fill, Art. 35/36 boundary) |
| `docs/compliance/README.md` | +24 lines | §3.6 GDPR DPIA reference |
| `scripts/render_gdpr_dpia_template.py` | ~140 | Deterministic JSON → Markdown |
| `tests/test_gdpr_dpia_template.py` | ~470 | 48 invariants |
| `.claude/plans/EPIC-6-E6-3C-GDPR-DPIA-TEMPLATE.md` | this | Plan doc + Codex chain |

## 4. Section Coverage (7 sections)

| Section | Status | Notes |
|---|---|---|
| Section 0 — Metadata + Trigger Assessment | baseline | 8 const trigger pins (repo_baseline_triggered false, operator_must_assess true, Art. 36 reminder string) |
| Section A — Systematic Description | baseline | 10 fields; all data-related fields baseline `<no-personal-data-in-repo-baseline>` |
| Section B — Necessity and Proportionality | baseline | 4 operator-to-assess fields |
| Section C — Risks | baseline | 6 risks all `risk_status: not_applicable`; likelihood/severity/score/mitigation null |
| Section D — Mitigation Measures | baseline | 4 operator-owned fields |
| Section E — Consultation | baseline | 3 status enum fields all `not_applicable_repo_baseline` |
| Section F — Decision and Approval | baseline | 4 operator-to-record fields |

## 5. Public Claim Discipline

**6 disclaimer fields const true** (`dpia_disclaimer`):
- `not_gdpr_certification` + `not_regulatory_approval`
- `not_actual_dpia_filing` + `not_legal_advice`
- `documentation_only` + `operator_legal_counsel_required`

**5 personal data disclosure pins**:
- `ao_kernel_processes_personal_data: const false`
- `no_personal_data_in_repo: const true`
- `not_data_controller: const true`
- `not_data_processor_in_v1: const true`
- `operator_dpia_decision: const true`

**6 guard flags const false**: 3 V5-canonical (`support_widening_allowed`,
`production_platform_claim_allowed`, `live_adapter_execution_allowed`) +
3 GDPR-scoped (`regulatory_filing_claim_allowed`,
`legal_advice_claim_allowed`, `contract_template_allowed`).

**26 prohibited claim tokens** (scanner-enforced in Markdown prose):
includes `GDPR-compliant`, `GDPR ready`, `Article 35 compliant`,
`DPIA-approved`, `DPO approved`, `ICO/CNIL/supervisory authority
approved`, `privacy compliant`, `data subject rights guaranteed`,
`lawful basis established`, `consent obtained`, etc.

**6 contract-construction patterns forbidden** (regex):
`agreement shall`, `controller shall`, `processor shall`,
`the parties agree`, `data processing agreement`,
`standard contractual clauses`.

**Personal-data-like sample scan** (JSON + Markdown):
- Email regex `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`
- US phone `\d{3}-\d{3}-\d{4}`
- SSN `\d{3}-\d{2}-\d{4}`
- IP candidate regex → `ipaddress.ip_address()` validation
- Name-like `John|Jane Doe`

All forbidden. RFC 5737 test-net IPs also forbidden.

## 6. Test Sections (48 invariants)

| Section | Count | Focus |
|---|---|---|
| 1. Schema validity | 8 | Draft 2020-12 + additionalProperties:false + 6 disclaimer + 5 disclosure + 6 guard flags + 7-section prefixItems + risk enum + Section E enum |
| 2. Schema negative | 5 | support_widening flip + production_platform flip + live_adapter flip + identified risk missing likelihood + Section E free-form value |
| 3. Section content | 4 | Instance validates + 7 sections exact ids/order + Section 0 trigger baseline + Section C all risks not_applicable |
| 4. Placeholder discipline | 5 (parametrized 15) | No email + no US phone + no SSN + no valid IP + no John/Jane Doe |
| 5. Wording discipline | 5 | 26 prohibited tokens (Markdown prose) + 6 contract patterns + token list parity + Art. 36 runbook wording + no lawful-basis determination wording |
| 6. Drift / governance | 4 | Markdown byte-equal + E-6-3 catalog zero-touch + E-6-3b HIPAA zero-touch + no workflows |
| 7. Cross-validation | 3 | README §3.6 link + Section E baseline all not_applicable_repo_baseline + Section A baseline non-data placeholders |
| 8. Governance | 2 | 6 guard flags const false in schema + 6 disclaimer const true in instance |

## 7. Out-of-scope follow-up slices (4)

| ID | Slice |
|---|---|
| E-6-3c-2 | ROPA (Records of Processing Activities) template |
| E-6-3c-3 | DPA counsel checklist (NOT contract template) |
| E-6-3c-4 | Data subject rights workflow (operator) |
| E-6-3c-5 | Breach notification GDPR Article 33-34 runbook |
| (E-6-3c-6 reserved) | Transfer Impact Assessment (international transfers) |

## 8. References

- E-6-3 SOC2/ISO compliance: PR #802 MERGED
- E-6-3b HIPAA mapping: PR #809
- E-6-6 incident response playbook: PR #801 MERGED
- HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14)
- HARD RULE Uzun Vadeli Kalıcı Çözüm (2026-05-27)
- Codex thread `019e84fb` (2-iter REVISE → AGREE)
- EDPB Guidelines on DPIA: https://edpb.europa.eu/
- V5 roadmap: `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`
