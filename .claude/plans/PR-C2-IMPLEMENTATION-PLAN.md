# PR-C2 Implementation Plan v2 — parent_env Union (Security-Split)

**Scope**: FAZ-C runtime closure 3. track. Driver parent_env={} sabit'leri iki farklı güvenlik sınırıyla doldurulur:
- **Adapter path** (`_run_adapter_step`): UNION `allowlist_secret_ids ∪ env_allowlist.allowed_keys` — adapter'ın GH_TOKEN/ANTHROPIC_API_KEY gibi secret'lara ihtiyacı var.
- **Sandbox path** (`_build_sandbox` for CI/patch): YALNIZ `env_allowlist.allowed_keys` — CI/patch subprocess'lerine secret SIZDIRILMAZ (least-privilege).

**Base**: `main 7c3449a` (PR #110 C1b merged). **Branch**: `feat/pr-c2-parent-env-union`.

**Status**: iter-1 PARTIAL absorb → iter-2 submit. Codex thread `019da01e-3eda-7c23-a995-7d273e5ae9d6`.

---

## v2 absorb summary (Codex iter-1 PARTIAL — 3 blocker + Q1-Q5)

| # | iter-1 bulgu | v2 fix |
|---|---|---|
| **B1 (HIGH SECURITY)** | v1 `_build_sandbox` union secret davranışı yanlış — `build_sandbox` `resolved_secrets`'i env_vars'a fold ediyor (`policy_enforcer.py:154`); `ci_pytest` subprocess GH_TOKEN/ANTHROPIC_API_KEY görür. Least-privilege ihlali. | v2 **güvenlik split**: Adapter path union (secret+env), sandbox path sadece env_allowlist. İki ayrı helper: `_compute_adapter_parent_env(policy)` vs `_compute_sandbox_parent_env(policy)`. `_build_sandbox` içinde `parent_env` SADECE env_allowlist keys; `resolve_allowed_secrets(policy, parent_env)` → resolved={} (CI için secret yok). |
| **B2 (coupling)** | Driver + Executor ayrı policy source'u tutuyor. `Executor._policy` via policy_loader kwarg (`:107`); `MultiStepDriver._policy` via policy_config kwarg default {} (`:196-202`). `build_driver` policy_loader'ı sadece Executor'a geçiriyor → driver `_build_sandbox` için policy boş. | v2 `build_driver(root, *, policy_loader=None)` **hem Executor hem Driver'a forward**: `MultiStepDriver(..., policy_config=policy_loader)`. Single source of truth. |
| **B3 (test eksik)** | v1 6 test `_build_sandbox` ikinci call-site'ı pinlemiyor. Security-critical negatif test ("CI sandbox'a secret gitmez") yok. | v2 test plan güncellendi: `test_build_sandbox_excludes_secrets` negatif test + `test_adapter_sandbox_includes_secrets` positive test. Toplam 8 test. |

### v2 absorb Q answers

- **Q1** (caching) ✅: Per-call doğru karar. `os.environ` stale risk nedeniyle cache etme.
- **Q2** (edge cases) ✅: `or {}` / `or ()` pattern doğru; `enabled=false` bu katmanda enforce edilmiyor zaten (Codex note: dormant semantik policy_enforcer'da aktif değil — C1b discovery ile tutarlı).
- **Q3** (test isolation) ✅: `monkeypatch.setenv` + `monkeypatch.delenv(raising=False)` yeterli. Unique env adları kullan (test çakışma önleme).
- **Q4** (C1b unlock) ⚠️: Kısmi. Adapter path için secret/env taşıma çözülür. `validate_command` PATH synthesis ayrı bug — C2 kapsamı dışı.
- **Q5** (iki site) ✅: Ayrı scope: adapter UNION, sandbox env_only. B1 fix bunu netleştiriyor.

---

## 1. Problem

C1a+C1b sonrası adapter path'in bitmemiş kısmı: driver parent_env={} sabit'i.

**Kod yüzey** (`multi_step_driver.py`):
- Line 477: `_run_adapter_step` → `executor.run_step(parent_env={})`.
- Line 1831: `_build_sandbox` → `resolve_allowed_secrets(policy, {})` + `build_sandbox(..., parent_env={})`.

**Sonuç**:
- `resolve_allowed_secrets` secret'ları resolve edemez → adapter GH_TOKEN/ANTHROPIC_API_KEY alamaz.
- `build_sandbox` env_allowlist passthrough boş → sandbox'ta PATH synth policy prefix'lerden gelir ama host PATH inherit edilmez.

**Ek coupling**: `build_driver(root, *, policy_loader=None)` (tests/_driver_helpers.py:100) sadece Executor'a geçiriyor; Driver `policy_config={}` kalıyor. Test helper ve gerçek driver init çağrılarında policy split var.

---

## 2. Scope (atomic deliverable)

### 2.1 İki güvenlik sınırı ile helper

**`multi_step_driver.py`** (yeni + `import os` kontrol):

```python
@staticmethod
def _compute_adapter_parent_env(
    policy: Mapping[str, Any],
) -> dict[str, str]:
    """PR-C2 adapter sandbox parent_env — UNION secret_ids + env_keys.
    Adapter runtime (codex-stub, claude-code-cli, gh-cli-pr) secret
    erişimine ihtiyaç duyar."""
    import os as _os
    secrets_spec = policy.get("secrets", {}) or {}
    env_spec = policy.get("env_allowlist", {}) or {}
    secret_ids = set(secrets_spec.get("allowlist_secret_ids", ()) or ())
    allowed_keys = set(env_spec.get("allowed_keys", ()) or ())
    union = secret_ids | allowed_keys
    return {k: _os.environ[k] for k in union if k in _os.environ}


@staticmethod
def _compute_sandbox_parent_env(
    policy: Mapping[str, Any],
) -> dict[str, str]:
    """PR-C2 CI/patch sandbox parent_env — env_allowlist only.
    Secret'lar DEĞİL — `ci_pytest`/`ci_ruff`/`patch_*` subprocess'leri
    least-privilege (GH_TOKEN sızdırmaz)."""
    import os as _os
    env_spec = policy.get("env_allowlist", {}) or {}
    allowed_keys = set(env_spec.get("allowed_keys", ()) or ())
    return {k: _os.environ[k] for k in allowed_keys if k in _os.environ}
```

### 2.2 `_run_adapter_step` — adapter UNION

**Before** (`:467-477`):
```python
exec_result = self._executor.run_step(
    ...,
    parent_env={},
    ...,
)
```

**After** (v2):
```python
adapter_parent_env = self._compute_adapter_parent_env(self._policy)
exec_result = self._executor.run_step(
    ...,
    parent_env=adapter_parent_env,  # UNION secret+env
    ...,
)
```

### 2.3 `_build_sandbox` — CI/patch env_only

**Before** (`:1822-1833`):
```python
def _build_sandbox(self, run_id: str) -> SandboxedEnvironment:
    ...
    resolved_secrets, _ = resolve_allowed_secrets(self._policy, {})
    sandbox, _ = build_sandbox(
        policy=self._policy,
        worktree_root=worktree,
        resolved_secrets=resolved_secrets,
        parent_env={},
    )
    return sandbox
```

**After** (v2 — secret bypass):
```python
def _build_sandbox(self, run_id: str) -> SandboxedEnvironment:
    ...
    sandbox_parent_env = self._compute_sandbox_parent_env(self._policy)
    # resolve_allowed_secrets(policy, parent_env) — parent_env secret
    # içermediği için resolved={} döner (secret_id'ler env'de yok).
    resolved_secrets, _ = resolve_allowed_secrets(
        self._policy, sandbox_parent_env,
    )
    sandbox, _ = build_sandbox(
        policy=self._policy,
        worktree_root=worktree,
        resolved_secrets=resolved_secrets,  # {} expected
        parent_env=sandbox_parent_env,
    )
    return sandbox
```

Güvenlik invariantı: `resolved_secrets=={}` CI/patch için. Test ile pin'li (B3 absorb).

### 2.4 `build_driver` policy_config forward

**Before** (`tests/_driver_helpers.py:100-119`):
```python
def build_driver(
    root: Path,
    *,
    policy_loader: Mapping[str, Any] | None = None,
) -> MultiStepDriver:
    ...
    executor = Executor(
        ...,
        policy_loader=policy_loader,
    )
    return MultiStepDriver(
        workspace_root=root,
        registry=wreg,
        adapter_registry=areg,
        executor=executor,
    )
```

**After** (v2 — policy_config forward):
```python
def build_driver(
    root: Path,
    *,
    policy_loader: Mapping[str, Any] | None = None,
) -> MultiStepDriver:
    ...
    executor = Executor(
        ...,
        policy_loader=policy_loader,
    )
    return MultiStepDriver(
        workspace_root=root,
        registry=wreg,
        adapter_registry=areg,
        executor=executor,
        policy_config=policy_loader,  # YENI — driver policy forward
    )
```

Backwards-compat: `policy_loader=None` → driver `policy_config={}` (mevcut davranış).

### 2.5 Signature invariants

`resolve_allowed_secrets(policy, all_env)`, `build_sandbox(...)`, `Executor.run_step(parent_env=...)` — **hepsi DOKUNULMAZ**. Union/env-only caller-layer değişikliği.

---

## 3. Test Plan

### 3.1 Yeni test (`tests/test_parent_env_union.py`, 8 case):

**Helper unit tests** (4):
- `test_adapter_parent_env_includes_allowlist_secret_ids` — `allowlist_secret_ids=['MY_TOKEN']` + env → union'da MY_TOKEN.
- `test_adapter_parent_env_includes_env_allowlist_keys` — `env_allowlist.allowed_keys=['PATH']` + env → union'da PATH.
- `test_sandbox_parent_env_excludes_secrets` — **GÜVENLİK**: `allowlist_secret_ids=['GH_TOKEN']` + env → sandbox_parent_env'de GH_TOKEN YOK (sadece env_allowlist).
- `test_parent_env_omits_missing_keys` — listelenmiş ama env'de yok → dict'te yok.

**Integration smoke** (2):
- `test_run_adapter_step_forwards_union_parent_env` — mock executor.run_step; `parent_env` arg union içerir (hem secret hem env).
- `test_build_sandbox_uses_env_only_parent_env` — `_build_sandbox` çağrısı sonrası `resolve_allowed_secrets` ikinci arg env_allowlist-only (secret yok).

**Security regression** (2):
- `test_ci_sandbox_does_not_leak_secret` — negatif test: policy `allowlist_secret_ids=['GH_TOKEN']` + env'de GH_TOKEN var → `_build_sandbox` sonrası sandbox.env_vars içinde GH_TOKEN YOK.
- `test_adapter_sandbox_includes_secret` — positive test: aynı policy + adapter path → executor call'a parent_env'de GH_TOKEN VAR.

### 3.2 Regression gate

- `pytest tests/ -x` — 2153 + 8 = 2161 green.
- Özellikle `test_executor_integration.py` (policy_loader testleri) + `test_driver_helpers_policy_loader.py` — build_driver policy_config forward yeni davranışı kırılan test'i olmamalı.

---

## 4. Out of Scope

- **`validate_command` PATH synthesis issue** (C1b full E2E blocker) — ayrı bug; C2 kapsamı dışı.
- **C3** (post_adapter_reconcile) / **C6** (dry_run_step) — paralel PR.
- Schema değişiklikleri — hiçbiri.
- `resolve_allowed_secrets` / `build_sandbox` / `run_step` signature değişiklikleri — hiçbiri.

---

## 5. Risk Register

| Risk | L | I | Mitigation |
|---|---|---|---|
| R1 `os.environ` read test isolation | M | M | `monkeypatch.setenv`/`delenv(raising=False)` pattern + unique env names |
| R2 `build_driver` policy_config forward mevcut callers'ı kırar | L | M | Additive default-None; mevcut davranış korunur |
| R3 CI sandbox secret leak regression (sec-critical) | L | H | Negatif test kontrat olarak pin'li (B3 absorb) |
| R4 policy.env_allowlist listelenmeyen secret_id'ler (ör. GH_TOKEN) adapter union'a girer ama env'de yoksa missing-secret violation | L | M | Beklenen davranış: mevcut `resolve_allowed_secrets` `secret_missing` violation emit eder; v2 caller iki nokta union kuruyor, downstream semantik değişmez |

---

## 6. Implementation Order

1. `_compute_adapter_parent_env` + `_compute_sandbox_parent_env` staticmethods.
2. `_run_adapter_step` call union.
3. `_build_sandbox` env-only.
4. `build_driver(policy_loader=)` policy_config forward.
5. 8 yeni test.
6. Regression pytest.
7. Commit + post-impl Codex review + PR #111.

---

## 7. LOC Estimate

~350 satır (helpers +40, call sites +10, build_driver +3, 8 test +280, imports +5).

---

## 8. Audit Trail

| Iter | Date | Verdict |
|---|---|---|
| v1 (Claude draft) | 2026-04-18 | Pre-Codex submit (`1f9a4a0`) |
| iter-1 (thread `019da01e`) | 2026-04-18 | **PARTIAL** — 3 blocker (B1 HIGH SEC: sandbox union secret leak, B2 driver/executor policy split, B3 test coverage) + Q1-Q5 net |
| **v2 (iter-1 absorb)** | 2026-04-18 | Pre-iter-2 submit. Security-split: adapter UNION, sandbox env-only + driver policy_config forward + negatif test. |
| iter-2 | TBD | AGREE expected (dar scope security-aware revision) |
