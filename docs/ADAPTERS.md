# Agent Adapters

An adapter is the bridge between an ao-kernel workflow and an external coding-agent runtime. The adapter contract is defined in [`ao_kernel/defaults/schemas/agent-adapter-contract.schema.v1.json`](../ao_kernel/defaults/schemas/agent-adapter-contract.schema.v1.json). This document is the human-readable companion: it explains the contract fields, walks through three reference adapters, and shows how to write a custom one.

---

## 1. Adapter Contract Overview

Every adapter ships a manifest file (typically at `.ao/adapters/<adapter_id>.manifest.v1.json`) that validates against the adapter contract schema. The manifest declares:

1. **Identity** — `adapter_id`, `adapter_kind`, `version`.
2. **Capabilities** — which atomic operations the adapter can perform.
3. **Invocation** — how ao-kernel launches the adapter (CLI subprocess or HTTP).
4. **Input/output envelopes** — the shapes of the data flowing between ao-kernel and the adapter.
5. **Interrupt contract** — how the adapter pauses mid-run for human input.
6. **Policy refs** — which ao-kernel policies must be loaded before invocation.
7. **Evidence refs** — where the adapter's JSONL evidence lands.

ao-kernel's workflow registry resolves the adapter by `adapter_id`, validates its manifest, and invokes it with a populated `input_envelope`.

### Read the schema alongside this doc

This document is narrative; the schema is normative. When the two disagree, the schema wins. Specifically:

- Exact field types, required/optional flags, and enums are in the schema.
- Walkthroughs use representative values; production adapters set values per their actual invocation needs.

---

## 2. Adapter Kinds

The `adapter_kind` field is a closed enum that tells ao-kernel how to route invocations and which defaults to apply. Eight values in FAZ-A:

| `adapter_kind` | Transport | Description |
|---|---|---|
| `claude-code-cli` | CLI | Anthropic Claude Code CLI, invoked as a subprocess with stdin/stdout protocol. |
| `codex-cli` | CLI | OpenAI Codex CLI. |
| `codex-stub` | CLI (in-process) | Deterministic in-process stub for tests and CI demos. Returns pre-seeded output without calling any LLM. |
| `github-copilot-cloud` | HTTP | GitHub Copilot cloud agent — third-party managed runtime, session-tracked. |
| `cursor-bg` | HTTP | Cursor background agents. |
| `gh-cli-pr` | CLI | **Typed VCS/PR connector**, not a full coding agent. Wraps `gh` (GitHub CLI) for PR creation only. Declares `capabilities: ["open_pr"]` and does not produce diffs. |
| `custom-cli` | CLI | User-defined CLI adapter. Escape hatch for runtimes not in the closed list. |
| `custom-http` | HTTP | User-defined HTTP adapter. Same escape hatch for HTTP transport. |

### Promotion criteria for new enum values

Adding a new `adapter_kind` is a contract change. Criteria (either one):

- (a) a bundled adapter manifest ships in `ao_kernel/defaults/`, OR
- (b) 3+ independent user requests for explicit enum support (without using `custom-cli` / `custom-http` override).

Currently routed via `custom-*` escape hatch:
- `aider-cli`
- `devin-http`
- `windsurf-cascade`

A rising contender graduates to explicit enum once the criteria are met, with a minor-version bump to the contract schema.

---

## 3. Capability Semantics

Capabilities are atomic operations the adapter can perform. The `capabilities` array in the manifest declares what the adapter is allowed and expected to do. Six values in FAZ-A:

| Capability | Meaning |
|---|---|
| `read_repo` | Adapter reads files listed in `input_envelope.workspace_view`. |
| `write_diff` | Adapter produces a unified diff in `output_envelope.diff`. |
| `run_tests` | Adapter executes the workspace test suite in its worktree. Usually paired with `read_repo`. |
| `open_pr` | Adapter itself opens a pull request (e.g., GitHub Copilot cloud agent). If absent, ao-kernel opens the PR via a separate `gh-cli-pr` adapter invocation. |
| `human_interrupt` | Adapter may mid-run request human input. Requires `interrupt_contract` in the manifest. |
| `stream_output` | Adapter streams partial output chunks rather than returning a single response. |

### What is NOT a capability

**`commit_write` and `branch_create` are NOT capabilities.** Git commit and branch operations are ao-kernel's responsibility, not the adapter's. The workflow orchestrator applies the adapter's `output_envelope.diff` to a worktree, creates a topic branch, and commits. Adapters that try to `git commit` inside their invocation are violating the contract (and will likely trip the `command_allowlist` or `cwd_confinement` check depending on worktree policy).

**MCP / tool access is NOT a capability.** An adapter that needs to invoke MCP tools (e.g., `ao_memory_read`, `ao_llm_call`) gains that access via `policy_refs` — the workflow declares `policy_tool_calling.v1.json` or `policy_mcp_memory.v1.json` in its run, and the adapter inherits the policy gates. MCP access is policy-gated, not capability-gated. This keeps the capability list focused on adapter output behavior, not internal tool reach.

### Future capabilities

A capability addition is a minor-version schema change. Proposed FAZ-B additions under consideration:
- `run_benchmarks` — for the agent benchmark / regression suite.
- `read_evidence` — adapter reads its own past evidence timeline (for context-aware retries).

These are not in v1.

---

## 4. Invocation Transport

Adapters use one of two transports: `cli` (subprocess-based) or `http` (network-based). The schema uses JSON Schema `oneOf` to enforce exactly one branch per manifest.

### 4.1 CLI transport

```json
"invocation": {
  "transport": "cli",
  "command": "claude",
  "args": ["code", "run", "--prompt-file", "{context_pack_ref}", "--run-id", "{run_id}"],
  "env_allowlist_ref": "#/env_allowlist/allowed_keys",
  "cwd_policy": "per_run_worktree",
  "stdin_mode": "none",
  "exit_code_map": {"0": "ok", "1": "failed", "2": "declined"}
}
```

Key fields:

- `command`: executable resolved via `$PATH` within `env_allowlist`. Must match `command_allowlist` (exact or prefix).
- `args`: argument template. Placeholders like `{task_prompt}`, `{context_pack_ref}`, `{run_id}` are substituted at invocation. **Secrets are never substituted** — `policy_worktree_profile.secrets.denied_exposure_modes` includes `argv`.
- `cwd_policy`: `per_run_worktree` (default; fresh worktree per run) or `shared_readonly` (analysis-only adapters).
- `stdin_mode`: `none`, `prompt_only` (task_prompt on stdin), or `multipart` (structured JSONL input_envelope). Secrets never written to stdin.
- `exit_code_map`: optional mapping from exit code (string key) to `output_envelope.status`. Default: `0` → `ok`, non-zero → `failed`.

### 4.2 HTTP transport

```json
"invocation": {
  "transport": "http",
  "endpoint": "https://api.example.com/v1/agents/{run_id}/run",
  "auth_secret_id_ref": "GITHUB_COPILOT_TOKEN",
  "headers_allowlist": ["Content-Type", "Accept", "X-Run-Id"],
  "request_body_template": {
    "prompt": "{task_prompt}",
    "context_ref": "{context_pack_ref}"
  },
  "response_parse": {
    "diff_jsonpath": "$.result.diff",
    "status_jsonpath": "$.result.status"
  }
}
```

Key fields:

- `endpoint`: URL template; `{run_id}` substitution allowed.
- `auth_secret_id_ref`: secret id referenced in `policy_worktree_profile.secrets.allowlist_secret_ids`. Resolved at invocation time; value injected into HTTP headers (not URL, not body).
- `headers_allowlist`: non-auth headers the adapter is allowed to set. Auth header is derived from `auth_secret_id_ref` and must follow the provider's documented auth scheme.
- `request_body_template`: JSON body template with placeholder substitution.
- `response_parse`: optional JSONPath hints for adapters whose response shape differs from the canonical `output_envelope`.

HTTP adapters must explicitly set `exposure_modes` to include `"http_header"` via workspace override — the bundled default policy denies `http_header` exposure. This forces a conscious decision before an adapter transports a secret over HTTP.

---

## 5. Walkthrough 1: Claude Code CLI

### Manifest sketch

```json
{
  "adapter_id": "claude-code-cli",
  "adapter_kind": "claude-code-cli",
  "version": "1.1.0",
  "capabilities": ["read_repo", "write_diff", "run_tests", "stream_output", "review_findings"],
  "invocation": {
    "transport": "cli",
    "command": "claude",
    "args": ["code", "run", "--prompt-file", "{context_pack_ref}", "--run-id", "{run_id}"],
    "env_allowlist_ref": "#/env_allowlist/allowed_keys",
    "cwd_policy": "per_run_worktree",
    "stdin_mode": "none",
    "exit_code_map": {"0": "ok", "1": "failed", "2": "declined"}
  },
  "input_envelope": {
    "task_prompt": "<issue body>",
    "context_pack_ref": ".ao/runs/{run_id}/context.md",
    "workspace_view": {
      "allowlist_globs": ["**/*.py", "**/*.md", "pyproject.toml"],
      "denylist_globs": [".ao/**", ".git/**", "**/.env*"],
      "max_bytes_per_file": 524288,
      "max_total_bytes": 16777216
    },
    "budget": {
      "tokens": {"limit": 100000},
      "time_seconds": {"limit": 600},
      "fail_closed_on_exhaust": true
    },
    "run_id": "<uuid>"
  },
  "output_envelope": {
    "status": "ok",
    "diff": "<unified diff>",
    "commands_executed": [],
    "evidence_events": [],
    "finish_reason": "normal"
  },
  "policy_refs": [
    "ao_kernel/defaults/policies/policy_worktree_profile.v1.json",
    "ao_kernel/defaults/policies/policy_secrets.v1.json"
  ],
  "evidence_refs": [
    ".ao/evidence/workflows/{run_id}/adapter-claude-code-cli.jsonl"
  ]
}
```

### Invocation path

1. Workflow registry resolves `adapter_id: "claude-code-cli"`.
2. `v4.0.0b1` executor shapes the sandbox `PATH` from `command_allowlist` **and** preflights the resolved adapter CLI command via `validate_command()` before `adapter_invoked`. Bundled `{python_executable}` is a localized exception only for the resolved `sys.executable` realpath.
3. Secret `ANTHROPIC_API_KEY` is in `allowlist_secret_ids`, resolved to env-var, injected into subprocess environment.
4. Worktree is created at `.ao/runs/{run_id}/worktree` (git worktree from main checkout).
5. Subprocess spawned with the resolved command, args template substituted, stdin not used, working dir = worktree.
6. Adapter reads context pack from `{context_pack_ref}` (narrative; adapter's CLI must support this flag).
7. Adapter emits unified diff on stdout (captured, redacted, stored).
8. Exit code mapped to `output_envelope.status` via `exit_code_map`.

### Evidence events emitted

- `adapter_invoked` — before subprocess start.
- `policy_checked` — a single aggregate pre-invocation policy summary event. In `v4.0.0b1`, the live scope covers secret resolution, sandbox shaping, HTTP-header exposure checks, and adapter CLI command enforcement.
- `adapter_returned` — after subprocess exit; payload includes status, finish_reason, cost_actual.

### Failure modes

- Binary not found → `error.category: "invocation_failed"`.
- Exit code not in `exit_code_map` → defaults to `failed`.
- Stdout not parseable as unified diff → `error.category: "output_parse_failed"`.
- Subprocess killed by timeout → `status: "partial"` + `finish_reason: "timeout"`.

---

## 6. Walkthrough 2: Codex Stub

The codex stub is an in-process adapter used for CI determinism and demos without real LLM calls. It ships with ao-kernel as a reference fixture.

### Manifest sketch

```json
{
  "adapter_id": "codex-stub",
  "adapter_kind": "codex-stub",
  "version": "1.0.0",
  "capabilities": ["read_repo", "write_diff"],
  "invocation": {
    "transport": "cli",
    "command": "{python_executable}",
    "args": ["-m", "ao_kernel.fixtures.codex_stub", "--run-id", "{run_id}", "--fixture", "{context_pack_ref}"],
    "env_allowlist_ref": "#/env_allowlist/allowed_keys",
    "cwd_policy": "per_run_worktree",
    "stdin_mode": "none",
    "exit_code_map": {"0": "ok"}
  },
  "input_envelope": {
    "task_prompt": "<stubbed>",
    "context_pack_ref": ".ao/runs/{run_id}/context.md",
    "budget": {
      "tokens": {"limit": 0},
      "fail_closed_on_exhaust": true
    },
    "run_id": "<uuid>"
  },
  "output_envelope": {
    "status": "ok",
    "diff": "<pre-seeded>",
    "evidence_events": []
  },
  "policy_refs": [
    "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"
  ],
  "evidence_refs": [
    ".ao/evidence/workflows/{run_id}/adapter-codex-stub.jsonl"
  ]
}
```

### Why it exists

- **CI determinism.** Tests that exercise the full workflow from `workflow_started` through `pr_opened` need a deterministic agent output. The stub reads a fixture file and emits the same diff every time.
- **Offline demos.** Lets ao-kernel demos run without an API key or network.
- **Contract validation.** The stub is the smallest adapter that validates against the schema — a reference implementation.

### Invocation differences from a real adapter

- No network calls.
- No API keys required; `secrets.allowlist_secret_ids` can stay empty.
- `budget.tokens.limit = 0` — budget is still fail-closed, but no tokens are actually consumed.
- Cost is zero.

---

## 7. Walkthrough 3: gh CLI PR Path

`gh-cli-pr` is a **typed VCS/PR connector**, not a full coding agent. It implements one capability: opening a pull request via the GitHub CLI. It's used by workflows that want ao-kernel to open the PR rather than having the coding adapter do it directly.

### Manifest sketch

```json
{
  "adapter_id": "gh-cli-pr",
  "adapter_kind": "gh-cli-pr",
  "version": "1.0.0",
  "capabilities": ["open_pr"],
  "invocation": {
    "transport": "cli",
    "command": "gh",
    "args": ["pr", "create", "--title", "{task_prompt}", "--body-file", "{context_pack_ref}", "--head", "ao-kernel/run-{run_id}"],
    "env_allowlist_ref": "#/env_allowlist/allowed_keys",
    "cwd_policy": "per_run_worktree",
    "stdin_mode": "none",
    "exit_code_map": {"0": "ok", "1": "failed"}
  },
  "input_envelope": {
    "task_prompt": "<PR title>",
    "context_pack_ref": ".ao/runs/{run_id}/pr-body.md",
    "budget": {
      "time_seconds": {"limit": 60},
      "fail_closed_on_exhaust": true
    },
    "run_id": "<uuid>"
  },
  "output_envelope": {
    "status": "ok",
    "commands_executed": [
      {"command": "gh", "exit_code": 0, "started_at": "...", "completed_at": "..."}
    ],
    "evidence_events": [
      {"kind": "pr_opened", "payload_hash": "..."}
    ]
  },
  "policy_refs": [
    "ao_kernel/defaults/policies/policy_worktree_profile.v1.json",
    "ao_kernel/defaults/policies/policy_secrets.v1.json"
  ],
  "evidence_refs": [
    ".ao/evidence/workflows/{run_id}/adapter-gh-cli-pr.jsonl"
  ]
}
```

### Why it's an adapter

- **Uniform invocation path.** The workflow doesn't have special cases for "open PR via gh" vs "agent opens PR itself". Both go through `adapter_invoked` / `adapter_returned`.
- **Policy and evidence uniformity.** The same worktree profile and evidence taxonomy apply, including secret handling for `GH_TOKEN`.
- **Replaceability.** A workspace that uses GitLab can swap `gh-cli-pr` for a hypothetical `glab-cli-mr` adapter without changing the workflow.

### Why it's NOT a full coding agent

- No `read_repo`, `write_diff`, or `run_tests` capability.
- No input envelope `workspace_view` — `gh` doesn't read the repo for PR creation.
- No `finish_reason` — the invocation is atomic (succeeds or fails).
- Budget is wall-clock-only (no tokens, no cost tracking).

---

## 8. Writing a Custom Adapter

If your runtime doesn't match one of the named `adapter_kind` values, use `custom-cli` or `custom-http`. Step-by-step:

### 8.1 Pick `adapter_kind`

- CLI-based? → `custom-cli`.
- HTTP-based? → `custom-http`.
- Different transport (gRPC, WebSocket)? → FAZ-B scope; open a consultation.

### 8.2 Declare `capabilities`

List the atomic operations the runtime supports. Start minimal — add capabilities only for behaviors you'll exercise. The worktree profile will deny anything beyond the declared capabilities.

### 8.3 Fill `invocation`

See §4. CLI: set `command`, `args`, `cwd_policy`, `stdin_mode`. HTTP: set `endpoint`, `auth_secret_id_ref`, `headers_allowlist`, `request_body_template`.

### 8.4 Map the input envelope

Decide how the runtime receives:
- The natural-language task (`task_prompt`).
- The compiled context pack (`context_pack_ref`).
- The workspace view (`workspace_view.allowlist_globs`).
- The budget ceiling.

Pick transport-appropriate placeholders in `args` or `request_body_template`.

### 8.5 Parse the output

Runtime output must produce an `output_envelope`:
- CLI: adapter writes JSON matching the envelope to stdout, or ao-kernel parses stdout heuristically (unified-diff detection) and fills the envelope.
- HTTP: use `response_parse.diff_jsonpath` and `status_jsonpath` for non-matching response shapes.

### 8.6 Reference the worktree profile

Every adapter MUST include `policy_worktree_profile.v1.json` in `policy_refs`. There is no override for this.

### 8.7 Emit evidence events

At minimum, `adapter_invoked` (emitted by ao-kernel) and `adapter_returned` (emitted from `output_envelope`). Additional evidence events go in `output_envelope.evidence_events`.

### 8.8 Register the manifest

Place the manifest at `.ao/adapters/<adapter_id>.manifest.v1.json`. The workflow registry (Tranche A PR-A2) discovers and validates it on run start.

---

## 9. Testing + Validation

### 9.1 Schema validation

Every manifest must pass:

```bash
python3 -c "
import json
from jsonschema import Draft202012Validator
schema = json.load(open('ao_kernel/defaults/schemas/agent-adapter-contract.schema.v1.json'))
manifest = json.load(open('.ao/adapters/<adapter_id>.manifest.v1.json'))
Draft202012Validator(schema).validate(manifest)
print('OK')
"
```

### 9.2 Demo script fixture

Running `docs/DEMO-SCRIPT.md` with your adapter substituted for Claude Code CLI is the fastest end-to-end behavioral test. If all 11 steps emit the expected evidence events and the PR opens cleanly, the adapter is contract-conformant.

### 9.3 CI-friendly testing

Pair your adapter with the `codex-stub` for deterministic CI: define a workflow variant that uses your adapter for invocation but the stub for output parsing, or run a trace-replay test against a pre-recorded evidence timeline.

---

## 10. Policy Binding

Adapters declare `policy_refs` — the policies ao-kernel must load before invocation. Standard bindings:

| Policy | When to reference | Why |
|---|---|---|
| `policy_worktree_profile.v1.json` | Always (MUST) | Sandbox for adapter invocation. No override for this requirement. |
| `policy_secrets.v1.json` | When adapter needs any secret | `allowed_secret_ids` + `fail_action: block`. Separate from worktree's `allowlist_secret_ids` in scope (policy_secrets is the overall registry; worktree's list is the per-invocation subset). |
| `policy_tool_calling.v1.json` | When adapter invokes ao-kernel MCP tools | Governs which tools the adapter may call and under what policy conditions. |
| `policy_mcp_memory.v1.json` | When adapter reads canonical memory via MCP | Controls which key prefixes the adapter may read / write. |
| `policy_quality.v1.json` | When workflow applies output quality gates | ao-kernel evaluates adapter output against quality gates before applying diff. |

The workflow registry loads the union of all referenced policies for all adapters in a run.

---

## 11. Cross-References

- [`ao_kernel/defaults/schemas/agent-adapter-contract.schema.v1.json`](../ao_kernel/defaults/schemas/agent-adapter-contract.schema.v1.json) — the normative schema this document describes.
- [docs/WORKTREE-PROFILE.md](WORKTREE-PROFILE.md) — the sandbox every adapter runs in.
- [docs/EVIDENCE-TIMELINE.md](EVIDENCE-TIMELINE.md) — the event taxonomy adapters contribute to.
- [docs/DEMO-SCRIPT.md](DEMO-SCRIPT.md) — the end-to-end flow exercising three reference adapters.
- [docs/COMPETITOR-MATRIX.md](COMPETITOR-MATRIX.md) — the live list of adapter-target platforms.
- `ao_kernel/defaults/policies/policy_worktree_profile.v1.json` — the sandbox policy referenced by every adapter.
- `.claude/plans/TRANCHE-STRATEGY-V2.md` §3, §4 — FAZ-A feature roadmap and adapter scope.
