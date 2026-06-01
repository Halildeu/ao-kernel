# ao-kernel GDPR DPIA Operator Template (V5 Epic 6 E-6-3c)

> **Documentation only.** **Not a GDPR certification.** **Not a regulatory
> approval.** **Not an actual DPIA filing.** **Not legal advice.** ao-kernel
> does NOT process personal data; this template is an operator-owned
> structure, not a public claim. The three V5 guard flags
> (`support_widening`, `production_platform_claim`, `live_adapter_execution`)
> remain `const false`, and three GDPR-scoped flags
> (`regulatory_filing_claim_allowed`, `legal_advice_claim_allowed`,
> `contract_template_allowed`) also remain `const false`. Operator MUST
> consult legal counsel before any external claim. **No DPA contract
> template** is shipped in this repository.
>
> This template does not determine lawful basis, controller/processor
> role, transfer mechanism, DPA filing need, or data subject notice
> content. Article 36 prior consultation determination remains operator
> and DPO/counsel responsibility.
>
> Generated from
> [`gdpr-dpia-template.v1.json`](gdpr-dpia-template.v1.json); do not edit
> this rendered document by hand. Regenerate via
> `python scripts/render_gdpr_dpia_template.py`.

**Framework version:** `GDPR-2018-applied`

## Personal Data Disclosure

- `ao_kernel_processes_personal_data`: `false`
- `no_personal_data_in_repo`: `true`
- `not_data_controller`: `true`
- `not_data_processor_in_v1`: `true`
- `operator_dpia_decision`: `true`

## Sections

### Section 0 — Metadata

- `controller_name`: `<operator-controller-name>`
- `dpo_contact`: `<operator-dpo-contact>`
- `dpa_reference`: `<operator-supervisory-authority>`
- `version`: `v1-baseline`
- `supervisory_authority`: `<operator-supervisory-authority>`


#### DPIA Trigger Assessment

- `repo_baseline_triggered`: `false`
- `operator_must_assess_art35_3`: `true`
- `operator_must_check_supervisory_authority_lists`: `true`
- `special_categories_or_art10_data_in_repo`: `false`
- `art35_3_a_systematic_profiling_in_repo`: `false`
- `art35_3_b_large_scale_special_categories_in_repo`: `false`
- `art35_3_c_systematic_monitoring_public_area_in_repo`: `false`
- `art36_residual_high_risk_prior_consultation_reminder`: Operator must determine with counsel/DPO whether residual high risk remains; if so, Article 36 prior consultation with supervisory authority may be required.

### Section A — Systematic Description of Processing

- `processing_operations`: `<operator-to-describe-processing-operations>`
- `purposes`: `<operator-to-describe-purposes>`
- `data_subjects`: `<no-personal-data-in-repo-baseline>`
- `personal_data_categories`: `<no-personal-data-in-repo-baseline>`
- `recipients`: `<no-personal-data-in-repo-baseline>`
- `transfers`: `<no-personal-data-in-repo-baseline>`
- `retention`: `<no-personal-data-in-repo-baseline>`
- `systems`: `<operator-to-describe-systems>`
- `processors_subprocessors`: `<no-personal-data-in-repo-baseline>`
- `data_flow_summary`: `<no-personal-data-in-repo-baseline>`

### Section B — Necessity and Proportionality Assessment

- `necessity_assessment`: `<operator-to-assess-necessity>`
- `proportionality_assessment`: `<operator-to-assess-proportionality>`
- `data_minimization_statement`: `<operator-to-state-data-minimization>`
- `lawful_basis_consideration_operator_owned`: `<operator-and-counsel-determine-lawful-basis>`

### Section C — Risks to Rights and Freedoms

#### `C1` — Unauthorized access or disclosure of personal data

- **Status:** `not_applicable`
- **Likelihood:** `null`
- **Severity:** `null`
- **Risk Score:** `null`
- **Mitigation:** `null`

#### `C2` — Loss or destruction of personal data

- **Status:** `not_applicable`
- **Likelihood:** `null`
- **Severity:** `null`
- **Risk Score:** `null`
- **Mitigation:** `null`

#### `C3` — Identification or re-identification of data subjects

- **Status:** `not_applicable`
- **Likelihood:** `null`
- **Severity:** `null`
- **Risk Score:** `null`
- **Mitigation:** `null`

#### `C4` — Profiling or automated decision-making impact

- **Status:** `not_applicable`
- **Likelihood:** `null`
- **Severity:** `null`
- **Risk Score:** `null`
- **Mitigation:** `null`

#### `C5` — Discriminatory effects on data subjects

- **Status:** `not_applicable`
- **Likelihood:** `null`
- **Severity:** `null`
- **Risk Score:** `null`
- **Mitigation:** `null`

#### `C6` — Cross-border transfer without adequate safeguards

- **Status:** `not_applicable`
- **Likelihood:** `null`
- **Severity:** `null`
- **Risk Score:** `null`
- **Mitigation:** `null`

### Section D — Mitigation Measures

- `technical_measures`: `<operator-owned-technical-measures>`
- `organizational_measures`: `<operator-owned-organizational-measures>`
- `residual_risk_summary`: `<operator-to-summarize-residual-risk>`
- `operator_owned_measures`: `Operator owns deployment configuration, access controls, encryption, key management, retention enforcement, and incident response.`

### Section E — Consultation Evidence

- `dpo_advice_status`: `not_applicable_repo_baseline`
- `data_subject_views_status`: `not_applicable_repo_baseline`
- `supervisory_authority_prior_consultation_status`: `not_applicable_repo_baseline`
- `consultation_evidence_reference`: `<operator-to-record-consultation-evidence-reference>`

### Section F — Decision and Approval

- `operator_decision_record`: `<operator-to-record-decision>`
- `operator_decision_date`: `<operator-to-record-date>`
- `operator_approver_role`: `<operator-approver-role>`
- `operator_review_cadence`: `<operator-to-define-review-cadence>`

## Prohibited Public Claims (scanner-enforced)

The following tokens are forbidden in any non-disclaimer prose across the GDPR DPIA template artifacts. The token list lives in the JSON catalog under `prohibited_claims` and is enforced by `test_no_prohibited_gdpr_claim_language`.

- `GDPR-compliant`
- `GDPR compliant`
- `GDPR-certified`
- `GDPR certified`
- `GDPR-ready`
- `GDPR ready`
- `fully GDPR`
- `we comply with GDPR`
- `Article 35 ready`
- `Article 35 compliant`
- `DPIA-approved`
- `DPIA approved`
- `DPIA-ready`
- `DPIA ready`
- `DPIA compliant`
- `DPA-approved`
- `DPO approved`
- `ICO approved`
- `CNIL approved`
- `supervisory authority approved`
- `privacy compliant`
- `data subject rights guaranteed`
- `privacy rights guaranteed`
- `lawful basis established`
- `lawful processing confirmed`
- `consent obtained`

## References

- Source catalog: [`gdpr-dpia-template.v1.json`](gdpr-dpia-template.v1.json)
- Schema: [`../../ao_kernel/defaults/schemas/gdpr-dpia-template.schema.v1.json`](../../ao_kernel/defaults/schemas/gdpr-dpia-template.schema.v1.json)
- Operator runbook: [`gdpr-dpia-operator-runbook.v1.md`](gdpr-dpia-operator-runbook.v1.md)
- E-6-3 SOC2/ISO compliance overview: [`README.md`](README.md)
- E-6-3b HIPAA mapping reference: [`hipaa-control-mapping.v1.md`](hipaa-control-mapping.v1.md)
- Codex cross-AI plan-time AGREE: thread `019e84fb` (2 iters: REVISE -> AGREE)
