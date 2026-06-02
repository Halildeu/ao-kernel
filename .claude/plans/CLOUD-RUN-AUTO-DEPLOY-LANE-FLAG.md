# CLOUD_RUN_AUTO_DEPLOY_ENABLED — Auto-Deploy Lane Flag

**Status:** active operational contract (CI-hygiene; not a GPP work-package)
**Date:** 2026-06-02
**Owner surface:** `.github/workflows/ao-release-gate-deploy-cloud-run.yml`,
`.github/workflows/policy-service-deploy-cloud-run.yml`
**Cross-AI review:** Claude (implementer) + Codex (reviewer), thread `019e8a05`
**Support impact:** none · **Production platform claim:** false ·
**Live adapter execution:** false

## 1. What this flag is

`CLOUD_RUN_AUTO_DEPLOY_ENABLED` is a **repository variable** (`vars.*`, never a
secret) that gates the **automatic** Cloud Run deploy lane of the two deploy
workflows:

| Workflow | Triggered by |
|---|---|
| Deploy AO Release Gate to Cloud Run | `workflow_run` on "Publish AO Release Gate Container" |
| Deploy Policy Service to Cloud Run | `workflow_run` on "Publish Policy Container" |

Both deploy jobs carry a job-level `if` with two lanes:

```yaml
if: >-
  github.event_name == 'workflow_dispatch' ||
  (
    github.event.workflow_run.conclusion == 'success' &&
    github.event.workflow_run.head_branch == 'main' &&
    github.event.workflow_run.event != 'pull_request' &&
    vars.CLOUD_RUN_AUTO_DEPLOY_ENABLED == 'true'
  )
```

- **Automatic lane** (`workflow_run`): runs only when the flag is the literal
  string `'true'`. This is the lane the flag gates.
- **Manual lane** (`workflow_dispatch`): flag-independent. An operator can always
  trigger a manual deploy/debug run; the flag does not block it.

## 2. Why it exists (the pre-cutover false-red it fixes)

The container-publish workflows trigger on `push` to `main` for
`pyproject.toml` and `ao_kernel/**` (the real dependency / source surface), so
any normal main commit touching those paths publishes an immutable
`sha-<commit>` image — correct and desirable. Each publish then fires the
downstream deploy workflow via `workflow_run`.

Cloud Run is **intentionally pre-cutover**: the GCP auth variables
(`GCP_PROJECT_ID`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT`, the
`RELEASE_GATE_SERVICE_NAME` / `AO_RELEASE_GATE_*` handles) are deliberately
unset. The Cloud Run deploy / callback-topology cutover is deferred as optional
future infrastructure under the GPP program closeout decision
(`keep_narrow_stable_runtime`), with `support_widening`,
`production_platform_claim`, and `live_adapter_execution` all still `false` (see
`gpp_status.v1.json` for the closeout record and
`GPP-2C-DEPLOYMENT-PROTECTION-CALLBACK-CUTOVER-PLAN.md` for the historical cutover
chain). Before this flag existed, the deploy job started anyway and its
"Validate trusted deploy configuration" step hard-failed on the missing
variables, painting `main` red on every `pyproject.toml` / `ao_kernel/**` push —
a recurring **false-red** on a non-required check.

With the flag unset (the default), the deploy job is **skipped** instead of
failing: the container still publishes, but the deploy surface is not red while
Cloud Run is pre-cutover. This is a false-red → non-failure conversion, **not**
turning live deploy on.

## 3. Default and values

- **Unset / absent (default):** auto-deploy lane OFF → deploy job skipped
  (non-failure; not red on `main`).
- **Exact lowercase `true`:** auto-deploy lane ON.
- Any other value (`"1"`, `"TRUE"`, `"yes"`, empty): treated as OFF — the `if`
  compares against the literal string `'true'`.

## 4. What the flag does NOT mean

Setting the flag to `true` only enables the **automatic deploy lane**. It is
**not**:

- a production-platform claim (`production_platform_claim` stays `false`),
- a live-adapter execution grant (`live_adapter_execution` stays `false`),
- a support-widening signal (`support_widening` stays `false`),
- a substitute for the "Validate trusted deploy configuration" step. With the
  lane enabled, that step still hard-fails if any required deploy variable is
  missing — that failure is a **real** misconfiguration signal (operator opted
  in but did not finish config), not a false-red.

The GPP top-level guard flags in `.claude/plans/gpp_status.v1.json` are
untouched by this flag and by the workflow change that introduced it.

## 5. Operator cutover step (when Cloud Run goes live)

When the Cloud Run cutover is genuinely authorized (per the GPP-2C operator
runbook), the operator:

1. Sets **all** required deploy repository variables first (use
   `scripts/ao_release_gate_cloud_run_repo_variables.py` /
   `scripts/policy_service_cloud_run_repo_variables.py` and provision the GCP
   Workload Identity Federation + service account + Secret Manager entries).
2. Verifies a manual `workflow_dispatch` deploy succeeds and health-checks pass.
3. **Only then** sets the flag:

   ```bash
   gh variable set CLOUD_RUN_AUTO_DEPLOY_ENABLED --repo Halildeu/ao-kernel --body true
   ```

To pause the automatic lane again without removing config, set the flag to
anything other than `true` (or `gh variable delete CLOUD_RUN_AUTO_DEPLOY_ENABLED`).

## 6. Tests

`tests/test_ao_release_gate_deploy_workflow.py` and
`tests/test_policy_service_deploy_workflow.py` each pin that the flag gates the
`workflow_run` AND-group (immediately after the non-PR guard) and that the
manual `workflow_dispatch` lane stays a standalone, flag-independent OR clause.
The assertions read the workflow text (no whole-repo `git diff`, no
`.startswith(".github/workflows/")`), so they do not trip the BLK-005 test-quality
gate.
