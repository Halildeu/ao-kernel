# v4.1.0 Release — Two-PR Plan (AO-MA-11G-2a + 11G-2b)

**Hedef:** AO-MA-SPM master plan §Faz 1-7 program tamamlanması (7/7 fazlar MERGED 2026-06-01, main `f1dc032`) sonrası v4.1.0 minor release'ini PyPI'ya yayınla. Otonom path; tek operator gate = post-merge tag push.

**Consultation:** CNS-20260601-003 · **Codex thread** `019e809a` (3 tur REVISE → AGREE)

## İki-PR neden gerekli (Codex iter-1 absorb)

`ao-release-gate` workflow PR head'deki gate kodunu değil **protected base ref**'teki gate kodunu çalıştırır (`.github/workflows/test.yml:323`). Dolayısıyla tek PR içinde `scripts/ao_release_gate_build_payload.py` allowlist'e `CHANGELOG.md` + `pyproject.toml` eklese bile, **aynı PR'ı yargılayan base-ref builder hâlâ eski allowlist'i kullanır** → `diff_scope` fail.

Bu yüzden iki PR:
- **PR-A (11G-2a)** sadece allowlist widening + governance/tests/plan. PR-A merge olduktan sonra trusted-base builder yeni allowlist'e sahip olur.
- **PR-B (11G-2b)** trusted base v4.1.0 bump + pyyaml dep + CHANGELOG release entry + version pin testleri. Artık `diff_scope` PR-B'yi otonom geçer.

## PR-A (11G-2a) — release-gate allowlist widening

**Branch:** `codex/release-gate-allowlist-widening`
**Risk:** path_sensitive_human_review tetiklenir (`scripts/ao_release_gate*.py` + `.claude/plans/...` HIGH_RISK_PATH_PATTERNS); önceki 11A/11I/11H/11F/4.6/11G slice'ları aynı pattern ile otonom mergelandi (gate satisfaction pattern doğrulanmış).

**5 dosya scope:**

1. `scripts/ao_release_gate_build_payload.py` — `DEFAULT_ALLOWED_PATH_PREFIXES` tail'e `CHANGELOG.md` + `pyproject.toml`; revize yorum (release lifecycle widening; NOT semantic approval; pyproject semantic discipline boundary)
2. `tests/test_ao_release_gate_build_payload.py` — `test_build_payload_allowed_path_prefixes_includes_release_lifecycle_files` invariant: yeni 2 path zorunlu pin + regression guard
3. `.claude/plans/RELEASE-V4-1-0.md` (bu) — iki-PR plan açıklaması
4. `local-ai-review-evidence.v1.json` — cross-AI evidence (work_package=AO-MA-11G-2A-ALLOWLIST-WIDENING, Codex 019e809a thread AGREE)
5. `.claude/plans/consultations/CNS-20260601-003.request.v1.json` — consultation kaydı

**Self-serving widening defense:** PR-A diff'i `scripts/` + `tests/` + `.claude/plans/` + `local-ai-review-evidence.v1.json` (HEPSI mevcut allowlist'te). PR kendi geçmesi için widening yapmıyor; sadece sonraki PR-B için. Base-ref trusted builder eski allowlist ile PR-A'yı judge eder, geçer.

## PR-B (11G-2b) — v4.1.0 release prep (PR-A merge sonrası)

**Branch:** `codex/release-v4-1-0`
**Risk:** normal (artık `CHANGELOG.md` + `pyproject.toml` allowlist'te)

**6 dosya scope:**

1. **`pyproject.toml`** — `dependencies` `["jsonschema>=4.23.0", "PyYAML>=6.0"]` (canonical isim); `version` `4.0.0` → `4.1.0`. **Diğer pyproject alanı (scripts, build-system, package-data, entrypoint, tool.*) değişmez** (Codex iter-2 semantic discipline)
2. **`ao_kernel/__init__.py`** — `__version__` `4.0.0` → `4.1.0`
3. **`CHANGELOG.md`** — `[Unreleased]` → `[4.1.0] - 2026-06-01` (mevcut Unreleased içeriği korunur + AO-MA-SPM §Faz 1-7 özet release notu; yeni boş `[Unreleased]` açılır)
4. **`tests/test_pr_a6_features.py`** — `4.0.0` pinleri `4.1.0` güncelle
5. **`tests/test_v410_version_pin.py`** (yeni) — `pyproject.toml::version == ao_kernel/__init__.py::__version__ == "4.1.0"` consistency pin + `PyYAML` dep presence check
6. `local-ai-review-evidence.v1.json` — cross-AI evidence (work_package=AO-MA-11G-2B-RELEASE-V4-1-0)

## Post-PR-B merge (operator-authorized tag push)

1. Primary main ff-only sync: `git fetch origin main && git merge --ff-only origin/main`
2. `git tag v4.1.0 -m "AO-MA-SPM master plan §Faz 1-7 tamamlanması (7/7 fazlar MERGED)"`
3. `git push origin v4.1.0`
4. `.github/workflows/publish.yml` `push.tags: ["v*"]` tetiklenir → environment `pypi` trusted publishing OIDC
5. PyPI sayfası: `https://pypi.org/project/ao-kernel/4.1.0/`
6. `pip install ao-kernel==4.1.0` herkese açık

## Semver kararı: 4.0.0 → 4.1.0 (minor)

6 yeni modül (notifier + run_governor + slice_evidence_registers + native_worker_import + quality_profile + plan_consensus) + 3 yeni schema family + 1 yeni CLI subcommand (`quality`) + AO-MA tracking SSOT + 5 retro ADR + ISO 25010 profile = **pure additions, breaking yok**. Public facade `AoKernelClient` imza değişmedi. Codex iter-1 doğrulama: minor doğru.

## CHANGELOG release entry içeriği (PR-B'de yazılacak)

- `[4.1.0] - 2026-06-01` başlığı
- Mevcut `[Unreleased]` içeriği (önceki PR satırları) altında yer alır
- Üstüne AO-MA-SPM §Faz 1-7 özet bölümü:
  - 11A plan consensus + tek operator approval gate
  - 11E GH-native tracking mirror (core)
  - 11I autonomous run governor (PAUSE + budget caps + safe-stop)
  - 11H notification & escalation (intent pure decide_notification)
  - 11F test/suggestion/update evidence registers (SHA-bound)
  - 4.6 native worker result import-only (live_adapter_execution=false korunur)
  - 11G SPM quality profile hardening (ADR template + ISO 25010 reference + CHANGELOG discipline)
- Yeni boş `[Unreleased]` başlığı

## Cross-AI review

Implementer: Claude (Anthropic). Reviewer: Codex (OpenAI) thread `019e809a` — plan-time iter-1 REVISE (file-count + high-risk evidence + pyproject yorum) → iter-2 REVISE (anthropic raw evidence reviewer rolü) → iter-3 AGREE ready_for_impl=true.

Post-impl review iter ile authoritative contract verify.

## Kapsam Harici (PR-A'da YOK)

- pyproject.toml + CHANGELOG.md + version bump (PR-B)
- pyyaml runtime dep (PR-B)
- tag push (operator-authorized post-PR-B)
- CI workflow changelog enforcement (ayrı 11G-2 slice)
- Pre-commit hook for changelog (ayrı 11G-2 slice)
- 4.6 native-import operator dogfooding (ayrı 11G-2 slice)
- Retro ADR cross-AI revalidation (ayrı 11G-2 slice)
- Yeni feature kodu (sadece release governance)
