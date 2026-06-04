# Multi-tenant production config recipe (V5 Epic 8 E-8-2)

> Slice #890. A copy-paste **recipe** for running one ao-kernel deployment
> per tenant with namespace isolation. This document **delegates** the
> mechanics to the Epic 4 chart surfaces — it does not introduce new chart
> features. Beta; no production claim; no guard flag touched.

## Model: one namespace + one release per tenant

ao-kernel multi-tenancy is **deployment-level isolation**, not in-process
tenant partitioning. Each tenant gets its own namespace, Helm release, secret,
database, NetworkPolicy, and resource quota. This is the strongest isolation
boundary k8s offers and keeps the runtime itself tenant-agnostic.

```
namespace: tenant-acme        namespace: tenant-globex
  release: ao-kernel            release: ao-kernel
  secret:  ao-kernel-db         secret:  ao-kernel-db
  PG:      acme-db (E-4-3)      PG:      globex-db (E-4-3)
  netpol:  default-deny (E-4-5) netpol:  default-deny (E-4-5)
```

## Step 1 — namespace + PodSecurityStandards (delegates to E-4-5)

```bash
kubectl create namespace "tenant-$T"
kubectl label namespace "tenant-$T" \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/enforce-version=latest
```

## Step 2 — per-tenant PostgreSQL + Secret (delegates to E-4-3)

Follow `docs/OPERATOR-SECRET-MANAGEMENT.md` per tenant: provision an
**isolated** database + a Secret in the tenant namespace. Never share a
database or a Secret across tenants.

## Step 3 — per-tenant values overlay

Create `values-tenant-$T.yaml` (operator-owned; NOT committed with secrets):

```yaml
# Per-tenant overlay. Connection coordinates are non-secret; credentials via
# secretKeyRef ONLY (the chart never holds them).
replicaCount: 2                      # tune per tenant SLA

postgresql:                          # E-4-3
  enabled: true
  host: "acme-db.example.internal"
  dbname: "ao_kernel"
  sslmode: "verify-full"
  secretName: "ao-kernel-db"

networkPolicy:                       # E-4-5
  enabled: true
  egress:
    allowCidrs:
      - "10.0.0.0/8"                 # tenant's allowed LLM provider range

monitoring:                          # E-4-4
  serviceMonitor:
    enabled: true
    additionalLabels:
      tenant: "acme"                 # so per-tenant Prometheus selects it

podSecurityStandards:                # E-4-5
  enforceProfile: "restricted"

resources:                           # per-tenant quota alignment
  requests: { cpu: "250m", memory: "256Mi" }
  limits:   { cpu: "1",    memory: "1Gi" }
```

## Step 4 — install per tenant

```bash
helm upgrade --install ao-kernel deploy/helm/ao-kernel \
  --namespace "tenant-$T" \
  --values "values-tenant-$T.yaml"
```

## Step 5 — namespace ResourceQuota (operator-owned)

```bash
kubectl apply -n "tenant-$T" -f - <<'YAML'
apiVersion: v1
kind: ResourceQuota
metadata: { name: ao-kernel-quota }
spec:
  hard:
    requests.cpu: "2"
    requests.memory: 2Gi
    limits.cpu: "4"
    limits.memory: 4Gi
YAML
```

## Isolation checklist (per tenant)

- [ ] dedicated namespace + PSS `restricted` enforce label (E-4-5)
- [ ] dedicated PostgreSQL + Secret, never shared (E-4-3)
- [ ] NetworkPolicy default-deny + scoped egress (E-4-5)
- [ ] ServiceMonitor labelled with tenant id (E-4-4)
- [ ] ResourceQuota applied (operator-owned)
- [ ] no cross-tenant ServiceAccount / ClusterRole (E-4-2a boundary)

## What this slice does NOT do

- Does NOT add chart features (delegates to E-4-2a/E-4-3/E-4-4/E-4-5).
- Does NOT enable in-process tenant partitioning (isolation is namespace-level).
- Does NOT flip any guard flag; does NOT claim production readiness (beta).

## Cross-references

- Multi-tenant boundary contract: `docs/MULTI-TENANT-DEPLOYMENT.md` (E-4-2a)
- Secret + PostgreSQL: `docs/OPERATOR-SECRET-MANAGEMENT.md` (E-4-3)
- Production deployment: `docs/PRODUCTION-DEPLOYMENT-GUIDE.md` (E-8-1)
