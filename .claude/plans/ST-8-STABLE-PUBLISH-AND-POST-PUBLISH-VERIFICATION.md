# ST-8 — Stable Publish and Post-Publish Verification

**Durum:** Active via issue
[#358](https://github.com/Halildeu/ao-kernel/issues/358).
**Umbrella:** [#329](https://github.com/Halildeu/ao-kernel/issues/329)
**Precondition:** `ST-7` completed via
[#357](https://github.com/Halildeu/ao-kernel/pull/357).

## 1. Amaç

`4.0.0` stable source candidate'i public package gerçeğine çevirmek. Bu gate
yalnız tag, publish ve post-publish verification yapar; runtime feature veya
support widening yapmaz.

## 2. Scope Boundary

ST-8 stable support boundary'yi değiştirmez. Publish edilen stable yüzey,
`ST-2` freeze ve `ST-7` candidate sonucundaki dar shipped baseline ile sınırlıdır:

1. CLI/module entrypoint'ler.
2. `ao-kernel doctor`.
3. `review_ai_flow + codex-stub`.
4. `examples/demo_review.py`.
5. policy command enforcement.
6. wheel-installed packaging smoke.
7. documented read-only kernel API actions.

`claude-code-cli`, `gh-cli-pr`, live-write PR açılışı ve real-adapter production
certification bu gate'te stable support'a alınmaz.

## 3. Publish Sequence

```bash
git checkout main
git pull --ff-only origin main
git status --short --branch
git tag v4.0.0
git push origin v4.0.0
```

Tag push sonrası `publish.yml` workflow'u izlenir. Workflow başarıya ulaşmadan
PyPI veya README üzerinde live stable claim'i yapılmaz.

## 4. Post-Publish Verification Bundle

Public package doğrulaması tag workflow başarıya ulaştıktan sonra yapılır:

```bash
python3 -m venv /tmp/ao-kernel-4.0.0-verify
/tmp/ao-kernel-4.0.0-verify/bin/python -m pip install --upgrade pip
/tmp/ao-kernel-4.0.0-verify/bin/python -m pip install ao-kernel==4.0.0
/tmp/ao-kernel-4.0.0-verify/bin/ao-kernel version
/tmp/ao-kernel-4.0.0-verify/bin/python -m ao_kernel version
/tmp/ao-kernel-4.0.0-verify/bin/python -m ao_kernel.cli version
/tmp/ao-kernel-4.0.0-verify/bin/python -m ao_kernel doctor
/tmp/ao-kernel-4.0.0-verify/bin/python examples/demo_review.py --cleanup
```

Ayrı bir fresh venv ile bare stable kanal da doğrulanır:

```bash
python3 -m venv /tmp/ao-kernel-stable-channel-verify
/tmp/ao-kernel-stable-channel-verify/bin/python -m pip install --upgrade pip
/tmp/ao-kernel-stable-channel-verify/bin/python -m pip install ao-kernel
/tmp/ao-kernel-stable-channel-verify/bin/ao-kernel version
```

Beklenen sonuç: tüm version komutları `4.0.0` döner, doctor shipped baseline
için `FAIL` üretmez ve installed demo `completed` olur.

## 5. Release Blockers

Aşağıdakilerden biri olursa release tamamlanmış sayılmaz:

1. Publish workflow fail eder veya package upload yapmaz.
2. PyPI project/version endpoint'leri `4.0.0` için görünür değildir.
3. Exact pin install `ao-kernel==4.0.0` fail eder.
4. Bare stable install `pip install ao-kernel` `4.0.0` döndürmez.
5. Entry point'lerden biri farklı version döndürür.
6. Public package installed demo `completed` durumuna ulaşmaz.
7. Docs/status public package live claim'i ile PyPI gerçeği ayrışır.

## 6. Out of Scope

- Runtime code changes.
- Support widening.
- Adapter production promotion.
- Live-write remote PR opening.
- GitHub release marketing metni dışında yeni ürün iddiası.

## 7. Done Definition

ST-8 tamamlandığında:

1. Tag `v4.0.0` origin'e pushed olur.
2. `publish.yml` success olur.
3. PyPI `ao-kernel==4.0.0` public olarak doğrulanır.
4. Exact pin ve bare stable install fresh venv içinde `4.0.0` döndürür.
5. Public package installed demo smoke geçer.
6. Status dosyaları stable live sonucunu ve kalan support boundary'yi yazar.
7. Issue [#358](https://github.com/Halildeu/ao-kernel/issues/358) closeout
   comment ile kapatılır.
