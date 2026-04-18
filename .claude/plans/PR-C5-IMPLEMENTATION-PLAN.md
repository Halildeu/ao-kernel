# PR-C5 Implementation Plan v2 — RFC 7396 Merge-Patch Policy-Sim

**v2 absorb (Codex iter-1 PARTIAL — 4 fix + 1 type contract)**:
1. **Filename contract reversible**: `policy_name.v1.patch.json` → `policy_name.v1.json` (version suffix korunur).
2. **Mutex `is not None`**: `proposed_policies={}` (empty dict) + `proposed_policy_patches={...}` kombinasyonu geçerli; sadece her ikisi `is not None` olduğunda `ValueError`.
3. **Parser-level CLI mutex test**: `argparse.mutually_exclusive_group(required=False)` + parser-level reject test eklendi.
4. **Unknown/new policy patch semantic**: **Fail-fast** seçildi — `resolve_target_policy` baseline bulamazsa `TargetPolicyNotFoundError` propagate (typo protection; scope-down alternative ret).
5. **`apply_merge_patch` type contract**: Narrow to **policy-doc object patch only** — imza `Mapping → dict`; non-Mapping top-level patch (list/scalar) desteklenmez. RFC 7396 "top-level=null" case (delete whole doc) **out of scope**.

---

# (v1 retained for history — see original plan body below)

## PR-C5 Implementation Plan v1 — RFC 7396 Merge-Patch Policy-Sim

**Scope**: FAZ-C strategic extension (bağımsız). `apply_merge_patch` stdlib-only RFC 7396 impl + `simulate_policy_change::proposed_policy_patches` additive kwarg (mutex with `proposed_policies`) + CLI `--proposed-patches <dir>` + edge-case test suite.

**Base**: `main 41e110a` (PR #112 C4 merged). **Branch**: `feat/pr-c5-merge-patch`.

**Status**: Pre-Codex iter-1 submit.

---

## 1. Problem

`simulate_policy_change` bugün tam policy JSON'ları `proposed_policies` kwarg'ında alıyor. Operator sadece DELTA geçirmek isterse her policy'nin tam kopyasını vermek zorunda → hata riski + noise. RFC 7396 JSON Merge Patch pattern standard; stdlib-only mümkün (~30 satır).

---

## 2. Scope (atomic deliverable)

### 2.1 `apply_merge_patch` stdlib impl

**Yeni modül**: `ao_kernel/policy_sim/merge_patch.py`:
```python
def apply_merge_patch(
    baseline: Mapping[str, Any],
    patch: Mapping[str, Any],
) -> dict[str, Any]:
    """RFC 7396 JSON Merge Patch — policy-doc object patch only.
    
    Returns a new dict; baseline + patch arg'ları MUTATE EDILMEZ.
    
    Scope-narrow (v2 Codex iter-1 note): imza `Mapping → dict`;
    top-level non-object patch (list/scalar/null) DESTEKLENMEZ —
    policy documents her zaman object-typed. Operator top-level
    null (whole-doc delete) isterse `proposed_policies` API'sini
    kullansın.
    
    Rules (RFC 7396 subset):
    - `patch[k] is None` → delete key `k` from baseline.
    - Both baseline[k] and patch[k] Mapping → recurse.
    - Else → replace baseline[k] with patch[k].
    - Keys only in baseline → preserved.
    """
    if not isinstance(patch, Mapping):
        raise TypeError(
            "apply_merge_patch: patch must be a Mapping "
            "(policy-doc object patch only)"
        )
    out = dict(baseline) if isinstance(baseline, Mapping) else {}
    for key, pval in patch.items():
        if pval is None:
            out.pop(key, None)
        elif (
            isinstance(pval, Mapping)
            and isinstance(out.get(key), Mapping)
        ):
            out[key] = apply_merge_patch(out[key], pval)
        else:
            out[key] = pval
    return out
```

Immutability invariant: baseline ve patch arg'larını MUTATE ETMEZ. `dict(...)` copy; recursion yeni dict yaratır.

### 2.2 `simulate_policy_change` additive kwarg

**Before** (`simulator.py:457-465`):
```python
def simulate_policy_change(
    *,
    project_root,
    scenarios,
    proposed_policies: Mapping[str, Mapping[str, Any]],
    baseline_source = BaselineSource.BUNDLED,
    baseline_overrides = None,
    include_host_fs_probes = False,
) -> DiffReport:
```

**After** (v1):
```python
def simulate_policy_change(
    *,
    project_root,
    scenarios,
    proposed_policies: Mapping[str, Mapping[str, Any]] | None = None,
    baseline_source = BaselineSource.BUNDLED,
    baseline_overrides = None,
    include_host_fs_probes = False,
    proposed_policy_patches: Mapping[str, Mapping[str, Any]] | None = None,
) -> DiffReport:
    """... existing docstring ...

    PR-C5: ``proposed_policy_patches`` provides RFC 7396 merge
    patches applied to baseline policies to produce effective
    proposed policies. Mutex with ``proposed_policies``:
    caller must supply at most one of the two.
    """
    # Mutex guard — v2 `is not None` (empty dict farklı truthiness'a sahip):
    if (
        proposed_policies is not None
        and proposed_policy_patches is not None
    ):
        raise ValueError(
            "proposed_policies and proposed_policy_patches are mutually "
            "exclusive — supply at most one."
        )
    
    if proposed_policy_patches:
        # Apply each patch against resolved baseline → treat as
        # effective proposed_policies.
        from ao_kernel.policy_sim.merge_patch import apply_merge_patch
        effective_proposed: dict[str, Mapping[str, Any]] = {}
        for policy_name, patch in proposed_policy_patches.items():
            baseline = resolve_target_policy(
                policy_name=policy_name,
                scenario_id="_merge_patch_resolve",
                project_root=project_root,
                proposed_policies={},  # no short-circuit
                baseline_source=baseline_source,
                baseline_overrides=baseline_overrides,
            )
            effective_proposed[policy_name] = apply_merge_patch(
                baseline, patch,
            )
        proposed_policies = effective_proposed
    
    proposed_policies = proposed_policies or {}
    # ... existing body unchanged ...
```

Backwards-compat: `proposed_policies` default None artık (previously required). None → `{}` (no proposed policies), mevcut callers'ın hepsi `proposed_policies=dict(...)` geçiriyor → etkilenmez.

### 2.3 CLI `--proposed-patches <dir>`

**`ao_kernel/cli.py`** (veya `policy_sim/cli.py`):

```bash
ao-kernel policy-sim run \
    --scenarios tests/fixtures/policy_sim_scenarios.v1.json \
    --proposed-patches path/to/patches_dir/
```

`<dir>` içindeki her `*.patch.json` → `{policy_name: patch_dict}`. Mutex CLI-level: `--proposed-patches` + `--proposed-policies` bir arada verilirse error.

Filename convention (v2 reversible): `<policy_filename>.patch.json` → `<policy_filename>.json` (version suffix korunur). Örnek: `policy_worktree_profile.v1.patch.json` → patches `policy_worktree_profile.v1.json`. Loader helper `load_policy_patches_from_dir(dir: Path) -> dict[str, dict]` yeni modülde; mevcut loader resolve mantığından ayrı.

### 2.4 Edge-case test suite

**`tests/test_merge_patch.py`** (stdlib impl unit):
- `test_null_value_deletes_key` — patch `{"k": None}` → baseline `{"k": "v"}` olunca `{}`.
- `test_nested_merge_recurses` — patch `{"outer": {"inner": "new"}}` → baseline `{"outer": {"inner": "old", "keep": "v"}}` olunca `{"outer": {"inner": "new", "keep": "v"}}`.
- `test_absent_key_preserves_baseline` — patch `{}` → baseline unchanged.
- `test_array_replace_not_merge` — patch `{"arr": [1]}` → baseline `{"arr": [2, 3]}` olunca `{"arr": [1]}` (RFC 7396 array=replace).
- `test_scalar_replacing_object` — patch `{"k": "scalar"}` → baseline `{"k": {"nested": "v"}}` olunca `{"k": "scalar"}`.
- `test_object_replacing_scalar` — patch `{"k": {"n": "v"}}` → baseline `{"k": "scalar"}` olunca `{"k": {"n": "v"}}` (Mapping on baseline side missing → straight replace).
- `test_baseline_immutable` — apply_merge_patch çağrıldıktan sonra baseline dict aynı.
- `test_patch_immutable` — patch dict aynı.

**`tests/test_simulate_policy_patches.py`** (integration):
- `test_mutex_raises_value_error` — `proposed_policies=dict` + `proposed_policy_patches=dict` aynı anda → `ValueError`.
- `test_empty_dict_proposed_with_patches_allowed` — `proposed_policies={}` + `proposed_policy_patches={...}` → `ValueError` YOK (v2 fix: `is not None` guard; empty dict normalize edilir patch tarafında).
- `test_patches_apply_against_baseline` — `proposed_policy_patches={"policy_x.v1": {"enabled": True}}` + baseline `enabled=False` → simulator effective proposed = merged.
- `test_unknown_policy_patch_fails_fast` — v2 **fail-fast**: `proposed_policy_patches={"nonexistent.v1": {...}}` → `TargetPolicyNotFoundError` (typo protection).
- `test_both_none_allowed` — `proposed_policies=None` + `proposed_policy_patches=None` → baseline-only run (existing behavior).
- `test_cli_parser_mutex` (parser-level, v2 fix): `ao-kernel policy-sim run --proposed-policies x --proposed-patches y` → argparse `SystemExit` (mutually_exclusive_group enforced).

---

## 3. Regression gate

- `pytest tests/ -x` — 2170 + ~11 test = ~2181 green.
- Existing `simulate_policy_change` callers geçtikleri `proposed_policies` kwargs davranışı korur.

---

## 4. Out of Scope

- CLI full integration test (dir loader) — v1'de basic unit kapsamı yeterli.
- Schema validation of patch shape — RFC 7396 schema-free; validation post-merge (mevcut `validate_proposed_policy`).
- C3/C6 — paralel.

---

## 5. Risk Register

| Risk | L | I | Mitigation |
|---|---|---|---|
| R1 `proposed_policies=None` default backwards-compat kırar | M | M | Mevcut callers kwarg-only + explicit dict; None default safe |
| R2 Recursive merge stack limit | L | L | Policy dict depth ≤5 pratikte; Python default 1000 recursion yeter |
| R3 Patch dict mutation | M | L | Test: patch arg immutability invariant assert |
| R4 CLI flag mutex oto-test | M | M | argparse mutually_exclusive_group |

---

## 6. Codex iter-1 için Açık Sorular

**Q1 — `apply_merge_patch` yeri**: Yeni modül `policy_sim/merge_patch.py` mi, yoksa `policy_sim/loader.py` içine ekleme mi? Loader zaten resolve logic yapıyor; merge daha çok data-transform.

**Q2 — Mutex guard site**: Mutex `simulate_policy_change` fn body'de `ValueError` mi (v1 plan), yoksa ayrı `_validate_mutex()` helper mı? v1 inline yeterli.

**Q3 — `proposed_policies=None` default**: Mevcut signature required; v1 `None = None`. Mevcut `test_simulator*.py` callers etkilenir mi (grep-gerek)?

**Q4 — CLI `--proposed-patches` dir loading**: `<dir>/*.patch.json` glob + `json.load` her biri. Filename convention `<policy_name>.patch.json`. Bundled ya mapping pattern mı? Farklı convention mı uygun?

**Q5 — Post-merge policy shape validation**: `apply_merge_patch` çıktısı `validate_proposed_policy` ile kontrol edilir mi (mevcut flow), yoksa merge öncesi patch shape ayrı mı validate (RFC 7396 schema-free → sonradan)?

---

## 7. Implementation Order

1. `apply_merge_patch` yeni modül.
2. `simulate_policy_change` additive kwarg + mutex guard.
3. CLI `--proposed-patches` flag + dir loader.
4. 8 edge-case + 3 integration test.
5. Regression + commit + post-impl Codex review + PR #113.

---

## 8. LOC Estimate

~450 satır (merge_patch.py +40, simulator.py +30, cli.py +20, 11 test +300, docs +60).

---

## 9. Audit Trail

| Iter | Date | Verdict |
|---|---|---|
| v1 (Claude draft) | 2026-04-18 | Pre-Codex submit (`4288d36`) |
| iter-1 (thread `019da04c`) | 2026-04-18 | **PARTIAL** — 4 fix (filename reversible + mutex is-not-None + CLI parser test + unknown patch semantic) + 1 type contract narrow |
| **v2 (iter-1 absorb)** | 2026-04-18 | Pre-iter-2. Filename versioned; `is not None` mutex; parser-level CLI mutex test; fail-fast unknown policy; `apply_merge_patch` policy-doc-only. |
| iter-2 | TBD | AGREE expected (4 concrete fix'ler + explicit type contract) |

**Codex thread**: `019da04c-a05e-7bf2-a27c-dc267d791367` (C5-specific).
