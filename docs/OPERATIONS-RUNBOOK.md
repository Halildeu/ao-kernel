# Operations Runbook

This document is the operator-facing incident and recovery companion for
`ao-kernel`. It expands the support boundary in
[`PUBLIC-BETA.md`](PUBLIC-BETA.md) into a concrete "what do I do now?"
playbook.

`PUBLIC-BETA.md` remains the normative support matrix. This runbook tells you
how to verify, triage, and stabilize the currently supported surfaces.

## 1. Incident classes

| Class | Trigger | Severity | Immediate effect |
|---|---|---|---|
| Shipped baseline incident | `examples/demo_review.py`, module entrypoints, `ao-kernel doctor`, or packaging smoke fail | Sev 1 | Stop calling the current build "ready" |
| Beta lane incident | `claude-code-cli` or `gh-cli-pr` helper-backed lanes fail while shipped baseline is healthy | Sev 2 | Keep shipped baseline claim; narrow operator guidance if needed |
| Contract/doc drift | Docs, support tier wording, or known-bugs inventory drift from runtime reality | Sev 3 | Fix docs/status before widening support |

## 2. First 5 minutes

Run the following from the repo root or from an environment where
`ao-kernel` is installed:

```bash
ao-kernel version
python -m ao_kernel version
python -m ao_kernel.cli version
ao-kernel doctor
python3 examples/demo_review.py --cleanup
```

If the incident involves an operator-managed real-adapter lane, run the lane's
smoke next:

```bash
python3 scripts/claude_code_cli_smoke.py --output text
python3 scripts/gh_cli_pr_smoke.py --output text
python3 scripts/kernel_api_write_smoke.py --output text
# Optional readiness probe (live-write, explicit opt-in + disposable guard):
# python3 scripts/gh_cli_pr_smoke.py --mode live-write --allow-live-write --head <branch> --base <branch>
```

Prerequisite contract (operator-managed lanes):

1. `claude-code-cli` lane için `claude auth status` tek başına yeterli sinyal
   değildir; karar yalnız `python3 scripts/claude_code_cli_smoke.py --output text`
   içindeki `overall_status` + `prompt_access` sonucuna göre verilir.
2. `gh-cli-pr` preflight için `gh` binary + aktif auth + repo context çözümü
   gerekir; preflight lane side-effect-safe dry-run'dır.
3. `gh-cli-pr` live-write probe için explicit
   `--mode live-write --allow-live-write --head ... --base ...` zorunludur.
4. Varsayılan disposable guard keyword `sandbox`'dır; repo adı keyword'ü
   taşımıyorsa probe bilerek `blocked` döner.
5. `--keep-live-write-pr-open` lane'i riskli kabul ettirir; bu sonucu support
   widening sinyali olarak yorumlama.

`bug_fix_flow` içinde workflow-level `open_pr` side effect'i varsayılan
fail-closed guard ile gelir. `AO_KERNEL_ALLOW_GH_CLI_PR_LIVE_WRITE=1` olmadan
`open_pr` adımında `LIVE_WRITE_NOT_ALLOWED` görmek beklenen davranıştır ve tek
başına incident sayılmaz.

`PRJ-KERNEL-API` write-side lane için helper-backed smoke komutu:

```bash
python3 scripts/kernel_api_write_smoke.py --output text
# Optional: keep artifacts in a fixed workspace for incident inspection
# python3 scripts/kernel_api_write_smoke.py --output json --workspace-root /tmp/kernel-api-write-smoke
```

## 3. Decision tree

### 3.1 Shipped baseline fails

Treat the build as not ready when any of these break:

- `ao-kernel version`
- `python -m ao_kernel version`
- `python -m ao_kernel.cli version`
- `ao-kernel doctor`
- `python3 examples/demo_review.py --cleanup`
- packaging smoke / required CI gates

Actions:

1. Capture exact command output and current commit SHA.
2. Record whether the failure is local-only, CI-only, or both.
3. Check [`ROLLBACK.md`](ROLLBACK.md) if the regression came from a recent
   merge or release.
4. Do not widen support claims until the shipped baseline is green again.

### 3.2 Beta/operator-managed lane fails

If shipped baseline stays green but one of these fails:

- `python3 scripts/claude_code_cli_smoke.py --output text`
- `python3 scripts/gh_cli_pr_smoke.py --output text`
- optional live-write readiness probe (`gh_cli_pr_smoke.py --mode live-write --allow-live-write ...`)
- `PRJ-KERNEL-API` write-side action lane (`project_status`, `roadmap_follow`, `roadmap_finish`)
- operator-run real-adapter benchmark path

Then the shipped baseline claim stays intact, but the operator guidance must
stay narrow. Actions:

1. Confirm the shipped baseline remains healthy.
2. Check [`KNOWN-BUGS.md`](KNOWN-BUGS.md) for an existing entry.
3. If it is new, add it before describing the lane as reliable.
4. Keep the lane in Beta / operator-managed status until a fix is verified.

## 4. Evidence to collect

For any Sev 1 or Sev 2 incident, collect:

- current commit SHA
- exact command(s) run
- stdout/stderr
- `ao-kernel doctor` output
- workflow evidence path if a workflow ran:
  `.ao/evidence/workflows/<run_id>/events.jsonl`
- adapter evidence path if an adapter lane ran:
  `.ao/evidence/workflows/<run_id>/adapter-*.jsonl`

## 5. Exit criteria

An incident is considered closed only when:

1. the relevant smoke or support command is green again,
2. the support boundary is still truthful,
3. the known-bugs registry is updated if the issue remains open but bounded,
4. upgrade / rollback guidance does not contradict the current runtime state.

## 6. Related documents

- [`PUBLIC-BETA.md`](PUBLIC-BETA.md) — release support matrix
- [`SUPPORT-BOUNDARY.md`](SUPPORT-BOUNDARY.md) — narrative support tiers
- [`UPGRADE-NOTES.md`](UPGRADE-NOTES.md) — upgrade checklist
- [`ROLLBACK.md`](ROLLBACK.md) — rollback procedures
- [`KNOWN-BUGS.md`](KNOWN-BUGS.md) — active known-bugs registry
