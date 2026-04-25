# GPP-1b - Agent Operating Program Contract

**Status:** active
**Date:** 2026-04-25
**Parent tracker:** [#470](https://github.com/Halildeu/ao-kernel/issues/470)
**Slice issue:** [#474](https://github.com/Halildeu/ao-kernel/issues/474)
**Branch:** `codex/gpp1b-agent-operating-program-contract`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gpp1b-agent-operating-program-contract`
**Base authority:** `origin/main` at `0ad7209`
**Target exit decision:** `agent_operating_contract_ready_no_support_widening`
**Support impact:** none
**Release impact:** none

## 1. Purpose

Make Codex and Claude Code follow the same repo-owned program state when they
operate on `ao-kernel`.

This slice is about operator discipline, not product live-adapter promotion.
It does not run `claude`, does not bind protected GitHub environments, and does
not widen support.

## 2. Problem

The GPP program now has a written tracker, but agents can still drift if they
infer the next action from chat history instead of repo state.

The required behavior is:

1. Read `origin/main` as authority.
2. Read the GPP status file.
3. Identify the single active work package.
4. Respect blocked runtime/support-widening gates.
5. Use one issue, one worktree, one branch, one PR, one exit decision.

## 3. Implemented Surface

1. `AGENTS.md` records the startup and execution contract for Codex and Claude
   Code.
2. `.claude/plans/gpp_status.v1.json` exposes the current GPP state in a
   machine-readable form.
3. `scripts/gpp_next.py` prints the active work package, blocked work packages,
   required startup checks, forbidden actions, and next allowed actions.
4. `tests/test_gpp_next.py` pins the status contract and helper behavior.
5. The human-readable GPP and post-beta status files point to this contract.

## 4. Current Program Decision

`GPP-1` remains closed as `blocked_attestation_missing`.

`GPP-2` remains blocked because the required protected live-adapter environment
and credential handle are not attested.

`GPP-1b` does not solve that runtime prerequisite. It prevents Codex/Claude
operator sessions from accidentally skipping it.

## 5. Acceptance Criteria

1. Agents have a short startup contract in `AGENTS.md`.
2. `python3 scripts/gpp_next.py` reports `GPP-1b` as the active work package.
3. `python3 scripts/gpp_next.py --output json` returns valid JSON.
4. `.claude/plans/gpp_status.v1.json` keeps:
   - `support_widening_allowed=false`
   - `production_platform_claim_allowed=false`
   - `live_adapter_execution_allowed=false`
5. `GPP-2` is explicitly listed as blocked.
6. Tests fail if the active WP, blocked WP, or support-widening guard drifts.
7. No runtime adapter code changes are made.

## 6. Non-Goals

1. No live adapter execution.
2. No GitHub environment creation.
3. No secret or credential handling.
4. No workflow `environment:` binding.
5. No support-tier promotion.
6. No release, tag, or publish.

## 7. Validation

Required local validation:

1. `git diff --check`
2. `python3 scripts/gpp_next.py`
3. `python3 scripts/gpp_next.py --output json`
4. `pytest -q tests/test_gpp_next.py`
5. `python3 -m ao_kernel doctor`

