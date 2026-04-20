# Roadmap Spec — FAZ-A Demo Script

Bu doküman roadmap/spec yüzeyidir; canlı Public Beta komut referansı
değildir. Desteklenen demo yüzeyi için
[`../PUBLIC-BETA.md`](../PUBLIC-BETA.md) dosyasına gidin.

This is the acceptance script for FAZ-A (v3.1.0 ship target). An 11-step flow that takes an issue from intent to merged PR, with every step governed by ao-kernel: policy checks, worktree confinement, canonical memory, evidence capture, human approval, and replay. When this script runs clean locally on a sample repository, FAZ-A is considered demo-ready.

The script is specification at PR-A0. The CLI commands and adapter bindings referenced here become executable incrementally across Tranche A PR-A1 through PR-A6.

---

## 1. Prerequisites

### 1.1 Installation

```bash
pip install 'ao-kernel[llm,mcp]'
```

> The `[coding]` meta-extra (`[llm]` + `[code-index]` + `[lsp]` + `[metrics]`) ships with FAZ-A PR-A6 alongside a runnable demo; for the PR-A0 spec you can follow the flow manually.

### 1.2 Workspace

```bash
cd <sample-repo>
ao-kernel init
```

`ao-kernel init` creates the `.ao/` workspace with the bundled policies and schemas.

### 1.3 Policy override

Place the demo workspace override at `.ao/policies/policy_worktree_profile.v1.json` (see [WORKTREE-PROFILE.md §3](../WORKTREE-PROFILE.md)):

```json
{
  "version": "v1",
  "enabled": true,
  "rollout": {"mode_default": "block"},
  "secrets": {"allowlist_secret_ids": ["ANTHROPIC_API_KEY", "GH_TOKEN"]}
}
```

### 1.4 Secrets

Export the allowlisted secrets before invoking ao-kernel:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export GH_TOKEN=ghp_...
```

These resolve through ao-kernel's secrets resolver via `secrets.allowlist_secret_ids` and are injected into the adapter worktree only as environment variables (`exposure_modes: ["env"]`). They never appear in command arguments, stdin payloads, files, or HTTP request bodies.

### 1.5 Adapter availability

The demo exercises three adapters:

- **`claude-code-cli`** — requires the Claude Code CLI binary on `$PATH`.
- **`codex-stub`** — in-process deterministic stub, shipped with ao-kernel for CI.
- **`gh-cli-pr`** — requires the `gh` CLI on `$PATH` and `GH_TOKEN` allowlisted.

Substitute `codex-stub` for `claude-code-cli` to run deterministically without an LLM provider.

---

## 2. Step-by-Step Flow

Each step lists the CLI command, expected output summary, and the evidence events emitted (see [EVIDENCE-TIMELINE.md §2](../EVIDENCE-TIMELINE.md)).

### Step 1 — Intent input

**Command:**
```bash
ao-kernel intent classify --input issue.md
```

**Input:** `issue.md` — a markdown file describing the bug or feature (could also be a GitHub issue URL via `gh issue view 42 --json body,title -q .body > issue.md`).

**Output:** one-line JSON with the chosen workflow id.
```json
{"workflow_id": "bug_fix_flow", "confidence": 0.82, "matched_rules": ["keyword:fix"]}
```

**Evidence events:** none yet (workflow not started).

### Step 2 — Workflow start

**Command:**
```bash
ao-kernel workflow start --flow bug_fix_flow --input issue.md
```

**Output:** run id and initial checkpoint.
```
run_id: a1b2c3d4-e5f6-4789-9012-3456789abcde
state: running
checkpoint: .ao/runs/a1b2c3d4.../checkpoint-0.jsonl
worktree: .ao/runs/a1b2c3d4.../worktree
```

**Evidence events:**
- `workflow_started` (actor: `ao-kernel`)
- `step_started` for `setup_worktree` (actor: `ao-kernel`)
- `policy_checked` for `policy_worktree_profile` (actor: `ao-kernel`)
- `step_completed` for `setup_worktree`

### Step 3 — Context compile

**Command:**
```bash
# Automatic; triggered by workflow start. No separate command needed.
```

ao-kernel's context compiler compiles a three-lane context pack: canonical decisions, session transcript, workspace facts (see [CLAUDE.md §9](../CLAUDE.md)).

**Evidence events:**
- `step_started` for `compile_context`
- `step_completed` for `compile_context` (payload: context pack byte count, lanes compiled)

### Step 4 — Adapter invocation

**Command:**
```bash
# Automatic; triggered after context compile.
# Demo uses the claude-code-cli adapter per the bug_fix_flow workflow definition.
```

The worktree executor resolves `policy_worktree_profile`, builds the adapter `input_envelope` (task_prompt from issue, context_pack_ref, workspace_view glob, budget ceiling), and invokes the adapter inside its per-run worktree.

**Evidence events:**
- `step_started` for `invoke_adapter:claude-code-cli`
- `policy_checked` for `command_allowlist`, `env_allowlist`, `secrets` (each a separate event)
- `adapter_invoked` (actor: `ao-kernel`, payload: adapter_id, invocation summary, budget remaining)
- `adapter_returned` (actor: `adapter`, payload: status, finish_reason, cost_actual)
- `step_completed` for `invoke_adapter:claude-code-cli`

### Step 5 — Diff preview

**Command:**
```bash
ao-kernel diff preview --run <run_id>
```

**Output:** unified diff from `adapter_returned.diff`, rendered to terminal with context.

**Evidence events:**
- `step_started` for `preview_diff`
- `diff_previewed` (payload: diff byte count, file count)
- `step_completed` for `preview_diff`

### Step 6 — CI gate

**Command:**
```bash
ao-kernel ci gate --run <run_id>
```

Runs the workspace test suite inside the worktree (`pytest` + `ruff` per the demo workflow). Exit code + summary are recorded.

**Evidence events:**
- `step_started` for `ci_gate`
- `test_executed` (payload: exit code, summary, test count)
- `step_completed` or `step_failed` for `ci_gate`

If the CI gate fails, the run transitions to `failed` with `error.category: "ci_failed"`. Recovery: re-invoke the adapter with the CI failure summary appended to the prompt (not a PR-A0 step; see §4 Failure Modes).

### Step 7 — Approval gate

**Command:**
```bash
ao-kernel approval request --run <run_id> --gate pre_apply
```

Run transitions to `waiting_approval`. An approval token is minted (distinct from any adapter `interrupt_token`). A human reviews the diff and CI result.

**Evidence events:**
- `step_started` for `await_approval`
- `approval_requested` (actor: `ao-kernel`, payload: gate, diff summary, CI summary)
- (state is `waiting_approval`, run paused)

**Resume:**
```bash
ao-kernel approval respond --run <run_id> --token <approval_token> --decision granted --actor halildeu
```

**Evidence events on resume:**
- `approval_granted` (actor: `human`, payload: actor id, decision, any attached notes)
- `step_completed` for `await_approval`

### Step 8 — Apply + commit

**Command:**
```bash
ao-kernel patch apply --run <run_id>
```

Diff is applied to the worktree, a commit is created in a fresh topic branch (`ao-kernel/run-<short-run-id>`), signed or unsigned per workspace policy.

**Evidence events:**
- `step_started` for `apply_patch`
- `diff_applied` (payload: commit SHA, branch name, files touched)
- `step_completed` for `apply_patch`

### Step 9 — PR creation

**Command:**
```bash
ao-kernel pr open --run <run_id>
```

Delegates to the `gh-cli-pr` adapter. PR title pulls from the workflow intent; body includes a link to the evidence timeline.

**Evidence events:**
- `step_started` for `open_pr`
- `policy_checked` for `gh-cli-pr` adapter's `secrets.allowlist_secret_ids` (must include `GH_TOKEN`)
- `adapter_invoked` for `gh-cli-pr`
- `adapter_returned` for `gh-cli-pr` (payload: PR URL, PR number)
- `pr_opened` (actor: `adapter`, payload: PR URL, base SHA, head SHA)
- `step_completed` for `open_pr`

### Step 10 — Workflow complete

Run transitions to `completed` automatically after `pr_opened`.

**Evidence events:**
- `workflow_completed` (actor: `ao-kernel`)

### Step 11 — Evidence replay

**Command:**
```bash
ao-kernel evidence timeline --run <run_id>
```

Prints the chronological event list — one line per event with `ts`, `kind`, `actor`, and a one-line payload summary. See [EVIDENCE-TIMELINE.md §8](../EVIDENCE-TIMELINE.md).

Variations:
```bash
ao-kernel evidence timeline --run <run_id> --format json         # full JSON dump
ao-kernel evidence timeline --run <run_id> --replay inspect       # read-only replay, diff recorded vs replayed state
ao-kernel evidence timeline --run <run_id> --verify-manifest      # SHA-256 integrity check
```

---

## 3. Expected Evidence Event Counts (happy path)

| Event kind | Expected count |
|---|---|
| `workflow_started` | 1 |
| `workflow_completed` | 1 |
| `workflow_failed` | 0 |
| `step_started` | ≥ 9 (one per step) |
| `step_completed` | ≥ 9 |
| `step_failed` | 0 |
| `adapter_invoked` | 2 (Claude Code CLI + gh-cli-pr) |
| `adapter_returned` | 2 |
| `diff_previewed` | 1 |
| `diff_applied` | 1 |
| `approval_requested` | 1 (pre_apply gate) |
| `approval_granted` | 1 |
| `approval_denied` | 0 |
| `test_executed` | 1 |
| `pr_opened` | 1 |
| `policy_checked` | ≥ 5 (worktree, command, env, secrets, gh-pr secret) |
| `policy_denied` | 0 (happy path) |

Total events on the happy path: ≈ 36.

---

## 4. Failure Modes + Recovery

### 4.1 Adapter invocation failure

Symptom: `adapter_returned` with `status: "failed"` and `error.category: "invocation_failed"` or `"adapter_crash"`.

Recovery (not part of PR-A0 spec, but the demo workflow in PR-A6 handles it):
- Retry once with the original input envelope.
- If second failure: transition the step to `step_failed`, bubble to `workflow_failed`.
- No auto-fallback to a different adapter (that is a workflow-registry decision, FAZ-B).

### 4.2 CI gate denied

Symptom: `test_executed` with non-zero exit code → `step_failed` for `ci_gate` → `workflow_failed` with `error.category: "ci_failed"`.

Recovery: in an iterative demo workflow, re-invoke the adapter with the test output appended. Not automatic in FAZ-A PR-A6; human can start a new run with the failure context.

### 4.3 Approval denied or timeout

Symptom: `approval_denied` event (actor: `human` or `system` on timeout). Run transitions to `cancelled` with `error.category: "approval_denied"`.

Evidence is preserved; a new run can reuse the prior diff via a new `adapter_invoked` if desired.

### 4.4 Worktree policy violation

Symptom: `policy_denied` event with one of `secret_leak_detected`, `cwd_escape_attempted`, `command_not_in_allowlist`, `unknown_env_key`.

Run transitions to `failed` with `error.category: "policy_denied"`. Worktree is preserved under `.ao/runs/{run_id}/worktree` for forensics; cleanup follows `worktree.cleanup_on_completion`.

### 4.5 Budget exhausted

Symptom: adapter invocation or run-level budget axis hits its limit. `adapter_returned` with `status: "failed"` and `error.category: "budget_exhausted"`, bubbling to `workflow_failed` with the same category.

`fail_closed_on_exhaust: true` is MUST: the run does NOT silently continue with reduced budget.

---

## 5. Acceptance Checklist (FAZ-A release gate)

Mirrors [TRANCHE-STRATEGY-V2.md §10](../.claude/plans/TRANCHE-STRATEGY-V2.md):

- [ ] End-to-end demo flow passes locally on the sample repository.
- [ ] Three adapter examples work:
  - [ ] `claude-code-cli` (or `codex-stub` for CI determinism)
  - [ ] `codex-stub`
  - [ ] `gh-cli-pr`
- [ ] Docs published: tutorial (this file) + three adapter walkthroughs (ADAPTERS.md).
- [ ] `ao-kernel evidence timeline` CLI works (happy path + `--replay inspect` + `--verify-manifest`).
- [ ] Worktree profile test matrix (see [WORKTREE-PROFILE.md §10](../WORKTREE-PROFILE.md)):
  - [ ] env allowlist violation denied
  - [ ] command allowlist violation denied
  - [ ] CWD escape denied
  - [ ] secret deny-by-default enforced
- [ ] CI gate deny/allow fixture test: policy-allowed status passes, policy-denied status blocks.
- [ ] COMPETITOR-MATRIX.md published and reviewed (prevents "rakipsiz" regression, CNS-016 W3).
- [ ] ≥ 1000 tests green (baseline: 1004 at v3.0.0).
- [ ] Branch coverage ≥ 85% (ratchet gate).

---

## 6. Adapter Walkthroughs

The three adapters exercised above have full configuration and trouble-shooting walkthroughs in [ADAPTERS.md](../ADAPTERS.md):

- Walkthrough 1 — Claude Code CLI (`adapter_kind: "claude-code-cli"`, CLI transport, Anthropic API key)
- Walkthrough 2 — Codex stub (`adapter_kind: "codex-stub"`, in-process, deterministic for CI)
- Walkthrough 3 — gh CLI PR path (`adapter_kind: "gh-cli-pr"`, typed VCS/PR connector — not a full coding agent)

Custom adapters (claude- or codex-compatible runtimes, GitHub Copilot cloud agent, Cursor background agent, aider, devin, windsurf-cascade) follow the "Writing a Custom Adapter" section in ADAPTERS.md.

---

## 7. Cross-References

- [docs/ADAPTERS.md](../ADAPTERS.md) — adapter contract human-readable + three walkthroughs
- [docs/WORKTREE-PROFILE.md](../WORKTREE-PROFILE.md) — worktree execution profile operator guide
- [docs/EVIDENCE-TIMELINE.md](../EVIDENCE-TIMELINE.md) — event taxonomy + replay contract
- [docs/COMPETITOR-MATRIX.md](../COMPETITOR-MATRIX.md) — live competitor/adapter matrix
- `ao_kernel/defaults/schemas/agent-adapter-contract.schema.v1.json`
- `ao_kernel/defaults/schemas/workflow-run.schema.v1.json`
- `ao_kernel/defaults/policies/policy_worktree_profile.v1.json`
