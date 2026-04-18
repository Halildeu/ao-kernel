# PR-C5 Implementation Plan v1 — RFC 7396 Merge-Patch Policy-Sim

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
    """RFC 7396 JSON Merge Patch. Returns a new dict — baseline
    NOT mutated.
    
    Rules:
    - `patch[k] is None`: delete key `k` from baseline.
    - `isinstance(patch[k], Mapping) AND isinstance(baseline.get(k), Mapping)`:
      recurse (nested merge).
    - Else: replace baseline[k] with patch[k] (arrays, scalars,
      object-replacing-scalar all handled by straight replace).
    - Keys present only in baseline (not in patch): preserved.
    """
    if not isinstance(patch, Mapping):
        return dict(patch) if isinstance(patch, (list, dict)) else patch
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
    # Mutex guard
    if proposed_policies and proposed_policy_patches:
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

Filename convention: `<policy_name>.patch.json` (ör. `policy_worktree_profile.patch.json` → patches `policy_worktree_profile.v1.json`).

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
- `test_patches_apply_against_baseline` — `proposed_policy_patches={"policy_x": {"enabled": True}}` + baseline `enabled=False` → simulator effective proposed = merged.
- `test_both_none_allowed` — `proposed_policies=None` + `proposed_policy_patches=None` → baseline-only run (existing behavior contract).

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
| v1 (Claude draft) | 2026-04-18 | Pre-Codex iter-1 submit |

**Codex thread**: Yeni (C5-specific).
