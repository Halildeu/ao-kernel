# PR-B4 Implementation Plan v3 — Policy Simulation Harness

**Tranche B PR 4/9 — plan v3, post-Codex iter-2 PARTIAL absorb (adapter snapshot API + iç tutarlılık fix'leri).**

**Head SHA**: `75c114f` (PR #102 B5 metrics merged). Base: `main`. Active branch (for draft work): currently `claude/tranche-b-pr-b3` — **will require new branch** `claude/tranche-b-pr-b4` before any commit work.

**Master-plan scope**: `ao_kernel/policy_sim/` — mid-depth simulator reusing `governance.check_policy` + executor policy primitives without worktree/adapter side-effects. Dry-run policy change → deny/allow diff report.

---

## v3 absorb summary (Codex CNS-20260418-038 iter-2 PARTIAL — 1 blocker + 3 warnings)

**iter-2 verdict**: PARTIAL — v2 6 bulgu absorb edildi, ancak adapter snapshot API hatalı (blocker) + 3 iç tutarsızlık (warnings).

| # | v2 bulgu | v3 fix |
|---|---|---|
| **1 (BLOCKER)** | **§2.1 `AdapterRegistry.load_workspace(project_root).capabilities_snapshot()` — böyle bir API YOK**. Gerçek surface: `load_bundled()`, `load_workspace()`, `get()`, `list_adapters()`, `missing_capabilities()`, `supports_capabilities()` (`ao_kernel/adapters/manifest_loader.py:125-163,305-339`, `ao_kernel/adapters/__init__.py:8-12`). Bundled sample `codex-stub` kullanıyor → `load_bundled()` gerekli. | **Adapter snapshot doğru pattern**: `reg = AdapterRegistry(); reg.load_bundled(); reg.load_workspace(project_root); snapshot = {adapter_id: reg.get(adapter_id) for adapter_id in reg.list_adapters()}`. §2.1 `pure_execution_context` GIRMEDEN önce çağrılır; context içinde snapshot'tan okunur. |
| **2 (warning)** | **Üst özet tablosu satır 18 `check_policy` için `workspace=None`** diyor; ana §2.3 (satır 264) `workspace=<sentinel>` diyor. `workspace=None` kullanılırsa `check_policy` ambient `resolve_ws()` yoluna girer (`governance.py:49-52`) ve v2'nin düzelttiği purity ambiguity geri gelir. | Üst özet tablosu güncellendi: `workspace=<sentinel>` (explicit). v2 nin purity düzeltmesi korunur. |
| **3 (warning)** | **`_policy_override_context` call vs declaration mismatch**: satır 264 iki argüman (`scenario.target_policy_name, active_policy_map[name]`), satır 330-338 tek argüman (`Mapping[str, Mapping[str, Any]]`). | Call site'i declaration'a uydur: `_policy_override_context(policy_overrides=active_policy_map)` — tek Mapping argüman. Tüm call örnekleri aynı imzayı kullanır. |
| **4 (warning)** | **Public facade alias `ao_kernel/executor/__init__.py:29-33,59-71` → `emit_event` re-export**. Sentinel listesi sadece 3 yol (`evidence_emitter`, `executor.executor`, `multi_step_driver`). "Pre-imported aliases covered" iddiası eksik. | **4. emit_event sentinel eklendi**: `ao_kernel.executor.emit_event` (facade alias). PATCHED_SENTINELS 23+ entry. |
| **5 (warning)** | **`project_root` docstring çelişki**: "NOT dereferenced for policy reads" deniyor, ama `baseline_source=WORKSPACE_OVERRIDE` için `<project_root>/.ao/policies/` okunuyor (`config.py:118-137` `load_with_override` default). | §2.3 docstring netleştirildi: `project_root` (a) adapter manifest discovery; (b) `baseline_source=WORKSPACE_OVERRIDE` durumunda `load_with_override` tarafından workspace policy override dir'i olarak okunur; (c) `EXPLICIT` durumunda dereferenced DEĞİL — baseline tamamen `baseline_overrides` arg'ından. |

**Ek notes (Codex onayları, unchanged)**:
- `check_policy` quasi-pure düzeltmesi doğru (`governance.py:40-52`)
- `build_sandbox` quasi-pure düzeltmesi doğru (`policy_enforcer.py:146-149`)
- `load_with_override` monkey-patch uygulanabilir (function scope import, `governance.py:40`)
- `_KINDS == 27` ground truth (`evidence_emitter.py:46-83`)
- Metrics görünmezliği doğru (`derivation.py:95-118,306-367`)
- JSON-only packaging uyumlu (`pyproject.toml:26,90-91`)
- Canonical policy hash `artifacts.py:66-74` aligned

---

## v2 absorb summary (Codex CNS-20260418-038 iter-1 REVISE — 6+ bulgu, SÜRÜYOR)

**iter-1 verdict**: REVISE — plan draft structurally too ambitious in some axes and too loose in others. 6 bulgu + multiple sub-notes.

| # | v1 bulgu | v2 fix |
|---|---|---|
| **1** | **Tek `policy_name` modeli ScenarioSet için kırık**: Global `policy_name="policy_worktree_profile.v1.json"` imzası aynı koşuda `executor_primitive` + `governance_policy` scenario'larını destekleyemez. Bundled 3 sample'da zaten 2 farklı policy var (worktree_profile + autonomy). | **Per-scenario `target_policy_name`**: scenario içinde field olarak taşınır. Public API `simulate_policy_change(proposed_policies: Mapping[str, Mapping[str, Any]])` — dict of `policy_name → proposed_dict`. Multi-policy batch zorunlu v1 (Codex Q4 karar: "v2 değil, temel doğruluk"). |
| **2** | **`workspace_root` semantiği ambiguity**: `config.workspace_root()` → `.ao/`, `workspace.project_root()` → proje kökü, `AdapterRegistry.load_workspace()` proje kökünden `.ao/adapters`, `governance.check_policy(workspace=ws)` `.ao/policies`. Tek `workspace_root` argümanıyla hepsi ikna edilmez. | **İki ayrı argüman**: `project_root: Path` (manifest loader için — adapter discovery) + `policy_override_map: Mapping[str, Mapping]` (proposed policies in-memory; disk bypass). `check_policy` için `workspace=<sentinel>` + explicit `policy_dict` injection (`_policy_override_context` monkey-patch `load_with_override`). |
| **3** | **No-side-effects guard yetersiz**: Pre-imported `emit_event` alias'ları (`executor.py`, `multi_step_driver.py`) monkey-patch kapsamı dışı; network erişimi kapsamı dışı (`socket.socket` binding/connect); `tempfile.*`, `Path.write_text/mkdir`, `os.replace`, `__pycache__`; `importlib.resources.as_file()` temp extraction. | **`_purity.py` genişlet — 15+ sentinel**: direct module imports (3 emit_event alias), subprocess, filesystem writes, os.replace/rename, tempfile family, socket bind/connect, `importlib.resources.as_file`. Her birine specific `PolicySimSideEffectError(sentinel_name, context)` raise. Re-entrancy hardened. |
| **4** | **Purity table factual yanlışlar**: (a) `build_sandbox` tam pure DEĞİL — `Path(prefix).resolve()` host FS symlink read (`policy_enforcer.py:146`). (b) `check_policy` loader dışında `resolve_ws()` cwd discovery yapar (`governance.py:40-52`); "workspace=None bundled'a düşer" cümlesi yanlış. | `build_sandbox` → "**quasi-pure** (host FS symlink read via `Path.resolve`)". `check_policy` → "**quasi-pure** (ambient cwd discovery when `workspace=None`)". §4 table düzeltildi; §2.1 disclaimer netleşti. |
| **5** | **YAML v1 için kötü uyum**: `pyproject.toml` base dep'te PyYAML yok; `package-data` sadece `**/*.json` ship ediyor → bundled YAML senaryolar wheel/sdist'e GİRMEZ. | **JSON-only v1**. YAML optional extra v2+ veya post-B4. Scenario schema + bundled samples `.json`. Q1 kesin karar. |
| **6** | **`_KINDS == 27` claim + `metrics/derivation.py` referansı**: Codex cwd'si `stupefied-swartz` worktree idi — pre-B5 state (`_KINDS = 18`). Gerçek main `75c114f` @ `_KINDS = 27`. | Plan acceptance `_KINDS == 27` doğru; dayanağı `ao_kernel/executor/evidence_emitter.py:46` at HEAD `75c114f`. §5 Regression'e explicit path ekle: "Metrics derivation (`ao_kernel/metrics/derivation.py` on main@75c114f) scans only `events.jsonl` kinds emitted by runtime." |

**Ek notlar (Codex sub-findings)**:
- **N1**: Structural validator "mirror of key-reads" yeterli değil → primitive'lerin tükettiği projection ortak helper'da merkezileştir. v2: `_policy_shape_registry.py` (read-only introspection mirror).
- **N2**: `baseline_policy=None` ambiguity → explicit enum: `bundled | workspace_override | explicit`. v2: `BaselineSource` enum.
- **N3**: Policy hash canonical kontrat: `sort_keys=True, ensure_ascii=False, separators=(",", ":")` → UTF-8 bytes SHA-256. `artifacts.py:66` ile hizalan. v2: `_canonical_policy_hash()` helper.
- **N4**: `DiffReport.asdict` güvenli değil: `Path`, `frozenset`, regex, manifest `source_path` normalize et. v2: custom `to_dict()` method.

---

## 5 Q v2 kararları (Codex iter-1 REVISE)

| Q | v1 tentative | v2 kararı | Gerekçe |
|---|---|---|---|
| Q1 YAML vs JSON | YAML with JSON fallback | **JSON-only v1** | Paketleme zorunluluğu (`package-data` JSON-only), base dep simplification |
| Q2 validate_command | opt-in flag | **default-off flag**, `host_fs_fingerprint` + `host_fs_dependent=true` | Deterministic baseline + explicit opt-in signal |
| Q3 proposed policy format | full replacement v1 | **full replacement v1**; RFC 7396 merge patch → v2 | Simpler semantics; operator UX is nice-to-have |
| Q4 multi-policy batch | v2 | **v1 zorunlu** (per-scenario `target_policy_name`) | Temel doğruluk — ScenarioSet aslında multi-policy (bundled 3 sample 2 farklı policy) |
| Q5 CLI placement | `ao-kernel policy-sim run` | **`ao-kernel policy-sim run`** (noun-group pattern) | Matches `ao-kernel metrics {export,debug-query}`, `ao-kernel evidence` precedent |

---

## CNS-031 prior concern (pre-B4 plan-time, iter-1)

"No-side-effects kontratı şüpheli". Plan'ın §2.1 + §4 (primitive pure/stateful classification table) + §5 (side-effect assertion tests) + §6 (R1/R2/R3 risks) doğrudan cevaplar. No evidence emits from `ao_kernel/policy_sim/` — the harness NEVER calls `emit_event` nor `create_worktree` nor any adapter transport. **v2 purity guard 15+ sentinel'e genişledi** (iter-1 bulgu 3 absorb).

## Scope independence (master plan §3)

B4 has no deps on B3 (cost-aware routing) nor B1 (coordination). B4 is one of the two "independent" tracks (alongside B5 — now merged). Consumes read-only: `governance.check_policy`, `load_with_override`, executor policy_enforcer primitives, adapter manifest loader.

---

## 1. Amaç

Operatöre **dry-run policy change** değerlendirmesi sunmak: "workspace override olarak bu policy patch'lerini uygulasam, fixture senaryolarımın kaçı deny → allow, kaçı allow → deny olur?" Zero workspace mutation, zero subprocess spawn, zero evidence emit, zero network. Çıktı: structured `DiffReport` (JSON) + operator-friendly summary. Public package + CLI subcommand `ao-kernel policy-sim run`.

**Dar kapsam**:
- Hedef policies: `policy_worktree_profile.v1.json`, `policy_autonomy.v1.json`, diğer `check_policy`-backed policy'ler. **Per-scenario `target_policy_name`** (v2 absorb bulgu 1).
- Re-evaluation grain: **mid-depth** — Q4 CNS-027 cevabı "full Executor.run_step dry-run" reddedilir (adapter mock gerektirir, out-of-scope). Sadece: `governance.check_policy` replay + executor policy_enforcer 4 saf primitive (`build_sandbox`, `resolve_allowed_secrets`, `check_http_header_exposure`, opsiyonel `validate_command`).
- Output contract: `SimulationResult` per-scenario + `DiffReport` aggregate (baseline vs proposed policy set).

### Kapsam özeti

| Katman | Modül | Satır (est.) |
|---|---|---|
| Public package | `ao_kernel/policy_sim/__init__.py` | ~50 |
| Scenario model | `ao_kernel/policy_sim/scenario.py` (+ `target_policy_name`) | ~200 |
| Purity contract guard | `ao_kernel/policy_sim/_purity.py` (15+ sentinel) | ~180 |
| Policy shape registry (N1) | `ao_kernel/policy_sim/_policy_shape_registry.py` | ~120 |
| Pure simulator core | `ao_kernel/policy_sim/simulator.py` (proposed_policies batch) | ~320 |
| Diff engine | `ao_kernel/policy_sim/diff.py` (normalized serialize) | ~190 |
| Proposed-policy loader | `ao_kernel/policy_sim/loader.py` (multi-policy + BaselineSource enum) | ~170 |
| Reporter (JSON + text) | `ao_kernel/policy_sim/report.py` | ~150 |
| Typed errors | `ao_kernel/policy_sim/errors.py` (7 types — +`TargetPolicyNotFoundError`) | ~90 |
| CLI handler | `ao_kernel/_internal/policy_sim/cli_handlers.py` + `cli.py` delta | ~170 + ~40 delta |
| Scenario schema | `ao_kernel/defaults/schemas/policy-sim-scenario.schema.v1.json` | ~240 |
| Bundled sample scenarios | `ao_kernel/defaults/policies/policy_sim_scenarios/` (3 **JSON** files) | ~200 |
| Tests | ~50 test, 7 dosya | ~780 |
| Docs | `docs/POLICY-SIM.md` (new) + CHANGELOG delta | ~290 |
| **Toplam** | 1 public package + 1 internal CLI + 1 schema + 3 bundled scenarios + ~50 test + docs | **~2880 satır** |

- Yeni evidence kind: **0** (policy_sim emit etmez — bkz. §2.1, §4)
- Yeni adapter capability: 0
- Yeni core dep: 0 (**v2 karar: JSON-only; PyYAML gerekmez**)
- Yeni error type: **7** (+`TargetPolicyNotFoundError` scenario referansı bilinmeyen policy'ye)

**Runtime LOC**: ~1360 (master plan ~1200 hedefinden ~13% ↑; purity genişletme + multi-policy batch gereksinimi).

---

## 2. Scope İçi

### 2.1 Purity contract + "no-side-effects" sözleşmesi (v2 geniş)

**CNS-031 iter-1 endişesi doğrudan cevaplanır.** `ao_kernel/policy_sim/_purity.py` bir context manager + assertion-based test harness sunar. **v2**: 15+ sentinel monkey-patched.

```python
PATCHED_SENTINELS: Mapping[str, Callable] = {
    # Direct evidence emission (4 import path — pre-imported aliases + public facade)
    "ao_kernel.executor.evidence_emitter.emit_event": _raise_evt,
    "ao_kernel.executor.executor.emit_event": _raise_evt,          # pre-imported alias
    "ao_kernel.executor.multi_step_driver.emit_event": _raise_evt, # pre-imported alias
    "ao_kernel.executor.emit_event": _raise_evt,                   # v3 — public facade re-export (__init__.py:29-33,59-71)
    # Worktree creation
    "ao_kernel.executor.worktree_builder.create_worktree": _raise_wt,
    # Subprocess (re-entrant safe)
    "subprocess.Popen.__init__": _raise_sp,
    "subprocess.run": _raise_sp,
    "subprocess.call": _raise_sp,
    "subprocess.check_output": _raise_sp,
    # Filesystem writes
    "pathlib.Path.write_text": _raise_fs,
    "pathlib.Path.write_bytes": _raise_fs,
    "pathlib.Path.mkdir": _raise_fs,
    "pathlib.Path.touch": _raise_fs,
    "os.replace": _raise_fs,
    "os.rename": _raise_fs,
    "os.remove": _raise_fs,
    "os.unlink": _raise_fs,
    # Temp file creation (importlib.resources.as_file uses mkstemp internally)
    "tempfile.NamedTemporaryFile": _raise_tf,
    "tempfile.mkstemp": _raise_tf,
    "tempfile.TemporaryFile": _raise_tf,
    "tempfile.mkdtemp": _raise_tf,
    # Network
    "socket.socket.connect": _raise_net,
    "socket.socket.bind": _raise_net,
    # Importlib resource extraction (triggers tempfile extraction for bundled)
    "importlib.resources.as_file": _raise_extract,
}


@contextmanager
def pure_execution_context() -> Iterator[None]:
    """Monkeypatches all sentinels in PATCHED_SENTINELS. Yields; on exit
    restores originals via finally. Re-entrancy: nested entry raises
    PolicySimReentrantError (prevents partial restore).
    """
```

Runtime kontratı: `simulate_policy_change()` içinde yapılan **her şey** bu context altında icra edilir. Herhangi bir geri çağrım yanlışlıkla bu 24 sentinel'den birine dokunursa fail-closed `PolicySimSideEffectError(sentinel_name, context)` raise eder. Test harness'ı da aynı context'i kullanarak **side-effect regression testleri** tanımlar (§5).

**v2 nota — importlib.resources limit** (v3 iter-2 blocker absorb — doğru API): `manifest_loader.load_bundled()` production'da `importlib.resources.as_file` kullanır — bu import-time temp extraction tetikler. Simulator adapter manifesto resolution'u için **pre-resolved registry snapshot**'a çalışır. **`pure_execution_context` GIRMEDEN önce** şu pattern:

```python
from ao_kernel.adapters import AdapterRegistry

reg = AdapterRegistry()
reg.load_bundled()                     # codex-stub gibi bundled adapter'lar
reg.load_workspace(project_root)        # workspace override'lar (<project_root>/.ao/adapters/)
snapshot = {
    adapter_id: reg.get(adapter_id)
    for adapter_id in reg.list_adapters()
}
# Alternatif: reg.supports_capabilities() / reg.missing_capabilities()
# doğrudan kullan (contextte gerekirse ek helper tanımla).
```

Context içinde `snapshot[adapter_id]` ile okur; `reg.load_*()` tekrar çağrılmaz. Gerçek API surface: `load_bundled`, `load_workspace`, `get`, `list_adapters`, `missing_capabilities`, `supports_capabilities` (`ao_kernel/adapters/manifest_loader.py:125-163, 305-339`; `ao_kernel/adapters/__init__.py:8-12`). `capabilities_snapshot()` diye bir metod YOK — v2'de yanlışlıkla kullanılmıştı.

**Pure function classification** (v2 düzeltilmiş — iter-1 bulgu 4):

| Primitive | Module | Pure? | Side effect (if any) | B4 reuses? |
|---|---|---|---|---|
| `governance.check_policy` | `ao_kernel/governance.py:29` | **Quasi-pure** (v2 fix) | `resolve_ws()` ambient cwd discovery when `workspace=None` (`governance.py:40-52`); file reads via `load_with_override`; no write, no emit | **YES** with explicit `workspace` arg + `_policy_override_context` |
| `build_sandbox` | `executor/policy_enforcer.py:86` | **Quasi-pure** (v2 fix) | `Path(prefix).resolve()` host FS symlink read (`policy_enforcer.py:146`); in-memory dict transforms + regex compile; no writes | **YES** (symlink read documented limit) |
| `resolve_allowed_secrets` | `executor/policy_enforcer.py:302` | **Pure** (dict filter) | None | **YES** |
| `check_http_header_exposure` | `executor/policy_enforcer.py:332` | **Pure** (set membership check) | None | **YES** |
| `validate_command` | `executor/policy_enforcer.py:194` | **Quasi-pure** (filesystem reads via `shutil.which` + `os.path.realpath`) | No writes, but reads host `$PATH` contents | **OPTIONAL** (Q2 — gated by `--enable-host-fs-probes`) |
| `validate_cwd` | `executor/policy_enforcer.py:268` | **Quasi-pure** (Path.resolve = symlink read) | No writes; reads filesystem symlinks | **NEVER** (excluded from v1 simulator) |
| `emit_event` | `executor/evidence_emitter.py:115` | **Stateful** | Appends to `events.jsonl`, fsync, file_lock | **NEVER** (sentinel-guarded — 3 import paths) |
| `create_worktree` | `executor/worktree_builder.py:52` | **Stateful** | Spawns `git worktree add`, chmod, mkdir | **NEVER** (sentinel-guarded) |
| `Executor.run_step` | `executor/executor.py:112` | **Stateful** | Above + `update_run` CAS + adapter invoke | **NEVER** |
| `load_with_override` | `config.py:118` | **Pure** (file read only) | Reads JSON | **YES** (via `_policy_override_context` monkey-patch) |

**Codex fact-check notu**: `check_policy` purity label v1'de "Pure" idi; v2 düzeltildi — `workspace=None` verildiğinde `resolve_ws()` cwd-walk yapar (`governance.py:40-52`). Simulator her zaman explicit workspace sağlar; `_policy_override_context` disk-bypass içindir. `build_sandbox` v1'de "Pure" idi; v2 düzeltildi — `Path(prefix).resolve()` symlink follow eder (`policy_enforcer.py:146`).

### 2.2 Scenario model (`scenario.py`) — v2 per-scenario target_policy_name

**v2 bulgu 1 absorb**: Scenario içinde `target_policy_name` field.

```json
{
  "scenario_id": "adapter_http_with_secret",
  "description": "HTTP adapter binds auth_secret_id_ref; expects http_header mode allowed",
  "kind": "executor_primitive",
  "target_policy_name": "policy_worktree_profile.v1.json",
  "inputs": {
    "adapter_manifest_ref": "codex-stub",
    "parent_env": {
      "PATH": "/usr/bin:/usr/local/bin",
      "ANTHROPIC_API_KEY": "sk-test-redacted"
    },
    "requested_command": null,
    "requested_cwd": null
  },
  "expected_baseline": {
    "violations_expected": [],
    "decision_expected": "allow"
  }
}
```

Scenarios cover three shapes:
1. **executor_primitive** → invokes `build_sandbox` + `resolve_allowed_secrets` + `check_http_header_exposure` against target policy (must be `policy_worktree_profile.v1.json`).
2. **governance_policy** → invokes `governance.check_policy(target_policy_name, action)` for non-worktree policies (tool_calling, autonomy, etc.).
3. **combined** → both; aggregates violations. `target_policy_name` identifies which policy per-primitive; scenario model ister combined kind için `target_policy_names: list[str]` tutar.

`ScenarioLoader` — validates against `policy-sim-scenario.schema.v1.json`; deny unknown fields. `ScenarioSet` — list of scenarios with optional metadata (name, version, description).

**`TargetPolicyNotFoundError`** (new): scenario references a `target_policy_name` that's not in `proposed_policies` OR bundled defaults.

### 2.3 Simulator core (`simulator.py`) — v2 multi-policy API

**v2 bulgu 1 + 2 absorb**: `proposed_policies: Mapping[str, Mapping]` + `project_root` + `policy_override_map`.

**Public entry point**:

```python
def simulate_policy_change(
    *,
    project_root: Path,  # v2 fix bulgu 2 — manifest loader for adapter discovery
    scenarios: ScenarioSet,
    proposed_policies: Mapping[str, Mapping[str, Any]],  # v2 fix bulgu 1 — batch
    baseline_source: BaselineSource = BaselineSource.BUNDLED,  # v2 fix N2 — enum
    baseline_overrides: Mapping[str, Mapping[str, Any]] | None = None,
    include_host_fs_probes: bool = False,  # gates validate_command (Q2)
) -> DiffReport:
    """Evaluate each scenario against baseline policy set AND proposed
    policy set under pure_execution_context. Returns structured
    DiffReport.

    Args:
        project_root: Project directory (containing .ao/). Used for:
          (a) adapter manifest discovery via AdapterRegistry snapshot
              taken BEFORE pure_execution_context entry;
          (b) baseline_source=WORKSPACE_OVERRIDE: load_with_override
              reads <project_root>/.ao/policies/<name> for baseline
              assembly (disk read under purity guard for read-only);
          (c) baseline_source=EXPLICIT: NOT dereferenced — baseline is
              fully provided via baseline_overrides arg (disk bypass).
          (d) baseline_source=BUNDLED: NOT dereferenced — bundled
              defaults from ao_kernel/defaults/policies/ used directly.
        proposed_policies: {policy_name: proposed_policy_dict, ...}
            — MULTI-POLICY batch. Each scenario's target_policy_name
            MUST be a key here OR in baseline_overrides (see below).
            Applied in-memory via _policy_override_context; never
            written to disk.
        baseline_source: BUNDLED | WORKSPACE_OVERRIDE | EXPLICIT.
            Determines how the baseline policy set is assembled:
              - BUNDLED: load from ao_kernel/defaults/policies/
              - WORKSPACE_OVERRIDE: load from <project_root>/.ao/policies/
                  (triggers load_with_override disk read under purity
                   guard for read-only)
              - EXPLICIT: use baseline_overrides arg directly (disk-bypass)
        baseline_overrides: only honored when
            baseline_source=EXPLICIT. Same shape as proposed_policies.
        include_host_fs_probes: If True, invoke validate_command for
            scenarios with requested_command. Report adds
            host_fs_fingerprint + host_fs_dependent=true.

    Raises:
        PolicySimSideEffectError — if any reused primitive attempts
            workspace writes, evidence emits, or subprocess spawns.
        ScenarioValidationError — scenario fails schema or references
            missing adapter_id.
        TargetPolicyNotFoundError — scenario target_policy_name not in
            proposed_policies nor baseline_overrides nor bundled.
        ProposedPolicyInvalidError — proposed_policy fails structural
            shape checks (§2.5).
    """
```

**Execution model** (per scenario):
1. Snapshot baseline policy set (baseline_source-driven: bundled / workspace / explicit).
2. Under `pure_execution_context`: evaluate scenario against **baseline[scenario.target_policy_name]** → `SimulationResult(scenario_id, primitive_results, decision)`.
3. Swap to **proposed[scenario.target_policy_name]** (in-memory only; no disk write).
4. Re-evaluate same scenario → second `SimulationResult`.
5. Diff → `ScenarioDelta(baseline, proposed, transition)` where transition ∈ {allow→allow, allow→deny, deny→allow, deny→deny, error}.

**`kind: executor_primitive` execution** (target MUST be policy_worktree_profile):
- `resolved_secrets, sv = resolve_allowed_secrets(policy, parent_env)`
- `sandbox, bv = build_sandbox(policy=policy, worktree_root=<sentinel_path>, resolved_secrets=resolved_secrets, parent_env=parent_env)`
- `hv = check_http_header_exposure(policy=policy, adapter_manifest_invocation=<from snapshot>)`
- Opsiyonel, only if `include_host_fs_probes=True` and scenario provides `requested_command`: `vc = validate_command(...)`.
- Aggregate `violations = sv + bv + hv + (vc or [])`.
- Decision = "deny" if violations else "allow".

**`kind: governance_policy` execution** (any target):
- `result = check_policy(scenario.target_policy_name, action, workspace=<sentinel>)` with `_policy_override_context(policy_overrides=active_policy_map)` wrapping. Monkey-patches `load_with_override` so the loader returns in-memory dict for any policy_name in `active_policy_map`; other names fall through to disk. **Call site imzası declaration ile aynı**: tek `policy_overrides: Mapping[str, Mapping[str, Any]]` argüman.

**`kind: combined` execution**: union of above with `target_policy_names: list[str]`; scenario constraint — must contain at least one `policy_worktree_profile` for executor primitives + one `check_policy`-backed policy.

**No worktree_root on disk**: simulator uses a sentinel `PosixPath("/__policy_sim_ephemeral__")` passed to `build_sandbox`. `build_sandbox` only stores this in `SandboxedEnvironment.cwd` — never dereferences. `validate_cwd` excluded (Q2).

### 2.4 Diff engine (`diff.py`) — v2 normalized serialize

**v2 N4 absorb**: custom `to_dict()` method handles Path, frozenset, regex, manifest source_path.

```python
@dataclass(frozen=True)
class ScenarioDelta:
    scenario_id: str
    target_policy_name: str  # v2 — per-scenario axis
    baseline: SimulationResult
    proposed: SimulationResult
    transition: Literal["allow→allow", "allow→deny", "deny→allow", "deny→deny", "error"]
    violation_diff: ViolationDiff  # added/removed violation kinds
    notable: bool  # True if transition != identity

@dataclass(frozen=True)
class DiffReport:
    baseline_policy_hashes: Mapping[str, str]  # {policy_name: sha256}
    proposed_policy_hashes: Mapping[str, str]  # {policy_name: sha256}
    scenarios_evaluated: int
    transitions: dict[Literal[...], int]  # counts per transition kind
    transitions_by_policy: Mapping[str, dict[Literal[...], int]]  # per-policy breakdown (v2)
    deltas: tuple[ScenarioDelta, ...]
    notable_deltas: tuple[ScenarioDelta, ...]
    emitted_at: str  # ISO-8601
    host_fs_dependent: bool  # v2 — flag set if validate_command ran
    host_fs_fingerprint: str | None  # v2 — sha256 of probed $PATH entries

    def to_dict(self) -> dict[str, Any]:
        """v2 custom serializer — handles Path→str, frozenset→sorted list,
        regex→pattern string, manifest source_path→relative path.
        Canonical JSON output: sort_keys=True, ensure_ascii=False,
        separators=(",",":").
        """
```

**v2 N3 canonical hash**: `_canonical_policy_hash(policy_dict) -> str` returns sha256 hex of `json.dumps(policy, sort_keys=True, ensure_ascii=False, separators=(",",":")).encode("utf-8")`. Aligns with `artifacts.py:66` capability artifact digest pattern.

### 2.5 Proposed-policy loader (`loader.py`) — v2 multi-policy

Two shapes accepted per policy:
1. **Full replacement**: proposed_policy is a complete policy dict.
2. Patch/diff form → **v2 scope dışı** (Q3 deferred).

**v1 kesin karar: full replacement only** (simpler semantics).

**v2 bulgu 1**: `proposed_policies: Mapping[str, Mapping]` supports multi-policy batch.

**Structural validation per policy_name** (no authoritative schema file for `policy_worktree_profile.v1.json`):
- **v2 N1 absorb**: Uses `_policy_shape_registry.py` — centralized introspection mirror of primitive key-reads. Each primitive declares its `required_keys` and `consumed_shape`; validator reads registry instead of hardcoded per-policy rules.
- Fail-closed `ProposedPolicyInvalidError` with structured violation records.
- Registry entries:
  - `policy_worktree_profile`: mirrors `build_sandbox` + `resolve_allowed_secrets` + `check_http_header_exposure` reads.
  - `policy_autonomy`, `policy_tool_calling`, etc.: mirrors `check_policy`'s branching (intents, defaults.mode, allowed_tools, etc.).

**Override context manager** (for `governance.check_policy` injection):

```python
@contextmanager
def _policy_override_context(
    policy_overrides: Mapping[str, Mapping[str, Any]],
) -> Iterator[None]:
    """v2 — multi-policy batch. Monkey-patch ao_kernel.config.load_with_override
    so that when check_policy queries any name in policy_overrides, it gets
    the dict instead of filesystem. ContextVar-based; thread-local; restored
    on exit. Does NOT touch disk.

    Other policy names fall through to original load_with_override (reads
    from disk) — so unrelated policies still work.
    """
```

Test: assert `_policy_override_context` never triggers `Path.write_text` / `Path.mkdir` / `os.replace` (purity sentinel guard).

### 2.6 Reporter (`report.py`)

Two formats:
1. **JSON** (canonical `DiffReport.to_dict()` → `json.dumps(..., sort_keys=True, ensure_ascii=False, separators=(",",":")))`.
2. **Text** (operator-friendly; table of transitions + per-policy breakdown + notable delta bullets):

```
Policy Simulation Report
========================
Policies under test: policy_worktree_profile.v1.json, policy_autonomy.v1.json
  baseline_source: BUNDLED
  proposed overrides: 2 policies
  host_fs_dependent: false

Scenarios evaluated: 7

Transitions (all):
  allow→allow: 4
  deny→deny:   1
  allow→deny:  1  ⚠ tightening
  deny→allow:  1  ⚠ loosening
  error:       0

Transitions per policy:
  policy_worktree_profile.v1.json: 3 scenarios (1 allow→allow, 1 allow→deny, 1 deny→deny)
  policy_autonomy.v1.json:         4 scenarios (3 allow→allow, 1 deny→allow)

Notable deltas:
  [allow→deny] adapter_http_with_secret (policy_worktree_profile): proposed.secrets.exposure_modes removed 'http_header'
  [deny→allow] command_out_of_path (policy_worktree_profile): proposed.command_allowlist.prefixes added '/tmp/evil/'
```

### 2.7 Errors (`errors.py`) — 7 types (v2 +1)

```
PolicySimError (base)
├── PolicySimSideEffectError       # purity contract violated at runtime
├── PolicySimReentrantError         # v2 — nested pure_execution_context
├── ScenarioValidationError         # scenario schema fail
├── ScenarioAdapterMissingError     # scenario references unknown adapter_id
├── TargetPolicyNotFoundError       # v2 — target_policy_name not found
├── ProposedPolicyInvalidError      # proposed_policy fails structural shape
├── SimulationAbortedError          # aggregate wrapper for per-scenario errors
└── ReportSerializationError        # JSON encode failure on Decimal/Path
```

### 2.8 CLI — `ao-kernel policy-sim run`

**v2 Q5 karar**: noun-group pattern (matches `ao-kernel metrics`, `ao-kernel evidence`).

```
ao-kernel policy-sim run \
  --scenarios <path-to-json-file-or-dir> \
  --proposed-policies <path-to-json-dir>  # JSON files named <policy_name>.json \
  [--baseline-source bundled|workspace|explicit] \
  [--baseline-overrides <path-to-json-dir>] \
  [--format json|text] \
  [--output <path>] \
  [--enable-host-fs-probes]
```

Exit codes:
- `0` — success, no tightening transitions (all allow→allow or neutral)
- `1` — user error (bad scenario file, missing adapter, proposed_policy invalid shape, target_policy_name not found)
- `2` — internal (simulation aborted, side-effect contract violation, re-entrancy)
- `3` — success-with-warning: at least one allow→deny transition detected (policy tightening; operator should review)

`--enable-host-fs-probes` gates `validate_command` invocation (Q2 — default off keeps simulator deterministic across hosts).

### 2.9 Scenario schema (`policy-sim-scenario.schema.v1.json`)

JSON Schema draft-2020-12; `additionalProperties: false` at all levels. Validates against `_SCENARIO_KIND_ENUM = {"executor_primitive", "governance_policy", "combined"}`. **Required field `target_policy_name`** (executor_primitive + governance_policy) OR `target_policy_names: list[str]` (combined). Bundled sample scenarios validated at load time.

### 2.10 Bundled sample scenarios (`defaults/policies/policy_sim_scenarios/`)

**v2 Q1 karar**: JSON-only.

Three reference scenarios (cover three `kind` values):
1. `adapter_http_with_secret.v1.json` — `executor_primitive` + `target_policy_name: policy_worktree_profile.v1.json` + expected allow.
2. `path_poisoned_python.v1.json` — `executor_primitive` + same target + expected deny (`command_path_outside_policy`).
3. `autonomy_unknown_intent.v1.json` — `governance_policy` + `target_policy_name: policy_autonomy.v1.json` + expected deny (AUTONOMY_UNKNOWN_INTENT).

These act as **regression fixtures**: any change to `policy_worktree_profile.v1.json` or `policy_autonomy.v1.json` or executor primitives is caught via CI `test_policy_sim_bundled_fixtures`.

### 2.11 Policy shape registry (`_policy_shape_registry.py`) — v2 N1 absorb

Centralized introspection mirror. Each primitive declares:

```python
@dataclass(frozen=True)
class PolicyShapeEntry:
    primitive_name: str
    policy_name_target: str  # e.g., "policy_worktree_profile.v1.json"
    required_top_keys: frozenset[str]
    consumed_sub_paths: Sequence[tuple[str, ...]]  # e.g., (("env_allowlist", "allowed_keys"),)
    type_contracts: Mapping[tuple[str, ...], type]
```

`POLICY_SHAPE_REGISTRY: Mapping[str, list[PolicyShapeEntry]]` — keyed by `policy_name`. Loader validates proposed_policy by walking sub-paths + type contracts. Centralization avoids per-primitive duplication in `loader.py`.

---

## 3. Write Order (5-commit DAG)

1. **C1**: `errors.py` (7 types) + `_purity.py` (15+ sentinel) + `_policy_shape_registry.py` + bundled scenario schema + 12 purity tests (~470 LOC)
2. **C2**: `scenario.py` (+ `target_policy_name`) + scenario schema validation tests + 3 bundled JSON sample scenarios + 10 scenario tests (~530 LOC)
3. **C3**: `simulator.py` (multi-policy batch) + `diff.py` (normalized serialize) + `loader.py` (multi-policy context) + side-effect regression tests + core simulation tests (~720 LOC)
4. **C4**: `report.py` + CLI handler + `cli.py` delta + 10 CLI tests (~480 LOC)
5. **C5**: `docs/POLICY-SIM.md` + `__init__.py` public surface + CHANGELOG delta + 4 integration tests (~530 LOC)

**Dependency invariant**: no commit breaks existing B0/B1/B2/B5/B6 tests. `test_executor_policy_enforcer.py` specifically must stay green (B4 is read-only consumer of its primitives).

---

## 4. Design trade-offs

### 4.1 Mid-depth vs full-depth simulation (CNS-027 Q4)

| Kriter | Mid-depth (seçilen) | Full Executor.run_step dry-run |
|---|---|---|
| Adapter mock needed | **No** (read manifests only) | Yes (mock CLI/HTTP transport) |
| Worktree required | **No** (policy_sim runs in-memory) | Yes (temp worktree + cleanup) |
| Evidence emit | **No** (purity contract) | Must be suppressed (fragile) |
| Side-effect risk | **Near-zero** (purity guard, 15+ sentinel) | Moderate (cleanup failure paths) |
| LOC estimate | ~1360 | ~1800+ |
| Fidelity | Policy-decision grade | Full-execution grade |
| Use case fit | "will my policy tighten/loosen?" | "will my run complete?" |

**Seçim**: Mid-depth. Operator soru surface'i policy-decision grade — adapter execution path mocking policy-sim scope creep. Full-depth gerekirse B7 (benchmark suite) harness'ında ayrıca yapılabilir.

### 4.2 Pure evaluator vs actual policy loader (user prompt item 3c)

| Kriter | Actual `governance.check_policy` (seçilen) | Pure re-implementation |
|---|---|---|
| Semantic drift risk | **Zero** (same code path as production) | High (must track every `check_policy` change) |
| Purity enforcement | Via `_purity.py` monkey-patch (15+ sentinel) | Built-in |
| `load_with_override` bypass | Via `_policy_override_context` (multi-policy) | Not needed |
| LOC | ~30 (context manager) | ~200+ duplication |
| Test burden | Reuses existing governance tests | New parallel test matrix |

**Seçim**: Reuse actual `check_policy`. Pure re-implementation = two sources of truth = inevitable drift. Monkey-patching `load_with_override` is surgical; isolated to simulator context.

### 4.3 `validate_command` inclusion (Q2 Codex)

`validate_command` is quasi-pure (reads `$PATH`, resolves symlinks via `os.path.realpath`). Including it:
- **Pro**: full policy_enforcer parity → catches command-path-poisoning reports.
- **Con**: results depend on host filesystem (CI vs developer laptop). Non-deterministic across environments.

**Default: excluded**. Opt-in via `--enable-host-fs-probes`. When enabled, simulator report includes a `host_fs_fingerprint` field (hash of probed paths) + `host_fs_dependent=true` so operators can see results are host-specific.

### 4.4 Multi-policy batch (v2 Q4 absorb)

v1 mandatory: ScenarioSet realistically hits multiple policies (bundled 3 sample covers 2 policies; operator PR audit use case routinely touches 3+). Scenario-level `target_policy_name` + batch input keeps combinatorics manageable:
- Per-scenario: 2 evaluations (baseline + proposed) — linear
- Scenarios × policies: each scenario references 1 policy (2 for `combined` kind) — bounded

**Alternative (rejected)**: single-policy v1 + `--proposed-policies` glob v2. Adds re-run ops + parallel reporter logic for per-policy reports. Cleaner in v1 to batch.

---

## 5. Acceptance Checklist

### Purity contract (CNS-031 central + iter-1 bulgu 3)
- [ ] `pure_execution_context` monkey-patches 22+ sentinels; restores on exit
- [ ] Test: calling `emit_event` via each of 3 import paths (evidence_emitter, executor, multi_step_driver) inside simulate → `PolicySimSideEffectError` with sentinel_name
- [ ] Test: calling `create_worktree` → error
- [ ] Test: `subprocess.Popen`, `subprocess.run`, `subprocess.call`, `subprocess.check_output` → error
- [ ] Test: `Path.write_text`, `Path.write_bytes`, `Path.mkdir`, `Path.touch` → error
- [ ] Test: `os.replace`, `os.rename`, `os.remove`, `os.unlink` → error
- [ ] Test: `tempfile.NamedTemporaryFile`, `tempfile.mkstemp`, `tempfile.TemporaryFile`, `tempfile.mkdtemp` → error
- [ ] Test: `socket.socket.connect`, `socket.socket.bind` → error
- [ ] Test: `importlib.resources.as_file` → error
- [ ] Test: simulator run on a temp project_root → no files written to `<ws>/.ao/` (assert `list(tmp/".ao").iterdir()` count unchanged pre/post)
- [ ] Test: `<ws>/.ao/evidence/workflows/` dir count unchanged
- [ ] Test: proposed_policies override does NOT touch disk (`Path.write_text` asserts 0 calls inside `_policy_override_context`)
- [ ] Re-entrancy: nested `pure_execution_context` → `PolicySimReentrantError` (prevent partial restore)

### Scenario loading (v2 multi-policy)
- [ ] Bundled 3 JSON scenarios load clean
- [ ] Unknown scenario `kind` → `ScenarioValidationError`
- [ ] Scenario with unknown `adapter_manifest_ref` → `ScenarioAdapterMissingError`
- [ ] Scenario with unknown `target_policy_name` → `TargetPolicyNotFoundError`
- [ ] Schema `additionalProperties: false` enforced
- [ ] JSON-only (YAML rejected at load time; schema ext check)

### Simulator core (v2 multi-policy API)
- [ ] `simulate_policy_change(project_root=..., proposed_policies={...})` with 2 policy_names in batch evaluates each scenario against correct target
- [ ] `executor_primitive` kind invokes all 3 primitives against `target_policy_name=policy_worktree_profile.v1.json`
- [ ] `governance_policy` kind invokes `check_policy(target_policy_name, ...)` with override context
- [ ] `combined` kind aggregates violations across targets
- [ ] Baseline snapshot is stable (same input → same hash)
- [ ] Proposed policy override isolated (baseline re-evaluation yields identical result after proposed run)
- [ ] `validate_command` NOT invoked when `include_host_fs_probes=False` (default)
- [ ] `baseline_source=BUNDLED`, `WORKSPACE_OVERRIDE`, `EXPLICIT` all route correctly

### Proposed-policy loader (v2 policy_shape_registry)
- [ ] Missing required top-level key → `ProposedPolicyInvalidError`
- [ ] Wrong type (`env_allowlist.allowed_keys` = dict not list) → `ProposedPolicyInvalidError`
- [ ] Valid policy structural check passes for each target_policy_name
- [ ] `_policy_shape_registry` mirror test: set of `required_top_keys` for each entry ⊆ keys actually consumed by the primitive (contract test)

### Diff engine (v2 N4 normalized)
- [ ] Transition taxonomy: allow→allow, allow→deny, deny→allow, deny→deny, error
- [ ] `notable` flag set iff transition != identity
- [ ] Violation-kind diff (added/removed) computed
- [ ] `DiffReport.to_dict()` handles Path→str, frozenset→sorted list, regex→pattern string, manifest source_path→relative path
- [ ] Canonical JSON roundtrip: `json.loads(json.dumps(report.to_dict(), sort_keys=True, ensure_ascii=False, separators=(",",":")))` = report.to_dict()
- [ ] Per-policy breakdown in `transitions_by_policy` accurate

### Policy hash canonical contract (v2 N3)
- [ ] `_canonical_policy_hash(policy_dict)` uses `sort_keys=True, ensure_ascii=False, separators=(",",":"))` + UTF-8 bytes + sha256
- [ ] Hash matches `artifacts.py:66` canonical digest pattern (cross-reference test)
- [ ] `baseline_policy_hashes` + `proposed_policy_hashes` stable across runs

### Reporter
- [ ] `--format json` canonical output (sorted keys, no trailing space)
- [ ] `--format text` operator-readable table + per-policy breakdown + notable deltas
- [ ] `--output <path>` atomic write (tmp + rename — but NOT under simulator pure context; CLI handler outside purity gate)
- [ ] `host_fs_dependent=true` banner in text/JSON when validate_command ran

### CLI
- [ ] Exit 0 for no-tightening result
- [ ] Exit 3 for ≥1 allow→deny transition
- [ ] Exit 1 for bad scenario file / unknown adapter / target_policy_name not found / proposed_policy invalid shape
- [ ] Exit 2 for simulation side-effect violation / re-entrancy
- [ ] `--enable-host-fs-probes` flag correctly gates `validate_command`
- [ ] `--baseline-source workspace` + `--baseline-overrides` interaction (explicit wins)
- [ ] Noun-group subcommand pattern preserved (`ao-kernel policy-sim run`)

### Regression (zero-delta guard)
- [ ] B0 bundled tests green
- [ ] B1 coordination tests green (policy_sim does not import coordination)
- [ ] B2 cost tests green
- [ ] B5 metrics tests green (policy_sim invisible to metrics derivation — `ao_kernel/metrics/derivation.py` on main@75c114f scans only `events.jsonl` kinds emitted by runtime; B4 emits NONE)
- [ ] B6 review/commit AI tests green
- [ ] `test_executor_policy_enforcer` green (read-only consumer; no primitive signature change)
- [ ] `_KINDS == 27` unchanged at `ao_kernel/executor/evidence_emitter.py:46` (B4 emit etmez)

---

## 6. Risk Register (v2)

| Risk | L | I | Mitigation |
|---|---|---|---|
| **R1** Purity contract bypass via unknown 3rd-party import side-effect | L | **H** | `_purity.py` monkey-patches 22+ sentinel APIs (v2 genişlet); CI test `test_simulator_no_fs_writes` scans tmp workspace before/after for any file creation |
| **R2** Proposed policy structural validator drifts from primitive consumption | M | M | `_policy_shape_registry.py` (v2 N1) centralizes — single source; contract test `test_shape_registry_matches_primitive_reads` |
| **R3** `governance.check_policy` override context leaks across threads | L | M | Override context uses `contextvars.ContextVar`; test `test_override_thread_isolation` |
| **R4** Scenario format divergence (YAML vs JSON) | Resolved | — | v2 Q1 karar: JSON-only; schema `.json` ext validation |
| **R5** `validate_command` host-fs nondeterminism mis-surfaced to CI | M | L | Default off; opt-in flag; report marks results as `host_fs_dependent=true` + `host_fs_fingerprint` |
| **R6** Simulator perf on large scenario sets (>100) | L | L | In-memory evaluation; perf budget ~1ms/scenario; stretch benchmark in C5 |
| **R7** CNS-031 "no-side-effects kontratı şüpheli" re-raised | Resolved | — | v2 §2.1 + §4 düzelt tablo + §5 assertion tests (22+ sentinel); explicit pure/quasi-pure/stateful classification with exact file path + line number |
| **R8** Scenario fixture drift when policy schema changes | M | M | Bundled fixtures versioned v1; schema bump = new `v2` scenarios (append, not replace) |
| **R9** Diff report transitions taxonomy incomplete for edge cases (error→allow) | L | L | `transition="error"` catchall + test matrix of 5×5 baseline→proposed states |
| **R10** Operator confuses "dry-run" semantics with "what run will this produce?" | M | L | `docs/POLICY-SIM.md` §2 explicit: policy-decision grade, NOT full-execution grade; mid-depth disclaimer |
| **R11** (v2 NEW) `importlib.resources.as_file` temp extraction bypasses purity guard | M | M | v2 adapter registry snapshot taken BEFORE `pure_execution_context` entry; context-time adapter lookups from snapshot only |
| **R12** (v2 NEW) Multi-policy batch combinatorics blow up | L | L | v2 constraint: each scenario references 1 target (2 for `combined`); no cartesian product; per-scenario linear |

---

## 7. Scope Dışı (post-B4)

- **Full `Executor.run_step` dry-run** (adapter mock harness) → B7 benchmark suite
- **RFC 7396 merge-patch support for proposed policy** → v2 (Q3 deferred)
- **Auto-discovery of scenarios** from `<workspace>/.ao/policy_sim/scenarios/*.json` → post-B4 v1.1
- **Evidence emit for simulation runs** (audit trail of "operator X ran simulation Y at ts Z") → **NEVER** per §2.1 purity contract
- **Integration with Grafana** (simulation-transition histogram) → B5.x opt-in post-ship
- **MCP tool surface** (`policy_sim.run` exposed via `mcp_server`) → v2
- **Time-travel** (simulate against past policy version from git history) → FAZ-C
- **Web UI** → NEVER (CLI + library only)
- **YAML scenario support** → v2 optional (PyYAML extra)

---

## 8. Cross-PR Conflict Resolution

### B1 (coordination) interaction
- Zero shared code. `policy_sim` does NOT import `ao_kernel.coordination`.
- B1 `claim_*` policies not simulated in v1 (scope = `policy_worktree_profile` + `check_policy`-backed policies; coordination policy is its own surface).

### B2 (cost) interaction
- Zero shared code. No imports from `ao_kernel.cost`.
- Cost policies (`policy_cost_tracking.v1.json`) can be simulated via `kind: governance_policy` scenarios (since `check_policy` handles them) — but bundled v1 scenarios don't cover this (stretch).

### B3 (cost-aware routing) interaction
- Zero shared code. B3 extends router + catalog; B4 is policy simulator. No overlap.
- B3 routing_by_cost policy could be simulated via `kind: governance_policy` scenarios when B3 lands (bundled fixture expansion post-merge).

### B5 (metrics) interaction (CRITICAL per user prompt + v2 bulgu 6)
- **Verified at main HEAD `75c114f`**: `policy_sim` emits ZERO evidence events. Metrics derivation (`ao_kernel/metrics/derivation.py`) scans `events.jsonl` — since B4 never writes there (sentinel guarded), it's invisible to the pipeline.
- **`_KINDS == 27` ground truth**: `ao_kernel/executor/evidence_emitter.py:46` at HEAD `75c114f`. B4 adds NO new kind.
- **Metric family absence confirmed**: no `ao_policy_sim_*` metric. v1 scope excludes observability surface.
- **Risk**: if future B4 iteration adds optional opt-in audit trail (R8 → v2 scope), that MUST be a new event kind (e.g., `policy_sim_executed`) and documented in `_KINDS` taxonomy. v1 does not.
- **Regression test**: `test_policy_sim_invisible_to_metrics` — runs simulation then invokes `derive_metrics_from_evidence` → metric counter values unchanged.

### B6 (review AI + commit AI) interaction
- Zero shared code. `policy_sim` CLI + library; B6 is workflow runtime.
- Review AI may *consume* simulation reports as input context in FAZ-C (stretch).

### Shared files touched
- `ao_kernel/cli.py` — 1 new subparser (`policy-sim`); ~40 LOC delta; no removal.
- `pyproject.toml` — **no new dep** (v2 Q1: JSON-only).
- `CHANGELOG.md` — new `[Unreleased]` entry under PR-B4.
- `docs/POLICY-SIM.md` — new file; no existing doc edit.

---

## 9. Codex iter-2 için açık soru: YOK

Tüm v1 Q kararları v2'de netleşti (Q1-Q5). 6 bulgu + 4 sub-finding (N1-N4) absorbe edildi. Beklenen verdict: **PARTIAL** (dar) veya **AGREE**.

---

## 10. Audit Trail

| Iter | Date | Verdict |
|---|---|---|
| v1 (Claude draft — parent wrote from subagent output) | 2026-04-18 | Pre-Codex iter-1 submit |
| iter-1 (CNS-20260418-038, thread `019d9da9` expired) | 2026-04-18 | **REVISE** — 6 bulgu + 4 sub-finding; 5 Q cevaplandı |
| v2 (iter-1 absorb) | 2026-04-18 | Pre-iter-2 submit |
| **iter-2** (fresh thread `019d9dca-0c18-79d1-948c-81668aa5027b`) | 2026-04-18 | **PARTIAL** — 1 blocker (adapter snapshot API fabrikası) + 3 warnings (workspace=None tutarsızlık + override_context call/decl mismatch + facade emit_event alias eksik + project_root docstring çelişkisi) |
| **v3 (iter-2 absorb)** | 2026-04-18 | Pre-iter-3 submit |
| iter-3 | TBD | AGREE expected |

### Plan revision history

| Ver | Change |
|---|---|
| v1 | Initial draft (background subagent); 10-primitive pure/stateful table; purity-context design (3 sentinel); 5 Q for Codex; single `policy_name` + single `proposed_policy`; YAML+JSON dual loader |
| v2 | iter-1 REVISE absorb (6 bulgu + 4 sub-notes): (1) per-scenario `target_policy_name` + `proposed_policies: Mapping[str, Mapping]` multi-policy batch; (2) `project_root` + `policy_override_map` iki ayrı argüman + `BaselineSource` enum; (3) `_purity.py` 22+ sentinel; (4) purity table quasi-pure düzelt; (5) JSON-only v1; (6) `_KINDS == 27` main@75c114f dayanağı; (N1) `_policy_shape_registry.py`; (N2) `BaselineSource` enum; (N3) `_canonical_policy_hash`; (N4) `DiffReport.to_dict()` normalize. |
| **v3** | **iter-2 PARTIAL absorb** (1 blocker + 4 warnings): (1) Adapter snapshot API düzelt — `reg.load_bundled() + reg.load_workspace(project_root) + reg.list_adapters()` pattern; `capabilities_snapshot()` diye API YOK (gerçek surface: `get`, `list_adapters`, `missing_capabilities`, `supports_capabilities`); (2) Üst özet tablosu `workspace=None` → `workspace=<sentinel>` (governance.py:49-52 ambient cwd discovery önlenir); (3) `_policy_override_context(policy_overrides=active_policy_map)` tek Mapping argüman (call vs declaration consistency); (4) `ao_kernel.executor.emit_event` public facade alias sentinel eklendi (23+ total); (5) `project_root` docstring netleştirildi — (a) adapter snapshot, (b) WORKSPACE_OVERRIDE disk read, (c) EXPLICIT/BUNDLED dereferenced değil. |

**Status**: Plan v3 hazır. Codex CNS-20260418-038 fresh thread `019d9dca-0c18-79d1-948c-81668aa5027b` iter-3 submit için hazır. AGREE (veya çok dar PARTIAL) beklenir.
