# Runbook 05 - MiniMax/Mavis Runtime Workaround for High-Risk Review Evidence

> **Agent-prepared only.** This runbook records the local runtime workaround
> discovered while diagnosing the MiniMax/Mavis reviewer lane for PR #997.
> It does not provide credentials, does not fabricate review evidence, does
> not close PR #997, does not widen support, does not authorize live adapter
> execution, and does not make a production platform claim.

## Purpose

PR #997 is intentionally fail-closed until MiniMax/Mavis produces real
high-risk review evidence with an `AGREE` verdict. The required artifact is:

```text
ao-ma-10-high-risk-reviews/minimax.local-ai-review-evidence.v1.json
```

The repository-owned `ao-release-gate` required check remains release
authority. AI reviewer output is evidence only. A MiniMax `REVISE` or `BLOCK`
verdict must keep the PR blocked.

## Observed Failure Modes

The default MiniMax/Mavis CLI path was not enough in the local Codex sandbox:

- Default daemon startup attempted to write under the user Mavis home and
  failed with filesystem permission errors.
- Running the daemon with system Node found incompatible native modules.
- A long local data directory caused the broker socket path to exceed the
  Unix socket length limit.
- The workaround was observed with the MiniMax Code app bundled Electron
  runtime reporting Node `v22.20.0` and module ABI `139`. If the app runtime
  changes, re-check the config response shape before relying on this runbook.
- CLI `status` style commands were not reliable against the manually started
  daemon, while the `/mavis/api/config` endpoint was reliable.
- Runtime startup is separate from credential readiness. The latest observed
  configuration reported an invalid API-key status, so provider review could
  not run.

## Prerequisites

1. Work from a clean feature worktree, not the primary checkout.
2. Never commit `.m/`, `.mavis/`, config files, logs, tokens, or provider
   credential material.
3. Do not paste credential material into prompts, PR comments, logs, shell
   history, or repository files.
4. Do not proceed to evidence generation unless the config endpoint reports
   credential readiness.

## Start the Local Daemon

Use the Electron runtime bundled with the MiniMax Code app. The short `.m`
data directory avoids the socket path limit, and the local npm cache avoids
writing to the user npm cache.

```bash
export WORKTREE_ROOT="/path/to/your/feature-worktree"
export MINIMAX_MAVIS_PORT="${MINIMAX_MAVIS_PORT:-55321}"

cd "$WORKTREE_ROOT"

mkdir -p .m/npm-cache
: > .m/.runbook-05-minimax-mavis-runtime

PATH='/Applications/MiniMax Code.app/Contents/Resources/resources/opencode:'"$PATH" \
ELECTRON_RUN_AS_NODE=1 \
NODE_PATH='/Applications/MiniMax Code.app/Contents/Resources/app.asar.unpacked/node_modules:/Applications/MiniMax Code.app/Contents/Resources/resources/daemon/node_modules' \
npm_config_cache="$PWD/.m/npm-cache" \
NPM_CONFIG_CACHE="$PWD/.m/npm-cache" \
'/Applications/MiniMax Code.app/Contents/MacOS/MiniMax Code' \
'/Applications/MiniMax Code.app/Contents/Resources/resources/daemon/daemon.js' \
  --port "$MINIMAX_MAVIS_PORT" \
  --data-dir "$PWD/.m"
```

Run this in a foreground terminal while producing evidence. Stop it with
`Ctrl-C` after the evidence attempt. If the selected port is already in use,
choose another local port and use the same `MINIMAX_MAVIS_PORT` value in the
verification command below.

## Verify Runtime and Credential Readiness

Use the local config endpoint, not the CLI `status` command:

```bash
/usr/bin/curl -sS --max-time 2 "http://127.0.0.1:${MINIMAX_MAVIS_PORT:-55321}/mavis/api/config" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("apiKeyStatus",{}).get("valid"))'
```

Expected value before any provider review attempt:

```text
true
```

If the value is anything else, stop. The runtime may be up, but the provider
credential gate is not satisfied.

## Credential Gate

Credential setup is operator-owned. The agent must not produce or guess a
provider key.

- Prefer MiniMax/Mavis UI or the operator-approved local secret mechanism for
  key configuration.
- Do not pass provider keys as shell arguments.
- Do not echo provider keys.
- Do not print the config file.
- Do not commit generated runtime state.
- Do not claim MiniMax review success unless the provider actually returns
  valid review JSON and the repository tests accept it.

## Evidence Production Boundary

The high-risk evidence producer expects a command in
`AO_MA10_MINIMAX_REVIEW_CMD`. The source of truth is
`scripts/ao_ma10_high_risk_raw_review_producer.py`, where the MiniMax provider
maps to that environment variable. Tests for this producer live in
`tests/test_ao_ma10_high_risk_raw_review_producer.py`.

The command must:

1. Read review input JSON from stdin.
2. Return JSON on stdout.
3. Include the required reviewer fields: `agent`, `verdict`,
   `checks_considered`, and `findings`.
4. Return a real MiniMax/Mavis verdict.

The repository checks must accept the generated artifact, including provider
separation, context binding, secret scan, and schema validation. Manual edits
that convert a non-AGREE result into `AGREE` are forbidden.

Example invocation shape, with the provider command supplied by the operator:

```bash
export AO_MA10_MINIMAX_REVIEW_CMD="python3 -m ao_kernel.ai_review_provider_wrappers mavis"
export AO_MA10_MAVIS_BIN="mavis"  # Optional; use ~/.mavis/bin/mavis when Mavis is not on PATH.
export AO_MA10_MAVIS_FROM_SESSION_ID="<local-agent-session-id>"
export AO_MA10_MAVIS_TO_SESSION_ID="<mavis-orchestrator-session-id>"

python3 scripts/ao_ma10_high_risk_raw_review_producer.py \
  --work-package "AO-MA-10 high-risk provider separation" \
  --base-ref origin/main \
  --head-ref HEAD \
  --implementer-provider openai
```

The wrapper accepts only messages from the configured Mavis target session to
the configured local session whose `time_created` is after the current send
operation. Older MiniMax messages in the daemon queue are ignored; timeout is a
fail-closed result, not an implicit approval.

## Stop Conditions

Stop and keep PR #997 blocked if any of these occur:

- The config endpoint does not report credential readiness.
- The selected local port is already in use and no alternate port has been
  selected consistently.
- Provider request returns an authentication, timeout, or transport error.
- Provider response is not valid JSON.
- Provider response records `REVISE`, `BLOCK`, or any non-AGREE verdict.
- Any token, key, credential, or config value is printed.
- Any evidence file is manually altered to change the provider verdict.

## Cleanup

After the local evidence attempt, stop the foreground daemon and remove local
runtime state from the worktree:

```bash
test -f .m/.runbook-05-minimax-mavis-runtime || {
  echo "cleanup marker missing; refusing to delete .m"
  exit 1
}

find .m -type f -delete
find .m -type l -delete
find .m -depth -type d -empty -delete
```

Confirm the worktree does not include generated state:

```bash
git status --short
```

## References

- PR #997 diagnosis comment: `https://github.com/Halildeu/ao-kernel/pull/997#issuecomment-4794769811`
- V5 gap document: `docs/V5-GOVERNED-CONTROL-PLANE-READINESS-GAP.md`
- V5 gap audit: `docs/V5-GOVERNED-CONTROL-PLANE-GAP-AUDIT.v1.json`
- High-risk review artifacts: `ao-ma-10-high-risk-reviews/`
