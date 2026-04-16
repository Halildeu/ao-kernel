# Evidence Timeline

Every governed workflow run in ao-kernel emits an append-only JSONL stream of evidence events. The stream is the single source of truth for what happened: what the agent was asked, what it returned, which policies fired, what was applied, who approved, and what the CI gate said. The `ao-kernel evidence timeline` CLI (Tranche A PR-A5) reads that stream and reconstructs a chronological, replayable view of the run.

This document is the contract: what events exist, what shape they take, where they land on disk, and what replay guarantees hold.

---

## 1. Purpose

The evidence timeline exists to answer four questions without reading code:

1. **What happened?** — chronological event list for the run.
2. **Can we reproduce it?** — deterministic replay of the workflow state machine against the event stream.
3. **What did the policies decide?** — every `policy_checked` and `policy_denied` event is in the stream.
4. **What did a human approve?** — every `approval_requested` / `approval_granted` / `approval_denied` event is in the stream with actor identity.

The timeline replaces ad-hoc log reading and makes governance auditable: a reviewer can replay a past run, inspect every policy decision, and verify that the sequence of state transitions followed the contract.

### Guarantees

- **Immutable**: events are append-only; an event is never mutated after it lands.
- **Integrity-checked**: workspace artefact evidence (workflow runs) carries a SHA-256 manifest (CLAUDE.md §2). MCP events are fsync'd JSONL without a manifest (deferred to Tranche D).
- **Redacted at emission**: secrets and secret-shaped content are scrubbed before the event reaches disk, per `policy_worktree_profile.evidence_redaction` rules.
- **Deterministic under replay** for the subset of events marked `replay_safe: true` (see §6).

---

## 2. Event Taxonomy — 18 Event Types, 8 Categories

Every event carries a `kind` field from this closed set. Additional kinds may appear in FAZ-B+ (for ops hardening and cron workflows) but FAZ-A ships exactly these 18 (PR-A0 initial 17 + PR-A4 `diff_rolled_back`).

### Workflow lifecycle (3)

| Kind | Emitted when | Actor |
|---|---|---|
| `workflow_started` | Workflow run transitions from `created` to `running` for the first time. | `ao-kernel` |
| `workflow_completed` | Workflow run transitions to terminal `completed` state. | `ao-kernel` |
| `workflow_failed` | Workflow run transitions to terminal `failed` or `cancelled` state. | `ao-kernel` |

### Step lifecycle (3)

| Kind | Emitted when | Actor |
|---|---|---|
| `step_started` | A step transitions from `created` to `running`. | `ao-kernel` |
| `step_completed` | A step transitions to terminal `completed` state. | `ao-kernel` |
| `step_failed` | A step transitions to terminal `failed`, `cancelled`, or `skipped` state. | `ao-kernel` |

### Adapter (2)

| Kind | Emitted when | Actor |
|---|---|---|
| `adapter_invoked` | Worktree executor has resolved policy, started the subprocess or HTTP request, and the adapter now owns the turn. | `ao-kernel` |
| `adapter_returned` | Adapter has produced `output_envelope` (regardless of `status`). | `adapter` (via ao-kernel) |

### Diff (3)

| Kind | Emitted when | Actor |
|---|---|---|
| `diff_previewed` | Adapter's `output_envelope.diff` has been rendered for human or CI review. | `ao-kernel` |
| `diff_applied` | Diff has been applied to the worktree (commit not yet created). | `ao-kernel` |
| `diff_rolled_back` | A previously applied patch has been reverted via its reverse-diff artefact (`{run_dir}/patches/{patch_id}.revdiff`). Idempotent skip cases do NOT emit this event. Introduced in PR-A4. | `ao-kernel` |

### Approval (3)

| Kind | Emitted when | Actor |
|---|---|---|
| `approval_requested` | Governance gate opens a HITL approval (state transitions to `waiting_approval`). | `ao-kernel` |
| `approval_granted` | Approver returns `granted`; state transitions forward. | `human` |
| `approval_denied` | Approver returns `denied` or approval times out; state transitions to `cancelled` or `failed`. | `human` or `system` |

### Test (1)

| Kind | Emitted when | Actor |
|---|---|---|
| `test_executed` | The CI gate step completes (either pass or fail). Payload includes exit code and summary. | `system` |

### PR (1)

| Kind | Emitted when | Actor |
|---|---|---|
| `pr_opened` | `gh-cli-pr` or native adapter has successfully opened a PR. Payload includes PR URL and base SHA. | `ao-kernel` or `adapter` |

### Policy (2)

| Kind | Emitted when | Actor |
|---|---|---|
| `policy_checked` | A policy check evaluated (both allow and deny outcomes emit this in `report_only` mode; in `block` mode, denies emit `policy_denied` instead). | `ao-kernel` |
| `policy_denied` | A policy check denied an operation in `block` mode. Run transitions to `failed` with `error.category: "policy_denied"`. | `ao-kernel` |

> **Total: 18 events across 8 categories.** This is the closed set for FAZ-A (PR-A0 initial 17 + PR-A4 `diff_rolled_back`).

---

## 3. Event Envelope

Every event is a single JSON object on one line of JSONL. The envelope shape is:

```json
{
  "event_id": "01HZK3Q8R9Y4M7V2A0N5C6B1X8",
  "run_id": "a1b2c3d4-e5f6-4789-9012-3456789abcde",
  "step_id": "invoke_adapter_claude_code",
  "ts": "2026-04-15T12:34:56.789+03:00",
  "actor": "ao-kernel",
  "kind": "adapter_invoked",
  "payload": {
    "adapter_id": "claude-code-cli",
    "invocation_summary": "claude code run --prompt <path>",
    "budget_remaining": {"tokens": 48000, "time_seconds": 540, "cost_usd": 4.2}
  },
  "payload_hash": "7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069",
  "replay_safe": true
}
```

### Field semantics

| Field | Type | Required | Description |
|---|---|---|---|
| `event_id` | string (URL-safe token) | ✓ | Opaque per-event identifier produced via `secrets.token_urlsafe(48)` (PR-A3). Consumers MUST NOT assume monotonicity; use the `seq` field for ordering. |
| `run_id` | UUIDv4 | ✓ | The workflow run this event belongs to. |
| `step_id` | string | — | Step identifier if the event is tied to a specific step. Absent for workflow-lifecycle events. |
| `ts` | ISO-8601 | ✓ | Wall-clock timestamp of event emission. |
| `actor` | string | ✓ | One of `adapter`, `ao-kernel`, `human`, `system`. |
| `kind` | string | ✓ | One of the 18 event kinds. |
| `payload` | object | ✓ | Event-specific payload. Redacted per `policy_worktree_profile.evidence_redaction`. |
| `payload_hash` | hex string (SHA-256) | ✓ | Hash of the (redacted) payload, for integrity manifest. |
| `replay_safe` | boolean | — | True if the event is deterministic under replay (see §6). |

Once written, an event is immutable. Correction or retraction is implemented by emitting a follow-up event (e.g., a `step_failed` that supersedes an earlier `step_completed`). The timeline is append-only.

---

## 4. JSONL File Layout

Three distinct evidence surfaces live under `.ao/evidence/`:

### 4.1 MCP events (pre-existing, CLAUDE.md §2)

- Path: `.ao/evidence/mcp/YYYY-MM-DD.jsonl`
- Scope: every MCP tool dispatch emits one event (tool name, envelope, duration, redacted params).
- Integrity: JSONL + fsync only. **No SHA-256 manifest** (deferred to Tranche D).
- Rotation: daily.

### 4.2 Workflow timeline events (new in PR-A5)

- Path: `.ao/evidence/workflows/{run_id}/events.jsonl`
- Scope: the 18 event kinds described in §2 for one workflow run.
- Integrity: JSONL + SHA-256 manifest (see §5). Workspace artefact convention.
- Rotation: per-run (one file per workflow run).

### 4.3 Adapter logs (new in PR-A5)

- Path: `.ao/evidence/workflows/{run_id}/adapter-{adapter_id}.jsonl`
- Scope: adapter-specific logs that the adapter itself wants captured (stdout, stderr, tool calls). Redacted at capture time.
- Integrity: JSONL + fsync; folded into the workflow's SHA-256 manifest under its `logs_ref`.
- Rotation: per-invocation (one file per adapter invocation per run).

### 4.4 Directory shape

```
.ao/
└── evidence/
    ├── mcp/
    │   └── 2026-04-15.jsonl                       # pre-existing, CLAUDE.md §2
    └── workflows/
        └── a1b2c3d4-e5f6-4789-9012-3456789abcde/
            ├── events.jsonl                       # workflow timeline (§4.2)
            ├── adapter-claude-code-cli.jsonl      # adapter logs (§4.3)
            ├── adapter-gh-cli-pr.jsonl
            └── manifest.json                      # SHA-256 integrity manifest (§5)
```

---

## 5. Integrity Manifest

**Scope note (PR-A3 revision):** The integrity manifest is **generated on demand by the PR-A5 evidence-timeline CLI** after a run completes (or at user request). PR-A3 (worktree executor) writes events to JSONL append-only with a per-run lock + fsync; it does NOT maintain a manifest file. The manifest is a separate PR-A5 artefact that re-hashes the artefacts at query time, so PR-A3 stays free of cross-file coordination cost.

Workflow run artefacts (events.jsonl + adapter logs) carry a SHA-256 integrity manifest at `.ao/evidence/workflows/{run_id}/manifest.json` (generated on demand):

```json
{
  "version": "1",
  "run_id": "a1b2c3d4-e5f6-4789-9012-3456789abcde",
  "generated_at": "2026-04-16T12:45:00+00:00",
  "files": [
    {
      "path": "events.jsonl",
      "sha256": "7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069",
      "bytes": 48291
    },
    {
      "path": "adapter-claude-code-cli.jsonl",
      "sha256": "a3f5c9e0...",
      "bytes": 12408
    },
    {
      "path": "artifacts/invoke_coding_agent-attempt1.json",
      "sha256": "b4d2e1f0...",
      "bytes": 1024
    },
    {
      "path": "patches/patch-abc.revdiff",
      "sha256": "c5e3f2a1...",
      "bytes": 512
    }
  ]
}
```

**Manifest scope (PR-A5):** `events.jsonl` + `adapter-*.jsonl` + `artifacts/**/*.json` + `patches/*.revdiff`. Excludes: `manifest.json`, `*.lock`, `*.tmp`.

The manifest is **generated on demand** by `ao-kernel evidence generate-manifest --run <run_id>`. PR-A3 emits events append-only (lock + fsync) without maintaining a manifest file; the CLI re-hashes the artefacts at command time so the hot write path stays free of cross-file coordination. `ao-kernel evidence verify-manifest --run <run_id>` recomputes SHA-256s and exits non-zero on mismatch (exit 1), outdated manifest (exit 2), or missing manifest (exit 3). Replay tooling verifies the manifest SHA-256s before trusting the stream.

**MCP events do NOT carry a manifest** (per CLAUDE.md §2, Tranche D scope). The dual-form evidence contract is: workspace artefacts have manifests, MCP events are fsync'd JSONL only.

---

## 6. Replay Contract

Replay is the act of reading the event stream and reconstructing the workflow-run state machine from `created` forward.

### Deterministic replay

Events with `replay_safe: true` produce identical state transitions on every replay. This includes:

- All workflow and step lifecycle events (the state machine is a function of the input event).
- Policy check results (policies are pure over their inputs).
- Diff preview and apply (the diff is in the event payload).

### Non-deterministic sources (not replay-safe)

- **Adapter invocation** — the external agent runtime is non-deterministic (LLM sampling, network jitter). The `adapter_returned` event captures the output, so downstream state is deterministic given the output, but a fresh invocation is not. Adapter events are NOT marked `replay_safe: true`.
- **Human approval** — an approval decision may differ on replay (the person may pick differently). Events carry the recorded decision; replay uses the recorded value, but a truly fresh execution would re-ask the human.
- **External API calls** (e.g., `gh pr create`) — mutating a remote system is not replay-safe.
- **Wall-clock time** — `ts` values embed real time; if replay uses recorded `ts`, determinism holds; if replay wants to re-run in "now" mode, timestamps diverge.

### Replay modes (Tranche A PR-A5 CLI)

- `--replay inspect` — read-only: reconstruct state, print diff between recorded and replayed state. No mutations.
- `--replay dry-run` — simulate state transitions; emit would-be events to stdout, no filesystem or API writes.
- `--replay full` — deny by default; explicit flag required; only runs events with `replay_safe: true`.

### Predicate replay (FAZ-D #9)

For conditional branching (FAZ-D feature #9), branch predicates emit deterministic `branch_decided` events (future enum addition). Replay verifies the predicate re-evaluates to the same branch decision, proving the workflow is replay-deterministic at the control-flow level.

---

## 7. Redaction Rules

Every event payload is subject to `policy_worktree_profile.evidence_redaction` before serialization:

- **Environment variable names** matching the `env_keys_matching` regex (`(?i).*(token|secret|key|password|credential).*`) have their values replaced with `***REDACTED***`.
- **Stdout / stderr / payload text** matching any pattern in `stdout_patterns` (6 P0 patterns: OpenAI, Anthropic, GitHub PAT, Slack bot, OAuth Bearer, HTTP Basic) has the match replaced with `***REDACTED***`.
- **Adapter input `workspace_view` contents** never appear in the event payload — only the shape and file count. If an adapter quotes a file into its `output_envelope.diff`, the diff text is redacted but the file itself is not replicated into the event.

Redaction is a defense-in-depth layer. The primary defense is `policy_worktree_profile.secrets.denied_exposure_modes`: secrets never reach a surface that gets logged. Redaction catches operator mistakes and residual leaks.

---

## 8. CLI Reference — `ao-kernel evidence` (PR-A5 shipped)

Four subcommands:

```bash
# Timeline — chronological event table or NDJSON
ao-kernel evidence timeline --run <run_id>
ao-kernel evidence timeline --run <run_id> --format json
ao-kernel evidence timeline --run <run_id> --filter-kind step_started,step_completed
ao-kernel evidence timeline --run <run_id> --filter-actor adapter
ao-kernel evidence timeline --run <run_id> --limit 20

# Replay — inferred state trace + replay_safe annotation
ao-kernel evidence replay --run <run_id> --mode inspect
ao-kernel evidence replay --run <run_id> --mode dry-run

# Manifest — on-demand SHA-256 generation
ao-kernel evidence generate-manifest --run <run_id>

# Verify — recompute + compare
ao-kernel evidence verify-manifest --run <run_id>
ao-kernel evidence verify-manifest --run <run_id> --generate-if-missing
```

**Timeline default output:** `seq | ts | kind | actor | step_id | payload_summary` (96-char payload truncation). `--format json` emits full event NDJSON. Secrets are already redacted in the source JSONL; the CLI does not re-redact.

**Replay:** produces an **inferred state trace** — not an exact recorded state. `state_source` per transition is `event` (explicit like `workflow_started → running`), `inferred` (e.g., `diff_applied → applying`), or `synthetic` (driver CAS chain with no matching evidence event). Illegal transitions produce warnings, not hard failures.

**Verify exit codes:** `0` = all match; `1` = hash mismatch or missing listed file; `2` = manifest outdated (new in-scope file); `3` = `manifest.json` missing.

---

## 9. Cross-References

- `ao_kernel/defaults/schemas/workflow-run.schema.v1.json` — the canonical run record this timeline reconstructs.
- `ao_kernel/defaults/schemas/agent-adapter-contract.schema.v1.json` — `output_envelope.evidence_events` is the adapter's handle into this timeline.
- `ao_kernel/defaults/policies/policy_worktree_profile.v1.json` — `evidence_redaction` patterns this timeline honors.
- `docs/WORKTREE-PROFILE.md` — operator-facing walkthrough of the redaction rules.
- `docs/DEMO-SCRIPT.md` — the E2E flow that emits every event kind once.
- `CLAUDE.md` §2 — the dual-form evidence invariant (workspace manifest vs MCP fsync-only).
