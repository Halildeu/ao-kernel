# AO-MA-10T - Dedicated Actor Secret Bootstrap

## Purpose

AO-MA-10S moved the final low-risk no-human smoke into a main-only GitHub
Actions workflow. This document records the earlier dedicated PAT bootstrap
path. That path is now historical: the accepted low-risk lane uses the
repo-owned workflow executor (`github-actions[bot]` / `app/github-actions`)
and does not require `GLADYATORE_LAB_GH_TOKEN` for the accepted AO-MA-10q
smoke.

The historical AO-MA-10T operator-contact path was:

1. the dedicated actor token is provided to the agent process through one named
   environment variable;
2. the bootstrap script writes the repository secret with `gh secret set` via
   stdin;
3. the output artifact records metadata only;
4. the next step is dispatching the already-main AO-MA-10S execute smoke.

This does not make a PAT, admin account, or AI output release authority.
Release authority remains `ao-release-gate+github-ruleset`.

## Command

Do not paste the token into chat, shell history, or a command-line flag. Put it
in the process environment and run:

```bash
export GLADYATORE_LAB_GH_TOKEN='<dedicated gladyatore-lab fine-grained token>'

python3 scripts/ao_ma10t_configure_dedicated_actor_secret.py \
  --output .ao/evidence/ao-ma-10t/dedicated-actor-secret-bootstrap.json \
  --execute \
  --confirmation AO-MA-10T-CONFIGURE-SECRET \
  --format text
```

The script passes the token to:

```bash
gh secret set GLADYATORE_LAB_GH_TOKEN --repo Halildeu/ao-kernel
```

through stdin. It does not put the token in argv or the evidence artifact.

## Success Criteria

- `decision.result == "secret_configured"`
- `mutations_performed == true`
- `token_value_recorded == false`
- `secret_value_recorded == false`
- `secret_metadata.name == "GLADYATORE_LAB_GH_TOKEN"`

Historical next step after success was dispatching AO-MA-10S:

```bash
gh workflow run 285224724 \
  --repo Halildeu/ao-kernel \
  --ref main \
  -f mode=execute \
  -f confirmation=AO-MA-10L-EXECUTE \
  -f timeout_seconds=900 \
  -f poll_seconds=10
```

Historical note: the `gladyatore-lab` fine-grained PAT path later proved unable
to call GitHub's pull merge endpoint. The accepted no-human low-risk evidence is
AO-MA-10q workflow run `26633091281`, which records `runner_status=0`,
decision `merged`, PR #737, and merge actor `app/github-actions`.

## Guardrails

- No support widening.
- No production platform claim.
- No live adapter execution.
- No admin bypass.
- No token material in evidence, PR text, logs, or command-line flags.
- The accepted smoke merge actor is the repo-owned workflow executor, not a PAT
  user and not an admin bypass.
