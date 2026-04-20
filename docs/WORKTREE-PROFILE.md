# Worktree Execution Profile

`policy_worktree_profile.v1.json` is the operator-facing contract for ao-kernel's external-agent sandbox. It defines the FAZ-A **expanded minimum** policy surface: worktree isolation, env allowlist, secret deny-by-default, command allowlist, cwd confinement, and evidence redaction. In `v4.0.0b1`, the live pre-invocation scope includes secret resolution, sandbox env shaping, HTTP header exposure checks, and adapter CLI command validation. OS-level network/egress sandboxing is deferred to FAZ-B.

This document is the plain-English companion to the policy JSON. Read this to decide how to engage the policy, configure it for a demo, or promote it to production mode.

---

## 1. Purpose

The worktree profile is ao-kernel's contract with external coding agents. When ao-kernel hands a task to an adapter (Claude Code CLI, Codex, Cursor background agent, GitHub Copilot cloud agent, gh CLI PR connector, or a custom adapter), the adapter needs:

- a place to work (worktree)
- access to the tools it needs (command allowlist)
- the environment variables it expects (env allowlist)
- the secrets it legitimately requires (secret allowlist + controlled exposure mode)
- constraints that keep it inside its lane (cwd confinement)
- a guarantee that what leaks into logs is sanitized (evidence redaction)

Everything outside those lanes is denied or stripped.

### Threat model covered by FAZ-A profile

- Adapter accidentally reads a file outside the intended workspace view.
- Adapter writes the OpenAI API key into a log line that gets committed.
- Adapter shells out to `rm -rf /` equivalent (command not in allowlist).
- Adapter resolves a symlink outside the worktree root.
- Adapter reads an environment variable that was inherited from the parent shell and contains a secret.
- Adapter passes a token as a CLI argument, where it is visible to `ps` and other process-listing tools.

### Threat model NOT covered by FAZ-A profile (deferred to FAZ-B)

- Adapter makes outbound network requests to arbitrary hosts (network egress).
- Adapter exhausts a kernel resource (RLIMIT-style).
- Adapter escapes a namespace sandbox (cgroups / firejail / nsjail).
- Adapter exfiltrates data through a covert channel (timing, file mtime).

FAZ-B closes the network/egress and OS-level gaps with platform-specific sandboxes. FAZ-A's profile is an in-process policy check plus a per-run worktree.

---

## 2. The Six Minimums (CNS-016 D4)

| # | Minimum | Policy block | What it blocks |
|---|---|---|---|
| 1 | **Per-agent worktree** | `worktree` | Adapter cannot touch other adapters' files or the main checkout. |
| 2 | **Sanitized env allowlist** | `env_allowlist` | Adapter cannot read inherited env variables that may contain secrets. |
| 3 | **Secret deny-by-default** | `secrets` | No secret is available unless its `secret_id` is explicitly allowlisted. |
| 4 | **Command allowlist** | `command_allowlist` | Adapter cannot shell out to arbitrary commands. |
| 5 | **CWD confinement** | `cwd_confinement` | Adapter cannot escape the worktree root via `..` or absolute paths. |
| 6 | **Evidence redaction** | `evidence_redaction` | Secret-shaped strings never appear in JSONL evidence. |

---

## 3. Demo Workspace Override

The bundled default policy is **dormant** (`enabled: false`). To run the DEMO-SCRIPT.md end-to-end flow, place the following override at `.ao/policies/policy_worktree_profile.v1.json` inside the workspace:

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

The override shallow-merges with the bundled default: only `enabled`, `rollout.mode_default`, and `secrets.allowlist_secret_ids` are replaced. Everything else (worktree strategy, env allowlist, command allowlist, cwd confinement, evidence redaction) comes from the bundled default.

Demo prerequisites must be set in the environment before launching:

- `ANTHROPIC_API_KEY` — Anthropic API key for the Claude Code CLI adapter.
- `GH_TOKEN` — GitHub personal access token for the `gh-cli-pr` adapter.

ao-kernel's secret resolver reads these from the host environment and injects them into the adapter's worktree env only via `exposure_modes: ["env"]`. They never appear in CLI arguments, stdin, or files.

---

## 4. Rollout Modes (Three Tiers)

The policy has three operational tiers. The tier is determined by the combination of `enabled` and `rollout.mode_default`:

| Tier | `enabled` | `rollout.mode_default` | Behavior |
|---|---|---|---|
| **Dormant** | `false` | — | Policy layer bypassed. No `policy_checked` or `policy_denied` events emitted; no step fails on policy. Sandbox is still built from declared fields so the adapter has a runnable env. This is the bundled default. |
| **Warmup** | `true` | `"report_only"` | Live violations from the current preflight scope are collected and a single aggregate `policy_checked` event is emitted with additive payload fields (`mode`, `would_block`, `violation_kinds`, `promoted_to_block`). Step continues even if violations are present — UNLESS a violation kind matches `promote_to_block_on` (see below). Command violations participate in this path too. |
| **Production** | `true` | `"block"` | Live violations emit `policy_checked` + `policy_denied`. Run fails closed with `error.category: "policy_denied"` / `PolicyViolationError`. In `v4.0.0b1`, this includes secret resolution, HTTP-header exposure checks, and adapter CLI command enforcement before adapter execution. |

Unknown `mode_default` value → `block` fallback (fail-closed).

### Escalation: `promote_to_block_on`

In `report_only` mode, if ANY `PolicyViolation.kind` value is also in `rollout.promote_to_block_on`, the executor escalates the step to block mode (`policy_denied` + fail). This lets operators warm-up most violations without losing fail-closed semantics for the highest-severity classes.

Entries MUST use the closed taxonomy from `ao_kernel/executor/errors.py::PolicyViolation.kind`:

- `secret_exposure_denied`
- `secret_missing`
- `cwd_escape`
- `command_not_allowlisted`
- `command_path_outside_policy`
- `http_header_exposure_unauthorized`

Bundled default: `["secret_exposure_denied", "cwd_escape", "command_not_allowlisted"]`.

### Promotion path

1. Start with dormant (ship, confirm no workflow depends on a hidden env/command).
2. Enable in report-only mode, run a full week of real demos, review `policy_checked` events (check the `violation_kinds` / `would_block` payload fields), and tune any missing env keys or command allowlist entries before flipping to block.
3. Flip to block mode for production.

---

## 5. Env / Secret Boundary

The policy distinguishes **non-secret environment variables** (`env_allowlist`) from **secrets** (`secrets.allowlist_secret_ids`). They are two different allowlists because they have different handling:

| Axis | `env_allowlist` | `secrets.allowlist_secret_ids` |
|---|---|---|
| What it holds | Non-secret env variable names | Named secret identifiers |
| Example entry | `"PATH"`, `"LANG"` | `"ANTHROPIC_API_KEY"`, `"GH_TOKEN"` |
| Resolution | Direct value passthrough from host env (if `inherit_from_parent: true`) or `explicit_additions` | ao-kernel secrets resolver (mirrors `policy_secrets.v1.json` pattern: `allowed_secret_ids` + `fail_action`) |
| Exposure channel | Injected as environment variable | Injected per `exposure_modes` (default: `["env"]`) |
| Redaction in evidence | No redaction (values assumed non-secret) | Matches `evidence_redaction` patterns and key-name regex |

The boundary matters because a secret appearing in `env_allowlist` would bypass the redaction + deny-by-default protections. Operators who mistakenly add `GH_TOKEN` to `env_allowlist.allowed_keys` would get the value but also lose the redaction guarantee. Hence the rule: **secrets go in the secret allowlist, never in the env allowlist**.

### `denied_exposure_modes`

The `secrets.denied_exposure_modes` list (`["argv", "stdin", "file", "http_header"]`) is the explicit set of channels where secrets must not appear:

- **argv** — secrets as command-line arguments are visible in `ps`, `/proc`, process-listing tools, and evidence command logs.
- **stdin** — adapter prompt payloads are captured in evidence; stdin is where the task prompt goes, not secrets.
- **file** — writing a secret to a file on disk risks accidental commit, backup leak, or later read by a less-trusted process.
- **http_header** — HTTP adapters must explicitly override `exposure_modes` to include `"http_header"`; the bundled default does not, so HTTP transport adapters need a conscious workspace-level decision before they can receive a secret.

Current runtime scope is still narrower than the full policy declaration:

- `argv` secret leakage is checked live via resolved CLI args.
- `http_header` exposure is checked live for HTTP adapters.
- CLI command allowlist enforcement is checked live before adapter execution.
- `stdin` / `file` exposure modes remain policy-declared but are not yet preflighted by the shipped adapter path.

---

## 6. Command Allowlist Semantics

`command_allowlist` has two axes:

- `exact` — list of unqualified command names. Resolved against `$PATH` (which is in `env_allowlist`).
- `prefixes` — list of absolute-path prefixes. Any command under a prefix directory is allowed.

Default prefixes: `/usr/bin/`, `/usr/local/bin/`, `/opt/homebrew/bin/`. The third covers macOS Apple Silicon Homebrew (Intel Macs ship Homebrew under `/usr/local/bin/`, Apple Silicon under `/opt/homebrew/bin/`).

### Tightening for production

The prefix allowlist is intentionally permissive for demo and development. Production workspaces should override with:

```json
{
  "command_allowlist": {
    "exact": ["git", "python3", "pytest", "ruff", "mypy"],
    "prefixes": [],
    "deny_if_not_in_list": true
  }
}
```

Exact-only allowlists are tighter at the cost of more maintenance (every new tool the adapter needs must be added explicitly).

### Resolution

`v4.0.0b1` note: the executor both shapes the sandbox `PATH` and validates the resolved CLI command before `adapter_invoked`. The sandbox object itself stays policy-only; the bundled `{python_executable}` escape hatch is a localized command-resolution exception, not a global allowlist mutation.

The worktree executor:

1. Resolves the command via `$PATH` if it's unqualified.
2. Compares the resolved absolute path against `exact` (by basename) and `prefixes` (by path prefix).
3. If neither matches and `deny_if_not_in_list: true`, the invocation is denied.

If a bundled adapter explicitly uses `{python_executable}` in the `command` field, the executor allows only the resolved `sys.executable` realpath for that invocation. The exception does not widen `allowed_commands_exact`, does not append a path anchor to the sandbox, and does not apply to args or unrelated commands.

---

## 7. CWD Confinement

The adapter runs inside a worktree root defined by `worktree.base_dir_template` (default: `.ao/runs/{run_id}/worktree`). CWD confinement prevents the adapter from leaving that root by:

- `deny_parent_escape: true` — `cd ..` past the root is refused. Each path operation normalizes to an absolute path; if the normalized path is not under the root, it's denied.
- `deny_absolute_paths_outside_root: true` — even explicit absolute paths (e.g., `/etc/passwd`) are denied if they resolve outside the worktree root.
- Symlink resolution — symlinks are resolved before the check, so a symlink pointing outside the root is caught.

`allowed_subdirs: ["*"]` means the adapter is free to move within any subdirectory of the root; the confinement applies only to escaping the root.

---

## 8. Evidence Redaction

`evidence_redaction` scrubs secret-shaped content before it is written to JSONL evidence. Two independent redaction axes:

- `env_keys_matching` — regex applied to environment variable **names**. Any env key whose name matches (case-insensitive) `.*(token|secret|key|password|credential).*` has its value redacted in evidence.
- `stdout_patterns` — regex applied to stdout and stderr **content**. P0 patterns:

| Pattern | Covers |
|---|---|
| `sk-[A-Za-z0-9]{20,}` | OpenAI API keys |
| `sk-ant-[A-Za-z0-9_-]{30,}` | Anthropic API keys (current format) |
| `ghp_[A-Za-z0-9]{20,}` | GitHub personal access tokens |
| `xoxb-[A-Za-z0-9-]+` | Slack bot tokens |
| `Bearer\s+[A-Za-z0-9._~+/=-]+` | Generic OAuth bearer tokens |
| `Basic\s+[A-Za-z0-9+/=]+` | HTTP Basic auth credentials |

Matches are replaced with `***REDACTED***` before the event is serialized to JSONL. Redaction happens at emission time, so the filesystem never holds the unredacted string.

Redaction is **not** a primary defense. The primary defense is `denied_exposure_modes`: secrets never reach stdout in the first place. Redaction is the belt-and-suspenders layer for operator mistakes.

### Deferred to FAZ-B (extended catalog)

- AWS access keys: `AKIA[0-9A-Z]{16}`
- Google API keys: `AIza[0-9A-Za-z_-]{35}`
- xAI tokens: `xai-[A-Za-z0-9]{30,}`
- Structured JWT payloads (three base64 segments joined by `.`)
- Private key blocks: `-----BEGIN (RSA |EC )?PRIVATE KEY-----`

These are left off FAZ-A so the P0 redaction list stays focused on the providers the governed demo actually uses. FAZ-B ops hardening expands the catalog.

---

## 9. Deferred to FAZ-B

| Capability | Target | Why deferred |
|---|---|---|
| OS-level network egress sandbox | FAZ-B | cgroups / firejail / nsjail are platform-specific; needs per-OS testing surface. |
| OS-level resource / namespace sandbox | FAZ-B | Same as above. |
| Extended redaction catalog | FAZ-B | Expands beyond the P0 demo providers. |
| **SSH agent forwarding** | **FAZ-A PR-A5 or later** | `SSH_AUTH_SOCK` inheritance is NOT supported in the FAZ-A demo tier. Demo flow uses HTTP-token auth (`GH_TOKEN`) via `secrets.allowlist_secret_ids`. Workspaces that need SSH for git push/pull must wait for a later FAZ-A PR (or provide their own override with explicit acknowledgement). |

---

## 10. Test Matrix (FAZ-A Release Gate)

The FAZ-A release gate (TRANCHE-STRATEGY-V2.md §10) requires these four deny paths to pass with the policy engaged in block mode:

| Test | Setup | Expected |
|---|---|---|
| env allowlist violation denied | Workspace override with `env_allowlist.allowed_keys` missing `PATH`; invoke adapter | Adapter invocation denied with `policy_denied` event, `error.category: "policy_denied"` |
| command allowlist violation denied | Adapter attempts to run `curl https://evil.example.com`; `curl` not in `exact` or `prefixes` | Denied before adapter execution; `policy_checked` carries the command violation and block mode emits `policy_denied` |
| CWD escape denied | Adapter attempts `open("/etc/passwd")` or `cd ../..`; both resolve outside worktree root | Operation denied, evidence event emitted |
| Secret deny-by-default enforced | Workspace without `secrets.allowlist_secret_ids` entry for `ANTHROPIC_API_KEY`; adapter requires it | Invocation denied before subprocess starts; `MISSING_SECRET_ID` error surfaces to the run |

Current shipped executor exercises the secret, HTTP-header, and command-path surfaces. `stdin` / `file` secret exposure checks remain future work.

---

## 11. Cross-References

- `ao_kernel/defaults/policies/policy_worktree_profile.v1.json` — the bundled policy this doc describes.
- `docs/ADAPTERS.md` — how adapters declare `policy_refs` that include this policy.
- `docs/EVIDENCE-TIMELINE.md` — the `policy_checked` and `policy_denied` events this policy emits.
- `docs/DEMO-SCRIPT.md` — the E2E demo that exercises the demo override above.
- `ao_kernel/defaults/policies/policy_secrets.v1.json` — the allowed-secret-ids + fail-action pattern this policy mirrors for secret resolution.
- `ao_kernel/defaults/schemas/agent-adapter-contract.schema.v1.json` — the adapter contract whose `invocation.cli.env_allowlist_ref` and `invocation.http.auth_secret_id_ref` point into this policy.
