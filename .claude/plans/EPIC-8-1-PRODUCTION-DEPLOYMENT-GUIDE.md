# V5 Epic 8 E-8-1: Production Deployment Guide

> **Risk class:** conservative low-risk (docs-only)
> **Implementer:** Anthropic Claude / **Reviewer:** OpenAI Codex (post-impl)

## 1. Scope

Production deployment guide for ao-kernel covering three operator-deployable
patterns: standalone Python package, Docker container, Kubernetes
microservice. Documents the governed-runtime contract preservation across
all three patterns. **Does not** flip any guard flag; explicitly disclaims
production-readiness.

**In scope:**
- `docs/PRODUCTION-DEPLOYMENT-GUIDE.md` (3 patterns + observability +
  security surfaces + operator-owned boundaries)
- 13 invariant tests (5 presence/structure + 4 claim discipline +
  3 boundary/forward-refs + 1 ZERO TOUCH)

**Out of scope (ZERO TOUCH):**
- `.github/workflows/*`
- Helm chart scaffold (deferred to E-4-1)
- Multi-tenancy config recipe (deferred to E-4-3)
- pgvector backend impl (deferred to E-7-5)
- Any guard flag flip (3 const false unchanged)

## 2. Implementation Artifacts

| File | LOC | Purpose |
|---|---|---|
| `docs/PRODUCTION-DEPLOYMENT-GUIDE.md` | ~220 | 9-section guide (scope + standalone + Docker + k8s + observability + security + operator-owned + roadmap forward refs + references) |
| `tests/test_production_deployment_guide.py` | ~170 | 13 invariants |
| `.claude/plans/EPIC-8-1-PRODUCTION-DEPLOYMENT-GUIDE.md` | this | Plan doc |

## 3. Claim Discipline

Guide disclaimer banner uses qualified language only:
- "Documentation only" (not certification)
- "Not a production-ready certification" (explicit negation)
- "No production-ready posture is established by this guide"
- 3 V5 guard flags listed `const false`
- Promotion authority pointed at "final operator-bound supersession PR"

**Prohibited positive-claim tokens** (whitespace-flattened scanner with
80+5 char window allowing cross-line negation cues):
- `production ready`, `production-ready`, `ga release`,
  `general availability`, `fully supported`, `we are production`,
  `live in production`

**Negation cues** (Markdown blockquote + emphasis stripped): `not a`,
`not an`, `is not`, `no production`, `documentation only`.

## 4. Three Deployment Patterns

| Pattern | Coverage |
|---|---|
| Standalone Python | `pip install ao-kernel` + `ao-kernel init` + extras matrix + workspace layout + Python 3.11+ + health checks |
| Docker | Minimal Dockerfile + Compose + non-root user + volume mounts + operator boundary (secrets, SBOM/vuln scan, multi-arch follow-up) |
| Kubernetes | Reference architecture diagram + required components (Deployment + PVC + ExternalSecrets + Service + ConfigMap + NetworkPolicy + PDB) + Helm chart deferred to E-4-1 + multi-tenancy deferred to E-4-3 |

## 5. Test Sections (13 invariants)

| Section | Count | Focus |
|---|---|---|
| 1. Presence/structure | 5 | Guide exists + standalone + Docker + k8s sections + Python 3.11+ requirement |
| 2. Claim discipline | 4 | 3 guard flags const false + no positive prod-ready claim (whitespace-flat 80+5 char window) + operator-bound final supersession reference + no in-prose flag flip |
| 3. Boundary + forward refs | 3 | Operator-owned surfaces listed (auth, key mgmt, TLS, physical, BCP) + V5 roadmap link + E-4-1 Helm forward reference |
| 4. Governance | 1 | ZERO TOUCH `.github/workflows/` |

## 6. References

- V5 roadmap: `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`
- E-8-6 Migration guide (already merged)
- E-5-1..5-5 observability slices (referenced in §5)
- E-6-1..6-6b security slices (referenced in §6)
- E-4-1..4-6 deployment + tenancy follow-ups
- HARD RULE Cross-AI Peer Review + No Fake Work + Uzun Vadeli
