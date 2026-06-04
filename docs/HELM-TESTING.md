# Helm chart testing — runbook + CI invocation (V5 Epic 4 E-4-6)

> Slice #865. How to validate the `ao-kernel` Helm chart locally and in CI.
> Two complementary layers: Python invariant tests (always run in CI) and
> `helm-unittest` render suites (operator-run, optional plugin).

## 1. Python invariant tests (CI, always)

The Epic 4 slices each ship a `tests/test_epic_4_*.py` invariant suite that
runs in the standard `pytest` CI matrix — no Helm binary required. They assert
chart structure, schema closure, secretKeyRef-only credentials, gating, and
governance (no workflow mutation, no guard flags). Run locally:

```bash
pytest tests/test_epic_4_1_helm_chart_skeleton.py \
       tests/test_epic_4_2a_multi_tenant_boundary.py \
       tests/test_epic_4_3_postgres_provisioning.py \
       tests/test_epic_4_4_observability_surface.py \
       tests/test_epic_4_5_networkpolicy_pss.py \
       tests/test_epic_4_6_helm_testing_doc.py -q
```

## 2. helm-unittest render suites (operator, optional)

`deploy/helm/ao-kernel/tests/*_test.yaml` are [helm-unittest] suites that
assert rendered manifests. They require the Helm binary + the plugin:

```bash
helm plugin install https://github.com/helm-unittest/helm-unittest
helm unittest deploy/helm/ao-kernel
```

These are **operator-run** (not wired into the Python CI matrix, which does
not install Helm). They give operators a fast render-level regression check
before deploying.

[helm-unittest]: https://github.com/helm-unittest/helm-unittest

## 3. Local render smoke (no plugin)

```bash
# Deterministic render check (same output across repeated renders):
helm template ao-kernel deploy/helm/ao-kernel > /tmp/r1.yaml
helm template ao-kernel deploy/helm/ao-kernel > /tmp/r2.yaml
diff /tmp/r1.yaml /tmp/r2.yaml && echo "idempotent render OK"

# Lint + values schema validation:
helm lint deploy/helm/ao-kernel
```

## 4. Epic-wide idempotency contract

Every Epic 4 chart slice MUST keep the render **deterministic** and
**default-safe**:

- Repeated `helm template` with identical inputs produces byte-identical output
  (no timestamps, no random suffixes in templates).
- All operator surfaces (`postgresql`, `monitoring`, `networkPolicy`,
  `podSecurityStandards`) default to **disabled / least-privilege** — a
  no-override `helm install` yields a minimal, secret-free, single-replica
  Deployment with no DB, no ServiceMonitor, no NetworkPolicy.
- `values.schema.json` stays **closed** (`additionalProperties: false`) at
  every level so unknown keys fail fast.

## 5. What this slice does NOT do

- Does NOT add `helm-unittest` to the Python CI matrix (operator-run; CI does
  not install Helm). The Python invariant tests are the CI source-of-truth.
- Does NOT flip any guard flag or claim production readiness (beta).
