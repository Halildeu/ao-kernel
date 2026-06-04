# Operator Secret Management + PostgreSQL Provisioning (V5 Epic 4 E-4-3)

> **Scope:** This document is the operator runbook for provisioning the
> Kubernetes Secrets and the **operator-owned** PostgreSQL backend that the
> `ao-kernel` Helm chart references. The chart **never creates secrets** and
> **never deploys a database** — it only references operator-provisioned
> resources via `secretKeyRef`. This keeps secret material out of chart
> values, git history, and rendered manifests (HARD RULE: secrets ASLA
> log/parametre/inline).
>
> **Beta / no production claim.** This runbook documents the *pattern*; it
> does not assert production readiness. The three guard flags
> (`support_widening`, `production_platform_claim`, `live_adapter_execution`)
> remain `const false` and are NOT touched by this slice.

## 1. Why operator-owned (not chart-managed)

ao-kernel is a **governed orchestration runtime library**, not a database
operator. Bundling a PostgreSQL StatefulSet into the chart would:

- couple the runtime's release cadence to a database's,
- put backup/restore/HA/upgrade burden inside a library chart,
- tempt inline credential defaults (a secret-leak vector).

Instead the operator provisions PostgreSQL out-of-band (managed cloud service,
existing cluster operator such as CloudNativePG/Zalando, or a dedicated
StatefulSet) and hands the chart a **connection reference + a Kubernetes
Secret**. The chart consumes them through `env.secretRefs` only.

## 2. Provision the PostgreSQL backend (operator choice)

Pick ONE; the chart is agnostic. Examples (operator runs these, NOT the chart):

| Option | When | Note |
|---|---|---|
| Managed (RDS / Cloud SQL / Azure DB) | production | operator owns backup/HA/patching |
| In-cluster operator (CloudNativePG, Zalando) | self-hosted prod | operator CRD owns lifecycle |
| Single StatefulSet | dev / staging | no HA; not for production |

Required outputs from whichever option:
`host`, `port`, `dbname`, `sslmode`, plus a **username** and **password**.

## 3. Create the Kubernetes Secret (out-of-band)

The chart references a Secret it does NOT create. Provision it with the
**least-privilege** application role (never the superuser):

```bash
# Operator runs this; password is read from a file or a secret manager,
# NEVER passed as a shell literal that lands in shell history.
kubectl create secret generic ao-kernel-db \
  --namespace "$AO_NS" \
  --from-literal=username="$(cat ./.pg-app-user)" \
  --from-file=password=./.pg-app-password
```

For GitOps, prefer an **ExternalSecret** (External Secrets Operator) so the
ciphertext lives in a secret manager (Vault, AWS/GCP Secrets Manager) and only
the synced `Secret` exists in-cluster. The chart binding is identical either
way — it only needs the resulting `Secret` name + keys.

## 4. Bind the Secret to the chart

In your operator-owned `values.yaml` overlay (NOT committed with real values):

The `postgresql` block is the **single** way to wire the database — when
`enabled: true`, the chart automatically renders the `AO_KERNEL_DB_HOST`,
`AO_KERNEL_DB_PORT`, `AO_KERNEL_DB_NAME`, `AO_KERNEL_DB_SSLMODE` (plain env) and
`AO_KERNEL_DB_USERNAME` / `AO_KERNEL_DB_PASSWORD` (`secretKeyRef`) variables.
**Do NOT also add these to `env.secretRefs` / `env.plain`** — that would
duplicate (and conflict with) the auto-rendered DB env (Codex E-4-3 review).

```yaml
postgresql:
  enabled: true
  # Operator-owned, external. The chart does NOT deploy this database.
  host: "ao-kernel-db.example.internal"   # non-secret connection coordinates
  port: 5432
  dbname: "ao_kernel"
  sslmode: "require"                        # require|verify-full in production
  # Username + password are resolved via secretKeyRef ONLY (never inline).
  secretName: "ao-kernel-db"
  usernameKey: "username"
  passwordKey: "password"
```

The chart renders `AO_KERNEL_DB_USERNAME` / `AO_KERNEL_DB_PASSWORD` via
`secretKeyRef` (see `templates/deployment.yaml`); connection coordinates are
plain env (non-secret). The `env.secretRefs` / `env.plain` lists remain for
**other** secrets (e.g. LLM provider API keys) — not for the DB, which the
`postgresql` block owns.

## 5. Rotation

1. Update the password in the secret manager (or `kubectl create secret ...
   --dry-run=client -o yaml | kubectl apply -f -`).
2. `kubectl rollout restart deploy/<release>-ao-kernel -n "$AO_NS"`.
3. Verify readiness; the pod picks up the new `secretKeyRef` value on restart.

Never edit a live Secret with an inline literal in a tracked file. Never put
the password in `values.yaml` committed to git.

## 6. What this slice does NOT do

- Does NOT deploy PostgreSQL (operator-owned, out-of-band).
- Does NOT create the Secret (operator pre-provisions; chart references).
- Does NOT enable any pgvector / semantic backend (that is E-7-5, lazy import,
  optional `[pgvector]` extra; this slice is connection + secret plumbing only).
- Does NOT flip any guard flag or claim production readiness.

## 7. Cross-references

- Chart values contract: `deploy/helm/ao-kernel/values.yaml` (`postgresql` block)
- Multi-tenant deployment: `docs/MULTI-TENANT-DEPLOYMENT.md` (E-4-2a/2b)
- pgvector backend (separate, optional): `ao_kernel/context/semantic_backends/pgvector.py` (E-7-5)
