# ST-2 — Stable Support Boundary Freeze

**Durum:** Completed on main via
[#346](https://github.com/Halildeu/ao-kernel/pull/346)
**Issue:** [#344](https://github.com/Halildeu/ao-kernel/issues/344)
**Umbrella:** [#329](https://github.com/Halildeu/ao-kernel/issues/329)
**Precondition:** `ST-1` tamamlandi; `v4.0.0-beta.2` published ve PyPI
exact pin `ao-kernel==4.0.0b2` fresh venv ile dogrulandi.
**Stable publish degil:** bu slice `4.0.0` tag veya PyPI publish yapmaz.

## 1. Amac

`4.0.0` stable oncesinde support boundary'yi dondurmak. Bu is, yeni runtime
feature eklemek degil; stable adayinda hangi yuzeylerin `shipped`, hangilerinin
`beta/operator-managed`, hangilerinin `deferred`, hangilerinin `known bug`
olarak kalacagini tek anlamli hale getirmek icindir.

Stable release ciktigi zaman kullanilacak dil:

- "dar ama kanitli governed runtime baseline"
- "genel amacli production coding automation platformu" degil
- "real adapter production-certified" degil, ancak ST-3 ayri olarak bunu
  kanitlarsa karar degisebilir

## 2. Authoritative Inputs

ST-2 kararinda asagidaki yuzeyler birlikte okunur:

| Kaynak | Rol |
|---|---|
| `docs/PUBLIC-BETA.md` | current support matrix SSOT |
| `docs/SUPPORT-BOUNDARY.md` | support boundary anlatimi |
| `docs/KNOWN-BUGS.md` | operator-relevant known bug registry |
| `docs/UPGRADE-NOTES.md` | kurulum/yukseltme dogrulama yolu |
| `docs/ROLLBACK.md` | rollback dogrulama yolu |
| `CHANGELOG.md` | release-facing claim dili |
| `.claude/plans/PRODUCTION-STABLE-LIVE-ROADMAP.md` | stable gate sirasi |
| `scripts/packaging_smoke.py` | wheel-installed shipped smoke |
| `scripts/truth_inventory_ratchet.py` | extension truth inventory snapshot |

`docs/PUBLIC-BETA.md` ile diger dokumanlar ayrisirsa
`docs/PUBLIC-BETA.md` kazanir; ST-2'nin isi bu ayrismayi ortadan kaldirmaktir.

## 3. Stable Shipped Candidate Matrix

Bu tablo, stable candidate'a girebilecek dar shipped yuzeyi temsil eder. Her
satir ST-2 sirasinda tekrar dogrulanir; kanit eksikse satir stable shipped
claim'inden cikar veya ST-2 blocker olarak isaretlenir.

| Yuzey | Kod/kontrat kaynagi | Test/smoke kaniti | Stable karari |
|---|---|---|---|
| CLI/module version entrypoint'leri | `ao_kernel/cli.py`, `ao_kernel/__main__.py` | `tests/test_cli_entrypoints.py`, `scripts/packaging_smoke.py` | Shipped candidate |
| `ao-kernel doctor` | `ao_kernel/doctor_cmd.py` | `tests/test_doctor_cmd.py`, `tests/test_cli.py`, `tests/test_client.py`, `python3 -m ao_kernel doctor` | Shipped candidate; WARN truth inventory blocker degil |
| `review_ai_flow` + `codex-stub` | `ao_kernel/defaults/workflows/review_ai_flow.v1.json`, `ao_kernel/defaults/adapters/codex-stub.manifest.v1.json`, `ao_kernel/fixtures/codex_stub.py` | `examples/demo_review.py`, `tests/benchmarks/test_governed_review.py`, `scripts/packaging_smoke.py` | Shipped candidate |
| `examples/demo_review.py` | `examples/demo_review.py` | wheel-installed run inside `scripts/packaging_smoke.py` and PyPI post-publish verify | Shipped candidate only when run with installed package Python |
| `PRJ-KERNEL-API` read-only actions | `ao_kernel/extensions/handlers/prj_kernel_api.py` | `tests/test_extension_dispatch.py` | Shipped candidate for `system_status` and `doc_nav_check` only |
| Adapter CLI command enforcement | `ao_kernel/executor/executor.py`, `ao_kernel/executor/policy_enforcer.py`, `ao_kernel/executor/adapter_invoker.py` | `tests/test_executor_policy_rollout_v311_p2.py`, `tests/test_executor_policy_enforcer.py`, `tests/test_executor_adapter_invoker.py`, `tests/test_executor_integration.py` | Shipped candidate |
| Release gate / packaging trust | `.github/workflows/test.yml`, `.github/workflows/publish.yml`, `scripts/packaging_smoke.py` | CI `packaging-smoke`, PyPI `v4.0.0-beta.2` publish verify | Shipped release gate, not runtime feature |
| Coverage gate | `pyproject.toml`, `.github/workflows/test.yml` | CI coverage `--fail-under=85` | Shipped quality gate, not runtime feature |

## 4. Stable-Dışı Tutulacak Yüzeyler

Bu tablo ST-2 boyunca varsayilan karar tablosudur. Promote etmek isteyen PR,
bu tabloyu ancak yeni kanitla degistirebilir.

| Yuzey | Mevcut tier | Neden stable shipped degil |
|---|---|---|
| `claude-code-cli` helper-backed lane | Beta, operator-managed | PATH binary + operator auth + prompt access prerequisite gerektirir; production-certified adapter failure-mode matrisi henuz stable gate degil |
| `gh-cli-pr` preflight/live-write readiness probe | Beta, operator-managed / deferred live opening | Live-write disposable sandbox + rollback kaniti olmadan remote PR opening shipped claim olamaz |
| `PRJ-KERNEL-API` write-side actions | Beta, operator-managed write contract | Gercek yazma explicit `confirm_write=I_UNDERSTAND_SIDE_EFFECTS` ister; stable shipped read-only yuzeyden ayridir |
| Real-adapter benchmark tam modu | Beta, operator-managed | Deterministik CI baseline degil; ortam/auth/prerequisite bagimli |
| `bug_fix_flow` release closure | Deferred | `open_pr` side-effect guard'i var ama workflow-level promoted support ve rollback zinciri yok |
| `docs/roadmap/DEMO-SCRIPT-SPEC.md` 11 adimli akis | Deferred/spec-only | Canli demo kontrati degil |
| Adapter-path `cost_usd` reconcile public claim | Deferred | Internal benchmark/runtime hook varligi public support claim icin yeterli degil |
| Bundled extension inventory geneli | Contract inventory | Manifest/loader/truth audit varligi end-to-end support claim uretmez |

## 5. Known Bug Gate

Stable support boundary icin known bug karari:

| ID | Surface | Stable blocker? | ST-2 karari |
|---|---|---|---|
| `KB-001` | `claude-code-cli` beta lane prompt access | Hayir, shipped baseline disi | Known bug registry'de kalir |
| `KB-002` | `claude-code-cli` token fallback | Hayir, shipped baseline disi | Known bug registry'de kalir |

ST-2 sirasinda shipped baseline'i bozan yeni bug bulunursa:

1. `docs/KNOWN-BUGS.md` icine eklenir.
2. Stable release blocker olarak isaretlenir.
3. `ST-2` tamamlanmaz; fix veya stable scope daraltma karari gerekir.

## 5.1 Freeze Decision

Freeze PR karari:

1. Stable candidate support set, `docs/PUBLIC-BETA.md` icindeki `Shipped`
   tablosuyla sinirli kalir.
2. Current known bugs shipped baseline'i bloklamaz; ikisi de
   `claude-code-cli` operator-managed beta lane'leriyle sinirlidir.
3. `ST-3` real-adapter certification dar stable runtime release icin blocker
   degildir, cunku real adapter lane'leri stable shipped claim'e alinmiyor.
4. `ST-4` live-write rollback rehearsal dar stable runtime release icin blocker
   degildir, cunku live-write / remote side-effect yuzeyleri stable shipped
   claim'e alinmiyor.
5. Gelecekte `claude-code-cli`, `gh-cli-pr`, kernel API write-side actions,
   real-adapter benchmark tam modu veya `bug_fix_flow` release closure stable'a
   promote edilmek istenirse ST-3/ST-4 tarzi yeni kanit gate'i zorunlu olur.

## 5.2 Closeout Evidence

`ST-2` closeout:

1. Freeze implementation PR: [#346](https://github.com/Halildeu/ao-kernel/pull/346)
2. Merge commit: `a7e010d`
3. CI: lint, typecheck, test matrix, coverage, benchmark-fast,
   packaging-smoke and scorecard all green.
4. Local validation:
   - `git diff --check`
   - `python3 -m pytest -q tests/test_cli_entrypoints.py tests/test_doctor_cmd.py tests/test_cli.py tests/test_client.py`
   - `python3 -m pytest -q tests/test_extension_dispatch.py`
   - `python3 -m pytest -q tests/test_executor_policy_enforcer.py tests/test_executor_adapter_invoker.py tests/test_executor_policy_rollout_v311_p2.py tests/test_executor_integration.py`
   - `python3 -m pytest -q tests/benchmarks/test_governed_review.py tests/benchmarks/test_governed_bugfix.py`
   - `python3 scripts/truth_inventory_ratchet.py --output json > /tmp/ao-kernel-st2-truth.json`
   - `python3 -m ao_kernel doctor`
   - `python3 scripts/packaging_smoke.py`
5. Outcome: stable candidate boundary is frozen to the shipped baseline only.
   Known bugs remain beta-lane issues and do not block the narrow stable
   runtime claim.

## 6. Exact File List

ST-2 contract PR'i:

| Dosya | Karar sorusu |
|---|---|
| `.claude/plans/ST-2-STABLE-SUPPORT-BOUNDARY-FREEZE.md` | Gate, matrix, risk ve DoD yazili mi? |
| `.claude/plans/POST-BETA-CORRECTNESS-EXPANSION-STATUS.md` | Aktif issue/contract `ST-2`ye gecti mi? |
| `.claude/plans/PRODUCTION-STABLE-LIVE-ROADMAP.md` | ST-2 active olarak gorunuyor mu? |

ST-2 implementation/freeze PR'i:

| Dosya | Karar sorusu |
|---|---|
| `docs/PUBLIC-BETA.md` | Stable candidate support matrix tek anlamli mi? |
| `docs/SUPPORT-BOUNDARY.md` | Narrative boundary matrix ile ayni mi? |
| `docs/KNOWN-BUGS.md` | Shipped baseline blocker yoksa acikca yaziyor mu? |
| `docs/UPGRADE-NOTES.md` | Stable/beta dogrulama komutlari support boundary ile ayni mi? |
| `docs/ROLLBACK.md` | Stable ve beta rollback yolu support boundary ile ayni mi? |
| `CHANGELOG.md` | `Unreleased` stable-boundary freeze notu gerekiyorsa eklendi mi? |

## 7. Validation Plan

Contract PR minimum:

```bash
git diff --check
```

Freeze PR minimum:

```bash
git diff --check
python3 -m pytest -q tests/test_cli_entrypoints.py tests/test_doctor_cmd.py tests/test_cli.py tests/test_client.py
python3 -m pytest -q tests/test_extension_dispatch.py
python3 -m pytest -q tests/test_executor_policy_enforcer.py tests/test_executor_adapter_invoker.py tests/test_executor_policy_rollout_v311_p2.py tests/test_executor_integration.py
python3 -m pytest -q tests/benchmarks/test_governed_review.py
python3 scripts/packaging_smoke.py
python3 scripts/truth_inventory_ratchet.py --output json
python3 -m ao_kernel doctor
```

Full CI must pass before merge. Stable release still requires later ST gates.

## 8. Risks

| Risk | Etki | Mitigation |
|---|---|---|
| Support widening by wording | Stable kullaniciya fazla vaat verir | PUBLIC-BETA SSOT + shipped evidence matrix |
| Fake shipped claim | Test/smoke olmayan yuzey stable'a girer | Her shipped satir kod + test/smoke + docs baglantisi ister |
| Real adapter overclaim | Operator-auth lane production-certified gibi gorunur | `operator-managed beta` dili korunur; ST-3 ayri gate |
| Live-write overclaim | Remote side-effect shipped gibi gorunur | ST-4 olmadan live-write stable'a girmez |
| Known bug under-reporting | Stable blocker sakli kalir | Known bug gate shipped baseline'a etkisini zorunlu sorar |

## 9. Exit Criteria

`ST-2` completed sayilmasi icin:

1. Contract PR merge edilir.
2. Freeze PR merge edilir.
3. `docs/PUBLIC-BETA.md`, `docs/SUPPORT-BOUNDARY.md`, `docs/KNOWN-BUGS.md`,
   `docs/UPGRADE-NOTES.md`, `docs/ROLLBACK.md` ayni support boundary'yi
   anlatir.
4. Her shipped candidate satiri kod/test/smoke/docs kanitina baglanir.
5. Stable blocker known bug yoktur veya stable scope daraltma karari yazilir.
6. ST-3 ve ST-4'un gerekli olup olmadigi acik karar olarak cikar.
7. Issue [#344](https://github.com/Halildeu/ao-kernel/issues/344) closeout
   comment ile kapatilir.
