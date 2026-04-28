# GPP-2w - AO Release Gate Check-Run Service

**Issue:** [#541](https://github.com/Halildeu/ao-kernel/issues/541)
**Decision:** `ao_release_gate_check_run_service_ready_no_support_widening`
**Date:** 2026-04-28
**Support widening:** false
**Production platform claim:** false
**Live adapter execution:** false

## Decision

GPP-2w wires the dry-run `ao-release-gate` evaluator into a GitHub App webhook
and check-run posting surface without granting merge authority. The service can
verify a GitHub webhook delivery, evaluate the repo-owned release-gate policy,
build an `ao-release-gate` check-run request, and the runtime can post that
check-run using GitHub App installation authentication when hosted with runtime
secrets.

This is still a dry-run release gate. It does not merge PRs, does not change
branch protection or rulesets, does not approve deployment protection reviews,
does not run a live adapter, and does not widen support.
It does not unblock GPP-2 and does not authorize human-free merges yet.

## Added Surface

1. `ao_kernel/ao_release_gate_service.py`
   - verifies webhook signature when required;
   - restricts supported events to PR/check/workflow delivery contexts;
   - decodes a JSON object payload fail-closed;
   - calls `ao_kernel.ao_release_gate.build_ao_release_gate_decision`;
   - builds a GitHub check-run POST request for `ao-release-gate`;
   - returns a machine-readable artifact without performing network I/O.

2. `ao_kernel/ao_release_gate_runtime.py`
   - exposes WSGI paths `/healthz` and `/github/ao-release-gate`;
   - loads webhook secret, GitHub App id/private key, API URL, and GPP status
     from runtime configuration;
   - mints a GitHub App JWT and installation token;
   - posts the check-run returned by the service boundary;
   - redacts runtime responses so token, private key, and webhook secret
     material are not echoed.

3. Tests cover:
   - missing or invalid signatures blocking before policy evaluation;
   - unsupported events and malformed JSON blocking before policy evaluation;
   - successful dry-run check-run request generation;
   - denied-policy check-run generation with `failure` conclusion;
   - runtime check-run POST path using a fake GitHub client;
   - missing installation id blocking before POST;
   - GitHub App client token/check-run POST behavior without returning secret
     material;
   - WSGI health and bad-signature responses.

## Guardrails

- `dry_run=true` remains true in the release-gate decision.
- `merge_authority_enabled=false` remains false.
- No branch protection/ruleset change.
- No admin bypass.
- No PAT-backed bot user.
- No product end-user release authority.
- No Claude/Codex release authority.
- No `AO_CLAUDE_CODE_CLI_AUTH` reference.
- No live adapter execution.
- No support widening and no production platform claim.

## Runtime Configuration Required Outside The Repo

A hosted service must provide these values through a runtime secret manager or
equivalent secret store:

- `AO_RELEASE_GATE_WEBHOOK_SECRET`
- `AO_GITHUB_APP_ID`
- `AO_GITHUB_APP_PRIVATE_KEY_PEM` or `AO_GITHUB_APP_PRIVATE_KEY_PATH`

Optional runtime values:

- `AO_GITHUB_API_URL`
- `AO_RELEASE_GATE_GPP_STATUS_PATH`
- `AO_RELEASE_GATE_MAX_BODY_BYTES`

Secret values must not be committed, echoed in logs, or sent to Claude MCP or
other advisory systems.

## Remaining Blockers

GPP-2 remains blocked after this work because:

1. The `ao-release-gate` service is not yet publicly hosted.
2. The GitHub App webhook URL/runtime secret configuration is not yet proven on
   a real delivery.
3. No real PR dry-run check-run evidence has been collected.
4. Branch protection/rulesets do not yet require `ao-release-gate`.
5. The deployment-protection policy service for
   `ao-kernel-live-adapter-gate` is still not publicly hosted/configured and
   still has no protected workflow callback evidence.

## Next Allowed Action

Deploy or host the `ao-release-gate` check-run service in dry-run mode, collect
real PR evidence that it posts the expected required check-run, and only then
consider a branch-protection/ruleset cutover to require `ao-release-gate`.
The deployment-protection policy service must also still be hosted/configured
before protected live-adapter workflow evidence is rerun.
