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
| `claim_acquired` | Successful fresh `acquire_claim` — new resource OR reclaim-of-released. NOT emitted on post-takeover (see `claim_takeover` below). |
| `claim_released` | Successful `release_claim` (owner-initiated) |
| `claim_heartbeat` | `heartbeat()` update. Audit only — the liveness decision is the claim record's `heartbeat_at`, never the event. |
| `claim_expired` | `prune_expired_claims` detects stale claim past grace |
| `claim_takeover` | Past-grace reclaim by a different agent. Mutually exclusive with `claim_acquired` — a single acquire/takeover path emits exactly one of the two. |
| `claim_conflict` | Attempted acquire/takeover blocked by live owner (`CLAIM_CONFLICT`) or grace window (`CLAIM_CONFLICT_GRACE`); payload includes `current_fencing_token` (B6v2 for FAZ-B master plan §10 race test). |

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

## 10. Runtime Impl Notes (PR-B1)

The B0-pinned contract above is implemented by `ao_kernel/coordination/` (PR-B1 shipped with commits `150b508`, `d7b23d2`, `3230edc`, `bf948a3`). Operators using this runtime should know the following invariants the implementation honours so debugging + extension remain predictable.

### 10.1 Public API surface

```python
from ao_kernel.coordination import ClaimRegistry

registry = ClaimRegistry(workspace_root, evidence_sink=None)

# Acquire / lifecycle
claim = registry.acquire_claim(resource_id, owner_agent_id, policy=None)
registry.heartbeat(resource_id, claim_id, owner_agent_id)
registry.release_claim(resource_id, claim_id, owner_agent_id)

# Takeover (explicit past-grace reclaim)
new_claim = registry.takeover_claim(resource_id, new_owner_agent_id, policy=None)

# Read / validate / list
registry.get_claim(resource_id)                # -> Claim | None
registry.validate_fencing_token(resource_id, token)  # -> raises on mismatch
registry.list_agent_claims(owner_agent_id)     # live-count only

# Admin
registry.prune_expired_claims(policy=None, *, max_batch=None)
```

Callers **MUST** hold onto the `Claim` dataclass returned by `acquire_claim` (or `takeover_claim`) — `heartbeat` and `release_claim` take both `resource_id` and `claim_id` (plus `owner_agent_id`) as arguments so the registry does O(1) direct file lookup rather than maintaining a reverse index.

### 10.2 Fail-closed vs fail-open

- **Fail-closed (raise, never silently absorb):**
  - Policy load errors (malformed JSON, schema violation in workspace override).
  - `resource_id` validation (`_validate_resource_id` regex; no path separators, wildcards, whitespace, leading non-alphanumeric).
  - `claim_resource_patterns` allowlist denial.
  - SSOT corruption — `{resource_id}.v1.json` or `_fencing.v1.json` parse / schema / revision-hash mismatch raises `ClaimCorruptedError` and propagates. The on-disk file is NOT repaired or overwritten; operator intervention required.
  - Dormant-policy gate — `policy.enabled=false` raises `ClaimCoordinationDisabledError` on every public API call.

- **Fail-open (log warning, keep going):**
  - Evidence emission. `_safe_emit_coordination_event` wraps the caller-injected sink in try/except; emit failures are logged at `warning` level with `{"coordination_kind": kind, "error": repr(e)}` in `extra` for parseability. Coordination correctness **never** depends on emission success — this is CLAUDE.md §2 side-channel contract.
  - Derived `_index.v1.json` cache. Corrupt or drifted index triggers silent rebuild from the per-resource SSOT scan under `claims.lock`. Rebuild never masks SSOT corruption — errors during the rebuild scan still raise `ClaimCorruptedError`.

### 10.3 Write ordering + atomicity

Every mutation acquires `claims.lock` (POSIX `fcntl` via `ao_kernel._internal.shared.lock.file_lock`) for the full read-mutate-write cycle. Inside the lock:

- **Acquire / takeover:** `_fencing.v1.json` (CAS) → `{resource_id}.v1.json` (atomic write) → `_index.v1.json` (derived last).
- **Release / prune:** load + validate `_fencing.v1.json` (pre-delete fail-closed check) → delete `{resource_id}.v1.json` → CAS-write `_fencing.v1.json` audit update → remove from `_index.v1.json`.

The release order ensures a corrupt fencing state raises `ClaimCorruptedError` while the claim file is still recoverable on disk; callers can restore the fencing artefact and retry release.

### 10.4 Fencing-token validation

`validate_fencing_token(resource_id, token)` implements **exact-equality** semantics. The currently-live issued token is `next_token - 1`; the supplied token must match it exactly. Both stale tokens (agent-victim of takeover) and future / fabricated tokens raise `ClaimStaleFencingError`. This is stricter than a one-sided "at least as recent" check and catches programmer errors that would otherwise slip through.

### 10.5 Forward-only fencing reconcile

`_reconcile_fencing_with_claims_locked()` (internal ops helper) recomputes fencing `next_token` per resource as `max(state.resources[rid].next_token, max_claim_fencing_token + 1)`. Fencing state **never decreases**; if the state already advanced past what the persisted claims would suggest (e.g. after a series of acquire/release cycles whose claim files were released), the reconcile preserves the advance rather than rewinding. Callers that want to force a full recovery run the helper under `claims.lock`.

### 10.6 Quota semantics (`max_claims_per_agent`)

- `max_claims_per_agent = 0` ⇒ **unlimited** (quota disabled). The enforcement line is `if limit > 0 and count >= limit: raise`, so `limit=0` bypasses the check regardless of count.
- Count is **live-count** only — expired-but-unpruned claims (still on disk past grace) are excluded. The registry loads each claim file referenced in `_index.v1.json` and applies the liveness predicate; stale index entries are tolerated.
- Quota check runs on **both** `acquire_claim` and `takeover_claim` paths (the takeover path previously skipped it; B1v5 fixed that).

### 10.7 Executor fencing entry

`Executor(claim_registry=…).run_step(fencing_token=…, fencing_resource_id=…)` delegates to `ClaimRegistry.validate_fencing_token` at entry, BEFORE any evidence emit, worktree build, or adapter invoke. On stale fencing the `ClaimStaleFencingError` propagates to the caller (typically `MultiStepDriver`), which applies its own `step_failed` emission + `error_category="other"` + `code="STALE_FENCING"` mapping per the PR-A4b handler. Canonical event order (`step_started` → `adapter_invoked` → ... → `step_completed` | `step_failed`) stays intact — the executor itself emits nothing on the stale-fencing path.

Passing only one of the fencing pair raises `ValueError`. Supplying fencing kwargs without `claim_registry` injected at construction also raises.

## 11. Document Status

- Contract surface pinned in PR-B0 commit 1 (schemas + dormant policy + docs skeleton).
- Runtime shipped in PR-B1 commits `150b508` → `bf948a3` (plan §3 Write Order 7 steps across 5 commits). Operator override walkthrough + failure recovery runbook expand further in PR-B5 (metrics + observability) scope.
