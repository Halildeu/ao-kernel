# Policy Command Enforcement Closure — Program Plan

**Durum:** Faz 1-3 implemented in branch, verification passed
**Onay tarihi:** 2026-04-20
**Plan sahibi:** Codex
**Yürütme modu:** Kapsam disiplini
**Motto:** Önce destek yüzeyini daralt, sonra onu ispatla, en son genişlet.

## 1. Yönetici Özeti

Bu program planı, `ao-kernel` içinde policy command enforcement ile ilgili
runtime, dokümantasyon ve test drift'ini kontrollü biçimde kapatmak için
hazırlanmıştır.

Sorunun özü feature eksikliği değildir. Ana problem, şu üç yüzeyin aynı
gerçeği söylememesidir:

1. runtime'da gerçekten çalışan enforcement kapsamı
2. operator-facing docs ve bundled policy yorumlarının vaat ettiği kapsam
3. CI/test katmanının gerçekten pinlediği semantik

Bu planın hedefi, `ao-kernel`'i **governed AI orchestration runtime** olarak
stabilize etmektir. Bu plan, ürünü "general-purpose production coding
automation platform"a genişletme planı değildir.

## 2. Problem Beyanı

Bugün stable hatta şu drift doğrulanmıştır:

- Adapter CLI yolunda command allowlist enforcement runtime'a bağlı değildir.
- Doküman ve policy comment'leri command enforcement'ı live gibi anlatır.
- Rollout testi kritik governance semantiğini yeterince pinlemez.

Doğrulanan başlıca finding seti:

- **P1** Adapter CLI path command allowlist bypass
- **P2** WORKTREE-PROFILE rollout anlatımı runtime'dan ileri
- **P3** rollout/dry-run testleri davranışsal pin yerine zayıf assertion kullanıyor
- **P1** `sys.executable` için sandbox-global allowlist istisnası kabul edilemez
- **P2** `policy_checked` event'i validation sonrası emit edilmelidir

## 3. Authoritative Baseline

Karar verirken aşağıdaki gerçeklik sırası kullanılacaktır:

1. **Stable truth:** `origin/main` üzerindeki `v3.13.2`
2. **Prepared closure line:** `.claude/worktrees/codex-v3133`
3. **Stale local drift:** local `main` yalnız inceleme için referans olabilir; ürün kararı için kaynak değildir

Stable support surface:

- bundled `review_ai_flow`
- bundled `codex-stub`
- `examples/demo_review.py`
- CLI/module entrypoint contract
- evidence timeline + review artifact materialization

## 4. Kapsam

### 4.1 Kapsam İçi

- `v3.13.3` truth-and-tests patch
- `v4.0.0b1` runtime command enforcement closure
- wheel-install packaging smoke gate
- Public Beta support matrix cleanup

### 4.2 Kapsam Dışı

- `bug_fix_flow` release closure
- real-adapter tam production garantisi
- OS-level sandbox / egress enforcement
- full PR automation surface
- post-beta correctness patch seti:

## 5. Değişmez Kurallar

Bu program boyunca aşağıdaki kurallar ihlal edilmeyecek:

1. `sys.executable` hiçbir policy için sandbox-wide allowlist istisnası olmayacak.
2. `{python_executable}` yalnız explicit reserved token kullanımı için, yalnız resolved interpreter realpath'i seviyesinde lokal override alabilecek.
3. `policy_checked` event'i command validation tamamlandıktan sonra emit edilecek.
4. Canonical event sırası korunacak:
   `step_started -> policy_checked -> policy_denied? -> adapter_invoked`
5. `enabled=false`, `report_only`, `block` rollout semantiği korunacak.
6. Editable install başarı kabul edilmeyecek; wheel-only smoke release gerçeği sayılacak.
7. Aynı yüzey bir anda hem `Shipped` hem `Beta`, ya da hem `Beta` hem `Deferred` olarak sınıflandırılmayacak.

## 6. Faz Yol Haritası

### Faz 1 — Truth Patch (`v3.13.3`)

**Amaç:** Runtime semantiğini değiştirmeden yanlış güveni kaldırmak.

**Çıktılar**

- Stable operator docs parity
- Bundled policy note parity
- Rollout/dry-run behavioral tests güçlendirmesi
- Coverage gate parity doğrulaması

**Hedef yüzeyler**

- `docs/WORKTREE-PROFILE.md`
- `docs/BENCHMARK-REAL-ADAPTER-RUNBOOK.md`
- `docs/ADAPTERS.md`
- `docs/EVIDENCE-TIMELINE.md`
- `docs/METRICS.md`
- `ao_kernel/defaults/policies/policy_worktree_profile.v1.json`
- `tests/test_executor_policy_rollout_v311_p2.py`

**Faz 1 mesajı**

Stable gövdede live enforcement kapsamı:

- secret resolution
- sandbox shaping
- HTTP header exposure check

Stable gövdede henüz live OLMAYAN:

- adapter CLI command preflight

### Faz 2 — Runtime Closure (`v4.0.0b1`)

**Amaç:** Adapter CLI command enforcement'ı gerçek runtime davranışına dönüştürmek.

**Çıktılar**

- shared CLI resolver
- executor command validation wiring
- localized `{python_executable}` exception
- `policy_checked` ordering fix
- command rollout matrix tests
- narrow allowlist integration repro

**Referans implementasyon kaynağı**

- `.claude/worktrees/codex-v3133/ao_kernel/executor/executor.py`
- `.claude/worktrees/codex-v3133/ao_kernel/executor/policy_enforcer.py`
- `.claude/worktrees/codex-v3133/tests/test_executor_policy_rollout_v311_p2.py`

### Faz 3 — Release Discipline (`v4.0.0b1`)

**Amaç:** Runtime closure'ı gerçek paketleme koşulunda release gate'e bağlamak.

**Çıktılar**

- wheel-install packaging smoke script
- blocking `test.yml` job
- publish öncesi `publish.yml` smoke
- Public Beta support matrix cleanup

### Faz 4 — Post-Beta Correctness

**Amaç:** Bu planın dışında bırakılan correctness borçlarını ayrı hatta eritmek.

**Çıktılar**

- correctness backlog görünür takibi
- beta-blocking olmayan bug'lar için ayrı yürütme

## 7. İş Paketleri ve Takip Tablosu

| ID | İş Paketi | Faz | Hedef Sürüm | Durum | Bağımlılık | Kanıt |
|---|---|---|---|---|---|---|
| `WP-1` | Stable docs parity | Faz 1 | `v3.13.3` | Completed in branch | — | doc diff + review |
| `WP-2` | Bundled policy note parity | Faz 1 | `v3.13.3` | Completed in branch | `WP-1` | policy JSON diff |
| `WP-3` | Rollout/dry-run behavioral tests | Faz 1 | `v3.13.3` | Completed in branch | — | pytest output |
| `WP-4` | Coverage gate parity | Faz 1 | `v3.13.3` | Verified in baseline | — | `origin/main` parity check |
| `WP-5` | Shared CLI resolver (`ResolvedCliInvocation`) | Faz 2 | `4.0.0b1` | Completed in branch | Faz 1 | code diff + tests |
| `WP-6` | Executor command validation wiring | Faz 2 | `4.0.0b1` | Completed in branch | `WP-5` | integration repro |
| `WP-7` | Localized `{python_executable}` exception | Faz 2 | `4.0.0b1` | Completed in branch | `WP-5` | unit tests |
| `WP-8` | `policy_checked` ordering fix | Faz 2 | `4.0.0b1` | Completed in branch | `WP-6` | event-order tests |
| `WP-9` | Command rollout matrix tests | Faz 2 | `4.0.0b1` | Completed in branch | `WP-6` | pytest output |
| `WP-10` | Narrow-allowlist integration repro | Faz 2 | `4.0.0b1` | Completed in branch | `WP-6` | deny repro |
| `WP-11` | Packaging smoke script | Faz 3 | `4.0.0b1` | Completed in branch | Faz 2 | smoke log |
| `WP-12` | Blocking CI packaging smoke | Faz 3 | `4.0.0b1` | Completed in branch | `WP-11` | CI workflow |
| `WP-13` | Publish pre-smoke | Faz 3 | `4.0.0b1` | Completed in branch | `WP-11` | publish workflow |
| `WP-14` | `PUBLIC-BETA.md` classification cleanup | Faz 3 | `4.0.0b1` | Completed in branch | Faz 2 | doc audit |
| `WP-15` | `sanitize.py:39` | Faz 4 | post-beta | Completed in branch | — | unit test + doc cleanup |
| `WP-16` | `compiler.py:139` | Faz 4 | post-beta | Completed in branch | — | unit test + doc cleanup |
| `WP-17` | `init_cmd.py:30-33` | Faz 4 | post-beta | Completed in branch | — | init override tests + doc cleanup |
| `WP-18` | `bug_fix_flow + codex-stub patch_preview` | Faz 4 | post-beta | Deferred | — | future patch |
| `WP-19` | deterministic test hygiene / time drift | Faz 4 | post-beta | Partial blocker absorbed in branch | — | full-suite verification |

## 8. Risk Register

| ID | Risk | Olasılık | Etki | Azaltım | Tetikleyici |
|---|---|---:|---:|---|---|
| `R1` | Stable docs yine runtime'dan ileri konuşur | Orta | Yüksek | Faz 1 truth patch + review | operator docs mismatch |
| `R2` | `sys.executable` sandbox-wide istisna olarak sızar | Orta | Yüksek | localized override kuralı | allowlist bypass repro |
| `R3` | `policy_checked` audit semantiği bozulur | Orta | Yüksek | validation sonrası emit + ordering tests | `violations_count=0` ama deny var |
| `R4` | Editable install sahte yeşil verir | Yüksek | Yüksek | wheel-only smoke | repo içi test geçer, wheel kırılır |
| `R5` | rollout modes regression alır | Orta | Yüksek | behavioral matrix tests | dormant/report_only/block divergence |
| `R6` | Beta/stable support matrix karışır | Orta | Orta | `PUBLIC-BETA.md` SSOT | aynı yüzey çoklu kategori |
| `R7` | Worktree çözümü yanlış/stale bazdan taşınır | Düşük | Yüksek | selective port from current main | unexpected merge drift |
| `R8` | Görünmez post-beta debt tekrar stable'a sızar | Orta | Orta | explicit deferred list | roadmap creep |

## 9. Başarı Kriterleri

Plan başarılı sayılabilmesi için aşağıdakilerin tamamı sağlanmalıdır:

1. Stable dokümanlar live runtime'dan ileri konuşmaz.
2. `exact=['git'], prefixes=[]` altında CLI adapter command'i deny olur.
3. `policy_checked.violations_count` command violation'ı da içerir.
4. `policy_checked` validation sonrası emit edilir.
5. `{python_executable}` yalnız explicit token kullanımında lokal istisna alır.
6. Built wheel ile clean venv smoke geçer.
7. Repo dışı temp cwd'de `examples/demo_review.py --cleanup` geçer.
8. Support matrix tek anlamlıdır; aynı yüzey çifte kategori taşımaz.

## 10. Definition of Done (DoD)

### 10.1 İş Paketi Seviyesi DoD

Bir iş paketi tamamlandı sayılabilmesi için:

1. Kod/doküman değişikliği yapılmış olmalı.
2. İlgili test veya smoke kanıtı üretilmiş olmalı.
3. Kapsam dışı yüzeylere sessiz semantik sızma olmamalı.
4. İlgili plan satırının durum alanı güncellenebilir hale gelmiş olmalı.

### 10.2 Faz Seviyesi DoD

**Faz 1 DoD**

- docs/policy yorumları stable runtime gerçeğiyle hizalı
- rollout/dry-run testleri davranışsal
- runtime semantiği intentionally değişmeden kalmış

**Faz 2 DoD**

- command validation adapter CLI yolunda live
- global interpreter injection yok
- event order doğru
- rollout semantics korunmuş

**Faz 3 DoD**

- packaging smoke blocking gate
- publish öncesi smoke tekrar koşuyor
- Public Beta support matrix temiz

### 10.3 Release Seviyesi DoD

`v4.0.0b1` release adayı ancak şu durumda hazır sayılır:

- Faz 1, Faz 2 ve Faz 3 DoD tamam
- CI yeşil
- packaging smoke yeşil
- support matrix ve changelog güncel
- deferred list görünür ve dürüst

## 11. Go / No-Go Gates

Aşağıdaki durumlardan biri varsa release yapılmaz:

1. Command validation docs'ta live, runtime'da yok.
2. `policy_checked` command ihlallerini saymıyor.
3. `sys.executable` policy-wide bypass yaratıyor.
4. Packaging smoke editable install'a dayanıyor.
5. `PUBLIC-BETA.md` aynı yüzeyi hem `Beta` hem `Deferred` gösteriyor.
6. README/support docs desteklenmeyen demo yüzeyi öneriyor.

## 12. Yürütme Kuralı

Her yeni iş başlamadan önce şu sınıflandırma zorunludur:

- truth patch
- runtime closure
- release discipline
- post-beta correctness
- scope creep

İlk dört sınıftan birine girmeyen iş aktif kapsama alınmaz.

## 13. Onay Kaydı

Bu plan kullanıcı onayı ile yürürlüğe alınmıştır.

**Onay durumu:** Approved
**Sonraki adım:** Faz 1 backlog'unu uygulanabilir sıraya indirmek

## 14. Faz 1 Yürütme Kaydı

Bu plan dosyasının bulunduğu branch, Faz 1 truth patch uygulamasını taşır.

**Gerçekleşen işler**

- Stable docs parity branch içinde uygulanmış durumda
- Bundled policy JSON note parity branch içinde uygulanmış durumda
- Rollout/dry-run behavioral assertions güçlendirildi
- `v3.13.2 -> v3.13.3` version bump + changelog girişi eklendi

**Doğrulama kanıtı**

- `pytest tests/test_executor_policy_rollout_v311_p2.py tests/test_cli_entrypoints.py tests/test_pr_a6_features.py -q`
  - sonuç: `17 passed, 1 skipped`
- `python3 examples/demo_review.py --cleanup`
  - sonuç: `final state: completed`

## 15. Faz 2-3 Yürütme Kaydı

Bu branch, prepared closure line'daki runtime command enforcement çözümünü
clean rebased worktree üzerine selective port ile taşır ve packaging gate'i
aktif eder.

**Gerçekleşen işler**

- Shared CLI resolver (`ResolvedCliInvocation`) aktive edildi
- Executor adapter CLI command validation wiring'i canlı hale getirildi
- `{python_executable}` istisnası sandbox-global değil, invocation-local hale getirildi
- `policy_checked` event'i command validation sonrasına taşındı
- Rollout matrix testleri command violations için genişletildi
- Narrow allowlist altında deny ve localized override path'leri pinlendi
- `scripts/packaging_smoke.py` eklendi
- `test.yml` blocking packaging-smoke job ile güncellendi
- `publish.yml` publish öncesi packaging smoke koşacak şekilde güncellendi
- `docs/PUBLIC-BETA.md` ve operator docs `v4.0.0b1` live surface ile hizalandı
- `3.13.3 -> 4.0.0b1` version bump + changelog girişi eklendi
- Full-suite doğrulamada yakalanan `memory_tiers` zaman drift blocker'ı absorbe edildi:
  - `classify_tier(..., now=...)` / `enforce_tier_budgets(..., now=...)` deterministic hale getirildi
  - `tests/test_memory_tiers.py` sabit referans zaman ile pinlendi

**Doğrulama kanıtı**

- `pytest tests/test_executor_adapter_invoker.py tests/test_executor_policy_enforcer.py tests/test_executor_policy_rollout_v311_p2.py tests/test_executor_integration.py tests/test_cli_entrypoints.py tests/test_pr_a6_features.py tests/test_cli.py -q`
  - sonuç: `83 passed, 1 skipped`
- `python3 examples/demo_review.py --cleanup`
  - sonuç: `final state: completed`
- `pytest tests/benchmarks -q`
  - sonuç: `15 passed, 1 skipped`
- `python3 scripts/packaging_smoke.py`
  - sonuç: wheel build + fresh venv + 3 CLI entrypoint + repo dışı `demo_review.py` smoke geçti
- `pytest tests/ --ignore=tests/benchmarks --cov=ao_kernel --cov-branch --cov-report=term-missing && coverage report --fail-under=85`
  - sonuç: `2756 passed, 1 skipped`, toplam coverage `%86`, gate geçti

**Açık kalan sonraki adım**

- Branch clean-up, commit, PR ve CI üzerinden merge/publish kararı
