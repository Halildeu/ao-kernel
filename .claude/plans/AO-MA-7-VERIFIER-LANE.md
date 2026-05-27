# AO-MA-7 — Verifier lane (deterministic; no LLM call; metadata-only secret scan)

**Status:** plan-time iter-1 AGREE absorbed (Codex thread `019e6996-4064-74a1-8a74-27ef14548a42`; `ready_for_impl: true` with must_close pins). Implementation in progress.
**Branch:** `codex/ao-ma-7-verifier-lane`
**Decision artifact:** `ao_ma_7_verifier_deterministic_metadata_secret_scan_v1`
**Parent:** AO-MA-1 §8 phased plan slice AO-MA-7
**Support impact:** none

## Purpose

AO-MA-1 §8 plan AO-MA-7 = "Verifier lane: GPP guard checks, secret scan, diff scope, and artifact hash reporting." AO-MA-5 v1 (#654) Integrator consumes `verification_report.v1.json`; AO-MA-7 **produces** it.

**Codex iter-1 AGREE absorb (kabul edilmiş tasarım):**

1. **L1 deterministic, no LLM call** — 4 check'lerin tümü pure-Python; LLM judgment yok
2. **A2 modular helpers** — `_check_gpp_guards`, `_check_secret_scan`, `_check_diff_scope`, `_compute_artifact_hashes`; `Verifier.verify()` koordine
3. **S1 regex-based secret scan + metadata-only scope** — common patterns (sk-…, BEGIN PRIVATE KEY, aws_access_key_id, etc.) + `worker_result.no_secret_attestation.secrets_recorded` check; **source file content scan NOT in v1** (explicit detail string)
4. **Pure static diff scope** — `set(worker_result.actual_changed_files) ⊆ set(worker_result.declared_write_set)` + `worker_result.declared_write_set == task_graph.tasks[task_id].declared_write_set` cross-ref (otherwise inflation defeats check)
5. **H1 artifact_hashes** — `{path, sha256}` only; no `role` field (schema rejects additionalProperties)
6. **CLI**: `--worker-result` required, `--review-verdict` optional, `--gpp-status` optional default `.claude/plans/gpp_status.v1.json`, `--verifier-provider` defaults to `tool` (no-LLM signal); same-provider-as-implementer fails closed
7. **HARD RULE pins** (AO-MA-6 pattern): no `subprocess` import in verifier module, no LLM literals, no `gh`/`git push`, no PR/GitHub fetch, no AO-MA-5/6 edits

**Must_close_before_impl (Codex iter-1 plan pins):**

1. `secret_scan.detail` says **"AO-MA JSON artifacts / metadata scanned; changed source file contents were not scanned in v1"** — explicit scope statement
2. `scope_check` includes task_graph cross-ref, not just worker_result internal subset
3. GPP guard reads from ALL of: `manifest.guard_flags`, `task_graph.guard_flags`, `worker_result.guard_flags`, optional `review_verdict.guard_flags`, `.claude/plans/gpp_status.v1.json` allowed flags. Any non-False → `failed_checks` entry
4. `artifact_hashes` H1 format `{path, sha256}` only — no `role`
5. `commands` use deterministic check names: `schema_validation`, `gpp_guard_check`, `metadata_secret_scan`, `diff_scope_static_check`, `artifact_hashing`. Outcomes: pass / fail / skipped
6. Exit codes: 0 all-pass + emitted, 1 schema-valid failed report emitted, 2 trust-boundary, 3 emit failure
7. No `subprocess` to `gpp_next.py` or `git`; JSON parse only

## Module layout (AO-MA-6 pattern follow)

```
ao_kernel/orchestration/
  verifier.py                       # Verifier class + VerificationInputs + VerificationResult
                                    # + 4 helpers (_check_gpp_guards, _check_secret_scan,
                                    #   _check_diff_scope, _compute_artifact_hashes)
  verification_report_writer.py     # emit + schema validate + atomic write
  cli_handlers.py                   # extend: cmd_orchestration_verify
```

## CLI surface

```bash
ao-kernel orchestration verify \
  --manifest <path>                              # required
  --task-id <id>                                 # required
  --worker-result <task_id>=<path>               # required (≥1)
  --verifier-agent-id <id>                       # required
  [--verifier-provider <enum>]                   # default: tool (no-LLM signal)
  --verifier-session-id <id>                     # required
  [--review-verdict <path>]                      # optional; verifier reads + hashes
  [--gpp-status <path>]                          # default: <repo>/.claude/plans/gpp_status.v1.json
  [--repo-root <path>]
  [--format text|json]
```

## Secret scan patterns (S1, regex; v1 fixed pattern set)

```
# AWS
AKIA[0-9A-Z]{16}                     # AWS Access Key ID
aws_secret_access_key\s*=\s*[A-Za-z0-9/+=]{40}

# GitHub
ghp_[A-Za-z0-9]{36,}
gho_[A-Za-z0-9]{36,}
github_pat_[A-Za-z0-9_]{82}

# OpenAI / Anthropic / xAI
sk-[A-Za-z0-9]{20,}
sk-ant-[A-Za-z0-9_-]{40,}
xai-[A-Za-z0-9]{40,}

# Google API
AIza[0-9A-Za-z_-]{35}

# Generic
-----BEGIN (RSA|DSA|EC|OPENSSH|PRIVATE) (PRIVATE )?KEY-----
-----BEGIN PGP PRIVATE KEY BLOCK-----
```

Patterns scan **only AO-MA artifact JSON content** (worker_result, review_verdict, task_graph, manifest, gpp_status). NOT changed source files.

False-positive defense: AO-MA artifacts contain `sha256:[0-9a-f]{64}` hashes and `git_sha` 40-char hex. Regex set explicitly excludes those (more specific patterns; no Shannon entropy).

## GPP guard check

For each of `support_widening`, `production_platform_claim`, `live_adapter_execution`:
- `manifest.guard_flags[X] != False` → failed_checks entry
- `task_graph.guard_flags[X] != False` → failed_checks entry
- `worker_result.guard_flags[X] != False` → failed_checks entry
- `review_verdict.guard_flags[X] != False` (if provided) → failed_checks entry
- `gpp_status.v1.json` `current_wp` or root allowlist → if applicable allowed_flag is True for any of the three → failed_checks entry

## Diff scope check

```python
def _check_diff_scope(worker_result, task_graph, task_id):
    # Cross-ref worker's declared_write_set matches task_graph's
    task = next((t for t in task_graph["tasks"] if t["task_id"] == task_id), None)
    if task is None:
        return ("diff_scope_static_check", "fail", ["task_id not found in task_graph"])
    if set(worker_result["declared_write_set"]) != set(task["declared_write_set"]):
        return ("diff_scope_static_check", "fail", ["worker_result.declared_write_set != task_graph.tasks[task_id].declared_write_set"])
    actual = set(worker_result.get("actual_changed_files", []))
    declared = set(worker_result["declared_write_set"])
    if not actual.issubset(declared):
        extras = sorted(actual - declared)
        return ("diff_scope_static_check", "fail", [f"actual outside declared: {extras}"])
    return ("diff_scope_static_check", "pass", None)
```

## Artifact hashes

For each input artifact actually consulted (manifest, task_graph, worker_result, optional review_verdict, optional gpp_status):

```python
{"path": str(<repo-relative>), "sha256": "<hex>"}  # 40 char hex per schema $defs.sha256
```

Verifier hashes inputs; does NOT hash its own output (verification_report.v1.json) — that would be a circular reference.

## Test coverage plan

| Test | Cover |
|---|---|
| `test_verify_happy_path_all_checks_pass` | full evidence chain → all_pass + report emitted |
| `test_verify_gpp_guard_violation_in_manifest` | manifest.guard_flags one True → failed_checks |
| `test_verify_gpp_guard_violation_in_worker_result` | worker_result.guard_flags one True → failed_checks |
| `test_verify_gpp_guard_violation_in_task_graph` | task_graph.guard_flags one True → failed_checks |
| `test_verify_gpp_guard_violation_in_review_verdict` | optional review_verdict.guard_flags True → failed_checks |
| `test_verify_gpp_guard_violation_in_gpp_status` | gpp_status allowlist flag True → failed_checks |
| `test_verify_secret_scan_detects_openai_key` | sk- pattern in worker_result.summary → failed_checks + secret_scan.passed=False |
| `test_verify_secret_scan_detects_private_key_block` | BEGIN PRIVATE KEY pattern → failed_checks |
| `test_verify_secret_scan_does_not_flag_sha256_hashes` | sha256:[0-9a-f]{64} stays clean (false-positive defense) |
| `test_verify_secret_scan_does_not_flag_git_sha` | 40-char hex git_sha stays clean |
| `test_verify_secret_scan_secrets_recorded_true_fails` | worker_result.no_secret_attestation.secrets_recorded=True → failed_checks |
| `test_verify_diff_scope_actual_outside_declared` | subset violation → failed_checks |
| `test_verify_diff_scope_declared_mismatch_with_task_graph` | inflation defense |
| `test_verify_diff_scope_happy_path` | clean subset → pass |
| `test_verify_artifact_hashes_h1_format_only` | every entry has only {path, sha256}, no role |
| `test_verify_artifact_hashes_does_not_include_self_report` | no circular reference |
| `test_verify_emit_failure_exits_three` | writer error → exit 3 |
| `test_verify_missing_manifest_exits_two` | trust boundary |
| `test_verify_invalid_worker_result_schema_exits_two` | schema fail |
| `test_verify_cross_provider_violation_exits_two` | verifier.provider == worker_result.worker.provider (same-LLM, e.g., both 'anthropic') |
| `test_verifier_module_has_no_subprocess_import` | HARD RULE static |
| `test_verifier_module_has_no_llm_call_literals` | HARD RULE static |
| `test_verifier_module_has_no_gh_or_git_push_literals` | HARD RULE static |
| `test_verify_no_pr_url_argument_in_cli` | HARD RULE static |
| `test_verify_does_not_modify_ao_ma_5_or_6_modules` | surface preservation |
| `test_cli_verify_happy_path_exits_zero` | end-to-end |
| `test_cli_verify_failed_check_exits_one` | failed_checks present → exit 1 |
| `test_cli_verify_text_format_summary` | human-readable output |
| `test_cli_verify_json_format_full_report` | json output structure |
| `test_verify_commands_use_deterministic_check_names` | Codex iter-1 must_close #5 |
| `test_verify_secret_scan_detail_says_metadata_only` | Codex iter-1 must_close #1 |

Minimum 30 tests.

## Hard stops

- No LLM call
- No `subprocess` import in verifier module (deterministic check)
- No GitHub write
- No PR/GitHub fetch
- No AO-MA-5/6 module edits
- No `gpp_next.py` subprocess (JSON parse only)
- `release_authority` NOT in verification_report.v1 schema (verifier is not authority)
- `guard_flags`: literal false

## Acceptance for AO-MA-7 v1

- ✅ Verifier class implements load → 4 checks → emit pipeline
- ✅ VerificationResult dataclass exposes per-check outcomes
- ✅ CLI subcommand `verify` lands
- ✅ 30+ tests pass (incl. HARD RULE pins, secret scan false-positive defenses, GPP guard 5-source check, diff scope inflation defense, artifact hash H1 format)
- ✅ Codex cross-AI review iter-N AGREE
- ✅ ruff + mypy clean
- ✅ no LLM call / no shell-out / no AO-MA-5/6 edits asserted by tests + plan doc + code review
- ✅ `secret_scan.detail` says "metadata-only, source file content not scanned in v1"
