# Operator Runbook (V5 Epic 8 E-8-3)

> **Documentation only.** **Operator-owned playbook.** This runbook
> describes operational procedures (rollback, tag revert, pause, emergency
> stop, incident triage) an operator follows when running ao-kernel in
> production. It does NOT flip any of the three V5 guard flags
> (`support_widening`, `production_platform_claim`,
> `live_adapter_execution`), which remain `const false`. No
> production-ready posture is established by this runbook; the final
> posture is recorded ONLY by the operator-bound supersession PR at the
> end of the V5 roadmap.

## 1. Scope

This runbook is a complement to:

- [`PRODUCTION-DEPLOYMENT-GUIDE.md`](PRODUCTION-DEPLOYMENT-GUIDE.md) — three deployment patterns
- [`incident-response/`](incident-response/) — E-6-6 incident response playbook (canonical)
- [`incident-response/vendor-escalation-matrix.v1.json`](incident-response/vendor-escalation-matrix.v1.json) — E-6-6b vendor escalation

It covers five operator scenarios that the playbook does not detail:

1. Controlled rollback to a previous release
2. Tag revert (release tag retraction)
3. Pause / graceful stop without data loss
4. Emergency stop (drop-everything halt)
5. Incident triage decision tree

## 2. Rollback to a Previous Release

### 2.1 Standalone Python (pip)

```bash
# 1. Confirm current installed version
ao-kernel version

# 2. Pin to the previous release in a clean venv
python -m venv .venv-rollback
source .venv-rollback/bin/activate
pip install 'ao-kernel==<previous-version>'

# 3. Smoke check
ao-kernel doctor

# 4. Cut traffic over via your process manager (systemd / supervisord)
#    while keeping the old workspace .ao/ mounted read-only.
```

The `.ao/` workspace is **forward-compatible across patch releases**;
schema-breaking changes carry their own migration notes (see
`MIGRATION-GUIDE-V4-TO-V5.md`).

### 2.2 Docker

```bash
# 1. Confirm current image digest
docker images your-registry/ao-kernel --digests

# 2. Pull the previous tag (or pinned digest)
docker pull your-registry/ao-kernel:<previous-tag>

# 3. Replace the running container; keep the evidence volume
docker stop ao-kernel-current
docker run -d --name ao-kernel-rollback \
  --volume ao-kernel-evidence:/home/aoekernel/.ao \
  --env-file /etc/ao-kernel/secrets.env \
  your-registry/ao-kernel:<previous-tag>
```

### 2.3 Kubernetes

```bash
# 1. Inspect rollout history
kubectl rollout history deployment/ao-kernel

# 2. Roll back to a specific revision
kubectl rollout undo deployment/ao-kernel --to-revision=<N>

# 3. Verify
kubectl rollout status deployment/ao-kernel
kubectl logs deployment/ao-kernel --tail=50
```

The `kubectl rollout undo` mechanism preserves the existing PVC, so the
evidence trail is intact across the rollback.

## 3. Tag Revert (Release Tag Retraction)

When a release tag must be retracted (e.g. published with an undetected
governance violation):

1. **Yank the PyPI release** (does NOT delete from cache; existing
   installs continue to work but new `pip install` resolves to the next
   non-yanked version):
   ```bash
   twine upload --skip-existing --repository pypi dist/ao-kernel-<v>*
   # Yank via PyPI web UI: Project -> Releases -> <version> -> Yank
   ```
2. **Reissue with a patch bump** (NEVER reuse a yanked version number).
3. **Update CHANGELOG.md** to mark the yanked release.
4. **Update SBOM** (E-6-1) to drop the yanked version.
5. **Open an incident postmortem** per the E-6-6 incident response
   playbook.

Tag deletion from git is NOT recommended; the audit trail must remain.

## 4. Pause / Graceful Stop

Use when you must temporarily halt new request acceptance without
losing in-flight work or evidence.

### 4.1 Standalone

Send `SIGTERM` to the MCP server process. The MCP server completes
in-flight calls, flushes evidence buffers, and exits cleanly:

```bash
pgrep -f 'ao-kernel mcp serve' | xargs kill -TERM
```

### 4.2 Docker

```bash
docker stop --time 60 ao-kernel-current
```

The 60s grace window allows the JSONL append-only evidence writer to
fsync any in-flight events.

### 4.3 Kubernetes

```bash
# Scale to zero pods (preserves PVC)
kubectl scale deployment/ao-kernel --replicas=0

# When ready to resume:
kubectl scale deployment/ao-kernel --replicas=<N>
```

## 5. Emergency Stop (Drop Everything)

Use ONLY when you have credible evidence of an active governance
violation that you cannot triage in real time (e.g. credential leakage
detected in evidence stream, runaway cost burn).

### 5.1 Three concurrent actions

1. **Revoke LLM provider credentials immediately** at the provider
   console (Anthropic console, OpenAI dashboard, etc.). This is the
   single most important step. Do NOT wait for graceful shutdown.
2. **Force-stop the running ao-kernel process / container / pod.**
3. **Snapshot the evidence trail** (copy `.ao/` to a forensic store)
   before any restart attempt.

### 5.2 Recovery sequence

After emergency stop:

1. Rotate API keys + secrets per the E-6-3 SOC2 + E-6-3b HIPAA + E-6-3c
   GDPR + E-6-3d PCI + E-6-3e NIST CSF mappings as applicable to your
   tenancy posture.
2. Run a full SBOM + vuln scan (E-6-1 + E-6-2 + E-6-5) on the evidence
   snapshot and the image set.
3. Write the postmortem before restoring service (E-6-6 playbook + E-6-6b
   vendor escalation matrix).

## 6. Incident Triage Decision Tree

```
incident-reported
       │
       ▼
 ┌─────────────┐
 │ Is governance│ yes ──▶ Emergency Stop (§5)
 │  violation? │
 └──────┬──────┘
        no
        ▼
 ┌─────────────┐
 │ Is data at  │ yes ──▶ Pause + forensic snapshot (§4)
 │   risk?     │
 └──────┬──────┘
        no
        ▼
 ┌─────────────┐
 │ Is SLI       │ yes ──▶ Rollback (§2) per E-6-6 playbook
 │  breached?  │
 └──────┬──────┘
        no
        ▼
   Operator triage: dashboards (E-5-2), tracing (E-5-3),
   SLO budget (E-5-4), alerts (E-5-5).
```

## 7. Operator Boundaries

This runbook describes **operator-owned** scenarios. ao-kernel does NOT
perform any of these actions on the operator's behalf. The runbook is
descriptive, not executable. Specifically:

- **Credential rotation** is operator + secret-store responsibility.
- **Customer notification** of incidents is operator + counsel
  responsibility per the regulatory disclosure matrix (E-6-3 family).
- **Postmortem cadence** is operator program responsibility.
- **Vendor escalation** uses the E-6-6b matrix; operator owns the actual
  escalation contact.
- **Live deployment evidence** (uptime, latency, cost burn) is operator
  telemetry, not ao-kernel claim.

## 8. Pre-Production Note

While the V5 roadmap is open, **all five scenarios are exercised as
tabletop drills**, not against a live customer-facing surface. Live
production exercise authority lives with the operator-bound supersession
PR at the end of the V5 roadmap.

## 9. Cross-AI Peer Review Trail

Per HARD RULE Cross-AI Peer Review (2026-05-05 + 2026-05-14):

- Implementer Anthropic Claude → Reviewer OpenAI Codex (post-impl).
- Plan-time consensus required for any change to operator-boundary
  language or guard-flag disclaimer.
- Codex iter chain audit trail in
  [`../.claude/plans/EPIC-8-3-OPERATOR-RUNBOOK.md`](../.claude/plans/EPIC-8-3-OPERATOR-RUNBOOK.md).

## 10. References

- [`PRODUCTION-DEPLOYMENT-GUIDE.md`](PRODUCTION-DEPLOYMENT-GUIDE.md) — E-8-1
- [`MIGRATION-GUIDE-V4-TO-V5.md`](MIGRATION-GUIDE-V4-TO-V5.md) — E-8-6 (if present)
- [`incident-response/`](incident-response/) — E-6-6 canonical playbook
- V5 roadmap: [`../.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`](../.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md)
- E-5-1..5-5 observability (referenced in §6 decision tree)
- E-6-1..6-6b security surfaces (referenced in §5 recovery)
- HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14)
- HARD RULE Uzun Vadeli Kalıcı Çözüm
