# Coordination — Multi-Agent Lease, Fencing, Takeover

**Status:** FAZ-B PR-B0 contract pin (docs skeleton). Runtime implementation PR-B1.

## 1. Overview

ao-kernel provides lease-based coordination primitives so multiple coding-agent workflows can safely share workspace resources (git worktrees, evidence run directories, workflow run records) without corrupting each other's state. The contract in this document locks the semantic surface PR-B1 runtime must honour; any deviation in B1 regresses B0 acceptance tests.

The coordination model rests on four concepts:

- **Claim** — a durable per-resource lease record, owned by a single agent at a time, protected by CAS revision token.
- **Fencing token** — a strictly monotonic per-resource integer that invalidates stale operations after takeover.
- **Heartbeat** — caller-driven liveness signal; stale heartbeat eventually yields takeover eligibility.
- **Takeover** — structured reclamation of an expired claim by a different agent, with fencing token advance.

Coordination is POSIX-only (per [CLAUDE.md §3](../CLAUDE.md)); Windows raises `LockPlatformNotSupported` (deferred to FAZ-C or later).

## 2. Claim Lifecycle

```
acquire ── heartbeat ─┬─ heartbeat (revival in grace) ── heartbeat ─┐
                      │                                              │
                      └─ release                                     └─ expire ── takeover (grace elapsed)
```

## 3. Storage Model

Claim records live under `{project_root}/.ao/claims/`. Three artefact kinds:

| Path | Role |
|---|---|
| `{project_root}/.ao/claims/{resource_id}.v1.json` | **SSOT** — durable claim record per resource. Schema: `claim.schema.v1.json`. |
| `{project_root}/.ao/claims/_index.v1.json` | **Derived cache** — `agent_id → [resource_id, ...]` reverse index. Rebuildable from a full claim file scan on drift; NOT source of truth. Schema: inline in PR-B1. |
| `{project_root}/.ao/claims/_fencing.v1.json` | **Fencing state** — `resource_id → {next_token, last_owner_agent_id, last_released_at}`. Survives release (claim file is deleted, but fencing state is preserved). Schema: `fencing-state.schema.v1.json`. |
| `{project_root}/.ao/claims/claims.lock` | Single workspace-level lock; held for the whole read-mutate-write cycle of any claim mutation. |

Rationale for the SSOT + derived cache split: a single global file would force all concurrent agents through one serialisation point; per-resource files + an index reduces the hot path to the files an agent actually touches. The index can drift (e.g., mid-mutation crash between file write and index update), so B1 runtime rebuilds it under the same `claims.lock` on detection.

**CAS protocol:** every claim mutation reads the current `revision` hash, applies the change to a working copy, computes the new `revision`, and writes atomically (tempfile + fsync + rename) with `expected_revision` guard. Conflict yields `ClaimRevisionConflictError`; caller retries.

## 4. Fencing Token

The fencing token is a strictly monotonic, never-reset, never-wrapping integer per resource. Python `int` is unbounded, so no wrap behaviour is defined.

Lifecycle:

1. **Acquire** (new resource): read `_fencing.v1.json` → if resource absent, `next_token = 0`, record `next_token = 1`. Token issued: 0.
2. **Acquire** (previously released): read `_fencing.v1.json[resource_id].next_token` → issue that token → increment `next_token` → CAS write `_fencing.v1.json`.
3. **Takeover**: same as acquire (next_token advances by 1; the previous owner's token is now strictly smaller and therefore stale).
4. **Release**: claim file deleted; `_fencing.v1.json[resource_id]` retained with updated `last_released_at`. The token authority survives the claim lifetime.

Stale token detection is caller-driven: any operation that accepts a `fencing_token` (e.g., `Executor.run_step(driver_managed=True)`) compares against the current `_fencing.v1.json[resource_id].next_token - 1` (the live issued token). Mismatch raises `ClaimStaleFencingError` before any side effect.

## 5. Heartbeat

Heartbeat is **caller-driven**, NOT evidence-based. The coordination runtime does not inspect the evidence stream to decide liveness; per [CLAUDE.md §2](../CLAUDE.md) evidence is a fail-open side-channel and must not gate correctness-critical decisions.

`claim.heartbeat()` updates `heartbeat_at` under CAS. The method is the explicit liveness signal; callers invoke it according to their own cadence (a long-running adapter may call it every N seconds; a short step may skip it entirely).

An evidence event (`claim_heartbeat`) is emitted for audit visibility, but the liveness decision is not read from evidence.

## 6. Expiry Authority (locked)

The following table is the authoritative source for B1 runtime; deviation regresses B0 acceptance.

| Decision | Value | Rationale |
|---|---|---|
| **Authoritative expiry field** | `effective_expires_at = heartbeat_at + expiry_seconds` (computed at evaluation time) | `expires_at` in `claim.schema.v1.json` is a **derived** field: written by mutators for validation/debug but not the source of truth. Source of truth = `heartbeat_at`. |
| **Takeover threshold** | `now > heartbeat_at + expiry_seconds + takeover_grace_period_seconds` | Takeover is not attempted before the grace period expires. A second agent that tries inside grace receives `CLAIM_CONFLICT_GRACE`. |
| **Second acquire in grace** | `CLAIM_CONFLICT_GRACE` error (distinct from `CLAIM_CONFLICT`) | Owner may still revive; takeover would be premature. The distinct error lets callers distinguish "owner might come back" from "owner is here right now". |
| **Owner heartbeat in grace** | **Claim revival** — `heartbeat_at` updated under CAS; `effective_expires_at` moves forward | While the owner can prove liveness, the claim stays alive. |
| **In-flight step, stale fencing** | `ClaimStaleFencingError`, raised immediately at `driver.run_step()` entry | Stale token means takeover has happened; the stale holder's side effects must be blocked. |
| **`max_claims_per_agent` counting** | Count **non-expired** claims only (`now ≤ effective_expires_at + grace`) | Expired but uncleaned records may linger in `_index.v1.json` until the next cleanup cycle; quota must reflect live claims, not bookkeeping artefacts. |
| **Multi-resource atomic acquire** | **v1: unsupported** — `acquire_claim(resource_id)` accepts a single resource | Atomic multi-acquire is deferred to FAZ-C. Callers that need multiple resources must acquire sequentially and handle partial failure; the shape of the higher-level operation is explicit here so B1 does not silently mis-support it. |
| **Cleanup cycle** | Caller-driven `prune_expired_claims()`; **no driver background loop** | Liveness correctness must not depend on a timer, daemon, or side-channel; callers request cleanup explicitly when they want it. |

## 7. Evidence Events (PR-B1 runtime)

B1 extends the PR-A evidence taxonomy from 18 kinds to 24 with six coordination-specific events. All six are additive; 18-kind invariant stays intact for B0.

| Event kind | Fired when |
|---|---|
| `claim_acquired` | Successful `acquire_claim` (new or post-takeover) |
| `claim_released` | Successful `release_claim` (owner-initiated) |
| `claim_heartbeat` | `claim.heartbeat()` update |
| `claim_expired` | Cleanup scan detects stale claim past grace |
| `claim_takeover` | Successful takeover by a different agent |
| `claim_conflict` | Attempted acquire/takeover blocked by live owner (`CLAIM_CONFLICT`) or grace (`CLAIM_CONFLICT_GRACE`); payload distinguishes the two |

## 8. Policy Binding

`policy_coordination_claims.v1.json` controls coordination behaviour. Shipped dormant (`enabled: false`) in B0; operators opt in by overriding at `{project_root}/.ao/policies/`. Defaults:

- `heartbeat_interval_seconds: 30`
- `expiry_seconds: 90`
- `takeover_grace_period_seconds: 15`
- `max_claims_per_agent: 5`
- `claim_resource_patterns: ["*"]`

`policy_multi_agent_coordination.v1.json` (existing, separate) covers worktree/branch semantics and is NOT modified; the two policies are independent surfaces.

## 9. Cross-References

- **Terminology (PR-B0 contract):** `response_parse` = transport-level canonical envelope extraction (HTTP body → envelope shape, see [agent-adapter-contract schema $defs.invocation_http.response_parse](../ao_kernel/defaults/schemas/agent-adapter-contract.schema.v1.json)); `output_parse` = capability-specific typed artifact extraction (envelope → schema-validated payload, see [agent-adapter-contract schema $defs.output_parse](../ao_kernel/defaults/schemas/agent-adapter-contract.schema.v1.json)). Two distinct contract layers that happen to share vocabulary.
- **Layer separation:** Claim/fencing primitives live in `ao_kernel/coordination/` (PR-B1, new public package). `Executor.run_step(driver_managed=True)` (PR-A4b) checks `fencing_token` at entry; artifact writes go through `artifacts.write_artifact()` (PR-A4b internal).
- Schemas: [`claim.schema.v1.json`](../ao_kernel/defaults/schemas/claim.schema.v1.json), [`fencing-state.schema.v1.json`](../ao_kernel/defaults/schemas/fencing-state.schema.v1.json), [`policy-coordination-claims.schema.v1.json`](../ao_kernel/defaults/schemas/policy-coordination-claims.schema.v1.json).
- Adversarial review: [CNS-20260416-028v2 consensus](../.ao/consultations/CNS-20260416-028v2.consensus.md), especially §B2 / B2' / Expiry Authority resolution.

## 10. Document Status

Skeleton in PR-B0 commit 1. Edge-case examples, operator override walkthrough, and failure recovery runbook land in PR-B0 commit 5 (docs final pass).
