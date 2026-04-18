# Policy Simulation Harness

`ao_kernel.policy_sim` runs dry-run evaluations of proposed policy changes against a set of scenario fixtures. It reuses the real `governance.check_policy` code path and the executor's policy primitives, but executes them under a 24-sentinel purity guard that fail-closes on any side effect (evidence emit, worktree creation, subprocess spawn, filesystem write, network I/O, tempfile allocation, importlib resource extraction).

The harness answers operator questions like:

- "If I apply this `policy_worktree_profile.v1.json` patch, how many of my fixtures flip from allow to deny?"
- "Does my proposed `policy_autonomy.v1.json` still block unknown intents?"
- "My PR touches two policies at once — does the combined change tighten any scenario I currently allow?"

## 1. Scope

- **Mid-depth simulation** — `governance.check_policy` plus
  `executor.policy_enforcer.build_sandbox` + `resolve_allowed_secrets` +
  `check_http_header_exposure` are exercised. `validate_command`
  is deferred for v1 (plan §2.3 Q2 — its host-FS dependence makes
  results host-specific; a future opt-in surfaces a
  `host_fs_fingerprint` on the report).
- **Multi-policy per run** — a `ScenarioSet` can mix scenarios
  targeting different policies; each scenario names its own
  `target_policy_name` (plan v3 bulgu 1 absorb).
- **Full-replacement proposed policies only** — RFC 7396 merge
  patch is deferred. The simulator compares a baseline dict to a
  proposed dict in full.
- **JSON-only scenario format** (plan v3 Q1 absorb). YAML
  support is a candidate for a post-B4 optional extra.

## 2. Invariants

- **No side effects** during simulation. `_purity.py` patches 24
  sentinels spanning subprocess, filesystem, tempfile, socket,
  `importlib.resources.as_file`, and every evidence-emit
  re-export path. Any trip raises `PolicySimSideEffectError`
  carrying the sentinel name.
- **Policy loader fail-closed** per
  `ao_kernel.cost.policy::_validate` + `load_cost_policy`
  contract. The simulator never swallows loader exceptions;
  structurally-broken proposed policies raise
  `ProposedPolicyInvalidError` before any scenario runs.
- **Canonical policy hash** matches `executor/artifacts.py:66-74`
  — `sort_keys=True`, `ensure_ascii=False`,
  `separators=(",", ":")`, UTF-8 + SHA-256 (plan v3 N3 absorb).
  Cross-module drift surfaces as a contract-test failure.
- **Adapter snapshot pre-captured** before entering the purity
  context. Bundled adapters (`codex-stub` et al.) remain
  discoverable without tripping the
  `importlib.resources.as_file` sentinel (plan v3 iter-2
  blocker absorb).
- `_KINDS == 27` in `executor/evidence_emitter.py:46` is
  preserved — simulation emits no new evidence kinds (plan v3
  bulgu 6 absorb).

## 3. Scenario Model

Scenarios are JSON documents validated against `policy-sim-scenario.schema.v1.json`.

```json
{
  "scenario_id": "adapter_http_with_secret",
  "description": "HTTP adapter binds auth_secret_id_ref.",
  "kind": "executor_primitive",
  "target_policy_name": "policy_worktree_profile.v1.json",
  "inputs": {
    "adapter_manifest_ref": "codex-stub",
    "parent_env": {
      "PATH": "/usr/bin:/usr/local/bin",
      "ANTHROPIC_API_KEY": "sk-test-redacted"
    },
    "requested_command": null,
    "requested_cwd": null
  },
  "expected_baseline": {
    "violations_expected": [],
    "decision_expected": "allow"
  }
}
```

### Kinds

- `executor_primitive` — invokes `build_sandbox` +
  `resolve_allowed_secrets` + `check_http_header_exposure`
  against `target_policy_name` (must be
  `policy_worktree_profile.v1.json`).
- `governance_policy` — invokes `governance.check_policy` against
  `target_policy_name` with the scenario's `inputs.action` wrapped
  into `{"intent": action}`.
- `combined` — both; requires `target_policy_names` (plural).

### Bundled fixtures

Three reference scenarios ship under
`ao_kernel/defaults/policies/policy_sim_scenarios/`:

1. `adapter_http_with_secret` — executor_primitive, expect allow.
2. `path_poisoned_python` — executor_primitive, expect deny when
   `--enable-host-fs-probes` is on. Currently allow under v1
   (validate_command deferred).
3. `autonomy_unknown_intent` — governance_policy, expect deny.

## 4. Public API

```python
from pathlib import Path
from ao_kernel.policy_sim import (
    BaselineSource,
    load_bundled_scenarios,
    simulate_policy_change,
)

report = simulate_policy_change(
    project_root=Path.cwd(),
    scenarios=load_bundled_scenarios(),
    proposed_policies={
        "policy_autonomy.v1.json": {
            "version": "v1",
            "intents": ["AUTONOMY_UNKNOWN_INTENT"],
            "defaults": {"mode": "allow"},
        },
    },
    baseline_source=BaselineSource.BUNDLED,
)

for delta in report.notable_deltas:
    print(delta.scenario_id, delta.transition)
```

### Baseline sources

- `BaselineSource.BUNDLED` — read baseline policies from
  `ao_kernel/defaults/policies/`.
- `BaselineSource.WORKSPACE_OVERRIDE` — read from
  `<project_root>/.ao/policies/<name>` via
  `load_with_override` (disk read).
- `BaselineSource.EXPLICIT` — use the caller-supplied
  `baseline_overrides` dict verbatim (no disk I/O).

### Errors

- `PolicySimSideEffectError(sentinel_name, context)` — the
  purity guard tripped.
- `PolicySimReentrantError` — a nested
  `pure_execution_context` was attempted.
- `ScenarioValidationError(scenario_id, reason)` — scenario JSON
  failed schema checks.
- `ScenarioAdapterMissingError(scenario_id, adapter_ref)` — the
  scenario references an adapter the registry snapshot does not
  know.
- `TargetPolicyNotFoundError(scenario_id, policy_name)` — the
  scenario's `target_policy_name` is not present in
  `proposed_policies`, `baseline_overrides`, nor bundled
  defaults.
- `ProposedPolicyInvalidError(policy_name, violations)` —
  structural shape checks (driven by
  `_policy_shape_registry`) failed.
- `SimulationAbortedError(scenario_ids, causes)` — aggregate
  wrapper used when per-scenario evaluation raised one or more
  unrecoverable errors.
- `ReportSerializationError(field_path, value_type)` — a
  non-normalisable value escaped
  `DiffReport.to_dict`.

## 5. CLI

```
ao-kernel policy-sim run \
  --scenarios <file-or-dir> \
  --proposed-policies <dir> \
  [--baseline-source bundled|workspace_override|explicit] \
  [--baseline-overrides <dir>] \
  [--format json|text] \
  [--output <path>] \
  [--enable-host-fs-probes] \
  [--project-root <path>]
```

### Exit codes

- `0` — success, no tightening transitions.
- `1` — user error (bad scenario file, structurally invalid
  proposed policy, unknown baseline source, adapter reference
  missing).
- `2` — internal (purity violation, reentrancy, simulator
  abort).
- `3` — success with warning (≥1 allow→deny transition).

## 6. Report Shape

`DiffReport.to_dict()` normalises `Path` → `str`, `frozenset`
→ sorted `list`, compiled regex → `.pattern`, and manifest
`source_path` → relative string (plan v3 N4 absorb). Output
example:

```json
{
  "schema_version": "v1",
  "emitted_at": "2026-04-18T00:55:19+00:00",
  "scenarios_evaluated": 3,
  "baseline_policy_hashes": {
    "policy_autonomy.v1.json": "sha256:...",
    "policy_worktree_profile.v1.json": "sha256:..."
  },
  "proposed_policy_hashes": { "...": "sha256:..." },
  "transitions": {
    "allow→allow": 2,
    "deny→deny": 1,
    "allow→deny": 0,
    "deny→allow": 0,
    "error": 0
  },
  "transitions_by_policy": {
    "policy_autonomy.v1.json": { "deny→deny": 1 },
    "policy_worktree_profile.v1.json": { "allow→allow": 2 }
  },
  "host_fs_dependent": false,
  "host_fs_fingerprint": null,
  "deltas": [...]
}
```

## 7. Scope Dışı (post-B4)

- **Full `Executor.run_step` dry-run** → benchmark-suite work
  (B7 or later); requires adapter mock harness.
- **RFC 7396 merge-patch proposed policies** → v2.
- **YAML scenario support** → post-B4 optional extra.
- **Auto-discovery of scenarios** from
  `<workspace>/.ao/policy_sim/scenarios/` → post-B4 v1.1.
- **Evidence emit for simulation runs** — **NEVER** under the
  purity contract.
- **Time-travel** (past policy versions from git history) →
  FAZ-C.
- **Web UI** — **NEVER**; CLI + library only.

## 8. Related

- `docs/WORKTREE-PROFILE.md` — baseline `policy_worktree_profile`
  contract that executor_primitive scenarios exercise.
- `docs/COST-MODEL.md` §6 — PR-B3 cost-aware routing; potential
  future scenario target.
- `.claude/plans/PR-B4-DRAFT-PLAN.md` v3 — Codex adversarial
  review audit trail.
