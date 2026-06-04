# E-4-2b — Multi-Tenant Matrix Final Seal

> V5 Epic 4 (Deployment, operations, tenancy). Final advisory seal for the
> `tenant_isolation_matrix.v1.json` artifact after E-4-3, E-4-4, and E-4-5
> landed. This is a high-risk documentation/schema seal because operators may
> use it to configure multi-tenant Kubernetes boundaries.

## Goal

Promote the E-4-2a placeholder matrix to the E-4-2b final advisory seal:

- `matrix_status: "e_4_2b_final_seal"`
- all seven dimensions use `entry_status: "filled"`
- every dimension carries a real `downstream_evidence_ref` that exists in the
  repository
- the final matrix still preserves the four advisory constants per dimension:
  `runtime_enforced: false`, `operator_enforceable: true`,
  `operator_action_required: true`, and `live_validated: false`

## What This Slice Delivers

1. `.claude/plans/tenant_isolation_matrix.v1.json` moves from placeholder to
   final advisory seal and binds downstream refs.
2. `docs/MULTI-TENANT-DEPLOYMENT.md` is refreshed from early-seal wording to
   final-seal wording while preserving advisory language.
3. `ao_kernel/defaults/schemas/e-4-2b-tenant-isolation-matrix.schema.v1.json`
   pins the E-4-2b final-state overlay.
4. `ao_kernel/defaults/schemas/e-4-2b-multi-tenant-final-seal-evidence.schema.v1.json`
   pins the E-4-2b evidence artifact and 3-way review requirement.
5. `tests/test_epic_4_2b_matrix_invariants.py` verifies final-state matrix,
   downstream refs, advisory constants, and no overclaim language.
6. `tests/test_epic_4_2b_write_set_invariant.py` verifies exact write-set,
   no workflow mutation, no pyproject change, and no runtime module mutation
   outside schema JSON.

## Downstream Binding

| Dimension | Downstream evidence ref | Why |
|---|---|---|
| `namespace_isolation` | `.claude/plans/E-4-1-HELM-CHART-SKELETON.v1.json` | chart skeleton proves namespace-scoped chart shape and no cluster-scoped default |
| `rbac_scope` | `.claude/plans/E-4-1-HELM-CHART-SKELETON.v1.json` | chart skeleton proves Role/RoleBinding scope |
| `secret_isolation` | `.claude/plans/E-4-3-POSTGRES-PROVISIONING.md` | E-4-3 records operator-owned secretKeyRef discipline |
| `network_policy` | `.claude/plans/E-4-5-NETWORKPOLICY-PSS.md` | E-4-5 records NetworkPolicy + PSS baseline |
| `resource_quota` | `deploy/helm/ao-kernel/values.yaml` | chart values expose pod resource requests/limits; Namespace ResourceQuota stays operator-applied |
| `audit_boundary` | `.claude/plans/E-4-4-OBSERVABILITY-SURFACE.md` | E-4-4 records observability surface and per-tenant telemetry boundary inputs |
| `cost_tracking_advisory` | `.claude/plans/E-4-4-OBSERVABILITY-SURFACE.md` | E-4-4 supplies telemetry surface; cost tracking remains advisory dashboard work |

## Boundaries

- No guard flag flip.
- No `.github/workflows/**` mutation.
- No runtime module mutation except new schema JSON files under
  `ao_kernel/defaults/schemas/`.
- No live cluster command embedded in docs.
- No live cross-tenant attack test claim.
- No production readiness or support widening claim.

## Review Requirement

E-4-2b is high-risk. This PR is implemented by Codex/OpenAI, so the evidence
artifact records a 3-provider quorum with two independent cross-provider
reviewers:

- OpenAI/Codex implementation record
- Anthropic/Claude independent review
- MiniMax/Mavis independent review

OpenAI/Codex adversarial self-review may be useful, but it is not counted as
independent release evidence when OpenAI/Codex is the implementer.

AI output remains evidence only. Release authority remains the repo-owned
`ao-release-gate` required check plus GitHub ruleset enforcement.
