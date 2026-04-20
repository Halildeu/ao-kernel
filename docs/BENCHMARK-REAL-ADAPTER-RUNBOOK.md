# Benchmark — Real-Adapter Runbook

**Scope.** Operator-facing walkthrough for running the `governed_review_claude_code_cli` workflow (v3.10 A2, PR #157) against a real `claude` CLI instead of the `codex-stub` baseline. Paired with:

- `governed_review_claude_code_cli.v1.json` (A2) — workflow variant that targets the `claude-code-cli` adapter.
- `claude-code-cli.manifest.v1.json` v1.1.0+ (A1) — advertises `review_findings` capability + `output_parse` rule pointing at `review-findings.schema.v1.json`.
- `policy_worktree_profile.v1.json` (bundled, dormant) — must be enabled via workspace override.

**Status.** This runbook documents configuration only. The real-adapter path is NOT exercised in ao-kernel CI — benchmark-fast stays on the deterministic `codex-stub` path, and `review_ai_flow` keeps that behaviour for baseline reproducibility. Running the real adapter is an operator-driven, out-of-repo action.

---

## 1. Prerequisites

1. **`claude` CLI** installed and authenticated. The manifest's invocation block is:
   ```json
   "invocation": {
     "transport": "cli",
     "command": "claude",
     "args": ["code", "run", "--prompt-file", "{context_pack_ref}", "--run-id", "{run_id}"]
   }
   ```
   Verify authentication with `claude --version` + a dry `claude code` call in a disposable directory before plugging in ao-kernel.

2. **`ANTHROPIC_API_KEY` in env.** The key is resolved via env var; ao-kernel never reads it from argv, stdin, or file (enforced by `policy_worktree_profile.secrets.exposure_modes`).

3. **Python 3.11+ with `ao-kernel` installed.** Existing requirement; no new extras needed.

4. **Disposable sandbox repo.** The real adapter reads/writes inside a per-run git worktree (`policy_worktree_profile.worktree.strategy = new_per_run`). Point ao-kernel at a scratch repo you're comfortable rolling back; do NOT run the first real-adapter pass against a working branch you care about.

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
    "allowlist_secret_ids": ["ANTHROPIC_API_KEY"],
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
- `secrets.allowlist_secret_ids` `[]` → `["ANTHROPIC_API_KEY"]`
- `command_allowlist.exact` += `"claude"`
- `rollout.mode_default` remains `report_only` in the override above, matching the bundled default. As of **v4.0.0b1**, the executor (`ao_kernel/executor/executor.py`) honors the three-tier activation + rollout semantics for the live preflight scope:
  - **`enabled=false`**: policy layer dormant — no events, no fail (sandbox still built from declared fields).
  - **`enabled=true + mode_default=report_only`**: violations collected; `policy_checked` emits with additive payload (`mode`, `would_block`, `violation_kinds`, `promoted_to_block`); step continues.
  - **`enabled=true + mode_default=block`**: violations emit `policy_checked` + `policy_denied`; run fails closed.
  - **Escalation**: in `report_only`, if a violation kind is in `rollout.promote_to_block_on`, escalation overrides and the step is blocked. Bundled default list uses the closed `PolicyViolation.kind` taxonomy (`secret_exposure_denied`, `cwd_escape`, `command_not_allowlisted`).

`v4.0.0b1` caveat: bundled adapters that explicitly use `{python_executable}` in the manifest `command` field get a localized exception for the resolved `sys.executable` realpath only. The sandbox itself is not widened, and unrelated commands still go through normal allowlist enforcement.

Use `report_only` for the first few runs to review `policy_checked` evidence without hitting fail-closed; flip to `block` once the allowlists are tuned.

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

# 4. Export the API key for THIS shell only (no shell-rc leak).
export ANTHROPIC_API_KEY='sk-ant-...'

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
- `adapter-claude-code-cli.jsonl` — the adapter invocation envelope (redacted per `evidence_redaction` patterns).
- `policy_checked` / `policy_denied` events — emitted whenever `policy_worktree_profile.enabled=true` and the executor runs the policy check layer. `policy_checked.payload.violation_kinds` / `policy_denied.payload.violation_kinds` carry the aggregate `PolicyViolation.kind` list for the live scope, including adapter CLI command kinds.

Common violation kinds and the fix:

| `PolicyViolation.kind` | Cause | Fix |
|---|---|---|
| `secret_exposure_denied` | Secret literal detected inside the resolved argv for the adapter invocation (current runtime scope). HTTP header leaks surface under the separate `http_header_exposure_unauthorized` kind; stdin/file exposure checks are deferred. | Audit the adapter invocation template; remove the secret from argv (the allowlisted channel is env). If the argv exposure is legitimate for this adapter, rotate the credential and reshape the invocation. |
| `secret_missing` | A `secret_id` listed in `allowlist_secret_ids` has no value in the resolved env. | Export the secret in the shell you launch the run from (`export ANTHROPIC_API_KEY=...`). |
| `cwd_escape` | Adapter tried to `cd ..` past the worktree root or resolve a path outside `{worktree_base}`. | Shouldn't happen with a well-behaved `claude` prompt; if you see it, report upstream with the evidence JSONL excerpt. |
| `command_not_allowlisted` | Adapter command could not be resolved within the sandbox policy boundary. | Add the command to `exact`, or switch the adapter to an explicitly allowed binary. |
| `command_path_outside_policy` | Adapter command resolved, but its realpath sits outside policy-declared prefixes / exact anchors. | Ensure the real command resolves inside an allowlisted prefix, or use the explicit `{python_executable}` reserved token when the manifest truly means the current interpreter. |
| `http_header_exposure_unauthorized` | An HTTP adapter tried to use a secret in a header but `secrets.exposure_modes` did not include `"http_header"`. | Add `"http_header"` to `exposure_modes` only if you've confirmed the adapter's HTTP transport is trusted with that surface. |

As of **v3.11 P2** the executor honors `rollout.mode_default`: in `report_only` violations emit `policy_checked` with `would_block=true` but the step continues; in `block` violations emit `policy_denied` and fail the run closed. See §2 for the full three-tier behavior and escalation via `promote_to_block_on`.

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
