# GPP-2af - Internal Gate Host Health Probe

**Issue:** [#567](https://github.com/Halildeu/ao-kernel/issues/567)
**Program head:** `GPP-2` remains blocked
**Decision:** `internal_gate_host_health_probe_ready_hosting_evidence_not_collected_no_support_widening`
**Support impact:** none
**Production platform claim:** no
**Live adapter execution:** no

## Decision

GPP-2af adds a repo-owned, no-secret health evidence probe for the internal
operator host path introduced by GPP-2ae.

The probe lives at:

```text
scripts/internal_gate_host_health_probe.py
```

It checks the public health endpoints exposed by `deploy/internal-gate-host`:

```text
https://<AO_GATE_HOSTNAME>/policy/healthz
https://<AO_GATE_HOSTNAME>/release-gate/healthz
```

The probe expects:

1. the policy service to return HTTP 200 with `status=ok` and
   `program_id=GPP-2q`;
2. `ao-release-gate` to return HTTP 200 with `status=ok` and
   `program_id=GPP-2w`;
3. both URLs to use HTTPS before `public_https_hosting_evidence=true` can be
   recorded.

Local `http://127.0.0.1` rehearsal can be allowed explicitly with
`--allow-http-localhost`, but that produces `local_health_ready`, not public
hosted evidence.

## Boundary

This is an evidence collection tool for operator-owned platform
infrastructure. It is not a product end-user setup requirement.

The probe does not:

1. read webhook secrets or GitHub App private keys;
2. configure GitHub App webhook URLs;
3. receive GitHub webhook deliveries;
4. post deployment-protection callback reviews;
5. post `ao-release-gate` check-runs;
6. change branch protection or rulesets;
7. dispatch protected workflows;
8. execute a live adapter;
9. widen support or claim production-platform readiness.

The emitted evidence keeps these flags closed:

```text
secret_value_readback=false
github_webhook_configured=false
github_callback_post=false
github_check_run_post=false
branch_protection_cutover=false
protected_workflow_dispatch=false
live_adapter_execution=false
support_widening=false
production_platform_claim=false
```

## Remaining GPP-2 Blockers

GPP-2 remains blocked until trusted operator infrastructure records the full
sequence:

1. public HTTPS health evidence for the hosted policy service;
2. public HTTPS health evidence for the hosted `ao-release-gate` service;
3. GitHub App webhook URL configuration for `/github/deployment-protection`;
4. GitHub App webhook URL configuration for `/github/ao-release-gate`;
5. policy callback review evidence;
6. real PR dry-run check-run evidence from `ao-release-gate`;
7. branch-protection or ruleset cutover to require `ao-release-gate`;
8. protected workflow evidence through the hosted deployment-protection gate.

Until those are recorded:

```text
live_execution_allowed=false
support_widening=false
production_platform_claim=false
```

## Validation

```bash
python3 -m pytest tests/test_internal_gate_host_health_probe.py -q
```

```bash
python3 scripts/internal_gate_host_health_probe.py \
  --host gate.example.test \
  --output text \
  --fail-on-blocked
```

The second command is expected to block unless `gate.example.test` is replaced
with the real operator-owned public HTTPS host.
