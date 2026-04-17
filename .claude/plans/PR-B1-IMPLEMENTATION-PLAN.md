# PR-B1 Implementation Plan v5 — Coordination Runtime (Lease / Fencing / Takeover)

**Tranche B PR 2/9** — post CNS-029v3 iter-1 PARTIAL (3B + 4W absorbed). Runtime for the B0-pinned coordination contract.

**v5 key absorb (CNS-029v3 iter-1):**
- **B1 takeover_claim live/grace gate:** Public `takeover_claim()` v4'te gate bypass ediyordu (`_takeover_locked()` doğrudan write path'e giriyordu, live claim'i zorla takeover edebilirdi). v5'te `_takeover_locked()` entry'sine **live/grace pre-check** eklendi: `now <= effective_expires` → `ClaimConflictError`; `now <= effective_expires + grace` → `ClaimConflictGraceError`; sadece `now > effective_expires + grace` past-grace path takeover'a izin verir. B0 "takeover ancak past-grace" kuralı runtime-enforced.
- **B2 claim CAS `save_claim_cas(expected_revision)` helper:** v4'te heartbeat snippet "CAS" diyordu ama `write_text_atomic()` direk yazıyordu (expected_revision check YOKTU). v5'te yeni helper:
  ```python
  def save_claim_cas(workspace_root, resource_id, new_claim_dict, *, expected_revision) -> None
  ```
  Pattern: `canonical_store.save_store_cas` mirror. Load existing → compute current_revision → compare with `expected_revision` → mismatch `ClaimRevisionConflictError` → else write_text_atomic. Heartbeat flow artık `save_claim_cas(workspace_root, resource_id, updated_dict, expected_revision=claim.revision)` kullanır.
- **B3 release/prune fail-closed order (fencing validate before delete):** v4 write order "claim DELETE first → fencing audit" `_fencing.v1.json` corrupt ise `ClaimCorruptedError` delete sonrası fırlıyordu (kısmi state). v5'te revize:
  1. **fencing state load + validate FIRST** (fail-closed `ClaimCorruptedError` delete öncesi fırlar)
  2. `current_rev = fencing_state_revision(state.to_dict())` hesapla
  3. `new_state = update_on_release(state, resource_id, owner_agent_id)`
  4. Claim DELETE
  5. `save_fencing_state_cas(workspace_root, new_state, current_rev)`
  6. `_index` remove LAST
  - Corruption detection pre-delete; fail-closed B0 atomicity ilkesi korunur.
- **W1 executor anchor fix:** v4 snippet `run_step()` içinde `step_started` emit'i gösteriyordu — gerçek kod `_run_adapter_step()` içinde emit ediyor. v5 yaklaşımı: **stale fencing check `run_step()` entry'de step_started emit ÖNCESİ yapılır, evidence emit HİÇ yok; `ClaimStaleFencingError` raise → MultiStepDriver catch edip step_record.state="failed" + step_failed emit eder (mevcut PR-A4b handle)**. Bu temiz çözüm canonical order bozmuyor (step_started henüz emit edilmemiş; step_failed driver tarafından emit edilecek).
- **W2 evidence_redaction binding:** v4 sink örneği `emit_event(..., redaction=...)` bağlamıyordu; schema alanı ölü kalıyordu. v5'te plan §2.7'ye caller injection örneği genişletildi: sink wrapper `policy_coordination_claims.evidence_redaction` config'ini load edip `emit_event(redaction=...)` bağlar (ya da policy-aware helper `build_coordination_sink(workspace_root, policy, run_id, actor)` önerilir).
- **W3 quota live-count semantic:** `_count_agent_claims(owner_agent_id)` **non-expired** claim'leri sayar (B0 invariant: "Count NON-EXPIRED claims only"). v5 implementasyon notu: `_count_agent_claims` index entries'inin her biri için claim file load edip `effective_expires_at + grace` check yapar; expired-but-unpruned → hariç tutulur. Bu O(k) per-check (k = agent claim count, small).
- **W4 core executor fail-open note:** Plan §2.7'ye explicit note eklendi: "Core executor evidence emission (`step_started`, `step_failed`, `adapter_invoked`, ...) PR-A3'te yerleşik convention'ını kullanır; B1 coordination wrapper sadece `claim_*` event'leri için fail-open sağlar. Core executor path'inin fail-open dönüşümü FAZ-C scope (out of B1)."
- **Yeni error type (B1v5):** `ClaimNotFoundError(resource_id)` — public `takeover_claim` veya internal lookup resource_id için claim yok (absent file).

**v4 key absorb (devralındı):**
- B v4 heartbeat/release lookup contract `(resource_id, claim_id, owner_agent_id)` üçlüsü; W1v4 executor imza fix; W2v4 step_failed flat payload; W3v4 single-emit delegate; W4v4 evidence_sink typing `Callable[..., Any]`.

**v3 key absorb:**
- B1v3 quota takeover + `0=unlimited`; B2v3 fencing exact-equality; B3v3 forward-only monotonic; B4v3 evidence_sink injection; B5v3 takeover validator preamble.

**v2 key absorb:**
- B1v2 quota SSOT; B2v2 write ordering; B3v2 safe-emit wrapper; B4v2 resource_id validator; B5v2 re-entrant lock avoidance; B6v2 CLAIM_CONFLICT payload; W1-W5v2.

## 1. Amaç

B0 foundation kontratları (merged #96, fbf7229) için runtime impl: `ao_kernel/coordination/` yeni public package. Multi-agent coding-agent workflow'ları `.ao/claims/`-kökenli lease primitive'iyle paylaşılan workspace kaynaklarını koruyacak. PR-A4b `Executor.run_step(driver_managed=True)` fencing-token check girişi B1'de ekleniyor (B0 söz verdi, PR-A4b implement etmedi — **kritik drift fix**).

### Kapsam özeti

| Katman | Modül | Satır (est.) |
|---|---|---|
| Public package | `ao_kernel/coordination/__init__.py` | ~40 |
| Claim record | `ao_kernel/coordination/claim.py` + `save_claim_cas` helper | ~320 |
| Fencing state | `ao_kernel/coordination/fencing.py` | ~160 |
| Registry | `ao_kernel/coordination/registry.py` | ~420 |
| Policy | `ao_kernel/coordination/policy.py` | ~120 |
| Typed errors | `ao_kernel/coordination/errors.py` (13 types) | ~145 |
| Executor entry | `executor.py` delta | ~40 delta (no emit inside run_step stale path) |
| Evidence taxonomy | `evidence_emitter.py` delta | ~8 delta |
| Tests | 5 test files, ~92 test | ~980 |
| Docs | `docs/COORDINATION.md` runtime notes + W1 fix | ~60 delta |
| CHANGELOG | `[Unreleased]` PR-B1 | ~60 |
| **Toplam** | 6 yeni modül + 2 code delta + 1 docs delta + ~92 test | **~2350 satır** |

- Yeni evidence kind: **6** (additive 18 → 24)
- Yeni adapter capability: 0
- Yeni core dep: 0
- Yeni schema: 0 (B0'da shipped)
- Yeni error type: **13** (+1 yeni v5: `ClaimNotFoundError`)

## 2. Scope İçi

### 2.1 `ao_kernel/coordination/claim.py`

```python
@dataclass(frozen=True)
class Claim:
    claim_id: str
    owner_agent_id: str
    resource_id: str
    fencing_token: int
    acquired_at: str
    heartbeat_at: str   # SSOT liveness
    expires_at: str | None  # DERIVED
    revision: str       # sha256:<64hex>
```

**Helpers:**
- `claim_revision(claim_dict) -> str` — canonical JSON hash (revision omitted)
- `claim_to_dict(claim)` / `claim_from_dict(doc)` — schema validate (SSOT fail-closed `ClaimCorruptedError`)
- **`save_claim_cas(workspace_root, resource_id, new_claim_dict, *, expected_revision) -> None` (B2v5):** canonical_store.save_store_cas mirror
  1. Load existing claim if exists (None if absent — treat as revision mismatch unless creating)
  2. Compute `current_revision = load_existing.revision` (if exists)
  3. If `expected_revision != current_revision` → `ClaimRevisionConflictError(resource_id, expected, actual)`
  4. Validate `new_claim_dict["revision"] == claim_revision(new_claim_dict)` (caller-set hash correctness)
  5. `write_text_atomic(claim_path, claim_to_json(new_claim_dict))`
  
  **Usage:** heartbeat flow `save_claim_cas(ws, resource_id, updated_dict, expected_revision=claim.revision)`.

### 2.2 `ao_kernel/coordination/fencing.py`

- `load_fencing_state(workspace_root) -> FencingState` — SSOT fail-closed on parse/schema failure
- `next_token(state, resource_id) -> (int, FencingState)`
- `update_on_release(state, resource_id, agent_id) -> FencingState`
- **`validate_fencing_token(state, resource_id, token)` (B2v3 exact-equality):** `live = next_token - 1`; `token != live` → `ClaimStaleFencingError(resource_id, supplied_token, live_token)`. Missing entry → raise.
- **`fencing_state_revision(state_dict) -> str` (W3v2):** runtime-only canonical JSON hash.
- `save_fencing_state_cas(workspace_root, state, expected_revision)`

**Invariants:**
- Token monotonic non-negative, never reset/wrap
- Release retains `_fencing` entry (audit only)
- Takeover `next_token` +1
- **Forward-only recovery (B3v3):** `new_next = max(current, max_claim+1)` — never decreases

### 2.3 `ao_kernel/coordination/registry.py`

**Public API (W4v3 pin; B v4 claim_id lookup; B1v5 takeover gate):**

```python
class ClaimRegistry:
    def __init__(
        self,
        workspace_root: Path,
        *,
        evidence_sink: Callable[[str, Mapping[str, Any]], Any] | None = None,
    ) -> None: ...

    def acquire_claim(self, resource_id: str, owner_agent_id: str, policy=None) -> Claim: ...
    def heartbeat(self, resource_id: str, claim_id: str, owner_agent_id: str) -> Claim: ...
    def release_claim(self, resource_id: str, claim_id: str, owner_agent_id: str) -> None: ...
    def takeover_claim(self, resource_id: str, new_owner_agent_id: str, policy=None) -> Claim: ...
    def get_claim(self, resource_id: str) -> Claim | None: ...
    def validate_fencing_token(self, resource_id: str, token: int) -> None: ...
    def prune_expired_claims(self, policy=None, *, max_batch: int | None = None) -> list[str]: ...
    def list_agent_claims(self, owner_agent_id: str) -> list[Claim]: ...
```

**Acquire flow (public):**

```python
def acquire_claim(self, resource_id, owner_agent_id, policy=None) -> Claim:
    policy = policy or load_coordination_policy(self._workspace_root)
    if not policy.enabled:
        raise ClaimCoordinationDisabledError(...)
    _validate_resource_id(resource_id)  # B4v2
    if not match_resource_pattern(policy, resource_id):
        raise ClaimResourcePatternError(...)
    with file_lock(self._workspace_root / ".ao/claims/claims.lock"):
        return self._acquire_or_takeover_locked(
            resource_id, owner_agent_id, policy, intent="acquire",
        )
```

**`_acquire_or_takeover_locked` — private (W3v4 single-emit delegate):**

```python
def _acquire_or_takeover_locked(self, resource_id, owner_agent_id, policy, *, intent) -> Claim:
    current = self._load_claim_if_exists(resource_id)  # SSOT fail-closed on corrupt
    if current is not None:
        now = now_utc()
        effective_expires = parse(current.heartbeat_at) + timedelta(seconds=policy.expiry_seconds)
        if now <= effective_expires:
            # Live → conflict + emit + raise
            self._safe_emit("claim_conflict", {
                "resource_id": resource_id, "requesting_agent_id": owner_agent_id,
                "current_owner_agent_id": current.owner_agent_id,
                "current_fencing_token": current.fencing_token,
                "conflict_kind": "CLAIM_CONFLICT", "now": iso(now),
            })
            raise ClaimConflictError(resource_id, current.owner_agent_id, current.fencing_token)
        grace_end = effective_expires + timedelta(seconds=policy.takeover_grace_period_seconds)
        if now <= grace_end:
            # Grace → distinct conflict + emit + raise
            self._safe_emit("claim_conflict", {..., "conflict_kind": "CLAIM_CONFLICT_GRACE", ...})
            raise ClaimConflictGraceError(resource_id, current.owner_agent_id, current.fencing_token)
        # Past-grace → delegate to _takeover_locked and IMMEDIATELY RETURN (W3v4 single emit)
        return self._takeover_locked(resource_id, owner_agent_id, policy, skip_gate=True)

    # Absent → acquire path
    self._ensure_index_consistent()
    count = self._count_agent_claims(owner_agent_id)  # W3v5 non-expired only
    if policy.max_claims_per_agent > 0 and count >= policy.max_claims_per_agent:
        raise ClaimQuotaExceededError(owner_agent_id, count, policy.max_claims_per_agent)

    # Write ordering (B2v2): fencing → claim → index
    state = load_fencing_state(self._workspace_root)
    current_fencing_rev = fencing_state_revision(state.to_dict())
    token, new_state = next_token(state, resource_id)
    save_fencing_state_cas(self._workspace_root, new_state, current_fencing_rev)
    claim_dict = {
        "claim_id": uuid4_str(), "owner_agent_id": owner_agent_id,
        "resource_id": resource_id, "fencing_token": token,
        "acquired_at": iso(now), "heartbeat_at": iso(now),
        "expires_at": iso(now + timedelta(seconds=policy.expiry_seconds)),
    }
    claim_dict["revision"] = claim_revision(claim_dict)
    # NEW claim (no expected_revision — creating), use write_text_atomic directly
    write_text_atomic(claim_path(resource_id), json_dumps(claim_dict))
    self._update_index_locked(claim_dict, action="add")

    self._safe_emit("claim_acquired", {
        "resource_id": resource_id, "owner_agent_id": owner_agent_id,
        "claim_id": claim_dict["claim_id"], "fencing_token": token,
        "acquired_at": claim_dict["acquired_at"],
    })
    return claim_from_dict(claim_dict)
```

**`_takeover_locked` — private (B1v5 live/grace gate + B1v3 quota):**

```python
def _takeover_locked(
    self,
    resource_id,
    new_owner_agent_id,
    policy,
    *,
    skip_gate: bool = False,  # True when called from _acquire_or_takeover_locked (gate already checked)
) -> Claim:
    prev = self._load_claim_if_exists(resource_id)
    if prev is None:
        raise ClaimNotFoundError(resource_id)  # B1v5 new error
    # B1v5 LIVE/GRACE GATE — takeover only past-grace
    if not skip_gate:
        now = now_utc()
        effective_expires = parse(prev.heartbeat_at) + timedelta(seconds=policy.expiry_seconds)
        grace_end = effective_expires + timedelta(seconds=policy.takeover_grace_period_seconds)
        if now <= effective_expires:
            raise ClaimConflictError(resource_id, prev.owner_agent_id, prev.fencing_token)
        if now <= grace_end:
            raise ClaimConflictGraceError(resource_id, prev.owner_agent_id, prev.fencing_token)
    # Past-grace — safe to takeover
    # B1v3 quota on takeover path
    self._ensure_index_consistent()
    count = self._count_agent_claims(new_owner_agent_id)
    if policy.max_claims_per_agent > 0 and count >= policy.max_claims_per_agent:
        raise ClaimQuotaExceededError(new_owner_agent_id, count, policy.max_claims_per_agent)
    # Write order same as acquire
    state = load_fencing_state(self._workspace_root)
    current_fencing_rev = fencing_state_revision(state.to_dict())
    token, new_state = next_token(state, resource_id)
    save_fencing_state_cas(self._workspace_root, new_state, current_fencing_rev)
    new_claim_dict = {
        "claim_id": uuid4_str(), "owner_agent_id": new_owner_agent_id,
        "resource_id": resource_id, "fencing_token": token,
        "acquired_at": iso(now_utc()), "heartbeat_at": iso(now_utc()),
        "expires_at": iso(now_utc() + timedelta(seconds=policy.expiry_seconds)),
    }
    new_claim_dict["revision"] = claim_revision(new_claim_dict)
    write_text_atomic(claim_path(resource_id), json_dumps(new_claim_dict))
    self._update_index_locked(new_claim_dict, action="replace", prev_owner=prev.owner_agent_id)

    self._safe_emit("claim_takeover", {
        "resource_id": resource_id,
        "new_owner_agent_id": new_owner_agent_id, "prev_owner_agent_id": prev.owner_agent_id,
        "new_claim_id": new_claim_dict["claim_id"], "prev_claim_id": prev.claim_id,
        "new_fencing_token": token, "prev_fencing_token": prev.fencing_token,
        "takeover_at": iso(now_utc()),
    })
    return claim_from_dict(new_claim_dict)
```

**Public `takeover_claim` (B5v3 + B1v5 gate runs in _takeover_locked):**

```python
def takeover_claim(self, resource_id, new_owner_agent_id, policy=None) -> Claim:
    policy = policy or load_coordination_policy(self._workspace_root)
    if not policy.enabled: raise ClaimCoordinationDisabledError(...)
    _validate_resource_id(resource_id)
    if not match_resource_pattern(policy, resource_id):
        raise ClaimResourcePatternError(...)
    with file_lock(...):
        # skip_gate=False → _takeover_locked enforces live/grace check (B1v5)
        return self._takeover_locked(resource_id, new_owner_agent_id, policy, skip_gate=False)
```

**Heartbeat (B v4 lookup + B2v5 CAS helper):**

```python
def heartbeat(self, resource_id, claim_id, owner_agent_id) -> Claim:
    _validate_resource_id(resource_id)
    with file_lock(...):
        claim = self._load_claim_if_exists(resource_id)  # O(1) direct
        if claim is None:
            raise ClaimAlreadyReleasedError(resource_id, claim_id)
        if claim.claim_id != claim_id or claim.owner_agent_id != owner_agent_id:
            raise ClaimOwnershipError(claim_id, owner_agent_id, claim.owner_agent_id)
        policy = load_coordination_policy(self._workspace_root)
        now = now_utc()
        grace_end = parse(claim.heartbeat_at) + timedelta(
            seconds=policy.expiry_seconds + policy.takeover_grace_period_seconds
        )
        if now > grace_end:
            raise ClaimAlreadyReleasedError(resource_id, claim_id)
        # B2v5 CAS — save_claim_cas with expected_revision
        updated_dict = {**claim_to_dict(claim),
                        "heartbeat_at": iso(now),
                        "expires_at": iso(now + timedelta(seconds=policy.expiry_seconds))}
        updated_dict["revision"] = claim_revision(updated_dict)
        save_claim_cas(
            self._workspace_root, resource_id, updated_dict,
            expected_revision=claim.revision,  # CAS guard
        )  # raises ClaimRevisionConflictError on concurrent mutation
        self._safe_emit("claim_heartbeat", {
            "resource_id": resource_id, "owner_agent_id": owner_agent_id,
            "claim_id": claim_id, "heartbeat_at": iso(now),
        })
        return claim_from_dict(updated_dict)
```

**Release (B v4 + W5v2 + B3v5 fail-closed order):**

```python
def release_claim(self, resource_id, claim_id, owner_agent_id) -> None:
    _validate_resource_id(resource_id)
    with file_lock(...):
        claim = self._load_claim_if_exists(resource_id)
        if claim is None:
            raise ClaimAlreadyReleasedError(resource_id, claim_id)
        if claim.claim_id != claim_id or claim.owner_agent_id != owner_agent_id:
            raise ClaimOwnershipError(...)
        # B3v5 fail-closed ordering: fencing load + validate FIRST
        state = load_fencing_state(self._workspace_root)  # may raise ClaimCorruptedError BEFORE delete
        current_rev = fencing_state_revision(state.to_dict())
        new_state = update_on_release(state, resource_id, owner_agent_id)
        # Fencing pre-validated; now safe to delete claim
        claim_path(resource_id).unlink()                              # a. claim delete
        save_fencing_state_cas(self._workspace_root, new_state, current_rev)  # b. fencing audit
        self._update_index_locked(claim, action="remove")              # c. index last
        self._safe_emit("claim_released", {
            "resource_id": resource_id, "owner_agent_id": owner_agent_id,
            "claim_id": claim_id, "released_at": iso(now_utc()),
        })
```

**`_index.v1.json` inline schema:**

```json
{"schema_version": "1",
 "agents": {"<owner_agent_id>": ["<resource_id>", ...]},
 "generated_at": "ISO-8601",
 "revision": "sha256:..."}
```

**Drift detection (W2v2):**
- Acquire quota + mutation + `list_agent_claims`: `_ensure_index_consistent()` hash check; mismatch → `_rebuild_index_locked()` **fail-open** (derived only)
- SSOT (claim / fencing) parse/schema/hash → `ClaimCorruptedError` **fail-closed** propagates

**`_count_agent_claims(owner_agent_id)` semantic (W3v5 live-count):**

```python
def _count_agent_claims(self, owner_agent_id: str) -> int:
    """Count ONLY non-expired claims (B0 invariant; W3v5 explicit).
    Expired-but-unpruned claims in _index are filtered out."""
    now = now_utc()
    policy = load_coordination_policy(self._workspace_root)
    count = 0
    index = self._load_index()
    for resource_id in index.agents.get(owner_agent_id, []):
        claim = self._load_claim_if_exists(resource_id)
        if claim is None: continue  # index stale
        grace_end = parse(claim.heartbeat_at) + timedelta(
            seconds=policy.expiry_seconds + policy.takeover_grace_period_seconds
        )
        if now <= grace_end: count += 1
    return count
```

**Cross-file recovery (B2v2 + B3v3 forward-only):**

```python
def _reconcile_fencing_with_claims_locked(self) -> None:
    """Forward-only: fencing state NEVER decreases."""
    state = load_fencing_state(self._workspace_root)
    for resource_id in self._scan_all_claims_resource_ids():
        claims = self._load_all_claims_for_resource(resource_id)
        if not claims: continue
        max_claim_token = max(c.fencing_token for c in claims)
        current = state.resources.get(resource_id, {}).get("next_token", 0)
        new_next = max(current, max_claim_token + 1)
        if new_next > current:
            state = _set_next_token(state, resource_id, new_next)
    save_fencing_state_cas(self._workspace_root, state, ...)
```

**Prune (Q7v2 + B3v5 fail-closed order):**

```python
def prune_expired_claims(self, policy=None, *, max_batch=None) -> list[str]:
    policy = policy or load_coordination_policy(self._workspace_root)
    pruned = []
    with file_lock(...):
        for resource_id in self._scan_all_claims_resource_ids():
            if max_batch is not None and len(pruned) >= max_batch: break
            claim = self._load_claim_if_exists(resource_id)
            if claim is None: continue
            now = now_utc()
            grace_end = parse(claim.heartbeat_at) + timedelta(
                seconds=policy.expiry_seconds + policy.takeover_grace_period_seconds
            )
            if now > grace_end:
                # B3v5 fail-closed order: fencing load FIRST
                state = load_fencing_state(self._workspace_root)
                current_rev = fencing_state_revision(state.to_dict())
                new_state = update_on_release(state, resource_id, claim.owner_agent_id)
                # Fencing pre-validated; now safe to delete claim
                claim_path(resource_id).unlink()
                save_fencing_state_cas(self._workspace_root, new_state, current_rev)
                self._update_index_locked(claim, action="remove")
                self._safe_emit("claim_expired", {
                    "resource_id": resource_id,
                    "last_owner_agent_id": claim.owner_agent_id,
                    "last_heartbeat_at": claim.heartbeat_at,
                    "expired_at": iso(now),
                })
                pruned.append(resource_id)
    return pruned
```

### 2.4 `ao_kernel/coordination/policy.py`

- `load_coordination_policy(workspace_root, override=None) -> CoordinationPolicy`
- Schema validation at load
- **`max_claims_per_agent=0` ⇒ unlimited (B1v3).**
- `match_resource_pattern(policy, resource_id) -> bool`

### 2.5 `ao_kernel/coordination/errors.py`

| Class | Fields |
|---|---|
| `CoordinationError` (base) | — |
| `ClaimConflictError` | `resource_id`, `current_owner_agent_id`, `current_fencing_token: int` (B6v2) |
| `ClaimConflictGraceError` | same |
| `ClaimStaleFencingError` | `resource_id`, `supplied_token`, `live_token` (B2v3 exact-equality) |
| `ClaimOwnershipError` | `claim_id`, `requesting_agent_id`, `current_owner_agent_id` |
| `ClaimRevisionConflictError` | `resource_id`, `expected_revision`, `actual_revision` (B2v5 CAS conflict) |
| `ClaimQuotaExceededError` | `owner_agent_id`, `current_count`, `limit` (B1v3 0=unlimited) |
| `ClaimResourcePatternError` | `resource_id`, `patterns` |
| `ClaimResourceIdInvalidError` | `resource_id`, `rejection_reason` (B4v2) |
| `ClaimCoordinationDisabledError` | — |
| `ClaimCorruptedError` | `path`, `cause` (SSOT only, W2v2) |
| `ClaimAlreadyReleasedError` | `resource_id`, `claim_id` (W5v2) |
| **`ClaimNotFoundError`** | `resource_id` (B1v5 — public takeover_claim on absent resource) |

### 2.6 `Executor.run_step` fencing entry (W1v5 — no internal emit)

**Mevcut imza (executor.py:98-107, v4 repo-verified):**
```python
def run_step(
    self,
    run_id: str,
    step_def: StepDefinition,
    *,
    parent_env: Mapping[str, str] | None = None,
    attempt: int = 1,
    driver_managed: bool = False,
    step_id: str | None = None,
) -> ExecutionResult:
```

**B1 delta (fencing kwargs sonuna kw-only, **stale check evidence emit ETMEZ**):**

```python
def run_step(
    self,
    run_id: str,
    step_def: StepDefinition,
    *,
    parent_env: Mapping[str, str] | None = None,
    attempt: int = 1,
    driver_managed: bool = False,
    step_id: str | None = None,
    fencing_token: int | None = None,              # NEW (B1)
    fencing_resource_id: str | None = None,        # NEW (B1)
) -> ExecutionResult:
    if (fencing_token is None) != (fencing_resource_id is None):
        raise ValueError(
            "fencing_token and fencing_resource_id must be passed together or both omitted"
        )

    # W1v5: stale fencing check ÖNCE step_started emit, evidence emit HİÇ YOK
    # step_started ve step_failed emit'leri _run_adapter_step() içinde (mevcut pattern).
    # Stale → ClaimStaleFencingError raise → MultiStepDriver catch edip step_record failed + step_failed emit eder.
    if fencing_token is not None:
        if self._claim_registry is None:
            raise ValueError("fencing kwargs supplied but Executor has no claim_registry")
        self._claim_registry.validate_fencing_token(fencing_resource_id, fencing_token)
        # raises ClaimStaleFencingError on mismatch — propagates to driver
        # driver handles: step_record.state="failed" + step_failed evidence emit
        # (mevcut PR-A4b retry-attempt append pattern'le uyumlu; executor kendisi emit etmez)

    # Mevcut flow devam: _run_adapter_step() step_started + ... emit eder.
```

**W1v5 çözümü:**
- Stale fencing check `run_step()` entry'de **evidence emit ÖNCESİ** çalışır
- Raise ise `ClaimStaleFencingError` propagates — mevcut `_run_adapter_step()` dokunulmaz
- `MultiStepDriver` catch eder; step_record.state="failed" + step_failed evidence emit (mevcut PR-A4b pattern, `error_category="other"`, `error_detail="stale fencing: ..."`)
- Canonical order korunur (step_started henüz emit edilmemiş; fail path driver'da)
- Backward compat: fencing kwargs yoksa davranış aynı

**`_claim_registry` injection:** `Executor.__init__(claim_registry: ClaimRegistry | None = None)`. `None` default; fencing kwargs supplied + None registry → `ValueError`.

### 2.7 Evidence taxonomy 18 → 24

`_KINDS` frozenset +6: `claim_acquired`, `claim_released`, `claim_heartbeat`, `claim_expired`, `claim_takeover`, `claim_conflict`. Payload shapes §2.3'te kod örneklerinde.

**`_safe_emit_coordination_event` (W4v4):**

```python
def _safe_emit_coordination_event(
    sink: Callable[[str, Mapping[str, Any]], Any] | None,
    kind: str,
    payload: Mapping[str, Any],
) -> None:
    if sink is None:
        return  # No-op if sink not injected
    try:
        sink(kind, payload)
    except Exception as e:
        logger.warning(
            "coordination evidence emit failed: kind=%s, cause=%r",
            kind, e, extra={"coordination_kind": kind, "error": repr(e)},
        )
```

**Caller sink injection (W4v4 explicit wrapper + W2v5 redaction binding):**

```python
def build_coordination_sink(
    workspace_root: Path,
    policy: CoordinationPolicy,
    run_id: str,
    actor: str = "ao-kernel",
) -> Callable[[str, Mapping[str, Any]], None]:
    """Recommended helper: binds policy.evidence_redaction config to emit_event.
    Callers wrap this sink into ClaimRegistry(evidence_sink=sink)."""
    redaction = policy.evidence_redaction  # W2v5 bind policy config
    def _sink(kind: str, payload: Mapping[str, Any]) -> None:
        emit_event(
            workspace_root, run_id=run_id, actor=actor,
            kind=kind, payload=payload,
            redaction=redaction,  # W2v5 live binding
        )
    return _sink

# Usage:
sink = build_coordination_sink(ws, policy, run_id="coord-workspace-1")
registry = ClaimRegistry(workspace_root=ws, evidence_sink=sink)
```

Typing `Callable[[str, Mapping[str, Any]], Any]`.

**W4v5 note (core executor evidence):** `Executor.run_step()` stale-fencing check **hiç emit etmez** (W1v5 çözümü); `_run_adapter_step` + `MultiStepDriver` mevcut PR-A3/PR-A4b convention'ıyla emit eder. Core executor evidence'in fail-open dönüşümü B1 scope dışı — FAZ-C scope (multi-step driver + executor arası refactor). Mevcut executor emit convention PR-A3'te yerleşik (ordinary `emit_event`); B1 `_safe_emit_coordination_event` wrapper sadece `claim_*` event'leri için fail-open güvencesi sağlar.

### 2.8 Integration points

- `Executor(claim_registry=None)` + `run_step(fencing_token=, fencing_resource_id=)` — B1 delta (W1v5 no internal emit)
- `MultiStepDriver`: default no coordination; stale fencing catch + step_failed emit (mevcut error handler path)
- `docs/COORDINATION.md` §7 event table W1v3 commit 5'te: `claim_acquired` NEW only; `claim_takeover` distinct

## 3. Write Order (5-commit DAG)

| Step | İçerik | Risk |
|---|---|---|
| 1 | errors.py (13 types) + __init__.py | Düşük |
| 2 | claim.py (+ save_claim_cas) + fencing.py (exact-equality + forward-only) + unit tests | Orta |
| 3 | policy.py (dormant + 0=unlimited) + unit | Düşük |
| 4 | registry.py CORE (acquire/heartbeat/release/validate + evidence_sink + live-count quota) + integration | **Yüksek** |
| 5 | takeover (live/grace gate + past-grace write) + prune (fail-closed order) + _index + reconcile forward-only + executor fencing (no-emit entry check) + _KINDS +6 + tests | Yüksek |
| 6 | integration tests (driver catches ClaimStaleFencingError → step_failed) + B0 regression | Orta |
| 7 | docs + CHANGELOG | Düşük |

**Commit DAG:**
```
commit 1: errors + claim + save_claim_cas + fencing + unit tests     (Steps 1+2)
commit 2: policy + unit                                                (Step 3)
commit 3: registry CORE + evidence_sink + integration (HIGH RISK)     (Step 4)
commit 4: takeover live/grace gate + prune fail-closed + executor fencing + tests  (Steps 5+6)
commit 5: docs + CHANGELOG                                             (Step 7)
```

## 4. Scope Dışı (PR-B2..B8+)

| Alan | PR |
|---|---|
| Cost runtime | B2 |
| Cost-aware routing | B3 |
| Policy simulation | B4 |
| Metrics export + `ao_claim_active_total`, `ao_claim_takeover_total`, `evidence_emit_failure_total` (Q11) | B5 |
| Review AI workflow runtime | B6 |
| Benchmark suite | B7 |
| v3.2.0 release | B8 |
| `MultiStepDriver` auto-coordination | FAZ-C+ |
| OS-level network sandbox | v3.2.x stretch |
| `ClaimRegistry.reconcile()` / `health_check()` admin API (Q12) | FAZ-C+ |
| `claim_id → resource_id` reverse index | v1'de gerek yok (B v4 lookup contract) |
| Core executor evidence fail-open wrapper (W4v5) | FAZ-C+ (executor + driver refactor) |

## 5. Acceptance

- [ ] `ao_kernel/coordination/` package loads; `__all__` exposes public API
- [ ] `Claim` + `FencingState` schema round-trip; `fencing_state_revision()` deterministic
- [ ] **`save_claim_cas(expected_revision)` helper (B2v5):** CAS conflict → `ClaimRevisionConflictError(resource_id, expected, actual)`
- [ ] `CoordinationPolicy` bundled dormant default passes schema
- [ ] **resource_id path-traversal (B4v2):** `../`, `./`, `a/b`, `*`, whitespace → `ClaimResourceIdInvalidError` BEFORE pattern
- [ ] **Validator applied to BOTH acquire AND takeover (B5v3)**
- [ ] **Acquire happy path:** fencing → claim → index; `fencing_token=0` new resource; `claim_acquired` emitted
- [ ] **Exact-equality fencing (B2v3):** `token < live` raises; `token > live` raises; only `==` passes
- [ ] **Conflict live:** `ClaimConflictError(current_fencing_token=...)`; evidence payload (B6v2)
- [ ] **Conflict grace:** `ClaimConflictGraceError(current_fencing_token=...)`; distinct `conflict_kind`
- [ ] **Heartbeat (B v4 + B2v5 CAS):** O(1) lookup; mismatch → `ClaimOwnershipError`; concurrent mutation → `ClaimRevisionConflictError`
- [ ] **Heartbeat revival:** grace-window heartbeat → claim lives + CAS updated
- [ ] **Heartbeat past-grace:** expired → `ClaimAlreadyReleasedError` (W5v2)
- [ ] **Takeover past grace (via acquire):** distinct `claim_takeover` event (W1v2); `fencing_token` +1; payload `prev_` + `new_` tokens
- [ ] **Single-emit delegate (W3v4):** past-grace acquire → delegate + immediate return; only ONE `claim_takeover` emitted
- [ ] **No `claim_acquired` on takeover path** (W1v2 negative assertion)
- [ ] **`takeover_claim()` live gate (B1v5):** public takeover on live claim → `ClaimConflictError` (NOT bypass, NOT force-takeover)
- [ ] **`takeover_claim()` grace gate (B1v5):** public takeover on in-grace claim → `ClaimConflictGraceError`
- [ ] **`takeover_claim()` past-grace success (B1v5):** only past-grace resource → new claim with fencing `+1`
- [ ] **`takeover_claim()` absent resource (B1v5):** → `ClaimNotFoundError`
- [ ] **Takeover quota (B1v3):** agent at limit + past-grace → `ClaimQuotaExceededError`
- [ ] **Quota `limit=0` unlimited:** policy `max_claims_per_agent=0` + any count → acquire succeeds
- [ ] **Quota live-count (W3v5):** expired-but-unpruned claims HARİÇ sayılır; `_count_agent_claims` loads each index entry + applies `effective_expires + grace` filter
- [ ] **Stale fencing executor entry (W1v5):** `run_step()` entry, BEFORE `_run_adapter_step()`, NO evidence emit; `ClaimStaleFencingError` propagates to driver; driver writes `step_record.state="failed"` + emits `step_failed` (mevcut PR-A4b pattern)
- [ ] **Partial fencing kwargs:** only one → `ValueError`
- [ ] **Executor fencing without claim_registry** → `ValueError` at entry
- [ ] **Executor backward compat:** no fencing + no registry → mevcut MultiStepDriver green
- [ ] **Release (B v4 + W5v2 + B3v5 fail-closed order):** `release_claim(resource_id, claim_id, owner_agent_id)` absent → `ClaimAlreadyReleasedError`
- [ ] **Release corrupt fencing (B3v5):** `_fencing.v1.json` corrupt → `ClaimCorruptedError` raises **BEFORE** claim file delete (claim dosyası hâlâ disk'te; caller recover edebilir)
- [ ] **Release preserves fencing:** next acquire advances `next_token`; never reset
- [ ] **Ownership mismatch heartbeat/release:** wrong agent or wrong claim_id → `ClaimOwnershipError`
- [ ] **Quota SSOT:** acquire + takeover both trigger `_ensure_index_consistent()` rebuild-if-drift
- [ ] **Resource pattern deny:** valid format + not matching → `ClaimResourcePatternError`
- [ ] **Dormant:** `policy.enabled=false` + any public API → `ClaimCoordinationDisabledError`
- [ ] **Prune (B3v5 fail-closed):** past-grace cleaned in B3v5 order; corrupt fencing → raise pre-delete
- [ ] **Prune max_batch:** respected; pagination correct
- [ ] **Index fail-open (W2v2):** corrupted `_index.v1.json` → silent recovery
- [ ] **SSOT fail-closed (W2v2):** corrupted claim/fencing → `ClaimCorruptedError` propagates
- [ ] **CAS conflict claim (B2v5):** concurrent heartbeat → `ClaimRevisionConflictError(expected, actual)`
- [ ] **CAS conflict fencing (W3v2):** `fencing_state_revision` mismatch → `ClaimRevisionConflictError`
- [ ] **Forward-only recovery (B3v3):** simulated crash → `new_next_token = max(current, max_claim+1)`; never decreases
- [ ] **Re-entrant lock (B5v2):** past-grace via acquire → no deadlock
- [ ] **Safe evidence emit (B3v2):** mock sink raise → registry mutation succeeds + logs warning
- [ ] **evidence_sink=None default (B4v3):** all mutations work; no-op emit
- [ ] **Redaction binding (W2v5):** `build_coordination_sink(policy=...)` helper binds `policy.evidence_redaction`; emitted events redacted per config
- [ ] **Evidence 18 → 24:** `_KINDS` +6; drift guard passes
- [ ] **B0 regression:** `TestBundledCodexStubEndToEnd` green
- [ ] pytest: baseline + ~92 new tests; ruff + mypy strict clean
- [ ] POSIX-only: Windows → `LockPlatformNotSupported`

## 6. Resolved Questions

**iter-1 (original expired):** Q1-Q8 resolved in v2.
**iter-1v2:** Q9 forward-only (B3v3); Q10 eager retained; Q11 `logger.warning + structured`; Q12 health_check skip; Q13 slash deny; Q14 takeover-fail omitted.
**iter-2v2:** Q15 simple `(kind, payload)` + `-> Any` return type.
**iter-1v3:** — absorbed as B1v5/B2v5/B3v5/W1v5/W2v5/W3v5/W4v5 in this plan.

**iter-2 için:** teyit sorusu yok. Plan v5 AGREE bekleniyor.

## 7. Audit Trail

| Field | Value |
|---|---|
| Plan version | **v5** (post CNS-029v3 iter-1 PARTIAL: 3B + 4W absorbed) |
| Predecessor chain | v1 → v2 (iter-1: 6B+5W) → v3 (iter-1v2: 5B+4W) → v4 (iter-2v2: 1B+4W) → **v5 (iter-1v3: 3B+4W)** |
| Head SHA | `fbf7229` |
| Base branch | `main` |
| Target branch | `claude/tranche-b-pr-b1` |
| FAZ-B master ref | `.claude/plans/FAZ-B-MASTER-PLAN.md` (CNS-027 iter-2 AGREE) |
| **Active CNS thread** | `019d99eb-6208-78c3-b5be-070b401f56d6` (CNS-20260416-029v3) |
| Previous CNS threads (expired) | `019d97b8-95df-7680-808e-07f2e523eed7` (original), `019d984b-c332-7892-be04-5a4cfa463ebb` (v2) |
| iter-1v3 verdict | PARTIAL — 3B (takeover live/grace bypass / claim CAS helper eksik / release+prune fail-closed order ihlali) + 4W (executor anchor / redaction binding / quota live-count / core executor fail-open scope) absorbed in v5 |
| iter-2v3 expectation | AGREE + `ready_for_impl: true` |
| Infra reuse | `canonical_store._mutate_with_cas`/`store_revision` (claim helper pattern); runtime-only `fencing_state_revision()`; `file_lock`; `write_text_atomic`; `emit_event` (caller-wrapped via `build_coordination_sink`) |
| B0 regression guards | `TestBundledCodexStubEndToEnd` green; 18-kind → 24-kind additive-only; `InvocationResult.extracted_outputs` public surface intact; Executor backward compat; MultiStepDriver catch-path for ClaimStaleFencingError |

**Status:** Plan v5 complete. Submit iter-2 via `mcp__codex__codex-reply` on active thread.
