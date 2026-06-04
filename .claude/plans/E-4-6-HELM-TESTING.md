# E-4-6 — helm-unittest CI invocation doc + lokal runbook + idempotency

> V5 Epic 4. Slice #865. Closes Epic 4 chart-hardening track (E-4-1/3/4/5/6;
> E-4-2b matrix seal is guard-flag-deferred). Guard-flag-independent.

## Delivered
- `docs/HELM-TESTING.md` — two-layer testing runbook: Python invariant tests
  (CI source-of-truth, no Helm binary) + helm-unittest render suites
  (operator-run) + local render smoke + epic-wide idempotency contract.
- `deploy/helm/ao-kernel/tests/{deployment,service}_test.yaml` — helm-unittest
  suites asserting replicas>=1, non-root securityContext, default-safe (no DB
  env when postgresql disabled), ClusterIP http service.
- `tests/test_epic_4_6_helm_testing_doc.py` — 8 invariants.

## Idempotency contract (epic-wide)
- Repeated `helm template` → byte-identical (no timestamps/random suffixes).
- All operator surfaces default disabled/least-privilege (no-override install
  yields minimal secret-free single-replica Deployment).
- `values.schema.json` closed at every level.

## Boundaries
- helm-unittest NOT added to Python CI matrix (CI has no Helm); operator-run.
- No guard flag; no `.github/workflows/` mutation.
