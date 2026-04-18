# Session Handoff — 2026-04-18 B3 + B4 Parallel Mid-Iter

**Handoff sebebi**: Claude Code permission prompt'lar `.claude/plans/*.md` edit'lerinde her seferinde tetikleniyor. Settings allowlist eklendi (`~/.claude/settings.json`) ama mid-session cache invalidation yok → yeni session'da tamamen temiz geçecek.

## Main durumu

- **Branch**: `claude/tranche-b-pr-b3` (active)
- **Main HEAD**: `75c114f` (PR-B5 merge, bugün)
- **PyPI**: v3.1.0 LIVE (v3.2.0 target FAZ-B sonunda)
- **Test**: 1998 passed / 3 skipped (B5 merge sonrası baseline)

## FAZ-B Progress: 7/9 merged

| PR | Status |
|---|---|
| B0 #96, B1 #97, docfix #98, B2 #99, B2-e2e #100, B5 #102, B6 #101 | ✅ MERGED |
| **B3** | 🔄 plan v2 yazıldı, iter-2 PARTIAL, iter-3 absorb bekliyor |
| **B4** | 🔄 plan draft v1 yazıldı, iter-1 REVISE, v2 absorb bekliyor |
| B7, B8 | ⏳ future |

## Aktif Codex MCP threads (saklı)

| Thread ID | PR | CNS | Son verdict |
|---|---|---|---|
| `019d9d8a-69bb-74b0-bb11-930ee6b80c81` | **B3** | CNS-20260418-037 | **PARTIAL** (iter-2) — dar iter-3 kapatır |
| `019d9da9-81de-7771-a4ac-e5aa790fe11f` | **B4** | CNS-20260418-038 | **REVISE** (iter-1) — daraltılmış v2 gerekir |

## B3 iter-3 absorb — 3 bulgu (DAR)

**Plan dosyası**: `.claude/plans/PR-B3-IMPLEMENTATION-PLAN.md` (v2 header, header'ı `v3` yap)

### Bulgu 1 — Q3 semantiği plan içinde 4 yerde tutarsız

Codex bulgusu: üst karar tablosu `skip-missing-if-any-known, fallback-if-none-known` diyor ama:
- §2.3 helper spec: `known_cost + unknown_cost in original order` (yanlış)
- §2.4 behavior matrix: unknown bucket seçilebilir (yanlış)
- §5 acceptance: "ordered last / unknown price = most expensive" (yanlış)

**v3 fix**: Tek semantik — `sort_providers_by_cost()` unknown-cost provider'ları eleme YAPMAZ (NO_SLOT preserve için); **ancak router tarafında** eğer en az bir known-cost varsa unknown-cost provider'lar order'dan düşürülür. Bu router delta'nın sorumluluğu, helper'ın değil.

Alternatif daha basit: helper `(known_cost_sorted, unknown_list)` tuple döner; router `known_cost_sorted` varsa sadece onu kullanır, unknown'ları drop eder; hiç known yoksa orijinal order'a fallback.

Plan'ın 4 yerinde (header absorb tablosu + §2.3 helper docstring + §2.4 matrix + §5 acceptance) aynı semantiği yaz.

### Bulgu 2 — `RoutingCatalogMissingError(CostError)` inheritance yanlış

Gerçek base sınıf `CostTrackingError` (grep: `ao_kernel/cost/errors.py:12`). `CostError` diye bir sınıf yok.

**v3 fix**: §2.5 `RoutingCatalogMissingError(CostTrackingError)` yaz.

### Bulgu 3 — `_MODEL_ALIAS_MAP` belirsiz

v2 header `_PROVIDER_ALIAS_MAP` yanında `_MODEL_ALIAS_MAP` deklare ediyor ama §2.3'te somut tablo yok. Provider alias tek başına catalog coverage gap'ini kapatmıyor (3/14 exact match).

**v3 fix**: İki seçenek — ikisinden birini net seç:
- **(A) v1'de model aliasing YOK**: header'dan `_MODEL_ALIAS_MAP` kaldır. Uncovered modeller → unknown-cost bucket → known-cost varsa drop, yoksa fallback.
- **(B) v1'de model aliasing VAR**: Somut `_MODEL_ALIAS_MAP` tablo (ör. `"claude-3-5-sonnet" → "claude-3-5-sonnet-20241022"` gibi yeterli örneklerle).

**Önerilen (A)** — daha az yüzey, daha net contract. Model aliasing FAZ-C scope.

## B4 v2 absorb — 6 bulgu (GENİŞ)

**Plan dosyası**: `.claude/plans/PR-B4-DRAFT-PLAN.md` (v1 draft header'ı `v2` yap; başlık "draft" kaldırabilir)

### Bulgu 1 — Tek `policy_name` modeli ScenarioSet için kırık

Global `policy_name="policy_worktree_profile.v1.json"` imzası aynı koşuda `executor_primitive` + `governance_policy` scenario'larını destekleyemez. Bundled 3 sample'da zaten 2 farklı policy var (worktree_profile + autonomy).

**v2 fix**: `policy_name` scenario içinde `target_policy_name` field'ı olarak taşı. `simulate_policy_change(proposed_policies: Mapping[str, Mapping])` — dict of `policy_name → proposed_dict`. Multi-policy batch zorunlu v1 (Codex Q4 karar: "v2 değil, temel doğruluk").

### Bulgu 2 — `workspace_root` semantiği ambiguity

- `config.workspace_root()` → `.ao/` dizini (auto-discovery)
- `workspace.project_root()` → proje kökü
- `AdapterRegistry.load_workspace()` proje kökünden `/.ao/adapters` arıyor
- `governance.check_policy(workspace=ws)` `.ao/policies` bekliyor

Tek `workspace_root` parametresiyle hepsi ikna edilmez.

**v2 fix**: İki ayrı argüman:
- `project_root: Path` — manifest loader için (adapter discovery)
- `policy_override_map: Mapping[str, Mapping]` — proposed policies in-memory; disk bypass

`check_policy` için `workspace=None` ambient-cwd discovery'yi önlemek üzere explicit `policy_dict` injection (via `_policy_override_context` monkey-patch `load_with_override`).

### Bulgu 3 — No-side-effects guard yetersiz

Codex bulguları:
- Pre-imported `emit_event` alias'ları (`executor.py` ve `multi_step_driver.py`) monkey-patch kapsamı dışı
- Network erişimi kapsamı dışı (`socket.socket` binding/connect)
- `tempfile.TemporaryFile/NamedTemporaryFile/mkstemp`, `Path.write_text/mkdir`, `os.replace`, `__pycache__` yazımı
- `importlib.resources.as_file()` → manifest_loader.load_bundled() içinde → temp extraction

**v2 fix**: `_purity.py` genişlet:
```python
PATCHED_SENTINELS = {
    # Direct module imports
    "ao_kernel.executor.evidence_emitter.emit_event",
    "ao_kernel.executor.executor.emit_event",          # pre-imported alias
    "ao_kernel.executor.multi_step_driver.emit_event", # pre-imported alias
    "ao_kernel.executor.worktree_builder.create_worktree",
    # Subprocess
    "subprocess.Popen.__init__",
    "subprocess.run",
    # Filesystem writes
    "pathlib.Path.write_text",
    "pathlib.Path.write_bytes",
    "pathlib.Path.mkdir",
    "pathlib.Path.touch",
    "os.replace",
    "os.rename",
    "tempfile.NamedTemporaryFile",
    "tempfile.mkstemp",
    "tempfile.TemporaryFile",
    # Network
    "socket.socket.connect",
    "socket.socket.bind",
}
```
Her birine specific `PolicySimSideEffectError(sentinel_name, context)` raise.

Plus: import time cache invalidation risk — `importlib.resources.as_file()` monkeypatch edilmeli (manifest_loader.load_bundled usage).

### Bulgu 4 — Purity table factual yanlışlar

- `build_sandbox` tam pure DEĞİL: `Path(prefix).resolve()` host FS symlink read (`policy_enforcer.py:146`). v2: "**quasi-pure** (host FS symlink read via `Path.resolve`)".
- `check_policy` loader dışında `resolve_ws()` cwd discovery yapar (`governance.py:40-52`). v2: "**quasi-pure** (ambient cwd discovery when `workspace=None`)". Plan'ın "workspace=None bundled'a düşer" cümlesi yanlış — düzelt.

### Bulgu 5 — YAML v1 için kötü uyum

- `pyproject.toml` base dep'te PyYAML yok
- `package-data` sadece `**/*.json` ship ediyor → bundled YAML senaryolar wheel/sdist'e GİRMEZ

**v2 fix**: **JSON-only v1**. YAML optional extra v2+ veya post-B4. Scenario schema + bundled samples `.json`. Q1 kesin karar.

### Bulgu 6 — `_KINDS == 27` claim ve `metrics/derivation.py` referansı

Codex'in cwd'si `stupefied-swartz` worktree idi — pre-B5 state (`_KINDS = 18`). Gerçek main `75c114f` @ `_KINDS = 27` (B2 ledger kinds eklendi; B5 emit etmez). `ao_kernel/metrics/derivation.py` gerçek main'de var.

**v2 fix**: Plan acceptance `_KINDS == 27` doğru; dayanağı `ao_kernel/executor/evidence_emitter.py:46` at HEAD `75c114f`. Stupefied-swartz worktree outdated değil problem — plan sadece upstream reference kullanıyor. Belki "B5 invisibility verified" için explicit path ekle: "Metrics derivation (`ao_kernel/metrics/derivation.py` on main@75c114f) scans only `events.jsonl` kinds emitted by runtime."

### Bulgu 7+ (Codex ek notlar)

- Structural validator "mirror of key-reads" yeterli değil — primitive'lerin tükettiği projection ortak helper'da merkezileştir
- `baseline_policy=None` ambiguity → explicit enum: `bundled | workspace_override | explicit`
- Policy hash canonical kontrat: `sort_keys=True, ensure_ascii=False, separators=(",", ":")` → UTF-8 bytes SHA-256. `artifacts.py:66` ile hizalan.
- `DiffReport` `asdict` güvenli değil: `Path`, `frozenset`, regex, manifest `source_path` normalize et

### 5 Q v2 kararları (Codex)

| Q | v2 karar |
|---|---|
| Q1 YAML vs JSON | **JSON-only v1** (paketleme zorunluluğu) |
| Q2 validate_command | **default-off flag**, `host_fs_fingerprint` + `host_fs_dependent=true` |
| Q3 proposed policy format | **full replacement v1**; RFC 7396 merge patch → v2 |
| Q4 multi-policy batch | **v1 zorunlu** (per-scenario target_policy_name) |
| Q5 CLI placement | **`ao-kernel policy-sim run`** (noun-group pattern) |

## Gelecek oturumun ilk adımları

1. **Codex MCP thread'leri hafızaya al** — yeni session başında thread ID'leri README.md veya bu handoff'tan alır.

2. **B3 v3 tek `Write`** ile full rewrite (1 prompt, onay sonrası promptsuz çünkü settings yeni session'da aktif):
   - Header: v2 → v3
   - §2.3 helper spec: tek semantik, unknown-cost preserve ama router drop
   - §2.4 matrix align
   - §5 acceptance align
   - §2.5 RoutingCatalogMissingError → CostTrackingError
   - Header tablosu'ndan `_MODEL_ALIAS_MAP` kaldır (v1'de yok)
   - §10 audit trail iter-2 PARTIAL + v3 absorb

3. **B3 iter-3 submit** (`codex-reply` thread `019d9d8a`):
   ```
   Iter-3 — v3 absorb: Q3 semantiği tek yerde (helper preserve + router drop);
   RoutingCatalogMissingError(CostTrackingError); model aliasing v1'de yok explicit.
   Beklenen: AGREE.
   ```

4. **B4 v2 tek `Write`** ile full rewrite (1 prompt):
   - Header: draft v1 → v2
   - Per-scenario `target_policy_name`
   - `project_root` + `policy_override_map` ayrı argümanlar
   - Purity guard genişletme (15+ sentinel)
   - JSON-only scenarios
   - Purity table quasi-pure düzeltmeleri (build_sandbox, check_policy)
   - baseline_policy enum
   - Policy hash canonical kontrat
   - DiffReport normalize
   - §10 audit trail iter-1 REVISE + v2 absorb

5. **B4 iter-2 submit** (`codex-reply` thread `019d9da9`):
   ```
   Iter-2 — v2 absorb: 6 bulgu + ek notlar absorbe edildi.
   Beklenen: PARTIAL veya AGREE.
   ```

6. **Paralel bekle**. AGREE sırasına göre:
   - B3 AGREE önce gelirse: impl başlat (4-commit DAG), B4 thread devam
   - B4 AGREE önce gelirse: impl başlat, B3 thread devam
   - İkisi birden AGREE: önce B3 (küçük), sonra B4

7. **Impl serial, PR paralel**:
   - B3 4-commit → PR → CI → merge
   - B4 5-commit → PR → CI → merge
   - Tek worktree, branch switch yok (farklı branch'ler üzerinden sırayla)

## Dosya referansları

### Plan dosyaları (aktif)
- `.claude/plans/PR-B3-IMPLEMENTATION-PLAN.md` — B3 v2 (next: v3)
- `.claude/plans/PR-B4-DRAFT-PLAN.md` — B4 draft v1 (next: v2 + rename? Yoksa aynı dosya OK)

### Reference plans (merged)
- `.claude/plans/PR-B0-IMPLEMENTATION-PLAN.md` → PR-B6-IMPLEMENTATION-PLAN.md (6 dosya)
- `.claude/plans/PR-B5-IMPLEMENTATION-PLAN.md` — v4 AGREE + post-impl absorb (pattern referansı)
- `.claude/plans/SESSION-HANDOFF-2026-04-17-FAZ-B-B6-MERGE.md` — dün handoff
- `.claude/plans/FAZ-B-MASTER-PLAN.md` — master plan (9 PR target)
- `.claude/plans/TRANCHE-STRATEGY-V2.md` — 5-faz roadmap

### Kod
- `ao_kernel/cost/policy.py:63-87` — `RoutingByCost` dataclass (B3 extend target)
- `ao_kernel/cost/errors.py:12` — `CostTrackingError` base (inherit target)
- `ao_kernel/_internal/prj_kernel_api/llm_router.py:104-210` — `resolve` fn (B3 cost-aware branch target)
- `ao_kernel/defaults/catalogs/price-catalog.v1.json` — provider/model naming
- `ao_kernel/defaults/operations/llm_provider_map.v1.json` — router provider names (alias source)
- `ao_kernel/executor/policy_enforcer.py:86,194,268,302,332` — B4 primitive targets
- `ao_kernel/governance.py:29-52` — `check_policy` + `resolve_ws` (B4 purity care)
- `ao_kernel/config.py:111-118` — `load_with_override` (B4 monkey-patch target)
- `ao_kernel/executor/evidence_emitter.py:46` — `_KINDS == 27` source of truth

### Settings
- `~/.claude/settings.json` — permissions allowlist eklendi (`.claude/plans/**` için)

## Bugün öğrenilen dersler

1. **Claude Code permission cache** mid-session invalidate olmuyor — `.claude/plans/` için settings ekle + yeni session aç.
2. **Paralel Codex thread'ler** etkili: B3 + B4 aynı anda plan-time iter'de koşar; her thread bağımsız.
3. **Background subagent** (B4 plan investigation) plan draft'ı paralel üretir; parent waits, subagent returns, parent writes to disk (subagent dosya yazamaz).
4. **Codex cwd farklı olabilir** — stupefied-swartz worktree pre-B5 state'te; `_KINDS` gibi değerler farklı okunabilir. Plan-time claim'ler main HEAD'e göre fact-check'lenmeli.
5. **Plan'da karar tutarsızlığı** Codex tarafından yakalanır (B3 Q3 semantiği 4 yerde farklıydı). Karar netleşince tüm bölümler tek seferde güncellenmeli.

## Status

- B3 plan-time 2/N iter done; iter-3 dar absorb bekliyor; AGREE yakın
- B4 plan-time 1/N iter done; v2 geniş absorb bekliyor; iter-2 PARTIAL beklenir
- Impl: henüz başlamadı (ikisinde de AGREE sonrası başlar)
- Tek worktree; paralel plan-time + serial impl pattern
