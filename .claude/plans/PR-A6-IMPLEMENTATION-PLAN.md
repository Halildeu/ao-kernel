# PR-A6 Implementation Plan v2 — Demo + Adapter Fixtures + Meta-Extra + v3.1.0 Release

**Tranche A PR 8/8 (final)** — post CNS-026 iter-1 PARTIAL (5B+7W absorbed). v3.1.0 ship.

## Revision History

| Version | Date | Scope |
|---|---|---|
| v1 | 2026-04-16 | Initial draft; CNS-026 iter-1 target. |
| **v2** | **2026-04-16** | **5 blocker absorbed: B1 gh_pr_stub fixture for demo (no real gh); B2 patch content wiring (codex_stub canned diff → patch_preview/apply); B3 AdapterRegistry.load_bundled() + workspace>bundled precedence; B4 IntentClassificationError typed error; B5 version bump 3.0.0→3.1.0 (pyproject.toml + __init__.py). 7 warning noted.** |

---

## 1. Amaç

FAZ-A'nın son PR'ı. Kalan 3 release gate'i kapatır + v3.1.0 tag:
- **End-to-end demo flow passes locally** — `examples/demo_bugfix.py` runnable script
- **3 adapter examples work** — bundled adapter manifests + `.ao/adapters/` auto-install
- **Docs published: tutorial + 3 adapter walkthroughs** — README CLI reference update + tutorial quickstart

### Kapsam özeti

| Katman | Dosya | LOC |
|---|---|---|
| Demo script | `examples/demo_bugfix.py` | ~200 |
| gh_pr_stub fixture | `ao_kernel/fixtures/gh_pr_stub.py` (B1) | ~40 |
| Bundled adapters + discovery | `ao_kernel/defaults/adapters/` + `AdapterRegistry.load_bundled()` (B3) | ~80 |
| Init auto-install | `ao_kernel/init_cmd.py` delta (`.ao/adapters/` seed) | ~20 |
| `[coding]` meta-extra | `pyproject.toml` delta | ~5 |
| Version bump | `pyproject.toml` + `__init__.py` 3.0.0→3.1.0 (B5) | ~4 |
| `llm_fallback` concrete | `ao_kernel/workflow/intent_router.py` delta + `IntentClassificationError` (B4) | ~100 |
| Patch content wiring | `multi_step_driver.py` adapter output_ref→patch (B2) | ~40 |
| README update | `README.md` delta (CLI ref + demo) | ~40 |
| Tutorial | `docs/TUTORIAL.md` (yeni) | ~150 |
| Docs fix | `docs/DEMO-SCRIPT.md` CLI syntax update (W4) | ~15 |
| CHANGELOG | `[3.1.0]` section finalize | ~30 |
| Tests | `tests/test_demo_flow.py` + `tests/test_llm_fallback.py` + `tests/test_adapter_bundled.py` | ~250 |
| **Toplam** | | **~975** |

- Evidence kind delta: **0** (18-kind intact)
- Schema delta: **0**
- Core dep: **0** (`jsonschema>=4.23.0` only; `llm_fallback` → `[llm]` extra lazy)

---

## 2. Scope

### Scope İçi

**1. Demo script (`examples/demo_bugfix.py`):**
- Python script, no external deps beyond `ao-kernel[llm]`
- Steps: workspace init → seed intent → create run → `MultiStepDriver.run_workflow` → codex-stub adapter → patch preview → CI gate (pytest) → approval gate (auto-grant for demo) → apply patch → evidence timeline → evidence verify-manifest
- Uses bundled `bug_fix_flow.v1.json` workflow + codex-stub adapter
- `context_compile` step stub (A4b) — empty preamble OK for demo
- `open_pr` step uses codex-stub substitute (no real `gh` call — demo-tier)
- Output: workflow_completed + evidence timeline table printed to stdout
- Exit 0 on success; non-zero with diagnostic on any failure

**2. Bundled adapter manifests:**
- Copy 3 production manifests from `tests/fixtures/adapter_manifests/` to `ao_kernel/defaults/adapters/`:
  - `claude-code-cli.manifest.v1.json`
  - `codex-stub.manifest.v1.json`
  - `gh-cli-pr.manifest.v1.json`
- `ao-kernel init` seeds `.ao/adapters/` with bundled defaults (same pattern as policies/schemas)
- `AdapterRegistry.load_bundled()` discovers them via `importlib.resources`

**3. `[coding]` meta-extra (`pyproject.toml`):**
- `coding = ["ao-kernel[llm]"]` — code-index, lsp, metrics henüz yok, placeholder
- `[enterprise]` placeholder — otel + metrics + dashboard + sso + pgvector (FAZ-E)

**4. `llm_fallback` concrete (`intent_router.py`):**
- Replace `NotImplementedError` with minimal LLM-based classifier
- Lazy import `tenacity` + `ao_kernel.llm.execute_request` (only when `[llm]` installed)
- Prompt: "Given the intent text, return one of these workflow_ids: {available_ids}. Reply with just the id."
- Parse response → workflow_id; on failure → `ClassificationResult(matched_rule_id="__llm_fallback__")`
- No `[llm]` installed → `ImportError` → `IntentClassificationError("llm_fallback requires ao-kernel[llm]")`
- Tests: mock `execute_request` response (no real LLM call in CI)

**5. README update:**
- CLI reference table: add `ao-kernel evidence timeline/replay/generate-manifest/verify-manifest`
- Demo quickstart section pointing to `examples/demo_bugfix.py`
- Architecture diagram: add `_internal/evidence/` and `executor/multi_step_driver.py`

**6. Tutorial (`docs/TUTORIAL.md`):**
- "Getting started with ao-kernel governed workflows"
- 3 sections: install → init workspace → run demo → inspect evidence
- References DEMO-SCRIPT.md for advanced 11-step walkthrough

**7. CHANGELOG + v3.1.0 tag:**
- `[Unreleased]` → `[3.1.0] - 2026-04-16`
- PR-A6 entry + FAZ-A summary header
- `git tag v3.1.0 && git push origin v3.1.0`

### Scope Dışı
- Real `gh` CLI PR creation (demo-tier codex-stub substitute)
- `context_compile` production wiring (FAZ-B)
- OS-level network sandbox (FAZ-B)
- `[code-index]`, `[lsp]`, `[metrics]` concrete implementations (FAZ-C)

---

## 3. Write Order

```
Layer 0 — Bundled adapter manifests + init delta
  1. ao_kernel/defaults/adapters/ (3 manifests copy)
  2. ao_kernel/init_cmd.py delta (.ao/adapters/ seed)

Layer 1 — llm_fallback concrete
  3. ao_kernel/workflow/intent_router.py delta

Layer 2 — Meta-extra
  4. pyproject.toml [coding] + [enterprise] placeholder

Layer 3 — Demo script
  5. examples/demo_bugfix.py

Layer 4 — Docs
  6. docs/TUTORIAL.md (new)
  7. README.md delta

Layer 5 — Tests
  8. tests/test_demo_flow.py (~10 tests)
  9. tests/test_llm_fallback.py (~8 tests)

Layer 6 — Release
 10. CHANGELOG.md [3.1.0] finalize
 11. git tag v3.1.0
```

---

## 4. CNS-026 Question Candidates

**Q1 — Demo script auto-approve.** Demo'da `await_approval` human gate var. Auto-grant seçenekleri: (a) demo script approval token'ı kendisi resume eder (programmatic); (b) `--auto-approve` workflow flag; (c) demo flow'dan human step çıkar. Hangisi?

**Q2 — Bundled adapters discovery.** `ao_kernel/defaults/adapters/` importlib.resources ile mi yoksa `init_cmd` sırasında `.ao/adapters/` kopyalama ile mi? Mevcut `AdapterRegistry.load_workspace()` `.ao/adapters/` scan ediyor; bundled discovery ayrı path mi?

**Q3 — llm_fallback test strategy.** Real LLM call CI'da yok. Mock `execute_request` response mu yoksa fixture-based deterministic response mu? `tenacity` retry'sız test mi?

**Q4 — v3.1.0 tag sırası.** PR merge sonrası tag mı (main'e squash sonrası), yoksa PR içinde CHANGELOG finalize + tag ayrı commit mi?

---

## 5. Audit Trail

| Field | Value |
|---|---|
| Plan version | **v2** |
| Head SHA | `aeda4eb` |
| Base branch | `main` |
| Target branch | `claude/tranche-a-pr-a6` |
| CNS-026 thread | NEW |
| Total test target | 1534+ (1516 + ~18) |
| Coverage gate | 85% |

| CNS-026 thread | `019d940f-40c7-7ee3-91c0-d5bcc305c682` |

**Status:** Plan v2 complete. Submit iter-2.
