# PR-C2 Implementation Plan v1 — parent_env Union (Real Adapter Full Mode)

**Scope**: FAZ-C runtime closure 3. track. Driver `_run_adapter_step` + `_build_sandbox` içinde `parent_env={}` sabit'i, `os.environ`'dan `policy.secrets.allowlist_secret_ids ∪ policy.env_allowlist.allowed_keys` union'u ile değiştirilir. Real adapter full-mode (secrets + env passthrough) enable olur.

**Base**: `main 7c3449a` (PR #110 C1b merged). **Branch**: `feat/pr-c2-parent-env-union`.

**Status**: Pre-Codex iter-1 submit.

---

## 1. Problem

C1a + C1b altyapısı sonrası adapter-path'in bitmemiş son parçası: driver secret/env passthrough.

**Kod yüzey**: `ao_kernel/executor/multi_step_driver.py`:
- Line 477: `parent_env={}` (executor.run_step call).
- Line 1831: `parent_env={}` (_build_sandbox internal).

**Sonuç**: `resolve_allowed_secrets(policy, all_env={})` — `allowlist_secret_ids` içinde olan secret'lar hiç resolve edilemez. `GH_TOKEN`, `ANTHROPIC_API_KEY` gibi secret'lar her zaman missing. Adapter full-mode (real `gh pr create`, real `claude-code-cli` çağrıları) imkansız.

Ayrıca C1b full E2E benchmark'ın blocker'ı kısmen bu — `validate_command` preflight'ın PATH synthesis'i policy-derived'dir (parent_env'e bağlı değil) ama sandbox env passthrough (build_sandbox içinde) parent_env={} nedeniyle kırılıyor.

---

## 2. Scope (atomic deliverable)

### 2.1 Union computation helper

**Yeni fonksiyon** (`multi_step_driver.py`):

```python
@staticmethod
def _compute_parent_env(policy: Mapping[str, Any]) -> dict[str, str]:
    """PR-C2: build parent_env from union of
    ``policy.secrets.allowlist_secret_ids ∪
    policy.env_allowlist.allowed_keys``, filtered by presence in
    ``os.environ``. Missing keys are silently omitted (caller
    policy layer will raise ``secret_missing`` if required).

    This is the CALLER-layer fix (Codex FAZ-C iter-4 absorb):
    resolver + sandbox signatures unchanged; union lives in driver.
    """
    secrets_spec = policy.get("secrets", {}) or {}
    env_spec = policy.get("env_allowlist", {}) or {}
    secret_ids = set(secrets_spec.get("allowlist_secret_ids", ()) or ())
    allowed_keys = set(env_spec.get("allowed_keys", ()) or ())
    union = secret_ids | allowed_keys
    return {k: os.environ[k] for k in union if k in os.environ}
```

Import eklenir: `import os` (dosya başında zaten olabilir; kontrol edilir).

### 2.2 `_run_adapter_step` parent_env forward

**Before** (`multi_step_driver.py:467-477`):
```python
exec_result = self._executor.run_step(
    run_id=run_id,
    step_def=step_def,
    parent_env={},  # HARDCODED
    attempt=attempt,
    ...
)
```

**After** (v1):
```python
exec_result = self._executor.run_step(
    run_id=run_id,
    step_def=step_def,
    parent_env=self._compute_parent_env(self._policy),  # UNION
    attempt=attempt,
    ...
)
```

### 2.3 `_build_sandbox` parent_env forward

**Before** (`multi_step_driver.py:1822-1833`):
```python
def _build_sandbox(self, run_id: str) -> SandboxedEnvironment:
    worktree = self._workspace_root / ".ao" / "runs" / run_id / "worktree"
    if not worktree.exists():
        worktree = self._workspace_root
    resolved_secrets, _ = resolve_allowed_secrets(self._policy, {})  # EMPTY
    sandbox, _violations = build_sandbox(
        policy=self._policy,
        worktree_root=worktree,
        resolved_secrets=resolved_secrets,
        parent_env={},  # HARDCODED
    )
    return sandbox
```

**After** (v1):
```python
def _build_sandbox(self, run_id: str) -> SandboxedEnvironment:
    worktree = self._workspace_root / ".ao" / "runs" / run_id / "worktree"
    if not worktree.exists():
        worktree = self._workspace_root
    parent_env = self._compute_parent_env(self._policy)  # UNION
    resolved_secrets, _ = resolve_allowed_secrets(self._policy, parent_env)
    sandbox, _violations = build_sandbox(
        policy=self._policy,
        worktree_root=worktree,
        resolved_secrets=resolved_secrets,
        parent_env=parent_env,
    )
    return sandbox
```

### 2.4 Signature invariants (MASTER plan v5 §C2 §B3 absorb)

- `resolve_allowed_secrets(policy, all_env)` — **SIGNATURE UNCHANGED**. İkinci arg hâlâ `Mapping[str, str]` — artık boş dict yerine union dict geliyor. Secret resolver secret-only kalır; env passthrough logic yok.
- `build_sandbox(policy, worktree_root, resolved_secrets, parent_env)` — **SIGNATURE UNCHANGED**. parent_env artık union-backed; sandbox içindeki env passthrough (line 118-128) zaten allowlist'e göre filtreliyor (inherit_from_parent=true iken).
- `Executor.run_step(parent_env=...)` — **SIGNATURE UNCHANGED**. Mevcut kwarg union-backed.

Union caller-layer değişikliği; downstream surface dokunulmaz.

---

## 3. Test Plan

### 3.1 Yeni test

`tests/test_parent_env_union.py`:
- `test_union_includes_allowlist_secret_ids` — policy fixture'da `secrets.allowlist_secret_ids=['MY_TOKEN']`; `os.environ['MY_TOKEN']='xyz'` monkeypatch → `_compute_parent_env` → `{'MY_TOKEN': 'xyz'}`.
- `test_union_includes_env_allowlist_allowed_keys` — policy `env_allowlist.allowed_keys=['PATH']`; `os.environ['PATH']='...'` → return dict'te PATH.
- `test_union_merges_both_sets` — her ikisi farklı key'lerle; union'da hepsi.
- `test_union_omits_missing_keys` — policy listeler ama env'de yok → dict'te yok (silent skip).
- `test_union_empty_when_policy_empty` — her iki liste boş → `{}`.
- Integration: `test_run_adapter_step_forwards_union_parent_env` — mock executor.run_step; `parent_env` arg union içerir.

### 3.2 Regression gate

- `pytest tests/ -x` — 2153 + N new = ~2158 green.
- Özellikle `test_multi_step_driver.py` ve `test_executor_integration.py` — parent_env={} → union dict geçişi davranış değişikliği sebep olmasın.

---

## 4. Out of Scope

- **`validate_command` preflight issue** (C1b full E2E blocker — command_allowlist PATH synthesis) — **C2 scope değil**. C2 sadece parent_env union. Eğer PATH synthesis ayrı bir bug ise ayrı PR.
- **C3** (post_adapter_reconcile middleware) — ayrı PR.
- **C6** (dry_run_step) — ayrı PR.
- Policy schema değişiklikleri — hiçbiri.
- `resolve_allowed_secrets` / `build_sandbox` signature değişiklikleri — hiçbiri.

---

## 5. Risk Register

| Risk | L | I | Mitigation |
|---|---|---|---|
| R1 Union `os.environ` read test isolation'ını kırar | M | M | Tüm testler `monkeypatch.setenv` kullanır; global `os.environ` mutate edilmez |
| R2 Mevcut callers `parent_env={}` varsayımıyla yazılmış | L | M | Regression gate: 2153 test zaten parent_env={} bekliyorsa bu değişiklik onları kırar mı? Büyük ihtimalle HAYIR çünkü downstream consumer'lar (resolve_allowed_secrets, build_sandbox) dict'in boş olup olmadığını özel olarak check etmiyor |
| R3 Güvenlik: gereksiz env key'leri sandbox'a sızabilir | L | H | Union policy-declared keys ile sınırlı; `os.environ` full copy DEĞİL. deny_on_unknown=true zaten filtreliyor |
| R4 `_compute_parent_env` static olmazsa self-dep oluşur | L | L | `@staticmethod` ile işaretle |

---

## 6. Codex iter-1 için Açık Sorular

**Q1 — Union timing**: `_compute_parent_env` her call'da hesaplanıyor (O(n) union + dict comprehension). Cache etmek gerekli mi? Driver lifetime boyunca policy sabit, `os.environ` değişebilir → cache stale risk. v1 per-call hesaplama.

**Q2 — Policy shape edge cases**: `policy.secrets` veya `policy.env_allowlist` yoksa (None veya missing key) — default empty set tolerans doğru mu? `deny_on_unknown=true` durumunda boş policy → hiçbir key union'a girmez → secrets missing hataları mevcut davranışla aynı (hiçbir şey değişmedi).

**Q3 — `os.environ` read güvenlik**: Union key'leri policy-declared olsa da, `os.environ` okuma testlerde isolation problemi yaratabilir. `monkeypatch` pattern'ine bağlı — alternative API var mı (os.environ dependency injection)?

**Q4 — C1b validate_command unlock**: Bu fix C1b full E2E'yi unlock eder mi? Gerçek kök neden `build_sandbox` içindeki env passthrough mu (`line 118-128`'in `inherit_from_parent=true` path'i), yoksa farklı bir yerde mi? Bundled policy `inherit_from_parent=false` — parent_env passthrough etkilemez bu case'de. Yani `validate_command` PATH synthesis muhtemelen ayrı bug.

**Q5 — `_build_sandbox` ayrı fix**: `_build_sandbox` (line 1822) `patch_preview`/`apply_patch`/`ci_gate` gibi ao-kernel operasyonlar için kullanılıyor. `_run_adapter_step` executor içinde ayrı sandbox kuruyor (`_run_adapter_step` → `run_step` → `_run_adapter_step executor` → `build_sandbox`). İki yerde de mi fix?

---

## 7. Implementation Order

1. `_compute_parent_env(policy)` staticmethod eklenir (+ `import os`).
2. `_run_adapter_step` call `parent_env=self._compute_parent_env(self._policy)`.
3. `_build_sandbox` parent_env + resolve_allowed_secrets all_env union-backed.
4. 6 yeni test (`test_parent_env_union.py`).
5. Regression pytest.
6. Commit + post-impl Codex review + PR #111.

---

## 8. LOC Estimate

~250 satır (helper +20, call site ×2 +5, 6 test +200, imports +5).

---

## 9. Audit Trail

| Iter | Date | Verdict |
|---|---|---|
| v1 (Claude draft) | 2026-04-18 | Pre-Codex iter-1 submit |

**Codex thread**: Yeni (C2-specific).
