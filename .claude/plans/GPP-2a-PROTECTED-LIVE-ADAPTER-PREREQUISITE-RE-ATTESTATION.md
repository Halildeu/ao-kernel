# GPP-2a - Protected Live-Adapter Prerequisite Re-Attestation

**Status:** completed by PR [#481](https://github.com/Halildeu/ao-kernel/pull/481)
**Date:** 2026-04-25
**Parent tracker:** [#470](https://github.com/Halildeu/ao-kernel/issues/470)
**Slice issue:** [#480](https://github.com/Halildeu/ao-kernel/issues/480)
**Slice PR:** [#481](https://github.com/Halildeu/ao-kernel/pull/481)
**Branch:** `codex/gpp2a-prereq-reattest`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gpp2a-prereq-reattest`
**Target decision:** `still_blocked_protected_prerequisites_missing`
**Support impact:** none
**Release impact:** none

## 1. Purpose

Re-attest the protected live-adapter prerequisites before any `GPP-2` runtime
binding work starts.

This slice is not runtime work. It records whether the project-owned protected
GitHub environment and credential handle exist. If they do not exist, `GPP-2`
must remain blocked.

## 2. Live Evidence

Commands run from clean `main` on 2026-04-25:

```bash
git status --short --branch
git rev-list --left-right --count HEAD...origin/main
bash .claude/scripts/ops.sh preflight
python3 scripts/gpp_next.py
gh api repos/Halildeu/ao-kernel/environments --jq '.environments[].name'
gh secret list --repo Halildeu/ao-kernel
gh secret list --env ao-kernel-live-adapter-gate --repo Halildeu/ao-kernel
```

Observed results:

1. `main` was synchronized with `origin/main`; divergence was `0 0`.
2. `scripts/gpp_next.py` reported `GPP-2` as blocked.
3. GitHub environment inventory returned only `pypi`.
4. Repository secret listing returned no visible secret handles.
5. Environment secret listing for `ao-kernel-live-adapter-gate` returned
   `HTTP 404` because the environment is absent.

## 3. Decision

`GPP-2a` exits with:

```text
still_blocked_protected_prerequisites_missing
```

`GPP-2` remains blocked because:

1. Protected environment `ao-kernel-live-adapter-gate` is absent.
2. Credential handle `AO_CLAUDE_CODE_CLI_AUTH` is not attested under that
   environment.
3. Project-owned live adapter execution evidence is still unavailable.

## 4. What Unblocks GPP-2

A future admin/provisioning step must provide fresh evidence that:

1. GitHub environment `ao-kernel-live-adapter-gate` exists.
2. The environment has the required protection policy.
3. Secret handle `AO_CLAUDE_CODE_CLI_AUTH` exists under that environment.
4. Fork-triggered workflows cannot access the credential.

Only after that evidence exists may a new attestation slice change the
precondition decision to `prerequisites_ready`.

## 5. Non-Goals

1. No runtime adapter code changes.
2. No workflow `environment:` binding.
3. No GitHub environment creation.
4. No secret creation or secret value handling.
5. No live adapter execution.
6. No support-tier widening.
7. No release, tag, or publish.

## 6. Validation

Required validation for this slice:

1. `git diff --check`
2. `python3 scripts/gpp_next.py`
3. `python3 scripts/gpp_next.py --output json`
4. `pytest -q tests/test_gpp_next.py tests/test_gp5_platform_claim_decision.py`
5. `python3 -m ao_kernel doctor`
