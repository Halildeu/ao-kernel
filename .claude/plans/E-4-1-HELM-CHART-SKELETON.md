# E-4-1 — Helm Chart Skeleton (V5 Epic 4)

> **Status:** ACCEPTED (post-impl Codex review AGREE; cross-AI provider-distinct).
> **Parent epic:** `.claude/plans/EPIC-4-KUBERNETES-HELM-MULTI-TENANT.md` §2 E-4-1
> **V5 roadmap:** `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md` §3 Epic 4 first slice
> **Branch:** `codex/epic-4-1-helm-chart`
> **Implementer:** Claude (Anthropic)
> **Reviewer:** Codex (OpenAI) — post-impl review via MCP

---

## 1. Scope (additive, low-risk)

Create the operator-installable **Helm chart skeleton** under `deploy/helm/ao-kernel/`. The chart is render-only; it does not embed any live cluster command, does not flip any runtime guard flag, does not modify any ao-kernel Python source, does not touch any GitHub Actions workflow, and does not modify `pyproject.toml`.

### Chart contents

| Path | Role |
|---|---|
| `Chart.yaml` | `apiVersion: v2`, `name: ao-kernel`, `type: application`, `version: 0.1.0`, `appVersion: 4.1.0` (manual pin against `ao_kernel.__version__`) |
| `values.yaml` | Defaults; `replicaCount: 1` (HARD RULE: scale-to-zero forbidden); no inline secrets; env block supports plain + secretKeyRef entries |
| `values.schema.json` | JSON Schema Draft 2020-12; `additionalProperties: false` everywhere; `replicaCount.minimum: 1` |
| `templates/_helpers.tpl` | Standard Helm name/fullname/labels/selectorLabels/serviceAccountName helpers |
| `templates/deployment.yaml` | Deployment with `replicas = .Values.replicaCount`; ServiceAccount-bound; envFrom configMap + secretKeyRef |
| `templates/service.yaml` | ClusterIP service with http + healthz + readyz ports |
| `templates/configmap.yaml` | Non-secret config (workspace_root + log_level) |
| `templates/serviceaccount.yaml` | Default SA, namespace-scoped |
| `templates/rbac.yaml` | Role + RoleBinding (namespace-scoped; ClusterRole forbidden by Epic 4 boundary) |
| `templates/NOTES.txt` | Post-install message: beta lifecycle, operator responsibilities, no live commands |
| `README.md` | Chart usage + six invariant bullets |

### Supporting files

| Path | Role |
|---|---|
| `.claude/plans/E-4-1-HELM-CHART-SKELETON.md` | This decision record |
| `.claude/plans/E-4-1-HELM-CHART-SKELETON.v1.json` | Schema-backed evidence artifact |
| `ao_kernel/defaults/schemas/e-4-1-helm-chart-evidence.schema.v1.json` | Evidence schema (Draft 2020-12 strict) |
| `tests/test_epic_4_1_helm_chart_skeleton.py` | Ten invariant test categories |
| `local-ai-review-evidence.v1.json` | Cross-AI review evidence |

---

## 2. Invariants (10 categories; machine-enforced by `tests/test_epic_4_1_helm_chart_skeleton.py`)

1. **shape** — `Chart.yaml` has `apiVersion: v2`, `name: ao-kernel`, `version`, `appVersion`; `values.yaml` exists; `templates/` contains the expected template files.
2. **no_guard_flip (key absence)** — Recursive grep across `deploy/helm/ao-kernel/` returns zero matches for the three runtime guard flag key strings.
3. **no_workflow_mutation** — `git diff --name-only origin/main..HEAD` contains zero entries under `.github/workflows/`.
4. **helm_template_deterministic** — Three sequential `helm template` renders are byte-identical (SHA256-equal).
5. **values_replicas_min_1** — `values.yaml` default `replicaCount: 1`; `values.schema.json` enforces `properties.replicaCount.minimum: 1`.
6. **no_secret_in_values** — Regex scan over `values.yaml` and templates for known secret patterns (`AKIA[0-9A-Z]{16}`, `sk-[A-Za-z0-9]{40,}`, `xoxb-`, `ghp_`, JWT-shaped tokens) returns zero matches; secret references are limited to `secretKeyRef`.
7. **evidence_validates** — `.claude/plans/E-4-1-HELM-CHART-SKELETON.v1.json` validates against `ao_kernel/defaults/schemas/e-4-1-helm-chart-evidence.schema.v1.json` under `Draft202012Validator`.
8. **write_set_exact_match** — Evidence `write_set` field equals `git diff --name-only origin/main..HEAD` (sorted, deduplicated).
9. **no_pyproject_change** — `git diff --name-only origin/main..HEAD` does not include `pyproject.toml`.
10. **chart_template_no_live_command** — `NOTES.txt` and `README.md` contain no `kubectl apply`, `helm install`, or `helm upgrade` strings.

---

## 3. Cross-AI peer review

- **Implementer:** Claude (provider `anthropic`).
- **Reviewer:** Codex (provider `openai`) via `mcp__codex__codex` (post-impl review thread).
- **Provider distinctness:** enforced by `reviewer_providers` `minItems: 2` + `uniqueItems: true` in the evidence schema; recorded in `local-ai-review-evidence.v1.json`.
- **Verdict flow:** AGREE / `ready_to_merge: true` → squash merge; REVISE → fix iter; RED → escalate to operator.

---

## 4. Decision

**ACCEPTED.** The slice is additive and low-risk. It does not change runtime behaviour and does not flip any guard flag. Future Epic 4 slices (E-4-2a multi-tenant boundary contract, E-4-3 operator-owned secret management, E-4-4 observability surface, E-4-5 security baseline, E-4-2b multi-tenant matrix final seal, E-4-6 helm-unittest runbook) extend the chart on this skeleton.

The production-readiness claim is deferred to V5 Epic 9 PR-Xfinal operator-bound supersession decision; the chart README and `NOTES.txt` reflect that deferral explicitly.

---

## 5. References

- Parent epic plan: `/Users/halilkocoglu/Documents/ao-kernel-epic4plan/.claude/plans/EPIC-4-KUBERNETES-HELM-MULTI-TENANT.md`
- Codex plan-time AGREE thread: `019e879d` iter-2 (recorded in parent epic plan §13 iter-2 absorb notes)
- ao-kernel version at slice author time: `4.1.0` (`ao_kernel/__init__.py::__version__`)
- HARD RULEs honoured: Cross-AI Peer Review (provider-level), TEST Cluster Scale-to-Zero YASAK, No Fake Work, Long-Term Permanent Solution Preferred, CI Red = No Merge
