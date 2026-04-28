# GPP-2ae - Internal Operator Host Bundle

**Issue:** [#565](https://github.com/Halildeu/ao-kernel/issues/565)
**Program head:** `GPP-2` remains blocked
**Decision:** `internal_operator_host_bundle_ready_service_not_hosted_no_support_widening`
**Support impact:** none
**Production platform claim:** no
**Live adapter execution:** no

## Decision

GPP-2ae adds a repo-owned internal operator host bundle for the two GPP-2 gate
services. This makes the no-paid-cloud path repeatable without requiring each
product end user to self-host Cloud Run, a vault, webhook secrets, or a GitHub
App private key.

The bundle lives at:

```text
deploy/internal-gate-host/
```

It includes:

```text
deploy/internal-gate-host/compose.yaml
deploy/internal-gate-host/Caddyfile.example
deploy/internal-gate-host/.env.example
deploy/internal-gate-host/README.md
```

The bundle composes the existing repo-owned container packages:

```text
ghcr.io/halildeu/ao-kernel-live-adapter-gate-policy-service
ghcr.io/halildeu/ao-kernel-ao-release-gate-service
```

The preferred runtime secret path remains vault-backed secret ids:

```text
AO_LIVE_ADAPTER_GATE_WEBHOOK_SECRET_ID
AO_RELEASE_GATE_WEBHOOK_SECRET_ID
AO_GITHUB_APP_PRIVATE_KEY_PEM_ID
```

The bundle does not commit, render, or require secret values in repo state.

## Operator-Owned Boundary

This is platform infrastructure owned by the operator of the ao-kernel service.
It is not a product end-user setup requirement.

End users must not be asked to:

1. host the deployment-protection policy service;
2. host `ao-release-gate`;
3. run a vault;
4. manage webhook secret values;
5. manage a GitHub App private key;
6. create a Cloud Run or equivalent hosting project.

End-user repo-intelligence onboarding remains limited to GitHub App
installation, selected repositories, and explicit opt-in configuration.

## Attestation

GPP-2ae adds a metadata-only attestation:

```bash
python3 scripts/internal_gate_host_bootstrap_attest.py \
  --output text \
  --fail-on-blocked
```

The attestation verifies only checked-in deployment metadata:

1. the internal host bundle files exist;
2. the compose bundle references both repo-owned GHCR container packages;
3. the Caddy route file exposes the two GitHub webhook paths;
4. the runtime configuration uses vault-backed secret ids;
5. forbidden direct secret markers are absent.

The attestation does not:

1. run Docker or Docker Compose;
2. contact HashiCorp Vault or `vault_stub`;
3. read secret values;
4. configure GitHub App webhook URLs;
5. receive GitHub webhook deliveries;
6. post deployment-protection callback reviews;
7. post `ao-release-gate` check-runs;
8. change branch protection or rulesets;
9. dispatch the protected live-adapter workflow;
10. execute a live adapter.

## Remaining GPP-2 Blockers

GPP-2 remains blocked until the following evidence exists from trusted
operator infrastructure:

1. public HTTPS health evidence for the hosted policy service;
2. public HTTPS health evidence for the hosted `ao-release-gate` service;
3. GitHub App webhook URL configuration for `/github/deployment-protection`;
4. GitHub App webhook URL configuration for `/github/ao-release-gate`;
5. policy callback review evidence;
6. real PR dry-run check-run evidence from `ao-release-gate`;
7. branch-protection or ruleset cutover to require `ao-release-gate`;
8. protected workflow evidence showing fail-closed/pass behavior through the
   hosted deployment-protection gate.

Until those are recorded:

```text
live_execution_allowed=false
support_widening=false
production_platform_claim=false
```

The machine-readable flags remain `live_execution_allowed=false`,
`support_widening=false`, and `production_platform_claim=false`.

## Validation

```bash
python3 scripts/internal_gate_host_bootstrap_attest.py \
  --output text \
  --fail-on-blocked
```

```bash
python3 -m pytest tests/test_internal_gate_host_bootstrap_attest.py -q
```
