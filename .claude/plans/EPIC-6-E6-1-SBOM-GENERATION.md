# Epic 6 E-6-1 — SBOM Generation (cyclonedx-py)

**Status:** Implementing E-6-1a (script + extras + tests + plan doc).
**Codex thread:** `019e8337` (plan-time REVISE, `ready_for_impl: true`,
PR sırası bölündü).
**Sub-slice:** E-6-1a (this PR) ⊂ Epic 6 E-6-1.
**Out-of-scope (E-6-1b follow-up PR):** publish.yml release-time
integration (GitHub Release artifact upload + workflow invariant tests).

## 1. Sorun

V5 Epic 6 E-6-1 plan'da yazıyor: "SBOM generation (cyclonedx-py;
release artifact)". Mevcut release pipeline:

- `pyproject.toml` — `[sbom]` extra YOK
- `scripts/` — SBOM generator YOK
- `publish.yml` — sadece wheel + sdist (twine check strict whitelist)
- `docs/` — SBOM dokümantasyonu YOK

Hedef: cross-PR / cross-machine release truth için canonical, validable,
generator-leak-free CycloneDX 1.5 JSON SBOM.

## 2. Codex iter-1 absorb (REVISE)

Plan-time istişare özet:

| Konu | Codex bulgu | Absorb |
|---|---|---|
| Target environment | `pip install -e .[sbom]` ile editable install SBOM'u yanlış (calling environment'ı tarar) | Wheel install edilen izole target venv → cyclonedx-py o venv'i tarar |
| SBOM path | `dist/` → twine check whitelist + `tests/test_publish_workflow.py` REJECT | Path: `build/sbom/` veya `release-artifacts/`; `dist/` içine YASAK |
| CLI form | `python3 -m cyclonedx_py environment --format json --output` | `python -m cyclonedx_py environment <TARGET_VENV_PYTHON> --output-format JSON --schema-version 1.5 --output-file` |
| Spec version | "latest" YASAK | Pin `1.5` (E-6-1 contract) |
| Validation | "at least 1 component" yetersiz | bomFormat + specVersion + components + ao-kernel visible + generator-tool-NOT-leaked |
| İmzalama | E-6-1a scope | OUT — Epic 9 final promotion veya Epic 6 follow-up slice |
| PR sırası | Tek PR risk | İki sub-slice: E-6-1a script+test+plan, E-6-1b publish.yml integration |
| publish.yml unblock | Same PR riski | Out-of-scope — E-6-1b ayrı |

## 3. E-6-1a değişiklik scope

### 3a. `pyproject.toml`
Yeni opsiyonel extra (alfabetik sıra korunarak metrics altına):
```toml
sbom = [
    "cyclonedx-bom>=4.0.0",
]
```

Constraint: minimum 4.0.0 (latest stable major + CycloneDX 1.5 desteği).
Üst sınır YOK; tooling SBOM bağımsız dependency tree analiz yapıyor.

### 3b. `scripts/generate_sbom.py`
Pure-stdlib library + thin CLI. Public API:

| Symbol | Tip | Sözleşme |
|---|---|---|
| `SBOM_SCHEMA_VERSION` | const str | `"1.5"` |
| `SBOM_FORMAT` | const str | `"CycloneDX"` |
| `RELEASE_COMPONENT_NAME` | const str | `"ao-kernel"` |
| `GENERATOR_PACKAGE_NAMES` | frozenset | `{"cyclonedx-bom", "cyclonedx-python-lib", "cyclonedx-py"}` |
| `SBOMGenerationError` | exception | Validation + subprocess fail için raise |
| `validate_sbom(sbom)` | function | Codex iter-1 invariant pinleri |
| `generate_sbom(wheel, output, schema_version=...)` | function | E2E: venv → install → cyclonedx → validate |
| `main(argv=None)` | function | argparse + dist/ reject + wheel exists |

Akış:
```
build/check wheel exists
  → tempdir target venv
    → install wheel into target venv
      → python -m cyclonedx_py environment <target-py> --output-format JSON \
          --schema-version 1.5 --output-file <out>
        → JSON parse + validate
          → return parsed sbom
```

Generator (`cyclonedx_py`) **calling environment**'tan çalıştırılır;
**target venv** içinde KURULU değil. Bu sayede tooling component'leri
release SBOM'u kirletmez.

### 3c. `tests/test_sbom_generation.py`
14 unit + 1 e2e smoke test.

Unit tests (validate_sbom — pure-Python, cyclonedx-bom gerektirmez):
- `test_validate_sbom_accepts_canonical_payload`
- `test_validate_sbom_rejects_wrong_bomformat`
- `test_validate_sbom_rejects_wrong_specversion`
- `test_validate_sbom_rejects_empty_components`
- `test_validate_sbom_rejects_missing_components_key`
- `test_validate_sbom_rejects_missing_release_component`
- `test_validate_sbom_accepts_release_in_metadata_only`
- `test_validate_sbom_rejects_generator_tool_leak` (3 sub-case)
- `test_validate_sbom_rejects_generator_tool_leak_case_insensitive`
- `test_validate_sbom_handles_non_list_components_gracefully`

pyproject + CLI wiring:
- `test_sbom_extra_present_in_pyproject`
- `test_sbom_extra_is_not_in_default_runtime_deps`
- `test_cli_rejects_dist_output_path`
- `test_cli_rejects_missing_wheel`

E2E smoke (gated on `importlib.util.find_spec("cyclonedx_py")`):
- `test_generate_sbom_end_to_end_smoke` — build wheel → SBOM → validate.
  cyclonedx-bom kurulu değilse `pytest.mark.skipif` ile skip.

### 3d. Plan doc
Bu dosya.

## 4. Out-of-scope (E-6-1b follow-up PR)

| Konu | Sonra |
|---|---|
| `.github/workflows/publish.yml` SBOM step | E-6-1b — workflow_dispatch path + `permissions.contents: write` + `gh release view || create --verify-tag` + tag-based VERSION extraction |
| GitHub Release artifact upload | E-6-1b — `gh release upload v$VERSION dist/...sbom.cdx.json` (NOT dist/ — separate path) |
| Workflow invariant tests | E-6-1b — `tests/test_publish_workflow.py` extend: SBOM step exists, `dist/` whitelist unchanged, contents:write permission present |
| Sigstore/cosign signing | Epic 6 follow-up slice veya Epic 9 final promotion |
| SHA256 checksum file | E-6-1b veya Epic 6 follow-up |
| SBOM diff per release (regression detection) | Epic 7 (performance + scalability) veya Epic 6 follow-up |

## 5. Risk + Mitigation

| Risk | Mitigation |
|---|---|
| `cyclonedx-bom` CI build time'ı uzatır | E-6-1a'da `[sbom]` extra-only; install pin'i ana CI'ya değil sadece release pipeline'a (E-6-1b) |
| Generator tool component'i SBOM'a sızar | `GENERATOR_PACKAGE_NAMES` frozenset + `validate_sbom` reject + 4 test invariant |
| Target venv install pip cache hit eder | `--no-cache-dir` flag |
| Spec version drift | `SBOM_SCHEMA_VERSION` const + `validate_sbom` reject |
| Wheel path traversal / non-wheel file | `_ensure_wheel_path` + `.whl` suffix check |
| Output path `dist/` içine yazar | CLI `parent.resolve().name == "dist"` reject + test invariant |
| Subprocess silent fail | `check=True` + `capture_output=True` + stderr decode in error message |

## 6. Acceptance

- ✅ `pytest tests/test_sbom_generation.py -x` → 14 pass + 1 skip local
- ✅ `ruff check scripts/generate_sbom.py tests/test_sbom_generation.py` clean
- ✅ `mypy scripts/generate_sbom.py --ignore-missing-imports` clean
- ✅ Plan doc bu dosya
- ⏳ Cross-AI post-impl review (Codex thread `019e8337` reply ile yeni iter veya yeni thread)
- ⏳ CI green (Test workflow + ao-release-gate — gate önkoşulu PR #793 merge'e bağlı, ayrı concern)
- ⏳ Squash merge audit trail: Implementer Anthropic Claude / Reviewer OpenAI Codex

## 7. Bağlantı

- V5 Epic 6 plan: `V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md` §3 (Epic 6
  Security + Compliance)
- HARD RULE — Cross-AI Peer Review: implementer Anthropic Claude;
  reviewer OpenAI Codex.
- HARD RULE — Uzun Vadeli Kalıcı Çözüm: minimum invariant 5 değil 9
  (generator-leak guard); script generator tool'u target venv'e
  KURULU değil; spec version pin'li.
- HARD RULE — No Fake Work: E-6-1a deliberately excludes publish.yml
  integration (Codex 8. madde absorb) — workflow change is its own
  validation surface; E-6-1b ships separately.
- HARD RULE — Continuous Autonomous Mode: PR #793 chicken-and-egg ile
  bağlantılı; ao-release-gate kendi PR'ında fail ettiği için bu PR'ın
  da CI'ı operatör action gerektirir. Plan doc bu durum için ayrı
  follow-up belgelemek yerine bağımlılık olarak işaretler.
