# V5 Epic 6 E-6-3b: HIPAA Control Mapping

> **Cross-AI plan-time AGREE** — Codex thread `019e84ee` (2 iters: REVISE → AGREE)
> **Implementer:** Anthropic Claude / **Reviewer:** OpenAI Codex
> **Risk class:** conservative low-risk (additive; ZERO TOUCH E-6-3 catalog)

## 1. Scope

Schema-backed HIPAA Safeguards + Privacy Rule + Breach Notification
control-reference mapping. Additive to E-6-3 SOC2/ISO compliance docs
(PR #802 MERGED); does NOT modify any E-6-3 contract.

**In scope:**
- HIPAA schema + instance + Markdown render + 1 README §3.5 link
- Deterministic renderer + byte-equal drift test
- 38 invariant tests

**Out of scope (ZERO TOUCH):**
- `control-evidence-catalog.v1.json` + schema (SOC2/ISO)
- `soc2-trust-services-criteria-mapping.v1.md`
- `iso-27001-controls-mapping.v1.md`
- `.github/workflows/*`
- Real PHI samples, BAA templates, audit attestation language

## 2. Codex Iter Chain

### iter-1 plan-time REVISE — 5 BLOCKER

| ID | Issue | Resolution |
|---|---|---|
| F1 | citation grammar narrow (4 HIPAA forms unsupported) | Stable slug `control_id` + free-form `citation` with regex supporting `§164.308(a)(1)` + `§164.310(b)` + `§164.500-534` + `§164.402-414` |
| F2 | Technical Safeguards `partial` reads as ePHI control claim | All Technical Safeguards → `out_of_scope`; per-control `ephi_control_operator_owned: const true` + `hipaa_control_effectiveness_claim: const false` |
| F3 | `covered entity` global token ban breaks operator boundary | Narrowed to 4 self-claim form patterns (`ao-kernel is a covered entity`, `we are a covered entity`, `covered-entity ready`, `covered-entity certified/approved/qualified`) |
| F4 | Markdown drift/parity missing | Deterministic renderer `scripts/render_hipaa_mapping.py` + byte-equal drift test |
| F5 | Section-level applicability ambiguous | `section_status` enum `{applicable, not_applicable, mixed}` + schema `allOf if/then` (not_applicable → controls maxItems 0) |

### iter-2 absorb AGREE + ready_for_impl:true + must_close_findings:[]

7 implementation guardrails (all enforced):
- Citation positive + negative fixtures (parametrized tests)
- Schema if/then branches for section_status
- `phi_handling_disclosure` 3 pins named correctly
- Technical Safeguards rationale: "repo evidence surface only; NOT ePHI control claim"
- README §3.5 numbering preserves existing structure
- BAA follow-up renamed to "operator decision guide / counsel checklist" (NOT template)
- 4 additional hardening enhancements

## 3. Implementation Artifacts

| File | LOC | Purpose |
|---|---|---|
| `ao_kernel/defaults/schemas/hipaa-control-mapping.schema.v1.json` | ~165 | Draft 2020-12 + 6 const-true disclaimer + section_status enum + per-control 2 const pins |
| `docs/compliance/hipaa-control-mapping.v1.json` | ~310 | Canonical SSOT (5 sections, 22 controls) |
| `docs/compliance/hipaa-control-mapping.v1.md` | ~145 | Generated Markdown (byte-equal drift-tested) |
| `docs/compliance/README.md` | +18 lines | §3.5 HIPAA mapping reference |
| `scripts/render_hipaa_mapping.py` | ~135 | Deterministic JSON → Markdown |
| `tests/test_hipaa_mapping.py` | ~470 | 38 invariants |
| `.claude/plans/EPIC-6-E6-3B-HIPAA-CONTROL-MAPPING.md` | this | Plan doc + Codex chain |

## 4. Section Coverage (5 sections, 22 controls)

| Section | section_status | Controls | Documented | Out-of-scope | Not-applicable |
|---|---|---|---|---|---|
| Administrative Safeguards (§164.308) | `mixed` | 9 | 3 (mgmt + incident + evaluation) | 6 | — |
| Physical Safeguards (§164.310) | `applicable` | 4 | 0 | 4 | — |
| Technical Safeguards (§164.312) | `applicable` | 5 | 0 | 5 (all ePHI op-owned) | — |
| Privacy Rule (§164.500-534) | `not_applicable` | 0 | — | — | section-level |
| Breach Notification (§164.402-414) | `not_applicable` | 0 | — | — | section-level |

**Total `documented`: 3** (Admin §§308(a)(1), 308(a)(6), 308(a)(8) — all
reference existing repo evidence surfaces). Conservative bound at 3
enforced by `test_documented_status_restricted`.

## 5. Public Claim Discipline

**6 disclaimer fields const true** (`hipaa_disclaimer`):
- `not_certified` + `not_audited` + `documentation_only`
- `not_phi_processor` + `not_baa_template` + `operator_legal_counsel_required`

**3 PHI handling disclosure pins** (`phi_handling_disclosure`):
- `ao_kernel_processes_phi: const false`
- `no_phi_in_repo: const true`
- `operator_phi_handler_decision: const true`

**Per-control 2 const pins** (every control across all sections):
- `ephi_control_operator_owned: const true`
- `hipaa_control_effectiveness_claim: const false`

**10 prohibited claim tokens** (scanner-enforced in Markdown prose):
`hipaa compliant`, `hipaa-compliant`, `hipaa certified`, `hipaa-certified`,
`phi-safe`, `baa-ready`, `we comply with hipaa`, `hipaa-grade`,
`fully hipaa`, `guaranteed phi protection`.

**4 covered-entity self-claim forms forbidden** (regex):
`ao-kernel is a covered entity`, `we are a covered entity`,
`covered-entity ready`, `covered-entity certified/approved/qualified`.

**4 BAA contract-construction patterns forbidden** (regex):
`covered entity shall`, `business associate shall`, `shall notify`,
`this agreement/baa governs/covers/applies`.

**PHI sample scan**: SSN pattern (`\d{3}-\d{2}-\d{4}`) + MRN pattern
(`MRN[:\s-]\d{6,}`) absent.

## 6. Test Sections (38 invariants)

| Section | Count | Focus |
|---|---|---|
| 1. Schema validity | 6 | Draft 2020-12 + 4 const pins + guard_flags + 6 disclaimer + 3 PHI disclosure |
| 2. Schema negative | 4 | Reject production_platform_claim + PHI processing + ePHI control owned false + bad citation |
| 3. Section content | 4 | Validates + 5 sections + Privacy/Breach not_applicable + Technical all out_of_scope |
| 4. Citation grammar | 3 (+ 8 parametrized) | All committed citations + 4 positive forms + 4 negative forms |
| 5. Wording discipline | 5 | Prohibited HIPAA scanner + self-claim covered-entity 4 forms + BAA contract patterns + PHI sample + prohibited list parity |
| 6. Drift / governance | 4 | Markdown byte-equal + E-6-3 catalog zero-touch + no workflows + E-6-3 schema present |
| 7. Cross-validation | 3 | README §3.5 link + documented ≤3 + PR ref format |
| 8. Governance | 3 | Guard flags + PHI disclosure + disclaimer pins |

## 7. Out-of-scope follow-up slices (4)

| ID | Slice |
|---|---|
| E-6-3b-2 | HIPAA technical safeguards deep-dive (operator-deployed encryption/access) |
| E-6-3b-3 | BAA operator decision guide / counsel checklist (NOT template; legal exposure boundary) |
| E-6-3b-4 | HHS OCR audit response template (operator action) |
| E-6-3b-5 | Breach Notification 60-day timeline runbook |

## 8. References

- E-6-3 SOC2/ISO compliance: PR #802 MERGED
- E-6-6 incident response playbook: PR #801 MERGED
- HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14)
- HARD RULE Uzun Vadeli Kalıcı Çözüm (2026-05-27)
- Codex thread `019e84ee` (2-iter REVISE → AGREE)
- HHS HIPAA Security Rule: https://www.hhs.gov/hipaa/for-professionals/security/index.html
- V5 roadmap: `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`
