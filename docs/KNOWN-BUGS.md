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

## Release readiness rule

Before a stable release candidate, this file must answer two questions:

1. Is there any known bug that affects the shipped baseline?
2. If a known bug remains open, is it explicitly outside stable shipped support?

If the answer to the first question is yes, the stable release gate stops until
the bug is fixed or the support boundary is narrowed. If the answer to the
second question is no, update this registry before continuing release work.
