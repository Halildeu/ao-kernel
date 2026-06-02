# V5 Epic P0 E-P0-4: README V5 Roadmap Badge + Link

> **Risk class:** conservative low-risk (docs-only)
> **Implementer:** Anthropic Claude / **Reviewer:** OpenAI Codex (post-impl)

## 1. Scope

Surface the V5.0.0 Full Production Promotion Roadmap as a transparent program
plan link in the project README. Add three lightweight Shields.io badges
referencing the roadmap, GPP status, and guard-flag posture. **Does not**
flip any guard flag; explicitly disclaims production-readiness.

**In scope:**
- README badge block (v5 roadmap + GPP + guard flags)
- README roadmap-status disclaimer banner (qualified language)
- Invariant test suite enforcing no production-ready claim creep

**Out of scope (ZERO TOUCH):**
- `.github/workflows/*`
- `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md` content (link only)
- Any guard flag flip (3 const false unchanged)
- Production-ready badge or "GA" badge (forbidden until final operator-bound supersession PR)
- ao-release-gate / branch protection mutation

## 2. Implementation Artifacts

| File | LOC | Purpose |
|---|---|---|
| `README.md` | +12 lines | 3 badges + roadmap-status banner disclaimer |
| `tests/test_readme_v5_roadmap_badge.py` | ~170 | 10 invariants |
| `.claude/plans/EPIC-P0-4-README-V5-ROADMAP-BADGE.md` | this | Plan doc |

## 3. Public Claim Discipline

The README banner uses **qualified language only**:
- "transparent program plan" (NOT "production-ready")
- "operator-bound supersession PR" (promotion authority anchor)
- "final" (no intermediate flag flip)
- 3 guard flags explicitly listed with `const false`

**Forbidden positive-claim tokens** (scanner-enforced):
- `production ready`, `production-ready`, `production platform`,
  `production-platform`, `fully supported`, `ga release`,
  `general availability`

Negation prose exception: tokens may appear only after `not a `, `not an `,
`blanket `, `"not `, `**not**`, or `no production` cues.

## 4. Test Sections (10 invariants)

| Section | Count | Focus |
|---|---|---|
| 1. Badge presence | 3 | v5 roadmap + GPP + guard flags badges |
| 2. Link targets exist | 2 | Roadmap MD file + GPP status MD file present |
| 3. Disclaimer banner | 2 | 3 guard flags mention + qualified language ("transparent program plan", "operator-bound supersession", "final") |
| 4. No claim creep | 2 | No production-ready prose + no in-prose flag flip |
| 5. Governance | 1 | E-P0-4 ZERO TOUCH `.github/workflows/` |

## 5. References

- V5 roadmap: `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`
- GPP status: `.claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md`
- HARD RULE Cross-AI Peer Review (2026-05-05 + 2026-05-14)
- HARD RULE No Fake Work / Uzun Vadeli Kalıcı Çözüm
