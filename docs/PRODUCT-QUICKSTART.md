# Product Quickstart — Local Governed Workflow

This guide takes a fresh install from zero to the first local evidence
artifacts for the productized `ao-kernel` workflow:

1. repo-intelligence onboarding,
2. PR delivery metadata,
3. bounded multi-agent local orchestration.

It is intentionally local and fail-closed. It does **not** configure GitHub
Apps, Vault, webhooks, branch protection, Cloud Run, live adapters, support
widening, or a production-platform claim.

## 1. Install

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install ao-kernel==4.3.1
ao-kernel version
```

For a checkout smoke before publishing, use:

```bash
python scripts/fresh_install_product_smoke.py --mode both
```

The smoke builds the checkout, installs the wheel and sdist into separate
clean virtualenvs, and writes evidence under:

```text
build/fresh-install-product-smoke/
```

## 2. Prepare A Project

Run these commands from the repository you want to onboard.

```bash
ao-kernel init
ao-kernel repo onboarding init-config \
  --project-root . \
  --path .ao/repo-intelligence.yml
ao-kernel repo onboarding doctor --project-root . --output json
```

Expected boundary:

- `status` should become `ready` once the `.ao` workspace and onboarding
  config are present.
- The generated config records GitHub App installation and repository
  selection as the user-managed setup boundary.
- End users are not asked to host `ao-release-gate`, Vault, Cloud Run,
  deployment-protection callbacks, or webhooks.

## 3. Add PR Delivery Metadata

Generate a metadata block:

```bash
ao-kernel pr-metadata generate \
  --work-package PRODUCT-SLICE-1 \
  --issue '#123' \
  --reviewer-provider anthropic > /tmp/pr-metadata.md
```

Insert or update it in a PR body:

```bash
ao-kernel pr-metadata fix \
  --body-file pr-body.md \
  --write \
  --work-package PRODUCT-SLICE-1 \
  --issue '#123' \
  --reviewer-provider anthropic

ao-kernel pr-metadata validate --body-file pr-body.md --output json
```

The PR metadata block is a structured declaration. It is not release authority.
Release authority remains the repo-owned `ao-release-gate` required check plus
GitHub branch protection.

## 4. Run A Bounded Local Multi-Agent Wrapper

Dry-run one declared write scope:

```bash
BASE_SHA="$(git rev-parse origin/main)"

ao-kernel orchestration run-wrapper \
  --goal "bounded local slice" \
  --repo-root . \
  --base-sha "$BASE_SHA" \
  --repo Halildeu/ao-kernel \
  --declared-spec task-001:src/example.py:"bounded local change" \
  --dry-run \
  --format json
```

Run multiple deterministic local worker fixtures concurrently:

```bash
ao-kernel orchestration run-wrapper-async \
  --goal "bounded parallel local slice" \
  --repo-root . \
  --worktree-base ../ao-kernel-workers \
  --base-sha "$BASE_SHA" \
  --repo Halildeu/ao-kernel \
  --declared-spec task-001:src/a.py:"worker one" \
  --declared-spec task-002:src/b.py:"worker two" \
  --execute-local-fixture \
  --max-workers 2 \
  --format json
```

The async wrapper:

- emits one task graph for all declared specs,
- prepares one worker worktree per declared task,
- invokes the pinned deterministic local worker fixture concurrently,
- collects `manifest.v1.json`, `runner_report.v1.json`, and
  `worker_invocation_report.v1.json`,
- reports review and verification phases as external evidence required rather
  than fabricating AI review or verifier approval.

## 5. Acceptance Boundary

This quickstart proves the local governed-control-plane workflow is installed
and operational. It does not prove or claim:

- support widening,
- production-platform readiness,
- live adapter execution,
- GitHub ruleset mutation,
- webhook callback delivery,
- cloud hosting,
- provider API execution.

Those remain separate operator-bound supersession decisions.
