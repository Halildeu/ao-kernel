# E-4-2a — Multi-Tenant Advisory Boundary Contract (Early Seal)

> **Statü:** ACCEPTED · V5 Epic 4 ikinci slice (E-4-2a). Erken advisory boundary kontratı; per-dimension entries PLACEHOLDER (E-4-2b'de filled).
> **Parent epic plan:** `.claude/plans/EPIC-4-KUBERNETES-HELM-MULTI-TENANT.md` §2 E-4-2a (iter-2 F1 absorb sonrası E-4-2 split)
> **Owner:** Halil Kocoglu · **Implementer:** Claude (Anthropic) · **Reviewer:** Codex (OpenAI) — plan-time AGREE thread `019e879d`; post-impl review thread TBD
> **Risk:** low (advisory contract; schema + matrix placeholder; runtime'a etki yok) · **Cross-AI:** 2-way (Codex only — 3-way Mavis additional reserved for E-4-2b high-risk final seal)
> **Bağımlılık:** E-4-1 (chart skeleton — bu slice chart template'lerine dokunmaz ama referans verir) — bu slice'ın write-set'i E-4-1'den bağımsız (sadece docs + schema + matrix + plan + test)

---

## 1. Slice nedir

Bu slice multi-tenant advisory boundary contract'ı **erken** mühürler. 7 isolation dimension için **şekil sözleşmesi** (schema + placeholder entries + advisory dil disiplini) yazılır. Per-dimension gerçek değerler (filled state) E-4-2b'de doldurulur. Erken kontrat, downstream slice'ları (E-4-3 DB/secret pattern, E-4-4 observability surface, E-4-5 NetworkPolicy + PSS baseline) bloklamaktan kurtarır — onlar bu boundary contract'a referans verebilir, ama final matrix seal E-4-2b'de yapılır.

### Neden split (Codex iter-2 F1 absorb)

Codex iter-1 review'unda E-4-2 (önceki tek-slice yaklaşım) high-risk olarak işaretlenmişti çünkü cross-tenant boundary matrix final seal **hem** schema kontratını **hem** downstream evidence ref'lerini taşıyordu. Iter-2'de F1 fix:

- **E-4-2a (bu slice):** sadece schema + matrix placeholder + advisory dil — düşük risk, 2-way cross-AI yeterli, erken merge
- **E-4-2b (gelecek slice):** filled matrix + downstream evidence ref + 3-way cross-AI (Codex + Mavis) — yüksek risk, en sonda mühürleme

Bu sayede E-4-3 / E-4-4 / E-4-5 paralel ilerleyebilir; her biri bu erken kontrat'a referans verir.

---

## 2. Write-set (git diff --name-only origin/main..HEAD ile birebir eşleşmeli)

```
docs/MULTI-TENANT-DEPLOYMENT.md
.claude/plans/E-4-2a-MULTI-TENANT-BOUNDARY-CONTRACT.md
.claude/plans/E-4-2a-MULTI-TENANT-BOUNDARY-CONTRACT.v1.json
.claude/plans/tenant_isolation_matrix.v1.json
ao_kernel/defaults/schemas/e-4-2a-multi-tenant-boundary-contract.schema.v1.json
ao_kernel/defaults/schemas/tenant-isolation-matrix.schema.v1.json
tests/test_epic_4_2a_multi_tenant_boundary.py
local-ai-review-evidence.v1.json
```

### Hiç dokunulmayan boundary'ler (zero-touch, machine-enforced)

- `.github/workflows/**` — F3 absorb; pyproject diff guard write_set test'inde
- `pyproject.toml` — Epic 4 invariant
- `ao_kernel/__init__.py` — runtime modülü dokunulmaz
- `ao_kernel/<her bir mevcut modül>.py` — sadece `ao_kernel/defaults/schemas/` altına YENİ JSON dosyaları eklenir; mevcut Python source modüllere dokunulmaz
- `deploy/helm/ao-kernel/` — E-4-1 territory; bu slice chart template'lerine dokunmaz

---

## 3. Advisory dil disiplini (F4 absorb)

Doc + matrix + schema'da kullanılan dil **advisory boundary pattern**'i ifade eder; **isolation guarantee** dilini reddeder.

| Yasak dil | Kullanılan dil |
|---|---|
| isolation achieved | isolation pattern |
| isolation enforced | advisory boundary |
| fully isolated | operator-enforceable |
| runtime enforces | `runtime_enforced: false` |
| operator_enforced: true | `operator_enforceable: true` |
| (implicit live validation) | `live_validated: false` |

Her dimension entry'sinde 4 const field zorunlu: `runtime_enforced: false`, `operator_enforceable: true`, `operator_action_required: true`, `live_validated: false`.

---

## 4. 7-dimension shape (placeholder; E-4-2b'de filled)

| Sıra | Dimension | enforcement_mechanism özet |
|---|---|---|
| 1 | namespace_isolation | One Helm release per Kubernetes Namespace; ClusterRole/ClusterRoleBinding YOK |
| 2 | rbac_scope | Role + RoleBinding namespace-scoped; cross-namespace verb YOK |
| 3 | secret_isolation | Per-namespace Kubernetes Secret + secretKeyRef indirection |
| 4 | network_policy | Default-deny ingress/egress + operator allowlist (E-4-5 cross-ref reserved) |
| 5 | resource_quota | ResourceQuota + LimitRange per-namespace (operator-applied) |
| 6 | audit_boundary | Per-tenant `workspace_root` + JSONL evidence per-tenant |
| 7 | cost_tracking_advisory | Per-tenant cost rollup operator dashboard (chart-rendered surface DEĞİL) |

E-4-2b'de her dimension için `downstream_evidence_ref` doldurulur (E-4-3, E-4-4, E-4-5 evidence path'leri).

---

## 5. Test invariants (11 kategori)

Per Codex iter-2 F2 + F3 + F4 absorb, plus this slice's specific lifecycle markers:

1. **shape**: 7 dimension entry; schema validates; doc exists
2. **no_guard_flip**: NO `support_widening` / `production_platform_claim` / `live_adapter_execution` key in any artifact (docs/MULTI-TENANT-DEPLOYMENT.md, matrix JSON, both schema JSONs, evidence JSON, plan doc)
3. **no_workflow_mutation**: `git diff --name-only origin/main..HEAD` only files in write-set; NO `.github/workflows/**`
4. **runtime_enforced_false_const**: schema `runtime_enforced` const false; all 7 entries `false`
5. **operator_enforceable_true_per_entry**: each dimension entry's `operator_enforceable` is `true`
6. **live_validated_false_const**: all 7 entries `live_validated: false`
7. **advisory_dil_test**: docs/MULTI-TENANT-DEPLOYMENT.md does NOT contain "isolation achieved" / "isolation enforced" / "fully isolated" / "runtime enforces" — only advisory dil
8. **placeholder_status_per_entry**: all 7 entries `entry_status: "placeholder"`
9. **write_set_exact_match**: evidence write_set EQUALS `git diff --name-only origin/main..HEAD`
10. **evidence_validates**: evidence JSON validates against evidence schema
11. **matrix_json_validates_against_matrix_schema**: matrix JSON validates against matrix schema

Plus meta checks: plan doc + schema files reachable; no_pyproject_change; no_runtime_module_change (only NEW schema files under `ao_kernel/defaults/schemas/`).

---

## 6. Guard-flag invariants (no-flip; F2 absorb)

3 guard flag const false korunur. Her artifact (docs + matrix + 2 schemas + evidence + plan + test) recursive grep:

- `support_widening` key string YOK
- `production_platform_claim` key string YOK
- `live_adapter_execution` key string YOK

> **Test pattern:** advisory_dil_test ek olarak overclaim kelime listesini de tarar; key absence ayrı invariant.

---

## 7. Cross-AI consensus protocol

| Phase | Verdict | Aksiyon |
|---|---|---|
| Plan-time (iter-2) | Codex AGREE thread `019e879d` (parent epic plan) | Impl başlat (Plan Consensus Autonomy) |
| Post-impl review | Codex MCP yeni thread; AGREE bekleniyor | AGREE → evidence verdict='AGREE' + final commit + auto-merge |
| 3-way Mavis | E-4-2b'de zorunlu; bu slice'da DEĞİL | (yok) |

Cross-AI provider distinctness invariant: implementer Anthropic + reviewer OpenAI ≠ aynı provider (HARD RULE Cross-AI Peer Review provider-level).

---

## 8. Acceptance kriterleri (özet)

- [x] Matrix JSON 7 dimension placeholder + advisory_only:true + runtime_enforced_global:false + live_validated_global:false
- [x] Matrix schema Draft 2020-12 strict (additionalProperties:false + unevaluatedProperties:false + allOf/contains per-dimension exact-once)
- [x] Evidence schema Draft 2020-12 strict; reviewer_providers minItems 2 + uniqueItems true
- [x] Doc dil disiplini (advisory only; no overclaim)
- [x] Test 11 invariants concrete (no `assert callable`, no `assert True`, no bare `except: pass`)
- [x] Write-set ↔ git diff exact match
- [x] Cross-AI peer review provider-level distinct
- [ ] Codex post-impl review AGREE (filled after submission)

---

## 9. Bağlantı (mevcut HARD RULE'lar ile)

- HARD RULE — Cross-AI Peer Review (2026-05-05): impl provider ≠ review provider
- HARD RULE — Admin Merge YASAK (2026-05-05): CI yeşil normal squash; admin bypass yok
- HARD RULE — Uzun Vadeli Kalıcı Çözüm (2026-05-27): schema-backed evidence + advisory dil + machine-enforced const fields
- HARD RULE — No Fake Work (2026-04-25): test'ler gerçekten koşar; cross-AI verdict gerçek Codex MCP response
- HARD RULE — CI Kırmızıyken Merge YASAK (2026-05-17): tüm checks yeşil olana kadar merge YOK
- CLAUDE.md §2 değişmezler: fail-closed + secrets + atomic writes (matrix JSON Python tooling ile atomic write yapmaz; insan-yazılan artifact)

---

## 10. Iter-2 absorb summary (parent epic plan'den miras)

Bu slice Codex thread `019e879d` iter-2 AGREE'de absorb edilen 8 finding'i (F1-F8) doğrudan içerir:

- **F1 (split):** E-4-2 → E-4-2a (bu slice) + E-4-2b
- **F2 (key absence):** 3 guard flag key string YOK her artifact'ta
- **F3 (workflow zero touch):** `.github/workflows/**` mutation YOK; write_set ↔ git diff exact match
- **F4 (advisory dil):** 4 const field per dimension + advisory dil disiplini + isolation overclaim YASAK
- **F5 (Slack absence):** bu slice chart template'lerine dokunmaz; Slack pattern E-4-4 territory
- **F6 (PSS):** bu slice security manifests'e dokunmaz; PSS namespace-label E-4-5 territory
- **F7 (live cluster commands):** docs/MULTI-TENANT-DEPLOYMENT.md `helm install` / `helm upgrade` / `kubectl apply` string YOK
- **F8 (pyproject):** pyproject.toml dokunulmaz
