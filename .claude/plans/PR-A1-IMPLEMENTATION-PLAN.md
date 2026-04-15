# PR-A1 Implementation Plan — Workflow State Machine + Run Store

**Status:** DRAFT **v2** · 2026-04-15
**Base branch:** `claude/tranche-a-pr-a1` (to create from `origin/main` after PR #87 merges)
**Plan authority:** Plan v2.1.1 §15 (Post-PR-A0 #2); PR-A0 `workflow-run.schema.v1.json` transition table
**Scope position:** Tranche A PR 1/6 — first code PR in FAZ-A governed demo MVP
**Adversarial:** CNS-20260415-020 iter-1 PARTIAL (7 blocking + 11 warning absorbed) → iter-2 pending

## Revision History

| Version | Date | Scope |
|---|---|---|
| v1 | 2026-04-15 12:30 | Initial draft. 7 modules + tests. |
| **v2** | 2026-04-15 14:30 | **CNS-020 iter-1 absorbed**: 7 blocker + 11 warning fixes. run_revision normalized projection, `_mutate_with_cas` signature aligned with canonical_store, run_id UUID path guard, `secrets.token_urlsafe(48)` replaces ULID, Decimal→float serialization policy, budget exhaust equality semantics clarified, `adapter_refs` added to `create_run`. Facade re-export list narrowed (private helpers + path helpers dropped). Test strategy literalized (no narrative parse), atomic test monkey-patched (no subprocess crash). |

---

## 1. Amaç

PR-A0'da spec edilen **workflow run canonical state**'ı Python ile implement et. 9-state state machine + CAS-backed run store + JSON Schema validation at boundaries + budget accounting + HITL interrupt/approval primitives. **Workflow registry** (intent → flow definition mapping) **PR-A2 scope'unda**; **adapter invocation** **PR-A3 scope'unda**. PR-A1 = run lifecycle'ı yöneten çekirdek primitive.

### Neden şimdi?

Tranche A'nın ilk kod PR'ı. Sonraki PR'lar (A2 registry, A3 executor, A4 diff engine, A5 evidence CLI, A6 demo) bu primitive üstüne inşa olur. `canonical_store.py` paketi gibi bir `workflow/` paketi yaratmak ve run persistence + state machine kontratlarını kilitlemek hedef.

### PR-A1'in teslim ettiği

- `ao_kernel/workflow/` public facade paketi — run lifecycle'ı yöneten API
- CAS-backed run store (`.ao/runs/<run_id>/state.v1.json`)
- State machine: 9 state + transition validation (PR-A0 transition table → Python impl)
- Runtime schema validation (Draft 2020-12 `@lru_cache`'li wrapper)
- Budget accounting (fail_closed_on_exhaust semantic netleştirildi, v2)
- HITL interrupt + governance approval primitives (2 token domain, `secrets.token_urlsafe` based, v2)
- Typed errors
- Test coverage: transition matrix + store + integration (stub run lifecycle)

---

## 2. Scope Fences

### Scope İçi

- `ao_kernel/workflow/` yeni public facade paketi (7 modül)
- `tests/test_workflow_*.py` (6 dosya) + `tests/fixtures/workflow_bug_fix_stub.json`
- CHANGELOG.md `[Unreleased]` FAZ-A PR-A1 alt-bloğu

### Scope Dışı

- Workflow registry (intent → workflow_definition) — PR-A2
- Adapter invocation — PR-A3
- Diff/patch engine — PR-A4
- Evidence timeline CLI — PR-A5
- Demo runnable + README — PR-A6
- CLI commands — PR-A2+
- Intent classification — PR-A2

### Bozulmaz İlkeler

- **POSIX-only** — `file_lock` Windows'ta `LockPlatformNotSupported` raise (canonical_store.py:252-257 + lock.py:82-86 mirror, CNS-010 invariant).
- **CAS tek yazma yolu** — `_mutate_with_cas` module-private; tüm public mutators (`save_run_cas`, `update_run`, implicit create_run) bu helper'dan geçer (CNS-010 invariant).
- **project_root() = `.ao/` içeren dizin** (canonical_store convention, CNS-010 invariant).
- **Atomic write** — `write_text_atomic` (tmp + fsync + rename, `_internal/shared/utils.py:47-78`).
- **Fail-closed budget** — `fail_closed_on_exhaust: true` MUST; `record_spend` raises when post-spend `remaining < 0` (strictly exceeds limit); equality (`remaining == 0`) valid but `is_exhausted == True`; next spend raises (v2 clarification).
- **HITL interrupt_token ≠ governance approval_token** — iki token ayrı domain, ayrı mint fonksiyonları (PR-A0 schema §5).
- **Sync SDK** (D9) — async yapma.
- **Schema validation at load/save boundaries** — runtime call path'te değil (perf). `@lru_cache` ile validator + schema once per process (v2 fix).
- **Canonicalization = `json.dumps(sort_keys=True, ensure_ascii=False)`** — canonical_store.store_revision pattern (v2 fix; RFC 8785 JCS'ye gidilmez).
- **Core dep değişmez** — sadece `jsonschema>=4.23.0` (ULID dep eklenmez; `secrets.token_urlsafe` stdlib'den, v2 fix).
- **`_internal` hariç coverage ≥ 85%** — `workflow/` public facade %85+ gerekli (D13 post-Tranche C baseline).

---

## 3. Write Order (bağımlılık DAG)

```
1. errors.py              (exception'lar — diğer modüller raise eder)
       ↓
2. state_machine.py       (pure: enum + TRANSITIONS table + validation)
       ↓
3. schema_validator.py    (Draft 2020-12 wrapper, @lru_cache)
       ↓
4. budget.py              (Decimal cost + immutable; exhaust semantic)
       ↓
5. primitives.py          (secrets.token_urlsafe based; resume idempotent)
       ↓ (hepsi import)
6. run_store.py           (_mutate_with_cas + UUID guard + canonicalization)
       ↓
7. __init__.py            (narrow public re-exports — v2)

Paralel:
8-13. Test dosyaları + fixture
14. CHANGELOG.md [Unreleased] PR-A1 alt-bloğu
15. git commit + gh pr create
```

Module-by-module validation: her modülün unit testi tamamlanınca bir sonrakine geç.

---

## 4. Module — `errors.py`

**Path:** `ao_kernel/workflow/errors.py`
**LOC budget:** ~90 satır (v2: slightly more due to v2.W7 structured validation errors)

### Exceptions

```python
class WorkflowError(Exception):
    """Base for all workflow-related errors."""

class WorkflowTransitionError(WorkflowError):
    """Illegal state transition attempted."""
    # fields: current_state, attempted_state, allowed_next

class WorkflowRunNotFoundError(WorkflowError):
    """Run record does not exist at the expected path."""
    # fields: run_id, store_path

class WorkflowRunCorruptedError(WorkflowError):
    """Run record exists but fails JSON decode or schema validation."""
    # fields: run_id, reason (json_decode|schema_invalid|hash_mismatch), details

class WorkflowCASConflictError(WorkflowError):
    """Expected revision did not match current revision on CAS update."""
    # fields: run_id, expected_revision, actual_revision

class WorkflowBudgetExhaustedError(WorkflowError):
    """A budget axis was overspent (post-spend remaining < 0)."""
    # fields: run_id, axis (tokens|time_seconds|cost_usd), limit, attempted_spend

class WorkflowSchemaValidationError(WorkflowError):
    """Payload does not match workflow-run.schema.v1.json at persist boundary."""
    # fields: run_id, errors (list[dict] of {json_path, message, validator})  ← v2 W7

class WorkflowTokenInvalidError(WorkflowError):
    """interrupt_token or approval_token not recognized or mismatched."""
    # fields: run_id, token_kind (interrupt|approval), token_value, reason

class WorkflowRunIdInvalidError(WorkflowError):  # ← v2 B3 (new)
    """run_id is not a valid UUIDv4 string (path traversal guard)."""
    # fields: run_id
```

### Rationale (v2 updates)

- **`WorkflowSchemaValidationError.errors`** artık structured `list[dict]` (json_path + message + validator); plain message list'ten upgrade (`utils.py:181-186` pattern'ı).
- **`WorkflowRunIdInvalidError`** yeni: `run_id` path component olarak kullanılmadan önce UUIDv4 parse ile doğrulanır; bu exception type raw run_id güvenlik ihlallerini (`../etc/passwd` pattern) path içerisine girmeden reddeder (B3 fix).

---

## 5. Module — `state_machine.py`

**Path:** `ao_kernel/workflow/state_machine.py`
**LOC budget:** ~200 satır

### Public API

```python
WorkflowState = Literal["created", "running", "interrupted", "waiting_approval",
                        "applying", "verifying", "completed", "failed", "cancelled"]

TERMINAL_STATES: frozenset[str] = frozenset({"completed", "failed", "cancelled"})

TRANSITIONS: Mapping[str, frozenset[str]] = _build_transition_table()

def is_terminal(state: str) -> bool: ...
def allowed_next(current: str) -> frozenset[str]: ...
def validate_transition(current: str, new: str) -> None:
    """Raises WorkflowTransitionError if new not in allowed_next(current).
    Raises ValueError if current or new is not a known state."""
```

### Transition Table

| Current | Allowed next | Count |
|---|---|---|
| `created` | `running`, `cancelled` | 2 |
| `running` | `interrupted`, `waiting_approval`, `applying`, `failed`, `cancelled` | 5 |
| `interrupted` | `running`, `failed`, `cancelled` | 3 |
| `waiting_approval` | `applying`, `failed`, `cancelled` | 3 |
| `applying` | `verifying`, `failed`, `cancelled` | 3 |
| `verifying` | `completed`, `failed`, `cancelled` | 3 |
| `completed` / `failed` / `cancelled` | ∅ (terminal) | 0 |

### Design decision: pure functions (no class)

Pure fns; state machine stateless (immutable `TRANSITIONS`). `context/canonical_store.py` hibriti burada gereksiz (CanonicalDecision bir domain record; state machine sadece transition validation). Executor-specific wrapper PR-A3'te gerekirse eklenir (Codex Q1 add1'i kabul).

### Test strategy (v2 W1 fix)

- **Literal expected table** (hand-maintained in test, NOT parsed from schema narrative). Any drift between schema's `state_enum.description` and the test's expected table is caught by a manual test update during schema diffs. Schema is PR-A0 frozen; drift is exceptional.
- **Parametrized matrix test:** 9 states × 9 candidate next states = 81 pairs. Each pair checks `validate_transition` result matches the literal table (single parametrized test, not 81 distinct `def` tests).
- **Terminal invariant:** `is_terminal(s) == (s in TERMINAL_STATES) == (allowed_next(s) == frozenset())`.
- **Unknown state:** `validate_transition("nonsense", "running")` raises `ValueError`; `validate_transition("created", "nonsense")` raises `WorkflowTransitionError`.

---

## 6. Module — `schema_validator.py`

**Path:** `ao_kernel/workflow/schema_validator.py`
**LOC budget:** ~140 satır (v2: slightly more for caching + structured errors)

### Public API (v2 updates)

```python
import functools
from jsonschema.validators import Draft202012Validator

@functools.lru_cache(maxsize=1)
def load_workflow_run_schema() -> Mapping[str, Any]:
    """Loads bundled workflow-run.schema.v1.json via importlib.resources (D4).
    Cached per-process (W5 fix)."""

@functools.lru_cache(maxsize=1)
def _get_validator() -> Draft202012Validator:
    """Cached Draft202012Validator instance (W5 fix)."""

def validate_workflow_run(record: Mapping[str, Any], *, run_id: str | None = None) -> None:
    """Validates record against workflow-run.schema.v1.json.
    Raises WorkflowSchemaValidationError on invalid; errors field is list[dict]
    with keys 'json_path', 'message', 'validator' (W7 fix)."""
```

### Error format (v2 W7 fix)

```python
class WorkflowSchemaValidationError(WorkflowError):
    errors: list[dict[str, str]]  # [{"json_path": "$.state", "message": "...", "validator": "enum"}, ...]
```

Pattern matches `ao_kernel/_internal/shared/utils.py:181-186` structured validation output.

### Validation boundaries

- **On load** (`run_store.load_run`) — after JSON decode, before returning to caller.
- **On save** (`run_store.save_run_cas` / `_mutate_with_cas`) — after mutation, before disk write.
- **NOT in runtime call path** — `state_machine.validate_transition`, `budget.record_spend` don't hit this (perf).

### Bundled schema access

`importlib.resources.files("ao_kernel.defaults.schemas").joinpath("workflow-run.schema.v1.json").read_text()` (D4 wheel-safe).

### Test strategy

- Valid minimal record passes.
- Missing required field raises with `json_path: "$.<field>"`.
- Wrong-type field raises with path + validator name.
- Unknown enum for `state` raises with validator=`enum`.
- Meta-validation: `Draft202012Validator.check_schema(load_workflow_run_schema())` — **test-only** (v2 W6: removed from runtime startup).
- Cache: second call to `load_workflow_run_schema()` returns same object id.

---

## 7. Module — `budget.py`

**Path:** `ao_kernel/workflow/budget.py`
**LOC budget:** ~180 satır (v2: slightly more for serialization policy)

### Public API (v2 B5 + B6 fixes)

```python
from decimal import Decimal
from dataclasses import dataclass

@dataclass(frozen=True)
class BudgetAxis:
    limit: int | float | Decimal
    spent: int | float | Decimal
    remaining: int | float | Decimal

@dataclass(frozen=True)
class Budget:
    tokens: BudgetAxis | None              # int (counts)
    time_seconds: BudgetAxis | None        # float (naturally fuzzy)
    cost_usd: BudgetAxis | None            # Decimal internal; float on persist (B5)
    fail_closed_on_exhaust: bool           # MUST be True

def budget_from_dict(record: Mapping[str, Any]) -> Budget:
    """Parses schema budget section. cost_usd values go via Decimal(str(...)) for precision."""

def budget_to_dict(budget: Budget) -> dict[str, Any]:
    """Serializes to schema-compatible dict. cost_usd Decimal -> float (B5 fix).
    NOTE: schema type:number for cost_usd; sub-cent precision is NOT guaranteed post-persist."""

def record_spend(
    budget: Budget,
    *,
    tokens: int | None = None,
    time_seconds: float | None = None,
    cost_usd: int | float | Decimal | None = None,
) -> Budget:
    """Returns updated Budget. cost_usd internally coerced to Decimal(str(value)) for exact arithmetic.
    Raises WorkflowBudgetExhaustedError if any axis's post-spend remaining < 0 (strictly exceeds limit).
    Spending exactly the remaining amount is VALID; post-spend remaining == 0; is_exhausted == True;
    next positive-valued spend on that axis raises (B6 semantic clarification)."""

def is_exhausted(budget: Budget) -> tuple[bool, str | None]:
    """Returns (True, axis_name) if ANY axis has remaining <= 0.
    is_exhausted is informational (used for event emission); record_spend enforces fail-closed."""
```

### Design decisions (v2)

- **Decimal for `cost_usd`**: internal arithmetic uses `Decimal(str(value))` to avoid FP drift. On persist (`budget_to_dict`), converted to `float` because schema `$defs/budget` declares `cost_usd.*.limit/spent/remaining` as `type: number` (JSON Schema draft-2020-12 numeric; jsonschema rejects Decimal literals unless custom encoder).
- **Serialization contract:** `budget_to_dict` produces schema-valid JSON; sub-cent precision is NOT persisted (docstring warns). FAZ-B may promote to `string` representation if operator precision demand emerges.
- **Exhaust semantic (B6):**
  - `record_spend` computes `new_remaining = remaining - spend`. If `new_remaining < 0` → raise.
  - `is_exhausted` reports `remaining <= 0` (informational).
  - Spending exactly `remaining` is valid; spending `remaining + 1` raises.
- **Immutable dataclass:** every update returns a new `Budget` (CAS-compatible, no in-place mutation).

### Test strategy

- Happy path: spend within limit → updated budget, no raise.
- Exact limit: `record_spend(budget, tokens=budget.tokens.remaining)` succeeds; `budget.is_exhausted(returned) == (True, "tokens")`; next spend raises.
- Over limit: `record_spend(budget, tokens=budget.tokens.remaining + 1)` raises `WorkflowBudgetExhaustedError` with `axis="tokens"`.
- Multi-axis: exhausting one axis while others have room still raises only when exceeded.
- Roundtrip: `budget_to_dict(budget_from_dict(d)) == d` modulo cost_usd precision note.
- Schema compat: `budget_to_dict(b)` validates against workflow-run schema `$defs/budget` via `validate_workflow_run` on a wrapper record.

---

## 8. Module — `primitives.py`

**Path:** `ao_kernel/workflow/primitives.py`
**LOC budget:** ~200 satır (v2: slightly more for idempotent resume)

### Public API (v2 B4 + W8 fixes)

```python
import secrets
import hashlib

def mint_interrupt_token() -> str:
    """64-char URL-safe opaque token. secrets.token_urlsafe(48) produces ~64 char base64url.
    Domain-specific alias (separate function, same impl) enforces type-safety at call sites (B4 fix)."""
    return secrets.token_urlsafe(48)

def mint_approval_token() -> str:
    """Same implementation as mint_interrupt_token; separate function keeps HITL and governance
    audit domains distinct (B4 fix)."""
    return secrets.token_urlsafe(48)

@dataclass(frozen=True)
class InterruptRequest:
    interrupt_id: str
    interrupt_token: str
    emitted_at: str               # ISO-8601
    adapter_id: str
    question_payload: Mapping[str, Any]
    resumed_at: str | None
    response_payload: Mapping[str, Any] | None

@dataclass(frozen=True)
class Approval:
    approval_id: str
    approval_token: str
    gate: Literal["pre_diff", "pre_apply", "pre_pr", "pre_merge", "post_ci", "custom"]
    requested_at: str
    actor: str
    decision: Literal["granted", "denied", "timeout"] | None
    responded_at: str | None
    payload: Mapping[str, Any]

def create_interrupt(adapter_id: str, question_payload: Mapping[str, Any]) -> InterruptRequest: ...
def create_approval(gate: str, actor: str, payload: Mapping[str, Any]) -> Approval: ...

def resume_interrupt(
    request: InterruptRequest,
    *,
    token: str,
    response_payload: Mapping[str, Any],
) -> InterruptRequest:
    """Validates token matches request.interrupt_token.
    Idempotent (W8 fix): if already resumed and response_payload hash matches prior, returns same request.
    Raises WorkflowTokenInvalidError on token mismatch OR on resume with different payload hash."""

def resume_approval(
    approval: Approval,
    *,
    token: str,
    decision: Literal["granted", "denied", "timeout"],
) -> Approval:
    """Idempotent (W8 fix): same token + same decision returns same approval; mismatch raises."""
```

### Token implementation (v2 B4)

`secrets.token_urlsafe(48)` produces a 64-character URL-safe base64 string from 48 bytes of OS entropy. This is stdlib, meets schema `minLength: 1` (well over), and sufficient for opaque resume tokens. No ULID dependency (would violate core dep invariant; plan v2.1.1 §4 core dep unchanged).

### Resume idempotency (v2 W8)

Network retries from orchestrator or UI may issue the same resume twice. Rather than raising on second call, we compute `sha256(sort_keys JSON-serialized response_payload).hex()` (or `decision` for Approval). If the second call matches the first, return the same request/approval (idempotent success). If the payload differs, raise `WorkflowTokenInvalidError(reason="resumed_with_different_payload")`.

### Test strategy

- Token mint uniqueness: 1000 mints, all distinct.
- Token length ≥ 64 chars (secrets.token_urlsafe(48) → ~64 base64url chars).
- Interrupt resume happy path: first resume returns updated request with resumed_at + response_payload.
- Interrupt resume idempotent (W8): second resume with SAME payload returns request object (no raise).
- Interrupt resume payload mismatch: second resume with DIFFERENT payload raises `WorkflowTokenInvalidError`.
- Approval resume: same token + same decision idempotent; same token + different decision raises.
- Cross-domain: pass approval_token to resume_interrupt → raises (token_kind="interrupt" in exception).

---

## 9. Module — `run_store.py`

**Path:** `ao_kernel/workflow/run_store.py`
**LOC budget:** ~420 satır (v2: more for helper signature alignment + UUID guard + normalization)

### Canonicalization policy (v2 W3)

`json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":"))` — matches `canonical_store.store_revision` (line 86-94) and `agent_coordination.get_revision` (line 45-55). NOT RFC 8785 JCS.

### Revision computation (v2 B1)

```python
def run_revision(record: Mapping[str, Any]) -> str:
    """SHA-256 hex of canonicalized JSON, with 'revision' field OMITTED before hashing.
    Self-reference avoided: hash over the 'unrevisioned' projection of the record
    (copy without 'revision' key). Mirrors canonical_store pattern for content-addressing."""
    projection = {k: v for k, v in record.items() if k != "revision"}
    return hashlib.sha256(
        json.dumps(projection, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
```

### Path helpers (v2 B3 path guard) — **module-private**

```python
import uuid as _uuid

def _run_path(workspace_root: Path, run_id: str) -> Path:
    """Validates run_id as UUIDv4 before joining to path (prevents path traversal).
    Raises WorkflowRunIdInvalidError on non-UUID input."""
    try:
        _uuid.UUID(run_id)
    except (ValueError, AttributeError, TypeError) as e:
        raise WorkflowRunIdInvalidError(run_id=run_id) from e
    return workspace_root / ".ao" / "runs" / run_id / "state.v1.json"

def _lock_path(workspace_root: Path, run_id: str) -> Path:
    """Companion lock file. run_id validated via _run_path."""
    return _run_path(workspace_root, run_id).with_suffix(".v1.json.lock")
```

> `_run_path` + `_lock_path` module-private (W2 fix); not re-exported via `__init__.py`.

### Private helper (v2 B2 signature aligned with canonical_store pattern)

```python
def _mutate_with_cas(
    workspace_root: Path,
    run_id: str,
    *,
    mutator: Callable[[dict[str, Any]], dict[str, Any]],
    expected_revision: str | None = None,
    allow_overwrite: bool = False,
) -> tuple[dict[str, Any], str]:
    """SINGLE canonical write path for run records (CNS-010 invariant).

    Behavior:
    - Hold file_lock for the whole load-mutate-write cycle (W4: lock is the wait primitive).
    - If allow_overwrite=False and the file exists, load it first; verify its revision
      matches expected_revision (if provided) → else WorkflowCASConflictError.
    - If allow_overwrite=True, treat absent file as empty initial record (used by create_run).
    - Run mutator on the current record.
    - validate_workflow_run(new_record) before disk write.
    - Compute new_revision = run_revision(new_record); set new_record["revision"] = new_revision.
    - Re-run validate_workflow_run (revision now present and required per schema).
    - Atomic write (write_text_atomic: tmp + fsync + rename).
    - Return (new_record, new_revision).

    Windows: file_lock raises LockPlatformNotSupported upstream (CNS-010 invariant mirror).
    """
```

### Public API (v2 B2 + B7)

```python
def create_run(
    workspace_root: Path,
    *,
    run_id: str,
    workflow_id: str,
    workflow_version: str,
    intent: Mapping[str, Any],
    budget: Mapping[str, Any],
    policy_refs: Sequence[str],
    evidence_refs: Sequence[str],
    adapter_refs: Sequence[str] = (),       # ← v2 B7 added
) -> tuple[dict[str, Any], str]:
    """Atomic create of a new run record.
    Raises FileExistsError if run_id already has a record on disk.
    Validates adapter_refs/policy_refs/evidence_refs per schema (minItems:1 for evidence/policy).
    Returns (record, revision)."""

def load_run(workspace_root: Path, run_id: str) -> tuple[dict[str, Any], str]:
    """Reads, validates, returns (record, revision).
    Raises WorkflowRunNotFoundError or WorkflowRunCorruptedError."""

def save_run_cas(
    workspace_root: Path,
    run_id: str,
    *,
    record: Mapping[str, Any],
    expected_revision: str,
) -> tuple[dict[str, Any], str]:
    """CAS write. Validates, writes atomically under lock, checks expected_revision.
    Returns (persisted_record, new_revision).
    Raises WorkflowCASConflictError, WorkflowSchemaValidationError."""

def update_run(
    workspace_root: Path,
    run_id: str,
    *,
    mutator: Callable[[dict[str, Any]], dict[str, Any]],
    max_retries: int = 1,                  # ← v2 W4: file_lock is the wait primitive
) -> tuple[dict[str, Any], str]:
    """Public CAS update helper.
    Loads record, applies mutator, retries on CASConflict up to max_retries (default 1).
    All writes route through _mutate_with_cas (single canonical write path, CNS-010 invariant).
    Returns (persisted_record, new_revision)."""
```

### File layout

- `.ao/runs/{run_id}/state.v1.json` — canonical JSON record.
- `.ao/runs/{run_id}/state.v1.json.lock` — POSIX file_lock.

### Integration with state_machine + budget + primitives

- `update_run` mutator that calls `state_machine.validate_transition` → transition errors raise before write.
- Mutator may call `budget.record_spend` → exhaust raises `WorkflowBudgetExhaustedError` mid-mutation; lock released; disk unchanged.
- Mutator may append `interrupt_request` or `approval` records → both validated on final write.

### Test strategy

- Create happy path: `create_run → load_run` roundtrip.
- Double create: second `create_run(run_id="same")` raises `FileExistsError`.
- **Invalid run_id (B3):** `create_run(run_id="../etc/passwd")` raises `WorkflowRunIdInvalidError` BEFORE touching disk.
- **Invalid run_id on load:** `load_run("../escape")` raises `WorkflowRunIdInvalidError`.
- CAS conflict: two concurrent `save_run_cas(expected_revision=old)` — first wins, second raises `WorkflowCASConflictError` with `expected_revision` + `actual_revision`.
- Schema rejection: mutator returns invalid record → raises `WorkflowSchemaValidationError` with structured `errors` list.
- Lock held under mutation: reads during long mutator see pre-mutation state (not partial).
- **Atomic write test (v2 W10):** `monkeypatch os.replace` to raise `OSError` mid-rename; verify file is either pre-mutation or absent (never partial). NO subprocess crash.
- Budget exhaust mid-mutation: mutator exhausts budget → raises, disk unchanged.
- `run_revision` determinism: same record → same hash; different `revision` field value but same other fields → SAME hash (v2 B1 invariant).

---

## 10. Module — `__init__.py` (narrow public surface — v2 W2)

**Path:** `ao_kernel/workflow/__init__.py`
**LOC budget:** ~50 satır

### Public API re-exports

```python
from ao_kernel.workflow.errors import (
    WorkflowError,
    WorkflowTransitionError,
    WorkflowRunNotFoundError,
    WorkflowRunCorruptedError,
    WorkflowCASConflictError,
    WorkflowBudgetExhaustedError,
    WorkflowSchemaValidationError,
    WorkflowTokenInvalidError,
    WorkflowRunIdInvalidError,
)
from ao_kernel.workflow.state_machine import (
    WorkflowState,
    TERMINAL_STATES,
    TRANSITIONS,
    is_terminal,
    allowed_next,
    validate_transition,
)
from ao_kernel.workflow.schema_validator import (
    validate_workflow_run,
    # load_workflow_run_schema: module-private helper, not re-exported (W2)
    # _get_validator: module-private (W2)
)
from ao_kernel.workflow.budget import (
    Budget,
    BudgetAxis,
    budget_from_dict,
    budget_to_dict,
    record_spend,
    is_exhausted,
)
from ao_kernel.workflow.primitives import (
    InterruptRequest,
    Approval,
    mint_interrupt_token,
    mint_approval_token,
    create_interrupt,
    resume_interrupt,
    create_approval,
    resume_approval,
)
from ao_kernel.workflow.run_store import (
    create_run,
    load_run,
    save_run_cas,
    update_run,
    run_revision,
    # _mutate_with_cas: module-private (W2)
    # _run_path, _lock_path: module-private (W2)
)

__all__ = [...]  # 35 names
```

### Narrow surface rationale (v2 W2)

Re-exports exclude:
- `_mutate_with_cas` — single canonical write path; only consumed inside `run_store.py`.
- `_run_path`, `_lock_path` — path computation helpers; callers use `create_run`/`load_run` directly.
- `load_workflow_run_schema`, `_get_validator` — validation internals; callers use `validate_workflow_run`.

Mirrors `ao_kernel/policy.py:15-46` and `ao_kernel/session.py:15-69` compact facade style.

---

## 11. Test Strategy

### Coverage targets

- **Public facade (`ao_kernel/workflow/`):** ≥ 85% branch coverage.
- **Per-module:**
  - `state_machine.py`: ~100% (finite)
  - `schema_validator.py`: ~95%
  - `budget.py`: ~95%
  - `primitives.py`: ~90%
  - `run_store.py`: ~85% (I/O branches harder)

### Test files

| File | Tests (approx) | Scope |
|---|---|---|
| `test_workflow_state_machine.py` | 15-20 | literal transition matrix (v2 W1) + terminal + unknown states |
| `test_workflow_schema_validator.py` | 10-15 | valid/invalid + structured error format (W7) + cache (W5) + meta-validation (W6 test-only) |
| `test_workflow_budget.py` | 12-15 | spend/exhaust equality (B6) + Decimal roundtrip (B5) + multi-axis |
| `test_workflow_primitives.py` | 12-15 | secrets.token_urlsafe uniqueness (B4) + idempotent resume (W8) + cross-domain |
| `test_workflow_run_store.py` | 22-28 | CAS + lock + corruption + schema + atomic monkeypatch (W10) + UUID guard (B3) + revision determinism (B1) + helper signature (B2) + concurrent (gentle, no subprocess) |
| `test_workflow_integration.py` | 5-8 | fixture file stub (W9) + full lifecycle |

**Total:** ~76-101 new tests.

### Integration test fixture (v2 W9 + W11)

**File:** `tests/fixtures/workflow_bug_fix_stub.json` — schema-valid stub workflow-run record.

Key fixture values:
- `adapter_refs: ["codex-stub"]` (non-empty; aligns with `create_run(adapter_refs=...)` default test case)
- `policy_refs: ["ao_kernel/defaults/policies/policy_worktree_profile.v1.json"]` (minItems:1)
- `evidence_refs: [".ao/evidence/workflows/{run_id}/events.jsonl"]` (minItems:1)
- `steps: [...]` — each step has all schema-required fields (`step_id`, `step_name`, `state`, `actor`, `started_at`).

### Test quality gate

- No `assert callable(x)` (BLK-001)
- No `assert True` (BLK-002)
- No `except: pass` (BLK-003)

---

## 12. CHANGELOG Update

Extend PR-A0 `[Unreleased]` block (no new version section yet; both ship together at v3.1.0):

```markdown
### Added — FAZ-A PR-A1 (workflow state machine + run store)

- `ao_kernel/workflow/` package: public facade for workflow run lifecycle. Mirrors `canonical_store.py` CAS pattern.
- State machine (`state_machine.py`): 9-state transition table from PR-A0 `workflow-run.schema.v1.json` as pure functions + immutable `TRANSITIONS` mapping.
- Run store (`run_store.py`): CAS-backed CRUD with POSIX `file_lock`, atomic writes (tmp + fsync + rename), runtime schema validation at load/save boundaries. `run_revision` computed over the record with `revision` field omitted (self-reference-free). `_mutate_with_cas(workspace_root, run_id, *, mutator, expected_revision=None, allow_overwrite=False) -> tuple[dict, str]` is the single canonical write path (CNS-010 invariant); `create_run`, `save_run_cas`, and `update_run` all route through it. `run_id` validated as UUIDv4 before use as path component (path-traversal guard).
- Budget (`budget.py`): immutable dataclasses; `cost_usd` tracked as `Decimal` internally for precision, serialized as `float` per schema `type:number`; `fail_closed_on_exhaust: true` raises `WorkflowBudgetExhaustedError` when post-spend `remaining < 0` (strictly exceeds limit). Spending exactly the remaining amount is valid; the next positive spend raises.
- Primitives (`primitives.py`): `InterruptRequest` + `Approval` dataclasses with separate `mint_interrupt_token` / `mint_approval_token` functions (distinct HITL vs governance audit domains). Tokens are `secrets.token_urlsafe(48)` (64-char URL-safe, stdlib — no new core dep). Resume operations are idempotent for repeat calls with identical payload; payload mismatch raises.
- Typed errors (`errors.py`): `WorkflowError` hierarchy + `WorkflowRunIdInvalidError` for path-traversal guard + structured `WorkflowSchemaValidationError.errors: list[dict]` with `json_path`, `message`, `validator`.
- Adversarial consensus: CNS-20260415-020 iter-X (TBD after iter-2 AGREE).
```

---

## 13. Acceptance Criteria (v2: check_schema runtime removed)

### Module + test

- [ ] 7 module files created + narrow public API exports in `__init__.py` (W2)
- [ ] 6 test files + 1 fixture JSON created; ≥ 76 new tests passing
- [ ] Branch coverage for `ao_kernel/workflow/` ≥ 85%
- [ ] Total test count ≥ 1080 (1004 baseline + 76 new minimum)
- [ ] Fixture `tests/fixtures/workflow_bug_fix_stub.json` validates against `workflow-run.schema.v1.json`

### Regression

- [ ] Ruff clean on new files + existing
- [ ] Mypy strict clean (new public facade strict from day 1)
- [ ] Existing 1004 tests still pass
- [ ] No modifications to `ao_kernel/defaults/schemas/workflow-run.schema.v1.json` (PR-A0 frozen)
- [ ] No new core dependency (pyproject.toml line 26 unchanged: only `jsonschema>=4.23.0`)

### Process

- [ ] Plan Türkçe (this file), code + tests + docstrings İngilizce
- [ ] Conventional commits format
- [ ] PR title < 70 chars, body with CNS-020 reference
- [ ] `.claude/plans/PR-A1-IMPLEMENTATION-PLAN.md` merged with PR

---

## 14. Risk & Mitigation (v2)

| Risk | Olasılık | Mitigation |
|---|---|---|
| State machine transition table drift from schema narrative | Düşük | Literal expected table in test (v2 W1); schema frozen PR-A0; drift requires explicit test update. |
| CAS write path divergence from canonical_store | Düşük | `_mutate_with_cas` signature mirrors canonical_store pattern (v2 B2); shared lock helper. |
| run_revision self-reference bug | Düşük | Hash over projection omitting `revision` field (v2 B1); determinism test. |
| UUID path traversal via run_id | Düşük | `_run_path` validates UUIDv4 before join (v2 B3); dedicated exception. |
| Budget serialization precision loss | Düşük | Docstring + schema contract: `cost_usd` Decimal → float on persist; sub-cent NOT guaranteed. |
| ULID dep drift | Eliminated | `secrets.token_urlsafe(48)` stdlib (v2 B4); pyproject.toml unchanged. |
| Exhaustion semantic ambiguity | Eliminated | `record_spend` raises when post-spend `< 0`; equality valid; next spend raises (v2 B6). |
| Resume race condition | Düşük | Idempotent by `(token, response_hash)` match (v2 W8). |
| Integration test fragility | Düşük | Fixture file schema-valid (v2 W9) with all required step fields. |
| Public API bloat | Düşük | Re-export list narrow (v2 W2); private helpers not exposed. |
| PR-A2 registry scope leak | Düşük | `create_run` takes explicit `workflow_version` string; no registry dep; `adapter_refs` default empty tuple (v2 B7). |

---

## 15. Post-PR-A1 Outlook

PR-A1 unblocks:

- **PR-A2** — intent router + workflow registry + adapter manifest loader. Registry populates `workflow_definition` (steps, policies, expected adapters) consumed by `create_run`. Adapter registry feeds `adapter_refs`.
- **PR-A3** — worktree executor. Consumes `update_run` for `adapter_invoked` / `adapter_returned` transitions; enforces `policy_worktree_profile` at invocation boundary.
- **PR-A4** — diff/patch engine. Consumes `update_run(mutator=apply_diff)` for `applying → verifying`.
- **PR-A5** — evidence timeline CLI. Reads run record + events.jsonl; replay uses `state_machine.validate_transition` to verify recorded transitions; considers SSH support in worktree profile.
- **PR-A6** — demo script runnable + `[coding]` meta-extra + README update. Wires A1-A5 with stub adapters.

---

## 16. Audit Trail

| Field | Value |
|---|---|
| Base SHA (after PR #87 merge) | TBD |
| Branch | `claude/tranche-a-pr-a1` |
| Plan authority | v2.1.1 §15 + PR-A0 `workflow-run.schema.v1.json` |
| CNS (PR-A1 plan) | CNS-20260415-020 iter-1 PARTIAL → iter-2 pending |
| Adversarial stats (iter-1) | 7 blocking + 11 warning absorbed in v2 |
| Sibling plans | `.claude/plans/PR-A0-DRAFT-PLAN.md` (v2), `.claude/plans/PR-C6a-IMPLEMENTATION-PLAN.md` |
| Canonical pattern reference | `ao_kernel/context/canonical_store.py` (`_mutate_with_cas`, `save_store_cas`, `store_revision`) |
| Shared lock | `ao_kernel/_internal/shared/lock.py::file_lock` |
| Shared atomic write | `ao_kernel/_internal/shared/utils.py::write_text_atomic` |

---

**Status:** DRAFT v2, awaiting user approval before CNS-020 iter-2 submission. No code yet, no commit yet.
