# Epic 2 — Live Adapter Execution Infrastructure

**Status:** PROPOSED · **Parent:** V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md (Epic 2 row) · **Risk class (aggregate):** CRITICAL · **Owner:** Halil Kocoglu

> **PURPOSE.** Bu epic, real-LLM provider HTTP çağrılarının governance plane'inden geçmesini sağlayan **altyapıyı** (envelope schema + per-call audit + cost ceiling + dry-run harness + secret discipline + opt-in advisory CI workflow) inşa eder. Production-ready CLAIM **DEĞİL**.

---

## 1. Scope + Non-Goal Statement

### IN SCOPE (this epic)

- `live_adapter_envelope.v1.json` schema (request + response + cost/usage + circuit-breaker state) — `live_adapter_execution: const false` pinned.
- `per_call_audit.v1.json` schema (one record per LLM call: provider/model/tokens-in/out/cost/latency/status) — schema fails closed if `cost_*` fields missing.
- Cost ceiling enforcement module — operator-configurable per-session / per-run budget; soft-stop (warn) + hard-abort (raise).
- Dry-run harness (`scripts/run_live_adapter_dryrun.py`) — envelope is real shape, response is stub; emits evidence; **never** opens a network socket.
- Secret resolution discipline module — env-var only (CLAUDE.md değişmez #3); circuit-breaker integration; vault-stub safe path; no MCP parameter passthrough (D11).
- Opt-in CI workflow `live-adapter-evidence-emit.yml` — advisory (not required), PR-comment triggered, generates envelope evidence under dry-run.
- (Optional) Pre-supersession-PR checklist artifact for Epic 9 PR-Xfinal.

### NON-GOAL (explicit) — bu epic'te YASAK

- **`live_adapter_execution` guard flag flip.** Bu epic'in HİÇBİR slice'ı bu bayrağı `true`'ya çevirmez. Flip yalnızca Epic 9 PR-Xfinal operator-bound supersession PR'ı tarafından yapılır (farklı schema versiyonu + operator authorization + 9-boyutlu evidence matrix).
- **Real LLM provider HTTP call yapma.** Bu epic'in tüm slice'ları stub-mode + dry-run + library-mode altında çalışır. Production-grade BC-10 tarzı operator-bound bounded window dispatch yalnızca Epic 9 sonrası.
- **`support_widening` veya `production_platform_claim` flip.** Bu iki flag de bu epic'te `const false` kalır.
- **"production-ready" public claim language.** README, badge, project board kalır "v5 roadmap / planned"; final PR'a kadar değişmez (V5 roadmap §9 + Codex iter-1 invariant #8).
- **Multi-tenant cost isolation.** Tenant boyutu Epic 4 kapsamı; burada cost ceiling tek-session/tek-run scope.
- **OTEL prod tunables.** Epic 5 E-5-1 kapsamı; burada yalnızca `telemetry.span` no-op fallback kullanılır.
- **Real provider call workflow tasarımı.** BC-1 / BC-10 desenleri **referans** olarak alınır; Epic 9 operator-bound supersession kendi authority window'unu kurar.

> **Tek cümle non-goal contract:** "No slice in this epic flips the `live_adapter_execution` guard flag; the flip is gated by an operator-bound supersession PR with evidence pack + cost ceiling + safety review."

---

## 2. Slice Breakdown (7 slice — hepsi additive + opt-in + flag-preserving)

### E-2-1 — Live Adapter Envelope Schema

**Risk:** low · **Scope:** `ao_kernel/defaults/schemas/live_adapter_envelope.schema.v1.json` + `tests/test_live_adapter_envelope.py` + plan binding doc.

**Schema fields (strict closure, `additionalProperties: false` + `unevaluatedProperties: false`):**

- `schema_version` const `"live-adapter-envelope.v1"`
- `artifact_kind` const `"live_adapter_envelope"`
- `mode` enum `["stub", "dry_run"]` — `"live"` **YASAK** (Epic 9 farklı schema versiyonu)
- `live_adapter_execution` const `false` (guard flag pin — ADR-0002 recompute-not-trust)
- `request` object: `provider_id`, `model`, `request_id` (uuid), `intent`, `messages_digest` (sha256), `params` (temperature/max_tokens/...)
- `response` object: `text_digest` (sha256), `usage` (input_tokens/output_tokens/total_tokens), `latency_ms`, `status` enum `["ok", "stub_emitted", "dry_run_emitted", "error"]`
- `cost` object: `currency` enum `["USD"]`, `input_cost_per_1k_usd` (decimal string), `output_cost_per_1k_usd` (decimal string), `actual_cost_usd` (decimal string, 8 decimal places), `pricing_source_digest` (sha256:)
- `circuit_breaker` object: `state` enum `["CLOSED", "OPEN", "HALF_OPEN"]`, `failure_count`, `last_failure_at` (RFC3339 or null)
- `secret_boundary` const `"no_secret_material_emitted_no_token_no_credential"`
- `timestamps` object: `created_at`, `finalized_at`

**Codex consultation key questions:** envelope superset of BC-10 marker? envelope captures dry-run mode flag explicit? circuit-breaker state pinned per-envelope (race-free)?

### E-2-2 — Per-Call Audit Evidence

**Risk:** low · **Scope:** `ao_kernel/defaults/schemas/per_call_audit.schema.v1.json` + writer module `ao_kernel/_internal/evidence/per_call_audit.py` + tests.

**Schema fields (strict closure):**

- `schema_version` const `"per-call-audit.v1"`
- `artifact_kind` const `"per_call_audit"`
- `envelope_digest` (sha256) — bağlandığı envelope referansı
- `provider_id`, `model`, `request_id`, `intent`
- `input_tokens`, `output_tokens`, `total_tokens` (integer ≥ 0; required)
- `actual_cost_usd` (decimal string, 8 dp; **required — yokluğu = schema invalid**)
- `latency_ms` (integer ≥ 0)
- `status` enum `["ok", "error", "stub_emitted", "dry_run_emitted"]`
- `live_adapter_execution` const `false`
- `recorded_at` (RFC3339)

**Fail-closed rule:** cost field yoksa → schema validation fail → audit write REJECTED → fail-closed module raise. (CLAUDE.md değişmez #1 — fail-closed scope policy/evidence path.)

**Writer:** JSONL append-only (`evidence/per_call_audit.jsonl` workspace mode'da; library mode'da skip). Atomic write (tmp + fsync + rename — değişmez #4).

### E-2-3 — Cost Ceiling Enforcement Module

**Risk:** medium · **Scope:** `ao_kernel/_internal/cost_ceiling.py` + public facade `ao_kernel.cost.CostCeiling` + tests + ADR `ADR-0005-cost-ceiling.md`.

**API (pure module, no I/O at call sites):**

```python
class CostCeiling:
    def __init__(self, soft_usd: Decimal, hard_usd: Decimal): ...
    def record_call(self, cost_usd: Decimal) -> None: ...
    def remaining_usd(self) -> Decimal: ...
    def breach_state(self) -> Literal["ok", "soft_breached", "hard_breached"]: ...
    def assert_under_hard(self) -> None:  # raises CostCeilingExceeded
        ...
```

**Behavior:**

- **soft_usd breach** → `telemetry.span("cost.soft_breach")` + return `"soft_breached"` (continue, ama caller karar verir)
- **hard_usd breach** → `raise CostCeilingExceeded` (fail-closed)
- Decimal arithmetic ile floating-point drift YOK
- Pricing source SHA-256 ile pin'lenir (BC-10 pattern)
- Library mode'da CostCeiling instance per-call yaratılabilir; workspace mode'da ek olarak JSONL `cost_ceiling_state.jsonl` append-only.

**Configuration:**

- Policy file: `ao_kernel/defaults/policies/policy_cost_ceiling.v1.json` (operator override-able)
- Defaults: `soft_usd: "0.10000000"`, `hard_usd: "1.00000000"` (operator değiştirebilir)

### E-2-4 — Dry-Run Harness

**Risk:** low · **Scope:** `scripts/run_live_adapter_dryrun.py` + invariant tests + runbook stub.

**Behavior:**

- Reads policy + envelope schema, **emits** valid envelope artifact, **stub response** (fixed text + zero cost + status `"dry_run_emitted"`).
- Library mode by default (no `.ao/` required).
- **No network call** — runtime kill-switches active (E-2-7 invariant `no_live_network_call`).
- CLI: `python3 scripts/run_live_adapter_dryrun.py --provider openai --model gpt-4o-mini --intent FAST_TEXT --output evidence/dryrun-${ts}.envelope.v1.json`
- Output passes E-2-1 schema strict + E-2-2 per-call audit emit.
- Exit code 0 on success, 1 on schema fail, 2 on cost ceiling breach (E-2-3 integration).

### E-2-5 — Secret Resolution Discipline Module

**Risk:** medium · **Scope:** `ao_kernel/_internal/secrets/discipline.py` + tests + audit doc + ADR `ADR-0006-secret-discipline.md`.

**Contract (CLAUDE.md değişmez #3):**

- Secret = env-var-only resolution (`os.environ`).
- MCP parametre olarak secret YASAK (D11 mevcut; bu modül enforcement).
- Log redaction: secret value asla log'a düşmez; redaction regex (`AKIA[0-9A-Z]{16}`, `sk-[A-Za-z0-9]{20,}`, `xoxb-`, `glpat-`, `gho_`, `eyJ` JWT-like) **emit öncesi** envelope/audit/log payload üzerinde çalıştırılır.
- False-positive boundary: redaction yalnızca string field'larda; integer/decimal cost field'ları üstünde **çalışmaz** (drift engelleme).
- Circuit breaker integration: secret resolution fail → CB state'i `OPEN` değişmez (secret eksikliği "provider failure" değil, "config failure"); ayrı exception sınıfı `SecretResolutionError`.
- Vault stub safe path: `vault_stub_provider.py` mevcut; bu modül onu **default fallback** olarak kullanmaz — vault yokluğu → `SecretResolutionError` (fail-closed).
- Hot-reload: secret rotation runtime'da `discipline.invalidate(provider_id)` ile cache temizlenir; eski secret cache'te kalmaz.

### E-2-6 — Opt-In Live Adapter Evidence CI Workflow

**Risk:** low · **Scope:** `.github/workflows/live-adapter-evidence-emit.yml` + scripts/`live_adapter_evidence_workflow_runner.py`.

**Trigger:** `pull_request_target.types: [labeled]` — yalnızca `live-adapter-evidence` label eklendiğinde + `workflow_dispatch` (manuel test).

**Behavior:**

- **Advisory** (not required check) — branch protection ruleset'inde required değil.
- Library mode dry-run harness'ı (E-2-4) koşar.
- Envelope + per-call audit artifact'ları PR comment'e attach (collapsible markdown).
- Provider HTTP call **YOK** — `no_live_network_call` invariant runtime kill-switches aktif (socket / urllib / requests / httpx / http.client / subprocess raise on call).
- `live_adapter_execution: false` envelope içinde + workflow yorum içinde + audit içinde — 3 yerde pin (recompute audit).

**Permissions:** `contents: read` only. No secrets injected. No `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` env scope.

**Teams notification:** Workflow başarısız olursa Microsoft Teams Power Automate webhook'una alert (E-2 §9). Slack workflow YOK (HARD RULE 2026-05-27 — bizim için Slack yok; multi-tenant gelecek için runbook'ta dormant snippet).

### E-2-7 — Pre-Supersession-PR Checklist (artifact only)

**Risk:** low · **Scope:** `.claude/plans/EPIC-9-PR-Xfinal-PRE-SUPERSESSION-CHECKLIST.md` (stub doc) + `ao_kernel/defaults/schemas/pre_supersession_checklist.schema.v1.json`.

**Purpose:** Epic 9 PR-Xfinal'in flag flip'i meşru sayması için zorunlu **dokuz koşul** listesi. Bu epic bu dokümanı **yazar**, ama Epic 9 PR-X final onu **kullanır**.

**Zorunlu evidence sıralaması** (Epic 9 PR-Xfinal squash mesajında pin'lenir):

1. Operator authority block (explicit "I authorize the `live_adapter_execution=true` flip" — PR commit/comment)
2. Cross-AI consensus 2-way minimum: Codex (OpenAI) + Mavis (MiniMax) ayrı sağlayıcı (ADR-0004 + HARD RULE Cross-AI Peer Review)
3. 7-day live test window: bounded operator dispatch (BC-10 pattern), per-call audit aggregate, cost evidence pinned
4. Cost ceiling enforced + breach evidence + rollback path (cumulative_cost_usd_after ≤ ceiling proof; soft/hard breach handling proven)
5. All required CI green (no advisory red either — HARD RULE CI Kırmızıyken Merge YASAK)
6. Public claim language sync (badge update + README + project board) — deferred until flip confirmed
7. Operator-bound rollback procedure: tag revert path documented, pause workflow ready
8. Secret rotation completion (her provider için fresh API key + audit log)
9. Pricing source freshness (≤ 30 gün; operator-pinned snapshot SHA-256 in supersession entry)

---

## 3. Risk Class Per Slice

| Slice | Bireysel risk | Sebep |
|---|---|---|
| E-2-1 Envelope schema | low | Schema-only; const-pinned; runtime mutation YOK |
| E-2-2 Per-call audit | low | Append-only writer; fail-closed cost field requirement; library/workspace mode safe |
| E-2-3 Cost ceiling | medium | Decimal arithmetic + breach semantics; soft vs hard yanlış konfig riski |
| E-2-4 Dry-run harness | low | Library mode + kill-switch invariants; envelope schema garantili |
| E-2-5 Secret discipline | medium | Redaction regex false-negative riski; vault fallback semantics; cross-cutting impact |
| E-2-6 CI workflow | low | Advisory + opt-in label trigger; secret scope YOK |
| E-2-7 Pre-supersession checklist | low | Doc + schema; runtime impact YOK |

**Epic-aggregate risk = CRITICAL.** Sebep: bu slice'lar Epic 9 PR-Xfinal flag flip'inin runway'idir. Bireysel slice low/medium ama epic toplamı flip authority'sine giden köprü — bu yüzden cross-AI consensus disiplini Epic 6 (security) seviyesinde sıkı tutulur.

---

## 4. Cross-AI Consensus Protocol

ADR-0004 + HARD RULE Cross-AI Peer Review (2026-05-05) uygulaması. Implementer ≠ reviewer **sağlayıcı seviyesinde** (Anthropic ≠ OpenAI ≠ MiniMax). Aynı sağlayıcının farklı session/thread/subagent reviewer olamaz.

| Slice | Implementer | Reviewer(lar) | Consensus tipi |
|---|---|---|---|
| E-2-1 Envelope schema | Claude (Anthropic) | **Codex + Mavis** (3-way) | Schema authority — 2 reviewer zorunlu |
| E-2-2 Per-call audit | Claude (Anthropic) | Codex (OpenAI) | 2-way |
| E-2-3 Cost ceiling | Claude (Anthropic) | Codex (OpenAI) | 2-way |
| E-2-4 Dry-run harness | Claude (Anthropic) | Codex (OpenAI) | 2-way |
| E-2-5 Secret discipline | Claude (Anthropic) | **Codex + Mavis** (3-way) | Security-critical |
| E-2-6 CI workflow | Claude (Anthropic) | Codex (OpenAI) | 2-way |
| E-2-7 Pre-supersession checklist | Claude (Anthropic) | Codex (OpenAI) | 2-way (Epic 9 PR-Xfinal kendi 3-way consensus'unu ayrıca çeker) |

**Verdict → aksiyon:**

- **AGREE / `ready_to_merge: true`** → normal squash merge (admin bypass YASAK — HARD RULE)
- **PARTIAL / REVISE** → fix iter + reviewer'a yeniden gönder + AGREE'ye kadar bekle
- **RED** → kullanıcıya rapor + Epic 2 sıralama gözden geçir

**Audit trail (PR squash mesajında zorunlu):**

```
Implementer: Anthropic (Claude session/thread <id>)
Reviewer:    OpenAI (Codex thread <id>)
Reviewer-2:  MiniMax (Mavis session <id>)   <-- yalnızca 3-way slice'lar
```

İki/üç provider farklı; aynı sağlayıcı = audit ihlali.

---

## 5. Guard-Flag Invariants (her slice'ta enforced)

Her slice şu 3 invariant'ı **simultaneously** korur:

1. **`live_adapter_execution: const false`** rendered output'unun her yerinde:
   - JSON schema `properties.live_adapter_execution.const = false`
   - Envelope artifact dosyasında `"live_adapter_execution": false`
   - Per-call audit JSONL satırında `"live_adapter_execution": false`
   - Workflow output / PR comment / CI log'unda **key absent** veya `false`
2. **`support_widening: const false`** — Epic 2 hiçbir slice support matrix'i genişletmez (Linux x86_64 / macOS arm64 / Python 3.11-3.13 sınırı korunur)
3. **`production_platform_claim: const false`** — Epic 2 hiçbir slice "production-ready" claim'i içermez; README/badge/project board "v5 roadmap" framing'inde kalır

**Recompute-not-trust enforcement (ADR-0002):**

Her slice'ta runtime test: artifact'ı parse et → yukarıdaki 3 key'i fiilen oku → `assert value is False`. Schema'da `const false` olması yetmez; runtime'da fiilen `False` döndüğü test edilir. Bu, schema'nın yanlış güncellenmesini veya partial render bug'ını yakalar.

**Per-slice "key absence" tests:**

Bazı render path'lerinde key'in **hiç olmaması** doğrudur (örn. CI log'unda flag bahsi olmamalı). Bu durumda test: `assert "live_adapter_execution" not in rendered_output` (regex word boundary ile). Bu test'in olmadığı slice merge edilmez.

---

## 6. Test Invariants Per Slice (minimum 7 per slice)

Her slice şu 7 invariant kategorisinde **en az bir** test içerir:

### inv-1: `no_guard_flip` (key absence + recompute)

- Artifact parse → 3 guard flag'in her birinin `False` olduğu doğrulanır
- Schema reload → `const False` korunduğu doğrulanır
- Workflow output'unda key absence (regex `\blive_adapter_execution\s*:\s*true\b` MUST NOT MATCH)

### inv-2: `no_live_network_call`

Runtime kill-switches per Epic 3 F3 pattern (referans). Test başlangıcında monkeypatch:

```python
def _no_net(*a, **kw): raise RuntimeError("network call attempted in dry-run/stub mode")
monkeypatch.setattr("socket.socket", _no_net)
monkeypatch.setattr("http.client.HTTPConnection.request", _no_net)
monkeypatch.setattr("urllib.request.urlopen", _no_net)
monkeypatch.setattr("requests.api.request", _no_net)  # if requests installed
monkeypatch.setattr("httpx.Client.send", _no_net)     # if httpx installed
monkeypatch.setattr("subprocess.run", _no_net)         # CLI kapsama
```

Slice run → ASSERT no RuntimeError raised. Yani: hiçbir codepath bu kill-switch'lere dokunmamış.

### inv-3: `no_secret_in_envelope`

Serialized envelope/audit/log payload regex scan:

```python
SECRET_PATTERNS = [
    r"AKIA[0-9A-Z]{16}",        # AWS access key
    r"sk-[A-Za-z0-9_\-]{20,}",   # OpenAI / Anthropic style
    r"xoxb-[A-Za-z0-9\-]{10,}",  # Slack bot token
    r"glpat-[A-Za-z0-9_\-]{20}",  # GitLab PAT
    r"gho_[A-Za-z0-9]{36}",       # GitHub OAuth
    r"eyJ[A-Za-z0-9_\-]{20,}\.",  # JWT prefix
]
for pat in SECRET_PATTERNS:
    assert not re.search(pat, payload_str), f"secret pattern {pat} leaked"
```

### inv-4: `cost_field_required`

Per-call audit emit testi: cost field'ı eksik / null / negatif → schema validation **fail** → writer raise. Pozitif: valid cost field → schema pass + JSONL append OK.

### inv-5: `circuit_breaker_state_pinned`

Envelope içinde `circuit_breaker.state` ∈ `{CLOSED, OPEN, HALF_OPEN}` + `failure_count` non-negative integer. State transition determinism: aynı input sequence → aynı state output (race-free).

### inv-6: `dry_run_only_in_epic_2`

Envelope `mode` enum **only** `["stub", "dry_run"]`. `"live"` value schema validation fail. Bu invariant Epic 9'a kadar korunur; Epic 9 PR-Xfinal yeni schema versiyonu (`live_adapter_envelope.v2.json`) ile `mode: "live"` ekler.

### inv-7: `recompute_not_trust` (ADR-0002)

Cost / usage / latency / status field'ları envelope içinden alınmaz; raw inputs'tan **yeniden hesaplanır**:

- `total_tokens = input_tokens + output_tokens` (eşit değilse audit fail)
- `actual_cost_usd = input_tokens * input_cost / 1000 + output_tokens * output_cost / 1000` (decimal arithmetic; 8 dp; pricing source SHA-256 ile pin'li)
- `latency_ms = finalized_at - created_at` (ms; negatif değer audit fail)
- `status` derive: provider_call_performed → `"ok"` / `"error"`; dry-run → `"dry_run_emitted"`; stub → `"stub_emitted"`

Her slice'ta minimum 1 recompute test (envelope'ı parse et, raw inputs'tan yeniden hesapla, eşitlik assert).

---

## 7. Schema Design Notes

### live_adapter_envelope.schema.v1.json (E-2-1)

**Strict closure (her object'te):**

```json
{
  "additionalProperties": false,
  "unevaluatedProperties": false
}
```

**Required scope (maximum closure):** Schema-driven test "every required field present in valid fixture" + "fixture without each required field fails" (parametrize one-field-removed).

**`additionalProperties: false` + `unevaluatedProperties: false` her object'te:** Codex iter'lerinde sıkça yakalanan "future field eklenince invariant kayar" bug'ını önler.

**const pinning:**

- `schema_version` → const string (v1 bumped → v2 ayrı dosya)
- `artifact_kind` → const string
- `mode` → enum 2 value (stub | dry_run) — `live` YASAK
- `live_adapter_execution` → const false
- `support_widening` (envelope opsiyonel ama eklenirse) → const false
- `production_platform_claim` (envelope opsiyonel ama eklenirse) → const false

**Decimal cost fields:**

- `actual_cost_usd`: `{"type": "string", "pattern": "^[0-9]+\\.[0-9]{8}$"}` (BC-10 pattern; 8 dp granularity gpt-4o-mini $0.00015/1k için yeterli)
- Float kabul edilmez (decimal precision drift)

**SHA-256 fields:**

- `messages_digest`, `text_digest`, `envelope_digest`: `{"type": "string", "pattern": "^[0-9a-f]{64}$"}`
- `pricing_source_digest`: `{"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}` (BC-10 prefix konvansiyonu)

**Allof / conditionals:**

- Schema-level `allOf` ile: `if mode == "stub"` then `response.status == "stub_emitted"`; `if mode == "dry_run"` then `response.status == "dry_run_emitted"`.
- `if circuit_breaker.state == "CLOSED"` then `failure_count == 0` (fail-closed invariant).

### per_call_audit.schema.v1.json (E-2-2)

Aynı strict closure + recompute pattern. Ek olarak:

- `envelope_digest` zorunlu (foreign-key) — her audit kaydı bir envelope'a bağlı
- `actual_cost_usd` **required** + pattern `^[0-9]+\.[0-9]{8}$` (cost field requirement invariant inv-4 buradan beslenir)
- JSONL append-only: writer module'da `O_APPEND | O_CREAT` flag'leri + fsync (POSIX atomic <PIPE_BUF satır boyutu için thread-safe)

### pre_supersession_checklist.schema.v1.json (E-2-7)

- `checklist` array of 9 items, her item: `{name, status: enum["unmet"|"met"], evidence_ref: uri|null, attestor: string|null}`
- `live_adapter_execution_proposed_state` const `true` (bu schema sadece Epic 9 PR-Xfinal tarafından kullanılır; flip proposal)
- `live_adapter_execution_current_state` const `false` (gözlem) — recompute-not-trust ile runtime'da fiili state ile kıyaslanır

---

## 8. Pre-Supersession-PR Gate Checklist (Epic 9 PR-Xfinal için)

E-2-7 doc + schema, Epic 9 PR-Xfinal'in flag flip'i meşru sayması için zorunlu **dokuz koşul** listesi:

1. **Operator authority block** — explicit "I authorize the `live_adapter_execution=true` flip" PR commit/comment (typo değil; exact string match enforced)
2. **Cross-AI consensus 2-way minimum** — Codex (OpenAI) + Mavis (MiniMax) ayrı sağlayıcı AGREE; her ikisi de PR comment / consultation response olarak kayıtlı
3. **7-day live test window** — bounded operator dispatch (BC-10 pattern); per-call audit aggregate; cumulative_cost_usd_after evidence dosyası; window içinde minimum N=10 real provider call
4. **Cost ceiling enforced + breach evidence + rollback path** — soft breach scenario + hard breach scenario evidence; rollback `git revert <flag-flip-commit>` doğrulandı (rehearsal)
5. **All required CI green** — `gh pr checks` zero red, zero advisory red (HARD RULE CI Kırmızıyken Merge YASAK)
6. **Public claim language sync** — README badge `production-ready` ÇIKARILMADI bu PR'a kadar; final PR'da yeni badge metni hazır; project board "Done" karta retargeted
7. **Operator-bound rollback procedure** — tag revert path documented; pause workflow ready (`gh workflow disable live-adapter-bc1-attestation` benzeri komut runbook'ta)
8. **Secret rotation completion** — her provider için fresh API key (Anthropic + OpenAI + Mavis); rotation timestamp PR'da; eski key invalidated
9. **Pricing source freshness** — operator-pinned snapshot SHA-256 ≤ 30 gün eski; pricing_source.v1.json'da `effective_from` date; bu PR'da fresh re-pin

**Bu 9 koşul birden meet olmadan Epic 9 PR-Xfinal merge edilmez. Eksik koşul → operator-bound supersession kapanır, yeni supersession entry açılır.**

---

## 9. Microsoft Teams / Slack Discipline

HARD RULE 2026-05-27 uygulaması:

- **Alert delivery default = Microsoft Teams** Power Automate workflow + Adaptive Card pattern (ADR-0027 + ADR-0029 mühürlü)
- **Slack pattern asset-preserved başka tenants için**; bizim için active webhook config YOK

### E-2-6 CI workflow notification scope

`live-adapter-evidence-emit.yml` workflow başarısız olursa (örn. schema validation fail, kill-switch raise):

- **Active path:** Vault `TEAMS_WEBHOOK_URL` env-var'a inject → workflow step'inde HTTP POST → Power Automate flow → Adaptive Card chat post
- **Dormant snippet (runbook):** RB `live-adapter-evidence-slack-reactivation-chain.md` (template) — multi-tenant Slack demand-driven reactivation için; bizim için aktif değil
- **Ayrı ExternalSecret manifest** (Teams active + Slack dormant) — tek manifest 2 required key YASAK (Ready=False chain)

### Webhook secret discipline (E-2-5 ile kesişim)

- `TEAMS_WEBHOOK_URL` env-var-only (D11 — MCP parametre değil)
- Workflow YAML'da raw webhook URL YOK; `${{ secrets.TEAMS_WEBHOOK_URL }}` syntax
- Webhook URL audit log'a düşmez (E-2-5 redaction regex `https://.*webhook` opt-in pattern olarak eklenebilir; default kapalı — false-positive engelleme)

---

## 10. Bağımlılık ve Sıralama

```
E-2-1 Envelope schema
   |
   +--> E-2-2 Per-call audit (envelope_digest foreign-key)
   |
   +--> E-2-3 Cost ceiling (audit'in cost field'ı ceiling input'u)
   |
   +--> E-2-4 Dry-run harness (envelope + audit emit)
                |
                +--> E-2-6 CI workflow (dry-run harness'ı koşar)
   
E-2-5 Secret discipline (paralel; tüm slice'lar üstüne enforced)

E-2-7 Pre-supersession checklist (paralel; doc + schema; runtime impact YOK)
```

**Önerilen merge sırası:** E-2-1 → E-2-5 (paralel) → E-2-2 → E-2-3 → E-2-4 → E-2-6 → E-2-7

**Worktree ayrımı (CLAUDE.md §17 + §19):** her slice ayrı short-lived branch + ayrı worktree (örn. `codex/epic-2-1-envelope`, `codex/epic-2-5-secret-discipline`). Stacked merge protocol §19 — alt PR merge sonrası üst PR retarget + diff doğrulama.

**Cross-slice overlap-check (ops.sh overlap-check):** E-2-2 + E-2-3 + E-2-4 birbirine bağımlı; paralel açılırsa overlap-check'te uyarı; sequential merge zorunlu.

---

## 11. Exit Criteria (Epic 2 kapanış için)

Her slice için:

- All sub-issues closed via merged PR
- Cross-AI consensus AGREE (HARD RULE; implementer ≠ reviewer provider)
- 7 invariant kategorisinin her birinde minimum 1 test
- Schema strict closure (additionalProperties:false + unevaluatedProperties:false) doğrulanmış
- Evidence ref repo'da (plan doc + schema + test fixture)
- ao-release-gate green + autonomous merge trail (bypass YOK — HARD RULE)

**Epic kapanış raporu (v5 plan doc'a entry):**

- 7/7 slice MERGED + Codex thread refs
- Aggregate cost ceiling enforcement evidence (E-2-3 + E-2-4 dry-run cost ≤ ceiling proof)
- 3 guard flag still `const false` doğrulandı (recompute audit script çıktısı)
- Epic 9 PR-Xfinal için E-2-7 checklist hazır — flip authority path açık

---

## 12. References

### CLAUDE.md sections

- §1 Bu Proje Nedir (governed AI orchestration runtime)
- §2 Değişmezler (fail-closed, evidence, secrets, atomic writes — sırasıyla #1, #2, #3, #4)
- §3 Çalışma Modları (library vs workspace)
- §6 Runtime Akışı (AoKernelClient.llm_call governed pipeline 9-step)
- §10 Streaming & Resilience (circuit breaker per-provider; StreamResult)
- §11 Telemetry (OTEL optional, no-op fallback)
- §13 Geliştirme Akışı (extras: `[llm]`, `[otel]`)
- §17 Branch Discipline (worktree-per-branch, ops.sh preflight)
- §19 Stacked PR Merge Protocol (alt PR squash YASAK; merge commit; retarget + diff doğrulama)
- §21 GPP Agent Operating Contract (gpp_status.v1.json guard flag pin format)

### Existing modules (referans, değiştirme bu epic'te değil)

- `ao_kernel/llm.py` — public facade (build_request, execute_request, normalize_response)
- `ao_kernel/_internal/prj_kernel_api/llm_transport.py` — HTTP transport + retry
- `ao_kernel/_internal/prj_kernel_api/circuit_breaker.py` — CB state machine
- `ao_kernel/_internal/prj_kernel_api/rate_limiter.py` — per-provider token bucket
- `ao_kernel/_internal/secrets/env_provider.py` — env-var resolution
- `ao_kernel/_internal/secrets/vault_stub_provider.py` — vault fallback stub
- `ao_kernel/_internal/evidence/` — JSONL writer + manifest

### Existing schemas (pattern reference)

- `ao_kernel/defaults/schemas/policy-llm-live.schema.json` — live policy gate
- `ao_kernel/defaults/schemas/ri7-8b-bc10-6c-per-call-evidence.schema.v1.json` — per-call evidence (E-2-2 pattern source)
- `ao_kernel/defaults/schemas/ri7-8b-bc10-per-call-runtime-call-marker.schema.v1.json` — runtime marker
- `ao_kernel/defaults/schemas/real-adapter-usage-cost-evidence.schema.v1.json` — aggregate
- `ao_kernel/defaults/pricing/openai_gpt_4o_mini.v1.json` — pricing source (Decimal 8 dp pattern)

### Existing workflows (pattern reference, **kopya değil**)

- `.github/workflows/bc1-protected-live-adapter-attestation.yml` — operator-bound bounded window (Epic 9 pattern source)
- `.github/workflows/bc10-real-adapter-usage-cost.yml` — secret-bearing runner + cost ceiling pre-check (Epic 9 pattern source)
- `.github/workflows/live-adapter-gate.yml` — design-only gate (referans; E-2-6 daha hafif)

### Sister epic plans

- `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md` — parent epic listesi
- `.claude/plans/RI-7.8a-LIVE-EVIDENCE-PRE-AUTHORIZATION.md` — operator pre-authorization pattern
- `.claude/plans/GP-4.2-LIVE-ADAPTER-EVIDENCE-ARTIFACT-CONTRACT.md` — evidence artifact contract precedent
- `.claude/plans/GP-4-CI-MANAGED-LIVE-ADAPTER-GATE-DESIGN.md` — CI gate design referans
- `.claude/plans/PB-5-ADAPTER-PATH-COST-EVIDENCE-COMPLETENESS.md` — cost evidence completeness pattern

### HARD RULES (global)

- HARD RULE Cross-AI Peer Review (2026-05-05) — implementer ≠ reviewer provider
- HARD RULE Admin Merge YASAK (2026-05-05) — normal squash; `--admin` flag yasak
- HARD RULE CI Kırmızıyken Merge YASAK (2026-05-17) — required + advisory red ikisi de bloklar
- HARD RULE Uzun Vadeli Kalıcı Çözüm (2026-05-27) — patch yerine root cause + adversarial review
- HARD RULE Workspace Tooling Teams Primary (2026-05-27) — Slack default önerisi YASAK
- HARD RULE No Fake Work (2026-04-25) — runtime kanıtlanmamış evidence kabul edilmez

### ADRs

- ADR-0002 recompute-not-trust — Epic 2'nin her invariant'ında runtime re-assert
- ADR-0004 cross-AI consensus distinct provider — Epic 2 her slice'ta uygulanır
- ADR-0005 cost-ceiling (bu epic E-2-3 ile inşa edilecek)
- ADR-0006 secret-discipline (bu epic E-2-5 ile inşa edilecek)

---

PLAN-READY: EPIC-2 7 slices, all flag-preserving.
