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

### Return to the historical Public Beta pre-release pin

```bash
pip install --force-reinstall ao-kernel==4.0.0b2
```

This is not the normal stable rollback path. Use it only when intentionally
returning an operator-managed environment to the historical Public Beta
pre-release line. The default rollback path remains the stable channel above.

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

### 3.1 Emergency decision matrix

| Bad state | Preferred action | Notes |
|---|---|---|
| Bad PR merged but no tag published | Revert or fix-forward on `main` | Do not create a release tag until the shipped baseline is green again |
| Tag pushed but publish workflow failed before upload | Fix the release workflow/package issue and retag only according to repository release policy | Do not announce the version as live |
| Package published and shipped baseline fails | Prefer fast corrective release; use package-level rollback for affected operators | Update `KNOWN-BUGS.md` only if the issue remains bounded and understood |
| Package published and install is dangerous or misleading for most users | Consider yanking the release in PyPI, then publish a corrective version | Yank is exceptional; record the reason in the release issue/changelog |
| Only beta/operator-managed lane regresses | Keep stable package; update known bugs/operator guidance | Do not yank or rollback the shipped baseline for beta-only regressions |

After any rollback, yank, or fix-forward decision, rerun the shipped baseline
commands and record the exact version/commit used for verification.

## 4. Beta lane rule

If only an operator-managed beta lane regresses while the shipped baseline
stays green, prefer narrowing guidance and updating
[`KNOWN-BUGS.md`](KNOWN-BUGS.md) over rolling back the whole baseline.

## 5. Stable boundary rule

Rollback does not widen support. If a stable shipped baseline check fails,
either rollback to the last known-good package or ship a corrective release.
Do not substitute an operator-managed beta lane as the stable path.

For the current stable boundary:

- shipped baseline regressions are release blockers,
- beta/operator-managed regressions stay in [`KNOWN-BUGS.md`](KNOWN-BUGS.md),
- live-write or real-adapter promotion requires separate ST gate evidence.

## 6. Related documents

- [`UPGRADE-NOTES.md`](UPGRADE-NOTES.md)
- [`OPERATIONS-RUNBOOK.md`](OPERATIONS-RUNBOOK.md)
- [`PUBLIC-BETA.md`](PUBLIC-BETA.md)
