# V5 Epic P0 E-P0-5: GitHub Issue Forms (V5 anchors + computed risk class)

> **Cross-AI plan-time AGREE** — Codex thread `019e8775` (AGREE with hardening note) + independent Anthropic Plan sub-agent (AGREE)
> **Implementer:** Anthropic Claude / **Reviewer:** OpenAI Codex
> **Risk class:** high-risk path (`.github/`) — requires supersession evidence pair + CODEOWNER review

## 1. Scope

Three GitHub Issue forms (v5-slice + v5-gate + governance-bug) + config
that enforce V5 §E-P0-5 anchor invariant: every roadmap-tracked issue
carries `spm_anchor`, `ao_authority_artifact`, `artifact_sha256`,
`plan_digest`, `slice_id`, `risk_class_source` (COMPUTED), and
`evidence_classes` (9-dim multi-select). Risk class is COMPUTED via
classifier output pointer; manual downward edit is forbidden.

**In scope:**
- `.github/ISSUE_TEMPLATE/v5-slice.yml` (slice tracking + 3 guard flag const-false checklist)
- `.github/ISSUE_TEMPLATE/v5-gate.yml` (gate/flip-declaration; no flip execution)
- `.github/ISSUE_TEMPLATE/governance-bug.yml` (HARD RULE violation reporting)
- `.github/ISSUE_TEMPLATE/config.yml` (disable blank issues + canonical doc links)
- 23 invariant tests (yaml shape + required fields + COMPUTED marker + 9 evidence classes + 3 ZERO TOUCH guards)
- `ao-ma-10-high-risk-reviews/{openai,anthropic}.local-ai-review-evidence.v1.json` (supersession pair)

**Out of scope (ZERO TOUCH; enforced by 3 invariant tests):**
- `.github/workflows/*` (no workflow mutation)
- `.github/CODEOWNERS` (no governance edge change)
- `.github/REPO-GOVERNANCE.md` (no policy edit)
- `.github/PULL_REQUEST_TEMPLATE.md` (no PR template edit)
- Branch protection ruleset (no rule change)
- Any guard flag flip (3 const false)

## 2. Cross-AI Verdicts

| Reviewer | Verdict | Note |
|---|---|---|
| Codex (OpenAI thread `019e8775`) | AGREE with hardening note | UX-layer COMPUTED label is sufficient for slice authority; CI-layer classifier-drift enforcement deferred to follow-up slice |
| Anthropic Plan sub-agent (claude-opus-reviewer) | AGREE | 23/23 tests pass + 0 expression-injection + 0 script markers + 0 guard flag flip; diff confined to allowed surfaces |

Codex's "REVISE → AGREE" reflects that the deferred CI-layer
enforcement does NOT block this slice's authority-only intake function.
Follow-up slice (e.g. `risk-class-source-drift-check.yml`) will codify
the classifier-output binding at CI time.

## 3. Implementation Artifacts

| File | LOC | Purpose |
|---|---|---|
| `.github/ISSUE_TEMPLATE/v5-slice.yml` | ~100 | Slice tracking + 7 mandatory anchors + 3 guard flag checklist |
| `.github/ISSUE_TEMPLATE/v5-gate.yml` | ~95 | Gate/flip-declaration dropdown (4 options: 3 flags + none_yet_pending_evidence) |
| `.github/ISSUE_TEMPLATE/governance-bug.yml` | ~85 | Violation_kind enum (6 HARD RULE categories + other) |
| `.github/ISSUE_TEMPLATE/config.yml` | ~10 | blank_issues_enabled:false + 2 contact_links (V5 roadmap + CLAUDE.md) |
| `tests/test_issue_forms_shape.py` | ~280 | 23 invariants |
| `ao-ma-10-high-risk-reviews/openai.local-ai-review-evidence.v1.json` | ~60 | OpenAI Codex AGREE (thread `019e8775`) |
| `ao-ma-10-high-risk-reviews/anthropic.local-ai-review-evidence.v1.json` | ~70 | Independent Anthropic Plan sub-agent AGREE |
| `.claude/plans/EPIC-P0-5-ISSUE-FORMS.md` | this | Plan doc |

## 4. Test Sections (23 invariants)

| Section | Count | Focus |
|---|---|---|
| 1. Form presence + structure | 5 | ISSUE_TEMPLATE dir + 3 forms + config.yml + blank_issues_enabled:false + contact_links canonical |
| 2. Required-field contract (parametrized 3 forms × N) | 3 | All 7 common required fields + validations.required:true + COMPUTED label + multi-select evidence_classes with 9 V5 dims |
| 3. Slice form guard-flag checklist | 1 | 3 V5 flags const false checkboxes required |
| 4. Gate form flip-declaration | 1 | guard_flag_to_flip dropdown enumerates 3 flags + safety option |
| 5. Governance-bug violation_kind | 1 | 6 HARD RULE categories + other fallback |
| 6. ZERO TOUCH governance | 3 | No `.github/workflows/` + only `.github/ISSUE_TEMPLATE/` under `.github/` + no CODEOWNERS/ruleset/PR-template diff |

## 5. Operator Boundary

Issue forms are **intake structure**, not authority. SSOT remains repo
artifacts (`.claude/plans/`, `ao_kernel/defaults/`, ADRs) and final
operator-bound supersession PR. Forms enforce:

- Reporters must reference `ao_authority_artifact` + `artifact_sha256`
- Reporters cannot bypass `risk_class_source` (label signals COMPUTED)
- Blank issues are disabled (forms are the only intake path)

Forms do NOT:
- Authorize guard flag flips (gate form declares, does not execute)
- Override CODEOWNERS or branch protection
- Trigger any workflow run

## 6. Follow-up: CI Classifier-Drift Enforcement (deferred)

Codex thread `019e8775` correctly noted: the `(COMPUTED)` label is a UX
hint, not a runtime guard. A future slice will add a workflow that:

1. Parses opened/edited issues for `risk_class_source` value
2. Reads the referenced classifier artifact at HEAD
3. Validates the issue's recorded risk class matches the classifier output
4. Fails the gate on drift (issue downgraded manually below classifier)

This is **out of scope for E-P0-5** (visibility-only governance
artifact); the follow-up slice would carry its own cross-AI peer review
+ workflow CODEOWNER approval.

## 7. References

- V5 roadmap §E-P0-5
- ADR-0002 (recompute-not-trust) → applies to follow-up drift check
- ADR-0004 (cross-AI peer review HARD RULE)
- Codex MCP thread `019e8775` (E-P0-5 plan-time AGREE)
- HARD RULE Cross-AI Peer Review (2026-05-05 + 2026-05-14)
- HARD RULE No Fake Work + Uzun Vadeli Kalıcı Çözüm
