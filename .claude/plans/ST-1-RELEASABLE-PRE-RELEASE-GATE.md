# ST-1 — Releasable Pre-Release Gate (`4.0.0b2`)

**Durum:** Active
**Issue:** [#340](https://github.com/Halildeu/ao-kernel/issues/340)
**Umbrella:** [#329](https://github.com/Halildeu/ao-kernel/issues/329)
**Hedef pre-release:** package version `4.0.0b2`, git tag
`v4.0.0-beta.2`
**Stable hedefi degil:** bu slice `4.0.0` stable publish yapmaz.

## 1. Amac

Current `main`, public tag `v4.0.0-beta.1` sonrasinda ilerledi. `ST-1`in
amacı bu ilerlemeyi yeni bir kanitli pre-release gate'e cevirmektir. Bu gate
stable'a dogrudan gecis degil; stable oncesi fresh wheel, CI, docs ve PyPI
pre-release gercegini tekrar kanitlama adimidir.

## 2. Current Baseline

- `main` `origin/main` ile senkron baslamali.
- Current package metadata `4.0.0b1` gosteriyor:
  - `pyproject.toml`
  - `ao_kernel/__init__.py`
- Son public pre-release tag'i `v4.0.0-beta.1`.
- `ST-0` kapandi:
  - production stable roadmap eklendi
  - GP-2.2 closeout verdict yazildi
  - Public Beta stable kanal dili hard-code exact stable version tasimiyor
- Support boundary degismedi:
  - shipped baseline dar
  - real adapter lane'leri operator-managed beta
  - adapter-path `cost_usd` reconcile public support claim olarak deferred

## 3. Kapsam

`ST-1` iki PR'a ayrilir:

1. **Contract PR** — bu dosya ve status/roadmap baglantilari.
2. **Release PR** — version bump, changelog/release notes, docs pin update,
   local smoke ve CI kaniti.

Bu ayrim bilerek yapilir: release PR'i baslamadan once gate net olmalidir.

## 4. Release PR Exact File List

`4.0.0b2` release PR'inda beklenen dosya listesi:

| Dosya | Karar sorusu |
|---|---|
| `pyproject.toml` | Package version `4.0.0b1 -> 4.0.0b2` olacak mi? |
| `ao_kernel/__init__.py` | `__version__` package version ile birebir ayni mi? |
| `CHANGELOG.md` | `[4.0.0b2] - <date>` entry'si beta.1 sonrasi kapanan PR/gate'leri dogru ozetliyor mu? |
| `docs/PUBLIC-BETA.md` | Public Beta pin `4.0.0b2` olarak guncellendi mi; support boundary genislemedi mi? |
| `docs/UPGRADE-NOTES.md` | Explicit beta install pin `4.0.0b2` oldu mu? |
| `docs/ROLLBACK.md` | Documented beta rollback pin `4.0.0b2` oldu mu; stable rollback komutu hard-code stable version yazmiyor mu? |
| `.claude/plans/POST-BETA-CORRECTNESS-EXPANSION-STATUS.md` | ST-1 release PR durumu, issue/PR ve kanitlar isleniyor mu? |
| `.claude/plans/PRODUCTION-STABLE-LIVE-ROADMAP.md` | ST-1 `Active -> Completed` gecisi yalniz release/publish kaniti sonrasinda mi yapiliyor? |
| `.claude/plans/ST-1-RELEASABLE-PRE-RELEASE-GATE.md` | Gate sonuc/kanit bolumu release PR ile tamamlandi mi? |

Opsiyonel dosyalar yalniz gercek drift bulunursa degisir:

| Dosya | Ne zaman degisir? |
|---|---|
| `docs/SUPPORT-BOUNDARY.md` | Support tier metni `4.0.0b1` pinine bagli kalmissa veya boundary drift'i varsa |
| `docs/KNOWN-BUGS.md` | Shipped baseline'i etkileyen yeni blocker veya beta lane known bug durumu degismisse |
| `.github/workflows/*.yml` | Release gate veya publish workflow'da gercek eksik bulunursa |

## 5. Release PR Non-Goals

- `4.0.0` stable publish yok.
- Support widening yok.
- `claude-code-cli` production-certified ilan edilmeyecek.
- `gh-cli-pr` live remote PR opening shipped/beta promoted olmayacak.
- `bug_fix_flow` release closure promoted olmayacak.
- Adapter-path `cost_usd` reconcile public support claim olarak deferred
  kalacak.

## 6. Local Validation Commands

Release PR acilmadan once:

```bash
git status --short --branch
git rev-list --left-right --count HEAD...origin/main
git diff --check
python3 -m pytest -q tests/ --ignore=tests/benchmarks --cov
python3 -m pytest -q tests/benchmarks/test_governed_review.py tests/benchmarks/test_governed_bugfix.py
python3 scripts/packaging_smoke.py
python3 scripts/truth_inventory_ratchet.py --output json
python3 examples/demo_review.py --cleanup
python3 -m ao_kernel doctor
```

Version-specific local checks:

```bash
python3 - <<'PY'
import ao_kernel
print(ao_kernel.__version__)
PY
python3 -m ao_kernel version
python3 -m ao_kernel.cli version
```

Expected release PR result: all version surfaces print `4.0.0b2`.

## 7. CI Gate

Release PR merge-ready olmak icin GitHub checks:

- `event-gate`
- `lint`
- `typecheck`
- `extras-install`
- `test (3.11)`
- `test (3.12)`
- `test (3.13)`
- `coverage` with 85% gate
- `benchmark-fast`
- `packaging-smoke`
- `scorecard` if applicable for the event

Required check isimleri repo branch protection ile uyumlu kalacak; skip edilen
push-only check, required gate gibi sayilmayacak.

## 8. Tag ve Publish Sirasi

Release PR merge olduktan sonra:

```bash
git switch main
git pull --ff-only origin main
git tag v4.0.0-beta.2
git push origin v4.0.0-beta.2
```

Sonra `publish.yml` izlenir. Publish workflow:

1. checkout
2. Python 3.13 setup
3. build/twine install
4. `python scripts/packaging_smoke.py`
5. `twine check dist/*`
6. PyPI OIDC publish

## 9. Post-Publish Verification

PyPI publish sonrasi fresh temp venv:

```bash
python3 -m venv /tmp/ao-kernel-4.0.0b2-verify
/tmp/ao-kernel-4.0.0b2-verify/bin/pip install ao-kernel==4.0.0b2
/tmp/ao-kernel-4.0.0b2-verify/bin/ao-kernel version
/tmp/ao-kernel-4.0.0b2-verify/bin/python -m ao_kernel version
/tmp/ao-kernel-4.0.0b2-verify/bin/python -m ao_kernel.cli version
```

Demo smoke repo checkout'tan ama installed package Python'i ile:

```bash
/tmp/ao-kernel-4.0.0b2-verify/bin/python examples/demo_review.py --cleanup
```

Expected:

- package install succeeds without `--pre` only when exact pin is used
- all version commands print `4.0.0b2`
- demo final state is `completed`

## 10. Blockers

Release PR veya tag publish su durumlarda durur:

- `pyproject.toml` ve `ao_kernel.__version__` ayrisir.
- Docs `4.0.0b1` pinini current install yolu gibi gostermeye devam eder.
- `CHANGELOG.md` beta.1 sonrasi kapanan support/gate kararlarini anlatmaz.
- `packaging_smoke.py` fresh wheel install ile gecmez.
- `publish.yml` packaging smoke veya `twine check` fail eder.
- Support boundary yanlislikla genisler.
- Tag `main` disindaki commit'e atilir.

## 11. Exit Criteria

`ST-1` completed sayilmasi icin:

1. Release PR merge edilir.
2. Tag `v4.0.0-beta.2` `main` merge commit'ine atilir.
3. `publish.yml` success olur.
4. PyPI exact pin install verify gecilir.
5. `.claude/plans/POST-BETA-CORRECTNESS-EXPANSION-STATUS.md` ve
   `.claude/plans/PRODUCTION-STABLE-LIVE-ROADMAP.md` ST-1'i completed
   olarak gosterir.
6. Issue [#340](https://github.com/Halildeu/ao-kernel/issues/340) closeout
   comment ile kapatilir.

