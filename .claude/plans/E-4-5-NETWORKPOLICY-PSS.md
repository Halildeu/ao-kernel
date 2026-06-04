# E-4-5 — NetworkPolicy + PodSecurityStandards namespace-label baseline

> V5 Epic 4. Slice #864. Guard-flag-independent. Builds on E-4-1 chart.

## Delivered
- `templates/networkpolicy.yaml` — opt-in default-deny NetworkPolicy
  (Ingress+Egress); egress DNS-only baseline + operator-allowed CIDRs.
- `values.yaml` `networkPolicy` + `podSecurityStandards` blocks (off/restricted).
- `values.schema.json` — closed blocks; PSS enforceProfile enum.
- `tests/test_epic_4_5_networkpolicy_pss.py` — 11 invariants.

## Boundaries
- Default egress DNS-only; operator MUST widen for LLM provider endpoints.
- Chart does NOT manage the namespace; operator applies PSS enforce label
  out-of-band. Existing container securityContext already meets 'restricted'.
- No guard flag; no `.github/workflows/` mutation.
