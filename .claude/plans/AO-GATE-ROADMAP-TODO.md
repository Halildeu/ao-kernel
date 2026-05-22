# AO Gate / Repo Intelligence Roadmap Todo

**Status:** draft / editable tracking plan  
**Date:** 2026-04-28  
**Owner model:** operator-owned gate infrastructure, product-facing repo-intelligence onboarding  
**Current program blocker:** `GPP-2 - Protected Live-Adapter Gate Runtime Binding` remains blocked / fail-closed  
**Decision baseline:** `testai.acik.com/ao-gate` path-based hosting is the preferred internal operator-host path

## How To Use This Todo

- Keep this file as the editable checklist for the AO gate unblock path.
- Mark only evidence-backed items as done.
- Keep every live change tied to target, reason, evidence, and rollback.
- Do not use this document to claim support widening, production platform readiness, live adapter execution, or branch-protection cutover by itself.
- Keep product end users out of Cloud Run, Vault, webhook hosting, GitHub App private-key handling, gate service hosting, and branch-protection setup.

## Guardrails

- [ ] GPP-2 remains fail-closed until public HTTPS health evidence, webhook evidence, dry-run check-run evidence, callback evidence, and branch protection/ruleset evidence exist.
- [ ] No GitHub App webhook URL is configured before public HTTPS health evidence passes.
- [ ] No branch protection/ruleset cutover happens before real PR `ao-release-gate` dry-run check-run evidence exists.
- [ ] No live adapter execution is started from this roadmap.
- [ ] No secret value, private key, webhook secret, or Vault token is committed, echoed, pasted into chat, or stored in evidence.
- [ ] Claude/Codex consultation remains advisory and is not release authority.
- [ ] Admin bypass is not used for GPP program PRs.

## Public URL Contract

```text
Policy health:
https://testai.acik.com/ao-gate/policy/healthz

Release-gate health:
https://testai.acik.com/ao-gate/release-gate/healthz

Deployment-protection webhook:
https://testai.acik.com/ao-gate/github/deployment-protection

ao-release-gate webhook:
https://testai.acik.com/ao-gate/github/ao-release-gate
```

## Host Port Contract

```text
live-adapter-gate-policy: 127.0.0.1:18081
ao-release-gate:         127.0.0.1:18082
```

## Nginx Route Contract

```nginx
location = /ao-gate/policy/healthz {
  proxy_pass http://127.0.0.1:18081/healthz;
}

location = /ao-gate/release-gate/healthz {
  proxy_pass http://127.0.0.1:18082/healthz;
}

location = /ao-gate/github/deployment-protection {
  proxy_pass http://127.0.0.1:18081/github/deployment-protection;
}

location = /ao-gate/github/ao-release-gate {
  proxy_pass http://127.0.0.1:18082/github/ao-release-gate;
}
```

## Roadmap Board

| ID | Work package | Repo / surface | Status | Blocking rule | Exit evidence |
|---|---|---|---|---|---|
| AO-GATE-1 | Path-based edge plan and runbook | `platform-k8s-gitops` | Not started | No live apply | PR with nginx route, host compose/env example, runbook, rollback |
| AO-GATE-2 | Operator host service rehearsal | `staging-sw` | Not started | AO-GATE-1 merged | Localhost health JSON for both services |
| AO-GATE-3 | Public `/ao-gate` nginx route apply | `staging-sw` | Not started | Localhost health passed | Public JSON health via `testai.acik.com/ao-gate/*` |
| AO-GATE-4 | Public HTTPS health evidence | `ao-kernel` | Not started | Public route returns JSON | `public_https_hosting_evidence=true` artifact |
| AO-GATE-5 | GitHub App webhook config evidence | GitHub App | Not started | AO-GATE-4 passed | Webhook URLs configured to `/ao-gate/github/*` |
| AO-GATE-6 | `ao-release-gate` dry-run PR evidence | GitHub PR | Not started | Webhook evidence present | Real PR dry-run check-run evidence |
| AO-GATE-7 | Deployment-protection callback evidence | GitHub deployment protection | Not started | Policy webhook configured | Callback review evidence or fail-closed evidence |
| AO-GATE-8 | Branch protection/ruleset cutover | GitHub repo settings | Not started | Dry-run check-run evidence present | Required `ao-release-gate` check blocks merge without pass |
| AO-GATE-9 | GPP-2 closeout update | `ao-kernel` | Not started | Evidence chain complete | GPP status updated without support widening |
| RI-NEXT | Repo Intelligence read-only E2E continuation | `ao-kernel` | Blocked | GPP-2 and GPP-4 blockers | GPP-6 execution path reopened |

## Evidence Artifact Paths

Use these paths as the default evidence targets unless a later work package
selects a more specific location.

| ID | Default evidence path |
|---|---|
| AO-GATE-1 | `platform-k8s-gitops` PR description plus reviewed files |
| AO-GATE-2 | `docs/evidence/ao-gate/ao-gate-localhost-health.v1.json` in the operator evidence surface, or an equivalent attached artifact |
| AO-GATE-3 | `docs/evidence/ao-gate/ao-gate-nginx-route-apply.v1.md` in the operator evidence surface, or an equivalent attached artifact |
| AO-GATE-4 | `internal-gate-host-health-evidence.json` from `scripts/internal_gate_host_health_probe.py` |
| AO-GATE-5 | `docs/evidence/ao-gate/github-app-webhook-config.v1.md`, with no secret material |
| AO-GATE-6 | `docs/evidence/ao-gate/ao-release-gate-dry-run-pr.v1.md`, with PR number and commit SHA |
| AO-GATE-7 | `docs/evidence/ao-gate/deployment-protection-callback.v1.md`, with no secret material |
| AO-GATE-8 | `docs/evidence/ao-gate/ao-release-gate-required-check-cutover.v1.md` |
| AO-GATE-9 | `.claude/plans/gpp_status.v1.json` and `GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md` update PR |

## AO-GATE-1: Path-Based Edge Plan And Runbook

**Goal:** Prepare the durable, reviewable infrastructure plan without changing live runtime.

**Branch:** `codex/ao-gate-path-edge-plan`  
**Repo:** `platform-k8s-gitops`  
**Live change:** no  
**Exit decision:** `ao_gate_path_edge_plan_ready_no_live_change`

### Todo

- [ ] Create a clean `platform-k8s-gitops` worktree from current `origin/main`.
- [ ] Read and apply `AGENTS.md` and `docs/context-priority-rules.md`.
- [ ] Add exact `/ao-gate` routes under the `testai.acik.com` HTTPS server block.
- [ ] Add operator-owned `host-compose/ao-gate/compose.yaml` or equivalent host manifest.
- [ ] Add `host-compose/ao-gate/.env.example` with secret ids only, no secret values.
- [ ] Define image tag strategy in the host manifest: prefer immutable `sha-*` or digest-pinned images; if `main` is used as a temporary default, mark it as deploy-artifact-only and not evidence.
- [ ] Add a runbook for preflight, apply, evidence, and rollback.
- [ ] State explicitly that this is not end-user setup.
- [ ] State explicitly that this PR does not configure GitHub webhooks.
- [ ] State explicitly that this PR does not claim public hosted health evidence.
- [ ] Verify no private key, token, webhook secret, or secret value is committed.
- [ ] Open PR as reviewable infrastructure plan.

### Acceptance Criteria

- [ ] `/ao-gate/policy/healthz` cannot fall through to SPA fallback.
- [ ] `/ao-gate/release-gate/healthz` cannot fall through to SPA fallback.
- [ ] Nginx upstream paths map to service-native paths exactly.
- [ ] Compose binds only localhost high ports.
- [ ] Runtime secret material is represented only by secret ids.
- [ ] Image tags cannot be mistaken for hosted evidence.
- [ ] Rollback is one of: route block revert, prior `default.conf` restore, `nginx -t`, `nginx -s reload`, compose down.

## AO-GATE-2: Operator Host Service Rehearsal

**Goal:** Run the two gate services on localhost high ports before public route exposure.

**Repo / surface:** `staging-sw` operator host  
**Live public change:** no  
**Exit decision:** `ao_gate_localhost_health_ready_no_public_route_claim`

### Todo

- [ ] Verify `platform-k8s-gitops` server checkout is clean.
- [ ] Fetch/sync the server checkout using non-destructive fast-forward only.
- [ ] Pull the two GHCR images or equivalent deploy artifacts.
- [ ] Configure runtime env with Vault secret ids, not secret values.
- [ ] Start the policy service on `127.0.0.1:18081`.
- [ ] Start the `ao-release-gate` service on `127.0.0.1:18082`.
- [ ] Confirm `docker ps` shows both services running.
- [ ] Confirm `curl http://127.0.0.1:18081/healthz` returns JSON with `program_id=GPP-2q`.
- [ ] Confirm `curl http://127.0.0.1:18082/healthz` returns JSON with `program_id=GPP-2w`.
- [ ] Confirm no GitHub callback or check-run post happened.
- [ ] Record local evidence as local only, not public hosted evidence.

### No-Go

- [ ] Port `18081` or `18082` is already occupied by another process.
- [ ] Either container enters crash-loop or fails its healthcheck.
- [ ] `http://127.0.0.1:18081/healthz` does not return HTTP 200 JSON.
- [ ] `http://127.0.0.1:18082/healthz` does not return HTTP 200 JSON.
- [ ] Policy health payload does not report `program_id=GPP-2q`.
- [ ] Release-gate health payload does not report `program_id=GPP-2w`.
- [ ] Runtime logs print secret values, private-key material, webhook secrets, or Vault tokens.

### Rollback

- [ ] `docker compose -f host-compose/ao-gate/compose.yaml down`
- [ ] Verify ports `18081` and `18082` are no longer listening.

## AO-GATE-3: Public `/ao-gate` Nginx Route Apply

**Goal:** Expose only the planned `/ao-gate` paths through existing `platform-web-nginx`.

**Repo / surface:** `staging-sw` operator host  
**Live public change:** yes  
**Exit decision:** `ao_gate_public_path_routes_ready_health_probe_pending`

### Pre-Apply Record

- [ ] Target change written: add exact `/ao-gate` routes under `testai.acik.com`.
- [ ] Reason written: required for GPP-2 no-secret public HTTPS health evidence.
- [ ] Evidence plan written: `nginx -t`, public `curl`, internal gate health probe.
- [ ] Rollback written: restore previous nginx config or revert route block, `nginx -t`, reload.
- [ ] Rollback TTL written: if public health does not return expected JSON within 5 minutes after reload, revert the nginx change and reload the previous config.

### Todo

- [ ] Back up the live nginx config.
- [ ] Apply route block from reviewed repo content.
- [ ] Run `docker exec platform-web-nginx nginx -t`.
- [ ] Reload only if `nginx -t` passes.
- [ ] Verify `https://testai.acik.com/ao-gate/policy/healthz` returns JSON, not HTML.
- [ ] Verify `https://testai.acik.com/ao-gate/release-gate/healthz` returns JSON, not HTML.
- [ ] Verify `program_id` values match `GPP-2q` and `GPP-2w`.
- [ ] Verify existing `testai.acik.com` root/API/realm routes are not regressed:
  - [ ] `https://testai.acik.com/`
  - [ ] `https://testai.acik.com/testai-healthz`
  - [ ] `https://testai.acik.com/api/v1/theme-registry`
  - [ ] `https://testai.acik.com/realms/platform-test/.well-known/openid-configuration`
  - [ ] `https://testai.acik.com/resources/`

### No-Go

- [ ] `nginx -t` fails.
- [ ] Health URL returns `text/html`.
- [ ] Health URL returns HTTP 200 with SPA body.
- [ ] `program_id` mismatch.
- [ ] Existing root/API/realm route smoke regresses.
- [ ] Public health JSON does not pass within the rollback TTL.

## AO-GATE-4: Public HTTPS Health Evidence

**Goal:** Produce no-secret hosted health evidence for GPP-2.

**Repo:** `ao-kernel`  
**Exit decision:** `internal_gate_host_public_https_health_evidence_collected_no_support_widening`

### Todo

- [ ] Run the health probe with the explicit path-based URLs.
- [ ] Use `/usr/bin/python3` or set a valid `SSL_CERT_FILE` if local Framework Python lacks CA roots.
- [ ] Store the JSON artifact in the agreed evidence location.
- [ ] Confirm `policy_health_evidence=true`.
- [ ] Confirm `release_gate_health_evidence=true`.
- [ ] Confirm `public_https_hosting_evidence=true`.
- [ ] Confirm `secret_value_readback=false`.
- [ ] Confirm `github_webhook_configured=false`.
- [ ] Confirm `github_callback_post=false`.
- [ ] Confirm `github_check_run_post=false`.
- [ ] Confirm `branch_protection_cutover=false`.
- [ ] Confirm `live_adapter_execution=false`.
- [ ] Confirm `support_widening=false`.
- [ ] Confirm `production_platform_claim=false`.

### Command

```bash
/usr/bin/python3 scripts/internal_gate_host_health_probe.py \
  --policy-url https://testai.acik.com/ao-gate/policy/healthz \
  --release-gate-url https://testai.acik.com/ao-gate/release-gate/healthz \
  --artifact-path internal-gate-host-health-evidence.json \
  --output text \
  --fail-on-blocked
```

## AO-GATE-5: GitHub App Webhook Config Evidence

**Goal:** Point GitHub App webhook delivery at the hosted gate endpoints after health evidence passes.

**Surface:** GitHub App settings  
**Exit decision:** `github_app_webhook_configured_after_health_evidence_no_support_widening`

### Todo

- [ ] Verify AO-GATE-4 artifact passed.
- [ ] Configure deployment-protection webhook URL to `/ao-gate/github/deployment-protection`.
- [ ] Configure `ao-release-gate` webhook URL to `/ao-gate/github/ao-release-gate`.
- [ ] Verify webhook secret is resolved by runtime through Vault secret id.
- [ ] Trigger or observe only a safe GitHub App `ping` delivery in this work package.
- [ ] Defer real PR and deployment-protection events to AO-GATE-6 and AO-GATE-7.
- [ ] Record delivery status without secret material.
- [ ] Keep branch protection unchanged.

### No-Go

- [ ] Public health evidence missing.
- [ ] A real PR, check-run, or deployment-protection event is required to verify this package.
- [ ] Secret value needed in chat or repo.
- [ ] Private key value needed in chat or repo.

## AO-GATE-6: `ao-release-gate` Dry-Run PR Evidence

**Goal:** Prove the check-run service can post a dry-run release gate result on a real PR.

**Surface:** GitHub PR  
**Exit decision:** `ao_release_gate_real_pr_dry_run_check_run_evidence_ready`

### Todo

- [ ] Select a low-risk real PR for dry-run evidence.
- [ ] Confirm webhook delivery reaches the hosted release-gate service.
- [ ] Confirm check-run name is stable: `ao-release-gate`.
- [ ] Confirm the check-run is dry-run evidence, not branch-protection enforcement yet.
- [ ] Confirm result is attached to the expected commit SHA.
- [ ] Record status, conclusion, URL, PR number, and commit SHA.
- [ ] Keep branch protection/ruleset unchanged.

## AO-GATE-7: Deployment-Protection Callback Evidence

**Goal:** Prove the policy service handles deployment-protection callback review behavior.

**Surface:** GitHub deployment protection  
**Exit decision:** `deployment_protection_callback_evidence_ready_fail_closed_preserved`

### Todo

- [ ] Confirm policy webhook config is active.
- [ ] Trigger a controlled deployment-protection event only when `python3 scripts/gpp_next.py` and `.claude/plans/gpp_status.v1.json` both allow the evidence slice.
- [ ] Confirm service validates payload and signature.
- [ ] Confirm callback request is produced only for allowed policy decisions.
- [ ] Record callback review evidence or fail-closed evidence.
- [ ] Treat inactive, denied, timed out, cancelled, or failing deployment protection as fail-closed evidence, not approval.
- [ ] Do not run live adapter execution from this step.

## AO-GATE-8: Branch Protection / Ruleset Cutover

**Goal:** Make `ao-release-gate` the durable autonomous merge/release enforcement path after dry-run evidence.

**Surface:** GitHub repository rules  
**Exit decision:** `ao_release_gate_required_status_check_cutover_ready_no_admin_bypass`

### Todo

- [ ] Confirm AO-GATE-6 dry-run evidence exists.
- [ ] Confirm selected required status check name is stable.
- [ ] Confirm admin bypass policy for GPP program PRs remains disallowed.
- [ ] Configure branch protection/ruleset to require `ao-release-gate`.
- [ ] Open or use a real PR to prove merge is blocked without passing check.
- [ ] Prove passing check allows the intended path.
- [ ] Record ruleset/protection evidence.

## AO-GATE-9: GPP-2 Closeout Update

**Goal:** Update program state only after the evidence chain exists.

**Repo:** `ao-kernel`  
**Exit decision:** `gpp2_protected_gate_runtime_binding_evidence_ready_no_support_widening`

### Required Evidence Checklist

- [ ] Public HTTPS policy health evidence.
- [ ] Public HTTPS release-gate health evidence.
- [ ] GitHub App webhook configuration evidence.
- [ ] Deployment-protection callback review or fail-closed evidence.
- [ ] Real PR dry-run `ao-release-gate` check-run evidence.
- [ ] Branch protection/ruleset required status check evidence.
- [ ] Protected workflow evidence confirming live execution remains governed.

### Program Flags

- [ ] `support_widening=false`
- [ ] `production_platform_claim=false`
- [ ] `live_adapter_execution=false` until a later explicit evidence slice permits it.

### Guardrail To Evidence Cross-Reference

| Guardrail | Required evidence before marking done |
|---|---|
| No webhook before health | AO-GATE-4 `public_https_hosting_evidence=true` artifact precedes AO-GATE-5 evidence |
| No branch protection before dry-run | AO-GATE-6 real PR dry-run check-run evidence precedes AO-GATE-8 evidence |
| No live adapter execution | AO-GATE-7 and AO-GATE-9 evidence keep `live_adapter_execution=false` unless a later explicit slice permits it |
| No secret value exposure | Every evidence artifact states secret values, private keys, webhook secrets, and Vault tokens were not recorded |
| No support widening | GPP status closeout keeps `support_widening=false` |
| No production claim | GPP status closeout keeps `production_platform_claim=false` |
| Advisory consultation only | Claude/Codex review is recorded as advisory, not release authority |
| No admin bypass | Branch protection/ruleset evidence states admin bypass was not used for GPP program PRs |

## RI-NEXT: Repo Intelligence Product Flow Continuation

**Goal:** Continue the general product path once upstream gates are ready.

**Current status:** blocked by GPP-2 and GPP-4  
**GPP-4 dependency:** production-certified read-only adapter decision for the real adapter path.

### Product User Surface

The product user sees only:

```text
GitHub App install -> repository selection -> optional .ao/repo-intelligence.yml -> read-only repo-intelligence workflow status
```

The product user does not see or operate the AO gate host, Vault, webhook
runtime, GitHub App private key, deployment-protection service, release-gate
service, or branch-protection cutover.

### Todo

- [ ] Use GPP-5 as read-only product workflow building block.
- [ ] Keep end-user onboarding limited to GitHub App install, selected repositories, and optional `.ao/repo-intelligence.yml`.
- [ ] Complete GPP-4 production-certified read-only adapter decision.
- [ ] Re-run GPP-6 read-only E2E preflight after GPP-2 and GPP-4 blockers clear.
- [ ] Do not add hidden prompt feed, MCP repo-intelligence exposure, root export, vector/artifact writes, or live adapter execution without explicit later gates.

## Current Known Findings

- [ ] `ao-kernel` `main` is clean and up to date with `origin/main` at the time this todo was created.
- [ ] `platform-k8s-gitops` local checkout was observed dirty on `codex/current-state-live-truth-20260423`; use a separate clean worktree for AO-GATE-1.
- [ ] `platform-backend` is not the right repo for gate hosting; it is backend source code, not runtime/edge authority.
- [ ] `staging-sw` has Docker, Docker Compose, sudo, and Docker group access available.
- [ ] `platform-web-nginx` currently owns public `80/443`.
- [ ] `https://testai.acik.com/ao-gate/policy/healthz` currently falls through to SPA HTML and is not evidence.
- [ ] `127.0.0.1:18081` and `127.0.0.1:18082` were observed free during discovery.
- [ ] `platform-vault-prod` was observed healthy, initialized, and unsealed; secret values were not read.

## Change Log

| Date | Change | Author |
|---|---|---|
| 2026-04-28 | Initial editable roadmap todo created from Codex + Claude advisory review | Codex |
| 2026-05-21 | AO-GATE-1..4 + AO-GATE-9 completed; AO-GATE-5..8 remain operator-bound. Codex thread 019e4a10 plan+post-impl AGREE v2.1 + Decision 1 Alt-B + Decision 2 AGREE_A. | Claude |

## Post-Merge Status (2026-05-21)

Public HTTPS health hosting evidence collected; GPP-2 SSOT updated. GPP-2 overall remains `blocked` until AO-GATE-5..8.

### Completed work packages

| ID | Status | Evidence |
|---|---|---|
| AO-GATE-1 | ✅ DONE | platform-k8s-gitops#938 merged (nginx routes); cross-AI Codex thread 019e4a10 plan AGREE v2.1 |
| AO-GATE-2 | ✅ DONE | Operator host rehearsal: `ao-gate-policy` + `ao-gate-release` Healthy on staging-sw; ports 127.0.0.1:18081/18082 |
| AO-GATE-3 | ✅ DONE | Public route apply: nginx live patch + nginx -t + reload + non-disruption regression smoke (testai-healthz, SPA root, hr-compensation, OIDC platform-test, ai.acik.com untouched) |
| AO-GATE-4 | ✅ DONE | `internal_gate_host_health_probe.py` artifact `hosted_health_ready` + `public_https_hosting_evidence=true` + `live_adapter_execution=false`; artifact sha256 `96e805d667b4a1a25b95dcf89dffeaa59a6ac5c8f36e23eea6c05b3a673d7acc` |
| AO-GATE-9 | ✅ DONE | ao-kernel#569 merged (4c51eee1): `current_wp.evidence_collected[]` audit row + `exit_decision` narrowed to `internal_gate_host_health_probe_collected_webhook_config_not_collected_no_support_widening` + `pending_external_actions[0..1]` removed + `blocked_wps[GPP-2].reason` updated |

### Decision 2 absorb (additional from Codex 019e4a10 PARTIAL → AGREE_A)

ao-kernel#570 (config contract per-service split) + platform-k8s-gitops#942 (gitops paralel) merged. Two GitHub Apps routing model: per-service `AO_POLICY_GITHUB_APP_ID` + `AO_RELEASE_GATE_GITHUB_APP_ID` (+ corresponding per-service `*_PRIVATE_KEY_PEM_ID`). Backward-compat fallback to legacy single `AO_GITHUB_APP_ID` preserved so existing operator deploys are not disturbed.

### Remaining work packages (operator-bound + sequencing locked)

| ID | Status | Operator action gerek |
|---|---|---|
| AO-GATE-5 | ✅ DONE (2026-05-22) | Two GitHub Apps created (`ao-kernel-live-adapter-gate-policy` id=3800120 + `ao-release-gate` id=3800233); Vault PEM + webhook-secret seeded (`/pem` and `/value` field-name suffix per ao-kernel `hashicorp_vault_provider.py` contract); `.env` updated per-service; containers Healthy + HMAC verification confirmed (origin returns sig-verified 4xx for ping = `wrong_event` not `signature_invalid`) |
| AO-GATE-6 | ✅ Evidence captured (2026-05-22) | Webhook delivery chain GREEN via smee.io non-production dry-run proxy (TCP/443 outbound; office firewall blocks TCP+UDP/7844, cloudflared infeasible). PR #572 opened → release-gate App posted check-run `ao-release-gate` conclusion=`failure` output_title=`deny_missing_evidence` (correct fail-closed posture, advisory only — no branch protection cutover) |
| AO-GATE-7 | ⏳ Blocked on App slug reconciliation + production topology | (a) Policy App slug drift: new App is `ao-kernel-live-adapter-gate-policy` but repo constant `REQUIRED_DEPLOYMENT_PROTECTION_APP_SLUG = "ao-kernel-live-adapter-gate"` and protected environment name expect old slug (`ao_kernel/live_adapter_gate.py:34,46`; `ao_kernel/defaults/schemas/live-adapter-gate-environment.schema.v1.json:107,119`); decision needed: rename new App OR update constant/schema/tests/attestation to new slug. (b) Production topology: smee.io is dry-run only; deployment-protection callback path needs publicly-reachable HTTPS endpoint with verified-context. (c) After (a)+(b): `workflow_dispatch` on `live-adapter-gate.yml` with `target_ref=main`, capture deployment_protection_rule webhook id + policy origin signature_verified + callback POST result + workflow run id |
| AO-GATE-8 | ⏳ Blocked on AO-GATE-6 + AO-GATE-7 | Branch protection cutover: required ao-release-gate check; admin bypass YASAK. Additional gate: at least one **positive `success` conclusion path** demonstrated (not only fail-closed `failure / deny_missing_evidence`) OR explicit documented decision that required check stays advisory until enrichment model produces verified-context |

### Constraints carried (unchanged from initial draft)

- `live_adapter_execution_allowed=false` (still)
- `support_widening_allowed=false` (still)
- `production_platform_claim_allowed=false` (still)
- Admin bypass on GPP-program PRs YASAK
- No secret value in chat/log/repo/issue/PR

### Cross-AI peer review chain (this closure)

- Codex thread `019e4a10-0fd5-7ff3-9601-80f56a9c8e81`
- Plan-time: REVISE → PARTIAL → AGREE v2.1
- Decision 1 (SSOT update): AGREE Alt-B
- Decision 2 (webhook routing): PARTIAL → AGREE_A (two Apps + config contract PRs first)
- Post-impl: Codex live verification confirmed evidence chain + corrected wording ("GPP-2 unblocked" → "public HTTPS health hosting evidence resolved, overall still blocked")
- Implementer Claude (Anthropic) / Reviewer Codex (OpenAI) — HARD RULE provider-level cross-AI uyumlu
