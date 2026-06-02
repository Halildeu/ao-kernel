# ao-kernel Helm Chart (V5 Epic 4 E-4-1 Skeleton)

This is the **operator-installable Helm chart skeleton** for ao-kernel. It is a beta artifact delivered by V5 Epic 4 slice E-4-1. The chart provides a render-only baseline (Deployment + Service + ConfigMap + ServiceAccount + Role/RoleBinding) so that operators can begin assembling a production deployment plan. It is **not** a production-ready chart on its own.

## Status

- **Lifecycle:** beta-skeleton
- **Production claim:** **deferred** to v5 final promotion (Epic 9 PR-Xfinal). The chart itself does **not** make any production-readiness claim.
- **Live execution:** chart is render-only at this stage. The three ao-kernel runtime guard flags governed by the kernel (the live-adapter-execution flag, the support-widening flag, and the production-platform-claim flag) all remain `false` and are **not** flipped by this chart. The chart never references those flag keys by name in any rendered manifest, values file, schema, or doc; the test suite enforces that key-string absence.
- **Multi-tenant boundary:** advisory pattern only at this skeleton stage; the runtime does not enforce tenant isolation. Operator must apply the boundary pattern (namespace + RBAC + NetworkPolicy + Secret) per the future E-4-2a / E-4-2b advisory contracts.

## Six skeleton invariants (machine-enforced by `tests/test_epic_4_1_helm_chart_skeleton.py`)

1. **No guard flag flip.** Chart files (`values.yaml`, `values.schema.json`, all templates, this README, `NOTES.txt`) do **not** contain the three runtime guard flag key strings anywhere — neither as keys, values, nor comments. The test suite enumerates the three forbidden key strings explicitly and asserts zero matches across the chart directory.
2. **No live adapter execution.** Chart templates do not embed any live cluster command (no apply-style verb against the cluster, no install or upgrade verb against the chart). Live deployment lives in operator-side runbooks (future E-4-3 / E-4-5 docs), not in the chart. The invariant test enumerates the three forbidden command strings and asserts zero matches in `NOTES.txt` and this README.
3. **No secret in values.** `values.yaml` carries **zero** inline secret material (no API keys, no tokens, no webhook URLs). Secrets are referenced via Kubernetes `secretKeyRef` only; the chart does **not** create Kubernetes Secrets — the operator pre-provisions them out-of-band.
4. **Env-only secret resolution.** Secret values reach the container only through Kubernetes Secret + env `secretKeyRef`. CLAUDE.md invariant: secrets are never logged, never passed as MCP parameters, and never written to values files.
5. **Operator-installable beta.** Chart is installable by an operator who has prepared the namespace, RBAC binding, secret resolution, and (when needed) NetworkPolicy / PSS label configuration. The chart itself does not provision any of these — that is operator responsibility.
6. **Production claim deferred.** Every chart-level claim regarding production readiness is held until V5 Epic 9 PR-Xfinal operator-bound supersession decision. The chart README, `Chart.yaml` annotations, and `NOTES.txt` all reflect this deferral explicitly.

## Files

| Path | Purpose |
|---|---|
| `Chart.yaml` | Chart metadata; `appVersion` pinned to `ao_kernel.__version__` (manual pin, no auto-bump) |
| `values.yaml` | Default values; `replicaCount: 1` (HARD RULE: scale-to-zero forbidden); no inline secrets |
| `values.schema.json` | JSON Schema (Draft 2020-12) strict: `additionalProperties: false` everywhere; `replicaCount.minimum: 1` |
| `templates/_helpers.tpl` | Standard Helm helper templates (name, fullname, labels, serviceAccountName) |
| `templates/deployment.yaml` | Deployment with `replicas = .Values.replicaCount`; ServiceAccount bound; env from ConfigMap + secretKeyRef |
| `templates/service.yaml` | ClusterIP service; http + healthz + readyz ports |
| `templates/configmap.yaml` | Non-secret config (workspace_root, log_level); never carries secret material |
| `templates/serviceaccount.yaml` | Default ServiceAccount, namespace-scoped |
| `templates/rbac.yaml` | Role + RoleBinding, namespace-scoped only (ClusterRole forbidden by Epic 4 boundary) |
| `templates/NOTES.txt` | Post-install message; reiterates beta status + operator responsibilities + no live commands |

## Usage (operator)

Render manifests locally without installing:

```
helm template my-release deploy/helm/ao-kernel/ --namespace my-tenant > rendered.yaml
```

Lint the chart:

```
helm lint deploy/helm/ao-kernel/
```

Live deployment is **out-of-scope** for this chart skeleton. Operator runbooks for installing and upgrading the chart against a real cluster will be delivered by future Epic 4 slices (E-4-3 operator-owned secret management, E-4-5 cluster security baseline). This README intentionally omits any live install/upgrade or apply-style command line; the invariant test asserts the absence of those forbidden command strings here.

## Schema validation

`values.schema.json` is enforced automatically by `helm template` when the chart is rendered. Notable constraints:

- `additionalProperties: false` on every object except a documented free-form allowlist (annotations, labels, nodeSelector, affinity) — see `test_values_schema_strict_closure_with_documented_freeform_allowlist`.
- `replicaCount` integer with `minimum: 1` (matches HARD RULE TEST cluster scale-to-zero ban).
- `image.repository`, `image.tag`, `image.pullPolicy` all required and non-empty.
- `serviceAccount.create` and `rbac.create` required booleans.
- `env.plain[].name + value` and `env.secretRefs[].name + secretName + secretKey` required when entries are present.

## Cross-AI peer review

This slice (E-4-1) was implemented by Anthropic Claude and reviewed by OpenAI Codex per the CLAUDE.md HARD RULE Cross-AI Peer Review (provider-level distinct). The cross-AI review evidence is recorded in `local-ai-review-evidence.v1.json` at the repository root; per-slice evidence and decision record live in `.claude/plans/E-4-1-HELM-CHART-SKELETON.md` and `.claude/plans/E-4-1-HELM-CHART-SKELETON.v1.json`.
