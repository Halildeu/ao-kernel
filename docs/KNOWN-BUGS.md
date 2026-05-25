# Known Bugs

This registry tracks bounded, operator-relevant issues that are still open.

`PUBLIC-BETA.md` contains the release-facing summary; this file is the fuller
operator registry.

## Current entries

Stable shipped baseline blocker status: **none currently known**.

The open entries below affect operator-managed beta lanes only. They do not
block a narrow stable runtime release unless a future ST gate promotes those
lanes into stable shipped support.

| ID | Surface | Symptom | Workaround | Shipped baseline impact |
|---|---|---|---|---|
| `KB-001` | `claude-code-cli` beta lane | `claude auth status` may report a healthy login while a real `claude -p` prompt call is still denied | Always trust `python3 scripts/claude_code_cli_smoke.py --output text` over `claude auth status` alone; if blocked, re-login the Claude Code session | None; affects operator-managed lane only |
| `KB-002` | `claude-code-cli` fallback token route | The long-lived token path derived from `claude setup-token` has shown `Invalid bearer token` failures in live validation | Prefer session auth; do not treat env-token fallback as the primary recovery path | None; affects fallback auth path only |

## Operational rule

If a bug only affects a beta/operator-managed lane while the shipped baseline
is green, do not silently widen support to cover the broken lane. Update this
registry and keep the support tier narrow until the issue is resolved.

## GP-5.8 promotion interpretation

For GP-5.8, the stable shipped baseline blocker count remains zero. `KB-001`
and `KB-002` are not stable blockers, but they are promotion blockers for any
claim that `claude-code-cli` is production-certified or project-owned. The
following non-bug prerequisites also block a broader GP-5 production claim until
separately closed:

1. protected live adapter gate remains unattested;
2. `claude-code-cli` authentication remains operator-managed;
3. `gh-cli-pr` live-write remains sandbox/disposable only;
4. repo-intelligence context handoff remains explicit and not runtime auto-fed.

Do not resolve these by changing wording alone. They require code path,
behavioral evidence, CI/protected-gate evidence where applicable, and support
boundary updates in the same slice.

## GP-5.9 closeout interpretation

GP-5.9 closes the production platform claim decision as
`keep_narrow_stable_runtime`. This does not add a stable shipped-baseline
blocker, and it does not mark `KB-001` or `KB-002` as shipped-baseline bugs.
They remain promotion blockers for broader claims because the affected lanes are
still beta/operator-managed or sandbox-only.

The following promotion blockers remain non-bug prerequisites rather than
shipped-baseline defects:

1. protected live adapter gate remains unattested;
2. BC-10 real-adapter usage/cost evidence is recorded as `exception` under the
   GPP-3b/GPP-3c policy decision; it is not a shipped-baseline bug and not
   authorization for production certification. Any future promotion still
   requires operator-bound live evidence and explicit GPP supersession;
3. `claude-code-cli` authentication remains operator-managed;
4. `gh-cli-pr` live-write remains sandbox/disposable only;
5. repo-intelligence context handoff remains explicit and not runtime auto-fed.

Future promotion must close these with behavior and protected-gate evidence. A
documentation-only change cannot convert the GP-5.9 non-promotion decision into
a production platform claim.

## GPP-4 closeout interpretation

GPP-4 closes the claude-code-cli read-only adapter production decision as
`keep_operator_beta` (Option Y authoritative). This does not promote
`KB-001` or `KB-002` to shipped-baseline bugs; they remain operator-managed
beta lane known bugs. Both remain promotion-relevant for any future
production-certified read-only claim:

1. `KB-001` (`claude auth status` vs real `claude -p` divergence) — retained
   as `kb001_claude_code_cli_operator_managed_auth` promotion blocker under
   the keep_operator_beta authority;
2. `KB-002` (`claude setup-token` long-lived token failures) — remains an
   operator-managed beta lane known bug; GPP-4c does not remove or rename
   any existing promotion blocker.

Clearing these requires operator-bound live evidence under a separate
Option X supersession slice (three protected clean live runs, one
protected fail-closed live run, `evidence_class=live` failure-mode matrix
artifact), not documentation wording alone.

## GPP-6 closeout interpretation

GPP-6 closes the read-only E2E execution decision as
`keep_rehearsal_only` (Option Y authoritative). This does not
introduce new shipped-baseline bugs or modify existing known bugs.
`KB-001` and `KB-002` remain operator-managed beta lane known bugs
under the GPP-4 `keep_operator_beta` authority (recorded in the
GPP-4 closeout interpretation subsection above). The GPP-6 closeout
preserves the GPP-6a preflight authority over upstream blockers; the
autonomous closure path does not reclassify the preflight
`execution_status` to `ready_for_protected_rehearsal` or remove the
existing GP-5.9 promotion blockers
(`claude_code_cli_auth_operator_managed`,
`kb001_claude_code_cli_operator_managed_auth`,
`protected_live_adapter_gate_unattested`,
`kb002_gh_cli_pr_sandbox_only_live_write`,
`gh_cli_pr_live_write_not_production_promoted`,
`repo_intelligence_context_handoff_not_runtime_auto_fed`).

Clearing those requires operator-bound live evidence under a separate
Option X supersession slice — `authorize_protected_live_e2e` for the
read-only E2E lane (GPP-6 Option X slot), or the GPP-4 Option X slot
for the production-certified read-only tier promotion. Documentation
wording alone does not constitute live evidence.

## Release readiness rule

Before a stable release candidate, this file must answer two questions:

1. Is there any known bug that affects the shipped baseline?
2. If a known bug remains open, is it explicitly outside stable shipped support?

If the answer to the first question is yes, the stable release gate stops until
the bug is fixed or the support boundary is narrowed. If the answer to the
second question is no, update this registry before continuing release work.
