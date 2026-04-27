# Protected Live-Adapter Gate Provisioning Runbook

This runbook is the operator/admin checklist for unblocking the protected
live-adapter prerequisite gate tracked in
[#482](https://github.com/Halildeu/ao-kernel/issues/482) and
[#485](https://github.com/Halildeu/ao-kernel/issues/485).

It is not a live-execution guide. Completing the checklist prepares or repairs
the metadata-only attestation that the protected workflow binding depends on.

Current selected model:

| Field | Value |
|---|---|
| Protected environment | `ao-kernel-live-adapter-gate` |
| Deployment protection model | GitHub App deployment protection rule |
| Required app slug | `ao-kernel-live-adapter-gate` |
| Required credential handle | `AO_CLAUDE_CODE_CLI_AUTH` |
| Current program head | `GPP-2` blocked on deployment protection policy response |

## Preconditions

Before changing GitHub admin state:

1. `main` must be clean and synchronized with `origin/main`.
2. `python3 scripts/gpp_next.py` must still report `support_widening=false`,
   `production_platform_claim=false`, and `live_adapter_execution_allowed=false`.
3. The operator must have GitHub admin permission for `Halildeu/ao-kernel`.
4. The operator must know the GitHub App or policy service that owns slug
   `ao-kernel-live-adapter-gate`, or open a decision PR before changing the
   selected slug/model.
5. Credential material must be available through the operator's approved
   secret handoff path. Do not paste it into issues, PRs, logs, MCP prompts, or
   chat.

Provisioned state after GPP-2l:

1. GitHub environment `ao-kernel-live-adapter-gate` exists.
2. Admin bypass is disabled.
3. The environment uses a custom branch policy that includes `main`.
4. GitHub App deployment protection rule
   `ao-kernel-live-adapter-gate` is attached and enabled.
5. `AO_CLAUDE_CODE_CLI_AUTH` exists as an environment secret handle by
   metadata.

Runtime-binding state after GPP-2m:

1. `.github/workflows/live-adapter-gate.yml` is bound to
   `ao-kernel-live-adapter-gate`.
2. The workflow remains `workflow_dispatch` only.
3. The workflow contains no `secrets.` expression.
4. The workflow does not invoke a live adapter.

Protected workflow evidence after GPP-2n:

1. Workflow run `25020015357` was dispatched from `main`.
2. GitHub created deployment `4503862042` for
   `ao-kernel-live-adapter-gate`.
3. Job `73277880393` stayed `waiting` before any workflow step ran.
4. Pending deployment metadata reported `current_user_can_approve=false` and
   no reviewers.
5. No `live-adapter-gate-*.json` artifacts were produced.
6. The run was cancelled after bounded observation and is fail-closed
   evidence, not approval.

Blocked interpretation for a fresh or drifted setup:

1. GitHub App slug `ao-kernel-live-adapter-gate` is not visible.
2. No custom deployment protection rule is attached to the environment.
3. `AO_CLAUDE_CODE_CLI_AUTH` is not visible as an environment secret handle.

## Admin Checklist

### 1. Confirm the Selected Gate

Use the selected model from `GPP-2h`/`GPP-2i`:

```text
release_gate_model = github_app_deployment_protection_rule
required_deployment_protection_app_slug = ao-kernel-live-adapter-gate
```

If the app slug or release-gate model must change, stop here and open a new
decision PR first. Do not silently replace the selected model in GitHub admin
state.

### 2. Create or Install the GitHub App

Create or install the GitHub App/policy service with slug:

```text
ao-kernel-live-adapter-gate
```

The app must behave as an independent release authority. It must fail closed
when evidence is missing, stale, from the wrong ref, from the wrong workflow, or
when support-boundary guards drift.

Minimum approval inputs for the app:

1. repository is `Halildeu/ao-kernel`;
2. ref is protected `main`;
3. workflow identity is the approved live-adapter gate workflow;
4. required CI checks are green for the approved ref;
5. `scripts/live_adapter_gate_attest.py` or a successor reports protected
   prerequisites ready;
6. credential handle metadata exists without reading the credential value;
7. `support_widening_allowed=false` remains true until a later explicit
   promotion decision;
8. `production_platform_claim_allowed=false` remains true until a later
   explicit promotion decision.

The GPP-2n evidence shows that merely attaching the app is not enough. The app
or backing policy service must actively respond to deployment protection
callbacks. A waiting run with no app decision must be treated as blocked.

### 3. Attach the Deployment Protection Rule

Attach the GitHub App as a custom deployment protection rule on environment:

```text
ao-kernel-live-adapter-gate
```

Keep the existing environment hardening in place:

1. admin bypass disabled;
2. branch policy restricted to `main`;
3. no fork-triggered path with access to protected credentials.

### 4. Store the Credential Handle

Store the project-owned Claude Code CLI credential material, or an explicitly
approved non-API-key equivalent, as an environment secret handle:

```text
AO_CLAUDE_CODE_CLI_AUTH
```

Allowed command shape:

```bash
gh secret set AO_CLAUDE_CODE_CLI_AUTH \
  --env ao-kernel-live-adapter-gate \
  --repo Halildeu/ao-kernel
```

This command may prompt for the secret value. Do not echo the value, commit it,
print it, copy it into issue/PR comments, or read it back. The only acceptable
evidence is secret-handle metadata such as the handle name and `updatedAt`.

## Metadata Verification

Run these commands after provisioning. They are metadata-only and must not print
secret values.

```bash
gh api repos/Halildeu/ao-kernel/environments/ao-kernel-live-adapter-gate \
  --jq '{name:.name, can_admins_bypass:.can_admins_bypass, protection_rules:.protection_rules, deployment_branch_policy:.deployment_branch_policy}'
```

Expected interpretation:

1. `name` is `ao-kernel-live-adapter-gate`;
2. `can_admins_bypass` is `false`;
3. deployment branch policy is custom and includes `main`;
4. protection rules include the expected branch policy metadata.

```bash
gh api /apps/ao-kernel-live-adapter-gate --jq '{slug:.slug,id:.id,name:.name}'
```

Expected interpretation:

1. the command returns app metadata, not `HTTP 404`;
2. `slug` is `ao-kernel-live-adapter-gate`.

```bash
gh api repos/Halildeu/ao-kernel/environments/ao-kernel-live-adapter-gate/deployment_protection_rules
```

Expected interpretation:

1. `total_count` is greater than zero;
2. `custom_deployment_protection_rules` includes the selected app slug;
3. the rule is enabled for the protected environment.

```bash
gh secret list \
  --env ao-kernel-live-adapter-gate \
  --repo Halildeu/ao-kernel \
  --json name,updatedAt
```

Expected interpretation:

1. `AO_CLAUDE_CODE_CLI_AUTH` is listed;
2. no secret value is shown or requested.

After metadata is visible, run the prerequisite attestation:

```bash
python3 scripts/live_adapter_gate_attest.py \
  --artifact-path /tmp/gpp-2-post-provisioning-attestation.json \
  --output text
```

Ready metadata plus the GPP-2m workflow binding allowed GPP-2n to collect
protected workflow evidence from `main`. That evidence failed closed because
the deployment protection app/policy service did not return a decision. It
still does not authorize live adapter execution, support widening, or a
production platform claim.

## Evidence Comment Template

Use this shape when commenting on #482, #485, or a follow-up attestation PR:

```markdown
## Protected live-adapter gate provisioning evidence

- Environment: `ao-kernel-live-adapter-gate`
- Admin bypass: `<false>`
- Branch policy: `<main custom policy present>`
- GitHub App slug: `ao-kernel-live-adapter-gate`
- Deployment protection rule: `<present/enabled>`
- Secret handle: `AO_CLAUDE_CODE_CLI_AUTH` listed by metadata only
- Secret value readback: `not performed`
- Attestation artifact: `<path or uploaded artifact URL>`
- Attestation status: `<blocked|ready>`
- Support widening: `false`
- Production platform claim: `false`
```

Do not include the credential value, local auth output, MCP payloads, or
operator-only secret handoff details.

## Blocked Interpretations

Keep protected workflow evidence blocked or failed when any of these remain
true:

1. app lookup returns `HTTP 404`;
2. deployment protection rule list is empty or missing the selected app;
3. `AO_CLAUDE_CODE_CLI_AUTH` is absent from environment secret metadata;
4. admin bypass is enabled;
5. branch policy is not restricted to `main`;
6. attestation reports `overall_status=blocked`;
7. the evidence came from local operator auth rather than project-owned
   protected gate metadata;
8. a protected workflow run remains `waiting` for the deployment protection app
   and produces no artifacts;
9. pending deployment metadata reports `current_user_can_approve=false` and no
   app decision.

## Rollback and Remediation

If the wrong app slug or wrong protection rule is attached:

1. remove or disable the incorrect deployment protection rule through GitHub
   admin UI/API;
2. attach the selected app slug, or open a decision PR before selecting a new
   slug/model;
3. rerun metadata verification;
4. rerun `scripts/live_adapter_gate_attest.py`;
5. record the corrected metadata only.

If the wrong credential handle is set:

1. do not print or inspect its value;
2. remove or supersede the incorrect handle through GitHub secret management;
3. set `AO_CLAUDE_CODE_CLI_AUTH` through the approved secret handoff path;
4. verify only with `gh secret list --env ... --json name,updatedAt`.

If the selected deployment protection app is attached but does not respond:

1. do not bypass the environment gate;
2. do not repeatedly dispatch waiting workflow runs;
3. activate or configure the app webhook/policy service so it returns an
   explicit approve, deny, timeout, or failure decision;
4. rerun protected workflow evidence from `main` only after the service is
   expected to respond.

## Forbidden Actions

1. No secret value readback.
2. No local `claude` auth output treated as project-owned production evidence.
3. No Claude/MCP response treated as release authority.
4. No product end-user account treated as release authority.
5. No PAT-backed bot user treated as release authority.
6. No `--equivalent-release-gate-approved` while #489 remains not approved.
7. No bypass of the protected workflow binding.
8. No repeated protected workflow dispatch while the policy service is known
   not to respond.
9. No live adapter execution.
10. No support widening.
11. No production platform claim.
