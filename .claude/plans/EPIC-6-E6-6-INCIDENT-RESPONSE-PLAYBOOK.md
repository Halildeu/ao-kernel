# V5 Epic 6 E-6-6: Incident Response Playbook

> **Cross-AI plan-time AGREE** — Codex thread `019e83c3` (2 iters: REVISE → AGREE)
> **Implementer:** Anthropic Claude
> **Reviewer:** OpenAI Codex

## 1. Scope

Operator-facing incident response playbook driven by E-5-5 Alertmanager alerts
+ E-5-4 SLI/SLO catalog. Schema-backed severity matrix + escalation policy +
post-mortem template + 6 scenario runbooks.

**In scope:**
- Severity matrix (3 tier: SEV-1/2/3) with typed bridge to Alertmanager severity + E-5-4 objective_kind
- Schema `ao_kernel/defaults/schemas/severity-matrix.schema.v1.json` (Draft 2020-12)
- 3-stage escalation policy (`escalation-policy.v1.yml`)
- Blameless post-mortem template (Google SRE)
- 6 scenario runbooks (one per E-5-4 indicator)
- Operator runbook README (10 sections)
- 46 invariant tests

**Out of scope (HARD RULE Long-term):**
- Live PagerDuty/Opsgenie integration (E-6-6c)
- On-call rotation tool deploy
- Actual incident dispatch / ChatOps bot
- Real Teams/Slack webhook URLs, Vault tokens, API keys
- Customer/regulatory disclosure templates
- 3 guard flag flip
- Runtime mutation

## 2. Codex Iter Chain

### iter-1 plan-time REVISE — 6 must-close findings

| ID | Severity | Issue | Resolution |
|---|---|---|---|
| F1 | HIGH | E-5-5 PR #800 path dependency — fake path existence risk | Existence-OR-deferred boundary test + README explicit "Depends on PR #800" + deferred placeholder pattern |
| F2 | HIGH | Severity mapping needs typed machine-checkable bridge (free-text too weak) | Schema: alertmanager_severity enum {critical, warning, advisory} + objective_kind enum + tier id enum + applicable_indicator_names cross-validated against E-5-4 catalog |
| F3 | MEDIUM | Schema-backed claim underspecified unless guard discipline pinned at artifact level | Root-level required: guard_flags 3 const false + operator_owned const true + is_contractual_sla const false |
| F4 | MEDIUM | Comms boundary missing regulatory + vendor escalation explicit fence | README §6.5 Regulatory Disclosure Boundary + §6.6 Vendor Escalation Boundary |
| F5 | MEDIUM | Scenarios omit policy_deny_rate (Epic 6 security relevance) | Added scenario 06 (policy_deny_rate spike; security observability) |
| F6 | LOW | PII regex risks false positive/negative; use targeted scanner | FORBIDDEN_PATTERNS dict (Teams/Slack webhook URLs, PAT, JWT, OpenAI/Anthropic keys, AWS, Bearer, private key) + ALLOWED_PLACEHOLDERS allowlist |

### iter-2 post-absorb AGREE + ready_for_impl:true + must_close_findings:[]

```yaml
verdict: AGREE
ready_for_impl: true
must_close_findings: []
```

Plus 4 small absorb tweaks (non-blocking):
- `04-cost-burn-breach.md` description: "SEV-2 budget objective / operator threshold-driven"
- Secret scanner: Teams hooks generic pattern + outlook.office.com pattern
- "PagerDuty/Opsgenie keyword" testi not full block — config/API material (URL/token/key/endpoint/YAML block) only YASAK
- README link resolver: text path vs markdown link ayrı ele al

Codex final: "Ben bu absorb setini finding closure açısından yeterli görüyorum. Implementasyona geçilebilir."

## 3. Implementation Artifacts

| File | Lines | Purpose |
|---|---|---|
| `ao_kernel/defaults/schemas/severity-matrix.schema.v1.json` | ~110 | Draft 2020-12 schema (guard discipline pinned at root) |
| `docs/incident-response/severity-matrix.v1.json` | ~50 | 3-tier instance (cross-validated against E-5-4 catalog) |
| `docs/incident-response/escalation-policy.v1.yml` | ~75 | 3-stage ladder + severity-specific cadence + comms boundary |
| `docs/incident-response/incident-template.v1.md` | ~95 | Blameless post-mortem template (10 required sections) |
| `docs/incident-response/scenarios/01-llm-usage-accounting-drop.md` | ~60 | SEV-1 triage |
| `docs/incident-response/scenarios/02-llm-latency-burn.md` | ~75 | SEV-1/SEV-2 per-provider |
| `docs/incident-response/scenarios/03-workflow-success-drop.md` | ~65 | SEV-1/SEV-2 terminal-state |
| `docs/incident-response/scenarios/04-cost-burn-breach.md` | ~85 | SEV-2 budget objective |
| `docs/incident-response/scenarios/05-coordination-takeover-spike.md` | ~75 | SEV-3 advisory |
| `docs/incident-response/scenarios/06-policy-deny-spike.md` | ~95 | SEV-3 security observability |
| `docs/incident-response/README.md` | ~190 | 10-section operator runbook |
| `tests/test_incident_response_playbook.py` | ~480 | 46 invariants |
| `.claude/plans/EPIC-6-E6-6-INCIDENT-RESPONSE-PLAYBOOK.md` | this | Plan doc + Codex chain |

## 4. Test Sections (46 invariants)

| Section | Count | Focus |
|---|---|---|
| 1. Schema validity | 8 | Draft 2020-12 + additionalProperties:false + const pins + enum sets |
| 2. Schema negative | 5 | Reject production_platform_claim=true, support_widening=true, is_contractual_sla=true, bad enum, bad tier id |
| 3. Severity matrix instance | 5 | Validates against schema + tier sequence + 1-to-1 mapping + cross-validation + SEV-3 null cadence |
| 4. Escalation YAML | 3 | Parse + 3 stages + severity-specific cadence |
| 5. Post-mortem template | 4 | Required sections + corrective actions table + distribution scope + redaction attestation |
| 6. README discipline | 6 | Numbered sections + disclaimer + guard flags + Teams primary + Slack dormant + regulatory/vendor boundary |
| 7. Scenarios | 6 | All 6 files exist + each references catalog indicator + SEV tier + no integration config + read-only diagnostic |
| 8. Secret/PII scanner | 1 | Targeted FORBIDDEN_PATTERNS + ALLOWED_PLACEHOLDERS |
| 9. E-5-5 dependency boundary | 2 | README references E-5-5 paths + existence-OR-deferred test |
| 10. Governance | 2 | severity-matrix.json guard flags + no positive production claim in artifacts |

## 5. Public Claim Discipline

- 3 guard flags const false at schema root + severity-matrix.v1.json instance
- operator_owned const true; is_contractual_sla const false
- README: "Not SLA", "Not a production platform claim", "operator-tunable", "Local/operator smoke is not production evidence"
- Microsoft Teams primary (HARD RULE Workspace Tooling 2026-05-27 + ADR-0029)
- Slack dormant asset-preserved (no Slack primary claim)
- No live integration, no real webhook URL, no real credential

## 6. Out-of-scope follow-up slices

| ID | Slice | Codex priority order |
|---|---|---|
| **E-6-6b** | Vendor escalation matrix (concrete) | First (provider outage handoff direct) |
| E-6-6c | PagerDuty / Opsgenie integration | Operator choice |
| E-6-6d | ChatOps bot | Live interactive layer |
| E-6-6e | Public post-mortem template | Stakeholder-facing |
| E-6-6f | Regulatory disclosure template | Jurisdiction-specific; legal counsel |
| E-6-6g | Customer comms template (PII-safe) | Operator-owned |

## 7. References

- V5 roadmap: `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`
- E-5-4 catalog: PR #799 MERGED
- E-5-5 alerts: PR #800 `--auto` pipeline
- E-5-1 OTEL tunables: PR #791 MERGED
- E-5-3a W3C trace context: PR #797 MERGED
- ADR-0029: perf-alertmanager Hibrit D
- HARD RULE Workspace Tooling (2026-05-27)
- HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14)
- Google SRE Workbook §13 (Postmortem culture)
- Codex thread `019e83c3` (2-iter REVISE → AGREE)
