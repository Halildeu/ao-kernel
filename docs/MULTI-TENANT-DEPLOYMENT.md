# Multi-Tenant Deployment — Advisory Boundary Pattern (V5 Epic 4)

> **Status:** ADVISORY boundary contract (early seal — V5 Epic 4 slice E-4-2a). Per-dimension entries are PLACEHOLDER in this slice; E-4-2b will fill the final matrix with downstream evidence references after E-4-3 / E-4-4 / E-4-5 land.
> **Audience:** operators who install the ao-kernel Helm chart (`deploy/helm/ao-kernel/`) into a multi-tenant Kubernetes cluster.
> **Authority boundary:** This document declares an advisory boundary pattern, not a guarantee. The ao-kernel runtime does NOT enforce multi-tenant isolation; the enforcement is Kubernetes-native and operator-installed. No live cross-tenant attack test has run in Epic 4 (`live_validated: false`); live validation is deferred to V5 Epic 9 operator-bound supersession.

---

## 1. Why "advisory boundary" — not "isolation achieved"

The ao-kernel package is a governed AI orchestration runtime, not a cluster-scoped controller. It cannot guarantee cross-tenant isolation because the enforcement mechanisms live in Kubernetes (Namespace, RBAC, NetworkPolicy, ResourceQuota), not in the Python runtime. Therefore this document uses the following language discipline (per Codex MCP thread `019e879d` iter-1 F4 absorb):

| Avoided dil (overclaim) | Used dil (advisory boundary) |
|---|---|
| isolation achieved | isolation pattern |
| isolation enforced | advisory boundary |
| fully isolated | operator-enforceable |
| runtime enforces | runtime_enforced: false |
| operator_enforced: true | operator_enforceable: true |
| (implicit live validation claim) | live_validated: false |

Every dimension below pins **four const fields** that together encode the advisory-only contract:

- `runtime_enforced: false` — ao-kernel runtime does NOT enforce this dimension.
- `operator_enforceable: true` — Kubernetes-native primitives CAN enforce it if the operator installs them.
- `operator_action_required: true` — the operator must execute a runbook step for the boundary to take effect.
- `live_validated: false` — no live cross-tenant attack test has confirmed the boundary in a real cluster.

The advisory boundary holds when (a) the chart is installed per the runbook, (b) the operator applies the supplementary RBAC + NetworkPolicy + ResourceQuota objects, and (c) the operator performs ongoing review of the boundary in audit logs. None of these steps is performed by ao-kernel itself.

---

## 2. The 7-Dimension Advisory Matrix

The `tenant_isolation_matrix.v1.json` advisory matrix (`.claude/plans/tenant_isolation_matrix.v1.json`) declares 7 dimensions of multi-tenant boundary pattern. In V5 Epic 4 slice E-4-2a (this slice), every entry is in **placeholder** state — the shape is locked, downstream evidence references are reserved. In V5 Epic 4 slice E-4-2b, the matrix will be promoted to `entry_status: "filled"` with concrete downstream evidence references to E-4-3 (database + secret pattern), E-4-4 (observability surface), and E-4-5 (NetworkPolicy + PodSecurityStandards baseline).

---

### 2.1. Namespace Isolation

Anchor: `#namespace-isolation`

**Advisory boundary:** One Helm release per Kubernetes Namespace. ClusterRole and ClusterRoleBinding objects are NOT rendered by the chart. Cluster-scoped controllers, webhooks, or cross-namespace selectors are out of the chart's scope. The advisory boundary holds when the operator installs each tenant's chart into its own Namespace and does not bind cluster-scoped privileges to the workload ServiceAccount.

**Operator action required:** create the per-tenant Namespace before `helm install`; pass `--namespace <tenant>` and `--create-namespace` flags; do not edit the rendered manifests to bind cluster-scoped roles.

**Const fields:** `runtime_enforced: false`, `operator_enforceable: true`, `operator_action_required: true`, `live_validated: false`. The enforcement_mechanism is the Kubernetes Namespace boundary plus the chart's refusal to render cluster-scoped role bindings.

---

### 2.2. RBAC Scope

Anchor: `#rbac-scope`

**Advisory boundary:** The chart renders Role + RoleBinding namespace-scoped only. The workload ServiceAccount cannot list, get, watch, create, update, patch, or delete resources outside its own Namespace because the binding is RoleBinding, not ClusterRoleBinding. Cross-namespace verbs are unavailable to the workload by default. This is an isolation pattern that depends on the operator never adding a ClusterRoleBinding referencing the workload ServiceAccount.

**Operator action required:** review the rendered RBAC manifest (`helm template`) before `helm install`; verify it contains only `kind: Role` and `kind: RoleBinding` (not `kind: ClusterRole` or `kind: ClusterRoleBinding`); never extend the binding to cluster scope without re-evaluating the multi-tenant contract.

**Const fields:** `runtime_enforced: false`, `operator_enforceable: true`, `operator_action_required: true`, `live_validated: false`. The enforcement_mechanism is Kubernetes RBAC namespace scope plus the chart's namespace-scoped binding render.

---

### 2.3. Secret Isolation

Anchor: `#secret-isolation`

**Advisory boundary:** Kubernetes Secret resources are per-Namespace by default; cross-namespace secret mount is blocked by Kubernetes (a Pod cannot mount a Secret from a different Namespace). The chart's Pod env block consumes secrets via `secretKeyRef` indirection only — the chart never renders raw secret values in `values.yaml`, ConfigMap, container args, or Helm release notes. This is an isolation pattern that depends on the operator (a) creating per-tenant Secret objects in each tenant Namespace, and (b) never pasting secrets into `values.yaml` or `helm install --set` flags.

**Operator action required:** create per-tenant Kubernetes Secret objects before `helm install`; reference them via `env[].valueFrom.secretKeyRef.name` in the chart values; rotate per per-tenant schedule. Do not log secrets, do not paste them in MCP tool parameters, do not embed them in evidence JSONL.

**Const fields:** `runtime_enforced: false`, `operator_enforceable: true`, `operator_action_required: true`, `live_validated: false`. The enforcement_mechanism is Kubernetes Secret namespace scope + chart secretKeyRef indirection.

---

### 2.4. Network Policy

Anchor: `#network-policy`

**Advisory boundary:** A default-deny ingress and egress NetworkPolicy is rendered by the chart (operator-extensible). The operator extends the allowlist for the per-tenant database peer, LLM provider hostnames, Microsoft Teams webhook hostname, and kube-dns peer. This advisory boundary holds when (a) the cluster CNI supports NetworkPolicy enforcement (Calico, Cilium, etc.; flannel without CNI extensions does NOT enforce NetworkPolicy), and (b) the operator extends the allowlist correctly for the per-tenant peer set.

**Operator action required:** verify the cluster CNI enforces NetworkPolicy (some CNIs ignore NetworkPolicy silently); extend `security.egress.allowlist.{database, llm_providers, teams_webhook, dns}` in values before `helm install`; review default-deny semantics on a per-tenant basis.

**Const fields:** `runtime_enforced: false`, `operator_enforceable: true`, `operator_action_required: true`, `live_validated: false`. The enforcement_mechanism is NetworkPolicy default-deny + operator-extended allowlist + CNI enforcement.

**Cross-reference reserved:** E-4-5 (NetworkPolicy + PSS baseline) will supply the rendered NetworkPolicy template. E-4-2b will set the downstream_evidence_ref to E-4-5 evidence.

---

### 2.5. Resource Quota

Anchor: `#resource-quota`

**Advisory boundary:** The chart's Pod spec declares `resources.requests` and `resources.limits` at the container level. The Namespace-level ResourceQuota and LimitRange objects are NOT rendered by the chart; they are operator-applied per-tenant. This advisory boundary holds when the operator applies a ResourceQuota that caps per-tenant CPU + memory + pod count + PVC count, and a LimitRange that supplies per-container defaults for ad-hoc Pods.

**Operator action required:** apply per-tenant ResourceQuota + LimitRange objects to each tenant Namespace before `helm install`; rotate caps as tenant tier changes; review quota usage on a recurring basis.

**Const fields:** `runtime_enforced: false`, `operator_enforceable: true`, `operator_action_required: true`, `live_validated: false`. The enforcement_mechanism is Kubernetes ResourceQuota + LimitRange + Pod resources.requests/limits.

---

### 2.6. Audit Boundary

Anchor: `#audit-boundary`

**Advisory boundary:** The ao-kernel JSONL evidence trail is written under the tenant-specific `workspace_root` on the Pod's persistent volume. Cross-tenant fact promotion is an advisory boundary respected by the workspace facts pipeline (the pipeline does not promote facts across distinct `workspace_root` locations). The operator is responsible for (a) mounting per-tenant PersistentVolumeClaim into each tenant Pod, (b) backing up per-tenant audit logs separately, and (c) reviewing the audit trail on a per-tenant basis for cross-tenant fact-promotion violations (none expected if the workspace_root pattern is followed).

**Operator action required:** mount per-tenant PVC; configure per-tenant audit log retention; review JSONL evidence per-tenant per-window; ensure backups are isolated.

**Const fields:** `runtime_enforced: false`, `operator_enforceable: true`, `operator_action_required: true`, `live_validated: false`. The enforcement_mechanism is per-tenant `workspace_root` mount + per-tenant audit log destination + advisory respect by the facts pipeline.

---

### 2.7. Cost Tracking Advisory

Anchor: `#cost-tracking-advisory`

**Advisory boundary:** Per-tenant cost tracking is advisory only. The `cost_tracking.available` capability stays at its declared default; per-tenant cost rollup is an operator dashboard pattern (Prometheus + per-tenant labels) that lives outside the chart. The advisory boundary holds when the operator (a) labels Pods with a per-tenant label (e.g. `tenant=<name>`), (b) configures Prometheus or an equivalent metrics pipeline to aggregate per-tenant metrics, and (c) maintains a per-tenant cost dashboard. The chart does not render a per-tenant cost surface.

**Operator action required:** label Pods per-tenant via `podLabels` values; configure Prometheus per-tenant aggregation; maintain per-tenant cost dashboard.

**Const fields:** `runtime_enforced: false`, `operator_enforceable: true`, `operator_action_required: true`, `live_validated: false`. The enforcement_mechanism is operator-side metrics pipeline + per-tenant label discipline.

**Note:** Per V5 Epic 4 plan §1, any flip of the `cost_tracking.available` capability is out of scope for Epic 4; the per-tenant cost tracking surface is advisory dashboard pattern only.

---

## 3. Why this slice is EARLY (E-4-2a) and what comes LATER (E-4-2b)

V5 Epic 4 plan iter-2 (Codex thread `019e879d`) split the original E-4-2 work into two slices:

- **E-4-2a (this slice):** early advisory boundary contract — schema + matrix placeholder + advisory dil discipline. 2-way cross-AI review (Claude implementer + Codex reviewer). Low-medium risk. Lands before E-4-3 / E-4-4 / E-4-5 so that downstream slices can reference the boundary contract.
- **E-4-2b (later slice):** final matrix seal — promotes `matrix_status` to `e_4_2b_final_seal`; promotes every entry to `entry_status: "filled"`; supplies `downstream_evidence_ref` to E-4-3 + E-4-4 + E-4-5 evidence. 3-way cross-AI review (Claude implementer + Codex reviewer + Mavis/MiniMax additional reviewer). High risk (cross-tenant boundary final seal).

This split serves two purposes per Codex iter-2 F1 absorb: (1) downstream slices (E-4-3, E-4-4, E-4-5) need the boundary contract pinned before they can claim alignment; (2) the final matrix seal carries higher risk and warrants a 3-way cross-AI review that this early advisory contract does not require.

---

## 4. What this slice does NOT promise

- No live cross-tenant attack test has been executed. The advisory boundary is a pattern, not a proof.
- ao-kernel runtime does not enforce isolation; the Kubernetes-native primitives do (when the operator installs them).
- The chart does not extend the allowlist beyond `kube-dns`; the operator must add per-tenant peers.
- No public production claim is made; the chart README and V5 roadmap consistently mark this as operator-installable beta template with production claim deferred to V5 final promotion.

---

## 5. References

- **Matrix artifact:** `.claude/plans/tenant_isolation_matrix.v1.json` (advisory; placeholder state)
- **Matrix schema:** `ao_kernel/defaults/schemas/tenant-isolation-matrix.schema.v1.json` (strict Draft 2020-12)
- **Slice plan doc:** `.claude/plans/E-4-2a-MULTI-TENANT-BOUNDARY-CONTRACT.md`
- **Slice evidence:** `.claude/plans/E-4-2a-MULTI-TENANT-BOUNDARY-CONTRACT.v1.json`
- **Slice evidence schema:** `ao_kernel/defaults/schemas/e-4-2a-multi-tenant-boundary-contract.schema.v1.json`
- **Slice test invariants:** `tests/test_epic_4_2a_multi_tenant_boundary.py`
- **Parent epic plan:** `.claude/plans/EPIC-4-KUBERNETES-HELM-MULTI-TENANT.md` §2 E-4-2a + §13 iter-2 F1/F4 absorb
- **Codex iter-2 AGREE thread:** `019e879d` (plan-time consensus)
- **E-4-1 chart skeleton:** `deploy/helm/ao-kernel/` (template foundation referenced by all multi-tenant dimensions)
