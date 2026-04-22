# Known Bugs

This registry tracks bounded, operator-relevant issues that are still open.

`PUBLIC-BETA.md` contains the release-facing summary; this file is the fuller
operator registry.

## Current entries

| ID | Surface | Symptom | Workaround | Shipped baseline impact |
|---|---|---|---|---|
| `KB-001` | `claude-code-cli` beta lane | `claude auth status` may report a healthy login while a real `claude -p` prompt call is still denied | Always trust `python3 scripts/claude_code_cli_smoke.py --output text` over `claude auth status` alone; if blocked, re-login the Claude Code session | None; affects operator-managed lane only |
| `KB-002` | `claude-code-cli` fallback token route | The long-lived token path derived from `claude setup-token` has shown `Invalid bearer token` failures in live validation | Prefer session auth; do not treat env-token fallback as the primary recovery path | None; affects fallback auth path only |

## Operational rule

If a bug only affects a beta/operator-managed lane while the shipped baseline
is green, do not silently widen support to cover the broken lane. Update this
registry and keep the support tier narrow until the issue is resolved.
