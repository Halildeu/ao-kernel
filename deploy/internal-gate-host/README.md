# Internal Gate Host Bundle

This bundle is the operator-owned, no-paid-cloud default for hosting the GPP-2
gate services after the internal vault secret-id contract. It composes the
existing repo-owned containers:

```text
ghcr.io/halildeu/ao-kernel-live-adapter-gate-policy-service
ghcr.io/halildeu/ao-kernel-ao-release-gate-service
```

It is not an end-user setup requirement. Product users should only install the
GitHub App, select repositories, and opt in to read-only repo-intelligence
configuration. They must not be asked to host this bundle, run a vault, manage
webhook secrets, or handle GitHub App private keys.

## Files

```text
deploy/internal-gate-host/compose.yaml
deploy/internal-gate-host/Caddyfile.example
deploy/internal-gate-host/.env.example
```

`compose.yaml` runs three containers:

1. `caddy`, the public HTTPS reverse proxy.
2. `live-adapter-gate-policy`, the GitHub deployment-protection callback
   policy service.
3. `ao-release-gate`, the dry-run check-run service.

The public GitHub App webhook URLs are:

```text
https://<AO_GATE_HOSTNAME>/github/deployment-protection
https://<AO_GATE_HOSTNAME>/github/ao-release-gate
```

The no-secret health URLs are:

```text
https://<AO_GATE_HOSTNAME>/policy/healthz
https://<AO_GATE_HOSTNAME>/release-gate/healthz
```

## Runtime Secret Contract

The services read secret values only at runtime. The checked-in bundle uses
vault secret ids and provider-local configuration:

```text
SECRETS_PROVIDER=hashicorp_vault
VAULT_ADDR=<operator vault URL>
VAULT_TOKEN=<operator vault token>
VAULT_SECRET_MOUNT=secret
AO_GITHUB_APP_PRIVATE_KEY_PEM_ID=gpp2/github/private-key-pem
AO_LIVE_ADAPTER_GATE_WEBHOOK_SECRET_ID=gpp2/policy/webhook-secret
AO_RELEASE_GATE_WEBHOOK_SECRET_ID=gpp2/release-gate/webhook-secret
```

`VAULT_TOKEN`, webhook secret values, and the GitHub App private key are
operator runtime material. They must not be committed, pasted into issues,
printed in logs, or sent through chat.

For local operator rehearsal, `SECRETS_PROVIDER=vault_stub` can be used with a
local `.secrets/vault.json` file in the service working directory. That file is
still secret material and must stay outside git.

## GPP Boundary

This bundle only makes the internal host path repeatable. It does not prove:

- public DNS and HTTPS are configured;
- the GitHub App webhook URLs are set;
- a deployment-protection callback review was posted;
- an `ao-release-gate` check-run was posted on a real PR;
- branch protection requires `ao-release-gate`;
- the protected live-adapter workflow can pass the gate;
- live adapter execution is allowed;
- support widening or a production platform claim is allowed.

Until those evidence items exist, GPP-2 remains blocked and fail-closed.

## Metadata-Only Attestation

The repository provides a no-secret static attestation for this bundle:

```bash
python3 scripts/internal_gate_host_bootstrap_attest.py \
  --output text \
  --fail-on-blocked
```

The attestation reads only checked-in deployment metadata. It does not run
Docker, contact a vault, call GitHub, configure webhooks, post callbacks,
post check-runs, dispatch protected workflows, or execute a live adapter.
