# Production Deployment Guide (V5 Epic 8 E-8-1)

> **Documentation only.** **Not a production-ready certification.** This
> guide describes deployment patterns an operator may use; it does NOT
> flip any of the three V5 guard flags
> (`support_widening`, `production_platform_claim`,
> `live_adapter_execution`), which remain `const false`. No
> production-ready posture is established by this guide; the final
> posture is recorded ONLY by the operator-bound supersession PR at
> the end of the V5 roadmap; no individual epic or slice can flip
> those flags.

## 1. Scope

This guide covers three deployment patterns for ao-kernel:

- **Standalone Python package** (`pip install ao-kernel`)
- **Docker container** (Dockerfile + Compose)
- **Kubernetes microservice** (Helm chart pattern — chart scaffold deferred to E-4-1)

Each pattern preserves the governed-runtime contract: policy SSOT in
`ao_kernel/governance.py`, evidence trail in JSONL append-only logs,
guard flags `const false`, and operator-owned credential boundary.

## 2. Standalone Python Package

### 2.1 Minimum install

```bash
python -m venv .venv
source .venv/bin/activate
pip install ao-kernel               # core (jsonschema only)
ao-kernel init                       # create .ao/ workspace
ao-kernel doctor                     # 8 health checks
```

The `core` install is fully sufficient for policy evaluation, evidence
replay, workflow inspection, and MCP server hosting. Add extras only
when needed:

| Extra | When needed |
|---|---|
| `[llm]` | Real LLM dispatch with tenacity retry + tiktoken token counting |
| `[mcp]` | MCP server (stdio) |
| `[mcp-http]` | MCP server over HTTP (starlette + uvicorn) |
| `[otel]` | OpenTelemetry traces + metrics |
| `[pgvector]` | pgvector backend pin (backend impl in E-7-5) |

### 2.2 Workspace layout

```
your-project/
├── .ao/
│   ├── canonical_decisions.v1.json
│   ├── checkpoints/
│   ├── evidence/
│   ├── facts/
│   └── policies/
├── ao_kernel_workspace.yaml
└── your_code.py
```

Workspace is resolved via `config.workspace_root()` (CWD up-walk).
Library mode (`workspace_root=None`) is in-memory; workspace mode
activates the full evidence + checkpoint + canonical-store pipeline.

### 2.3 Required environment

- **Python:** 3.11+ (3.11 / 3.12 / 3.13 tested in CI)
- **OS:** POSIX (Linux, macOS); Windows scheduled for E-3-2 (V5 roadmap)
- **Secrets:** env-var resolution only (NEVER passed as MCP parameters)

### 2.4 Health checks

```bash
ao-kernel doctor                     # 8 categories: workspace, policies, schemas, ...
ao-kernel evidence timeline          # evidence trail
ao-kernel policy-sim ...             # dry-run policy simulation
ao-kernel metrics ...                # usage + cost (opt-in)
```

## 3. Docker Container

### 3.1 Minimal Dockerfile pattern

```dockerfile
FROM python:3.13-slim

# Non-root user for governance plane
RUN useradd --create-home --shell /bin/bash aoekernel
USER aoekernel
WORKDIR /home/aoekernel

# Pin to a specific ao-kernel release
RUN pip install --no-cache-dir 'ao-kernel==4.2.1' 'ao-kernel[mcp,llm,otel]'

# Workspace + evidence volume mount points
VOLUME /home/aoekernel/.ao

# Default: launch the MCP server over stdio
CMD ["ao-kernel", "mcp", "serve"]
```

### 3.2 Compose pattern (governance + evidence persistence)

```yaml
services:
  ao-kernel:
    image: your-registry/ao-kernel:4.2.1
    user: aoekernel
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
    volumes:
      - ao-kernel-evidence:/home/aoekernel/.ao
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "ao-kernel", "doctor"]
      interval: 60s
      timeout: 30s
      retries: 3

volumes:
  ao-kernel-evidence:
```

### 3.3 Operator boundaries

- Secrets MUST come from operator-managed env vars or secret stores
  (HashiCorp Vault, AWS Secrets Manager, etc.). NEVER baked into the
  image, NEVER passed as CLI arguments.
- Image SHOULD be SBOM-scanned (E-6-1 CycloneDX) and vuln-scanned
  (E-6-2 Trivy + Dependabot, E-6-5 CodeQL) before production push.
- Multi-arch builds (Linux ARM64, Apple Silicon) are an open follow-up
  in E-3-5.

## 4. Kubernetes Microservice (operator-deployed)

### 4.1 Reference architecture

```
┌──────────────────────────────────────────────────────────┐
│ Kubernetes Cluster (operator-managed)                    │
│                                                           │
│  ┌────────────┐   ┌─────────────┐   ┌─────────────────┐  │
│  │ Ingress    │──▶│ ao-kernel   │──▶│ Secrets         │  │
│  │ (mTLS/SSO) │   │ Pod(s)      │   │ (External       │  │
│  │            │   │             │   │  Secrets Op.)   │  │
│  └────────────┘   └──────┬──────┘   └─────────────────┘  │
│                          │                                │
│                  ┌───────▼───────┐    ┌───────────────┐  │
│                  │ Persistent    │    │ OTEL Collector │  │
│                  │ Volume (.ao/) │    │ (E-5-1)        │  │
│                  └───────────────┘    └───────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### 4.2 Required components

- **Deployment:** ao-kernel Pod(s); image-pinned, non-root
- **PersistentVolumeClaim:** for `/home/aoekernel/.ao` (evidence trail)
- **Secret:** API keys via ExternalSecrets operator (NOT plain k8s
  Secret YAML committed to git)
- **Service:** stdio MCP behind sidecar OR HTTP MCP via `[mcp-http]` +
  ingress
- **ConfigMap:** workspace policies + extension manifests (read-only
  mount)
- **NetworkPolicy:** restrict egress to operator-allowed LLM provider
  endpoints
- **PodDisruptionBudget:** operator-defined SLO

### 4.3 Helm chart status

A Helm chart scaffold is **deferred to E-4-1** (Epic 4 Deployment).
This guide documents the architecture pattern; operators can author
their own Helm chart or Kustomize overlay against the patterns above
in the interim.

### 4.4 Multi-tenancy boundary

Multi-tenant production isolation (RBAC + secret + quota + audit) is
covered separately in E-4-3 (operator runbook) + E-4-4 (tenancy
isolation test suite). v1 single-tenant deployment is the supported
baseline.

## 5. Observability

| Capability | Status |
|---|---|
| OTEL traces + metrics | E-5-1 (lazy import, no-op fallback when extras absent) |
| Prometheus dashboards | E-5-2 (Grafana JSON templates) |
| Distributed tracing | E-5-3 (multi-session correlation) |
| SLI/SLO definitions | E-5-4 (catalog) |
| Alertmanager rules | E-5-5 (rule templates) |

Operator owns the SLO budget, alert routing, and on-call rotation.

## 6. Security Surfaces

| Surface | Slice |
|---|---|
| SBOM (CycloneDX) | E-6-1 |
| Vuln scanning | E-6-2 (Dependabot + Trivy, in pipeline) |
| SOC2/ISO mapping | E-6-3 |
| HIPAA control mapping | E-6-3b |
| GDPR DPIA template | E-6-3c |
| PCI-DSS mapping | E-6-3d |
| NIST CSF mapping | E-6-3e (in pipeline) |
| License compliance | E-6-4 |
| CodeQL analysis | E-6-5 (in pipeline) |
| Incident response playbook | E-6-6 |
| Vendor escalation matrix | E-6-6b |

These are **control-reference mappings + advisory baselines**, not
compliance claims. See each artifact's disclaimer banner.

## 7. Operator-Owned Surfaces

ao-kernel ships **runtime + governance plane + evidence trail**. The
following surfaces are explicitly operator-owned and out of repo
scope:

- Authentication (SSO, MFA), authorization, IAM, key management
- Transport encryption (TLS), certificate management, cipher policy
- Physical security, datacenter controls, environmental controls
- HR (hiring, training, termination)
- BCP, DR plan, RTO/RPO target setting
- Vendor contract negotiation, supplier SLA review
- Regulatory disclosure determination (GDPR, HIPAA, jurisdiction-specific)
- Live deployment evidence, customer notification, tabletop exercises
- Incident on-call rotation, postmortem distribution cadence
- LLM provider rate limits + cost guardrails (operator API agreements)

## 8. Roadmap Forward References

| What | Where |
|---|---|
| Live adapter execution (flag flip) | E-2-1 (operator-bound supersession PR) |
| Support widening (Windows + ARM64 + provider matrix) | E-3-1..5 |
| Helm chart scaffold | E-4-1 |
| Multi-tenant config recipe | E-4-3 |
| pgvector backend impl | E-7-5 |
| Migration guide v4.x → v5.0.0 | E-8-6 (merged) |

## 9. References

- V5 roadmap: [`../.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`](../.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md)
- README: [`../README.md`](../README.md)
- Doctor + CLI surfaces: `ao_kernel/cli.py`
- Workspace resolver: `ao_kernel/config.py`
- Migration guide: [`MIGRATION-GUIDE-V4-TO-V5.md`](MIGRATION-GUIDE-V4-TO-V5.md) (if present)
