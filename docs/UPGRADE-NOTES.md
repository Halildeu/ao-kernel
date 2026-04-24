# Upgrade Notes

This document covers operator-facing upgrade steps for the currently documented
stable and beta channels.

## 1. Choose the right channel

### Stable channel

```bash
pip install -U ao-kernel
# exact stable pin
pip install ao-kernel==4.0.0
```

### Public Beta channel

```bash
pip install --pre ao-kernel
# or pin explicitly
pip install ao-kernel==4.0.0b2
```

Do not assume `pip install ao-kernel` will pick a beta. It stays on the stable
channel unless you ask for a pre-release explicitly. `v4.0.0` is live on PyPI;
post-publish verification confirmed both `pip install ao-kernel` and
`pip install ao-kernel==4.0.0` resolve to `ao-kernel 4.0.0` in fresh virtual
environments.

## 1.1 Stable support boundary

The stable support boundary is intentionally narrow. Treat the
`Shipped` table in [`PUBLIC-BETA.md`](PUBLIC-BETA.md) and the `Shipped
baseline` layer in [`SUPPORT-BOUNDARY.md`](SUPPORT-BOUNDARY.md) as the supported
runtime claim.

Do not treat the following as stable shipped support unless a later release
explicitly promotes them:

- `claude-code-cli` real-adapter lane,
- `gh-cli-pr` preflight or live-write lane,
- `PRJ-KERNEL-API` write-side actions,
- real-adapter benchmark full mode,
- `bug_fix_flow` release closure,
- full remote PR opening.

## 2. Pre-upgrade snapshot

Before upgrading, record the current environment state:

```bash
ao-kernel version
python -m ao_kernel version
python -m ao_kernel.cli version
python -m pip show ao-kernel
```

## 3. Post-upgrade verification

After upgrading, run the baseline checks:

```bash
ao-kernel version
python -m ao_kernel version
python -m ao_kernel.cli version
ao-kernel doctor
python3 examples/demo_review.py --cleanup
```

`examples/demo_review.py` must be executed with a Python environment that has
the intended `ao-kernel` package installed. The release gate version of this
check is `scripts/packaging_smoke.py`, which installs the wheel into a fresh
venv before running the demo.

If you use operator-managed real-adapter lanes, run the corresponding smoke as
well:

```bash
python3 scripts/claude_code_cli_smoke.py --output text
python3 scripts/gh_cli_pr_smoke.py --output text
# Optional readiness probe (live-write, explicit opt-in + disposable guard):
# python3 scripts/gh_cli_pr_smoke.py --mode live-write --allow-live-write --head <branch> --base <branch>
```

Prerequisite contract:

1. `claude-code-cli` lane health kararı için `claude auth status` tek başına
   yeterli kabul edilmez; belirleyici komut
   `python3 scripts/claude_code_cli_smoke.py --output text` olmalıdır.
2. `gh-cli-pr` preflight lane için `gh` binary + aktif auth + repo context
   çözümü gerekir; preflight lane side-effect-safe dry-run olarak çalışır.
3. `gh-cli-pr` live-write probe explicit
   `--mode live-write --allow-live-write --head ... --base ...` ister.
4. Varsayılan disposable guard keyword `sandbox` olup, repo adında yoksa
   probe bilerek `blocked` döner.
5. `--keep-live-write-pr-open` seçeneği lane'i riskli sayar ve `blocked`
   sonucu beklenen davranıştır.

`bug_fix_flow` workflow path'inde `open_pr` adımı varsayılan fail-closed
guard arkasındadır. Gerçek live-write denemesi yalnız disposable ortamda,
explicit `AO_KERNEL_ALLOW_GH_CLI_PR_LIVE_WRITE=1` ile yapılmalıdır.

## 3.1 Release operator verification

For a release candidate or freshly published package, run this from a checkout
that contains `examples/demo_review.py`, but prefer an isolated verification
environment over the current editable install:

```bash
python3 -m venv /tmp/ao-kernel-release-verify
/tmp/ao-kernel-release-verify/bin/python -m pip install -U pip
/tmp/ao-kernel-release-verify/bin/python -m pip install ao-kernel==<version>
/tmp/ao-kernel-release-verify/bin/ao-kernel version
/tmp/ao-kernel-release-verify/bin/python -m ao_kernel version
/tmp/ao-kernel-release-verify/bin/python -m ao_kernel.cli version
/tmp/ao-kernel-release-verify/bin/ao-kernel doctor
/tmp/ao-kernel-release-verify/bin/python examples/demo_review.py --cleanup
```

For pre-release validation, replace the install command with either an exact
pre-release pin or `--pre`. Do not use an editable install as release evidence.

From a source checkout, the equivalent package gate is:

```bash
python3 scripts/packaging_smoke.py
```

This script builds the sdist/wheel, installs the wheel into a fresh venv, and
runs the shipped entrypoint/demo checks outside the editable install path.

## 4. Expected warnings

These do not automatically mean the upgrade failed:

- `ao-kernel doctor` may show a `WARN` for missing optional `llm` extras on a
  core-only install
- bundled extension truth inventory may report contract-only or quarantined
  candidates
- guard env tanımlı değilken `bug_fix_flow` `open_pr` adımının
  `LIVE_WRITE_NOT_ALLOWED` ile fail etmesi (beklenen güvenlik davranışı)

Treat those as expected unless the support matrix says otherwise.

## 5. When to stop and roll back

Stop the upgrade and use [`ROLLBACK.md`](ROLLBACK.md) if any shipped-baseline
check fails:

- entrypoint contract commands
- `ao-kernel doctor`
- `python3 examples/demo_review.py --cleanup`
- required CI or packaging smoke for the target release
