# Runbook 01 — PyPI v4.3.0 Publish (P0-1)

> **Agent-prepared only.** This runbook directs the operator to dispatch
> the existing `.github/workflows/publish.yml` workflow. The agent does
> NOT dispatch on the operator's behalf.

## Prerequisites

- v4.3.0 tag pushed to `origin` (verify: `git tag --list v4.3.0`)
- Tag SHA matches main release commit (`git rev-parse v4.3.0` ↔
  `git rev-parse origin/main`)
- PyPI maintainer permissions for `ao-kernel`
- GHCR maintainer permissions for the matching container

## Steps

1. Confirm the tag is reachable:
   ```bash
   git fetch --tags origin
   git rev-parse refs/tags/v4.3.0
   ```
2. Confirm the workflow file is on the head commit:
   ```bash
   gh workflow list --repo Halildeu/ao-kernel | grep publish
   ```
3. Dispatch the workflow with the v-tag ref:
   ```bash
   gh workflow run publish.yml \
       --repo Halildeu/ao-kernel \
       --ref refs/tags/v4.3.0 \
       --field ref=refs/tags/v4.3.0
   ```
4. Watch the run:
   ```bash
   gh run watch --repo Halildeu/ao-kernel
   ```
5. Confirm `https://pypi.org/project/ao-kernel/4.3.0/` resolves.
6. Confirm the GHCR container tag exists and matches.

## Verification

- PyPI page: `https://pypi.org/project/ao-kernel/4.3.0/`
- GHCR container: matching v4.3.0 digest
- Workflow run conclusion is `success`
- No test version published to the production index

## Rollback

PyPI releases are NOT deletable. The correct rollback path is:

- `pip` users: `pip install ao-kernel==<previous>` to pin away from 4.3.0
- Maintainer: **yank** the broken release if necessary (this is reversible)
  and publish a corrective patch release (next patch, e.g. `v4.3.1`)
- Do NOT attempt to delete 4.3.0 from PyPI; deletion is not supported and
  yank-then-corrective-patch is the safer path

## Stop and contact owner if

- The tag SHA does not match `origin/main` head at the time of release
- `pypi.org` already has a `4.3.0` entry from an earlier accidental publish
- The workflow run shows unexpected `inputs` (a `ref` value other than
  `refs/tags/v4.3.0`)
- The GHCR push step fails (digest mismatch)
- The `inputs.ref` v-tag guard rejects the input

## References

- `.github/workflows/publish.yml`
- Codex thread `019e84c6` (cross-AI plan-time AGREE)
- HARD RULE Tam Otonom Önerme (2026-05-28)
