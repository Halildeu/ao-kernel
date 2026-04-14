# .githooks/

Versioned git hooks for ao-kernel. Activated via `core.hooksPath=.githooks`.

## Install (once per clone/worktree)

```bash
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit .githooks/pre-push
```

Verify:

```bash
git config core.hooksPath   # should print: .githooks
ls -l .githooks/pre-*       # both files executable
```

## Hooks

### `pre-commit`
Runs on every `git commit`. Blocks the commit if any of:
- A staged file contains a known secret pattern (API keys, tokens, credentials)
- A `.patch` file is staged at repo root (use `.archive/patches/` instead)
- A file ≥ 100 MB is staged

Skipped paths: binaries (`*.png`, `*.pdf`, ...), `.ao/consultations/`, `.claude/`.

### `pre-push`
Runs on every `git push`. Blocks or warns on:
- **Blocks** direct push to `refs/heads/main` or `refs/heads/master` (GitHub branch protection is the primary defense; this is a second layer)
- **Warns** if any commit in the push range has a message starting with `WIP`, `wip`, `fixup!`, or `squash!`

## Bypass

Both hooks accept `--no-verify` (`git commit --no-verify`, `git push --no-verify`). Bypasses should be rare and documented in the commit/PR description.

## Why versioned?

Hooks in `.git/hooks/` are not shared between clones or worktrees. Putting them under `.githooks/` and setting `core.hooksPath` means every contributor sees the same rules after a one-line setup.

See `CONTRIBUTING.md` (to be added in Tranş A) for the full onboarding flow.
