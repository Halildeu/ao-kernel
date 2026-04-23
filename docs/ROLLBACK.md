# Rollback

Use this document when a recent upgrade, merge, or release leaves the shipped
baseline or an explicitly supported beta lane in a worse state.

## 1. Package-level rollback

### Return to stable

```bash
pip install --force-reinstall ao-kernel
```

`ao-kernel` stable channel pin'i dokümana sabit yazılmaz; bu komut pre-release
flag olmadan en güncel stable hattı geri yükler.

### Return to the documented beta pin

```bash
pip install --force-reinstall ao-kernel==4.0.0b1
```

After either rollback, verify:

```bash
ao-kernel version
python -m ao_kernel version
python -m ao_kernel.cli version
ao-kernel doctor
python3 examples/demo_review.py --cleanup
```

## 2. Source-repo rollback

If the problem comes from a recent merge on `main`:

1. identify the merge commit or squash commit,
2. revert it in a new branch,
3. run the same baseline verification commands,
4. merge the revert only after the support boundary is truthful again.

Use non-interactive git commands only. Do not reset shared history.

## 3. Release rollback rule

In this repo, merge does not publish a package. Tag-triggered publish is the
release boundary. That means:

- a merged docs/runtime PR may need a repo revert,
- a published package may need a package reinstall or follow-up release,
- both may be needed if the bad state already reached users.

## 4. Beta lane rule

If only an operator-managed beta lane regresses while the shipped baseline
stays green, prefer narrowing guidance and updating
[`KNOWN-BUGS.md`](KNOWN-BUGS.md) over rolling back the whole baseline.

## 5. Related documents

- [`UPGRADE-NOTES.md`](UPGRADE-NOTES.md)
- [`OPERATIONS-RUNBOOK.md`](OPERATIONS-RUNBOOK.md)
- [`PUBLIC-BETA.md`](PUBLIC-BETA.md)
