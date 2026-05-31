# AO-MA-11G-1 — SPM Quality Profile Hardening (pure core)

**Faz:** AO-MA-11G (master plan §Faz 7, SON faz) · **Dilim:** AO-MA-11G-1 (pure core) · **Risk:** normal (schemas + module + CLI + ADR/profile assets; `.github`'a dokunmaz)
**Consultation:** CNS-20260601-002 · **Codex thread** `019e8050-fe36-76d1-b599-77882d3d5772` (2 tur REVISE → AGREE, ready_for_impl=true)

## Amaç

Master plan §Faz 7: "Standarda yazılmalı + sektörün en iyi uygulamaları."
- **ADR template formalize** — Markdown YAML front-matter, schema-backed,
  supersede chain consistent, retrospective ADR'ler explicit etiketli.
- **ISO/IEC 25010:2023 quality profile reference** — sertifika DEĞİL,
  8 characteristic × 35 sub-characteristic canonical set; applicable=true →
  measure_method (ci_test/coverage_gate/manual_review/code_review/
  schema_validation); applicable=false → measure_method=not_measured + rationale.
- **Keep-a-Changelog discipline** — diff-aware: `[Unreleased]` altında yeni
  bullet line VEYA chore-no-changelog rationale.

11G-1 = pure core + retro ADR + ISO profile + CHANGELOG semantik. 11G-2 = CI
enforcement wiring + operator dogfooding (4.6 native-import üzerinden
operator-produced worker_result) + retro ADR'lerin Codex+Mavis cross-AI
revalidation (review_status: cross_ai_validated).

## Mimari konum (notifier / slice_evidence_registers / native_worker_import paritesi)

`ao_kernel/orchestration/quality_profile.py` PURE compiler: no I/O, no
subprocess, no network, no LLM, no GitHub. AST import-allowlist (yaml.safe_load
+ stdlib + jsonschema) yapısal garanti. CLI thin wrapper
`ao_kernel/orchestration/quality_handlers.py` + `ao_kernel/cli.py` dispatch
(top-level `ao-kernel quality`, `orchestration` altında DEĞİL — Codex iter-2
daraltma).

## Üretilenler (15+ dosya)

- **3 schema** (Draft 2020-12, additionalProperties:false, 3 guard const false,
  register_authority="evidence_record_only", github_write_authorized=false):
  - `ao-ma-adr.schema.v1.json` — front-matter validator + retro if/then +
    supersede if/then (status=superseded ↔ superseded_by required)
  - `ao-ma-iso-25010-profile.schema.v1.json` — 8 char × 35 sub-char EXACT set;
    sub-char `applicable=true` → measure_method enum without not_measured;
    `applicable=false` → measure_method const "not_measured"; iso_25010_certified
    + certification_target + external_audit_claim hepsi const false
  - `ao-ma-changelog-discipline.schema.v1.json` — verdict {pass|fail} + 3 check
    {changelog_in_diff, unreleased_entry_added, chore_opt_out_satisfied} +
    findings
- **PURE module** `ao_kernel/orchestration/quality_profile.py`:
  - `QualityProfileError` — fatal trust-boundary exception
  - `parse_adr(adr_text, filename, *, adr_schema)` — front-matter extract +
    YAML safe_load + date normalize + schema validate + filename↔id cross-check
  - `build_adr_index(records)` — ID uniqueness + supersede chain (canonical edge:
    supersedes; reciprocal: superseded_by) + dangling/cycle/self-reference reject +
    sorted id-ascending
  - `render_adr_index_json(index)` — deterministic JSON (sort_keys + no wall clock)
  - `load_iso_25010_profile(profile, *, profile_schema)` — schema validate +
    canonical char/sub-char EXACT cross-check + applicable/measure_method consistency
  - `check_changelog_compliance(*, base_changelog_text, head_changelog_text,
    pr_diff_paths, chore_label_present, chore_rationale)` — diff-aware bullet-line
    set comparison + chore opt-out path
  - `build_changelog_verdict_artifact(verdict, *, evaluated_at, verdict_schema)` —
    schema-valid emit + RFC3339 check
  - Helpers: `_normalize_date`, `_normalize_back_populated_at`,
    `_extract_frontmatter_block`, `_safe_load_yaml`, `_detect_supersede_cycle`,
    `_slug_from_title`, `_parse_unreleased_bullets`
- **CLI handler** `ao_kernel/orchestration/quality_handlers.py` +
  `ao_kernel/cli.py` dispatch — top-level `ao-kernel quality` subparser
  (4 subcommand) + `add_quality_subparser`
- **Bundled assets:**
  - `ao_kernel/defaults/quality/iso-25010-profile.v1.json` — bizim profile
    (applicable=true: Functional 3/3, Performance Efficiency 2/3, Compatibility
    Interoperability, Interaction Capability 6/8, Reliability 3/4, Security 6/6,
    Maintainability 5/5, Flexibility Adaptability+Installability;
    applicable=false rationale ile: Performance Capacity, Compatibility Co-existence,
    Interaction Capability User Engagement+Inclusivity, Reliability Availability,
    Flexibility Scalability+Replaceability)
  - `.claude/plans/adr/template.md` (gelecek ADR'ler için)
  - `.claude/plans/adr/ADR-0001-ao-ma-spm-program-adoption.md` (retro)
  - `.claude/plans/adr/ADR-0002-fail-closed-recompute-not-trust.md` (retro)
  - `.claude/plans/adr/ADR-0003-native-import-import-only.md` (retro)
  - `.claude/plans/adr/ADR-0004-cross-ai-implementer-reviewer-distinct-provider.md` (retro)
  - `.claude/plans/adr/ADR-0005-keep-a-changelog-per-pr-discipline.md` (CURRENT — not retro)
  - `.claude/plans/adr/index.json` (deterministic id-ascending)
- **AO-MA tracking drift fix** `.claude/plans/ao_ma_status.v1.json` — 11H/11F/4.6
  slice=merged + phase=done; 11G phase=in_progress + slice=in_progress; current_*
  güncellendi
- **CHANGELOG.md entry + `pyproject.toml` pyyaml runtime dep** — DEFERRED to
  AO-MA-11G-2 governance PR. The release-gate `diff_scope` allowlist does
  not permit pyproject.toml / CHANGELOG.md edits inside the same PR that
  adds the quality module; allowlist widening + dependency declaration
  belong to a separate operator-approved governance PR. The module imports
  yaml lazily (try/except ImportError → `QualityProfileError`); ADR-related
  tests use `pytest.importorskip("yaml")` so the slice ships cleanly today
  and 11G-2 wires the dep + entry + allowlist widening together.
- **Tests:**
  - `tests/test_ao_ma_11g_quality_profile.py` (functional — parse_adr happy/negative,
    build_adr_index supersede chain + cycle + dangling, load_iso_25010_profile
    canonical set + applicable consistency, check_changelog_compliance happy/fail
    paths, build_changelog_verdict_artifact schema)
  - `tests/test_ao_ma_11g_quality_profile_purity.py` (AST allowlist — only yaml +
    stdlib + jsonschema; yaml.load/FullLoader/UnsafeLoader/yaml.unsafe_load
    rejected via attribute denylist; subprocess/socket/requests/httpx/urllib
    forbidden)
  - CLI forbidden flag pin (RI-7.8c)
- **Plan doc** (bu) + **Evidence** (`local-ai-review-evidence.v1.json`) + **CNS**
  (`.claude/plans/consultations/CNS-20260601-002.request.v1.json`)

## Fail-closed / recompute-not-trust invariant'lar

### ADR
- front-matter delimiter `^---` ilk satırda (Codex iter-2 daraltma)
- YAML date implicit-timestamp coercion → `YYYY-MM-DD` string normalize
- `back_populated_at` → RFC3339 UTC normalize
- ID pattern `^ADR-[0-9]{4}$` + filename `ADR-NNNN-<slug>.md` cross-check
- retrospective if/then: true → review_status + back_populated_at required;
  false → review_status const "original" + back_populated_at forbidden
- status=superseded ↔ superseded_by required; ≠superseded → superseded_by forbidden
- supersede chain: canonical edge `supersedes`; cycle DFS reject; self-ref reject;
  dangling target reject; reciprocal `superseded_by` mismatch reject

### ISO 25010
- schema char/sub-char EXACT set (additionalProperties:false her seviyede)
- module canonical set re-check (schema-only relaxation engellenir)
- applicable=true → measure_method ∈ {ci_test,coverage_gate,manual_review,
  code_review,schema_validation} (not_measured YASAK)
- applicable=false → measure_method const "not_measured"
- rationale minLength 10
- iso_25010_certified + certification_target + external_audit_claim hepsi const false

### CHANGELOG discipline
- diff-aware: base_bullets vs head_bullets set fark
- `## [Unreleased]` altında `### Added/Changed/Deprecated/Removed/Fixed/Security`
  altındaki bullet line'lar
- CHANGELOG.md PR diff'inde değişen path olmalı + ≥1 yeni bullet
- VEYA chore_label + rationale (minLength 10)
- heading-only / whitespace-only edit pass DEĞİL

## Self-hosting kanıtı (master plan §6 son faz)

11G-1 PR kanıtı: ADR-0001..0005 commit + parse/index valid + ISO 25010 profile
commit + schema+canonical-set valid + AO-MA tracking drift kapatma. 11G-1 PR'ı
ADR + ISO profile + changelog **discipline çekirdeği**ni (pure module + 3
schema + CLI + tests) kullanır → "uygulama kanıtı". CHANGELOG entry
dogfooding + pyyaml runtime dep + CI/pre-commit enforcement = AO-MA-11G-2
(operator-approved governance PR allowlist'i `CHANGELOG.md` + `pyproject.toml`
için genişletir).

## Cross-AI review

Implementer: Claude (Anthropic). Reviewer: Codex (OpenAI) thread `019e8050`
plan-time iter-1 REVISE (3 kritik fail-open + 12+ invariant) → iter-2 AGREE
(ready_for_impl=true, 10 ek mekanik daraltma absorb). Post-impl review iter
ile authoritative contract verify.

## Kanıt

- 50+ test PASS (functional + AST allowlist + CLI forbidden flag)
- `ao_kernel/orchestration/quality_profile.py` %85+ branch cover (gate %85+)
- 3 yeni schema Draft 2020-12 valid; ISO profile schema+canonical-set valid
- ADR-0001..0005 parse + supersede graph valid + index deterministic
- ruff + mypy strict temiz (264+ src file)
- AST import-allowlist binding guarantee (yaml.safe_load only; load/FullLoader/UnsafeLoader rejected)
- 3 guard + iso_25010_certified + certification_target + external_audit_claim const false
- `live_adapter_execution=false` korunur; `support_widening=false`; `production_platform_claim=false`

## Sonraki (AO-MA-11G-2)

- CI workflow check: PR'da changelog discipline fail → block (CI'da
  ao-kernel quality check-changelog çağrısı)
- Pre-commit hook (lokal yardımcı; release authority değil)
- 4.6 native-import dogfooding (operator claude-cli ile worker_result üretip
  11G impl'i için integrated)
- Retro ADR (0001..0004) Codex+Mavis cross-AI consensus revalidation →
  review_status: cross_ai_validated
- Yeni ADR'ler (gelecek mimari kararlar) için template usage enforcement

## 7/7 fazlar tamamlandı (post-merge)

AO-MA-11G-1 merge sonrası: 11A/11E/11I/11H/11F/4.6/11G hepsi MERGED.
AO-MA-SPM master plan §Faz 1-7 program tam tamamlanır. Sonraki sprint:
follow-up (-2) dilimleri (11A-2/11E-2/11G-2/4.6-2) operator demand-driven.
