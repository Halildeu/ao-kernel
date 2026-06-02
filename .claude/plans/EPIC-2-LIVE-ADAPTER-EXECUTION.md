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
- Opt-in CI workflow `live-adapter-evidence-emit.yml` — advisory (not required); Path A default (pull_request, no secrets, artifact-only) OR Path B advanced upgrade (pull_request_target.types:[labeled] with explicit threat model + separate notify workflow); generates envelope evidence under dry-run.
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

### HARD STOP — V5 Roadmap §3 Epic 2 Amend Dependency (F7)

**Implementation slices E-2-1..E-2-7 BAŞLAYAMAZ** aşağıdaki koşul karşılanana kadar:

- **`V5-ROADMAP-EPIC-2-AMEND` ayrı work item / PR merged** — V5 roadmap §3 Epic 2 satırı şu şekilde yeniden yazılmış olmalı: _"Epic 2 — Live Adapter Execution **Infrastructure** (envelope + audit + cost ceiling + dry-run + secret discipline + opt-in advisory CI workflow + pre-supersession checklist artifact); flip gerçekleştirilmez. `live_adapter_execution` flag flip Epic 9 PR-Xfinal operator-bound supersession PR'ında yapılır."_

**Bu plan PR'ında V5 roadmap dosyası DEĞİŞTİRİLMEZ.** Roadmap amend ayrı slice + ayrı PR; bu plan PR'ı yalnız dependency'yi **DECLARE** eder.

**Doğrulama gate'i:** E-2-1 envelope schema slice'ı açılmadan önce automation veya manual check:

```bash
gh pr list --repo Halildeu/ao-kernel --state merged --search "V5-ROADMAP-EPIC-2-AMEND in:title"
# Must return ≥1 merged PR before E-2-1 work begins.
```

Bu HARD STOP CLAUDE.md HARD RULE Uzun Vadeli Kalıcı Çözüm (2026-05-27) + SSOT drift engelleme disiplini uygulamasıdır.

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
- `status` enum `["ok", "error", "stub_emitted", "dry_run_emitted"]` — **provider call lifecycle status** (NOT a breach state — F10 disambiguation)
- `cost_breach_state` enum `["ok", "soft_breached", "hard_breached", "not_applicable"]` — **separate from `status`; tracks whether this call's cost recording crossed soft/hard ceiling thresholds** (F10 absorption — Codex iter-2 disambiguation)
  - `"ok"` — call recorded under soft threshold; no breach
  - `"soft_breached"` — call recording crossed soft threshold; caller continued/stopped/deferred
  - `"hard_breached"` — call recording crossed hard threshold; module raised `CostCeilingExceeded` (see hard-breach audit-writing path below)
  - `"not_applicable"` — stub/dry-run mode where cost ceiling does not apply
- `cost_breach_handling` (object; conditionally required) — populated only when `cost_breach_state == "soft_breached"`; see "Soft breach audit contract" in E-2-3
- `live_adapter_execution` const `false`
- `recorded_at` (RFC3339)

**Schema conditional (allOf):**

```json
{
  "allOf": [
    {
      "if": { "properties": { "cost_breach_state": { "const": "soft_breached" } } },
      "then": { "required": ["cost_breach_handling"] }
    }
  ]
}
```

`cost_breach_state == "soft_breached"` → `cost_breach_handling` field zorunlu (caller decision audit).

**Hard-breach audit-writing path (F10 — explicit):**

`cost_breach_state == "hard_breached"` durumu için audit writing dar bir akış izler çünkü `record_call()` exception raise eder ve normal serialize path'i tamamlanmaz:

- Module hard breach detect ettiğinde önce **fail-closed audit row** yazar (try-finally pattern) sonra `raise CostCeilingExceeded`.
- Fail-closed audit row schema: `cost_breach_state: "hard_breached"`, `status: "error"`, `actual_cost_usd: <cost that triggered breach>`, `cost_breach_handling: null` (caller decision yok; hard breach unconditional).
- Bu satır ayrı failure artifact path'inde tutulur: workspace mode `evidence/cost_hard_breach.jsonl` + ana `per_call_audit.jsonl` ikisine de yazılır (cross-reference için).
- Library mode: in-memory log + raise; persistence yok (single-process contract).

**Fail-closed rule:** cost field yoksa → schema validation fail → audit write REJECTED → fail-closed module raise. (CLAUDE.md değişmez #1 — fail-closed scope policy/evidence path.)

**Writer:** JSONL append-only (`evidence/per_call_audit.jsonl` workspace mode'da; library mode'da skip). Atomic write (tmp + fsync + rename — değişmez #4).

### E-2-3 — Cost Ceiling Enforcement Module

**Risk:** medium · **Scope:** `ao_kernel/_internal/cost_ceiling.py` + public facade `ao_kernel.cost.CostCeiling` + tests + ADR `ADR-0005-cost-ceiling.md`.

**API (pure module, no I/O at call sites except workspace-mode lock acquire):**

```python
from decimal import Decimal
from typing import Literal

BreachState = Literal["ok", "soft_breached", "hard_breached"]

class CostCeiling:
    def __init__(self, soft_usd: Decimal, hard_usd: Decimal, *, session_id: str | None = None): ...
    def record_call(self, cost_usd: Decimal) -> BreachState:
        """Record a cost; return explicit breach state.

        Validation (fail-closed):
        - cost_usd < 0 → ValueError
        - not cost_usd.is_finite() (NaN, Inf, -Inf) → ValueError
        - cost_usd == 0 AND live-mode AND status='ok' AND tokens>0 AND price>0 → ValueError
          (zero-cost is suspicious in real provider call; allowed only in stub/dry_run)

        Concurrency:
        - workspace mode: file-lock on `cost_ledger.lock` per session (fcntl LOCK_EX)
        - library mode: single-process contract documented (no cross-process safety)

        Hard breach:
        - on hard_usd breach → raise CostCeilingExceeded (fail-closed; this method does
          NOT return on hard breach)

        Soft breach:
        - on soft_usd breach → return "soft_breached" (caller decides continue/stop;
          caller MUST record decision into per-call audit `cost_breach_handling` field)
        """
        ...
    def remaining_usd(self) -> Decimal: ...
    def breach_state(self) -> BreachState: ...
    def assert_under_hard(self) -> None:  # raises CostCeilingExceeded
        ...
    def reserve(self, estimated_usd: Decimal) -> "Reservation":
        """Pre-reservation pattern alternative for concurrent callers.

        Reserves estimated cost upfront; settle later with actual cost via
        reservation.settle(actual_usd). Prevents read-modify-write race when
        many callers race against the same ceiling concurrently.
        """
        ...
```

**Behavior:**

- **soft_usd breach** → `telemetry.span("cost.soft_breach")` + return `"soft_breached"` (caller karar verir; karar audit'e `cost_breach_handling` alanına ZORUNLU kayıt — "continued" | "stopped" | "deferred")
- **hard_usd breach** → `raise CostCeilingExceeded` (fail-closed; method return etmez)
- Decimal arithmetic ile floating-point drift YOK; tüm cost field'lar `Decimal` (8 dp granularity)
- Pricing source SHA-256 ile pin'lenir (BC-10 pattern)
- Library mode: in-memory state + **single-process contract** (module docstring'de explicit; multi-process kullanım caller sorumluluğu)
- Workspace mode: in-memory state + JSONL `cost_ceiling_state.jsonl` append-only + **file-lock on `cost_ledger.lock` per session** (fcntl LOCK_EX) — concurrent record_call atomic
- Alternative: **pre-reservation pattern** (`reserve()` + `Reservation.settle()`) — read-modify-write race'i tamamen önler

**Validation (fail-closed):**

| Input | Davranış |
|---|---|
| `cost_usd < 0` | `raise ValueError("cost_usd must be non-negative")` |
| `cost_usd.is_nan() or not cost_usd.is_finite()` | `raise ValueError("cost_usd must be finite")` |
| `cost_usd == 0` AND live-mode AND status=`"ok"` AND tokens>0 AND price>0 | `raise ValueError("zero-cost suspicious in real provider call")` |
| `cost_usd == 0` AND mode ∈ {"stub", "dry_run"} | OK (zero-cost expected) |

**Audit-write contract (soft breach handling):**

Soft breach durumunda caller mutlaka per-call audit kaydında **iki alan** doldurur (F10 disambiguation — `status` provider call lifecycle için, `cost_breach_state` breach durumu için):

```json
{
  "status": "ok",
  "cost_breach_state": "soft_breached",
  "cost_breach_handling": {
    "decision": "continued" | "stopped" | "deferred",
    "decided_by": "operator" | "policy_default" | "caller_module",
    "decided_at": "RFC3339"
  }
}
```

Per-call audit schema (E-2-2) bu alanı `if cost_breach_state == "soft_breached" then cost_breach_handling required` allOf koşulu ile zorunlu kılar. `status` field'ı provider call lifecycle (`ok`/`error`/`stub_emitted`/`dry_run_emitted`) için; `cost_breach_state` cost ceiling breach durumu için — iki ayrı boyut, ayrı enum.

Hard breach audit-write (yukarıda E-2-2 §"Hard-breach audit-writing path" detayında): `cost_breach_state: "hard_breached"`, `status: "error"`, `cost_breach_handling: null`. Bu satır hem ana audit JSONL hem ayrı `cost_hard_breach.jsonl` failure artifact'ına yazılır.

**Configuration:**

- Policy file: `ao_kernel/defaults/policies/policy_cost_ceiling.v1.json` (operator override-able)
- Defaults: `soft_usd: "0.10000000"`, `hard_usd: "1.00000000"` (operator değiştirebilir)

### E-2-4 — Dry-Run Harness

**Risk:** medium (revised from low; F4 absorption) · **Scope:** `scripts/run_live_adapter_dryrun.py` + invariant tests + runbook stub + `tests/test_dryrun_killswitch_bypass.py`.

**Behavior:**

- Reads policy + envelope schema, **emits** valid envelope artifact, **stub response** (fixed text + zero cost + status `"dry_run_emitted"`).
- Library mode by default (no `.ao/` required).
- **No network call** — comprehensive runtime kill-switches active (see "Kill-switch coverage" below).
- CLI: `python3 scripts/run_live_adapter_dryrun.py --provider openai --model gpt-4o-mini --intent FAST_TEXT --output evidence/dryrun-${ts}.envelope.v1.json`
- Output passes E-2-1 schema strict + E-2-2 per-call audit emit.
- Exit code 0 on success, 1 on schema fail, 2 on cost ceiling breach (E-2-3 integration).

**Kill-switch coverage (F4 — comprehensive bypass prevention):**

Tüm aşağıdaki bypass path'leri kapatılır (test ile kanıtlanır):

| Kategori | Patched targets |
|---|---|
| **Raw socket** | `socket.socket`, `socket.create_connection`, `socket.socket.connect` |
| **subprocess (full family)** | `subprocess.Popen.__init__`, `subprocess.run`, `subprocess.call`, `subprocess.check_output`, `subprocess.check_call` |
| **os shell exec** | `os.system`, `os.popen`, `os.spawnv*` family |
| **httpx (sync + async)** | `httpx.Client.send`, `httpx.AsyncClient.send`, `httpx.stream` |
| **urllib stack** | `urllib.request.urlopen`, `urllib3.connectionpool.HTTPConnectionPool._make_request` |
| **requests** | `requests.api.request` (if installed) |
| **aiohttp** | `aiohttp.ClientSession._request` (if installed) |
| **http.client** | `http.client.HTTPConnection.request`, `http.client.HTTPSConnection.request` |
| **Native libs (static denylist)** | `ctypes.CDLL("libcurl")` reject; `cffi.FFI` usage scan in imports |

**Bypass fixture tests (`test_dryrun_killswitch_bypass.py`):**

Her kill-switch için ayrı negative test — bypass denemesi yapılır, exception raise edilmesi assert edilir:

```python
@pytest.mark.parametrize("bypass_attempt", [
    lambda: socket.create_connection(("1.1.1.1", 80)),
    lambda: subprocess.Popen(["curl", "https://example.com"]),
    lambda: subprocess.check_output(["wget", "https://example.com"]),
    lambda: os.system("curl https://example.com"),
    lambda: os.popen("wget https://example.com"),
    lambda: httpx.Client().send(httpx.Request("GET", "https://example.com")),
    # ... (full list per table above)
])
def test_killswitch_blocks_bypass(install_killswitches, bypass_attempt):
    with pytest.raises(RuntimeError, match="network call attempted"):
        bypass_attempt()
```

**Static import scan:**

`tests/test_dryrun_import_denylist.py` AST-based scan: dry-run harness import graph'ında `ctypes.CDLL("libcurl")` veya `cffi.FFI()` çağrısı bulursa fail. Bu native-lib bypass'ını commit-time'da yakalar.

### E-2-5 — Secret Resolution Discipline Module

**Risk:** medium · **Scope:** `ao_kernel/_internal/secrets/discipline.py` + `ao_kernel/_internal/secrets/taint.py` + tests + audit doc + ADR `ADR-0006-secret-discipline.md`.

**Primary invariant (F5 — value-based taint tracking):**

> "**Resolve edilen secret değeri serialized output'ta GÖRÜNMEZ.**"

Regex redaction **defense-in-depth**'tir (false-negative riski); primary mekanizma value-based taint set:

```python
class SecretTaintSet:
    """In-memory set of resolved secret values; checked before any serialization."""

    def add(self, provider_id: str, value: str) -> None: ...
    def scan_and_redact(self, payload: str | dict | list) -> str | dict | list:
        """Walk payload recursively; replace any taint value with [REDACTED:provider=X]."""
        ...
    def contains(self, value: str) -> bool: ...
```

**Serialization pipeline (mandatory):**

```
LLM call → response normalize → envelope build → SecretTaintSet.scan_and_redact() → JSONL write
                                                  per-call audit ─┘
                                                  log line ──────┘
                                                  telemetry span ┘
```

Hiçbir serialized output `scan_and_redact()` çağrısı OLMADAN diske / log'a / telemetry'ye gitmez. Lint rule + test enforce.

**Contract (CLAUDE.md değişmez #3):**

- Secret = env-var-only resolution (`os.environ`).
- MCP parametre olarak secret YASAK (D11 mevcut; bu modül enforcement).
- **Taint tracking (PRIMARY):** secret resolve edildiği an `taint_set.add(provider_id, value)`. Sonraki tüm serialize işlemleri `scan_and_redact()` üzerinden geçer.
- **Regex redaction (DEFENSE-IN-DEPTH):** taint set'in yakalayamayacağı durumlar için (örn. external library log'u, third-party hata mesajı) regex pattern set:
  - `AKIA[0-9A-Z]{16}` (AWS access key)
  - `sk-[A-Za-z0-9_\-]{20,}` (generic sk- prefix)
  - `sk-ant-[A-Za-z0-9_\-]{20,}` (Anthropic)
  - `sk-proj-[A-Za-z0-9_\-]{20,}` (OpenAI project key)
  - `xoxb-[A-Za-z0-9\-]{10,}` (Slack bot token)
  - `glpat-[A-Za-z0-9_\-]{20}` (GitLab PAT)
  - `gho_[A-Za-z0-9]{36}` (GitHub OAuth)
  - `ghp_[A-Za-z0-9]{36}` (GitHub PAT classic)
  - `github_pat_[A-Za-z0-9_]{82}` (GitHub fine-grained PAT)
  - `ghs_[A-Za-z0-9]{36}` (GitHub server token)
  - `ghu_[A-Za-z0-9]{36}` (GitHub user-to-server token)
  - `eyJ[A-Za-z0-9_\-]{20,}\.` (JWT prefix)
  - `https://[a-z0-9.\-]+\.webhook\.office\.com/webhookb2/[A-Za-z0-9@/\-]+` (Teams webhook URL)
- False-positive boundary: redaction yalnızca string field'larda; integer/decimal cost field'ları üstünde **çalışmaz** (drift engelleme).
- Circuit breaker integration: secret resolution fail → CB state'i `OPEN` değişmez (secret eksikliği "provider failure" değil, "config failure"); ayrı exception sınıfı `SecretResolutionError`.
- Vault stub safe path: `vault_stub_provider.py` mevcut; bu modül onu **default fallback** olarak kullanmaz — vault yokluğu → `SecretResolutionError` (fail-closed).
- Hot-reload: secret rotation runtime'da `discipline.invalidate(provider_id)` ile cache + taint set temizlenir; eski secret cache/taint'te kalmaz.

**Test invariants (E-2-5):**

1. **Taint absence test (PRIMARY):** mock `taint_set.add("openai", "sk-test-12345...")` → call full pipeline (envelope build + audit write + log emit) → assert string `"sk-test-12345..."` not in any serialized output.
2. **Regex defense test (SECONDARY):** her regex pattern için negative+positive case: pattern matched → redacted; non-matching string → unchanged.
3. **Serialization gate test:** every serialize call path (envelope, audit, log, telemetry) MUST go through `scan_and_redact()` — AST-based test scans codepaths and fails if any direct `json.dumps` / `open().write` bypasses redaction.

### E-2-6 — Opt-In Live Adapter Evidence CI Workflow

**Risk:** medium (revised from low; F2 absorption) · **Scope:** `.github/workflows/live-adapter-evidence-emit.yml` + `.github/workflows/live-adapter-evidence-notify.yml` (separate trusted notify workflow if Path B chosen) + scripts/`live_adapter_evidence_workflow_runner.py`.

#### Path A (DEFAULT — recommended, safer)

**Trigger:** `pull_request` (NOT `pull_request_target`) + `workflow_dispatch` (manual test).

**Behavior:**

- **Advisory** (not required check) — branch protection ruleset'inde required değil.
- Library mode dry-run harness'ı (E-2-4) koşar.
- Envelope + per-call audit **artifact-only output** — `actions/upload-artifact` ile workflow artifact olarak yayımlanır.
- **PR comment write YOK** — reviewer artifact'ı PR Checks UI'dan indirir.
- **No secrets injected** — `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `TEAMS_WEBHOOK_URL` workflow env scope'unda YOK.
- **Teams notification YOK Path A'da** — secret gerektirir; failure görünürlüğü PR Checks status'unda.
- Provider HTTP call **YOK** — comprehensive kill-switches aktif (E-2-4 listesi).
- `live_adapter_execution: false` envelope + audit içinde — 2 yerde pin (recompute audit).

**Permissions:**

```yaml
permissions:
  contents: read
  # NO pull-requests: write (PR comment yok)
  # NO actions: write
  # NO id-token: write
  # NO secrets: ... (env scope YOK)
```

**Trigger semantics:** `pull_request` head SHA'sından code çalıştırır; bu güvenlidir çünkü secret YOK ve write permission YOK. Worst-case attacker: malicious PR + dry-run harness'ı çalıştırır + artifact'ı upload eder. Hiçbir secret leak edemez, hiçbir write işlemi yapamaz.

#### Path B (ADVANCED — explicit upgrade with own threat model)

Path B yalnızca aşağıdaki koşullardan biri zorunluysa açılır:

- Label-based trigger gerek (PR'a `live-adapter-evidence` label eklendiğinde tetiklenir)
- PR comment write gerek (reviewer artifact indirmek yerine inline gormek isterse)
- Teams notification gerek (failure'da operator chat post)

**Path B threat model (separate dedicated section required in workflow YAML comment header):**

```yaml
# THREAT MODEL — pull_request_target.types: [labeled]
# 1. Trigger: pull_request_target fires on label add (NOT on PR push); secret-bearing.
# 2. Trusted actor check: first step asserts label-add actor IN {Halildeu};
#    untrusted actor → exit 0 (no-op).
# 3. Base-only checkout: actions/checkout@v4 with ref=${{ github.event.pull_request.base.sha }}
#    NEVER ref=${{ github.event.pull_request.head.sha }}; HEAD code is UNTRUSTED.
# 4. No head code execution: pip install -e . disallowed; only invoke base-branch scripts.
# 5. Minimal write permission: contents: read + actions: write (artifact only); NO pull-requests: write
#    in PR-triggered workflow. PR comment write moved to separate workflow_run workflow.
# 6. Teams notification: SEPARATE workflow `live-adapter-evidence-notify.yml` triggered by
#    workflow_run completion event; runs on `main` (trusted code path); Teams secret accessed here.
# 7. Secret scope: TEAMS_WEBHOOK_URL exposed ONLY in notify workflow, NEVER in PR-triggered workflow.
# 8. Label authorization: label add by non-trusted actor immediately removes label + comments warning.
```

**Trigger (Path B):**

```yaml
on:
  pull_request_target:
    types: [labeled]
    branches: [main]
  workflow_dispatch:

jobs:
  emit-evidence:
    if: github.event.label.name == 'live-adapter-evidence' && github.event.sender.login == 'Halildeu'
    permissions:
      contents: read
      actions: write   # artifact upload only
      pull-requests: read   # explicitly NOT write
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.base.sha }}   # BASE only, never HEAD
      - run: python3 scripts/run_live_adapter_dryrun.py ...
      - uses: actions/upload-artifact@v4
```

**Separate notify workflow (Path B):**

```yaml
# live-adapter-evidence-notify.yml — runs on main (trusted code), secret-bearing
name: live-adapter-evidence-notify
on:
  workflow_run:
    workflows: [live-adapter-evidence-emit]
    types: [completed]

jobs:
  notify-on-failure:
    if: ${{ github.event.workflow_run.conclusion == 'failure' }}
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - run: curl -X POST -H "Content-Type: application/json" -d @payload.json ${{ secrets.TEAMS_WEBHOOK_URL }}
```

**Default choice for this epic:** Path A. Path B aktivasyonu ayrı PR + ayrı threat model review + Codex 3-way consensus (§4 protocol update).

### E-2-7 — Pre-Supersession-PR Checklist (artifact only)

**Risk:** low · **Scope:** `.claude/plans/EPIC-9-PR-Xfinal-PRE-SUPERSESSION-CHECKLIST.md` (stub doc) + `ao_kernel/defaults/schemas/pre_supersession_checklist.schema.v1.json`.

**Purpose:** Epic 9 PR-Xfinal'in flag flip'i meşru sayması için zorunlu **on sekiz koşul** listesi (F6 extension). Bu epic bu dokümanı **yazar**, ama Epic 9 PR-Xfinal onu **kullanır**.

**`proposed_state` field namespacing (F6 — anti-drift):**

E-2-7 schema'sında **`live_adapter_execution_proposed_state` const true DİREKT ROOT'TA TAŞINMAZ.** İki çözüm seçeneği:

- **Option A (recommended):** Field tamamen Epic 9 supersession schema'sına TAŞINIR. E-2-7 schema'sı sadece koşul listesini içerir; flip proposal Epic 9 PR-Xfinal'in kendi schema'sında belirir.
- **Option B (compromise):** Field strict namespace altında `epic_9_proposal_only.live_adapter_execution_proposed_state: const true` (explicit comment field: `"_comment": "this field is consumed ONLY by Epic 9 PR-Xfinal validator; Epic 2 scanners ignore this namespace"`).

**Default choice:** Option A — Epic 2 artifact `live_adapter_execution_proposed_state` field'ını HİÇ TAŞIMAZ. Bu, no-guard-flip scanner'ın Epic 2 artifact'larında `live_adapter_execution: true` literal'ını ASLA görmemesini garanti eder.

**Zorunlu evidence sıralaması (18 koşul; Epic 9 PR-Xfinal squash mesajında pin'lenir):**

1. **Operator authority block** — explicit "I authorize the `live_adapter_execution=true` flip" PR commit/comment (exact string match)
2. **Cross-AI consensus 2-way minimum** — Codex (OpenAI) + Mavis (MiniMax) ayrı sağlayıcı AGREE
3. **7-day live test window** — bounded operator dispatch (BC-10 pattern), per-call audit aggregate, cost evidence pinned
4. **Cost ceiling enforced + breach evidence + rollback path** — soft/hard breach handling proven
5. **All required CI green** — no advisory red either (HARD RULE CI Kırmızıyken Merge YASAK)
6. **Public claim language sync** — badge/README/project board: deferred until flip confirmed
7. **Operator-bound rollback procedure** — tag revert path documented, pause workflow ready
8. **Secret rotation completion** — her provider için fresh API key + audit log
9. **Pricing source freshness** — ≤30 gün, operator-pinned snapshot SHA-256
10. **Workflow content SHA pin + base SHA + head SHA** — supersession PR'da kullanılan tüm workflow YAML'larının content hash'i ve trigger commit base/head SHA'ları squash mesajında ve evidence artifact'ında pin'li
11. **Protected environment reviewer proof** — GitHub Environment `live-adapter-flip` protected reviewer (Halildeu) approval evidence; environment secret scope listesi
12. **Provider/model allowlist** — flip sırasında kullanılabilecek provider+model çiftleri explicit allowlist; allowlist dışı çağrı fail-closed
13. **Provider SLA/ToS/data-retention/region policy proof** — her allowlisted provider için: SLA URL + ToS URL + data-retention policy + data-region (EU/US) snapshot SHA-256
14. **Budget overrun → auto-create follow-up issue** — hard breach OR cumulative cost > 80% ceiling tetiklediğinde GitHub Actions otomatik issue açar (template: `live-adapter-budget-overrun.yml`)
15. **Branch-protection ruleset source-pin drift check** — supersession PR merge öncesi ruleset SHA-256 alındı + post-merge drift check passes
16. **Required-check name/source collision check** — yeni required check ismi mevcut check listesi ile çakışmıyor; supersession sonrası check name unique
17. **Post-window deauthorization + secret scope removal** — 7-day window bittiğinde otomatik deauth workflow (operator authority block expires; secret env scope removed)
18. **Audit retention + tamper evidence** — per-call audit JSONL en az 90 gün retain; her satır SHA-256 chain ile linked (önceki satır digest = sonraki satır prev_digest); tamper detect script `verify_audit_chain.py`

**Bu 18 koşul birden meet olmadan Epic 9 PR-Xfinal merge edilmez. Eksik koşul → operator-bound supersession kapanır, yeni supersession entry açılır.**

---

## 3. Risk Class Per Slice

| Slice | Bireysel risk | Sebep |
|---|---|---|
| E-2-1 Envelope schema | low | Schema-only; const-pinned; runtime mutation YOK |
| E-2-2 Per-call audit | low | Append-only writer; fail-closed cost field requirement; library/workspace mode safe |
| E-2-3 Cost ceiling | medium | Decimal arithmetic + breach semantics; soft vs hard yanlış konfig riski; concurrent record_call atomicity |
| **E-2-4 Dry-run harness** | **medium** (F4 absorption — F11 alignment) | Comprehensive kill-switch coverage zorunlu (socket / subprocess full family / os.system+popen / httpx async / urllib3 / aiohttp / ctypes/cffi); bypass fixture tests + AST import scan |
| E-2-5 Secret discipline | medium | Value-based taint primary; regex defense-in-depth; cross-cutting impact tüm serialize path'lerine |
| **E-2-6 CI workflow (Path A default)** | **medium** (F2 absorption — F11 alignment) | Even Path A advisory: pull_request trigger semantics + artifact upload + no PR comment write disiplini; Path B upgrade additional risk (pull_request_target + secret + trusted-actor) — ayrı 3-way review |
| E-2-7 Pre-supersession checklist | low | Doc + 18-condition schema; runtime impact YOK; Epic 9 PR-Xfinal authority window spec'i |

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
| E-2-6 CI workflow (Path A) | Claude (Anthropic) | Codex (OpenAI) | 2-way (no secrets, no write permission, no pull_request_target) |
| E-2-6 CI workflow (Path B upgrade) | Claude (Anthropic) | **Codex + Mavis** (3-way) | Security-critical: `pull_request_target` OR secrets-injected OR write permission |
| E-2-7 Pre-supersession checklist | Claude (Anthropic) | **Codex + Mavis** (3-way) | Critical flip-gate spec; Epic 9 PR-Xfinal authority window defined here |

**F8 absorption — 3-way consensus condition matrix:**

E-2-6 default Path A → 2-way. **Path B trigger conditions** (3-way required if any TRUE):

| Condition | If TRUE → 3-way required |
|---|---|
| Trigger contains `pull_request_target` | YES |
| Any secret injected into workflow env | YES |
| Workflow permission includes `pull-requests: write` OR `contents: write` OR `id-token: write` | YES |
| Trigger label-based with non-owner authorization | YES (extra: explicit threat model section) |
| Workflow callable from external PR head SHA without trusted-actor gate | YES |

E-2-7 → 3-way **always** (flip-gate spec is critical; single-reviewer blind spot unacceptable).

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

### inv-2: `no_live_network_call` (baseline; full matrix in inv-8)

Baseline kill-switches per Epic 3 F3 pattern (referans). Bu invariant **baseline coverage**'dır; **comprehensive bypass matrix inv-8 altındadır** (F11 alignment — Codex iter-2). E-2-4 dry-run harness slice'ı inv-8'i ZORUNLU içerir; diğer slice'lar minimum inv-2 baseline ile yetinebilir.

Test başlangıcında monkeypatch:

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

**Full bypass matrix:** inv-8 (`killswitch_bypass_negative_tests`) — E-2-4 zorunlu; subprocess full family + os.system+popen + httpx async + urllib3 + aiohttp + ctypes/cffi/libcurl static denylist + bypass fixture tests.

### inv-3: `no_secret_in_envelope` (regex defense-in-depth; primary invariant in inv-9)

Bu invariant **defense-in-depth** kategorisindedir; **primary value-based taint absence invariant inv-9 altındadır** (F11 alignment — Codex iter-2). E-2-5 secret discipline slice'ı inv-9'u ZORUNLU içerir (primary); diğer slice'lar inv-3 regex baseline ile defense-in-depth ekler.

Serialized envelope/audit/log payload regex scan (extended pattern set — full list E-2-5 §"Regex redaction" altında; özet:):

```python
SECRET_PATTERNS = [
    r"AKIA[0-9A-Z]{16}",                            # AWS access key
    r"sk-[A-Za-z0-9_\-]{20,}",                       # generic sk- prefix
    r"sk-ant-[A-Za-z0-9_\-]{20,}",                   # Anthropic
    r"sk-proj-[A-Za-z0-9_\-]{20,}",                  # OpenAI project key
    r"xoxb-[A-Za-z0-9\-]{10,}",                     # Slack bot token
    r"glpat-[A-Za-z0-9_\-]{20}",                     # GitLab PAT
    r"gho_[A-Za-z0-9]{36}",                          # GitHub OAuth
    r"ghp_[A-Za-z0-9]{36}",                          # GitHub PAT classic
    r"github_pat_[A-Za-z0-9_]{82}",                  # GitHub fine-grained PAT
    r"ghs_[A-Za-z0-9]{36}",                          # GitHub server token
    r"ghu_[A-Za-z0-9]{36}",                          # GitHub user-to-server token
    r"eyJ[A-Za-z0-9_\-]{20,}\.",                     # JWT prefix
    r"https://[a-z0-9.\-]+\.webhook\.office\.com/webhookb2/[A-Za-z0-9@/\-]+",  # Teams webhook URL
]
for pat in SECRET_PATTERNS:
    assert not re.search(pat, payload_str), f"secret pattern {pat} leaked"
```

**Primary invariant:** inv-9 (`value_based_taint_absence`) — E-2-5 zorunlu; resolved secret value asla serialized output'ta görünmez.

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

### inv-8: `killswitch_bypass_negative_tests` (F4 — E-2-4)

Her kill-switch path için bypass denemesi yapılır + RuntimeError raise edilmesi assert edilir (full list E-2-4 §"Kill-switch coverage" tablosunda). Parametrize fixture; her hatlı bypass için ayrı test (socket / subprocess full family / os.system+popen / httpx sync+async / urllib3 / requests / aiohttp / http.client). Plus AST import scan: `ctypes.CDLL("libcurl")` ve `cffi.FFI` import edilmiyor.

### inv-9: `value_based_taint_absence` (F5 — E-2-5)

Primary invariant. Test pattern:

```python
def test_taint_value_absent_in_serialized_output(monkeypatch, tmp_path):
    test_secret = "sk-test-FAKE-VALUE-FOR-TAINT-12345"
    monkeypatch.setenv("OPENAI_API_KEY", test_secret)

    # Trigger full pipeline (envelope build + audit write + log emit)
    discipline = SecretResolutionDiscipline()
    secret = discipline.resolve("openai")
    envelope = build_envelope(provider="openai", ...)
    audit_path = tmp_path / "audit.jsonl"
    write_audit(envelope, audit_path)

    # Assert taint value absent in EVERY serialized surface
    audit_text = audit_path.read_text()
    assert test_secret not in audit_text
    assert test_secret not in json.dumps(envelope)
    # If logging captured: assert test_secret not in caplog.text
```

Bonus: each regex pattern test (positive + negative) — `tests/test_secret_redaction_regex.py` parametrize.

### inv-10: `cost_ceiling_concurrency_safe` (F3 — E-2-3)

Workspace mode concurrent record_call atomic test:

```python
def test_cost_ceiling_concurrent_record_call_atomic(tmp_path):
    ceiling = CostCeiling(soft_usd=Decimal("0.05"), hard_usd=Decimal("1.00"), session_id="test-sess")

    def worker():
        try:
            ceiling.record_call(Decimal("0.01000000"))
        except CostCeilingExceeded:
            pass

    threads = [threading.Thread(target=worker) for _ in range(100)]
    for t in threads: t.start()
    for t in threads: t.join()

    # 100 calls × $0.01 = $1.00; should hit hard breach
    # Total recorded must equal sum of accepted calls (no double-count, no lost update)
    assert ceiling.total_recorded_usd() <= Decimal("1.00")
```

Bonus: validation tests for negative / NaN / Inf / suspicious-zero inputs (each raises ValueError).

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

- `checklist` array of **18 items** (F6 extension), her item: `{name, status: enum["unmet"|"met"], evidence_ref: uri|null, attestor: string|null}`
- **`live_adapter_execution_current_state` const `false`** (gözlem) — recompute-not-trust ile runtime'da fiili state ile kıyaslanır
- **`live_adapter_execution_proposed_state` field DEĞİL** — Option A applied: bu field Epic 9 supersession schema'sına taşındı. Epic 2 artifact'ı `proposed_state: true` literal'ını ASLA içermez. No-guard-flip scanner Epic 2 artifact'larında `live_adapter_execution: true` ile karşılaşmaz. (F6 absorption.)
- Epic 9 supersession schema (ayrı dosya `epic_9_supersession_proposal.schema.v1.json`) `live_adapter_execution_proposed_state: const true` taşır; Epic 9 PR-Xfinal validator bu schema'yı kullanır; Epic 2 scanner'lar bu schema'yı IGNORE eder.

---

## 8. Pre-Supersession-PR Gate Checklist (Epic 9 PR-Xfinal için)

E-2-7 doc + schema, Epic 9 PR-Xfinal'in flag flip'i meşru sayması için zorunlu **on sekiz koşul** (F6 absorption — extended from 9 to 18). Tam liste E-2-7 slice tanımında ve `pre_supersession_checklist.schema.v1.json` items array'inde tek yerde yaşar; bu §8 onların SSOT mirror'ıdır:

| # | Koşul | Evidence ref türü |
|---|---|---|
| 1 | Operator authority block (exact string match) | PR commit/comment text |
| 2 | Cross-AI consensus 2-way minimum (Codex + Mavis ayrı provider AGREE) | Codex thread + Mavis session refs |
| 3 | 7-day live test window (bounded operator dispatch, ≥10 real calls) | Per-call audit JSONL aggregate |
| 4 | Cost ceiling enforced + soft/hard breach evidence + rollback rehearsal | Cost ceiling state JSONL + revert dry-run log |
| 5 | All required CI green (advisory red dahil zero) | `gh pr checks` snapshot |
| 6 | Public claim language sync (badge/README/project board ÇIKARILMADI bu PR'a kadar) | Diff inspection |
| 7 | Operator-bound rollback procedure (tag revert + pause workflow ready) | Runbook MD + workflow disable command snippet |
| 8 | Secret rotation completion (her provider fresh API key + audit) | Rotation timestamp ledger + revoke audit |
| 9 | Pricing source freshness (≤30 gün, snapshot SHA-256 pin) | pricing_source.v1.json `effective_from` date |
| 10 | **Workflow content SHA + base SHA + head SHA pin** (F6 add) | Squash mesajı + evidence artifact `workflow_sha_pin` field |
| 11 | **Protected environment reviewer proof** (GitHub Environment `live-adapter-flip` approval) | GitHub Environment approval log |
| 12 | **Provider/model allowlist** (flip sırasında kullanılabilecek çiftler) | Allowlist JSON + fail-closed test |
| 13 | **Provider SLA/ToS/data-retention/region policy proof** | Per-provider URL + snapshot SHA-256 |
| 14 | **Budget overrun → auto-create follow-up issue** (workflow template) | `.github/workflows/live-adapter-budget-overrun.yml` exists + smoke run |
| 15 | **Branch-protection ruleset source-pin drift check** | Pre+post SHA-256 comparison |
| 16 | **Required-check name/source collision check** | Check listing diff |
| 17 | **Post-window deauthorization + secret scope removal** (otomatik 7-day deauth) | Deauth workflow log + scope diff |
| 18 | **Audit retention + tamper evidence** (≥90 gün + SHA-256 chain) | `verify_audit_chain.py` output |

**Bu 18 koşul birden meet olmadan Epic 9 PR-Xfinal merge edilmez. Eksik koşul → operator-bound supersession kapanır, yeni supersession entry açılır.**

---

## 9. Microsoft Teams / Slack Discipline

HARD RULE 2026-05-27 uygulaması:

- **Alert delivery default = Microsoft Teams** Power Automate workflow + Adaptive Card pattern (ADR-0027 + ADR-0029 mühürlü)
- **Slack pattern asset-preserved başka tenants için**; bizim için active webhook config YOK

### E-2-6 CI workflow notification scope (F9 absorption — Path-aligned)

`live-adapter-evidence-emit.yml` workflow başarısız olursa (örn. schema validation fail, kill-switch raise) notification kanalı Path seçimine **kesinlikle** bağlıdır. **§2 E-2-6 ile çelişen herhangi bir Teams secret ifadesi bu sürümde KALDIRILDI** (önceki sürümde §9 emit workflow içinde `TEAMS_WEBHOOK_URL` inject + HTTP POST tarif ediyordu; bu F2'nin "no secrets in PR-triggered emit workflow" sınırını ihlal ediyordu — Codex F9).

#### Path A (DEFAULT)

- **Teams notification YOK.** Emit workflow secret-free; `TEAMS_WEBHOOK_URL` env scope'unda **bulunmaz**, workflow step'inde **HTTP POST yapılmaz**.
- **Failure görünürlüğü:** PR Checks UI status (`failure` / `success` / `cancelled`). Reviewer artifact'ı PR Checks status'undan indirir.
- Operator manuel takip: GitHub watch / e-mail / GitHub mobile push.

#### Path B (ADVANCED upgrade — opsiyonel, ayrı PR + threat model)

- **Teams notification ayrı `live-adapter-evidence-notify.yml` workflow_run-triggered workflow'unda**; PR-triggered emit workflow'unda **DEĞİL**.
- Notify workflow:
  - Trigger: `workflow_run` (emit workflow tamamlandığında) — runs on `main` branch (trusted code path)
  - Permission: `contents: read` only
  - Secret: `${{ secrets.TEAMS_WEBHOOK_URL }}` **YALNIZCA notify workflow scope'unda** erişilir
  - Emit workflow YAML'ı bu secret'ı **referans etmez**; emit ve notify iki ayrı workflow file ve iki ayrı secret-scope sınırı
- Active path (Path B only): Notify workflow → `curl -X POST https://*.webhook.office.com/...` → Power Automate flow → Adaptive Card chat post
- Dormant snippet (runbook): RB `live-adapter-evidence-slack-reactivation-chain.md` — multi-tenant Slack demand-driven reactivation; bizim için aktif değil
- Ayrı ExternalSecret manifest (Teams active + Slack dormant) — tek manifest 2 required key YASAK (Ready=False chain)

### Webhook secret discipline (E-2-5 ile kesişim — Path B only)

Aşağıdaki kurallar **yalnız Path B** notify workflow'unda geçerlidir (Path A'da Teams secret hiç tanımlanmaz):

- `TEAMS_WEBHOOK_URL` env-var-only (D11 — MCP parametre değil)
- Notify workflow YAML'da raw webhook URL YOK; `${{ secrets.TEAMS_WEBHOOK_URL }}` syntax
- Webhook URL audit log'a düşmez (E-2-5 redaction regex Teams webhook pattern `https://[a-z0-9.\-]+\.webhook\.office\.com/webhookb2/...` zaten default açık)
- Notify workflow secret-bearing olduğu için tek `pull_request_target` veya `pull_request` etkisinde değildir (`workflow_run` trigger only); attacker PR'ı bu workflow'u tetikleyemez (workflow_run security model)

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

---

## 13. Iter-2 Absorb Summary (Codex thread 019e87b6 iter-1 → revision)

Codex iter-1 verdict: **REVISE**, `ready_for_impl: false`. 7 blocker (F1-F7) + 1 non-blocker (F8). Bu revision tüm finding'leri absorb eder.

| Finding | Severity | Section(s) revised | Summary of fix |
|---|---|---|---|
| **F1** Evidence reviewer.verdict='AGREE' pre-recorded before Codex review (No Fake Work ihlali) | blocker/high | `local-ai-review-evidence.v1.json` (önceki commit) | Evidence reviewer.verdict reverted to `"REVISE"`; F1-F8 findings list + iter-2 pending status recorded; iter-2 verdict gerçek Codex AGREE alınmadan AGREE'ye GEÇMEZ. |
| **F2** E-2-6 `pull_request_target` permission/secret çelişkisi | blocker/high | §2 E-2-6 | **Path A default** (pull_request, no secrets, artifact-only, no PR comment); **Path B advanced** (pull_request_target with explicit threat model: base-only checkout, trusted-actor check, separate notify workflow, minimal write). |
| **F3** Cost ceiling API/concurrency inconsistencies | blocker/high | §2 E-2-3 | API: `record_call() -> BreachState` (explicit); validation: reject negative/non-finite/suspicious-zero; concurrency: file-lock per session OR `reserve()`+`settle()` pre-reservation; hard breach raises `CostCeilingExceeded` (no return); soft breach mandates `cost_breach_handling` audit field. |
| **F4** Dry-run kill-switch coverage incomplete | blocker/medium | §2 E-2-4, §6 inv-8 | Expanded: subprocess full family, os.system/popen, httpx async, urllib3, aiohttp, ctypes/cffi/libcurl static denylist. Bypass fixture tests added (parametrize per kill-switch); AST import scan. |
| **F5** Secret redaction regex false-negative | blocker/medium | §2 E-2-5, §6 inv-9 | **Value-based taint tracking PRIMARY** (resolve secret → add to taint set → scan_and_redact before every serialize); regex defense-in-depth (extended: ghp_/github_pat_/ghs_/ghu_/sk-ant-/sk-proj-/Teams webhook URL); serialization gate AST test. |
| **F6** E-2-7 checklist eksik koşullar + `proposed_state` namespacing | blocker/medium | §2 E-2-7, §7, §8 | Extended 9 → 18 conditions (workflow SHA pin, env reviewer, allowlist, provider SLA, budget overrun follow-up, ruleset drift, check collision, deauth, audit chain). `live_adapter_execution_proposed_state` field Option A applied: completely moved to Epic 9 supersession schema; Epic 2 artifact NEVER carries `proposed_state: true`. |
| **F7** V5 roadmap §3 Epic 2 semantics drift | blocker/medium | §1 HARD STOP added | `V5-ROADMAP-EPIC-2-AMEND` ayrı work item / PR declared as hard dependency. E-2-1..E-2-7 implementation BAŞLAYAMAZ until roadmap amend PR merged. This plan PR does NOT touch V5 roadmap. |
| **F8** Cross-AI 3-way insufficient for E-2-6 + E-2-7 | non-blocker/medium | §4 | E-2-6 default Path A = 2-way; **Path B trigger conditions table** specifies when 3-way required (pull_request_target, secrets, write permission). E-2-7 **3-way always** (flip-gate spec critical). |

**Plan PR scope (unchanged):** plan-only PR; runtime code yok, workflow değişikliği yok, guard flag flip yok. Plan PR'ı merge edildikten sonra V5 roadmap amend PR'ı bir sonraki sıradadır; E-2-1 implementation slice'ı roadmap amend merge edildikten SONRA başlar.

---

## 14. Iter-3 Absorb Summary (Codex thread 019e87b6 iter-2 → revision)

Codex iter-2 verdict: **REVISE**, `ready_for_impl: false`. 2 blocker (F9-F10) + 2 non-blocker (F11-F12). Bu revision tüm finding'leri absorb eder. (Iter-1 F1-F8 zaten §13'te kapatıldı.)

| Finding | Severity | Section(s) revised | Summary of fix |
|---|---|---|---|
| **F9** §9 Teams notification metni F2 sınırını yeniden açıyordu (emit workflow içinde `TEAMS_WEBHOOK_URL` inject + HTTP POST) | blocker/high | §1 in-scope, §9 | §9 tam yeniden yazıldı: Path A'da Teams notification YOK (emit workflow secret-free); Path B'de Teams notification AYRI `live-adapter-evidence-notify.yml` `workflow_run`-triggered workflow'unda (main/trusted code path); emit workflow secret-bearing OLMAZ; webhook secret iki workflow file arasında scope-isolated. §1 in-scope satırında da Path A/Path B notasyonu eklendi. |
| **F10** Cost ceiling soft-breach audit schema koşulu yanlış alanı (status enum) kullanıyordu; `soft_breached` provider call status değil breach state | blocker/medium | §2 E-2-2, §2 E-2-3 | Per-call audit schema'sına ayrı `cost_breach_state` enum eklendi (`ok|soft_breached|hard_breached|not_applicable`); `status` provider call lifecycle için ayrı boyut. AllOf koşulu `if cost_breach_state == soft_breached then cost_breach_handling required` olarak güncellendi. Hard-breach audit-writing path explicit dokümante: fail-closed audit row (try-finally) → ana `per_call_audit.jsonl` + ayrı `cost_hard_breach.jsonl` failure artifact'ına yazılır; sonra `raise CostCeilingExceeded`. |
| **F11** Risk table E-2-4 ve E-2-6 hâlâ "low" iken slice başlıkları "medium"; inv-2/inv-3 eski dar kill-switch ve regex listelerini tekrar ediyordu | non-blocker/medium | §3 risk table, §6 inv-2, §6 inv-3 | Risk table E-2-4 medium, E-2-6 Path A medium olarak güncellendi (sebep kolonlarıyla). inv-2 "baseline" + cross-ref inv-8 (full bypass matrix); inv-3 "regex defense-in-depth" + cross-ref inv-9 (primary value-based taint absence). |
| **F12** PR #827 body iter-1 PENDING/9-condition/eski 3-way kapsam özetini gösteriyordu (plan dosyası güncel, PR surface stale) | non-blocker/low | PR #827 body | `gh pr edit 827 --body` ile body iter-2 state'e güncellendi: 18-condition checklist, E-2-6 Path A default/Path B gated, E-2-7 always 3-way, V5 amend hard-stop, current iter sequence (iter-1 REVISE F1-F8 absorbed, iter-2 REVISE F9-F12 absorbed, iter-3 PENDING). |

**Iter-3 expected outcome:** Codex iter-3 → AGREE (F9-F10 closure plus F11-F12 hygiene) → V5 roadmap amend PR opens → roadmap amend merge → E-2-1 envelope schema slice opens (separate worktree per CLAUDE.md §17 + §19).
