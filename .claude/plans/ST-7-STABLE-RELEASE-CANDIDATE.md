# ST-7 — Stable Release Candidate

**Durum:** Completed on `main` via issue
[#355](https://github.com/Halildeu/ao-kernel/issues/355), contract PR
[#356](https://github.com/Halildeu/ao-kernel/pull/356), and implementation PR
[#357](https://github.com/Halildeu/ao-kernel/pull/357).
**Umbrella:** [#329](https://github.com/Halildeu/ao-kernel/issues/329)
**Precondition:** `ST-6` completed via
[#354](https://github.com/Halildeu/ao-kernel/pull/354).

## 1. Amaç

`4.0.0` stable release candidate PR'ını hazırlanabilir hale getirmek. Bu gate
stable tag veya PyPI publish yapmaz; yalnızca final aday PR'ının dosya
kapsamını, karar sorularını ve kanıt paketini kilitler.

## 2. Scope Boundary

ST-7 stable support'u genişletmez. Stable candidate yalnız mevcut narrow
shipped baseline için hazırlanır:

1. CLI/module entrypoint'ler.
2. `ao-kernel doctor`.
3. `review_ai_flow + codex-stub`.
4. `examples/demo_review.py`.
5. policy command enforcement.
6. wheel-installed packaging smoke.
7. documented read-only kernel API actions.

`claude-code-cli`, `gh-cli-pr`, write-side kernel API actions, real-adapter
benchmark full mode ve deferred lanes stable support'a promote edilmez.

## 3. Exact File List

Stable candidate implementation PR'ı yalnız şu yüzeyleri değiştirebilir:

| Dosya | Karar sorusu |
|---|---|
| `pyproject.toml` | package version `4.0.0` olacak mı? |
| `ao_kernel/__init__.py` | runtime version `4.0.0` ile hizalı mı? |
| `CHANGELOG.md` | `[4.0.0]` entry stable boundary'yi doğru anlatıyor mu? |
| `README.md` | stable install quick-start pre-release dilinden ayrıldı mı? |
| `docs/PUBLIC-BETA.md` | beta dokümanı stable claim üretmeden `4.0.0` sonrası rolünü koruyor mu? |
| `docs/SUPPORT-BOUNDARY.md` | shipped/beta/deferred boundary stable aday için değişmeden duruyor mu? |
| `docs/UPGRADE-NOTES.md` | stable install ve verification komutları exact package/fresh venv yolunu anlatıyor mu? |
| `docs/OPERATIONS-RUNBOOK.md` | release readiness gates `4.0.0` adayına uygulanabilir mi? |
| `docs/ROLLBACK.md` | bad stable publish / yank / fix-forward kararı yeterli mi? |
| `docs/KNOWN-BUGS.md` | shipped baseline blocker var mı sorusu cevaplı mı? |
| `.claude/plans/*STATUS*.md` ve bu contract | program status `ST-7` sonucu ile hizalı mı? |

Bu liste dışı runtime değişiklikleri ST-7'de yapılmaz. Runtime blocker çıkarsa
stable candidate durur ve ayrı bugfix PR açılır.

## 4. Release Candidate Validation Bundle

ST-7 implementation PR'ı merge edilmeden önce aşağıdaki kanıt paketi gerekir:

```bash
git diff --check
python3 -m ao_kernel doctor
python3 scripts/packaging_smoke.py
```

Raw `python3 examples/demo_review.py --cleanup` is valid only when the current
Python environment already has `ao-kernel` installed. It is not standalone
release evidence from an uninstalled source checkout because the demo switches
into a disposable temp workspace before running `python -m ao_kernel init`.
`scripts/packaging_smoke.py` is the authoritative release gate because it
builds the wheel, installs it into a fresh venv, and then runs the installed
demo path.

CI tarafında ayrıca şunlar yeşil olmalıdır:

1. `lint`
2. Python `test` matrix
3. `coverage`
4. `typecheck`
5. `benchmark-fast`
6. `packaging-smoke`
7. `scorecard` advisory result

Stable publish'e geçmeden önce, tag workflow dışında ayrıca fresh venv exact
install verification planı hazırlanır. Bu doğrulama `ST-8` publish gate'inde
koşar; ST-7 bunu yalnız checklist olarak hazırlar.

## 5. Release Blockers

Aşağıdakilerden biri varsa `4.0.0` release candidate merge edilmez:

1. `KNOWN-BUGS.md` içinde shipped baseline'ı etkileyen açık blocker var.
2. `docs/PUBLIC-BETA.md`, `README.md` veya `SUPPORT-BOUNDARY.md` beta/deferred
   lane'i stable gibi anlatıyor.
3. `scripts/packaging_smoke.py` wheel-installed demo yolunda fail ediyor.
4. `ao-kernel doctor` shipped baseline için `FAIL` üretiyor.
5. Version değeri `pyproject.toml`, `ao_kernel/__init__.py`, CLI çıktısı ve
   changelog arasında ayrışıyor.
6. Publish workflow release gate'leri `test.yml` ile aynı smoke kontratını
   taşımıyor.

## 6. Out of Scope

- `v4.0.0` tag push.
- PyPI publish.
- GitHub release yayını.
- Support widening.
- Real-adapter production certification.
- Live-write remote PR opening.

## 7. Done Definition

ST-7 tamamlandığında:

1. `4.0.0` stable candidate PR'ı merge edilmiştir.
2. Version/changelog/docs aynı stable boundary'yi anlatır.
3. Full CI ve local validation bundle geçmiştir.
4. `ST-8` stable publish gate'i için public post-publish verification sırası
   açık kalmıştır.
5. `pip install ao-kernel` için stable live iddiası hâlâ yapılmamıştır; bu
   iddia yalnız `ST-8` publish ve public install verify sonrası yapılır.

## 8. Implementation Result

ST-7 implementation PR'i `4.0.0` source candidate hazırladı:

1. `pyproject.toml` ve `ao_kernel/__init__.py` version değerleri `4.0.0` oldu.
2. `CHANGELOG.md` `[4.0.0]` entry'si narrow stable boundary'yi açık yazıyor.
3. README ve support docs stable install dilini beta/pre-release dilinden
   ayırır.
4. Public package live claim'i yapılmaz; tag/publish/post-publish verify
   `ST-8` kapsamındadır.
5. Support widening yapılmaz.
6. PR CI gate'leri yeşil kapandı: test matrix, coverage, benchmark-fast,
   packaging-smoke, scorecard.
