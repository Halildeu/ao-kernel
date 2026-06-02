# V5 Epic 6 E-6-3d: PCI-DSS v4.0.1 Control Reference Mapping

> **Cross-AI plan-time AGREE** — Codex thread `019e850a` (2 iters: REVISE → AGREE)
> **Implementer:** Anthropic Claude / **Reviewer:** OpenAI Codex
> **Risk class:** conservative low-risk (additive; ZERO TOUCH E-6-3 + E-6-3b + E-6-3c)

## 1. Scope

Schema-backed PCI-DSS v4.0.1 control reference mapping for the 12
requirements. Additive to E-6-3 SOC2/ISO catalog (PR #802 MERGED),
E-6-3b HIPAA control mapping (PR #809), and E-6-3c GDPR DPIA template
(PR #810). Repo ships mapping structure + operator scope/QSA
engagement runbook + deterministic Markdown render. ao-kernel does
NOT process CHD/SAD, has no PAN in repo, and has no CDE.

**In scope:**
- PCI-DSS schema + canonical JSON + Markdown render
- Operator scope and QSA engagement runbook
- 55 invariant tests
- README §3.7 PCI-DSS reference link

**Out of scope (ZERO TOUCH):**
- E-6-3 SOC2/ISO catalog + schema + Markdown renders
- E-6-3b HIPAA mapping + schema + Markdown render
- E-6-3c GDPR DPIA template + schema + Markdown + runbook
- Real PAN/CHD/SAD/Track 1/2 sample
- Known public test PANs (must NOT appear in artifacts; test sabit only)
- SAQ template / actual SAQ filing
- AOC / ROC / QSA assessment report
- ASV scan / penetration test execution
- "Repo is in PCI scope" claim
- `.github/workflows/*` mutation

## 2. Codex Iter Chain

### iter-1 plan-time REVISE — 5 BLOCKER

| ID | Issue | Resolution |
|---|---|---|
| F1 | Public-claim token count (Q4 said 12 but list had 16); inadequate variants | Expanded to 32 prohibited tokens; exact-set parity test (JSON list == scanner literals lowered-sorted) |
| F2 | PAN/SAD scanner contiguous `\d{13,19}` insufficient; separator forms + Luhn + Track 1/2 + CVV/CVC/CID + PIN block + known test PANs | Separator-normalized Luhn helper + Track 1/2 regex + CVV/CVC/CID context regex + PIN block context regex + 5 known test PAN forbidden + H11 raw-text scanning (no code exemption for PAN/SAD) |
| F3 | SAQ taxonomy enum drift risk (P2PE-HW etc.) | Machine slug enum + separate display_label string; runbook source note (H15) for v4.0.1 label re-confirmation |
| F4 | Req 10/11 `partial` could read as PCI control claim | Req 10 rationale explicit "NOT CDE logging, NOT cardholder data access audit, NOT a PCI control operation"; Req 11 rationale explicit "NOT ASV scan, NOT penetration test, NOT segmentation test" |
| F5 | `minItems=maxItems=12` does NOT enforce exact id coverage | `req_id` pattern `^(?:[1-9]\|1[0-2])$` + 12 `contains` entries (`minContains:1`, `maxContains:1`) + test `sorted(map(int, ids)) == list(range(1,13))` |

### iter-2 absorb AGREE + ready_for_impl:true + must_close_findings:[]

5 hardening (H11–H15, all enforced):

- H11: PAN/SAD scanner walks raw text (no inline/fenced code exemption);
  public-claim scanner does prose-only with code exemption
- H12: Known test PAN literals (4242..., 4111..., 5555..., 3782..., 6011...)
  must NOT appear in any artifact; only allowed as scanner constants
- H13: Word-boundary regex for token scanner (substring false-positive
  reduction)
- H14: req_id numeric sort (`sorted(map(int, ids)) == list(range(1, 13))`)
- H15: SAQ display labels operator-updatable; runbook source note for
  v4.0.1 re-confirmation (schema does NOT pin labels)

## 3. Implementation Artifacts

| File | LOC | Purpose |
|---|---|---|
| `ao_kernel/defaults/schemas/pci-dss-control-mapping.schema.v1.json` | ~210 | Draft 2020-12 + root 6 const pins + 6 const-false guard flags + 7 const-true disclaimers + 5 CHD disclosure + SAQ machine enum + 12 `contains` requirements + status-driven evidence_refs cardinality |
| `docs/compliance/pci-dss-control-mapping.v1.json` | ~210 | Canonical SSOT (12 reqs: 0 documented + 3 partial + 7 out_of_scope + 2 not_applicable) |
| `docs/compliance/pci-dss-control-mapping.v1.md` | ~150 | Generated Markdown (byte-equal drift-tested) |
| `docs/compliance/pci-dss-operator-scope-and-qsa-engagement-runbook.v1.md` | ~145 | Operator runbook (CDE scoping, SAQ selection, QSA engagement, ASV, pen-test; SAQ source note) |
| `docs/compliance/README.md` | +20 lines | §3.7 PCI-DSS Control Reference Mapping reference |
| `scripts/render_pci_dss_docs.py` | ~145 | Deterministic JSON → Markdown |
| `tests/test_pci_dss_mapping.py` | ~570 | 55 invariants |
| `.claude/plans/EPIC-6-E6-3D-PCI-DSS-MAPPING.md` | this | Plan doc + Codex chain |

## 4. Requirement Coverage (12 requirements)

| Req | Title | Status |
|---|---|---|
| 1 | Network Security Controls | `out_of_scope` |
| 2 | Secure Configurations | `out_of_scope` |
| 3 | Protect Stored Account Data | `not_applicable` |
| 4 | Cryptography in Transit | `not_applicable` |
| 5 | Anti-malware | `out_of_scope` |
| 6 | Secure SDLC | `partial` (E-6-1 SBOM + E-6-2 vuln scan + E-6-5 CodeQL) |
| 7 | RBAC | `out_of_scope` |
| 8 | Authentication | `out_of_scope` |
| 9 | Physical | `out_of_scope` |
| 10 | Logging | `partial` (E-5-3 tracing + E-5-3b consultation tracing) |
| 11 | Testing | `partial` (E-6-2 + E-6-5 SAST) |
| 12 | Org Policy | `out_of_scope` |

**Distribution:** 0 documented + 3 partial + 7 out_of_scope + 2 not_applicable.

## 5. Public Claim Discipline

**7 disclaimer fields const true** (`pci_disclaimer`):
- `not_pci_certified` + `not_aoc_holder` + `not_roc_holder`
- `not_saq_filed` + `not_asv_scanned`
- `documentation_only` + `operator_qsa_engagement_required`

**5 CHD handling disclosure pins**:
- `ao_kernel_processes_chd: const false`
- `ao_kernel_processes_sad: const false`
- `no_pan_in_repo: const true`
- `no_cde_in_repo: const true`
- `operator_cde_decision: const true`

**6 guard flags const false**: 3 V5-canonical (`support_widening_allowed`,
`production_platform_claim_allowed`, `live_adapter_execution_allowed`) +
3 PCI-scoped (`cde_claim_allowed`, `qsa_assessment_claim_allowed`,
`saq_filing_claim_allowed`).

**32 prohibited claim tokens** (Markdown prose, word-boundary):
includes `PCI-compliant`, `PCI-DSS certified`, `PCI-DSS validated`,
`fully PCI-DSS`, `we comply with PCI-DSS`, `PCI-DSS Level 1`,
`QSA-approved`, `AOC-ready`, `ROC-ready`, `SAQ-A ready`, `SAQ eligible`,
`PCI ready`, etc.

**10 contract-construction patterns forbidden** (regex):
`merchant shall`, `service provider shall`, `AOC shall`, `assessor shall`,
`QSA shall`, `we have completed`, `has been assessed`, `validated by`,
`the parties agree`, `assessment confirms`.

**PAN/SAD raw-text scan** (BOTH JSON + Markdown + runbook, NO code
exemption):
- PAN candidate `\d[\d\s-]{11,21}\d` post-normalize → Luhn-valid forbidden
- 5 known public test PANs forbidden (4242..., 4111..., 5555...,
  3782..., 6011...)
- Track 1: `%B\d+\^[A-Z/\s.]+\^\d+`
- Track 2: `;\d+=\d+\?`
- CVV/CVC/CID context: `(?:cvv2?|cvc2?|cid)[\s:]*\d{3,4}`
- PIN block / PIN digits context
- Expiry context

## 6. Test Sections (55 invariants)

| Section | Count | Focus |
|---|---|---|
| 1. Schema validity | 10 | Draft 2020-12 + additionalProperties:false + root 6 const + 6 guard + 7 disclaimer + 5 CHD + SAQ const + 12 `contains` + status enum + req_id pattern |
| 2. Schema negative | 5 | 2 guard flips + partial without evidence + out_of_scope with evidence + req_id outside 1-12 |
| 3. Section content | 5 | Instance validates + 12 ids exact 1-12 + status distribution (0/3/7/2) + Req 10 wording + Req 11 wording |
| 4. PAN/SAD discipline | 6 (parametrized 18) | No Luhn-valid PAN + no known test PAN + no Track 1 + no Track 2 + no CVV/CVC/CID + no PIN block |
| 5. Wording discipline | 5 | 32 prohibited tokens (Markdown prose word-boundary) + 10 contract patterns + token list parity + Req 10/11 boundary in Markdown + QSA engagement section |
| 6. Drift / governance | 5 | Markdown byte-equal + allowlist diff + E-6-3 zero-touch + E-6-3b HIPAA zero-touch + E-6-3c GDPR zero-touch |
| 7. Cross-validation | 3 | README §3.7 link + SAQ source note runbook + SAQ baseline `none` instance |
| 8. Governance | 2 | 6 guard flags const false instance + 7 disclaimer const true instance |

## 7. Out-of-scope follow-up slices (5)

| ID | Slice |
|---|---|
| E-6-3d-2 | Operator CDE scoping worksheet (prerequisite) |
| E-6-3d-3 | SAQ-A operator fill guide (NOT actual SAQ) |
| E-6-3d-4 | ASV scan operator playbook (NOT scan execution) |
| E-6-3d-5 | QSA engagement RFP template (operator) |
| E-6-3d-6 | P2PE solution evaluation checklist (operator) |

## 8. References

- E-6-3 SOC2/ISO compliance: PR #802 MERGED
- E-6-3b HIPAA mapping: PR #809
- E-6-3c GDPR DPIA template: PR #810
- E-6-6 incident response playbook: PR #801 MERGED
- HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14)
- HARD RULE Uzun Vadeli Kalıcı Çözüm (2026-05-27)
- Codex thread `019e850a` (2-iter REVISE → AGREE)
- PCI Security Standards Council: https://www.pcisecuritystandards.org/
- V5 roadmap: `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`

