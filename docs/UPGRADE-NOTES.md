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
pip install ao-kernel==4.0.0b1
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
```

## 4. Expected warnings

These do not automatically mean the upgrade failed:

- `ao-kernel doctor` may show a `WARN` for missing optional `llm` extras on a
  core-only install
- bundled extension truth inventory may report contract-only or quarantined
  candidates

Treat those as expected unless the support matrix says otherwise.

## 5. When to stop and roll back

Stop the upgrade and use [`ROLLBACK.md`](ROLLBACK.md) if any shipped-baseline
check fails:

- entrypoint contract commands
- `ao-kernel doctor`
- `python3 examples/demo_review.py --cleanup`
- required CI or packaging smoke for the target release
