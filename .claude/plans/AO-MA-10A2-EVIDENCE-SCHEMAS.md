# AO-MA-10a2 - Context-Bound Evidence Bundle + Registered Provider Schemas

**Status:** recorded / schema + read-only builder slice
**Date:** 2026-05-28
**Parent:** AO-MA-10 low-risk autonomous merge lane
**Support impact:** none
**Production platform claim:** false
**Live adapter execution:** false

## Purpose

AO-MA-10a2 defines the evidence contract that later AO-MA-10 slices will feed
into `ao-release-gate`. It does not change GitHub settings and does not activate
autonomous merge.

The slice records two strict schemas:

1. `ao-ma-10-provider-consensus.schema.v1.json`
2. `ao-ma-10-evidence-bundle.schema.v1.json`

and a read-only local builder:

```text
scripts/ao_ma10_evidence_bundle.py
```

The bundle binds registered provider verdicts to one exact repository diff:

```text
repository_full_name + base_ref + head_ref + head_sha + diff_digest + changed_files_count
```

This prevents stale, replayed, or context-free AI agreement from becoming merge
evidence in later slices.

## Claude Consultation

Claude was consulted before implementation. It recommended AO-MA-10a2 as the
next slice and explicitly rejected jumping directly to live GitHub settings,
ruleset mutation, branch-protection mutation, or merge-agent execution.

The accepted order remains:

```text
AO-MA-10a2  evidence bundle + registered-provider consensus schemas
AO-MA-10b   ao-release-gate payload + decision integration
AO-MA-10d   negative fail-closed suite
AO-MA-10c   merge-agent identity + dry-run executor
AO-MA-10e   positive disposable low-risk autonomous merge smoke
AO-MA-10f   activation/cutover
```

## Contract

The provider consensus artifact records one registered provider's verdict:

- provider id (`openai`, `anthropic`, `minimax`, `google`, or `xai`);
- agent id;
- role (`reviewer`, `verifier`, or `planner`);
- verdict (`AGREE`, `REVISE`, `PARTIAL`, or `RED`);
- round index bounded to `1..3`;
- the exact context binding;
- no-secret and guard flags.

The evidence bundle aggregates at least two provider verdicts and requires the
current hard baseline providers:

```text
openai + anthropic
```

MiniMax stays registered but optional until its transport is verified in a later
provider-integration slice.

## Hard Stops

This slice does not:

- mutate `.github/**`;
- mutate `CODEOWNERS`;
- mutate branch protection or rulesets;
- change `ao_kernel/ao_release_gate*.py`;
- change `scripts/ao_release_gate*.py`;
- change `scripts/local_gpp_gate*.py`;
- change `gpp_status.v1.json`;
- execute live adapters;
- widen support;
- claim production platform readiness;
- activate or execute any merge agent.

## Acceptance

AO-MA-10a2 is accepted when:

1. both schemas are Draft 2020-12 valid and strict (`additionalProperties: false`);
2. valid provider and bundle fixtures pass schema validation;
3. invalid same-provider, missing `head_sha`, stale freshness, guard-flag flip,
   secret flag, and live-adapter flag cases fail closed;
4. the read-only builder emits a schema-valid bundle from a local git diff and
   provider artifacts;
5. provider artifacts whose context does not match the bundle diff are rejected;
6. script token scans show no GitHub write APIs, no admin merge, no ruleset
   mutation, no CODEOWNERS mutation, and no PR merge call;
7. `local_gpp_gate` accepts the PR evidence without changing release authority.
