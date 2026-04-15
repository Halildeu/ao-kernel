# PR-A3 Implementation Plan — Worktree Executor + Policy Enforcement + Adapter Invocation

**Status:** DRAFT **v2** · 2026-04-15
**Base branch:** `claude/tranche-a-pr-a3` (to create from `origin/main` @ `e68b655`)
**Plan authority:** Plan v2.1.1 §15 (Post-PR-A2 #4); PR-A0/A1/A2 contracts
**Scope position:** Tranche A PR 4/6 — the first PR that actually invokes adapters and enforces `policy_worktree_profile`
**Adversarial:** CNS-20260415-022 iter-1 PARTIAL (8 blocking + 9 warning absorbed) → iter-2 pending

## Revision History

| Version | Date | Scope |
|---|---|---|
| v1 | 2026-04-15 19:45 | Initial draft. 6 executor modules + fixtures stub + 5 tests. |
| **v2** | 2026-04-15 20:15 | **CNS-022 iter-1 absorbed**: 8 blocker + 9 warning fixes. PATH hardening (realpath + policy-derived prefix match), env inherit semantic netleştirildi, evidence canonical order + per-run lock + monoton `seq`, ULID yerine opaque event_id + seq, JSONPath minimal dotted subset, text/plain fallback (content-type + marker + capability triple), cross-ref her step'te re-run, `ao_kernel/fixtures/__init__.py` explicit, `codex_stub` JSON envelope output kanonik, CI subprocess budget 1-2 testle sınırlı. |

---

## 1. Amaç

PR-A0'da sözleşmeleri (schema), PR-A1'de durable lifecycle'ı (run state machine + store), PR-A2'de registry + intent + adapter manifest loader'ı kurulan katmanların üstüne **çalışan executor**'ı getirmek. PR-A3'te ilk kez bir adapter gerçekten spawn edilir (subprocess/HTTP), `policy_worktree_profile` runtime'da enforce edilir, evidence events gerçek zamanlı JSONL'e yazılır ve run state machine programatik olarak ilerler (`running → applying/verifying/...`).

### Kapsam özeti (6 modül yeni + 1 fixtures package + 5 test + CHANGELOG)

1. `ao_kernel/executor/worktree_builder.py` — per-run git worktree (`.ao/runs/{run_id}/worktree/`), POSIX 0o700 perms, cleanup.
2. `ao_kernel/executor/policy_enforcer.py` — runtime validation against `policy_worktree_profile.v1.json`. **v2 hardened:** env inherit semantic net; PATH policy-derived (default inherit edilmez); command resolution resolved realpath + policy-declared prefix match (basename-only bypass elendi, Q2 B1-B2).
3. `ao_kernel/executor/adapter_invoker.py` — `subprocess.run` CLI / `urllib.request` HTTP dispatch. **v2:** JSON-first output parse + minimal JSONPath subset (dotted only) + text/plain fallback content-type + diff marker + `write_diff` capability triple (Q4 B6-B7).
4. `ao_kernel/executor/evidence_emitter.py` — JSONL writer. **v2:** per-run evidence lock + monoton `seq` field + opaque `event_id` (token_urlsafe, ULID iddiası kaldırıldı) + canonical emission order; manifest update PR-A5 scope'unda (docs revize) (Q3 B3-B5).
5. `ao_kernel/executor/executor.py` — orchestrator. **v2:** `run_step` primitive sözleşmesi (single-step, no loop); step_def ↔ run record tutarlılık check; her adapter invocation öncesi cross-ref re-run (no cache) (Q1 add, Q5 B8).
6. `ao_kernel/executor/__init__.py` — narrow public facade.
7. `ao_kernel/executor/errors.py` — typed executor exceptions.
8. `ao_kernel/fixtures/__init__.py` + `ao_kernel/fixtures/codex_stub.py` — deterministic stub; **v2:** JSON `output_envelope` stdout (kanonik; diff JSON içinde), test/demo stability note (Q6 W, Q7 W).

---

## 2. Scope Fences

### Scope İçi (v2)

- New package `ao_kernel/executor/` (6 modules).
- New package `ao_kernel/fixtures/` (2 files: `__init__.py`, `codex_stub.py`).
- Runtime enforcement of `policy_worktree_profile.v1.json`.
- Adapter invocation (CLI + HTTP) for a single step.
- Evidence event emission with per-run lock + monoton seq.
- Budget tracking via PR-A1 `record_spend`.
- Step-level state transitions using PR-A1 `validate_transition`.
- 5 new test files + 2 fixture directories (policy profiles + executor adapter manifests).
- Docs revision: `docs/EVIDENCE-TIMELINE.md` manifest ifadesi revize (PR-A3 append-only, manifest PR-A5 CLI).
- CHANGELOG `[Unreleased]` extension.

### Scope Dışı

- Multi-step workflow driver — PR-A4.
- Diff application (`apply_patch`) — PR-A4.
- CI gate integration (pytest + ruff runner) — PR-A4/A6.
- Evidence timeline CLI + manifest generation — PR-A5.
- Demo runnable + README — PR-A6.
- Network egress OS sandbox (cgroups/firejail/nsjail) — FAZ-B.
- Async/concurrent step execution — D9 sync SDK invariant.
- LLM-based intent classifier — PR-A6 `[llm]` extra.

### Bozulmaz İlkeler (v2 güncel)

- **POSIX-only.**
- **CAS tek yazma yolu** (PR-A1 `_mutate_with_cas` invariant; CNS-010).
- **Fail-closed** — herhangi bir policy violation → adapter spawn EDİLMEZ + run `failed` + `error.category="policy_denied"` + `policy_denied` evidence event.
- **No new core dep** — `subprocess` + `urllib` + `json` + `hashlib` + `secrets` stdlib; core dep sadece `jsonschema>=4.23.0`.
- **Narrow public facade** — `executor/__init__.py` private helper'ları re-export etmez.
- **Secret handling** — secrets NEVER in `argv`, NEVER in stdin, NEVER file; sadece `exposure_modes` içinde izinli kanallar (bundled default: `["env"]`). HTTP adapter için `exposure_modes` içinde `"http_header"` explicit workspace override gerekir (v2 Q4 W).
- **Cross-ref validation per adapter step** — no cache; definition pin + adapter registry state her çağrıda doğrulanır (v2 B8).
- **Default policy: host PATH inherit edilmez** — `inherit_from_parent=false` default; PATH `explicit_additions` veya workspace override ile set edilir (v2 B1-B2).
- **PR-A0/A1/A2 schema + kod frozen** — sadece additive entries (`workflow/errors.py` eklemeleri); PR-A0 docs (EVIDENCE-TIMELINE) revize kabul edilir (bug fix).

---

## 3. Write Order (bağımlılık DAG)

```
1. executor/errors.py                    (typed exceptions + PolicyViolation)
       ↓
2. executor/policy_enforcer.py           (pure validation — no I/O; v2 PATH hardening)
       ↓
3. executor/worktree_builder.py          (filesystem layer)
       ↓
4. executor/evidence_emitter.py          (per-run lock + monoton seq + JSONL)
       ↓
5. executor/adapter_invoker.py           (subprocess + urllib + JSONPath subset)
       ↓
6. executor/executor.py                  (orchestrator; single-step primitive)
       ↓
7. executor/__init__.py                  (narrow facade)
       ↓
8. fixtures/__init__.py + fixtures/codex_stub.py   (deterministic, JSON envelope)
       ↓
9. docs/EVIDENCE-TIMELINE.md revision    (manifest PR-A5 clarification)

Paralel tests:
10. test_executor_policy_enforcer.py     (env/command/cwd/secret/PATH hardening unit tests)
11. test_executor_worktree_builder.py    (per-run worktree creation + cleanup + perms)
12. test_executor_evidence_emitter.py    (17-kind + lock + seq monotonicity + redaction)
13. test_executor_adapter_invoker.py     (CLI subprocess + HTTP urllib mock + JSONPath + text/plain)
14. test_executor_integration.py         (full step lifecycle; 1 unmocked happy + cross-ref + fail paths)

+ tests/fixtures/executor_policy_profiles/
+ tests/fixtures/executor_adapter_manifests/

Son:
15. CHANGELOG.md [Unreleased] — PR-A3 bullet
16. git commit + gh pr create + CI monitor + M2 merge
```

---

## 4. Module — `executor/errors.py`

**Path:** `ao_kernel/executor/errors.py`
**LOC budget:** ~150 satır

Exceptions (v1'den korunur):

```python
class ExecutorError(Exception): ...
class PolicyViolationError(ExecutorError):
    violations: list[PolicyViolation]
class AdapterInvocationFailedError(ExecutorError):
    reason: Literal[
        "command_not_found", "timeout", "non_zero_exit",
        "http_error", "http_timeout", "connection_refused",
        "stdin_write_failed", "subprocess_crash",
    ]
class AdapterOutputParseError(ExecutorError):
    raw_excerpt: str  # redacted
class WorktreeBuilderError(ExecutorError):
    reason: Literal["git_worktree_failed", "permissions", "cleanup_failed"]
class EvidenceEmitError(ExecutorError): ...
```

**PolicyViolation dataclass (v2 expanded kind enum):**

```python
@dataclass(frozen=True)
class PolicyViolation:
    kind: Literal[
        "env_unknown",
        "env_missing_required",
        "command_not_allowlisted",
        "command_path_outside_policy",   # v2 B1: resolved realpath policy prefix altında değil
        "cwd_escape",
        "secret_exposure_denied",
        "secret_missing",
        "http_header_exposure_unauthorized",  # v2 Q4 W: exposure_modes http_header override yok
    ]
    detail: str
    policy_ref: str
    field_path: str
```

---

## 5. Module — `executor/policy_enforcer.py` (v2 hardened)

**Path:** `ao_kernel/executor/policy_enforcer.py`
**LOC budget:** ~360-420 satır (v2: +60 for hardening)

### Public API (v2)

```python
@dataclass(frozen=True)
class SandboxedEnvironment:
    env_vars: Mapping[str, str]
    cwd: Path
    allowed_commands_exact: frozenset[str]
    allowed_command_prefixes: tuple[str, ...]
    policy_derived_path_entries: tuple[Path, ...]   # v2 B1: computed from command_allowlist.prefixes + explicit_additions.PATH
    exposure_modes: frozenset[str]
    evidence_redaction: RedactionConfig
    inherit_from_parent: bool                       # v2 B2: explicit on sandbox


def build_sandbox(
    *,
    policy: Mapping[str, Any],
    worktree_root: Path,
    resolved_secrets: Mapping[str, str],
    parent_env: Mapping[str, str],
) -> tuple[SandboxedEnvironment, list[PolicyViolation]]:
    """v2 semantic (B1+B2):
    - inherit_from_parent=True: allowed_keys subset of parent_env is kept (passthrough).
    - inherit_from_parent=False (default): NO parent passthrough; env_vars populated
      ONLY from explicit_additions and resolved_secrets.
    - PATH resolution: if present in explicit_additions use that; else inherit from parent
      ONLY if inherit=True; else synthesize PATH as ':'-joined command_allowlist.prefixes.
      policy_derived_path_entries carries the authoritative list for command validation."""


def validate_command(
    command: str,
    resolved_args: Sequence[str],
    sandbox: SandboxedEnvironment,
    secret_values: Mapping[str, str],
) -> list[PolicyViolation]:
    """v2 hardened (B1):
    1. Resolve command via shutil.which(command, path=sandbox.env_vars['PATH']).
    2. If resolved is None -> command_not_allowlisted.
    3. Compute realpath(resolved) to expand symlinks.
    4. Check realpath is under at least one sandbox.allowed_command_prefixes entry
       OR matches an exact basename AND realpath is under a policy_derived_path_entry.
    5. Basename-alone match is NOT sufficient — resolved realpath must be policy-anchored.
    6. For each arg: if arg contains a secret value literal -> secret_exposure_denied.
    7. http_header exposure: secret in http_header NOT allowed unless
       policy.secrets.exposure_modes contains 'http_header'.
    """


def validate_cwd(
    requested_cwd: Path,
    sandbox: SandboxedEnvironment,
) -> list[PolicyViolation]:
    """Resolve symlinks + normalize; ensure resolved path starts with sandbox.cwd
    (both resolved). Rejects '..' escapes and absolute paths outside root."""


def resolve_allowed_secrets(
    policy: Mapping[str, Any],
    all_env: Mapping[str, str],
) -> tuple[Mapping[str, str], list[PolicyViolation]]:
    """Pick only the secrets listed in policy.secrets.allowlist_secret_ids from all_env.
    Missing secret -> violation(kind='secret_missing').
    Caller (build_sandbox) folds these into env_vars when exposure_modes includes 'env'."""
```

### Design decisions (v2)

- **PATH comes from policy, not host (B1).** `build_sandbox` computes:
  1. If `explicit_additions.PATH` present → use it as PATH.
  2. Else if `inherit_from_parent=True` → use `parent_env.get("PATH", "")` but filter entries: drop any entry NOT under `command_allowlist.prefixes` OR explicitly ack'd via workspace override (opt-in field `env_allowlist.allow_host_path_passthrough=true`).
  3. Else → synthesize PATH from `":".join(policy.command_allowlist.prefixes)`.
- **Basename-alone is not enough (B1).** Command validation requires realpath to be under a policy-declared path entry. If user override allows `/custom/tools/` prefix, commands under that are fine; but `/tmp/sabotaged/python3` is rejected even though `python3` is in exact list.
- **`inherit_from_parent=False` strict (B2).** Default bundled policy sets false; NO parent env leakage. Workspace override must set true explicitly if passthrough desired.
- **Command validation tests (new in v2 acceptance):** `test_path_poisoning_denied` puts a fake `python3` under `/tmp/evil` first in PATH; validation must reject.
- **http_header exposure (Q4 W).** When adapter is HTTP and `invocation.http.auth_secret_id_ref` set, sandbox check: `"http_header" in policy.secrets.exposure_modes` → else `PolicyViolation(kind="http_header_exposure_unauthorized")`.

---

## 6. Module — `executor/worktree_builder.py` (unchanged from v1 structurally)

**Path:** `ao_kernel/executor/worktree_builder.py`
**LOC budget:** ~220-260 satır

(Same as v1 §6; v2 impl-time hardening: explicit `os.chmod(worktree_path, 0o700)` immediately after creation; cleanup idempotency unchanged.)

---

## 7. Module — `executor/evidence_emitter.py` (v2 ordering + lock + seq)

**Path:** `ao_kernel/executor/evidence_emitter.py`
**LOC budget:** ~320-380 satır (v2: +50 for lock + seq + docs update)

### Public API (v2)

```python
@dataclass(frozen=True)
class EvidenceEvent:
    event_id: str             # opaque 64-char URL-safe (token_urlsafe); NOT monotonic
    seq: int                  # per-run monotonic sequence; REPLAY ORDERING KEY (v2 B3+B5)
    run_id: str
    step_id: str | None
    ts: str
    actor: Literal["adapter", "ao-kernel", "human", "system"]
    kind: str
    payload: Mapping[str, Any]
    payload_hash: str         # SHA-256 of redacted payload
    replay_safe: bool


_KINDS: Final[frozenset[str]] = frozenset({
    "workflow_started", "workflow_completed", "workflow_failed",
    "step_started", "step_completed", "step_failed",
    "adapter_invoked", "adapter_returned",
    "diff_previewed", "diff_applied",
    "approval_requested", "approval_granted", "approval_denied",
    "test_executed", "pr_opened",
    "policy_checked", "policy_denied",
})


def emit_event(
    workspace_root: Path,
    *,
    run_id: str,
    kind: str,
    actor: str,
    payload: Mapping[str, Any],
    step_id: str | None = None,
    redaction: RedactionConfig | None = None,
    replay_safe: bool = True,
) -> EvidenceEvent:
    """v2 (B3):
    Acquire per-run evidence lock (file_lock at
    .ao/evidence/workflows/{run_id}/events.jsonl.lock).
    Under lock:
      1. Read last line of events.jsonl (if any); parse seq; next_seq = last_seq + 1.
      2. Build event with seq=next_seq, event_id=secrets.token_urlsafe(48).
      3. Redact payload (env keys regex + stdout patterns).
      4. Compute payload_hash (SHA256 of canonical JSON of redacted payload).
      5. Append JSONL line; flush; fsync.
    Release lock.
    Raises EvidenceEmitError on write/lock failure.
    NOTE: Manifest (SHA256 integrity) is NOT updated here — PR-A5 CLI generates it
    on demand. docs/EVIDENCE-TIMELINE.md revised to reflect this."""


def emit_adapter_log(
    workspace_root: Path,
    *,
    run_id: str,
    adapter_id: str,
    captured_stdout: str,
    captured_stderr: str,
    redaction: RedactionConfig,
) -> Path:
    """Write redacted stdout/stderr to adapter-{adapter_id}.jsonl.
    Same fsync pattern; NO lock (separate file per adapter per run;
    single-writer during invocation)."""
```

### Canonical emission order (v2 B3 net)

Plan v2 defines the canonical order a step emits:

```
1. step_started                (ao-kernel)
2. policy_checked              (ao-kernel) x N per policy gate
3. policy_denied               (ao-kernel) IF any violation -> step terminates here
4. adapter_invoked             (ao-kernel) BEFORE subprocess spawn / HTTP request sent
5. <adapter log capture>       (adapter)   via emit_adapter_log during / after
6. adapter_returned            (ao-kernel) AFTER subprocess/HTTP returns
7. step_completed | step_failed (ao-kernel)
<state CAS update happens AFTER step lifecycle events written>
```

Replay uses `seq` for ordering, NOT `event_id`. Consumers sort by `(run_id, seq)`.

### Design decisions (v2)

- **event_id opaque, not monotonic (B5).** Plan v1 claimed ULID via `token_urlsafe` — retracted. `event_id` is now documented as opaque + unique; ordering via `seq`.
- **Per-run lock (B3).** `.ao/evidence/workflows/{run_id}/events.jsonl.lock` via `_internal/shared/lock.py::file_lock`. Holds for the entire read-seq + append cycle.
- **No manifest update (B4).** Docs revised: workflow manifest is PR-A5 CLI artefact, NOT per-event artefact. PR-A3 append-only to JSONL.
- **Kind whitelist enforced.**

---

## 8. Module — `executor/adapter_invoker.py` (v2 JSONPath subset + text/plain fallback)

**Path:** `ao_kernel/executor/adapter_invoker.py`
**LOC budget:** ~460-550 satır (v2: +80 for JSONPath subset + text/plain + http_header exposure enforcement)

### Public API (v2)

```python
def invoke_cli(
    *,
    manifest: AdapterManifest,
    input_envelope: Mapping[str, Any],
    sandbox: SandboxedEnvironment,
    worktree: WorktreeHandle,
    budget: Budget,
    workspace_root: Path,
    run_id: str,
) -> tuple[InvocationResult, Budget]:
    """v2 parse order:
    1. Capture stdout + stderr (redacted at emit_adapter_log).
    2. If stdout is fully valid JSON AND matches output_envelope shape -> JSON-first.
    3. Else if stdout is clearly a unified diff (single leading '---' / '+++' / '@@' pattern,
       no prose) AND manifest.capabilities includes 'write_diff' -> synthesize
       {status: 'ok', diff: stdout}.
    4. Else -> status='failed', error.category='output_parse_failed'.
    Free text with embedded diff is ambiguous -> failed (no extraction heuristic).
    """


def invoke_http(
    *,
    manifest: AdapterManifest,
    input_envelope: Mapping[str, Any],
    sandbox: SandboxedEnvironment,
    worktree: WorktreeHandle,
    budget: Budget,
    workspace_root: Path,
    run_id: str,
) -> tuple[InvocationResult, Budget]:
    """v2 HTTP parse (Q4 B6-B7):
    1. If policy.secrets.exposure_modes lacks 'http_header' -> reject before request.
    2. Build headers: auth from resolved secret, others from headers_allowlist.
    3. POST body from request_body_template (placeholder substitution; no secret
       substitution in body / url).
    4. Response parsing:
        a. If body is valid JSON:
           - If response_parse absent -> expect canonical output_envelope shape.
           - If response_parse present -> apply minimal JSONPath subset
             (dotted keys only: '$.a.b'; no array indices, no filters, no wildcards).
        b. Else if Content-Type starts with 'text/plain' AND body begins with unified
           diff markers AND manifest.capabilities includes 'write_diff':
           synthesize {status: 'ok', diff: body}.
        c. Else -> status='failed', error.category='output_parse_failed'.
    5. Auth header value never logged; captured response body redacted per policy."""
```

### Minimal JSONPath subset (v2 B6)

Module-private helper `_jsonpath_dotted(root: Mapping, path: str) -> Any | _SENTINEL_MISSING`:

- Accepts only `$.<key>(.<key>)*` (dot-separated). No `[n]`, no `..`, no filters, no wildcards.
- Parses to tuple of keys; walks the root dict; returns value or `_SENTINEL_MISSING`.
- On non-subset input (e.g. `$.arr[0].diff`), raises `ValueError` at load time so the adapter manifest is rejected early (plan acceptance: loader validates `response_parse.*` paths against the subset before runtime).

Schema description for `response_parse` should warn about subset (docs update in ADAPTERS.md §8, minor; not a scope-fence break — public-facing doc clarification).

### Design decisions (v2)

- **text/plain fallback triple.** content-type + diff marker + capability MUST all hold; otherwise fail.
- **Free text + embedded diff ambiguous.** No heuristic extraction; explicit `output_parse_failed`.
- **Auth header gate (Q4 W).** invoke_http pre-flights `policy.secrets.exposure_modes` before building request; otherwise `PolicyViolation(kind="http_header_exposure_unauthorized")`.
- **Timeout mapping.** `subprocess.TimeoutExpired` → `status='partial'`, `finish_reason='timeout'`. `urllib.error.URLError` with timeout → `status='failed'`, `error.category='http_timeout'`.
- **No per-invocation schema revalidation.** Manifest validated at load (PR-A2); runtime trusts the loaded manifest object.

---

## 9. Module — `executor/executor.py` (v2 cross-ref per-call, primitive contract)

**Path:** `ao_kernel/executor/executor.py`
**LOC budget:** ~400-480 satır (v2: +50 for cross-ref per-call + primitive contract asserts)

### Public API

```python
class Executor:
    def __init__(
        self,
        workspace_root: Path,
        *,
        workflow_registry: WorkflowRegistry,
        adapter_registry: AdapterRegistry,
    ) -> None: ...

    def run_step(
        self,
        run_id: str,
        step_def: StepDefinition,
        *,
        parent_env: Mapping[str, str] | None = None,
    ) -> ExecutionResult:
        """Execute ONE step. Primitive; caller loops for multi-step (PR-A4).

        Pre-flight (v2 B8):
        1. Load run record; assert state != terminal.
        2. Resolve pinned workflow definition from run.workflow_id + workflow_version.
        3. Assert step_def is in definition.steps (by step_name); mismatch -> raise.
        4. Assert step has not already completed (run.steps query); duplicate -> raise.
        5. For actor='adapter': run workflow_registry.validate_cross_refs
           (definition, current_adapter_registry). Non-empty -> raise
           WorkflowDefinitionCrossRefError (fail-closed, NO cache).

        Execution (actor='adapter'):
        6. Build sandbox (policy_enforcer).
        7. Create worktree (worktree_builder).
        8. emit_event 'step_started', 'policy_checked' (allow/deny).
        9. If violations -> emit 'policy_denied' -> CAS update run to failed ->
           raise PolicyViolationError.
        10. emit_event 'adapter_invoked' -> invoke_cli or invoke_http ->
            emit_event 'adapter_returned'.
        11. Map output_envelope.status -> workflow state transition.
        12. CAS update run record (workflow.update_run).
        13. Cleanup worktree (idempotent, finally block).
        14. Return ExecutionResult.
        """
```

### Design decisions (v2)

- **Primitive contract (Q1 add).** `run_step` validates step_def ↔ run record consistency; duplicate / foreign steps rejected. PR-A4 multi-step driver owns the loop.
- **Cross-ref per-call (Q5 B8).** No result caching. Argument: adapter registry is mutable (workspace manifests can be added/removed between steps); PR-A4 may opt into fingerprint-based caching.
- **try/finally worktree cleanup.** If invoke or emit raises, worktree still cleaned.
- **State transition always via `validate_transition`.**
- **Evidence + CAS ordering.** All step lifecycle events emitted BEFORE final run state CAS (crash-safety preference: evidence is the source of truth; state CAS lag by one fsync is recoverable from evidence replay).

---

## 10. Module — `executor/__init__.py`

**Path:** `ao_kernel/executor/__init__.py`
**LOC budget:** ~80 satır

Public re-exports: `Executor`, `ExecutionResult`, `InvocationResult`, `WorktreeHandle`, `SandboxedEnvironment`, `RedactionConfig`, `EvidenceEvent`, `PolicyViolation`, `emit_event`, `emit_adapter_log`, `build_sandbox`, `validate_command`, `validate_cwd`, `resolve_allowed_secrets`, `create_worktree`, `cleanup_worktree`, `invoke_cli`, `invoke_http`, all errors.

**Private (not re-exported):** `_build_env`, `_parse_stdout`, `_redact_command_args`, `_substitute_args`, `_jsonpath_dotted`, `_SENTINEL_MISSING`.

---

## 11. `fixtures` package (v2 canonical JSON output)

**Paths:**
- `ao_kernel/fixtures/__init__.py` (v2 Q6 W: required for setuptools package discovery)
- `ao_kernel/fixtures/codex_stub.py`

### codex_stub contract (v2 Q7 W)

- Entry: `python3 -m ao_kernel.fixtures.codex_stub --prompt-file <path> --run-id <uuid>` [--stdin-mode <mode>].
- Reads prompt from file or stdin per mode.
- Emits **canonical `output_envelope` JSON** on stdout (single line JSON; no prose):

```json
{"status":"ok","diff":"--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n","evidence_events":[],"cost_actual":{"tokens_input":0,"tokens_output":0,"time_seconds":0.01}}
```

- Exit 0 on success; non-zero reserved for stub crashes (test fixtures).
- Stability note: `codex_stub` is a **test/demo** adapter; deterministic behaviour preserved within semver (PR-A3+). NOT a public adapter authoring API.

### Acceptance (Q6 W explicit)

- [ ] `ao_kernel/fixtures/__init__.py` exists and is included in setuptools `packages.find`.
- [ ] `pip install ao-kernel` ships `codex_stub.py` (wheel presence test).
- [ ] `codex_stub` manifest fixture (tests/fixtures/executor_adapter_manifests/) points at `python3 -m ao_kernel.fixtures.codex_stub`.

---

## 12. Docs revision — `docs/EVIDENCE-TIMELINE.md` (v2 B4 clarification)

Minor edit to §5 "Integrity Manifest":

**v1 wording (inaccurate for PR-A3):** "The manifest is updated on every event append (atomic write)."

**v2 wording:** "The manifest is **generated on demand by the PR-A5 evidence-timeline CLI** after a run completes (or at user request). PR-A3 writes events to JSONL append-only with per-run lock + fsync; the manifest is a separate PR-A5 artefact that re-hashes the artefacts at query time."

This is a bug-fix clarification, not a schema/contract change.

---

## 13. Test Strategy (v2 expanded)

### Coverage targets (unchanged)

- `policy_enforcer.py`: ≥ 95%
- `worktree_builder.py`: ≥ 85%
- `evidence_emitter.py`: ≥ 95%
- `adapter_invoker.py`: ≥ 85%
- `executor.py`: ≥ 90%

### Test file breakdown (target: ≥ 145 new tests)

| File | Tests | v2 additions |
|---|---|---|
| `test_executor_policy_enforcer.py` | 42-50 | +PATH poisoning denied (B1); +inherit_from_parent=False strict (B2); +http_header_exposure_unauthorized (Q4 W) |
| `test_executor_worktree_builder.py` | 18-22 | chmod 0o700 check; idempotent cleanup |
| `test_executor_evidence_emitter.py` | 32-38 | +seq monotonicity under concurrent writers (simulated); +event_id opaque (not assumed monotonic); +canonical emission order for a full step |
| `test_executor_adapter_invoker.py` | 48-58 | +JSONPath subset happy + rejected-non-subset; +text/plain fallback triple; +http_header_exposure_unauthorized pre-flight |
| `test_executor_integration.py` | 22-28 | +cross-ref per-call (adapter removed between steps); +duplicate step rejection; +foreign step rejection |

**Total:** ~162-196 new tests. Baseline 1260 → target ≥ 1422.

### Fixtures (v2 expanded)

- `tests/fixtures/executor_policy_profiles/` — bundled override + PATH-hardening policy variant.
- `tests/fixtures/executor_adapter_manifests/` — codex-stub (points at `ao_kernel.fixtures.codex_stub`), mock HTTP adapter, timeout stub, crash stub.

### CI subprocess budget (v2 Q8 W net)

- **1 unmocked CLI happy-path** integration: `python3 -m ao_kernel.fixtures.codex_stub` — target < 2 s.
- **1 unmocked env-hermeticity helper subprocess**: a tiny script that dumps env; asserts only sandbox keys present — target < 1 s.
- **All other subprocess paths mocked** via `monkeypatch.setattr(subprocess, "run", ...)`.

### Test quality gate

No `assert True`, no `except: pass`, no single `assert x is not None` as sole assertion.

---

## 14. CHANGELOG Update

(Same shape as v1 §13; full content populated at commit time.)

---

## 15. Acceptance Criteria (v2)

### Module + test

- [ ] 6 executor modules + `ao_kernel/fixtures/{__init__.py, codex_stub.py}` created.
- [ ] 5 test files + 2 fixture directories; ≥ 145 new tests passing.
- [ ] Coverage targets met per §13.
- [ ] Total test count ≥ 1405 (1260 baseline + 145 minimum).

### End-to-end acceptance (v2 specific)

- [ ] `codex-stub` invocation via real subprocess succeeds with canonical JSON envelope.
- [ ] PATH poisoning denied: fake `python3` under `/tmp/evil` first in PATH → invocation denied.
- [ ] `inherit_from_parent=False` strict: sandbox env_vars contains only explicit_additions + secrets (verified by env-dump helper subprocess).
- [ ] Evidence events written in canonical order with monotonic `seq`; per-run lock prevents interleaving.
- [ ] JSONPath subset validated at adapter manifest load; `$.a.b[0]` rejected.
- [ ] text/plain fallback fires only when content-type + marker + `write_diff` capability all hold.
- [ ] HTTP adapter with `auth_secret_id_ref` but `exposure_modes` lacking `http_header` → pre-flight denial.
- [ ] Cross-ref validation fires per-call; adapter manifest removed between `run_step` invocations → second call raises.
- [ ] Budget exhaust mid-invocation → failed with `error.category="budget_exhausted"`.
- [ ] Evidence redaction: 6 P0 secret patterns replaced with `***REDACTED***`.

### Regression

- [ ] 1260 existing tests still pass.
- [ ] Ruff + mypy strict clean on new modules.
- [ ] No PR-A0/A1/A2 schema or module modifications (grep-verified).
- [ ] `docs/EVIDENCE-TIMELINE.md` §5 revised (scope-acknowledged bug fix).
- [ ] `pyproject.toml` unchanged (no new core dep).

---

## 16. Risk & Mitigation (v2)

| Risk | Olasılık | Mitigation |
|---|---|---|
| PATH poisoning bypass | Düşük | realpath + policy-derived prefix anchor (v2 B1); explicit test |
| inherit semantic drift | Düşük | Default false, strict passthrough off; explicit test (v2 B2) |
| Event ordering race | Düşük | Per-run lock + monotonic seq (v2 B3); concurrent-writer simulation test |
| event_id non-monotonic surprise | Düşük | Doc states opaque; consumers sort by seq (v2 B5) |
| Manifest not generated | Düşük | docs revised; PR-A5 CLI generates (v2 B4) |
| JSONPath subset limitation | Düşük | Load-time validation rejects non-subset paths; error message points to subset docs (v2 B6) |
| text/plain misinterpretation | Düşük | Triple-gate (content-type + marker + capability); ambiguous fails (v2 B7) |
| Cross-ref stale cache | Eliminated | Per-call re-validation, no cache (v2 B8) |
| Subprocess env leak | Düşük | env-dump helper integration test |
| Docs-revision seen as scope break | Düşük | Bug-fix clarification, not contract change; PR body calls it out |

---

## 17. CNS-022 Status + Post-PR-A3 Outlook

### CNS-022 iter-2 expectation (per-fix verification)

iter-2 micro-verification of 8 blocker fixes (NB1–NB8) + 9 warning fixes (NB9 grouped); expected AGREE given full absorption (CNS-019/020/021 pattern).

### Post-PR-A3

- **PR-A4** — multi-step workflow driver + diff/patch engine + CI gate runner.
- **PR-A5** — evidence timeline CLI + manifest generator (the deferred piece in v2 B4).
- **PR-A6** — demo runnable + `[coding]` meta-extra + README + `[llm]` intent classifier impl.

---

## 18. Audit Trail

| Field | Value |
|---|---|
| Base SHA | `e68b655` (PR-A2 merge @ main) |
| Branch | `claude/tranche-a-pr-a3` (to create) |
| Plan authority | v2.1.1 §15 + PR-A0/A1/A2 |
| CNS (PR-A3 plan) | CNS-20260415-022 iter-1 PARTIAL → iter-2 pending |
| Adversarial stats (iter-1) | 8 blocking + 9 warning absorbed in v2 |
| MCP thread | `019d9214-9200-75a0-be8e-ff1ec265351c` |
| Sibling plans | `PR-A0-DRAFT-PLAN.md`, `PR-A1-IMPLEMENTATION-PLAN.md`, `PR-A2-IMPLEMENTATION-PLAN.md` |
| Schema references | agent-adapter-contract, workflow-run, workflow-definition, policy_worktree_profile |
| Module references | `ao_kernel/workflow/run_store.py` (PR-A1 CAS), `ao_kernel/workflow/registry.py` + `ao_kernel/adapters/manifest_loader.py` (PR-A2), `ao_kernel/_internal/evidence/writer.py` (JSONL), `ao_kernel/_internal/prj_kernel_api/llm_transport.py` (urllib), `ao_kernel/_internal/roadmap/step_templates.py` (subprocess) |
| Docs revision | `docs/EVIDENCE-TIMELINE.md` §5 (manifest clarification) |

---

**Status:** DRAFT v2, 8 blocker + 9 warning absorbed. Awaiting CNS-022 iter-2 AGREE before implementation.
