# Upgrade Notes

This document covers operator-facing upgrade steps for the currently documented
stable and beta channels.

## 1. Choose the right channel

### Stable channel

```bash
pip install -U ao-kernel
```

### Public Beta channel

```bash
pip install --pre ao-kernel
# or pin explicitly
pip install ao-kernel==4.0.0b2
```

Do not assume `pip install ao-kernel` will pick the beta. It stays on the
stable channel unless you ask for a pre-release explicitly.

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
