# General-Purpose Production Promotion Status

**Status:** GPP-2 internal gate host health probe recorded after internal
operator host bundle, Cloud Run bootstrap paths, `ao-release-gate` autonomous
deploy paths, and internal vault secret-id contract; operator-owned public
hosting evidence, webhook configuration, callback/check-run evidence, and
cutover still blocked
**Date:** 2026-04-28
**Authority:** live `origin/main`; run `git rev-parse --short origin/main` for
the current head
**Tracker issue:** [#470](https://github.com/Halildeu/ao-kernel/issues/470)
**Current slice issue:** [#567](https://github.com/Halildeu/ao-kernel/issues/567)
for internal gate host health probe
**Current slice record:** `.claude/plans/GPP-2af-INTERNAL-GATE-HOST-HEALTH-PROBE.md`
**Machine-readable status:** `.claude/plans/gpp_status.v1.json`
**Branch:** none active
**Worktree:** none active
**Mode:** written, trackable, fail-closed promotion program
**Support impact:** none
**Release impact:** none

## 1. Purpose

This document is the execution SSOT for promoting `ao-kernel` from a narrow
stable production runtime toward a general-purpose production coding automation
platform.

The current product is not allowed to claim general-purpose production support
until the work packages below close with evidence. Completing a roadmap or
decision record is not enough; production support requires runtime behavior,
tests, smoke evidence, CI or protected-gate evidence, docs, runbooks, known-bug
state, and support-boundary wording to agree.

## 2. Current Baseline

Last live verification on current `origin/main` showed:

1. `main` synchronized with `origin/main`, divergence `0 0`.
2. `python3 -m ao_kernel version` returned `ao-kernel 4.0.0`.
3. `python3 -m ao_kernel doctor` returned `8 OK, 1 WARN, 0 FAIL`.
4. `python3 scripts/packaging_smoke.py` passed with wheel build, fresh venv
   install, three CLI entrypoint checks, and installed `demo_review.py`
   final state `completed`.
5. `pytest -q` passed with `3076 passed, 2 skipped`.
6. `GP-5.9` claim decision returned `keep_narrow_stable_runtime`,
   `support_widening=false`, and `production_platform_claim=false`.
7. `live_adapter_gate_contract.py` returned `overall_status=blocked` because
   the protected live-adapter gate is still design-only.
8. GitHub environment inventory now includes `ao-kernel-live-adapter-gate`.
   The environment has custom branch policy enabled for `main` and
   `can_admins_bypass=false`.
9. `AO_CLAUDE_CODE_CLI_AUTH` was not attested as a repository or environment
   secret handle.
10. Local `claude-code-cli` operator smoke passed, but that is operator-managed
    local auth, not project-owned production evidence.
11. `gh-cli-pr` preflight passed, but live remote PR write remains explicitly
    guarded and not production-supported.
12. Controlled local patch/test rehearsal passed in a disposable worktree with
    rollback, but `support_widening=false`.
13. GPP-1 live attestation on 2026-04-25 showed only GitHub environment
    `pypi`; at that point `ao-kernel-live-adapter-gate` was absent.
14. `gh secret list --repo Halildeu/ao-kernel` returned no visible repository
    secret handles.
15. `gh secret list --env ao-kernel-live-adapter-gate --repo Halildeu/ao-kernel`
    returns an empty list; the environment exists, but the required credential
    handle is not present.
16. `.github/workflows/live-adapter-gate.yml` still has only
    `workflow_dispatch` among live-gate trigger/secret/environment grep terms;
    no `environment:`, `secrets.`, `pull_request`, or `pull_request_target`
    binding is present.
17. GPP-1b added a machine-readable operator contract so Codex and Claude Code
    read the same current work package and blocked gates from repo state instead
    of chat memory.
18. GPP-2a re-attestation on 2026-04-25 reconfirmed the same then-current
    blocker: `ao-kernel-live-adapter-gate` was absent, environment secret
    lookup returned `HTTP 404`, and `AO_CLAUDE_CODE_CLI_AUTH` was not
    project-owned/attested.
19. GPP-2b opened issue
    [#482](https://github.com/Halildeu/ao-kernel/issues/482) to track the
    external/admin provisioning work. The protected gate requires an
    independent release authority; this is not a product end-user account.
20. GPP-2b partially provisioned the GitHub environment: the environment exists,
    deployment branch policy includes `main`, and admin bypass is disabled.
    The selected GitHub App deployment protection rule and
    `AO_CLAUDE_CODE_CLI_AUTH` are still missing, so `GPP-2` remains blocked.
21. GPP-2d merged metadata-only attestation tooling so the live gate can be
    checked repeatably without reading secret values. GPP-2e records that the
    single-admin equivalent release gate is not approved; the
    `--equivalent-release-gate-approved` attestation option must not be used
    until a future explicit approval supersedes this decision.
22. GPP-2f records the required trust boundary as an independent release gate.
    Acceptable future models are GitHub-native release authority, GitHub App
    deployment protection, or OIDC-backed external secret broker. Product
    end-user accounts are not release authority.
23. GPP-2g selects GitHub-native release authority as the first GPP-2 gate
    model and records Claude Code + ao-kernel MCP as advisory consultation
    only. Claude/MCP consultation does not approve release gates, credentials,
    support widening, or production-platform claims.
24. GPP-2h supersedes the first provisioning path from required reviewer/team
    to GitHub App deployment protection. A PAT-backed bot user is rejected;
    the selected model is a policy bot connected to environment deployment
    protection. GPP-2 remains blocked.
25. GPP-2i adds metadata-only attestation support for the selected GitHub App
    deployment protection model. The current live gate remains blocked because
    the app rule and `AO_CLAUDE_CODE_CLI_AUTH` handle are not yet attested.
26. GPP-2j refreshed live metadata on 2026-04-27 after RI-6 closeout. The
    protected environment, admin-bypass-off setting, and branch policy still
    pass; the selected GitHub App slug returns `HTTP 404`, deployment
    protection rules are empty, and `AO_CLAUDE_CODE_CLI_AUTH` is not listed as
    an environment secret handle. `GPP-2` remains blocked.
27. GPP-2k adds an operator/admin provisioning runbook for #482/#485 so the
    selected GitHub App deployment protection rule and
    `AO_CLAUDE_CODE_CLI_AUTH` handle can be provisioned without secret
    readback. `GPP-2` remains blocked until a future metadata attestation exits
    `prerequisites_ready`.
28. GPP-2l records the post-provisioning metadata attestation on 2026-04-27.
    `scripts/live_adapter_gate_attest.py` now reports `overall_status=ready`,
    the selected deployment protection app rule passes, and
    `AO_CLAUDE_CODE_CLI_AUTH` is listed as an environment secret handle.
    Runtime binding has not started; `live_execution_allowed=false`,
    `support_widening=false`, and `production_platform_claim=false` remain
    closed.
29. GPP-2m binds `.github/workflows/live-adapter-gate.yml` to protected
    environment `ao-kernel-live-adapter-gate`. The workflow remains
    `workflow_dispatch` only, contains no `secrets.` expression, and still
    does not invoke a live adapter. Deployment protection inactivity, denial,
    timeout, or failure is fail-closed evidence, not approval.
30. GPP-2n dispatched `Live Adapter Gate` from `main` on run
    `25020015357`. GitHub created deployment `4503862042` for
    `ao-kernel-live-adapter-gate`, held job `73277880393` in `waiting`, exposed
    `current_user_can_approve=false`, produced no artifacts, and after bounded
    observation the run was cancelled. This is fail-closed evidence that the
    protected environment is on the execution path, but the deployment
    protection app/policy service did not return a decision.
31. GPP-2o adds a repo-owned, side-effect-free deployment protection policy
    decision core and local CLI. Raw/unverified callbacks reject fail-closed;
    contract-only approval requires verified workflow identity, ready protected
    prerequisites, `main`, no pull-request context, and closed
    live-execution/support/production-claim boundaries. GPP-2 remains blocked
    until this policy is deployed or configured behind the GitHub App webhook
    and new protected workflow evidence is collected.
32. GPP-2p adds the repo-owned webhook service boundary for that policy. It
    verifies GitHub `X-Hub-Signature-256`, accepts only
    `deployment_protection_rule`, builds the GitHub callback request body
    (`environment_name`, `state`, `comment`), and emits a local artifact
    without posting to GitHub. GPP-2 remains blocked until a hosted service is
    configured with webhook secret and GitHub App auth and new protected
    workflow evidence is collected.
33. GPP-2q adds a deployable WSGI runtime around that service boundary. It
    exposes `ao_kernel.live_adapter_gate_policy_runtime:application`, accepts
    `POST /github/deployment-protection`, reads webhook/GitHub App auth only
    from runtime environment or secret-file paths, mints installation tokens,
    and posts redacted deployment protection callback review results. GPP-2
    remains blocked until this runtime or an equivalent service is publicly
    hosted, configured in the GitHub App webhook settings, and protected
    workflow evidence confirms an explicit app response.
34. GPP-2r adds a container deploy package for the policy webhook service. It
    builds the GPP-2q runtime into a `python:3.13-slim` image, runs `gunicorn`,
    exposes `/healthz`, adds bounded no-secret container smoke tooling plus CI
    validation, and keeps `AO_CLAUDE_CODE_CLI_AUTH` out of the service. GPP-2
    remains blocked until the image is deployed to a public host, the GitHub App
    webhook URL is configured, runtime secrets are supplied through a secret
    manager, and protected workflow evidence confirms an explicit app response.
35. GPP-2s adds a GHCR image publication path for the policy webhook
    container. Pull requests build and no-secret smoke the image without
    pushing; trusted non-PR events can publish
    `ghcr.io/halildeu/ao-kernel-live-adapter-gate-policy-service:sha-<commit>`
    and `:main` without referencing protected live credentials. GPP-2 remains
    blocked until that image is deployed to a public host, the GitHub App
    webhook URL is configured, runtime secrets are supplied through a secret
    manager, and protected workflow evidence confirms an explicit app response.
36. GPP-2t adds an autonomous Cloud Run deployment path for the policy service.
    A trusted `main` image can be mirrored from GHCR to Artifact Registry,
    deployed with GitHub OIDC, bound to Secret Manager object names, and
    health-checked with `secret_value_readback=false`,
    `live_adapter_execution=false`, and `github_callback_post=false`. GPP-2
    remains blocked until cloud bootstrap is attested, a hosted service
    deployment produces evidence from `main`, the GitHub App webhook URL is
    configured to the deployed endpoint, and protected workflow evidence
    confirms an explicit callback response.
37. GPP-2u selects the durable no-human-approval merge model:
    `ao-release-gate`, a GitHub App release gate that emits a required status
    check/check-run. Admin bypass, PAT-backed bot reviewers/mergers,
    product-user release authority, and Claude/Codex release authority remain
    rejected. This does not unblock GPP-2; the deployment-protection service is
    still not hosted and `ao-release-gate` is not yet implemented, dry-run
    validated, installed, or required by branch protection.
38. GPP-2v adds the repo-owned dry-run `ao-release-gate` decision scaffold.
    `ao_kernel/ao_release_gate.py` and `scripts/ao_release_gate_decision.py`
    evaluate PR-shaped evidence, GPP status, CI status, branch freshness, diff
    scope, and forbidden authority signals without posting to GitHub or merging
    anything. GPP-2 remains blocked until the GitHub App is installed/wired to
    post the required check-run, branch protection is cut over after dry-run
    evidence, and the deployment-protection policy service is hosted.
39. GPP-2w wires that dry-run evaluator into a GitHub App webhook/check-run
    service surface. `ao_kernel/ao_release_gate_service.py` verifies webhook
    signature/event/body inputs and builds the check-run request;
    `ao_kernel/ao_release_gate_runtime.py` exposes WSGI health/webhook paths
    and can post the check-run with GitHub App installation auth when hosted.
    GPP-2 remains blocked until the service is publicly hosted/configured, real
    PR dry-run check-run evidence is collected, branch protection is cut over,
    and the deployment-protection policy service is hosted.
40. GPP-2x packages the `ao-release-gate` check-run service as a repo-owned
    container with a no-secret `/healthz` smoke path. The Dockerfile runs
    `ao_kernel.ao_release_gate_runtime:application`, the smoke script verifies
    health without webhook secrets or GitHub writes, and CI builds the
    container. GPP-2 remains blocked until the container is published or
    deployed, the hosted service is configured, real PR dry-run check-run
    evidence is collected, branch protection is cut over, and the
    deployment-protection policy service is hosted.
41. GPP-2y adds a GHCR publication path for the `ao-release-gate` container.
    PRs and codex branches build and no-secret smoke the image without pushing;
    trusted `main` or manual dispatch can publish
    `ghcr.io/halildeu/ao-kernel-ao-release-gate-service:sha-<commit>` and the
    moving `:main` tag. GPP-2 remains blocked until the image is actually
    deployed to a public host, the GitHub App webhook/runtime secrets are
    configured, real PR dry-run check-run evidence is collected, branch
    protection is cut over, and the deployment-protection policy service is
    hosted.
42. GPP-2aa adds an autonomous Cloud Run deploy path for the `ao-release-gate`
    image. Trusted `main` publication or explicit manual dispatch can mirror
    the immutable GHCR image to Artifact Registry, deploy Cloud Run with
    Secret Manager references, health-check `/healthz`, and upload deploy
    evidence. GPP-2 remains blocked until the deploy trust bootstrap exists,
    the GitHub App webhook URL is configured, real PR dry-run check-run
    evidence is collected, branch protection is cut over, and the
    deployment-protection policy service is hosted.
43. GPP-2ab adds a metadata-only bootstrap attestation tool for the GitHub
    repository variable handles required by the Cloud Run deployment workflow.
    The current live metadata check reports required handles missing.
    `metadata_ready` would mean only that the variable handles are present by
    name/timestamp. It would not prove Google Cloud OIDC trust,
    service-account permissions, Secret Manager objects, Cloud Run hosting,
    GitHub App webhook configuration, callback posting, live adapter execution,
    support widening, or production-platform readiness.
44. GPP-2ac records the product boundary after the Cloud Run/vault/webhook
    discussion. The deployment-protection policy service is operator-owned
    platform infrastructure, not an end-user setup requirement. End users must
    not be required to self-host Cloud Run, a vault, a webhook secret, or a
    GitHub App private key. GPP-2 remains blocked on operator-owned hosted
    callback evidence; repo-intelligence onboarding can be prioritized only as
    explicit opt-in/read-only work with no support widening.
45. GPP-2ad records the internal vault path. The policy service and
    `ao-release-gate` runtimes now accept vault-backed secret ids for webhook
    secrets and the GitHub App private key while preserving direct env/path
    compatibility. This makes the preferred GPP-2 unblock route
    operator-owned internal hosting plus vault-backed runtime configuration,
    not a Cloud Run-only path and not an end-user setup requirement. GPP-2
    remains blocked until public HTTPS health, GitHub App webhook, callback
    review, real PR dry-run check-run, branch-protection cutover, and protected
    workflow evidence exist.
46. GPP-2ae adds the internal operator host bundle. `deploy/internal-gate-host`
    composes Caddy, the policy service container, and the `ao-release-gate`
    container with vault-backed secret ids and a metadata-only no-secret
    attestation. This gives the no-paid-cloud operator path a repeatable repo
    surface, but it still does not prove public DNS/HTTPS, GitHub webhook
    configuration, callback/check-run posting, branch-protection cutover, or
    protected workflow pass behavior.
47. GPP-2af adds a no-secret hosted health probe for the internal gate host.
    `scripts/internal_gate_host_health_probe.py` checks the public HTTPS
    `/policy/healthz` and `/release-gate/healthz` endpoints and emits a JSON
    evidence artifact with callback, check-run, branch-protection, protected
    workflow, live-adapter, support-widening, and production-claim side effects
    pinned false. It does not configure webhooks or collect real callback/
    check-run evidence.
48. GPP-5d closes the repo-intelligence read-only workflow surface with a
    schema-backed preflight over GPP-5a/GPP-5b/GPP-5c records, public APIs,
    schemas, and negative runtime guards. GPP-6 preparation may use this
    closeout as repo-intelligence evidence, but GPP-6 execution remains
    blocked by GPP-2 and GPP-4.
49. GPP-6a adds a preparation-only read-only E2E preflight. The preflight
    report is ready and records `execution_status=blocked_by_upstream_gates`
    because GPP-2 protected gate evidence and the GPP-4 read-only adapter
    decision are still missing. It does not dispatch protected workflows, call
    live adapters, write artifacts/vectors, perform remote writes, widen
    support, or claim production-platform readiness.

## 3. Current Verdict

| Claim | Current verdict |
|---|---|
| Narrow stable governed runtime | Yes |
| General-purpose production coding automation platform | No |
| Production-certified real adapter support | No |
| Repo-intelligence production workflow integration | No |
| Production remote PR live-write support | No |
| Controlled local write-side candidate | Rehearsal passed; no support widening |

The final production claim stays closed until `GPP-9` passes.

## 4. Execution Rules

1. `origin/main` is the authority after every merge.
2. Every work package uses a dedicated worktree and a `codex/gpp-*` branch.
3. Every work package has one GitHub issue, one PR, one acceptance surface, and
   one written exit decision.
4. Runtime, docs, tests, CI, support boundary, and runbook wording must move
   together before support is widened.
5. Live external side effects are never run by default CI or fork-triggered CI.
6. Missing credentials, missing protected environments, denied live writes, or
   unavailable evidence produce `blocked`, not fake `pass`.
7. Local operator auth is useful evidence, but it is not project-owned
   production support evidence.
8. A passing rehearsal does not widen support unless the same PR explicitly
   updates the support boundary and production claim decision.
9. No final production claim is allowed before a full matrix run records at
   least three clean chains and one fail-closed chain.

## 5. Work Package Board

| WP | Status | Goal | Exit decision |
|---|---|---|---|
| `GPP-0` | Completed | Create written tracker and acceptance model | `tracker_ready_no_support_widening` |
| `GPP-1` | Completed | Protected live-adapter prerequisite attestation | `blocked_attestation_missing` |
| `GPP-1b` | Completed | Agent operating program contract | `agent_operating_contract_ready_no_support_widening` |
| `GPP-2a` | Completed | Protected live-adapter prerequisite re-attestation | `still_blocked_protected_prerequisites_missing` |
| `GPP-2b` | Partially provisioned / blocked | Protected live-adapter environment and credential provisioning | environment exists; `main` branch policy and admin-bypass-off are set; deployment protection app gate and credential handle still missing |
| `GPP-2c` | Blocked external/admin decision | Deployment-protection and credential gate resolution | `AO_CLAUDE_CODE_CLI_AUTH` and selected deployment protection app gate still missing |
| `GPP-2d` | Implemented / no support widening | Metadata-only live gate attestation tool | repeatable attestation is available; current live gate still blocked |
| `GPP-2e` | Completed / no support widening | Single-admin equivalent gate decision | `not_approved`; equivalent gate override cannot be used without a future explicit approval |
| `GPP-2f` | Completed / no support widening | Independent release gate architecture decision | independent release gate required; product end-user account is not release authority |
| `GPP-2g` | Completed / no support widening | GitHub-native release authority selection and Claude MCP consultation protocol | provisioning path superseded by GPP-2h; Claude/MCP advisory protocol remains active |
| `GPP-2h` | Completed / no support widening | Deployment protection bot gate decision | GitHub App deployment protection selected; PAT-backed bot reviewer rejected |
| `GPP-2i` | Completed / no support widening | Deployment protection attestation support | selected app-gate metadata is recognized; current live gate still blocked |
| `GPP-2j` | Completed / no support widening | Protected live gate metadata refresh after RI-6 closeout | current live gate still blocked; selected app gate and credential handle missing |
| `GPP-2k` | Completed / no support widening | Protected live gate provisioning runbook | operator/admin checklist ready; current live gate still blocked |
| `GPP-2l` | Completed / no support widening | Protected live gate prerequisites-ready attestation | protected prerequisites ready; runtime binding not started |
| `GPP-2m` | Completed / no support widening | Protected live gate runtime binding | workflow bound to protected environment; live execution still disabled |
| `GPP-2n` | Completed / no support widening | Protected live gate workflow evidence | protected workflow reached environment gate and failed closed because policy response is missing |
| `GPP-2o` | Completed / no support widening | Deployment protection policy decision core | repo-owned decision core and CLI ready; service is not yet deployed/configured |
| `GPP-2p` | Completed / no support widening | Deployment protection policy webhook service scaffold | repo-owned webhook/callback request scaffold ready; service is not yet deployed/configured |
| `GPP-2q` | Completed / no support widening | Deployable policy webhook runtime | repo-owned WSGI runtime and GitHub App callback POST path ready; hosted service is not yet deployed/configured |
| `GPP-2r` | Completed / no support widening | Policy webhook container deploy package | repo-owned container image package and bounded no-secret health smoke/CI job ready; hosted service is not yet deployed/configured |
| `GPP-2s` | Completed / no support widening | Policy container image publication | repo-owned GHCR image publish path ready; hosted service is not yet deployed/configured |
| `GPP-2t` | Completed / no support widening | Autonomous policy service deployment path | repo-owned Cloud Run OIDC deploy path ready; cloud bootstrap, hosted health evidence, GitHub App webhook config, and callback evidence are not yet attested |
| `GPP-2u` | Completed / no support widening | Autonomous GitHub App release-gate decision | `ao-release-gate` required status-check model selected; app implementation/cutover still required |
| `GPP-2v` | Completed / no support widening | `ao-release-gate` dry-run scaffold | side-effect-free decision core and CLI ready; GitHub App wiring/cutover still required |
| `GPP-2w` | Completed / no support widening | `ao-release-gate` check-run service wiring | webhook/check-run request service and WSGI GitHub App POST runtime ready; hosting, real PR evidence, and branch-protection cutover still required |
| `GPP-2x` | Completed / no support widening | `ao-release-gate` container package | container build target, no-secret health smoke, and CI job ready; publish/hosting, real PR evidence, and branch-protection cutover still required |
| `GPP-2y` | Completed / no support widening | `ao-release-gate` container image publication | GHCR publish workflow ready; public hosting, real PR evidence, and branch-protection cutover still required |
| `GPP-2aa` | Completed / no support widening | `ao-release-gate` autonomous deploy path | Cloud Run deploy workflow ready; cloud bootstrap, webhook config, real PR evidence, and branch-protection cutover still required |
| `GPP-2ab` | Completed / no support widening | Policy Cloud Run bootstrap attestation | metadata-only attestation tool ready; required repository variable handles are currently missing; GCP trust, Secret Manager objects, hosted service evidence, GitHub App webhook config, and callback evidence are not yet attested |
| `GPP-2ac` | Completed / no support widening | Operator gate and end-user onboarding boundary | GPP-2 gate hosting is operator-owned platform infrastructure; end users must not self-host Cloud Run, vault, webhook, or GitHub App private-key setup |
| `GPP-2ad` | Completed / no support widening | Internal vault gate secret contract | policy and release-gate runtimes accept vault-backed secret ids; services are still not hosted/evidenced |
| `GPP-2ae` | Completed / no support widening | Internal operator host bundle | Caddy + policy service + `ao-release-gate` compose bundle and no-secret metadata attestation ready; services are still not publicly hosted/evidenced |
| `GPP-2af` | Completed / no support widening | Internal gate host health probe | no-secret public HTTPS health probe ready; actual hosted health evidence, webhooks, callback/check-run evidence, and cutover are still missing |
| `GPP-2` | Blocked / internal hosting/config/evidence and release-gate cutover missing | Protected live-adapter gate runtime binding | deployment protection app/policy service and `ao-release-gate` must be hosted with public HTTPS health evidence, configured with vault-backed runtime secrets and webhooks, and evidenced/cut over before human-free program merges |
| `GPP-3` | Not started | Real-adapter usage/cost evidence closure | `cost_evidence_ready` / `defer_cost_policy` |
| `GPP-4` | Not started | `claude-code-cli` production-certified read-only decision | `promote_read_only` / `keep_operator_beta` / `defer` |
| `GPP-5a` | Completed / no support widening | Repo-intelligence product onboarding contract | GitHub App install + selected repositories + optional `.ao/config.yml`; no end-user Cloud Run, vault, webhook, private key, or gate service hosting |
| `GPP-5b` | Completed / no support widening | Repo-intelligence explicit workflow context resolver | product onboarding + explicit handoff validation compose into visible read-only handoff pointer; no auto-feed or runtime execution |
| `GPP-5c` | Completed / no support widening | Repo-intelligence read-only workflow surface output contract | accepted workflow context converts to a visible pointer + source metadata payload; no Markdown body, auto-feed, MCP, root export, or runtime execution |
| `GPP-5d` | Completed / no support widening | Repo-intelligence read-only workflow surface closeout preflight | schema-backed closeout verifies GPP-5a/GPP-5b/GPP-5c, public APIs, schemas, and negative runtime guards; GPP-6 execution remains blocked by GPP-2/GPP-4 |
| `GPP-5` | Completed as read-only building block / no support widening | Repo-intelligence explicit workflow integration | onboarding, workflow-context resolver, output contract, and closeout preflight ready; runtime ingestion remains disabled |
| `GPP-6a` | Completed / preparation only / no support widening | Read-only E2E preflight contract | preflight ready; execution blocked by GPP-2 protected gate and GPP-4 adapter decision |
| `GPP-6` | Preparation only / execution blocked | Read-only production E2E over real adapter + repo intelligence | `read_only_e2e_ready` / `blocked_e2e` |
| `GPP-7` | Not started | Controlled write-side production candidate | `write_candidate_ready` / `keep_rehearsal_only` |
| `GPP-8` | Not started | Remote PR live-write promotion candidate | `remote_pr_candidate_ready` / `keep_sandbox_only` |
| `GPP-9` | Not started | Full production matrix + claim decision | `promote_general_purpose_production` / `promote_general_purpose_beta` / `keep_narrow_stable_runtime` |

## 6. GPP-0 - Tracker and SSOT

**Goal:** Make the remaining production promotion work written, discoverable,
and executable step by step.

**Status:** completed on `main` by PR
[#471](https://github.com/Halildeu/ao-kernel/pull/471).

**Entry criteria:**

1. `main` is clean and synchronized with `origin/main`.
2. No open PR conflicts with this docs/status-only tracker.

**Scope:**

1. Add this status file.
2. Link the tracker issue.
3. Record the current baseline and blocker list.
4. Define `GPP-1..GPP-9` with acceptance criteria.

**Acceptance criteria:**

1. This file records that the current product is a narrow stable runtime, not
   a general-purpose production platform.
2. `GPP-1` is identified as the next active work after this tracker merges.
3. No runtime code changes are made.
4. No support boundary is widened.
5. No release tag or PyPI publish is triggered.

**Validation:**

1. `git diff --check`
2. `python3 -m ao_kernel doctor`
3. `python3 -m ao_kernel version`
4. stale-claim grep for accidental production wording

## 7. GPP-1 - Protected Live-Adapter Prerequisite

**Goal:** Establish project-owned protected live-adapter prerequisites before
any workflow binding or support promotion.

**Status:** completed on `main` by PR
[#473](https://github.com/Halildeu/ao-kernel/pull/473).

**Exit decision:** `blocked_attestation_missing`.

**Entry criteria:**

1. `GPP-0` merged.
2. Current `origin/main` remains clean.

**Required decisions:**

1. Protected environment name: `ao-kernel-live-adapter-gate`.
2. Credential handle: `AO_CLAUDE_CODE_CLI_AUTH` or an explicitly approved
   replacement.
3. Secret values are never read; only handle existence is attested.

**Acceptance criteria:**

1. GitHub environment inventory contains `ao-kernel-live-adapter-gate`: met.
2. Deployment branch policy is restricted through custom branch policies and
   includes `main`: met.
3. Admin bypass is disabled on `ao-kernel-live-adapter-gate`: met.
4. Required secret handle is attested at repository or environment scope: not
   met; environment-scoped secret lookup returns an empty list.
5. Independent release gate is configured: not met; GPP-2h/GPP-2i selected
   GitHub App deployment protection, and the app rule is not yet attested.
6. Fork-triggered PR contexts cannot access protected credentials: met for the
   current design-only workflow, because the workflow is `workflow_dispatch`
   only and has no `environment:` or `secrets.` reference.
7. Missing secret or selected deployment-protection gate produces
   `blocked_attestation_missing`: met by this slice.
8. Status docs and support boundary still say no support widening: met.

**Validation:**

1. `gh api repos/Halildeu/ao-kernel/environments`
2. `gh secret list --repo Halildeu/ao-kernel`
3. workflow file inspection for no accidental secret exposure
4. schema-backed prerequisite report if implemented

**Decision record:** `.claude/plans/GPP-1-PROTECTED-LIVE-ADAPTER-PREREQUISITE-ATTESTATION.md`

## 8. GPP-1b - Agent Operating Program Contract

**Goal:** Make Codex and Claude Code follow the repo-owned GPP program state
before choosing or implementing the next work package.

**Status:** completed by PR [#475](https://github.com/Halildeu/ao-kernel/pull/475).

**Exit decision target:** `agent_operating_contract_ready_no_support_widening`.

**Scope:**

1. Add `AGENTS.md` startup and execution contract.
2. Add `.claude/plans/gpp_status.v1.json` as the machine-readable GPP status.
3. Add `scripts/gpp_next.py` to print the current/active WP and blocked gates.
4. Add tests that pin the current WP, blocked WP, and no-widening guards.
5. Keep `GPP-2` blocked.

**Acceptance criteria:**

1. `python3 scripts/gpp_next.py` reports `GPP-2` as blocked after the merge.
2. `python3 scripts/gpp_next.py --output json` returns valid JSON.
3. `support_widening_allowed`, `production_platform_claim_allowed`, and
   `live_adapter_execution_allowed` are all `false`.
4. `GPP-2` remains listed as blocked.
5. `AGENTS.md` tells Codex and Claude Code to read repo state before acting.
6. No live adapter execution, credential binding, support widening, release, or
   production claim is introduced.

**Decision record:** `.claude/plans/GPP-1b-AGENT-OPERATING-PROGRAM-CONTRACT.md`

## 9. GPP-2 - Protected Live-Adapter Gate Runtime Binding

**Goal:** Convert the current design-only `live-adapter-gate.yml` into a
protected manual gate that can actually run a real adapter under project-owned
evidence.

**Status:** blocked after GPP-2af; policy decision core, webhook scaffold,
deployable WSGI runtime, container package, GHCR image publication path,
Cloud Run deploy automation, metadata-only bootstrap attestation tooling,
internal vault-backed secret-id runtime support, internal operator host bundle,
hosted health probe, `ao-release-gate` dry-run/check-run/container/publish/
deploy automation, and release-gate fail-closed policy records and
operator/end-user boundary decision exist, but operator-owned hosted service
deployment/configuration, real PR check-run evidence, branch-protection
cutover, and callback evidence are still missing.

**Entry criteria:**

1. `GPP-1` exit decision is `prerequisites_ready`.
2. Protected environment and credential handle are attested.

GPP-2l records ready protected prerequisite metadata. GPP-2m binds the manual
workflow to `ao-kernel-live-adapter-gate` without invoking a live adapter or
using the protected credential value. GPP-2n proves the bound workflow reaches
the protected environment gate, but the deployment protection app/policy
service did not return an approval, denial, timeout, or failure decision.
GPP-2o adds the repo-owned policy decision core and CLI that the service can
use, but no webhook/service deployment or GitHub callback review evidence has
been recorded. GPP-2p adds the repo-owned webhook service boundary and callback
request artifact, but no hosted endpoint, webhook secret, GitHub App auth, or
actual callback POST evidence has been recorded. GPP-2q adds a deployable WSGI
runtime plus GitHub App installation-token callback POST path, but no public
endpoint has been hosted or configured in the GitHub App webhook settings.
GPP-2r adds a container deployment package plus bounded no-secret health smoke
tooling with CI validation, but no public hosted endpoint, webhook URL, runtime
secret manager configuration, or live callback evidence has been recorded.
GPP-2s adds a GHCR image publication path for trusted non-PR builds, but no
public hosted endpoint, webhook URL, runtime secret manager configuration, or
live callback evidence has been recorded. GPP-2t adds an autonomous Cloud Run
deploy path, but no GCP trust bootstrap, hosted health evidence, webhook URL
configuration, or callback evidence has been recorded. GPP-2ab adds a
metadata-only repository variable bootstrap attestation tool for that deploy
path, and the current live metadata check reports required handles missing.
Even after a future `metadata_ready`, that status is not Google Cloud OIDC,
Secret Manager, Cloud Run, webhook, or callback evidence.
GPP-2u selects `ao-release-gate`, a GitHub App release authority that should
emit a required status check/check-run for human-free PR merges. That app has
not yet been implemented, installed, dry-run validated, or required by branch
protection; GitHub App PR-review counting remains a spike only, not the durable
enforcement path.
GPP-2v adds the side-effect-free evaluator and CLI that a future GitHub App can
call to produce an `ao-release-gate` check-run decision. It produces dry-run
artifacts only; it does not post to GitHub, grant merge authority, or change
branch protection.
GPP-2w adds the webhook service boundary and WSGI runtime that can post the
dry-run `ao-release-gate` check-run with GitHub App installation auth when
hosted. It still does not merge PRs, grant merge authority, change branch
protection, or prove real PR check-run evidence.
GPP-2x adds the container build target and no-secret health smoke for that WSGI
runtime. It still does not publish the image, host the service, post check-runs
to GitHub, grant merge authority, or change branch protection.
GPP-2y adds the GHCR image publication path for that release-gate container.
It still does not host the service, configure a webhook URL, post check-runs to
GitHub, grant merge authority, or change branch protection.
GPP-2aa adds the autonomous Cloud Run deploy workflow for that release-gate
image. It still does not prove cloud bootstrap, configure the GitHub App webhook
URL, post check-runs, collect real PR evidence, grant merge authority, or change
branch protection.
GPP-2ac records that the live-adapter deployment-protection service and the
release-gate hosting path are operator-owned platform infrastructure. They are
not setup requirements for product end users, and they do not block read-only
repo-intelligence onboarding design work that avoids live execution and support
widening.
GPP-2ad adds internal vault-backed secret-id resolution to both hosted gate
runtimes. This lets the operator run the repo-owned containers on internal
platform infrastructure with secret ids such as
`AO_LIVE_ADAPTER_GATE_WEBHOOK_SECRET_ID`,
`AO_RELEASE_GATE_WEBHOOK_SECRET_ID`, and
`AO_GITHUB_APP_PRIVATE_KEY_PEM_ID`. It does not host either service, configure
GitHub webhooks, post callbacks/check-runs, grant merge authority, or unblock
live adapter execution.
GPP-2ae adds `deploy/internal-gate-host` as the no-paid-cloud operator host
bundle. It composes Caddy with the two repo-owned gate service containers,
routes `/github/deployment-protection` and `/github/ao-release-gate`, mounts
the GPP status file for `ao-release-gate`, and keeps secret material behind
vault-backed secret ids. Its metadata-only attestation proves only that the
checked-in host bundle is coherent and no direct secret markers are present. It
does not run Docker, contact a vault, configure webhooks, post callbacks or
check-runs, change branch protection, dispatch protected workflows, or execute
a live adapter.
GPP-2af adds `scripts/internal_gate_host_health_probe.py` so the operator can
collect no-secret health evidence after that host is deployed. The probe
requires HTTPS for public evidence, validates the expected `GPP-2q` and
`GPP-2w` health payloads, and emits an artifact with secret readback, webhook
configuration, callback posts, check-run posts, branch-protection cutover,
protected workflow dispatch, live adapter execution, support widening, and
production-platform claims all false. It does not by itself host services or
unblock GPP-2.

**Acceptance criteria:**

1. Workflow binds to `environment: ao-kernel-live-adapter-gate`: met by
   GPP-2m.
2. Manual dispatch can run `claude-code-cli` preflight: not yet met; live
   execution remains disabled.
3. A governed workflow smoke runs through the protected gate: not yet met; the
   protected job remained waiting before any steps ran.
4. Evidence artifact records adapter identity, workflow identity, event order,
   timeout, redaction status, artifact paths, and failure mode.
5. Missing auth, missing binary, timeout, prompt denial, malformed output, and
   policy denial are all non-pass states.
6. Default CI and fork PRs do not execute live adapters.
7. `support_widening=false` remains until `GPP-4`.

**Validation:**

1. protected workflow dispatch on `main`
2. downloaded evidence artifacts validate against schema
3. negative/fail-closed runs are recorded
4. local tests for artifact schema and status mapping

## 10. GPP-3 - Real-Adapter Usage and Cost Evidence

**Goal:** Close or explicitly decide the `BC-10` blocker from `GP-5.9`.

**Entry criteria:**

1. `GPP-2` produces protected live-adapter evidence.

**Acceptance criteria:**

1. Every live adapter run records adapter identity and elapsed time.
2. Every live adapter run records token/cost data or an explicit unavailable
   reason such as `usage_missing`, `token_unavailable`, or `cost_unavailable`.
3. Missing usage data is not silently treated as zero cost.
4. Evidence schema, docs, and support boundary agree on the meaning of
   unavailable usage.
5. `GP-5.9` `BC-10` can be reclassified from missing evidence to pass or a
   deliberate policy exception.

**Validation:**

1. schema tests for usage/cost evidence
2. live protected run with successful evidence
3. live or simulated unavailable-usage path
4. support-boundary wording check

## 11. GPP-4 - Production-Certified Read-Only Adapter Decision

**Goal:** Decide whether `claude-code-cli` can move from
`Beta (operator-managed)` to production-certified read-only.

**Entry criteria:**

1. `GPP-2` live protected gate is ready.
2. `GPP-3` usage/cost evidence is ready or explicitly resolved.

**Acceptance criteria:**

1. At least three protected clean read-only adapter runs pass.
2. At least one protected fail-closed run proves non-pass behavior.
3. Failure-mode matrix includes auth missing, binary missing, timeout, prompt
   denied, malformed output, policy denied, and redaction checks.
4. Decision artifact chooses one: `promote_read_only`, `keep_operator_beta`,
   or `defer`.
5. Docs, known-bugs, runbook, and support-boundary update in the same PR.

**Validation:**

1. protected gate run artifacts
2. targeted adapter tests
3. support-boundary grep for tier consistency
4. no production write support is implied

## 12. GPP-5 - Repo-Intelligence Workflow Integration

**Goal:** Move repo intelligence from explicit operator handoff toward
governed workflow integration without hidden prompt injection.

**Entry criteria:**

1. `RI-5b` create-only root export remains Beta/operator-managed.
2. No hidden root export, MCP, or `context_compiler` feed is active by default.

**Acceptance criteria:**

1. Workflow context ingestion is explicit opt-in.
2. Context payload carries source paths, line ranges, source hashes, namespace,
   freshness state, and support tier.
3. Missing metadata, stale sources, hash mismatch, or unknown namespace fail
   closed.
4. No MCP tool, root file write, or context compiler auto-feed is introduced
   without an explicit design gate.
5. Support tier remains clear: beta building block or production read-only
   building block candidate, not final platform claim.

**Validation:**

1. valid handoff test
2. stale handoff test
3. missing metadata test
4. disabled-config test
5. negative grep for hidden MCP/root export/context compiler wiring

**GPP-5a closeout:** PR for issue
[#553](https://github.com/Halildeu/ao-kernel/issues/553) defines the
product-facing onboarding contract before workflow ingestion is widened. The
accepted user path is GitHub App installation, explicit repository selection,
and optional repo-local `.ao/config.yml` style configuration. Product users are
not required to host Cloud Run, vault/Secret Manager, webhook endpoints, GitHub
App private keys, deployment-protection services, or `ao-release-gate`.

GPP-5 remains open for explicit read-only workflow integration. GPP-2 remains
blocked, and this slice does not authorize live-adapter execution, support
widening, production platform claims, hidden prompt injection, MCP exposure,
root export requirements, or context-compiler auto-feed.

**GPP-5b closeout:** PR for issue
[#555](https://github.com/Halildeu/ao-kernel/issues/555) adds a workflow-level
resolver that composes the product onboarding contract with the existing
explicit repo-query handoff validator. The accepted result is a visible handoff
pointer and source metadata only. It does not return hidden prompt content,
write context artifacts, expose MCP tools, enable root export, auto-feed the
context compiler, call adapters, or run live-adapter code.

GPP-5 remains open for output contract and read-only workflow surface work.
GPP-2 remains blocked, and support widening / production platform claims remain
closed.

**GPP-5c closeout:** PR for issue
[#557](https://github.com/Halildeu/ao-kernel/issues/557) adds a read-only
workflow surface output contract on top of the accepted explicit workflow
context. The accepted output carries handoff path, Markdown SHA-256, namespace,
source artifact hashes, freshness state, stale candidate count, source paths,
line ranges, and source content hashes. It explicitly excludes Markdown body
text and keeps hidden prompt injection, context compiler auto-feed, MCP
exposure, root export, artifact/vector writes, live adapter execution, support
widening, and production platform claims disabled.

After GPP-5c, GPP-5 remained open for read-only workflow surface closeout and
GPP-6 preparation. GPP-2 remained blocked, and that slice did not authorize
runtime adapter execution or support/production promotion.

**GPP-5d closeout:** PR for issue
[#559](https://github.com/Halildeu/ao-kernel/issues/559) adds the
schema-backed closeout preflight for GPP-5. The preflight verifies the
GPP-5a/GPP-5b/GPP-5c records, public repo-intelligence APIs, JSON schemas,
context compiler negative guard, workflow-definition negative guard, MCP
negative guard, and program flags. GPP-5 is now closed as a read-only building
block only.

GPP-6 preparation may use this closeout as repo-intelligence evidence, but
GPP-6 execution remains blocked until GPP-2 protected gate evidence and the
GPP-4 read-only adapter decision are ready. This closeout does not authorize
runtime ingestion, live-adapter execution, support widening, or production
platform claims.

## 13. GPP-6 - Read-Only Production E2E

**Goal:** Prove the first complete read-only coding automation chain with real
adapter and repo intelligence.

**Target chain:**

```text
repo scan/index/query
-> explicit context handoff
-> protected real adapter
-> governed workflow
-> review_findings or patch_plan artifact
-> evidence timeline
```

**Entry criteria:**

1. `GPP-4` has a production-certified read-only adapter decision or explicit
   protected beta permission for this rehearsal.
2. `GPP-5d` repo-intelligence closeout is ready.

**Acceptance criteria:**

1. At least three clean read-only E2E runs pass.
2. Each run records context source hashes, adapter evidence, policy events,
   artifact path, redaction status, and final state.
3. At least one fail-closed E2E run is recorded.
4. No write or remote side effect occurs.
5. Evidence can be reproduced by another operator following the runbook.

**Validation:**

1. protected E2E run artifacts
2. schema validation
3. event-order assertions
4. runbook reproduction check

**GPP-6a preflight:** PR for issue
[#561](https://github.com/Halildeu/ao-kernel/issues/561) adds a
preparation-only GPP-6 preflight. The report records the target chain and entry
criteria, verifies GPP-5d closeout evidence, and pins
`execution_status=blocked_by_upstream_gates` because `GPP-2` remains blocked
and `GPP-4` is missing.

This slice does not dispatch protected workflows, invoke live adapters, write
repo-intelligence artifacts or vectors, perform remote writes, widen support,
or claim production-platform readiness. GPP-6 execution remains blocked.

## 14. GPP-7 - Controlled Write-Side Production Candidate

**Goal:** Promote local patch/test from rehearsal-only toward a production
candidate under disposable/dedicated worktree controls.

**Entry criteria:**

1. `GPP-6` read-only E2E is ready.
2. Path-scoped ownership remains enforced.

**Acceptance criteria:**

1. Active main worktree is never modified.
2. Diff preview is mandatory before apply.
3. Explicit apply approval is mandatory.
4. Path-scoped write ownership is acquired and released.
5. Targeted tests are explainable.
6. Full-gate fallback is available.
7. Rollback and idempotency are verified.
8. At least three clean controlled write runs pass.
9. At least one conflict/fail-closed run is recorded.

**Validation:**

1. controlled patch/test reports
2. dirty-main guard tests
3. rollback artifact verification
4. path ownership event checks

## 15. GPP-8 - Remote PR Live-Write Promotion Candidate

**Goal:** Move `gh-cli-pr` from preflight/disposable rehearsal toward a
production candidate without granting arbitrary repository write support by
accident.

**Entry criteria:**

1. `GPP-7` controlled write candidate is ready.
2. Disposable sandbox target is defined.

**Acceptance criteria:**

1. `--allow-live-write` remains required before any remote write.
2. Non-disposable or arbitrary production repositories are blocked by default.
3. At least three sandbox live-write rehearsals pass.
4. Each rehearsal creates, verifies, closes, verifies closed, deletes branch,
   and verifies branch deletion.
5. Failure modes cover auth denied, permission denied, branch exists, PR
   creation failed, PR close failed, and branch delete failed.
6. Support boundary distinguishes sandbox rehearsal from arbitrary user repo
   production support.

**Validation:**

1. sandbox live-write artifacts
2. cleanup verification
3. no side effects remaining
4. docs/runbook/known-bugs parity

## 16. GPP-9 - Full Production Matrix and Claim Decision

**Goal:** Decide the general-purpose production claim with complete evidence.

**Entry criteria:**

1. `GPP-1..GPP-8` have explicit pass/defer decisions.
2. Any deferred item is declared non-blocking with support-boundary wording.

**Required matrix:**

1. three clean full chains;
2. one fail-closed full chain;
3. protected real adapter;
4. repo-intelligence context;
5. controlled patch/test;
6. disposable PR rollback;
7. operations/runbook readiness;
8. support docs parity.

**Acceptance criteria:**

1. Full matrix report validates against schema.
2. `BC-1` and `BC-10` are not blocked.
3. `production_platform_claim_decision` emits one of:
   - `promote_general_purpose_production`
   - `promote_general_purpose_beta`
   - `keep_narrow_stable_runtime`
4. If support widens, the same PR updates docs, known bugs, runbook, support
   boundary, examples, and release notes.
5. If support does not widen, the decision explains the blocker and next
   work package.

**Validation:**

1. `python3 scripts/gp5_full_production_rehearsal.py --matrix-file <matrix>`
2. `python3 scripts/gp5_platform_claim_decision.py --output json`
3. full CI
4. wheel-installed packaging smoke
5. protected live-adapter evidence artifacts

## 17. Current Active Work

No live execution/support-widening work is active. `GPP-2` is blocked on the
deployment protection app/policy service response path and the autonomous
release-gate wiring/cutover path. GPP-2l records a metadata-only
`overall_status=ready` prerequisite attestation, GPP-2m binds
`.github/workflows/live-adapter-gate.yml` to
`ao-kernel-live-adapter-gate` without using secret values, GPP-2n proves the
bound workflow reaches that protected environment but stays waiting without a
policy decision, and GPP-2o adds the repo-owned decision core that can return
`approve_contract_gate` or `reject` once it is placed behind the GitHub App
webhook. GPP-2p adds the repo-owned webhook service scaffold that verifies
GitHub signatures, constrains the event, and builds the deployment callback
request without posting it. GPP-2q adds the deployable WSGI runtime and GitHub
App callback POST path, but that runtime has not yet been hosted or configured
as the GitHub App webhook URL. GPP-2r adds the container deploy package and
bounded no-secret health smoke/CI job, but the container has not yet been
deployed to a public host or configured in the GitHub App webhook settings.
GPP-2s adds the GHCR image publication path for that container, but the image
has not yet been deployed to a public host or configured in the GitHub App
webhook settings. GPP-2u selects `ao-release-gate`, a GitHub App required
webhook settings. GPP-2t adds the autonomous Cloud Run deploy path for the
policy service, but cloud OIDC/Secret Manager bootstrap, hosted health evidence
from `main`, GitHub App webhook URL configuration, and live callback evidence
are not yet attested. GPP-2ab adds a metadata-only bootstrap attestation tool
for the Cloud Run deploy workflow's required GitHub repository variable
handles, and the current live metadata check reports required handles missing.
A future `metadata_ready` must be treated only as repository-variable evidence,
not GCP trust, hosted service, webhook configuration, callback, or live
execution evidence. GPP-2u selects `ao-release-gate`, a GitHub App required
status-check authority for no-human-approval program PR merges. GPP-2v adds
`ao_kernel/ao_release_gate.py` and `scripts/ao_release_gate_decision.py` as the
dry-run decision core and CLI that can produce future `ao-release-gate`
check-run output. GPP-2w adds `ao_kernel/ao_release_gate_service.py` and
`ao_kernel/ao_release_gate_runtime.py` so a hosted GitHub App can verify
webhooks, evaluate the dry-run release-gate decision, and post the check-run
with installation auth. The service is still not publicly hosted/configured,
real PR dry-run check-run evidence is not collected, and branch protection does
not yet require it. GPP-2x adds `deploy/ao-release-gate-service/Dockerfile`
and `scripts/ao_release_gate_container_smoke.py` so the same runtime has a
repo-owned no-secret container health smoke path. GPP-2y adds
`.github/workflows/ao-release-gate-container-publish.yml`, which builds and
smokes the image on PR/codex branch changes and publishes only on trusted
`main` or manual dispatch events. The image may now be published as a deploy
artifact, but it is still not hosted and no GitHub delivery evidence exists.
GPP-2aa adds `.github/workflows/ao-release-gate-deploy-cloud-run.yml`, which can
mirror the immutable release-gate image to Artifact Registry, deploy Cloud Run
with Secret Manager references, health-check `/healthz`, and upload deploy
evidence after trusted `main` publication or manual dispatch. The deploy path
is not itself GitHub App webhook configuration, check-run evidence, branch
protection cutover, or merge authority.
GPP-2b
[#482](https://github.com/Halildeu/ao-kernel/issues/482) and GPP-2c
[#485](https://github.com/Halildeu/ao-kernel/issues/485) are resolved at the
metadata prerequisite level: the protected environment exists, admin bypass is
disabled, `main` branch policy is present, the selected GitHub App deployment
protection rule is enabled, and `AO_CLAUDE_CODE_CLI_AUTH` is listed as an
environment secret handle.

GPP-2d provides `scripts/live_adapter_gate_attest.py` for repeatable
metadata-only evidence. GPP-2e still records the single-admin equivalent gate
as `not_approved`; the attestation override
`--equivalent-release-gate-approved` remains forbidden until a future explicit
approval supersedes [#489](https://github.com/Halildeu/ao-kernel/issues/489).
GPP-2f clarifies that the gate is an independent release authority, not a
product end-user account. GPP-2g records Claude/MCP consultation as advisory
only. GPP-2h selects GitHub App deployment protection, GPP-2i adds attestation
support for that model, GPP-2j refreshes blocked metadata, GPP-2k adds the
operator provisioning runbook, and GPP-2u selects a separate GitHub App release
gate for PR merge automation. GPP-2v provides the dry-run evaluator for that
release gate while keeping `merge_authority_enabled=false`. GPP-2w provides the
check-run service/runtime surface while still keeping merge authority disabled.
GPP-2x provides the container package while still avoiding secret value
readback, GitHub check-run POSTs, branch-protection cutover, and live adapter
execution. GPP-2y provides the release-gate container publish path while still
avoiding public hosting, webhook configuration, GitHub check-run POSTs,
branch-protection cutover, and live adapter execution. GPP-2aa provides the
release-gate Cloud Run deploy workflow while still avoiding secret value
readback, GitHub check-run POST evidence, branch-protection cutover, merge
authority, and live adapter execution.
Existing PRs
[#536](https://github.com/Halildeu/ao-kernel/pull/536) and
[#538](https://github.com/Halildeu/ao-kernel/pull/538) can stay blocked by
review-required branch protection until independent approval or the future
`ao-release-gate` required-check cutover exists; admin bypass remains
forbidden.

The next GPP-2 action is to run
`scripts/policy_service_cloud_run_bootstrap_attest.py`, provision any missing
repository variable handles, then bootstrap or run the autonomous policy
service deployment path: GitHub OIDC trust, Google service-account permissions,
Artifact Registry, Cloud Run, and Secret Manager object handles must exist
without secret value readback, then the deploy workflow must produce hosted
`/healthz` evidence from a trusted `main` image. After that, configure or verify
the `ao-kernel-live-adapter-gate` GitHub App webhook URL points to the deployed
`/github/deployment-protection` endpoint so the service can receive protected
deployment callbacks, enrich them with trusted context, evaluate the repo-owned
policy modules, attach GitHub App auth at runtime, and post an explicit GitHub
deployment review callback. In parallel, bootstrap/run the trusted dry-run
`ao-release-gate` deploy path from `main`, configure that check-run service's
GitHub App webhook URL, collect real PR check-run evidence, and only then cut
branch protection/rulesets over to require `ao-release-gate`. Do not
repeatedly dispatch `.github/workflows/live-adapter-gate.yml` until that
service is expected to respond. GPP-6a records read-only E2E preflight
preparation, but GPP-6 execution remains blocked by GPP-2 and GPP-4. Any
follow-up must keep fork and pull-request contexts away from protected
credentials, must not use
`AO_CLAUDE_CODE_CLI_AUTH` through a `secrets.` expression until a later
live-execution slice explicitly permits it, must reject PAT-backed bots and
admin bypass for PR merge automation, and must keep
`live_execution_allowed=false`, `support_widening=false`, and
`production_platform_claim=false`.

## 18. Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| Protected environment never appears | Real-adapter production support stays blocked | Keep `claude-code-cli` Beta/operator-managed; do not widen support |
| Local auth mistaken for project-owned evidence | False production claim | Require protected gate artifacts for GPP-4 |
| Usage/cost remains unavailable | BC-10 stays blocked | Add explicit unavailable policy or defer promotion |
| Repo-intelligence hidden injection | Context trust boundary breaks | Explicit opt-in + metadata fail-closed tests |
| Remote PR writes leak to arbitrary repos | Production side effect risk | Disposable guard + explicit allow flag + rollback evidence |
| Full matrix becomes stale | Fake green promotion | Require fresh artifacts from current `origin/main` |
| Advisory consultation mistaken for release authority | Protected gate can be falsely unblocked | Claude/MCP protocol is advisory only; deployment protection app or explicitly approved equivalent gate remains required |
| Bot account mistaken for deployment protection | Same operator can rubber-stamp the gate | PAT-backed bot reviewer is rejected; use GitHub App deployment protection |
| Deployment protection app installed but inactive | Protected workflow waits forever and produces no artifacts | Treat waiting/cancelled runs as fail-closed; activate policy service before repeating evidence dispatch |
| Policy decision core exists but is not deployed | Protected workflow still receives no app response | Treat GPP-2o as implementation readiness only; deploy/configure webhook before rerunning evidence |
| Webhook scaffold exists but has no runtime auth | Callback artifact exists but GitHub still receives no review | Treat GPP-2p as implementation readiness only; deploy with webhook secret and GitHub App auth before rerunning evidence |
| Webhook runtime exists but is not hosted | GitHub App still cannot receive or answer deployment callbacks | Treat GPP-2q as deployability readiness only; configure the hosted endpoint and GitHub App webhook before rerunning evidence |
| Container package exists but is not hosted | Local image health does not prove GitHub can call the app | Treat GPP-2r as packaging readiness only; deploy to a public host and configure GitHub App webhook before rerunning evidence |
| Container image exists but service is not hosted | GHCR image publication does not prove GitHub can call the app | Treat GPP-2s as deploy artifact readiness only; deploy the image to a public host and configure GitHub App webhook before rerunning evidence |
| Deploy workflow exists but cloud bootstrap is missing | Automation path cannot produce hosted evidence | Treat GPP-2t as deploy automation readiness only; bootstrap OIDC/Secret Manager/Cloud Run and verify hosted health before rerunning protected workflow evidence |
| Human review requirement blocks autonomous program PRs | Green CI still cannot merge without manual approval | Implement `ao-release-gate` as a GitHub App required status check; reject admin bypass, PAT-backed bots, and Claude/Codex release authority |
| Dry-run release gate mistaken for merge authority | A scaffold could be overclaimed as production release control | GPP-2v sets `dry_run=true` and `merge_authority_enabled=false`; require GitHub App wiring and real PR evidence before branch-protection cutover |
| Check-run service mistaken for cutover evidence | A hosted-capable runtime could be overclaimed as active enforcement | GPP-2w still requires public hosting, real PR dry-run check-run evidence, and explicit branch-protection cutover before release authority is active |
| Release-gate container mistaken for hosted evidence | A local/CI image health pass could be overclaimed as active GitHub enforcement | GPP-2x treats the container as deploy artifact readiness only; require public hosting, webhook configuration, real PR dry-run evidence, and branch-protection cutover |
| Release-gate image publish mistaken for hosted evidence | A GHCR image tag could be overclaimed as an active GitHub App | GPP-2y treats GHCR publication as deploy artifact readiness only; require public hosting, webhook configuration, real PR dry-run evidence, and branch-protection cutover |
| Release-gate deploy health mistaken for release authority | A hosted `/healthz` response could be overclaimed as required-check enforcement | GPP-2aa records `check_run_post=false`, `real_pr_evidence=false`, `branch_protection_cutover=false`, and `merge_authority_enabled=false`; require real PR evidence and explicit cutover |
| Internal gate host health mistaken for webhook evidence | Public HTTPS health could be overclaimed as callback/check-run readiness | GPP-2af records `github_webhook_configured=false`, `github_callback_post=false`, `github_check_run_post=false`, and `branch_protection_cutover=false`; require webhook, real PR, and cutover evidence separately |
| Missing repository variables bypassed | Deploy workflow could be dispatched before non-secret handles exist | Run GPP-2ab attestation with `--fail-on-blocked` and provision missing GitHub repository variables before deploy dispatch |
| `metadata_ready` mistaken for cloud readiness | Deployment could be treated as unblocked without GCP trust or hosting proof | Treat GPP-2ab as repository-variable metadata only; separately prove OIDC, service account permissions, Secret Manager objects, Cloud Run health, webhook URL, and callback evidence |
| GPP-5 closeout mistaken for GPP-6 approval | Read-only repo-intelligence evidence could be overclaimed as protected E2E readiness | GPP-5d records `gpp6_readiness=blocked_by_upstream_gates`; require GPP-2 protected gate evidence and GPP-4 adapter decision before GPP-6 execution |
| GPP-6 preflight mistaken for E2E execution approval | A preparation report could be overclaimed as a protected adapter run | GPP-6a records `execution_status=blocked_by_upstream_gates`, `protected_workflow_dispatch_allowed=false`, and `live_adapter_execution_allowed=false`; require GPP-2/GPP-4 before any execution |

## 19. Tracking Log

| Date | Event | Notes |
|---|---|---|
| 2026-04-25 | GPP-0 issue opened | Issue [#470](https://github.com/Halildeu/ao-kernel/issues/470) created to track the written production-promotion program. |
| 2026-04-25 | GPP-0 branch opened | Branch `codex/gpp0-production-promotion-tracker` and dedicated worktree opened from `origin/main` at `1b8078f`. |
| 2026-04-25 | GPP-0 merged | PR [#471](https://github.com/Halildeu/ao-kernel/pull/471) merged at `f3823be`; tracker is live on `main`. |
| 2026-04-25 | GPP-1 issue opened | Issue [#472](https://github.com/Halildeu/ao-kernel/issues/472) created for protected live-adapter prerequisite attestation. |
| 2026-04-25 | GPP-1 attestation recorded | Live GitHub environment/secret evidence keeps GPP-1 at `blocked_attestation_missing`; GPP-2 remains blocked. |
| 2026-04-25 | GPP-1 merged | PR [#473](https://github.com/Halildeu/ao-kernel/pull/473) merged at `0ad7209`; protected live-adapter prerequisite remains blocked. |
| 2026-04-25 | GPP-1b issue opened | Issue [#474](https://github.com/Halildeu/ao-kernel/issues/474) created for agent operating program contract. |
| 2026-04-25 | GPP-1b contract added | `AGENTS.md`, `.claude/plans/gpp_status.v1.json`, and `scripts/gpp_next.py` make the current program state machine-readable for Codex/Claude operator sessions. |
| 2026-04-25 | GPP-1b merged | PR [#475](https://github.com/Halildeu/ao-kernel/pull/475) merged at `c579089`; status now holds at `GPP-2` blocked. |
| 2026-04-25 | GPP-1c issue opened | Issue [#476](https://github.com/Halildeu/ao-kernel/issues/476) tracks this status closeout so operator sessions do not see stale `GPP-1b active` state. |
| 2026-04-25 | GPP-1d issue opened | Issue [#478](https://github.com/Halildeu/ao-kernel/issues/478) tracks removal of moving authority SHAs from live status so merge commits do not create stale SSOT drift. |
| 2026-04-25 | GPP-1d merged | PR [#479](https://github.com/Halildeu/ao-kernel/pull/479) merged; live authority head is now read from git signals instead of static status text. |
| 2026-04-25 | GPP-2a issue opened | Issue [#480](https://github.com/Halildeu/ao-kernel/issues/480) created to re-attest protected live-adapter prerequisites before any GPP-2 runtime binding. |
| 2026-04-25 | GPP-2a re-attestation recorded | PR [#481](https://github.com/Halildeu/ao-kernel/pull/481) recorded then-current evidence: only `pypi` environment existed and `ao-kernel-live-adapter-gate` secret lookup returned `HTTP 404`; GPP-2 remained blocked. |
| 2026-04-25 | GPP-2b external/admin issue opened | Issue [#482](https://github.com/Halildeu/ao-kernel/issues/482) tracks protected environment, independent release gate, and credential provisioning required before `GPP-2` can start. |
| 2026-04-25 | GPP-2b partial provisioning recorded | `ao-kernel-live-adapter-gate` now exists, custom deployment branch policy includes `main`, and admin bypass is disabled. The selected deployment-protection app gate and `AO_CLAUDE_CODE_CLI_AUTH` remain missing, so #482 stays open and `GPP-2` stays blocked. |
| 2026-04-25 | GPP-2c issue opened | Issue [#485](https://github.com/Halildeu/ao-kernel/issues/485) tracks the remaining independent release gate and credential gate: configure the selected deployment-protection app gate and set `AO_CLAUDE_CODE_CLI_AUTH` without secret readback. |
| 2026-04-25 | GPP-2d issue opened | Issue [#487](https://github.com/Halildeu/ao-kernel/issues/487) tracks a metadata-only attestation tool for repeatable protected gate evidence. |
| 2026-04-25 | GPP-2d merged | PR [#488](https://github.com/Halildeu/ao-kernel/pull/488) added `scripts/live_adapter_gate_attest.py`; live attestation remains blocked by missing credential handle and, after GPP-2h/GPP-2i, the selected deployment-protection app gate. |
| 2026-04-25 | GPP-2e issue opened | Issue [#489](https://github.com/Halildeu/ao-kernel/issues/489) tracks the single-admin equivalent gate decision; current repo decision is `not_approved`, so the attestation override remains forbidden. |
| 2026-04-26 | GPP-2f issue opened | Issue [#491](https://github.com/Halildeu/ao-kernel/issues/491) tracks the independent release gate architecture decision; product end-user accounts are explicitly not release authority. |
| 2026-04-26 | GPP-2g issue opened | Issue [#493](https://github.com/Halildeu/ao-kernel/issues/493) tracks GitHub-native release authority selection and Claude/MCP advisory consultation protocol. |
| 2026-04-26 | GPP-2h issue opened | Issue [#495](https://github.com/Halildeu/ao-kernel/issues/495) tracks deployment protection bot gate selection; GitHub App deployment protection supersedes the required-reviewer provisioning path. |
| 2026-04-26 | GPP-2i issue opened | Issue [#497](https://github.com/Halildeu/ao-kernel/issues/497) tracks metadata-only attestation support for the selected deployment protection bot gate. |
| 2026-04-27 | GPP-2j issue opened | Issue [#515](https://github.com/Halildeu/ao-kernel/issues/515) tracks the post-RI-6 metadata refresh for the protected live gate. |
| 2026-04-27 | GPP-2j live metadata refreshed | `scripts/live_adapter_gate_attest.py` still reports `overall_status=blocked`; protected environment/admin bypass/branch policy pass, but `AO_CLAUDE_CODE_CLI_AUTH` and the selected deployment protection app gate remain missing. |
| 2026-04-27 | GPP-2k issue opened | Issue [#517](https://github.com/Halildeu/ao-kernel/issues/517) tracks the protected live gate provisioning runbook for #482/#485. |
| 2026-04-27 | GPP-2k provisioning runbook added | `docs/LIVE-ADAPTER-GATE-PROVISIONING-RUNBOOK.md` records the no-secret-readback checklist, metadata verification commands, and evidence template for the selected deployment protection app gate. |
| 2026-04-27 | GPP-2l issue opened | Issue [#519](https://github.com/Halildeu/ao-kernel/issues/519) tracks the post-provisioning prerequisites-ready attestation. |
| 2026-04-27 | GPP-2l prerequisites ready | `scripts/live_adapter_gate_attest.py` reports `overall_status=ready`; protected environment/admin bypass/branch policy, `AO_CLAUDE_CODE_CLI_AUTH`, and the selected deployment protection app gate pass. Runtime binding has not started and live execution/support widening remain false. |
| 2026-04-27 | GPP-2m issue opened | Issue [#521](https://github.com/Halildeu/ao-kernel/issues/521) tracks protected live gate workflow binding. |
| 2026-04-27 | GPP-2m workflow bound | `.github/workflows/live-adapter-gate.yml` is bound to `ao-kernel-live-adapter-gate`; triggers remain manual-only, no `secrets.` expression is present, and live execution/support widening remain false. |
| 2026-04-28 | GPP-2n issue opened | Issue [#523](https://github.com/Halildeu/ao-kernel/issues/523) tracks protected workflow evidence collection after the environment binding. |
| 2026-04-28 | GPP-2n evidence fail-closed | Workflow run `25020015357` reached `ao-kernel-live-adapter-gate` and stayed waiting for deployment protection app response; no steps or artifacts ran, `current_user_can_approve=false`, and the run was cancelled after bounded observation. |
| 2026-04-28 | GPP-2o issue opened | Issue [#525](https://github.com/Halildeu/ao-kernel/issues/525) tracks the repo-owned deployment protection policy decision core. |
| 2026-04-28 | GPP-2o decision core added | `ao_kernel/live_adapter_gate_policy.py` and `scripts/live_adapter_gate_policy_decision.py` add fail-closed policy evaluation; service deployment/configuration remains required before rerunning protected workflow evidence. |
| 2026-04-28 | GPP-2p issue opened | Issue [#527](https://github.com/Halildeu/ao-kernel/issues/527) tracks the repo-owned deployment protection policy webhook service scaffold. |
| 2026-04-28 | GPP-2p webhook scaffold added | `ao_kernel/live_adapter_gate_policy_service.py` and `scripts/live_adapter_gate_policy_service_smoke.py` add webhook signature/event checks and callback request artifact generation; hosted service deployment/configuration remains required before rerunning protected workflow evidence. |
| 2026-04-28 | GPP-2q issue opened | Issue [#529](https://github.com/Halildeu/ao-kernel/issues/529) tracks the deployable deployment protection policy webhook runtime. |
| 2026-04-28 | GPP-2q webhook runtime added | `ao_kernel/live_adapter_gate_policy_runtime.py` exposes a WSGI service entrypoint and GitHub App installation-token callback POST path; public hosting and GitHub App webhook configuration remain required before rerunning protected workflow evidence. |
| 2026-04-28 | GPP-2r issue opened | Issue [#531](https://github.com/Halildeu/ao-kernel/issues/531) tracks the deployment protection policy webhook container package. |
| 2026-04-28 | GPP-2r container package added | `deploy/live-adapter-gate-policy-service/Dockerfile`, `scripts/live_adapter_gate_policy_container_smoke.py`, and the `policy-container-smoke` CI job package the WSGI runtime as a no-secret health-checkable container; public hosting and GitHub App webhook configuration remain required before rerunning protected workflow evidence. |
| 2026-04-28 | GPP-2s issue opened | Issue [#533](https://github.com/Halildeu/ao-kernel/issues/533) tracks the deployment protection policy container image publication path. |
| 2026-04-28 | GPP-2s image publish path added | `.github/workflows/policy-container-publish.yml` builds, no-secret smokes, and publishes trusted non-PR images to `ghcr.io/halildeu/ao-kernel-live-adapter-gate-policy-service`; public hosting and GitHub App webhook configuration remain required before rerunning protected workflow evidence. |
| 2026-04-28 | GPP-2t issue opened | Issue [#535](https://github.com/Halildeu/ao-kernel/issues/535) tracks the autonomous policy service deployment path. |
| 2026-04-28 | GPP-2t deploy path added | `.github/workflows/policy-service-deploy-cloud-run.yml` can mirror trusted GHCR images to Artifact Registry, deploy Cloud Run with OIDC and Secret Manager references, health-check `/healthz`, and upload no-secret deployment evidence; cloud bootstrap, GitHub App webhook URL configuration, and callback evidence remain required before rerunning protected workflow evidence. |
| 2026-04-28 | GPP-2u issue opened | Issue [#537](https://github.com/Halildeu/ao-kernel/issues/537) tracks the autonomous GitHub App release-gate decision for no-human-approval program PR merges. |
| 2026-04-28 | GPP-2u release-gate model selected | `ao-release-gate` required status-check model is selected; GitHub App review counting remains a spike, and admin bypass/PAT-backed bot/Codex-Claude release authority remains rejected. |
| 2026-04-28 | GPP-2v issue opened | Issue [#539](https://github.com/Halildeu/ao-kernel/issues/539) tracks the `ao-release-gate` dry-run decision scaffold. |
| 2026-04-28 | GPP-2v dry-run scaffold added | `ao_kernel/ao_release_gate.py` and `scripts/ao_release_gate_decision.py` produce side-effect-free future check-run decisions; GitHub App wiring, dry-run evidence, and branch-protection cutover remain required. |
| 2026-04-28 | GPP-2w issue opened | Issue [#541](https://github.com/Halildeu/ao-kernel/issues/541) tracks the `ao-release-gate` webhook/check-run service wiring. |
| 2026-04-28 | GPP-2w check-run service added | `ao_kernel/ao_release_gate_service.py` and `ao_kernel/ao_release_gate_runtime.py` verify webhook input, evaluate the dry-run release gate, and can post the GitHub App check-run when hosted; public hosting, real PR dry-run evidence, branch-protection cutover, and deployment-protection hosting remain required. |
| 2026-04-28 | GPP-2x issue opened | Issue [#543](https://github.com/Halildeu/ao-kernel/issues/543) tracks the `ao-release-gate` container package and no-secret health smoke path. |
| 2026-04-28 | GPP-2x container package added | `deploy/ao-release-gate-service/Dockerfile`, `scripts/ao_release_gate_container_smoke.py`, and the `release-gate-container-smoke` CI job package the WSGI runtime as a no-secret health-checkable container; publish/hosting, real PR dry-run evidence, branch-protection cutover, and deployment-protection hosting remain required. |
| 2026-04-28 | GPP-2y issue opened | Issue [#545](https://github.com/Halildeu/ao-kernel/issues/545) tracks the `ao-release-gate` container image publication path. |
| 2026-04-28 | GPP-2y publish path added | `.github/workflows/ao-release-gate-container-publish.yml` builds, no-secret smokes, and publishes trusted `main` or manual images to `ghcr.io/halildeu/ao-kernel-ao-release-gate-service`; public hosting, real PR dry-run evidence, branch-protection cutover, and deployment-protection hosting remain required. |
| 2026-04-28 | GPP-2aa issue opened | Issue [#547](https://github.com/Halildeu/ao-kernel/issues/547) tracks the `ao-release-gate` autonomous Cloud Run deploy path. |
| 2026-04-28 | GPP-2aa deploy path added | `.github/workflows/ao-release-gate-deploy-cloud-run.yml` can mirror the trusted immutable release-gate image to Artifact Registry, deploy Cloud Run with Secret Manager references, health-check `/healthz`, and upload deploy evidence; webhook configuration, real PR check-run evidence, branch-protection cutover, and deployment-protection hosting remain required. |
| 2026-04-28 | GPP-2ab issue opened | Issue [#549](https://github.com/Halildeu/ao-kernel/issues/549) tracks metadata-only Cloud Run bootstrap attestation for the policy service deploy path. |
| 2026-04-28 | GPP-2ab bootstrap attestation added | `scripts/policy_service_cloud_run_bootstrap_attest.py` checks required GitHub repository variable handles with `gh variable list --json name,updatedAt`, ignores values, and records that current live metadata is `overall_status=blocked` because all required handles are missing; GCP trust, Secret Manager objects, Cloud Run hosting, webhook URL configuration, callback posting, live execution, support widening, and production-platform claims remain unproven. |
| 2026-04-28 | GPP-2ae issue opened | Issue [#565](https://github.com/Halildeu/ao-kernel/issues/565) tracks the internal operator host bundle for the vault-backed no-paid-cloud GPP-2 path. |
| 2026-04-28 | GPP-2ae host bundle added | `deploy/internal-gate-host` composes Caddy, the policy service container, and `ao-release-gate` with vault-backed secret ids; `scripts/internal_gate_host_bootstrap_attest.py` records metadata readiness only, with no Docker run, vault access, webhook configuration, callback/check-run posting, live adapter execution, support widening, or production claim. |
| 2026-04-28 | GPP-2af issue opened | Issue [#567](https://github.com/Halildeu/ao-kernel/issues/567) tracks the no-secret hosted health probe for the internal gate host path. |
| 2026-04-28 | GPP-2af health probe added | `scripts/internal_gate_host_health_probe.py` can collect public HTTPS health evidence for `/policy/healthz` and `/release-gate/healthz`; it does not configure webhooks, post callbacks/check-runs, change branch protection, dispatch protected workflows, execute live adapters, widen support, or claim production readiness. |
| 2026-04-28 | GPP-5d issue opened | Issue [#559](https://github.com/Halildeu/ao-kernel/issues/559) tracks repo-intelligence read-only workflow closeout before GPP-6 preparation. |
| 2026-04-28 | GPP-5d closeout preflight added | `scripts/gpp5_repo_intelligence_closeout.py` records GPP-5 as closed for read-only workflow-surface purposes while keeping GPP-6 execution blocked by GPP-2 and GPP-4. |
| 2026-04-28 | GPP-6a issue opened | Issue [#561](https://github.com/Halildeu/ao-kernel/issues/561) tracks the read-only E2E preflight contract for GPP-6 preparation. |
| 2026-04-28 | GPP-6a preflight added | `scripts/gpp6_read_only_e2e_preflight.py` records GPP-6 preparation as ready while keeping execution blocked by GPP-2 and GPP-4 with no live adapter, protected workflow dispatch, remote write, support widening, or production claim. |
