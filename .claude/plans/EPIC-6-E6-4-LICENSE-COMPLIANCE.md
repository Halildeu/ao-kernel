# V5 Epic 6 E-6-4: License Compliance

> **Cross-AI plan-time AGREE** — Codex thread `019e83df` (2 iters: REVISE → AGREE)
> **Implementer:** Anthropic Claude / **Reviewer:** OpenAI Codex

## 1. Scope

Schema-backed SPDX license-tier policy + deterministic per-component
dependency inventory generated from CycloneDX 1.5 SBOM. Distinct from
runtime `policy_license.v1.json` capability policy (different scope,
distinct naming).

**In scope:** Policy schema + instance + inventory schema + generator
(stdlib JSON; no cyclonedx-python-lib runtime dep) + Markdown render +
README + 41 invariant tests.

**Out of scope (HARD RULE Long-term):** Full SPDX expression interpreter,
NOTICE generation, exception semantics, source distribution compliance,
remediation runbook, vendor review workflow, legacy policy migration.

## 2. Codex Iter Chain

### iter-1 plan-time REVISE — 6 must-close

| ID | Severity | Issue | Resolution |
|---|---|---|---|
| F1 | CRITICAL | SPDX expression false negative risk | `spdx_expression_handling: simple_identifier_only`; composite/exception/ref → `review_required` |
| F2 | HIGH | unknown_handling unsafe (allow) or overclaim (deny) | `unknown_handling: review` (fail-closed review) |
| F3 | HIGH | MPL-2.0 duplicated across tiers | Mutually exclusive tier membership + cross-tier uniqueness test |
| F4 | HIGH | Runtime `policy_license.v1.json` naming collision | Distinct naming: `license-compliance-policy.v1.json` + `dependency-license-inventory.v1.json` |
| F5 | MEDIUM | Generated inventory wall-clock drift | No timestamps; source SHA256 provenance; stable sort; canonical JSON; repo-relative paths |
| F6 | MEDIUM | Preflight fetch failed in sandbox | Rerun in writable shell at impl time (documented) |

### iter-2 absorb AGREE + ready_for_impl:true + must_close_findings:[]

4 non-blocking hardening tweaks (H11-H14):
- H11 Markdown drift test (byte-equal)
- H12 CLI single entrypoint name (`generate_license_inventory.py`)
- H13 Summary numeric counts (component/pass/review/deny)
- H14 review_reason enum (10 values)

## 3. Implementation Artifacts

| File | Lines | Purpose |
|---|---|---|
| `ao_kernel/defaults/schemas/license-compliance-policy.schema.v1.json` | ~90 | Policy schema (Draft 2020-12; F1+F2+F3+F4+F5 pins) |
| `ao_kernel/defaults/schemas/dependency-license-inventory.schema.v1.json` | ~95 | Inventory schema |
| `docs/license-compliance/license-compliance-policy.v1.json` | ~50 | Canonical policy SSOT (3 tiers, mutually exclusive) |
| `docs/license-compliance/dependency-license-inventory.v1.json` | generated | From SBOM + policy |
| `docs/license-compliance/dependency-license-inventory.v1.md` | generated | Markdown summary |
| `docs/license-compliance/README.md` | ~180 | 10-section operator-facing |
| `scripts/generate_license_inventory.py` | ~280 | stdlib JSON; no cyclonedx-python-lib; repo-relative path normalize |
| `tests/fixtures/sample-sbom.cdx.json` | ~80 | CycloneDX 1.5 fixture (8 components covering allow/review/expression/name-only) |
| `tests/test_license_compliance.py` | ~520 | 41 invariants |

## 4. Test Sections (41 invariants)

| Section | Count | Focus |
|---|---|---|
| 1. Schema validity | 8 | Draft 2020-12 + additionalProperties + const pins (both schemas) |
| 2. Schema negative | 4 | Reject guard flip / SLA flip / bad enum / bad status |
| 3. Policy content | 5 | 3 tiers + mutually exclusive (F3) + unknown_handling review (F2) + expression handling const |
| 4. Naming collision (F4) | 3 | Runtime policy preserved + distinct compliance naming + distinct schema_version |
| 5. Generator + provenance (F5) | 6 | Idempotent + drift byte-equal + Markdown drift + no wall-clock + stable sort + source SHA256 |
| 6. CycloneDX shape | 5 | Simple id → pass + review tier + expression → unsupported_expression + name-only → unresolved_name + review_reason enum |
| 7. Wording discipline | 3 | Legal claim scanner (prose-mode) + disclaimer + guard flag mention |
| 8. Summary + report_status | 3 | Counts consistency + status mapping + schema validation |
| 9. LICENSE parity | 2 | File exists + ao_kernel_license == MIT |
| 10. Governance | 2 | Guard flags + no .github/workflows |

## 5. Out-of-scope follow-up slices (10)

E-6-4b through E-6-4k (see README §9).

## 6. References

- E-6-1a SBOM generator (PR #795 MERGED)
- HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14)
- HARD RULE Uzun Vadeli Kalıcı Çözüm (2026-05-27)
- Codex thread `019e83df`
