# GPP-2ad - Internal Vault Gate Secret Contract

**Issue:** [#563](https://github.com/Halildeu/ao-kernel/issues/563)
**Decision:** `internal_vault_gate_secret_contract_ready_service_not_hosted_no_support_widening`
**Date:** 2026-04-28
**Program head:** `GPP-2` remains blocked on hosted callback/check-run evidence
**Support widening:** false
**Production platform claim:** false
**Live adapter execution:** false

## Decision

GPP-2ad switches the preferred unblock direction from a Cloud Run-only
bootstrap path to an operator-owned internal host plus vault-backed runtime
secret contract.

The policy service and `ao-release-gate` can now resolve GitHub App runtime
secrets through the existing ao-kernel secrets provider interface. Hosted
operators may pass secret ids instead of secret values:

```text
AO_LIVE_ADAPTER_GATE_WEBHOOK_SECRET_ID
AO_RELEASE_GATE_WEBHOOK_SECRET_ID
AO_GITHUB_APP_PRIVATE_KEY_PEM_ID
```

The existing direct environment and private-key path inputs remain supported
for compatibility:

```text
AO_LIVE_ADAPTER_GATE_WEBHOOK_SECRET
AO_RELEASE_GATE_WEBHOOK_SECRET
AO_GITHUB_APP_PRIVATE_KEY_PEM
AO_GITHUB_APP_PRIVATE_KEY_PATH
```

## Internal Vault Model

The operator-owned internal path is:

1. run the repo-owned policy service container on an operator host;
2. run the repo-owned `ao-release-gate` container on an operator host;
3. expose both services through public HTTPS routes reachable by GitHub;
4. configure the host with a secrets provider such as `hashicorp_vault` or
   `vault_stub`;
5. pass secret ids into the runtime, not secret values;
6. keep vault credentials as operator host material outside repository files,
   GitHub variables, PRs, issues, logs, and chat.

Required policy service runtime handles:

```text
SECRETS_PROVIDER
AO_GITHUB_APP_ID
AO_LIVE_ADAPTER_GATE_WEBHOOK_SECRET_ID
AO_GITHUB_APP_PRIVATE_KEY_PEM_ID
```

Required `ao-release-gate` runtime handles:

```text
SECRETS_PROVIDER
AO_GITHUB_APP_ID
AO_RELEASE_GATE_WEBHOOK_SECRET_ID
AO_GITHUB_APP_PRIVATE_KEY_PEM_ID
AO_RELEASE_GATE_GPP_STATUS_PATH
```

For `hashicorp_vault`, the host also supplies provider-local configuration:

```text
VAULT_ADDR
VAULT_TOKEN
VAULT_SECRET_MOUNT
```

Those provider credentials are not product user configuration and are not
repository configuration.

## Trust Boundary

This path is operator-owned platform infrastructure. End users must not be
asked to self-host the policy service, `ao-release-gate`, a vault, webhook
secrets, GitHub App private keys, Cloud Run, or equivalent hosting. End-user
repo-intelligence onboarding remains GitHub App installation, repository
selection, and explicit read-only opt-in.

This slice does not:

1. read or echo secret values;
2. configure a public host;
3. configure GitHub App webhook URLs;
4. post deployment protection callback reviews;
5. post `ao-release-gate` check-runs;
6. change branch protection or rulesets;
7. dispatch the protected live-adapter workflow;
8. run a live adapter;
9. widen support;
10. claim production platform readiness.

## Still Blocked

GPP-2 remains blocked until all of the following evidence exists:

1. policy service public `/healthz` evidence;
2. policy service public `/github/deployment-protection` GitHub App webhook
   configuration evidence;
3. policy service deployment protection callback review evidence;
4. `ao-release-gate` public `/healthz` evidence;
5. `ao-release-gate` public `/github/ao-release-gate` webhook configuration
   evidence;
6. real PR dry-run `ao-release-gate` check-run evidence;
7. branch protection or ruleset cutover requiring the durable
   `ao-release-gate` status check after dry-run evidence;
8. protected workflow evidence from `main` proving the policy service responds
   fail-closed or approve-contract-gate while `live_execution_allowed=false`.

Still closed:

1. `live_execution_allowed=false`;
2. `support_widening=false`;
3. `production_platform_claim=false`.

## Validation

```bash
python3 -m pytest tests/test_live_adapter_gate_policy_runtime.py tests/test_ao_release_gate_runtime.py tests/test_gpp_next.py -q
python3 -m ruff check ao_kernel/live_adapter_gate_policy_runtime.py ao_kernel/ao_release_gate_runtime.py tests/test_live_adapter_gate_policy_runtime.py tests/test_ao_release_gate_runtime.py tests/test_gpp_next.py
python3 -m json.tool .claude/plans/gpp_status.v1.json
python3 scripts/gpp_next.py
git diff --check
```

Recorded closeout decision:

```text
internal_vault_gate_secret_contract_ready_service_not_hosted_no_support_widening
```
