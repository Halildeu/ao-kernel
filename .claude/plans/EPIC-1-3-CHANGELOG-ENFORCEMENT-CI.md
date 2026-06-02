# V5 Epic 1 E-1-3: Changelog Enforcement CI Workflow

> **Cross-AI plan-time iter-2 AGREE** — Codex thread `019e877e` (REVISE 5 BLOCKER absorbed) + independent Anthropic Plan sub-agent (AGREE)
> **Implementer:** Anthropic Claude / **Reviewer:** OpenAI Codex
> **Risk class:** high-risk path (`.github/workflows/`) — supersession evidence pair + CODEOWNER review

## 1. Scope

CI workflow that enforces ADR-0005 Keep-a-Changelog discipline at PR
review time by invoking the canonical `ao-kernel quality check-changelog`
CLI (the SSOT validator). The local `pre-commit-changelog-gate.sh`
helper (E-1-4, PR #818) remains the UX shortcut for developers; this
workflow is the authoritative CI enforcement bound to the same SSOT.

**In scope:**
- `.github/workflows/changelog-enforcement.yml` (~95 LOC)
- `tests/test_changelog_enforcement_workflow_shape.py` (~270 LOC, 17 invariants)
- `ao-ma-10-high-risk-reviews/{openai,anthropic}.local-ai-review-evidence.v1.json` (supersession pair)

**Out of scope (ZERO TOUCH; enforced by 3 invariant tests):**
- `.github/CODEOWNERS` (no governance edge change)
- `.github/REPO-GOVERNANCE.md`
- `.github/PULL_REQUEST_TEMPLATE.md`
- Other `.github/workflows/*` (exactly one new workflow file)
- Branch protection ruleset (required-check wiring is a follow-up operator-bound slice)
- ADR-0005 content
- `ao_kernel/orchestration/quality_profile.py` (SSOT validator unchanged)

## 2. Codex Iter Chain (REVISE → AGREE absorb)

### iter-1 REVISE — 5 BLOCKER

| ID | Issue | Resolution |
|---|---|---|
| F1 | YAML drift: workflow re-implemented ADR-0005 decision (prefix-based) instead of binding to canonical CLI | Replaced with `ao-kernel quality check-changelog --base origin/$BASE_REF --labels-json pr-labels.json`; SSOT stays in `quality_profile.py::check_changelog` |
| F2 | "non-bypassable" overclaim without ruleset required-check wiring | Header reworded: "CI enforcement"; required-check ruleset wiring deferred to follow-up operator-bound slice |
| F3 | Fork-PR diff sağlamlığı: HEAD_SHA fetch garantisi yok | Explicit `actions/checkout@v6` with `ref: github.event.pull_request.head.sha` + `fetch-depth: 0` + separate `git fetch origin "$BASE_REF"` step |
| F4 | "only this workflow added" invariant vs test dosyası ekleme çelişkisi | Test invariant'ı `only one workflow under .github/workflows/` olarak daraltıldı (test dosyası `tests/` altında, governance kapsamı dışında) |
| F5 | `echo "$PR_TITLE"` portability | `printf '%s\n' "$VAR"` pattern uygulandı |

### iter-2 absorb AGREE

- Workflow CLI'a delege ediliyor (SSOT korunuyor)
- 17 invariant (15 pass + 2 skip pre-commit untracked-only state için)
- ZERO TOUCH governance + supersession evidence pair

## 3. Decision Contract (delegated to CLI)

The workflow does NOT implement the decision logic. It delegates to
`ao-kernel quality check-changelog` which, per ADR-0005 + `quality_profile.py`,
enforces:

1. PR adds at least one new bullet under `## [Unreleased]` in CHANGELOG.md, OR
2. PR carries the `chore-no-changelog` label AND PR body contains a ≥10-character rationale

Either condition satisfies; otherwise the CLI exits non-zero and the
workflow fails with an actionable error citing both recovery paths.

## 4. Test Sections (17 invariants)

| Section | Count | Focus |
|---|---|---|
| 1. Presence + structure | 5 | File + pull_request trigger + edited/synchronize event types + no pull_request_target + concurrency cancel-in-progress + single enforce-changelog job |
| 2. Permissions + token discipline | 3 | Read-only contents+pull-requests + no write surface + persist-credentials:false + env-routed BASE_REF + PR_LABELS_JSON (no inline expression) |
| 3. CLI binding (F1 absorb) | 4 | Invokes `ao-kernel quality check-changelog` + core-only install (no live LLM extras) + `--base origin/$BASE_REF --labels-json pr-labels.json` flags + actionable error cites both recovery paths |
| 4. Coexistence with E-1-4 hook | 2 | Optional local hook skip + header documents E-1-4 reference |
| 5. SSOT binding (F1+F2 absorb) | 2 | No inline prefix regex (drift detection) + no "non-bypassable" overclaim language |
| 6. ZERO TOUCH governance | 3 | Only one workflow file + no CODEOWNERS/PR-template/governance + no secret/admin/PAT/id-token surface |

## 5. References

- ADR-0005 Keep-a-Changelog discipline
- E-1-4 PR #818 local hook (pre-commit-changelog-gate.sh)
- `ao_kernel/orchestration/quality_profile.py::check_changelog` (SSOT validator)
- Codex MCP thread `019e877e` (E-1-3 plan-time iter chain)
- HARD RULE Cross-AI Peer Review (2026-05-05 + 2026-05-14)
- HARD RULE No Fake Work + Uzun Vadeli Kalıcı Çözüm
- V5 roadmap §E-1-3
