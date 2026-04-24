# Benchmark — Real-Adapter Runbook

**Scope.** Operator-facing walkthrough for running the `governed_review_claude_code_cli` workflow (v3.10 A2, PR #157; invocation contract refreshed in WP-8.2) against a real `claude` CLI instead of the `codex-stub` baseline. Paired with:

- `governed_review_claude_code_cli.v1.json` (A2) — workflow variant that targets the `claude-code-cli` adapter.
- `claude-code-cli.manifest.v1.json` v1.1.0+ (A1) — advertises `review_findings` capability + `output_parse` rule pointing at `review-findings.schema.v1.json`.
- `policy_worktree_profile.v1.json` (bundled, dormant) — must be enabled via workspace override.

**Status.** This runbook now includes an explicit operator preflight, but the real-adapter path is still NOT exercised in ao-kernel CI. `benchmark-fast` stays on the deterministic `codex-stub` path, and `review_ai_flow` keeps that behaviour for baseline reproducibility. Running the real adapter remains an operator-driven, out-of-repo action.

Successful completion here validates an operator setup, not the whole product support matrix. [`PUBLIC-BETA.md`](PUBLIC-BETA.md) remains the authoritative source for what ao-kernel currently supports as a shipped or beta surface.

---

## 1. Prerequisites

1. **`claude` CLI** installed. The bundled manifest currently targets:
   ```json
   "invocation": {
     "transport": "cli",
     "command": "claude",
     "args": ["-p", "{task_prompt}", "--append-system-prompt-file", "{context_pack_ref}"]
   }
   ```
   Do NOT treat "binary exists" as sufficient. The authoritative preflight is the helper in §1.1, which verifies version, auth status, prompt access, and whether the installed Claude CLI still accepts the bundled manifest argv shape.

2. **Primary auth route = Claude Code session.** Bu repo için varsayılan ve beklenen yol `claude-code-cli` oturumu ile gerçek prompt access almaktır. `claude auth status` tek başına yeterli sayılmaz; §1.1 helper'ı belirleyicidir çünkü `loggedIn=true` durumunda bile gerçek prompt erişimi bloklu olabilir.

   Exported API key route (`ANTHROPIC_API_KEY` / `CLAUDE_API_KEY`) yalnız istisnai operator fallback'idir. `WP-8.2` kabulü için varsayılan yol olarak görülmez ve normal certification lane bunun üzerine kurulmaz.

3. **Python 3.11+ with `ao-kernel` installed.** Existing requirement; no new extras needed.

4. **Disposable sandbox repo.** The real adapter reads/writes inside a per-run git worktree (`policy_worktree_profile.worktree.strategy = new_per_run`). Point ao-kernel at a scratch repo you're comfortable rolling back; do NOT run the first real-adapter pass against a working branch you care about.

### 1.1 Authoritative operator preflight

Run this from the repo root before any real-adapter certification attempt:

```bash
python3 scripts/claude_code_cli_smoke.py --output text
```

The helper is the current smoke SSOT for `claude-code-cli`. It performs four checks:

1. `claude --version`
2. `claude auth status`
3. a live prompt-access probe via `claude -p`
4. a bundled-manifest smoke that resolves the repo's actual `claude-code-cli` invocation template and runs it against a disposable prompt/context file pair

**Success criterion:** all four checks report `pass`.

**Current blocker semantics:**

| `finding_code` | Meaning | Typical next action |
|---|---|---|
| `claude_binary_missing` | `claude` binary yok veya PATH'te değil | CLI'ı kur, PATH'i düzelt |
| `claude_not_logged_in` | `claude auth status` login göstermiyor | `claude auth login` veya auth route'unu düzelt |
| `prompt_access_denied` | login görünse bile gerçek prompt çağrısı yetkisiz | org/subscription/access tarafını çöz; yalnız `auth status`'a güvenme |
| `prompt_smoke_timeout` | canlı prompt probe sürede dönemedi | CLI hang/latency nedenini ayır; helper artık crash etmez, fail-closed raporlar |
| `manifest_cli_contract_mismatch` | bundled manifest argv yüzeyi yüklü Claude CLI ile uyuşmuyor | manifest/runtime contract düzeltmesi aç; workflow smoke'a geçme |
| `manifest_smoke_timeout` | bundled manifest smoke sürede dönemedi | auth/CLI hang ve prompt contract etkisini ayır; workflow’a geçmeden nedeni çöz |
| `manifest_output_not_json` | CLI çalıştı ama required JSON envelope dönmedi | prompt contract'ı veya adapter invocation'ı düzelt |
| `manifest_output_missing_status` | stdout JSON ama top-level `status` yok | fail-closed output contract'ı düzelt |

Helper çıkışı `blocked` ise bu lane certification-pass veya production-tier sayılamaz.

### 1.2 Governed workflow smoke

Helper preflight `pass` olduktan sonra gerçek workflow path'ini doğrulamak için:

```bash
python3 scripts/claude_code_cli_workflow_smoke.py --output text --timeout-seconds 60
```

Bu smoke helper-level manifest probe'dan daha kapsamlıdır:

1. kontrollü disposable workspace hazırlar,
2. `governed_review_claude_code_cli` workflow'unu read-only prompt ile çalıştırır,
3. `review_findings` artifact'inin materialize olduğunu, schema-valid olduğunu
   ve `schema_version` / `findings` / `summary` semantik alanlarını taşıdığını
   doğrular,
4. `events.jsonl` içinde `step_started`, `policy_checked`, `adapter_invoked`,
   `step_completed` ve terminal `workflow_completed` eventlerini arar ve bu
   eventlerin canonical sırada göründüğünü doğrular,
5. `adapter-claude-code-cli.jsonl` evidence log'unun varlığını ve temel redaction
   kontrolünü doğrular.

**Success criterion:** `overall_status: pass` ve `final_state: completed`.

Bu komut `claude-code-cli` yüzeyini production-certified yapmaz. `GP-2.4d`
final verdict'i `operator_managed_beta_keep` olduğu için lane Beta
(operator-managed) olarak kalır.

### 1.3 Failure-mode matrix

Certification kararında yeşil sayılabilecek tek durum `overall_status: pass`'tir.
Aşağıdaki stable finding code'lar ise promotion blocker'dır:

| Failure | Stable finding code | Nerede yüzeye çıkar |
|---|---|---|
| `claude` binary missing | `claude_binary_missing` | helper preflight |
| `auth_status` not logged in | `claude_not_logged_in` | helper preflight |
| `auth_status` malformed JSON | `claude_auth_status_not_json` | helper preflight |
| `prompt_access` fail despite auth pass | `prompt_access_denied` | helper preflight |
| prompt invocation timeout | `prompt_smoke_timeout` | helper preflight |
| manifest invocation timeout | `manifest_smoke_timeout` | helper preflight |
| manifest non-JSON output | `manifest_output_not_json` | helper preflight |
| manifest JSON missing `status` | `manifest_output_missing_status` | helper preflight |
| adapter non-zero exit | `adapter_non_zero_exit` | governed workflow smoke |
| adapter timeout | `adapter_timeout` | governed workflow smoke |
| malformed workflow output | `output_parse_failed` | governed workflow smoke |
| policy deny before invocation | `policy_denied` | governed workflow smoke |

Bu matrix, "auth yeşil ama prompt erişimi yok" ve "workflow koştu ama output
parse edilmedi" gibi fake-green durumlarını production certification dışı tutar.

2026-04-22 canlı ayrım:

- Aynı makinede ilk preflight, `claude auth status` yeşil olmasına rağmen
  `claude -p` ve bundled manifest smoke'u
  "Your organization does not have access to Claude" ile blokladı.
- Kontrollü `claude auth logout` + `claude auth login --claudeai` sonrası yeni
  organizasyon oturumunda helper tamamen `pass` verdi ve doğrudan
  `claude -p "reply with exactly ok"` çağrısı `ok` döndürdü.
- `claude setup-token` ile üretilen uzun ömürlü OAuth token bu turda güvenilir
  kurtarma yolu olarak kanıtlanmadı; env-var altında ayrıca
  `Invalid bearer token` reddi görüldü.

Sonuç: bu lane'de "auth status yeşil" = "prompt access var" varsayımı yasak.
Belirleyici sinyal her zaman helper'ın gerçek `claude -p` probe sonucudur.
Başarı koşulu yalnız binary/manifest değil, prompt access veren doğru org/account
oturumudur.

---

## 2. Workspace override — `policy_worktree_profile.v1.json`

Bundled default ships **dormant** (`enabled=false`). Operator override lands in `.ao/policies/policy_worktree_profile.v1.json` (workspace-level, overrides bundled).

Minimum viable override:

```json
{
  "version": "v1",
  "enabled": true,

  "worktree": {
    "strategy": "new_per_run",
    "base_dir_template": ".ao/runs/{run_id}/worktree",
    "cleanup_on_completion": true,
    "max_concurrent": 4
  },

  "env_allowlist": {
    "allowed_keys": ["PATH", "HOME", "USER", "LANG", "LC_ALL", "TZ", "SHELL", "TMPDIR"],
    "inherit_from_parent": false,
    "deny_on_unknown": true
  },

  "secrets": {
    "deny_by_default": true,
    "allowlist_secret_ids": [],
    "exposure_modes": ["env"],
    "denied_exposure_modes": ["argv", "stdin", "file", "http_header"]
  },

  "command_allowlist": {
    "exact": ["git", "python", "python3", "pytest", "ruff", "mypy", "claude"],
    "prefixes": ["/usr/bin/", "/usr/local/bin/", "/opt/homebrew/bin/"],
    "deny_if_not_in_list": true
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
    ]
  },

  "rollout": {
    "mode_default": "report_only",
    "promote_to_block_on": [
      "secret_exposure_denied",
      "cwd_escape",
      "command_not_allowlisted"
    ]
  }
}
```

Key deltas from bundled:
- `enabled` false → **true** (engages the policy)
- `command_allowlist.exact` += `"claude"`
- `rollout.mode_default` remains `report_only` in the override above, matching the bundled default. As of **v4.0.0b1**, the executor (`ao_kernel/executor/executor.py`) honors the three-tier activation + rollout semantics for the live preflight scope:
  - **`enabled=false`**: policy layer dormant — no events, no fail (sandbox still built from declared fields).
  - **`enabled=true + mode_default=report_only`**: violations collected; `policy_checked` emits with additive payload (`mode`, `would_block`, `violation_kinds`, `promoted_to_block`); step continues.
  - **`enabled=true + mode_default=block`**: violations emit `policy_checked` + `policy_denied`; run fails closed.
  - **Escalation**: in `report_only`, if a violation kind is in `rollout.promote_to_block_on`, escalation overrides and the step is blocked. Bundled default list uses the closed `PolicyViolation.kind` taxonomy (`secret_exposure_denied`, `cwd_escape`, `command_not_allowlisted`).

`v4.0.0b1` caveat: bundled adapters that explicitly use `{python_executable}` in the manifest `command` field get a localized exception for the resolved `sys.executable` realpath only. The sandbox itself is not widened, and unrelated commands still go through normal allowlist enforcement.

Use `report_only` for the first few runs to review `policy_checked` evidence without hitting fail-closed; flip to `block` once the allowlists are tuned.

If you deliberately use the rare env-secret fallback, extend the override with:

```json
"secrets": {
  "deny_by_default": true,
  "allowlist_secret_ids": ["ANTHROPIC_API_KEY"],
  "exposure_modes": ["env"],
  "denied_exposure_modes": ["argv", "stdin", "file", "http_header"]
}
```

### Note on `policy_secrets.v1.json`

The workflow's `invoke_review_agent` step declares `policy_refs` that include `policy_secrets.v1.json`. In the current ao-kernel executor (`executor/policy_enforcer.py`), the **live secret gate is `policy_worktree_profile.secrets.allowlist_secret_ids`** — that's the single source the invoker reads. `policy_secrets.v1.json` is the **canonical declarative companion**: a registry of documented secret IDs + fail actions that downstream audits can cross-reference. Flipping fields in `policy_secrets.v1.json` alone will NOT change runtime behaviour today; the switch you want is inside `policy_worktree_profile`.

---

## 3. Prompt contract (required)

The `claude-code-cli` manifest's `output_parse` rule is **fail-closed**:

```json
{"json_path": "$.review_findings", "capability": "review_findings", "schema_ref": "review-findings.schema.v1.json"}
```

Runtime parser (`ao_kernel/executor/adapter_invoker.py`) reads the adapter's stdout, strips whitespace, calls `json.loads()` on the result, and requires a top-level dict with a valid `status` enum (`ok | declined | interrupted | failed | partial`). So the adapter's stdout MUST be a single JSON object — **no markdown code fences, no prose before or after**. The capability payload rides inside that envelope under the `review_findings` key:

```json
{
  "status": "ok",
  "review_findings": {
    "schema_version": "1",
    "findings": [
      {
        "severity": "warning",
        "file": "src/foo.py",
        "line": 42,
        "message": "Helper duplicates logic from utils/bar.py — consider dedup.",
        "suggestion": "Extract common branch into shared_utils.normalise_path()"
      }
    ],
    "summary": "One warning; no blocking errors.",
    "score": 0.82
  }
}
```

The `status` field is NOT optional — the runtime rejects any dict that lacks it, or carries a value outside the allowed enum, with `AdapterOutputParseError` before `output_parse` rules even run.

Minimum required fields per `review-findings.schema.v1.json`:
- `review_findings.schema_version` — const `"1"`.
- `review_findings.findings` — array (empty is legal = "reviewed, no issues"; missing/wrong shape = workflow fails).
- `review_findings.summary` — non-empty string.

Optional:
- `review_findings.score` — 0.0..1.0.
- Per-finding: `file`, `line`, `suggestion`.

`severity` enum is closed: `error | warning | info | note`. **`critical` is deliberately not valid.**

Supply the prompt template to the adapter via `{context_pack_ref}` (the `compile_context` step produces this). Minimum guidance for the prompt body:

> "Your entire response MUST be a single JSON object — no markdown, no code fences, no prose. The object MUST have `\"status\": \"ok\"` at the top level, plus a `\"review_findings\"` key whose value conforms to `review-findings.schema.v1.json`. Every `findings[]` entry MUST include `severity` (one of `error`, `warning`, `info`, `note`) and `message`. `summary` is mandatory and must be one line. Do not print anything before the opening `{` or after the closing `}`."

If the adapter's stdout doesn't parse as a single JSON dict with a valid `status`, `adapter_invoker` raises `AdapterOutputParseError` and the workflow transitions to `failed` — a clean signal, not a silent miss.

---

## 4. Disposable sandbox repo pattern

The real adapter can mutate the worktree. Strongest isolation:

```bash
# 1. Clone your target repo into a disposable directory you will delete after.
cd /tmp
mkdir real-adapter-sandbox && cd real-adapter-sandbox
git clone --depth 1 git@github.com:your-org/target-repo.git .

# 2. Create your ao workspace here.
ao-kernel init

# 3. Drop your override into .ao/policies/
mkdir -p .ao/policies
cat > .ao/policies/policy_worktree_profile.v1.json <<'EOF'
{ ...the override from §2... }
EOF

# 4. Verify the Claude Code session can answer a trivial prompt.
python3 scripts/claude_code_cli_smoke.py --output text

# 5. Run the benchmark workflow with the real-adapter variant.
#    The exact ao-kernel bench entrypoint depends on your install; see
#    `ao-kernel --help` and docs/BENCHMARK-SUITE.md for the current
#    invocation surface.

# 6. Inspect evidence, then rm -rf the whole sandbox directory.
```

The `policy_worktree_profile.worktree.cleanup_on_completion = true` setting plus `rm -rf` the sandbox directory after each run keeps the worktree off any persistent disk.

---

## 5. Evidence & troubleshooting

Every run writes JSONL evidence under `.ao/evidence/workflows/{run_id}/`:
- `adapter-claude-code-cli.jsonl` — captured adapter stdout/stderr evidence log (redacted per `evidence_redaction` patterns).
- `policy_checked` / `policy_denied` events — emitted whenever `policy_worktree_profile.enabled=true` and the executor runs the policy check layer. `policy_checked.payload.violation_kinds` / `policy_denied.payload.violation_kinds` carry the aggregate `PolicyViolation.kind` list for the live scope, including adapter CLI command kinds.

Common violation kinds and the fix:

| `PolicyViolation.kind` | Cause | Fix |
|---|---|---|
| `secret_exposure_denied` | Secret literal detected inside the resolved argv for the adapter invocation (current runtime scope). HTTP header leaks surface under the separate `http_header_exposure_unauthorized` kind; stdin/file exposure checks are deferred. | Audit the adapter invocation template; remove the secret from argv (the allowlisted channel is env). If the argv exposure is legitimate for this adapter, rotate the credential and reshape the invocation. |
| `secret_missing` | A `secret_id` listed in `allowlist_secret_ids` has no value in the resolved env. | Bu yalnız env-secret fallback kullaniyorsan anlamlıdır; normal Claude Code session yolunda `allowlist_secret_ids` boş kalabilir. |
| `cwd_escape` | Adapter tried to `cd ..` past the worktree root or resolve a path outside `{worktree_base}`. | Shouldn't happen with a well-behaved `claude` prompt; if you see it, report upstream with the evidence JSONL excerpt. |
| `command_not_allowlisted` | Adapter command could not be resolved within the sandbox policy boundary. | Add the command to `exact`, or switch the adapter to an explicitly allowed binary. |
| `command_path_outside_policy` | Adapter command resolved, but its realpath sits outside policy-declared prefixes / exact anchors. | Ensure the real command resolves inside an allowlisted prefix, or use the explicit `{python_executable}` reserved token when the manifest truly means the current interpreter. |
| `http_header_exposure_unauthorized` | An HTTP adapter tried to use a secret in a header but `secrets.exposure_modes` did not include `"http_header"`. | Add `"http_header"` to `exposure_modes` only if you've confirmed the adapter's HTTP transport is trusted with that surface. |

As of **v3.11 P2** the executor honors `rollout.mode_default`: in `report_only` violations emit `policy_checked` with `would_block=true` but the step continues; in `block` violations emit `policy_denied` and fail the run closed. See §2 for the full three-tier behavior and escalation via `promote_to_block_on`.

### Preflight failures before workflow evidence exists

The helper in §1.1 can fail before ao-kernel reaches `policy_checked` / workflow evidence. These are certification-preflight finding codes, not `PolicyViolation.kind` values:

| Preflight finding | Why it matters |
|---|---|
| `claude_binary_missing` | No real-adapter lane exists on this machine yet |
| `claude_not_logged_in` | Operator auth route incomplete |
| `prompt_access_denied` | Login surface and actual model access disagree |
| `manifest_cli_contract_mismatch` | Bundled manifest no longer matches installed Claude CLI flags/subcommands |
| `manifest_output_not_json` / `manifest_output_missing_status` | Prompt contract no longer satisfies ao-kernel's fail-closed parser |

---

## 6. Cost & budget

Bundled adapter manifest sets a per-run budget:

```json
"budget": {
  "tokens": {"limit": 100000, "remaining": 100000},
  "time_seconds": {"limit": 600.0, "remaining": 600.0},
  "fail_closed_on_exhaust": true
}
```

At `sk-ant` pricing tiers (as of 2026-04), 100k tokens on a Sonnet tier run is ≈ $0.30–$1.50 per invocation depending on the output size. Multiply by the number of benchmark rows you plan to run. Keep `fail_closed_on_exhaust = true` so a runaway invocation can't blow the budget ceiling.

---

## 7. What this runbook does NOT ship

- **An `ao-kernel bench init-sandbox` command.** Per Codex plan-time review, introducing new product surface here would balloon v3.10 A's scope. Use the manual steps in §4 instead; if a bootstrap command proves useful, it lands as a separate proposal.
- **Automated real-adapter smoke in CI.** The ao-kernel CI stays on deterministic local stubs. Running the real adapter is explicitly operator-driven.
- **Scoring / comparison harness.** The benchmark score pipeline is `review_ai_flow` + `codex-stub`; real-adapter runs produce the same `review_findings` shape that an external scoring tool can consume, but ao-kernel does not ship a cross-run comparison UI in v3.10.

---

## 8. Related docs

- `docs/BENCHMARK-SUITE.md` — benchmark suite architecture, `review_ai_flow`, scorecard contract.
- `docs/BENCHMARK-FULL-MODE.md` — `@pytest.mark.full_mode` + `--benchmark-mode` option contract.
- `docs/ADAPTERS.md` — adapter manifest schema, capability enum, registry lookup.
- `docs/WORKTREE-PROFILE.md` — full `policy_worktree_profile` field reference.

---

## 9. v3.10 A arc ship map

- PR #156 (A1) — `claude-code-cli` manifest `review_findings` capability + `output_parse` rule + v1.0.0 → v1.1.0.
- PR #157 (A2) — `governed_review_claude_code_cli.v1.json` workflow variant (contrast with `review_ai_flow` which stays pinned at `codex-stub`).
- **This PR (A3)** — Operator runbook.

v3.10.0 release ships A1 + A2 + A3 together. Post-v3.10 follow-ups tracked: `AoKernelClient.call_tool()` standalone reset (preexisting debt, deferred M3), additional `_internal/*` coverage tranches (providers, shared).
