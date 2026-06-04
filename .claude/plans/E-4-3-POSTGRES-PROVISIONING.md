# E-4-3 — Operator-owned PostgreSQL provisioning + secret management

> V5 Epic 4 (Deployment, operations, tenancy). Slice issue: #862.
> Builds on E-4-1 Helm chart skeleton (#829). Guard-flag-independent
> (infrastructure-only; no `live_adapter_execution` / `support_widening`
> / `production_platform_claim` touched).

## Goal

Give operators a **secure, chart-referenced** path to wire an
**external, operator-owned** PostgreSQL backend into the ao-kernel Helm
chart — without the chart deploying a database or holding any secret.

## What this slice delivers

1. `docs/OPERATOR-SECRET-MANAGEMENT.md` — operator runbook: provision PG
   (managed / in-cluster operator / StatefulSet), create the Kubernetes
   Secret out-of-band (file-based, not shell-literal), bind via
   `secretKeyRef`, rotate.
2. `deploy/helm/ao-kernel/values.yaml` — `postgresql` block
   (`enabled: false` default; host/port/dbname/sslmode plain;
   secretName + usernameKey + passwordKey pointers — **no inline creds**).
3. `deploy/helm/ao-kernel/values.schema.json` — closed `postgresql`
   schema (`additionalProperties: false`; sslmode enum pins safe modes).
4. `deploy/helm/ao-kernel/templates/deployment.yaml` — DB env gated on
   `postgresql.enabled`; username/password via `secretKeyRef` ONLY,
   connection coordinates via plain env.
5. `tests/test_epic_4_3_postgres_provisioning.py` — 16 invariants.

## Invariants (machine-enforced)

- `postgresql.enabled` defaults `false` (library/in-memory is the default).
- No inline credential literal anywhere (secretKeyRef only).
- Chart does NOT deploy PostgreSQL (no `image: postgres`, no `StatefulSet`).
- values.schema.json closes the block; sslmode enum includes require/verify-full.
- Runbook covers operator-owned rationale + rotation + secretKeyRef + guard-flag affirmation + pgvector(E-7-5) disambiguation.
- No `.github/workflows/` mutation (introducer-PR detected diff).
- No runtime guard-flag key strings introduced.

## Boundaries (NOT in scope)

- NOT deploying PostgreSQL (operator-owned, out-of-band).
- NOT creating the Secret (operator pre-provisions; chart references).
- NOT enabling pgvector / semantic backend (separate E-7-5, lazy import).
- NOT flipping any guard flag; NOT claiming production readiness (beta).

## Cross-AI review

Implementer Anthropic; reviewer OpenAI (Codex MCP). Low-risk lane
(no `.github/workflows/`, no CODEOWNERS/ruleset). Root
`local-ai-review-evidence.v1.json` carries the gate attestation.
