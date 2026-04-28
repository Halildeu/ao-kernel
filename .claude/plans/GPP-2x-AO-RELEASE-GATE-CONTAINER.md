# GPP-2x - AO Release Gate Container Package

**Issue:** [#543](https://github.com/Halildeu/ao-kernel/issues/543)
**Decision:** `ao_release_gate_container_ready_no_support_widening`
**Date:** 2026-04-28
**Support widening:** false
**Production platform claim:** false
**Live adapter execution:** false

## Decision

GPP-2x packages the `ao-release-gate` check-run service runtime as a
repo-owned container image build target with a bounded no-secret health smoke.
This makes the GPP-2w WSGI runtime deployable by a hosting platform without
inventing packaging steps outside the repo.

This slice does not publish the image, host the service, configure the GitHub
App webhook URL, post a check-run to GitHub, change branch protection, merge
PRs, run a live adapter, widen support, or claim production readiness.
It does not unblock GPP-2 and does not authorize human-free merges.

## Added Surface

1. `deploy/ao-release-gate-service/Dockerfile`
   - builds from `python:3.13-slim`;
   - installs `ao-kernel[release-gate-service]`;
   - runs `gunicorn` against `ao_kernel.ao_release_gate_runtime:application`;
   - exposes port `8000`;
   - adds a container health check for `/healthz`;
   - runs as a non-root user.

2. `scripts/ao_release_gate_container_smoke.py`
   - builds the container image;
   - runs it on a loopback-only random host port;
   - checks `GET /healthz`;
   - bounds Docker build/run waits with explicit timeouts;
   - reports no secret readback, no GitHub check-run POST, no merge authority,
     no branch-protection cutover, and no live adapter execution.

3. `.github/workflows/test.yml`
   - adds `release-gate-container-smoke` to build and health-check the
     container in CI without secret context.

4. `pyproject.toml`
   - adds a `release-gate-service` optional extra for hosted service runtime
     dependencies.

5. `tests/test_ao_release_gate_container.py`
   - pins the Dockerfile runtime entrypoint and no-secret boundary;
   - pins smoke-script defaults;
   - pins CI wiring without secret context.

## Container Contract

Build:

```bash
docker build \
  -f deploy/ao-release-gate-service/Dockerfile \
  -t ao-kernel-ao-release-gate-service:local \
  .
```

No-secret local health smoke:

```bash
python3 scripts/ao_release_gate_container_smoke.py \
  --image ao-kernel-ao-release-gate-service:smoke \
  --build-timeout-seconds 600
```

Hosted service configuration still must provide runtime-only values outside
the repo:

```text
AO_RELEASE_GATE_WEBHOOK_SECRET
AO_GITHUB_APP_ID
AO_GITHUB_APP_PRIVATE_KEY_PEM
```

or:

```text
AO_GITHUB_APP_PRIVATE_KEY_PATH
```

The public GitHub App webhook URL must route to:

```text
POST /github/ao-release-gate
```

Do not pass `AO_CLAUDE_CODE_CLI_AUTH` to this container. The release-gate
service posts dry-run check-runs only after it is explicitly hosted and
configured with GitHub App runtime secrets.

## Remaining Blockers

GPP-2 remains blocked after this work because:

1. The `ao-release-gate` container image is not yet published to GHCR or
   deployed to a public host.
2. The `ao-release-gate` GitHub App webhook URL/runtime secret configuration is
   not yet proven on a real delivery.
3. No real PR dry-run check-run evidence has been collected.
4. Branch protection/rulesets do not yet require `ao-release-gate`.
5. The deployment-protection policy service for
   `ao-kernel-live-adapter-gate` is still not publicly hosted/configured and
   still has no protected workflow callback evidence.

## Next Allowed Action

Publish or otherwise deploy the `ao-release-gate` container as a deploy
artifact, configure the hosted dry-run service with runtime secret-manager
values, collect real PR check-run evidence, and only then consider a branch
protection/ruleset cutover. The deployment-protection policy service must also
still be hosted/configured before protected live-adapter workflow evidence is
rerun.
