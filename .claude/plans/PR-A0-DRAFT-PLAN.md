# PR-A0 Implementation Plan — FAZ-A Foundation (docs + spec, **no code**)

**Status:** DRAFT **v2** · 2026-04-15
**Base branch:** `claude/faz-a-pr-a0` (from `origin/main` @ `99bf057`)
**Plan authority:** Plan v2.1.1 `strategic_commit_ready=true` (CNS-018 AGREE)
**Adversarial:** CNS-20260415-019 iter-1 PARTIAL (2 blocking + 18 warning absorbed) → iter-2 pending

## Revision History

| Version | Date | Scope |
|---|---|---|
| v1 | 2026-04-15 12:00 | Initial draft, 16 bölüm, user review requested |
| **v2** | 2026-04-15 12:30 | **CNS-019 iter-1 absorbed**: 2 blocker fix + 14 high-value warning fix. Muhasebe '8 artefakt + CHANGELOG' tekleştirildi; worktree policy `$schema` silindi + enabled/mode semantics netleşti + demo override JSON eklendi; `gh-cli-pr` adapter_kind enum'a eklendi; `timeout` status top-level'dan çıkarıldı; state transition tablosu §5'e eklendi; redaction patterns genişletildi; acceptance'a manuel schema validation komutları eklendi. |

---

## 1. Amaç

FAZ-A'nın adopt zeminini dökmek. **8 artefakt + CHANGELOG satır** ile governed demo MVP'sinin **sözleşmelerini** (contracts) kilitle; kod implementasyonu Tranche A PR-A1..PR-A6 ile gelir. PR-A0 = docs + schema + policy, **tek satır Python kodu yok**.

### Neden Docs-First?

CNS-016 önerisi: spec önce yazılır, Codex/kullanıcı adversarial görür, sonra impl. Aksi halde kod yazılırken scope drift olur ve Tranche C pattern'ı kırılır (plan → impl-plan → impl → CNS → merge).

### PR-A0'ın Teslim Ettiği — 8 Artefakt + CHANGELOG

1. `ao_kernel/defaults/schemas/agent-adapter-contract.schema.v1.json` (2 schema'dan 1.)
2. `ao_kernel/defaults/schemas/workflow-run.schema.v1.json` (2 schema'dan 2.)
3. `ao_kernel/defaults/policies/policy_worktree_profile.v1.json` (1 policy)
4. `docs/EVIDENCE-TIMELINE.md` (5 markdown'dan 1.)
5. `docs/DEMO-SCRIPT.md` (5 markdown'dan 2.)
6. `docs/COMPETITOR-MATRIX.md` (5 markdown'dan 3.)
7. `docs/ADAPTERS.md` (5 markdown'dan 4.)
8. `docs/WORKTREE-PROFILE.md` (5 markdown'dan 5.)
+ `CHANGELOG.md` `[Unreleased]` altına FAZ-A PR-A0 başlık + bullet listesi (v3.0.0 pattern)

> **Not (muhasebe tutarlılığı):** Plan v2.1.1 §5 ve SESSION-HANDOFF'ta "6 deliverable" terimi bundled sayımdır: **adapter docs+schema** tek aile, **worktree docs+policy** tek aile. PR-A0 implementasyon planı ise dosya-seviyesinde sayar: **8 dosya + CHANGELOG**. Her iki muhasebe aynı işi gösterir.

---

## 2. Scope Fences (değişmez)

### Scope İçi

- `docs/` dizini oluşturulur (projede ilk kez)
- **2 yeni JSON schema:** `agent-adapter-contract.schema.v1.json`, `workflow-run.schema.v1.json`
- **1 yeni policy:** `policy_worktree_profile.v1.json` (inline `_comment`, ayrı `$schema` yok — `policy_quality.v1.json` pattern'ı; validation schema Tranche A PR-A3 impl ile gelir)
- **5 yeni markdown:** `ADAPTERS.md`, `EVIDENCE-TIMELINE.md`, `WORKTREE-PROFILE.md`, `DEMO-SCRIPT.md`, `COMPETITOR-MATRIX.md`
- `CHANGELOG.md` `[Unreleased]` altına FAZ-A PR-A0 notu (başlık + bullet list, v3.0.0 pattern)

### Scope Dışı (regresyonu önle)

- **Python kodu yok** — `ao_kernel/**/*.py` dokunulmaz
- **Test yok** — impl PR'larında gelir (Tranche A)
- **pyproject.toml extras genişletilmez** — yeni extras (`[code-index]`, `[lsp]`, `[coding]` vb.) dolduğunda eklenir
- **README.md değişmez** — FAZ-A ship aşamasında (Tranche A PR-A6) güncellenir
- **CLAUDE.md değişmez** — FAZ-A ship sonrası (v3.1.0) governance bölümüne adapter contract eklenir
- **1004 test sayısı korunur** — kod değişmediği için zaten doğal
- **Coverage 85% korunur** — aynı

### Bozulmaz İlkeler (plan v2.1.1'den)

- Core dep: sadece `jsonschema>=4.23.0`
- Fail-closed: worktree policy default `enabled: false`
- Schema'lar `additionalProperties: false` (forward-compat vendor fields hariç)
- Workspace artefact evidence = JSONL + SHA256 manifest; MCP evidence = JSONL + fsync (manifest yok, CLAUDE.md §2)
- `project_root()` = `.ao/`'yı içeren dizin
- Policy 4 tipinden biri (autonomy/tool-calling/provider-guardrails/generic)
- POSIX-only kapsam

---

## 3. Yazma Sırası (bağımlılık DAG — CNS-019 confirmed conservative)

```
1. ao_kernel/defaults/schemas/agent-adapter-contract.schema.v1.json
       ↓ (referanslanır)
2. ao_kernel/defaults/schemas/workflow-run.schema.v1.json
       ↓ (execution kapsamı)
3. ao_kernel/defaults/policies/policy_worktree_profile.v1.json
       ↓ (her ikisi de policy'yi referanslar)
4. docs/WORKTREE-PROFILE.md  (policy'nin human-readable; CNS-019 Q1 W1)
5. docs/EVIDENCE-TIMELINE.md  (event taxonomy)
       ↓ (birleşik akış)
6. docs/DEMO-SCRIPT.md  (11-step E2E)

Paralel (bağımsız):
7. docs/COMPETITOR-MATRIX.md

Birleştirici (1..6 sonrası):
8. docs/ADAPTERS.md  (adapter contract human-readable + 3 walkthrough)

Son:
9. CHANGELOG.md [Unreleased] bullet listesi eklenir
10. git commit + gh pr create
```

> Değişiklik (v2): WORKTREE-PROFILE.md artık policy hemen ardından yazılıyor (4. sıra). v1'de demo sonrası birleştiriciyle birlikte yazılacaktı — CNS-019 Q1 W1 bunun demo-bağımsız olduğunu gösterdi.

---

## 4. Artefakt 1 — `agent-adapter-contract.schema.v1.json`

**Path:** `ao_kernel/defaults/schemas/agent-adapter-contract.schema.v1.json`
**Purpose:** ao-kernel'in harici coding agent runtime'larıyla konuştuğu tek sözleşme. Adapter = "ao-kernel → external agent" köprüsü.

### Üst seviye alanlar

| Field | Tip | Gerekli | Açıklama |
|---|---|---|---|
| `$schema` | URI | ✓ | Draft 2020-12 |
| `$id` | URI | ✓ | `urn:ao:agent-adapter-contract:v1` |
| `title`, `description` | string | ✓ | Standart |
| `adapter_id` | string, pattern `^[a-z][a-z0-9-]{2,63}$` | ✓ | Unique slug |
| `adapter_kind` | enum | ✓ | Aşağıda (v2 genişlemesi) |
| `version` | semver string | ✓ | Adapter paketinin versiyonu |
| `capabilities` | array of enum | ✓ | Aşağıda (v2 düzeltme) |
| `invocation` | object | ✓ | Transport ayrımı |
| `input_envelope` | object | ✓ | ao-kernel → adapter input schema |
| `output_envelope` | object | ✓ | adapter → ao-kernel output schema |
| `interrupt_contract` | object | opsiyonel | HITL resume semantics |
| `policy_refs` | array<string> | ✓ | Bu adapter için gerekli policies |
| `evidence_refs` | array<string> | ✓ | JSONL path patterns |

### `adapter_kind` enum (v2 — `gh-cli-pr` eklendi)

```
claude-code-cli | codex-cli | codex-stub |
github-copilot-cloud | cursor-bg |
gh-cli-pr |                     ← NEW (CNS-019 Q2 W1): typed VCS/PR connector, not full coding agent
custom-cli | custom-http
```

**Terfi kriteri** (ADAPTERS'e yazılır): Yeni `adapter_kind` enum değeri eklemek için 2 şart: (a) bundled adapter manifest şipiriyor veya (b) explicit workspace override'sız 3+ kullanıcı talep etti. `aider-cli`, `devin-http`, `windsurf-cascade` şu an için `custom-cli`/`custom-http` escape hatch kullanır.

### `capabilities` enum (v2 — `context_pack_read` silindi)

```
read_repo | write_diff | run_tests | open_pr |
human_interrupt | stream_output
```

> CNS-019 Q2 Add1 düzeltme: `context_pack_read` capability olarak çıkarıldı; compiled context `input_envelope.context_pack_ref` alanı olarak adapter'a zaten verilmiş durumda — ayrı privilege değil. Canonical memory erişimi `policy_mcp_memory` ref'iyle gate edilir (capability değil).

> **Boundary clarification** (ADAPTERS §2 ve §8'de netleşecek): `commit_write`, `branch_create` eklenmez. Git commit + branch oluşturma **ao-kernel sorumluluğu** (worktree executor + PR orchestrator, Tranche A PR-A4). Adapter sadece `write_diff` üretir, ao-kernel bunu apply + commit + branch eder. `open_pr` capability'si = adapter kendisi PR açabiliyor (örn. GitHub Copilot cloud agent) — aksi halde ao-kernel PR açar (gh CLI adapter üzerinden).

> **MCP/Tool access:** Adapter'ın MCP tool çağırma yetkisi ayrı capability **değil**. `policy_refs` içinde `policy_tool_calling.v1.json` veya `policy_mcp_memory.v1.json` varsa adapter o tool'lara erişebilir; yoksa erişemez. Policy-gated, capability-free.

### `invocation` alt yapısı

- `transport`: enum `cli` | `http`
- `cli` branch: `command`, `args` (template), `env_allowlist_ref` (→ `policy_worktree_profile.env_allowlist`), `cwd_policy` (enum: `per_run_worktree`/`shared_readonly`), `stdin_mode` (enum: `none`/`prompt_only`/`multipart`), `exit_code_map`
- `http` branch: `endpoint` (URL template), `auth_secret_id_ref` (→ `policy_worktree_profile.secrets.allowlist_secret_ids`), `headers_allowlist`, `request_body_template`
- `grpc`/`websocket`: FAZ-B scope (terfi kriteri: 2 bundled adapter veya explicit demand)

### `input_envelope` alt yapısı

- `task_prompt`: string (her zaman)
- `context_pack_ref`: path ref (canonical compile output)
- `workspace_view`: file allowlist + `max_bytes`
- `budget`: tokens + time + cost ceiling
- `run_id`: UUID (workflow run'dan ref)

### `output_envelope` alt yapısı (v2 — `timeout` status silindi)

- `status`: enum `ok` | `declined` | `interrupted` | `failed` | `partial`
- `diff`: unified diff (opsiyonel, `write_diff` capability'sine bağlı)
- `commands_executed`: array of command records (worktree policy'nin redaction kuralları uygulanmış)
- `logs_ref`: JSONL path (redacted)
- `evidence_events`: emit edilecek event array
- `error`: `{code, message, category}` (failed only) — `category` enum: `timeout` | `invocation_failed` | `output_parse_failed` | `policy_denied` | `budget_exhausted` | `adapter_crash` | `other`
- `finish_reason`: enum (partial/ok için) — `normal` | `timeout` | `max_tokens` | `stop_sequence` | `tool_call` | `filtered`
- `interrupt_token`: resume token (interrupted only)
- `cost_actual`: tokens + time + cost

> CNS-019 Q2 W4 düzeltme: `timeout` top-level status değil. Repo precedenti (`tests/test_stream_post_processors.py:100-115`, `tests/test_client.py:395-416`) `status='PARTIAL'` + `finish_reason='timeout'` kullanıyor. Adapter v1 bu pattern'ı takip eder.

### `$defs` (nested types)

- `budget`, `workspace_view`, `command_record`, `evidence_event_ref`, `interrupt_request`, `cost_record`, `diff_patch`

### Cross-referanslar (narrative, not schema `$ref`)

- `policy_refs` → `policy_worktree_profile.v1.json` (MUST), `policy_tool_calling.v1.json` (opsiyonel), `policy_mcp_memory.v1.json` (agent memory erişimi varsa)
- `evidence_refs` → `.ao/evidence/workflows/{run_id}/adapter-{adapter_id}.jsonl` pattern
- `run_id` → `workflow-run.schema.v1.json`'dan

> CNS-019 Q3 W1 düzeltme: Cross-schema `$ref` instance identity validate etmez; narrative pattern olarak dokümante edilir. PR-A0 scope'unda loader/registry yok — referential integrity Tranche A PR-A2 (registry) ile gelir.

---

## 5. Artefakt 2 — `workflow-run.schema.v1.json`

**Path:** `ao_kernel/defaults/schemas/workflow-run.schema.v1.json`
**Purpose:** Durable workflow run canonical state. CAS-backed. FAZ-A'da sadece **şema**; state machine impl Tranche A PR-A1.

### Üst seviye alanlar

| Field | Tip | Gerekli | Açıklama |
|---|---|---|---|
| `$schema`, `$id`, `title`, `description` | standart | ✓ | `urn:ao:workflow-run:v1` |
| `run_id` | UUIDv4 | ✓ | Unique |
| `workflow_id` | string | ✓ | Registry ref (örn. `bug_fix_flow`) |
| `workflow_version` | semver | ✓ | Registered workflow'un versiyonu |
| `state` | enum | ✓ | 9 state (aşağıda) |
| `created_at`, `started_at`, `updated_at`, `completed_at` | ISO-8601 | `created_at` ✓ | Timestamps |
| `revision` | string (CAS token) | ✓ | 64-char SHA256 (canonical_store convention, `ao_kernel/context/agent_coordination.py:45-55`) |
| `intent` | object | ✓ | Input spec (issue/prompt/URL) |
| `steps` | array<step_record> | ✓ | Sıralı adımlar |
| `checkpoint` | object | opsiyonel | Son durable checkpoint |
| `policy_refs` | array<string> | ✓ | Run başlangıcında referans alınan policies |
| `adapter_refs` | array<string> | ✓ | Kullanılan adapter_id'ler |
| `evidence_refs` | array<string> | ✓ | JSONL paths |
| `budget` | object | ✓ | remaining + spent + `fail_closed_on_exhaust: true` |
| `approvals` | array<approval> | opsiyonel | HITL governance events |
| `error` | object | opsiyonel | Failure summary |

### State enum (9 state)

```
created | running | interrupted | waiting_approval |
applying | verifying |
completed | failed | cancelled
```

### State Transition Tablosu (v2 yeni — CNS-019 Q3 W2)

| Current | Allowed next | Trigger |
|---|---|---|
| `created` | `running`, `cancelled` | start / abort |
| `running` | `interrupted`, `waiting_approval`, `applying`, `failed`, `cancelled` | adapter HITL request / CI gate / diff apply / adapter error / user abort |
| `interrupted` | `running`, `cancelled`, `failed` | HITL resume / timeout / user abort |
| `waiting_approval` | `applying`, `cancelled`, `failed` | approval granted / denied+cancelled / approval timeout |
| `applying` | `verifying`, `failed`, `cancelled` | patch applied / apply error / user abort |
| `verifying` | `completed`, `failed`, `cancelled` | tests pass / tests fail / user abort |
| `completed`, `failed`, `cancelled` | (terminal) | — |

> `interrupted` = **agent** HITL istedi (adapter.output.interrupt_token), resume adapter tarafında.
> `waiting_approval` = **governance** gate tetiklendi (policy_refs → approval required), resume human/orchestrator tarafında.
> İki token ayrı domain: `$defs.interrupt_request.interrupt_token` (adapter) vs `$defs.approval.approval_token` (governance). CNS-019 Q3 W3 düzeltme.

### `$defs/step_record`

- `step_id`, `step_name`, `state` (same enum), `started_at`, `completed_at`
- `actor`: enum `adapter` | `ao-kernel` | `human` | `system`
- `input_ref`, `output_ref`: event or artefact pointers
- `evidence_event_ids`: emitted events
- `error`: per-step

### `$defs/checkpoint`

- `checkpoint_id`, `sha256`, `jsonl_pointer`, `created_at`, `step_completed_up_to` (step_id)
- Compatible with `ao_kernel/_internal/session/context_store` + `roadmap/checkpoint` patterns

### `$defs/approval`

- `approval_id`, `approval_token`, `requested_at`, `responded_at`, `decision` (`granted`/`denied`/`timeout`), `actor`, `payload`

### `$defs/interrupt_request`

- `interrupt_id`, `interrupt_token`, `emitted_at`, `resumed_at`, `adapter_id`, `question_payload`, `response_payload`

### `$defs/budget`

- `tokens`: `{limit, spent, remaining}`
- `time_seconds`: `{limit, spent, remaining}`
- `cost_usd`: `{limit, spent, remaining}`
- `fail_closed_on_exhaust: true` — CNS-007 pattern (TRANCHE-STRATEGY-V2.md:89 hard budget cap)

### Cross-referanslar (narrative)

- `adapter_refs[*]` → `agent-adapter-contract.schema.v1.json::adapter_id` (value match, not schema `$ref`)
- `policy_refs` → `.ao/` altındaki policy dosyalarına
- `checkpoint.sha256` → workspace integrity manifest

---

## 6. Artefakt 3 — `policy_worktree_profile.v1.json`

**Path:** `ao_kernel/defaults/policies/policy_worktree_profile.v1.json`
**Purpose:** CNS-016 D4 expanded minimum — agent execution sandbox P0. Demo-tier (report_only default). OS-level network/egress FAZ-B.

### Enforcement Semantic (v2 — CNS-019 Q4 blocker 2 fix)

Üç mod, net ayrım:

| `enabled` | `rollout.mode_default` | Davranış |
|---|---|---|
| `false` | — | Policy **dormant**: ne log, ne block. Bundled default. |
| `true` | `"report_only"` | Violations **evidence log'a yazılır** (`policy_checked` event), execution bloklanmaz. Demo warm-up için. |
| `true` | `"block"` | Violations **deny edilir** + evidence log emit. `promote_to_block_on` listesi etkin. Production pattern. |

> `promote_to_block_on` listesi **sadece `mode: "block"` aktifken anlamlı**. report_only'da sadece log. WORKTREE-PROFILE.md §4 bu ayrımı operatör bakışıyla açıklar.

### Secret/Env Modeli (v2 — CNS-019 Q4 blocker 3 fix)

`env_allowlist` = **non-secret environment variables** (PATH, HOME, LANG, ...).
`secrets.allowlist_secret_ids` = **explicitly allowed secrets**, `secret_id → env_name` mapping `policy_secrets.v1.json:4-8` pattern'ına bağlı.

Demo prereq'ler (`ANTHROPIC_API_KEY`, `GH_TOKEN`) **secret allowlist üzerinden** gelir, `env_allowlist`'e yazılmaz. Bu sayede evidence redaction secret'ları otomatik sanitize eder.

### Bundled Default JSON

```json
{
  "version": "v1",
  "enabled": false,
  "_comment": "Fail-closed. Bundled default DORMANT. Workspace override required to enable. Expanded minimum per CNS-016 D4. When enabling, see demo override example in docs/WORKTREE-PROFILE.md §3.",

  "worktree": {
    "strategy": "new_per_run",
    "base_dir_template": ".ao/runs/{run_id}/worktree",
    "cleanup_on_completion": true,
    "max_concurrent": 4
  },

  "env_allowlist": {
    "allowed_keys": ["PATH", "HOME", "USER", "LANG", "LC_ALL", "TZ", "SHELL", "TMPDIR"],
    "inherit_from_parent": false,
    "explicit_additions": {},
    "deny_on_unknown": true
  },

  "secrets": {
    "deny_by_default": true,
    "allowlist_secret_ids": [],
    "exposure_modes": ["env"],
    "denied_exposure_modes": ["argv", "stdin", "file", "http_header"],
    "_exposure_note": "env = exported environment variable. argv/stdin/file/http_header explicitly denied — secret must not appear in command arguments, stdin payloads, files on disk, or HTTP request headers. Adapter invocation stdin_mode='prompt_only' uses task_prompt (non-secret) only."
  },

  "command_allowlist": {
    "exact": ["git", "python", "python3", "pytest", "ruff", "mypy"],
    "prefixes": ["/usr/bin/", "/usr/local/bin/", "/opt/homebrew/bin/"],
    "deny_if_not_in_list": true,
    "_prefix_note": "Prefix allowlist resolves to 'any command under this directory'. Operators with tighter needs should override with exact-only list."
  },

  "cwd_confinement": {
    "root_template": "{worktree_base}",
    "allowed_subdirs": ["*"],
    "deny_absolute_paths_outside_root": true,
    "deny_parent_escape": true
  },

  "evidence_redaction": {
    "env_keys_matching": ["(?i).*(token|secret|key|password|credential).*"],
    "stdout_patterns": [
      "sk-[A-Za-z0-9]{20,}",
      "sk-ant-[A-Za-z0-9_-]{30,}",
      "ghp_[A-Za-z0-9]{20,}",
      "xoxb-[A-Za-z0-9-]+",
      "Bearer\\s+[A-Za-z0-9._~+/=-]+",
      "Basic\\s+[A-Za-z0-9+/=]+"
    ],
    "_redaction_scope_note": "P0 patterns cover: OpenAI (sk-), Anthropic (sk-ant-), GitHub PAT (ghp_), Slack bot (xoxb-), generic OAuth Bearer, HTTP Basic. FAZ-B expands: AWS (AKIA), Google (AIza), xAI (xai-), structured JWT payloads.",
    "file_content_patterns": []
  },

  "deferred_to_faz_b": {
    "network_egress_sandbox": {"status": "planned", "target": "FAZ-B"},
    "os_sandbox": {"status": "planned", "options": ["cgroups", "firejail", "nsjail"], "target": "FAZ-B"},
    "extended_redaction_catalog": {"status": "planned", "target": "FAZ-B"}
  },

  "rollout": {
    "mode_default": "report_only",
    "_mode_note": "Only meaningful when enabled=true. When enabled=false, policy is dormant.",
    "promote_to_block_on": [
      "secret_leak_detected",
      "cwd_escape_attempted",
      "command_not_in_allowlist",
      "unknown_env_key"
    ]
  }
}
```

### Demo Workspace Override Örneği (WORKTREE-PROFILE.md §3'te)

```json
{
  "version": "v1",
  "enabled": true,
  "_comment": "Demo workspace override for DEMO-SCRIPT.md E2E. Activates full sandbox in block mode with minimal secret allowlist.",

  "rollout": {
    "mode_default": "block"
  },

  "secrets": {
    "allowlist_secret_ids": ["ANTHROPIC_API_KEY", "GH_TOKEN"]
  }
}
```

> Workspace override sadece **üst-düzey değişiklikleri** belirtir; bundled default ile shallow-merge edilir. Demo override 3 field yazar (enabled, rollout.mode_default, secrets.allowlist_secret_ids); geri kalan bundled default'tan gelir (env_allowlist, command_allowlist, cwd_confinement, evidence_redaction). Shallow-merge semantiği Tranche A PR-A3 impl'inde kesinleşir.

### Policy tip tespiti & `$schema` kararı

4 tip içinde **generic** (required_fields + blocked_values + limits) ile **tool-calling** kesişim. `ao_kernel/governance.py::_check_rules` semantik değil, sadece validasyon yapar. Enforcement implementasyonu Tranche A PR-A3 (worktree executor) sorumluluğu.

**`$schema` yazılmaz** (v2 karar — CNS-019 Q4 blocker 1 fix): Pattern `policy_quality.v1.json` (inline `_comment`, no external schema). Validation schema Tranche A PR-A3'te impl ile birlikte gelir. Scope §2.1 "sadece 2 schema" garantisi korunur.

---

## 7. Artefakt 4 — `docs/WORKTREE-PROFILE.md`

**Path:** `docs/WORKTREE-PROFILE.md`
**Dil:** İngilizce
**Uzunluk hedefi:** ~200-250 satır
**Amaç:** `policy_worktree_profile.v1.json`'ın human-readable docs'u, operator bakış açısıyla açıklar.

### Bölüm iskeleti

1. **Purpose** — sandbox niye gerekli, threat model, attacker surface
2. **The Six Minimums (CNS-016 D4)**
   - Per-agent worktree · Sanitized env allowlist · Secret deny-by-default · Command allowlist · CWD confinement · Evidence redaction
3. **Demo Workspace Override** — §6'daki override JSON'un adım-adım açıklaması (enabled=true, mode=block, allowlist_secret_ids)
4. **Rollout Modes (Three Tiers)**
   - `enabled: false` — dormant (bundled default)
   - `enabled: true` + `mode: report_only` — log only, warmup
   - `enabled: true` + `mode: block` — deny + emit
   - Geçiş rehberi: nasıl report_only → block'a yükseltilir
5. **Env/Secret Boundary**
   - `env_allowlist` ≠ `secrets.allowlist_secret_ids` (non-secret vs secret)
   - Mapping pattern `policy_secrets.v1.json:4-8` ile relation
   - `exposure_modes: ["env"]` + `denied_exposure_modes` nedenleri
6. **Command Allowlist Semantics**
   - `exact` vs `prefixes` trade-off
   - macOS Apple Silicon note (`/opt/homebrew/bin/`)
   - Tightening: production'da `prefixes: []`, sadece `exact`
7. **CWD Confinement**
   - Worktree root template, subdir allowlist, escape prevention
8. **Evidence Redaction**
   - P0 patterns (6 pattern) açıklaması
   - FAZ-B genişleme roadmap'i
9. **Deferred to FAZ-B** — OS-level network/egress, extended redaction catalog
10. **Test Matrix** (FAZ-A release gate — `TRANCHE-STRATEGY-V2.md:285`)
    - env allowlist violation → denied
    - command allowlist violation → denied
    - cwd escape → denied
    - secret deny-by-default → explicit allowlist gerekli
11. **Cross-references** — adapter contract, workflow run, evidence timeline

---

## 8. Artefakt 5 — `docs/EVIDENCE-TIMELINE.md`

**Path:** `docs/EVIDENCE-TIMELINE.md`
**Dil:** İngilizce
**Uzunluk hedefi:** ~220-270 satır

### Bölüm iskeleti

1. **Purpose** — neden timeline, ne garanti eder (replay determinism, audit, debug)
2. **Event Taxonomy — 17 Event Types** (v2 — CNS-019 Q1 W2 düzeltme)

   Kategoriler:
   - **Workflow lifecycle (3):** `workflow_started`, `workflow_completed`, `workflow_failed`
   - **Step lifecycle (3):** `step_started`, `step_completed`, `step_failed`
   - **Adapter (2):** `adapter_invoked`, `adapter_returned`
   - **Diff (2):** `diff_previewed`, `diff_applied`
   - **Approval (3):** `approval_requested`, `approval_granted`, `approval_denied`
   - **Test (1):** `test_executed`
   - **PR (1):** `pr_opened`
   - **Policy (2):** `policy_checked`, `policy_denied`

3. **Event Envelope** — standart alanlar
   - `event_id` (ULID), `run_id`, `step_id`, `ts`, `actor`, `kind`, `payload`, `payload_hash` (SHA256)
   - Immutable: event yazıldıktan sonra değişmez
   - Redacted: `payload` değerleri worktree policy'nin kurallarıyla sanitized
4. **JSONL File Layout**
   - MCP events: `.ao/evidence/mcp/YYYY-MM-DD.jsonl` (mevcut, CLAUDE.md §2)
   - Workflow events: `.ao/evidence/workflows/{run_id}/events.jsonl` (yeni, PR-A5)
   - Adapter logs: `.ao/evidence/workflows/{run_id}/adapter-{adapter_id}.jsonl`
5. **Integrity Manifest** — workspace artefakt kısmı için SHA256 manifest (MCP için yok, Tranche D)
6. **Replay Contract**
   - Deterministic replay: aynı events → aynı state
   - Predicate replay (FAZ-D #9): aynı branch decisions
   - Non-determinism kaynakları: HITL, external API, time — `replay_safe` flag'iyle işaretlenir
7. **Redaction Rules** — `policy_worktree_profile.evidence_redaction` ref
8. **CLI Plan** — `ao-kernel evidence timeline --run <id>` (Tranche A PR-A5 impl)
9. **Cross-references** — agent-adapter-contract, workflow-run

---

## 9. Artefakt 6 — `docs/DEMO-SCRIPT.md`

**Path:** `docs/DEMO-SCRIPT.md`
**Dil:** İngilizce
**Uzunluk hedefi:** ~250-300 satır

### Bölüm iskeleti

1. **Prerequisites** (v2 — CNS-019 Q5 W2 düzeltme)
   - Install: `pip install ao-kernel[llm,mcp]` (mevcut extras; `[coding]` meta-extra FAZ-A PR-A6 ile ship olacak)
   - Workspace init: `ao-kernel init`
   - Adapter örnekleri: Claude Code CLI yüklü, veya `codex-stub` fixture
   - Env (demo override policy üzerinden): `ANTHROPIC_API_KEY`, `GH_TOKEN` secret'lar `allowlist_secret_ids` ile geçer
2. **Step-by-Step Flow** (11 adım — her adım: command + expected output + evidence event)
3. **Expected Evidence Events** — her step'in emit ettiği 1-3 event (§8 taxonomy ile map)
4. **Failure Modes + Recovery**
5. **Acceptance Checklist** (FAZ-A release gate ile birebir — `TRANCHE-STRATEGY-V2.md:281-288`)
6. **Adapter Walkthrough Placeholders** — detay `docs/ADAPTERS.md`

---

## 10. Artefakt 7 — `docs/COMPETITOR-MATRIX.md`

**Path:** `docs/COMPETITOR-MATRIX.md`
**Dil:** İngilizce
**Uzunluk hedefi:** ~150-200 satır
**Amaç:** CNS-016 W3 — "rakipsiz" regresyonunu önle, canlı doküman.

### Bölüm iskeleti (v1 ile aynı)

1. Purpose
2. Matrix Table (9 row)
3. Adapter Status Taxonomy (`planned/prototype/shipped/blocked/comparison-only`)
4. Update Cadence — FAZ-A/B/C ship sonrası review

---

## 11. Artefakt 8 — `docs/ADAPTERS.md`

**Path:** `docs/ADAPTERS.md`
**Dil:** İngilizce
**Uzunluk hedefi:** ~300-400 satır
**Amaç:** Adapter contract schema'nın human-readable karşılığı + 3 walkthrough.

### Bölüm iskeleti

1. **Adapter Contract Overview** — schema → docs bridge
2. **Adapter Kinds** — 8 enum (v2 `gh-cli-pr` eklendi) + **terfi kriteri** kutucuğu
3. **Capability Semantics** — 6 capability + boundary clarification (commit_write/branch_create niye yok — ao-kernel sorumluluğu; MCP access niye capability değil — policy-gated)
4. **Walkthrough 1: Claude Code CLI Adapter**
5. **Walkthrough 2: Codex Stub Adapter**
6. **Walkthrough 3: gh CLI PR Path Adapter** (`adapter_kind: "gh-cli-pr"`, typed VCS/PR connector — full coding agent değildir, sadece PR creation)
7. **Writing a Custom Adapter** (step-by-step, `custom-cli`/`custom-http` escape hatch)
8. **Testing + Validation**
   - `jsonschema.validators.Draft202012Validator.check_schema(...)` ile schema geçerliliği
   - Demo script fixture ile behavioral test
9. **Policy Binding** — `policy_worktree_profile` (required), `policy_tool_calling` (optional), `policy_mcp_memory` (optional)

---

## 12. CHANGELOG Update (v2 — CNS-019 Q1 blocker 1 fix)

**Path:** `CHANGELOG.md`
**Scope:** `[Unreleased]` altına **başlık + bullet list** (v3.0.0 pattern'ı).

```markdown
## [Unreleased]

### Added — FAZ-A PR-A0 (docs + spec, no code)

- Agent adapter contract schema (`ao_kernel/defaults/schemas/agent-adapter-contract.schema.v1.json`). Defines how external coding agent runtimes (Claude Code CLI, Codex, Cursor background agent, GitHub Copilot cloud agent, gh CLI PR connector, custom CLI/HTTP) integrate with ao-kernel. 8 `adapter_kind` variants + 6 `capabilities` + `cli`/`http` invocation + input/output envelopes + evidence/policy refs.
- Workflow run canonical state schema (`ao_kernel/defaults/schemas/workflow-run.schema.v1.json`). Durable 9-state machine with CAS revision token, checkpoint refs, budget (fail-closed on exhaust), HITL interrupt + governance approval tokens as separate domains, state transition table documented.
- Worktree execution profile policy (`ao_kernel/defaults/policies/policy_worktree_profile.v1.json`). CNS-016 D4 expanded minimum — per-agent worktree + sanitized env allowlist + secret deny-by-default with explicit `allowlist_secret_ids` + command allowlist (POSIX prefixes inc. Apple Silicon `/opt/homebrew/bin/`) + cwd confinement + evidence redaction (6 P0 patterns: sk-, sk-ant-, ghp_, xoxb-, Bearer, Basic). Three rollout tiers: dormant / report_only / block. Network/egress OS sandbox + extended redaction catalog deferred to FAZ-B.
- Docs: `docs/ADAPTERS.md`, `docs/WORKTREE-PROFILE.md`, `docs/EVIDENCE-TIMELINE.md` (17-event taxonomy), `docs/DEMO-SCRIPT.md` (11-step E2E), `docs/COMPETITOR-MATRIX.md` (9-row live competitor/adapter matrix per CNS-016 W3).
- Adversarial consensus: CNS-20260415-019 (PR-A0 plan review) — 2 blocking + 18 warning absorbed.
- Foundation for FAZ-A governed demo MVP (v3.1.0 ship target). Implementation lands in Tranche A PR-A1..PR-A6.
```

---

## 13. Acceptance Criteria (v2 — manuel validation komutları eklendi)

### Artefakt bütünlüğü

- [ ] 8 artefakt + CHANGELOG bullet list oluşturuldu
- [ ] JSON schema'lar geçerli:
  ```bash
  python -m json.tool < ao_kernel/defaults/schemas/agent-adapter-contract.schema.v1.json > /dev/null
  python -m json.tool < ao_kernel/defaults/schemas/workflow-run.schema.v1.json > /dev/null
  python3 -c "import json; from jsonschema.validators import Draft202012Validator; Draft202012Validator.check_schema(json.load(open('ao_kernel/defaults/schemas/agent-adapter-contract.schema.v1.json'))); print('OK: adapter-contract')"
  python3 -c "import json; from jsonschema.validators import Draft202012Validator; Draft202012Validator.check_schema(json.load(open('ao_kernel/defaults/schemas/workflow-run.schema.v1.json'))); print('OK: workflow-run')"
  ```
- [ ] Policy JSON parse edilebilir:
  ```bash
  python -m json.tool < ao_kernel/defaults/policies/policy_worktree_profile.v1.json > /dev/null
  ```
- [ ] Cross-reference grep tutarlılığı:
  ```bash
  grep -c "adapter_id" docs/ADAPTERS.md ao_kernel/defaults/schemas/agent-adapter-contract.schema.v1.json ao_kernel/defaults/schemas/workflow-run.schema.v1.json
  grep -c "run_id" docs/DEMO-SCRIPT.md docs/EVIDENCE-TIMELINE.md ao_kernel/defaults/schemas/workflow-run.schema.v1.json
  grep -c "policy_worktree_profile" docs/*.md ao_kernel/defaults/schemas/agent-adapter-contract.schema.v1.json
  ```

### Regresyon

- [ ] 1004 test sayısı değişmedi (kod yok — doğal korunur)
- [ ] Coverage 85% gate değişmedi
- [ ] Ruff + mypy clean (dosya eklendi, kod yok, etkilenmez)

### Process

- [ ] CLAUDE.md §16 dil kuralı: plan Türkçe, docs/schemas/policy İngilizce
- [ ] Commit mesajı İngilizce, conventional commits format
- [ ] PR title < 70 karakter, body summary + test plan + CNS-019 reference

---

## 14. Risk & Mitigation (v2 — güncel)

| Risk | Olasılık | Mitigation |
|---|---|---|
| Schema alanları eksik/fazla (spec drift) | Düşük (CNS-019 absorbed 2B+18W) | CNS-019 iter-2 verify; gerekirse iter-3 |
| JSON schema draft-2020-12 uyumsuz | Düşük | Acceptance'ta manuel `check_schema` |
| Cross-reference kopuk (adapter ↔ workflow ↔ worktree) | Düşük | Acceptance grep-based, registry Tranche A PR-A2 |
| Worktree policy operator-unfriendly | Düşük | Demo override örneği + rollout 3-tier açıklaması |
| CHANGELOG format hatası | Düşük | v3.0.0 pattern'ı takip edilir (başlık + bullet) |
| Docs marketing-y ("rakipsiz") | Düşük | COMPETITOR-MATRIX.md explicit factual (CNS-016 W3) |

---

## 15. Post-PR-A0 (sonraki iş, scope DEĞİL)

1. **CNS-019 iter-2** — iter-1 blocker fix + warning fix verify (expected AGREE + ready_for_impl=true)
2. **PR-A1** — workflow state machine impl (Tranche A başlangıcı, transition table'dan impl)
3. **PR-A2** — intent router + workflow registry + adapter manifest loader (cross-reference registry burada gelir)
4. **PR-A3** — worktree executor (policy enforcement, `_check_rules` entegrasyonu, `$schema` validation schema)
5. **PR-A4** — diff/patch engine (`#6` + `#16` birleşik primitive)
6. **PR-A5** — evidence timeline CLI (`ao-kernel evidence timeline --run <id>`)
7. **PR-A6** — demo script runnable + adapter fixtures + `[coding]` meta-extra + README update

---

## 16. Audit Trail

| Field | Value |
|---|---|
| Base SHA | `99bf057` (main HEAD) |
| Branch | `claude/faz-a-pr-a0` |
| Plan authority | v2.1.1 (`.claude/plans/TRANCHE-STRATEGY-V2.md`) |
| CNS (strategic) | CNS-20260414-018 AGREE (`strategic_commit_ready=true`) |
| CNS (PR-A0 plan) | CNS-20260415-019 iter-1 PARTIAL → iter-2 pending |
| Adversarial stats (iter-1) | 2 blocking + 18 warning absorbed in v2 |
| Scope reference | Plan v2.1.1 §3 P0; SESSION-HANDOFF §"Next Session" |
| Sibling plans | `.claude/plans/PR-C6a-IMPLEMENTATION-PLAN.md`, `.claude/plans/PR-C6b-IMPLEMENTATION-PLAN.md` (pattern reference) |

---

**Status:** DRAFT v2, awaiting user approval before CNS-019 iter-2. No code yet, no commit yet.
