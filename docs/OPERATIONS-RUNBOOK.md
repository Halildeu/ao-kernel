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
# python3 scripts/gh_cli_pr_smoke.py --mode live-write --allow-live-write --repo <owner>/<sandbox-repo> --head <branch> --base <branch>
# Optional: persist canonical JSON evidence artifact
# python3 scripts/gh_cli_pr_smoke.py --mode live-write --allow-live-write --repo <owner>/<sandbox-repo> --head <branch> --base <branch> --output json --report-path /tmp/gh-cli-pr-live-write.report.json
```

`live-adapter-gate` workflow'u (`GP-4.1`/`GP-4.2`) farklı bir yüzeydir: bugün
canlı adapter çalıştırmaz. Manual workflow
`live-adapter-gate-contract.v1.json` ve schema-backed
`live-adapter-gate-evidence.v1.json` artifact'lerini üretir. `GP-4.3` aynı
bundle'a `live-adapter-gate-environment-contract.v1.json` artifact'ini ekler.
`GP-4.4` aynı bundle'a
`live-adapter-gate-rehearsal-decision.v1.json` artifact'ini ekler.
Environment contract artifact'i required protected environment
`ao-kernel-live-adapter-gate` ve secret handle `AO_CLAUDE_CODE_CLI_AUTH`
adlarını kaydeder, ama secret değerlerini okumaz veya yazmaz. Rehearsal
decision artifact'i `decision="blocked_no_rehearsal"` döner. Contract/evidence
artifact'lerinde `finding_code="live_gate_not_implemented"`, environment
contract artifact'inde `finding_code="live_gate_protected_environment_not_attested"`,
rehearsal decision artifact'inde
`finding_code="live_gate_rehearsal_blocked_missing_protected_prerequisites"`
beklenir; hepsi `overall_status="blocked"` / `support_widening=false`
semantiğindedir. Workflow'un yeşil olması production-certified
`claude-code-cli` support anlamına gelmez.
`GP-4.5` closeout kararı `close_no_widening_keep_operator_beta` olduğu için bu
yüzey artık aktif widening gate değil, blocked/no-widening operasyon kaydıdır.

Prerequisite contract (operator-managed lanes):

1. `claude-code-cli` lane için `claude auth status` tek başına yeterli sinyal
   değildir; karar yalnız `python3 scripts/claude_code_cli_smoke.py --output text`
   içindeki `overall_status` + `prompt_access` sonucuna göre verilir.
2. `gh-cli-pr` preflight için `gh` binary + aktif auth + repo context çözümü
   gerekir; preflight lane side-effect-safe dry-run'dır.
3. `gh-cli-pr` live-write probe için explicit
   `--mode live-write --allow-live-write --repo <owner>/<sandbox-repo> --head ... --base ...`
   zorunludur.
4. Varsayılan disposable guard keyword `sandbox`'dır; repo adı keyword'ü
   taşımıyorsa probe bilerek `blocked` döner.
5. `--keep-live-write-pr-open` lane'i riskli kabul ettirir; bu sonucu support
   widening sinyali olarak yorumlama.

Deterministic command/evidence pack (`GP-1.2` live-write rehearsal):

```bash
ARTIFACT_ROOT=/tmp/ao-kernel-gh-cli-pr-live-write
mkdir -p "$ARTIFACT_ROOT"
python3 scripts/gh_cli_pr_smoke.py \
  --mode live-write \
  --allow-live-write \
  --head <feature-branch> \
  --base <target-branch> \
  --output json \
  --report-path "$ARTIFACT_ROOT/gh-cli-pr-live-write.report.json"
```

Bu komut paketi support widening kararı için canonical evidence girdisidir;
`report_path` dosyası issue/PR karar notuna doğrudan bağlanır.

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

### 3.3 Failure-to-command map

Use this table when triaging an operator report. It keeps the first response
aligned with the current support boundary.

| Failure report | First command(s) | Stable impact |
|---|---|---|
| Install or import fails | `python -m pip show ao-kernel`, `ao-kernel version`, `python -m ao_kernel version` | Stable blocker if package install or module entrypoint fails for the shipped channel |
| Demo does not complete | `python3 examples/demo_review.py --cleanup`, then `python3 scripts/packaging_smoke.py` from a checkout | Stable blocker if the installed-package demo fails |
| Doctor reports `FAIL` | `ao-kernel doctor` and capture the JSON/text output | Stable blocker if the failing check is part of the shipped baseline |
| Doctor reports extension truth `WARN` only | `python3 scripts/truth_inventory_ratchet.py --output json` | Not automatically a blocker; compare with `SUPPORT-BOUNDARY.md` |
| Policy/command deny looks wrong | Targeted executor policy tests plus workflow evidence `events.jsonl` | Blocker only if shipped baseline policy contract regresses |
| `claude-code-cli` smoke fails | `python3 scripts/claude_code_cli_smoke.py --output text` | Beta lane incident unless the shipped baseline also fails |
| `gh-cli-pr` smoke fails | `python3 scripts/gh_cli_pr_smoke.py --output text` | Beta/deferred lane incident unless shipped baseline also fails |
| GP-5 controlled patch/test contract fails | Validate `gp5-controlled-patch-test-contract.schema.v1.json` and run `pytest -q tests/test_gp5_controlled_patch_test_contract.py` | Design-gate blocker only; not a stable shipped baseline incident |
| GP-5.5b controlled patch/test rehearsal fails | `python3 scripts/gp5_controlled_patch_test_rehearsal.py --approve-apply --output json` and `pytest -q tests/test_gp5_controlled_patch_test_rehearsal.py` | Rehearsal-gate blocker only; do not widen write-side support |
| GP-5.6a disposable PR write rehearsal fails | Validate `gp5-disposable-pr-write-rehearsal-report.schema.v1.json` and run `pytest -q tests/test_gp5_disposable_pr_write_rehearsal.py` | Remote side-effect rehearsal blocker only; close/delete any sandbox residue before retry |
| GP-5.7a full production rehearsal contract fails | Validate `gp5-full-production-rehearsal-contract.schema.v1.json` and run `pytest -q tests/test_gp5_full_production_rehearsal_contract.py` | Contract-gate blocker only; do not claim production platform readiness |
| Publish or package verification fails | `python3 scripts/packaging_smoke.py`, `twine check dist/*`, post-publish fresh-venv install | Release blocker; do not publish or announce readiness |

### 3.4 GP-5 controlled patch/test rehearsal skeleton

This is a design skeleton, not shipped runtime write support. A future GP-5
controlled patch/test rehearsal must be blocked unless the operator can collect:

1. disposable or dedicated worktree path, with proof it is not the active
   operator `main` worktree;
2. preflight dirty-state output for the target worktree;
3. path-scoped write ownership claim ids and release evidence;
4. diff preview artifact and changed-path list;
5. explicit apply decision record;
6. targeted test commands plus the full-gate fallback decision;
7. reverse-diff rollback artifact;
8. rollback verification and idempotency evidence;
9. cleanup evidence showing the disposable/dedicated worktree was removed or
   intentionally retained for investigation.

If any item is missing, the result is `blocked` for GP-5 support widening. It
does not change the shipped baseline support claim.

### 3.5 GP-5.5b controlled local patch/test rehearsal

`GP-5.5b` provides one deterministic local rehearsal command:

```bash
python3 scripts/gp5_controlled_patch_test_rehearsal.py --approve-apply --output json
```

Expected pass evidence:

1. `gp5_controlled_patch_test_rehearsal_report` validates against
   `gp5-controlled-patch-test-rehearsal-report.schema.v1.json`;
2. `overall_status=pass`;
3. `support_widening=false`;
4. `runtime_patch_support_widening=false`;
5. `remote_side_effects_allowed=false`;
6. `active_main_worktree_touched=false`;
7. `target_worktree.kind=disposable_worktree`;
8. apply and rollback path-scoped claims are present and released;
9. targeted verification and rollback verification pass;
10. rollback idempotency passes;
11. cleanup shows the disposable worktree and temporary root were removed.

Without `--approve-apply`, the command must stop after preview and emit a
schema-valid `blocked` report. That is an expected safety behavior, not a
runtime incident.

This rehearsal does not enable live remote PR creation, arbitrary repository
patching, real-adapter live-write, or production write-side support. Those
remain GP-5.6+ gates.

### 3.6 GP-5.6a disposable PR write rehearsal

`GP-5.6a` is the first bounded remote PR side-effect rehearsal. It must start
from a passing GP-5.5b local patch/test report:

```bash
python3 scripts/gp5_controlled_patch_test_rehearsal.py \
  --approve-apply \
  --output json \
  --report-path /tmp/gp55b-local-patch-report.json
```

Safety path without remote writes:

```bash
python3 scripts/gp5_disposable_pr_write_rehearsal.py \
  --local-patch-report /tmp/gp55b-local-patch-report.json \
  --repo Halildeu/ao-kernel-sandbox \
  --base main \
  --output json \
  --report-path /tmp/gp56a-blocked.json
```

Live sandbox path:

```bash
python3 scripts/gp5_disposable_pr_write_rehearsal.py \
  --local-patch-report /tmp/gp55b-local-patch-report.json \
  --allow-live-write \
  --repo Halildeu/ao-kernel-sandbox \
  --base main \
  --output json \
  --report-path /tmp/gp56a-disposable-pr-write-report.json
```

Expected live pass evidence:

1. `gp5_disposable_pr_write_rehearsal_report` validates against
   `gp5-disposable-pr-write-rehearsal-report.schema.v1.json`;
2. the target repo satisfies the default `sandbox` guard;
3. remote head branch starts with `smoke/gp56a-`;
4. a sandbox branch is created and seeded with one evidence file;
5. `gh-cli-pr` creates a draft PR, verifies it open, and closes it;
6. final PR state verifies as `CLOSED`;
7. remote branch delete verifies;
8. `support_widening=false`, `production_remote_pr_support=false`, and
   `arbitrary_repo_support=false`.

If the rehearsal leaves a sandbox PR or branch behind, close the PR manually
with `gh pr close <url> --repo <owner>/<sandbox-repo>` and delete the branch
with `gh api -X DELETE repos/<owner>/<sandbox-repo>/git/refs/heads/<head>`.
Do not rerun against a production repo to compensate for sandbox failures.

### 3.7 GP-5.7a full production rehearsal contract

`GP-5.7a` is a contract gate, not an executable full rehearsal. Validate the
contract schema and docs boundary before starting GP-5.7b:

```bash
pytest -q tests/test_gp5_full_production_rehearsal_contract.py
```

Expected contract evidence:

1. `gp5_full_production_rehearsal_contract` validates against
   `gp5-full-production-rehearsal-contract.schema.v1.json`;
2. `support_widening=false`;
3. `production_platform_claim=false`;
4. protected real-adapter promotion remains gated on GP-5.1b attestation;
5. GP-5.3e, GP-5.4a, GP-5.5b, and GP-5.6a are referenced as preconditions;
6. the target chain is exactly issue/task -> repo intelligence -> explicit
   context handoff -> adapter reasoning -> patch plan -> controlled patch/test
   -> disposable PR rehearsal -> rollback/closeout;
7. the future execution matrix includes at least three clean rehearsals;
8. the future execution matrix includes at least one fail-closed rehearsal;
9. remote PR rehearsal remains disposable/sandbox-only and rejects arbitrary
   user repositories.

If this contract fails, do not run a best-effort full rehearsal. Fix the
contract or status boundary first, then open GP-5.7b as the execution slice.

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
- helper smoke report artifact path (opsiyonel ama önerilen):
  `--report-path` ile üretilen `gh-cli-pr-live-write.report.json`
- GP-5.6a disposable PR write rehearsal artifact path, if the incident touches
  remote write-side rehearsal:
  `--report-path` ile üretilen
  `gp5-disposable-pr-write-rehearsal-report.json`

## 5. Exit criteria

An incident is considered closed only when:

1. the relevant smoke or support command is green again,
2. the support boundary is still truthful,
3. the known-bugs registry is updated if the issue remains open but bounded,
4. upgrade / rollback guidance does not contradict the current runtime state.

## 6. Release readiness gates

Before a stable release candidate can move forward, the operator must have a
green gate bundle:

1. PR CI: `lint`, Python `test` matrix, `coverage`, `typecheck`,
   `benchmark-fast`, and `packaging-smoke`.
2. Advisory PR surface: `scorecard` should run on pull requests, but it is
   advisory and must not be described as a hard release blocker unless branch
   protection changes.
3. Publish workflow: tag-triggered `publish.yml` must run
   `scripts/packaging_smoke.py`, `twine check dist/*`, and PyPI trusted
   publishing successfully.
4. Post-publish verification: install the exact published version in a fresh
   venv, then run the entrypoint, doctor, and demo commands from section 2.

Merge is not publish. A release is only live after the tag workflow succeeds
and the public package install path is verified.

## 7. Related documents

- [`PUBLIC-BETA.md`](PUBLIC-BETA.md) — release support matrix
- [`SUPPORT-BOUNDARY.md`](SUPPORT-BOUNDARY.md) — narrative support tiers
- [`UPGRADE-NOTES.md`](UPGRADE-NOTES.md) — upgrade checklist
- [`ROLLBACK.md`](ROLLBACK.md) — rollback procedures
- [`KNOWN-BUGS.md`](KNOWN-BUGS.md) — active known-bugs registry
